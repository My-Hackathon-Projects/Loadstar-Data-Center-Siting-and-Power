import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { TECH_SECTIONS, type TechSection } from "./content";

const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

const PIPELINE = [
  { label: "data", sub: "public sources" },
  { label: "pipeline", sub: "ingest + features" },
  { label: "engine", sub: "score + optimize" },
  { label: "api", sub: "fastapi" },
  { label: "console", sub: "react + deck.gl" },
];

function ArchitectureDiagram() {
  const width = 150;
  const gap = 36;
  const top = 24;
  const height = 56;
  const x = (index: number) => index * (width + gap);
  const agentX = x(3);
  const agentY = 150;

  return (
    <svg
      className="mt-6 w-full"
      role="img"
      aria-label="Loadstar architecture: data to pipeline to engine to api to console, with the agent on the api."
      viewBox="0 0 922 220"
    >
      {PIPELINE.map((node, index) => (
        <g key={node.label}>
          <rect
            className="fill-panel stroke-subtle"
            height={height}
            rx={12}
            width={width}
            x={x(index)}
            y={top}
          />
          <text
            className="fill-primary"
            fontSize="15"
            textAnchor="middle"
            x={x(index) + width / 2}
            y={top + 26}
          >
            {node.label}
          </text>
          <text
            className="fill-dim"
            fontSize="11"
            textAnchor="middle"
            x={x(index) + width / 2}
            y={top + 44}
          >
            {node.sub}
          </text>
          {index < PIPELINE.length - 1 ? (
            <line
              className="stroke-dim"
              strokeWidth={1.5}
              x1={x(index) + width}
              x2={x(index + 1)}
              y1={top + height / 2}
              y2={top + height / 2}
            />
          ) : null}
        </g>
      ))}

      <line
        className="stroke-accent"
        strokeWidth={1.5}
        x1={agentX + width / 2}
        x2={agentX + width / 2}
        y1={top + height}
        y2={agentY}
      />
      <rect
        className="fill-panel stroke-accent"
        height={44}
        rx={12}
        width={width}
        x={agentX}
        y={agentY}
      />
      <text
        className="fill-accent"
        fontSize="15"
        textAnchor="middle"
        x={agentX + width / 2}
        y={agentY + 27}
      >
        fred · agent
      </text>
    </svg>
  );
}

function Section({ section }: { section: TechSection }) {
  return (
    <motion.section
      className="border-t border-subtle py-12"
      initial={{ opacity: 0, y: 24 }}
      transition={{ duration: 0.7, ease: EASE_OUT }}
      viewport={{ once: true, margin: "-80px" }}
      whileInView={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-baseline gap-4">
        <span className="text-sm tabular-nums text-faint">{section.number}</span>
        <p className="eyebrow">{section.eyebrow}</p>
      </div>
      <h2 className="mt-4 max-w-2xl text-2xl font-light leading-snug text-primary sm:text-3xl">
        {section.title}
      </h2>
      <div className="mt-4 max-w-2xl space-y-3 text-dim">
        {section.body.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>
      {section.sources ? (
        <dl className="mt-6 grid max-w-3xl gap-2 sm:grid-cols-2">
          {section.sources.map((source) => (
            <div
              className="rounded-lg border border-subtle px-3 py-2"
              key={source.name}
            >
              <dt className="text-sm text-primary">{source.name}</dt>
              <dd className="text-xs text-dim">{source.role}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {section.number === "05" ? <ArchitectureDiagram /> : null}
    </motion.section>
  );
}

export default function BehindTheTech() {
  return (
    <main className="min-h-screen bg-void px-6 py-16 text-primary">
      <div className="mx-auto max-w-3xl">
        <header className="flex items-center justify-between">
          <div>
            <p className="eyebrow">behind the tech</p>
            <h1 className="mt-2 text-3xl font-light text-primary">
              How Loadstar finds and powers a site.
            </h1>
          </div>
          <Link
            className="text-xs lowercase tracking-wide text-dim transition-colors hover:text-primary"
            to="/app"
          >
            ‹ console
          </Link>
        </header>

        <div className="mt-8">
          {TECH_SECTIONS.map((section) => (
            <Section key={section.number} section={section} />
          ))}
        </div>

        <footer className="border-t border-subtle py-12 text-sm text-dim">
          <Link className="transition-colors hover:text-accent" to="/thanks">
            end the journey ›
          </Link>
        </footer>
      </div>
    </main>
  );
}
