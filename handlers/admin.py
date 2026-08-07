from config import CONFIG
from repository import repo
from services import moderation, coins
from telegram_api import send_msg
from utils import get_display_name
import keyboards as kb
from handlers.common import user_state


def handle_admin_callback(user_id: int, data: str):
    if not repo.is_admin(user_id):
        return

    if data == "ban":
        user_state[user_id] = "await_ban_id"
        send_msg(user_id, "🚫 Введите ID пользователя для бана:")
        return
    if data == "unban":
        user_state[user_id] = "await_unban_id"
        send_msg(user_id, "✅ Введите ID пользователя для разбана:")
        return
    if data == "addcoins":
        user_state[user_id] = "await_addcoins"
        send_msg(user_id, "🎁 Введите ID и сумму через пробел:\n<i>Например: 123456789 100</i>")
        return
    if data == "setprice":
        user_state[user_id] = "await_setprice"
        send_msg(user_id, f"💰 Введите новую цену раскрытия:\n<i>Текущая: {repo.get_reveal_price()}</i>")
        return
    if data == "users":
        show_users(user_id)
        show_admin_menu(user_id)
        return
    if data == "reports":
        show_reports(user_id)
        return
    if data == "stats":
        show_admin_stats(user_id)
        return
    if data == "manage_admins":
        if not repo.is_owner(user_id):
            send_msg(user_id, "👑 Только владелец.")
            return
        send_msg(user_id, "<b>👑 Управление администраторами</b>", kb.admin_manage_kb())
        return
    if data == "addadmin_inline":
        user_state[user_id] = "await_addadmin"
        send_msg(user_id, "👑 Введите ID нового администратора:")
        return
    if data == "removeadmin_inline":
        user_state[user_id] = "await_removeadmin"
        send_msg(user_id, "👑 Введите ID администратора для удаления:")
        return
    if data == "listadmins":
        msg = "<b>🛡️ Администраторы:</b>\n\n"
        msg += f"👑 {get_display_name(CONFIG.OWNER_ID)} — <b>Владелец</b>\n"
        admins = repo.get_admins()
        for aid in admins:
            msg += f"🛡️ {get_display_name(aid)}\n"
        if not admins:
            msg += "<i>Администраторов нет</i>\n"
        send_msg(user_id, msg)
        return
    if data == "admin_back":
        show_admin_menu(user_id)
        return

    # Report verdicts
    if data.startswith("ban_"):
        uid = int(data.split("_")[1])
        if repo.is_admin(uid) or repo.is_owner(uid):
            send_msg(user_id, "🛡️ Нельзя забанить администратора или владельца.")
            return
        user_state[user_id] = f"ban_details_{uid}"
        send_msg(user_id, "🚫 Введите время бана (в минутах) и причину через |\n<i>Например: 60 | Спам</i>\n\nДля перманентного: 0 | Причина")
        return
    if data.startswith("noban_"):
        uid = int(data.split("_")[1])
        moderation.resolve(uid, "ignored")
        send_msg(user_id, f"✅ Пользователь {get_display_name(uid)} не забанен. Жалобы очищены.")
        return
    if data.startswith("cancel_report_"):
        send_msg(user_id, "❌ Жалоба отменена.")
        return


def show_admin_menu(user_id: int):
    if not repo.is_admin(user_id):
        return
    send_msg(user_id, f"<b>🛡️ Админ-панель</b>\nТекущая цена раскрытия: {repo.get_reveal_price()} 💰",
             kb.menu_admin(repo.get_reveal_price(), repo.is_owner(user_id)))


def show_users(user_id: int):
    chats = repo.get_all_active_chats()
    if not chats:
        send_msg(user_id, "👥 Нет активных пар.")
        return
    msg = "<b>👥 Активные пары:</b>\n\n"
    seen = set()
    for s in chats:
        if s.user_a in seen:
            continue
        na = get_display_name(s.user_a)
        nb = get_display_name(s.user_b)
        pa = repo.get_profile(s.user_a)
        pb = repo.get_profile(s.user_b)
        ga = {"M": "👨", "F": "👩"}.get(pa.gender, "❓")
        gb = {"M": "👨", "F": "👩"}.get(pb.gender, "❓")
        aa = pa.age or "?"
        ab = pb.age or "?"
        msg += f"{ga} {na} ({aa}) ↔️ {gb} {nb} ({ab})\n\n"
        seen.add(s.user_a)
        seen.add(s.user_b)
    send_msg(user_id, msg)


