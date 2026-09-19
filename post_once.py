#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ارسال یک پست در هر نیم‌ساعت تهران (۵:۰۰ تا ۲۳:۰۰).
اسلات بر اساس ساعت تهران است تا اگر Actions دیر اجرا شد، همان نیم‌ساعت پر شود.
محتوا ترتیبی و بدون تکرار.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from contents import CONTENTS
from nahj_content import HIKAM, KHUTAB, LETTERS, HADITHS

API_TIMEOUT = 25
STATE_FILE = Path("state.json")
CHANNEL_FOOTER = (
    "\n\n━━━━━━━━━━━━━━\n"
    "🔗 کانال مهدویان:\n"
    "https://rubika.ir/Mahdaviyan_azari\n"
    "@Mahdaviyan_azari"
)

TEHRAN = timezone(timedelta(hours=3, minutes=30))

DESTINATIONS = [
    "@Mahdaviyan_azari",
    "c0BnCQS000e39851ca7e6fc6421d949d",
    os.environ.get("CHAT_ID", "").strip(),
]

CATEGORIES = [
    ("mahdavi", CONTENTS, ""),
    ("hikam", HIKAM, "📖 از نهج‌البلاغه — حکمت:\n"),
    ("hadith", HADITHS, "📿 حدیث:\n"),
    ("khutba", KHUTAB, "📜 از نهج‌البلاغه — خطبه:\n"),
    ("letter", LETTERS, "✉️ از نهج‌البلاغه — نامه:\n"),
]


def with_footer(text):
    body = (text or "").rstrip()
    if "rubika.ir/Mahdaviyan_azari" in body:
        return body
    return body + CHANNEL_FOOTER


def tehran_now():
    return datetime.now(TEHRAN)


def is_active_hours(now):
    """۵:۰۰ تا ۲۳:۰۰ تهران (آخرین اسلات: ۲۲:۳۰)"""
    h, m = now.hour, now.minute
    if h < 5:
        return False
    if h >= 23:
        return False
    return True


def tehran_slot_id(now):
    """شناسه نیم‌ساعت تهران: 2026-09-19-14-0 (=14:00) یا 14-1 (=14:30)"""
    half = 0 if now.minute < 30 else 1
    return f"{now.strftime('%Y-%m-%d')}-{now.hour:02d}-{half}"


def slot_label(slot_id):
    """برای لاگ خوانا"""
    try:
        parts = slot_id.rsplit("-", 2)
        day, hour, half = parts[0], parts[1], parts[2]
        minute = "00" if half == "0" else "30"
        return f"{day} {hour}:{minute} Tehran"
    except Exception:
        return slot_id


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault("last_tehran_slot", None)
    data.setdefault("last_slot", None)  # سازگاری قدیمی
    data.setdefault("sent_count", 0)
    data.setdefault("category_turn", 0)
    data.setdefault("mahdavi_index", 0)
    data.setdefault("hikam_index", 0)
    data.setdefault("hadith_index", 0)
    data.setdefault("khutba_index", 0)
    data.setdefault("letter_index", 0)
    data.setdefault("ayah_number", 1)
    return data


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_sequential_ayah(number):
    try:
        n = ((int(number) - 1) % 6236) + 1
        fa = requests.get(
            f"https://api.alquran.cloud/v1/ayah/{n}/fa.fooladvand",
            timeout=20,
        )
        fa.raise_for_status()
        fa_data = fa.json()["data"]
        ar = requests.get(
            f"https://api.alquran.cloud/v1/ayah/{n}/quran-uthmani",
            timeout=20,
        )
        ar.raise_for_status()
        ar_data = ar.json()["data"]
        surah = fa_data.get("surah", {}).get("name") or ar_data.get("surah", {}).get("name", "")
        num = fa_data.get("numberInSurah") or ar_data.get("numberInSurah")
        return (
            "📖 آیه‌ای از قرآن کریم\n"
            f"{surah} | آیه {num}\n\n"
            f"{ar_data.get('text', '')}\n\n"
            f"{fa_data.get('text', '')}\n\n"
            "اللهم عجل لولیک الفرج"
        )
    except Exception as e:
        print("ayah fetch failed:", e)
        return None


def pick_sequential(state):
    turn = int(state.get("category_turn", 0))

    if turn % 6 == 5:
        n = int(state.get("ayah_number", 1))
        ayah = fetch_sequential_ayah(n)
        if ayah:
            state["ayah_number"] = n + 1
            state["category_turn"] = turn + 1
            return ayah, f"ayah:{n}"

    for offset in range(len(CATEGORIES)):
        cat_idx = (turn + offset) % len(CATEGORIES)
        key, items, prefix = CATEGORIES[cat_idx]
        idx_key = key + "_index"
        current = int(state.get(idx_key, 0))
        if not items:
            continue
        if current < len(items):
            text = prefix + items[current]
            state[idx_key] = current + 1
            state["category_turn"] = turn + 1
            return text, f"{key}:{current}"

    for key, items, prefix in CATEGORIES:
        if not items:
            continue
        idx_key = key + "_index"
        current = int(state.get(idx_key, 0)) % len(items)
        text = prefix + items[current]
        state[idx_key] = current + 1
        state["category_turn"] = turn + 1
        return text, f"{key}:cycle:{current}"

    return (
        "اللهم عجل لولیک الفرج\n\n"
        "یاد امام زمان (عج) را زنده نگه داریم و برای تعجیل فرج دعا کنیم.",
        "fallback",
    )


def send(token, chat_id, text):
    url = f"https://botapi.rubika.ir/v3/{token}/sendMessage"
    resp = requests.post(
        url, json={"chat_id": chat_id, "text": text}, timeout=API_TIMEOUT
    )
    print("Trying", chat_id, "HTTP", resp.status_code, resp.text[:250])
    try:
        data = resp.json()
    except Exception:
        return False
    return data.get("status") == "OK" or bool(
        (data.get("data") or {}).get("message_id")
    )


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

    slot = tehran_slot_id(now)
    print("Current Tehran slot:", slot_label(slot), "id=", slot)

    state = load_state()

    if state.get("last_tehran_slot") == slot:
        print("SKIP: already posted for this half-hour:", slot_label(slot))
        return 0

    text, meta = pick_sequential(state)
    text = with_footer(text)
    print("meta=", meta)
    print("preview:", text[:180])

    ok = False
    tried = []
    for chat_id in DESTINATIONS:
        if not chat_id or chat_id in tried:
            continue
        tried.append(chat_id)
        if send(token, chat_id, text):
            print("Posted using", chat_id, "for slot", slot_label(slot))
            ok = True
            break

    if not ok:
        print("ERROR: could not send")
        return 1

    state["last_tehran_slot"] = slot
    state["last_slot"] = slot  # سازگاری
    state["sent_count"] = int(state.get("sent_count", 0)) + 1
    save_state(state)
    print("State saved. sent_count=", state["sent_count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
