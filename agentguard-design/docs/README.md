# AgentGuard DataFlow 开发文档

本文档包将 [AgentGuard V2 产品方案](../AgentGuard-产品方案-v2.md) 转换为可实施的工程规格。项目目标是在 Agent 与下游 MCP Server 之间提供透明代理，通过工具输入输出追踪敏感数据的跨工具传播，并在外部写入发生前执行策略决策。

## 文档导航

1. [系统架构](01-system-architecture.md)
2. [协议、接口与数据模型](02-protocol-and-data-model.md)
3. [策略 DSL](03-policy-dsl.md)
4. [威胁模型](04-threat-model.md)
5. [测试与基准评测](05-testing-and-benchmark.md)
6. [前端与 API 规格](06-frontend-and-api.md)
7. [实施计划](07-implementation-plan.md)
8. [开发状态](08-development-status.md)

## MVP 成功标准

- 支持本地 stdio MCP 的透明转发和工具发现。
- 记录 `tools/list`、`tools/call` 请求、响应与决策轨迹。
- 为敏感工具返回建立来源标签和内容指纹。
- 检测原文、子串、Base64、Hex、空白变形和简单拆分重组泄漏。
- 在 `github.create_issue` 等外部写入工具执行前返回 `DENY`。
- 支持同一轨迹在不同策略版本下确定性回放。
- 正常任务测试通过，且 P95 网关增量延迟目标低于 30ms（不含模型与下游工具耗时）。

## 非目标

- 不读取或还原模型隐藏思维。
- 不监控未经过 AgentGuard 的调用。
- MVP 不接入真实邮件、GitHub 写权限或生产秘密。
- MVP 不解决所有自然语言形式的语义泄漏。
- MVP 不以通用 Prompt Injection 分类器为核心竞争点。

## 推荐仓库结构

```text
agentguard/
├── pyproject.toml
├── README.md
├── src/agentguard/
│   ├── gateway/
│   ├── protocol/
│   ├── registry/
│   ├── tracing/
│   ├── classification/
│   ├── fingerprint/
│   ├── dataflow/
│   ├── policy/
│   ├── replay/
│   ├── api/
│   └── cli/
├── web/
├── mock_servers/
│   ├── email_mcp/
│   ├── filesystem_mcp/
│   └── github_mcp/
├── scenarios/
├── policies/
├── tests/
└── docs/
```

## 决策原则

1. 协议代理与安全判断解耦。
2. 确定性检测优先于 LLM 判断。
3. 工具执行前完成最终决策。
4. 所有阻断必须附带可审计证据。
5. 任何安全提升都必须同时报告正常任务成功率和误报率。
