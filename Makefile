# One command per job; see documentation/Stellar-Forge Build Plan.md.

UV := $(shell command -v uv || echo $(HOME)/.local/bin/uv)

.PHONY: setup check dev bench data export

setup:
	$(UV) sync
	cd web && npm install

# Must pass before every commit.
check:
	.venv/bin/ruff check .
	.venv/bin/pytest -q
	cd web && npx tsc -b && npx eslint . && npx vitest run

dev:
	cd web && npm run dev

bench:
	OMP_NUM_THREADS=1 .venv/bin/python scripts/bench.py

# MIST v1.2 archives (~1.5 GB, resumable) and their compact grids in ~/.cache/stellar-forge/.
data:
	.venv/bin/python scripts/fetch_mist.py all
	.venv/bin/python -m stellarforge.mist convert

# The Star Builder grid in web/public/data/ (about 120 MB), plus the Phase 1 reports.
export:
	OMP_NUM_THREADS=1 .venv/bin/python -m stellarforge.export web
	.venv/bin/python -m stellarforge.evolution check
