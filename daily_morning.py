#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بسته صبحگاهی (حدود ۵ صبح تهران):
۱. تقویم دقیق شمسی + اعمال + مناسبت
۲. متن مهدوی (بدون پیشوند)
۳. یک صفحه ترتیبی از قرآن کریم
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jdatetime
import requests
from contents import CONTENTS

API_TIMEOUT = 30
STATE_FILE = Path("state.json")
CHANNEL_FOOTER = (
    "\n\n━━━━━━━━━━━━━━\n"
    "🔗 کانال مهدویان:\n"
    "https://rubika.ir/Mahdaviyan_azari\n"
    "@Mahdaviyan_azari"
)

DESTINATIONS = [
    "@Mahdaviyan_azari",
    "c0BnCQS000e39851ca7e6fc6421d949d",
    os.environ.get("CHAT_ID", "").strip(),
]

TEHRAN = timezone(timedelta(hours=3, minutes=30))
API_BASE = "https://api.alquran.cloud/v1"

WEEKDAYS_FA = [
    "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه",
]

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

OCCASIONS = {
    (1, 1): "نوروز — آغاز سال نو شمسی. روز نو شدن طبیعت و دل‌ها.",
    (1, 12): "روز جمهوری اسلامی",
    (1, 13): "روز طبیعت (سیزده‌به‌در)",
    (3, 14): "رحلت امام خمینی (ره)",
    (3, 15): "قیام ۱۵ خرداد",
    (6, 31): "آغاز هفته دفاع مقدس",
    (11, 22): "پیروزی انقلاب اسلامی",
    (12, 29): "روز ملی شدن صنعت نفت",
}

DAILY_ACTS = {
    0: "امروز دوشنبه است.\n• خواندن دعای عهد\n• صدقه دادن\n• زیارت مجازی امام زمان (عج)\n• یاد حضرت در دل",
    1: "امروز سه‌شنبه است.\n• تلاوت قرآن (حداقل یک صفحه)\n• صلوات بسیار\n• یاد امام زمان در دل\n• کمک به نیازمندان",
    2: "امروز چهارشنبه است.\n• دعای فرج\n• کمک به نیازمندان\n• مطالعه درباره ظهور\n• ترک یک گناه",
    3: "امروز پنج‌شنبه است.\n• زیارت اهل قبور (اگر ممکن)\n• دعای کمیل\n• آمادگی برای جمعه\n• صدقه",
    4: "امروز جمعه است — عید هفته.\n• دعای ندبه\n• غسل جمعه\n• زیارت امام زمان (عج)\n• دعای فرج ویژه\n• صله رحم",
    5: "امروز شنبه است.\n• شروع هفته با یاد حضرت\n• برنامه‌ریزی اعمال صالح\n• صله رحم\n• دعای عهد",
    6: "امروز یکشنبه است.\n• تجدید عهد با امام زمان\n• خواندن زیارت آل یاسین\n• خودسازی\n• صدقه",
}


def tehran_now():
    return datetime.now(TEHRAN)


def with_footer(text):
    body = (text or "").rstrip()
    if "rubika.ir/Mahdaviyan_azari" in body:
        return body
    return body + CHANNEL_FOOTER


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "quran_page": 1,
        "last_morning_date": None,
        "mahdavi_morning_index": 0,
    }


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def send(token, chat_id, text):
    url = f"https://botapi.rubika.ir/v3/{token}/sendMessage"
    resp = requests.post(
        url, json={"chat_id": chat_id, "text": text}, timeout=API_TIMEOUT
    )
    print("HTTP", resp.status_code, resp.text[:250])
    try:
        data = resp.json()
    except Exception:
        return False
    return data.get("status") == "OK" or bool(
        (data.get("data") or {}).get("message_id")
    )


def send_any(token, text):
    text = with_footer(text)
    for chat_id in DESTINATIONS:
        if not chat_id:
            continue
        if send(token, chat_id, text):
            print("Posted to", chat_id)
            return True
    return False


def calendar_text(now):
    j = jdatetime.datetime.fromgregorian(datetime=now.replace(tzinfo=None))
    wd = WEEKDAYS_FA[now.weekday()]
    month_name = JALALI_MONTHS[j.month - 1]
    jy, jm, jd = j.year, j.month, j.day

    occasion = OCCASIONS.get((jm, jd), "")
    if not occasion:
        if now.weekday() == 4:
            occasion = "جمعه — روز ویژه دعا و انتظار فرج حضرت مهدی (عج)"
        else:
            occasion = "روزی دیگر در مسیر انتظار حضرت مهدی (عج)"

    acts = DAILY_ACTS.get(now.weekday(), "یاد امام زمان (عج) را زنده نگه دارید.")

    return (
        "📅 تقویم امروز\n"
        f"روز هفته: {wd}\n"
        f"تاریخ شمسی: {jd} {month_name} {jy}\n"
        f"تاریخ میلادی: {now.strftime('%Y-%m-%d')}\n"
        f"ساعت تهران: {now.strftime('%H:%M')}\n\n"
        f"✨ مناسبت:\n{occasion}\n\n"
        f"🙏 ذکر اعمال دینی پیشنهادی:\n{acts}\n\n"
        "اللهم عجل لولیک الفرج\n"
        "صبح شما با یاد امام زمان (عج) پُربرکت باشد."
    )


def quran_page_text(page):
    page = max(1, min(604, int(page)))
    ar = requests.get(f"{API_BASE}/page/{page}/quran-uthmani", timeout=30)
    ar.raise_for_status()
    fa = requests.get(f"{API_BASE}/page/{page}/fa.fooladvand", timeout=30)
    fa.raise_for_status()
    arabic = ar.json()["data"]["ayahs"]
    persian = fa.json()["data"]["ayahs"]

    lines = [
        f"📖 صفحه {page} از ۶۰۴ — قرآن کریم\n"
        "متن عربی + ترجمه فولادوند\n"
        + "─" * 16
    ]
    for a, p in list(zip(arabic, persian))[:12]:
        lines.append(
            f"{a['surah']['name']} | آیه {a['numberInSurah']}\n"
            f"{a['text']}\n"
            f"{p['text']}\n"
        )
    if len(arabic) > 12:
        lines.append("... (ادامه آیات این صفحه در قرآن کریم)")
    text = "\n".join(lines)
    if len(text) > 3800:
        text = text[:3700] + "\n..."
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

    if not send_any(token, calendar_text(now)):
        return 1
    time.sleep(1.5)

    idx = int(state.get("mahdavi_morning_index", 0))
    if CONTENTS:
        mahdavi = CONTENTS[idx % len(CONTENTS)]
        if not send_any(token, mahdavi):
            return 1
        state["mahdavi_morning_index"] = idx + 1
    time.sleep(1.5)

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
        send_any(
            token,
            f"📖 امروز صفحه {page} قرآن کریم\n"
            "(موقتاً دریافت متن کامل ممکن نشد — فردا ادامه می‌دهیم)\n"
            "اللهم عجل لولیک الفرج",
        )

    state["last_morning_date"] = today
    save_state(state)
    print("Morning package done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
