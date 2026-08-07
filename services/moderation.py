import time
from typing import Optional, List

from models import BanRecord, Report
from repository import repo
from utils import get_display_name


class ModerationService:
    def ban(self, user_id: int, minutes: int, reason: str, banned_by: int) -> str:
        if repo.is_admin(user_id) or repo.is_owner(user_id):
            return "🛡️ Нельзя забанить администратора или владельца."
        permanent = minutes <= 0
        until = None if permanent else time.time() + minutes * 60
        record = BanRecord(
            user_id=user_id, permanent=permanent, until=until,
            reason=reason, banned_by=banned_by
        )
        repo.ban(record)
        if permanent:
            return f"🚫 {get_display_name(user_id)} забанен навсегда.
📌 Причина: {reason}"
        return f"🚫 {get_display_name(user_id)} забанен на {minutes} мин.
📌 Причина: {reason}"

    def unban(self, user_id: int) -> str:
        repo.unban(user_id)
        return f"✅ {get_display_name(user_id)} разбанен."

    def is_banned(self, user_id: int) -> tuple:
        return repo.is_banned(user_id)

    def report(self, reporter_id: int, offender_id: int) -> None:
        report = Report(reporter_id=reporter_id, offender_id=offender_id)
        repo.add_report(report)

    def get_reports(self, offender_id: int) -> List[Report]:
        return repo.get_reports_for(offender_id)

    def get_unresolved_reports(self):
        return repo.get_all_unresolved_reports()

    def resolve(self, offender_id: int, verdict: str):
        repo.resolve_reports(offender_id, verdict)


moderation = ModerationService()
