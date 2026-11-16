package main

import (
	"context"
	"errors"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"unicode"
)

const folderFields = "id,displayName,parentFolderId,childFolderCount,totalItemCount,unreadItemCount"

type foldersInput struct {
	ParentFolderID string `json:"parent_folder_id,omitempty" jsonschema:"Omit for top-level folders; use a returned folder ID for its direct children"`
	NextLink       string `json:"next_link,omitempty" jsonschema:"Returned next_link to continue listing the same parent_folder_id"`
}

func folderPageParams(path, link string) (url.Values, error) {
	if link == "" {
		return url.Values{"$top": {"100"}, "$select": {folderFields}}, nil
	}
	invalid := inputError{"next_link", "invalid_continuation", "use the returned next_link with the same parent_folder_id"}
	pagePath, query, found := strings.Cut(link, "?")
	decoded, decodeErr := url.PathUnescape(pagePath)
	expected, _ := url.PathUnescape("https://graph.microsoft.com/v1.0" + path)
	if len(link) > 8192 || !found || !strings.HasPrefix(link, "https://graph.microsoft.com/v1.0/") || decodeErr != nil || decoded != expected || strings.ContainsAny(link, "#\\") || strings.ContainsFunc(link, func(c rune) bool { return unicode.IsControl(c) || c == ' ' }) {
		return nil, invalid
	}
	params, err := url.ParseQuery(query)
	if err != nil {
		return nil, invalid
	}
	for key, values := range params {
		if len(values) != 1 || (key != "$top" && key != "$select" && key != "$skip" && key != "$skiptoken") {
			return nil, invalid
		}
	}
	top, err := strconv.Atoi(params.Get("$top"))
	if err != nil || len(params.Get("$top")) > 3 || strings.ContainsFunc(params.Get("$top"), func(c rune) bool { return c < '0' || c > '9' }) || top < 1 || top > 100 || params.Get("$select") != folderFields || params.Has("$skip") == params.Has("$skiptoken") {
		return nil, invalid
	}
	if params.Has("$skip") {
		if params.Get("$skip") == "" || strings.ContainsFunc(params.Get("$skip"), func(c rune) bool { return c < '0' || c > '9' }) {
			return nil, invalid
		}
	} else if params.Get("$skiptoken") == "" {
		return nil, invalid
	}
	return params, nil
}

func (s *mailTools) listFolders(ctx context.Context, args foldersInput) (map[string]any, error) {
	path := "/me/mailFolders"
	if len(args.ParentFolderID) > 2048 || strings.ContainsFunc(args.ParentFolderID, unicode.IsControl) {
		return nil, inputError{"parent_folder_id", "invalid_id", "invalid parent folder ID"}
	}
	if args.ParentFolderID != "" {
		segment, err := resourceSegment(args.ParentFolderID)
		if err != nil {
			return nil, inputError{"parent_folder_id", "invalid_id", err.Error()}
		}
		path += "/" + segment + "/childFolders"
	}
	params, err := folderPageParams(path, args.NextLink)
	if err != nil {
		return nil, err
	}
	data, err := s.graph.request(ctx, http.MethodGet, path, params, nil)
	if err != nil {
		return nil, err
	}
	folders, ok := data["value"].([]any)
	if !ok || len(folders) > 100 {
		return nil, errors.New("Graph returned an invalid folder collection")
	}
	for _, value := range folders {
		folder, ok := value.(map[string]any)
		id, _ := folder["id"].(string)
		_, named := folder["displayName"].(string)
		if !ok || id == "" || !named {
			return nil, errors.New("Graph returned an invalid folder collection")
		}
	}
	if value := data["@odata.nextLink"]; value != nil {
		link, ok := value.(string)
		if !ok {
			return nil, errors.New("Graph returned an invalid folder continuation")
		}
		if _, err := folderPageParams(path, link); err != nil {
			return nil, errors.New("Graph returned an invalid folder continuation")
		}
	}
	_, link := collection(data)
	return map[string]any{"folders": folders, "next_link": link, "content_metadata": contentMetadata("mail_folder")}, nil
}
