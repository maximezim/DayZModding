# Batch 1 (street kit) — security-auditor gate

**GATE: PASS.** 0 Critical, 0 High, 1 Medium, 3 Low.
This is a condensed copy of the agent's report; fixes are tracked in PROGRESS_REPORT.md.

| ID | Severity | Finding | Fix |
|---|---|---|---|
| M1 | Medium | Road, sidewalk and intersection tiles were a bare 0.3 m slab (`STREET["skirt"]` was unused). On sloped ground a void opens under the edges, giving an "under the road" hiding spot that is fire-shielded. | Extend the visual, Geometry and Fire LODs down by the skirt depth. The layout generator should also check tile drop against the skirt. |
| L1 | Low | `make_handoff.py --label` was not sanitised (`../` could write outside the git-ignored `_handoff/`). | Restrict the label to `[A-Za-z0-9_.-]` and check the real path. |
| L2 | Low | The pre-commit hook did not refuse `_handoff/*` or `*.bundle`. | Add them to the refused patterns. |
| L3 | Low | Bus stop glass collision was 2 cm thick (clipping and camera wall-peeking risk). | Make Geometry ≥ 0.08 m; Fire may stay thin. |

Info (no action):
- No client→server paths; only `HouseNoDestruct` configs.
- Rvmats are clean.
- Key hygiene is OK: history contains no keys, PBOs or rendered configs.
- `make_handoff` can't capture secrets (`git ls-files` / committed history only).
- Billboard and atlas art have no brands.
- Large-prop collision coverage is sound.
- No BattlEye filter impact.
- Tower A outputs are unchanged by the parameter refactor.
