using System.Net;
using System.Net.Http.Headers;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using Microsoft.Win32.SafeHandles;

namespace M365Mcp.Local;

internal sealed class AttachmentPushClient
{
    private const int MaxBytes = 20 * 1024 * 1024;
    private readonly string root;
    private readonly Uri pushUri;

    internal AttachmentPushClient()
    {
        root = RequireRoot();
        var configuredUrl = Environment.GetEnvironmentVariable("M365_ATTACHMENT_PUSH_URL");
        if (!Uri.TryCreate(configuredUrl, UriKind.Absolute, out var uri)
            || uri.Scheme != Uri.UriSchemeHttps
            || !string.IsNullOrEmpty(uri.UserInfo)
            || !string.IsNullOrEmpty(uri.Query)
            || !string.IsNullOrEmpty(uri.Fragment)
            || uri.AbsolutePath != "/uploads/push")
        {
            throw new InvalidToolArgumentException(
                "M365_ATTACHMENT_PUSH_URL must be the trusted HTTPS /uploads/push endpoint");
        }
        pushUri = uri;
    }

    internal static FileStream OpenLocalArtifact(
        string relativePath, out string name, out string contentType) =>
        OpenBoundedFile(RequireRoot(), relativePath, out name, out contentType);

    internal static string[] SavePathSegments(string relativePath)
    {
        if (string.IsNullOrEmpty(relativePath) || Encoding.UTF8.GetByteCount(relativePath) > 1024
            || relativePath.Any(character => char.IsControl(character) || "<>:\"\\|?*".Contains(character)))
        {
            throw new InvalidToolArgumentException("use a new relative file path with forward slashes under M365_ATTACHMENT_ROOT");
        }
        var parts = relativePath.Split('/');
        foreach (var part in parts)
        {
            var stem = part.Split('.')[0].TrimEnd(' ').ToUpperInvariant();
            if (part is "" or "." or ".." || part.TrimEnd(' ', '.') != part
                || part.EnumerateRunes().Count() > 255
                || stem is "CON" or "PRN" or "AUX" or "NUL" or "CONIN$" or "CONOUT$"
                || (stem.Length == 4 && (stem.StartsWith("COM", StringComparison.Ordinal)
                    || stem.StartsWith("LPT", StringComparison.Ordinal)) && "123456789¹²³".Contains(stem[3])))
            {
                throw new InvalidToolArgumentException("relative_path contains an invalid Windows path segment");
            }
        }
        return parts;
    }

    internal static void SaveLocalArtifact(string relativePath, byte[] content)
    {
        var parts = SavePathSegments(relativePath);
        var current = RequireRoot();
        var directories = new List<SafeFileHandle>();
        try
        {
            // Pin every parent without write/delete sharing before creating the file.
            for (var index = 0; index < parts.Length; index++)
            {
                if (index > 0)
                {
                    current = Path.Combine(current, parts[index - 1]);
                }
                var handle = CreateFileW(current, 0, FileShare.Read, IntPtr.Zero,
                    FileMode.Open, 0x02000000 | 0x00200000, IntPtr.Zero);
                directories.Add(handle);
                if (handle.IsInvalid
                    || (File.GetAttributes(current) & (FileAttributes.Directory | FileAttributes.ReparsePoint)) != FileAttributes.Directory)
                {
                    throw new InvalidToolArgumentException("attachment root and parent directories must exist and must not be symbolic links or junctions");
                }
                current = FinalPath(handle);
            }
            var destination = Path.Combine(current, parts[^1]);
            var created = false;
            var saved = false;
            try
            {
                // OPEN_REPARSE_POINT keeps CREATE_NEW from following a dangling file link.
                using (var handle = CreateFileW(destination, 0x40000000, FileShare.None, IntPtr.Zero,
                    FileMode.CreateNew, 0x00200000, IntPtr.Zero))
                {
                    if (handle.IsInvalid)
                    {
                        throw new IOException("Cannot create attachment destination");
                    }
                    created = true;
                    using var file = new FileStream(handle, FileAccess.Write);
                    file.Write(content);
                    file.Flush(flushToDisk: true);
                }
                saved = true;
            }
            catch (IOException) when (!created && File.Exists(destination))
            {
                throw new InvalidToolArgumentException("destination already exists; choose a new filename");
            }
            finally
            {
                if (created && !saved)
                {
                    File.Delete(destination);
                }
            }
        }
        finally
        {
            for (var index = directories.Count - 1; index >= 0; index--)
            {
                directories[index].Dispose();
            }
        }
    }

