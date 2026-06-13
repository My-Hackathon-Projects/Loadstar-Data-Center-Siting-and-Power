export function speakFred(message: string): void {
  const trimmed = message.trim();
  if (
    !trimmed ||
    typeof window === "undefined" ||
    !("speechSynthesis" in window) ||
    !("SpeechSynthesisUtterance" in window)
  ) {
    return;
  }

  try {
    window.speechSynthesis.cancel();
    const utterance = new window.SpeechSynthesisUtterance(trimmed);
    utterance.pitch = 0.95;
    utterance.rate = 0.96;
    window.speechSynthesis.speak(utterance);
  } catch {
    // Browsers can reject speech before a user gesture; the visual chat still works.
  }
}
