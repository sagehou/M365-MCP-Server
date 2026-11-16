package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strings"
	"testing"
)

func folderLink(path string, cursor url.Values) string {
	params := url.Values{"$top": {"100"}, "$select": {folderFields}}
	for key, values := range cursor {
		params[key] = values
	}
	return "https://graph.microsoft.com/v1.0" + path + "?" + params.Encode()
}

func TestFolderListingPagesAndMove(t *testing.T) {
	for _, parent := range []string{"", "parent/a?b#c", "parent+=="} {
		for _, cursor := range []url.Values{{"$skip": {"100"}}, {"$skiptoken": {"a+b/== &中文..token"}}} {
			path := "/me/mailFolders"
			if parent != "" {
				path += "/" + url.PathEscape(parent) + "/childFolders"
			}
			link := folderLink(strings.ReplaceAll(path, "+", "%2B"), cursor)
			calls := 0
			graph := testGraph(t, func(w http.ResponseWriter, r *http.Request) {
				calls++
				if calls == 3 {
					var body map[string]string
					if r.Method != http.MethodPost || r.URL.Path != "/me/messages/message/move" || json.NewDecoder(r.Body).Decode(&body) != nil || body["destinationId"] != "folder-two" {
						t.Error("move did not use the selected folder ID")
					}
					io.WriteString(w, `{"id":"new-message"}`)
					return
				}
				params := r.URL.Query()
				if r.Method != http.MethodGet || r.URL.EscapedPath() != path || params.Get("$top") != "100" || params.Get("$select") != folderFields {
					t.Errorf("unexpected folder request: %s %s", r.Method, r.URL)
				}
				if calls == 2 {
					for key := range cursor {
						if params.Get(key) != cursor.Get(key) {
							t.Error("lost continuation query")
						}
					}
					io.WriteString(w, `{"value":[]}`)
					return
				}
				json.NewEncoder(w).Encode(map[string]any{
					"value": []any{
						map[string]any{"id": "folder-one", "displayName": `项目 "归档"`, "parentFolderId": parent, "childFolderCount": 1, "totalItemCount": 20, "unreadItemCount": 2},
						map[string]any{"id": "folder-two", "displayName": `项目 "归档"`, "parentFolderId": parent},
					},
					"@odata.nextLink": link,
				})
			})
			service := &mailTools{graph: graph}
			ctx := context.Background()
			result, err := service.listFolders(ctx, foldersInput{ParentFolderID: parent})
			if err != nil {
				t.Fatal(err)
			}
			folders := result["folders"].([]any)
			if len(result) != 3 || len(folders) != 2 || folders[0].(map[string]any)["displayName"] != `项目 "归档"` || result["next_link"] != link || result["content_metadata"].(map[string]string)["trust"] != "untrusted" {
				t.Fatalf("lost names, duplicate folders or common result fields: %v", result)
			}
			last, err := service.listFolders(ctx, foldersInput{ParentFolderID: parent, NextLink: link})
			if err != nil || len(last["folders"].([]any)) != 0 || last["next_link"] != nil || calls != 2 {
				t.Fatalf("invalid final folder page: %v %v", last, err)
			}
			moved, err := service.move(ctx, moveInput{MessageID: "message", DestinationFolderID: folders[1].(map[string]any)["id"].(string)})
			if err != nil || moved["message_id"] != "new-message" || calls != 3 {
				t.Fatalf("could not move to returned folder ID: %v %v", moved, err)
			}
		}
	}
}

func TestFolderListingRejectsUnsafeContinuationBeforeGraph(t *testing.T) {
	calls := 0
	graph := testGraph(t, func(http.ResponseWriter, *http.Request) { calls++ })
	service := &mailTools{graph: graph}
	good := folderLink("/me/mailFolders", url.Values{"$skip": {"100"}})
	links := []string{
		"https://evil.example/v1.0/me/mailFolders?x=1",
		strings.Replace(good, "/me/mailFolders?", "/users/other/mailFolders?", 1),
		strings.Replace(good, "/me/mailFolders?", "/me/messages?", 1),
		strings.Replace(good, "/me/mailFolders?", "/me/mailFolders/../messages?", 1),
		folderLink("/me/mailFolders/other/childFolders", url.Values{"$skip": {"100"}}),
		good + "&$skip=200", good + "&$skiptoken=token", good + "&$filter=anything",
		good + "#fragment", good + "\\x", good + "\n", good + " ", strings.Repeat("x", 8193),
		folderLink("/me/mailFolders", url.Values{"$skip": {""}}),
		folderLink("/me/mailFolders", url.Values{"$skip": {"-1"}}),
		folderLink("/me/mailFolders", url.Values{"$skip": {"١"}}),
		folderLink("/me/mailFolders", url.Values{"$skiptoken": {""}}),
		folderLink("/me/mailFolders", url.Values{"$skip": {"100"}, "$top": {"101"}}),
		folderLink("/me/mailFolders", url.Values{"$skip": {"100"}, "$top": {"0"}}),
		folderLink("/me/mailFolders", url.Values{"$skip": {"100"}, "$top": {"+10"}}),
		folderLink("/me/mailFolders", url.Values{"$skip": {"100"}, "$select": {"id"}}),
		folderLink("/me/mailFolders", nil),
	}
	for _, link := range links {
		if _, err := service.listFolders(context.Background(), foldersInput{NextLink: link}); err == nil {
			t.Errorf("accepted unsafe continuation %q", link)
		}
	}
	for _, parent := range []string{".", "..", "bad\x00id", strings.Repeat("x", 2049)} {
		if _, err := service.listFolders(context.Background(), foldersInput{ParentFolderID: parent}); err == nil {
			t.Errorf("accepted invalid parent %q", parent)
		}
	}
	if _, err := service.listFolders(context.Background(), foldersInput{ParentFolderID: "parent", NextLink: good}); err == nil {
		t.Error("accepted another parent's continuation")
	}
	if calls != 0 {
		t.Fatal("invalid folder arguments reached Graph")
	}
}

func TestFolderListingRejectsMalformedGraphData(t *testing.T) {
	pages := []string{
		`[]`, `{}`, `{"value":null}`, `{"value":{}}`, `{"value":[null]}`,
		`{"value":[{"id":"","displayName":"name"}]}`,
		`{"value":[{"id":"id","displayName":42}]}`,
		`{"value":[],"@odata.nextLink":42}`,
		`{"value":[],"@odata.nextLink":"https://evil.example/PROVIDER_SECRET"}`,
		`{"value":[` + strings.Repeat(`{"id":"id","displayName":"name"},`, 100) + `{"id":"id","displayName":"name"}]}`,
	}
	for _, page := range pages {
		calls := 0
		graph := testGraph(t, func(w http.ResponseWriter, _ *http.Request) {
			calls++
			io.WriteString(w, page)
		})
		_, err := (&mailTools{graph: graph}).listFolders(context.Background(), foldersInput{})
		if err == nil || strings.Contains(err.Error(), "PROVIDER_SECRET") || calls != 1 {
			t.Errorf("accepted invalid Graph page or leaked provider data: %v", err)
		}
	}
}
