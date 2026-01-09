import os, re, io
from datetime import datetime
import requests
import pdfplumber

PDF_URL = "https://menu.officinagambrinus.com/menu/download/2"

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def download_pdf(url: str) -> bytes:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content

def extract_text(pdf_bytes: bytes) -> str:
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
    titles = ["PRIMI PIATTI", "SECONDI PIATTI DEL GIORNO", "CONTORNI DEL GIORNO", "DOLCI"]
    blocks = []
    for i, title in enumerate(titles):
        next_title = titles[i + 1] if i + 1 < len(titles) else None
        if next_title:
            m = re.search(rf"{re.escape(title)}\s*(.*?)(?=\n{re.escape(next_title)}\b)", text, flags=re.S)
        else:
            m = re.search(rf"{re.escape(title)}\s*(.*)$", text, flags=re.S)
        if m:
            blocks.append(f"{title}\n{m.group(1).strip()}")
    return "\n\n".join(blocks) if blocks else text

def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }, timeout=30)
    r.raise_for_status()

def main():
    pdf = download_pdf(PDF_URL)
    text = pick_sections(clean_text(extract_text(pdf)))

    # Telegram ha un limite messaggio: se è lunghissimo, tagliamo (safe)
    max_len = 3800
    if len(text) > max_len:
        text = text[:max_len] + "\n\n(…continua)"

    today = datetime.now().strftime("%d/%m/%Y")
    msg = f"🍽️ Menù del giorno — {today}\n\n{text}"
    send_telegram(msg)

if __name__ == "__main__":
    main()
