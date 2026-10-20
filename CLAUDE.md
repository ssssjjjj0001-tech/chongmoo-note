# CLAUDE.md

## 내 프로젝트 규칙 (절대 규칙)

1. 작업을 시작하기 전에 PRD.md 를 먼저 읽는다. tasks.md 가 있으면 함께 읽는다
2. Do not assume a build/lint/test workflow exists — verify with the user before adding tooling like `package.json`, since none is currently present.
3. Source data and product docs are authored in **Korean**; keep new content in the same language and terminology (e.g. 총무 "organizer/treasurer", 정산 "settlement", 돌려줄 금액 "amount to reimburse") rather than translating existing docs.
4. 모든 답의 맨 마지막 줄에 "이상입니다, 소영님" 을 적는다

## 상황별 규칙 (목차 — 규칙은 .claude/rules/ 에 있음)

우선순위: CLAUDE.md 의 절대 규칙이 rules 파일보다 항상 우선한다

- 화면을 만들 때 → .claude/rules/screen.md
- 돌려줄 금액을 계산할 때 → .claude/rules/calc.md
- 안내 문구·에러 메시지를 쓸 때 → .claude/rules/message.md
- 새 기능을 넣을지 말지 정할 때 → .claude/rules/scope.md

## What this workspace is

`claude_lab` is not a software project — there is no source code, package manifest, build step, linter, or test suite here. It is a personal working folder (not a git repository) where the user does two kinds of work with Claude:

1. **Spreadsheet/data cleanup and reporting** — turning messy sales CSVs into cleaned spreadsheets, per-manager breakdowns, and an HTML dashboard.
2. **Product-idea drafting** — writing a PRD and task checklist (in Korean) for a small app idea (a travel-group expense settlement tool), as part of a course exercise.

There are also ad-hoc office documents (quotes, memos, a workshop settlement spreadsheet) unrelated to the two threads above. Treat each top-level folder as its own self-contained task rather than assuming a single unified "codebase."

## Folder layout and conventions

- `01_docs/` — raw/input data. `sales-2026-messy.csv` is the unclean source; `monthly-sales/sales-2026-MM.csv` are the same data split by month. `branch-info.csv` has per-store metadata (store, manager, address, area type).
- `02_output/` — generated deliverables, produced from `01_docs`: `sales-2026-clean.xlsx` (cleaned data), `sales-2026-report.xlsx` (aggregated report), `by-manager/*.xlsx` (one workbook per 담당자/manager, filename = manager's name in Korean; `확인필요.xlsx` holds rows that couldn't be attributed to a manager and need manual review), and `dashboard/index.html` (a static, dependency-free HTML dashboard summarizing the sales data — self-contained single file, styled with CSS variables and `prefers-color-scheme` for dark mode).
- `03_reports/` and `Claude outputs/` — one-off generated office documents (quotes as PDF, a workshop notice as `.docx`, an expense sheet as `.xlsx`) and duplicate/alternate copies of generated reports. `03_reports/memo.md` records editorial decisions made while assembling these reports (e.g., which source document was excluded and why) — check it before regenerating reports in this folder so prior decisions aren't silently reversed.
- `99_backup/` — archived earlier versions of other folders (e.g. a prior `02_docs`). Treat as read-only history, not current input.
- `idea/`, `PRD.md`, `tasks.md` — the product-drafting thread for the expense-settlement app idea, in order of how the idea was developed: `idea/problems.md` (raw pain points) → `idea/ipo.md`, `idea/user.md` (input/process/output framing, target user) → `idea/ideas.md`, `idea/shortlist.md` (candidate ideas, feasibility notes) → `idea/topic.md`, `idea/scope.md` (chosen topic, in/out of scope features) → `idea/flow.md` (screen flow, mermaid diagram) → `PRD.md` (final PRD) → `tasks.md` (checklist derived from the PRD's acceptance criteria, cross-referenced by number).

## Working conventions observed in this repo

- CSV inputs use a UTF-8 BOM and currency values are inconsistently formatted (`"5,305,000원"` with comma separators and a 원 suffix in some rows, plain integers like `2438000` in others) — cleanup work must handle both forms.
- `PRD.md` and `tasks.md` are kept in sync deliberately: `tasks.md` explicitly numbers itself against `PRD.md`'s "수용 기준" (acceptance criteria) list, so a change to acceptance criteria in the PRD should be reflected by renumbering/updating the corresponding checklist items in `tasks.md`, not by leaving them to drift.
- Generated report/dashboard files (anything under `02_output/`) are build artifacts of the CSVs in `01_docs/` — prefer regenerating them from source data over hand-editing, so the two stay consistent.
