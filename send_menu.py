import os, re, io, json
import requests
import pdfplumber
from datetime import datetime

TOKEN = os.environ["TELEGRAM_TOKEN"]
PDF_URL = "https://menu.officinagambrinus.com/menu/download/2"

STATE_FILE = "last_update_id.txt"


def telegram_get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 0}
    if offset:
        params["offset"] = offset
    return requests.get(url, params=params, timeout=30).json()


def telegram_send(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True
    }, timeout=30)


def read_state():
    try:
        return int(open(STATE_FILE).read().strip())
    except:
        return None


def write_state(update_id):
    with open(STATE_FILE, "w") as f:
        f.write(str(update_id))


def download_menu():
    r = requests.get(PDF_URL, timeout=30)
    r.raise_for_status()
    pdf = r.content

    parts = []
    with pdfplumber.open(io.BytesIO(pdf)) as pdf_file:
        for page in pdf_file.pages:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t)

    text = "\n".join(parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    last_update = read_state()
    updates = telegram_get_updates(last_update + 1 if last_update else None)

    if not updates.get("ok"):
        return

    for u in updates["result"]:
        update_id = u["update_id"]
        msg = u.get("message", {})
        text = msg.get("text", "").strip().lower()
        chat_id = msg.get("chat", {}).get("id")

        if not chat_id:
            write_state(update_id)
            continue

        if text == "menu":
            menu = download_menu()
            today = datetime.now().strftime("%d/%m/%Y")
            telegram_send(chat_id, f"🍽️ Menù del giorno — {today}\n\n{menu}")

        write_state(update_id)


if __name__ == "__main__":
    main()
