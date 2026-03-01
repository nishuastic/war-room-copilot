import { useRef, useCallback, useState, useEffect } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphNode, GraphLink } from "@/data/mockData";

interface AgentGraphProps {
  nodes: GraphNode[];
  links: GraphLink[];
}

const AgentGraph = ({ nodes, links }: AgentGraphProps) => {
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 300 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let zoomTimer: ReturnType<typeof setTimeout>;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height: height - 10 });
      clearTimeout(zoomTimer);
      zoomTimer = setTimeout(() => {
        fgRef.current?.zoomToFit(400, 40);
      }, 300);
    });
    obs.observe(el);
    return () => { obs.disconnect(); clearTimeout(zoomTimer); };
  }, []);

  useEffect(() => {
    if (fgRef.current) {
      fgRef.current.d3Force("charge")?.strength(-200);
      fgRef.current.d3Force("link")?.distance(60);
    }
  }, []);

  const connectedNodes = useCallback(
    (nodeId: string) => {
      const connected = new Set<string>();
      connected.add(nodeId);
      links.forEach((l) => {
        const src = typeof l.source === "object" ? (l.source as any).id : l.source;
        const tgt = typeof l.target === "object" ? (l.target as any).id : l.target;
        if (src === nodeId) connected.add(tgt);
        if (tgt === nodeId) connected.add(src);
      });
      return connected;
    },
    [links]
  );

  const graphData = { nodes: nodes.map((n) => ({ ...n })), links: links.map((l) => ({ ...l })) };

  return (
    <div ref={containerRef} className="relative w-full h-full">
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="transparent"
        warmupTicks={50}
        cooldownTicks={100}
        onEngineStop={() => fgRef.current?.zoomToFit(400, 40)}
        nodeRelSize={6}
        linkDirectionalParticles={(link: any) => (link.active ? 4 : 0)}
        linkDirectionalParticleSpeed={0.005}
        linkDirectionalParticleWidth={2}
        linkColor={(link: any) => (link.active ? "#10b981" : "#1e2235")}
        linkWidth={(link: any) => (link.active ? 2 : 1)}
        onNodeHover={(node: any) => setHoveredNode(node?.id || null)}
        onNodeClick={(node: any) => {
          const found = nodes.find((n) => n.id === node.id);
          setSelectedNode(found || null);
        }}
        nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
          const size = 6 + (node.activationCount || 0) * 1.5;
          const isConnected = hoveredNode ? connectedNodes(hoveredNode).has(node.id) : true;
          const alpha = hoveredNode ? (isConnected ? 1 : 0.15) : 1;

          ctx.globalAlpha = alpha;

          // Glow for active nodes
          if (node.status === "running" || node.status === "completed") {
            ctx.beginPath();
            ctx.arc(node.x, node.y, size + 4, 0, 2 * Math.PI);
            ctx.fillStyle = node.status === "running" ? "rgba(16,185,129,0.3)" : "rgba(16,185,129,0.15)";
            ctx.fill();
          }
          if (node.status === "error") {
            ctx.beginPath();
            ctx.arc(node.x, node.y, size + 4, 0, 2 * Math.PI);
            ctx.fillStyle = "rgba(239,68,68,0.3)";
            ctx.fill();
          }

          // Node circle
          ctx.beginPath();
          ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
          ctx.fillStyle = node.color;
          ctx.fill();

          // Label
          const label = node.name;
          const fontSize = 10 / globalScale;
          ctx.font = `${fontSize}px 'JetBrains Mono', monospace`;
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillStyle = `rgba(228,228,231,${alpha})`;
          ctx.fillText(label, node.x, node.y + size + 3);

          ctx.globalAlpha = 1;
        }}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          const size = 6 + (node.activationCount || 0) * 1.5;
          ctx.beginPath();
          ctx.arc(node.x, node.y, size + 5, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
        }}
      />
      {selectedNode && (
        <div className="absolute bottom-2 left-2 right-2 glass-card p-3 text-xs">
          <div className="flex items-center justify-between mb-1">
            <span className="font-semibold text-foreground">{selectedNode.name}</span>
            <button onClick={() => setSelectedNode(null)} className="text-muted-foreground hover:text-foreground">✕</button>
          </div>
          <p className="text-muted-foreground">Status: {selectedNode.status}</p>
          <p className="text-muted-foreground">Activations: {selectedNode.activationCount}</p>
        </div>
      )}
    </div>
  );
};

export default AgentGraph;
