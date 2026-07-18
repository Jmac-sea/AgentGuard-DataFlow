import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import { api } from "./api";
import { Sidebar, type Page } from "./components/Sidebar";
import { demoBenchmark, demoLineage } from "./demo";
import { BenchmarkPage } from "./pages/BenchmarkPage";
import { ApprovalPage } from "./pages/ApprovalPage";
import { LineagePage } from "./pages/LineagePage";
import { PolicyPage } from "./pages/PolicyPage";
import { ReplayPage } from "./pages/ReplayPage";
import type { Benchmark, Lineage, TraceEvent, TraceSummary } from "./types";

export default function App() {
  const [page, setPage] = useState<Page>("lineage");
  const [lineage, setLineage] = useState<Lineage>(demoLineage);
  const [benchmark, setBenchmark] = useState<Benchmark>(demoBenchmark);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [selectedTrace, setSelectedTrace] = useState(demoLineage.trace_id);
  const [lineageLive, setLineageLive] = useState(false);
  const [benchmarkLive, setBenchmarkLive] = useState(false);
  const [apiStatus, setApiStatus] = useState<"loading" | "live" | "offline">("loading");

  useEffect(() => {
    const load = async () => {
      let connected = false;
      const [traceResult, benchmarkResult] = await Promise.allSettled([
        api.traces(),
        api.benchmarks(),
      ]);
      if (traceResult.status === "fulfilled") {
        setTraces(traceResult.value);
        connected = true;
        if (traceResult.value.length) {
          const traceId = traceResult.value[0].trace_id;
          const [nextLineage, detail] = await Promise.all([
            api.lineage(traceId),
            api.trace(traceId),
          ]);
          setSelectedTrace(traceId);
          setLineage(nextLineage);
          setEvents(detail.events);
          setLineageLive(true);
        }
      }
      if (benchmarkResult.status === "fulfilled") {
        connected = true;
        if (benchmarkResult.value.length) {
          setBenchmark(benchmarkResult.value[0]);
          setBenchmarkLive(true);
        }
      }
      setApiStatus(connected ? "live" : "offline");
    };
    void load().catch(() => setApiStatus("offline"));
  }, []);

  const changeTrace = async (traceId: string) => {
    setSelectedTrace(traceId);
    const [nextLineage, detail] = await Promise.all([api.lineage(traceId), api.trace(traceId)]);
    setLineage(nextLineage);
    setEvents(detail.events);
  };

  const content = (() => {
    if (page === "lineage") return <LineagePage lineage={lineage} live={lineageLive} traces={traces} selectedTrace={selectedTrace} onTraceChange={(traceId) => void changeTrace(traceId)} events={events} />;
    if (page === "benchmark") return <BenchmarkPage benchmark={benchmark} live={benchmarkLive} />;
    if (page === "policy") return <PolicyPage />;
    if (page === "replay") return <ReplayPage traces={traces} />;
    return <ApprovalPage />;
  })();

  return (
    <div className="app-shell">
      <Sidebar page={page} onPageChange={setPage} />
      <main>
        <header className="topbar">
          <button className="project-selector"><span>Support Agent / MCP Gateway</span><ChevronDown size={17} /></button>
          <div className={`gateway-status ${apiStatus}`}><i />{apiStatus === "loading" ? "正在连接 Gateway" : apiStatus === "live" ? "Gateway 已连接" : "离线演示模式"}</div>
        </header>
        <div className="content">
          {content}
        </div>
      </main>
    </div>
  );
}
