#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ارسال یک پست به کانال مهدویان بدون تکرار در بازه ۱۵ دقیقه‌ای.

ایده اصلی:
- هر بازه ۱۵ دقیقه‌ای یک «اسلات» یکتا دارد (بر اساس timestamp).
- اگر برای همان اسلات قبلاً پست شده باشد، دوباره ارسال نمی‌شود.
- متن از روی شماره اسلات انتخاب می‌شود تا اجرای هم‌زمان هم همان ایندکس را ببیند،
  ولی فقط یک اجرا اجازه ارسال دارد (قفل اسلات در state).
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests
from contents import CONTENTS
from nahj_content import HIKAM, KHUTAB, LETTERS

API_TIMEOUT = 25
STATE_FILE = Path("state.json")
SLOT_SECONDS = 15 * 60  # ۱۵ دقیقه
RECENT_LIMIT = 80

DESTINATIONS = [
    "@Mahdaviyan_azari",
    "c0BnCQS000e39851ca7e6fc6421d949d",
    os.environ.get("CHAT_ID", "").strip(),
]

POOL = []
for t in CONTENTS:
    POOL.append(t)
for h in HIKAM:
    POOL.append("📖 از نهج‌البلاغه — حکمت:\n" + h)
for k in KHUTAB:
    POOL.append("📜 از نهج‌البلاغه — خطبه:\n" + k)
for letter in LETTERS:
    POOL.append("✉️ از نهج‌البلاغه — نامه:\n" + letter)


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def current_slot():
    return int(time.time() // SLOT_SECONDS)


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault("last_slot", None)
    data.setdefault("last_hashes", [])
    data.setdefault("content_index", 0)
    data.setdefault("sent_count", 0)
    return data


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_external_ayah():
    """آیه تصادفی از API عمومی قرآن (تنوع بیرونی)."""
    try:
        r = requests.get("https://api.alquran.cloud/v1/ayah/random/fa.fooladvand", timeout=20)
        r.raise_for_status()
        fa = r.json()["data"]
        ar = requests.get(
            "https://api.alquran.cloud/v1/ayah/{}/{}".format(fa["number"], "quran-uthmani"),
            timeout=20,
        )
        ar.raise_for_status()
        arabic = ar.json()["data"]
        surah = fa.get("surah", {}).get("name") or arabic.get("surah", {}).get("name", "")
        num = fa.get("numberInSurah") or arabic.get("numberInSurah")
        return (
            "📖 آیه‌ای از قرآن کریم\n"
            "{} | آیه {}\n\n"
            "{}\n\n"
            "{}\n\n"
            "اللهم عجل لولیک الفرج"
        ).format(surah, num, arabic.get("text", ""), fa.get("text", ""))
    except Exception as e:
        print("external ayah failed:", e)
        return None


def pick_text(slot, state):
    """انتخاب متن یکتا برای این اسلات؛ اگر در recent بود، بعدی را امتحان می‌کند."""
    recent = set(state.get("last_hashes") or [])
    n = len(POOL)

    # هر ۸ اسلات یک‌بار از منبع بیرونی
    if slot % 8 == 0:
        external = fetch_external_ayah()
        if external:
            h = text_hash(external)
            if h not in recent:
                return external, h, "external"

    for offset in range(n):
        idx = (slot + offset) % n
        text = POOL[idx]
        h = text_hash(text)
        if h not in recent:
            return text, h, idx

    # اگر همه recent پر بود، از اسلات خام استفاده کن
    idx = slot % n
    text = POOL[idx]
    return text, text_hash(text), idx


def send(token, chat_id, text):
    url = "https://botapi.rubika.ir/v3/{}/sendMessage".format(token)
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=API_TIMEOUT)
    print("Trying", chat_id, "HTTP", resp.status_code, resp.text[:250])
    try:
        data = resp.json()
    except Exception:
        return False
    return data.get("status") == "OK" or bool((data.get("data") or {}).get("message_id"))


def main():
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: BOT_TOKEN is missing")
        return 1

    slot = current_slot()
    state = load_state()

    if state.get("last_slot") == slot:
        print("SKIP: already posted for slot", slot)
        return 0

    text, h, meta = pick_text(slot, state)
    print("slot=", slot, "meta=", meta, "hash=", h)
    print("preview:", text[:120])

    ok = False
    tried = []
    for chat_id in DESTINATIONS:
        if not chat_id or chat_id in tried:
            continue
        tried.append(chat_id)
        if send(token, chat_id, text):
            print("Posted using", chat_id)
            ok = True
            break

    if not ok:
        print("ERROR: could not send")
        return 1

    # فقط بعد از ارسال موفق قفل اسلات و هش را ثبت کن
    state["last_slot"] = slot
    hashes = state.get("last_hashes") or []
    hashes.append(h)
    state["last_hashes"] = hashes[-RECENT_LIMIT:]
    state["sent_count"] = int(state.get("sent_count", 0)) + 1
    if isinstance(meta, int):
        state["content_index"] = (meta + 1) % len(POOL)
    save_state(state)
    print("State saved. sent_count=", state["sent_count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
