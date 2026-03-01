# War Room Copilot — Test Dialogues

Three realistic incident dialogues for demo and testing.
Each includes speaker labels, wake-word trigger lines, contradiction-bait lines, and expected agent responses.

---

## Dialogue 1: Backboard Gateway Latency Spike (~15 turns)

**Incident**: War room agent responses are slow. Engineers suspect the Backboard memory layer.

---

**Engineer1**: The agent felt sluggish this morning — took like 15 seconds to respond.

**Engineer2**: Yeah, I noticed too. Something's off with response times.

**SRE**: Could be the Backboard layer. It's been flaky before.

**Engineer1**: *[triggers wake word]* Hey Sam, what's the current latency for backboard-gateway in Datadog?

> **[Agent expected]**: Queries `query_datadog_apm(service="backboard-gateway")`. Returns: "Backboard-gateway p99 latency is 12,100ms — that's over 12 seconds. Error rate is 34%. Normal baseline is under 500ms."

**Engineer2**: 12 seconds?! That explains everything.

**SRE**: What's causing it? Could be the database.

**Engineer1**: *[triggers wake word]* Hey Sam, check CloudWatch RDS logs for war-room-db — any slow queries?

> **[Agent expected]**: Queries `query_cloudwatch_logs(log_group="/aws/rds/war-room-db/postgresql")`. Returns: "Found slow query logs: INSERT taking 8.9s, SELECT taking 4.5s. Max connections reached — 100/100 active connections, 0 idle. New connections are being refused."

**SRE**: Postgres connection pool is maxed out. That's the root cause.

**Engineer2**: How many are waiting in queue?

**Engineer1**: *[triggers wake word]* Hey Sam, check application logs for backboard-gateway — how many connections are waiting?

> **[Agent expected]**: Queries `query_datadog_logs(query="connection pool", service="backboard-gateway")`. Returns: "Log at 08:08: CRITICAL — All 20 Postgres connections in use for >30s. Wait queue depth: 63 queries."

**Engineer2**: 63 queries waiting. We're completely backed up.

**SRE**: We need PgBouncer or to increase max_connections.

**Engineer1**: *[contradiction bait]* The database was fine this morning, right? I thought we checked it at 7am.

> **[Agent expected — contradiction]**: "Actually, the RDS logs show the connection pool maxed out at 08:02 this morning. The fatal errors started at 08:02:00Z — that's about an hour ago now, not this morning after your 7am check. It may have degraded quickly after that."

**SRE**: Good catch. We need the runbook for this.

**Engineer2**: *[triggers wake word]* Hey Sam, what's the runbook for database connection pool exhaustion?

> **[Agent expected]**: Queries `search_runbook(keywords=["connection pool", "postgres"])`. Returns step-by-step: check pg_stat_activity, kill idle connections, scale PgBouncer, tune pool_size.

**Engineer1**: Let's follow those steps. Can you open an incident issue on GitHub?

**SRE**: *[triggers wake word]* Hey Sam, create a GitHub issue: title "Incident: Backboard Postgres connection pool exhausted 2026-03-01", body should include the root cause and impact.

> **[Agent expected]**: Calls `create_github_issue(title="Incident: Backboard Postgres connection pool exhausted 2026-03-01", body="Root cause: Postgres max_connections=100 reached at 08:02 UTC. Impact: Backboard gateway p99 latency 12.1s, error rate 34%. Resolution: Apply PgBouncer connection pooling or increase max_connections.")`. Returns: "Issue #47 created."

**Engineer2**: Good. Who's taking the PgBouncer config change?

**SRE**: I'll do it. Let's track that as a decision.

> **[Agent note]**: Decision tracker should extract: "SRE will deploy PgBouncer config change to resolve Postgres connection pool exhaustion." (confidence ~0.9)

---

## Dialogue 2: ElevenLabs TTS Failures — Agent Going Silent (~12 turns)

**Incident**: The war room agent has stopped speaking. Engineers can see it's active (dashboard shows wake-word hits) but no audio output.

---

**Engineer1**: Sam went completely silent like 20 minutes ago. Waved word is triggering — I can see it on the dashboard — but no audio.

**Engineer2**: TTS is probably down. ElevenLabs maybe?

**SRE**: Could also be a LiveKit issue. Let's check the logs.

**Engineer1**: *[triggers wake word]* Hey Sam, check application logs for elevenlabs-tts — what errors do you see?

