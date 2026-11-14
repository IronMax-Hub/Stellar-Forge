# Provenance

Every file in Stellar-Forge that began as a copy from Aion Forge (`~/NEW_PP/Aion-Forge`), which is
read-only: files were copied out with `cp` and only the copies were changed.

- **Source commit:** `12b5749d7b237cb897752b23060a7b644aa7f609`
- **Copied:** 11 November 2026
- **Check:** a SHA-256 manifest of all 1,016 Aion Forge files (outside `node_modules` and `.git`) was
  taken before and after the copy; the two are identical.

Source paths are under Aion Forge's `frontend/`. The checksum is the first 16 characters of the
source file's SHA-256.

| Source | Destination | Source SHA-256 | Changes made to the copy |
| --- | --- | --- | --- |
| `src/rendering/starColour.ts` | `web/src/rendering/starColour.ts` | `5d6f730305519a54` | Rewritten to take the exported `rgb`; the temperature-to-colour call is gone. The saturation boost is kept. |
| `src/rendering/blackHole/BlackHoleView.ts` | `web/src/rendering/blackHole/BlackHoleView.ts` | `7746d7e43b8c1b40` | Types come from `aionStubs.ts`; the horizon radius is read from the input instead of computed; quality defaults to `standard`, the lowest. Phase 2: a `gas` uniform, off for accretion mode `none` (an isolated stellar black hole). |
| `src/rendering/blackHole/quality.ts` | `web/src/rendering/blackHole/quality.ts` | `1e6a807974fa1b0d` | Import path only. |
| `src/rendering/blackHole/shaders/blackHole.vert.glsl` | `web/src/rendering/blackHole/shaders/blackHole.vert.glsl` | `6e41d740153c6e2f` | None. |
| `src/rendering/blackHole/shaders/blackHole.frag.glsl` | `web/src/rendering/blackHole/shaders/blackHole.frag.glsl` | `36ba985d76fe352b` | Phase 2: a `gas` uniform; at 0 no disc or hot flow is drawn, only the lensed sky. |
| `src/rendering/systemView.ts` | `web/src/rendering/system/systemView.ts` | `4f3351fa9de95265` | Import paths only. |
| `src/rendering/systemLayout.ts` | `web/src/rendering/system/systemLayout.ts` | `eb9f86c4583f942d` | The orbit is read in AU as exported; `effectiveOrbitAU` and the `config` parameter are gone. |
| `src/rendering/planet/PlanetView.ts` | `web/src/rendering/planet/PlanetView.ts` | `f537485df52250d4` | City lights and the orbital shell removed (life simulation). Star colour, glow colour and star spectrum are read from the inputs instead of computed from temperature. |
| `src/rendering/planet/globe.ts` | `web/src/rendering/planet/globe.ts` | `3dcd07e67c5d5252` | The surface map, overcast share, boiling and freezing points are read from the `SolidWorld` stub instead of computed; vegetation removed. |
| `src/rendering/planet/globeBake.ts` | `web/src/rendering/planet/globeBake.ts` | `46ef648449232e05` | Vegetation input removed; its shader uniforms are set to zero. Copied because `globe.ts` cannot compile without it. |
| `src/rendering/planet/surfaceMap.ts` | `web/src/rendering/planet/surfaceMap.ts` | `968e73acf0a130a3` | Cut down to the data shape and the texture upload; the builder that read Aion Forge's geography and climate is gone. Copied because `globeBake.ts` needs it. |
| `src/rendering/planet/atmosphere.ts` | `web/src/rendering/planet/atmosphere.ts` | `7575562b3040f026` | The Planck-spectrum function and the overcast re-export are gone; the star's channel spectrum is an input. |
| `src/rendering/planet/cubeSphere.ts` | `web/src/rendering/planet/cubeSphere.ts` | `bb7ff28229074715` | None. |
| `src/rendering/planet/cubeFaces.ts` | `web/src/rendering/planet/cubeFaces.ts` | `c6fa028d10927a69` | None. |
| `src/rendering/planet/rings.ts` | `web/src/rendering/planet/rings.ts` | `61d5a35830b752a5` | None. |
| `src/rendering/planet/shaders/globe.vert.glsl` | `web/src/rendering/planet/shaders/globe.vert.glsl` | `07740038e24e050c` | None. |
| `src/rendering/planet/shaders/globe.frag.glsl` | `web/src/rendering/planet/shaders/globe.frag.glsl` | `a0f8d610ab635b1b` | None. |
| `src/rendering/planet/shaders/atmosphere.vert.glsl` | `web/src/rendering/planet/shaders/atmosphere.vert.glsl` | `db7419426965897f` | None. |
| `src/rendering/planet/shaders/atmosphere.frag.glsl` | `web/src/rendering/planet/shaders/atmosphere.frag.glsl` | `86c1105fe589b034` | None. |
| `src/rendering/planet/shaders/clouds.frag.glsl` | `web/src/rendering/planet/shaders/clouds.frag.glsl` | `1a76386ab48d6b52` | None. |
| `src/rendering/planet/shaders/rings.frag.glsl` | `web/src/rendering/planet/shaders/rings.frag.glsl` | `f0e0e52a113a16e7` | None. |
| `src/rendering/planet/shaders/giantBake.frag.glsl` | `web/src/rendering/planet/shaders/giantBake.frag.glsl` | `c17466d78526042e` | None. |
| `src/rendering/planet/shaders/globeBake.vert.glsl` | `web/src/rendering/planet/shaders/globeBake.vert.glsl` | `7f90adb6f62b1b71` | None. |
| `src/rendering/planet/shaders/globeBake.frag.glsl` | `web/src/rendering/planet/shaders/globeBake.frag.glsl` | `6abe1a5161053a1d` | None. |
| `src/rendering/planet/shaders/simplexNoise.glsl` | `web/src/rendering/planet/shaders/simplexNoise.glsl` | `b897b00f29b0f2d3` | None. |
| `src/simulation/rng.ts` | `web/src/util/rng.ts` | `07eac9e3c7939bf7` | Uses `Math.log` and `Math.cos` in place of Aion Forge's deterministic maths; visual randomness only. |
| `package.json` | `web/package.json` | `056e6499bdc9d948` | Capacitor, the fonts and the Android, stats and probes scripts removed; a `typecheck` script added. |
| `tsconfig.json` | `web/tsconfig.json` | `770b4140bbb581e2` | None. |
| `tsconfig.app.json` | `web/tsconfig.app.json` | `b1eac9ba6cd1c01d` | Node types and `resolveJsonModule` added. |
| `tsconfig.node.json` | `web/tsconfig.node.json` | `0011850458792264` | `stats` removed from `include`. |
| `vite.config.ts` | `web/vite.config.ts` | `2a03a53d4b9684ec` | API proxies and the long test timeout removed; the server may read `../contract`. |
| `eslint.config.js` | `web/eslint.config.js` | `f7c801df95518c20` | Aion Forge's simulation-only rules removed. |
| `index.html` | `web/index.html` | `ed7e299a645262fd` | Title changed; favicon link and `viewport-fit` removed. |
| `src/vite-env.d.ts` | `web/src/vite-env.d.ts` | `283dda342ed30207` | Aion Forge's environment variables removed. |

