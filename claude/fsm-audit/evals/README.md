# Evals

Files here are the answer key and the test plan. Do not give this folder to the audited agent: point it only at `toy-repo/` or `toy-repo-fixed/`, which contain no hints.

- `trigger_queries.json`: 20 queries for tuning the skill description (10 should trigger, 10 near-misses).
- `evals.json`: quality cases and assertions.
- `toy-repo/jobs.py`: a 40-line job queue with five planted defects: `fail` has no from-guard (line 26), `retry_failed` resets any state including done and has no attempts cap (line 36), `reap_expired` acts on elapsed time only and is a second writer (line 31), `complete` ignores the rows-affected result (line 21), and nothing caps attempts (line 15).
- `toy-repo-fixed/jobs.py`: the same queue with from-guards, an owner check, an attempts cap and checked row counts. It is the false-alarm control: the planted defects must not be reported as open. It still has real design questions (an owner name is not a fencing token, a fixed lease has no renewal), so a few risks are fair.

A smoke test of this folder is not evidence of accuracy: real repositories are harder.
