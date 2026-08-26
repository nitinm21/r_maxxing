import { NextRequest } from "next/server";

export const maxDuration = 30;

export async function POST(req: NextRequest) {
  const form = await req.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) return Response.json({ error: "bad_request" }, { status: 400 });
  if (file.size > 4 * 1024 * 1024) return Response.json({ error: "too_long" }, { status: 413 });

  const out = new FormData();
  out.append("file", file, file.name || "audio.webm");
  out.append("model", "gpt-4o-mini-transcribe");
  out.append("response_format", "json");

  const res = await fetch("https://api.openai.com/v1/audio/transcriptions", {
    method: "POST",
    headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` },
    body: out,
  });
  if (!res.ok) return Response.json({ error: "stt_failed" }, { status: 500 });
  const { text } = await res.json();
  return Response.json({ text });
}
