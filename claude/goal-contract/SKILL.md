---
name: goal-contract
description: Write the /goal contract for a bounded autonomous run — the acceptance criteria, the NO-GO clauses, and the anti-gaming clause — from the decisions already made in this conversation. Use when the developer asks to formulate a goal, wants a run made autonomous, or says "сформулируй goal", "write the goal", "make this a bounded run".
---

# Goal contract

Produce the text of a `/goal` contract from the discussion already in this conversation. Treat
decisions made here as settled input. Output the contract and stop — the developer invokes it.
Invoking it is the approval, and the text they send, including their edits, is the contract.

The contract is re-injected verbatim on every turn, so it has to stand alone: anything the run must
not forget belongs in it, not in the conversation.

## Rules

**1. Both outcomes are terminal.** A NO-GO with a stated blocker satisfies the goal exactly as fully
as a PASS. Without this clause, a goal like "improve X" has no honest negative ending, so it presses
the worker toward a positive result it may be unable to reach.

**2. Every predicate must be satisfiable inside the run.** If a criterion needs a purchase, an
unavailable resource, or another person's decision, it is not an acceptance criterion. It is a NO-GO
trigger. List it as one.

**3. Name what gaming would look like, specific to this task.** A generic "do not cheat" clause
forbids nothing. Name the side effect cheating would produce, so it becomes legible and reportable.

**4. An unanswerable question is a NO-GO, not a prompt.** The run terminates with the exact human
decision required. Say so explicitly, and forbid interactive question tools by name.

**5. A criterion that turns out unsatisfiable as literally written is terminal, not a reason to
loop.** State this. It is the most common way a healthy run burns itself down.

**6. One goal, one stage.** Staged work means separate goals. Never write "then wait for my approval"
into a condition: the goal mechanism re-prompts the run every time it tries to stop, so a pause
clause pauses nothing and only burns turns.

**7. Demand the discriminating observation, not the aggregate that hides it.** An exit code, a green
pipeline, "0 errors in the log", "N mutations killed" — each collapses several different outcomes
into one symbol, and the failure it hides looks exactly like success. Before writing a criterion,
ask: *what distinct outcomes does this signal merge, and which of them would I have to act on?* Then
write the criterion as the observation that separates them. "Tests pass" → "the named test that
covers X fails when X is broken". "Mutation killed" → "anchor found in source, diff non-empty, and
the NAMED test reddened — a build failure is not a kill". Automating a check without this separation
scales its visibility, not the check. (Measured: the same day, two people hit the same mutation trap;
the manual run happened to separate the outcomes and caught it, the automated one read the exit code
and recorded four false proofs.)

**8. Keep it under ~1,500 characters, and require a terse final report.** The evaluator ingests the
whole transcript and hard-fails past its context limit, so a sprawling contract or a verbose finale
can prevent adjudication entirely.

## Template

Replace every `<…>` with concrete task content. Drop clauses that do not apply.

```text
/goal This goal is SATISFIED — stop, do not start another turn — the moment EITHER TERMINAL-PASS OR
TERMINAL-NOGO appears in the transcript. Both are terminal. A NO-GO with a stated blocker satisfies
this goal exactly as fully as a PASS; never re-open it, never keep nudging toward PASS once
TERMINAL-NOGO is printed.

PASS — all of:
1. <concrete acceptance criteria, each checkable inside this run>
2. <the project's existing checks> exit 0, run against the committed candidate
3. <named adjudicator that definitely runs> reports no unresolved HIGH finding; every finding
   carries a verdict verified against file and line
4. <state hygiene: working tree clean, the reported commit is the one that was checked, no check
   was modified during the run>
5. Final report is terse and surfaces: commands run, exit codes, coverage of each check, SHAs,
   changed files, approved assumptions, autonomous decisions
Each item resolves ONLY on its named observation. "Probably holds", "looks correct" and any
unresolved item count as NOT held.
When all of the above hold, print TERMINAL-PASS and stop.

NO-GO — print TERMINAL-NOGO, report blocker, evidence, preserved state, and the exact human decision
needed, then STOP. Do this when:
- a PASS criterion turns out unsatisfiable as literally written — that is terminal, not a loop
- <task-specific ambiguity classes>
- scope expansion, production access, push, deploy, secrets, or an irreversible operation is required
- 3 identical failures with no new evidence
- any predicate can only be satisfied outside this run

ANTI-GAMING: a failed check is a failure. Never weaken, mock, exclude, or re-freeze a check to reach
PASS. A check covering a subset must print the subset and the population; a partial check is never
reported as proof. Gaming here would look like: <task-specific side effect>. Report it as failure if
it appears.

An unanswerable question is a NO-GO, not a prompt — never call AskUserQuestion.
```

## Check before handing it over

- Could an honest failure close this goal? If not, rule 1 is missing.
- Is every PASS predicate checkable by something inside the run?
- Does the anti-gaming clause name a side effect, or does it only say "do not cheat"?
- Does any PASS criterion rest on an aggregate (exit code, green pipeline, "N killed", "no errors")?
  Name the outcomes it merges and replace it with the observation that separates them.
- Could each named check return a negative verdict on THIS task at all? A check that cannot produce
  the finding class its criterion names is vacuous and passes itself.
- Is there any clause that asks the model to pause, wait, or ask?
- If the context were compacted right now, would this text alone be enough to resume?
- Under ~1,500 characters?

## Ambiguity the run may settle alone

Naming, local structure, reversible refactoring, internal organization with no observable behavior
change — decided alone and recorded.

Everything else is a NO-GO: user-visible semantics, auth/authz, data retention, schema
compatibility, destructive migration, conflicting acceptance criteria, security boundaries, scope
expansion, production access, secrets, push, deploy, anything irreversible.
