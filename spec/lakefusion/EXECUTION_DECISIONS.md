# Execution amendments after the Phase A freeze

These explicit user decisions amend the current execution constraints. The
[original decisions](DECISIONS.md), [protocol](PROTOCOL.md) and
[Phase A freeze receipt](frozen/phase-a-v0.1.json) remain byte-for-byte historical
records. References to the earlier cap or private visibility in dated evidence
describe the conditions at that time.

## LF-DEC-005 — Raise the LF-B experiment cap to 12

**Selected by Laurent on 2026-09-22:** “raise it to 12”.

This answers the proposed increase from eight to twelve total LF-B experiments.
The existing eight runs remain consumed, including failures; four additional
iterations are available under the [extension plan](../../bench/lakefusion/NEXT_EXPERIMENTS.md).
This supersedes the protocol's eight-iteration cap for **LF-B only**. Other LF
phase caps and all original ZR limits remain unchanged.

Keep the declared time, memory, candidate, join and single-active-remote-run
bounds. Quality targets and the confirmation holdout remain frozen. The increase
does not establish acceptance or authorize tuning on confirmation results. Each
new experiment still requires its committed implementation, run plan and inputs,
the bounded runner, terminal evidence and cleanup.

## LF-DEC-006 — Public repository and publication

**Selected by Laurent on 2026-09-22:** “change to public”.

Use the public GitHub repository `laurentfabre/lakematch`. This supersedes the
private-repository requirements in the original campaign, LF-DEC-002 and the
roadmap goal. The standing instruction to push completed work now applies to
that public destination, through the existing managed hooks.

A read-only GitHub check on this date returned `private=false` and
`visibility=public`; no visibility API mutation was needed. Preserve the
Apache-2.0 license and existing public/synthetic-data restrictions. This decision
does not publish a package to PyPI, change commercial scope, choose a customer
workspace or grant rights to third-party implementation assets.
