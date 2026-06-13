const FRED_PENDING_PROMPT_KEY = "loadstar:fred-pending-prompt";

function sessionStorageSafe(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function savePendingFredPrompt(prompt: string): void {
  const trimmed = prompt.trim();
  const storage = sessionStorageSafe();
  if (!trimmed || storage === null) {
    return;
  }
  storage.setItem(FRED_PENDING_PROMPT_KEY, trimmed);
}

export function consumePendingFredPrompt(): string | null {
  const storage = sessionStorageSafe();
  if (storage === null) {
    return null;
  }
  const prompt = storage.getItem(FRED_PENDING_PROMPT_KEY);
  storage.removeItem(FRED_PENDING_PROMPT_KEY);
  return prompt?.trim() || null;
}
