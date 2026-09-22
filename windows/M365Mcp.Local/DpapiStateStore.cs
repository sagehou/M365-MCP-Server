using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;

namespace M365Mcp.Local;

internal sealed class DpapiStateStore(LocalConfiguration configuration)
{
    private static readonly byte[] Magic = Encoding.ASCII.GetBytes("M365MCP1");

    internal TokenState? Load()
    {
        if (configuration.Ephemeral || !File.Exists(configuration.StateFile))
        {
            return null;
        }

        try
        {
            var envelope = File.ReadAllBytes(configuration.StateFile);
            if (envelope.Length <= Magic.Length
                || !envelope.AsSpan(0, Magic.Length).SequenceEqual(Magic))
            {
                throw new LocalAuthException(
                    "Stored authentication state is unreadable; run logout and login again.");
            }

            var plaintext = Dpapi.Unprotect(envelope.AsSpan(Magic.Length).ToArray());
            try
            {
                var state = TokenState.FromJson(plaintext);
                return string.Equals(
                        state.ClientId,
                        configuration.ClientId,
                        StringComparison.OrdinalIgnoreCase)
                    && string.Equals(
                        state.TenantId,
                        configuration.TenantId,
                        StringComparison.OrdinalIgnoreCase)
                    ? state
                    : null;
            }
            finally
            {
                CryptographicOperations.ZeroMemory(plaintext);
            }
        }
        catch (LocalAuthException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is IOException
            or UnauthorizedAccessException
            or System.Text.Json.JsonException
            or Win32Exception)
        {
            throw new LocalAuthException(
                "Stored authentication state is unreadable; run logout and login again.");
        }
    }

    internal void Save(TokenState state)
    {
        if (configuration.Ephemeral)
        {
            return;
        }

        var directory = Path.GetDirectoryName(configuration.StateFile)
            ?? throw new LocalAuthException("The authentication state path is invalid.");
        Directory.CreateDirectory(directory);
        var plaintext = Encoding.UTF8.GetBytes(state.ToJson().ToJsonString());
        try
        {
            var protectedBytes = Dpapi.Protect(plaintext);
            var envelope = new byte[Magic.Length + protectedBytes.Length];
            Magic.CopyTo(envelope, 0);
            protectedBytes.CopyTo(envelope, Magic.Length);
            File.WriteAllBytes(configuration.StateFile, envelope);
            CryptographicOperations.ZeroMemory(protectedBytes);
            CryptographicOperations.ZeroMemory(envelope);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or Win32Exception)
        {
            throw new LocalAuthException("Authentication state could not be saved.");
        }
        finally
        {
            CryptographicOperations.ZeroMemory(plaintext);
        }
    }

    internal void Delete()
    {
        if (configuration.Ephemeral)
        {
            return;
        }

        try
        {
            File.Delete(configuration.StateFile);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            throw new LocalAuthException("Authentication state could not be removed.");
        }
    }
}

internal static class Dpapi
{
    private const int CryptProtectUiForbidden = 0x1;
    private static readonly byte[] Entropy =
        Encoding.UTF8.GetBytes("M365-MCP-Server/windows-local/state/v1");

    internal static byte[] Protect(byte[] plaintext) =>
        Transform(plaintext, protect: true);

    internal static byte[] Unprotect(byte[] ciphertext) =>
        Transform(ciphertext, protect: false);

    private static byte[] Transform(byte[] inputBytes, bool protect)
    {
        var input = CreateBlob(inputBytes);
        var entropy = CreateBlob(Entropy);
        DataBlob output = default;
        try
        {
            var succeeded = protect
                ? CryptProtectData(
                    ref input,
                    null,
                    ref entropy,
                    IntPtr.Zero,
                    IntPtr.Zero,
                    CryptProtectUiForbidden,
                    out output)
                : CryptUnprotectData(
                    ref input,
                    IntPtr.Zero,
                    ref entropy,
                    IntPtr.Zero,
                    IntPtr.Zero,
                    CryptProtectUiForbidden,
                    out output);
            if (!succeeded)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            var result = new byte[output.Size];
            Marshal.Copy(output.Data, result, 0, output.Size);
            return result;
        }
        finally
        {
            if (input.Data != IntPtr.Zero)
            {
                Marshal.FreeHGlobal(input.Data);
            }
            if (entropy.Data != IntPtr.Zero)
            {
                Marshal.FreeHGlobal(entropy.Data);
            }
            if (output.Data != IntPtr.Zero)
            {
                LocalFree(output.Data);
            }
        }
    }

    private static DataBlob CreateBlob(byte[] value)
    {
        var pointer = Marshal.AllocHGlobal(value.Length);
        Marshal.Copy(value, 0, pointer, value.Length);
        return new DataBlob { Size = value.Length, Data = pointer };
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct DataBlob
    {
        internal int Size;
        internal IntPtr Data;
    }

    [DllImport("crypt32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CryptProtectData(
        ref DataBlob dataIn,
        string? description,
        ref DataBlob optionalEntropy,
        IntPtr reserved,
        IntPtr prompt,
        int flags,
        out DataBlob dataOut);

    [DllImport("crypt32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CryptUnprotectData(
        ref DataBlob dataIn,
        IntPtr description,
        ref DataBlob optionalEntropy,
        IntPtr reserved,
        IntPtr prompt,
        int flags,
        out DataBlob dataOut);

    [DllImport("kernel32.dll")]
    private static extern IntPtr LocalFree(IntPtr memory);
}
