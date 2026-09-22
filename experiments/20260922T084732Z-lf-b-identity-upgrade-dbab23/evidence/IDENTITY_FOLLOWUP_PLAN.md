# LF-B iteration 4 — identity upgrade and timestamp consistency

The first identity experiment passed 134 checks and its lifecycle/restart probe:
`20260922T084351Z-lf-b-persistent-identity-6122ca`. Its evidence remains unchanged.
Review afterward identified a real portability issue: serialized creation times
followed the PostgreSQL session timezone, so restoration from a differently
configured connection could reject equivalent timestamps as unequal state.

Normalize identity receipt/snapshot times to UTC. Add a regression that allocates
and merges from one connection, restores from a Pacific/Auckland connection,
then compares exact reads/retries. Also close the additive migration evidence gap:
upgrade a populated 0002 prototype without rekeying, and show that an unattributed
merged row makes 0003 fail atomically without changing its earlier schema/data.
Check identical source keys in different source namespaces remain distinct.

This run consumes LF-B slot 4, regardless of outcome. Repeat the existing bounded
identity suite/lifecycle with fresh report paths. Retain the same 300-second
outer limit, 180-second test limit, 4 GiB main-process RSS gate, private local
PostgreSQL/Spark and cleanup rules. No corpus, remote service, selection method
or confirmation partition changes. The original 0001/0002 files stay immutable.
