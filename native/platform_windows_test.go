package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
	"unsafe"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"golang.org/x/sys/windows"
)

func TestMain(m *testing.M) {
	if os.Getenv("M365_TEST_COMMAND") == "1" {
		if err := run(os.Args[1:]); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		os.Exit(0)
	}
	if len(os.Args) > 1 && os.Args[1] == "extract-worker" {
		if os.Getenv("M365_SECRET_TEST") != "" {
			os.Exit(2)
		}
		if runExtractionWorker() != nil {
			os.Exit(1)
		}
		os.Exit(0)
	}
	os.Exit(m.Run())
}

func TestWindowsStdioConnectionWithConsumerAccount(t *testing.T) {
	t.Setenv("LOCALAPPDATA", t.TempDir())
	t.Setenv("M365_ATTACHMENT_ROOT", "")
	dir, err := stateDirectory()
	if err != nil {
		t.Fatal(err)
	}
	config := localConfig{ClientID: builtInClientID, Tenant: "consumers", AccountID: "ci-consumer-account", HTTPToken: strings.Repeat("a", 64)}
	data, err := json.Marshal(config)
	if err != nil {
		t.Fatal(err)
	}
	if err := saveProtected(filepath.Join(dir, "settings.dpapi"), data); err != nil {
		t.Fatal(err)
	}
	stored, err := loadConfig(dir)
	if err != nil || stored != config {
		t.Fatalf("consumer account configuration did not round-trip: %v", err)
	}
	executable, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	command := exec.CommandContext(ctx, executable, "connection")
	command.Env = append(os.Environ(), "M365_TEST_COMMAND=1")
	output, err := command.Output()
	if err != nil {
		t.Fatalf("connection command failed: %v", err)
	}
	var connection struct {
		Servers map[string]struct {
			Command string   `json:"command"`
			Args    []string `json:"args"`
		} `json:"mcpServers"`
	}
	if err := json.Unmarshal(output, &connection); err != nil {
		t.Fatal(err)
	}
	entry := connection.Servers["m365"]
	if entry.Command != executable || len(entry.Args) != 1 || entry.Args[0] != "stdio" {
		t.Fatalf("connection did not generate the stdio command: %s", output)
	}
	if bytes.Contains(output, []byte(config.HTTPToken)) || bytes.Contains(output, []byte(config.AccountID)) {
		t.Fatal("stdio configuration exposed account credentials")
	}
	command = exec.CommandContext(ctx, entry.Command, entry.Args...)
	command.Env = append(os.Environ(), "M365_TEST_COMMAND=1")
	client := mcp.NewClient(&mcp.Implementation{Name: "windows-cli-check", Version: "1"}, nil)
	session, err := client.Connect(ctx, &mcp.CommandTransport{Command: command}, nil)
	if err != nil {
		t.Fatalf("generated stdio configuration could not initialize MCP: %v", err)
	}
	defer session.Close()
	listed, err := session.ListTools(ctx, nil)
	if err != nil || len(listed.Tools) != 12 {
		t.Fatalf("stdio did not expose all twelve tools: %v %v", listed, err)
	}
}

func TestWindowsProtectedStorageAndProcessLock(t *testing.T) {
	dir := t.TempDir()
	if err := protectDirectory(dir); err != nil {
		t.Fatal(err)
	}
	descriptor, err := windows.GetNamedSecurityInfo(dir, windows.SE_FILE_OBJECT, windows.DACL_SECURITY_INFORMATION)
	if err != nil {
		t.Fatal(err)
	}
	user, err := windows.GetCurrentProcessToken().GetTokenUser()
	if err != nil {
		t.Fatal(err)
	}
	dacl, _, err := descriptor.DACL()
	if err != nil || dacl == nil || dacl.AceCount != 1 {
		t.Fatalf("credential directory must have exactly one explicit grant: %s (%v)", descriptor.String(), err)
	}
	control, _, err := descriptor.Control()
	if err != nil || control&windows.SE_DACL_PROTECTED == 0 {
		t.Fatalf("credential directory inherits permissions: %s (%v)", descriptor.String(), err)
	}
	var ace *windows.ACCESS_ALLOWED_ACE
	if err := windows.GetAce(dacl, 0, &ace); err != nil {
		t.Fatal(err)
	}
	// SDDL may abbreviate a built-in account's SID. Compare the actual SID bytes.
	grantedSID := (*windows.SID)(unsafe.Pointer(&ace.SidStart))
	if ace.Header.AceType != windows.ACCESS_ALLOWED_ACE_TYPE || !grantedSID.Equals(user.User.Sid) {
		t.Fatalf("credential directory grants access beyond the current user: %s", descriptor.String())
	}
	plain := []byte("test refresh credential")
	path := filepath.Join(dir, "cache.dpapi")
	if err := saveProtected(path, plain); err != nil {
		t.Fatal(err)
	}
	onDisk, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(onDisk, plain) {
		t.Fatal("credentials were stored in plaintext")
	}
	decoded, err := loadProtected(path)
	if err != nil || !bytes.Equal(decoded, plain) {
		t.Fatal("DPAPI round trip failed")
	}
	if err := saveProtected(path, []byte("rotated credential")); err != nil {
		t.Fatal("could not atomically replace the encrypted cache")
	}
	if updated, err := loadProtected(path); err != nil || string(updated) != "rotated credential" {
		t.Fatal("cache rotation was not persisted")
	}
	onDisk[len(onDisk)-1] ^= 1
	if _, err := unprotectData(onDisk); err == nil {
		t.Fatal("accepted tampered DPAPI data")
	}
	unlock, err := lockState(dir)
	if err != nil {
		t.Fatal(err)
	}
	if release, err := lockState(dir); err == nil {
		release()
		unlock()
		t.Fatal("two processes can own the same account")
	}
	unlock()
	unlock, err = lockState(dir)
	if err != nil {
		t.Fatal("process lock was not released")
	}
	unlock()
}

func TestWindowsIsolatedAttachmentWorker(t *testing.T) {
	t.Setenv("M365_SECRET_TEST", "must not reach parser")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	result, err := isolatedExtraction(ctx, fileAttachment{Name: "notes.txt", Content: []byte("isolated hello")})
	if err != nil || result.Content != "isolated hello" {
		t.Fatalf("Windows worker failed: %+v %v", result, err)
	}
	if _, err := isolatedExtraction(ctx, fileAttachment{Name: "invalid.pdf", Content: []byte("not a pdf")}); err == nil {
		t.Fatal("worker accepted invalid PDF")
	}
}
