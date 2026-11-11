**English** | [简体中文](zh-CN/runtime-dependency-audit.md)

# Runtime dependency audit

## Python dependencies

`pyproject.toml` pins direct and build dependencies. `uv.lock` contains 103
registry packages, including development and platform-specific dependencies,
with distribution hashes. CI and Docker install with `uv sync --frozen`.
The updated lock was resolved on GitHub Actions, not in the editing environment.

| Package | Resolved version |
| --- | ---: |
| `cryptography` | 50.0.2 |
| `fastapi` | 0.162.4 |
| `fastmcp` / `fastmcp-slim` | 4.1.8 |
| `mcp` / `mcp-types` | 2.3.0 |
| `authlib` | 1.9.5 |
| `joserfc` | 1.8.0 |
| `httpx` | 0.28.1 |
| `httpx2` | 2.16.0 |
| `msal` | 1.39.0 |
| `PyJWT` | 2.15.1 |
| `pypdf` | 7.0.1 |
| `python-docx` | 1.2.0 |
| `openpyxl` | 3.1.5 |
| `python-pptx` | 1.0.2 |
| `pydantic` | 2.14.3 |
| `pydantic-settings` | 2.16.2 |
| `starlette` | 1.10.0 |
| `uvicorn` | 0.54.0 |
| `annotated-doc` | 0.0.6 |
| `markdown-it-py` | 4.3.0 |
| `uncalled-for` | 0.6.1 |
| `pytest` | 9.2.0 |
| `pip-audit` | 2.10.1 |

PyPI metadata was checked for every locked registry package. The six packages
updated in this review are FastAPI, FastMCP, pypdf, annotated-doc,
markdown-it-py and uncalled-for; FastMCP also updates fastmcp-slim. The full lock
was checked against OSV and CI runs `pip-audit --skip-editable` independently.
No withdrawn locked distributions were found. Build tools remain
`setuptools==84.2.1`, `wheel==0.48.0` and `uv==0.13.7`.

Application Graph and OIDC requests use `httpx`. FastMCP 4 and MCP SDK v2 use
`httpx2`; both have active callers. FastMCP's client API is also used by the
protocol integration tests. Neither HTTP dependency is an accidental duplicate.
The pypdf 7 line includes the fix for
[GHSA-59jv-x5x2-gg4c](https://github.com/py-pdf/pypdf/security/advisories/GHSA-59jv-x5x2-gg4c).

## Native dependencies and runtimes

| Component | Version or policy |
| --- | --- |
| Python | Supported 3.12 runtime line |
| Go | 1.27.4 in `native/go.mod` |
| Go MSAL | `github.com/AzureAD/microsoft-authentication-library-for-go` v1.10.1 |
| Go MCP SDK | `github.com/modelcontextprotocol/go-sdk` v1.8.0 |
| Go PDF | `github.com/ledongthuc/pdf` v0.0.0-20261020125853-5e46805f718e |
| Go XLSX | `github.com/xuri/excelize/v2` v2.11.1 |
| Go Windows API | `golang.org/x/sys` v0.50.0 |
| .NET | .NET 10 LTS; no direct NuGet dependencies; Actions selects the latest 10.0.x SDK |

The current .NET metadata reports SDK 10.0.404 and runtime 10.0.15; .NET 10 is
supported through 2028-11-14. All 24 Go direct/transitive module versions were
compared with the Go module proxy. Three dependencies intentionally use commits
newer than their latest stable tags: `x/crypto`, `xuri/efp` and `xuri/nfp`.
Do not downgrade them to the older tags.

The `x/crypto` pin `v0.58.1-0.20261009181718-2f1f834330b2` includes the upstream
[GO-2026-5932](https://pkg.go.dev/vuln/GO-2026-5932) fix and removes retired
OpenPGP code. The application does not import OpenPGP. Older release dates alone
do not establish abandonment: the reviewed UUID, browser, godebug, asm and URI
template repositories are not archived, and the selected versions remain their
current releases. Their compiled Windows use is checked with `govulncheck` for
both AMD64 and ARM64.

## Container and delivery gates

The runtime image uses the supported Python 3.12 Alpine base with system
security updates and the C++ runtime required by native wheels. It omits the
Debian mount/login/Perl tools implicated by the previous base-image scan. `pip`
and `uv` are removed after dependency installation. The existing non-root
UID/GID and `/data` ownership are preserved for persisted OAuth state.

CI scans the exact candidate with Trivy 0.76.2. Both test-image publication and
stable releases run the same scanner before pushing. Known findings at every
severity fail the gate, including findings without a published fix; there is
no vulnerability ignore list. Image smoke checks exercise startup, OAuth
storage and isolated TXT/PDF/DOCX/XLSX/PPTX extraction on the installed image.

[PR #60](https://github.com/sagehou/M365-MCP-Server/pull/60) contains the source
changes and hosted check results. Functional, static and artifact coverage is
recorded in the [implementation review](review-status.md). Runtime dependency
reports remain in the CI logs; deployment image digests must be recorded for
the actual deployed image.

---

Version and advisory checks describe the reviewed snapshot and cannot guarantee that unknown vulnerabilities do not exist. Live tenant/client behavior and Windows ARM64 execution require separate validation. All builds, tests and audit tools run on GitHub Actions; no local test environment or dependency installation was used. Updated: 2026-11-11.
