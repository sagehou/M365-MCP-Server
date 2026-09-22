import re

from m365_mcp.oauth.completion import authorization_completion_response


def test_workbuddy_completion_page_launches_client_and_has_safe_fallback() -> None:
    redirect_uri = (
        "workbuddy://workbuddy/mcp/test/oauth/callback"
        "?code=local-code&state=client-state"
    )

    response = authorization_completion_response(redirect_uri)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert response.media_type == "text/html"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "window.location.replace(callbackUri)" in body
    assert "window.close()" in body
    assert 'history.replaceState(null, "", "/oauth/complete")' in body
    assert "Authentication complete / 认证已完成" in body
    assert r"code=local-code\u0026state=client-state" in body

    policy = response.headers["content-security-policy"]
    nonce_match = re.search(r"script-src 'nonce-([^']+)'", policy)
    assert nonce_match is not None
    assert f'<script nonce="{nonce_match.group(1)}">' in body
    assert "default-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy


def test_completion_page_encodes_script_breakout_characters() -> None:
    redirect_uri = (
        "workbuddy://workbuddy/mcp/</script><script>alert(1)</script>"
        "?code=local&state=state"
    )

    response = authorization_completion_response(redirect_uri)
    body = response.body.decode("utf-8")

    assert "</script><script>alert(1)</script>" not in body
    assert r"\u003c/script\u003e\u003cscript\u003ealert(1)" in body


def test_non_workbuddy_completion_preserves_standard_redirect() -> None:
    redirect_uri = "http://127.0.0.1:43123/oauth/callback?code=local&state=state"

    response = authorization_completion_response(redirect_uri)

    assert response.status_code == 302
    assert response.headers["location"] == redirect_uri
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
