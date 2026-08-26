# r_maxxing — Implementation Plan (v2, granular)

Persona chat app: users describe a life problem, get an answer in Elisha Long's
"retardmaxxing" voice, grounded in his video transcripts via RAG. Public web app on
Vercel, anonymous users, unofficial-fan-project disclaimer.

Every phase ends at a **gate**: work stops, you review the deliverable, nothing in the
next phase starts until you approve. Phase 1 is already running (approved).

## Locked decisions (from A/B testing, 2026-08-11)

| Concern | Decision | Evidence/cost |
|---|---|---|
| Answer model | GPT-5.6 Terra, `reasoning_effort: "none"` | Won A/B vs Luna; near Kimi K2.5 persona; higher reasoning breaks character (2/8 at xhigh). ~$0.0114/answer, 0.74s TTFT |
| Pipeline model | GPT-5.6 Luna, reasoning none | classification + query rewrite, ~$0.001/call |
| Transcription + mic STT | `gpt-4o-mini-transcribe` | ~$0.003/min |
| Embeddings | `text-embedding-3-small` | ~$0.02 for whole corpus |
| Vector DB | Upstash Vector | free tier covers ~2,000 chunks |
| Users | Anonymous; localStorage chats; per-IP rate limit | no auth in v1 |
| Repo / deploy | public `nitinm21/r_maxxing` → Vercel | transcripts/audio never committed |
| Persona ethics | visible "unofficial fan project" disclaimer | user decision |
| Voice output | v2 (Chatterbox on serverless GPU + Blob cache) | deferred |

---

## Phase 1 — Knowledge base (RUNNING)

Luna classified all 1,657 videos (1,172 on-topic), scored 0–10 (`data/videos_ranked.json`).
`pipeline/transcribe.py` walks the ranked list top-down within `MAX_HOURS=72` (~$13
approved): yt-dlp → mp3 32k mono → 20-min ffmpeg segments → gpt-4o-mini-transcribe →
`data/transcripts/{id}.json` (`{id,title,duration,score,url,model,text}`). Resumable;
skips existing files; aborts after 15 download failures.

**Gate 1 deliverable:** transcript count + failure list · 5 spot-checks vs audio ·
actual spend from OpenAI dashboard · your 72h-vs-232h (+~$29) decision.

## Phase 2 — Search index

**New file `pipeline/chunk_embed.py`:**
1. For each transcript: split text into **~600-word chunks with 100-word overlap**
   (≈800 tokens); skip transcripts under 100 words; chunk id `{videoId}#{n}`.
2. Prepend `"{video title} — "` to each chunk body before embedding (titles carry his
   framing: "Be retarded and stop overthinking").
