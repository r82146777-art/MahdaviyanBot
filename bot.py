#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ربات مهدویان - ارسال محتوای مذهبی هر ۳۰ دقیقه به کانال روبیکا
"""

import os
import time
import random
import requests
from dotenv import load_dotenv
from contents import CONTENTS

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # مثلاً c0xxxxxxxx یا @Mahdaviyan_azari

API_BASE = f"https://botapi.rubika.ir/v3/{BOT_TOKEN}"

def send_message(chat_id: str, text: str) -> dict:
    """ارسال پیام متنی به چت"""
    url = f"{API_BASE}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        return resp.json()
    except Exception as e:
        print(f"خطا در ارسال پیام: {e}")
        return {"status": "ERROR", "error": str(e)}

def get_random_content() -> str:
    """یک محتوای تصادفی از لیست برمی‌گرداند"""
    return random.choice(CONTENTS)

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ خطا: BOT_TOKEN یا CHAT_ID تنظیم نشده است.")
        print("لطفاً فایل .env را بسازید یا متغیرهای محیطی را ست کنید.")
        return

    print("✅ ربات مهدویان شروع به کار کرد...")
    print(f"کانال هدف: {CHAT_ID}")
    print("هر ۳۰ دقیقه یک محتوا ارسال می‌شود.\n")

    while True:
        content = get_random_content()
        print(f"📤 در حال ارسال محتوا...\n{content[:80]}...")
        
        result = send_message(CHAT_ID, content)
        
        if result.get("status") == "OK" or "message_id" in str(result):
            print("✅ پیام با موفقیت ارسال شد.\n")
        else:
            print(f"⚠️ پاسخ سرور: {result}\n")
        
        # ۳۰ دقیقه صبر (۱۸۰۰ ثانیه)
        print("⏳ منتظر ۳۰ دقیقه بعدی...")
        time.sleep(1800)

if __name__ == "__main__":
    main()
