# Coherent-source acceptance refresh

Execute after the active ZR-6 fixture and final ZR-3/4 iteration have stopped.
Keep one experiment/Spark process group active at a time and retain every failure.
This verification does not change benchmark selections, thresholds, seeds or data.

ZR-1: run the existing five-step `tools/accept_zr1.py` sequence: wheel/private
repository check, complete local classic and Connect suites, OS-denied-egress
synthetic CLI and historical original-FEBRL development smoke. Each step retains
its 300-second limit. Pin Java 17/Python 3.12 and local[2] as before.

ZR-2 iteration 6: repeat the four predeclared ablation fixtures using
`tools/accept_zr2.py`, each at most 900 seconds, with all variants, partitions,
seeds and explicit historical feature/retrieval settings unchanged. Local MiniLM
is already prepared; external egress stays denied. These are validation
reproducibility checks, not new selection or confirmation runs. Stop at the first
execution failure; no automatic resource increase.

ZR-5 iteration 4: repeat offline composite fit/reload (300 seconds each) and
normal CLI accepted-pointer reload (300 seconds), then the existing two-task
remote tracking fixture on fevm-gdpr2 (600 seconds/task, 1500 seconds/job,
2100-second outer envelope). Retain the same synthetic training/evaluation
records and model parameters. This may create the next version of the owned
synthetic pair_model and update its champion alias only after its existing
acceptance checks. No frozen benchmark model or alias is promoted.

Run phase verifiers read-only after their evidence is sealed. Missing, failed or
stale evidence remains a failure. Keep the million-record scale failure, blocked
complete campaign CLI, unresolved Photon/billing evidence, APX maintenance
prerequisite and classic-compute capability restriction visible.
