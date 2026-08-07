from repository import repo
from services.coins import coins
from utils import get_display_name, escape_html


class RevealService:
    def reveal(self, user_id: int, partner_id: int, price: int) -> tuple:
        if repo.is_admin(partner_id) or repo.is_owner(partner_id):
            return False, "🛡️ Невозможно раскрыть личность администратора или владельца."
        if not coins.spend_coins(user_id, price):
            p = repo.get_profile(user_id)
            return False, f"❌ Недостаточно монет!
🔓 Раскрытие стоит <b>{price}</b> 💰
💰 У вас: <b>{p.coins}</b>"
        partner = repo.get_profile(partner_id)
        if partner.username:
            info = f"👤 Имя: {escape_html(partner.name)}
🔗 Юзернейм: @{escape_html(partner.username)}"
        else:
            info = f"👤 Имя: {escape_html(partner.name)}
🆔 ID: {partner_id}
<i>(Юзернейм не установлен)</i>"
        return True, f"<b>🔓 Личность раскрыта!</b>

{info}"


reveal = RevealService()
