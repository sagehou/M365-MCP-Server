using System.Runtime.InteropServices;

namespace M365Mcp.Local;

internal static class NativeFilePicker
{
    private const uint FileMustExist = 0x00001000;
    private const uint PathMustExist = 0x00000800;
    private const uint NoChangeDirectory = 0x00000008;
    private const uint ExplorerStyle = 0x00080000;
    private const int PathBufferChars = 32768;

    internal static Task<string?> SelectFileAsync(CancellationToken cancellationToken)
    {
        var completion = new TaskCompletionSource<string?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var thread = new Thread(() =>
        {
            try
            {
                completion.TrySetResult(SelectFile());
            }
            catch (Exception exception)
            {
                completion.TrySetException(exception);
            }
        }) { IsBackground = true };
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        return completion.Task.WaitAsync(cancellationToken);
    }

    private static string? SelectFile()
    {
        var pathBuffer = Marshal.AllocHGlobal(PathBufferChars * sizeof(char));
        var filter = Marshal.StringToHGlobalUni("All files\0*.*\0\0");
        var title = Marshal.StringToHGlobalUni("Select an attachment for the draft");
        try
        {
            Marshal.WriteInt16(pathBuffer, 0);
            var dialog = new OpenFileName
            {
                StructSize = (uint)Marshal.SizeOf<OpenFileName>(),
                Filter = filter,
                FilterIndex = 1,
                File = pathBuffer,
                MaxFile = PathBufferChars,
                Title = title,
                Flags = FileMustExist | PathMustExist | NoChangeDirectory | ExplorerStyle,
            };
            if (!GetOpenFileNameW(ref dialog))
            {
                if (CommDlgExtendedError() == 0)
                {
                    return null;
                }
                throw new GraphOperationException("Windows file selection failed.");
            }
            return Marshal.PtrToStringUni(pathBuffer)
                ?? throw new GraphOperationException("Windows file selection returned no path.");
        }
        finally
        {
            Marshal.FreeHGlobal(title);
            Marshal.FreeHGlobal(filter);
            Marshal.FreeHGlobal(pathBuffer);
        }
    }

    [DllImport("comdlg32.dll", EntryPoint = "GetOpenFileNameW", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetOpenFileNameW(ref OpenFileName dialog);

    [DllImport("comdlg32.dll", EntryPoint = "CommDlgExtendedError")]
    private static extern uint CommDlgExtendedError();

    [StructLayout(LayoutKind.Sequential)]
    private struct OpenFileName
    {
        public uint StructSize;
        public nint Owner;
        public nint Instance;
        public nint Filter;
        public nint CustomFilter;
        public uint MaxCustomFilter;
        public uint FilterIndex;
        public nint File;
        public uint MaxFile;
        public nint FileTitle;
        public uint MaxFileTitle;
        public nint InitialDirectory;
        public nint Title;
        public uint Flags;
        public ushort FileOffset;
        public ushort FileExtension;
        public nint DefaultExtension;
        public nint CustomData;
        public nint Hook;
        public nint TemplateName;
        public nint Reserved;
        public uint ReservedFlags;
        public uint FlagsEx;
    }
}
