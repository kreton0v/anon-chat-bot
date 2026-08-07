import json
import urllib.request
import ssl
from config import CONFIG

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def api(method: str, data: dict = None) -> dict:
    url = f"https://api.telegram.org/bot{CONFIG.BOT_TOKEN}/{method}"
    try:
        if data:
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        else:
            req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, context=_ctx, timeout=30)
        return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"api err {method}: {e}")
        return {"ok": False}


def send_msg(chat_id: int, text: str, markup: dict = None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if markup:
        payload["reply_markup"] = json.dumps(markup, ensure_ascii=False)
    api("sendMessage", payload)


def answer_cb(callback_query_id: str):
    api("answerCallbackQuery", {"callback_query_id": callback_query_id})


def send_media(chat_id: int, media_type: str, file_id: str, caption: str = "", markup: dict = None):
    method_map = {
        "photo": "sendPhoto", "video": "sendVideo", "video_note": "sendVideoNote",
        "voice": "sendVoice", "audio": "sendAudio", "document": "sendDocument", "sticker": "sendSticker"
    }
    method = method_map.get(media_type, "sendDocument")
    payload = {"chat_id": chat_id}
    key = "photo" if media_type == "photo" else media_type
    payload[key] = file_id
    if caption and media_type not in ("sticker", "video_note"):
        payload["caption"] = caption
    if markup:
        payload["reply_markup"] = json.dumps(markup, ensure_ascii=False)
    api(method, payload)
