package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
)

func TestSaveAttachmentBytesMetadataAndLimits(t *testing.T) {
	root := t.TempDir()
	t.Setenv("M365_ATTACHMENT_ROOT", root)
	for _, tc := range []struct {
		id      string
		content []byte
		kind    string
		valid   bool
		limit   string
		header  bool
	}{
		{"binary", []byte{0, 255, 1, 128}, "#microsoft.graph.fileAttachment", true, "", false},
		{"empty", []byte{}, "#microsoft.graph.fileAttachment", true, "", false},
		{"large", make([]byte, 17<<20), "#microsoft.graph.fileAttachment", true, "", false},
		{"limit", make([]byte, 1<<20), "#microsoft.graph.fileAttachment", true, "1", true},
		{"oversized-header", make([]byte, (1<<20)+1), "#microsoft.graph.fileAttachment", false, "1", true},
		{"oversized-stream", make([]byte, (1<<20)+1), "#microsoft.graph.fileAttachment", false, "1", false},
		{"item", []byte("mail item"), "#microsoft.graph.itemAttachment", false, "", false},
	} {
		t.Run(tc.id, func(t *testing.T) {
			t.Setenv("M365_MAX_DOWNLOAD_MIB", tc.limit)
			graph := testGraph(t, func(w http.ResponseWriter, r *http.Request) {
				if strings.HasSuffix(r.URL.Path, "/$value") {
					w.Header().Set("Content-Type", "application/octet-stream")
					if tc.header {
						w.Header().Set("Content-Length", strconv.Itoa(len(tc.content)))
					} else {
						w.(http.Flusher).Flush()
					}
					w.Write(tc.content)
					return
				}
				if r.URL.Query().Get("$select") != "id,name,contentType" {
					t.Error("save must fetch metadata without base64 content")
				}
				json.NewEncoder(w).Encode(map[string]any{
					"@odata.type": tc.kind, "id": "file", "name": "../untrusted.exe", "contentType": "application/octet-stream",
					"size": 99999999,
				})
			})
			service := newMailTools(graph, newDownloads(), slog.New(slog.NewJSONHandler(io.Discard, nil)))
			relative := "downloads/" + tc.id + ".bin"
			args := saveAttachmentInput{MessageID: "message", AttachmentID: "file", RelativePath: relative}
			destinationRoot := root
			if tc.id == "binary" {
				args.DownloadDir = filepath.Join(t.TempDir(), "agent", "override")
				destinationRoot = args.DownloadDir
			}
			result, err := service.saveAttachment(context.Background(), args)
			path := filepath.Join(destinationRoot, filepath.FromSlash(relative))
			if !tc.valid {
				if err == nil {
					t.Fatal("unsupported or oversized attachment was saved")
				}
				if _, err := os.Stat(path); !os.IsNotExist(err) {
					t.Fatal("failed save left a file")
				}
				return
			}
			content, readErr := os.ReadFile(path)
			digest := sha256.Sum256(tc.content)
			if err != nil || readErr != nil || !bytes.Equal(content, tc.content) || result["content_length"] != int64(len(tc.content)) || result["content_sha256"] != hex.EncodeToString(digest[:]) || result["relative_path"] != relative || result["path"] != path || result["saved"] != true || len(result) != 7 {
				t.Fatalf("attachment bytes or common result schema changed: %v %v %v", result, err, readErr)
			}
		})
	}
}

func TestSaveRejectsUnsafePathsAndNeverOverwrites(t *testing.T) {
	root := t.TempDir()
	t.Setenv("M365_ATTACHMENT_ROOT", root)
	save := func(relative string, content []byte) error {
		_, _, _, err := saveLocalAttachment(context.Background(), root, relative, bytes.NewReader(content), 150<<20)
		return err
	}
	for _, relative := range []string{"", "/outside.bin", "../outside.bin", "a/../outside.bin", "a//b.bin", `a\b.bin`, "C:/outside.bin", "file.bin:stream", "file.bin.", "file.bin ", "CON.txt", "COM1.bin", "LPT³.txt", "a\x00.bin", "a?.bin"} {
		if err := save(relative, []byte("unsafe")); err == nil {
			t.Fatalf("accepted unsafe or missing parent path %q", relative)
		}
	}
	outside := t.TempDir()
	if err := os.Symlink(outside, filepath.Join(root, "linked")); err != nil {
		t.Fatal(err)
	}
	if err := save("linked/escaped.bin", []byte("unsafe")); err == nil {
		t.Fatal("followed a parent symbolic link")
	}
	if err := os.Symlink(filepath.Join(outside, "new.bin"), filepath.Join(root, "file-link.bin")); err != nil {
		t.Fatal(err)
	}
	if err := save("file-link.bin", []byte("unsafe")); err == nil {
		t.Fatal("followed a destination symbolic link")
	}
	entries, err := os.ReadDir(outside)
	if err != nil || len(entries) != 0 {
		t.Fatal("save escaped the configured directory")
	}
	var saved atomic.Int32
	var group sync.WaitGroup
	for i := 0; i < 8; i++ {
		group.Go(func() {
			if save("unique.bin", []byte("original")) == nil {
				saved.Add(1)
			}
		})
	}
	group.Wait()
	content, err := os.ReadFile(filepath.Join(root, "unique.bin"))
	if saved.Load() != 1 || err != nil || string(content) != "original" {
		t.Fatal("concurrent saves did not create exactly one intact file")
	}
	if err := save("unique.bin", []byte("replacement")); err == nil {
		t.Fatal("existing file was overwritten")
	}
	content, _ = os.ReadFile(filepath.Join(root, "unique.bin"))
	if string(content) != "original" {
		t.Fatal("rejected save changed the original file")
	}
	if _, _, _, err := saveLocalAttachment(context.Background(), filepath.Join(root, "linked", "new"), "file.bin", strings.NewReader("unsafe"), 100); err == nil {
		t.Fatal("followed a symbolic link while creating a download root")
	}
	if entries, _ := os.ReadDir(outside); len(entries) != 0 {
		t.Fatal("created directories outside the chosen root")
	}
}

