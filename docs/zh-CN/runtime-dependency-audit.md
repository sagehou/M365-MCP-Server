[English](../runtime-dependency-audit.md) | **简体中文**

# 运行时依赖审计

## Python 依赖

`pyproject.toml` 固定直接依赖和构建依赖；`uv.lock` 记录包含开发及平台条件依赖在内的
103 个注册表包及分发文件哈希。CI 和 Docker 使用 `uv sync --frozen` 安装。
更新后的锁文件由 GitHub Actions 解析，没有在编辑环境中执行解析或安装。

| Package | 实际解析版本 |
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

已逐一查询所有锁定注册表包的 PyPI 元数据。本次更新六个包：FastAPI、FastMCP、pypdf、
annotated-doc、markdown-it-py、uncalled-for；FastMCP 同步更新 fastmcp-slim。
全部锁定版本已查询 OSV，CI 另独立运行 `pip-audit --skip-editable`。
未发现被撤回的锁定分发版本。构建工具保持 `setuptools==84.2.1`、`wheel==0.48.0`、`uv==0.13.7`。

项目 Graph 和 OIDC 请求使用 `httpx`，FastMCP 4 与 MCP SDK v2 使用 `httpx2`，两套客户端
均有实际调用；协议集成测试也使用 FastMCP 客户端 API，因此它们不是意外的重复依赖。
pypdf 7 已包含
[GHSA-59jv-x5x2-gg4c](https://github.com/py-pdf/pypdf/security/advisories/GHSA-59jv-x5x2-gg4c)
修复。

## 原生依赖及运行时

| 组件 | 版本或策略 |
| --- | --- |
| Python | 受支持的 3.12 运行时系列 |
| Go | `native/go.mod` 中固定 1.27.4 |
| Go MSAL | `github.com/AzureAD/microsoft-authentication-library-for-go` v1.10.1 |
| Go MCP SDK | `github.com/modelcontextprotocol/go-sdk` v1.8.0 |
| Go PDF | `github.com/ledongthuc/pdf` v0.0.0-20261020125853-5e46805f718e |
| Go XLSX | `github.com/xuri/excelize/v2` v2.11.1 |
| Go Windows API | `golang.org/x/sys` v0.50.0 |
| .NET | .NET 10 LTS；无直接 NuGet 依赖；Actions 选择最新 10.0.x SDK |

当前 .NET 元数据为 SDK 10.0.404、运行时 10.0.15，.NET 10 支持至 2028-11-14。
已对全部 24 个 Go 直接及传递模块查询 Go 模块代理；其中 `x/crypto`、`xuri/efp`、`xuri/nfp`
固定在比最新稳定标签更新的提交，不应降级到旧标签。

`x/crypto` 固定的 `v0.58.1-0.20261009181718-2f1f834330b2` 包含上游
[GO-2026-5932](https://pkg.go.dev/vuln/GO-2026-5932) 修复并移除了停止维护的 OpenPGP 代码，
本程序不导入 OpenPGP。不能仅凭发布日期较早认定依赖已废弃：已核对的 UUID、browser、godebug、
asm、URI 模板仓库未归档，所选版本仍是各自当前版本；CI 对 AMD64、ARM64 两种 Windows 编译目标
运行 `govulncheck` 检查实际调用路径。

## 容器及交付检查

运行镜像使用受支持的 Python 3.12 Alpine 基础镜像，应用系统安全更新，并安装原生 Wheel 所需的
C++ 运行时。此前 Debian 镜像扫描涉及的挂载、登录、Perl 工具不再进入运行镜像；依赖安装完成后
移除 `pip`、`uv`。保留原有非 root 用户 UID/GID 及 `/data` 所有权，兼容持久化 OAuth 状态。

CI 使用 Trivy 0.76.2 扫描确切候选镜像，测试镜像和稳定版也在推送前运行同一检查。
所有严重程度的已知问题都会使检查失败，包括上游尚无修复的项目；未设置漏洞忽略列表。
镜像烟测覆盖启动、OAuth 存储，以及安装后镜像中的 TXT/PDF/DOCX/XLSX/PPTX 隔离提取。

[PR #60](https://github.com/sagehou/M365-MCP-Server/pull/60) 包含源码变更及远程检查结果；
功能、静态分析及产物检查范围见[实现复核](review-status.md)。运行时依赖报告保留在 CI 日志中；
实际部署时需记录所用镜像的 Digest。

---

版本和安全公告检查只反映被审计的快照，不能保证不存在未知漏洞；真实租户/客户端行为及 Windows ARM64 实机运行仍需单独验收。构建、测试和审计工具全部在 GitHub Actions 执行，本次未在本地创建测试环境或安装依赖。更新日期：2026-11-11。
