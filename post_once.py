#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import random
import sys

import requests
from contents import CONTENTS

API_TIMEOUT = 25
CANDIDATES = [
    os.environ.get("CHAT_ID", "").strip(),
    "c0BnCQS01d1819995026bf3758b9b067",
    "@Mahdaviyan_azari",
    "Mahdaviyan_azari",
]


def api(token, method, payload=None):
    url = "https://botapi.rubika.ir/v3/{}/{}".format(token, method)
    resp = requests.post(url, json=payload or {}, timeout=API_TIMEOUT)
    print("{} HTTP {}".format(method, resp.status_code))
    print("{} body: {}".format(method, resp.text[:1500]))
    try:
        return {"http": resp.status_code, "json": resp.json(), "raw": resp.text}
    except Exception:
        return {"http": resp.status_code, "json": {}, "raw": resp.text}


def extract_chat_ids(obj, found):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ("chat_id", "object_guid", "channel_guid") and isinstance(value, str):
                found.add(value)
            else:
                extract_chat_ids(value, found)
    elif isinstance(obj, list):
        for item in obj:
            extract_chat_ids(item, found)


def send(token, chat_id, text):
    print("Trying chat_id={}".format(chat_id))
    result = api(token, "sendMessage", {"chat_id": chat_id, "text": text})
    data = result.get("json") or {}
    status = str(data.get("status", "")).upper()
    if result["http"] == 200 and status in ("OK", "SUCCESS"):
        print("SEND SUCCESS")
        return True
    nested = data.get("data") or {}
    if result["http"] == 200 and nested.get("message_id"):
        print("SEND SUCCESS")
        return True
    return False


def main():
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: BOT_TOKEN is missing")
        return 1

    print("--- getMe ---")
    api(token, "getMe")

    print("--- getUpdates ---")
    updates = api(token, "getUpdates", {"limit": 20})
    found = set()
    extract_chat_ids(updates.get("json"), found)
    print("chat_ids found in updates:", sorted(found))

    content = random.choice(CONTENTS)
    print("Selected content preview:", content[:120])

    tried = []
    for chat_id in CANDIDATES + sorted(found):
        if not chat_id or chat_id in tried:
            continue
        tried.append(chat_id)
        if send(token, chat_id, content):
            print("Posted using", chat_id)
            return 0

    print("ERROR: could not send with any known chat_id")
    return 1


if __name__ == "__main__":
    sys.exit(main())