`web/src/rendering/aionStubs.ts` is new. It holds the data shapes the copies read, in place of Aion
Forge's simulation modules, and takes the planet colour table and `bodyKey` from Aion Forge's
`src/simulation/planet.ts` and `src/simulation/bodyKey.ts`.

## Still to review

These copies compile but nothing draws with them yet. Before a view uses one:

- **Formulas left in the copies.** `atmosphere.ts` scales Rayleigh optical depth with pressure,
  `rings.ts` and `PlanetView.ts` turn temperature into ring iciness and shimmer, `globe.ts` sets a
  giant's band count from its spin, and `systemView.ts` solves Kepler's equation to animate orbits.
  Each is either display maths that may stay or a result that must move to Python (ground rule 2);
  decide when the view is built in Phases 6 and 7.
- **Shaders.** The black-hole and giant-bake shaders take temperatures and compute colour on the
  GPU. They are unchanged and unreviewed.
- **Comments.** The copies still carry Aion Forge's comments, including its phase names
  ("Worlds Up Close", A5, MO6) and mentions of removed features.

## Not copied yet

- `src/ui/physics/chapters/` and `src/ui/EncyclopediaPanel.tsx`: the plan takes their structure only,
  with all text written new. They wait for Phase 7, when there is text to write.
- `life.ts`, the city-light and orbital-shell shaders: left out for good; they belong to Aion
  Forge's life simulation.

## Ported to Python (read in place, not copied)

| Source | Python | Source SHA-256 | Notes |
| --- | --- | --- | --- |
| `src/simulation/star.ts`: `temperatureToColor` | `stellarforge/colour.py`: `temperature_to_rgb` | `be90050abefbae03` | Same coefficients and clamps, vectorised with NumPy. Checked against the expectations in `src/__tests__/starColour.test.ts`, read as text. Read on 11 November 2026 at commit `12b5749`. |
| `src/simulation/star.ts`: `xuvLuminosityAt` and its terms (`saturationTimeGyr`, `activityAt`, `photosphericXuvShare`, `ACTIVITY_SCALE`) | `stellarforge/planets/xuv.py` | `be90050abefbae03` | Same constants; the bolometric luminosity is MIST's instead of Aion Forge's linear main-sequence law, and the fluence is integrated numerically along the track. Checked against `src/__tests__/xuv.test.ts` (`645c57c4550aa49f`), read as text. Read on 14 November 2026 at commit `12b5749`. |
| `src/simulation/atmosphericEscape.ts`: `criticalDose`, `airRetained` (the shoreline only) | `stellarforge/planets/shoreline.py` | `a66cd749314083c8` | K = 10 and the retention curve kept and labelled as Aion Forge's choices; the Earth dose is the MIST Sun's. Water loss and climate coupling not ported. Checked against `src/__tests__/atmosphericEscape.test.ts` (`1b753424883fe0d8`), read as text. Read on 14 November 2026 at commit `12b5749`. |
