import { useCallback, useEffect, useRef, useState } from "react";

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionResultListLike {
  length: number;
  [index: number]: SpeechRecognitionResultLike;
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: SpeechRecognitionResultListLike;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  abort: () => void;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

interface SpeechRecognitionWindow extends Window {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
}

interface SpeechInputOptions {
  lang?: string;
  onFinalTranscript: (transcript: string) => void;
}

function recognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") {
    return null;
  }
  const speechWindow = window as SpeechRecognitionWindow;
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

export function useSpeechInput({
  lang = "en-US",
  onFinalTranscript,
}: SpeechInputOptions) {
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const supported = recognitionConstructor() !== null;

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  const start = useCallback(() => {
    const Recognition = recognitionConstructor();
    if (Recognition === null || listening) {
      return;
    }

    const recognition = new Recognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = lang;
    recognition.onresult = (event) => {
      let interimTranscript = "";
      let finalTranscript = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const phrase = result[0].transcript.trim();
        if (!phrase) {
          continue;
        }
        if (result.isFinal) {
          finalTranscript = `${finalTranscript} ${phrase}`.trim();
        } else {
          interimTranscript = `${interimTranscript} ${phrase}`.trim();
        }
      }

      const currentTranscript = [finalTranscript, interimTranscript]
        .filter(Boolean)
        .join(" ");
      if (currentTranscript) {
        setTranscript(currentTranscript);
      }
      if (finalTranscript) {
        onFinalTranscript(finalTranscript);
      }
    };
    recognition.onerror = () => {
      setError("Voice input is unavailable.");
      setListening(false);
      recognitionRef.current = null;
    };
    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    setError(null);
    setTranscript("");
    setListening(true);

    try {
      recognition.start();
    } catch {
      setError("Voice input is unavailable.");
      setListening(false);
      recognitionRef.current = null;
    }
  }, [lang, listening, onFinalTranscript]);

  const toggle = useCallback(() => {
    if (listening) {
      stop();
      return;
    }
    start();
  }, [listening, start, stop]);

  useEffect(
    () => () => {
      recognitionRef.current?.abort();
    },
    [],
  );

  return { error, listening, start, stop, supported, toggle, transcript };
}
