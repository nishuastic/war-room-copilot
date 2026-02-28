"""Skill-specific prompt suffixes appended to the base agent.md prompt."""

from .models import Skill

SKILL_PROMPTS: dict[Skill, str] = {
    Skill.DEBUG: (
        "\n\n## Active Skill: Debug\n"
        "Focus on root cause analysis. Use GitHub tools (blame, recent commits, "
        "commit diffs) to trace the issue. Be precise and technical — cite specific "
        "files, lines, and commits. Narrow from symptoms to cause systematically. "
        "Do not speculate without evidence."
    ),
    Skill.IDEATE: (
        "\n\n## Active Skill: Ideate\n"
        "Brainstorm potential solutions and mitigations. Present 2-3 options with "
        "trade-offs (speed vs safety, quick fix vs proper fix). Don't commit to one "
        "answer — help the team evaluate choices. Ask what constraints matter most."
    ),
    Skill.INVESTIGATE: (
        "\n\n## Active Skill: Investigate\n"
        "Proactively use tools to gather evidence. Chain multiple tool calls: search "
        "code, then read files, then check blame. Cross-reference findings. Present "
        "what you found with supporting evidence. Don't wait to be asked — dig in."
    ),
    Skill.RECALL: (
        "\n\n## Active Skill: Recall\n"
        "Use the recall_decision tool to search past decisions, action items, and "
        "agreements. Reference specific past context — who said what, when it was "
        "decided, what the outcome was. Be specific about dates and participants."
    ),
    Skill.SUMMARIZE: (
        "\n\n## Active Skill: Summarize\n"
        "Provide a structured status recap:\n"
        "1. Known facts — what we know for sure\n"
        "2. What's been tried — actions taken so far\n"
        "3. Open unknowns — what we still don't know\n"
        "4. Suggested next actions — what to do next\n"
        "Keep it concise but complete."
    ),
    Skill.GENERAL: "",
}
