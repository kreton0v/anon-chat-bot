import time
from typing import Optional

from config import CONFIG
from repository import repo
from services import coins
from utils import get_display_name, escape_html, get_ref_link
import keyboards as kb
from telegram_api import send_msg, api


# --- In-memory state (per-user FSM) ---
user_state: dict = {}  # user_id -> state string


def set_state(user_id: int, state: Optional[str]):
    if state is None:
        user_state.pop(user_id, None)
    else:
        user_state[user_id] = state


def get_state(user_id: int) -> Optional[str]:
    return user_state.get(user_id)


# --- Support / Suggestion modes ---
support_mode: set = set()
suggestion_mode: set = set()


def handle_start(user_id: int, text: str):
    p = repo.get_profile(user_id)
    args = text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer = int(args[1].replace("ref_", ""))
            if coins.register_referral(user_id, referrer):
                send_msg(user_id, "👋 Вы присоединились по приглашению друга!\n💰 Зарабатывайте монеты вместе!")
                send_msg(referrer, f"🎉 {get_display_name(user_id)} присоединился по вашей ссылке!\n⏱ Как только он посидит в чате 1 минуту — вы получите засчитанного реферала.")
        except Exception:
            pass

    if not p.is_registered:
        send_msg(user_id, "👋 Добро пожаловать! Выберите ваш пол:", kb.menu_register_gender())
    else:
        send_msg(user_id, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))


def handle_callback_common(user_id: int, data: str):
    p = repo.get_profile(user_id)

    # Registration
    if data == "reg_M":
        p.gender = "M"
        repo.save_profile(p)
        send_msg(user_id, "📅 Выберите возраст:", kb.menu_register_age())
        return
    if data == "reg_F":
        p.gender = "F"
        repo.save_profile(p)
        send_msg(user_id, "📅 Выберите возраст:", kb.menu_register_age())
        return
    if data.startswith("reg_age_"):
        age = data.replace("reg_age_", "")
        p.age = age
        repo.save_profile(p)
        send_msg(user_id, "✅ Регистрация завершена!")
        send_msg(user_id, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))
        return

    # Main menu
    if data == "profile":
        show_profile(user_id)
        return
    if data == "stats":
        show_stats(user_id)
        return
    if data == "referral":
        show_referral(user_id)
        return
    if data == "support":
        support_mode.add(user_id)
        send_msg(user_id, "💬 Вы в режиме поддержки. Опишите вашу проблему — мы ответим вам здесь.", kb.support_keyboard())
        return
    if data == "suggest":
        suggestion_mode.add(user_id)
        send_msg(user_id, "💡 Напишите вашу идею для бота. Мы обязательно рассмотрим её!", kb.suggestion_keyboard())
        return
    if data == "main_menu":
        send_msg(user_id, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))
        return


def show_profile(user_id: int):
    p = repo.get_profile(user_id)
    g = {"M": "👨 Мужской", "F": "👩 Женский"}.get(p.gender, "❓ Не указан")
    a = p.age or "❓"
    ref_count = len(p.referrals)
    ref_earned = p.referral_batches * 100
    role = ""
    if repo.is_owner(user_id):
        role = "\n👑 <b>Роль:</b> Владелец"
    elif repo.is_admin(user_id):
        role = "\n🛡️ <b>Роль:</b> Администратор"
    msg = (f"<b>👤 Профиль</b>{role}\n\n"
           f"👤 Пол: {g}\n📅 Возраст: {a}\n"
           f"💰 Монеты: {p.coins}\n"
           f"👥 Приглашено: {ref_count}\n"
           f"🎁 Заработано: {ref_earned} 💰")
    send_msg(user_id, msg)
    send_msg(user_id, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))


