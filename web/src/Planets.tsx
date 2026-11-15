// Planets (Phase 5): the planet population by star mass and [Fe/H], from Ida & Lin's population
// synthesis. Reads web/public/data/planets/population.json and the selected cell's systems file
// (`make planets`). The selectors snap to the exported grid. Nothing here computes a physical
// value: every number is read from the files, and the panels only regroup them for drawing.

import { Fragment, memo, useEffect, useMemo, useState } from "react";
import { Curves } from "./Experiments";
import { parseDocument } from "./data/loader";
import type { Calibration, Meta, Panel, PlanetClass, PlanetSystem, Population, PopulationCell, Systems } from "./data/types";
import { PLANET_CLASSES } from "./data/types";
import type { TimelineTarget } from "./SystemTimeline";
import ProvTag from "./ProvTag";
import StarNote from "./StarNote";
import { MetaContext } from "./data/metaContext";
import { fmtFeh, nearest, skipWhileHidden, type StarProps } from "./currentStar";

const DATA = `${import.meta.env.BASE_URL}data/`;

/** Class colours on the charts (presentation only). */
const CLASS_COLOURS: Record<PlanetClass, string> = {
  "gas giant": "#e0a458", "ice giant": "#6fa8dc", "sub-Neptune": "#8fd3c6", "super-Earth": "#c58bd9", terrestrial: "#c9785a",
};

/** One cell's sample systems; a string is the error to show, null while loading. */
function useSystems(file: string): Systems | string | null {
  const [state, setState] = useState<{ file: string; value: Systems | string } | null>(null);
  useEffect(() => {
    let live = true;
    fetch(DATA + file)
      .then((r) => {
        if (!r.ok) throw new Error(`${file}: HTTP ${r.status}; run \`make planets\``);
        return r.json();
      })
      .then((raw) => parseDocument(raw).systems ?? `${file} has no systems block`)
      .catch((e: Error) => e.message)
      .then((value) => { if (live) setState({ file, value }); });
    return () => { live = false; };
  }, [file]);
  return state?.file === file ? state.value : null;
}

export function CalibrationBadge({ label }: { label: Calibration }) {
  return <span className={`calib calib-${label.replace(/ /g, "-")}`}>{label}</span>;
}

type Props = StarProps & { onOpenTimeline: (t: TimelineTarget) => void };

function Planets(props: Props) {
  const [doc, setDoc] = useState<{ meta: Meta; population: Population } | string | null>(null);
  useEffect(() => {
    fetch(DATA + "planets/population.json")
      .then((r) => {
        if (!r.ok) throw new Error(`planets/population.json: HTTP ${r.status}; run \`make planets\``);
        return r.json();
      })
      .then((raw) => {
        const d = parseDocument(raw);
        setDoc(d.population ? { meta: d.meta, population: d.population } : "population.json has no population block");
      })
      .catch((e: Error) => setDoc(e.message));
  }, []);
  return (
    <main className="experiments">
      <header>
        <h1>Planets</h1>
        <p className="note">How many planets form, and of which kinds, in simulated disks around each star. Every value is a model prediction; the label on each panel says how far it is calibrated.</p>
      </header>
      {doc === null && <p>Loading…</p>}
      {typeof doc === "string" && <p role="alert">{doc}</p>}
      {doc !== null && typeof doc === "object" && <PopulationView meta={doc.meta} population={doc.population} {...props} />}
    </main>
  );
}

export default memo(Planets, skipWhileHidden);

