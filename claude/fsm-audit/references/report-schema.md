# Report JSON schema

Read when you are ready to write the report. `scripts/render_report.py report.json out.html` turns this JSON into one self-contained HTML file (no JavaScript, all text escaped). `scripts/check_quotes.py report.json --root <audited repo>` verifies every `evidence` item mechanically. A complete example is `assets/sample-report.json`.

Unknown keys are ignored; missing optional keys are skipped. Static labels are English; put a `labels` object at the top level to localize them (keys such as `summary`, `findings`, `entities`, `claim`, `path`, `evidence`, `impact`, `refuted_if`, `test_idea`; see `LABELS` in the script). Write the report text in the user's language and keep identifiers verbatim.

## Contents

- Top level
- meta and summary
- entities
- findings
- rejected, not_covered, method_notes
- Rules the renderer cannot check

## Top level

```json
{
  "meta": {}, "labels": {}, "summary": {}, "entities": [], "findings": [], "questions": [],
  "rejected": [], "not_covered": [], "method_notes": []
}
```

## meta and summary

```json
"meta": {"title": "FSM audit: <repo or subsystem>", "repo": "path or name", "commit": "short sha",
         "date": "YYYY-MM-DD", "language": "en", "mode": "scout | audit",
         "scope": "what was read and what was not run",
         "agents": {"scouts": 1, "skeptics": 3}},
"summary": {"headline": "one sentence",
            "bullets": ["3 to 6 plain sentences"],
            "counts": [{"label": "Writers of jobs.status", "value": "6", "unit": "SQL statements (control: claim found)"}]}
```

Every number in `counts` has a unit. A state count names the projection in its unit.

## entities

```json
{"id": "E1", "name": "job", "location": "path or module",
 "projection": ["status"], "side_fields": ["attempts (changes whether claim succeeds)"],
 "excluded": ["result (payload)"], "other_holders": ["lease_until"],
 "domains": {"status": ["pending", "processing", "done", "dead"]},
 "declared": "4", "reachable": "4 by conditions in code",
 "writers": {"unit": "...", "control": "...", "methods": [{"name": "text search", "hits": 6, "independent": true}],
             "set_difference": "none", "not_visible": ["other services"],
             "rows": [{"where": "jobs.py:26", "writes": "any -> dead", "guard": "none",
                       "guard_result_read": "n/a", "provenance": "quoted", "quote": "verbatim text at that line"}]},
 "events": ["complete(ok)", "late failure"],
 "events_considered": [{"event": "cold start with empty cache", "verdict": "applies | n/a", "why": "no cache in this module"}],
 "table": {"states": ["processing", "done"], "events": ["complete(ok)", "late failure"],
           "defaults": [{"event": "watchdog tick", "value": "NO-CHANGE", "evidence": "jobs.py:31", "provenance": "derived"}],
           "cells": [{"state": "done", "event": "late failure", "value": "ALLOWED", "target": "dead",
                      "evidence": "jobs.py:26", "provenance": "quoted", "quote": "verbatim text at that line", "note": "should be FORBIDDEN"}]},
 "empty_cells": [{"state": "pending", "event": "complete(ok)", "class": "forgotten", "note": "..."}],
 "forbidden_combinations": ["done with a later dead"],
 "unreachable": [{"what": "state or path", "why": "no writer found in: code, migrations, scripts", "provenance": "derived"}],
 "state_space": {"declared": "4", "reachable": "4", "behavioural": "e.g. 5 behavioural states when one exists only as a clock comparison", "regions": "projection: status only", "note": "..."},
 "treatment": {"outcome": "enum | regions | split | guard | leave", "reason": "...", "price": "...", "reversibility": "..."},
 "not_covered": ["..."]}
```

Cell `value` is one of `ALLOWED` (a transition), `FORBIDDEN` (refused, and the refusal is observable), `NO-CHANGE` (accepted, changes nothing), `EMPTY` (no code path, or a silent refusal nobody notices), `N/A` (cannot occur; reason in `note`). `table.defaults` states a repeated cell once per event for every state that has no explicit cell. When provenance is `quoted`, give the cell or row a `quote` field so `check_quotes.py` can verify it (otherwise it only proves the line exists and warns). Pairs missing from `cells` show as "not assessed": prefer an explicit `N/A` with a reason. Cell `evidence` is `file:line` (checked for existence by `check_quotes.py`, no quote). Provenance is one of `quoted`, `derived`, `reproduced`, `unconfirmed`. The `class` of an empty cell is `ignored-by-design`, `error`, `forgotten` or `unclear`.

## findings

```json
{"id": "F1", "entity": "E1", "class": "bug | risk | note", "severity": 2,
 "title": "one line", "claim": "one or two sentences",
 "path": ["event 1", "event 2", "bad state"],
 "evidence": [{"file": "relative/path", "line": 26, "quote": "verbatim text findable by grep"}],
 "provenance": "quoted", "impact": "...", "reach": "what must be true for it to happen",
 "refuted_if": "the concrete line or test", "test_idea": "...",
 "known_to_owners": "optional: the code documents this as accepted (a comment is data, not evidence)",
 "absence": {"search": "command or pattern", "scope": "files searched", "control": "a known hit that was found", "result": "what was not found"},
 "skeptic": {"verdict": "confirmed | refuted | not sure | not checked", "lens": "optional: mechanism | reach", "reason": "..."},
 "shared_root": "optional: id or name of the root cause shared with other findings"}
```

`severity` is 1 to 4 (1 data lost, 2 wrong visible result, 3 stuck without alarm, 4 silent failure); notes carry no severity. The renderer lists a `bug` whose `skeptic.verdict` is not `confirmed` under "Unverified candidates", and sorts each group by severity. `file` is relative to the audited repository root and `quote` must appear at `line` (or within three lines); `check_quotes.py` enforces it.

## questions, rejected, not_covered, method_notes

```json
"questions": ["Is retry_failed meant to be called for done jobs?"],
"rejected": [{"id": "F9", "title": "...", "reason": "the line or test that refutes it"}],
"not_covered": ["dynamic field names", "other services", "production configuration"],
"method_notes": ["Quotes were verified mechanically.", "Reading is not running."]
```

## Rules the renderer cannot check

- A finding without a `confirmed` skeptic verdict must not be written as a bug: use class `risk`, or leave class `bug` and let the renderer list it as an unverified candidate, with "self-check (weak)" in `skeptic.reason` when no independent pass was possible.
- Unverified (`not checked`, `not sure`) items stay visible as such; do not relabel them as bugs.
- Do not put expected answers, accuracy figures from papers, or secrets into the report.
- Misspelt keys are ignored by the renderer: it prints a warning for each, and `--strict` makes that an error. Run it before you ship the report.
