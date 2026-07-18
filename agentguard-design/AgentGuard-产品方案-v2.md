# AgentGuard V2 产品方案

## 1. 新定位

AgentGuard 是一个部署在 Agent 与 MCP Server 之间的跨工具数据流安全网关。它不读取模型隐藏思维，也不宣称监控任意第三方 Agent；它只分析经过网关的 MCP 工具请求和响应，追踪敏感数据从来源工具到外部写入工具的传播过程，并在泄漏发生前阻断调用。

一句话定位：

> 面向 MCP 工具调用链的动态数据血缘追踪与敏感信息泄漏防护。

## 2. 目标用户与使用场景

目标用户：正在开发带工具调用 Agent 的 AI 工程师、MCP 平台团队和安全工程师。

典型场景：一个客服 Agent 连接 Email、Filesystem 和 GitHub MCP。Agent 读取客户邮件后，受到邮件内恶意指令诱导，读取本地密钥并尝试写入公开 Issue。开发者将 MCP 地址改为 AgentGuard Gateway，由网关记录工具数据来源、检测跨工具敏感数据流并阻止最终写入。

接入前：

```text
Agent → Email / Filesystem / GitHub MCP
```

接入后：

```text
Agent → AgentGuard Gateway → Email / Filesystem / GitHub MCP
```

## 3. 产品边界

AgentGuard 能看到：

- MCP 工具名称、参数和返回值
- 工具调用顺序与会话标识
- 数据来自哪个工具、资源和字段
- 敏感数据是否流入外部写入参数
- 策略命中、审批和阻断结果

AgentGuard 不依赖也不宣称看到：

- 模型隐藏思维过程
- 未经过网关的工具调用
- 未接入系统的第三方 Agent 对话
- 真实用户未授权的数据

## 4. 核心能力

### MCP 透明代理

发现下游 MCP 工具并向上游 Agent 暴露兼容接口，统一转发和记录 `tools/list`、`tools/call` 等请求。

### 数据来源标记

为工具返回中的数据建立来源记录：

```json
{
  "source": "filesystem.read",
  "resource": "/secrets/api_key.txt",
  "classification": "secret",
  "fingerprint": "sha256:..."
}
```

### 跨工具数据流检测

当后续工具参数包含来源数据或其变形结果时，恢复传播关系：

```text
filesystem.read → secret → github.create_issue
```

### 数据变形识别

首版支持：

- 原文与子串泄漏
- Base64/Hex 编码
- 前后缀拼接
- 空格、换行和标点变形
- 多段拆分后重新组合

### 策略决策

根据数据类型、来源、目标工具和目标域返回：

```text
ALLOW / DENY / REQUIRE_APPROVAL
```

### 回放与评测

记录完整 MCP 调用轨迹，允许在不同策略下重放同一攻击，比较检出率、误报率和延迟。

## 5. MVP

首版只支持本地 stdio MCP，提供三个模拟 MCP Server：

- Email MCP：返回正常或恶意客户邮件
- Filesystem MCP：返回包含 Canary Secret 的文件
- GitHub MCP：模拟创建公开 Issue

首个攻击链：

```text
email.read
→ 邮件中的间接提示词注入
→ filesystem.read(/secrets/api_key.txt)
→ github.create_issue(body=CANARY_SECRET...)
→ AgentGuard DENY
```

MVP 验收标准：

- 不启用防护时可以稳定复现 Canary 泄漏
- 启用防护时在 GitHub 写入前阻断
- 正常客户邮件仍可成功创建模拟 Issue
- 页面展示完整来源、传播、目标和策略证据
- 支持攻击轨迹 JSON 导出与命令行重放
- 单元测试不依赖真实秘密或生产账户

## 6. 技术架构

```text
Agent / MCP Client
        ↓
MCP Gateway
        ├── Protocol Proxy
        ├── Tool Registry
        ├── Trace Collector
        ├── Data Classifier
        ├── Fingerprint Engine
        ├── DataFlow Tracker
        └── Policy Engine
        ↓
Downstream MCP Servers
```

推荐技术栈：

- Gateway：Python 3.12、FastAPI、MCP Python SDK、Pydantic
- 数据流：内容指纹、Canary、确定性编码归一化和会话级来源图
- 策略：YAML DSL，后续评估 OPA/Rego
- 存储：SQLite + JSONL
- 前端：React、TypeScript、Tailwind CSS、React Flow、ECharts
- 测试：pytest、固定攻击集、Docker 沙箱

## 7. 前端信息架构

### 流量总览

展示受保护调用数、泄漏尝试、误报率、P95 网关延迟和最近阻断事件。

### 数据血缘

以图形式展示 Source、Transformation、Sink：

```text
Email MCP → Agent → Filesystem MCP → Secret → GitHub MCP
```

节点可查看工具参数、返回值摘要、数据标签、指纹和策略证据。

### 工具策略

按工具、数据类型和目标定义允许、拒绝或审批规则。

### 攻击回放

选择已记录轨迹，在不同策略版本下重新执行，比较决策变化。

### 基准评测

比较关键词、DLP、LLM 审查和 AgentGuard 数据流追踪的检出率、误报率与延迟。

## 8. 核心评测集

每类至少准备 10 个场景：

- 原文泄漏
- 部分内容泄漏
- Base64/Hex 编码泄漏
- 空格和标点变形
- 多工具、多步骤传播
- 拆分后重新组合
- 正常数据相似导致的误报测试

指标：

- Secret Leakage Detection Rate
- False Positive Rate
- Transformed Leakage Recall
- Normal Task Completion Rate
- P50/P95 Gateway Latency
- Replay Reproducibility

## 9. 项目差异点

项目不与企业安全平台比功能数量，而是深入实现一个可解释、模型无关的技术点：

> 不读取 Agent 内部对话，仅依靠 MCP 工具输入输出，通过来源标签、内容指纹和动态数据流图检测跨工具敏感信息泄漏。

简历和演示重点放在数据血缘算法、变形泄漏检测、策略性能和与开源方案的可复现实验对比。

## 10. 开发里程碑

### M1：透明代理

打通一个 Agent、AgentGuard Gateway 和三个模拟 MCP Server，完整记录调用轨迹。

### M2：数据流追踪

实现 Canary、来源标签、指纹匹配以及原文、子串和编码泄漏检测。

### M3：阻断与回放

实现 YAML 策略、写入阻断、人工审批状态及攻击轨迹重放。

### M4：评测与前端

构建攻击集，完成数据血缘图、阻断证据、性能指标和方案对比页面。