function PopulationView({ meta, population, star, setStar, show, onOpenTimeline }: Props & { meta: Meta; population: Population }) {
  const masses = population.star_masses_msun, fehs = population.feh_values;
  // The cell nearest the current star; a slider sets the current star to its cell
  const mi = nearest(masses, star.mass_msun, true), fi = nearest(fehs, star.feh);
  const cell = population.cells[fi * masses.length + mi];
  const pick = (m: number, f: number) => setStar({ ...star, mass_msun: masses[m], feh: fehs[f] });
  const [lo, hi] = population.calibration_feh;
  return (
    <MetaContext value={meta}>
      <section>
        <h2>Conclusions</h2>
        <ul className="conclusions">
          {population.conclusions.map((c) => <li key={c.statement}><CalibrationBadge label={c.label} /> {c.statement}</li>)}
        </ul>
        <p className="source">{meta.models.planets}. {meta.models.disks}. Prediction inside {population.calibration_mass_msun[0]}–{population.calibration_mass_msun[1]} M☉ and [Fe/H] {lo} to +{hi}; extrapolation outside.</p>
      </section>
      <GiantOccurrence population={population} />
      <section className="controls">
        <label>
          Star mass
          <output>{masses[mi]} M☉</output>
          <input type="range" min={0} max={masses.length - 1} value={mi} onChange={(e) => pick(+e.target.value, fi)} />
        </label>
        <label>
          [Fe/H]
          <output>{fmtFeh(fehs[fi])}</output>
          <input type="range" min={0} max={fehs.length - 1} value={fi} onChange={(e) => pick(mi, +e.target.value)} />
        </label>
      </section>
      <StarNote star={star} shown={{ mass_msun: cell.m_star_msun, feh: cell.feh }} />
      <p className="note">
        <button className="linklike" onClick={() => { pick(mi, fi); show("star"); }}>This star's life in Star Builder</button>
      </p>
      <CellView key={cell.systems_file} cell={cell} onFollow={(index) => { pick(mi, fi); onOpenTimeline({ index }); }} />
    </MetaContext>
  );
}

function GiantOccurrence({ population }: { population: Population }) {
  const panel = useMemo<Panel>(() => {
    const n = population.star_masses_msun.length;
    return {
      title: "Systems with a gas giant", kind: "curves", x_label: "[Fe/H]", y_label: "share of systems", value_label: "share",
      log_x: false, log_values: false, x_values: population.feh_values, columns: [],
      rows: population.star_masses_msun.map((m, k) => ({
        label: `${m} M☉`, y: null,
        values: population.feh_values.map((_, f) => population.cells[f * n + k].host_share["gas giant"]),
        labels: population.feh_values.map(() => null), provenance: population.feh_values.map(() => "predicted"),
      })),
    };
  }, [population]);
  return (
    <section>
      <h2>Gas-giant occurrence against [Fe/H] <CalibrationBadge label="prediction" /> <CalibrationBadge label="extrapolation" /></h2>
      <p className="note">Prediction for [Fe/H] {population.calibration_feh[0]} to +{population.calibration_feh[1]}, extrapolation below. Any gas giant at any distance counts; survey comparisons apply their own mass and period cuts.</p>
      <Curves panel={panel} />
    </section>
  );
}

function CellView({ cell, onFollow }: { cell: PopulationCell; onFollow: (index: number) => void }) {
  const systems = useSystems(cell.systems_file);
  const [picked, setPicked] = useState<number | null>(null);
  const sample = typeof systems === "object" && systems !== null ? systems : null;
  const chosen = sample?.systems.find((s) => s.index === picked) ?? null;
  return (
    <>
      <section>
        <h2>{cell.m_star_msun} M☉, [Fe/H] {cell.feh > 0 ? "+" : ""}{cell.feh} <CalibrationBadge label={cell.calibration} /></h2>
        <dl className="cell-stats">
          <dt>Systems simulated</dt><dd>{cell.n_systems.toLocaleString()} (seed {cell.seed})</dd>
          <dt>Planets per star (≥ 0.1 M⊕)</dt><dd>{cell.planets_per_star}<ProvTag p={cell.provenance} what={`Planets per star: ${cell.planets_per_star}`} flags={cell.flags} /></dd>
          <dt>Snow line</dt><dd>{cell.a_ice_au} AU</dd>
          {cell.flags.length > 0 && <><dt>Warnings</dt><dd className="flags">{cell.flags.join("; ")}</dd></>}
          {PLANET_CLASSES.map((k) => (
            <Fragment key={k}><dt><i className="swatch" style={{ background: CLASS_COLOURS[k] }} />Systems with a {k}</dt>
              <dd>{(100 * cell.host_share[k]).toFixed(1)}%<ProvTag p={cell.provenance} what={`Systems with a ${k}: ${(100 * cell.host_share[k]).toFixed(1)}%`} flags={cell.flags} /></dd></Fragment>
          ))}
        </dl>
      </section>
      <PlanetCount cell={cell} />
      {systems === null && <p>Loading sample systems…</p>}
      {typeof systems === "string" && <p role="alert">{systems}</p>}
      {sample && <MassDistance sample={sample} picked={picked} onPick={setPicked} />}
      {sample && chosen && <SystemDiagram sample={sample} system={chosen} onFollow={() => onFollow(chosen.index)} />}
    </>
  );
}

