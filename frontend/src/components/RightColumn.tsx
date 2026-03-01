import { motion, AnimatePresence } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, MessageSquare, Search, CheckCircle, AlertTriangle, Wrench, GitCommit, GitPullRequest, CircleDot } from "lucide-react";
import { LineChart, Line, ResponsiveContainer } from "recharts";
import { useState } from "react";
import type { Decision, TimelineEvent, Finding } from "@/data/mockData";
import { GIT_COMMITS, GIT_PRS, GIT_ISSUES, SPARKLINE_DATA } from "@/data/mockData";

interface RightColumnProps {
  decisions: Decision[];
  timeline: TimelineEvent[];
  findings: Finding[];
  messageCount: number;
  elapsed: string;
}

const timelineIcons: Record<string, React.ReactNode> = {
  transcript: <MessageSquare className="w-3 h-3" />,
  finding: <Search className="w-3 h-3" />,
  decision: <CheckCircle className="w-3 h-3" />,
  contradiction: <AlertTriangle className="w-3 h-3" />,
  tool_call: <Wrench className="w-3 h-3" />,
};

const timelineColors: Record<string, string> = {
  transcript: "#3b82f6",
  finding: "#8b5cf6",
  decision: "#10b981",
  contradiction: "#f59e0b",
  tool_call: "#06b6d4",
};

const prStatusColors: Record<string, string> = {
  merged: "bg-wr-purple",
  in_review: "bg-wr-amber",
  open: "bg-wr-green",
};

