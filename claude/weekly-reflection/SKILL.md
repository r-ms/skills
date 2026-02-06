---
name: weekly-reflection
description: Weekly self-reflection. Collects data from task tracker, Git, analyzes AI sessions, and conducts a structured interview.
triggers:
  - /weekly-reflection
  - /reflection
  - weekly reflection
---

# Weekly Reflection Skill

Weekly self-reflection for AI-first teams. Collects context from your task tracker, Git, and Claude Code sessions, conducts a structured interview, and generates a report.

## Configuration

Before using, set these variables in the skill or in your CLAUDE.md:

```
# Task tracker (Jira, Linear, YouTrack, GitHub Issues, etc.)
TRACKER_TYPE=jira                          # jira | linear | youtrack | github
TRACKER_API_URL=https://your-org.atlassian.net
TRACKER_TOKEN_PATH=~/.config/tracker/token # path to API token file
TRACKER_PROJECT=PROJ                       # project key
TRACKER_SPRINT_FIELD=sprint                # custom field name for sprint

# Git repositories to scan
REPOS_ROOT=~/projects                      # parent directory containing your repos
REPOS_SCAN_DEPTH=3                         # how deep to search for .git directories

# Output
REFLECTIONS_PATH=knowledge-base/team       # where to store reflection reports
```

## Workflow

### Phase 0: Determine Context

Determine reflection parameters:

```bash
# User
USER_NAME=$(git config user.name)
USER_SLUG=$(echo "$USER_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')

# Period: Monday of current week → today
WEEK_START=$(date -v-monday +%Y-%m-%d 2>/dev/null || date -d "last monday" +%Y-%m-%d)
WEEK_END=$(date +%Y-%m-%d)
```

Determine the current sprint via your tracker's API. Examples:

<details>
<summary>Jira</summary>

```bash
curl -s -u "email:$(cat $TRACKER_TOKEN_PATH)" \
  "$TRACKER_API_URL/rest/agile/1.0/board/{boardId}/sprint?state=active" | \
  jq '.values[0].name'
```

</details>

<details>
<summary>Linear</summary>

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $(cat $TRACKER_TOKEN_PATH)" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ cycles(filter:{isActive:{eq:true}}){nodes{name number}}}"}' | \
  jq '.data.cycles.nodes[0]'
```

</details>

<details>
<summary>YouTrack</summary>

```bash
NOW_MS=$(($(date +%s) * 1000))
curl -s -H "Authorization: Bearer $(cat $TRACKER_TOKEN_PATH)" \
  "$TRACKER_API_URL/api/agiles?fields=id,name,sprints(id,name,start,finish)" | \
  jq --argjson now "$NOW_MS" '
    .[] | select(.name == "YOUR_BOARD") |
    .sprints[] | select(.start != null and .finish != null and .start <= $now and .finish >= $now) |
    .name
  '
```

</details>

<details>
<summary>GitHub Projects</summary>

```bash
gh api graphql -f query='
  { viewer { projectV2(number: PROJECT_NUMBER) {
    items(first: 50, orderBy: {field: POSITION, direction: ASC}) {
      nodes { fieldValueByName(name: "Sprint") { ... on ProjectV2IterationFieldValue { title } } }
    }
  }}}' | jq '.data.viewer.projectV2.items.nodes[0].fieldValueByName.title'
```

</details>

### Phase 1: Parallel Data Collection

Launch 3 parallel Task agents to collect data:

#### Agent 1: Task Tracker (subagent_type: general-purpose)

Collect user's tasks from the current sprint and monthly epics/objectives:

**What to collect:**
1. **Sprint tasks** — all tasks assigned to the user in the current sprint (id, title, status, story points)
2. **Monthly epics/objectives** — active epics or goals for the current month
3. **Delegated tasks** — tasks created by the user and assigned to others (this is work too)

Adapt the API calls to your tracker. The key queries:
- My sprint tasks: `project = PROJ AND sprint = currentSprint() AND assignee = currentUser()`
- Active epics: `project = PROJ AND type = Epic AND updated >= startOfMonth()`
- Created for others: `project = PROJ AND creator = currentUser() AND assignee != currentUser() AND created >= WEEK_START`

#### Agent 2: Git (subagent_type: general-purpose)

Collect commits from all repositories:

```bash
USER=$(git config user.name)
SINCE="$WEEK_START"  # From Phase 0

echo "=== Git Activity for $USER since $SINCE ==="

find $REPOS_ROOT -maxdepth $REPOS_SCAN_DEPTH -name '.git' 2>/dev/null | while read g; do
  repo=$(dirname "$g")
  repo_name=$(basename "$repo")
  commits=$(git -C "$repo" log --author="$USER" --since="$SINCE" --oneline --no-merges 2>/dev/null)
  if [ -n "$commits" ]; then
    echo ""
    echo "## $repo_name"
    echo "$commits"
  fi
