# 02 协议、接口与数据模型

## 1. MCP 支持范围

MVP 支持：

- stdio transport
- initialize
- notifications/initialized
- tools/list
- tools/call

暂不支持：

- resources 与 prompts 的完整代理
- sampling
- HTTP/SSE/Streamable HTTP
- 多租户远程认证

## 2. 工具命名空间

下游工具统一映射为：

```text
<server_id>.<tool_name>
```

例：

```text
email.read
filesystem.read
github.create_issue
```

Registry 保存上游名称、下游名称、输入 Schema 与安全元数据。

## 3. 核心实体

### Session

```json
{
  "session_id": "ses_01J...",
  "agent_id": "support-agent",
  "policy_version": "policy_2026_07_18_01",
  "started_at": "2026-07-18T08:00:00Z",
  "status": "active"
}
```

### ToolCall

```json
{
  "call_id": "call_01J...",
  "session_id": "ses_01J...",
  "parent_call_id": null,
  "tool_name": "github.create_issue",
  "category": "external_write",
  "arguments": {
    "title": "Login failure",
    "body": "..."
  },
  "requested_at": "2026-07-18T08:00:03Z"
}
```

持久化时必须对 `arguments` 执行字段级脱敏；完整值只在受限内存中参与匹配。

### ToolResult

```json
{
  "result_id": "res_01J...",
  "call_id": "call_01J...",
  "status": "success",
  "content_type": "text/plain",
  "content_summary": "[REDACTED SECRET, 24 chars]",
  "completed_at": "2026-07-18T08:00:02Z"
}
```

### DataArtifact

表示从工具响应中提取出的可追踪数据：

```json
{
  "artifact_id": "art_01J...",
  "session_id": "ses_01J...",
  "source_call_id": "call_fs_01J...",
  "source_tool": "filesystem.read",
  "resource": "/secrets/api_key.txt",
  "labels": [
    "sensitivity:secret",
    "handling:no_external_write"
  ],
  "length": 24,
  "fingerprints": [
    {"kind": "sha256", "value": "..."},
    {"kind": "normalized_sha256", "value": "..."}
  ],
  "retention": "session_memory"
}
```

### ProvenanceEdge

```json
{
  "edge_id": "edge_01J...",
  "artifact_id": "art_01J...",
  "target_call_id": "call_gh_01J...",
  "target_path": "$.body",
  "match_type": "base64_decoded",
  "confidence": 0.96,
  "evidence": {
    "source_fingerprint": "sha256:...",
    "target_fingerprint": "sha256:..."
  }
}
```

### PolicyDecision

```json
{
  "decision_id": "dec_01J...",
  "call_id": "call_gh_01J...",
  "action": "DENY",
  "severity": "critical",
  "matched_rules": ["block_secret_to_external"],
  "reason": "Tracked secret data is flowing to an external write tool",
  "decided_at": "2026-07-18T08:00:03Z"
}
```

## 4. 追踪事件格式

轨迹采用 append-only JSONL：

```json
{"type":"tool_call_requested","trace_id":"tr_...","payload":{}}
{"type":"policy_decided","trace_id":"tr_...","payload":{}}
{"type":"tool_call_completed","trace_id":"tr_...","payload":{}}
{"type":"artifact_registered","trace_id":"tr_...","payload":{}}
{"type":"provenance_matched","trace_id":"tr_...","payload":{}}
```

所有事件包含：

- `event_id`
- `trace_id`
- `session_id`
- `timestamp`
- `schema_version`
- `payload`

## 5. 匹配管线

工具参数递归展开为标量字段：

```text
$.title
$.body
$.labels[0]
```

对字符串依次执行：

1. 原文精确匹配。
2. Unicode 与空白归一化。
3. Base64/Hex 候选解码。
4. 固定窗口子串匹配。
5. token 分片集合匹配。
6. 合并同一调用多个字段的拆分匹配。

每种匹配器返回：

```python
MatchResult(
    matched=True,
    match_type="base64_decoded",
    confidence=0.96,
    artifact_id="art_...",
    target_path="$.body",
)
```

## 6. 数据保留

- 原始敏感内容：仅会话内存，默认会话结束立即清除。
- 指纹和标签：保留用于回放和评测。
- 工具参数/响应：默认脱敏摘要。
- 测试 Canary：允许在隔离测试环境保存，但必须明确标记 `synthetic:true`。

## 7. Schema 版本

所有公共事件和 API 对象包含 `schema_version`。MVP 从 `1.0` 开始；新增可选字段不升级主版本，删除或改变语义才升级主版本。
