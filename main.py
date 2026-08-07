import json
import time
import signal
import sys
import urllib.request
import ssl
from concurrent.futures import ThreadPoolExecutor

from config import CONFIG
from telegram_api import api, answer_cb, send_msg
from middlewares import middleware
from repository import repo

# Import handlers
from handlers.common import (
    handle_start, handle_callback_common, support_mode, suggestion_mode,
    forward_support, forward_suggestion, user_state
)
from handlers.chat import (
    handle_find_callback, handle_stop, handle_report, handle_reveal,
    relay_text, relay_media, ask_media_consent, handle_media_consent,
    pending_media
)
from handlers.admin import (
    handle_admin_callback, handle_admin_commands, handle_admin_state,
    show_admin_menu
)
import keyboards as kb


# Graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    print("\nShutdown requested, finishing pending updates...")

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# Thread pool for handlers
executor = ThreadPoolExecutor(max_workers=20)


def process_update(update: dict):
    try:
        if "callback_query" in update:
            q = update["callback_query"]
            cid = q["from"]["id"]
            data = q["data"]
            qid = q["id"]
            answer_cb(qid)

            # Run middleware
            result = middleware.process(cid, q.get("message", {}), {})
            if result and result.get("action") == "banned":
                return

            # Admin callbacks
            if data in ("ban", "unban", "addcoins", "setprice", "users", "reports", "stats",
                        "manage_admins", "addadmin_inline", "removeadmin_inline", "listadmins",
                        "admin_back") or data.startswith(("ban_", "noban_", "cancel_report_")):
                handle_admin_callback(cid, data)
                return

            # Chat callbacks
            if data in ("find",) or data.startswith(("find_", "find_age_")):
                handle_find_callback(cid, data)
                return
            if data.startswith("consent_") or data == "consent_cancel":
                handle_media_consent(cid, data)
                return
            if data == "report_msg":
                handle_report(cid)
                return
            if data == "stop":
                handle_stop(cid)
                return
            if data == "reveal":
                handle_reveal(cid)
                return

            # Common callbacks
            handle_callback_common(cid, data)
            return

        if "message" in update:
            m = update["message"]
            cid = m["chat"]["id"]
            text = m.get("text", "")

            # Run middleware
            result = middleware.process(cid, m, {})
            if result and result.get("action") == "banned":
                return

            # Text message routing
            if text:
                # Admin commands
                if handle_admin_commands(cid, text):
                    return
                # Admin FSM states
                if handle_admin_state(cid, text):
                    return

                # Support mode
                if cid in support_mode:
                    if text == "🔙 Выйти из поддержки":
                        support_mode.discard(cid)
                        send_msg(cid, "✅ Вы вышли из поддержки.", kb.remove_keyboard())
                        send_msg(cid, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))
                        return
                    forward_support(cid, text)
                    return

                # Suggestion mode
                if cid in suggestion_mode:
                    if text == "🔙 Отменить":
                        suggestion_mode.discard(cid)
                        send_msg(cid, "❌ Предложение отменено.", kb.remove_keyboard())
                        send_msg(cid, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))
                        return
                    suggestion_mode.discard(cid)
                    forward_suggestion(cid, text)
                    send_msg(cid, "✅ Спасибо!", kb.remove_keyboard())
                    send_msg(cid, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))
                    return

                # Chat keyboard commands
                if text == "⛔ Завершить чат":
                    handle_stop(cid)
                    return
                if text == "🚨 Пожаловаться":
                    handle_report(cid)
                    return
                if text == "📋 Меню":
                    session = repo.get_active_chat(cid)
                    if session:
                        send_msg(cid, "❌ Сначала завершите текущий чат.")
                        return
                    if cid in support_mode:
                        send_msg(cid, "❌ Сначала выйдите из поддержки.")
                        return
                    if cid in suggestion_mode:
                        send_msg(cid, "❌ Сначала отмените предложение идеи.")
                        return
                    send_msg(cid, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))
                    return

                # Commands
                if text.startswith("/start"):
                    handle_start(cid, text)
                    return
                if text == "/find":
                    send_msg(cid, "🔍 Кого ищем?", kb.menu_find_prefs())
                    return
                if text == "/stop":
                    handle_stop(cid)
                    return
                if text == "/stats":
                    from handlers.common import show_stats
                    show_stats(cid)
                    return
                if text == "/report":
                    handle_report(cid)
                    return

                # Relay text in chat
                if not relay_text(cid, text):
                    send_msg(cid, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))
                return

            # Media message
            media_type = None
            if "photo" in m:
                media_type = "photo"
            elif "video" in m:
                media_type = "video"
            elif "video_note" in m:
                media_type = "video_note"
            elif "voice" in m:
                media_type = "voice"
            elif "audio" in m:
                media_type = "audio"
            elif "document" in m:
                media_type = "document"
            elif "sticker" in m:
                media_type = "sticker"

            if media_type:
                # Support mode media
                if cid in support_mode:
                    forward_support(cid, None, m)
                    return

                # Teen consent for photo/video/video_note
                p = repo.get_profile(cid)
                if p.is_teen and media_type in ("photo", "video", "video_note"):
                    ask_media_consent(cid, m, media_type)
                    return

                if not relay_media(cid, m):
                    send_msg(cid, "<b>📋 Главное меню</b>", kb.menu_main(repo.get_reveal_price()))

    except Exception as e:
        print(f"Error processing update: {e}")
        import traceback
        traceback.print_exc()


def get_updates(offset: int):
    try:
        url = f"https://api.telegram.org/bot{CONFIG.BOT_TOKEN}/getUpdates?offset={offset}&limit=10"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        data = json.loads(resp.read().decode('utf-8'))
        if not data.get("ok"):
            return []
        return data.get("result", [])
    except Exception as e:
        print(f"getUpdates error: {e}")
        return []


def main():
    print("Bot starting...")
    offset = 0
    try:
        with open("/tmp/bot_offset.txt", "r") as f:
            offset = int(f.read().strip())
    except:
        pass

    consecutive_errors = 0
    while not shutdown_requested:
        try:
            updates = get_updates(offset)
            consecutive_errors = 0
            for u in updates:
                offset = u["update_id"] + 1
                executor.submit(process_update, u)
                try:
                    with open("/tmp/bot_offset.txt", "w") as f:
                        f.write(str(offset))
                except:
                    pass
            time.sleep(1)
        except Exception as e:
            consecutive_errors += 1
            sleep_time = min(consecutive_errors * 2, 30)
            print(f"Main loop error: {e}, retrying in {sleep_time}s...")
            time.sleep(sleep_time)

    print("Shutting down gracefully...")
    executor.shutdown(wait=True)
    print("Bye!")


if __name__ == "__main__":
    main()
