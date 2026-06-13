import { FormEvent, useState } from "react";

import { useUiStore } from "../../hooks/useUiStore";
import {
  formatCarbon,
  formatEurPerMwh,
  formatMw,
  formatPercent,
} from "../../lib/formatters";
import { useSiteDetail } from "../../lib/queries";

interface ChatMessage {
  body: string;
  speaker: "assistant" | "user";
}

export function ChatPanel() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      body: "Ask for a deterministic explanation of the selected site, ranking factors, or optimizer next step.",
      speaker: "assistant",
    },
  ]);
  const powerMw = useUiStore((state) => state.powerMw);
  const selectedCellId = useUiStore((state) => state.selectedCellId);
  const workloadType = useUiStore((state) => state.workloadType);
  const detail = useSiteDetail(selectedCellId);
  const site = detail.data?.site;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message) {
      return;
    }
    setMessages((current) => [
      ...current,
      { body: message, speaker: "user" },
      {
        body: site
          ? siteExplanation(site.region_name, powerMw, workloadType, {
              carbon: formatCarbon(site.carbon_intensity_g_kwh),
              headroom: formatMw(site.headroom_mw),
              land: formatPercent(site.buildable_fraction),
              ml: formatPercent(site.lightgbm_score),
              price: formatEurPerMwh(site.mean_price_eur_mwh),
            })
          : "Select a ranked cell first so the explanation can use site detail data.",
        speaker: "assistant",
      },
    ]);
    setDraft("");
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-base font-semibold">Chat</h2>
      <div className="mt-3 grid max-h-56 gap-2 overflow-y-auto">
        {messages.map((message, index) => (
          <p
            className={`rounded-md px-3 py-2 text-sm ${
              message.speaker === "assistant"
                ? "bg-slate-100 text-slate-700"
                : "bg-cyan-700 text-white"
            }`}
            key={`${message.speaker}-${index}`}
          >
            {message.body}
          </p>
        ))}
      </div>
      <form className="mt-3 flex gap-2" onSubmit={handleSubmit}>
        <input
          className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900"
          placeholder="Explain this site"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button
          className="rounded-md bg-cyan-700 px-3 py-2 text-sm font-medium text-white"
          type="submit"
        >
          Send
        </button>
      </form>
    </section>
  );
}

interface SiteExplanationFacts {
  carbon: string;
  headroom: string;
  land: string;
  ml: string;
  price: string;
}

function siteExplanation(
  regionName: string,
  powerMw: number,
  workloadType: string,
  facts: SiteExplanationFacts,
): string {
  return `${regionName} is being evaluated for ${formatMw(powerMw)} ${workloadType}. Key facts: ${facts.headroom} headroom, ${facts.price}, ${facts.carbon}, ${facts.land} buildable land, and ${facts.ml} ML viability. Use the Pareto panel to inspect cost/carbon tradeoffs for this selected cell.`;
}
