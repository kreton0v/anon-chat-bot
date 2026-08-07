import html
from typing import Optional

from config import CONFIG
from repository import repo


def escape_html(text: Optional[str]) -> str:
    if not text:
        return ""
    return html.escape(str(text))


def get_display_name(user_id: int) -> str:
    p = repo.get_profile(user_id)
    if p.name or p.username:
        if p.username:
            return escape_html(f"{p.name} (@{p.username})")
        return escape_html(f"{p.name} (ID: {user_id})")
    return f"ID: {user_id}"


def get_role_tag(user_id: int) -> str:
    if user_id == CONFIG.OWNER_ID:
        return "[👑 owner] "
    if repo.is_admin(user_id):
        return "[🛡️ admin] "
    return ""


def get_ref_link(user_id: int) -> str:
    # BOT_TOKEN format: 123456789:ABC... -> bot username unknown
    # Use token prefix as placeholder, user should set actual username env
    return f"https://t.me/your_bot_username?start=ref_{user_id}"


def format_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m > 0:
        return f"{m} мин {s} сек"
    return f"{s} сек"
