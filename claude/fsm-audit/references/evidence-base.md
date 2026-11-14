# Evidence base

Read when someone asks "why does the skill do this?" or before quoting a source in a report. The skill is a practice built on analogies, not a proven method. This file separates what is well sourced from what is practice, and records what was checked. Sources were read in 2026; pages change, so re-check a number before you publish it. Do not copy accuracy figures from these sources into reports.

## Contents

- The honest summary
- Well sourced: event classes and mechanisms
- Practice only: our own claims
- Empirical context and what it does not prove
- Design guidance for treatment
- Auditing with language models
- Tools and their documented limits
- Packaging and distribution
- Not verified, open gaps
- Pilot of this method

## The honest summary

- No empirical study was found that measures implicit lifecycle bugs in ordinary application code (status columns, queue jobs, flags, caches). Published extraction work targets network protocols, parsers, PLC and embedded C, and starts from a model rather than from messy business code. Do not write "research shows implicit state machines cause most bugs".
- What is well sourced are the mechanisms behind the event catalog: retries, restarts, late events, leases and zombies, reapers, outbox gaps, timers, caches, conditional updates.
- Three of our claims are practice, not literature: "state is a combination of fields", "silent empty cell is a defect" (UML treats unhandled events as dropped), and "a read error read as absent".

## Well sourced: event classes and mechanisms

- Retries are selfish and multiply across layers; cap attempts, use backoff with jitter, make side effects idempotent: AWS Builders' Library, "Timeouts, retries, and backoff with jitter" (2019) https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter and "Making retries safe with idempotent APIs" https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/. Google SRE book, "Addressing cascading failures" (2016) https://sre.google/sre-book/addressing-cascading-failures/.
- Activity side effects may run more than once; "exactly once" refers to how a workflow observes a result; default retry is very long unless bounded; "not picked up" and "picked up then hung" are different stalls with different timers: Temporal docs https://docs.temporal.io/activity-definition and https://temporal.io/blog/activity-timeouts.
- A queue visibility timeout is a lease; a consumer that does not delete in time loses the message to another; dead-letter queues are the terminal exit: Amazon SQS docs https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html. Celery with a Redis broker re-delivers unacknowledged tasks after the visibility timeout (default one hour) and a task with a later ETA repeats: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html.
- A lease holder can pause and write after expiry; checking the clock before writing does not help; a fencing token checked by the storage does: Kleppmann, "How to do distributed locking" (2016) https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html. (There is a public dispute about Redlock that was not reviewed.)
- A reaper that returns stuck jobs by elapsed time can restart a job that is still running: Oban Lifeline docs https://oban.hexdocs.pm/Oban.Lifeline.html.
- Jobs run at least once, so pass ids and re-read state: Sidekiq best practices https://github.com/sidekiq/sidekiq/wiki/Best-Practices. Webhook providers do not promise order; dedupe by event id; re-fetch the object: Stripe docs https://docs.stripe.com/webhooks.
- Dual writes are not atomic; use a transactional outbox and idempotent consumers: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html. Two stores for one fact drift apart: Kleppmann (2015) https://martin.kleppmann.com/2015/05/27/logs-for-data-infrastructure.html.
- Cache races ("stale set") and lease tokens at scale: Nishtala et al., NSDI 2013 https://www.usenix.org/system/files/conference/nsdi13/nsdi13-final170_update.pdf. A service that cannot work with an empty cache fails when it is lost: SRE book (above). Retries plus cache weakness can create metastable failure: Bronson et al., HotOS 2021 https://sigops.org/s/conferences/hotos/2021/papers/hotos21-s11-bronson.pdf.
- Under PostgreSQL Read Committed an `UPDATE ... WHERE status = X` re-checks the condition on the newest row version, so it acts as an atomic from-check; under Repeatable Read and Serializable the application must retry on serialization errors: https://www.postgresql.org/docs/current/transaction-iso.html. `CHECK` sees only the new row, not the old value, so it cannot express a transition: https://www.postgresql.org/docs/current/ddl-constraints.html.
- Bulk updates bypass versions, callbacks and events in the common ORMs (vendor docs, see `idioms-by-stack.md`): Rails `update_all` https://api.rubyonrails.org/classes/ActiveRecord/Relation.html; Hibernate `@Version` and bulk updates; SQLAlchemy `version_id_col` https://docs.sqlalchemy.org/en/20/orm/versioning.html; EF Core `ExecuteUpdate` https://learn.microsoft.com/en-us/ef/core/saving/execute-insert-update-delete.

