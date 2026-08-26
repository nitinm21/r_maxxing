#!/usr/bin/env python3
"""Retrieval eval: 15 realistic questions -> top-5 chunks each, with and without
query rewrite. Writes data/eval_retrieval.md for gate-2 review."""
import json, os, pathlib, urllib.request
from rewrite import rewrite

ROOT = pathlib.Path(__file__).resolve().parent.parent
PINECONE_HOST = "https://rmaxxing-n9s6x6u.svc.aped-4627-b74a.pinecone.io"

QUESTIONS = [
    "My girlfriend of three years broke up with me and I can't stop thinking about her.",
    "I'm 26 and everyone around me is succeeding while I'm stuck. The shame is unbearable.",
    "I doomscroll every night for hours and feel disgusting afterwards.",
    "I can't make even small decisions without agonizing over them for days.",
    "I get so anxious before talking to people that I rehearse everything.",
    "I've been planning a business for two years but never start. I think I'm a coward.",
    "My parents keep pressuring me about my career and it's making me resent them.",
    "I feel anxious all the time and I don't even know why.",
    "I compare myself to people on Instagram constantly and it's ruining my self-esteem.",
    "I keep relapsing into porn and I hate myself for it.",
    "I have no real friends and I'm lonely most days.",
    "I have no idea what my purpose is. Everything feels pointless.",
    "I'm broke and stressed about money all the time.",
    "I have zero confidence around women.",
    "I lie awake at night replaying every mistake I've ever made.",
]

def post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)

def embed_one(text):
    out = post("https://api.openai.com/v1/embeddings",
               {"model": "text-embedding-3-small", "input": [text]},
               {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
    return out["data"][0]["embedding"]

def query(text, k=5):
    vec = embed_one(text)
    out = post(f"{PINECONE_HOST}/query",
               {"vector": vec, "topK": k, "includeMetadata": True},
               {"Api-Key": os.environ["PINECONE_API_KEY"]})
    return out["matches"]

def fmt(matches):
    lines = []
    for m in matches:
        md = m["metadata"]
        snippet = " ".join(md["text"].split()[:55])
        lines.append(f"- `{m['score']:.3f}` **{md['title'].strip()}** — {snippet}…")
    return "\n".join(lines)

def main():
    out = ["# Retrieval eval — gate 2\n"]
    for i, q in enumerate(QUESTIONS, 1):
        rw = rewrite(q)
        out.append(f"## Q{i}: {q}\n")
        out.append(f"**Rewrite:** {rw}\n")
        out.append("**Top-5 combined (question + concepts):**\n" + fmt(query(f"{q} {rw}")) + "\n")
        out.append("**Top-5 rewrite only:**\n" + fmt(query(rw)) + "\n")
        out.append("**Top-5 raw question:**\n" + fmt(query(q)) + "\n")
        print(f"Q{i} done", flush=True)
    (ROOT / "data/eval_retrieval.md").write_text("\n".join(out))
    print("-> data/eval_retrieval.md")

if __name__ == "__main__":
    main()
