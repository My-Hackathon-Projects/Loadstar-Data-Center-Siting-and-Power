interface VoiceBarsProps {
  /** When true the bars pulse; otherwise they rest, calm. Purely decorative — never audio-driven. */
  active?: boolean;
  bars?: number;
  className?: string;
}

/**
 * Fred's presence: thin amber bars pulsing via CSS keyframes. Used in the intro
 * greeting and the dashboard chat panel. There is no audio anywhere; the motion
 * stands in for a voice.
 */
export function VoiceBars({
  active = false,
  bars = 6,
  className = "",
}: VoiceBarsProps) {
  return (
    <div className={`flex items-center gap-[3px] ${className}`} aria-hidden>
      {Array.from({ length: bars }).map((_, index) => (
        <span
          className="voicebar"
          key={index}
          style={{
            animationDelay: `${index * 0.12}s`,
            animationPlayState: active ? "running" : "paused",
          }}
        />
      ))}
    </div>
  );
}