function PlanetCount({ cell }: { cell: PopulationCell }) {
  const W = 800, H = 220, PAD = 40;
  const counts = cell.systems_with_count;
  const top = Math.max(...counts) / cell.n_systems;
  const bw = (W - PAD - 10) / counts.length;
  return (
    <section>
      <h2>Planets per star <CalibrationBadge label={cell.calibration} /></h2>
      <svg viewBox={`0 0 ${W} ${H}`} className="curve-plot" role="img" aria-label="Share of systems with each number of planets">
        <rect x={PAD} y={10} width={W - PAD - 10} height={H - PAD - 10} className="frame" />
        {counts.map((c, k) => {
          const h = ((c / cell.n_systems) / top) * (H - PAD - 20);
          return (
            <g key={k}>
              <rect x={PAD + k * bw + 4} y={H - PAD - h} width={bw - 8} height={h} fill="#6f7bd9">
                <title>{`${k} planets: ${c} systems (${((100 * c) / cell.n_systems).toFixed(1)}%)`}</title>
              </rect>
              <text x={PAD + (k + 0.5) * bw} y={H - PAD + 16} textAnchor="middle">{k}</text>
            </g>
          );
        })}
        <text x={PAD - 6} y={18} textAnchor="end">{(100 * top).toFixed(0)}%</text>
        <text x={PAD - 6} y={H - PAD} textAnchor="end">0</text>
        <text x={(W + PAD) / 2} y={H - 6} textAnchor="middle">planets (≥ 0.1 M⊕) in the system</text>
      </svg>
    </section>
  );
}

const logPos = (v: number, lo: number, hi: number) => (Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo));

function MassDistance({ sample, picked, onPick }: { sample: Systems; picked: number | null; onPick: (i: number) => void }) {
  const W = 800, H = 380, PAD = 50;
  const A = [0.03, 100], M = [0.1, 1e4];
  const x = (a: number) => PAD + logPos(a, A[0], A[1]) * (W - PAD - 10);
  const y = (m: number) => 10 + (1 - logPos(m, M[0], M[1])) * (H - PAD - 10);
  const withPlanets = sample.systems.filter((s) => s.planets.length > 0);
  return (
    <section>
      <h2>Mass against distance, {sample.systems.length} sample systems <CalibrationBadge label={sample.calibration} /></h2>
      <p className="note">Where planets end up when the gas disk is gone. Click a planet to open its system.</p>
      <svg viewBox={`0 0 ${W} ${H}`} className="curve-plot" role="img" aria-label="Planet mass against orbital distance">
        <rect x={PAD} y={10} width={W - PAD - 10} height={H - PAD - 10} className="frame" />
        <line x1={x(sample.a_ice_au)} x2={x(sample.a_ice_au)} y1={10} y2={H - PAD} className="snow-line" />
        <text x={x(sample.a_ice_au) + 4} y={22}>snow line</text>
        {[0.1, 1, 10, 100].map((a) => <text key={a} x={x(a)} y={H - PAD + 16} textAnchor="middle">{a}</text>)}
        {[0.1, 1, 10, 100, 1000, 1e4].map((m) => <text key={m} x={PAD - 6} y={y(m) + 4} textAnchor="end">{m >= 1e4 ? "10⁴" : m}</text>)}
        <text x={(W + PAD) / 2} y={H - 8} textAnchor="middle">orbit (AU)</text>
        <text x={12} y={(H - PAD) / 2} transform={`rotate(-90 12 ${(H - PAD) / 2})`} textAnchor="middle">mass (M⊕)</text>
        {withPlanets.flatMap((s) => s.planets.map((p, k) => (
          <circle key={`${s.index}-${k}`} cx={x(Math.min(Math.max(p.a_au, A[0]), A[1]))} cy={y(Math.min(Math.max(p.mass_mearth, M[0]), M[1]))}
            r={s.index === picked ? 5 : 3} fill={CLASS_COLOURS[p.class]} fillOpacity={picked === null || s.index === picked ? 0.85 : 0.25}
            stroke={s.index === picked ? "#fff" : "none"} className="clickable" onClick={() => onPick(s.index)}>
            <title>{`System ${s.index}: ${p.class}, ${p.mass_mearth} M⊕ at ${p.a_au} AU`}</title>
          </circle>
        )))}
      </svg>
      <ul className="curve-legend">
        {PLANET_CLASSES.map((k) => <li key={k}><i style={{ background: CLASS_COLOURS[k] }} />{k}</li>)}
      </ul>
      <label className="system-pick">
        Sample system{" "}
        <select value={picked ?? ""} onChange={(e) => onPick(+e.target.value)}>
          <option value="" disabled>choose…</option>
          {withPlanets.map((s) => <option key={s.index} value={s.index}>{`${s.index}: ${s.planets.length} planet${s.planets.length > 1 ? "s" : ""}`}</option>)}
        </select>
      </label>
    </section>
  );
}

