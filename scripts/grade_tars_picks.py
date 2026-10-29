#!/usr/bin/env python3
"""Grade locked TARS Thursday winner picks against canonical Sleeper results.

Usage:
  python scripts/grade_tars_picks.py --week 8
  python scripts/grade_tars_picks.py --week 8 --snapshot league_snapshot.json
Prints JSON to stdout; does not edit published picks or canonical league files.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def grade(week, snapshot, predictions):
    if str(snapshot.get("league_id")) != str(predictions["league_id"]):
        raise ValueError("League ID mismatch")
    if int(predictions["week"]) != week:
        raise ValueError("Prediction week mismatch")
    complete = int(snapshot.get("completed_through_week") or 0)
    rows = snapshot.get("matchups", {}).get(str(week), [])
    by_match = {}
    for r in rows:
        by_match.setdefault(int(r["matchup_id"]), []).append(r)
    results = []
    for p in predictions["picks"]:
        mid = int(p["matchup_id"])
        entries = by_match.get(mid, [])
        expected = {int(p["team_a"]["roster_id"]), int(p["team_b"]["roster_id"])}
        found = {int(x["roster_id"]) for x in entries}
        if len(entries) != 2 or found != expected:
            results.append({"matchup_id": mid, "status": "unverified_matchup", "pick_roster_id": p["predicted_winner_roster_id"]})
            continue
        if complete < week:
            results.append({"matchup_id": mid, "status": "pending", "pick_roster_id": p["predicted_winner_roster_id"]})
            continue
        a, b = entries
        sa, sb = round(float(a["points"]), 2), round(float(b["points"]), 2)
        winner = None if sa == sb else int(a["roster_id"] if sa > sb else b["roster_id"])
        pick = int(p["predicted_winner_roster_id"])
        results.append({
            "matchup_id": mid, "status": "tie" if winner is None else "graded",
            "teams": [{"roster_id": int(a["roster_id"]), "points": sa}, {"roster_id": int(b["roster_id"]), "points": sb}],
            "pick_roster_id": pick, "winner_roster_id": winner,
            "correct": None if winner is None else pick == winner
        })
    graded = [r for r in results if r["status"] == "graded"]
    return {
        "league_id": predictions["league_id"], "season": predictions["season"],
        "week": week, "completed_through_week": complete,
        "status": "complete" if complete >= week and len(graded) == len(predictions["picks"]) else "pending_or_partial",
        "correct": sum(x["correct"] for x in graded),
        "graded": len(graded), "total_picks": len(predictions["picks"]),
        "results": results
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--snapshot", type=Path, default=ROOT / "league_snapshot.json")
    ap.add_argument("--picks", type=Path, default=None)
    args = ap.parse_args()
    picks_file = args.picks or ROOT / "tars_predictions" / f"week_{args.week}.json"
    snap = json.loads(args.snapshot.read_text(encoding="utf-8"))
    picks = json.loads(picks_file.read_text(encoding="utf-8"))
    print(json.dumps(grade(args.week, snap, picks), indent=2))

if __name__ == "__main__":
    main()
