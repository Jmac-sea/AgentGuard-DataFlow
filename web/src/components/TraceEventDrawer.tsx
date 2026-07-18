import { X } from "lucide-react";
import type { TraceEvent } from "../types";

export function TraceEventDrawer({ event, onClose }: { event: TraceEvent | null; onClose: () => void }) {
  if (!event) return null;
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="event-drawer" onClick={(current) => current.stopPropagation()}>
        <div className="drawer-heading">
          <div><span className="eyebrow">{event.event_id}</span><h2>{event.type}</h2></div>
          <button aria-label="关闭事件详情" onClick={onClose}><X size={20} /></button>
        </div>
        <dl className="event-meta">
          <div><dt>Trace</dt><dd>{event.trace_id}</dd></div>
          <div><dt>Session</dt><dd>{event.session_id}</dd></div>
          <div><dt>Time</dt><dd>{new Date(event.timestamp).toLocaleString()}</dd></div>
        </dl>
        <h3>脱敏事件载荷</h3>
        <pre>{JSON.stringify(event.payload, null, 2)}</pre>
      </aside>
    </div>
  );
}