3. Embed with `text-embedding-3-small`, batches of 100 inputs per API call.
4. Upsert to Upstash Vector: `{id, vector, metadata: {videoId, title, url, score, n, text}}`.
   No per-moment timestamps (transcription model doesn't emit them) — citations link to
   the video page only.

**New file `pipeline/rewrite.py`** (shared later by the app): Luna prompt that maps an
emotional problem statement to his concept vocabulary. Contract:
`rewrite("my ex left and I check her insta") → "letting go, overthinking a breakup,
social media brain rot, reclaiming your center"`. The rewritten string is what gets
embedded for retrieval.

**New file `pipeline/eval_retrieval.py`:** 15 fixed realistic questions (breakup,
career shame, doomscrolling, decision paralysis, social anxiety, business fear, family
friction, anxiety-no-reason, comparison, porn/dopamine, loneliness, purpose, money
stress, confidence, overthinking-at-night). For each: retrieve top-5 with and without
rewrite → markdown report `data/eval_retrieval.md`.

**Needs from you:** Upstash account (free, no card) — or approve Marketplace
provisioning in P4 and use a local JSON index meanwhile.

**Gate 2 deliverable:** `eval_retrieval.md` — you judge whether each question surfaces
the right passages, and whether rewrite earns its latency.

## Phase 3 — Answer engine (no UI)

**New file `lib/prompt.ts`** (single source of truth, mirrored by a CLI harness):
- *Identity block*: who he is, what retardmaxxing means, worldview.
- *Voice rules* (from the corpus): brothers/dude/man address; thoughts-are-clouds;
  be-the-bread; Master Gardener; thumos; anti-brain-rot; mocks optimization culture;
  occasionally spiritual; concrete prescriptions (delete apps, jump rope, 10 pages,
  talk to people, start today); 150–300 words; no bullet points; ends with
  encouragement/"Peace".
- *Grounding rules*: retrieved excerpts injected under a delimiter; reuse his actual
  phrases; never quote more than a sentence verbatim; if excerpts are off-topic,
  answer from the persona's philosophy without inventing biographical claims.
- **Safety block (load-bearing):** if the message indicates self-harm, suicide, abuse,
  or medical/psychiatric crisis → drop the persona, say plainly you're an AI fan
  project, encourage professional help, and give crisis resources (988 in the US,
  findahelpline.com elsewhere). No in-character medical, legal, or financial advice.
  Minors-related content → refuse gently.
- *Format*: plain prose, no headers/lists, no emojis.

**New file `pipeline/answer_cli.py`:** full chain (rewrite → retrieve top-6 → Terra
stream) against 12 sample problems **plus 3 crisis-adjacent prompts** → single review
file `data/eval_answers.md` with latency + cost per answer.

**Gate 3 deliverable:** `eval_answers.md`. This is where you tune the voice — cheapest
iteration point. Crisis behavior must pass before P4 starts.

## Phase 4 — Web app on Vercel

### Stack
Next.js (App Router) + TypeScript + AI SDK; no component library, no CSS framework —
one global stylesheet with tokens. System font stack. Node runtime (Fluid), default region.

### File tree
```
app/
  layout.tsx            # metadata, tokens.css import, footer disclaimer
  page.tsx              # the single screen
  api/chat/route.ts     # rate limit → rewrite → retrieve → Terra stream
  api/stt/route.ts      # multipart audio → gpt-4o-mini-transcribe → {text}
components/
  Sidebar.tsx           # chat list + New chat (drawer on mobile)
  Messages.tsx          # message list + auto-scroll + jump-to-latest pill
  StageLine.tsx         # pipeline status while waiting for first token
  Composer.tsx          # textarea + mic + send
  MicButton.tsx         # record / transcribe states
  Toast.tsx             # errors + rate-limit notices
  EmptyState.tsx        # new-chat screen with example prompts
lib/
  openai.ts  rewrite.ts  retrieve.ts  prompt.ts  ratelimit.ts  storage.ts
styles/tokens.css
```

### UI specification (bare-bones by design)

**Layout.** One screen. Desktop: fixed left sidebar 260px; main column with a
720px-max reading column centered. Mobile (<768px): sidebar hidden; hamburger top-left
opens it as a slide-over drawer with scrim; otherwise identical.

**Palette (tokens).** `--bg` near-white warm gray; `--fg` near-black; `--muted` gray;
`--line` hairline; `--accent` deep green `#156B4A` (used only for send button, active
chat, links); `--danger` for recording dot and destructive hover. Dark theme via
`prefers-color-scheme` only — no toggle.

**Header (main column).** App display name (your pick, pending) left; a small muted
chip right: "Unofficial fan project" → links to the channel. Nothing else.

**Sidebar.** Top: `+ New chat` button (full-width, quiet). Below: chats newest-first;
item = first user message truncated to one line + relative time; active item has
`--accent` left border and tinted bg; hover shows a small `×` (delete, with
`confirm()` — bare-bones). Footer: one muted line "Not affiliated with Elisha Long"
+ channel link.

**Messages.** User: right-aligned bubble, `--line` bordered, max 80% width. Assistant:
no bubble — plain text on the background, full column width (it reads like an essay,
matching the persona's monologue form). Streamed markdown: bold/italic only (persona
prompt forbids lists/headers anyway). Under each finished assistant message: muted
one-line source row — `From: {video title}` links (up to 3, deduped) to YouTube.
Timestamps omitted (bare-bones).

**StageLine.** After the user sends, one muted line sits where the answer will start,
driven by streamed data parts (never timers): `reading your problem…` →
`finding what Elisha says about this…` → answer replaces it at first token. This is
the perceived-latency treatment for the ~1.5s pipeline gap.

**Composer.** Fixed at column bottom. Auto-growing textarea (1→5 lines, then internal
scroll), placeholder "What's weighing on you?". Right: send button (accent, arrow icon),
disabled when empty or while an answer is streaming. Left of send: mic button.
Enter sends; Shift+Enter newlines. Below composer, one muted caption line:
"AI imitation of a YouTuber. Not therapy. In crisis? Call or text 988."

**Mic flow.** Tap mic → browser permission → recording: button turns `--danger`, a
small pulsing dot + elapsed `0:07` appear, composer placeholder becomes "Listening…";
tap again (or Esc) stops → button shows spinner "…" while `/api/stt` runs (~1s) →
transcribed text lands **in the composer, editable — never auto-sent** → user presses
send. Recording hard-capped at 60s. Errors (mic denied, STT failure) → Toast.

**EmptyState (new chat).** Vertically centered in the column: display name, one-line
description ("Tell it your problem. It answers like Elisha would."), then 4 example
prompt chips (tap → fills composer): overthinking a mistake, checking an ex's
Instagram, stuck-not-starting, doomscrolling. Below, small muted disclaimer.

**Errors & limits.** All failures → bottom-center Toast, 5s, dismissible. 429 from
rate limit (20 messages/day/IP, Upstash Ratelimit sliding window): composer disables
with inline note "Daily limit reached — come back tomorrow" (+ reset time from the
429 body). Answer-stream failure: partial text kept, small inline `Retry` link
re-sends the same message.

**Scrolling.** Pinned to bottom while streaming *unless* the user scrolls up >150px —
then a `↓ Latest` pill appears bottom-center; clicking re-pins.

**Persistence (`lib/storage.ts`).** localStorage key `rmx.chats.v1`:
`[{id, createdAt, messages: [{role, content, sources?, ts}]}]`, ~50-chat FIFO cap,
title derived (not stored) from first user message. No server-side storage of chats.

### API contracts
- `POST /api/chat` body `{messages: [{role, content}]}` (client sends trimmed history,
  last 12 messages max). Stream (AI SDK data parts):
  `{type:'stage', value:'rewriting'|'retrieving'}` → `{type:'sources', value:[{title,url}]}`
  → text deltas. Errors: `429 {error:'rate_limit', resetAt}`, `500 {error:'answer_failed'}`.
- `POST /api/stt` multipart `file` (audio/webm;opus, ≤60s) → `200 {text}` |
  `413` too long | `500 {error:'stt_failed'}`.
- Both routes check `Origin` and are rate-limited (stt shares the daily budget).

### Motion spec (via `find-animation-opportunities` gate)

Shared tokens: `--ease-out: cubic-bezier(0.23,1,0.32,1)`; durations per row. Animate
`transform`/`opacity` only. `prefers-reduced-motion`: crossfades become instant swaps,
drawer/toast durations halve, pulse stops (static dot).

| # | Surface | Purpose | Frequency | Recipe |
|---|---|---|---|---|
| 1 | StageLine text swaps | State indication / prevent jarring swap | Once per message | Crossfade: outgoing `opacity 1→0`, incoming `0→1` `translateY(2px)→0`, 200ms `--ease-out`; answer's first token swaps instantly (never delay content) |
| 2 | Mic idle↔recording | State indication | Occasional | Color + `scale(1→1.06→1)` 160ms `--ease-out`; while recording, dot pulses `opacity .4↔1` 1.2s ease-in-out loop |
| 3 | Mobile sidebar drawer | Spatial consistency | Occasional | `translateX(-100%)→0` 280ms `cubic-bezier(0.32,0.72,0,1)`, scrim `opacity 0→1` same clock; exit = reverse, same edge |
| 4 | Toast enter/exit | Prevent jarring appearance | Occasional | `translateY(100%) + opacity 0` → settled, 300ms `--ease-out` via `@starting-style`; exits the same edge |
| 5 | Send button press | Feedback | Tens/day | `:active { transform: scale(0.97) }` `transition: transform 140ms --ease-out` — near-imperceptible tier |
| 6 | EmptyState example chips | Delight (sanctioned: empty state) | Rare | 40ms stagger, `opacity 0→1` + `translateY(4px)→0`, 250ms `--ease-out`; never blocks input |

**Rejected (gate failures):** per-token fade on streaming text (functional reading
surface — decoration hinders); chat switching (core navigation, tens/day — instant);
composer autogrow (tracks typing, 100+/day — any easing lags input); Enter-to-send
(keyboard-initiated — never animate); sidebar hover states (tens/day — plain color
swap, no transition); answer-complete flourish (reading surface).

### Deploy
Vercel **preview** (project created under your account, `vercel env` for
`OPENAI_API_KEY`, `UPSTASH_VECTOR_REST_URL/TOKEN`, `UPSTASH_REDIS_REST_URL/TOKEN`).

**Needs from you at P4 start:** `vercel login` + project-creation approval · app
display name · Upstash (if not done at P2) · confirm 20 msgs/day/IP.

**Gate 4 deliverable:** preview URL — use it like a real user (desktop + phone).

## Phase 5 — Mic input polish

MediaRecorder wiring per the mic flow above (the UI shell ships in P4; P5 makes it
real): webm/opus capture, 60s cap, `/api/stt`, error toasts, iOS Safari quirks
(`audio/mp4` fallback — Safari's MediaRecorder emits mp4/aac).

**Gate 5 deliverable:** same preview; test matrix = desktop Chrome, desktop Safari,
iOS Safari, Android Chrome.

## Phase 6 — Launch

Rotate every key pasted in chat (OpenAI, Puter) → fresh keys only in Vercel env ·
OpenAI budget alert ($25/mo suggested) · Vercel Analytics · final safety-prompt pass ·
production deploy · custom domain (optional).

**Gate 6 deliverable:** production URL + one-page runbook (costs, limits, corpus
expansion, key rotation).

## v2 (parked)
Chatterbox TTS on Modal/Replicate + Blob cache + per-answer speaker icon · corpus to
232h · optional accounts/sync.

## Standing risks
- **Right of publicity:** disclaimer-only per your call; takedown path = strip
  name/persona, keep philosophy.
- **Self-help ≠ therapy:** safety layer tested at gate 3 with crisis prompts; 988 line
  in the composer caption permanently.
- **Cost:** ~$0.013/message all-in; 20/day/IP cap + budget alarm bound the worst case.