def show_reports(user_id: int):
    reports = repo.get_all_unresolved_reports()
    if not reports:
        send_msg(user_id, "📝 Жалоб нет.")
        return
    for offender_id, reps in reports:
        session = repo.get_active_chat(offender_id)
        history = session.history if session else []
        offender_msgs = [h for h in history if h.get("from") == offender_id][-5:]
        msg = f"🚨 <b>Жалоба!</b>\n\n"
        msg += f"👤 <b>На:</b> {get_display_name(offender_id)}\n"
        msg += f"📝 <b>Кол-во жалоб:</b> {len(reps)}\n\n"
        if offender_msgs:
            msg += "<b>📨 Последние сообщения нарушителя:</b>\n"
            for m in offender_msgs:
                msg += f"• {m.get('text', '[media]')}\n"
        else:
            msg += "<i>История сообщений пуста</i>\n"
        send_msg(user_id, msg, kb.report_verdict_kb(offender_id))


def show_admin_stats(user_id: int):
    from handlers.common import show_stats
    show_stats(user_id)
    show_admin_menu(user_id)


def handle_admin_commands(user_id: int, text: str) -> bool:
    """Returns True if command was handled."""
    if not repo.is_admin(user_id):
        return False

    if text.startswith("/ban "):
        try:
            uid = int(text.split()[1])
            if repo.is_admin(uid) or repo.is_owner(uid):
                send_msg(user_id, "🛡️ Нельзя забанить администратора или владельца.")
                return True
            moderation.ban(uid, 0, "Бан администратором", user_id)
            from services.matching import matching
            matching.stop_chat(uid)
            send_msg(user_id, f"🚫 {get_display_name(uid)} забанен.")
        except Exception:
            send_msg(user_id, "⚠️ Использование: /ban ID")
        return True

    if text.startswith("/unban "):
        try:
            uid = int(text.split()[1])
            send_msg(user_id, moderation.unban(uid))
        except Exception:
            send_msg(user_id, "⚠️ Использование: /unban ID")
        return True

    if text.startswith("/addcoins "):
        try:
            parts = text.split()
            uid = int(parts[1])
            amount = int(parts[2])
            new_balance = coins.add_coins(uid, amount)
            send_msg(user_id, f"🎁 Выдано {amount} 💰 пользователю {get_display_name(uid)}. Баланс: {new_balance}")
            send_msg(uid, f"🎁 Администратор выдал вам <b>{amount}</b> 💰!\n💰 Баланс: {new_balance}")
        except Exception:
            send_msg(user_id, "⚠️ Использование: /addcoins ID сумма")
        return True

    if text.startswith("/setprice "):
        try:
            price = int(text.split()[1])
            repo.set_reveal_price(price)
            send_msg(user_id, f"💰 Цена раскрытия установлена: {price} 💰")
        except Exception:
            send_msg(user_id, f"⚠️ Использование: /setprice сумма\nТекущая: {repo.get_reveal_price()}")
        return True

    if text.startswith("/say "):
        parts = text.split(" ", 2)
        if len(parts) < 3:
            send_msg(user_id, "⚠️ Использование: /say ID текст")
            return True
        try:
            tid = int(parts[1])
            session = repo.get_active_chat(tid)
            if session:
                partner = session.partner_of(tid)
                send_msg(partner, parts[2])
                send_msg(user_id, f"📨 От {get_display_name(tid)}:\n{parts[2]}")
            else:
                send_msg(user_id, f"❌ {get_display_name(tid)} не в чате.")
        except Exception:
            send_msg(user_id, "⚠️ Использование: /say ID текст")
        return True

    if text.startswith("/reply "):
        parts = text.split(" ", 2)
        if len(parts) < 3:
            send_msg(user_id, "⚠️ Использование: /reply ID текст")
            return True
        try:
            uid = int(parts[1])
            send_msg(uid, f"💬 <b>Ответ поддержки:</b>\n{parts[2]}")
            send_msg(user_id, f"✅ Ответ отправлен {get_display_name(uid)}.")
        except Exception:
            send_msg(user_id, "⚠️ Использование: /reply ID текст")
        return True

    if text == "/admin":
        show_admin_menu(user_id)
        return True

    # Owner commands
    if repo.is_owner(user_id):
        if text.startswith("/addadmin "):
            try:
                uid = int(text.split()[1])
                repo.add_admin(uid)
                send_msg(user_id, f"👑 {get_display_name(uid)} назначен администратором.")
                send_msg(uid, "🛡️ Вы назначены администратором бота!")
            except Exception:
                send_msg(user_id, "⚠️ Использование: /addadmin ID")
            return True
        if text.startswith("/removeadmin "):
            try:
                uid = int(text.split()[1])
                if uid == CONFIG.OWNER_ID:
                    send_msg(user_id, "👑 Нельзя снять владельца.")
                    return True
                repo.remove_admin(uid)
                send_msg(user_id, f"✅ {get_display_name(uid)} лишён прав администратора.")
                send_msg(uid, "⚠️ Вы больше не администратор.")
            except Exception:
                send_msg(user_id, "⚠️ Использование: /removeadmin ID")
            return True

    return False


