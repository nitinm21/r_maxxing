#!/usr/bin/env python3
"""Diagnose why answers feel AI-generated: prompt vs retrieval vs model.
Conditions A-D on Terra (E=Kimi runs separately via browser). -> data/eval_style.md"""
import json, os, pathlib, time, urllib.request
from rewrite import rewrite

ROOT = pathlib.Path(__file__).resolve().parent.parent
PINECONE_HOST = "https://rmaxxing-n9s6x6u.svc.aped-4627-b74a.pinecone.io"
RULES_PROMPT = (ROOT / "lib/persona_prompt.txt").read_text()

QUESTIONS = [
    "My girlfriend of three years broke up with me and I can't stop thinking about her.",
    "I doomscroll every night for hours and feel disgusting afterwards.",
    "I feel anxious all the time and I don't even know why.",
]

SAFETY = """SAFETY OVERRIDE (beats everything below): if the message indicates suicidal thoughts, self-harm, abuse, or a psychiatric crisis, drop the persona entirely and respond plainly: you are an AI imitation of a YouTuber, urge real help now (US: call/text 988; elsewhere findahelpline.com). Never give medical, medication, legal, or financial advice in character."""

def exemplars():
    out = []
    for vid, lo, hi in [("-IJ71tbhOLY", 60, 800), ("1V11itjbyVE", 150, 900)]:
        r = json.loads((ROOT / f"data/transcripts/{vid}.json").read_text())
        words = r["text"].split()
        out.append(f"[From your video \"{r['title'].strip()}\"]\n" + " ".join(words[lo:hi]))
    return "\n\n".join(out)

MIMIC_PROMPT = f"""You ARE Elisha Long, the retardmaxxing YouTuber. Below are VERBATIM transcripts from your own videos. That is exactly how you talk: the rhythm, the tangents, the sudden personal stories, the crude jokes, the half-finished sentences, the way you circle a point three times and then land it hard.

{SAFETY}

A viewer wrote to you about their problem. Answer the way you would actually riff on it in a video — same voice, same messiness, same conviction. Do NOT structure it like an essay or a tidy pep talk. Don't recite your catchphrases like a checklist; only what flows naturally. Let one concrete image or story carry the answer. Talk TO them. 200-350 words, plain prose.

HOW YOU TALK (verbatim from your videos):

{exemplars()}"""

def post(url, body, headers, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def retrieve(q):
    rw = rewrite(q)
    emb = post("https://api.openai.com/v1/embeddings",
               {"model": "text-embedding-3-small", "input": [f"{q} {rw}"]},
               {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})["data"][0]["embedding"]
    return post(f"{PINECONE_HOST}/query",
                {"vector": emb, "topK": 6, "includeMetadata": True},
                {"Api-Key": os.environ["PINECONE_API_KEY"]})["matches"]

def gen(system, q, temp):
    body = {"model": "gpt-5.6-terra", "reasoning_effort": "none", "temperature": temp,
            "max_completion_tokens": 700,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": q}]}
    out = post("https://api.openai.com/v1/chat/completions", body,
               {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
    return out["choices"][0]["message"]["content"]

def ctx(matches):
    return "\n\n---\n\n".join(
        f"From \"{m['metadata']['title'].strip()}\":\n{m['metadata']['text']}" for m in matches)

def main():
    out = ["# Style diagnosis — A: baseline rules+chunks · B: rules only · "
           "C: rules+exemplars+chunks · D: mimic+exemplars+chunks\n"]
    for i, q in enumerate(QUESTIONS, 1):
        matches = retrieve(q)
        topical = ctx(matches)
        conds = {
            "A rules + topical chunks (current)": (f"{RULES_PROMPT}\n\nCONTEXT:\n{topical}", 0.8),
            "B rules only, no context": (RULES_PROMPT, 0.8),
            "C rules + exemplars + chunks": (
                f"{RULES_PROMPT}\n\nHOW YOU TALK (verbatim):\n{exemplars()}\n\nCONTEXT:\n{topical}", 0.8),
            "D mimic prompt + exemplars + chunks": (
                f"{MIMIC_PROMPT}\n\nIDEAS RELEVANT TO THIS VIEWER (from your videos):\n{topical}", 1.0),
        }
        out.append(f"\n# Q{i}: {q}\n")
        for name, (system, temp) in conds.items():
            t0 = time.time()
            text = gen(system, q, temp)
            out.append(f"## {name}\n\n{text}\n")
            print(f"Q{i} {name[:1]} done ({time.time()-t0:.1f}s)", flush=True)
    (ROOT / "data/eval_style.md").write_text("\n".join(out))
    print("-> data/eval_style.md")

if __name__ == "__main__":
    main()
