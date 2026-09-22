using System.Net;
using System.Text;
using System.Text.Json.Nodes;

namespace M365Mcp.Local;

internal static class Program
{
    internal static async Task<int> Main(string[] args)
    {
        Console.InputEncoding = new UTF8Encoding(false);
        Console.OutputEncoding = new UTF8Encoding(false);

        var ephemeral = args.Any(
            argument => argument.Equals("--ephemeral", StringComparison.OrdinalIgnoreCase));
        var command = args.FirstOrDefault(argument => !argument.StartsWith("--", StringComparison.Ordinal))
            ?? "help";
        var configuration = LocalConfiguration.Load(ephemeral);
        using var cancellation = new CancellationTokenSource();
        Console.CancelKeyPress += (_, eventArgs) =>
        {
            eventArgs.Cancel = true;
            cancellation.Cancel();
        };

        try
        {
            if (command is "help" or "--help" or "-h")
            {
                WriteHelp();
                return 0;
            }
            if (command is "version" or "--version")
            {
                Console.WriteLine("m365-mcp 0.1.0");
                return 0;
            }
            if (command == "doctor")
            {
                var result = configuration.DoctorResult();
                Console.WriteLine(result.ToJsonString());
                return result["ok"]?.GetValue<bool>() is true ? 0 : 2;
            }

            var validationErrors = configuration.Validate();
            if (validationErrors.Count != 0)
            {
                Console.Error.WriteLine(validationErrors[0]);
                return 2;
            }

            using var handler = new HttpClientHandler
            {
                AutomaticDecompression =
                    DecompressionMethods.GZip
                    | DecompressionMethods.Deflate
                    | DecompressionMethods.Brotli,
                UseCookies = false,
            };
            using var httpClient = new HttpClient(handler)
            {
                Timeout = TimeSpan.FromSeconds(100),
            };
            var store = new DpapiStateStore(configuration);
            var auth = new PublicClientAuth(configuration, store, httpClient);

            switch (command)
            {
                case "login":
                {
                    var state = await auth.LoginInteractiveAsync(cancellation.Token);
                    Console.WriteLine(new JsonObject
                    {
                        ["authenticated"] = true,
                        ["expires_at"] = DateTimeOffset
                            .FromUnixTimeSeconds(state.ExpiresAtUnixSeconds)
                            .ToString("O"),
                        ["ephemeral"] = ephemeral,
                    }.ToJsonString());
                    return 0;
                }
                case "logout":
                    auth.Logout();
                    Console.WriteLine(new JsonObject
                    {
                        ["authenticated"] = false,
                        ["state_removed"] = !ephemeral,
                    }.ToJsonString());
                    return 0;
                case "status":
                    Console.WriteLine(auth.Status().ToJsonString());
                    return 0;
                case "stdio":
                {
                    var graph = new LocalGraphClient(auth, httpClient);
                    var server = new StdioMcpServer(graph);
                    await server.RunAsync(cancellation.Token);
                    return 0;
                }
                default:
                    Console.Error.WriteLine($"Unknown command '{command}'.");
                    WriteHelp(Console.Error);
                    return 2;
            }
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
            return 130;
        }
        catch (Exception exception) when (
            exception is LocalAuthException
            or HttpRequestException
            or TaskCanceledException)
        {
            Console.Error.WriteLine(exception.Message);
            return 1;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(
                $"Unexpected local runtime failure ({exception.GetType().Name}).");
            return 1;
        }
    }

    private static void WriteHelp(TextWriter? writer = null)
    {
        writer ??= Console.Out;
        writer.WriteLine(
            """
            M365 MCP Server - Windows local runtime

            Usage:
              m365-mcp.exe doctor [--ephemeral]
              m365-mcp.exe login [--ephemeral]
              m365-mcp.exe status [--ephemeral]
              m365-mcp.exe logout [--ephemeral]
              m365-mcp.exe stdio [--ephemeral]
              m365-mcp.exe version

            Required environment:
              M365_LOCAL_CLIENT_ID=<public desktop application id>

            Optional environment:
              M365_LOCAL_TENANT_ID=<tenant id or organizations>
              M365_LOCAL_GRAPH_SCOPES=<space/comma-separated delegated scopes>

            stdio writes only MCP JSON-RPC messages to stdout. Diagnostics use stderr.
            Normal execution never installs a service or startup entry.
            """);
    }
}
