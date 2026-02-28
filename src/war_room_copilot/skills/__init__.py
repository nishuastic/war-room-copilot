"""Skill routing — intent classification and per-skill prompt specialization."""

from .models import Skill, SkillResult
from .prompts import SKILL_PROMPTS
from .router import SkillRouter

__all__ = ["Skill", "SkillResult", "SkillRouter", "SKILL_PROMPTS"]
