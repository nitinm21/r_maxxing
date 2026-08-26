export type Source = { title: string; url: string };
export type ChatMsg = { role: "user" | "assistant"; content: string; sources?: Source[]; ts: number };
export type Chat = { id: string; createdAt: number; messages: ChatMsg[] };

const KEY = "rmx.chats.v1";
const MAX_CHATS = 50;

export function loadChats(): Chat[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Chat[]) : [];
  } catch {
    return [];
  }
}

export function saveChats(chats: Chat[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(chats.slice(0, MAX_CHATS)));
  } catch {}
}

export function chatTitle(c: Chat): string {
  const first = c.messages.find((m) => m.role === "user");
  return first ? first.content.slice(0, 60) : "New chat";
}

export function relTime(ts: number): string {
  const s = (Date.now() - ts) / 1000;
  if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}
