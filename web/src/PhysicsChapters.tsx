// Physics Chapters (Phase 7 step 6): how each model works, with its citations. Written new for
// Stellar-Forge in the structure of Aion Forge's Physics page (chapters of cards; see PROVENANCE.md).
// Text only: no number is computed or shown here. The values each model used are in the provenance
// panel of the file that carries them.

import { useState } from "react";

interface Card {
  title: string;
  /** What the model says, in one or two sentences. */
  statement: string;
  /** How Stellar-Forge implements it. */
  how: string;
  source: string;
  limits: string[];
  /** Where the code lives. */
  code: string;
}

interface Chapter {
  id: string;
  title: string;
  intro: string;
  cards: Card[];
}

const CHAPTERS: readonly Chapter[] = [
  {
    id: "sources",
    title: "Where the numbers come from",
    intro: "Python computes every value from published physics and exports it; the browser only draws. Each value carries a label saying how it was made.",
    cards: [
      {
        title: "Five labels",
        statement: "Published: read from a dataset as released. Interpolated: blended between published tracks at the same evolutionary phase. Substituted: the nearest published track stands in. Derived: computed in Python from published values by a cited rule. Predicted: the output of a model run, such as a planet population.",
        how: "Every exported block carries its label, the method that made it and validity flags. Flags are warnings, never silent fixes. Click any label to open the panel with the file's dataset, models, parameters, code commit and sources.",
        source: "Stellar-Forge ground rules 1, 2 and 6",
        limits: ["Some displayed values (a planet's orbit, the snow line) have no label of their own yet."],
        code: "stellarforge/export.py · build_meta; web/src/ProvTag.tsx",
      },
      {
        title: "One star shared by every view",
        statement: "Star Builder, Inside the Star, Planets and System Timeline share one current star and age. Each view shows the exported star nearest to it and says so when the two differ.",
        how: "Sliders snap to the grid Python exported; no view blends two files.",
        source: "Stellar-Forge design",
        limits: ["Inside the Star has one exported model, so it only reports which star it shows."],
        code: "web/src/currentStar.ts",
      },
    ],
  },
  {
    id: "stars",
    title: "Stars: lives from MIST",
    intro: "A star's life is read from the MIST stellar evolution tracks, computed with the MESA code. Stellar-Forge processes and presents those tracks; it does not evolve stars itself.",
    cards: [
      {
        title: "Evolutionary tracks",
        statement: "Each MIST track follows one initial mass and metallicity from the pre-main sequence to the white-dwarf cooling sequence or the end of carbon burning, where its run ends.",
        how: "MIST v1.2 (rotating, [α/Fe] = 0) archives are streamed, never unpacked, and kept as compact per-metallicity files. A track's ending is read from its header, never assumed from its mass.",
        source: "Choi et al. 2016; Dotter 2016; Paxton et al. 2011 (MESA)",
        limits: ["Some tracks stop early, most often at low metallicity; their later phases and remnants are not shown, and the track says where it stops.", "The lowest-mass stars stop at the end of the main sequence, which they have not reached in the universe's age."],
        code: "stellarforge/mist.py",
      },
      {
        title: "Stars between the published tracks",
        statement: "A star between grid tracks is built by blending its neighbours at the same equivalent evolutionary phase (EEP), in log mass and [Fe/H].",
        how: "Only inside a grid cell whose four corner tracks exist and end the same way. Near a boundary the nearest valid track stands in, labelled substituted, with its distance in log mass and [Fe/H]. Nothing is extrapolated.",
        source: "Dotter 2016 (the EEP method)",
        limits: ["Tracks that end differently are never blended."],
        code: "stellarforge/evolution.py",
      },
      {
        title: "A star's colour",
        statement: "The colour drawn for a star is the colour of a blackbody at its effective temperature.",
        how: "Computed in Python from the temperature by a standard blackbody fit, ported from Aion Forge; the browser only boosts its saturation so classes read apart, and says so.",
        source: "A standard blackbody-colour approximation (Helland's fit)",
        limits: ["Real spectra differ from a blackbody, most of all in cool stars."],
        code: "stellarforge/colour.py",
      },
    ],
  },
  {
    id: "remnants",
    title: "Remnants",
    intro: "What is left when a star's track ends: a white dwarf, a neutron star, a black hole, or nothing. Every remnant names the prescription that made it and the alternative's result.",
    cards: [
      {
        title: "White dwarfs",
        statement: "A star that sheds its envelope leaves its core as a white dwarf, which then cools for billions of years.",
        how: "The white dwarf's mass is the MIST track's final mass; the alternative is the MIST-based initial–final mass relation of Cummings et al. Cooling follows the published thick-hydrogen sequences of Bédard et al., drawn dashed on the HR diagram.",
        source: "Cummings et al. 2018; Bédard et al. 2020",
        limits: ["The Cummings mass has no cooling sequence of its own; the cooling shown is for the MIST mass."],
        code: "stellarforge/remnants.py",
      },
      {
        title: "Neutron stars and black holes",
        statement: "A massive star's core collapses; how much falls back decides whether a neutron star or a black hole forms, and its mass.",
        how: "Both Fryer et al. prescriptions are computed from the carbon–oxygen core and final mass: delayed is adopted, rapid is the alternative, and Star Builder's remnant card switches between them. A neutron star's radius is fixed inside the measured range; a black hole's horizon radius is computed in Python.",
        source: "Fryer et al. 2012; Özel & Freire 2016",
        limits: ["MIST stops at the end of carbon burning, not at core collapse; such remnants carry a flag saying so.", "Single stars only: most massive stars interact with a companion (Sana et al. 2012), so no remnant mass is presented as uniquely set by the initial mass."],
        code: "stellarforge/remnants.py",
      },
      {
        title: "Pair instability",
        statement: "Very large helium cores become unstable: pulsations shed mass, heavier cores are destroyed outright, and the heaviest collapse whole.",
        how: "Read from the helium-core mass with Belczynski et al.'s pulsational cap and Heger & Woosley's ranges; this opens the black-hole mass gap.",
        source: "Heger & Woosley 2002; Belczynski et al. 2016",
        limits: ["The edges of the gap differ between papers; the adopted values are in the file's provenance."],
        code: "stellarforge/remnants.py",
      },
    ],
  },
  {
    id: "experiments",
    title: "Experiments across mass and metallicity",
    intro: "Sweeps over the whole grid answer how lifetimes and remnants change with mass and metallicity, and runs repeat exactly.",
    cards: [
      {
        title: "Lifetime and remnant maps",
        statement: "Main-sequence lifetime, total lifetime and remnant type for every mass and metallicity on the grid.",
        how: "Each cell is one track, read as in Star Builder; cells whose track stops early are shown as such, not filled in.",
        source: "Choi et al. 2016; Fryer et al. 2012",
        limits: ["Lower metallicities have more incomplete tracks."],
        code: "stellarforge/experiments.py",
      },
      {
        title: "Populations of stars",
        statement: "How many stars of a generation end as each kind of remnant follows from how many are born at each mass.",
        how: "Masses drawn from the Kroupa initial mass function with a fixed seed, so a rerun gives byte-identical results.",
        source: "Kroupa 2001",
        limits: ["One mass function for every metallicity."],
        code: "stellarforge/experiments.py · kroupa_sample",
      },
    ],
  },
  {
    id: "structure",
    title: "Inside the star",
    intro: "Hydrostatic equilibrium and energy generation from first principles, checked against MIST.",
    cards: [
      {
        title: "Polytropes",
        statement: "If pressure depends on density alone, the Lane–Emden equation gives a star's whole structure; the index n sets how centrally concentrated it is.",
        how: "Solved numerically for n from 0 to 5; the cases with exact solutions are the tests. Scaled to the Sun, the standard model's central temperature falls short of full solar models, a lesson in what simple physics misses.",
        source: "Chandrasekhar 1939; Kippenhahn, Weigert & Weiss 2012",
        limits: ["No energy generation or transport: a polytrope is a shape, not a star."],
        code: "stellarforge/structure.py",
      },
      {
        title: "A zero-age main-sequence star",
        statement: "Four structure equations (mass, pressure, luminosity and temperature against mass) with real microphysics give a young star's interior.",
        how: "Integrated out from the centre and in from the photosphere and matched at half the mass. Ideal gas plus radiation with Saha ionisation of hydrogen and helium, OPAL and Ferguson opacity tables, pp chain and CNO cycle, Schwarzschild convection with mixing length. Compared with MIST's zero-age star of the same mass and composition.",
        source: "Kippenhahn, Weigert & Weiss 2012; Iglesias & Rogers 1996; Asplund et al. 2009",
        limits: ["Uniform composition: a zero-age star only.", "A few heavy or low-metallicity cases do not converge, and are reported rather than hidden."],
        code: "stellarforge/structure.py, eos.py, opacity.py",
      },
    ],
  },
  {
    id: "planets",
    title: "Planet formation",
    intro: "How many planets form, of which kinds, around which stars: statistics over thousands of simulated disks, labelled by how well the model is calibrated there.",
    cards: [
      {
        title: "Disks and metallicity",
        statement: "A disk's solids scale with its star's metallicity, so metal-rich stars build cores faster; beyond the snow line ice adds to the solids.",
        how: "Gas and solid surface densities from Ida & Lin, the disk mass roughly linear in the star's mass, drawn with a spread, and gas that fades over a few million years.",
        source: "Ida & Lin 2004a; Ida, Lin & Nagasawa 2013; Andrews et al. 2013",
        limits: ["A semi-analytic model: no hydrodynamics."],
        code: "stellarforge/planets/disk.py",
      },
      {
        title: "Growth, gas capture and migration",
        statement: "Cores grow oligarchically; past a critical mass they capture gas; the disk drags planets inward.",
        how: "Core growth to the isolation mass, Kelvin–Helmholtz gas capture limited by the disk and tapered at the gap, type I migration scaled by the fiducial C1 and type II from the viscous gap, with resonant convoys. After the gas, giant impacts merge neighbours whose orbits cross, to 1 Gyr.",
        source: "Ida, Lin & Nagasawa 2013; Ida & Lin 2008a, 2010; Ikoma et al. 2000",
        limits: ["The published fiducial makes too many giants around Sun-like stars, as the paper itself reports; survey checks are listed in Planets."],
        code: "stellarforge/planets/growth.py, migration.py, population.py, impacts.py",
      },
      {
        title: "Planet classes",
        statement: "Each planet gets exactly one class from its mass, envelope fraction and core ice: gas giant, ice giant, sub-Neptune, super-Earth or terrestrial.",
        how: "Ordered rules, first match wins; the thresholds are Stellar-Forge choices, tested in sensitivity runs. Display radii come from Chen & Kipping's mass–radius relation and never enter the class.",
        source: "Chen & Kipping 2017; Owen & Wu 2017",
        limits: ["Every cell is labelled: observational constraint, prediction inside the calibration range, parameter-sensitive, or extrapolation."],
        code: "stellarforge/planets/classify.py",
      },
    ],
  },
  {
    id: "fates",
    title: "Planets through the star's life",
    intro: "What happens to each planet as its star ages, swells, sheds mass and dies, keeping the link between where it formed and what later happens to it.",
    cards: [
      {
        title: "The habitable zone",
        statement: "Where a planet could hold liquid water moves outward as the star brightens.",
        how: "Inner (runaway greenhouse) and outer (maximum greenhouse) edges from the star's luminosity and temperature at each age.",
        source: "Kopparapu et al. 2013",
        limits: ["Defined only for the effective temperatures the fits cover; outside them it is flagged, not drawn."],
        code: "stellarforge/planets/coevolution.py · habitable_edge_au",
      },
      {
        title: "Orbits widen as the star loses mass",
        statement: "When a star loses mass slowly compared with an orbit, the orbit widens so that its size times the star's mass stays constant, and its eccentricity is kept.",
        how: "Applied along the track's mass loss; a sudden loss of more than half the mass unbinds the planet.",
        source: "Veras et al. 2011; Hills 1983",
        limits: ["Neutron-star kicks and eccentric survival through a supernova are not yet modelled (Phase 6.2)."],
        code: "stellarforge/planets/coevolution.py",
      },
      {
        title: "Tides, drag and engulfment",
        statement: "A giant's convective envelope raises tides that pull close planets in; just outside its surface, drag in the thin chromosphere slows them further. A planet whose closest approach falls inside the star is engulfed.",
        how: "Equilibrium tides with eccentricity terms after the main sequence, chromospheric drag, and engulfment when the pericentre reaches the star's radius. Each planet reports its closest approach in stellar radii and the phase that decided its fate.",
        source: "Zahn 1977; Mustill & Villaver 2012; Schröder & Connon Smith 2008; Ostriker 1999",
        limits: ["Fiducial tidal strength; the Solar System's widening factor is slightly above the published range."],
        code: "stellarforge/planets/coevolution.py",
      },
      {
        title: "Eccentric orbits",
        statement: "Planets move on ellipses; the closest approach, not the average distance, decides engulfment.",
        how: "Each planet's eccentricity comes from Phase 5 (a lower bound) or, for the Solar System, from measured values; the 2D and 3D maps draw each orbit through its exported pericentre and apocentre.",
        source: "Ida & Lin 2010; Mustill & Villaver 2012",
        limits: ["In the 3D map, where a planet is along its ellipse is animation only."],
        code: "stellarforge/planets/coevolution.py; web/src/SystemView3D.tsx",
      },
      {
        title: "Atmospheres: the shoreline and escape",
        statement: "Two separate answers to whether a planet keeps its air: the cosmic shoreline, an observed trend of high-energy dose against escape velocity, and energy-limited escape, a rate integrated over the star's history.",
        how: "The star's X-ray and ultraviolet output saturates when young and then decays; it is held after the main sequence. The shoreline gives a kept-or-lost label; escape lowers the envelope fraction and can turn a sub-Neptune into a super-Earth. Where the two disagree the planet carries both and a flag.",
        source: "Zahnle & Catling 2017; Owen & Wu 2017; Wright et al. 2011; Ribas et al. 2005",
        limits: ["The shoreline's scale factor and retention curve are Aion Forge's choices, labelled as such."],
        code: "stellarforge/planets/xuv.py, shoreline.py, escape.py",
      },
      {
        title: "After the giant (planned, Phase 6.2)",
        statement: "Survivors then face the hot post-AGB star's and white dwarf's own ultraviolet, and around massive stars a supernova with a kick.",
        how: "Not built yet. Planned: ultraviolet from the remnant's blackbody, timelines continued along Bédard et al.'s cooling sequences, and Monte Carlo supernova survival with Hobbs et al.'s kicks.",
        source: "Bédard et al. 2020; Hobbs et al. 2005; Hills 1983",
        limits: ["Until then, kicks are flagged where a planet stays bound."],
        code: "—",
      },
    ],
  },
];

