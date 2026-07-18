# 03 策略 DSL

## 1. 设计目标

策略 DSL 负责把数据来源、敏感级别、目标工具和匹配证据转换为可解释决策。MVP 使用 YAML，要求：

- 可读、可版本化、可测试。
- 决策确定性，不依赖 LLM。
- 默认拒绝冲突或无效策略部署。
- 每次决策返回命中规则和证据。

## 2. 策略文件结构

```yaml
version: "1.0"
policy_id: default-mcp-policy
defaults:
  read: allow
  internal_write: require_approval
  external_write: require_approval
  execute: deny

rules:
  - id: block_secret_to_external
    description: Block tracked secret data from external write tools
    priority: 100
    when:
      all:
        - target.category.eq: external_write
        - provenance.labels.contains: sensitivity:secret
        - provenance.confidence.gte: 0.85
    action: deny
    severity: critical
```

## 3. 可用字段

### Target

```text
target.tool
target.server
target.category
target.arguments.<path>
```

### Provenance

```text
provenance.exists
provenance.source_tool
provenance.resource
provenance.labels
provenance.match_type
provenance.confidence
```

### Session

```text
session.agent_id
session.environment
session.approved_scopes
session.policy_version
```

### Trace

```text
trace.call_count
trace.external_write_count
trace.sensitive_read_count
```

## 4. 条件操作符

MVP 支持：

```text
eq / neq
in / not_in
contains
starts_with
matches
gte / lte
exists
all / any / not
```

不允许在策略中执行任意 Python 或 Shell 表达式。

## 5. 示例策略

### 阻止秘密写入外部系统

```yaml
- id: block_secret_to_external
  priority: 100
  when:
    all:
      - target.category: external_write
      - provenance.labels.contains: sensitivity:secret
      - provenance.confidence.gte: 0.85
  action: deny
  severity: critical
```

### 中等置信度进入审批

```yaml
- id: review_possible_secret_leak
  priority: 80
  when:
    all:
      - target.category: external_write
      - provenance.confidence.gte: 0.60
      - provenance.confidence.lte: 0.849
  action: require_approval
  severity: high
```

### 禁止测试 Agent 调用真实外部写工具

```yaml
- id: deny_external_write_in_test
  priority: 90
  when:
    all:
      - session.environment: test
      - target.category: external_write
      - target.server.not_in: [mock-github, mock-email]
  action: deny
  severity: high
```

### 允许公开信息创建 Issue

```yaml
- id: allow_public_issue
  priority: 50
  when:
    all:
      - target.tool: github.create_issue
      - provenance.labels.not_contains: sensitivity:secret
      - provenance.labels.not_contains: sensitivity:pii
  action: allow
  severity: info
```

## 6. 冲突处理

1. 匹配规则按 `priority` 从高到低排序。
2. 同优先级采用更严格决策：`DENY > REQUIRE_APPROVAL > ALLOW`。
3. 未匹配时使用工具类别默认值。
4. 规则 ID 必须唯一。
5. 策略加载前执行静态验证和测试用例。

## 7. 策略测试

策略文件可附带测试：

```yaml
tests:
  - name: secret_to_github_is_denied
    input:
      target:
        tool: github.create_issue
        category: external_write
      provenance:
        labels: [sensitivity:secret]
        confidence: 0.96
    expected:
      action: deny
      rule: block_secret_to_external
```

CLI：

```text
agentguard policy validate policies/default.yaml
agentguard policy test policies/default.yaml
```

## 8. 审批语义

`REQUIRE_APPROVAL` 产生待审批记录，包含脱敏参数、来源、匹配方式和风险解释。MVP 只实现本地审批 API；审批后生成一次性 `approval_token`，绑定：

- session_id
- call_id
- 参数摘要
- 过期时间

Token绑定会话、工具名称和规范化参数摘要。参数变化后原审批自动失效；Token过期或成功使用一次后也不能再次使用。原始请求的 `call_id` 保留用于审计。
