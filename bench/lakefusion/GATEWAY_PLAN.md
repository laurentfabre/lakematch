# LF-A iteration 6: Unity Gateway capability

Selected profile: `fevm-gdpr2`. LF-DEC-003 authorizes AI through Unity Gateway.
Hypothesis: this workspace can discover system model services and invoke one
through `/ai-gateway/mlflow/v1/chat/completions` under the selected identity.

Read at most 100 `system.ai` services with BASIC metadata, then select the highest
numbered discovered Claude Sonnet. Make at most one synthetic connectivity call,
with at most 1,024 UTF-8 input bytes and 128 output tokens, no inference retries,
45-second request timeout and 120-second outer experiment timeout. No resources,
preview settings, ACLs or gateway routing configurations are created or changed.
If metadata or inference is unavailable, retain that outcome and continue local
work; do not switch to another provider, legacy endpoint or workspace.

Record service name, path, timing, usage if returned and request/response hashes.
No auth headers or tokens are persisted. Cost remains unreconciled pending
resource/time-window billing evidence. A successful synthetic response only
proves this identity's connectivity; app-principal access, structured production
error handling, cost controls and quality benefit remain later acceptance work.
