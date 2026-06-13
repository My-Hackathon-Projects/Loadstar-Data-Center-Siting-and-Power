import { useCallback, useEffect, useRef, useState } from "react";

import { useUiStore } from "../../hooks/useUiStore";
import { useSpeechInput } from "../../hooks/useSpeechInput";
import { useChatAgent } from "../../lib/queries";
import { consumePendingFredPrompt } from "../../lib/fredPrompt";
import { speakFred } from "../../lib/fredVoice";
import type { AgentChatRequest } from "../../types/api";
import { VoiceBars } from "../journey/VoiceBars";
import { FRED_GREETING } from "../journey/constants";
import type { ExplainSource } from "./types";

interface ChatMessage {
  body: string;
  speaker: "assistant" | "user";
  source?: ExplainSource;
  model?: string | null;
}

const INTRO: ChatMessage = {
  body: FRED_GREETING,
  speaker: "assistant",
};

type AgentChatHistory = NonNullable<AgentChatRequest["history"]>;

function toAgentHistory(messages: ChatMessage[]): AgentChatHistory {
  return messages.slice(-8).map((message) => ({
    body: message.body,
    speaker: message.speaker,
  }));
}

export function FredPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([INTRO]);
  const [waitingForResponse, setWaitingForResponse] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const initializedRef = useRef(false);
  const startListeningRef = useRef<() => void>(() => undefined);

  const powerMw = useUiStore((state) => state.powerMw);
  const workloadType = useUiStore((state) => state.workloadType);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const setSearchParams = useUiStore((state) => state.setSearchParams);
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  const chat = useChatAgent();

  const append = useCallback((message: ChatMessage) => {
    setMessages((current) => [...current, message]);
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
    });
  }, []);

  const runAgent = useCallback(
    (rawMessage: string) => {
      const message = rawMessage.trim();
      if (!message || chat.isPending) {
        return;
      }

      setWaitingForResponse(false);
      const history = toAgentHistory(messages);
      append({ body: message, speaker: "user" });
      chat.mutate(
        {
          history,
          message,
          power_mw: powerMw,
          selected_cell_id: selectedCellId,
          workload_type: workloadType,
        },
        {
          onSuccess: (response) => {
            append({
              body: response.message,
              speaker: "assistant",
              source: response.source,
              model: response.model,
            });
            void speakFred(response.message, {
              onEnd: () => {
                setWaitingForResponse(true);
                startListeningRef.current();
              },
            });

            if (response.action.type === "search" && response.action.applied) {
              const applied = response.action.applied;
              setSearchParams({
                powerMw: applied.power_mw,
                workloadType: applied.workload_type,
                topK: applied.top_k,
                weights: applied.weights,
                countryFilter: applied.country_filter ?? [],
              });
              if (response.action.focus_cell_id) {
                setSelectedCellId(response.action.focus_cell_id);
              }
            }
          },
          onError: () => {
            const failure =
              "That did not go through. Try again, or adjust the specifications on the left.";
            append({
              body: failure,
              speaker: "assistant",
              source: "template",
            });
            void speakFred(failure, {
              onEnd: () => {
                setWaitingForResponse(true);
                startListeningRef.current();
              },
            });
          },
        },
      );
    },
    [
      append,
      chat,
      messages,
      powerMw,
      selectedCellId,
      setSearchParams,
      setSelectedCellId,
      workloadType,
    ],
  );

  const handleVoiceTranscript = useCallback(
    (transcript: string) => {
      runAgent(transcript);
    },
    [runAgent],
  );

  const speech = useSpeechInput({ onFinalTranscript: handleVoiceTranscript });

  useEffect(() => {
    startListeningRef.current = speech.start;
  }, [speech.start]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (initializedRef.current || chat.isPending) {
        return;
      }
      initializedRef.current = true;
      const pendingPrompt = consumePendingFredPrompt();
      if (pendingPrompt !== null) {
        runAgent(pendingPrompt);
        return;
      }

      void speakFred(FRED_GREETING, {
        onEnd: () => {
          setWaitingForResponse(true);
          startListeningRef.current();
        },
      });
    }, 0);

    return () => window.clearTimeout(timer);
  }, [chat.isPending, runAgent]);

  useEffect(() => {
    if (!waitingForResponse || chat.isPending || speech.listening || speech.error) {
      return;
    }
    const timer = window.setTimeout(speech.start, 350);
    return () => window.clearTimeout(timer);
  }, [
    chat.isPending,
    speech.error,
    speech.listening,
    speech.start,
    waitingForResponse,
  ]);

  return (
    <section className="flex h-full flex-col rounded-2xl border border-subtle bg-panel p-4">
      <div className="flex items-center gap-3">
        <VoiceBars active={chat.isPending || speech.listening} bars={6} />
        <div>
          <p className="eyebrow">fred</p>
          <p className="text-sm text-dim">siting copilot</p>
        </div>
      </div>

      <div className="mt-3 flex-1 space-y-2 overflow-y-auto pr-1" ref={listRef}>
        {messages.map((message, index) => (
          <div
            className={`rounded-xl px-3 py-2 text-sm ${
              message.speaker === "assistant"
                ? "bg-panel-raised text-primary"
                : "border border-subtle text-dim"
            }`}
            key={`${message.speaker}-${index}`}
          >
            {message.speaker === "assistant" && message.source ? (
              <span className="mr-2 inline-flex rounded-full border border-subtle px-2 py-0.5 text-[0.625rem] uppercase tracking-wide text-dim">
                {sourceLabel(message.source, message.model)}
              </span>
            ) : null}
            <span>{message.body}</span>
          </div>
        ))}
        {chat.isPending ? (
          <p className="px-3 py-2 text-sm text-dim">Fred is working...</p>
        ) : null}
      </div>

      <div className="mt-3 min-h-10 rounded-full border border-subtle bg-void px-4 py-2.5 text-center text-sm text-dim">
        {!speech.supported
          ? "voice input is unavailable in this browser"
          : chat.isPending
          ? "working..."
          : speech.listening
            ? speech.transcript || "listening..."
            : "waiting for voice..."}
      </div>
      {speech.error ? <p className="mt-2 text-xs text-dim">{speech.error}</p> : null}
    </section>
  );
}

function sourceLabel(source: ExplainSource, model?: string | null): string {
  if (source === "openai") {
    return model ? `live · ${model}` : "live";
  }
  return "engine";
}