## Practice only: our own claims

- "State is a combination of fields": no direct source. Indirect support: copies inside messages go stale (Sidekiq, Stripe) and dual writes keep state in two systems. Present as method.
- "A silent empty cell is a defect": no direct source; unhandled events are dropped by default in UML-style designs. Libraries differ: Umple, XState v5 and python-statemachine `StateChart` ignore silently; Akka FSM logs a warning; python-statemachine `StateMachine` and XState v4 strict mode raise. Hence step 6 classifies each empty cell instead of flagging it. Sources: https://cruise.umple.org/umple/UnspecifiedEvents.html, https://doc.akka.io/docs/akka/2.3/scala/fsm.html, https://python-statemachine.readthedocs.io/en/latest/api.html, https://stately.ai/docs/migration.
- "A read error read as absent": no strong primary source for this class; the nearest general result is Yuan et al. (below). The Go standard library distinguishes "does not exist" from other errors, which illustrates the pattern.
- Three independent search paths with a control site and set comparison: not described in the literature; it is our proposal and must be measured.

## Empirical context and what it does not prove

- Yuan et al., OSDI 2014, "Simple Testing Can Prevent Most Critical Failures" https://files.usenix.org/s3fs-public/cdn/osdi14-paper-yuan.pdf: 198 failures in five distributed systems; 48 catastrophic; 44 of 48 (92%) were caused by incorrect handling of non-fatal errors that the software signalled. Does not show that implicit automata cause most bugs; small sample, Java mostly. Use it only to justify analysing failure, timeout and retry columns.
- Harel, "Statecharts: a visual formalism" (1987) https://www.state-machine.com/doc/Harel87.pdf: two components with 1000 states each give a million in the flat product; hierarchy and orthogonality avoid it. It is arithmetic, not a measurement of reachable states. Basis for "independent axes are regions, count reachable not declared".
- Strom and Yemini, "Typestate" (IEEE TSE 1986): the operations permitted depend on a state. Abstract read only. Applying it to database rows is an analogy.
- Minsky, "Effective ML Revisited" (2011) https://blog.janestreet.com/effective-ml-revisited/: replace a record of optional fields with a variant type. A design rule, not a result. Authorship wording ("make illegal states unrepresentable") is attributed to Minsky by his own later statement; the idea is older.
- Bailis et al., "Feral Concurrency Control", SIGMOD 2015 http://www.bailis.org/papers/feral-sigmod2015.pdf: 67 Rails applications; application-level validations are used more than 37 times as often as transactions; many are unsafe under concurrency. About invariants such as uniqueness, not status transitions.
- Warszawski and Bailis, "ACIDRain", SIGMOD 2017 http://www.bailis.org/papers/acidrain-sigmod2017.pdf: 22 critical vulnerabilities in 12 e-commerce applications; 17 come from wrong transaction scope and appear even under the strongest isolation. Eight to twelve applications is a small sample; e-commerce only.
- Tang et al., "Ad Hoc Transactions in Web Applications", SIGMOD 2022: 91 hand-made coordination mechanisms in 8 applications; 53 had correctness problems (abstract only was read). Basis for treating hand-rolled locks, version columns and "processing" flags as part of the automaton.
- Qiu et al. (MSR 2022) on server-side request races: races that break semantics without crashes are common (abstract only). Yang et al. (ICSE 2020) on data constraints: developers struggle to keep constraints consistent across components (abstract only). None of these measures the share of implicit automata among defects.

## Design guidance for treatment

