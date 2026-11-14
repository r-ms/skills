# Audit mode pipeline

Read before starting an Audit (a whole repository or subsystem). The shape is the one that works for finding bugs with agents: several finders in parallel, a separate step that checks each candidate against the code, then ranking. Reading code does not run it, so the report must say what it did not cover.

## Contents

- Phase 0: scope and budget
- Phase 1: map the entities
- Phase 2: scouts
- Phase 3: skeptics
- Phase 4: completeness critic
- Phase 5: report
- Without subagents
- Cost control

## Phase 0: scope and budget

Confirm with the user: the repository or subsystem; whether code may be run (default no); the language of the report; the agent budget. State the plan in numbers: "N entities, one scout each, then skeptics for the bug-class findings, one critic". Ask before starting when more than about 10 agents are needed. Do not cap silently: if you drop entities, list them in the report.

## Phase 1: map the entities

One agent (or you) lists candidate entities by searching for:

- fields named `status`, `state`, `phase`, `step`, `stage`, `kind`; enums and constant groups with state-like names;
- groups of boolean fields on one record (`is_*`, `has_*`, `*_enabled`, `*_at` timestamps used as flags);
- tables or collections that look like queues or jobs; leases, locks, heartbeats;
- cache key namespaces, marker or lock files, in-memory maps that survive across requests;
- reconcilers, watchdogs, schedulers, retry loops.

For each: location, fields, number of writers (rough), what a failure would cost. Rank by impact (data loss, wrong visible result, stuck without alarm, silent failure) and by how many places write it. Propose at most eight areas and let the user confirm or cut the list. An entity and its queue job are two entities.

## Phase 2: scouts

One scout per entity, in parallel. Give each: the Scout steps from `SKILL.md` (steps 1 to 9), the rules for the whole run, `references/idioms-by-stack.md`, `references/event-catalog.md`, `references/table-and-findings-format.md`, and the required output (the JSON of `references/report-schema.md`, one entity). Do not tell the scouts what you expect to find or how many writers there are; expected answers bias results. Each scout returns: entity card, writers inventory with unit and control, the table, forbidden combinations, finding cards, state-space estimate, unreachable and no-exit states, a treatment suggestion, and the not-covered list. Cap the reading budget per scout (for example about 60 reads and searches) and say so in the prompt.

## Phase 3: skeptics

For every finding of class `bug` (and for serious `risk`): mechanical quote check first, then the protocol in `skeptic-protocol.md`, one or two skeptics per finding with different lenses. Unverified findings stay in their own list. Keep rejected findings with reasons; re-check a sample.

## Phase 4: completeness critic

A separate agent reads: the entity list, the writers inventories, the event classes actually used, the rejected list and the not-covered lists, and answers: which entities were never scouted; which event classes appear in no table; which idioms or file types were not searched (scripts, migrations, configs, other languages); which configurations were not read; where two scouts disagree on the same shared field. It proposes a second round for gaps. Run the second round if the budget allows; otherwise list the gaps.

## Phase 5: report

Merge into one JSON, deduplicate findings that share a root cause across entities (for example the same unconditioned status write in several handlers) and say so as a shared fix; run `scripts/check_quotes.py` once more on the merged file; render with `scripts/render_report.py`. Report sections: summary with counts and their units; scope and coverage; entities; writers inventories; tables; findings by severity with provenance and skeptic verdict; unreachable and dead states; state-space estimates with projections; treatment decisions; rejected findings; not covered; method notes. Do not include accuracy numbers from papers.

## Without subagents

Do the same phases sequentially. Run each scout in a separate fresh session, saving its JSON to disk; run each skeptic as another fresh session fed only the finding card, the writers list and the prompt; run the critic last. If you must do everything in one session, write all cards to disk first, do the skeptic pass reading only the cards, and mark every finding `verification: self-check (weak)`.

## Cost control

- One scout per entity, not one per file.
- Check quotes mechanically before spending model calls on a finding.
- Skip skeptics for notes; use them for bugs and serious risks.
- Prefer one pass per finding and a second only for severity 1 or 2.
- Report how many agents ran and how many findings each stage rejected.
