#!/usr/bin/env python3
"""Chunk transcripts (~600 words, 100 overlap), embed with text-embedding-3-small,
upsert to Pinecone index 'rmaxxing'. Resumable via data/embedded_ids.json."""
import json, os, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PINECONE_HOST = "https://rmaxxing-n9s6x6u.svc.aped-4627-b74a.pinecone.io"

for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

def post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)

def embed(texts):
    out = post("https://api.openai.com/v1/embeddings",
               {"model": "text-embedding-3-small", "input": texts},
               {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
    return [d["embedding"] for d in out["data"]]

def chunks_of(r, size=600, overlap=100):
    words = r["text"].split()
    if len(words) < 100:
        return
    step = size - overlap
    for n, start in enumerate(range(0, len(words), step)):
        seg = words[start:start + size]
        if len(seg) < 50 and n > 0:
            break
        yield n, f"{r['title']} — {' '.join(seg)}"

def main():
    state_path = DATA / "embedded_ids.json"
    done = set(json.loads(state_path.read_text())) if state_path.exists() else set()
    files = sorted(DATA.glob("transcripts/*.json"))
    total = 0
    for f in files:
        r = json.loads(f.read_text())
        if r["id"] in done:
            continue
        batch = []
        for n, text in chunks_of(r):
            batch.append((f"{r['id']}#{n}", text, n))
        for off in range(0, len(batch), 100):
            part = batch[off:off + 100]
            vecs = embed([t for _, t, _ in part])
            post(f"{PINECONE_HOST}/vectors/upsert", {
                "vectors": [{
                    "id": cid, "values": vec,
                    "metadata": {"videoId": r["id"], "title": r["title"],
                                 "url": r["url"], "score": r.get("score") or 0,
                                 "n": n, "text": text},
                } for (cid, text, n), vec in zip(part, vecs)],
            }, {"Api-Key": os.environ["PINECONE_API_KEY"]})
        done.add(r["id"])
        total += len(batch)
        state_path.write_text(json.dumps(sorted(done)))
        print(f"{r['id']} +{len(batch)} chunks ({len(done)}/{len(files)} videos)", flush=True)
    print(f"DONE: {total} chunks upserted this run", flush=True)

if __name__ == "__main__":
    main()