> **[Agent expected]**: Queries `query_datadog_logs(query="error", service="elevenlabs-tts")`. Returns: "Found 3 ERROR logs from elevenlabs-tts since 08:03 UTC: '429 Too Many Requests. Retry-After: 60s.' Daily quota at 98.4%. All TTS synthesis requests are failing."

**Engineer2**: Rate limit. We burned through the daily quota.

**SRE**: That's... 98.4%? We've never hit that before. What's driving the extra usage?

**Engineer1**: *[contradiction bait]* TTS was totally fine at 8am, I was testing it myself.

> **[Agent expected — contradiction]**: "The logs show TTS started failing at 08:03 UTC, and the quota hit 95% warning at 08:02:30 UTC. The timeline suggests quota was nearly exhausted shortly after 8am. You may have been testing right at the threshold."

**SRE**: What's the speechmatics side look like? If STT is also degraded, that would explain the extra audio processing load.

**Engineer2**: *[triggers wake word]* Hey Sam, check GKE for the speechmatics-proxy pod status.

> **[Agent expected]**: Queries `query_gke_pod_logs(cluster="war-room-gke-prod", namespace="stt", pod_prefix="speechmatics-proxy")`. Returns: "speechmatics-proxy pod 'speechmatics-proxy-7d8f9c-xk2lp' is OOMKilled — 4 restarts in the last hour. Running on 1/2 replicas. The surviving replica is handling double load, latency 2800ms (baseline: 400ms)."

**Engineer1**: OOMKilled! So we lost half our STT capacity. That forced the surviving pod to buffer more audio in memory.

**Engineer2**: Which means longer sessions, more audio, more TTS calls — quota spike makes sense now.

**SRE**: Two issues: fix the speechmatics pod memory limit and reset/upgrade the ElevenLabs quota.

**Engineer1**: *[triggers wake word]* Hey Sam, what's the runbook for pod crashloop from OOM?

> **[Agent expected]**: Queries `search_runbook(keywords=["OOM", "crashloop", "pod", "memory"])`. Returns k8s-pod-crashloop runbook: check kubectl describe pod, examine resource limits, consider increasing memory limit or adding VPA.

**Engineer2**: Let's bump the speechmatics memory limit from 512Mi to 1Gi.

**SRE**: And for TTS — do we need to upgrade the ElevenLabs plan or can we wait until quota resets?

**Engineer1**: *[triggers wake word]* Hey Sam, when does the ElevenLabs quota reset? Is there a way to check?

> **[Agent expected]**: "The ElevenLabs quota typically resets at midnight UTC. Based on the 98.4% usage at 08:03 today (March 1), you're likely exhausted until March 2 at 00:00 UTC — about 16 hours from now. Short-term fix: either upgrade the plan or switch to a fallback TTS provider."

> **[Agent proactive interject]**: "By the way — the ElevenLabs logs show TTS has been failing since 08:03, which was 25 minutes before this conversation started. If anyone said 'TTS was working fine a moment ago', that's not consistent with what I'm seeing in the logs."

**SRE**: Okay. I'll open a PR to bump the speechmatics memory limit.

---

## Dialogue 3: LiveKit Agent CrashLoop After Deploy (~10 turns)

**Incident**: The backup LiveKit agent replica on AKS keeps crashlooping. Engineers need to identify whether it's a code regression from the latest deploy.

---

**SRE**: The AKS backup agent is in a CrashLoopBackOff. Second time this morning.

**Engineer1**: Same pod as before? Or a new one?

**SRE**: Same pod — livekit-agent-backup. It's restarted twice.

**Engineer2**: *[triggers wake word]* Hey Sam, check Azure AKS logs for the livekit-agent-backup namespace — what's causing the crashes?

> **[Agent expected]**: Queries `query_aks_logs(cluster="war-room-aks-prod", namespace="agent-backup")`. Returns: "Pod 'livekit-agent-backup-5c8a2b-r9klm' OOMKilled twice — restart #1 at 07:50 UTC, restart #2 at 07:55 UTC. Memory exceeded 2Gi limit during 'large transcript processing'. Currently stable at 1.2Gi/2Gi (60%)."

**SRE**: OOMKilled during transcript processing. Same pattern as speechmatics.

**Engineer1**: Was there a recent code change that could've increased memory usage?

**Engineer2**: *[triggers wake word]* Hey Sam, check recent commits to war-room-copilot for anything touching transcript processing or memory.

