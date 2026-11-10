// Experiments (Phase 3): the results of `python -m stellarforge.experiments all --export`, read from
// web/public/data/experiments. Heatmaps, curves and tables; hovering shows each cell's value, or the
// word that replaces it, and its provenance. Nothing here computes a physical value: colour scales,
// axes and log scaling are display only.

import { useEffect, useMemo, useRef, useState } from "react";
import { parseDocument } from "./data/loader";
import type { Experiment, Meta, Panel, PanelRow, Provenance } from "./data/types";

const DATA = `${import.meta.env.BASE_URL}data/experiments/`;
/** The six Phase 3 experiments, in the order the tabs show them. */
const NAMES = ["lifetime-map", "full-life-map", "remnant-map", "remnant-mass-curves", "population", "sun-metallicities"];

// Display colours for words that stand in for numbers
const WORD_COLOURS: Record<string, string> = {
  "white dwarf": "#e8e4d8", "neutron star": "#5b8def", "black hole": "#111111", none: "#d94f3d",
  "not yet": "#6fae5c", "not predicted": "#555a66", "track incomplete": "#555a66",
  "still on the main sequence": "#6fae5c",
};
const CURVE_COLOURS = ["#8fa8ff", "#f0b08a", "#8ad8f0", "#f0d58a", "#c9a0f0", "#9be0a8", "#f08aa8", "#e0e0e0", "#a0c0f0", "#f0c0a0"];
// Viridis, as five stops; colours between them are blended linearly
const SCALE = [[68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37]];

