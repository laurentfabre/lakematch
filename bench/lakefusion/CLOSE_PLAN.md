# LF-A iteration 8: contract preparation and corrected gateway request

This is the final experiment slot in the eight-iteration LF-A envelope. The
iteration-7 response diagnosed a request-shape incompatibility, not unavailable
workspace capability: Claude Sonnet 5 rejects `temperature`. Remove that parameter
without changing the model or provider. Keep both earlier failures unchanged.

Sequential checks, no parallel remote work:

1. Run mastering contract/policy, generator and hygiene unit checks with a
   120-second bound. Generator unit seeds are 41–46 with 250 families.
2. Prepare the approved development/validation sources and truth in a fresh
   ignored directory; retain the compact manifest. At most 10,000 declared
   families; 32,000 actual source rows; no confirmation rows or matching scores.
   Bound this preparation to 60 seconds.
3. Repeat the single Unity Gateway request with the unsupported parameter removed.
   Keep the same profile (`fevm-gdpr2`), runtime-discovered model, 1,024 input-byte,
   128 output-token, one-call, no-retry and 45-second request limits. No service or
   account setting changes. Record actual usage and unresolved billing.

Outer experiment: 300 seconds, one child at a time, owned-process cleanup.
Local memory expectation below 512 MiB; no Spark/warehouse is started. Report
each result independently; an unavailable gateway cannot be presented as an
inference success or invalidate separate source-generation checks. No further
LF-A experiments after this slot, irrespective of outcome. Matching comparisons
belong to LF-B only after the Phase A contracts/manifests are committed.
