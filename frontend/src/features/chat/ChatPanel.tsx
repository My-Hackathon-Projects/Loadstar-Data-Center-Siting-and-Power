import { FormEvent, useState } from "react";

import { useUiStore } from "../../hooks/useUiStore";
import { useExplainSite, useSiteDetail } from "../../lib/queries";
import type { ExplainSource } from "./types";

interface ChatMessage {
  body: string;
  speaker: "assistant" | "user";
  source?: ExplainSource;
  model?: string;
}

const INTRO_BODY =
  "Ask for an explanation of the selected site, ranking factors, or what to do next. " +
  "Live LLM when configured; deterministic template otherwise.";

export function ChatPanel() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { body: INTRO_BODY, speaker: "assistant" },
  ]);
  const powerMw = useUiStore((state) => state.powerMw);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const workloadType = useUiStore((state) => state.workloadType);
  const detail = useSiteDetail(selectedCellId);
  const site = detail.data?.site;
  const explain = useExplainSite();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message) {
      return;
    }
    setDraft("");
    if (!selectedCellId || !site) {
      setMessages((current) => [
        ...current,
        { body: message, speaker: "user" },
        {
          body: "Select a ranked cell first so the explanation can use site detail data.",
          speaker: "assistant",
          source: "template",
        },
      ]);
      return;
    }
    setMessages((current) => [...current, { body: message, speaker: "user" }]);
    explain.mutate(
      {
        cell_id: selectedCellId,
        power_mw: powerMw,
        workload_type: workloadType,
      },
      {
        onSuccess: (response) => {
          setMessages((current) => [
            ...current,
            {
              body: response.message,
              speaker: "assistant",
              source: response.source,
              model: response.model ?? undefined,
            },
          ]);
        },
        onError: () => {
          setMessages((current) => [
            ...current,
            {
              body: "Live explanation failed; rerunning the deterministic template.",
              speaker: "assistant",
              source: "template",
            },
          ]);
        },
      },
    );
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-base font-semibold">Chat</h2>
      <div className="mt-3 grid max-h-56 gap-2 overflow-y-auto">
        {messages.map((message, index) => (
          <div
            className={`rounded-md px-3 py-2 text-sm ${
              message.speaker === "assistant"
                ? "bg-slate-100 text-slate-700"
                : "bg-cyan-700 text-white"
            }`}
            key={`${message.speaker}-${index}`}
          >
            {message.speaker === "assistant" && message.source ? (
              <span className="mr-2 inline-flex rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                {sourcePillLabel(message.source, message.model)}
              </span>
            ) : null}
            <span>{message.body}</span>
          </div>
        ))}
        {explain.isPending ? (
          <p className="rounded-md bg-slate-100 px-3 py-2 text-sm text-slate-500">
            Generating explanation...
          </p>
        ) : null}
      </div>
      <form className="mt-3 flex gap-2" onSubmit={handleSubmit}>
        <input
          className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900"
          placeholder="Explain this site"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button
          className="rounded-md bg-cyan-700 px-3 py-2 text-sm font-medium text-white disabled:bg-slate-400"
          disabled={explain.isPending}
          type="submit"
        >
          Send
        </button>
      </form>
    </section>
  );
}

function sourcePillLabel(source: ExplainSource, model?: string): string {
  if (source === "openai") {
    return model ? `Live · ${model}` : "Live";
  }
  return "Deterministic template";
}
