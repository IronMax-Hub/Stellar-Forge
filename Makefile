# One command per job; see documentation/Stellar-Forge Build Plan.md.
# `make data` and `make export` arrive with Phase 1, when there is data to fetch and export.

UV := $(shell command -v uv || echo $(HOME)/.local/bin/uv)

.PHONY: setup check dev bench

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
