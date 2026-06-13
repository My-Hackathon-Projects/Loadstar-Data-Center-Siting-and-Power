interface SkipControlProps {
  onSkip: () => void;
}

/** Quiet skip-to-app control, visible in every phase of the journey. */
export function SkipControl({ onSkip }: SkipControlProps) {
  return (
    <button
      className="absolute bottom-5 right-6 z-50 text-xs lowercase tracking-wider text-dim transition-colors hover:text-primary"
      onClick={onSkip}
      type="button"
    >
      skip to app
    </button>
  );
}
