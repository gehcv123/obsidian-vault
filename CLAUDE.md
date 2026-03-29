# Obsidian Vault — Claude Code Instructions

## Writing Rules
- All files are **Markdown** (.md)
- Use **YAML frontmatter** at the top of every note:
  ```yaml
  ---
  title: Note Title
  tags: [tag1, tag2]
  date: YYYY-MM-DD
  ---
  ```
- Use **WikiLinks** for internal references: `[[Note Name]]`
- Only link to existing notes unless explicitly asked to create a new one
- Write in Hebrew or English depending on context
- Keep frontmatter fields consistent with templates in `Templates/`

## Folder Map
| Folder | Content | Tags |
|--------|---------|------|
| `Journal/` | Daily notes, weekly reviews | `#daily`, `#weekly` |
| `Notes/` | General notes, analysis results | `#analysis`, misc |
| `Projects/` | Project-specific notes | `#project` |
| `References/` | Reference material, external sources | `#reference` |
| `Templates/` | MD templates (DO NOT move these) | — |
| `Scripts/` | Python scripts for automation | — |

## Tag Rules
- `#daily` — daily journal entry
- `#weekly` — weekly review
- `#project` — project note
- `#reference` — reference material
- `#analysis` — analysis output from pattern scanning

## File Naming
- Daily notes: `YYYY-MM-DD.md` in `Journal/`
- Weekly reviews: `YYYY-Www.md` in `Journal/` (e.g., `2026-W13.md`)
- Analysis: `analysis-YYYY-MM-DD.md` in `Notes/`

## Templates
Use templates from `Templates/` when creating new notes:
- Daily note → `Templates/daily.md`
- Weekly review → `Templates/weekly.md`
- Project note → `Templates/project.md`

## Commit Rules
After every change to the Vault:
```bash
cd C:/Users/Administrator/ObsidianVault
git add -A
git commit -m "<type>: <description>"
git push
```
Types: `journal`, `note`, `project`, `reference`, `analysis`, `template`, `script`, `chore`

## Dashboard
After creating or updating notes, run:
```bash
python Scripts/update_dashboard.py
```
This regenerates `Dashboard.md` with current stats.