def show_stats(user_id: int):
    chats = repo.get_all_active_chats()
    waiting = repo.get_all_waiting()
    total_users = len(repo.get_all_profiles())
    banned_count = len(repo.get_ban_list())
    reports_count = len([r for _, reps in repo.get_all_unresolved_reports() for r in reps])
    price = repo.get_reveal_price()
    msg = (f"<b>📊 Статистика</b>\n\n"
           f"🔗 Пар: {len(chats)}\n"
           f"⏳ В очереди: {len(waiting)}\n"
           f"👥 Всего пользователей: {total_users}\n"
           f"🚫 Забанено: {banned_count}\n"
           f"📝 Активных жалоб: {reports_count}\n"
           f"💰 Цена раскрытия: {price}")
    send_msg(user_id, msg)


def show_referral(user_id: int):
    p = repo.get_profile(user_id)
    ref_link = get_ref_link(user_id)
    ref_count = len(p.referrals)
    ref_earned = p.referral_batches * 100
    msg = (f"<b>👥 Реферальная программа</b>\n\n"
           f"💰 <b>Награда:</b> 100 монет за каждых 5 друзей\n"
           f"⏱ <b>Условие:</b> друг должен посидеть в чате минимум 1 минуту\n\n"
           f"👥 Приглашено: <b>{ref_count}</b>\n"
           f"🎁 Заработано: <b>{ref_earned}</b> 💰\n\n"
           f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>")
    share_url = f"https://t.me/share/url?url={ref_link}&text=Присоединяйся к анонимному чату!"
    inline = {
        "inline_keyboard": [
            [{"text": "📤 Поделиться", "url": share_url}],
            [{"text": "🔙 Назад", "callback_data": "main_menu"}]
        ]
    }
    send_msg(user_id, msg, inline)


def forward_support(user_id: int, text: str, msg_obj: dict = None):
    target = CONFIG.OWNER_ID if CONFIG.OWNER_ID else CONFIG.ADMIN_ID
    if not target:
        send_msg(user_id, "❌ Поддержка временно недоступна.")
        return
    prefix = f"💬 <b>Поддержка</b> от {get_display_name(user_id)} (ID: {user_id}):\n"
    if msg_obj and not text:
        # Media support message
        media_type = None
        file_id = None
        if "photo" in msg_obj:
            media_type, file_id = "photo", msg_obj["photo"][-1]["file_id"]
        elif "video" in msg_obj:
            media_type, file_id = "video", msg_obj["video"]["file_id"]
        elif "document" in msg_obj:
            media_type, file_id = "document", msg_obj["document"]["file_id"]
        elif "voice" in msg_obj:
            media_type, file_id = "voice", msg_obj["voice"]["file_id"]
        elif "audio" in msg_obj:
            media_type, file_id = "audio", msg_obj["audio"]["file_id"]
        elif "sticker" in msg_obj:
            media_type, file_id = "sticker", msg_obj["sticker"]["file_id"]
        if media_type and file_id:
            method_map = {"photo": "sendPhoto", "video": "sendVideo", "document": "sendDocument",
                          "voice": "sendVoice", "audio": "sendAudio", "sticker": "sendSticker"}
            method = method_map.get(media_type, "sendDocument")
            payload = {"chat_id": target}
            payload[media_type if media_type != "photo" else "photo"] = file_id
            caption = msg_obj.get("caption", "")
            payload["caption"] = prefix + (caption or f"[{media_type}]")
            api(method, payload)
            send_msg(user_id, "✅ Сообщение отправлено в поддержку. Ожидайте ответа.")
    else:
        send_msg(target, prefix + text)
        send_msg(user_id, "✅ Сообщение отправлено в поддержку. Ожидайте ответа.")
    send_msg(target, f"📨 <i>Чтобы ответить:</i> <code>/reply {user_id} ваш_текст</code>")


def forward_suggestion(user_id: int, text: str):
    target = CONFIG.OWNER_ID if CONFIG.OWNER_ID else CONFIG.ADMIN_ID
    if not target:
        send_msg(user_id, "❌ Отправка идеи временно недоступна.")
        return
    send_msg(target, f"💡 <b>Новая идея!</b>\n\nОт: {get_display_name(user_id)} (ID: {user_id})\n\n{text}")
    send_msg(user_id, "💡 <b>Спасибо за идею!</b>\nМы обязательно рассмотрим её.")
