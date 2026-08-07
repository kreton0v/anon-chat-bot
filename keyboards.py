import json
from typing import Dict, Any, List


def _inline(buttons: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
    return {"inline_keyboard": buttons}


def _reply(buttons: List[List[str]]) -> Dict[str, Any]:
    return {
        "keyboard": [[{"text": t} for t in row] for row in buttons],
        "resize_keyboard": True
    }


def remove_keyboard() -> Dict[str, Any]:
    return {"remove_keyboard": True}


def menu_register_gender() -> Dict[str, Any]:
    return _inline([
        [{"text": "👨 Мужской", "callback_data": "reg_M"},
         {"text": "👩 Женский", "callback_data": "reg_F"}]
    ])


def menu_register_age() -> Dict[str, Any]:
    return _inline([
        [{"text": "13-16", "callback_data": "reg_age_13-16"},
         {"text": "16-18", "callback_data": "reg_age_16-18"}],
        [{"text": "18+", "callback_data": "reg_age_18+"}]
    ])


def menu_main(reveal_price: int) -> Dict[str, Any]:
    return _inline([
        [{"text": "🔍 Найти собеседника", "callback_data": "find"}],
        [{"text": "👤 Мой профиль", "callback_data": "profile"}],
        [{"text": f"🔓 Раскрыть личность ({reveal_price} 💰)", "callback_data": "reveal"}],
        [{"text": "📊 Статистика", "callback_data": "stats"}],
        [{"text": "👥 Пригласить друзей", "callback_data": "referral"}],
        [{"text": "💡 Предложить идею", "callback_data": "suggest"}],
        [{"text": "💬 Поддержка", "callback_data": "support"}]
    ])


def menu_admin(reveal_price: int, is_owner: bool) -> Dict[str, Any]:
    kb = [
        [{"text": "👥 Активные пары", "callback_data": "users"}],
        [{"text": "📊 Статистика", "callback_data": "stats"}],
        [{"text": "🚫 Бан", "callback_data": "ban"},
         {"text": "✅ Разбан", "callback_data": "unban"}],
        [{"text": "📝 Жалобы", "callback_data": "reports"}],
        [{"text": "💰 Цена раскрытия", "callback_data": "setprice"}],
        [{"text": "🎁 Выдать монеты", "callback_data": "addcoins"}]
    ]
    if is_owner:
        kb.append([{"text": "👑 Управление админами", "callback_data": "manage_admins"}])
    return _inline(kb)


def menu_find_prefs() -> Dict[str, Any]:
    return _inline([
        [{"text": "👨 Мужской", "callback_data": "find_M"},
         {"text": "👩 Женский", "callback_data": "find_F"}],
        [{"text": "🌐 Любой", "callback_data": "find_A"}]
    ])


def menu_find_age() -> Dict[str, Any]:
    return _inline([
        [{"text": "13-16", "callback_data": "find_age_13-16"},
         {"text": "16-18", "callback_data": "find_age_16-18"}],
        [{"text": "18+", "callback_data": "find_age_18+"},
         {"text": "🌐 Любой", "callback_data": "find_age_A"}]
    ])


def chat_keyboard() -> Dict[str, Any]:
    return _reply([
        ["⛔ Завершить чат"],
        ["🚨 Пожаловаться"],
        ["📋 Меню"]
    ])


def support_keyboard() -> Dict[str, Any]:
    return _reply([["🔙 Выйти из поддержки"]])


def suggestion_keyboard() -> Dict[str, Any]:
    return _reply([["🔙 Отменить"]])


def report_inline_kb() -> Dict[str, Any]:
    return _inline([[{"text": "🚨 Пожаловаться", "callback_data": "report_msg"}]])


def cancel_search_kb() -> Dict[str, Any]:
    return _inline([[{"text": "❌ Отменить поиск", "callback_data": "stop"}]])


def media_consent_kb(media_type: str) -> Dict[str, Any]:
    return _inline([
        [{"text": "✅ Я согласен", "callback_data": f"consent_{media_type}"}],
        [{"text": "❌ Отменить", "callback_data": "consent_cancel"}]
    ])


def admin_manage_kb() -> Dict[str, Any]:
    return _inline([
        [{"text": "➕ Добавить админа", "callback_data": "addadmin_inline"}],
        [{"text": "➖ Удалить админа", "callback_data": "removeadmin_inline"}],
        [{"text": "📋 Список админов", "callback_data": "listadmins"}],
        [{"text": "🔙 Назад", "callback_data": "admin_back"}]
    ])


def report_verdict_kb(offender_id: int) -> Dict[str, Any]:
    return _inline([
        [{"text": "🚫 Забанить", "callback_data": f"ban_{offender_id}"}],
        [{"text": "✅ Не банить", "callback_data": f"noban_{offender_id}"}],
        [{"text": "❌ Отмена", "callback_data": f"cancel_report_{offender_id}"}]
    ])
