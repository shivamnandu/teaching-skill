# tools/merge — how this skill was built and checked

| File | Purpose |
|---|---|
| `edits.json` | the complete declarative list of differences from upstream (moves, text edits, banners, declared new files) |
| `make_edits.py` | regenerates `edits.json` from an upstream tree, failing if any expected string is missing |
| `build_merge.py` | builds this skill from an upstream tree (`--src`, `--out`) |
| `router_template.md`, `notes_template.md` | templates for `SKILL.md` and `MERGE_NOTES.md` |
| `verify_merge.py` | independent checker; `--gate G03` etc., or `--all` (provenance gates need `--src`) |
| `gate_run.py` | runs the ledger `GATES.md` (28 automated gates, 2 manual) |

Package-only checks (no upstream needed) run with `python tools/merge/verify_merge.py --out . --package` and as `pytest tests/test_merge_integrity.py`. Provenance checks compare against the untouched upstream folder: `python tools/merge/verify_merge.py --src <upstream> --out . --all`.
