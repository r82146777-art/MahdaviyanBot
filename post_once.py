#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ارسال یک پست چرخشی به کانال مهدویان.
محتوا ترتیبی است (تکرار کم) و state بعد از هر ارسال ذخیره می‌شود.
"""
import json
import os
import sys
from pathlib import Path

import requests
from contents import CONTENTS
from nahj_content import HIKAM, KHUTAB, LETTERS

API_TIMEOUT = 25
STATE_FILE = Path("state.json")
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


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"content_index": 0, "last_posts": []}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def next_content(state):
    idx = int(state.get("content_index", 0)) % len(POOL)
    text = POOL[idx]
    state["content_index"] = (idx + 1) % len(POOL)
    recent = state.get("last_posts") or []
    recent.append(idx)
    state["last_posts"] = recent[-50:]
    return text


def send(token, chat_id, text):
    url = "https://botapi.rubika.ir/v3/{}/sendMessage".format(token)
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=API_TIMEOUT)
    print("Trying", chat_id, "HTTP", resp.status_code, resp.text[:300])
    try:
        data = resp.json()
    except Exception:
        return False
    if data.get("status") == "OK" or (data.get("data") or {}).get("message_id"):
        print("SEND SUCCESS")
        return True
    return False


def main():
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: BOT_TOKEN is missing")
        return 1

    state = load_state()
    content = next_content(state)
    print("Selected content preview:", content[:120])

    tried = []
    ok = False
    for chat_id in DESTINATIONS:
        if not chat_id or chat_id in tried:
            continue
        tried.append(chat_id)
        if send(token, chat_id, content):
            print("Posted using", chat_id)
            ok = True
            break

    if not ok:
        print("ERROR: could not send")
        return 1

    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
