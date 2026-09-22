using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace M365Mcp.Local;

internal sealed class PublicClientAuth(
    LocalConfiguration configuration,
    DpapiStateStore stateStore,
    HttpClient httpClient)
{
    private TokenState? memoryState;

    internal async Task<string> GetAccessTokenAsync(
        bool interactiveAllowed,
        CancellationToken cancellationToken)
    {
        var state = memoryState ?? stateStore.Load();
        if (state?.IsUsable() is true)
        {
            memoryState = state;
            return state.AccessToken;
        }

        if (state is not null)
        {
            try
            {
                state = await RefreshAsync(state, cancellationToken);
                memoryState = state;
                stateStore.Save(state);
                return state.AccessToken;
            }
            catch (LocalAuthException)
            {
                memoryState = null;
            }
        }

        if (!interactiveAllowed)
        {
            throw new LocalAuthException("Interactive sign-in is required.");
        }

        state = await LoginInteractiveAsync(cancellationToken);
        return state.AccessToken;
    }

    internal async Task<TokenState> LoginInteractiveAsync(
        CancellationToken cancellationToken)
    {
        var errors = configuration.Validate();
        if (errors.Count != 0)
        {
            throw new LocalAuthException(errors[0]);
        }

        var verifier = Base64Url(RandomNumberGenerator.GetBytes(64));
        var challenge = Base64Url(SHA256.HashData(Encoding.ASCII.GetBytes(verifier)));
        var expectedState = Base64Url(RandomNumberGenerator.GetBytes(32));
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start(1);
        var port = ((IPEndPoint)listener.LocalEndpoint).Port;
        var redirectUri = $"http://localhost:{port}";
        var authorizationUri = BuildAuthorizationUri(
            redirectUri,
            expectedState,
            challenge);

        try
        {
            Process.Start(new ProcessStartInfo(authorizationUri)
            {
                UseShellExecute = true,
            });
        }
        catch (Exception exception) when (
            exception is InvalidOperationException
            or System.ComponentModel.Win32Exception)
        {
            listener.Stop();
            throw new LocalAuthException("The system browser could not be opened.");
        }

        Console.Error.WriteLine(
            "Microsoft 365 sign-in opened in the system browser; waiting for completion.");

        try
        {
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken);
            timeout.CancelAfter(TimeSpan.FromMinutes(5));
            var callback = await ReceiveCallbackAsync(listener, timeout.Token);
            if (!string.Equals(callback.State, expectedState, StringComparison.Ordinal))
            {
                await WriteBrowserResponseAsync(
                    callback.Client,
                    succeeded: false,
                    cancellationToken);
                throw new LocalAuthException("The sign-in response state was invalid.");
            }

            if (!string.IsNullOrEmpty(callback.Error) || string.IsNullOrEmpty(callback.Code))
            {
                await WriteBrowserResponseAsync(
                    callback.Client,
                    succeeded: false,
                    cancellationToken);
                throw new LocalAuthException("Microsoft 365 sign-in was not completed.");
            }

            try
            {
                var token = await RedeemAuthorizationCodeAsync(
                    callback.Code,
                    redirectUri,
                    verifier,
                    cancellationToken);
                await WriteBrowserResponseAsync(
                    callback.Client,
                    succeeded: true,
                    cancellationToken);
                memoryState = token;
                stateStore.Save(token);
                return token;
            }
            catch
            {
                await WriteBrowserResponseAsync(
                    callback.Client,
                    succeeded: false,
                    cancellationToken);
                throw;
            }
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            throw new LocalAuthException("Microsoft 365 sign-in timed out.");
        }
        finally
        {
            listener.Stop();
        }
    }

    internal JsonObject Status()
    {
        var state = memoryState ?? stateStore.Load();
        return new JsonObject
        {
            ["authenticated"] = state?.IsUsable(0) is true,
            ["expires_at"] = state is null
                ? null
                : DateTimeOffset.FromUnixTimeSeconds(state.ExpiresAtUnixSeconds)
                    .ToString("O"),
            ["user_id"] = state?.UserId,
            ["display_name"] = state?.DisplayName,
            ["user_principal_name"] = state?.UserPrincipalName,
            ["ephemeral"] = configuration.Ephemeral,
        };
    }

    internal void Logout()
    {
        memoryState = null;
        stateStore.Delete();
    }

    internal void InvalidateAccessToken()
    {
        if (memoryState is null)
        {
            return;
        }

        memoryState = memoryState with { ExpiresAtUnixSeconds = 0 };
    }

    private string BuildAuthorizationUri(
        string redirectUri,
        string state,
        string challenge)
    {
        var query = new Dictionary<string, string>
        {
            ["client_id"] = configuration.ClientId,
            ["response_type"] = "code",
            ["redirect_uri"] = redirectUri,
            ["response_mode"] = "query",
            ["scope"] = string.Join(' ', configuration.Scopes),
            ["state"] = state,
            ["code_challenge"] = challenge,
            ["code_challenge_method"] = "S256",
            ["prompt"] = "select_account",
        };
        return $"{configuration.Authority}/authorize?{FormEncode(query)}";
    }

    private async Task<TokenState> RedeemAuthorizationCodeAsync(
        string code,
        string redirectUri,
        string verifier,
        CancellationToken cancellationToken)
    {
        var fields = new Dictionary<string, string>
        {
            ["client_id"] = configuration.ClientId,
            ["grant_type"] = "authorization_code",
            ["code"] = code,
            ["redirect_uri"] = redirectUri,
            ["code_verifier"] = verifier,
            ["scope"] = string.Join(' ', configuration.Scopes),
        };
        return await RequestTokenAsync(fields, null, cancellationToken);
    }

    private async Task<TokenState> RefreshAsync(
        TokenState previous,
        CancellationToken cancellationToken)
    {
        var fields = new Dictionary<string, string>
        {
            ["client_id"] = configuration.ClientId,
            ["grant_type"] = "refresh_token",
            ["refresh_token"] = previous.RefreshToken,
            ["scope"] = string.Join(' ', configuration.Scopes),
        };
        return await RequestTokenAsync(fields, previous, cancellationToken);
    }

    private async Task<TokenState> RequestTokenAsync(
        Dictionary<string, string> fields,
        TokenState? previous,
        CancellationToken cancellationToken)
    {
        using var content = new FormUrlEncodedContent(fields);
        using var response = await httpClient.PostAsync(
            $"{configuration.Authority}/token",
            content,
            cancellationToken);
        var payload = await ReadBoundedAsync(response, 1024 * 1024, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            throw new LocalAuthException(
                response.StatusCode is HttpStatusCode.BadRequest
                    or HttpStatusCode.Unauthorized
                    ? "Microsoft 365 authorization must be renewed."
                    : "Microsoft 365 authorization is temporarily unavailable.");
        }

        try
        {
            using var document = JsonDocument.Parse(payload);
            var root = document.RootElement;
            var accessToken = RequiredString(root, "access_token");
            var refreshToken = OptionalString(root, "refresh_token")
                ?? previous?.RefreshToken
                ?? throw new LocalAuthException(
                    "Microsoft 365 did not return a refresh token.");
            var expiresIn = root.TryGetProperty("expires_in", out var expiry)
                && expiry.TryGetInt64(out var seconds)
                ? seconds
                : 3600;
            return new TokenState(
                accessToken,
                refreshToken,
                DateTimeOffset.UtcNow.ToUnixTimeSeconds() + Math.Max(60, expiresIn),
                configuration.ClientId,
                configuration.TenantId,
                previous?.UserId,
                previous?.DisplayName,
                previous?.UserPrincipalName);
        }
        catch (JsonException)
        {
            throw new LocalAuthException(
                "Microsoft 365 returned an invalid authorization response.");
        }
    }

    private static async Task<BrowserCallback> ReceiveCallbackAsync(
        TcpListener listener,
        CancellationToken cancellationToken)
    {
        var client = await listener.AcceptTcpClientAsync(cancellationToken);
        try
        {
            using var reader = new StreamReader(
                client.GetStream(),
                Encoding.ASCII,
                detectEncodingFromByteOrderMarks: false,
                bufferSize: 4096,
                leaveOpen: true);
            var requestLine = await reader.ReadLineAsync(cancellationToken);
            if (requestLine is null || requestLine.Length > 8192)
            {
                throw new LocalAuthException("The local sign-in callback was invalid.");
            }

            for (var index = 0; index < 100; index++)
            {
                var header = await reader.ReadLineAsync(cancellationToken);
                if (header is null || header.Length == 0)
                {
                    break;
                }
                if (header.Length > 8192)
                {
                    throw new LocalAuthException("The local sign-in callback was invalid.");
                }
            }

            var parts = requestLine.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 2 || parts[0] != "GET")
            {
                throw new LocalAuthException("The local sign-in callback was invalid.");
            }

            var uri = new Uri($"http://localhost{parts[1]}");
            if (uri.AbsolutePath != "/")
            {
                throw new LocalAuthException("The local sign-in callback path was invalid.");
            }

            var query = ParseQuery(uri.Query);
            return new BrowserCallback(
                client,
                query.GetValueOrDefault("code"),
                query.GetValueOrDefault("state"),
                query.GetValueOrDefault("error"));
        }
        catch
        {
            client.Dispose();
            throw;
        }
    }

    private static async Task WriteBrowserResponseAsync(
        TcpClient client,
        bool succeeded,
        CancellationToken cancellationToken)
    {
        using (client)
        {
            var title = succeeded
                ? "Authentication complete / 认证已完成"
                : "Authentication failed / 认证失败";
            var message = succeeded
                ? "You can close this tab and return to your agent. / 可以关闭此标签页并返回 Agent。"
                : "Return to the application and start sign-in again. / 请返回应用重新登录。";
            var body = $"""
                <!doctype html><html lang="en"><head><meta charset="utf-8">
                <meta name="viewport" content="width=device-width,initial-scale=1">
                <title>{title}</title></head><body>
                <main><h1>{title}</h1><p>{message}</p></main>
                <script>setTimeout(() => window.close(), 500);</script>
                </body></html>
                """;
            var bytes = Encoding.UTF8.GetBytes(body);
            var headers = Encoding.ASCII.GetBytes(
                "HTTP/1.1 200 OK\r\n"
                + "Content-Type: text/html; charset=utf-8\r\n"
                + $"Content-Length: {bytes.Length}\r\n"
                + "Cache-Control: no-store\r\n"
                + "Pragma: no-cache\r\n"
                + "Referrer-Policy: no-referrer\r\n"
                + "Content-Security-Policy: default-src 'none'; script-src 'unsafe-inline'; frame-ancestors 'none'\r\n"
                + "Connection: close\r\n\r\n");
            var stream = client.GetStream();
            await stream.WriteAsync(headers, cancellationToken);
            await stream.WriteAsync(bytes, cancellationToken);
            await stream.FlushAsync(cancellationToken);
        }
    }

    private static Dictionary<string, string> ParseQuery(string query)
    {
        var result = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var pair in query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            var separator = pair.IndexOf('=');
            var name = separator < 0 ? pair : pair[..separator];
            var value = separator < 0 ? string.Empty : pair[(separator + 1)..];
            name = Uri.UnescapeDataString(name.Replace('+', ' '));
            value = Uri.UnescapeDataString(value.Replace('+', ' '));
            if (!result.TryAdd(name, value))
            {
                throw new LocalAuthException("The local sign-in callback was invalid.");
            }
        }
        return result;
    }

    private static string FormEncode(IEnumerable<KeyValuePair<string, string>> fields) =>
        string.Join(
            "&",
            fields.Select(field =>
                $"{Uri.EscapeDataString(field.Key)}={Uri.EscapeDataString(field.Value)}"));

    private static string RequiredString(JsonElement root, string name) =>
        OptionalString(root, name)
        ?? throw new LocalAuthException(
            "Microsoft 365 returned an incomplete authorization response.");

    private static string? OptionalString(JsonElement root, string name) =>
        root.TryGetProperty(name, out var property)
        && property.ValueKind == JsonValueKind.String
        ? property.GetString()
        : null;

    private static async Task<byte[]> ReadBoundedAsync(
        HttpResponseMessage response,
        int limit,
        CancellationToken cancellationToken)
    {
        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var output = new MemoryStream();
        var buffer = new byte[16 * 1024];
        while (true)
        {
            var read = await stream.ReadAsync(buffer, cancellationToken);
            if (read == 0)
            {
                return output.ToArray();
            }
            if (output.Length + read > limit)
            {
                throw new LocalAuthException(
                    "Microsoft 365 returned an oversized authorization response.");
            }
            output.Write(buffer, 0, read);
        }
    }

    private static string Base64Url(byte[] value) =>
        Convert.ToBase64String(value).TrimEnd('=').Replace('+', '-').Replace('/', '_');

    private sealed record BrowserCallback(
        TcpClient Client,
        string? Code,
        string? State,
        string? Error);
}
