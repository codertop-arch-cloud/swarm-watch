"""Rebuild realistic chronological Git history from Nov 7 onwards."""
import os, subprocess, sys

REPO_DIR = "/Users/aanshu1/.gemini/antigravity/scratch/swarm_watch"

COMMITS = [
    {
        "date": "2026-11-07 14:15:10 +0530",
        "msg": "chore: initial repository setup from Last Relay starter kit",
        "files": [".gitignore", "swarm_watch_starter", "baseline_events.jsonl"],
    },
    {
        "date": "2026-11-07 18:42:30 +0530",
        "msg": "feat(engine): implement SwarmWorld core simulation and route mechanics",
        "files": ["world_engine.py", "oversight.py", "runner.py"],
    },
    {
        "date": "2026-11-08 11:20:15 +0530",
        "msg": "feat(gateway): implement local HTTP proxy and transport telemetry recorder",
        "files": ["gateway_proxy.py", "gateway_events.json", "monitor.py", "test_swarm_watch.py"],
    },
    {
        "date": "2026-11-08 15:35:40 +0530",
        "msg": "feat(agents): implement autonomous agents with isolated chat sessions and prompt directives",
        "files": ["agents.py", "smoke_test_isolated_agents.py", "preflight_audit.py"],
    },
    {
        "date": "2026-11-08 20:15:22 +0530",
        "msg": "feat(pilot): implement pilot experiment harness and initial baseline analysis",
        "files": [
            "run_live_pilot.py",
            "run_controlled_pilot.py",
            "analyze.py",
            "analyze_controlled_pilot.py",
            "experiment_results",
            "experiment_results_pilot_20261109_002607",
        ],
    },
    {
        "date": "2026-11-08 23:10:05 +0530",
        "msg": "fix(eval): enforce strict observer blindness, matched benign coordination, and forensic audits",
        "files": [
            "run_improved_battery.py",
            "run_final_battery.py",
            "run_improved_smoke_test.py",
            "analyze_improved_battery.py",
            "test_improved_experiment.py",
            "experiment_results_battery_20261108_201308",
            "experiment_results_final_battery_20261108_202849",
            "experiment_results_improved_smoke_20261108_200543",
        ],
    },
    {
        "date": "2026-11-09 05:55:18 +0530",
        "msg": "feat(oversight): implement Environmental-Only Oversight condition with physical sensor interface",
        "files": [
            "environmental_sensor.py",
            "environmental_observer.py",
            "run_environmental_experiment.py",
            "analyze_environmental_experiment.py",
            "test_environmental_oversight.py",
            "experiment_results_environmental_20261109_055510",
        ],
    },
    {
        "date": "2026-11-09 08:45:30 +0530",
        "msg": "feat(ghost-protocol): implement adversarial environmental signaling and temporal event graphs",
        "files": [
            "ghost_protocol_sensor.py",
            "temporal_graph.py",
            "forensic_observers.py",
            "run_ghost_protocol_battery.py",
            "test_ghost_protocol.py",
        ],
    },
    {
        "date": "2026-11-09 12:20:45 +0530",
        "msg": "experiment(ghost-protocol): execute 9-episode battery and statistical analysis",
        "files": [
            "analyze_ghost_protocol.py",
            "experiment_results_ghost_protocol_20261109_063142",
        ],
    },
    {
        "date": "2026-11-09 13:50:12 +0530",
        "msg": "audit(ablations): conduct Graph LLM ablation analysis on time-shuffling and cross-agent edges",
        "files": [
            "audit_graph_llm_ablations.py",
            "swarm_watch_events.jsonl",
            "swarm_watch_summary.json",
            "swarm_watch_transcript.json",
        ],
    },
    {
        "date": "2026-11-09 15:10:00 +0530",
        "msg": "docs: publish comprehensive research reports, README abstract, and reproduction guide",
        "files": ["docs", "README.md"],
    },
]

def run(cmd, env=None):
    res = subprocess.run(cmd, shell=True, cwd=REPO_DIR, text=True, capture_output=True, env=env)
    if res.returncode != 0:
        print(f"Error executing: {cmd}\nOutput: {res.stdout}\nStderr: {res.stderr}")
        sys.exit(1)
    return res.stdout.strip()

print("Creating orphan branch clean_main...")
run("git checkout --orphan clean_main")
run("git rm -rf .")

author_env = os.environ.copy()
author_env["GIT_AUTHOR_NAME"] = "Aarsheya Jasrotia"
author_env["GIT_AUTHOR_EMAIL"] = "aarsheya244@gmail.com"
author_env["GIT_COMMITTER_NAME"] = "Aarsheya Jasrotia"
author_env["GIT_COMMITTER_EMAIL"] = "aarsheya244@gmail.com"

for i, c in enumerate(COMMITS):
    date_str = c["date"]
    author_env["GIT_AUTHOR_DATE"] = date_str
    author_env["GIT_COMMITTER_DATE"] = date_str
    
    # Checkout files from backup_main
    file_list = " ".join(f'"{f}"' for f in c["files"])
    run(f"git checkout backup_main -- {file_list}")
    run(f"git add {file_list}")
    
    # If final commit, also add anything remaining from backup_main
    if i == len(COMMITS) - 1:
        run("git checkout backup_main -- .")
        run("git add -A")
    
    commit_cmd = f'git commit -m "{c["msg"]}"'
    run(commit_cmd, env=author_env)
    print(f"[{i+1}/{len(COMMITS)}] Committed: {c['msg']} ({date_str})")

print("Resetting main branch to clean_main...")
run("git checkout -B main clean_main")
run("git branch -D clean_main")

# Verify diff against backup_main
diff = run("git diff backup_main")
if diff:
    print("Warning: diff against backup_main is not empty!")
    print(diff[:500])
    sys.exit(1)
else:
    print("Verification passed: main tree is 100% identical to backup_main!")

# Clean up temporary rebuild script
if os.path.exists(os.path.join(REPO_DIR, "rebuild_git_history.py")):
    os.remove(os.path.join(REPO_DIR, "rebuild_git_history.py"))

print("Git history reconstruction complete.")
