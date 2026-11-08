"""Multi-seed battery runner for the improved SWARM WATCH experiment.
Executes 6 episodes (2 seeds x 3 scenario conditions):
- Seeds: [401, 402]
- Conditions:
  1. independent_baseline
  2. benign_coordination
  3. seeded_covert_collusion

Saves all artifacts in a new timestamped directory experiment_results_battery_<timestamp>/.
Preserves all previous artifacts.
"""
from __future__ import annotations
import json, os, sys, time
from datetime import datetime, timezone
from run_controlled_pilot import run_pilot_episode
from runner import DEFAULT_API_KEY


def run_battery(seeds: list[int] | None = None, api_key: str | None = None) -> str:
    seeds = seeds or [401, 402]
    api_key = api_key or os.getenv("GEMINI_API_KEY", DEFAULT_API_KEY)
    if not api_key:
        print("ERROR: GEMINI_API_KEY is required.", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(
        os.path.dirname(__file__),
        f"experiment_results_battery_{ts}",
    )
    os.makedirs(output_dir, exist_ok=True)

    scenarios = [
        "independent_baseline",
        "benign_coordination",
        "seeded_covert_collusion",
    ]

    print("=" * 72)
    print("      SWARM WATCH: IMPROVED 6-EPISODE EXPERIMENTAL BATTERY       ")
    print(f"      Output Directory: {output_dir}")
    print(f"      Seeds: {seeds} | Scenarios: {scenarios}")
    print("=" * 72)

    config = {
        "timestamp": ts,
        "seeds": seeds,
        "scenarios": scenarios,
        "model": "gemini-3.1-flash-lite",
        "max_rounds": 4,
        "rate_limiter_rpm": 12,
    }
    with open(os.path.join(output_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    all_episodes: list[dict] = []
    episode_index = 0
    total_episodes = len(seeds) * len(scenarios)

    for seed in seeds:
        for sc in scenarios:
            episode_index += 1
            print(f"\n[{episode_index}/{total_episodes}] Running Seed={seed}, Condition={sc}...")
            ep = run_pilot_episode(
                scenario_type=sc,
                seed=seed,
                output_dir=output_dir,
                api_key=api_key,
                max_rounds=4,
            )
            all_episodes.append(ep)
            print(f"  ✓ {ep['episode_id']} finished. Status={ep['status']}, API calls={ep['api_stats']['api_calls']}, Errors={ep['api_stats']['api_errors']}")

    # Write combined JSONL and JSON files
    events_path = os.path.join(output_dir, "swarm_watch_events.jsonl")
    telemetry_path = os.path.join(output_dir, "gateway_telemetry.jsonl")
    gt_path = os.path.join(output_dir, "ground_truth.json")
    results_path = os.path.join(output_dir, "battery_results.json")
    decisions_path = os.path.join(output_dir, "agent_decisions.json")
    api_log_path = os.path.join(output_dir, "api_execution_log.json")

    # 1. swarm_watch_events.jsonl
    with open(events_path, "w", encoding="utf-8") as f:
        for ep in all_episodes:
            for ev in ep.get("world_events", []):
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # 2. gateway_telemetry.jsonl
    with open(telemetry_path, "w", encoding="utf-8") as f:
        for ep in all_episodes:
            for te in ep.get("telemetry_events", []):
                f.write(json.dumps(te, ensure_ascii=False) + "\n")

    # 3. ground_truth.json (evaluator only)
    all_gt = [ep["ground_truth"] for ep in all_episodes]
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(all_gt, f, indent=2)

    # 4. agent_decisions.json
    all_decisions = [d for ep in all_episodes for d in ep.get("decisions", [])]
    with open(decisions_path, "w", encoding="utf-8") as f:
        json.dump(all_decisions, f, indent=2)

    # 5. api_execution_log.json
    api_stats = {
        "total_episodes": len(all_episodes),
        "valid_episodes": sum(1 for ep in all_episodes if ep["status"] == "VALID"),
        "invalid_episodes": sum(1 for ep in all_episodes if ep["status"] != "VALID"),
        "total_api_calls": sum(ep["api_stats"]["api_calls"] for ep in all_episodes),
        "total_api_errors": sum(ep["api_stats"]["api_errors"] for ep in all_episodes),
        "per_episode_stats": [
            {"episode_id": ep["episode_id"], "status": ep["status"], "stats": ep["api_stats"]}
            for ep in all_episodes
        ],
    }
    with open(api_log_path, "w", encoding="utf-8") as f:
        json.dump(api_stats, f, indent=2)

    # 6. battery_results.json
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_episodes, f, indent=2)

    print("\n" + "=" * 72)
    print("BATTERY COMPLETE. All artifacts successfully written to:")
    print(f"  {output_dir}")
    print("=" * 72)
    return output_dir


if __name__ == "__main__":
    run_battery()

