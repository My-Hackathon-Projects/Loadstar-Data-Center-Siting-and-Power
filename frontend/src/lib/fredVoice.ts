import { API_BASE_URL } from "../config/env";

interface SpeakFredOptions {
  onEnd?: () => void;
}

let currentAudio: HTMLAudioElement | null = null;

export async function speakFred(
  message: string,
  options: SpeakFredOptions = {},
): Promise<boolean> {
  const trimmed = message.trim();
  if (!trimmed || typeof window === "undefined") {
    options.onEnd?.();
    return false;
  }

  try {
    currentAudio?.pause();
    currentAudio = null;

    const response = await fetch(`${API_BASE_URL}/agent/speech`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: trimmed }),
    });
    if (!response.ok) {
      throw new Error(`Fred speech failed: ${response.status}`);
    }

    const audioUrl = URL.createObjectURL(await response.blob());
    const audio = new window.Audio(audioUrl);
    currentAudio = audio;
    await playAudio(audio);
    return true;
  } catch {
    return false;
  } finally {
    currentAudio = null;
    options.onEnd?.();
  }
}

function playAudio(audio: HTMLAudioElement): Promise<void> {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("error", handleError);
      URL.revokeObjectURL(audio.src);
    };
    const handleEnded = () => {
      cleanup();
      resolve();
    };
    const handleError = () => {
      cleanup();
      reject(new Error("Audio playback failed."));
    };

    audio.addEventListener("ended", handleEnded, { once: true });
    audio.addEventListener("error", handleError, { once: true });
    void audio.play().catch((error: unknown) => {
      cleanup();
      reject(error instanceof Error ? error : new Error("Audio playback failed."));
    });
  });
}
