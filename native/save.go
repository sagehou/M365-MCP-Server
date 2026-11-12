package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

type saveAttachmentInput struct {
	MessageID    string `json:"message_id" jsonschema:"Outlook message ID"`
	AttachmentID string `json:"attachment_id" jsonschema:"Outlook attachment ID"`
	RelativePath string `json:"relative_path" jsonschema:"New relative filename with forward slashes; missing parent directories are created; never overwrites"`
	DownloadDir  string `json:"download_dir,omitempty" jsonschema:"Optional absolute destination directory on the EXE's PC; overrides M365_ATTACHMENT_ROOT and Windows Downloads/M365-MCP"`
}

func savePathSegments(relative string) ([]string, error) {
	invalid := inputError{"relative_path", "invalid_path", "use a new relative file path with forward slashes under the download directory"}
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

func downloadDirectory(override string) (string, error) {
	rootPath := override
	if rootPath == "" {
		rootPath = os.Getenv("M365_ATTACHMENT_ROOT")
	}
	if rootPath == "" {
		return defaultDownloadDirectory()
	}
	if !filepath.IsAbs(rootPath) {
		return "", inputError{"download_dir", "invalid_directory", "download_dir or M365_ATTACHMENT_ROOT must be an absolute directory"}
	}
	return filepath.Clean(rootPath), nil
}

func downloadLimit() (int64, error) {
	value := strings.TrimSpace(os.Getenv("M365_MAX_DOWNLOAD_MIB"))
	if value == "" {
		return 150 << 20, nil
	}
	mib, err := strconv.ParseInt(value, 10, 64)
	if err != nil || mib <= 0 || mib > (1<<43)-1 {
		return 0, inputError{"M365_MAX_DOWNLOAD_MIB", "invalid_limit", "set M365_MAX_DOWNLOAD_MIB to a positive integer number of MiB"}
	}
	return mib << 20, nil
}

func openSaveDirectory(rootPath string, parents []string) (*os.Root, error) {
	base := filepath.VolumeName(rootPath) + string(filepath.Separator)
	relative, err := filepath.Rel(base, rootPath)
	if err != nil {
		return nil, inputError{"download_dir", "invalid_directory", "could not resolve the absolute destination directory"}
	}
	parts := []string{}
	if relative != "." {
		parts, err = savePathSegments(filepath.ToSlash(relative))
		if err != nil {
			return nil, err
		}
	}
	parts = append(parts, parents...)
	root, err := os.OpenRoot(base)
	if err != nil {
		return nil, errors.New("could not open the destination volume")
	}
	opened := false
	defer func() {
		if !opened {
			root.Close()
		}
	}()
	for _, part := range parts {
		if err := root.Mkdir(part, 0700); err != nil && !os.IsExist(err) {
			return nil, errors.New("could not create the download directory")
		}
		info, err := root.Lstat(part)
		if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
			return nil, inputError{"download_dir", "invalid_parent", "download directories must not be symbolic links or junctions"}
		}
		next, err := root.OpenRoot(part)
		if err != nil {
			return nil, inputError{"download_dir", "invalid_parent", "parent directory is unavailable or escapes the download directory"}
		}
		root.Close()
		root = next
	}
	opened = true
	return root, nil
}

func saveLocalAttachment(ctx context.Context, rootPath, relative string, input io.Reader, limit int64) (string, int64, string, error) {
	parts, err := savePathSegments(relative)
	if err != nil {
		return "", 0, "", err
	}
	root, err := openSaveDirectory(rootPath, parts[:len(parts)-1])
	if err != nil {
		return "", 0, "", err
	}
	defer root.Close()
	name := parts[len(parts)-1]
	file, err := root.OpenFile(name, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if os.IsExist(err) {
		return "", 0, "", inputError{"relative_path", "already_exists", "destination already exists; choose a new filename"}
	}
	if err != nil {
		return "", 0, "", errors.New("could not create the attachment destination")
	}
	saved := false
	defer func() {
		file.Close()
		if !saved {
			root.Remove(name)
		}
	}()
	digest := sha256.New()
	var length int64
	buffer := make([]byte, 64<<10)
	for {
		if err := ctx.Err(); err != nil {
			return "", 0, "", err
		}
		n, readErr := input.Read(buffer)
		if n > 0 {
			if int64(n) > limit-length {
				return "", 0, "", inputError{"attachment_id", "too_large", "attachment exceeds the M365_MAX_DOWNLOAD_MIB limit"}
			}
			if _, err := file.Write(buffer[:n]); err != nil {
				return "", 0, "", errors.New("could not write the attachment destination")
			}
			digest.Write(buffer[:n])
			length += int64(n)
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			return "", 0, "", errors.New("attachment transfer failed; incomplete file cleanup was attempted")
		}
	}
	if err := ctx.Err(); err != nil {
		return "", 0, "", err
	}
	if err := file.Sync(); err != nil {
		return "", 0, "", errors.New("could not flush the attachment destination")
	}
	if err := file.Close(); err != nil {
		return "", 0, "", errors.New("could not close the attachment destination")
	}
	saved = true
	return filepath.Join(rootPath, filepath.FromSlash(relative)), length, hex.EncodeToString(digest.Sum(nil)), nil
}

func (s *mailTools) saveAttachment(ctx context.Context, args saveAttachmentInput) (map[string]any, error) {
	if _, err := savePathSegments(args.RelativePath); err != nil {
		return nil, err
	}
	rootPath, err := downloadDirectory(args.DownloadDir)
	if err != nil {
		return nil, err
	}
	limit, err := downloadLimit()
	if err != nil {
		return nil, err
	}
	attachment, err := attachmentPath(attachmentInput{args.MessageID, args.AttachmentID})
	if err != nil {
		return nil, err
	}
	metadata, err := s.graph.request(ctx, http.MethodGet, attachment, url.Values{"$select": {"id,name,contentType"}}, nil)
	if err != nil {
		return nil, err
	}
	kind, _ := metadata["@odata.type"].(string)
	if !strings.EqualFold(kind, "#microsoft.graph.fileAttachment") {
		return nil, inputError{"attachment_id", "unsupported_attachment", "only Outlook file attachments are supported"}
	}
	name, _ := metadata["name"].(string)
	contentType, _ := metadata["contentType"].(string)
	if name == "" || len(name) > 4096 || len(contentType) > 1024 {
		return nil, errors.New("attachment metadata is invalid")
	}
	if contentType == "" {
		contentType = "application/octet-stream"
	}
	response, err := s.graph.openResponse(ctx, http.MethodGet, attachment+"/$value", nil, nil, "application/octet-stream")
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.ContentLength > limit {
		return nil, inputError{"attachment_id", "too_large", "attachment exceeds the M365_MAX_DOWNLOAD_MIB limit"}
	}
	path, length, digest, err := saveLocalAttachment(ctx, rootPath, args.RelativePath, response.Body, limit)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"saved": true, "relative_path": args.RelativePath, "path": path, "name": name,
		"content_type": contentType, "content_length": length, "content_sha256": digest,
	}, nil
}
