package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
)

func TestSaveAttachmentBytesMetadataAndLimits(t *testing.T) {
	root := t.TempDir()
	t.Setenv("M365_ATTACHMENT_ROOT", root)
	if err := os.Mkdir(filepath.Join(root, "downloads"), 0700); err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		id      string
		content []byte
		kind    string
		valid   bool
	}{
		{"binary", []byte{0, 255, 1, 128}, "#microsoft.graph.fileAttachment", true},
		{"empty", []byte{}, "#microsoft.graph.fileAttachment", true},
		{"limit", make([]byte, maxAttachmentBytes), "#microsoft.graph.fileAttachment", true},
		{"oversized", make([]byte, maxAttachmentBytes+1), "#microsoft.graph.fileAttachment", false},
		{"item", []byte("mail item"), "#microsoft.graph.itemAttachment", false},
	} {
		t.Run(tc.id, func(t *testing.T) {
			graph := testGraph(t, func(w http.ResponseWriter, r *http.Request) {
				json.NewEncoder(w).Encode(map[string]any{
					"@odata.type": tc.kind, "id": "file", "name": "../untrusted.exe", "contentType": "application/octet-stream",
					"size": 99999999, "contentBytes": base64.StdEncoding.EncodeToString(tc.content),
				})
			})
			service := newMailTools(graph, newDownloads(), slog.New(slog.NewJSONHandler(io.Discard, nil)))
			relative := "downloads/" + tc.id + ".bin"
			result, err := service.saveAttachment(context.Background(), saveAttachmentInput{"message", "file", relative})
			path := filepath.Join(root, filepath.FromSlash(relative))
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
			if err != nil || readErr != nil || !bytes.Equal(content, tc.content) || result["content_length"] != len(tc.content) || result["content_sha256"] != hex.EncodeToString(digest[:]) || result["relative_path"] != relative || result["saved"] != true || len(result) != 6 {
				t.Fatalf("attachment bytes or common result schema changed: %v %v %v", result, err, readErr)
			}
		})
	}
}

func TestSaveRejectsUnsafePathsAndNeverOverwrites(t *testing.T) {
	root := t.TempDir()
	t.Setenv("M365_ATTACHMENT_ROOT", root)
	for _, relative := range []string{"", "/outside.bin", "../outside.bin", "a/../outside.bin", "a//b.bin", `a\b.bin`, "C:/outside.bin", "file.bin:stream", "file.bin.", "file.bin ", "CON.txt", "COM1.bin", "LPT³.txt", "a\x00.bin", "a?.bin", "missing/file.bin"} {
		if err := saveLocalAttachment(relative, []byte("unsafe")); err == nil {
			t.Fatalf("accepted unsafe or missing parent path %q", relative)
		}
	}
	outside := t.TempDir()
	if err := os.Symlink(outside, filepath.Join(root, "linked")); err != nil {
		t.Fatal(err)
	}
	if err := saveLocalAttachment("linked/escaped.bin", []byte("unsafe")); err == nil {
		t.Fatal("followed a parent symbolic link")
	}
	if err := os.Symlink(filepath.Join(outside, "new.bin"), filepath.Join(root, "file-link.bin")); err != nil {
		t.Fatal(err)
	}
	if err := saveLocalAttachment("file-link.bin", []byte("unsafe")); err == nil {
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
			if saveLocalAttachment("unique.bin", []byte("original")) == nil {
				saved.Add(1)
			}
		})
	}
	group.Wait()
	content, err := os.ReadFile(filepath.Join(root, "unique.bin"))
	if saved.Load() != 1 || err != nil || string(content) != "original" {
		t.Fatal("concurrent saves did not create exactly one intact file")
	}
	if err := saveLocalAttachment("unique.bin", []byte("replacement")); err == nil {
		t.Fatal("existing file was overwritten")
	}
	content, _ = os.ReadFile(filepath.Join(root, "unique.bin"))
	if string(content) != "original" {
		t.Fatal("rejected save changed the original file")
	}
	t.Setenv("M365_ATTACHMENT_ROOT", "")
	if err := saveLocalAttachment("no-root.bin", []byte("unsafe")); err == nil {
		t.Fatal("save did not require an operator-configured directory")
	}
}