/** A top-down view: orbits on a log scale in distance (true scale would hide the inner planets), planets enlarged by radius. */
function SystemDiagram({ sample, system, onFollow }: { sample: Systems; system: PlanetSystem; onFollow: () => void }) {
  const S = 420, c = S / 2, inner = 18, outer = c - 14;
  const A = [0.03, 100];
  const r = (a: number) => inner + logPos(Math.min(Math.max(a, A[0]), A[1]), A[0], A[1]) * (outer - inner);
  return (
    <section>
      <h2>System {system.index} <CalibrationBadge label={sample.calibration} /></h2>
      <p className="note">Disk: gas {system.f_g0}× and solids {system.f_d0}× the minimum-mass solar nebula, gas gone on a {(system.tau_disk_yr / 1e6).toFixed(2)} Myr timescale. Orbits on a log scale (0.03–100 AU); planet sizes are enlarged.</p>
      <div className="system-view">
        <svg viewBox={`0 0 ${S} ${S}`} width={S} height={S} role="img" aria-label={`System ${system.index}, seen from above`}>
          {[0.1, 1, 10].map((a) => <circle key={a} cx={c} cy={c} r={r(a)} className="scale-ring" />)}
          {[0.1, 1, 10].map((a) => <text key={a} x={c + r(a) + 2} y={c - 3}>{a} AU</text>)}
          <circle cx={c} cy={c} r={r(sample.a_ice_au)} className="snow-line" fill="none" />
          <circle cx={c} cy={c} r={6} fill="#ffe7a8" />
          {system.planets.map((p, k) => {
            const angle = (k * 2.4) % (2 * Math.PI);   // spread round the star so neighbours don't overlap
            return (
              <g key={k}>
                <circle cx={c} cy={c} r={r(p.a_au)} className="orbit" />
                <circle cx={c + r(p.a_au) * Math.cos(angle)} cy={c + r(p.a_au) * Math.sin(angle)}
                  r={2 + 1.6 * Math.sqrt(p.radius_rearth)} fill={CLASS_COLOURS[p.class]}>
                  <title>{`${p.class}, ${p.mass_mearth} M⊕ at ${p.a_au} AU`}</title>
                </circle>
              </g>
            );
          })}
        </svg>
        <table className="result-table">
          <thead><tr><th>Class</th><th>Mass (M⊕)</th><th>Radius (R⊕)</th><th>Orbit (AU)</th><th>Core grew at (AU)</th><th>Envelope</th><th>Core</th></tr></thead>
          <tbody>
            {system.planets.map((p, k) => (
              <tr key={k}>
                <td><i className="swatch" style={{ background: CLASS_COLOURS[p.class] }} />{p.class}</td>
                <td>{p.mass_mearth}<ProvTag p={p.provenance} what={`Planet mass: ${p.mass_mearth} M⊕`} /></td>
                <td>{p.radius_rearth}<ProvTag p={p.radius_provenance} what={`Planet radius: ${p.radius_rearth} R⊕`} how="Chen & Kipping 2017 mass-radius relation, for display; never used to classify" /></td>
                <td>{p.a_au}</td>
                <td>{p.a_form_au}</td>
                <td>{p.f_env < 1e-4 ? "< 0.01%" : `${(100 * p.f_env).toPrecision(3)}%`}</td>
                <td>{p.core}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p><button onClick={onFollow}>Follow this system through its star's life</button></p>
      <p className="source">Radii from Chen & Kipping 2017 (derived, for display only). The 3D system view joins in a later phase, once planets carry temperatures.</p>
    </section>
  );
}
