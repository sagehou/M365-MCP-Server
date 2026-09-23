**English** | [简体中文](zh-CN/release-checklist.md)

# v0.1.0 release checklist

Target:

- Project version: `0.1.0`
- Git tag: `v0.1.0`
- Container platform: `linux/amd64`
- Stable image: `ghcr.io/sagehou/m365-mcp-server:v0.1.0`
- Windows asset: `m365-mcp-windows-x64.exe`

Do not create or push the stable tag until every item in sections 1–4 below has
evidence. The automation-send checks after section 4 are a deployment gate for
that mode, not a v0.1.0 tag gate; they remain explicitly unverified for this
release.

Never store tokens, secrets, mailbox content, attachment content, or unredacted
tenant/user identifiers in the evidence.

## 1. Reviewed candidate

- [ ] The release-preparation PR is merged into `main`.
- [ ] The candidate commit is identified by its full SHA.
- [ ] Required PR checks are green.
- [ ] `pyproject.toml` reports version `0.1.0`.
- [ ] The repository `LICENSE` and Python package metadata both declare MIT.
- [ ] English and Chinese `v0.1.0` Release Notes are reviewed.
- [ ] Supported scope and known limitations match the README.

Evidence:

- Candidate SHA:
- PR/checks URL:
- Reviewer:
- Date (UTC):

## 2. Real WorkBuddy OAuth

Use a clean WorkBuddy profile and the candidate deployment.

- [ ] Protected Resource Metadata discovery succeeds.
- [ ] Authorization Server Metadata discovery succeeds.
- [ ] Dynamic Client Registration succeeds.
- [ ] Entra interactive sign-in completes through the registered WorkBuddy
  callback.
- [ ] MCP initializes and lists the expected eleven mail tools.
- [ ] Token expiry triggers a successful refresh and one-time rotation.
- [ ] Replaying the old refresh token is rejected.
- [ ] Authentication remains usable after a server restart.
- [ ] No user manually copies or pastes a bearer token.

Evidence:

- WorkBuddy version:
- Candidate deployment identifier:
- Sanitized audit/event references:
- Result/evidence URL:
- Tester and date (UTC):

## 3. Identity isolation

Use two real users. Cross-tenant validation requires two real tenants.

- [ ] User A can access only User A's mailbox.
- [ ] User B can access only User B's mailbox.
- [ ] Concurrent sessions do not cross identities.
- [ ] A caller cannot select another user's mailbox.
- [ ] Tenant A and Tenant B remain isolated.
- [ ] OBO uses the current caller's tenant.
- [ ] Session, refresh-token, and cache state do not cross users or tenants.

Evidence:

- Redacted account/tenant labels:
- Sanitized audit/event references:
- Result/evidence URL:
- Tester and date (UTC):

## 4. Real mailbox and attachments

- [ ] Search and message read succeed.
- [ ] One representative write succeeds and is verified in the mailbox.
- [ ] `mail_create_draft` creates the reviewed plain-text recipients, subject,
  and body without sending the message.
- [ ] In interactive mode, a separate explicit confirmation precedes
  `mail_send_draft`; the message appears once in Sent Items and reaches the
  controlled test recipient once.
- [ ] An ambiguous send failure is not automatically retried.
- [ ] PDF, DOCX, XLSX, PPTX, TXT, ZIP, and ordinary binary attachments are
  exercised.
- [ ] Oversized and unsupported attachments fail safely.
- [ ] Metadata `size` and decoded `content_length` are correct.
- [ ] Parser timeout/crash does not terminate the server.
- [ ] Download links are single-use and expire.
- [ ] A server restart invalidates old download links.
- [ ] Errors contain a safe reference matching exactly one audit event.
- [ ] Tokens, provider bodies, message bodies, and attachment content do not leak
  into client errors or diagnostics.

Evidence:

- Sanitized test-message identifiers:
- Sanitized audit/event references:
- Result/evidence URL:
- Tester and date (UTC):

## Automation-send deployment gate (not verified for v0.1.0)

The bounded automation-send contract remains supported at the client/agent
layer, but the following real-client checks were not completed for v0.1.0.
Do not claim they passed. Before enabling automated sending in a deployment:

- [ ] The recorded authorization includes recipients/domains, trigger, content
  rules and trusted sources, per-run and daily limits, and expiry; one in-policy
  draft sends without a per-message prompt.
- [ ] An out-of-policy recipient, content change, limit, or expired authorization
  stops before `mail_send_draft` and requests confirmation.

## 5. Create and verify the release

After sections 1–4 are complete:

```bash
git switch main
git pull --ff-only origin main
git tag -a v0.1.0 -m "M365 MCP Server v0.1.0"
git push origin v0.1.0
```

The tag workflow must then complete all of the following:

- [ ] Tag/version/ancestry validation passes.
- [ ] Bilingual documentation check passes.
- [ ] Python test suite passes.
- [ ] Exact production image builds and passes its health smoke test.
- [ ] Compose validation passes.
- [ ] The Windows x64 NativeAOT executable builds and passes the exact release smoke test.
- [ ] `m365-mcp-windows-x64.exe.sha256` verifies successfully against the published executable.
- [ ] GitHub Artifact Attestation exists for `m365-mcp-windows-x64.exe` and verifies against this repository.
- [ ] GHCR contains `v0.1.0`, `0.1.0`, `0.1`, and `latest`.
- [ ] GitHub Release `v0.1.0` exists with the reviewed notes and both Windows release assets.
- [ ] Anonymous `docker pull` works if the package is intended to be public.
- [ ] The deployed image digest matches the published candidate.

Evidence:

- Tag workflow URL:
- GitHub Release URL:
- GHCR digest:
- Windows EXE SHA-256:
- Windows attestation verification result:
- Anonymous-pull result:
- Release operator and date (UTC):

## Failure handling

Do not move or overwrite `v0.1.0`. If publishing partially succeeds, preserve
the logs, mark the incomplete release clearly, fix the workflow on `main`, and
publish a new patch version. Never hide a failed real-client gate by replacing it
with mocked evidence.
