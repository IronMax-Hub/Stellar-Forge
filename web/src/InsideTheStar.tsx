// Inside the Star (Phase 4): the zero-age Sun from the structure solver, then the polytrope explorer.
// Reads web/public/data/zams.json (`python -m stellarforge.export zams`) and polytropes.json
// (`... export polytropes`); the n slider snaps to the exported indices. Nothing here computes a
// physical value: the panels only regroup the exported arrays for drawing.

import { useEffect, useState } from "react";
import { Curves } from "./Experiments";
import { parseDocument } from "./data/loader";
import type { Meta, Panel, PanelRow, Polytrope, Polytropes, Profile, StellarDocument } from "./data/types";
import { PROFILE_SCALARS } from "./data/types";

const DATA = `${import.meta.env.BASE_URL}data/`;

/** Loads one exported document; a string is the error to show. */
function useDocument(file: string): StellarDocument | string | null {
  const [doc, setDoc] = useState<StellarDocument | string | null>(null);
  useEffect(() => {
    fetch(DATA + file)
      .then((r) => {
        if (!r.ok) throw new Error(`${file}: HTTP ${r.status}; run \`make export\``);
        return r.json();
      })
      .then((raw) => setDoc(parseDocument(raw)))
      .catch((e: Error) => setDoc(e.message));
  }, [file]);
  return doc;
}

const fmt = (v: number | null, unit = "") => (v === null ? "—" : `${Math.abs(v) >= 1e4 ? v.toExponential(3) : v.toPrecision(6)} ${unit}`.trim());

function row(label: string, values: number[]): PanelRow {
  return { label, y: null, values, labels: values.map(() => null), provenance: values.map(() => "derived") };
}

function curves(title: string, y_label: string, x_values: number[], rows: PanelRow[], log_values = false): Panel {
  return { title, kind: "curves", x_label: "r / R", y_label, value_label: "", log_x: false, log_values, x_values, columns: [], rows };
}

export default function InsideTheStar() {
  const zams = useDocument("zams.json");
  const polytropes = useDocument("polytropes.json");
  return (
    <main className="experiments">
      <header>
        <h1>Inside the Star</h1>
      </header>
      <Status doc={zams} />
      {typeof zams === "object" && zams?.profiles && <ZeroAgeStar meta={zams.meta} star={zams.profiles.models[0]} />}
      <Status doc={polytropes} />
      {typeof polytropes === "object" && polytropes?.polytropes && <PolytropeExplorer meta={polytropes.meta} polytropes={polytropes.polytropes} />}
    </main>
  );
}

function Status({ doc }: { doc: StellarDocument | string | null }) {
  if (doc === null) return <p>Loading…</p>;
  return typeof doc === "string" ? <p role="alert">{doc}</p> : null;
}

const ZONE_COLOURS = { convective: "#d9774a", radiative: "#3b4a7a", burning: "rgba(255, 214, 102, 0.6)" };
const SCALAR_NAMES: Record<(typeof PROFILE_SCALARS)[number], string> = {
  log_l_lsun: "log L (L☉)", log_r_rsun: "log R (R☉)", log_teff_k: "log Teff (K)",
  log_t_c_k: "log Tc (K)", log_rho_c_kg_m3: "log ρc (kg m⁻³)",
};

/** Concentric zones, drawn from the surface inwards: each point's flag colours the disc out to its radius. */
function CrossSection({ star }: { star: Profile }) {
  const size = 300, c = size / 2, outer = c - 6;
  return (
    <figure className="cross-section">
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img"
        aria-label="Cross-section: convective and radiative zones, and the core that makes 99% of the light">
        {star.r_frac.map((_, k) => star.r_frac.length - 1 - k).map((i) => (
          <circle key={i} cx={c} cy={c} r={star.r_frac[i] * outer}
            fill={star.convective[i] ? ZONE_COLOURS.convective : ZONE_COLOURS.radiative} />
        ))}
        <circle cx={c} cy={c} r={star.energy_core_r_frac * outer} fill={ZONE_COLOURS.burning} stroke="#ffd666" strokeDasharray="4 3" />
      </svg>
      <figcaption className="legend">
        <span><i style={{ background: ZONE_COLOURS.convective }} />convective</span>
        <span><i style={{ background: ZONE_COLOURS.radiative }} />radiative</span>
        <span><i style={{ background: ZONE_COLOURS.burning }} />99% of the light made inside r/R = {star.energy_core_r_frac}</span>
      </figcaption>
    </figure>
  );
}

