# LF-A iteration 7: retain the Unity Gateway service diagnostic

Iteration 6 discovered 40 services but its one inference request to
`system.ai.claude-sonnet-5` returned HTTP 400. The initial probe retained the HTTP
status but omitted the response error code/message. Do not infer a permission,
regional-availability or request-shape diagnosis from that status alone.

Repeat the same single-request smoke once with error-code/message capture.
All iteration-6 profile, model-selection, byte/token/time, no-resource-mutation
and no-provider-substitution bounds remain unchanged. This is an additional
failed-or-passed experiment, not an overwritten receipt or free quality retry.
An unsupported response parks inference acceptance for this phase; do not
iterate across models or change workspace settings to force a passing result.
