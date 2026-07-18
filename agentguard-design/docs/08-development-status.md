# 08 开发状态

更新时间：2026-07-18

## 已完成

### 工程基础

- uv + Python 3.11+ 项目结构。
- Ruff、Mypy strict、Pytest和覆盖率检查。
- CLI、运行目录和脱敏 JSONL Trace。

### 安全核心

- 会话级 DataArtifact 注册。
- 敏感路径与 Canary 分类。
- 原文、归一化、子串、Base64和Hex匹配。
- 跨工具参数字段拆分重组匹配。
- YAML策略加载、Schema验证、优先级和默认决策。
- `block_secret_to_external` 确定性策略。
- Baseline观察模式和Protected阻断模式。
- Trace Replay Engine，可在不调用模型和下游工具的情况下重新判定。
- 人工审批状态机。
- 一次性Approval Token，绑定会话、工具和参数摘要。
- Token过期、参数变化和重复消费检查。
- SQLite审批持久化，API与stdio MCP Gateway可跨进程共享。
- 数据库只持久化Token哈希，不保存可直接使用的原始Token。

### 真实 stdio MCP 链路

- Email Mock MCP Server。
- Filesystem Mock MCP Server。
- GitHub Mock MCP Server。
- 下游 MCP Client生命周期和工具契约验证。
- AgentGuard stdio MCP Gateway。
- Gateway公开工具：

```text
email.read
filesystem.read
github.create_issue
```

- 外部客户端到Gateway、再到三个下游Server的完整协议集成测试。

### FastAPI

- Health与概览指标。
- Trace列表和事件详情。
- 数据血缘节点与边。
- Active Policy与YAML验证。
- Trace Replay API。
- Approval列表、批准与拒绝。
- 自动OpenAPI文档。

### Benchmark

- 多模式批量场景执行。
- 每种模式可配置重复次数。
- Attack Success、Secret Leak、Issue Creation、Blocking和Task Completion指标。
- JSON与Markdown报告。
- Benchmark列表、运行、详情和报告API。
- In-process与真实stdio MCP两种Benchmark transport。
- Average、P50和P95场景耗时指标。

### React前端

- React 19 + TypeScript + Vite工程。
- 深色安全可观测性设计系统。
- 数据血缘图和Source→Artifact→Sink展示。
- 泄漏阻断证据、工具调用与变形检测面板。
- Benchmark结果表和防护对比条形图。
- Trace、Lineage与Benchmark API接入。
- API不可用时明确标记的合成演示数据。
- Trace选择器和脱敏事件详情抽屉。
- YAML策略验证页面。
- 离线Replay决策对比页面。
- Approval列表、批准、拒绝和一次性Token展示。

### 容器化

- Python API Dockerfile。
- Node构建与Nginx运行的前端Dockerfile。
- Nginx `/api` 反向代理。
- Docker Compose服务依赖与健康检查。
- 当前开发机未安装Docker CLI，Compose YAML结构已验证，实际镜像构建待Docker环境验证。

### 持续集成

- GitHub Actions后端Ruff、Mypy和Pytest。
- 前端npm构建和Vitest。
- API与Web Docker镜像构建。
- Docker Compose配置验证。

## 当前验证结果

```text
Ruff: 通过
Mypy strict: 通过
Pytest: 34 passed
Coverage: 88%
Frontend build: passed
Frontend tests: 2 passed
```

端到端场景：

| 模式 | 结果 |
|---|---|
| normal | 正常Issue写入成功 |
| baseline | 成功复现Canary泄漏 |
| protected | 原文泄漏被阻止，下游零写入 |
| protected-base64 | Base64泄漏被阻止，下游零写入 |
| protected-split | 跨字段拆分重组泄漏被阻止，下游零写入 |

## 运行命令

进程内快速测试：

```powershell
uv run agentguard demo --mode protected
```

真实 stdio MCP 测试：

```powershell
uv run agentguard mcp-demo --mode normal --project-root .
uv run agentguard mcp-demo --mode baseline --project-root .
uv run agentguard mcp-demo --mode protected --project-root .
uv run agentguard mcp-demo --mode protected-base64 --project-root .
uv run agentguard mcp-demo --mode protected-split --project-root .
uv run agentguard replay <trace.jsonl> --policy policies/default.yaml
uv run agentguard serve-api --runtime-dir runtime --policy policies/default.yaml
uv run agentguard benchmark --runs 10 --runtime-dir runtime-benchmark
cd web
npm run dev
```

## 与实施计划的对应关系

- M1透明代理：核心链路已完成；动态发现任意下游Server和配置文件仍待实现。
- M2数据流追踪：原文、子串、Base64、Hex和多字段拆分重组已完成。
- M3策略与回放：YAML策略、离线回放和人工审批已完成。
- M4 API与前端：FastAPI、Benchmark和React数据血缘第一阶段已完成。

## 下一开发批次

1. 前端浏览器端到端测试。
2. Gateway调用级延迟与资源使用指标。
3. 动态下游MCP配置和工具发现。
4. 根据GitHub Actions结果修复跨平台问题。
