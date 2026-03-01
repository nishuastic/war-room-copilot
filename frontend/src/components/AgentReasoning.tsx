import { motion, AnimatePresence } from "framer-motion";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CheckCircle, Loader2, Github, BarChart3, Code } from "lucide-react";
import type { AgentTraceStep, Finding } from "@/data/mockData";

const skillColors: Record<string, string> = {
  investigate: "#3b82f6",
  summarize: "#8b5cf6",
  recall: "#10b981",
  respond: "#6b7280",
  contradict: "#f59e0b",
  postmortem: "#06b6d4",
};

const sourceIcons: Record<string, React.ReactNode> = {
  github: <Github className="w-3.5 h-3.5" />,
  metrics: <BarChart3 className="w-3.5 h-3.5" />,
  code: <Code className="w-3.5 h-3.5" />,
};

interface AgentReasoningProps {
  traceSteps: AgentTraceStep[];
  findings: Finding[];
}

const AgentReasoning = ({ traceSteps, findings }: AgentReasoningProps) => {
  return (
    <Tabs defaultValue="trace" className="flex flex-col h-full">
      <TabsList className="bg-secondary/50 mx-3 mt-2 shrink-0">
        <TabsTrigger value="trace" className="text-xs">Trace</TabsTrigger>
        <TabsTrigger value="findings" className="text-xs">Findings</TabsTrigger>
      </TabsList>

      <TabsContent value="trace" className="flex-1 overflow-hidden mt-0">
        <ScrollArea className="h-full">
          <div className="px-3 py-2 space-y-0">
            <AnimatePresence initial={false}>
              {traceSteps.map((step, i) => (
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.05 }}
                  className="flex gap-3 relative"
                >
                  {/* Timeline line */}
                  <div className="flex flex-col items-center w-4 shrink-0">
                    <div
                      className="w-3 h-3 rounded-full shrink-0 mt-1"
                      style={{ backgroundColor: skillColors[step.skill] || "#888" }}
                    />
                    {i < traceSteps.length - 1 && (
                      <div className="w-[2px] flex-1 bg-border" />
                    )}
                  </div>
                  <div className="pb-3 flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span
                        className="text-[10px] font-mono px-1.5 py-0.5 rounded uppercase"
                        style={{
                          color: skillColors[step.skill],
                          backgroundColor: `${skillColors[step.skill]}15`,
                        }}
                      >
                        {step.skill}
                      </span>
                      {step.status === "running" ? (
                        <Loader2 className="w-3 h-3 animate-spin text-wr-green" />
                      ) : step.status === "completed" ? (
                        <CheckCircle className="w-3 h-3 text-wr-green" />
                      ) : null}
                    </div>
                    <p className="text-xs text-foreground truncate">{step.query}</p>
                    <span className="text-[10px] font-mono text-muted-foreground">{step.duration}s</span>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </ScrollArea>
      </TabsContent>

      <TabsContent value="findings" className="flex-1 overflow-hidden mt-0">
        <ScrollArea className="h-full">
          <div className="px-3 py-2 space-y-2">
            <AnimatePresence initial={false}>
              {findings.map((f, i) => (
                <motion.div
                  key={f.id}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.05 }}
                  className="border-l-[3px] border-l-wr-purple bg-secondary/30 rounded-r-lg p-2.5"
                >
                  <div className="flex items-center gap-1.5 mb-1 text-wr-purple">
                    {sourceIcons[f.source]}
                    <span className="text-[10px] font-mono uppercase">{f.source}</span>
                  </div>
                  <p className="text-xs text-foreground">{f.text}</p>
                  <span className="text-[10px] font-mono text-muted-foreground">{f.timestamp}</span>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </ScrollArea>
      </TabsContent>
    </Tabs>
  );
};

export default AgentReasoning;