> **[Agent expected]**: Queries `get_recent_commits(repo="nishuastic/war-room-copilot", branch="main", count=10)`. Returns: "Most recent commit: '14b6316 — fix: natural interruptions, reliable transcript capture, and intent-aware routing' by nishuastic, March 1 2026. Previous: '0ba1422 — feat: maximize Backboard memory integration for judging score'."

**SRE**: "Reliable transcript capture" — that commit could've changed how we buffer transcripts in memory.

**Engineer1**: *[triggers wake word]* Hey Sam, show me the diff for commit 14b6316.

> **[Agent expected]**: Queries `get_commit_diff(commit_sha="14b6316", repo="nishuastic/war-room-copilot")`. Returns the diff with changes to transcript capture logic — highlight any changes to buffer sizes or accumulation patterns.

**Engineer2**: I see it — the wake word buffer now accumulates more segments before processing. That's holding more in memory per session.

**SRE**: If we have 3 concurrent sessions, that triples the memory footprint.

**Engineer1**: *[contradiction bait]* I thought that commit was only changing wake word detection timing, nothing major.

> **[Agent expected — contradiction]**: "The commit message says 'natural interruptions, reliable transcript capture' — but the diff shows changes to how transcript segments are buffered before sending to the skill router. If the buffer now accumulates more segments before flushing, that directly increases per-session memory usage."

**SRE**: We need to either revert that commit or increase the memory limit to 3Gi.

**Engineer2**: *[triggers wake word]* Hey Sam, should we revert commit 14b6316 or just bump the memory limit?

> **[Agent expected]**: "Based on what I'm seeing: if the transcript buffer change is the root cause, reverting 14b6316 risks losing the improvements to interruption detection. I'd recommend first testing with a 3Gi memory limit on the AKS pod spec — that's a safer change. If memory is still exhausted at 3Gi with 3 concurrent sessions, then the buffer logic needs a fix. I can create a GitHub issue to track the memory investigation."

**Engineer2**: Good call. Let's bump to 3Gi first.

**SRE**: Agreed. And let's open that issue.

**Engineer1**: *[triggers wake word]* Hey Sam, create a GitHub issue: "Investigate memory usage spike in transcript buffer after commit 14b6316" — label it `bug` and `memory`.

> **[Agent expected]**: Calls `create_github_issue(title="Investigate memory usage spike in transcript buffer after commit 14b6316", body="AKS backup pod OOMKilled twice at 07:50 and 07:55 UTC on 2026-03-01. Root suspect: commit 14b6316 changed transcript buffer accumulation. Short-term fix: increase memory limit to 3Gi. Investigation needed: profile memory per session with new buffer logic.", labels=["bug", "memory"])`. Returns: "Issue #48 created."

> **[Agent note]**: Decision tracker should extract: "Engineer2/SRE agreed to bump AKS livekit-agent memory limit to 3Gi as short-term fix before investigating commit 14b6316 buffer changes." (confidence ~0.85)

---

## Wake Word Trigger Summary

Lines designed to trigger the `sam` wake word (for testing routing):
- "Hey Sam, what's the current latency for backboard-gateway in Datadog?"
- "Hey Sam, check CloudWatch RDS logs for war-room-db"
- "Hey Sam, check application logs for backboard-gateway — how many connections are waiting?"
- "Hey Sam, what's the runbook for database connection pool exhaustion?"
- "Hey Sam, create a GitHub issue: title 'Incident: ...'"
- "Hey Sam, check application logs for elevenlabs-tts"
- "Hey Sam, check GKE for the speechmatics-proxy pod status"
- "Hey Sam, what's the runbook for pod crashloop from OOM?"
- "Hey Sam, when does the ElevenLabs quota reset?"
- "Hey Sam, check Azure AKS logs for the livekit-agent-backup namespace"
- "Hey Sam, check recent commits to war-room-copilot"
- "Hey Sam, show me the diff for commit 14b6316"
- "Hey Sam, should we revert commit 14b6316 or just bump the memory limit?"
- "Hey Sam, create a GitHub issue: 'Investigate memory usage spike...'"

## Contradiction Lines

Lines designed to trigger Sam's proactive contradiction detection:
- "The database was fine this morning, right? I thought we checked it at 7am." → Agent should cite 08:02 RDS fatal errors
- "TTS was totally fine at 8am, I was testing it myself." → Agent should cite 08:03 first failure timestamp
- "I thought that commit was only changing wake word detection timing, nothing major." → Agent should cite diff evidence of buffer changes
