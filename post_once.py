#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ارسال یک پست به کانال مهدویان هر ۳۰ دقیقه (۵ صبح تا ۲۳ به وقت تهران).
محتوا به صورت ترتیبی و بدون تکرار تا اتمام کل بانک (برای پوشش یک سال).
ترتیب چرخشی دسته‌ها: مهدوی → حکمت → حدیث → خطبه → نامه → آیه
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from contents import CONTENTS
from nahj_content import HIKAM, KHUTAB, LETTERS, HADITHS

API_TIMEOUT = 25
STATE_FILE = Path("state.json")
SLOT_SECONDS = 30 * 60
CHANNEL_FOOTER = "\n\n━━━━━━━━━━━━━━\n🔗 کانال مهدویان:\nhttps://rubika.ir/Mahdaviyan_azari\n@Mahdaviyan_azari"

TEHRAN = timezone(timedelta(hours=3, minutes=30))

DESTINATIONS = [
    "@Mahdaviyan_azari",
    "c0BnCQS000e39851ca7e6fc6421d949d",
    os.environ.get("CHAT_ID", "").strip(),
]

# دسته‌بندی محتوا برای ارسال ترتیبی بدون تکرار
# برای متن مهدوی پیشوند خالی (فقط خود متن)
# برای نهج‌البلاغه و حدیث پیشوند نگه داشته می‌شود
CATEGORIES = [
    ("mahdavi", CONTENTS, ""),
    ("hikam", HIKAM, "📖 از نهج‌البلاغه — حکمت:\n"),
    ("hadith", HADITHS, "📿 حدیث:\n"),
    ("khutba", KHUTAB, "📜 از نهج‌البلاغه — خطبه:\n"),
    ("letter", LETTERS, "✉️ از نهج‌البلاغه — نامه:\n"),
]


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def with_footer(text):
    body = (text or "").rstrip()
    if "rubika.ir/Mahdaviyan_azari" in body:
        return body
    return body + CHANNEL_FOOTER


def tehran_now():
    return datetime.now(TEHRAN)


def is_active_hours(now):
    h, m = now.hour, now.minute
    if h < 5:
        return False
    if h > 23:
        return False
    if h == 23 and m > 0:
        return False
    return True


def current_slot():
    return int(time.time() // SLOT_SECONDS)


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault("last_slot", None)
    data.setdefault("sent_count", 0)
    data.setdefault("category_turn", 0)  # کدام دسته بعدی است
    data.setdefault("mahdavi_index", 0)
    data.setdefault("hikam_index", 0)
    data.setdefault("hadith_index", 0)
    data.setdefault("khutba_index", 0)
    data.setdefault("letter_index", 0)
    data.setdefault("ayah_count", 0)
    return data


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_external_ayah():
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


def pick_sequential(state):
    """انتخاب ترتیبی از دسته‌ها بدون تکرار تا اتمام بانک هر دسته"""
    turn = int(state.get("category_turn", 0))

    # هر ۷ نوبت یک آیه تصادفی (برای تنوع)
    if turn % 7 == 6:
        ayah = fetch_external_ayah()
        if ayah:
            state["ayah_count"] = int(state.get("ayah_count", 0)) + 1
            state["category_turn"] = turn + 1
            return ayah, "ayah"

    # چرخش بین دسته‌ها
    for offset in range(len(CATEGORIES)):
        cat_idx = (turn + offset) % len(CATEGORIES)
        key, items, prefix = CATEGORIES[cat_idx]
        idx_key = key + "_index"
        current = int(state.get(idx_key, 0))

        if not items:
            continue

        # اگر هنوز آیتم استفاده نشده داریم
        if current < len(items):
            text = prefix + items[current]
            state[idx_key] = current + 1
            state["category_turn"] = turn + 1
            return text, f"{key}:{current}"

        # اگر تموم شده، از اول شروع کن (بعد از یک دور کامل)
        # ولی اول بقیه دسته‌ها را چک کن

    # اگر همه دسته‌ها حداقل یک دور زده‌اند، از اول کوچک‌ترین ایندکس استفاده کن
    for key, items, prefix in CATEGORIES:
        if not items:
            continue
        idx_key = key + "_index"
        current = int(state.get(idx_key, 0)) % len(items)
        text = prefix + items[current]
        state[idx_key] = current + 1
        state["category_turn"] = turn + 1
        return text, f"{key}:cycle:{current}"

    # fallback
    return "اللهم عجل لولیک الفرج\n\nیاد امام زمان (عج) را زنده نگه داریم.", "fallback"


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

    now = tehran_now()
    print("Tehran now:", now.isoformat())

    if not is_active_hours(now):
        print("SKIP: outside active hours (5:00–23:00 Tehran)")
        return 0

    slot = current_slot()
    state = load_state()

    if state.get("last_slot") == slot:
        print("SKIP: already posted for slot", slot)
        return 0

    text, meta = pick_sequential(state)
    text = with_footer(text)
    print("slot=", slot, "meta=", meta)
    print("preview:", text[:160])

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

    state["last_slot"] = slot
    state["sent_count"] = int(state.get("sent_count", 0)) + 1
    save_state(state)
    print("State saved. sent_count=", state["sent_count"])
    print("Indexes → mahdavi:{}, hikam:{}, hadith:{}, khutba:{}, letter:{}".format(
        state.get("mahdavi_index"), state.get("hikam_index"),
        state.get("hadith_index"), state.get("khutba_index"), state.get("letter_index")
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
