// System Timeline (Phase 6): planets through their star's life. Reads web/public/data/planets/
// solar_system.json and the timeline_<nnn>.json files (`make planets`). The scrubber moves along
// the exported ages; between two exported ages the drawing is smoothed linearly along that one
// track. Nothing here computes a physical value: orbits, the star, the habitable zone, events and
// fates all come from the files.

import { useEffect, useMemo, useState } from "react";
import { parseDocument } from "./data/loader";
import type { Meta, PlanetClass, Population, Timeline, TimelinePlanet } from "./data/types";
import { CalibrationBadge } from "./Planets";

const DATA = `${import.meta.env.BASE_URL}data/`;
const SOLAR = "planets/solar_system.json";

/** Class colours, as in the Planets view (presentation only). */
const CLASS_COLOURS: Record<PlanetClass, string> = {
  "gas giant": "#e0a458", "ice giant": "#6fa8dc", "sub-Neptune": "#8fd3c6", "super-Earth": "#c58bd9", terrestrial: "#c9785a",
};

export interface TimelineTarget {
  file: string;
  index: number;
}

const cache = new Map<string, Promise<{ meta: Meta; timeline: Timeline }>>();
function loadTimeline(file: string) {
  if (!cache.has(file)) {
    cache.set(file, fetch(DATA + file).then((r) => {
      if (!r.ok) throw new Error(`${file}: HTTP ${r.status}; run \`make planets\``);
      return r.json();
    }).then((raw) => {
      const d = parseDocument(raw);
      if (!d.timeline) throw new Error(`${file} has no timeline block`);
      return { meta: d.meta, timeline: d.timeline };
    }));
    cache.get(file)!.catch(() => cache.delete(file));
  }
  return cache.get(file)!;
}

function useTimeline(file: string) {
  const [state, setState] = useState<{ file: string; value: { meta: Meta; timeline: Timeline } | string } | null>(null);
  useEffect(() => {
    let live = true;
    loadTimeline(file).catch((e: Error) => e.message).then((value) => { if (live) setState({ file, value }); });
    return () => { live = false; };
  }, [file]);
  return state?.file === file ? state.value : null;
}

export default function SystemTimeline({ target }: { target: TimelineTarget | null }) {
  const [source, setSource] = useState<TimelineTarget>(target ?? { file: SOLAR, index: 0 });
  // A new target from the Planets view replaces the current choice (adjusted while rendering)
  const [lastTarget, setLastTarget] = useState(target);
  if (target !== lastTarget) {
    setLastTarget(target);
    if (target) setSource(target);
  }
  const [population, setPopulation] = useState<Population | null>(null);
  useEffect(() => {
    fetch(DATA + "planets/population.json").then((r) => (r.ok ? r.json() : null))
      .then((raw) => setPopulation(raw ? parseDocument(raw).population ?? null : null))
      .catch(() => setPopulation(null));
  }, []);
  const doc = useTimeline(source.file);
  return (
    <main className="experiments">
      <header>
        <h1>System Timeline</h1>
        <p className="note">What happens to each planet as its star ages, swells, sheds mass and dies. Every orbit, edge and event is a model prediction from the files; the drawing only scales them.</p>
      </header>
      <Picker source={source} onPick={setSource} population={population} timeline={typeof doc === "object" && doc ? doc.timeline : null} />
      {doc === null && <p>Loading…</p>}
      {typeof doc === "string" && <p role="alert">{doc}</p>}
      {doc !== null && typeof doc === "object" && (
        <TimelineView key={`${source.file}:${source.index}`} meta={doc.meta} timeline={doc.timeline} index={source.index} />
      )}
    </main>
  );
}

function Picker({ source, onPick, population, timeline }: {
  source: TimelineTarget; onPick: (t: TimelineTarget) => void; population: Population | null; timeline: Timeline | null;
}) {
  const cells = population?.cells ?? [];
  const cell = cells.find((c) => c.timeline_file === source.file);
  const masses = population?.star_masses_msun ?? [], fehs = population?.feh_values ?? [];
  const mi = cell ? masses.indexOf(cell.m_star_msun) : masses.indexOf(1);
  const fi = cell ? fehs.indexOf(cell.feh) : fehs.indexOf(0);
  const pickCell = (m: number, f: number) => {
    const c = population && population.cells[f * masses.length + m];
    if (c) onPick({ file: c.timeline_file, index: 0 });
  };
  return (
    <section className="controls">
      <label>
        Systems
        <select value={source.file === SOLAR ? "solar" : "sample"} onChange={(e) => (e.target.value === "solar" ? onPick({ file: SOLAR, index: 0 }) : pickCell(Math.max(mi, 0), Math.max(fi, 0)))}>
          <option value="solar">Solar System (reference case)</option>
          <option value="sample" disabled={!population}>Phase 5 sample systems</option>
        </select>
      </label>
      {source.file !== SOLAR && population && mi >= 0 && fi >= 0 && (
        <>
          <label>
            Star mass
            <output>{masses[mi]} M☉</output>
            <input type="range" min={0} max={masses.length - 1} value={mi} onChange={(e) => pickCell(+e.target.value, fi)} />
          </label>
          <label>
            [Fe/H]
            <output>{fehs[fi] > 0 ? "+" : ""}{fehs[fi]}</output>
            <input type="range" min={0} max={fehs.length - 1} value={fi} onChange={(e) => pickCell(mi, +e.target.value)} />
          </label>
          {timeline && (
            <label>
              System
              <select value={source.index} onChange={(e) => onPick({ file: source.file, index: +e.target.value })}>
                {timeline.systems.filter((s) => s.planets.length > 0).map((s) => (
                  <option key={s.index} value={s.index}>{`${s.index}: ${s.planets.length} planet${s.planets.length > 1 ? "s" : ""}`}</option>
                ))}
              </select>
            </label>
          )}
          {cell && <CalibrationBadge label={cell.calibration} />}
        </>
      )}
    </section>
  );
}

