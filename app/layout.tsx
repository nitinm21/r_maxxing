import type { Metadata, Viewport } from "next";
import "../styles/tokens.css";

export const metadata: Metadata = {
  title: "Retardmaxx",
  description:
    "Tell it your problem. It answers like Elisha would. Unofficial fan project — not affiliated with Elisha Long.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
