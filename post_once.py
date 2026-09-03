#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import random
import sys

import requests
from contents import CONTENTS


def main() -> int:
    token = os.environ.get("BOT_TOKEN", "").strip()
    chat_id = os.environ.get("CHAT_ID", "").strip()

    if not token or not chat_id:
        print("ERROR: BOT_TOKEN or CHAT_ID secret is missing")
        return 1

    content = random.choice(CONTENTS)
    print("Selected content preview:", content[:120])

    url = f"https://botapi.rubika.ir/v3/{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": content}

    try:
        resp = requests.post(url, json=payload, timeout=25)
        print("Status:", resp.status_code)
        print("Response:", resp.text)
        if resp.status_code >= 400:
            return 1
        data = resp.json() if resp.text else {}
        status = str(data.get("status", "")).upper()
        if status and status not in {"OK", "SUCCESS"}:
            return 1
        return 0
    except Exception as exc:
        print("Request failed:", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
