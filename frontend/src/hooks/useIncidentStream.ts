import { useState, useEffect, useCallback } from "react";
import {
  TRANSCRIPT, AGENT_TRACE, FINDINGS, DECISIONS, TIMELINE_EVENTS,
  GRAPH_NODES, GRAPH_LINKS, SPEAKERS,
  type TranscriptMessage, type AgentTraceStep, type Finding,
  type Decision, type TimelineEvent, type GraphNode, type GraphLink,
  type Speaker,
} from "@/data/mockData";
import { toast } from "sonner";

export type ConnectionStatus = "connected" | "disconnected" | "reconnecting";
export type OrbState = "idle" | "listening" | "thinking" | "speaking";

const API_URL = import.meta.env.VITE_API_URL || "";

export function useIncidentStream() {
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [traceSteps, setTraceSteps] = useState<AgentTraceStep[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>(GRAPH_NODES);
  const [graphLinks] = useState<GraphLink[]>(GRAPH_LINKS);
  const [speakers, setSpeakers] = useState<Speaker[]>(API_URL ? [] : SPEAKERS);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>(
    API_URL ? "disconnected" : "connected"
  );
  const [orbState, setOrbState] = useState<OrbState>("idle");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Load mock data when no API_URL is set
  useEffect(() => {
    if (API_URL) return;

    setMessages(TRANSCRIPT);
    setTraceSteps(AGENT_TRACE);
    setFindings(FINDINGS);
    setDecisions(DECISIONS);
    setTimeline(TIMELINE_EVENTS);
    setElapsedSeconds(300);

    setTimeout(() => toast.info("3 related GitHub issues found", { duration: 5000 }), 1000);
    setTimeout(() => toast.warning("Contradiction detected: deploy timing mismatch", { duration: 5000 }), 2500);
    setTimeout(() => toast.success("Decision captured: 3 action items", { duration: 5000 }), 4000);
  }, []);

  // Cycle orb state for demo (only when no API_URL)
  useEffect(() => {
    if (API_URL) return;
    const states: OrbState[] = ["idle", "listening", "thinking", "speaking"];
    let i = 0;
    const interval = setInterval(() => {
      i = (i + 1) % states.length;
      setOrbState(states[i]);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Elapsed timer
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsedSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Hydrate initial state from /state endpoint on mount
  useEffect(() => {
    if (!API_URL) return;

    fetch(`${API_URL}/state`)
      .then((r) => r.json())
      .then((data) => {
        if (data.transcript?.length) setMessages(data.transcript);
        if (data.findings?.length) setFindings(data.findings);
        if (data.decisions?.length) setDecisions(data.decisions);
        if (data.speakers?.length) setSpeakers(data.speakers);
        if (data.timeline?.length) setTimeline(data.timeline);
        if (data.graph_traces?.length) setTraceSteps(data.graph_traces);
        if (data.orb_state) setOrbState(data.orb_state);
      })
      .catch(() => {
        // Silently fail — SSE will catch up
      });
  }, []);

  // SSE connection (when API_URL is set)
  useEffect(() => {
    if (!API_URL) return;

    const eventSource = new EventSource(`${API_URL}/events`);
    eventSource.onopen = () => setConnectionStatus("connected");
    eventSource.onerror = () => {
      setConnectionStatus("disconnected");
      setTimeout(() => {
        if (eventSource.readyState === EventSource.CONNECTING) {
          setConnectionStatus("reconnecting");
        }
      }, 1000);
    };

    eventSource.onmessage = (event) => {
      const parsed = JSON.parse(event.data);
      switch (parsed.type) {
        case "transcript":
          setMessages((prev) =>
            prev.some((m) => m.id === parsed.data.id) ? prev : [...prev, parsed.data]
          );
          break;
        case "finding":
          setFindings((prev) => {
            if (prev.some((f) => f.id === parsed.data.id)) return prev;
            toast.info(parsed.data.text?.slice(0, 80), { duration: 5000 });
            return [...prev, parsed.data];
          });
          break;
        case "decision":
          setDecisions((prev) => {
            if (prev.some((d) => d.id === parsed.data.id)) return prev;
            toast.success(`Decision: ${parsed.data.text?.slice(0, 80)}`, { duration: 5000 });
            return [...prev, parsed.data];
          });
          break;
        case "graph_trace":
          setTraceSteps((prev) => {
            if (prev.some((s) => s.id === parsed.data.id)) return prev;
            setGraphNodes((nodes) =>
              nodes.map((n) =>
                n.id === parsed.data.skill
                  ? { ...n, status: "completed" as const, activationCount: n.activationCount + 1 }
                  : n
              )
            );
            return [...prev, parsed.data];
          });
          break;
        case "timeline":
          setTimeline((prev) =>
            prev.some((t) => t.id === parsed.data.id) ? prev : [...prev, parsed.data]
          );
          break;
        case "speaker_update":
          setSpeakers((prev) => {
            const exists = prev.find((s) => s.id === parsed.data.id);
            if (exists) return prev.map((s) => (s.id === parsed.data.id ? parsed.data : s));
            return [...prev, parsed.data];
          });
          break;
        case "orb_state":
          setOrbState(parsed.data.state);
          break;
        case "graph_update":
          setGraphNodes((prev) =>
            prev.map((n) => (n.id === parsed.data.id ? { ...n, ...parsed.data } : n))
          );
          break;
        case "error":
          toast.error(parsed.data, { duration: 5000 });
          break;
      }
    };

    return () => eventSource.close();
  }, []);

  const formatElapsed = useCallback(() => {
    const h = Math.floor(elapsedSeconds / 3600).toString().padStart(2, "0");
    const m = Math.floor((elapsedSeconds % 3600) / 60).toString().padStart(2, "0");
    const s = (elapsedSeconds % 60).toString().padStart(2, "0");
    return `${h}:${m}:${s}`;
  }, [elapsedSeconds]);

  return {
    messages, traceSteps, findings, decisions, timeline,
    graphNodes, graphLinks, speakers,
    connectionStatus, orbState, elapsedSeconds, formatElapsed,
  };
}
