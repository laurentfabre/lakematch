# Declarative Automation Bundle

Read the installed `databricks-core`, `databricks-pipelines`, `databricks-jobs`
and `databricks-dabs` skills for changes here. `../goal.md` is authoritative.
Use only the explicitly selected `fevm-gdpr2` profile. Public/synthetic fixtures
only. No schedules or continuous pipelines; one owned run, bounded timeouts,
terminal-state polling and explicit cleanup. Classic capability is unavailable.

These files currently prepare and measure frozen-model inference. They do not
establish training/clustering task, app, Genie or complete ZR-6 acceptance.