/** Linear along the exported samples: the value at fractional sample position s. */
function along(values: number[], s: number): number {
  const i = Math.min(Math.floor(s), values.length - 1), j = Math.min(i + 1, values.length - 1);
  return values[i] + (values[j] - values[i]) * (s - i);
}

function alongNullable(values: (number | null)[], s: number): number | null {
  const i = Math.min(Math.floor(s), values.length - 1), j = Math.min(i + 1, values.length - 1);
  const a = values[i], b = values[j];
  if (a === null || b === null) return null;
  return a + (b - a) * (s - i);
}

/** The planet's orbit at sample position s, from its knots; null once it is gone. */
function orbitAt(p: TimelinePlanet, s: number): number | null {
  const k = p.orbit_sample;
  if (s > k[k.length - 1]) return null;
  let j = 0;
  while (j < k.length - 1 && k[j + 1] < s) j++;
  if (j === k.length - 1 || s <= k[0]) return p.orbit_a_au[j];
  const w = (s - k[j]) / (k[j + 1] - k[j]);
  return p.orbit_a_au[j] + (p.orbit_a_au[j + 1] - p.orbit_a_au[j]) * w;
}

const fmtAge = (yr: number) => (yr >= 1e9 ? `${(yr / 1e9).toFixed(3)} Gyr` : yr >= 1e6 ? `${(yr / 1e6).toFixed(2)} Myr` : `${yr.toPrecision(3)} yr`);
const css = ([r, g, b]: number[]) => `rgb(${Math.round(255 * r)}, ${Math.round(255 * g)}, ${Math.round(255 * b)})`;
const label = (p: TimelinePlanet, k: number) => p.name ?? `planet ${k + 1} (${p.class_at_formation})`;

