"use client";

/** Last-resort boundary (a crash in the root layout itself). Plain HTML and
 * inline styles only: nothing here may depend on the app's own providers. */
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", background: "#f7f4eb", textAlign: "center", paddingTop: "20vh" }}>
        <h1 style={{ color: "#0b2d20" }}>The admin panel hit an unexpected error</h1>
        <p style={{ color: "#4a4433" }}>Reloading usually fixes it.</p>
        <button
          onClick={reset}
          style={{ background: "#0b2d20", color: "#fff", border: 0, borderRadius: 4, padding: "8px 16px", fontWeight: 600, cursor: "pointer" }}
        >
          Reload
        </button>
      </body>
    </html>
  );
}