- Make illegal states unrepresentable (Wlaschin, https://fsharpforfunandprofit.com/posts/designing-with-types-making-illegal-states-unrepresentable/); boolean blindness (Harper, 2011); parse, don't validate (King, 2019); temporal coupling (Seemann, 2011). Against: constructive types are hard to evolve and miss some legitimate values (Wayne, https://hillelwayne.com/post/constructive/). Resolution in the skill: five outcomes with price and reversibility, never "always enum".
- Independent flags must not be merged: statecharts keep independent regions (Harel); the state pattern literature describes the impossible-combination problem of boolean groups: https://gameprogrammingpatterns.com/state.html.
- Feature toggles are state with an owner and a lifetime: Mahdavi-Hezaveh et al., arXiv 1907.06157. The combinatorial blow-up of flags is arithmetic there, not a finding.
- Exhaustiveness linters and compiler checks: Go `exhaustive` https://github.com/nishanths/exhaustive and `go-check-sumtype`; typescript-eslint `switch-exhaustiveness-check` https://typescript-eslint.io/rules/switch-exhaustiveness-check (a trailing `default` makes it dead code); Python `assert_never` https://typing.python.org/en/latest/guides/unreachable.html; Kotlin `when` https://kotlinlang.org/docs/control-flow.html.

## Auditing with language models

- Self-correction without outside feedback does not improve reasoning (Huang et al., arXiv 2310.01798), so verification must be an independent pass grounded in code, a trace or a test.
- A single-author preprint (arXiv 2604.19049) reports a staged pipeline (finders, adversarial reviewers, execution, cross-family critic) and a case where about ten reviewers confirmed a wrong finding while one run of the code refuted it. Preprint, no ablation: use it as a caution, not a measurement.
- Framing a change as correct lowers detection (arXiv 2603.18740, preprint); drop comments and PR text that assert correctness. LLM verifiers also tend to flag correct code as defective (arXiv 2508.12358): demand a trace and allow "not sure".
- A second AI pass over static-analysis alerts cut false positives sharply but suppressed about a fifth of true positives in the best configuration (arXiv 2601.22952, preprint): keep rejected findings, with reasons, and re-check a sample.
- Voting raises precision but can cost recall; "no verdict on disagreement" rules cut effective recall (PromptAudit, arXiv 2605.24171; Kodus engineering blog). Use agreement for disputed items, not for discovery. Rejecting only with a concrete counter-line or test was the change that helped in the vendor report.
- Mechanical checks first: file, line and verbatim quote exist (HalluJudge idea, arXiv 2601.19072); models treat line numbers as tokens.
- Run-to-run variance is large: one reported large-scale study found single-run pass@1 varying by several points; use several runs and report spread (arXiv 2602.07150). Anthropic's agent evaluation guide recommends multiple runs, pass^k for reliability, and a calibrated judge with an "unknown" outcome: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents.
- Vendor numbers (precision, "less than 1% wrong") were seen only through secondary reports and measure rejection by engineers, not truth; do not use them.
- Existing public skills reviewed: `audit-fsm` for the Open Autonomy framework (deterministic tools first, parallel agents, quote verification, false-positive guide, "not covered" section; explicit machines only) https://github.com/valory-xyz/open-autonomy/tree/main/claude-skills/audit-fsm. Several registry skills for state-machine review exist; only descriptions were seen, none has a blind skeptic or injected-defect controls as far as reviewed.

## Tools and their documented limits

- ripgrep skips files named in `.gitignore`, hidden files and binaries by default (`-u` and `-uu` relax this): a writer inside an ignored or generated directory is invisible unless you say so. https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md.
- Semgrep states it gives no soundness guarantees and expects false positives and false negatives; by default it skips tests, vendor directories, files over 1 MB and unknown extensions; matching is mostly within one file: https://docs.semgrep.dev/writing-rules/data-flow/data-flow-overview, https://docs.semgrep.dev/ignoring-files-folders-code.md.
- ast-grep does no type, scope or data-flow analysis; one rule targets one language; relational rules need `stopBy: end` or they silently look only at the neighbour: https://ast-grep.github.io/advanced/faq.html, https://ast-grep.github.io/cheatsheet/rule.html.
- SCIP and LSIF indexes give exact references but only for languages with an indexer and a buildable project; search-based navigation is textual: https://sourcegraph.com/blog/announcing-scip.
- No measured recall of text search versus AST search on multi-language repositories was found. A small blog pilot reported about two thirds recall for both and a third of references found by nobody (weak source). Treat the control site and the second method as necessary, not sufficient.
- Active automata learning and passive learning (k-tails, RPNI) produce hypotheses, never proofs; learned models depend on the input alphabet and on trace completeness: Vaandrager, "Model Learning", CACM 2017 https://www.labri.fr/perso/anca/Games/Bib/vaandrager-model-learning.pdf; AALpy https://github.com/DES-Lab/AALpy; LearnLib https://github.com/LearnLib/learnlib.
- Model-based testing: fast-check, Hypothesis, rapid, proptest-state-machine and others are listed with caveats in `verification-ladder.md`. ShardStore (Amazon S3, SOSP 2021) https://jamesbornholt.com/papers/shardstore-sosp21.pdf used executable reference models plus property-based tests and stopped 16 issues before production; models were built per component with a stable interface. MongoDB (VLDB 2020) https://arxiv.org/pdf/2006.00915 judged trace checking of a large code base impractical. AWS used TLA+ for designs (2015) https://lamport.azurewebsites.net/tla/amazon-excerpt.html.

## Packaging and distribution

- Agent Skills specification: `SKILL.md` with `name` (1 to 64 characters, lowercase letters, digits, hyphens, equal to the folder name) and `description` (up to 1024 characters); progressive disclosure; references one level deep: https://agentskills.io/specification, best practices https://agentskills.io/skill-creation/best-practices, description tuning https://agentskills.io/skill-creation/optimizing-descriptions, script guidance https://agentskills.io/skill-creation/using-scripts.
- Anthropic skill best practices (third-person description, evaluation first, test on several model sizes): https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices. Claude Code skills: https://code.claude.com/docs/en/skills (only the first 5000 tokens of an invoked skill survive context compaction). Plugins and marketplaces: https://code.claude.com/docs/en/plugin-marketplaces.
- Supply-chain risk is real: a measurement of about 98,000 skills from two registries confirmed 157 malicious ones (arXiv 2602.06547). Hence the read-only, offline, no-environment-access design and the short readable scripts.
- Short focused skills beat long ones in one benchmark (SkillsBench, arXiv 2602.12670, preprint); numbers differ between versions.

## Not verified, open gaps

- Brooker and Desai, "Systems Correctness Practices at AWS" (ACM Queue 2024, CACM 2025): exists; full text could not be read (403), so its practices and their order are not used here.
- Typestate, Tang et al., Qiu et al. and Yang et al.: abstracts only. The fairness of generalizing Rails, e-commerce or Java results to other stacks is an assumption.
- Not studied: orchestrators other than Airflow (Dagster, Prefect, Temporal internals), payment providers other than Stripe, OAuth state and token rotation, CI other than GitHub Actions, local mobile databases.
- Idiom examples in `idioms-by-stack.md` come from vendor documentation and general knowledge and were not executed; TypeORM, Sequelize, Laravel on MySQL and some Hibernate 6 details were not confirmed from primary pages.
- Semantics checked only for PostgreSQL Read Committed; other databases and isolation levels must be checked case by case.

## Pilot of this method

An early version of the method was run on one private codebase, blind (the runs were not told the known defects). On code before a known fix: the method found two of three known defects in two of three runs, as plain review also did; it did not find a defect whose state lived in a separate queue job, which produced the rule that a job about an entity is its own entity; on the fixed code it raised no false alarm in eight checks. Three runs on one project say almost nothing about reliability. The toy repository in `evals/` and its fixed twin allow a quick smoke test; real evaluation needs several repositories of different stacks, injected defects, runs with and without the skill, repeated runs, and small, medium and large models.
