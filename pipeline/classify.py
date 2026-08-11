#!/usr/bin/env python3
"""Classify all channel videos as in-scope (retardmaxxing/self-help) or out-of-scope
using GPT-5.6 Luna over titles. Writes data/videos.json."""
import json, os, pathlib, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

def load_env():
    env = ROOT / ".env"
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

load_env()

PROMPT = """You are filtering a YouTube channel's videos for a knowledge base about the creator's life-advice philosophy ("retardmaxxing": stop overthinking, act boldly, quit brain rot, get ahead in life, deal with anxiety/women/jobs/purpose).

INCLUDE: videos about overthinking, anxiety, self-improvement mindset, life advice, women/relationships advice, jobs/purpose, brain rot / social media, spirituality-as-life-advice, retardmaxxing philosophy.
EXCLUDE: pure fitness/muscle-building/diet content, vlogs/meetups/shorts under 5 minutes, gear or channel-logistics videos.

For each numbered video title below, answer with a JSON array of the numbers to INCLUDE. Respond with ONLY the JSON array.

{titles}"""

def call_luna(titles_block):
    body = {
        "model": "gpt-5.6-luna",
        "reasoning_effort": "none",
        "messages": [{"role": "user", "content": PROMPT.format(titles=titles_block)}],
        "max_completion_tokens": 2000,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.load(r)
    text = out["choices"][0]["message"]["content"].strip()
    start, end = text.find("["), text.rfind("]")
    return json.loads(text[start:end + 1])

def main(listing_path):
    rows = []
    for line in open(listing_path):
        parts = line.strip().split("|", 2)
        if len(parts) == 3 and parts[1] not in ("NA", ""):
            rows.append({"id": parts[0], "duration": float(parts[1]), "title": parts[2].strip()})
    print(f"{len(rows)} videos to classify")

    keep = []
    B = 60
    for off in range(0, len(rows), B):
        batch = rows[off:off + B]
        block = "\n".join(f"{i+1}. {v['title']}  [{int(v['duration']//60)}min]" for i, v in enumerate(batch))
        nums = call_luna(block)
        for n in nums:
            if 1 <= n <= len(batch):
                keep.append(batch[n - 1])
        print(f"batch {off//B + 1}/{(len(rows)+B-1)//B}: kept {len(nums)} (total {len(keep)})")

    hours = sum(v["duration"] for v in keep) / 3600
    (DATA / "videos.json").write_text(json.dumps(keep, indent=2))
    print(f"DONE: {len(keep)} videos, {hours:.1f} hours -> data/videos.json")

if __name__ == "__main__":
    main(sys.argv[1])
