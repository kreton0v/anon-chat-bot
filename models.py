from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum


class Gender(str, Enum):
    MALE = "M"
    FEMALE = "F"


class AgeGroup(str, Enum):
    TEEN = "13-16"
    YOUNG = "16-18"
    ADULT = "18+"


class MediaType(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    VIDEO_NOTE = "video_note"
    VOICE = "voice"
    AUDIO = "audio"
    DOCUMENT = "document"
    STICKER = "sticker"


@dataclass
class UserProfile:
    user_id: int
    gender: Optional[Gender] = None
    age: Optional[AgeGroup] = None
    coins: int = 0
    username: str = ""
    name: str = ""
    referrals: List[int] = field(default_factory=list)
    referral_batches: int = 0  # сколько раз уже получил награду
    referred_by: Optional[int] = None

    @property
    def is_registered(self) -> bool:
        return self.gender is not None and self.age is not None

    @property
    def is_teen(self) -> bool:
        return self.age == AgeGroup.TEEN


@dataclass
class ChatSession:
    user_a: int
    user_b: int
    started_at: float
    history: List[Dict] = field(default_factory=list)

    def partner_of(self, user_id: int) -> int:
        return self.user_b if user_id == self.user_a else self.user_a


@dataclass
class WaitingUser:
    user_id: int
    gender: Gender
    age: AgeGroup
    find_gender: Optional[Gender] = None  # None = Any
    find_age: Optional[AgeGroup] = None   # None = Any
    joined_at: float = field(default_factory=lambda: __import__('time').time())


@dataclass
class BanRecord:
    user_id: int
    permanent: bool
    until: Optional[float] = None
    reason: str = ""
    banned_by: Optional[int] = None
    banned_at: float = field(default_factory=lambda: __import__('time').time())


@dataclass
class Report:
    reporter_id: int
    offender_id: int
    reported_at: float = field(default_factory=lambda: __import__('time').time())
    resolved: bool = False
    verdict: Optional[str] = None  # "banned", "ignored"
