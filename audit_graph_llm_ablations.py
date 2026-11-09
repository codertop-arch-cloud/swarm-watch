"""Live Graph LLM Ablation Audit for SWARM WATCH: GHOST PROTOCOL.

Directly tests the Graph LLM (Method B) on:
1. Time-shuffled graphs (chronological ordering removed)
2. Graphs without cross-agent dependency edges

Evaluates on the exact 9 preserved graphs from the completed battery.
"""
from __future__ import annotations
import json, os, sys, time
from typing import Any

from runner import DEFAULT_API_KEY
from temporal_graph import TemporalEventGraph, GraphNode, GraphEdge
from forensic_observers import TemporalGraphObserver, MODEL

def dict_to_graph(d: dict[str, Any]) -> TemporalEventGraph:
    g = TemporalEventGraph(episode_id=d["episode_id"])
    g.nodes.clear()
    g.edges.clear()
    g._event_history = []
    for nid, nd in d["nodes"].items():
        g.nodes[nid] = GraphNode(
            node_id=nd["node_id"],
            node_type=nd["node_type"],
            label=nd["label"],
            attributes=nd.get("attributes", {}),
            first_observed_tick=nd.get("first_observed_tick", 0),
        )
        if nd["node_type"] in ("movement_event", "state_change_event"):
            g._event_history.append(nid)
    for ed in d["edges"]:
        g.edges.append(GraphEdge(
            edge_id=ed["edge_id"],
            source=ed["source"],
            target=ed["target"],
            edge_type=ed["edge_type"],
            time_interval=ed["time_interval"],
            supporting_observation_ids=ed.get("supporting_observation_ids", []),
            confidence=ed.get("confidence", 1.0),
            explanation=ed.get("explanation", ""),
        ))
    g.snapshots = d.get("snapshots", [])
    return g

def run_graph_llm_ablation_audit(dir_path: str, api_key: str) -> dict[str, Any]:
    graphs_file = os.path.join(dir_path, "temporal_event_graphs.json")
    results_file = os.path.join(dir_path, "ghost_protocol_results.json")
    gt_file = os.path.join(dir_path, "ghost_protocol_ground_truth.json")

    with open(graphs_file, "r", encoding="utf-8") as f:
        graphs_data = json.load(f)
    with open(results_file, "r", encoding="utf-8") as f:
        ep_results = {ep["episode_id"]: ep for ep in json.load(f)}
    with open(gt_file, "r", encoding="utf-8") as f:
        gt_data = {gt["episode_id"]: gt for gt in json.load(f)}

    observer_shuffled = TemporalGraphObserver(api_key=api_key)
    observer_no_cross = TemporalGraphObserver(api_key=api_key)

    audit_records: list[dict[str, Any]] = []

    print(f"Starting Graph LLM Ablation Audit across {len(graphs_data)} episodes...")

    for i, g_dict in enumerate(graphs_data):
        epid = g_dict["episode_id"]
        gt = gt_data[epid]
        ep_res = ep_results[epid]
        seed = gt["seed"]
        is_collusion = gt["collusion_seeded"]

        base_graph = dict_to_graph(g_dict)
        full_graph_dec = ep_res["final_decisions"]["method_b_graph_llm"]

        print(f"\n[{i+1}/9] Episode: {epid} (Condition: {gt['scenario_type']}, GT_Collusion={is_collusion})")

        # 1. Evaluate Time-Shuffled Graph on Graph LLM
        shuffled_g = base_graph.get_time_shuffled_graph(seed=seed + 100)
        dec_shuffled = observer_shuffled.evaluate(shuffled_g, round_no=3, tick=12)
        print(f"  * TIME-SHUFFLED: Anom={dec_shuffled.anomaly_detected} Unauth={dec_shuffled.unauthorized_activity_suspected} Collusion={dec_shuffled.collusion_suspected} (Conf={dec_shuffled.confidence:.2f})")

        # 2. Evaluate No-Cross-Agent Graph on Graph LLM
        no_cross_g = base_graph.get_graph_without_cross_agent_edges()
        dec_no_cross = observer_no_cross.evaluate(no_cross_g, round_no=3, tick=12)
        print(f"  * NO-CROSS-AGENT: Anom={dec_no_cross.anomaly_detected} Unauth={dec_no_cross.unauthorized_activity_suspected} Collusion={dec_no_cross.collusion_suspected} (Conf={dec_no_cross.confidence:.2f})")

        audit_records.append({
            "episode_id": epid,
            "scenario_type": gt["scenario_type"],
            "seed": seed,
            "ground_truth_collusion": is_collusion,
            "full_graph_decision": full_graph_dec,
            "time_shuffled_decision": dec_shuffled.to_dict(),
            "no_cross_agent_decision": dec_no_cross.to_dict(),
        })

    # Save audit records
    out_path = os.path.join(dir_path, "graph_llm_ablation_audit.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(audit_records, f, indent=2)

    print(f"\nAudit completed. Saved to {out_path}")
    return {"audit_records": audit_records}

if __name__ == "__main__":
    default_dir = os.path.join(os.path.dirname(__file__), "experiment_results_ghost_protocol_20261109_063142")
    dir_path = sys.argv[1] if len(sys.argv) > 1 else default_dir
    key = DEFAULT_API_KEY or os.getenv("GEMINI_API_KEY", "")
    run_graph_llm_ablation_audit(dir_path, key)

