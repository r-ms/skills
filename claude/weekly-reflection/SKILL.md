---
name: weekly-reflection
description: Еженедельная саморефлексия. Собирает данные из трекера задач, Git, анализирует AI-сессии и проводит интервью.
triggers:
  - /weekly-reflection
  - /рефлексия
  - итоги недели
  - weekly reflection
---

# Weekly Reflection Skill

Еженедельная саморефлексия для AI-first команд. Собирает контекст из трекера задач, Git и Claude Code сессий, проводит структурированное интервью и генерирует отчёт.

## Конфигурация

Перед использованием задай переменные в скилле или в CLAUDE.md:

```
# Трекер задач (Jira, Linear, YouTrack, GitHub Issues и т.д.)
TRACKER_TYPE=jira                          # jira | linear | youtrack | github
TRACKER_API_URL=https://your-org.atlassian.net
TRACKER_TOKEN_PATH=~/.config/tracker/token # путь к API-токену
TRACKER_PROJECT=PROJ                       # ключ проекта
TRACKER_SPRINT_FIELD=sprint                # название поля спринта

# Git-репозитории для сканирования
REPOS_ROOT=~/projects                      # директория с репозиториями
REPOS_SCAN_DEPTH=3                         # глубина поиска .git

# Выходные данные
REFLECTIONS_PATH=knowledge-base/team       # куда сохранять отчёты
```

## Workflow

### Фаза 0: Определение контекста

Определи параметры рефлексии:

```bash
# Пользователь
USER_NAME=$(git config user.name)
USER_SLUG=$(echo "$USER_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')

# Период: понедельник текущей недели → сегодня
WEEK_START=$(date -v-monday +%Y-%m-%d 2>/dev/null || date -d "last monday" +%Y-%m-%d)
WEEK_END=$(date +%Y-%m-%d)
```

Определи текущий спринт через API трекера. Примеры:

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

### Фаза 1: Параллельный сбор данных

Запусти 3 параллельных Task агента для сбора данных:

#### Агент 1: Трекер задач (subagent_type: general-purpose)

Собери задачи пользователя из текущего спринта и месячные цели:

**Что собирать:**
1. **Задачи спринта** — все задачи пользователя в текущем спринте (id, название, статус, story points)
2. **Месячные epics/цели** — активные epics или цели на текущий месяц
3. **Делегированные задачи** — задачи, созданные пользователем и назначенные на других (делегирование — тоже работа)

Адаптируй API-вызовы под свой трекер. Ключевые запросы:
- Мои задачи спринта: `project = PROJ AND sprint = currentSprint() AND assignee = currentUser()`
- Активные epics: `project = PROJ AND type = Epic AND updated >= startOfMonth()`
- Созданные для других: `project = PROJ AND creator = currentUser() AND assignee != currentUser() AND created >= WEEK_START`

#### Агент 2: Git (subagent_type: general-purpose)

Собери коммиты из всех репозиториев:

```bash
USER=$(git config user.name)
SINCE="$WEEK_START"  # Из Фазы 0

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

#### Агент 3: Анализ Claude-сессий (subagent_type: general-purpose)

Проанализируй AI-сессии за неделю по фреймворку learnings.

Найди файлы сессий:
```bash
find ~/.claude/projects -name "*.jsonl" -mtime -7 2>/dev/null
```

Читай каждый jsonl файл и категоризируй инсайты по фреймворку:

**Workflow Improvements** (что улучшило работу):
- `plan_before_code` — планирование перед написанием кода
- `requirements_first` — уточнение требований до реализации
- `parallel_exploration` — использование параллельных агентов
- `test_first` — написание тестов перед реализацией
- `incremental_approach` — инкрементальный подход к задачам
- `docs_first` — документация до кода
- `dry_run_first` — проверка команд перед выполнением
- `validation_before_commit` — валидация до коммита

**Automation Opportunities** (что можно автоматизировать):
- `skill` — повторяющийся процесс → создать skill
- `hook` — автоматическая проверка → создать hook
- `subagent` — сложная задача → создать subagent
- `mcp_integration` — интеграция с сервисом → MCP-сервер
- `alias` — частая команда → алиас

**CLAUDE.md Additions** (что добавить в инструкции проекта):
- `architecture_rule` — архитектурное правило проекта
- `code_convention` — соглашение о коде
- `gotcha` — неочевидная особенность/ловушка
- `context_file` — файл для загрузки в контекст
- `command_shortcut` — команда-шорткат
- `tool_preference` — предпочтение инструмента

**Knowledge to Capture** (знания для сохранения):
- `codebase_fact` — факт о кодовой базе
- `solution_pattern` — паттерн решения проблемы
- `external_resource` — полезный внешний ресурс
- `team_convention` — командное соглашение

Для каждой категории выдели 2-3 конкретных примера из сессий.

### Фаза 2: Показ контекста

После завершения всех агентов покажи пользователю собранный контекст:

**Мои задачи спринта:**
| ID | Задача | SP | Статус |
|----|--------|:--:|--------|
| PROJ-123 | ... | 5 | In Progress |

**Задачи, созданные для других:**
| ID | Задача | Assignee | SP | Статус |
|----|--------|----------|:--:|--------|
| PROJ-456 | ... | @colleague | 3 | Open |

**Git summary:**
- repo-a: X коммитов
- repo-b: Y коммитов

**AI Learnings:**
- Лучшие практики: ...
- Возможности автоматизации: ...
- Предложения для CLAUDE.md: ...

### Фаза 3: Интервью

Проведи структурированное интервью, задавая вопросы по одному:

1. **Результаты недели** — Что удалось сделать? Какие задачи считаешь главными достижениями?

2. **Проблемы** — Что мешало работе? Какие блокеры или трудности возникли?

3. **Закрытие задач** — Какие из задач можно закрыть? (покажи список Open/In Progress)

4. **Связь с месячными целями** — Как работа недели связана с Epics? Какой вклад в месячные цели?

5. **Предложения по улучшению** — Есть ли идеи по улучшению процессов, инструментов, workflow?

6. **Что было приятно** — Что порадовало на этой неделе? (момент, достижение, коллега, инструмент)

Используй AskUserQuestion для каждого вопроса.

### Фаза 4: Генерация отчёта

Создай отчёт по шаблону из `templates/reflection.md`:

```
{REFLECTIONS_PATH}/{user-slug}/{sprint}/reflection.md
```

Например: `knowledge-base/team/john-doe/sprint-12/reflection.md`

Создай необходимые директории если их нет.

### Фаза 5: Актуализация трекера

На основе ответа на вопрос 3 сформируй команды для закрытия задач.

**НЕ выполняй автоматически** — только покажи команды для ручного выполнения.

Адаптируй под свой трекер:

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

## Выходные данные

- Отчёт рефлексии: `{REFLECTIONS_PATH}/{user-slug}/{sprint}/reflection.md`
- Список команд для закрытия задач в трекере
- AI Learnings с категоризацией по фреймворку

## Зависимости

- API-токен трекера задач
- Git-доступ к репозиториям
- Сессии Claude Code: `~/.claude/projects/*/transcript.jsonl`
