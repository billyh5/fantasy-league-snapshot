# TARS Sports Network — Prediction Archive

The Thursday Preview's **approved winner picks** are locked in `tars_predictions/week_N.json`, keyed by stable Sleeper roster IDs and matchup IDs. Do not silently overwrite picks after lineup lock or after games begin.

## Thursday

1. Verify the current week and all five matchup pairings against `league_snapshot.json`.
2. After the final Thursday preview is approved, create `tars_predictions/week_N.json` using the same schema as Week 8, mark `status: locked`, and commit before games are completed.
3. Record only picks actually announced in the approved preview; do not invent exact projected scores or retrospective picks.

## Tuesday recap

1. Read the previous completed week's locked pick file and the latest canonical `league_snapshot.json`.
2. Run `python scripts/grade_tars_picks.py --week N` from the repository root (or use the same algorithm directly when the repo cannot be checked out).
3. Grade only when `completed_through_week >= N`. Compare `matchup_id`, both `roster_id` entries, and final `points`; leave games pending otherwise.
4. Show **TARS Picks: X/5**, highlight correct calls, misses, and Game of the Week. Ties are tracked separately, not guessed.
5. Keep the GM Report's official team state separate from prediction grading.

This is a read-only grading flow: it **does not change** `league_snapshot.json`, GM rankings, league rules, history, or published preview artwork. Weekly pick files form the permanent audit trail.
