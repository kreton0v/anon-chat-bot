import time
from typing import Optional

from config import CONFIG
from repository import repo
from services import matching, moderation, coins, reveal
from utils import get_display_name, get_role_tag, escape_html
from telegram_api import send_msg, send_media, answer_cb
import keyboards as kb
from handlers.common import support_mode, suggestion_mode, set_state


# Pending media consent (in-memory)
pending_media: dict = {}  # user_id -> {"file_id", "caption", "media_type"}


def handle_find_callback(user_id: int, data: str):
    p = repo.get_profile(user_id)
    if not p.is_registered:
        send_msg(user_id, "⚠️ Сначала завершите регистрацию!")
        return
    if data == "find":
        send_msg(user_id, "🔍 Кого ищем?", kb.menu_find_prefs())
        return
    if data.startswith("find_") and not data.startswith("find_age_"):
        set_state(user_id, data)  # store gender pref
        send_msg(user_id, "📅 Возрастной диапазон?", kb.menu_find_age())
        return
    if data.startswith("find_age_"):
        state = get_state(user_id)
        fg = state.replace("find_", "") if state else "A"
        fa = data.replace("find_age_", "")
        set_state(user_id, None)

        # Check ban
        banned, reason = moderation.is_banned(user_id)
        if banned:
            send_msg(user_id, f"🚫 Вы заблокированы.\n📌 Причина: {reason}")
            return

        # Check existing chat
        existing = repo.get_active_chat(user_id)
        if existing:
            send_msg(user_id, "💬 Вы уже в чате.")
            return

        session = matching.find_pair(user_id, fg, fa)
        if session:
            warn = ""
            if repo.get_profile(user_id).is_teen or repo.get_profile(session.partner_of(user_id)).is_teen:
                warn = "\n\n⚠️ <b>ВНИМАНИЕ:</b> Один из собеседников 13-16 лет.\n<b>Отправка медиа запрещена.</b>"
            send_msg(user_id, f"<b>🎉 Собеседник найден!</b>{warn}", kb.chat_keyboard())
            send_msg(session.partner_of(user_id), f"<b>🎉 Собеседник найден!</b>{warn}", kb.chat_keyboard())
            # Notify admin
            if CONFIG.ADMIN_ID and not repo.is_admin(user_id):
                send_msg(CONFIG.ADMIN_ID, f"🔗 Новая пара:\n{get_display_name(user_id)} ↔️ {get_display_name(session.partner_of(user_id))}")
        else:
            send_msg(user_id, "🔍 Ищем собеседника...", kb.cancel_search_kb())
        return


def get_state(user_id: int) -> Optional[str]:
    from handlers.common import user_state
    return user_state.get(user_id)


def handle_stop(user_id: int):
    result = matching.stop_chat(user_id)
    if result:
        partner_id, duration, history = result
        send_msg(user_id, "💔 Чат завершён.", kb.remove_keyboard())
        send_msg(partner_id, "👋 Собеседник покинул чат.", kb.remove_keyboard())
        # Track referral
        coins.track_chat_duration(user_id, duration)
        coins.track_chat_duration(partner_id, duration)
        # Notify admin
        if CONFIG.ADMIN_ID and not repo.is_admin(user_id):
            send_msg(CONFIG.ADMIN_ID, f"💔 Пара разошлась:\n{get_display_name(user_id)} ↔️ {get_display_name(partner_id)}")
    else:
        # Maybe was just searching
        if matching.stop_search(user_id):
            send_msg(user_id, "❌ Поиск отменён.", kb.remove_keyboard())
        send_msg(user_id, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))


def handle_report(user_id: int):
    session = repo.get_active_chat(user_id)
    if not session:
        send_msg(user_id, "❌ Нет собеседника.")
        return
    partner = session.partner_of(user_id)
    moderation.report(user_id, partner)

    # Build report message for admin
    offender_msgs = [h for h in session.history if h.get("from") == partner][-5:]
    msg = f"🚨 <b>Новая жалоба!</b>\n\n"
    msg += f"👤 <b>От:</b> {get_display_name(user_id)}\n"
    msg += f"👤 <b>На:</b> {get_display_name(partner)}\n\n"
    if offender_msgs:
        msg += "<b>📨 Последние сообщения нарушителя:</b>\n"
        for m in offender_msgs:
            msg += f"• {m.get('text', '[media]')}\n"
    else:
        msg += "<i>История сообщений пуста</i>\n"
    if CONFIG.ADMIN_ID:
        send_msg(CONFIG.ADMIN_ID, msg, kb.report_verdict_kb(partner))
    send_msg(user_id, "🚨 <b>Жалоба отправлена!</b>\nАдминистратор рассмотрит её.")


