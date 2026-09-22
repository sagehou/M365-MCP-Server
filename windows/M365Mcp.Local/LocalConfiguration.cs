using System.Text.Json.Nodes;

namespace M365Mcp.Local;

internal sealed record LocalConfiguration(
    string ClientId,
    string TenantId,
    IReadOnlyList<string> Scopes,
    string StateFile,
    bool Ephemeral,
    bool ClientIdOverridden)
{
    internal const string BuiltInClientId = "6e35216e-2623-43cc-b867-83bec0865cf3";

    private static readonly string[] DefaultScopes =
    [
        "openid",
        "profile",
        "offline_access",
        "https://graph.microsoft.com/User.Read",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Mail.Send",
    ];

    internal string Authority =>
        $"https://login.microsoftonline.com/{Uri.EscapeDataString(TenantId)}/oauth2/v2.0";

    internal static LocalConfiguration Load(bool ephemeral)
    {
        var localAppData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData);
        var stateFile = Path.Combine(localAppData, "M365-MCP-Server", "state.bin");
        var rawClientId = Environment.GetEnvironmentVariable("M365_LOCAL_CLIENT_ID");
        var clientIdOverridden = !string.IsNullOrWhiteSpace(rawClientId);
        var rawScopes = Environment.GetEnvironmentVariable("M365_LOCAL_GRAPH_SCOPES");
        var scopes = string.IsNullOrWhiteSpace(rawScopes)
            ? DefaultScopes
            : rawScopes
                .Split([',', ' ', ';'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Distinct(StringComparer.Ordinal)
                .ToArray();

        return new LocalConfiguration(
            clientIdOverridden ? rawClientId!.Trim() : BuiltInClientId,
            (Environment.GetEnvironmentVariable("M365_LOCAL_TENANT_ID") ?? "organizations").Trim(),
            scopes,
            stateFile,
            ephemeral,
            clientIdOverridden);
    }

    internal IReadOnlyList<string> Validate()
    {
        var errors = new List<string>();
        if (!Guid.TryParse(ClientId, out var clientId) || clientId == Guid.Empty)
        {
            errors.Add("M365_LOCAL_CLIENT_ID must be a non-empty application GUID.");
        }

        if (!IsTenant(TenantId))
        {
            errors.Add(
                "M365_LOCAL_TENANT_ID must be a tenant GUID or organizations/common/consumers.");
        }

        if (Scopes.Count == 0)
        {
            errors.Add("M365_LOCAL_GRAPH_SCOPES must contain at least one delegated scope.");
        }

        if (Scopes.Any(scope => scope.Contains('\r') || scope.Contains('\n')))
        {
            errors.Add("M365_LOCAL_GRAPH_SCOPES contains an invalid line break.");
        }

        return errors;
    }

    internal JsonObject DoctorResult()
    {
        var errors = Validate();
        return new JsonObject
        {
            ["ok"] = errors.Count == 0,
            ["runtime"] = "windows-native-aot",
            ["architecture"] = System.Runtime.InteropServices.RuntimeInformation.ProcessArchitecture.ToString(),
            ["ephemeral"] = Ephemeral,
            ["state_file"] = Ephemeral ? null : StateFile,
            ["client_id"] = ClientId,
            ["client_id_configured"] = Guid.TryParse(ClientId, out var id) && id != Guid.Empty,
            ["client_id_source"] = ClientIdOverridden ? "environment" : "built_in",
            ["tenant"] = TenantId,
            ["errors"] = new JsonArray(errors.Select(error => (JsonNode?)error).ToArray()),
        };
    }

    private static bool IsTenant(string value) =>
        value is "organizations" or "common" or "consumers"
        || (Guid.TryParse(value, out var tenantId) && tenantId != Guid.Empty);
}