export default function PhysicsChapters() {
  const [id, setId] = useState(CHAPTERS[0].id);
  const chapter = CHAPTERS.find((c) => c.id === id)!;
  return (
    <main className="experiments physics">
      <header>
        <h1>Physics Chapters</h1>
        <p className="note">How each model works and where it comes from. The values each model used are in the provenance panel of the file that carries them.</p>
      </header>
      <nav className="subtabs chapter-tabs" aria-label="Chapters">
        {CHAPTERS.map((c) => <button key={c.id} aria-pressed={c.id === id} onClick={() => setId(c.id)}>{c.title}</button>)}
      </nav>
      <section>
        <h2>{chapter.title}</h2>
        <p>{chapter.intro}</p>
        {chapter.cards.map((card) => (
          <article key={card.title} className="panel chapter-card">
            <h3>{card.title}</h3>
            <p>{card.statement}</p>
            <dl>
              <dt>How</dt><dd>{card.how}</dd>
              <dt>Source</dt><dd>{card.source}</dd>
              <dt>Limits</dt><dd><ul>{card.limits.map((l) => <li key={l}>{l}</li>)}</ul></dd>
              <dt>Code</dt><dd><code>{card.code}</code></dd>
            </dl>
          </article>
        ))}
      </section>
    </main>
  );
}
