# Stellar-Forge

Stars and their planets from published physics. The full plan is
`documentation/Stellar-Forge Build Plan.md`; claims are checked in `documentation/Source checks.md`.

## Ground rules

A change that breaks one of these is rejected.

1. **Published physics, not a full stellar code.** Every model names the paper or dataset it
   implements and passes its phase's validation checks.
2. **Python owns all physics, including interpolation.** `web/` never contains a physical formula
   and never blends two tracks. Sliders snap to the grid Python exported. TypeScript draws, animates
   and runs shader maths; every number it shows arrives in the JSON.
3. **One shared JSON contract.** `contract/fixture.json` is checked by `tests/test_contract.py` and
   `web/src/__tests__/contract.test.ts`. Field names carry units (`_msun`, `_yr`, `log_`…). To change
   the format, follow `contract/README.md` and raise `schema_version` on both sides.
4. **Aion Forge (`~/NEW_PP/Aion-Forge`) is read-only.** Only read files, `git rev-parse` and
   checksums there. Never run npm, builds, tests, formatters or writing git commands in it (`git
   status` writes too). Copy out with `cp`, compare checksum manifests before and after, and record
   every copy in `PROVENANCE.md`.
5. **Everything runs on this machine.** At most 4 worker processes, under 4 GiB per job, about 5 GB
   of disk in all. MIST archives are streamed, never unpacked. 3D stays light; every view works in 2D.
6. **Every result says where it came from:** published, interpolated, derived or predicted, with
   validity flags. Flags are warnings, never silent fixes.
7. **Git: ask before every commit and every push.**

## Working here

- `make setup` installs both stacks; `make check` runs ruff, pytest, the TypeScript compile, ESLint
  and Vitest and must pass before every commit; `make dev` starts the web app.
- Python 3.12 lives in `.venv/` (made by uv, which is at `~/.local/bin/uv`). System Python stays as it is.
- Each phase has its own branch, merged into `development` when its "Done when" is met.
- Documents go in `documentation/`. Downloaded papers stay out of Git; the repository is public.
- `web/src/rendering/aionStubs.ts` holds provisional types for the copied views; later phases
  replace them with contract blocks.
