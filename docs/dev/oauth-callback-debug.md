# OAuth callback debugging notes

This document is temporary developer guidance for diagnosing MCP OAuth callback failures.

Do not log authorization codes, access tokens, refresh tokens, client secrets, or PKCE values.

When Entra authorization succeeds but the MCP callback returns an error, inspect the stages:

1. transaction lookup
2. upstream token exchange
3. token validation
4. local authorization code creation
5. redirect back to the MCP client