    internal JsonObject Inspect(string relativePath)
    {
        using var file = OpenBoundedFile(root, relativePath, out var name, out var contentType);
        var digest = SHA256.HashData(file);
        return Metadata(name, contentType, file.Length, Convert.ToHexString(digest).ToLowerInvariant());
    }

    internal async Task<JsonObject> PushAsync(
        string relativePath,
        JsonObject grant,
        CancellationToken cancellationToken)
    {
        var handle = RequiredString(grant, "upload_handle");
        var name = RequiredString(grant, "name");
        var expectedHash = RequiredString(grant, "content_sha256");
        var expectedType = RequiredString(grant, "content_type");
        var grantedUrl = RequiredString(grant, "upload_url");
        if (!Uri.TryCreate(grantedUrl, UriKind.Absolute, out var grantedUri)
            || grantedUri != pushUri
            || handle.Length != 43
            || handle.Any(character => !char.IsAsciiLetterOrDigit(character) && character is not '_' and not '-')
            || expectedHash.Length != 64
            || expectedHash.Any(character => !Uri.IsHexDigit(character)))
        {
            throw new InvalidToolArgumentException("upload grant does not match the configured endpoint");
        }
        if (grant["content_length"] is not JsonValue lengthNode
            || !lengthNode.TryGetValue<int>(out var expectedLength)
            || expectedLength is < 1 or > MaxBytes)
        {
            throw new InvalidToolArgumentException("upload grant has an invalid content_length");
        }

        using var file = OpenBoundedFile(root, relativePath, out var actualName, out var actualType);
        if (file.Length != expectedLength || actualName != name || actualType != expectedType)
        {
            throw new InvalidToolArgumentException("file metadata does not match the upload grant");
        }
        var bytes = new byte[expectedLength];
        await file.ReadExactlyAsync(bytes, cancellationToken);
        var actualHash = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        if (!actualHash.Equals(expectedHash, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidToolArgumentException("file SHA-256 does not match the upload grant");
        }

        try
        {
            using var handler = new HttpClientHandler
            {
                AllowAutoRedirect = false,
                UseCookies = false,
                AutomaticDecompression = DecompressionMethods.None,
            };
            using var client = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(120) };
            using var request = new HttpRequestMessage(HttpMethod.Post, pushUri);
            request.Headers.Add("X-Upload-Handle", handle);
            request.Content = new ByteArrayContent(bytes);
            request.Content.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
            using var response = await client.SendAsync(request, cancellationToken);
            if (response.StatusCode != HttpStatusCode.Created)
            {
                throw new HttpRequestException($"Attachment push failed with HTTP {(int)response.StatusCode}");
            }
            if (response.Content.Headers.ContentLength is > 4096)
            {
                throw new HttpRequestException("Attachment push response exceeds the size limit");
            }
            using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
            using var buffer = new MemoryStream();
            var chunk = new byte[4097];
            while (true)
            {
                var count = await stream.ReadAsync(chunk, cancellationToken);
                if (count == 0)
                {
                    break;
                }
                if (buffer.Length + count > 4096)
                {
                    throw new HttpRequestException("Attachment push response exceeds the size limit");
                }
                buffer.Write(chunk, 0, count);
            }
            var result = JsonNode.Parse(Encoding.UTF8.GetString(buffer.ToArray())) as JsonObject;
            if (result is null
                || RequiredString(result, "upload_handle") != handle
                || RequiredString(result, "name") != actualName
                || RequiredString(result, "content_type") != actualType
                || RequiredString(result, "content_sha256") != actualHash
                || result["content_length"] is not JsonValue resultLength
                || !resultLength.TryGetValue<int>(out var actualLength)
                || actualLength != expectedLength)
            {
                throw new HttpRequestException("Attachment push response did not match the uploaded file");
            }
            return Metadata(actualName, actualType, expectedLength, actualHash);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(bytes);
        }
    }

