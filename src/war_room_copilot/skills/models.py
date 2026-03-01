"""Skill classification models."""

from enum import Enum

from pydantic import BaseModel


class Skill(str, Enum):
    DEBUG = "debug"
    IDEATE = "ideate"
    INVESTIGATE = "investigate"
    RECALL = "recall"
    GENERAL = "general"


class SkillResult(BaseModel):
    skill: Skill
    confidence: float
    reasoning: str
