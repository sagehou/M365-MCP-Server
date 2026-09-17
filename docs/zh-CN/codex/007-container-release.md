[English](../../codex/007-container-release.md) | **简体中文**

# Task 007 - 容器发布

## 目标

准备 Production Container Delivery。

## 要求

- 提供 Production Dockerfile。
- 提供 Docker Compose Deployment Example。
- 支持 Environment-based Configuration。
- 提供 Health Check Endpoint。
- 通过 CI/CD 发布 Container Image。

## 交付物

- Docker Image
- Compose Deployment
- GitHub Actions Workflow
- Release Documentation

## 非目标

- 第一版不实现 Kubernetes Deployment。

## 实现说明

Production Dockerfile 在不保留 Cache 的情况下安装应用，以独立 Non-root User 运行，Expose 8000，并声明指向 Public Health Endpoint 的 Health Check。Compose 提供 Environment Configuration 和 Health Checks，不持久化 Mailbox Content。

CI Workflow 会远程 Build 并启动镜像，然后探测 `healthz`。Release Workflow 由 `vX.Y.Z` Tag 触发，重新运行测试，并向 GHCR 发布 Version、Major/Minor 和 `latest` Tags。Kubernetes 和 SIEM Integration 仍不在 Scope 内。
