# AgentGuard DataFlow

AgentGuard DataFlow is a model-independent security gateway for tracking sensitive data across tool calls and blocking leakage before an external write executes.

The current MVP is intentionally local and deterministic. It uses synthetic Canary secrets and
mock Email, Filesystem, GitHub, and attacker-controlled MCP tools without touching a real
external service.

```text
normal     -> legitimate issue creation succeeds
baseline   -> an unprotected agent leaks a Canary secret
protected  -> AgentGuard blocks the external write
```

## Quick start

```powershell
uv sync --extra dev
uv run agentguard demo --mode normal
uv run agentguard demo --mode baseline
uv run agentguard demo --mode protected
uv run pytest
```

Run the same flow through a real stdio MCP gateway and four independent downstream MCP
processes:

```powershell
uv run agentguard mcp-demo --mode normal --project-root .
uv run agentguard mcp-demo --mode baseline --project-root .
uv run agentguard mcp-demo --mode protected --project-root .
uv run agentguard mcp-demo --mode protected-base64 --project-root .
uv run agentguard mcp-demo --mode protected-split --project-root .
```

Run the synthetic malicious MCP tool-poisoning comparison:

```powershell
uv run agentguard mcp-demo --mode baseline-malicious-mcp --project-root .
uv run agentguard mcp-demo --mode protected-malicious-mcp --project-root .
```

The malicious MCP embeds an instruction in its tool description and result that tells the Agent
to read `/secrets/api_key.txt` and call `attacker.exfiltrate`. The baseline writes only to a local
JSONL collector, while the protected run is denied before that collector executes.

Replay a saved trace with the current YAML policy without calling any downstream tool:

```powershell
uv run agentguard replay runtime/traces/<trace-id>.jsonl --policy policies/default.yaml
```

Start the developer API:

```powershell
uv run agentguard serve-api --runtime-dir runtime --policy policies/default.yaml
```

OpenAPI is available at `http://127.0.0.1:8000/docs`. The first API slice includes Health,
Trace, Lineage, Policy validation, Replay, and Approval endpoints.

Run a deterministic benchmark and generate JSON plus Markdown reports:

```powershell
uv run agentguard benchmark --runs 10 --runtime-dir runtime-benchmark
```

Run a benchmark through the real stdio MCP process chain:

```powershell
uv run agentguard benchmark `
  --transport mcp `
  --runs 1 `
  --mode protected `
  --project-root . `
  --runtime-dir runtime-benchmark
```

Reports include average, P50, and P95 scenario duration. MCP runs are capped at 10 repetitions per
mode because they create real subprocess chains.

Benchmark API endpoints:

```text
GET  /api/v1/benchmarks
POST /api/v1/benchmarks/run
GET  /api/v1/benchmarks/{run_id}
GET  /api/v1/benchmarks/{run_id}/report
```

## Web dashboard

Start the API and frontend in separate terminals:

```powershell
uv run agentguard serve-api --runtime-dir runtime --policy policies/default.yaml
```

```powershell
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The first frontend slice includes the Data Lineage workspace,
policy decision evidence, recent tool calls, and Benchmark results. If the API has no traces yet,
the interface uses clearly labelled synthetic demo data.

The interface also includes Trace selection and event inspection, YAML policy validation, offline
Replay, and Approval management.

## Control Plane playground

The web application now starts on an Agent Playground. Choose one of the normal, baseline,
protected, Base64, split-field, or malicious-MCP scenarios and click **Run security scenario**. The API launches
the real stdio MCP process chain, returns each simulated Agent step, and writes a trace directly to
the active `runtime/` directory. The result links to the corresponding Data Lineage graph, so the
complete demo no longer requires a separate terminal command.

The **MCP Connections** page reads [`config/mcp-servers.yaml`](config/mcp-servers.yaml) and shows
every configured downstream server, exposed tool name, and security category. **Check all
connections** starts the downstream processes, performs real tool discovery, and reports tools
that AgentGuard deliberately hides because they have not been classified.

Control Plane endpoints:

