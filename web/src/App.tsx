// Star Builder (Phase 1): pick a mass and [Fe/H] from the exported grid and scrub a star's life.
// Every number shown comes from web/public/data, written by `python -m stellarforge.export web`;
// this file only selects, scales and draws.

import { useEffect, useMemo, useRef, useState } from "react";
import { parseDocument } from "./data/loader";
import type { Provenance, StellarDocument, Track } from "./data/types";
import { starDisplayCss } from "./rendering/starColour";

const DATA = `${import.meta.env.BASE_URL}data/`;
const FIRST_FILE = "tracks_feh_+0.0.json";
const SUN_AGE_YR = 4.57e9; // where the first star opens: the Sun today

const cache = new Map<string, Promise<StellarDocument>>();
function load(file: string): Promise<StellarDocument> {
  if (!cache.has(file)) {
    cache.set(file, fetch(DATA + file).then((r) => {
      if (!r.ok) throw new Error(`${file}: HTTP ${r.status}; run \`make export\``);
      return r.json();
    }).then(parseDocument));
  }
  return cache.get(file)!;
}

/** Slider steps go one [Fe/H] at a time, so the neighbours are fetched ahead (a first load takes ~60 ms).
 * Files more than two steps away are dropped, so a full sweep does not keep all 46 grids in memory. */
function prefetchAround({ grid }: StellarDocument) {
  const k = grid.feh_values.indexOf(grid.feh);
  for (const file of cache.keys()) {
    if (Math.abs(grid.files.indexOf(file) - k) > 2) cache.delete(file);
  }
  for (const file of [grid.files[k - 1], grid.files[k + 1]]) {
    if (file) load(file).catch(() => cache.delete(file));
  }
}

const fmt = (x: number, digits = 4) => x.toPrecision(digits);

export default function App() {
  const [doc, setDoc] = useState<StellarDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [massIndex, setMassIndex] = useState<number | null>(null);
  const [point, setPoint] = useState(0);
  // The [Fe/H] file asked for last; a slower, older request must not replace it when it lands
  const wanted = useRef(FIRST_FILE);

  useEffect(() => {
    load(FIRST_FILE).then((d) => {
      const sun = d.grid.mass_values_msun.indexOf(1);
      setDoc(d);
      prefetchAround(d);
      setMassIndex(sun);
      setPoint(Math.max(0, d.grid.tracks[sun].age_yr.findIndex((a) => a >= SUN_AGE_YR)));
    }, (e: Error) => setError(e.message));
  }, []);

  if (error) return <main><p role="alert">{error}</p></main>;
  if (!doc || massIndex === null) return <main><p>Loading tracks…</p></main>;

  const { grid } = doc;
  const track = grid.tracks[massIndex];
  const i = Math.min(point, track.age_yr.length - 1);
  const fehIndex = grid.feh_values.indexOf(grid.feh);

  const pickFeh = (k: number) => {
    const file = (wanted.current = grid.files[k]);
    load(file).then((d) => {
      if (wanted.current !== file) return;
      setDoc(d);
      prefetchAround(d);
    }, (e: Error) => setError(e.message));
  };

  return (
    <main className="builder">
      <header>
        <h1>Star Builder</h1>
        <p className="source">{doc.meta.dataset}</p>
      </header>

      <section className="controls" aria-label="Star">
        <label>
          Initial mass <output>{fmt(track.mass_msun)} M☉</output>
          <input type="range" min={0} max={grid.mass_values_msun.length - 1} value={massIndex}
            onChange={(e) => setMassIndex(Number(e.target.value))} />
        </label>
        <label>
          [Fe/H] <output>{grid.feh.toFixed(1)}</output>
          <input type="range" min={0} max={grid.feh_values.length - 1} value={fehIndex}
            onChange={(e) => pickFeh(Number(e.target.value))} />
        </label>
        <label>
          Age <output>{(track.age_yr[i] / 1e9).toPrecision(6)} Gyr</output>
          <input type="range" min={0} max={track.age_yr.length - 1} value={i}
            onChange={(e) => setPoint(Number(e.target.value))} />
        </label>
      </section>

      <div className="views">
        <HrDiagram track={track} point={i} />
        <StarDisc track={track} point={i} />
      </div>

      <PhaseTimeline track={track} point={i} onPick={setPoint} />
      <Numbers track={track} point={i} />
    </main>
  );
}

