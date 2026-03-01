export interface Speaker {
  id: number;
  name: string;
  role: string;
  colorVar: string; // e.g. "--speaker-1"
}

export interface TranscriptMessage {
  id: string;
  timestamp: string; // "+MM:SS"
  speakerId: number | "ai";
  text: string;
  type: "normal" | "ai" | "contradiction" | "decision";
}

export interface AgentTraceStep {
  id: string;
  skill: string;
  query: string;
  duration: number; // seconds
  status: "idle" | "running" | "completed" | "error";
  timestamp: string;
}

export interface Finding {
  id: string;
  text: string;
  source: "github" | "metrics" | "code";
  timestamp: string;
}

export interface Decision {
  id: string;
  number: number;
  text: string;
  speaker: string;
  timestamp: string;
}

export interface TimelineEvent {
  id: string;
  type: "transcript" | "finding" | "decision" | "contradiction" | "tool_call";
  description: string;
  timestamp: string;
}

export interface GraphNode {
  id: string;
  name: string;
  group: "input" | "router" | "skill" | "tool";
  color: string;
  status: "idle" | "running" | "completed" | "error";
  activationCount: number;
}

export interface GraphLink {
  source: string;
  target: string;
  active: boolean;
}

export interface GitCommit {
  hash: string;
  message: string;
  time: string;
  suspect: boolean;
}

export interface GitPR {
  number: number;
  title: string;
  status: "merged" | "in_review" | "open";
}

export interface GitIssue {
  number: number;
  title: string;
  label: "bug" | "feature" | "enhancement";
  status: "open" | "closed";
}

export const SPEAKERS: Speaker[] = [
  { id: 1, name: "Sarah Chen", role: "Incident Commander", colorVar: "--speaker-1" },
  { id: 2, name: "Marcus Johnson", role: "SRE", colorVar: "--speaker-2" },
  { id: 3, name: "Priya Patel", role: "Backend Lead", colorVar: "--speaker-3" },
  { id: 4, name: "Alex Kim", role: "DBA", colorVar: "--speaker-4" },
];

export const TRANSCRIPT: TranscriptMessage[] = [
  { id: "t1", timestamp: "+00:00", speakerId: 1, text: "Alright everyone, we've got a SEV-1. Checkout service is returning 503s. PagerDuty fired 3 minutes ago.", type: "normal" },
  { id: "t2", timestamp: "+00:15", speakerId: 2, text: "I'm seeing connection pool exhaustion on the primary PostgreSQL instance. Active connections jumped from 50 to 500 in the last 10 minutes.", type: "normal" },
  { id: "t3", timestamp: "+00:32", speakerId: 3, text: "That correlates with our deploy at 2pm. We pushed a new query to the product recommendation engine.", type: "normal" },
  { id: "t4", timestamp: "+00:45", speakerId: 4, text: "Checking the slow query log now. I see a full table scan on the orders table — no index on the new column.", type: "normal" },
  { id: "t5", timestamp: "+01:02", speakerId: 1, text: "Marcus, can you check if we can increase the connection pool limit temporarily?", type: "normal" },
  { id: "t6", timestamp: "+01:15", speakerId: 2, text: "Pool is maxed at 500. We can bump to 750 but that's a band-aid. The real fix is that missing index.", type: "normal" },
  { id: "t7", timestamp: "+01:30", speakerId: "ai", text: "I found 3 related issues in the checkout-service repo. Issue #1247 reports similar connection exhaustion from last month. The fix was adding a composite index on (user_id, created_at).", type: "ai" },
  { id: "t8", timestamp: "+01:48", speakerId: 4, text: "That's exactly the pattern. The new recommendation query is scanning orders WHERE user_id = ? ORDER BY created_at without an index.", type: "normal" },
  { id: "t9", timestamp: "+02:05", speakerId: 3, text: "I can push the index migration now. It should be safe to run concurrently on PostgreSQL.", type: "normal" },
  { id: "t10", timestamp: "+02:15", speakerId: 1, text: "Go ahead Priya. Marcus, bump the pool to 750 as a stopgap.", type: "normal" },
  { id: "t11", timestamp: "+02:30", speakerId: "ai", text: "⚠️ Contradiction detected: Marcus said the deploy was recent, but Priya mentioned the deploy was at 2pm. Current time is 4:30pm — that's 2.5 hours ago. The connection spike started only 10 minutes ago. Something else may have triggered the spike.", type: "contradiction" },
  { id: "t12", timestamp: "+02:52", speakerId: 2, text: "Good catch. Let me check... there was a cron job that kicked off at 4:20pm that runs the recommendation query for all users. That's what saturated the pool.", type: "normal" },
  { id: "t13", timestamp: "+03:10", speakerId: 4, text: "Confirmed. The cron job is the trigger, not the deploy itself. The deploy added the bad query, but the cron amplified it.", type: "normal" },
  { id: "t14", timestamp: "+03:25", speakerId: 1, text: "Alright, decision: Priya pushes the index. Marcus kills the cron job immediately and bumps the pool. Alex, monitor recovery.", type: "normal" },
  { id: "t15", timestamp: "+03:40", speakerId: "ai", text: "Decision captured: Push composite index migration, kill recommendation cron job, bump connection pool to 750.", type: "decision" },
  { id: "t16", timestamp: "+04:00", speakerId: 3, text: "Index migration running. CREATE INDEX CONCURRENTLY, should take about 2 minutes.", type: "normal" },
  { id: "t17", timestamp: "+04:30", speakerId: 2, text: "Cron killed. Pool bumped. Active connections dropping — down to 200 already.", type: "normal" },
  { id: "t18", timestamp: "+05:00", speakerId: 1, text: "Connections normalizing. Error rate back to baseline. Let's monitor for 15 minutes then downgrade to SEV-2.", type: "normal" },
];

