using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using M365Mcp.Local;

var root = Path.Combine(Path.GetTempPath(), "m365-local-checks-" + Guid.NewGuid());
Directory.CreateDirectory(root);
var oldRoot = Environment.GetEnvironmentVariable("M365_ATTACHMENT_ROOT");
try
{
    Environment.SetEnvironmentVariable("M365_ATTACHMENT_ROOT", root);
    var configuration = new LocalConfiguration(
        LocalConfiguration.BuiltInClientId, "organizations", ["https://graph.microsoft.com/Mail.ReadWrite"],
        Path.Combine(root, "state.bin"), false, false);
    var state = new TokenState("ci-access", "ci-refresh", DateTimeOffset.UtcNow.AddHours(1).ToUnixTimeSeconds(),
        configuration.ClientId, configuration.TenantId);
    var store = new DpapiStateStore(configuration);
    store.Save(state);
    Check(store.Load() == state, "DPAPI state must round-trip");
    Check(new DpapiStateStore(configuration with { TenantId = "common" }).Load() is null,
        "state must be bound to the configured tenant");
    Check(new DpapiStateStore(configuration with { ClientId = Guid.NewGuid().ToString() }).Load() is null,
        "state must be bound to the configured client");
    var ephemeral = new DpapiStateStore(configuration with { Ephemeral = true, StateFile = Path.Combine(root, "ephemeral.bin") });
    ephemeral.Save(state);
    Check(ephemeral.Load() is null && !File.Exists(Path.Combine(root, "ephemeral.bin")), "ephemeral state must stay in memory");

    using var transport = new MockGraph();
    using var client = new HttpClient(transport);
    var auth = new PublicClientAuth(configuration, store, client);
    var graph = new LocalGraphClient(auth, client);
    await File.WriteAllBytesAsync(Path.Combine(root, "report.pdf"), [1, 2, 3, 4]);

    transport.Expect("GET", "/v1.0/me/messages", "{\"value\":[{\"id\":\"message\"}]}", (request, _) =>
    {
        var query = Query(request);
        Check(query["$search"] == "\"(budget) AND received>=2026-01-01T00:00:00Z AND received<=2026-02-01T00:00:00Z\"",
            "keyword/date search must combine KQL terms and normalize timezones");
        Check(!query.ContainsKey("$filter") && !query.ContainsKey("$orderby"), "KQL must not be combined with OData filtering/sorting");
    });
    transport.Expect("GET", "/v1.0/me/messages", "{\"value\":[]}", (request, _) =>
    {
        var query = Query(request);
        Check(!query.ContainsKey("$search") && query["$filter"] == "receivedDateTime ge 2026-01-01T00:00:00Z"
            && query["$orderby"] == "receivedDateTime desc", "date-only search must use OData filtering and received-time order");
    });
    transport.Expect("GET", "/v1.0/me/messages/message", "{\"id\":\"message\",\"body\":{\"content\":\"untrusted\"}}");
    transport.Expect("POST", "/v1.0/me/messages", "{\"id\":\"draft\"}", (_, body) =>
    {
        Check(body?["subject"]?.GetValue<string>() == "Subject" && body["body"]?["contentType"]?.GetValue<string>() == "Text",
            "draft must retain plain-text content");
        Check(body?["toRecipients"]?[0]?["emailAddress"]?["address"]?.GetValue<string>() == "a@example.com", "draft recipient mismatch");
    });
    transport.Expect("POST", "/v1.0/me/messages/draft/send", "", status: HttpStatusCode.Accepted);
    transport.Expect("GET", "/v1.0/me/messages/draft", "{\"id\":\"draft\",\"isDraft\":true}");
    transport.Expect("POST", "/v1.0/me/messages/draft/attachments", "{\"id\":\"attached\"}", (_, body) =>
        Check(body?["contentBytes"]?.GetValue<string>() == "AQIDBA==", "draft attachment bytes changed"));
    transport.Expect("GET", "/v1.0/me/messages/message/attachments", "{\"value\":[{\"id\":\"attachment\",\"contentBytes\":\"c2VjcmV0\"}]}");
    transport.Expect("GET", "/v1.0/me/messages/message/attachments/attachment",
        "{\"id\":\"attachment\",\"name\":\"a.txt\",\"contentType\":\"text/plain\",\"contentBytes\":\"aGVsbG8=\"}");
    transport.Expect("PATCH", "/v1.0/me/messages/message", "{}", (_, body) =>
        Check(body?["isRead"]?.GetValue<bool>() is false, "mark unread must preserve false"));
    transport.Expect("POST", "/v1.0/me/messages/message/move", "{\"id\":\"archived\"}", (_, body) =>
        Check(body?["destinationId"]?.GetValue<string>() == "archive", "archive destination mismatch"));
    transport.Expect("POST", "/v1.0/me/messages/message/move", "{\"id\":\"moved\"}", (_, body) =>
        Check(body?["destinationId"]?.GetValue<string>() == "folder", "move destination mismatch"));
    transport.Expect("PATCH", "/v1.0/me/messages/message", "{}", (_, body) =>
        Check(body?["categories"] is JsonArray { Count: 0 }, "empty categories must clear the existing categories"));

    var results = await Exchange(graph,
        Rpc("initialize"), Rpc("tools/list"),
        Call("mail_search", "{\"query\":\"budget\",\"date_from\":\"2026-01-01T08:00:00+08:00\",\"date_to\":\"2026-02-01T00:00:00Z\"}"),
        Call("mail_search", "{\"date_from\":\"2026-01-01T00:00:00Z\"}"),
        Call("mail_get", "{\"message_id\":\"message\"}"),
        Call("mail_create_draft", "{\"to_recipients\":[\"a@example.com\"],\"subject\":\"Subject\",\"body\":\"Body\\nSecond line\"}"),
        Call("mail_send_draft", "{\"draft_id\":\"draft\"}"),
        Call("mail_add_draft_attachment", "{\"draft_id\":\"draft\",\"relative_path\":\"report.pdf\"}"),
        Call("mail_list_attachments", "{\"message_id\":\"message\"}"),
        Call("mail_read_attachment", "{\"message_id\":\"message\",\"attachment_id\":\"attachment\"}"),
        Call("mail_mark_read", "{\"message_id\":\"message\",\"is_read\":false}"),
        Call("mail_archive", "{\"message_id\":\"message\"}"),
        Call("mail_move", "{\"message_id\":\"message\",\"destination_folder_id\":\"folder\"}"),
        Call("mail_set_category", "{\"message_id\":\"message\",\"categories\":[]}"));
    Check(results[1]["result"]?["tools"] is JsonArray { Count: 11 }, "all eleven tools must be exposed");
    foreach (var result in results.Skip(2))
    {
        Check(result["result"]?["isError"]?.GetValue<bool>() is false, "valid mail tool call failed: " + result);
    }
    Check(Payload(results[6])["delivery_confirmed"]?.GetValue<bool>() is false, "send acceptance must not claim delivery");
    Check(!Payload(results[8]).ToJsonString().Contains("c2VjcmV0"), "attachment listing must omit content bytes");
    Check(Payload(results[9])["content"]?.GetValue<string>() == "hello", "attachment decoding mismatch");
    Check(Payload(results[11])["message_id"]?.GetValue<string>() == "archived"
        && Payload(results[12])["message_id"]?.GetValue<string>() == "moved", "move/archive must return the new Graph ID");
    transport.CheckEmpty();

    foreach (var arguments in new[] {
        "{\"query\":42}", "{\"limit\":\"25\"}", "{\"date_from\":\"2026-01-01T00:00:00\"}",
        "{\"date_from\":\"2026-02-01T00:00:00Z\",\"date_to\":\"2026-01-01T00:00:00Z\"}",
    })
    {
        var invalid = await Exchange(graph, Call("mail_search", arguments), Rpc("ping"));
        Check(invalid[0]["result"]?["isError"]?.GetValue<bool>() is true && invalid[1]["result"] is JsonObject,
            "invalid search must be rejected without stopping stdio");
    }
    foreach (var arguments in new[] {
        "{\"to_recipients\":[\"a@example.com\"],\"cc_recipients\":42,\"subject\":\"S\",\"body\":\"B\"}",
        "{\"to_recipients\":[\"a@b@c\"],\"subject\":\"S\",\"body\":\"B\"}",
        "{\"to_recipients\":[\"a@example.com\"],\"subject\":\"bad\\r\\nsubject\",\"body\":\"B\"}",
        new JsonObject { ["to_recipients"] = new JsonArray("a@example.com"), ["subject"] = new string('a', 256), ["body"] = "B" }.ToJsonString(),
        new JsonObject { ["to_recipients"] = new JsonArray("a@example.com"), ["subject"] = "S", ["body"] = new string('b', 100_001) }.ToJsonString(),
    })
    {
        var invalid = await Exchange(graph, Call("mail_create_draft", arguments));
        Check(invalid[0]["result"]?["isError"]?.GetValue<bool>() is true, "unsafe draft arguments must be rejected");
    }
    var badEnvelopes = await Exchange(graph,
        new JsonObject { ["id"] = 1, ["method"] = "ping" },
        new JsonObject { ["jsonrpc"] = "2.0", ["id"] = new JsonObject(), ["method"] = "ping" },
        new JsonObject { ["jsonrpc"] = "2.0", ["id"] = 1, ["method"] = "tools/call", ["params"] = new JsonArray() }, Rpc("ping"));
    Check(badEnvelopes[0]["error"]?["code"]?.GetValue<int>() == -32600
        && badEnvelopes[1]["error"]?["code"]?.GetValue<int>() == -32600
        && badEnvelopes[2]["error"]?["code"]?.GetValue<int>() == -32602
        && badEnvelopes[3]["result"] is JsonObject, "malformed envelopes must not terminate stdio");

    transport.Expect("GET", "/v1.0/me/messages/message", "[]");
    transport.Expect("POST", "/v1.0/me/messages/message/move", "{\"error\":\"provider-secret\"}", status: HttpStatusCode.ServiceUnavailable);
    var failures = await Exchange(graph, Call("mail_get", "{\"message_id\":\"message\"}"),
        Call("mail_archive", "{\"message_id\":\"message\"}"), Rpc("ping"));
    Check(failures[0]["result"]?["isError"]?.GetValue<bool>() is true
        && failures[1]["result"]?["isError"]?.GetValue<bool>() is true
        && !failures[1].ToJsonString().Contains("provider-secret") && failures[2]["result"] is JsonObject,
        "ambiguous writes must not be replayed or expose provider details");
    transport.CheckEmpty();

    transport.Expect("GET", "/v1.0/me/messages/message", "{}", status: HttpStatusCode.Unauthorized);
    transport.Expect("POST", "/organizations/oauth2/v2.0/token", "{\"access_token\":\"ci-renewed\",\"refresh_token\":\"ci-refresh-2\",\"expires_in\":3600}");
    transport.Expect("GET", "/v1.0/me/messages/message", "{\"id\":\"message\"}");
    var renewed = await Exchange(graph, Call("mail_get", "{\"message_id\":\"message\"}"));
    Check(renewed[0]["result"]?["isError"]?.GetValue<bool>() is false && store.Load()?.AccessToken == "ci-renewed",
        "401 must refresh and persist the new token before retrying");
    transport.CheckEmpty();

    var oversized = new byte[2 * 1024 * 1024 + 1];
    await File.WriteAllBytesAsync(configuration.StateFile, oversized);
    try { store.Load(); throw new Exception("oversized authentication state was accepted"); }
    catch (LocalAuthException) { }
    Console.WriteLine("Windows local checks passed: eleven tools, validation, protocol recovery, DPAPI binding and token refresh.");
}
finally
{
    Environment.SetEnvironmentVariable("M365_ATTACHMENT_ROOT", oldRoot);
    Directory.Delete(root, recursive: true);
}

