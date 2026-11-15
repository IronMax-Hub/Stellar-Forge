// System Timeline (Phase 6): planets through their star's life. Reads web/public/data/planets/
// solar_system.json and the timeline_<nnn>.json files (`make planets`). The scrubber moves along
// the exported ages; between two exported ages the drawing is smoothed linearly along that one
// track. Nothing here computes a physical value: orbits, the star, the habitable zone, events and
// fates all come from the files.

import { memo, useEffect, useMemo, useState } from "react";
import { parseDocument } from "./data/loader";
import type { Meta, PlanetClass, Population, PopulationCell, Timeline, TimelinePlanet } from "./data/types";
import { CalibrationBadge } from "./Planets";
import ProvTag from "./ProvTag";
import StarNote from "./StarNote";
import { MetaContext } from "./data/metaContext";
import { fmtFeh, indexAtAge, nearest, skipWhileHidden, type StarProps } from "./currentStar";
import SystemView3D, { type SystemFrame } from "./SystemView3D";

const DATA = `${import.meta.env.BASE_URL}data/`;
const SOLAR = "planets/solar_system.json";

/** Class colours, as in the Planets view (presentation only). */
const CLASS_COLOURS: Record<PlanetClass, string> = {
  "gas giant": "#e0a458", "ice giant": "#6fa8dc", "sub-Neptune": "#8fd3c6", "super-Earth": "#c58bd9", terrestrial: "#c9785a",
};

