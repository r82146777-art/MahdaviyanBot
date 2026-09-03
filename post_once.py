#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import random
import sys

import requests
from contents import CONTENTS

API_TIMEOUT = 25
# Username works with Rubika Bot API; numeric secret may be a GUID and fail.
DESTINATIONS = [
    "@Mahdaviyan_azari",
    "c0BnCQS000e39851ca7e6fc6421d949d",
    os.environ.get("CHAT_ID", "").strip(),
]


def send(token, chat_id, text):
    url = "https://botapi.rubika.ir/v3/{}/sendMessage".format(token)
    resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=API_TIMEOUT)
    print("Trying", chat_id, "HTTP", resp.status_code, resp.text[:400])
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

    content = random.choice(CONTENTS)
    print("Selected content preview:", content[:120])

    tried = []
    for chat_id in DESTINATIONS:
        if not chat_id or chat_id in tried:
            continue
        tried.append(chat_id)
        if send(token, chat_id, content):
            print("Posted using", chat_id)
            return 0

    print("ERROR: could not send")
    return 1


if __name__ == "__main__":
    sys.exit(main())