static void Check(bool condition, string message)
{
    if (!condition) { throw new Exception(message); }
}

static JsonObject Rpc(string method) => new() { ["jsonrpc"] = "2.0", ["id"] = 1, ["method"] = method };
static JsonObject Call(string name, string arguments)
{
    var request = Rpc("tools/call");
    request["params"] = new JsonObject { ["name"] = name, ["arguments"] = JsonNode.Parse(arguments) };
    return request;
}
static JsonNode Payload(JsonObject response) => JsonNode.Parse(response["result"]!["content"]![0]!["text"]!.GetValue<string>())!;
static Dictionary<string, string> Query(HttpRequestMessage request) => request.RequestUri!.Query.TrimStart('?').Split('&')
    .Select(pair => pair.Split('=', 2)).ToDictionary(pair => Uri.UnescapeDataString(pair[0]), pair => Uri.UnescapeDataString(pair[1]));

static async Task<JsonObject[]> Exchange(LocalGraphClient graph, params JsonObject[] requests)
{
    var originalInput = Console.In;
    var originalOutput = Console.Out;
    using var input = new StringReader(string.Join('\n', requests.Select(request => request.ToJsonString())) + "\n");
    using var output = new StringWriter();
    try
    {
        Console.SetIn(input);
        Console.SetOut(output);
        await new StdioMcpServer(graph).RunAsync(CancellationToken.None);
        var results = output.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Select(line => (JsonObject)JsonNode.Parse(line)!).ToArray();
        Check(results.Length == requests.Length, "stdio response count mismatch");
        return results;
    }
    finally
    {
        Console.SetIn(originalInput);
        Console.SetOut(originalOutput);
    }
}