export const AGENT_TRACE: AgentTraceStep[] = [
  { id: "s1", skill: "investigate", query: "Route to investigation skill", duration: 0.3, status: "completed", timestamp: "+01:25" },
  { id: "s2", skill: "investigate", query: 'Search "connection pool checkout"', duration: 1.8, status: "completed", timestamp: "+01:26" },
  { id: "s3", skill: "investigate", query: "Found 3 related issues", duration: 1.2, status: "completed", timestamp: "+01:28" },
  { id: "s4", skill: "contradict", query: "Route to contradiction detection", duration: 0.2, status: "completed", timestamp: "+02:28" },
  { id: "s5", skill: "contradict", query: "Timeline contradiction detected", duration: 0.8, status: "completed", timestamp: "+02:29" },
  { id: "s6", skill: "summarize", query: "Capture 1 decision", duration: 0.3, status: "completed", timestamp: "+03:38" },
];

export const FINDINGS: Finding[] = [
  { id: "f1", text: "Issue #1247: Connection pool exhaustion — fixed with composite index on (user_id, created_at)", source: "github", timestamp: "+01:30" },
  { id: "f2", text: "PR #892: Added recommendation query to checkout-service — merged 2 days ago", source: "github", timestamp: "+01:30" },
  { id: "f3", text: "3 similar incidents in the last quarter involving PostgreSQL connection exhaustion", source: "metrics", timestamp: "+01:30" },
  { id: "f4", text: "Cron job 'daily-recommendations' runs at 4:20pm UTC, triggers bulk ORDER BY queries", source: "code", timestamp: "+02:52" },
];

export const DECISIONS: Decision[] = [
  { id: "d1", number: 1, text: "Push composite index migration on orders table", speaker: "Priya Patel", timestamp: "+03:25" },
  { id: "d2", number: 2, text: "Kill recommendation cron job immediately", speaker: "Marcus Johnson", timestamp: "+03:25" },
  { id: "d3", number: 3, text: "Bump connection pool limit from 500 to 750 as stopgap", speaker: "Marcus Johnson", timestamp: "+03:25" },
];

