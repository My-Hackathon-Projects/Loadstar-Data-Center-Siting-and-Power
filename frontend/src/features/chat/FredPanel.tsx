import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";

import { useUiStore } from "../../hooks/useUiStore";
import {
  consumePendingAgentHandoff,
  type FredHandoff,
} from "../../lib/fredHandoff";
import { consumePendingFredPrompt } from "../../lib/fredPrompt";
import { useChatAgent } from "../../lib/queries";
import type { AgentChatRequest, AgentChatResponse } from "../../types/api";
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
  const [inputValue, setInputValue] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const initializedRef = useRef(false);

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

  /**
   * Apply the search action returned by `/agent/chat` to the dashboard. Lifted
   * out of `runAgent` so the mount-time handoff path can reuse it without
   * round-tripping the network.
   */
  const applySearchAction = useCallback(
    (response: AgentChatResponse) => {
      if (response.action.type !== "search" || !response.action.applied) {
        return;
      }
      const applied = response.action.applied;
      setSearchParams({
        countryFilter: applied.country_filter ?? [],
        powerMw: applied.power_mw,
        topK: applied.top_k,
        weights: applied.weights,
        workloadType: applied.workload_type,
      });
      if (response.action.focus_cell_id) {
        setSelectedCellId(response.action.focus_cell_id);
      }
    },
    [setSearchParams, setSelectedCellId],
  );

  const runAgent = useCallback(
    (rawMessage: string) => {
      const message = rawMessage.trim();
      if (!message || chat.isPending) {
        return;
      }

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
          onError: () => {
            append({
              body: "That did not go through. Try again, or adjust the specifications on the left.",
              source: "template",
              speaker: "assistant",
            });
          },
          onSuccess: (response) => {
            append({
              body: response.message,
              model: response.model,
              source: response.source,
              speaker: "assistant",
            });
            applySearchAction(response);
          },
        },
      );
    },
    [
      append,
      applySearchAction,
      chat,
      messages,
      powerMw,
      selectedCellId,
      workloadType,
    ],
  );

  /**
   * Mount: pull whatever the landing screen left for us. A successful handoff
   * seeds both turns of the conversation and applies the search action without
   * re-calling the agent. An error fallback (raw prompt) re-runs the agent
   * once. Otherwise the panel stays idle on the INTRO message.
   */
  useEffect(() => {
    if (initializedRef.current) {
      return;
    }
    initializedRef.current = true;

    const handoff: FredHandoff | null = consumePendingAgentHandoff();
    if (handoff !== null) {
      setMessages((current) => [
        ...current,
        { body: handoff.userMessage, speaker: "user" },
        {
          body: handoff.response.message,
          model: handoff.response.model,
          source: handoff.response.source,
          speaker: "assistant",
        },
      ]);
      requestAnimationFrame(() => {
        listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
      });
      applySearchAction(handoff.response);
      return;
    }

    const pendingPrompt = consumePendingFredPrompt();
    if (pendingPrompt !== null) {
      runAgent(pendingPrompt);
    }
  }, [applySearchAction, runAgent]);

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!inputValue.trim() || chat.isPending) {
        return;
      }
      runAgent(inputValue);
      setInputValue("");
    },
    [chat.isPending, inputValue, runAgent],
  );

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key !== "Enter" || event.shiftKey) {
        return;
      }
      event.preventDefault();
      if (!inputValue.trim() || chat.isPending) {
        return;
      }
      runAgent(inputValue);
      setInputValue("");
    },
    [chat.isPending, inputValue, runAgent],
  );

  // Auto-grow the textarea up to ~5 lines.
  useEffect(() => {
    const node = inputRef.current;
    if (!node) {
      return;
    }
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 140)}px`;
  }, [inputValue]);

  return (
    <section className="flex h-full flex-col rounded-2xl border border-subtle bg-panel p-4">
      <div className="flex items-center gap-3">
        <div
          aria-hidden
          className={`h-2 w-2 rounded-full transition-colors ${
            chat.isPending ? "bg-accent" : "bg-subtle"
          }`}
        />
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
            <span className="whitespace-pre-wrap">{message.body}</span>
          </div>
        ))}
        {chat.isPending ? (
          <p className="px-3 py-2 text-sm text-dim">Fred is thinking...</p>
        ) : null}
      </div>

      <form className="mt-3 flex items-end gap-2" onSubmit={handleSubmit}>
        <textarea
          aria-label="Message Fred"
          className="min-h-10 max-h-36 flex-1 resize-none rounded-2xl border border-subtle bg-void px-4 py-2.5 text-sm text-primary outline-none transition-colors focus:border-accent disabled:opacity-60"
          disabled={chat.isPending}
          onChange={(event) => setInputValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Fred about a site, a country, or the tradeoffs..."
          ref={inputRef}
          rows={1}
          value={inputValue}
        />
        <button
          className="rounded-full border border-strong px-4 py-2 text-xs lowercase tracking-wide text-primary transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
          disabled={chat.isPending || !inputValue.trim()}
          type="submit"
        >
          send
        </button>
      </form>
    </section>
  );
}

function sourceLabel(source: ExplainSource, model?: string | null): string {
  if (source === "openai") {
    return model ? `live · ${model}` : "live";
  }
  return "engine";
}
