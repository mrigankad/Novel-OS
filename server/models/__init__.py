"""All tables. Importing this module registers them with SQLModel.metadata."""

from .agents import Agent, Memory, Message, Run, Thread
from .book import (
    Chapter,
    ChapterVersion,
    CodexEntry,
    CodexLink,
    ContinuityExemption,
    Media,
    PlotThread,
    Project,
)
from .studio import (
    BookMetadata,
    Connection,
    CoverDesign,
    Release,
    ResearchSource,
    ResearchTask,
    VoiceProfile,
    VoiceSample,
)

__all__ = [
    "Agent", "Memory", "Message", "Run", "Thread",
    "Chapter", "ChapterVersion", "CodexEntry", "CodexLink", "ContinuityExemption",
    "Media", "PlotThread", "Project",
    "BookMetadata", "Connection", "CoverDesign", "Release", "ResearchSource",
    "ResearchTask", "VoiceProfile", "VoiceSample",
]
from .settings_extra import RoleDefault  # noqa: E402,F401
from .publish_extra import MarketingAsset  # noqa: E402,F401
from .suggest_extra import Suggestion  # noqa: E402,F401