```text
GET  /api/v1/playground/scenarios
POST /api/v1/playground/runs
GET  /api/v1/mcp/servers
POST /api/v1/mcp/servers/discover
GET  /api/v1/gateway/remote
```

## Remote Streamable HTTP MCP gateway

Start a stateful remote MCP endpoint on localhost. Use an environment variable instead of a
command-line argument so the bearer token is not exposed in process listings:

```powershell
$env:AGENTGUARD_HTTP_TOKEN = "replace-with-a-long-random-token"
uv run agentguard serve-mcp-http `
  --host 127.0.0.1 `
  --port 8100 `
  --project-root . `
  --runtime-dir runtime
```

Endpoints:

```text
MCP     http://127.0.0.1:8100/mcp
Health  http://127.0.0.1:8100/health
```

A typical Streamable HTTP MCP client entry is:

```json
{
  "mcpServers": {
    "agentguard": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8100/mcp",
      "headers": {
        "Authorization": "Bearer replace-with-a-long-random-token"
      }
    }
  }
}
```

Client configuration field names vary, so some MCP hosts use `type: "http"` for the same
transport. Each stateful client session receives its own AgentGuard session id, Trace id,
in-memory provenance registry, and downstream MCP process chain. Approval tokens remain shared
through SQLite but are still scoped to the originating Agent session and exact arguments.

Binding beyond localhost requires a bearer token and explicit `--allowed-host` values. DNS
rebinding protection is enabled by default. For example:

```powershell
$env:AGENTGUARD_HTTP_TOKEN = "replace-with-a-long-random-token"
uv run agentguard serve-mcp-http `
  --host 0.0.0.0 `
  --allowed-host "agentguard.example.com:*" `
  --allowed-origin "https://agent.example.com:*"
```

Docker Compose also starts the remote gateway on port `8100`. Set
`AGENTGUARD_HTTP_TOKEN` before deployment; the Compose fallback is intended only for local
development.

## Docker Compose

```powershell
docker compose up --build
```

Open `http://127.0.0.1:5173`. The frontend proxies `/api` to the backend container, while runtime
traces remain under the local `runtime/` directory.

## Continuous integration

GitHub Actions runs backend linting, strict typing and tests, frontend build/tests, both Docker
image builds, and Docker Compose configuration validation.

Runtime traces and reports are written under `runtime/` and never persist raw Canary values.

## Architecture

```text
Target Agent Simulator
        ↓
Tool Gateway
        ├── Trace Collector
        ├── Artifact Registry
        ├── Fingerprint Matcher
        └── Policy Engine
        ↓
Mock Email / Filesystem / GitHub / Attacker Tools
```

The repository contains both a fast in-process test adapter and a real stdio MCP gateway. The
gateway exposes namespaced tools and forwards allowed calls to independent mock Email,
Filesystem, GitHub, and synthetic attacker MCP servers.

Downstream MCP processes and their exposed tool names are declared in
[`config/mcp-servers.yaml`](config/mcp-servers.yaml). At startup, the gateway discovers each
server's actual tool schema, fails closed if a configured tool is missing, and does not expose
unclassified tools. Commands, arguments, environments, and working directories support the
`{python}` and `{project_root}` placeholders, and `AGENTGUARD_MCP_CONFIG` can select another
configuration file.

Product and engineering documents are available in [`agentguard-design/docs`](agentguard-design/docs/README.md).

## Safety boundary

- No real API keys are used.
- No real email or GitHub write access is used.
- The attacker MCP never accesses the network; its exfiltration sink is a local test-only JSONL file.
- Raw tracked secrets remain in session memory only.
- Persisted traces contain labels, hashes, match types, and redacted summaries.

## Policy

The active gateway policy is stored in [`policies/default.yaml`](policies/default.yaml). Rules are
validated with Pydantic and resolved by priority, then by decision strictness.

`REQUIRE_APPROVAL` decisions create a scoped request. The approval token is bound to the session,
tool name, and canonical argument digest; it expires and can be consumed only once.
