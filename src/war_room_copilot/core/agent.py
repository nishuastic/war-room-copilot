"""Stage 0: Bare minimum LiveKit agent — joins a room, echoes back what you say."""

from __future__ import annotations

import logging

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.plugins import openai, silero

load_dotenv()

logger = logging.getLogger("war-room-copilot")


class WarRoomAgent(Agent):
    """Simple echo agent for Stage 0. Will evolve into full copilot."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are War Room Copilot, an AI assistant in a production incident war room. "
                "For now, you are in echo/test mode. Repeat back what the user says, prefixed with "
                "'I heard you say: '. Keep responses short. "
                "Do not use markdown or special characters."
            ),
        )

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Greet the user briefly. Say you are War Room Copilot and ready to listen."
        )


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    logger.info("Room: %s", ctx.room.name)

    session = AgentSession(
        stt=openai.STT(model="whisper-1"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(model="tts-1", voice="alloy"),
        vad=ctx.proc.userdata["vad"],
    )

    # Log metrics
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage() -> None:
        summary = usage_collector.get_summary()
        logger.info("Usage: %s", summary)

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=WarRoomAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