function scaleColour(t: number): string {
  const x = Math.min(1, Math.max(0, t)) * (SCALE.length - 1);
  const i = Math.min(SCALE.length - 2, Math.floor(x));
  const f = x - i;
  const c = SCALE[i].map((a, k) => Math.round(a + (SCALE[i + 1][k] - a) * f));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

const fmt = (v: number) => (Math.abs(v) >= 1e4 || Math.abs(v) < 1e-2 ? v.toExponential(3) : v.toPrecision(4));

function cellText(row: PanelRow, k: number, unit: string): string {
  const word = row.labels[k];
  const value = row.values[k];
  return word ?? (value === null ? "—" : `${fmt(value)} ${unit}`.trim());
}

export default function Experiments() {
  const [name, setName] = useState(NAMES[0]);
  const [docs, setDocs] = useState<Record<string, { meta: Meta; experiment: Experiment } | string>>({});

  useEffect(() => {
    if (docs[name]) return;
    fetch(DATA + name + ".json")
      .then((r) => {
        if (!r.ok) throw new Error(`${name}: HTTP ${r.status}; run \`make experiments\``);
        return r.json();
      })
      .then((raw) => {
        const { meta, experiment } = parseDocument(raw);
        if (!experiment) throw new Error(`${name} holds no experiment`);
        setDocs((d) => ({ ...d, [name]: { meta, experiment } }));
      })
      .catch((e: Error) => setDocs((d) => ({ ...d, [name]: e.message })));
  }, [name, docs]);

  const doc = docs[name];
  return (
    <main className="experiments">
      <header>
        <h1>Experiments</h1>
        <nav className="subtabs" aria-label="Experiments">
          {NAMES.map((n) => (
            <button key={n} aria-pressed={n === name} onClick={() => setName(n)}>{n}</button>
          ))}
        </nav>
      </header>
      {doc === undefined && <p>Loading…</p>}
      {typeof doc === "string" && <p role="alert">{doc}</p>}
      {typeof doc === "object" && (
        <>
          <h2>{doc.experiment.title}</h2>
          <p>{doc.experiment.summary}</p>
          <p className="source">
            {doc.meta.dataset} · {Object.values(doc.meta.models).join(" · ")} · code {doc.meta.generator.git_commit}
            {doc.meta.seed !== null && ` · seed ${doc.meta.seed}`}
          </p>
          {doc.experiment.panels.map((p) => (
            <section key={p.title} className="panel" aria-label={p.title}>
              <h3>{p.title}</h3>
              {p.kind === "heatmap" && <Heatmap panel={p} />}
              {p.kind === "curves" && <Curves panel={p} />}
              {p.kind === "table" && <Table panel={p} />}
            </section>
          ))}
        </>
      )}
    </main>
  );
}

function ProvenanceTag({ p }: { p: Provenance | null }) {
  return p ? <span className={`prov prov-${p}`}>{p}</span> : null;
}

/** Log or linear position of v between lo and hi, 0-1 (display scaling). */
function share(v: number, lo: number, hi: number, log: boolean): number {
  return log ? Math.log(v / lo) / Math.log(hi / lo) : (v - lo) / (hi - lo || 1);
}

function Heatmap({ panel }: { panel: Panel }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState<{ row: number; col: number } | null>(null);
  const rows = panel.rows;
  const cols = panel.x_values.length;
  const numbers = rows.flatMap((r) => r.values.filter((v, k): v is number => v !== null && r.labels[k] === null && (!panel.log_values || v > 0)));
  const lo = Math.min(...numbers), hi = Math.max(...numbers);
  const words = [...new Set(rows.flatMap((r) => r.labels.filter((w): w is string => w !== null)))];
  // Rows are stored from the lowest [Fe/H] up; the highest is drawn at the top
  const W = 800, CELL_H = Math.max(6, Math.round(320 / rows.length));
  const H = CELL_H * rows.length;

  useEffect(() => {
    const ctx = ref.current!.getContext("2d")!;
    const cw = W / cols;
    rows.forEach((r, i) => {
      const top = H - (i + 1) * CELL_H;
      r.values.forEach((v, k) => {
        const word = r.labels[k];
        ctx.fillStyle = word ? WORD_COLOURS[word] ?? "#777" : v === null ? "#222" : scaleColour(share(v, lo, hi, panel.log_values));
        ctx.fillRect(k * cw, top, Math.ceil(cw), CELL_H);
      });
    });
  }, [rows, cols, H, CELL_H, lo, hi, panel.log_values]);

  const pick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const col = Math.floor(((e.clientX - box.left) / box.width) * cols);
    const row = rows.length - 1 - Math.floor(((e.clientY - box.top) / box.height) * rows.length);
    setHover(col >= 0 && col < cols && row >= 0 && row < rows.length ? { row, col } : null);
  };
  const xTicks = panel.log_x ? [0.1, 1, 10, 100].filter((t) => t >= panel.x_values[0] && t <= panel.x_values[cols - 1]) : [];

  return (
    <div className="heatmap">
      <div className="heat-plot">
        <span className="y-axis">{panel.y_label}: {rows[0].label} (bottom) to {rows[rows.length - 1].label} (top)</span>
        <canvas ref={ref} width={W} height={H} onMouseMove={pick} onMouseLeave={() => setHover(null)}
          aria-label={`${panel.title}: heatmap of ${panel.value_label} against ${panel.x_label} and ${panel.y_label}`} />
        <div className="x-ticks">
          {xTicks.map((t) => (
            <span key={t} style={{ left: `${share(t, panel.x_values[0], panel.x_values[cols - 1], true) * 100}%` }}>{t}</span>
          ))}
        </div>
        <span className="x-axis">{panel.x_label}</span>
      </div>
      <p className="readout" aria-live="polite">
        {hover ? (
          <>
            {panel.y_label} {rows[hover.row].label}, {panel.x_label.replace(/ \(.*\)$/, "")} {fmt(panel.x_values[hover.col])}:{" "}
            <strong>{cellText(rows[hover.row], hover.col, panel.value_label)}</strong>{" "}
            {rows[hover.row].labels[hover.col] && rows[hover.row].values[hover.col] !== null && `(${fmt(rows[hover.row].values[hover.col]!)} ${panel.value_label}) `}
            <ProvenanceTag p={rows[hover.row].provenance[hover.col]} />
          </>
        ) : "Hover over a cell for its value and provenance."}
      </p>
      <div className="legend">
        {numbers.length > 0 && (
          <span className="gradient">
            {fmt(lo)} <span className="bar" style={{ background: `linear-gradient(to right, ${[0, 0.25, 0.5, 0.75, 1].map(scaleColour).join(", ")})` }} /> {fmt(hi)} {panel.value_label}{panel.log_values && " (log scale)"}
          </span>
        )}
        {words.map((w) => (
          <span key={w}><i style={{ background: WORD_COLOURS[w] ?? "#777" }} />{w}</span>
        ))}
      </div>
    </div>
  );
}

