# r_maxxing

Chat with a digital version of the retardmaxxing philosophy — grounded in transcripts
of Elisha Long's YouTube videos via RAG.

> **Unofficial fan project.** Not affiliated with or endorsed by Elisha Long.
> All ideas belong to the original creator; go watch the channel:
> https://www.youtube.com/@ElishaLong

## How it works

1. **Pipeline** (`pipeline/`): classify channel videos by topic (GPT-5.6 Luna),
   rank by relevance, transcribe audio (gpt-4o-mini-transcribe), chunk + embed
   (text-embedding-3-small) into Upstash Vector.
2. **App**: Next.js chat UI. Questions are rewritten into the creator's concept
   vocabulary (Luna), matching transcript chunks are retrieved, and GPT-5.6 Terra
   answers in his voice, streaming. Mic input via OpenAI STT.

Transcripts and audio are **not** stored in this repo (`data/` is gitignored).

## Setup

```bash
cp .env.example .env   # add your keys
python3 pipeline/classify.py <channel-listing.txt>
python3 pipeline/prioritize.py
python3 pipeline/transcribe.py   # MAX_HOURS=72 by default
```
