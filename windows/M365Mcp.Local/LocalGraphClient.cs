using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace M365Mcp.Local;

internal sealed class LocalGraphClient(
    PublicClientAuth auth,
    HttpClient httpClient)
{
    private const string GraphBase = "https://graph.microsoft.com/v1.0";
    private const int MaxResponseBytes = 16 * 1024 * 1024;
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    internal Task<JsonNode> SearchAsync(
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        var query = OptionalString(arguments, "query") ?? string.Empty;
        var limit = OptionalInt(arguments, "limit") ?? 25;
        if (limit is < 1 or > 50)
        {
            throw new InvalidToolArgumentException("limit must be between 1 and 50");
        }

        var dateFrom = OptionalTimestamp(arguments, "date_from");
        var dateTo = OptionalTimestamp(arguments, "date_to");
        if (dateFrom is not null && dateTo is not null && dateFrom > dateTo)
        {
            throw new InvalidToolArgumentException("date_from must not be after date_to");
        }

        var parameters = new List<KeyValuePair<string, string>>
        {
            new("$top", limit.ToString(System.Globalization.CultureInfo.InvariantCulture)),
            new("$select", "id,subject,from,toRecipients,ccRecipients,receivedDateTime,isRead,hasAttachments,bodyPreview"),
        };
        if (!string.IsNullOrWhiteSpace(query))
        {
            var escaped = query.Replace("\\", "\\\\").Replace("\"", "\\\"");
            parameters.Add(new("$search", $"\"{escaped}\""));
        }

        var filters = new List<string>();
        if (dateFrom is not null)
        {
            filters.Add($"receivedDateTime ge {dateFrom.Value.UtcDateTime:O}");
        }
        if (dateTo is not null)
        {
            filters.Add($"receivedDateTime le {dateTo.Value.UtcDateTime:O}");
        }
        if (filters.Count != 0)
        {
            parameters.Add(new("$filter", string.Join(" and ", filters)));
        }

        return RequestAsync(
            HttpMethod.Get,
            $"/me/messages?{EncodeQuery(parameters)}",
            null,
            cancellationToken);
    }

    internal async Task<JsonNode> GetMessageAsync(
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        var messageId = RequiredString(arguments, "message_id");
        return await RequestAsync(
            HttpMethod.Get,
            $"/me/messages/{Segment(messageId)}"
            + "?%24select=id,subject,from,toRecipients,ccRecipients,bccRecipients,"
            + "receivedDateTime,sentDateTime,isRead,hasAttachments,body,bodyPreview,categories",
            null,
            cancellationToken);
    }

    internal async Task<JsonNode> CreateDraftAsync(
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        var body = new JsonObject
        {
            ["subject"] = RequiredString(arguments, "subject"),
            ["body"] = new JsonObject
            {
                ["contentType"] = "Text",
                ["content"] = RequiredString(arguments, "body"),
            },
            ["toRecipients"] = Recipients(arguments, "to_recipients", required: true),
            ["ccRecipients"] = Recipients(arguments, "cc_recipients", required: false),
            ["bccRecipients"] = Recipients(arguments, "bcc_recipients", required: false),
        };
        var response = await RequestAsync(
            HttpMethod.Post,
            "/me/messages",
            body,
            cancellationToken);
        var identifier = response["id"]?.GetValue<string>();
        if (string.IsNullOrWhiteSpace(identifier))
        {
            throw new GraphOperationException("Draft response did not contain an id.");
        }
        return new JsonObject
        {
            ["draft_id"] = identifier,
            ["created"] = true,
        };
    }

    internal async Task<JsonNode> SendDraftAsync(
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        var draftId = RequiredString(arguments, "draft_id");
        await RequestAsync(
            HttpMethod.Post,
            $"/me/messages/{Segment(draftId)}/send",
            new JsonObject(),
            cancellationToken);
        return new JsonObject
        {
            ["draft_id"] = draftId,
            ["send_accepted"] = true,
            ["delivery_confirmed"] = false,
        };
    }

    internal Task<JsonNode> ListAttachmentsAsync(
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        var messageId = RequiredString(arguments, "message_id");
        return RequestAsync(
            HttpMethod.Get,
            $"/me/messages/{Segment(messageId)}/attachments",
            null,
            cancellationToken);
    }

    internal async Task<JsonNode> ReadAttachmentAsync(
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        var messageId = RequiredString(arguments, "message_id");
        var attachmentId = RequiredString(arguments, "attachment_id");
        var attachment = await RequestAsync(
            HttpMethod.Get,
            $"/me/messages/{Segment(messageId)}/attachments/{Segment(attachmentId)}",
            null,
            cancellationToken) as JsonObject
            ?? throw new GraphOperationException("Attachment response was invalid.");

        var type = attachment["@odata.type"]?.GetValue<string>();
        if (type is not null
            && !type.EndsWith("fileAttachment", StringComparison.OrdinalIgnoreCase))
        {
            throw new GraphOperationException(
                "Only Outlook file attachments can be read locally.");
        }

        var encoded = attachment["contentBytes"]?.GetValue<string>();
        if (string.IsNullOrWhiteSpace(encoded)
            || encoded.Length > 4 * ((10 * 1024 * 1024 + 2) / 3))
        {
            throw new GraphOperationException(
                "Attachment content is unavailable or exceeds the 10 MiB limit.");
        }

        byte[] bytes;
        try
        {
            bytes = Convert.FromBase64String(encoded);
        }
        catch (FormatException)
        {
            throw new GraphOperationException("Attachment content was invalid.");
        }

        if (bytes.Length > 10 * 1024 * 1024)
        {
            throw new GraphOperationException("Attachment exceeds the 10 MiB limit.");
        }

        var contentType = attachment["contentType"]?.GetValue<string>()
            ?? "application/octet-stream";
        if (!IsTextContent(contentType))
        {
            throw new GraphOperationException(
                "This local preview currently supports text, JSON, CSV, and XML attachments.");
        }

        string text;
        try
        {
            text = StrictUtf8.GetString(bytes);
        }
        catch (DecoderFallbackException)
        {
            throw new GraphOperationException("Attachment is not valid UTF-8 text.");
        }

        var truncated = text.Length > 100_000;
        if (truncated)
        {
            text = text[..100_000];
        }

        return new JsonObject
        {
            ["attachment"] = new JsonObject
            {
                ["id"] = attachment["id"]?.GetValue<string>() ?? attachmentId,
                ["name"] = attachment["name"]?.GetValue<string>() ?? "attachment",
                ["content_type"] = contentType,
                ["content_length"] = bytes.Length,
                ["format"] = "text",
                ["truncated"] = truncated,
            },
            ["content"] = text,
            ["content_metadata"] = new JsonObject
            {
                ["trusted"] = false,
                ["source"] = "email_attachment",
            },
        };
    }

    internal async Task<JsonNode> MarkReadAsync(
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        var messageId = RequiredString(arguments, "message_id");
        var isRead = arguments["is_read"]?.GetValue<bool>() ?? true;
        await RequestAsync(
            HttpMethod.Patch,
            $"/me/messages/{Segment(messageId)}",
            new JsonObject { ["isRead"] = isRead },
            cancellationToken);
        return new JsonObject
        {
            ["message_id"] = messageId,
            ["is_read"] = isRead,
        };
    }

    internal Task<JsonNode> ArchiveAsync(
        JsonObject arguments,
        CancellationToken cancellationToken) =>
        MoveCoreAsync(arguments, "archive", archived: true, cancellationToken);

    internal Task<JsonNode> MoveAsync(
        JsonObject arguments,
        CancellationToken cancellationToken) =>
        MoveCoreAsync(
            arguments,
            RequiredString(arguments, "destination_folder_id"),
            archived: false,
            cancellationToken);

    internal async Task<JsonNode> SetCategoryAsync(
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        var messageId = RequiredString(arguments, "message_id");
        var categories = StringArray(arguments, "categories", required: true);
        await RequestAsync(
            HttpMethod.Patch,
            $"/me/messages/{Segment(messageId)}",
            new JsonObject { ["categories"] = categories },
            cancellationToken);
        return new JsonObject
        {
            ["message_id"] = messageId,
            ["categories"] = categories.DeepClone(),
        };
    }

    private async Task<JsonNode> MoveCoreAsync(
        JsonObject arguments,
        string destination,
        bool archived,
        CancellationToken cancellationToken)
    {
        var messageId = RequiredString(arguments, "message_id");
        var moved = await RequestAsync(
            HttpMethod.Post,
            $"/me/messages/{Segment(messageId)}/move",
            new JsonObject { ["destinationId"] = destination },
            cancellationToken);
        var newId = moved["id"]?.GetValue<string>();
        if (string.IsNullOrWhiteSpace(newId))
        {
            throw new GraphOperationException("Move response did not contain an id.");
        }

        var result = new JsonObject
        {
            ["message_id"] = newId,
            ["source_message_id"] = messageId,
        };
        if (archived)
        {
            result["archived"] = true;
        }
        else
        {
            result["destination_folder_id"] = destination;
        }
        return result;
    }

    private async Task<JsonNode> RequestAsync(
        HttpMethod method,
        string path,
        JsonNode? body,
        CancellationToken cancellationToken)
    {
        if (!path.StartsWith("/me", StringComparison.Ordinal)
            || path.Contains("..", StringComparison.Ordinal))
        {
            throw new GraphOperationException("The Graph path was rejected.");
        }

        for (var attempt = 0; attempt < 2; attempt++)
        {
            using var request = new HttpRequestMessage(method, GraphBase + path);
            var token = await auth.GetAccessTokenAsync(
                interactiveAllowed: true,
                cancellationToken);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
            if (body is not null)
            {
                request.Content = new StringContent(
                    body.ToJsonString(),
                    Encoding.UTF8,
                    "application/json");
            }

            using var response = await httpClient.SendAsync(
                request,
                HttpCompletionOption.ResponseHeadersRead,
                cancellationToken);
            if (response.StatusCode == HttpStatusCode.Unauthorized && attempt == 0)
            {
                auth.InvalidateAccessToken();
                continue;
            }

            var payload = await ReadBoundedAsync(response, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                var requestId = response.Headers.TryGetValues("request-id", out var values)
                    ? values.FirstOrDefault()
                    : null;
                throw new GraphOperationException(
                    $"Microsoft Graph rejected the operation"
                    + (string.IsNullOrWhiteSpace(requestId) ? "." : $" (request {requestId})."));
            }

            if (payload.Length == 0)
            {
                return new JsonObject();
            }

            try
            {
                return JsonNode.Parse(payload)
                    ?? new JsonObject();
            }
            catch (JsonException)
            {
                throw new GraphOperationException(
                    "Microsoft Graph returned an invalid response.");
            }
        }

        throw new GraphOperationException("Microsoft Graph authorization failed.");
    }

    private static async Task<byte[]> ReadBoundedAsync(
        HttpResponseMessage response,
        CancellationToken cancellationToken)
    {
        await using var input = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var output = new MemoryStream();
        var buffer = new byte[16 * 1024];
        while (true)
        {
            var read = await input.ReadAsync(buffer, cancellationToken);
            if (read == 0)
            {
                return output.ToArray();
            }
            if (output.Length + read > MaxResponseBytes)
            {
                throw new GraphOperationException(
                    "Microsoft Graph response exceeds the 16 MiB limit.");
            }
            output.Write(buffer, 0, read);
        }
    }

    private static JsonArray Recipients(
        JsonObject arguments,
        string name,
        bool required)
    {
        var values = StringArray(arguments, name, required);
        var recipients = new JsonArray();
        foreach (var value in values)
        {
            var address = value?.GetValue<string>()
                ?? throw new InvalidToolArgumentException($"{name} contains an invalid value");
            if (address.Length > 320 || !address.Contains('@'))
            {
                throw new InvalidToolArgumentException($"{name} contains an invalid address");
            }
            recipients.Add((JsonNode?)new JsonObject
            {
                ["emailAddress"] = new JsonObject { ["address"] = address },
            });
        }
        return recipients;
    }

    private static JsonArray StringArray(
        JsonObject arguments,
        string name,
        bool required)
    {
        if (arguments[name] is not JsonArray source)
        {
            if (!required)
            {
                return new JsonArray();
            }
            throw new InvalidToolArgumentException($"{name} must be an array");
        }
        if (required && source.Count == 0)
        {
            throw new InvalidToolArgumentException($"{name} must not be empty");
        }
        if (source.Count > 100)
        {
            throw new InvalidToolArgumentException($"{name} contains too many values");
        }

        var result = new JsonArray();
        foreach (var item in source)
        {
            var value = item?.GetValue<string>()?.Trim();
            if (string.IsNullOrEmpty(value))
            {
                throw new InvalidToolArgumentException($"{name} contains an empty value");
            }
            result.Add((JsonNode?)value);
        }
        return result;
    }

    private static string RequiredString(JsonObject arguments, string name)
    {
        var value = OptionalString(arguments, name);
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidToolArgumentException($"{name} is required");
        }
        if (value.Length > 1_000_000)
        {
            throw new InvalidToolArgumentException($"{name} is too long");
        }
        return value;
    }

    private static string? OptionalString(JsonObject arguments, string name) =>
        arguments[name] is JsonValue value && value.TryGetValue<string>(out var result)
            ? result
            : null;

    private static int? OptionalInt(JsonObject arguments, string name) =>
        arguments[name] is JsonValue value && value.TryGetValue<int>(out var result)
            ? result
            : null;

    private static DateTimeOffset? OptionalTimestamp(JsonObject arguments, string name)
    {
        var value = OptionalString(arguments, name);
        if (value is null)
        {
            return null;
        }
        if (!DateTimeOffset.TryParse(
            value,
            System.Globalization.CultureInfo.InvariantCulture,
            System.Globalization.DateTimeStyles.RoundtripKind,
            out var result))
        {
            throw new InvalidToolArgumentException(
                $"{name} must be an ISO 8601 timestamp with a timezone");
        }
        return result;
    }

    private static string Segment(string value) => Uri.EscapeDataString(value);

    private static string EncodeQuery(IEnumerable<KeyValuePair<string, string>> values) =>
        string.Join(
            "&",
            values.Select(pair =>
                $"{Uri.EscapeDataString(pair.Key)}={Uri.EscapeDataString(pair.Value)}"));

    private static bool IsTextContent(string contentType)
    {
        var mediaType = contentType.Split(';', 2)[0].Trim();
        return mediaType.StartsWith("text/", StringComparison.OrdinalIgnoreCase)
            || mediaType.Equals("application/json", StringComparison.OrdinalIgnoreCase)
            || mediaType.Equals("application/xml", StringComparison.OrdinalIgnoreCase)
            || mediaType.EndsWith("+json", StringComparison.OrdinalIgnoreCase)
            || mediaType.EndsWith("+xml", StringComparison.OrdinalIgnoreCase);
    }
}
