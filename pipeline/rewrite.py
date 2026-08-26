#!/usr/bin/env python3
"""Query rewrite: map an emotional personal-problem statement to the creator's
concept vocabulary (Luna, reasoning none). Used before embedding the query."""
import json, os, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

PROMPT = """A user of a self-help chat app described a personal problem. Rewrite it as a short
comma-separated list of the concepts and phrases a "retardmaxxing" life-advice YouTuber
uses when talking about this problem. His vocabulary: overthinking, rumination,
intrusive thoughts, thoughts are clouds, brain rot, doomscrolling, noise, reclaiming
your center, thumos, righteous living, bold action, being the bread, letting go, women,
purpose, jobs, quitting, fear disguised as preparation, comparison, shame, anxiety.

RULES: Start with the concrete topic domain of the problem (e.g. breakup, women,
girlfriend, job, boss, money, porn, friends, family, purpose, decisions) — keep the
user's specific nouns. THEN add 4-6 of his concepts that fit THIS problem. Do not
use the same generic concepts for every problem.
Output ONLY the comma-separated list (8-15 words total), nothing else.

User's problem: {q}"""

def rewrite(q):
    body = {
        "model": "gpt-5.6-luna",
        "reasoning_effort": "none",
        "max_completion_tokens": 60,
        "messages": [{"role": "user", "content": PROMPT.format(q=q)}],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["choices"][0]["message"]["content"].strip()

if __name__ == "__main__":
    import sys
    print(rewrite(sys.argv[1]))
