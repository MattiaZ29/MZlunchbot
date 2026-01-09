import os, re, io, hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import pdfplumber

# Sorgente del menu (PDF aggiornato)
PDF_URL = "https://menu.officinagambrinus.com/menu/download/2"

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_HASH = "state_last_menu_hash.txt"
STATE_DAY = "state_last_sent_day.txt"


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def download_pdf(url: str) -> bytes:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t)
    return "\n".join(parts)


def clean_text(s: str) -> str:
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def pick_sections(text: str) -> str:
    # Sezioni tipiche del menu
    titles = ["PRIMI PIATTI", "SECONDI PIATTI DEL GIORNO", "CONTORNI DEL GIORNO", "DOLCI"]
    blocks = []

    for i, title in enumerate(titles):
        next_title = titles[i + 1] if i + 1 < len(titles) else None
        if next_title:
            m = re.search(rf"{re.escape(title)}\s*(.*?)(?=\n{re.escape(next_title)}\b)", text, flags=re.S)
        else:
            m = re.search(rf"{re.escape(title)}\s*(.*)$", text, flags=re.S)

        if m:
            body = m.group(1).strip()
            blocks.append(f"*{title}*\n{body}")

    return "\n\n".join(blocks) if blocks else text


def telegram_send(message: str) -> None:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    r.raise_for_status()


def main():
    # Invia solo alle 12:00 ora di Roma
    now = datetime.now(ZoneInfo("Europe/Rome"))
   # if not (now.hour == 12 and now.minute == 0):
    #    print("Non è l'ora giusta:", now)
     #   return

    # TEST: invia sempre
    if not (now.hour == 12 and now.minute == 0):
        print("Non è l'ora giusta:", now)
        return


    today = now.strftime("%Y-%m-%d")
    if read_file(STATE_DAY) == today:
        print("Già inviato oggi.")
        return

    pdf_bytes = download_pdf(PDF_URL)
    current_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # Evita doppioni se il PDF non è cambiato dall'ultima volta
    if current_hash == read_file(STATE_HASH):
        print("Menu invariato rispetto all'ultimo invio.")
        write_file(STATE_DAY, today)
        return

    raw = clean_text(extract_text_from_pdf(pdf_bytes))
    menu_text = pick_sections(raw)

    msg = f"🍽️ *Menù del giorno* — {now:%d/%m/%Y}\n\n{menu_text}"
    telegram_send(msg)

    write_file(STATE_HASH, current_hash)
    write_file(STATE_DAY, today)
    print("Inviato.")


if __name__ == "__main__":
    main()
