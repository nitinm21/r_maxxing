import { readFileSync } from "fs";
import path from "path";

const OPENAI = "https://api.openai.com/v1";
const PINECONE = "https://rmaxxing-n9s6x6u.svc.aped-4627-b74a.pinecone.io";

const oaHeaders = () => ({
  Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
  "Content-Type": "application/json",
});
const pcHeaders = () => ({
  "Api-Key": process.env.PINECONE_API_KEY ?? "",
  "Content-Type": "application/json",
});

export type Source = { title: string; url: string };
export type Match = { metadata: { videoId: string; title: string; url: string; text: string } };

const REWRITE_PROMPT = `A user of a self-help chat app described a personal problem. Rewrite it as a short
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

User's problem: `;

export async function rewriteQuery(q: string): Promise<string> {
  const res = await fetch(`${OPENAI}/chat/completions`, {
    method: "POST",
    headers: oaHeaders(),
    body: JSON.stringify({
      model: "gpt-5.6-luna",
      reasoning_effort: "none",
      max_completion_tokens: 60,
      messages: [{ role: "user", content: REWRITE_PROMPT + q }],
    }),
  });
  if (!res.ok) throw new Error(`rewrite ${res.status}`);
  const out = await res.json();
  return (out.choices[0].message.content as string).trim();
}

export async function retrieve(q: string, rewritten: string): Promise<Match[]> {
  const embRes = await fetch(`${OPENAI}/embeddings`, {
    method: "POST",
    headers: oaHeaders(),
    body: JSON.stringify({ model: "text-embedding-3-small", input: [`${q} ${rewritten}`] }),
  });
  if (!embRes.ok) throw new Error(`embed ${embRes.status}`);
  const vector = (await embRes.json()).data[0].embedding;
  const qRes = await fetch(`${PINECONE}/query`, {
    method: "POST",
    headers: pcHeaders(),
    body: JSON.stringify({ vector, topK: 6, includeMetadata: true }),
  });
  if (!qRes.ok) throw new Error(`pinecone ${qRes.status}`);
  return (await qRes.json()).matches as Match[];
}

// Voice exemplars live in Pinecone metadata (transcripts are not in the repo).
// Fetched once per instance and cached.
let exemplarCache: string | null = null;
export async function exemplars(): Promise<string> {
  if (exemplarCache) return exemplarCache;
  const ids = ["-IJ71tbhOLY#0", "-IJ71tbhOLY#1", "1V11itjbyVE#0", "1V11itjbyVE#1"];
  const qs = ids.map((i) => `ids=${encodeURIComponent(i)}`).join("&");
  const res = await fetch(`${PINECONE}/vectors/fetch?${qs}`, { headers: pcHeaders() });
  if (!res.ok) throw new Error(`exemplars ${res.status}`);
  const vecs = (await res.json()).vectors as Record<string, Match>;
  const byVideo = new Map<string, string[]>();
  for (const id of ids) {
    const md = vecs[id]?.metadata;
    if (!md) continue;
    const arr = byVideo.get(md.title) ?? [];
    // chunk #0 opens with the video-intro greeting; skip it so chat answers don't greet
    const words = md.text.split(/\s+/);
    arr.push(id.endsWith("#0") ? words.slice(60).join(" ") : words.join(" "));
    byVideo.set(md.title, arr);
  }
  exemplarCache = [...byVideo.entries()]
    .map(([title, parts]) => `[From your video "${title.trim()}"]\n${parts.join(" ")}`)
    .join("\n\n");
  return exemplarCache;
}

let personaCache: string | null = null;
export function personaInstructions(): string {
  personaCache ??= readFileSync(path.join(process.cwd(), "lib/persona_prompt.txt"), "utf8");
  return personaCache;
}

export async function buildSystemPrompt(matches: Match[]): Promise<string> {
  const context = matches
    .map((m) => `From "${m.metadata.title.trim()}":\n${m.metadata.text}`)
    .join("\n\n---\n\n");
  return `${personaInstructions()}\n\nHOW YOU TALK (verbatim from your videos):\n\n${await exemplars()}\n\nIDEAS RELEVANT TO THIS VIEWER (from your videos):\n${context}`;
}

export function dedupeSources(matches: Match[]): Source[] {
  const seen = new Set<string>();
  const out: Source[] = [];
  for (const m of matches) {
    const t = m.metadata.title.trim();
    if (!seen.has(t)) {
      seen.add(t);
      out.push({ title: t, url: m.metadata.url });
    }
    if (out.length === 3) break;
  }
  return out;
}
