// Inside the Star (Phase 4): the polytrope explorer. Reads web/public/data/polytropes.json, written by
// `python -m stellarforge.export polytropes`; the n slider snaps to the exported indices. Nothing here
// computes a physical value: the panels only regroup the exported arrays for drawing.

import { useEffect, useState } from "react";
import { Curves } from "./Experiments";
import { parseDocument } from "./data/loader";
import type { Meta, Panel, PanelRow, Polytrope, Polytropes } from "./data/types";

const FILE = `${import.meta.env.BASE_URL}data/polytropes.json`;

const fmt = (v: number | null, unit = "") => (v === null ? "—" : `${Math.abs(v) >= 1e4 ? v.toExponential(3) : v.toPrecision(6)} ${unit}`.trim());

function row(label: string, values: number[]): PanelRow {
  return { label, y: null, values, labels: values.map(() => null), provenance: values.map(() => "derived") };
}

function curves(title: string, y_label: string, x_values: number[], rows: PanelRow[]): Panel {
  return { title, kind: "curves", x_label: "r / R", y_label, value_label: "", log_x: false, log_values: false, x_values, columns: [], rows };
}

export default function InsideTheStar() {
  const [doc, setDoc] = useState<{ meta: Meta; polytropes: Polytropes } | string | null>(null);
  const [k, setK] = useState(6); // n = 3, Eddington's standard model

  useEffect(() => {
    fetch(FILE)
      .then((r) => {
        if (!r.ok) throw new Error(`polytropes.json: HTTP ${r.status}; run \`make export\``);
        return r.json();
      })
      .then((raw) => {
        const { meta, polytropes } = parseDocument(raw);
        if (!polytropes) throw new Error("polytropes.json holds no polytropes");
        setDoc({ meta, polytropes });
      })
      .catch((e: Error) => setDoc(e.message));
  }, []);

  if (doc === null) return <main className="experiments"><p>Loading…</p></main>;
  if (typeof doc === "string") return <main className="experiments"><p role="alert">{doc}</p></main>;

  const { models, n_values } = doc.polytropes;
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
    <main className="experiments">
      <header>
        <h1>Inside the Star</h1>
      </header>
      <p>
        A polytrope is a star whose pressure follows P = K ρ^(1 + 1/n). The Lane–Emden equation gives its
        structure; higher n concentrates the mass towards the centre. Applied to the Sun, n = 3 is
        Eddington's standard model.
      </p>
      <p className="source">
        {Object.values(doc.meta.models).join(" · ")} · code {doc.meta.generator.git_commit}
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
    </main>
  );
}
