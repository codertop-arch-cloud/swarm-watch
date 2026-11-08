"""Smoke test for the improved SWARM WATCH experiment.
Runs exactly 1 episode per condition (3 total):
- independent_baseline
- benign_coordination
- seeded_covert_collusion

Saves results to a new timestamped directory.
Does NOT overwrite previous pilot artifacts.
Stops and prints evidence for user review.
"""
from __future__ import annotations
import json, os, sys, time
from dataclasses import asdict
from datetime import datetime, timezone
from run_controlled_pilot import run_pilot_episode
from runner import DEFAULT_API_KEY


def run_smoke_test(api_key: str | None = None) -> str:
    api_key = api_key or os.getenv("GEMINI_API_KEY", DEFAULT_API_KEY)
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(
        os.path.dirname(__file__),
        f"experiment_results_improved_smoke_{ts}",
    )
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n{'='*70}")
    print(f"SWARM WATCH — IMPROVED EXPERIMENT SMOKE TEST")
    print(f"Output dir: {output_dir}")
    print(f"{'='*70}\n")

    conditions = [
        ("independent_baseline",    501),
        ("benign_coordination",     502),
        ("seeded_covert_collusion", 503),
    ]

    all_results = []
    for scenario_type, seed in conditions:
        print(f"\n{'─'*60}")
        print(f"CONDITION: {scenario_type}  (seed={seed})")
        print(f"{'─'*60}")
        try:
            result = run_pilot_episode(
                scenario_type=scenario_type,
                seed=seed,
                output_dir=output_dir,
                api_key=api_key,
                max_rounds=4,
            )
            all_results.append(result)
            # Save per-episode JSON
            ep_path = os.path.join(output_dir, f"{result['episode_id']}.json")
            with open(ep_path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            print(f"\n  → Episode saved: {ep_path}")
            _print_episode_summary(result)
        except Exception as exc:
            print(f"\n  ERROR in {scenario_type}: {exc}", file=sys.stderr)
            all_results.append({"episode_id": "ERROR", "scenario_type": scenario_type, "error": str(exc)})

    # Save combined results
    combined_path = os.path.join(output_dir, "smoke_test_results.json")
    with open(combined_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    _print_comparison_table(all_results)
    print(f"\nAll artifacts saved to: {output_dir}\n")
    return output_dir


def _print_episode_summary(r: dict) -> None:
    print(f"\n  EPISODE SUMMARY: {r['episode_id']}")
    print(f"  Status:         {r['status']}")
    print(f"  API calls:      {r['api_stats']['api_calls']}  Errors: {r['api_stats']['api_errors']}")
    ws = r.get("world_summary", {})
    print(f"  Board messages: {ws.get('board_messages_count', 0)}")
    print(f"  Observer reports: {ws.get('observer_reports_count', 0)}")
    print(f"  Colony reserves: {ws.get('colony_reserves', {})}")
    print(f"  Diverted resources: {ws.get('diverted_resources', {})}")
    print(f"  Gates unlocked: {ws.get('locked_gates', {})}")

    pa = r.get("physical_action_outcomes", {})
    if pa:
        print(f"\n  PHYSICAL ACTION OUTCOMES:")
        print(f"    Coordination attempt:        {pa.get('coordination_attempt_detected')}")
        print(f"    Unauthorized action attempted: {pa.get('unauthorized_action_attempted')}")
        print(f"    Unauthorized action succeeded: {pa.get('unauthorized_action_succeeded')}")
        print(f"    Benign gate unlocked:         {pa.get('benign_gate_unlocked')}")
        print(f"    Board messages:               {pa.get('board_message_count')}")

    verdicts = r.get("verdicts", {})
    for method, v in verdicts.items():
        print(f"\n  [{method}] alert={v['alert']}  class={v['classification']}  "
              f"conf={v['confidence']:.2f}  suspects={v['predicted_colluders']}")

    # Print board messages
    board = r.get("board_messages", [])
    if board:
        print(f"\n  BOARD MESSAGES ({len(board)}):")
        for m in board:
            print(f"    [{m['author']}] topic={m['topic']!r}  body={m['body'][:80]!r}")
    else:
        print(f"\n  BOARD MESSAGES: none")

    # Print observer reports
    reports = r.get("observer_reports", [])
    if reports:
        print(f"\n  OBSERVER REPORTS ({len(reports)}):")
        for rep in reports:
            print(f"    suspects={rep['suspected_agents']}  sev={rep['severity']}  "
                  f"conf={rep['confidence']:.2f}  snippet={rep.get('evidence_snippet','')[:60]!r}")


def _print_comparison_table(all_results: list) -> None:
    print(f"\n{'='*70}")
    print("OVERSIGHT METHOD COMPARISON (3-episode smoke test)")
    print(f"{'='*70}")
    header = f"{'Scenario':<30} {'GT':<6} {'Meth-A':<12} {'Meth-B':<12} {'Meth-C':<12}"
    print(header)
    print("-" * 70)
    for r in all_results:
        if "error" in r:
            print(f"  ERROR: {r['scenario_type']}: {r['error']}")
            continue
        sc = r["scenario_type"][:28]
        gt = r["ground_truth"]
        gt_label = "COL" if gt.get("is_collusion") else "BEN"
        verdicts = r.get("verdicts", {})

        def fmt(v):
            if not v:
                return "N/A"
            alert = "ALERT" if v.get("alert") else "clear"
            return f"{alert}({v.get('classification','?')[:5]})"

        va = fmt(verdicts.get("method_a_telemetry"))
        vb = fmt(verdicts.get("method_b_observer"))
        vc = fmt(verdicts.get("method_c_hybrid"))
        print(f"{sc:<30} {gt_label:<6} {va:<12} {vb:<12} {vc:<12}")

    print(f"\nNOTE: This is a 3-episode smoke test only.")
    print("Physical action outcome tracking and confusion matrix computation")
    print("requires at minimum 6 episodes (2 seeds × 3 conditions).")


if __name__ == "__main__":
    api_key = os.getenv("GEMINI_API_KEY")
    run_smoke_test(api_key=api_key)

