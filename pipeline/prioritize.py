#!/usr/bin/env python3
"""Score classified videos 0-10 for closeness to core retardmaxxing themes (Luna),
sort descending, write data/videos_ranked.json."""
import json, os, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

PROMPT = """Score each numbered YouTube video title 0-10 for how central it is to this creator's core philosophy content: retardmaxxing, overthinking, rumination, anxiety, quitting brain rot, bold action, getting ahead in life, purpose, dealing with women/jobs through that lens.

10 = core philosophy monologue. 5 = adjacent life advice. 0 = tangential (news reactions, meetups, shorts, misc).
Longer monologues (20min+) about core themes deserve higher scores than 1-5min clips.

Respond ONLY with a JSON object mapping number -> score, e.g. {{"1": 9, "2": 3}}.

{titles}"""

def call(block):
    body = {
        "model": "gpt-5.6-luna",
        "reasoning_effort": "none",
        "messages": [{"role": "user", "content": PROMPT.format(titles=block)}],
        "max_completion_tokens": 3000,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.load(r)
    text = out["choices"][0]["message"]["content"]
    return json.loads(text[text.find("{"):text.rfind("}") + 1])

videos = json.loads((DATA / "videos.json").read_text())
B = 60
for off in range(0, len(videos), B):
    batch = videos[off:off + B]
    block = "\n".join(f"{i+1}. {v['title']}  [{int(v['duration']//60)}min]" for i, v in enumerate(batch))
    scores = call(block)
    for i, v in enumerate(batch):
        v["score"] = scores.get(str(i + 1), 0)
    print(f"scored {off + len(batch)}/{len(videos)}")

videos.sort(key=lambda v: (-v["score"], -v["duration"]))
(DATA / "videos_ranked.json").write_text(json.dumps(videos, indent=2))
cum = 0
for i, v in enumerate(videos):
    cum += v["duration"]
    if cum / 3600 >= 72:
        print(f"72h cutoff at rank {i+1} (score {v['score']})")
        break
print(f"DONE -> data/videos_ranked.json ({len(videos)} videos)")
