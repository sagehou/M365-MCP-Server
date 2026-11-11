using System.Text.Json;
using System.Text.Json.Nodes;

namespace M365Mcp.Local;

internal sealed record TokenState(
    string AccessToken,
    string RefreshToken,
    long ExpiresAtUnixSeconds,
    string ClientId,
    string TenantId)
{
    internal bool IsUsable(long minimumLifetimeSeconds = 120) =>
        !string.IsNullOrWhiteSpace(AccessToken)
        && ExpiresAtUnixSeconds > DateTimeOffset.UtcNow.ToUnixTimeSeconds() + minimumLifetimeSeconds;

    internal JsonObject ToJson() => new()
    {
        ["version"] = 2,
        ["access_token"] = AccessToken,
        ["refresh_token"] = RefreshToken,
        ["expires_at"] = ExpiresAtUnixSeconds,
        ["client_id"] = ClientId,
        ["tenant_id"] = TenantId,
    };

    internal static TokenState FromJson(ReadOnlySpan<byte> json)
    {
        var root = JsonNode.Parse(json) as JsonObject
            ?? throw new JsonException("Authentication state is not an object.");
        var version = root["version"]?.GetValue<int>();
        if (version != 2)
        {
            throw new JsonException("Authentication state version is unsupported.");
        }

        var accessToken = root["access_token"]?.GetValue<string>();
        var refreshToken = root["refresh_token"]?.GetValue<string>();
        var expiresAt = root["expires_at"]?.GetValue<long>();
        var clientId = root["client_id"]?.GetValue<string>();
        var tenantId = root["tenant_id"]?.GetValue<string>();
        if (string.IsNullOrWhiteSpace(accessToken)
            || string.IsNullOrWhiteSpace(refreshToken)
            || expiresAt is null or < 0 or > 253402300799
            || string.IsNullOrWhiteSpace(clientId)
            || string.IsNullOrWhiteSpace(tenantId))
        {
            throw new JsonException("Authentication state is incomplete.");
        }

        return new TokenState(
            accessToken,
            refreshToken,
            expiresAt.Value,
            clientId,
            tenantId);
    }
}

internal sealed class LocalAuthException(string message) : Exception(message);
internal sealed class InvalidToolArgumentException(string message) : Exception(message);
internal sealed class GraphOperationException(string message) : Exception(message);