def handle_reveal(user_id: int):
    session = repo.get_active_chat(user_id)
    if not session:
        send_msg(user_id, "❌ Нет собеседника.")
        return
    partner = session.partner_of(user_id)
    price = repo.get_reveal_price()
    success, msg = reveal.reveal(user_id, partner, price)
    if success:
        p = repo.get_profile(user_id)
        send_msg(user_id, msg + f"\n\n💰 Осталось монет: {p.coins}")
        if CONFIG.ADMIN_ID:
            send_msg(CONFIG.ADMIN_ID, f"🔓 {get_display_name(user_id)} раскрыл {get_display_name(partner)} за {price} 💰")
    else:
        send_msg(user_id, msg)


def relay_text(user_id: int, text: str):
    session = repo.get_active_chat(user_id)
    if not session:
        return False
    partner = session.partner_of(user_id)
    send_msg(partner, text, kb.report_inline_kb())
    session.history.append({"from": user_id, "text": text, "type": "text", "time": time.time()})
    repo.update_chat_history(session.user_a, session.user_b, session.history)
    # Admin notify
    if CONFIG.ADMIN_ID and not repo.is_admin(user_id):
        tag = get_role_tag(user_id)
        send_msg(CONFIG.ADMIN_ID, f"💬 {tag}{get_display_name(user_id)} → {get_display_name(partner)}:\n{text}")
    return True


def relay_media(user_id: int, msg_obj: dict):
    session = repo.get_active_chat(user_id)
    if not session:
        return False
    partner = session.partner_of(user_id)

    # Check teen media block
    if repo.get_profile(user_id).is_teen or repo.get_profile(partner).is_teen:
        send_msg(user_id, "<b>🚫 Медиа заблокировано!</b>\nОдин из собеседников 13-16 лет. Только текст.")
        return True

    media_type = None
    file_id = None
    if "photo" in msg_obj:
        media_type, file_id = "photo", msg_obj["photo"][-1]["file_id"]
    elif "video" in msg_obj:
        media_type, file_id = "video", msg_obj["video"]["file_id"]
    elif "video_note" in msg_obj:
        media_type, file_id = "video_note", msg_obj["video_note"]["file_id"]
    elif "voice" in msg_obj:
        media_type, file_id = "voice", msg_obj["voice"]["file_id"]
    elif "audio" in msg_obj:
        media_type, file_id = "audio", msg_obj["audio"]["file_id"]
    elif "document" in msg_obj:
        media_type, file_id = "document", msg_obj["document"]["file_id"]
    elif "sticker" in msg_obj:
        media_type, file_id = "sticker", msg_obj["sticker"]["file_id"]

    if not media_type or not file_id:
        return False

    caption = msg_obj.get("caption", "")
    send_media(partner, media_type, file_id, caption, kb.report_inline_kb())

    display_text = f"[{media_type}]"
    if caption:
        display_text += f" {caption}"
    session.history.append({"from": user_id, "text": display_text, "type": media_type, "time": time.time()})
    repo.update_chat_history(session.user_a, session.user_b, session.history)

    if CONFIG.ADMIN_ID and not repo.is_admin(user_id):
        tag = get_role_tag(user_id)
        send_msg(CONFIG.ADMIN_ID, f"📎 [{media_type}] {tag}{get_display_name(user_id)} → {get_display_name(partner)}")
    return True


def ask_media_consent(user_id: int, msg_obj: dict, media_type: str):
    file_id = None
    caption = msg_obj.get("caption", "")
    if media_type == "photo":
        file_id = msg_obj["photo"][-1]["file_id"]
    elif media_type == "video":
        file_id = msg_obj["video"]["file_id"]
    elif media_type == "video_note":
        file_id = msg_obj["video_note"]["file_id"]

    pending_media[user_id] = {
        "file_id": file_id, "caption": caption, "media_type": media_type, "msg_obj": msg_obj
    }
    disclaimer = (
        "⚠️ <b>Важное уведомление</b>\n\n"
        "Вы собираетесь отправить медиафайл.\n"
        "Нажимая «Согласен», вы подтверждаете:\n\n"
        "• Владелец бота не несёт ответственности за содержимое переписки\n"
        "• Вы не имеете претензий к владельцу и администрации\n"
        "• Вы несёте полную ответственность за отправляемый контент\n\n"
        "<i>Это обязательное согласие для категории 13-16 лет.</i>"
    )
    send_msg(user_id, disclaimer, kb.media_consent_kb(media_type))


def handle_media_consent(user_id: int, data: str):
    if data == "consent_cancel":
        pending_media.pop(user_id, None)
        send_msg(user_id, "❌ Отправка отменена.")
        return
    media_type = data.replace("consent_", "")
    if user_id in pending_media and pending_media[user_id]["media_type"] == media_type:
        pm = pending_media.pop(user_id)
        relay_media(user_id, pm["msg_obj"])
