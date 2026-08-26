"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Chat, ChatMsg, Source, chatTitle, loadChats, relTime, saveChats } from "@/lib/storage";

const CHANNEL = "https://www.youtube.com/@ElishaLong";
const EXAMPLES = [
  "I keep replaying a mistake I made and can't let it go",
  "I still check my ex's Instagram every day",
  "I've been 'about to start' my thing for a year",
  "I doomscroll every night and hate it",
];

const newChat = (): Chat => ({ id: crypto.randomUUID(), createdAt: Date.now(), messages: [] });

export default function Page() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [currentId, setCurrentId] = useState<string>("");
  const [input, setInput] = useState("");
  const [stage, setStage] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [pinned, setPinned] = useState(true);
  const [recState, setRecState] = useState<"idle" | "recording" | "transcribing">("idle");
  const [recSecs, setRecSecs] = useState(0);

  const scrollerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const chatsRef = useRef(chats);
  chatsRef.current = chats;

  useEffect(() => {
    const loaded = loadChats();
    const first = loaded[0] ?? newChat();
    setChats(loaded.length ? loaded : [first]);
    setCurrentId(first.id);
  }, []);

  const current = chats.find((c) => c.id === currentId);

  const update = useCallback((fn: (cs: Chat[]) => Chat[]) => {
    setChats((cs) => {
      const next = fn(cs);
      saveChats(next);
      return next;
    });
  }, []);

  const patchMsg = useCallback(
    (chatId: string, idx: number, patch: Partial<ChatMsg>) => {
      update((cs) =>
        cs.map((c) =>
          c.id !== chatId
            ? c
            : { ...c, messages: c.messages.map((m, i) => (i === idx ? { ...m, ...patch } : m)) }
        )
      );
    },
    [update]
  );

  const showToast = (m: string) => {
    setToast(m);
    setTimeout(() => setToast(null), 5000);
  };

  useEffect(() => {
    if (pinned) scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight });
  });

  const onScroll = () => {
    const el = scrollerRef.current!;
    setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 150);
  };

  async function send(text: string) {
    const q = text.trim();
    if (!q || streaming || !current) return;
    setInput("");
    const chatId = current.id;
    const userMsg: ChatMsg = { role: "user", content: q, ts: Date.now() };
    const asstIdx = current.messages.length + 1;
    update((cs) =>
      cs.map((c) =>
        c.id !== chatId
          ? c
          : { ...c, messages: [...c.messages, userMsg, { role: "assistant", content: "", ts: Date.now() }] }
      )
    );
    setStreaming(true);
    setStage("reading your problem…");
    setPinned(true);
    try {
      const history = [...current.messages, userMsg].map(({ role, content }) => ({ role, content }));
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });
      if (res.status === 429) {
        patchMsg(chatId, asstIdx, { content: "Daily limit reached — come back tomorrow." });
        return;
      }
      if (!res.ok || !res.body) throw new Error();
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let text = "";
      let sources: Source[] = [];
      let gotDone = false;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const l of lines) {
          if (!l.trim()) continue;
          let ev: { t: string; v?: unknown };
          try {
            ev = JSON.parse(l);
          } catch {
            continue;
          }
          if (ev.t === "stage") setStage(ev.v as string);
          else if (ev.t === "sources") sources = ev.v as Source[];
          else if (ev.t === "delta") {
            setStage(null);
            text += ev.v as string;
            patchMsg(chatId, asstIdx, { content: text });
          } else if (ev.t === "done") {
            gotDone = true;
            patchMsg(chatId, asstIdx, { content: text, sources });
          } else if (ev.t === "error") throw new Error();
        }
      }
      if (!gotDone && !text) throw new Error();
    } catch {
      showToast("Couldn't answer — try again.");
      update((cs) =>
        cs.map((c) =>
          c.id !== chatId
            ? c
            : c.messages[asstIdx]?.content
              ? c
              : { ...c, messages: c.messages.slice(0, asstIdx) }
        )
      );
      setInput(q);
    } finally {
      setStreaming(false);
      setStage(null);
    }
  }

  async function toggleMic() {
    if (recState === "recording") {
      recRef.current?.stop();
      return;
    }
    if (recState !== "idle") return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
      const rec = new MediaRecorder(stream, { mimeType: mime });
      const parts: Blob[] = [];
      rec.ondataavailable = (e) => parts.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecState("transcribing");
        try {
          const blob = new Blob(parts, { type: mime });
          const form = new FormData();
          form.append("file", blob, mime.includes("mp4") ? "audio.mp4" : "audio.webm");
          const res = await fetch("/api/stt", { method: "POST", body: form });
          if (!res.ok) throw new Error();
          const { text } = await res.json();
          setInput((v) => (v ? v + " " : "") + text);
          textareaRef.current?.focus();
        } catch {
          showToast("Couldn't transcribe — try again or type it.");
        } finally {
          setRecState("idle");
          setRecSecs(0);
        }
      };
      rec.start();
      recRef.current = rec;
      setRecState("recording");
      setRecSecs(0);
      const t0 = Date.now();
      const iv = setInterval(() => {
        const s = Math.floor((Date.now() - t0) / 1000);
        setRecSecs(s);
        if (s >= 60 || recRef.current !== rec || rec.state !== "recording") {
          clearInterval(iv);
          if (rec.state === "recording") rec.stop();
        }
      }, 500);
    } catch {
      showToast("Microphone access was denied.");
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && recRef.current?.state === "recording") recRef.current.stop();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const autoGrow = () => {
    const el = textareaRef.current!;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 132) + "px";
  };

  if (!current) return null;

  return (
    <div className="app">
      <div className={`scrim ${drawer ? "open" : ""}`} onClick={() => setDrawer(false)} />
      <nav className={`sidebar ${drawer ? "open" : ""}`}>
        <button
          className="newchat"
          onClick={() => {
            const c = newChat();
            update((cs) => [c, ...cs]);
            setCurrentId(c.id);
            setDrawer(false);
          }}
        >
          + New chat
        </button>
        <div className="chatlist">
          {chats.map((c) => (
            <button
              key={c.id}
              className={`chatitem ${c.id === currentId ? "active" : ""}`}
              onClick={() => {
                setCurrentId(c.id);
                setDrawer(false);
              }}
            >
              <span className="title">{chatTitle(c)}</span>
              <span className="time">{relTime(c.createdAt)}</span>
              <span
                className="del"
                onClick={(e) => {
                  e.stopPropagation();
                  if (!confirm("Delete this chat?")) return;
                  update((cs) => {
                    const next = cs.filter((x) => x.id !== c.id);
                    if (!next.length) next.push(newChat());
                    if (c.id === currentId) setCurrentId(next[0].id);
                    return next;
                  });
                }}
              >
                ×
              </span>
            </button>
          ))}
        </div>
        <div className="sidefoot">
          Not affiliated with Elisha Long · <a href={CHANNEL} target="_blank">channel ↗</a>
        </div>
      </nav>

      <main className="main">
        <header className="header">
          <span style={{ display: "flex", alignItems: "center" }}>
            <button className="hamburger" onClick={() => setDrawer(true)} aria-label="Open chats">☰</button>
            <span className="name">Retardmaxx</span>
          </span>
          <a className="chip" href={CHANNEL} target="_blank">Unofficial fan project</a>
        </header>

        {current.messages.length === 0 ? (
          <div className="empty">
            <h1>Retardmaxx</h1>
            <p>Tell it your problem. It answers like Elisha would.</p>
            <div className="chips">
              {EXAMPLES.map((e) => (
                <button key={e} className="chip-btn" onClick={() => { setInput(e); textareaRef.current?.focus(); }}>
                  {e}
                </button>
              ))}
            </div>
            <div className="disclaimer">
              Unofficial fan project · AI imitation · not affiliated with{" "}
              <a href={CHANNEL} target="_blank">Elisha Long</a>
            </div>
          </div>
        ) : (
          <div className="scroller" ref={scrollerRef} onScroll={onScroll}>
            <div className="column">
              {current.messages.map((m, i) =>
                m.role === "user" ? (
                  <div key={i} className="msg-user">{m.content}</div>
                ) : (
                  <div key={i} className="msg-assistant">
                    {m.content}
                    {i === current.messages.length - 1 && stage && (
                      <div className="stageline"><span className="stagetext" key={stage}>{stage}</span></div>
                    )}
                    {m.sources && m.sources.length > 0 && (
                      <div className="sources">
                        From:{" "}
                        {m.sources.map((s, j) => (
                          <span key={s.url}>
                            {j > 0 && " · "}
                            <a href={s.url} target="_blank">{s.title}</a>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )
              )}
              {!pinned && (
                <button className="jump" onClick={() => { setPinned(true); }}>↓ Latest</button>
              )}
            </div>
          </div>
        )}

        <div className="composerwrap">
          <div className="composer">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              placeholder={recState === "recording" ? "Listening…" : "What's weighing on you?"}
              onChange={(e) => { setInput(e.target.value); autoGrow(); }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
            />
            <button
              className={`iconbtn mic ${recState === "recording" ? "recording" : ""}`}
              onClick={toggleMic}
              disabled={recState === "transcribing"}
              aria-label="Record a voice question"
            >
              {recState === "transcribing" ? "…" : recState === "recording" ? `${recSecs}s` : "🎙"}
            </button>
            <button
              className="iconbtn send"
              onClick={() => send(input)}
              disabled={!input.trim() || streaming}
              aria-label="Send"
            >
              ↑
            </button>
          </div>
          <div className="caption">
            {recState === "recording" && <span className="recdot" />}
            AI imitation of a YouTuber. Not therapy. In crisis? Call or text 988.
          </div>
        </div>
      </main>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
