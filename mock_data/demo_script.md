# War Room Copilot — Demo Script
**Speak these lines out loud to test each tool through the voice agent.**
Say lines marked `YOU:` naturally in the room. Lines marked `→ Sam should:` show expected behaviour.

---

## Scene 1 — Datadog Monitoring (tests `query_datadog_apm`, `query_datadog_metrics`, `get_datadog_monitors`)

**Setup**: Start the agent, join a LiveKit room. Speak normally about an incident.

---

**Colleague A**: Something's wrong — the agent has been really slow to respond.

**Colleague B**: Yeah, responses are taking like 10–15 seconds. Definitely not normal.

**YOU**: **"Hey Sam, check Datadog APM for backboard-gateway — what's the latency looking like?"**

→ Sam should: Call `query_datadog_apm("backboard-gateway")` and report p99 latency ~12,100ms, error rate ~34%, mention Postgres pool exhaustion.

---

**Colleague A**: That's insane. What about TTS — the agent went silent a while ago.

**YOU**: **"Hey Sam, what's the error rate on elevenlabs-tts in Datadog?"**

→ Sam should: Call `query_datadog_apm("elevenlabs-tts")` and report 41% error rate, 429 rate limit, daily quota at 100%.

---

**Colleague B**: Are there any active monitors firing right now?

**YOU**: **"Hey Sam, check Datadog for any triggered monitors."**

→ Sam should: Call `get_datadog_monitors()` and list 2–4 alerting monitors (backboard latency, TTS errors, Postgres connections).

---

**Colleague A**: What about the Postgres connection count — is that what's causing the backboard issue?

**YOU**: **"Hey Sam, query the Datadog metric for Postgres active connections over the last two hours."**

→ Sam should: Call `query_datadog_metrics("war_room.postgres.active_connections")` and show the ramp from ~14 healthy connections up to 100 maxed out.

---

## Scene 2 — Cloud Logs (tests `query_cloudwatch_logs`, `query_gke_pod_logs`, `query_aks_logs`)

---

**Colleague A**: Let's look at the actual RDS logs — are there slow queries?

**YOU**: **"Hey Sam, check CloudWatch logs for the RDS database — any slow queries or connection errors?"**

→ Sam should: Call `query_cloudwatch_logs("/aws/rds/war-room-db/postgresql")` and return the FATAL connection slot errors and slow query entries (4.5s SELECT, 8.9s INSERT).

---

**Colleague B**: And the speechmatics pod — I heard it's been restarting.

**YOU**: **"Hey Sam, check GKE pod logs for the speechmatics-proxy in the stt namespace."**

→ Sam should: Call `query_gke_pod_logs("war-room-gke-prod", "stt", "speechmatics-proxy")` and report 4x OOMKilled restarts, running on 1/2 replicas, latency 2800ms.

---

**Colleague A**: What about the backup agent on Azure — that was also crashing earlier.

**YOU**: **"Hey Sam, check AKS logs for the agent-backup namespace."**

→ Sam should: Call `query_aks_logs("war-room-aks-prod", "agent-backup")` and report 2 OOMKilled events (07:50, 07:55), memory exceeded 2Gi, currently stable at 1.2Gi.

---

## Scene 3 — Service Graph (tests `get_service_health`, `get_service_dependencies`)

---

**Colleague B**: What's the overall system health right now?

**YOU**: **"Hey Sam, give me a health summary of all services."**

→ Sam should: Call `get_service_health()` and list: postgres-rds UNHEALTHY, redis-cache UNHEALTHY, backboard-gateway UNHEALTHY, elevenlabs-tts UNHEALTHY, speechmatics-proxy DEGRADED.

---

**Colleague A**: So backboard is the main bottleneck — what does it depend on?

**YOU**: **"Hey Sam, what are the dependencies for backboard-gateway?"**

→ Sam should: Call `get_service_dependencies("backboard-gateway")` and list postgres-rds (UNHEALTHY) and redis-cache (UNHEALTHY) as the root causes.

---

## Scene 4 — Runbook (tests `search_runbook`)

---

**Colleague B**: We need the steps to fix the Postgres connection pool issue.

**YOU**: **"Hey Sam, what's the runbook for database connection pool exhaustion?"**

→ Sam should: Call `search_runbook("connection pool postgres")` and return the `db-connection-pool-exhaustion` runbook with steps: check pg_stat_activity, kill idle connections, scale PgBouncer, tune pool_size.

