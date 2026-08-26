#!/usr/bin/env python3
"""Transcribe ranked videos with OpenAI gpt-4o-mini-transcribe, in priority order,
up to MAX_HOURS (default 72). Resumable: skips videos already in data/transcripts/.

Per video: yt-dlp audio -> mp3 32k mono -> ffmpeg 20-min segments -> transcribe -> join.
Audio is deleted after each video to save disk.
"""
import json, os, pathlib, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AUDIO = DATA / "audio"
OUT = DATA / "transcripts"
AUDIO.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

MAX_HOURS = float(os.environ.get("MAX_HOURS", "72"))
MODEL = os.environ.get("TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")

def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)

def transcribe_file(path):
    import urllib.request, uuid
    boundary = uuid.uuid4().hex
    fields = {"model": MODEL, "response_format": "json"}
    body = b""
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
             "Content-Type: audio/mpeg\r\n\r\n").encode()
    body += path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)["text"]
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(15 * (attempt + 1))

def process(video):
    vid = video["id"]
    dest = OUT / f"{vid}.json"
    if dest.exists():
        return "skip"
    mp3 = AUDIO / f"{vid}.mp3"
    r = sh("yt-dlp", "-f", "ba", "-x", "--audio-format", "mp3",
           "--postprocessor-args", "ffmpeg:-ac 1 -b:a 32k",
           "-o", str(AUDIO / f"{vid}.%(ext)s"), "--", vid)
    if not mp3.exists():
        return f"download-failed: {r.stderr.strip()[-200:]}"
    # segment into 20-minute chunks (API duration limits)
    seg_pat = AUDIO / f"{vid}_%03d.mp3"
    # 8-min segments: gpt-4o-mini-transcribe silently truncates output around
    # 2k tokens (~12 min of speech), so segments must stay well under that.
    sh("ffmpeg", "-y", "-i", str(mp3), "-f", "segment", "-segment_time", "480",
       "-c", "copy", str(seg_pat))
    segments = sorted(AUDIO.glob(f"{vid}_*.mp3"))
    texts = [transcribe_file(s) for s in segments]
    dest.write_text(json.dumps({
        "id": vid, "title": video["title"], "duration": video["duration"],
        "score": video.get("score"), "url": f"https://www.youtube.com/watch?v={vid}",
        "model": MODEL, "text": "\n".join(texts),
    }, indent=2))
    for f in [mp3, *segments]:
        f.unlink(missing_ok=True)
    return "ok"

def main():
    videos = json.loads((DATA / "videos_ranked.json").read_text())
    budget_s = MAX_HOURS * 3600
    spent = done = failed = 0
    for v in videos:
        if spent + v["duration"] > budget_s:
            continue
        try:
            status = process(v)
        except Exception as e:  # a single video must never kill the batch
            status = f"exception: {type(e).__name__}: {e}"
        spent += v["duration"] if status in ("ok", "skip") else 0
        if status == "ok":
            done += 1
            print(f"[{done}] ok {v['id']} {int(v['duration']//60)}min "
                  f"(cum {spent/3600:.1f}h) {v['title'][:60]}", flush=True)
        elif status != "skip":
            failed += 1
            print(f"FAIL {v['id']}: {status}", flush=True)
            if failed > 15:
                print("too many failures, aborting", flush=True)
                sys.exit(1)
    print(f"DONE: {done} new, {failed} failed, {spent/3600:.1f}h in budget", flush=True)

if __name__ == "__main__":
    main()
