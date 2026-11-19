#!/usr/bin/env python3
"""OpenAI Python SDK drop-in call against Bifrost's /openai/v1 endpoint."""

import os
import sys

from openai import OpenAI


def main() -> int:
    base = os.environ.get("BIFROST_BASE", "http://127.0.0.1:8088/openai/v1")
    key = os.environ.get("VK_NETOPS") or os.environ.get("OPENAI_API_KEY")
    if not key:
        print("VK_NETOPS is not set", file=sys.stderr)
        return 2
    client = OpenAI(base_url=base, api_key=key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a concise network engineer assistant. One short paragraph.",
            },
            {
                "role": "user",
                "content": "In one sentence, what does a BGP NOTIFICATION with Cease / Administrative Shutdown usually mean?",
            },
        ],
        max_tokens=80,
        temperature=0,
    )
    choice = resp.choices[0].message.content
    print("model:", resp.model)
    print("id:", resp.id)
    print("usage:", resp.usage)
    print("content:", choice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
