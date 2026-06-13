import { FormEvent, useRef, useState } from "react";

import { useUiStore } from "../../hooks/useUiStore";
import { useChatAgent } from "../../lib/queries";
import { VoiceBars } from "../journey/VoiceBars";
import type { ExplainSource } from "./types";

interface ChatMessage {
  body: string;
  speaker: "assistant" | "user";
  source?: ExplainSource;
  model?: string | null;
}

const INTRO: ChatMessage = {
  body: "Hey, I'm Fred. Ask me to find sites — try \"cheapest site in Sweden\" or \"greenest 400 MW campus\". I run a real search and fly the map there.",
  speaker: "assistant",
};

export function FredPanel() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([INTRO]);
  const listRef = useRef<HTMLDivElement>(null);

  const powerMw = useUiStore((state) => state.powerMw);
  const workloadType = useUiStore((state) => state.workloadType);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const setSearchParams = useUiStore((state) => state.setSearchParams);
  const setSelectedCellId = useUiStore((state) => state.setSelectedCellId);
  const chat = useChatAgent();

  function append(message: ChatMessage) {
    setMessages((current) => [...current, message]);
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || chat.isPending) {
      return;
    }
    setDraft("");
    append({ body: message, speaker: "user" });
    chat.mutate(
      {
        message,
        power_mw: powerMw,
        workload_type: workloadType,
        selected_cell_id: selectedCellId,
      },
      {
        onSuccess: (response) => {
          append({
            body: response.message,
            speaker: "assistant",
            source: response.source,
            model: response.model,
          });
          // Apply the agent's action to the dashboard: the store change drives
          // the existing search query, the map fly-to, and the stat strip.
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
          append({
            body: "That search did not go through. Try again, or adjust the specifications on the left.",
            speaker: "assistant",
            source: "template",
          });
        },
      },
    );
  }

  return (
    <section className="flex h-full flex-col rounded-2xl border border-subtle bg-panel p-4">
      <div className="flex items-center gap-3">
        <VoiceBars active={chat.isPending} bars={6} />
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
          <p className="px-3 py-2 text-sm text-dim">Fred is searching...</p>
        ) : null}
      </div>

      <form className="mt-3 flex gap-2" onSubmit={handleSubmit}>
        <input
          className="min-w-0 flex-1 rounded-full border border-subtle bg-void px-4 py-2.5 text-sm text-primary outline-none placeholder:text-faint focus:border-accent"
          onChange={(event) => setDraft(event.target.value)}
          placeholder="ask fred to find sites"
          value={draft}
        />
        <button
          className="rounded-full bg-accent px-4 py-2.5 text-sm font-medium text-accent-contrast transition-opacity disabled:opacity-40"
          disabled={chat.isPending}
          type="submit"
        >
          Send
        </button>
      </form>
    </section>
  );
}

function sourceLabel(source: ExplainSource, model?: string | null): string {
  if (source === "openai") {
    return model ? `live · ${model}` : "live";
  }
  return "deterministic";
}
