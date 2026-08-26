import { NextRequest } from "next/server";
import { rewriteQuery, retrieve, buildSystemPrompt, dedupeSources } from "@/lib/server";

export const maxDuration = 60;

type Msg = { role: "user" | "assistant"; content: string };

const enc = new TextEncoder();
const line = (o: unknown) => enc.encode(JSON.stringify(o) + "\n");

export async function POST(req: NextRequest) {
  let messages: Msg[];
  try {
    const body = await req.json();
    messages = (body.messages as Msg[]).slice(-12).map((m) => ({
      role: m.role === "assistant" ? "assistant" : "user",
      content: String(m.content).slice(0, 4000),
    }));
    if (!messages.length || messages[messages.length - 1].role !== "user") throw new Error();
  } catch {
    return Response.json({ error: "bad_request" }, { status: 400 });
  }
  const question = messages[messages.length - 1].content;

  const stream = new ReadableStream({
    async start(controller) {
      try {
        controller.enqueue(line({ t: "stage", v: "reading your problem…" }));
        const rewritten = await rewriteQuery(question);
        controller.enqueue(line({ t: "stage", v: "finding what Elisha says about this…" }));
        const matches = await retrieve(question, rewritten);
        controller.enqueue(line({ t: "sources", v: dedupeSources(matches) }));
        const system = await buildSystemPrompt(matches);

        const res = await fetch("https://api.openai.com/v1/chat/completions", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            model: "gpt-5.6-terra",
            reasoning_effort: "none",
            temperature: 1.0,
            max_completion_tokens: 700,
            stream: true,
            messages: [{ role: "system", content: system }, ...messages],
          }),
        });
        if (!res.ok || !res.body) throw new Error(`openai ${res.status}`);

        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let buf = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const l of lines) {
            const s = l.trim();
            if (!s.startsWith("data: ") || s === "data: [DONE]") continue;
            try {
              const delta = JSON.parse(s.slice(6)).choices?.[0]?.delta?.content;
              if (delta) controller.enqueue(line({ t: "delta", v: delta }));
            } catch {}
          }
        }
        controller.enqueue(line({ t: "done" }));
      } catch (e) {
        controller.enqueue(line({ t: "error", v: "answer_failed" }));
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: { "Content-Type": "application/x-ndjson", "Cache-Control": "no-store" },
  });
}
