import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import { api } from "./api";
import { Sidebar, type Page } from "./components/Sidebar";
import { demoBenchmark, demoLineage } from "./demo";
import { BenchmarkPage } from "./pages/BenchmarkPage";
import { LineagePage } from "./pages/LineagePage";
import type { Benchmark, Lineage } from "./types";

export default function App() {
  const [page, setPage] = useState<Page>("lineage");
  const [lineage, setLineage] = useState<Lineage>(demoLineage);
  const [benchmark, setBenchmark] = useState<Benchmark>(demoBenchmark);
  const [lineageLive, setLineageLive] = useState(false);
  const [benchmarkLive, setBenchmarkLive] = useState(false);

  useEffect(() => {
    void api.traces().then(async (traces) => {
      if (traces.length) {
        setLineage(await api.lineage(traces[0].trace_id));
        setLineageLive(true);
      }
    }).catch(() => undefined);
    void api.benchmarks().then((reports) => {
      if (reports.length) {
        setBenchmark(reports[0]);
        setBenchmarkLive(true);
      }
    }).catch(() => undefined);
  }, []);

  return (
    <div className="app-shell">
      <Sidebar page={page} onPageChange={setPage} />
      <main>
        <header className="topbar">
          <button className="project-selector"><span>Support Agent / MCP Gateway</span><ChevronDown size={17} /></button>
          <div className="gateway-status"><i />Gateway 已连接</div>
        </header>
        <div className="content">
          {page === "lineage" ? <LineagePage lineage={lineage} live={lineageLive} /> : <BenchmarkPage benchmark={benchmark} live={benchmarkLive} />}
        </div>
      </main>
    </div>
  );
}