export const TIMELINE_EVENTS: TimelineEvent[] = [
  { id: "e1", type: "transcript", description: "Incident declared — SEV-1", timestamp: "+00:00" },
  { id: "e2", type: "transcript", description: "Connection pool exhaustion identified", timestamp: "+00:15" },
  { id: "e3", type: "finding", description: "3 related GitHub issues found", timestamp: "+01:30" },
  { id: "e4", type: "contradiction", description: "Deploy timing contradiction detected", timestamp: "+02:30" },
  { id: "e5", type: "tool_call", description: "Cron job identified as trigger", timestamp: "+02:52" },
  { id: "e6", type: "decision", description: "Action plan: index + kill cron + bump pool", timestamp: "+03:25" },
  { id: "e7", type: "transcript", description: "Index migration started", timestamp: "+04:00" },
  { id: "e8", type: "transcript", description: "Connections normalizing", timestamp: "+05:00" },
];

export const GRAPH_NODES: GraphNode[] = [
  { id: "user_query", name: "User Query", group: "input", color: "#3b82f6", status: "idle", activationCount: 2 },
  { id: "skill_router", name: "Skill Router", group: "router", color: "#f59e0b", status: "idle", activationCount: 3 },
  { id: "investigate", name: "Investigate", group: "skill", color: "#a855f7", status: "completed", activationCount: 2 },
  { id: "summarize", name: "Summarize", group: "skill", color: "#a855f7", status: "completed", activationCount: 1 },
  { id: "recall", name: "Recall", group: "skill", color: "#a855f7", status: "idle", activationCount: 0 },
  { id: "respond", name: "Respond", group: "skill", color: "#a855f7", status: "idle", activationCount: 0 },
  { id: "contradict", name: "Contradict", group: "skill", color: "#a855f7", status: "completed", activationCount: 1 },
  { id: "postmortem", name: "Post-mortem", group: "skill", color: "#a855f7", status: "idle", activationCount: 0 },
  { id: "github", name: "GitHub", group: "tool", color: "#06b6d4", status: "completed", activationCount: 2 },
  { id: "sentry", name: "Sentry", group: "tool", color: "#06b6d4", status: "idle", activationCount: 0 },
  { id: "pagerduty", name: "PagerDuty", group: "tool", color: "#06b6d4", status: "idle", activationCount: 0 },
];

export const GRAPH_LINKS: GraphLink[] = [
  { source: "user_query", target: "skill_router", active: false },
  { source: "skill_router", target: "investigate", active: true },
  { source: "skill_router", target: "summarize", active: true },
  { source: "skill_router", target: "recall", active: false },
  { source: "skill_router", target: "respond", active: false },
  { source: "skill_router", target: "contradict", active: true },
  { source: "skill_router", target: "postmortem", active: false },
  { source: "investigate", target: "github", active: true },
  { source: "investigate", target: "sentry", active: false },
  { source: "investigate", target: "pagerduty", active: false },
];

export const GIT_COMMITS: GitCommit[] = [
  { hash: "a3f8c2d", message: "Add recommendation query", time: "2 days ago", suspect: true },
  { hash: "b7e1f9a", message: "Fix logging format", time: "3 days ago", suspect: false },
  { hash: "c4d2e8b", message: "Update deps", time: "4 days ago", suspect: false },
  { hash: "d9a3f1c", message: "Add health check", time: "5 days ago", suspect: false },
  { hash: "e2b7c4d", message: "Refactor auth", time: "6 days ago", suspect: false },
];

export const GIT_PRS: GitPR[] = [
  { number: 892, title: "Product recommendations v2", status: "merged" },
  { number: 901, title: "Fix pool logging", status: "in_review" },
];

export const GIT_ISSUES: GitIssue[] = [
  { number: 1247, title: "Connection pool exhaustion", label: "bug", status: "closed" },
  { number: 1250, title: "Slow checkout queries", label: "bug", status: "open" },
  { number: 1253, title: "Cron optimization", label: "enhancement", status: "open" },
];

export const SPARKLINE_DATA = {
  messages: [2, 4, 3, 5, 8, 6, 10, 12, 15, 18],
  findings: [0, 0, 1, 1, 2, 2, 3, 3, 4, 4],
  decisions: [0, 0, 0, 0, 0, 0, 1, 2, 3, 3],
};