function HrDiagram({ track, point }: { track: Track; point: number }) {
  const W = 460, H = 340, PAD = 44;
  const { x, y, path, xTicks, yTicks } = useMemo(() => {
    const extent = (v: number[]) => {
      const lo = Math.min(...v), hi = Math.max(...v), pad = Math.max(0.05, (hi - lo) * 0.06);
      return [lo - pad, hi + pad];
    };
    const [t0, t1] = extent(track.log_teff_k);
    const [l0, l1] = extent(track.log_l_lsun);
    // Hot stars on the left, as in every HR diagram
    const x = (t: number) => PAD + ((t1 - t) / (t1 - t0)) * (W - PAD - 10);
    const y = (l: number) => 10 + ((l1 - l) / (l1 - l0)) * (H - PAD - 10);
    const ticks = (a: number, b: number) => {
      const step = [0.1, 0.2, 0.5, 1, 2].find((s) => (b - a) / s <= 7) ?? 5;
      const out = [];
      for (let v = Math.ceil(a / step) * step; v <= b; v += step) out.push(+v.toFixed(2));
      return out;
    };
    const path = track.log_teff_k.map((t, k) => `${k ? "L" : "M"}${x(t).toFixed(1)},${y(track.log_l_lsun[k]).toFixed(1)}`).join("");
    return { x, y, path, xTicks: ticks(t0, t1), yTicks: ticks(l0, l1) };
  }, [track]);

  return (
    <svg className="hr" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Hertzsprung–Russell diagram of the track">
      <rect x={PAD} y={10} width={W - PAD - 10} height={H - PAD - 10} className="frame" />
      {xTicks.map((t) => (
        <text key={`x${t}`} x={x(t)} y={H - PAD + 16} textAnchor="middle">{t}</text>
      ))}
      {yTicks.map((l) => (
        <text key={`y${l}`} x={PAD - 6} y={y(l) + 4} textAnchor="end">{l}</text>
      ))}
      <text x={(W + PAD) / 2} y={H - 6} textAnchor="middle">log T_eff (K)</text>
      <text transform={`translate(12 ${(H - PAD) / 2}) rotate(-90)`} textAnchor="middle">log L (L☉)</text>
      <path d={path} className="track" />
      <circle cx={x(track.log_teff_k[point])} cy={y(track.log_l_lsun[point])} r={6}
        fill={starDisplayCss(track.rgb[point])} stroke="#fff" />
    </svg>
  );
}

function StarDisc({ track, point }: { track: Track; point: number }) {
  // Display scale only: log radius maps to pixels, clamped to the panel
  const size = Math.min(220, Math.max(6, 60 * 2 ** (track.log_r_rsun[point] * 1.2)));
  const colour = starDisplayCss(track.rgb[point]);
  return (
    <div className="disc-panel">
      <div className="star" role="img" aria-label="The star, coloured and sized by its exported values"
        style={{ width: size, height: size, background: colour, boxShadow: `0 0 ${size / 3}px ${size / 8}px ${colour}` }} />
      <p className="note">Size on a log scale; colour boosted for legibility</p>
    </div>
  );
}

const PHASE_COLOURS: Record<string, string> = {
  "-1": "#6b5b95", "0": "#3f7fbf", "2": "#d9822b", "3": "#c4a000", "4": "#b5523b",
  "5": "#8c2f39", "6": "#9aa0a6", "9": "#2a9d8f",
};

function PhaseTimeline({ track, point, onPick }: { track: Track; point: number; onPick: (k: number) => void }) {
  const names = track.phase_names;
  const runs: { phase: number; start: number; end: number }[] = [];
  track.phase.forEach((p, k) => {
    const last = runs[runs.length - 1];
    if (last && last.phase === p) last.end = k;
    else runs.push({ phase: p, start: k, end: k });
  });
  const n = track.phase.length;
  return (
    <section aria-label="Phases" className="timeline">
      <div className="bar">
        {runs.map((r) => (
          <button key={r.start} title={names[r.phase]} onClick={() => onPick(r.start)}
            style={{ flexGrow: r.end - r.start + 1, background: PHASE_COLOURS[r.phase] ?? "#555" }}>
            {(r.end - r.start + 1) / n > 0.12 ? names[r.phase] : ""}
          </button>
        ))}
        <span className="cursor" style={{ left: `${(100 * (point + 0.5)) / n}%` }} />
      </div>
      <p className="note">Widths follow evolutionary stages (MIST EEPs), not time.</p>
    </section>
  );
}

function Label({ p }: { p: Provenance }) {
  return <span className={`prov prov-${p}`}>{p}</span>;
}

function Numbers({ track, point }: { track: Track; point: number }) {
  const fp = track.field_provenance;
  const names = track.phase_names;
  const rows: [string, string, Provenance][] = [
    ["Age", `${(track.age_yr[point] / 1e9).toPrecision(6)} Gyr`, fp.age_yr],
    ["Phase", names[track.phase[point]] ?? String(track.phase[point]), fp.phase],
    ["Mass now", `${fmt(track.mass_now_msun[point])} M☉`, fp.mass_now_msun],
    ["log L", `${track.log_l_lsun[point]} L☉`, fp.log_l_lsun],
    ["log T_eff", `${track.log_teff_k[point]} K`, fp.log_teff_k],
    ["log R", `${track.log_r_rsun[point]} R☉`, fp.log_r_rsun],
    ["Colour (sRGB)", track.rgb[point].join(", "), fp.rgb],
  ];
  return (
    <section aria-label="Values" className="numbers">
      <dl>
        {rows.map(([name, value, p]) => (
          <div key={name}><dt>{name}</dt><dd>{value} <Label p={p} /></dd></div>
        ))}
        <div><dt>Track</dt><dd>{track.method}</dd></div>
        <div><dt>Track ends at</dt><dd>{track.ending}</dd></div>
        {track.flags.length > 0 && <div><dt>Warnings</dt><dd className="flags">{track.flags.join("; ")}</dd></div>}
      </dl>
    </section>
  );
}
