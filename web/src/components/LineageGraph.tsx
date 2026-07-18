import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { FileKey2, Mail, OctagonX, Server } from "lucide-react";
import "@xyflow/react/dist/style.css";
import type { Lineage } from "../types";

type SecurityNodeData = { label: string; subtitle: string; status: string; kind: string };

function SecurityNode({ data }: NodeProps<Node<SecurityNodeData>>) {
  const Icon = data.kind === "artifact" ? FileKey2 : data.label.includes("email") ? Mail : data.status === "blocked" ? OctagonX : Server;
  return (
    <div className={`security-node ${data.status}`}>
      <Handle type="target" position={Position.Left} />
      <Icon size={24} />
      <strong>{data.label}</strong>
      <span>{data.subtitle}</span>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { security: SecurityNode };

export function LineageGraph({ lineage }: { lineage: Lineage }) {
  const nodes: Node<SecurityNodeData>[] = lineage.nodes.map((node, index) => ({
    id: node.id,
    type: "security",
    position: { x: 30 + index * 220, y: node.type === "data_artifact" ? 145 : 70 },
    data: {
      label: node.label,
      subtitle: node.labels?.[0] ?? node.category ?? node.type,
      status: node.status,
      kind: node.type === "data_artifact" ? "artifact" : "tool",
    },
  }));
  const edges: Edge[] = lineage.edges.map((edge, index) => ({
    id: `edge-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.confidence ? `${edge.type} · ${Math.round(edge.confidence * 100)}%` : edge.type,
    animated: edge.confidence !== undefined,
    className: edge.confidence ? "critical-edge" : "",
  }));

  return (
    <div className="lineage-canvas">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
        <Background color="#20334d" gap={26} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