function Curves({ panel }: { panel: Panel }) {
  const W = 800, H = 320, PAD = 50;
  const [hover, setHover] = useState<number | null>(null);
  const xs = panel.x_values;
  const { x, y, paths, yTicks } = useMemo(() => {
    const finite = panel.rows.flatMap((r) => r.values.filter((v): v is number => v !== null && (!panel.log_values || v > 0)));
    const lo = Math.min(...finite), hi = Math.max(...finite);
    const x = (v: number) => PAD + share(v, xs[0], xs[xs.length - 1], panel.log_x) * (W - PAD - 10);
    const y = (v: number) => 10 + (1 - share(v, lo, hi, panel.log_values)) * (H - PAD - 10);
    const paths = panel.rows.map((r) => {
      let d = "";
      let pen = false;
      r.values.forEach((v, k) => {
        if (v === null || (panel.log_values && v <= 0)) { pen = false; return; }   // a gap: no value
        d += `${pen ? "L" : "M"}${x(xs[k]).toFixed(1)},${y(v).toFixed(1)}`;
        pen = true;
      });
      return d;
    });
    const yTicks = panel.log_values
      ? [0.01, 0.1, 1, 10, 100, 1000].filter((t) => t >= lo && t <= hi)
      : [0, 0.25, 0.5, 0.75, 1].map((f) => lo + f * (hi - lo));
    return { x, y, paths, yTicks };
  }, [panel, xs]);

  const pick = (e: React.MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * W;
    let best = 0;
    xs.forEach((v, k) => { if (Math.abs(x(v) - px) < Math.abs(x(xs[best]) - px)) best = k; });
    setHover(best);
  };

  return (
    <div className="curves">
      <svg viewBox={`0 0 ${W} ${H}`} className="curve-plot" onMouseMove={pick} onMouseLeave={() => setHover(null)}
        role="img" aria-label={`${panel.title}: ${panel.y_label} against ${panel.x_label}`}>
        <rect x={PAD} y={10} width={W - PAD - 10} height={H - PAD - 10} className="frame" />
        {yTicks.map((t) => <text key={t} x={PAD - 6} y={y(t) + 4} textAnchor="end">{fmt(t)}</text>)}
        <text x={PAD} y={H - PAD + 16} textAnchor="middle">{fmt(xs[0])}</text>
        <text x={W - 10} y={H - PAD + 16} textAnchor="end">{fmt(xs[xs.length - 1])}</text>
        <text x={(W + PAD) / 2} y={H - 8} textAnchor="middle">{panel.x_label}</text>
        <text transform={`translate(12 ${(H - PAD) / 2}) rotate(-90)`} textAnchor="middle">{panel.y_label}</text>
        {paths.map((d, k) => <path key={k} d={d} fill="none" stroke={CURVE_COLOURS[k % CURVE_COLOURS.length]} strokeWidth={1.4} />)}
        {hover !== null && <line x1={x(xs[hover])} x2={x(xs[hover])} y1={10} y2={H - PAD} className="cursor-line" />}
      </svg>
      <ul className="curve-legend">
        {panel.rows.map((r, k) => (
          <li key={r.label}>
            <i style={{ background: CURVE_COLOURS[k % CURVE_COLOURS.length] }} />{r.label}
            {hover !== null && <>: <strong>{cellText(r, hover, panel.value_label)}</strong> <ProvenanceTag p={r.provenance[hover]} /></>}
          </li>
        ))}
      </ul>
      <p className="readout">{hover !== null ? `${panel.x_label} ${fmt(xs[hover])}` : "Hover over the plot for each curve's value and provenance."}</p>
    </div>
  );
}

function Table({ panel }: { panel: Panel }) {
  return (
    <table className="result-table">
      <thead>
        <tr><th />{panel.columns.map((c) => <th key={c} scope="col">{c}</th>)}</tr>
      </thead>
      <tbody>
        {panel.rows.map((r) => (
          <tr key={r.label}>
            <th scope="row">{r.label}</th>
            {panel.columns.map((c, k) => (
              <td key={c}>
                {c.includes("sRGB") && r.labels[k] && <i className="swatch" style={{ background: `rgb(${r.labels[k]!.split(",").map((v) => Math.round(Number(v) * 255)).join(",")})` }} />}
                {cellText(r, k, "")} <ProvenanceTag p={r.provenance[k]} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