const Section = ({ title, defaultOpen = true, children }: { title: string; defaultOpen?: boolean; children: React.ReactNode }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex items-center justify-between w-full py-2 px-3">
        <span className="panel-header">{title}</span>
        <ChevronDown className={`w-3 h-3 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </CollapsibleTrigger>
      <CollapsibleContent className="px-3 pb-3">{children}</CollapsibleContent>
    </Collapsible>
  );
};

const SparklineChart = ({ data, color }: { data: number[]; color: string }) => (
  <ResponsiveContainer width="100%" height={30}>
    <LineChart data={data.map((v, i) => ({ v, i }))}>
      <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} dot={false} />
    </LineChart>
  </ResponsiveContainer>
);

const RightColumn = ({ decisions, timeline, findings, messageCount, elapsed }: RightColumnProps) => {
  return (
    <ScrollArea className="h-full">
      <div className="space-y-1">
        {/* Decisions */}
        <Section title="Decisions">
          <div className="space-y-2">
            <AnimatePresence initial={false}>
              {decisions.map((d) => (
                <motion.div
                  key={d.id}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ type: "spring", stiffness: 300, damping: 25 }}
                  className="flex gap-2"
                >
                  <div className="w-6 h-6 rounded-full bg-wr-green/20 text-wr-green flex items-center justify-center text-xs font-bold shrink-0">
                    {d.number}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm text-foreground">{d.text}</p>
                    <span className="text-[10px] font-mono text-muted-foreground">{d.speaker} · {d.timestamp}</span>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </Section>

        {/* Timeline */}
        <Section title="Timeline">
          <div className="space-y-0 relative">
            <div className="absolute left-[5px] top-0 bottom-0 w-[1px] bg-border" />
            <AnimatePresence initial={false}>
              {timeline.map((e, i) => (
                <motion.div
                  key={e.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2, delay: i * 0.03 }}
                  className="flex gap-2.5 py-1.5 relative"
                >
                  <div
                    className={`w-3 h-3 rounded-full shrink-0 mt-0.5 z-10 ${i === timeline.length - 1 ? "animate-pulse-dot" : ""}`}
                    style={{ backgroundColor: timelineColors[e.type] }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1 text-muted-foreground">
                      {timelineIcons[e.type]}
                      <span className="text-[10px] font-mono">{e.timestamp}</span>
                    </div>
                    <p className="text-xs text-foreground">{e.description}</p>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </Section>

        {/* Metrics */}
        <Section title="Metrics">
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "MESSAGES", value: messageCount, color: "#3b82f6", data: SPARKLINE_DATA.messages },
              { label: "DURATION", value: elapsed, color: "#f59e0b", data: null },
              { label: "FINDINGS", value: findings.length, color: "#8b5cf6", data: SPARKLINE_DATA.findings },
              { label: "DECISIONS", value: decisions.length, color: "#10b981", data: SPARKLINE_DATA.decisions },
            ].map((m) => (
              <div key={m.label} className="bg-secondary/50 rounded-lg p-3">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{m.label}</span>
                <div className="text-2xl font-mono font-bold tabular-nums" style={{ color: m.color }}>
                  {m.value}
                </div>
                {m.data && <SparklineChart data={m.data} color={m.color} />}
              </div>
            ))}
          </div>
        </Section>

        {/* Service Map */}
        <Section title="Service Map">
          <ServiceMap />
        </Section>

        {/* GitHub */}
        <Section title="GitHub" defaultOpen={false}>
          <div className="space-y-3">
            <div>
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1 block">Recent Commits</span>
              {GIT_COMMITS.map((c) => (
                <div key={c.hash} className={`flex items-center gap-2 py-1 ${c.suspect ? "text-wr-amber" : ""}`}>
                  <GitCommit className="w-3 h-3 shrink-0" />
                  <span className="text-[11px] font-mono text-accent">{c.hash}</span>
                  <span className="text-xs text-foreground truncate flex-1">{c.message}</span>
                  <span className="text-[10px] font-mono text-muted-foreground shrink-0">{c.time}</span>
                </div>
              ))}
            </div>
            <div>
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1 block">Open PRs</span>
              {GIT_PRS.map((pr) => (
                <div key={pr.number} className="flex items-center gap-2 py-1">
                  <GitPullRequest className="w-3 h-3 shrink-0 text-muted-foreground" />
                  <Badge variant="secondary" className="text-[10px] font-mono">#{pr.number}</Badge>
                  <span className="text-xs text-foreground truncate flex-1">{pr.title}</span>
                  <span className={`text-[9px] px-1.5 py-0.5 rounded text-primary-foreground ${prStatusColors[pr.status]}`}>{pr.status}</span>
                </div>
              ))}
            </div>
            <div>
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1 block">Issues</span>
              {GIT_ISSUES.map((issue) => (
                <div key={issue.number} className="flex items-center gap-2 py-1">
                  <CircleDot className="w-3 h-3 shrink-0 text-muted-foreground" />
                  <Badge variant="secondary" className="text-[10px] font-mono">#{issue.number}</Badge>
                  <span className="text-xs text-foreground truncate flex-1">{issue.title}</span>
                  <Badge variant={issue.label === "bug" ? "destructive" : "secondary"} className="text-[9px]">
                    {issue.label}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        </Section>
      </div>
    </ScrollArea>
  );
};

const ServiceMap = () => {
  const nodes = [
    { id: "api", label: "API Gateway", x: 150, y: 20, health: "green" },
    { id: "auth", label: "Auth Service", x: 50, y: 80, health: "green" },
    { id: "user", label: "User Service", x: 50, y: 140, health: "green" },
    { id: "order", label: "Order Service", x: 150, y: 80, health: "amber" },
    { id: "payment", label: "Payment Svc", x: 250, y: 80, health: "green" },
    { id: "stripe", label: "Stripe API", x: 250, y: 140, health: "green" },
    { id: "pg", label: "PostgreSQL", x: 120, y: 155, health: "red" },
    { id: "redis", label: "Redis Cache", x: 200, y: 140, health: "green" },
  ];
  const edges = [
    ["api", "auth"], ["auth", "user"], ["api", "order"],
    ["order", "payment"], ["payment", "stripe"],
    ["order", "pg"], ["order", "redis"],
  ];
  const healthColors: Record<string, string> = { green: "#10b981", amber: "#f59e0b", red: "#ef4444" };
  const nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]));

  return (
    <svg viewBox="0 0 310 180" className="w-full">
      {edges.map(([from, to]) => {
        const a = nodeMap[from], b = nodeMap[to];
        return (
          <line key={`${from}-${to}`} x1={a.x} y1={a.y + 10} x2={b.x} y2={b.y}
            stroke="hsl(232,22%,16%)" strokeWidth={1} strokeDasharray="4 2" />
        );
      })}
      {nodes.map((n) => (
        <g key={n.id}>
          {n.id === "pg" && (
            <rect x={n.x - 38} y={n.y - 12} width={76} height={28} rx={6}
              fill="none" stroke="#ef4444" strokeWidth={1.5}
              style={{ filter: "drop-shadow(0 0 8px rgba(239,68,68,0.5))" }} />
          )}
          <rect x={n.x - 35} y={n.y - 10} width={70} height={24} rx={5}
            fill="hsl(230,24%,14%)" stroke="hsl(232,22%,16%)" strokeWidth={1} />
          <circle cx={n.x - 24} cy={n.y + 2} r={3} fill={healthColors[n.health]} />
          <text x={n.x - 15} y={n.y + 5} fill="hsl(240,5%,90%)" fontSize={8}
            fontFamily="'JetBrains Mono', monospace">
            {n.label}
          </text>
        </g>
      ))}
    </svg>
  );
};

export default RightColumn;
