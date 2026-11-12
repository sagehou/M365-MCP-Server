package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"unicode"
	"unicode/utf8"
)

type saveAttachmentInput struct {
	MessageID    string `json:"message_id" jsonschema:"Outlook message ID"`
	AttachmentID string `json:"attachment_id" jsonschema:"Outlook attachment ID"`
	RelativePath string `json:"relative_path" jsonschema:"New file under M365_ATTACHMENT_ROOT; use forward slashes and existing parent directories; never overwrites"`
}

func savePathSegments(relative string) ([]string, error) {
	invalid := inputError{"relative_path", "invalid_path", "use a new relative file path with forward slashes under M365_ATTACHMENT_ROOT"}
	if relative == "" || len(relative) > 1024 || strings.ContainsAny(relative, "<>:\"\\|?*") || strings.ContainsFunc(relative, unicode.IsControl) {
		return nil, invalid
	}
	parts := strings.Split(relative, "/")
	for _, part := range parts {
		if part == "" || part == "." || part == ".." || strings.TrimRight(part, " .") != part || utf8.RuneCountInString(part) > 255 {
			return nil, invalid
		}
		stem := strings.ToUpper(strings.TrimRight(strings.SplitN(part, ".", 2)[0], " "))
		if stem == "CON" || stem == "PRN" || stem == "AUX" || stem == "NUL" || stem == "CONIN$" || stem == "CONOUT$" ||
			(utf8.RuneCountInString(stem) == 4 && (strings.HasPrefix(stem, "COM") || strings.HasPrefix(stem, "LPT")) && strings.ContainsRune("123456789¹²³", []rune(stem)[3])) {
			return nil, invalid
		}
	}
	return parts, nil
}

func saveLocalAttachment(relative string, content []byte) error {
	parts, err := savePathSegments(relative)
	if err != nil {
		return err
	}
	rootPath := os.Getenv("M365_ATTACHMENT_ROOT")
	if !filepath.IsAbs(rootPath) {
		return inputError{"relative_path", "root_not_configured", "set M365_ATTACHMENT_ROOT to an absolute operator-controlled directory"}
	}
	info, err := os.Lstat(rootPath)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return inputError{"relative_path", "invalid_root", "M365_ATTACHMENT_ROOT must be an existing directory without a symbolic link or junction"}
	}
	root, err := os.OpenRoot(rootPath)
	if err != nil {
		return errors.New("could not open the configured attachment root")
	}
	defer func() { root.Close() }()
	for _, part := range parts[:len(parts)-1] {
		info, err := root.Lstat(part)
		if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
			return inputError{"relative_path", "invalid_parent", "parent directories must already exist and must not be symbolic links or junctions"}
		}
		next, err := root.OpenRoot(part)
		if err != nil {
			return inputError{"relative_path", "invalid_parent", "parent directory is unavailable or escapes the attachment root"}
		}
		root.Close()
		root = next
	}
	name := parts[len(parts)-1]
	file, err := root.OpenFile(name, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if os.IsExist(err) {
		return inputError{"relative_path", "already_exists", "destination already exists; choose a new filename"}
	}
	if err != nil {
		return errors.New("could not create the attachment destination")
	}
	saved := false
	defer func() {
		file.Close()
		if !saved {
			root.Remove(name)
		}
	}()
	if _, err := file.Write(content); err != nil {
		return errors.New("could not write the attachment destination")
	}
	if err := file.Sync(); err != nil {
		return errors.New("could not flush the attachment destination")
	}
	if err := file.Close(); err != nil {
		return errors.New("could not close the attachment destination")
	}
	saved = true
	return nil
}

func (s *mailTools) saveAttachment(ctx context.Context, args saveAttachmentInput) (map[string]any, error) {
	if _, err := savePathSegments(args.RelativePath); err != nil {
		return nil, err
	}
	file, err := s.file(ctx, attachmentInput{args.MessageID, args.AttachmentID})
	if err != nil {
		return nil, err
	}
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if err := saveLocalAttachment(args.RelativePath, file.Content); err != nil {
		return nil, err
	}
	digest := sha256.Sum256(file.Content)
	return map[string]any{
		"saved": true, "relative_path": args.RelativePath, "name": file.Name,
		"content_type": file.ContentType, "content_length": len(file.Content), "content_sha256": hex.EncodeToString(digest[:]),
	}, nil
}