    private static string RequireRoot()
    {
        var configuredRoot = Environment.GetEnvironmentVariable("M365_ATTACHMENT_ROOT");
        if (string.IsNullOrWhiteSpace(configuredRoot) || !Path.IsPathFullyQualified(configuredRoot))
        {
            throw new InvalidToolArgumentException(
                "M365_ATTACHMENT_ROOT must be an absolute, operator-controlled directory");
        }
        if (!Directory.Exists(configuredRoot))
        {
            throw new InvalidToolArgumentException("M365_ATTACHMENT_ROOT does not exist");
        }
        return Path.GetFullPath(configuredRoot);
    }

    private static FileStream OpenBoundedFile(
        string root,
        string relativePath,
        out string name,
        out string contentType)
    {
        if (string.IsNullOrWhiteSpace(relativePath)
            || relativePath.Length > 1024
            || relativePath.Any(char.IsControl)
            || Path.IsPathRooted(relativePath)
            || relativePath.Split(['/', '\\']).Any(part => part is "" or "." or ".." || part.Contains(':')))
        {
            throw new InvalidToolArgumentException("attachment path must be relative to M365_ATTACHMENT_ROOT");
        }
        name = Path.GetFileName(relativePath);
        contentType = Path.GetExtension(name).ToLowerInvariant() switch
        {
            ".docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx" => "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".pptx" => "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".zip" => "application/zip",
            ".pdf" => "application/pdf",
            _ => throw new InvalidToolArgumentException("attachment extension is not allowed"),
        };
        string path;
        try
        {
            path = Path.GetFullPath(Path.Combine(root, relativePath));
        }
        catch (ArgumentException)
        {
            throw new InvalidToolArgumentException("attachment path is invalid");
        }
        var file = new FileStream(
            path, FileMode.Open, FileAccess.Read, FileShare.Read,
            64 * 1024, FileOptions.Asynchronous | FileOptions.SequentialScan);
        try
        {
            var rootPath = FinalDirectoryPath(root);
            var filePath = FinalPath(file.SafeFileHandle);
            if (!filePath.StartsWith(rootPath.TrimEnd('\\') + "\\", StringComparison.OrdinalIgnoreCase)
                || file.Length is < 1 or > MaxBytes)
            {
                throw new InvalidToolArgumentException(
                    "attachment must be a non-empty file of at most 20 MiB inside M365_ATTACHMENT_ROOT");
            }
            return file;
        }
        catch
        {
            file.Dispose();
            throw;
        }
    }

    private static string FinalDirectoryPath(string path)
    {
        using var handle = CreateFileW(
            path, 0, FileShare.ReadWrite | FileShare.Delete, IntPtr.Zero,
            FileMode.Open, 0x02000000, IntPtr.Zero);
        if (handle.IsInvalid)
        {
            throw new IOException("Cannot open attachment root");
        }
        return FinalPath(handle);
    }

    private static string FinalPath(SafeFileHandle handle)
    {
        var buffer = new StringBuilder(32768);
        var length = GetFinalPathNameByHandleW(handle, buffer, (uint)buffer.Capacity, 0);
        if (length == 0 || length >= buffer.Capacity)
        {
            throw new IOException("Cannot resolve attachment path");
        }
        return buffer.ToString();
    }

    private static string RequiredString(JsonObject value, string name) =>
        value[name] is JsonValue node && node.TryGetValue<string>(out var text)
            && !string.IsNullOrWhiteSpace(text)
            ? text
            : throw new InvalidToolArgumentException($"upload grant is missing {name}");

    private static JsonObject Metadata(string name, string contentType, long length, string sha256) => new()
    {
        ["name"] = name,
        ["content_type"] = contentType,
        ["content_length"] = length,
        ["content_sha256"] = sha256,
    };

    [DllImport("kernel32.dll", EntryPoint = "CreateFileW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFileW(
        string fileName, uint desiredAccess, FileShare shareMode, IntPtr securityAttributes,
        FileMode creationDisposition, uint flagsAndAttributes, IntPtr templateFile);

    [DllImport("kernel32.dll", EntryPoint = "GetFinalPathNameByHandleW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetFinalPathNameByHandleW(
        SafeFileHandle file, StringBuilder path, uint pathLength, uint flags);
}
