import { useEffect, useState } from "react";
import { CheckCircle2, PlugZap, RefreshCw, ShieldQuestion } from "lucide-react";
import { api } from "../api";
import type { MCPRegistry, RemoteGateway } from "../types";

export function MCPConnectionsPage() {
  const [registry, setRegistry] = useState<MCPRegistry | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [remoteGateway, setRemoteGateway] = useState<RemoteGateway | null>(null);

  useEffect(() => {
    void Promise.all([api.mcpServers(), api.remoteGateway()])
      .then(([nextRegistry, gateway]) => { setRegistry(nextRegistry); setRemoteGateway(gateway); })
      .catch(() => setError("无法读取 MCP 配置"));
  }, []);

  const discover = async () => {
    setChecking(true);
    setError(null);
    try {
      setRegistry(await api.discoverMcpServers());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "连接检查失败");
    } finally {
      setChecking(false);
    }
  };

  return (
    <section className="panel connections-page">
      <div className="panel-heading connections-heading">
        <div><span className="eyebrow">MCP REGISTRY</span><h2>MCP 接入中心</h2><p>查看下游服务、显式工具分类以及未授权暴露的工具。</p></div>
        <button className="verify-button" onClick={() => void discover()} disabled={checking}><RefreshCw size={17} className={checking ? "spinning" : ""} />{checking ? "正在发现工具…" : "检查全部连接"}</button>
      </div>
      {remoteGateway && <div className={`remote-gateway-banner ${remoteGateway.status}`}><div><span>REMOTE STREAMABLE HTTP GATEWAY</span><strong>{remoteGateway.endpoint}</strong></div><code>{remoteGateway.transport} · auth: {remoteGateway.authentication}</code><b>{remoteGateway.status.toUpperCase()}</b></div>}
      {registry && <div className="registry-meta"><span>配置文件</span><code>{registry.config_path}</code><span>最后检查</span><strong>{registry.last_checked_at ? new Date(registry.last_checked_at).toLocaleString() : "尚未执行"}</strong><span>状态</span><b className={registry.status === "healthy" ? "allow-text" : "configured-text"}>{registry.status.toUpperCase()}</b></div>}
      {error && <div className="playground-error">{error}</div>}
      <div className="server-grid">
        {registry?.servers.map((server) => <article className="server-card" key={server.id}>
          <header><div className="server-icon"><PlugZap size={21} /></div><div><strong>{server.id}</strong><code>{server.command}</code></div><span className={`server-status ${server.status}`}>{server.status === "healthy" ? <CheckCircle2 size={14} /> : <ShieldQuestion size={14} />}{server.status}</span></header>
          <div className="connection-tool-list">{server.tools.map((tool) => <div key={tool.expose_as}><span><strong>{tool.expose_as}</strong><small>{tool.downstream_name}</small></span><b className={`category-tag ${tool.category}`}>{tool.category}</b></div>)}</div>
          {!!server.hidden_tools?.length && <div className="hidden-tools"><ShieldQuestion size={16} />未分类工具已隐藏：{server.hidden_tools.join(", ")}</div>}
        </article>)}
      </div>
      {!registry && !error && <div className="empty-state">正在读取 MCP Registry…</div>}
    </section>
  );
}