---

**Colleague A**: And what do we do about the OOMKilled pod?

**YOU**: **"Hey Sam, what's the runbook for a Kubernetes pod in crashloop?"**

→ Sam should: Call `search_runbook("OOM crashloop pod")` and return the `k8s-pod-crashloop` runbook with steps: kubectl describe, check resource limits, consider VPA.

---

## Scene 5 — GitHub Read (tests `get_recent_commits`, `get_commit_diff`, `search_issues`)

---

**Colleague B**: Could this be related to a recent deploy? Something changed this morning.

**YOU**: **"Hey Sam, what are the last five commits to main?"**

→ Sam should: Call `get_recent_commits(count=5)` and list the 5 most recent commits with SHA, author, message.

---

**Colleague A**: That transcript buffer commit looks suspicious.

**YOU**: **"Hey Sam, show me the diff for commit 14b6316."**

→ Sam should: Call `get_commit_diff("14b6316")` and display the files changed, additions/deletions, and patch content.

---

**Colleague B**: Has anyone opened an issue about memory leaks before?

**YOU**: **"Hey Sam, search GitHub issues for memory leak."**

→ Sam should: Call `search_issues("memory leak")` and return any matching issues (or "no issues found" which is also fine).

---

## Scene 6 — GitHub Write (tests `create_github_issue`, `revert_commit`)

---

**Colleague A**: We should open an incident issue to track this.

**YOU**: **"Hey Sam, create a GitHub issue titled 'Incident: Postgres connection pool exhaustion 2026-03-01' with a description of the root cause — Postgres max connections reached, backboard gateway timing out, TTS rate limited."**

→ Sam should: Call `create_github_issue(title="...", body="...")` and return "Issue #XX created: github.com/..."

---

**Colleague B**: I think we need to revert that transcript buffer commit before we scale.

**YOU**: **"Hey Sam, create a revert PR for commit 14b6316."**

→ Sam should: Call `revert_commit("14b6316")` and return "Revert PR #XX created" with a link and instructions to push the revert commit.

---

## Scene 7 — Contradiction Detection (no wake word needed — Sam interjects automatically)

**These lines are designed to trigger Sam's proactive contradiction detection:**

---

**Colleague A**: "The database was totally fine this morning — I checked it myself at 7am."

→ Sam should interject: The RDS logs show FATAL connection errors starting at 08:02 UTC. The pool was exhausted within minutes of 8am.

---

**Colleague B**: "TTS was working fine just a moment ago."

→ Sam should interject: ElevenLabs logs show the first 429 error at 08:03 UTC — that's over 25 minutes ago, not "a moment ago".

---

**Colleague A**: "That commit was just a minor timing tweak, shouldn't affect memory."

→ Sam should interject: The diff for 14b6316 shows changes to the transcript buffer accumulation logic — that directly affects per-session memory usage.

---

## Recall Test (tests `recall_decision`)

---

**After Sam has captured some decisions during the session:**

**YOU**: **"Hey Sam, what decisions have we made so far in this incident?"**

→ Sam should: Call `recall_decision("incident decisions")` and list any decisions captured with confidence scores and timestamps.

---

## Quick Reference — Wake Word Lines

Copy-paste these to speak quickly during a demo:

| Tool | Line to speak |
|------|--------------|
| Datadog APM | "Hey Sam, check Datadog APM for backboard-gateway" |
| Datadog logs | "Hey Sam, check Datadog logs for elevenlabs-tts errors" |
| Datadog monitors | "Hey Sam, are any Datadog monitors triggered?" |
| CloudWatch | "Hey Sam, check CloudWatch RDS logs for connection errors" |
| GKE pods | "Hey Sam, check GKE logs for speechmatics-proxy" |
| AKS logs | "Hey Sam, check AKS logs for agent-backup" |
| Service health | "Hey Sam, what's the health of all services?" |
| Dependencies | "Hey Sam, what does backboard-gateway depend on?" |
| Runbook | "Hey Sam, what's the runbook for connection pool exhaustion?" |
| Recent commits | "Hey Sam, what are the last five commits to main?" |
| Commit diff | "Hey Sam, show me the diff for commit 14b6316" |
| Create issue | "Hey Sam, create a GitHub issue for this incident" |
| Revert PR | "Hey Sam, create a revert PR for commit 14b6316" |
| Recall | "Hey Sam, what decisions have we made?" |
