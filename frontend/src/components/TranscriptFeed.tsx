import { useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Bot, AlertTriangle, CheckCircle, ArrowDown } from "lucide-react";
import type { TranscriptMessage, Speaker } from "@/data/mockData";

interface TranscriptFeedProps {
  messages: TranscriptMessage[];
  speakers: Speaker[];
}

const speakerColorMap: Record<number, string> = {
  1: "#38bdf8", 2: "#fb7185", 3: "#fbbf24", 4: "#34d399",
  5: "#a78bfa", 6: "#fb923c", 7: "#2dd4bf", 8: "#f472b6",
};

const TranscriptFeed = ({ messages, speakers }: TranscriptFeedProps) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showJump, setShowJump] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const getSpeaker = (id: number | "ai") => {
    if (id === "ai") return { name: "AI Agent", color: "#06b6d4" };
    const s = speakers.find((sp) => sp.id === id);
    return { name: s?.name || "Unknown", color: speakerColorMap[id as number] || "#888" };
  };

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowJump(distFromBottom > 100);
  };

  const jumpToBottom = () => bottomRef.current?.scrollIntoView({ behavior: "smooth" });

  return (
    <div className="flex-1 relative overflow-hidden">
      <ScrollArea className="h-full">
        <div className="px-3 pb-3 space-y-1" onScroll={handleScroll} ref={scrollRef}>
          <AnimatePresence initial={false}>
            {messages.map((msg) => {
              const speaker = getSpeaker(msg.speakerId);
              const isAI = msg.speakerId === "ai";
              const isContradiction = msg.type === "contradiction";
              const isDecision = msg.type === "decision";

              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className={`flex gap-2 py-1.5 px-2 rounded-lg ${
                    isAI || isContradiction || isDecision ? "bg-secondary/50" : ""
                  } ${isContradiction ? "border-l-[3px] border-l-wr-amber shadow-[0_0_15px_rgba(245,158,11,0.15)]" : ""}
                    ${isDecision ? "border-l-[3px] border-l-wr-green" : ""}
                    ${isAI && !isContradiction && !isDecision ? "border-l-[3px] border-l-accent" : ""}`}
                >
                  <span className="text-[11px] font-mono text-muted-foreground w-14 shrink-0 pt-0.5">
                    {msg.timestamp}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      {isAI && <Bot className="w-3 h-3" style={{ color: speaker.color }} />}
                      {isContradiction && <AlertTriangle className="w-3 h-3 text-wr-amber" />}
                      {isDecision && <CheckCircle className="w-3 h-3 text-wr-green" />}
                      <span
                        className="text-xs font-medium px-1.5 py-0.5 rounded"
                        style={{
                          color: speaker.color,
                          backgroundColor: `${speaker.color}15`,
                        }}
                      >
                        {speaker.name}
                      </span>
                    </div>
                    <p className={`text-sm text-foreground leading-relaxed ${
                      isContradiction ? "text-wr-amber" : isDecision ? "text-wr-green" : isAI ? "text-accent" : ""
                    }`}>
                      {msg.text}
                    </p>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
          <div ref={bottomRef} />
        </div>
      </ScrollArea>
      {showJump && (
        <button
          onClick={jumpToBottom}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1 px-3 py-1 rounded-full bg-primary text-primary-foreground text-xs"
        >
          <ArrowDown className="w-3 h-3" /> Jump to latest
        </button>
      )}
    </div>
  );
};

export default TranscriptFeed;