done
```

#### Agent 3: Claude Sessions Analysis (subagent_type: general-purpose)

Analyze AI sessions for the week using the learnings framework.

Find session files:
```bash
find ~/.claude/projects -name "*.jsonl" -mtime -7 2>/dev/null
```

Read each jsonl file and categorize insights using this framework:

**Workflow Improvements** (what improved your work):
- `plan_before_code` — planning before writing code
- `requirements_first` — clarifying requirements before implementation
- `parallel_exploration` — using parallel agents for research
- `test_first` — writing tests before implementation
- `incremental_approach` — incremental approach to tasks
- `docs_first` — documentation before code
- `dry_run_first` — checking commands before execution
- `validation_before_commit` — validation before committing

**Automation Opportunities** (what can be automated):
- `skill` — repeating process → create a skill
- `hook` — automatic check → create a hook
- `subagent` — complex task → create a subagent
- `mcp_integration` — service integration → MCP server
- `alias` — frequent command → alias

**CLAUDE.md Additions** (what to add to project instructions):
- `architecture_rule` — architectural rule for the project
- `code_convention` — code convention
- `gotcha` — non-obvious quirk or trap
- `context_file` — file to load into context
- `command_shortcut` — command shortcut
- `tool_preference` — tool preference

**Knowledge to Capture** (knowledge worth preserving):
- `codebase_fact` — fact about the codebase
- `solution_pattern` — problem-solving pattern
- `external_resource` — useful external resource
- `team_convention` — team convention

For each category, extract 2-3 concrete examples from the sessions.

### Phase 2: Show Context

After all agents complete, show the user the collected context:

**My sprint tasks:**
| ID | Task | SP | Status |
|----|------|:--:|--------|
| PROJ-123 | ... | 5 | In Progress |

**Tasks created for others:**
| ID | Task | Assignee | SP | Status |
|----|------|----------|:--:|--------|
| PROJ-456 | ... | @colleague | 3 | Open |

**Git summary:**
- repo-a: X commits
- repo-b: Y commits

**AI Learnings:**
- Workflow improvements: ...
- Automation opportunities: ...
- CLAUDE.md suggestions: ...

### Phase 3: Interview

Conduct a structured interview, asking questions one at a time:

1. **Results** — What did you accomplish? Which tasks do you consider the main achievements?

2. **Problems** — What got in the way? What blockers or difficulties came up?

3. **Closing tasks** — Which tasks can be closed? (show the list of Open/In Progress tasks)

4. **Connection to monthly goals** — How does this week's work relate to Epics? What's the contribution to monthly goals?

5. **Improvement suggestions** — Any ideas for improving processes, tools, workflow?

6. **What felt good** — What was the highlight of the week? (a moment, achievement, colleague, tool)

Use AskUserQuestion for each question.

### Phase 4: Generate Report

Create a report using the template from `templates/reflection.md`:

```
{REFLECTIONS_PATH}/{user-slug}/{sprint}/reflection.md
```

For example: `knowledge-base/team/john-doe/sprint-12/reflection.md`

Create directories if they don't exist.

### Phase 5: Update Tracker

Based on the answer to question 3, generate commands to close tasks.

**DO NOT execute automatically** — only show the commands for manual execution.

Adapt to your tracker:

<details>
<summary>Jira</summary>

```bash
curl -X POST -u "email:$(cat $TRACKER_TOKEN_PATH)" \
  -H "Content-Type: application/json" \
  -d '{"transition":{"id":"DONE_TRANSITION_ID"}}' \
  "$TRACKER_API_URL/rest/api/3/issue/PROJ-123/transitions"
```

</details>

<details>
<summary>Linear</summary>

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $(cat $TRACKER_TOKEN_PATH)" \
  -H "Content-Type: application/json" \
  -d '{"query":"mutation { issueUpdate(id: \"ISSUE_ID\", input: { stateId: \"DONE_STATE_ID\" }) { success }}"}'
```

</details>

<details>
<summary>YouTrack</summary>

```bash
curl -X POST -H "Authorization: Bearer $(cat $TRACKER_TOKEN_PATH)" \
  -H "Content-Type: application/json" \
  -d '{"customFields":[{"name":"State","$type":"StateIssueCustomField","value":{"name":"Done"}}]}' \
  "$TRACKER_API_URL/api/issues/PROJ-123"
```

</details>

## Output

- Reflection report: `{REFLECTIONS_PATH}/{user-slug}/{sprint}/reflection.md`
- List of commands to close tasks in your tracker
- AI Learnings categorized by the framework

## Dependencies

- Task tracker API token
- Git access to repositories
- Claude Code sessions: `~/.claude/projects/*/transcript.jsonl`
