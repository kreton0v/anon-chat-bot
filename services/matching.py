import time
from typing import Optional, Tuple

from models import WaitingUser, ChatSession, Gender, AgeGroup
from repository import repo
from utils import get_display_name


class MatchingService:
    """Thread-safe matching via repository (SQLite handles concurrency)."""

    def find_pair(self, user_id: int, find_gender: Optional[str], find_age: Optional[str]) -> Optional[ChatSession]:
        profile = repo.get_profile(user_id)
        if not profile.is_registered:
            return None

        # Convert preferences
        fg = Gender(find_gender) if find_gender and find_gender != "A" else None
        fa = AgeGroup(find_age) if find_age and find_age != "A" else None

        # Check if already in chat
        existing = repo.get_active_chat(user_id)
        if existing:
            return existing

        # Check if already waiting
        waiting_self = repo.get_waiting(user_id)
        if waiting_self:
            return None  # Already in queue

        # Try to match
        candidates = repo.get_all_waiting()
        for w in candidates:
            if w.user_id == user_id:
                continue
            # My preferences match candidate
            ok_g = (fg is None or w.gender == fg)
            ok_a = (fa is None or w.age == fa)
            # Candidate's preferences match me
            ok_wg = (w.find_gender is None or w.find_gender == profile.gender)
            ok_wa = (w.find_age is None or w.find_age == profile.age)
            if ok_g and ok_a and ok_wg and ok_wa:
                # Match found!
                repo.remove_waiting(w.user_id)
                session = ChatSession(
                    user_a=user_id, user_b=w.user_id,
                    started_at=time.time(), history=[]
                )
                repo.create_chat(session)
                return session

        # No match — add to waiting
        w = WaitingUser(
            user_id=user_id, gender=profile.gender, age=profile.age,
            find_gender=fg, find_age=fa
        )
        repo.add_waiting(w)
        return None

    def stop_search(self, user_id: int) -> bool:
        w = repo.get_waiting(user_id)
        if w:
            repo.remove_waiting(user_id)
            return True
        return False

    def stop_chat(self, user_id: int) -> Optional[Tuple[int, int, list]]:
        """Returns (partner_id, duration_seconds, history) if chat existed."""
        session = repo.get_active_chat(user_id)
        if not session:
            return None
        partner = session.partner_of(user_id)
        duration = time.time() - session.started_at
        history = session.history
        repo.delete_chat(session.user_a, session.user_b)
        return partner, int(duration), history


matching = MatchingService()
