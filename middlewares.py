import time
from typing import Callable, Any
from repository import repo
from utils import get_display_name


class MiddlewarePipeline:
    def __init__(self):
        self.middlewares: list = []

    def add(self, mw: Callable):
        self.middlewares.append(mw)

    def process(self, user_id: int, msg_obj: dict, context: dict) -> tuple:
        for mw in self.middlewares:
            result = mw(user_id, msg_obj, context)
            if result is not None:
                return result
        return None


def ban_check(user_id: int, msg_obj: dict, context: dict):
    banned, reason = repo.is_banned(user_id)
    if banned:
        return {"action": "banned", "reason": reason}
    return None


def profile_update(user_id: int, msg_obj: dict, context: dict):
    """Auto-update username/name on every message."""
    from_user = msg_obj.get("from", {})
    username = from_user.get("username", "") or ""
    name = from_user.get("first_name", "") or ""
    p = repo.get_profile(user_id)
    changed = False
    if p.username != username:
        p.username = username
        changed = True
    if p.name != name:
        p.name = name
        changed = True
    if changed:
        repo.save_profile(p)
    return None


middleware = MiddlewarePipeline()
middleware.add(ban_check)
middleware.add(profile_update)
