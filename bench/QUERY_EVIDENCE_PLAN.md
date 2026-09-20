# Bounded query-history and billing evidence capture

Run after the active train/cluster fixture is terminal. The shared warehouse
`4aaa742e4712c3c9` is stopped and is not campaign-owned. Create one uniquely
named/tagged serverless PRO warehouse, 2X-Small, one cluster, 10-minute fallback
auto-stop. Limit startup to 300 seconds, each of two read-only statements to
180 seconds, and explicit warehouse shutdown to 180 seconds. Outer runner:
1,200 seconds. No scheduled query, no table writes, no shared resource changes.

Read only billing rows attributable to explicit completed campaign job/run/
pipeline receipts, and the 16 exact pipeline statement IDs in the corrected
DQX Photon capture. Preserve source hashes, request/result IDs, raw responses,
truncation/row-limit findings and the final STOPPED state. Missing or delayed
rows are unresolved evidence, never zero cost. Usage totals are not invoice
charges. Query text can support stage mapping, but cannot substitute for
executed operator-profile JSON. A failed permission check is retained without
repeating the same query or switching profiles.