/** A system of the current star's cell, picked in the Planets view. */
export interface TimelineTarget {
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

function SystemTimeline({ star, setStar, show, target }: StarProps & { target: TimelineTarget | null }) {
  const isSun = star.mass_msun === 1 && star.feh === 0;
  // The Solar System is the reference case for the Sun; any other star shows its cell's sample systems
  const [solar, setSolar] = useState(isSun && !target);
  const [index, setIndex] = useState(target?.index ?? 0);
  // A system followed from the Planets view, or another star, replaces the choice (adjusted while rendering)
  const [seenStar, setSeenStar] = useState(star);
  const [seenTarget, setSeenTarget] = useState(target);
  if (star !== seenStar || target !== seenTarget) {
    setSeenStar(star);
    setSeenTarget(target);
    if (target && target !== seenTarget) {
      setSolar(false);
      setIndex(target.index);
    } else if (star.mass_msun !== seenStar.mass_msun || star.feh !== seenStar.feh) {
      setSolar(isSun);
      setIndex(0);
    }
  }
  const [population, setPopulation] = useState<Population | string | null>(null);
  useEffect(() => {
    const missing = "planets/population.json is missing; run `make planets`";
    fetch(DATA + "planets/population.json").then((r) => (r.ok ? r.json() : null))
      .then((raw) => setPopulation((raw && parseDocument(raw).population) || missing))
      .catch((e: Error) => setPopulation(e.message));
  }, []);
  const grid = typeof population === "object" ? population : null;
  // The cell nearest the current star
  const cell = grid && grid.cells[nearest(grid.feh_values, star.feh) * grid.star_masses_msun.length + nearest(grid.star_masses_msun, star.mass_msun, true)];
  const file = solar ? SOLAR : cell?.timeline_file ?? null;
  const doc = useTimeline(file ?? SOLAR);
  const shown = file === null ? population : doc;
  // Optional 3D map (Phase 7); the 2D map is the default
  const [threeD, setThreeD] = useState(false);
  return (
    <main className="experiments">
      <header>
        <h1>System Timeline</h1>
        <p className="note">What happens to each planet as its star ages, swells, sheds mass and dies. Every orbit, edge and event is a model prediction from the files; the drawing only scales them.</p>
        <p className="note"><button className="linklike" onClick={() => show("star")}>This star's life in Star Builder</button></p>
      </header>
      <Picker solar={solar} index={index} cell={solar ? null : cell} population={grid} timeline={file !== null && typeof doc === "object" && doc ? doc.timeline : null}
        onSolar={(on) => { setSolar(on); setIndex(0); if (on) setStar({ ...star, mass_msun: 1, feh: 0 }); }}
        onCell={(mass_msun, feh) => setStar({ ...star, mass_msun, feh })} onIndex={setIndex} />
      {!solar && cell && <StarNote star={star} shown={{ mass_msun: cell.m_star_msun, feh: cell.feh }} />}
      {shown === null && <p>Loading…</p>}
      {typeof shown === "string" && <p role="alert">{shown}</p>}
      {file !== null && doc !== null && typeof doc === "object" && (
        <TimelineView key={`${file}:${index}`} meta={doc.meta} timeline={doc.timeline} index={index}
          ageYr={star.age_yr} onAge={(age_yr) => setStar({ ...star, age_yr })} threeD={threeD} setThreeD={setThreeD} />
      )}
    </main>
  );
}

export default memo(SystemTimeline, skipWhileHidden);

function Picker({ solar, index, cell, population, timeline, onSolar, onCell, onIndex }: {
  solar: boolean; index: number; cell: PopulationCell | null; population: Population | null; timeline: Timeline | null;
  onSolar: (on: boolean) => void; onCell: (mass_msun: number, feh: number) => void; onIndex: (index: number) => void;
}) {
  const masses = population?.star_masses_msun ?? [], fehs = population?.feh_values ?? [];
  const mi = cell ? masses.indexOf(cell.m_star_msun) : -1;
  const fi = cell ? fehs.indexOf(cell.feh) : -1;
  return (
    <section className="controls">
      <label>
        Systems
        <select value={solar ? "solar" : "sample"} onChange={(e) => onSolar(e.target.value === "solar")}>
          <option value="solar">Solar System (reference case)</option>
          <option value="sample" disabled={!population}>Phase 5 sample systems</option>
        </select>
      </label>
      {cell && (
        <>
          <label>
            Star mass
            <output>{masses[mi]} M☉</output>
            <input type="range" min={0} max={masses.length - 1} value={mi} onChange={(e) => onCell(masses[+e.target.value], fehs[fi])} />
          </label>
          <label>
            [Fe/H]
            <output>{fmtFeh(fehs[fi])}</output>
            <input type="range" min={0} max={fehs.length - 1} value={fi} onChange={(e) => onCell(masses[mi], fehs[+e.target.value])} />
          </label>
          {timeline && (
            <label>
              System
              <select value={index} onChange={(e) => onIndex(+e.target.value)}>
                {timeline.systems.filter((s) => s.planets.length > 0).map((s) => (
                  <option key={s.index} value={s.index}>{`${s.index}: ${s.planets.length} planet${s.planets.length > 1 ? "s" : ""}`}</option>
                ))}
              </select>
            </label>
          )}
          <CalibrationBadge label={cell.calibration} />
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

type OrbitSeries = "orbit_a_au" | "orbit_e" | "orbit_pericentre_au" | "orbit_apocentre_au";

/** One orbit series at sample position s, drawn linearly between its knots; null once the planet
 * is gone. */
function orbitAt(p: TimelinePlanet, s: number, series: OrbitSeries = "orbit_a_au"): number | null {
  const k = p.orbit_sample, v = p[series];
  if (s > k[k.length - 1]) return null;
  let j = 0;
  while (j < k.length - 1 && k[j + 1] < s) j++;
  if (j === k.length - 1 || s <= k[0]) return v[j];
  const w = (s - k[j]) / (k[j + 1] - k[j]);
  return v[j] + (v[j + 1] - v[j]) * w;
}

const fmtAge = (yr: number) => (yr >= 1e9 ? `${(yr / 1e9).toFixed(3)} Gyr` : yr >= 1e6 ? `${(yr / 1e6).toFixed(2)} Myr` : `${yr.toPrecision(3)} yr`);
const css = ([r, g, b]: number[]) => `rgb(${Math.round(255 * r)}, ${Math.round(255 * g)}, ${Math.round(255 * b)})`;
const label = (p: TimelinePlanet, k: number) => p.name ?? `planet ${k + 1} (${p.class_at_formation})`;

function TimelineView({ meta, timeline, index, ageYr, onAge, threeD, setThreeD }: {
  meta: Meta; timeline: Timeline; index: number; ageYr: number; onAge: (age_yr: number) => void;
  threeD: boolean; setThreeD: (on: boolean) => void;
}) {
  const star = timeline.star;
  const n = star.age_yr.length;
  const system = timeline.systems.find((s) => s.index === index) ?? timeline.systems[0];
  const planets = system.planets;
  const formedAt = planets.map((p) => p.events.find((e) => e.kind === "formed")?.age_yr ?? star.age_yr[0]);
  // Opens at the current age; an age set in another view moves the scrubber to it
  const [s, setS] = useState(() => indexAtAge(star.age_yr, ageYr));
  const [playing, setPlaying] = useState(false);
  const [seenAge, setSeenAge] = useState(ageYr);
  if (ageYr !== seenAge) {
    setSeenAge(ageYr);
    setPlaying(false);
    setS(indexAtAge(star.age_yr, ageYr));
  }
  /** Sets the current age from this view; marked as seen, so the scrubber is not snapped to a sample. */
  const publish = (age_yr: number) => {
    setSeenAge(age_yr);
    onAge(age_yr);
  };
  const endAge = star.age_yr[n - 1];
  useEffect(() => {
    if (!playing) return;
    let frame = 0, last = performance.now();
    const tick = (now: number) => {
      const step = ((now - last) / 1000) * 6;   // six exported samples per second
      last = now;
      setS((v) => {
        if (v + step < n - 1) return v + step;
        // The end of the track: stop, and make its age the current age (after this render)
        setPlaying(false);
        queueMicrotask(() => onAge(endAge));
        return n - 1;
      });
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, n, endAge, onAge]);
  const age = along(star.age_yr, s);
  const i = Math.round(s);
  const events = useMemo(() => planets.flatMap((p, k) => p.events.map((e) => ({ ...e, who: label(p, k), k })))
    .sort((a, b) => a.age_yr - b.age_yr), [planets]);
  const jump = (yr: number) => {
    const j = indexAtAge(star.age_yr, yr);
    setS(j);
    publish(star.age_yr[j]);
  };
  const sizeOf = (p: TimelinePlanet) => 2.5 + 1.4 * Math.log10(1 + p.mass_mearth);

  // Log scale in distance, star and orbits alike, so an engulfed orbit lies inside the drawn star
  const S = 460, c = S / 2, outer = c - 12;
  const A = [0.003, 300];
  const r = (a: number) => Math.max(0, ((Math.log10(a) - Math.log10(A[0])) / (Math.log10(A[1]) - Math.log10(A[0]))) * outer);
  const hzIn = alongNullable(star.hz_inner_au, s), hzOut = alongNullable(star.hz_outer_au, s);
  const radius = along(star.radius_au, s);
  // The 3D camera is framed once per system, on its widest orbit or largest star radius over the whole track
  const extentAu = useMemo(() => Math.max(...star.radius_au, ...planets.flatMap((p) => p.orbit_apocentre_au)), [star, planets]);
  const frame: SystemFrame | null = threeD ? {
    starRadiusAu: radius, rgb: star.rgb[i], hzInAu: hzIn, hzOutAu: hzOut,
    planets: planets.map((p, k) => {
      const a = orbitAt(p, s);
      return a === null || age < formedAt[k] ? null : { a_au: a, e: orbitAt(p, s, "orbit_e")!, colour: CLASS_COLOURS[p.class_at_formation], size: sizeOf(p) / 2.5 };
    }),
  } : null;
  return (
    <MetaContext value={meta}>
      <section>
        <h2>{timeline.name}{timeline.systems_file ? `, system ${system.index}` : ""}</h2>
        <div className="controls timeline-controls">
          <button onClick={() => { if (playing) publish(age); setPlaying(!playing); }}>{playing ? "Pause" : "Play"}</button>
          <label className="wide">
            Age
            <output>{fmtAge(age)}</output>
            <input type="range" min={0} max={n - 1} step={0.01} value={s} onChange={(e) => { setPlaying(false); setS(+e.target.value); publish(along(star.age_yr, +e.target.value)); }} />
          </label>
          <label className="check"><input type="checkbox" checked={threeD} onChange={(e) => setThreeD(e.target.checked)} /> 3D view</label>
        </div>
        <dl className="cell-stats">
          <dt>Phase</dt><dd>{star.phase[i]}</dd>
          <dt>Star</dt><dd>{star.mass_msun[i]} M☉, {star.l_lsun[i]} L☉, {star.teff_k[i]} K, radius {star.radius_au[i]} AU<ProvTag p={star.provenance} what="The star at this age" how={star.method} flags={star.flags} /></dd>
          <dt>Habitable zone</dt><dd>{star.hz_inner_au[i] === null ? "not defined (Teff outside 2,600–7,200 K)" : `${star.hz_inner_au[i]}–${star.hz_outer_au[i]} AU`}<ProvTag p="derived" what="Habitable zone" how={meta.models["habitable zone"]} /></dd>
          <dt>Track</dt><dd>{star.method}; ends at {star.ending}</dd>
          {star.flags.length > 0 && <><dt>Track warnings</dt><dd className="flags" title="These apply somewhere along the whole track, not necessarily at this age">{star.flags.join("; ")}</dd></>}
        </dl>
        <div className="system-view">
          {frame && <SystemView3D frame={frame} extentAu={extentAu} label={`${timeline.name} at ${fmtAge(age)}, in 3D`} />}
          {!frame && <svg viewBox={`0 0 ${S} ${S}`} width={S} height={S} role="img" aria-label={`${timeline.name} at ${fmtAge(age)}, seen from above`}>
            {hzIn !== null && hzOut !== null && (
              <circle cx={c} cy={c} r={(r(hzIn) + r(hzOut)) / 2} className="hz-band" strokeWidth={Math.max(1, r(hzOut) - r(hzIn))} />
            )}
            {[0.01, 0.1, 1, 10, 100].map((a) => <circle key={a} cx={c} cy={c} r={r(a)} className="scale-ring" />)}
            {[0.01, 0.1, 1, 10, 100].map((a) => <text key={a} x={c + r(a) + 2} y={c - 3}>{a} AU</text>)}
            <circle cx={c} cy={c} r={Math.max(2, r(radius))} fill={css(star.rgb[i])} fillOpacity={0.9} />
            {planets.map((p, k) => {
              const a = orbitAt(p, s);
              if (a === null || age < formedAt[k]) return null;
              const e = orbitAt(p, s, "orbit_e")!;
              // An ellipse through the exported pericentre and apocentre on the log scale, its
              // pericentre towards the planet's angle; the planet is drawn at its pericentre
              const rq = r(orbitAt(p, s, "orbit_pericentre_au")!), rQ = r(orbitAt(p, s, "orbit_apocentre_au")!);
              const deg = ((k * 2.4) % (2 * Math.PI)) * (180 / Math.PI);
              return (
                <g key={k} transform={`rotate(${deg} ${c} ${c})`}>
                  <ellipse cx={c - (rQ - rq) / 2} cy={c} rx={(rq + rQ) / 2} ry={Math.sqrt(rq * rQ)} className="orbit" />
                  <circle cx={c + rq} cy={c} r={sizeOf(p)} fill={CLASS_COLOURS[p.class_at_formation]}>
                    <title>{`${label(p, k)}: a ${a.toPrecision(4)} AU, e ${e.toPrecision(3)}, pericentre ${orbitAt(p, s, "orbit_pericentre_au")!.toPrecision(4)} AU`}</title>
                  </circle>
                </g>
              );
            })}
          </svg>}
          <ol className="event-log">
            {events.map((e, j) => (
              <li key={j} className={e.age_yr <= age ? "past" : ""}>
                <button className="linklike" onClick={() => jump(e.age_yr)}>{fmtAge(e.age_yr)}</button>{" "}
                <b>{e.who}</b> {e.kind}: {e.detail}
              </li>
            ))}
          </ol>
        </div>
        <p className="source">{frame
          ? "Orbits and the star to scale (drag to turn, scroll to zoom); planets, and a star too small to see, are enlarged; each planet's place along its orbit is animation only; the green ring is the habitable zone."
          : "Orbits and the star on one log scale (0.003–300 AU), each drawn through its pericentre and apocentre with the planet at its pericentre; planet sizes are enlarged; the green band is the habitable zone."} Shaded star colour from its temperature (derived in Python). {meta.models.orbits}.</p>
      </section>
      <section>
        <h2>Fates</h2>
        <table className="result-table">
          <thead><tr><th>Planet</th><th>Mass (M⊕)</th><th>Fate</th><th>e (start → end)</th><th>Closest approach</th><th>Deciding phase</th><th>Class at the end</th><th>Shoreline</th><th>XUV dose</th><th>Warnings</th></tr></thead>
          <tbody>
            {planets.map((p, k) => (
              <tr key={k}>
                <td><i className="swatch" style={{ background: CLASS_COLOURS[p.class_at_formation] }} />{label(p, k)}</td>
                <td>{p.mass_mearth}{p.final_mass_mearth !== p.mass_mearth && ` → ${p.final_mass_mearth}`}</td>
                <td>{p.fate}<ProvTag p={p.provenance} what={`${label(p, k)}: ${p.fate}`} how={`Closest approach ${p.closest_approach_rstar} R★, decided on the ${p.deciding_phase}`} flags={p.flags} /></td>
                <td>{p.e}{p.final_e !== p.e && ` → ${p.final_e}`}</td>
                <td>{p.closest_approach_rstar} R★ (pericentre)</td>
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
    </MetaContext>
  );
}
