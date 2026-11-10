# One command per job; see documentation/Stellar-Forge Build Plan.md.

BEDARD := $(HOME)/.cache/stellar-forge/bedard2020/AllSequences.tar.gz
UV := $(shell command -v uv || echo $(HOME)/.local/bin/uv)

.PHONY: setup check dev bench data export experiments

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

# MIST v1.2 archives (~1.5 GB, resumable) and their compact grids, and the Bédard et al. 2020
# white-dwarf cooling sequences (0.57 MB, read in place), all in ~/.cache/stellar-forge/.
data:
	.venv/bin/python scripts/fetch_mist.py all
	.venv/bin/python -m stellarforge.mist convert
	mkdir -p $(HOME)/.cache/stellar-forge/bedard2020
	curl --fail -sSL -z $(BEDARD) -o $(BEDARD) \
	  https://www.astro.umontreal.ca/~bergeron/CoolingModels/CoolingModels/AllSequences.tar.gz

# The Star Builder grid in web/public/data/ (about 120 MB), plus the Phase 1 reports.
export:
	OMP_NUM_THREADS=1 .venv/bin/python -m stellarforge.export web
	.venv/bin/python -m stellarforge.evolution check

# The six Phase 3 experiments into results/ (timestamped), and copies for the Experiments view.
experiments:
	OMP_NUM_THREADS=1 .venv/bin/python -m stellarforge.experiments all --export
