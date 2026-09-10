#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بسته صبحگاهی کانال مهدویان (حدود ۵ صبح تهران)
۱. تقویم روز + ذکر اعمال دینی + مناسبت
۲. متن مهدوی
۳. یک صفحه از قرآن کریم
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from contents import CONTENTS
from nahj_content import HIKAM  # فقط برای تنوع احتمالی

API_TIMEOUT = 30
STATE_FILE = Path("state.json")
CHANNEL_FOOTER = "\n\n━━━━━━━━━━━━━━\n🔗 کانال مهدویان:\nhttps://rubika.ir/Mahdaviyan_azari\n@Mahdaviyan_azari"

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
    "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه",
]

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# مناسبت‌های تقریبی ثابت شمسی (نمونه برای یک سال)
OCCASIONS = {
    (1, 1): "نوروز — آغاز سال نو شمسی. روز نو شدن طبیعت و دل‌ها.",
    (1, 12): "روز جمهوری اسلامی",
    (1, 13): "روز طبیعت (سیزده‌به‌در)",
    (3, 14): "رحلت امام خمینی (ره)",
    (3, 15): "قیام ۱۵ خرداد",
    (6, 31): "آغاز هفته دفاع مقدس",
    (9, 9): "روز عرفه (تقریبی — بسته به قمری)",
    (11, 22): "پیروزی انقلاب اسلامی",
    (12, 29): "روز ملی شدن صنعت نفت",
}

# اعمال پیشنهادی بر اساس روز هفته
DAILY_ACTS = {
    0: "امروز دوشنبه است.\n• خواندن دعای عهد\n• صدقه دادن\n• زیارت مجازی امام زمان (عج)",
    1: "امروز سه‌شنبه است.\n• تلاوت قرآن (حداقل یک صفحه)\n• صلوات بسیار\n• یاد امام زمان در دل",
    2: "امروز چهارشنبه است.\n• دعای فرج\n• کمک به نیازمندان\n• مطالعه درباره ظهور",
    3: "امروز پنج‌شنبه است.\n• زیارت اهل قبور (اگر ممکن)\n• دعای کمیل\n• آمادگی برای جمعه",
    4: "امروز جمعه است — عید هفته.\n• دعای ندبه\n• غسل جمعه\n• زیارت امام زمان (عج)\n• دعای فرج ویژه",
    5: "امروز شنبه است.\n• شروع هفته با یاد حضرت\n• برنامه‌ریزی اعمال صالح\n• صله رحم",
    6: "امروز یکشنبه است.\n• تجدید عهد با امام زمان\n• خواندن زیارت آل یاسین\n• خودسازی",
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
        "content_index": 0,
        "hikam_index": 0,
        "khutba_index": 0,
        "letter_index": 0,
        "quran_page": 1,
        "last_morning_date": None,
        "last_posts": [],
        "mahdavi_morning_index": 0,
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
    text = with_footer(text)
    for chat_id in DESTINATIONS:
        if not chat_id:
            continue
        if send(token, chat_id, text):
            print("Posted to", chat_id)
            return True
    return False


def gregorian_to_jalali(gy, gm, gd):
    """تبدیل میلادی به شمسی (الگوریتم استاندارد بدون وابستگی)"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        gy -= 1600
        jy = 979
    else:
        gy -= 621
        jy = 0
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + (gy2 // 4) - (gy2 // 100) + (gy2 // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def calendar_text(now):
    wd = WEEKDAYS_FA[now.weekday()]
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    month_name = JALALI_MONTHS[jm - 1] if 1 <= jm <= 12 else str(jm)

    occasion = OCCASIONS.get((jm, jd), "")
    if not occasion:
        # مناسبت‌های کلی
        if now.weekday() == 4:
            occasion = "جمعه — روز ویژه دعا و انتظار فرج"
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
    ar = requests.get(f"{API_BASE}/page/{page}/{ARABIC_EDITION}", timeout=30)
    ar.raise_for_status()
    fa = requests.get(f"{API_BASE}/page/{page}/{PERSIAN_EDITION}", timeout=30)
    fa.raise_for_status()
    arabic = ar.json()["data"]["ayahs"]
    persian = fa.json()["data"]["ayahs"]

    lines = [f"📖 صفحه {page} قرآن کریم\nمتن عربی + ترجمه فولادوند\n" + "─" * 16]
    for a, p in list(zip(arabic, persian))[:10]:
        lines.append(
            f"{a['surah']['name']} | آیه {a['numberInSurah']}\n"
            f"{a['text']}\n"
            f"{p['text']}\n"
        )
    if len(arabic) > 10:
        lines.append("... (ادامه آیات این صفحه در قرآن)")
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

    # ۱. تقویم + اعمال + مناسبت
    if not send_any(token, calendar_text(now)):
        return 1
    time.sleep(1.5)

    # ۲. متن مهدوی
    idx = int(state.get("mahdavi_morning_index", 0)) % len(CONTENTS)
    mahdavi = CONTENTS[idx]
    if not send_any(token, "🌟 متن مهدوی صبحگاهی\n\n" + mahdavi):
        return 1
    state["mahdavi_morning_index"] = (idx + 1) % len(CONTENTS)
    time.sleep(1.5)

    # ۳. صفحه قرآن
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
        send_any(token, f"📖 امروز صفحه {page} قرآن کریم\n(موقتاً دریافت متن کامل ممکن نشد)\nاللهم عجل لولیک الفرج")

    state["last_morning_date"] = today
    save_state(state)
    print("Morning package done (calendar + mahdavi + quran).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
