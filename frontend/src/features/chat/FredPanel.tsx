import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

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
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([INTRO]);
  const listRef = useRef<HTMLDivElement>(null);
  const consumedPendingPromptRef = useRef(false);

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

      const history = toAgentHistory(messages);
      setDraft("");
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
            speakFred(response.message);

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
            speakFred(failure);
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
      setDraft(transcript);
      runAgent(transcript);
    },
    [runAgent],
  );

  const speech = useSpeechInput({ onFinalTranscript: handleVoiceTranscript });

  useEffect(() => {
    if (consumedPendingPromptRef.current || chat.isPending) {
      return;
    }

    const timer = window.setTimeout(() => {
      if (consumedPendingPromptRef.current || chat.isPending) {
        return;
      }
      consumedPendingPromptRef.current = true;
      const pendingPrompt = consumePendingFredPrompt();
      if (pendingPrompt !== null) {
        runAgent(pendingPrompt);
      }
    }, 0);

    return () => window.clearTimeout(timer);
  }, [chat.isPending, runAgent]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    runAgent(draft);
  }

  const visibleDraft = speech.listening && speech.transcript ? speech.transcript : draft;

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

      <form className="mt-3 flex gap-2" onSubmit={handleSubmit}>
        <input
          className="min-w-0 flex-1 rounded-full border border-subtle bg-void px-4 py-2.5 text-sm text-primary outline-none placeholder:text-faint focus:border-accent"
          onChange={(event) => setDraft(event.target.value)}
          placeholder="ask fred to find sites"
          value={visibleDraft}
        />
        {speech.supported ? (
          <button
            aria-label={speech.listening ? "stop voice input" : "start voice input"}
            className="rounded-full border border-subtle px-3 py-2.5 text-xs lowercase text-dim transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
            disabled={chat.isPending}
            onClick={speech.toggle}
            type="button"
          >
            {speech.listening ? "stop" : "voice"}
          </button>
        ) : null}
        <button
          className="rounded-full bg-accent px-4 py-2.5 text-sm font-medium text-accent-contrast transition-opacity disabled:opacity-40"
          disabled={chat.isPending || !visibleDraft.trim()}
          type="submit"
        >
          Send
        </button>
      </form>
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
