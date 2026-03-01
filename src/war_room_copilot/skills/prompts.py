"""Skill-specific prompt suffixes appended to the base agent.md prompt."""

from .models import Skill

SKILL_PROMPTS: dict[Skill, str] = {
    Skill.DEBUG: (
        "\n\n## Active Skill: Debug\n"
        "Find the root cause. Use tools — don't guess.\n"
        "Chain: recent commits → diff → read file → blame. "
        "Also check logs and monitoring for correlated errors.\n"
        "Report what you found in 1-2 sentences with specifics: file, commit, error message."
    ),
    Skill.IDEATE: (
        "\n\n## Active Skill: Ideate\n"
        "Check service health and runbooks first, then suggest 2-3 options with trade-offs. "
        "Keep it short — one sentence per option. Ask what matters more: speed or safety."
    ),
    Skill.INVESTIGATE: (
        "\n\n## Active Skill: Investigate\n"
        "Use tools. Don't answer from memory.\n"
        "Hit the most relevant tool first, chain further if needed. "
        "Report findings in 1-2 sentences — lead with the critical number or error."
    ),
    Skill.RECALL: (
        "\n\n## Active Skill: Recall\n"
        "Use recall_decision to look up past decisions. "
        "Be specific: who decided what, when. If nothing found, say so."
    ),
    Skill.GENERAL: "",
}
