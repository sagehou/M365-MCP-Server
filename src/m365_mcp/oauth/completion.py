"""Browser handoff responses for completed OAuth authorization."""

from __future__ import annotations

import json
import secrets
from urllib.parse import urlsplit

from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import Response


_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def _javascript_string(value: str) -> str:
    """Encode untrusted text for a JavaScript string inside an HTML script."""

    return (
        json.dumps(value)
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("&", r"\u0026")
        .replace("\u2028", r"\u2028")
        .replace("\u2029", r"\u2029")
    )


def authorization_completion_response(redirect_uri: str) -> Response:
    """Return the OAuth result to the registered client.

    HTTP(S) and loopback clients retain the normal redirect response. WorkBuddy's
    private URI receives a minimal completion page so the browser can launch the
    desktop client, attempt to close a script-opened authorization window, and
    otherwise leave a clear manual-close message.
    """

    if urlsplit(redirect_uri).scheme.casefold() != "workbuddy":
        return RedirectResponse(
            redirect_uri,
            status_code=302,
            headers=_NO_STORE_HEADERS,
        )

    nonce = secrets.token_urlsafe(18)
    callback_uri = _javascript_string(redirect_uri)
    content_security_policy = (
        "default-src 'none'; "
        f"script-src 'nonce-{nonce}'; "
        f"style-src 'nonce-{nonce}'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Microsoft 365 authorization complete</title>
  <style nonce="{nonce}">
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f5f7fb; color: #172033; }}
    main {{ width: min(36rem, calc(100% - 3rem)); padding: 2rem; border-radius: 1rem; background: white; box-shadow: 0 1rem 3rem rgb(15 23 42 / 12%); text-align: center; }}
    h1 {{ margin-top: 0; font-size: 1.5rem; }}
    p {{ line-height: 1.6; }}
    a {{ display: inline-block; margin-top: .5rem; padding: .7rem 1rem; border-radius: .6rem; background: #2563eb; color: white; text-decoration: none; }}
    @media (prefers-color-scheme: dark) {{ body {{ background: #111827; color: #e5e7eb; }} main {{ background: #1f2937; }} }}
  </style>
</head>
<body>
  <main>
    <h1>Authentication complete / 认证已完成</h1>
    <p>Returning to WorkBuddy. If this tab stays open, you can close it safely.</p>
    <p>正在返回 WorkBuddy；如果此标签页仍然打开，可以安全关闭。</p>
    <a id="return-to-client" rel="noreferrer">Return to WorkBuddy / 返回 WorkBuddy</a>
  </main>
  <script nonce="{nonce}">
    (() => {{
      const callbackUri = {callback_uri};
      history.replaceState(null, "", "/oauth/complete");
      document.getElementById("return-to-client").href = callbackUri;
      window.location.replace(callbackUri);
      setTimeout(() => window.close(), 900);
    }})();
  </script>
</body>
</html>
"""
    headers = dict(_NO_STORE_HEADERS)
    headers["Content-Security-Policy"] = content_security_policy
    return HTMLResponse(html, status_code=200, headers=headers)