func TestDownloadDefaultsOverridesAndLimitConfiguration(t *testing.T) {
	root := t.TempDir()
	t.Setenv("M365_ATTACHMENT_ROOT", root)
	configured, err := downloadDirectory("")
	if err != nil || configured != root {
		t.Fatal("configured directory was not preserved")
	}
	override := filepath.Join(t.TempDir(), "agent", "output")
	resolved, err := downloadDirectory(override)
	if err != nil || resolved != override {
		t.Fatal("Agent directory did not override configured root")
	}
	if _, _, _, err := saveLocalAttachment(context.Background(), resolved, "nested/report.bin", strings.NewReader("saved"), 100); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(resolved, "nested", "report.bin")); err != nil {
		t.Fatal("missing directories were not created")
	}
	t.Setenv("M365_ATTACHMENT_ROOT", "")
	defaultRoot, err := downloadDirectory("")
	if err != nil || !filepath.IsAbs(defaultRoot) || filepath.Base(defaultRoot) != "M365-MCP" {
		t.Fatal("default download directory is unavailable")
	}
	relative := "ci-" + randomToken() + "/default.bin"
	t.Cleanup(func() { os.RemoveAll(filepath.Join(defaultRoot, strings.Split(relative, "/")[0])) })
	if _, _, _, err := saveLocalAttachment(context.Background(), defaultRoot, relative, strings.NewReader("default"), 100); err != nil {
		t.Fatal("default directory could not save a file:", err)
	}
	if _, err := downloadDirectory("relative/path"); err == nil {
		t.Fatal("relative override accepted")
	}
	t.Setenv("M365_MAX_DOWNLOAD_MIB", "")
	if limit, err := downloadLimit(); err != nil || limit != 150<<20 {
		t.Fatal("default limit must be 150 MiB")
	}
	for _, value := range []string{"0", "-1", "x", "1.5", "8796093022208"} {
		t.Setenv("M365_MAX_DOWNLOAD_MIB", value)
		if _, err := downloadLimit(); err == nil {
			t.Fatalf("invalid limit %q accepted", value)
		}
	}
	t.Setenv("M365_MAX_DOWNLOAD_MIB", "512")
	if limit, err := downloadLimit(); err != nil || limit != 512<<20 {
		t.Fatal("configured download limit was not applied")
	}
}

type failedDownload struct{}

func (failedDownload) Read([]byte) (int, error) { return 0, errors.New("PROVIDER_SECRET") }

func TestStreamingFailureAndCancellationRemoveIncompleteFile(t *testing.T) {
	root := t.TempDir()
	input := io.MultiReader(strings.NewReader("partial"), failedDownload{})
	_, _, _, err := saveLocalAttachment(context.Background(), root, "failed.bin", input, 100)
	if err == nil || strings.Contains(err.Error(), "PROVIDER_SECRET") {
		t.Fatal("stream error was not sanitized")
	}
	if _, err := os.Stat(filepath.Join(root, "failed.bin")); !os.IsNotExist(err) {
		t.Fatal("incomplete file was retained")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, _, _, err := saveLocalAttachment(ctx, root, "cancelled.bin", strings.NewReader("unsafe"), 100); err == nil {
		t.Fatal("cancelled save succeeded")
	}
	if _, err := os.Stat(filepath.Join(root, "cancelled.bin")); !os.IsNotExist(err) {
		t.Fatal("cancelled save left an incomplete file")
	}
}
