import os
import re
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import pdfplumber

# PDF del menù del giorno
PDF_URL = "https://menu.officinagambrinus.com/menu/download/2"

# Secrets GitHub Actions
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# File stato: evita doppio invio nello stesso giorno
STATE_DAY_FILE = "state_last_sent_day.txt"


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
    return "\n".join(parts).strip()


def clean_text(s: str) -> str:
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def pick_sections(text: str) -> str:
    """
    Prova a prendere sezioni tipiche dal menù.
    Se non trova i titoli, manda comunque tutto il testo pulito.
    """
    titles = [
        "PRIMI PIATTI",
        "SECONDI PIATTI DEL GIORNO",
        "CONTORNI DEL GIORNO",
        "DOLCI",
    ]

    blocks = []
    for i, title in enumerate(titles):
        next_title = titles[i + 1] if i + 1 < len(titles) else None

        if next_title:
            m = re.search(
                rf"{re.escape(title)}\s*(.*?)(?=\n{re.escape(next_title)}\b)",
                text,
                flags=re.S,
            )
        else:
            m = re.search(rf"{re.escape(title)}\s*(.*)$", text, flags=re.S)

        if m:
            body = m.group(1).strip()
            blocks.append(f"*{title}*\n{body}")

    return "\n\n".join(blocks) if blocks else text


def telegram_send(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    r.raise_for_status()


def main() -> None:
    # Ora Italia (gestisce ora legale/solare)
    now = datetime.now(ZoneInfo("Europe/Rome"))

    # Invia SOLO alle 16:00
    if not (now.hour == 16 and now.minute == 0):
        print("Non è l'ora giusta:", now.isoformat())
        return

    today = now.strftime("%Y-%m-%d")
    if read_file(STATE_DAY_FILE) == today:
        print("Già inviato oggi.")
        return

    pdf_bytes = download_pdf(PDF_URL)
    raw_text = extract_text_from_pdf(pdf_bytes)
    text = pick_sections(clean_text(raw_text))

    # Safety: Telegram ha limite messaggio; tagliamo se troppo lungo
    if len(text) > 3800:
        text = text[:3800] + "\n\n(…continua)"

    msg = f"🍽️ *Menù del giorno* — {now:%d/%m/%Y}\n\n{text}"
    telegram_send(msg)

    write_file(STATE_DAY_FILE, today)
    print("Inviato.")


if __name__ == "__main__":
    main()
