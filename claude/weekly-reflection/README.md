# /weekly-reflection — Claude Code Skill

AI-assisted weekly self-reflection for engineering teams. Automates data collection, keeps the human reflection.

## How It Works

```
/weekly-reflection
```

The skill runs through 5 phases:

**Phase 0-1: Automated data collection** — three parallel agents gather your sprint tasks, git commits across all repos, and analyze your Claude Code sessions for patterns.

**Phase 2: Context display** — you see everything you did this week in one place, including tasks you delegated to others.

**Phase 3: Structured interview** — AI asks 6 questions one by one: achievements, blockers, task closure, alignment with goals, improvement ideas, highlights.

**Phase 4: Report** — generates a structured markdown reflection stored in your knowledge base.

**Phase 5: Tracker update** — generates commands to close tasks (manual execution only).

## The AI Learnings Framework

The most valuable part. The skill analyzes your Claude Code sessions and categorizes insights:

| Category | What it captures | Example |
|----------|-----------------|---------|
| **Workflow Improvements** | What made you more effective | `plan_before_code`, `parallel_exploration`, `test_first` |
| **Automation Opportunities** | What should become automated | Repeating process → skill, check → hook, integration → MCP server |
| **CLAUDE.md Additions** | What to add to project instructions | Architecture rules, gotchas, code conventions |
| **Knowledge to Capture** | What's worth preserving | Codebase facts, solution patterns, team conventions |

This turns weekly reflection into a continuous improvement mechanism for your AI workflow.

## Setup

1. Copy the `weekly-reflection` folder to `.claude/skills/` in your project
2. Edit `SKILL.md` — set your tracker type, API URL, token path, and repos root
3. Run `/weekly-reflection` in Claude Code

### Supported Trackers

The skill includes API examples for:
- Jira
- Linear
- YouTrack
- GitHub Projects

Adapt the API calls in Phase 0 and Agent 1 to your tracker.

### Directory Structure

```
.claude/skills/weekly-reflection/
  SKILL.md              # The skill definition
  templates/
    reflection.md       # Report template
```

Reports are saved to:
```
knowledge-base/team/{user}/{sprint}/reflection.md
```

## Why This Exists

Weekly retrospectives take time and often become a formality. The main problem — gathering context. Data is scattered across tracker, Git, and chats. By Friday you don't remember what you did on Tuesday.

This skill automates the data collection and leaves only the reflection to the human. 15 minutes instead of an hour-long meeting.

## License

MIT
