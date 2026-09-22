using System.Text.Json;
using System.Text.Json.Nodes;

namespace M365Mcp.Local;

internal sealed record TokenState(
    string AccessToken,
    string RefreshToken,
    long ExpiresAtUnixSeconds,
    string? UserId,
    string? DisplayName,
    string? UserPrincipalName)
{
    internal bool IsUsable(long minimumLifetimeSeconds = 120) =>
        !string.IsNullOrWhiteSpace(AccessToken)
        && ExpiresAtUnixSeconds > DateTimeOffset.UtcNow.ToUnixTimeSeconds() + minimumLifetimeSeconds;

    internal JsonObject ToJson() => new()
    {
        ["version"] = 1,
        ["access_token"] = AccessToken,
        ["refresh_token"] = RefreshToken,
        ["expires_at"] = ExpiresAtUnixSeconds,
        ["user_id"] = UserId,
        ["display_name"] = DisplayName,
        ["user_principal_name"] = UserPrincipalName,
    };

    internal static TokenState FromJson(ReadOnlySpan<byte> json)
    {
        var root = JsonNode.Parse(json) as JsonObject
            ?? throw new JsonException("Authentication state is not an object.");
        if (root["version"]?.GetValue<int>() != 1)
        {
            throw new JsonException("Authentication state version is unsupported.");
        }

        var accessToken = root["access_token"]?.GetValue<string>();
        var refreshToken = root["refresh_token"]?.GetValue<string>();
        var expiresAt = root["expires_at"]?.GetValue<long>();
        if (string.IsNullOrWhiteSpace(accessToken)
            || string.IsNullOrWhiteSpace(refreshToken)
            || expiresAt is null)
        {
            throw new JsonException("Authentication state is incomplete.");
        }

        return new TokenState(
            accessToken,
            refreshToken,
            expiresAt.Value,
            root["user_id"]?.GetValue<string>(),
            root["display_name"]?.GetValue<string>(),
            root["user_principal_name"]?.GetValue<string>());
    }
}

internal sealed class LocalAuthException(string message) : Exception(message);
internal sealed class InvalidToolArgumentException(string message) : Exception(message);
internal sealed class GraphOperationException(string message) : Exception(message);
