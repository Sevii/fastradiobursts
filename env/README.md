# Environments

Two isolated Python environments back Project ECHO-FRB. **Which env runs which
track matters for reproducibility** — the literal track must use the
reconstructed authors' env; everything we author uses the project env.

| Env | Lock | Runs | Notes |
|---|---|---|---|
| Project `.venv` | `requirements.lock` | WP0 pipeline; WP1 clean-room, selection (W1.4), sensitivity aggregation, matrix (W1.6); all `pytest` | Python 3.10, uv-managed on popos |
| `venv_microfrb` | `microfrb_repro.lock` | WP1 **literal** reproduction (authors' `SearchLensedFRB.py`) and the W1.5 literal sweep | Reconstructed authors' env; includes 2 **undeclared** deps (colossus, statsmodels) |

## Why two envs
The clean-room track is deliberately independent of the authors' code, so it
runs on our own stack (`.venv`). The literal track must run the authors' code as
published, which needs a reconstructed environment (`venv_microfrb`) — the repo
ships no `requirements.txt`, so versions were pinned by hand and validated by
reproducing the committed G_3/SG_20/SG_100 candidate lists exactly.

## Running (on popos)
```bash
# literal track / sensitivity sweep
PYTHONPATH=~/Projects/fastradiobursts/src MPLBACKEND=Agg \
  ~/frb_catalog2_prep/wp1_repro/venv_microfrb/bin/python -m echo_frb.repro.<...>

# clean-room / selection / matrix / tests
PYTHONPATH=~/Projects/fastradiobursts/src \
  ~/Projects/fastradiobursts/.venv/bin/python -m echo_frb.repro.<...>
```

The factorial (W1.4c) imports the authors' `modules` **and** `echo_frb`, so it
runs in `venv_microfrb` with `PYTHONPATH=src`.
