import { cn } from "@/lib/utils";

export type OrbState = "idle" | "listening" | "thinking" | "speaking";

interface SiriOrbProps {
  state: OrbState;
}

const stateLabels: Record<OrbState, string> = {
  idle: "Listening...",
  listening: "Hearing speech...",
  thinking: "Reasoning...",
  speaking: "Speaking...",
};

const SiriOrb = ({ state }: SiriOrbProps) => {
  return (
    <div className="flex flex-col items-center gap-3 py-4">
      <div
        className={cn(
          "relative w-[160px] h-[160px] rounded-full overflow-hidden transition-shadow duration-300",
          state === "speaking" && "shadow-[0_0_30px_rgba(99,102,241,0.4)]",
          state === "thinking" && "shadow-[0_0_20px_rgba(139,92,246,0.3)]",
          `orb-${state}`
        )}
      >
        {/* Layer 1 - Indigo */}
        <div
          className="orb-layer-1 absolute inset-0 opacity-60 will-change-transform"
          style={{
            background: "radial-gradient(circle at 30% 40%, #6366f1 0%, transparent 60%)",
            filter: "blur(20px)",
          }}
        />
        {/* Layer 2 - Violet */}
        <div
          className="orb-layer-2 absolute inset-0 opacity-60 will-change-transform"
          style={{
            background: "radial-gradient(circle at 70% 30%, #8b5cf6 0%, transparent 60%)",
            filter: "blur(20px)",
          }}
        />
        {/* Layer 3 - Cyan */}
        <div
          className="orb-layer-3 absolute inset-0 opacity-60 will-change-transform"
          style={{
            background: "radial-gradient(circle at 50% 70%, #06b6d4 0%, transparent 60%)",
            filter: "blur(20px)",
          }}
        />
        {/* Layer 4 - Pink */}
        <div
          className="orb-layer-4 absolute inset-0 opacity-60 will-change-transform"
          style={{
            background: "radial-gradient(circle at 25% 65%, #ec4899 0%, transparent 60%)",
            filter: "blur(20px)",
          }}
        />
        {/* Layer 5 - Emerald */}
        <div
          className="orb-layer-5 absolute inset-0 opacity-60 will-change-transform"
          style={{
            background: "radial-gradient(circle at 75% 60%, #10b981 0%, transparent 60%)",
            filter: "blur(20px)",
          }}
        />
      </div>
      <span className="text-xs text-muted-foreground">{stateLabels[state]}</span>
    </div>
  );
};

export default SiriOrb;
