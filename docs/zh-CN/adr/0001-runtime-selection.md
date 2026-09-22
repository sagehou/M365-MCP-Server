[English](../../adr/0001-runtime-selection.md) | **简体中文**

# ADR-0001：运行时选择

## 状态

已接受（针对 Windows 本地模式修订）

## 决策

托管 HTTP/OBO Server 与容器交付继续使用 Python 3.12 作为主要运行时。

Windows 本地模式使用独立的 .NET 8 NativeAOT 可执行文件。本地主机与 Agent
同机运行，通过 MCP stdio 通信，并采用 Microsoft Entra 公共客户端授权码 +
PKCE。它不替代托管 Python Server。

## 背景

本项目是企业级 Microsoft 365 MCP Server，核心工作负载包括：

- MCP Protocol Handling
- Microsoft Entra OAuth/OBO Authentication
- Microsoft Graph API Calls
- Email Attachment Document Extraction
- AI Agent Integration

托管工作负载主要是网络与系统集成而非 CPU 密集计算，部署目标为容器；Python
在 MCP 和文档处理方面具有成熟生态。

Windows 本地模式有不同的分发约束：用户只接收一个可执行文件，不要求预装
Python 或 .NET Runtime，也不会在程序目录或临时目录解压应用文件树。Agent
负责进程生命周期，并通过 stdio 通信。

## 考虑过的方案

### 所有模式都使用 Python 3.12

优点：

- MCP 与 AI Tooling 生态成熟
- 文档处理库成熟
- 只维护一种实现语言

缺点：

- 常见 Python 单文件打包器启动时会解压内嵌 Runtime 与依赖
- 这种解压行为不满足 Windows 无 Runtime、无解压的分发契约

### 所有模式都使用 .NET 8

优点：

- Microsoft 生态第一方支持
- Entra ID 与 Graph 集成优秀
- 企业采用广泛

缺点：

- 重写托管 Server 会丢弃已经建立的 Python MCP、附件处理和容器实现
- 大范围重写会增加发布风险，却不会改善托管模式契约

### 拆分运行时：Python 托管 Server + .NET 8 NativeAOT 本地主机

优点：

- 保留现有托管实现
- 生成不依赖托管 Runtime、启动时也不创建解压目录的自包含 Windows 原生程序
- 适合公共客户端认证与 MCP stdio 进程模型

缺点：

- 两套实现必须保持重叠 MCP Tool 契约一致
- NativeAOT 要求依赖兼容 AOT，并显式提供序列化元数据
- Windows 代码签名和稳定 Release Asset 仍是独立交付门禁

## 决策理由

两种部署契约差异足以采用两个入口。Python 仍最适合托管集成层与丰富附件处理；
.NET 8 NativeAOT 仅用于受约束的 Windows 本地分发，因为真正自包含的单文件
程序是明确产品要求。

两种模式都通过标准 OAuth Flow 调用 Microsoft Graph。托管 Server 保留
Confidential-client/OBO 行为；本地主机使用独立的 Entra Public-client
Application，并用当前用户 DPAPI 保存刷新状态。

## 影响

正面：

- 无需重写托管 Server
- 保留 Python 的快速迭代能力
- Windows 用户只需一个 EXE，无需另装 Runtime
- 本地凭据限定在当前 Windows 用户范围

负面：

- 重叠行为必须通过 Contract Tests 和文档保持一致
- 本地模式初期提供的 Tool Set 小于托管服务
- Release Engineering 仍需构建、扫描、签名并发布 Windows Binary