sealed class MockGraph : HttpMessageHandler
{
    private readonly Queue<Func<HttpRequestMessage, Task<HttpResponseMessage>>> requests = new();

    internal void Expect(string method, string path, string response, Action<HttpRequestMessage, JsonNode?>? inspect = null,
        HttpStatusCode status = HttpStatusCode.OK)
    {
        requests.Enqueue(async request =>
        {
            if (request.Method.Method != method || request.RequestUri!.AbsolutePath != path)
            {
                throw new Exception($"Expected {method} {path}; received {request.Method} {request.RequestUri}");
            }
            var isGraph = request.RequestUri.Host == "graph.microsoft.com";
            if (isGraph ? request.Headers.Authorization?.Scheme != "Bearer" : request.Headers.Authorization is not null)
            {
                throw new Exception("Graph bearer token must be present only on Graph requests");
            }
            JsonNode? body = null;
            if (request.Content?.Headers.ContentType?.MediaType == "application/json")
            {
                body = JsonNode.Parse(await request.Content.ReadAsStringAsync());
            }
            inspect?.Invoke(request, body);
            return new HttpResponseMessage(status) { Content = new StringContent(response, Encoding.UTF8, "application/json") };
        });
    }

    internal void CheckEmpty()
    {
        if (requests.Count != 0) { throw new Exception("Expected Graph requests were not issued"); }
    }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
        requests.Count == 0 ? throw new Exception("Unexpected network request: " + request.RequestUri) : requests.Dequeue()(request);
}