def handle_admin_state(user_id: int, text: str) -> bool:
    """Handle FSM states for admin actions. Returns True if handled."""
    if user_id not in user_state:
        return False
    state = user_state.pop(user_id)

    # Ban with details
    if state.startswith("ban_details_"):
        target = int(state.split("_")[2])
        try:
            text_stripped = text.strip()
            if "|" in text_stripped:
                parts = text_stripped.split("|", 1)
                minutes = int(parts[0].strip())
                reason = parts[1].strip()
            else:
                parts = text_stripped.split(None, 1)
                minutes = int(parts[0].strip())
                reason = parts[1].strip() if len(parts) > 1 else "Не указана"
            if repo.is_admin(target) or repo.is_owner(target):
                send_msg(user_id, "🛡️ Нельзя забанить администратора или владельца.")
                return True
            msg = moderation.ban(target, minutes, reason, user_id)
            from services.matching import matching as _matching_svc
            _matching_svc.stop_chat(target)
            send_msg(user_id, msg)
            if minutes <= 0:
                send_msg(target, f"🚫 Вы заблокированы!\n📌 Причина: {reason}\n⏱ Срок: навсегда")
            else:
                send_msg(target, f"🚫 Вы заблокированы!\n📌 Причина: {reason}\n⏱ Срок: {minutes} минут")
        except Exception as e:
            print(f"ban_details err: {e}")
            send_msg(user_id, "⚠️ Неверный формат. Используйте: минуты | причина\nНапример: 60 | Спам")
        return True

    if state == "await_ban_id":
        try:
            uid = int(text.strip())
            if repo.is_admin(uid) or repo.is_owner(uid):
                send_msg(user_id, "🛡️ Нельзя забанить администратора или владельца.")
                return True
            moderation.ban(uid, 0, "Бан администратором", user_id)
            from services.matching import matching
            matching.stop_chat(uid)
            send_msg(user_id, f"🚫 {get_display_name(uid)} забанен.")
        except Exception:
            send_msg(user_id, "⚠️ Неверный ID.")
        return True

    if state == "await_unban_id":
        try:
            uid = int(text.strip())
            send_msg(user_id, moderation.unban(uid))
        except Exception:
            send_msg(user_id, "⚠️ Неверный ID.")
        return True

    if state == "await_addcoins":
        try:
            parts = text.strip().split()
            uid = int(parts[0])
            amount = int(parts[1])
            new_balance = coins.add_coins(uid, amount)
            send_msg(user_id, f"🎁 Выдано {amount} 💰 пользователю {get_display_name(uid)}. Баланс: {new_balance}")
            send_msg(uid, f"🎁 Администратор выдал вам <b>{amount}</b> 💰!\n💰 Баланс: {new_balance}")
        except Exception:
            send_msg(user_id, "⚠️ Неверный формат. Используйте: ID сумма")
        return True

    if state == "await_setprice":
        try:
            price = int(text.strip())
            repo.set_reveal_price(price)
            send_msg(user_id, f"💰 Цена раскрытия установлена: {price} 💰")
        except Exception:
            send_msg(user_id, "⚠️ Неверная сумма.")
        return True

    if state == "await_addadmin":
        try:
            uid = int(text.strip())
            repo.add_admin(uid)
            send_msg(user_id, f"👑 {get_display_name(uid)} назначен администратором.")
            send_msg(uid, "🛡️ Вы назначены администратором бота!")
        except Exception:
            send_msg(user_id, "⚠️ Неверный ID.")
        return True

    if state == "await_removeadmin":
        try:
            uid = int(text.strip())
            if uid == CONFIG.OWNER_ID:
                send_msg(user_id, "👑 Нельзя снять владельца.")
                return True
            repo.remove_admin(uid)
            send_msg(user_id, f"✅ {get_display_name(uid)} лишён прав администратора.")
            send_msg(uid, "⚠️ Вы больше не администратор.")
        except Exception:
            send_msg(user_id, "⚠️ Неверный ID.")
        return True

    return False
