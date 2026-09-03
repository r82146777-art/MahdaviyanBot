#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بسته صبحگاهی کانال مهدویان (حدود ۸ صبح تهران):
۱) تقویم روز
۲) سه حکمت از نهج‌البلاغه
۳) یک خطبه + یک نامه (گزیده)
۴) یک صفحه قرآن (عربی + ترجمه)
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from nahj_content import HIKAM, KHUTAB, LETTERS

API_TIMEOUT = 30
STATE_FILE = Path("state.json")
DESTINATIONS = [
    "@Mahdaviyan_azari",
    "c0BnCQS000e39851ca7e6fc6421d949d",
    os.environ.get("CHAT_ID", "").strip(),
]

TEHRAN = timezone(timedelta(hours=3, minutes=30))
API_BASE = "https://api.alquran.cloud/v1"
ARABIC_EDITION = "quran-uthmani"
PERSIAN_EDITION = "fa.fooladvand"

WEEKDAYS_FA = [
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنج‌شنبه",
    "جمعه",
    "شنبه",
    "یکشنبه",
]


def tehran_now():
    return datetime.now(TEHRAN)


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "content_index": 0,
        "hikam_index": 0,
        "khutba_index": 0,
        "letter_index": 0,
        "quran_page": 1,
        "last_morning_date": None,
        "last_posts": [],
    }


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def send(token, chat_id, text):
    url = "https://botapi.rubika.ir/v3/{}/sendMessage".format(token)
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=API_TIMEOUT)
    print("HTTP", resp.status_code, resp.text[:250])
    try:
        data = resp.json()
    except Exception:
        return False
    return data.get("status") == "OK" or bool((data.get("data") or {}).get("message_id"))


def send_any(token, text):
    for chat_id in DESTINATIONS:
        if not chat_id:
            continue
        if send(token, chat_id, text):
            print("Posted to", chat_id)
            return True
    return False


def calendar_text(now):
    wd = WEEKDAYS_FA[now.weekday()]
    return (
        "📅 تقویم امروز\n"
        f"روز: {wd}\n"
        f"تاریخ میلادی: {now.strftime('%Y-%m-%d')}\n"
        f"ساعت تهران: {now.strftime('%H:%M')}\n\n"
        "اللهم عجل لولیک الفرج\n"
        "صبح شما با یاد امام زمان (عج) پُربرکت."
    )


def take_items(lst, start, count):
    n = len(lst)
    out = []
    idx = start % n
    for _ in range(count):
        out.append(lst[idx])
        idx = (idx + 1) % n
    return out, idx


def quran_page_text(page):
    ar = requests.get(f"{API_BASE}/page/{page}/{ARABIC_EDITION}", timeout=30)
    ar.raise_for_status()
    fa = requests.get(f"{API_BASE}/page/{page}/{PERSIAN_EDITION}", timeout=30)
    fa.raise_for_status()
    arabic = ar.json()["data"]["ayahs"]
    persian = fa.json()["data"]["ayahs"]

    lines = [f"📖 صفحه {page} قرآن کریم\nمتن عربی + ترجمه فولادوند\n" + "─" * 16]
    for a, p in list(zip(arabic, persian))[:12]:
        lines.append(
            f"{a['surah']['name']} | آیه {a['numberInSurah']}\n"
            f"{a['text']}\n"
            f"{p['text']}\n"
        )
    if len(arabic) > 12:
        lines.append("... (ادامه آیات این صفحه)")
    text = "\n".join(lines)
    if len(text) > 3500:
        text = text[:3400] + "\n..."
    return text


def main():
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: BOT_TOKEN missing")
        return 1

    now = tehran_now()
    today = now.date().isoformat()
    state = load_state()

    if state.get("last_morning_date") == today:
        print("Morning package already sent today.")
        return 0

    # 1) تقویم
    if not send_any(token, calendar_text(now)):
        return 1
    time.sleep(1.2)

    # 2) سه حکمت
    hikam, hi = take_items(HIKAM, int(state.get("hikam_index", 0)), 3)
    msg = "📖 سه حکمت از نهج‌البلاغه\n\n" + "\n\n".join(hikam)
    if not send_any(token, msg):
        return 1
    state["hikam_index"] = hi
    time.sleep(1.2)

    # 3) خطبه + نامه
    kh, ki = take_items(KHUTAB, int(state.get("khutba_index", 0)), 1)
    lt, li = take_items(LETTERS, int(state.get("letter_index", 0)), 1)
    msg2 = "📜 خطبه و نامه از نهج‌البلاغه\n\n" + kh[0] + "\n\n" + lt[0]
    if not send_any(token, msg2):
        return 1
    state["khutba_index"] = ki
    state["letter_index"] = li
    time.sleep(1.2)

    # 4) صفحه قرآن
    page = int(state.get("quran_page", 1))
    if page < 1 or page > 604:
        page = 1
    try:
        qtext = quran_page_text(page)
        if not send_any(token, qtext):
            return 1
        state["quran_page"] = page + 1 if page < 604 else 1
    except Exception as e:
        print("Quran page error:", e)
        send_any(token, f"📖 امروز صفحه {page} قرآن\n(موقتاً دریافت متن کامل ممکن نشد)")

    state["last_morning_date"] = today
    save_state(state)
    print("Morning package done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