function ZeroAgeStar({ meta, star }: { meta: Meta; star: Profile }) {
  const x = star.r_frac;
  const panels = [
    curves("Structure", "fraction of central (or total) value", x, [
      row("temperature T/Tc", star.t_frac), row("density ρ/ρc", star.rho_frac), row("pressure P/Pc", star.p_frac),
      row("mass m/M", star.m_frac), row("luminosity L/L", star.l_frac),
    ]),
    curves("Temperature gradients d ln T / d ln P", "∇ (log scale)", x, [
      row("actual ∇", star.nabla), row("adiabatic ∇ad", star.nabla_ad), row("radiative ∇rad", star.nabla_rad),
    ], true),
    // Linear: on a log axis the rates span ~80 decades out to the surface
    curves("Energy generation", "W/kg", x, [row("pp chain", star.eps_pp_w_kg), row("CNO cycle", star.eps_cno_w_kg)]),
    curves("Opacity", "m²/kg (log scale)", x, [row("Rosseland mean κ", star.kappa_m2_kg)], true),
  ];
  return (
    <>
      <h2>A {star.mass_msun} M☉ star at the zero-age main sequence, [Fe/H] {star.feh}</h2>
      <p>
        Solved from the four structure equations with tabulated opacities, pp and CNO burning, hydrogen and
        helium ionisation and mixing-length convection, then compared with MIST's zero-age star.
      </p>
      <p className="source">
        {star.method} · X {star.x}, Y {star.y}, Z {star.z} · code {meta.generator.git_commit}
      </p>
      {star.flags.length > 0 && <p className="source" role="note">⚠ {star.flags.join(" · ")}</p>}
      <div className="zams-summary">
        <CrossSection star={star} />
        <table className="result-table">
          <thead>
            <tr><th />
              <th scope="col">Model <span className={`prov prov-${star.provenance}`}>{star.provenance}</span></th>
              {star.mist && <th scope="col">MIST <span className={`prov prov-${star.mist.provenance}`}>{star.mist.provenance}</span></th>}
              {star.mist && <th scope="col">Model − MIST (dex)</th>}
            </tr>
          </thead>
          <tbody>
            {PROFILE_SCALARS.map((k) => (
              <tr key={k}>
                <th scope="row">{SCALAR_NAMES[k]}</th>
                <td>{star[k]}</td>
                {star.mist && <td>{star.mist[k]}</td>}
                {star.mist && <td>{star.mist[`delta_${k}`]}</td>}
              </tr>
            ))}
            <tr><th scope="row">pp chain's share of the energy</th><td>{star.pp_share}</td></tr>
          </tbody>
        </table>
      </div>
      {panels.map((p) => (
        <section key={p.title} className="panel" aria-label={p.title}>
          <h3>{p.title}</h3>
          <Curves panel={p} />
        </section>
      ))}
    </>
  );
}

function PolytropeExplorer({ meta, polytropes }: { meta: Meta; polytropes: Polytropes }) {
  const [k, setK] = useState(6); // n = 3, Eddington's standard model
  const { models, n_values } = polytropes;
  const p: Polytrope = models[Math.min(k, models.length - 1)];
  const profile = curves(`Profiles for n = ${p.n}`, "fraction of central (or total) value", p.radius_frac, [
    row("density ρ/ρc", p.density_frac),
    row("pressure P/Pc", p.pressure_frac),
    row("θ (T/Tc for an ideal gas)", p.theta),
    row("mass m/M", p.mass_frac),
  ]);
  const density = curves("Density ρ/ρc for every n", "ρ / ρc", models[0].radius_frac,
    models.map((m) => row(`n = ${m.n}`, m.density_frac)));

  return (
    <>
      <h2>Polytropes</h2>
      <p>
        A polytrope is a star whose pressure follows P = K ρ^(1 + 1/n). The Lane–Emden equation gives its
        structure; higher n concentrates the mass towards the centre. Applied to the Sun, n = 3 is
        Eddington's standard model.
      </p>
      <p className="source">
        {Object.values(meta.models).join(" · ")} · code {meta.generator.git_commit}
      </p>

      <section className="controls" aria-label="Polytrope">
        <label>
          Polytropic index n <output>{p.n}</output>
          <input type="range" min={0} max={n_values.length - 1} value={k} onChange={(e) => setK(Number(e.target.value))} />
        </label>
      </section>

      <section className="panel" aria-label="Constants">
        <h3>n = {p.n} <span className={`prov prov-${p.provenance}`}>{p.provenance}</span></h3>
        {p.flags.map((f) => <p key={f} role="note">⚠ {f}</p>)}
        <table className="result-table">
          <tbody>
            <tr><th scope="row">Surface ξ₁</th><td>{fmt(p.xi1)}</td></tr>
            <tr><th scope="row">Mass constant −ξ₁² θ′(ξ₁)</th><td>{fmt(p.mass_constant)}</td></tr>
            <tr><th scope="row">Central / mean density ρc/ρ̄</th><td>{fmt(p.density_concentration)}</td></tr>
            <tr><th scope="row">As the Sun: central temperature</th><td>{fmt(p.sun_t_c_k, "K")}</td></tr>
            <tr><th scope="row">As the Sun: central density</th><td>{fmt(p.sun_rho_c_kg_m3, "kg m⁻³")}</td></tr>
            <tr><th scope="row">As the Sun: central pressure</th><td>{fmt(p.sun_p_c_pa, "Pa")}</td></tr>
          </tbody>
        </table>
      </section>

      <section className="panel" aria-label={profile.title}>
        <h3>{profile.title}</h3>
        <Curves panel={profile} />
      </section>
      <section className="panel" aria-label={density.title}>
        <h3>{density.title}</h3>
        <Curves panel={density} />
      </section>
    </>
  );
}