function TimelineView({ meta, timeline, index }: { meta: Meta; timeline: Timeline; index: number }) {
  const star = timeline.star;
  const n = star.age_yr.length;
  const system = timeline.systems.find((s) => s.index === index) ?? timeline.systems[0];
  const planets = system.planets;
  const formedAt = planets.map((p) => p.events.find((e) => e.kind === "formed")?.age_yr ?? star.age_yr[0]);
  const [s, setS] = useState(() => Math.max(0, star.age_yr.findIndex((a) => a >= 4.57e9)));
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    let frame = 0, last = performance.now();
    const tick = (now: number) => {
      const step = ((now - last) / 1000) * 6;   // six exported samples per second
      last = now;
      setS((v) => {
        if (v + step >= n - 1) { setPlaying(false); return n - 1; }
        return v + step;
      });
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, n]);
  const age = along(star.age_yr, s);
  const i = Math.round(s);
  const events = useMemo(() => planets.flatMap((p, k) => p.events.map((e) => ({ ...e, who: label(p, k), k })))
    .sort((a, b) => a.age_yr - b.age_yr), [planets]);
  const jump = (yr: number) => {
    const j = star.age_yr.findIndex((a) => a >= yr);
    setS(j < 0 ? n - 1 : j);
  };
  const sizeOf = (p: TimelinePlanet) => 2.5 + 1.4 * Math.log10(1 + p.mass_mearth);

  // Log scale in distance, star and orbits alike, so an engulfed orbit lies inside the drawn star
  const S = 460, c = S / 2, outer = c - 12;
  const A = [0.003, 300];
  const r = (a: number) => Math.max(0, ((Math.log10(a) - Math.log10(A[0])) / (Math.log10(A[1]) - Math.log10(A[0]))) * outer);
  const hzIn = alongNullable(star.hz_inner_au, s), hzOut = alongNullable(star.hz_outer_au, s);
  const radius = along(star.radius_au, s);
  return (
    <>
      <section>
        <h2>{timeline.name}{timeline.systems_file ? `, system ${system.index}` : ""}</h2>
        <div className="controls timeline-controls">
          <button onClick={() => setPlaying((p) => !p)}>{playing ? "Pause" : "Play"}</button>
          <label className="wide">
            Age
            <output>{fmtAge(age)}</output>
            <input type="range" min={0} max={n - 1} step={0.01} value={s} onChange={(e) => { setPlaying(false); setS(+e.target.value); }} />
          </label>
        </div>
        <dl className="cell-stats">
          <dt>Phase</dt><dd>{star.phase[i]}</dd>
          <dt>Star</dt><dd>{star.mass_msun[i]} M☉, {star.l_lsun[i]} L☉, {star.teff_k[i]} K, radius {star.radius_au[i]} AU<span className={`prov prov-${star.provenance}`}>{star.provenance}</span></dd>
          <dt>Habitable zone</dt><dd>{star.hz_inner_au[i] === null ? "not defined (Teff outside 2,600–7,200 K)" : `${star.hz_inner_au[i]}–${star.hz_outer_au[i]} AU`}<span className="prov prov-derived">derived</span></dd>
          <dt>Track</dt><dd>{star.method}; ends at {star.ending}</dd>
          {star.flags.length > 0 && <><dt>Track warnings</dt><dd className="flags" title="These apply somewhere along the whole track, not necessarily at this age">{star.flags.join("; ")}</dd></>}
        </dl>
        <div className="system-view">
          <svg viewBox={`0 0 ${S} ${S}`} width={S} height={S} role="img" aria-label={`${timeline.name} at ${fmtAge(age)}, seen from above`}>
            {hzIn !== null && hzOut !== null && (
              <circle cx={c} cy={c} r={(r(hzIn) + r(hzOut)) / 2} className="hz-band" strokeWidth={Math.max(1, r(hzOut) - r(hzIn))} />
            )}
            {[0.01, 0.1, 1, 10, 100].map((a) => <circle key={a} cx={c} cy={c} r={r(a)} className="scale-ring" />)}
            {[0.01, 0.1, 1, 10, 100].map((a) => <text key={a} x={c + r(a) + 2} y={c - 3}>{a} AU</text>)}
            <circle cx={c} cy={c} r={Math.max(2, r(radius))} fill={css(star.rgb[i])} fillOpacity={0.9} />
            {planets.map((p, k) => {
              const a = orbitAt(p, s);
              if (a === null || age < formedAt[k]) return null;
              const angle = (k * 2.4) % (2 * Math.PI);
              return (
                <g key={k}>
                  <circle cx={c} cy={c} r={r(a)} className="orbit" />
                  <circle cx={c + r(a) * Math.cos(angle)} cy={c + r(a) * Math.sin(angle)} r={sizeOf(p)} fill={CLASS_COLOURS[p.class_at_formation]}>
                    <title>{`${label(p, k)}: ${a.toPrecision(4)} AU`}</title>
                  </circle>
                </g>
              );
            })}
          </svg>
          <ol className="event-log">
            {events.map((e, j) => (
              <li key={j} className={e.age_yr <= age ? "past" : ""}>
                <button className="linklike" onClick={() => jump(e.age_yr)}>{fmtAge(e.age_yr)}</button>{" "}
                <b>{e.who}</b> {e.kind}: {e.detail}
              </li>
            ))}
          </ol>
        </div>
        <p className="source">Orbits and the star on one log scale (0.003–300 AU); planet sizes are enlarged; the green band is the habitable zone. Shaded star colour from its temperature (derived in Python). {meta.models.orbits}.</p>
      </section>
      <section>
        <h2>Fates</h2>
        <table className="result-table">
          <thead><tr><th>Planet</th><th>Mass (M⊕)</th><th>Fate</th><th>Closest approach</th><th>Deciding phase</th><th>Class at the end</th><th>Shoreline</th><th>XUV dose</th><th>Warnings</th></tr></thead>
          <tbody>
            {planets.map((p, k) => (
              <tr key={k}>
                <td><i className="swatch" style={{ background: CLASS_COLOURS[p.class_at_formation] }} />{label(p, k)}</td>
                <td>{p.mass_mearth}{p.final_mass_mearth !== p.mass_mearth && ` → ${p.final_mass_mearth}`}</td>
                <td>{p.fate}<span className="prov">{p.provenance}</span></td>
                <td>{p.closest_approach_rstar} R★</td>
                <td>{p.deciding_phase}</td>
                <td>{p.class_final}{p.final_f_env > 0 && ` (envelope ${(100 * p.final_f_env).toPrecision(3)}%)`}</td>
                <td>{p.shoreline} ({(100 * p.air_retained).toFixed(0)}% kept)</td>
                <td>{p.xuv_dose_earth} Earth doses</td>
                <td className="flags">{p.flags.join("; ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="source">{meta.models.shoreline}. {meta.models.escape}. The shoreline label and the escape calculation are kept apart; a planet carries a warning where they disagree.</p>
      </section>
    </>
  );
}
