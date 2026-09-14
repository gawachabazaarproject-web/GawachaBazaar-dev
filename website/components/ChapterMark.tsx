type Tone = "dark" | "light";

export default function ChapterMark({
  index,
  tone = "dark",
  className = "",
}: {
  index: number;
  tone?: Tone;
  className?: string;
}) {
  const faint = tone === "dark" ? "text-primary-800/[0.06]" : "text-neutral-100/[0.08]";

  return (
    <span
      aria-hidden
      className={`pointer-events-none block select-none font-display text-[22vw] font-bold leading-none sm:text-[13rem] ${faint} ${className}`}
    >
      {String(index).padStart(2, "0")}
    </span>
  );
}
