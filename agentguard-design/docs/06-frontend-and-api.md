# 06 前端与 API 规格

## 1. 前端目标

前端不是通用管理后台，核心任务是解释一次安全决策：

1. 数据从哪里产生。
2. 经过了哪些工具和变形。
3. 准备流向哪里。
4. 哪条策略为何允许或阻止。

原型参考：[AgentGuard DataFlow V2](../agentguard-dataflow-prototype-v2.png)。

## 2. 页面路由

```text
/overview
/lineage/:traceId
/policies
/replay
/benchmarks
/approvals
```

### 流量总览 `/overview`

展示：

- 受保护调用数。
- 泄漏尝试数。
- 误报率。
- P95 网关延迟。
- 最近阻断事件。
- 按工具和策略聚合的事件分布。

### 数据血缘 `/lineage/:traceId`

核心组件：

- `LineageGraph`：Source、Artifact、Transformation、Sink 节点。
- `IncidentPanel`：来源、目标、匹配方式、置信度、策略。
- `ToolCallTable`：工具调用时间线。
- `ArtifactInspector`：标签、指纹、脱敏摘要。

图节点类型：

```text
tool_read
untrusted_content
data_artifact
transformation
tool_write
blocked_sink
```

### 工具策略 `/policies`

- 策略列表和当前生效版本。
- YAML 编辑器。
- 静态验证结果。
- 内置策略测试。
- 发布和回滚。

MVP 可先提供只读 YAML 和启停按钮，编辑器放入第二迭代。

### 攻击回放 `/replay`

- 选择 Trace。
- 选择策略版本和匹配算法版本。
- 运行回放。
- 对比旧决策与新决策。

回放不调用真实下游工具。

### 基准评测 `/benchmarks`

- 场景集版本。
- 各方案检测率、误报率和延迟。
- 失败场景列表。
- JSON/Markdown 报告下载。

### 审批 `/approvals`

- 待审批调用。
- 脱敏参数。
- 来源与数据血缘。
- 批准、拒绝和过期状态。

## 3. 状态颜色

```text
trusted / allow       青绿色
untrusted             琥珀色
secret / critical     红色
processing            紫色
neutral               灰蓝色
```

颜色必须同时配合文本和图标，不能仅依赖颜色表达状态。

## 4. REST API

### 系统状态

```http
GET /api/v1/health
GET /api/v1/stats/overview
```

### Trace

```http
GET /api/v1/traces
GET /api/v1/traces/{trace_id}
GET /api/v1/traces/{trace_id}/events
GET /api/v1/traces/{trace_id}/lineage
```

### 策略

```http
GET  /api/v1/policies
GET  /api/v1/policies/{policy_id}
POST /api/v1/policies/validate
POST /api/v1/policies/{policy_id}/test
POST /api/v1/policies/{policy_id}/activate
```

### 回放

```http
POST /api/v1/replays
GET  /api/v1/replays/{replay_id}
```

创建回放请求：

```json
{
  "trace_id": "tr_8F31A72",
  "policy_version": "policy_02",
  "matcher_version": "matcher_01"
}
```

### Benchmark

```http
GET  /api/v1/benchmarks
POST /api/v1/benchmarks/run
GET  /api/v1/benchmarks/{run_id}
GET  /api/v1/benchmarks/{run_id}/report
```

Benchmark运行请求：

```json
{
  "runs": 10,
  "modes": ["normal", "baseline", "protected", "protected-base64", "protected-split"],
  "transport": "inprocess"
}
```

### 审批

```http
GET  /api/v1/approvals
POST /api/v1/approvals/{approval_id}/approve
POST /api/v1/approvals/{approval_id}/reject
```

## 5. Lineage API 示例

```json
{
  "trace_id": "tr_8F31A72",
  "nodes": [
    {
      "id": "call_email",
      "type": "tool_read",
      "label": "email.read",
      "status": "allow"
    },
    {
      "id": "artifact_secret",
      "type": "data_artifact",
      "label": "Secret Data",
      "status": "critical",
      "metadata": {
        "resource": "/secrets/api_key.txt",
        "labels": ["sensitivity:secret"]
      }
    },
    {
      "id": "call_github",
      "type": "blocked_sink",
      "label": "github.create_issue",
      "status": "deny"
    }
  ],
  "edges": [
    {
      "source": "artifact_secret",
      "target": "call_github",
      "label": "base64_decoded · 96%",
      "status": "critical"
    }
  ]
}
```

## 6. 实时更新

MVP 可以先用轮询；实时演示阶段增加：

```text
GET /api/v1/events/stream
```

使用 SSE 推送：

- tool_call_requested
- policy_decided
- tool_call_completed
- artifact_registered
- provenance_matched

## 7. 前端技术建议

- React + TypeScript + Vite
- Tailwind CSS
- React Flow：血缘图
- TanStack Query：API 状态
- ECharts：Benchmark 图表
- Monaco Editor：策略 YAML（后续）
- Vitest + Testing Library
- Playwright：关键页面端到端测试

## 8. 前端验收

- 能从阻断事件进入完整数据血缘。
- 所有敏感值默认脱敏。
- 数据来源、变形和目标在一屏内可理解。
- 回放结果明确展示策略变化。
- 1,000 个 Trace 的列表操作保持流畅。
- 关键页面在 1440×900 与 1920×1080 正常展示。
