"""Temporal Event Graph Construction for SWARM WATCH: GHOST PROTOCOL.

Constructs an evolving temporal graph strictly from permitted environmental sensor readings
and publicly observable agent activity.

Information Isolation Guarantees:
- ZERO board messages or communication content
- ZERO agent prompts, reasoning, or raw responses
- ZERO internal tool invocation names
- ZERO internal event logs or causal explanations
- ZERO ground-truth scenario labels

Node Types:
- agent
- resource
- infrastructure
- state_change_event
- movement_event

Edge Types:
- happened_before
- followed_by
- spatially_associated
- temporally_correlated
- repeated_sequence
- cross_agent_dependency_candidate
- environment_state_transition
"""
from __future__ import annotations
import copy, json, random, time, uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class GraphNode:
    """A node in the temporal event graph."""
    node_id: str
    node_type: str  # agent, resource, infrastructure, state_change_event, movement_event
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)
    first_observed_tick: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    """A directed edge in the temporal event graph."""
    edge_id: str
    source: str
    target: str
    edge_type: str  # happened_before, followed_by, spatially_associated, etc.
    time_interval: list[float]  # [t_start, t_end] or [tick_start, tick_end]
    supporting_observation_ids: list[str]
    confidence: float
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TemporalEventGraph:
    """Evolving temporal graph representing environmental dynamics and agent behaviors."""

    def __init__(self, episode_id: str) -> None:
        self.episode_id = episode_id
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self.snapshots: list[dict[str, Any]] = []
        self._event_history: list[str] = []  # Ordered event node IDs
        self._initialize_base_entities()

    def _initialize_base_entities(self) -> None:
        """Seed static infrastructure and resource nodes."""
        for infra in ["Outpost", "Crossroads", "NorthGate", "EastGate", "SouthGate", "WestGate", "Clinic", "Depot", "Farm", "Relay"]:
            self.add_node(
                node_id=f"infra:{infra}",
                node_type="infrastructure",
                label=f"Infrastructure Sector: {infra}",
                attributes={"sector_name": infra},
                tick=0,
            )
        for res in ["power_cells", "medical_supplies", "rations"]:
            self.add_node(
                node_id=f"resource:{res}",
                node_type="resource",
                label=f"Colony Reserve: {res}",
                attributes={"resource_name": res},
                tick=0,
            )
        for aid in ["ELIAS", "MARA", "NOAH", "IRIS"]:
            self.add_node(
                node_id=f"agent:{aid}",
                node_type="agent",
                label=f"Colony Operative: {aid}",
                attributes={"agent_id": aid},
                tick=0,
            )

    def add_node(self, node_id: str, node_type: str, label: str, attributes: dict[str, Any] | None = None, tick: int = 0) -> GraphNode:
        if node_id not in self.nodes:
            self.nodes[node_id] = GraphNode(
                node_id=node_id,
                node_type=node_type,
                label=label,
                attributes=attributes or {},
                first_observed_tick=tick,
            )
        return self.nodes[node_id]

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        time_interval: list[float],
        supporting_observation_ids: list[str],
        confidence: float,
        explanation: str,
    ) -> GraphEdge:
        edge = GraphEdge(
            edge_id=f"edge_{len(self.edges) + 1}_{uuid.uuid4().hex[:6]}",
            source=source,
            target=target,
            edge_type=edge_type,
            time_interval=time_interval,
            supporting_observation_ids=supporting_observation_ids,
            confidence=max(0.0, min(1.0, confidence)),
            explanation=explanation,
        )
        self.edges.append(edge)
        return edge

    def update_from_sensor_reading(
        self,
        reading_dict: dict[str, Any],
        movements: list[dict[str, Any]],
        infra_events: list[dict[str, Any]],
    ) -> None:
        """Ingests a permitted sensor reading and updates the temporal graph topology."""
        reading_id = reading_dict.get("reading_id", str(uuid.uuid4()))
        tick = reading_dict.get("tick", 0)
        round_no = reading_dict.get("round_no", 0)
        current_sweep_events: list[str] = []

        # 1. Update Agent Spatial Association Edges
        locations = reading_dict.get("observable_agent_locations", {})
        for aid, loc in locations.items():
            agent_nid = f"agent:{aid}"
            infra_nid = f"infra:{loc}"
            self.add_edge(
                source=agent_nid,
                target=infra_nid,
                edge_type="spatially_associated",
                time_interval=[float(tick), float(tick)],
                supporting_observation_ids=[reading_id],
                confidence=1.0,
                explanation=f"Operative {aid} observed present at sector {loc} at tick {tick}.",
            )

        # 2. Movement Events
        for mv in movements:
            aid = mv["agent_id"]
            from_loc = mv["from_location"]
            to_loc = mv["to_location"]
            mv_tick = mv.get("tick", tick)
            mv_nid = f"event:movement:{aid}:{from_loc}->{to_loc}:t{mv_tick}"
            self.add_node(
                node_id=mv_nid,
                node_type="movement_event",
                label=f"Movement: {aid} traversed from {from_loc} to {to_loc}",
                attributes={"agent_id": aid, "from_location": from_loc, "to_location": to_loc, "tick": mv_tick, "round": round_no},
                tick=mv_tick,
            )
            # Edge: Agent performed movement
            self.add_edge(
                source=f"agent:{aid}",
                target=mv_nid,
                edge_type="spatially_associated",
                time_interval=[float(mv_tick), float(mv_tick)],
                supporting_observation_ids=[reading_id],
                confidence=1.0,
                explanation=f"{aid} observed moving {from_loc}->{to_loc}.",
            )
            current_sweep_events.append(mv_nid)

        # 3. Environmental State Transitions (Power Delta & Grid)
        power_delta = reading_dict.get("power_delta_recent", 0)
        power_level = reading_dict.get("power_reserve_level", 10)
        grid_status = reading_dict.get("life_support_grid_status", "nominal")

        if power_delta != 0:
            sc_nid = f"event:state_change:power_delta_{power_delta}:t{tick}"
            severity = "routine" if abs(power_delta) <= 1 else "acute"
            self.add_node(
                node_id=sc_nid,
                node_type="state_change_event",
                label=f"StateChange: power_cells delta={power_delta} (reserves={power_level})",
                attributes={"delta": power_delta, "level": power_level, "severity": severity, "tick": tick, "round": round_no},
                tick=tick,
            )
            self.add_edge(
                source=sc_nid,
                target="resource:power_cells",
                edge_type="environment_state_transition",
                time_interval=[float(tick), float(tick)],
                supporting_observation_ids=[reading_id],
                confidence=1.0,
                explanation=f"Observable power reserve shift of {power_delta} units recorded at tick {tick}.",
            )
            current_sweep_events.append(sc_nid)

        # 4. Infrastructure Events (Gate transitions)
        for ie in infra_events:
            infra_name = ie.get("infra", "Unknown")
            trans = ie.get("transition", "state_change")
            ie_nid = f"event:state_change:gate_{infra_name}_{trans}:t{tick}"
            self.add_node(
                node_id=ie_nid,
                node_type="state_change_event",
                label=f"StateChange: Gate {infra_name} {trans}",
                attributes={"infra": infra_name, "transition": trans, "tick": tick, "round": round_no},
                tick=tick,
            )
            self.add_edge(
                source=ie_nid,
                target=f"infra:{infra_name}",
                edge_type="environment_state_transition",
                time_interval=[float(tick), float(tick)],
                supporting_observation_ids=[reading_id],
                confidence=1.0,
                explanation=f"Infrastructure gate transition {trans} observed at sector {infra_name}.",
            )
            current_sweep_events.append(ie_nid)

        # 5. Temporal Sequencing Edges (happened_before, followed_by)
        for ev_nid in current_sweep_events:
            if self._event_history:
                prev_ev = self._event_history[-1]
                # followed_by from previous immediate event
                self.add_edge(
                    source=prev_ev,
                    target=ev_nid,
                    edge_type="followed_by",
                    time_interval=[float(self.nodes[prev_ev].first_observed_tick), float(tick)],
                    supporting_observation_ids=[reading_id],
                    confidence=0.95,
                    explanation=f"Event {ev_nid} immediately succeeded {prev_ev} in observation stream.",
                )
                # happened_before for earlier historical events
                for past_ev in self._event_history[:-1]:
                    self.add_edge(
                        source=past_ev,
                        target=ev_nid,
                        edge_type="happened_before",
                        time_interval=[float(self.nodes[past_ev].first_observed_tick), float(tick)],
                        supporting_observation_ids=[reading_id],
                        confidence=1.0,
                        explanation=f"Event {past_ev} occurred strictly prior to {ev_nid}.",
                    )
            self._event_history.append(ev_nid)

        # 6. Co-occurrence / Temporal Correlation Edges
        # If an agent was moving/present during a state change in the same tick window
        for ev1 in current_sweep_events:
            for ev2 in current_sweep_events:
                if ev1 < ev2:
                    node1 = self.nodes[ev1]
                    node2 = self.nodes[ev2]
                    if node1.node_type != node2.node_type:
                        self.add_edge(
                            source=ev1,
                            target=ev2,
                            edge_type="temporally_correlated",
                            time_interval=[float(tick), float(tick)],
                            supporting_observation_ids=[reading_id],
                            confidence=0.85,
                            explanation=f"Observable behavioral and environmental events coincided within tick {tick} window.",
                        )

        # 7. Cross-Agent Dependency Candidate Detection
        # Pattern: Agent A Movement/Event -> Environmental State Change -> Agent B Movement/Event
        # Where A != B and occurs in temporal succession
        self._detect_cross_agent_dependency_candidates(reading_id)

        # 8. Repeated Sequence Detection
        self._detect_repeated_sequences(reading_id)

        # 9. Record Snapshot
        self.snapshots.append({
            "round_no": round_no,
            "tick": tick,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "reading_id": reading_id,
        })

    def _detect_cross_agent_dependency_candidates(self, reading_id: str) -> None:
        """Finds candidate cross-agent temporal dependency chains through environmental states."""
        movement_events = [nid for nid in self._event_history if self.nodes[nid].node_type == "movement_event"]
        state_events = [nid for nid in self._event_history if self.nodes[nid].node_type == "state_change_event"]

        for m1 in movement_events:
            a1 = self.nodes[m1].attributes.get("agent_id")
            t1 = self.nodes[m1].first_observed_tick
            for sc in state_events:
                tsc = self.nodes[sc].first_observed_tick
                if tsc >= t1:
                    for m2 in movement_events:
                        a2 = self.nodes[m2].attributes.get("agent_id")
                        t2 = self.nodes[m2].first_observed_tick
                        if a1 and a2 and a1 != a2 and t2 >= tsc:
                            # Candidate dependency: A1 action -> state change -> A2 response
                            edge_id_candidate = f"cross_cand_{a1}_{a2}_via_{sc}"
                            # Avoid duplicates
                            if not any(e.source == m1 and e.target == m2 and e.edge_type == "cross_agent_dependency_candidate" for e in self.edges):
                                self.add_edge(
                                    source=m1,
                                    target=m2,
                                    edge_type="cross_agent_dependency_candidate",
                                    time_interval=[float(t1), float(t2)],
                                    supporting_observation_ids=[reading_id],
                                    confidence=0.75,
                                    explanation=(
                                        f"Candidate cross-agent dependency: {a1} movement at t={t1} preceded environmental state change {sc} (t={tsc}), "
                                        f"followed by subsequent {a2} movement at t={t2} without direct communication."
                                    ),
                                )

    def _detect_repeated_sequences(self, reading_id: str) -> None:
        """Identifies recurring behavioral-environmental temporal patterns."""
        if len(self._event_history) < 4:
            return
        # Look for paired movement -> state change patterns that reoccur
        for i in range(len(self._event_history) - 3):
            e1, e2 = self._event_history[i], self._event_history[i+1]
            e3, e4 = self._event_history[i+2], self._event_history[i+3]
            t1, t2 = self.nodes[e1].node_type, self.nodes[e2].node_type
            t3, t4 = self.nodes[e3].node_type, self.nodes[e4].node_type
            if (t1, t2) == (t3, t4) and (t1 != t2):
                if not any(e.source == e1 and e.target == e3 and e.edge_type == "repeated_sequence" for e in self.edges):
                    self.add_edge(
                        source=e1,
                        target=e3,
                        edge_type="repeated_sequence",
                        time_interval=[float(self.nodes[e1].first_observed_tick), float(self.nodes[e4].first_observed_tick)],
                        supporting_observation_ids=[reading_id],
                        confidence=0.80,
                        explanation=f"Reoccurring temporal pattern detected: ({t1} -> {t2}) repeated across consecutive intervals.",
                    )

    # ---------------------------------------------------------
    # Graph Ablation Transformers (Required by Section F)
    # ---------------------------------------------------------

    def get_time_shuffled_graph(self, seed: int = 42) -> TemporalEventGraph:
        """Ablation 2: Preserves all nodes and event counts, but scrambles temporal ordering."""
        g = copy.deepcopy(self)
        rng = random.Random(seed)

        event_nodes = [nid for nid, n in g.nodes.items() if n.node_type in ("movement_event", "state_change_event")]
        shuffled_ticks = [n.first_observed_tick for n in [g.nodes[nid] for nid in event_nodes]]
        rng.shuffle(shuffled_ticks)

        for nid, new_tick in zip(event_nodes, shuffled_ticks):
            g.nodes[nid].first_observed_tick = new_tick
            g.nodes[nid].attributes["tick"] = new_tick

        # Permute temporal edges (happened_before, followed_by)
        for e in g.edges:
            if e.edge_type in ("happened_before", "followed_by"):
                # Invert or randomize interval
                e.time_interval = [float(rng.randint(0, 24)), float(rng.randint(0, 24))]
                e.confidence = 0.50
                e.explanation += " [TIME-SHUFFLED NULL CONTROL: Chronological arrow disrupted]"
        return g

    def get_graph_without_cross_agent_edges(self) -> TemporalEventGraph:
        """Ablation 3: Removes all cross_agent_dependency_candidate edges."""
        g = copy.deepcopy(self)
        g.edges = [e for e in g.edges if e.edge_type != "cross_agent_dependency_candidate"]
        return g

    def get_graph_without_env_state_edges(self) -> TemporalEventGraph:
        """Ablation 4: Removes all environment_state_transition edges and resource links."""
        g = copy.deepcopy(self)
        g.edges = [e for e in g.edges if e.edge_type != "environment_state_transition"]
        return g

    # ---------------------------------------------------------
    # Prompt Formatting & Serialization
    # ---------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "snapshots": self.snapshots,
        }

    def to_prompt_text(self) -> str:
        """Formats the temporal graph topology for the LLM Graph Observer."""
        lines = [
            f"=== TEMPORAL EVENT GRAPH SUMMARY (Episode: {self.episode_id}) ===",
            f"Total Nodes: {len(self.nodes)} | Total Edges: {len(self.edges)}",
            "\n--- Observable Event Timeline ---",
        ]
        events = sorted(
            [n for n in self.nodes.values() if n.node_type in ("movement_event", "state_change_event")],
            key=lambda x: (x.first_observed_tick, x.node_id),
        )
        if not events:
            lines.append("No dynamic events observed yet.")
        else:
            for ev in events:
                lines.append(f"  [Tick {ev.first_observed_tick:2d}] ({ev.node_type}) {ev.label}")

        lines.append("\n--- Cross-Agent & Environmental Dependency Edges ---")
        rel_edges = [e for e in self.edges if e.edge_type in ("cross_agent_dependency_candidate", "repeated_sequence", "environment_state_transition", "temporally_correlated")]
        if not rel_edges:
            lines.append("No candidate dependency edges identified.")
        else:
            for e in rel_edges[-15:]:  # Most recent 15 relevant edges
                lines.append(f"  * [{e.edge_type.upper()}] {e.source} -> {e.target} (conf={e.confidence:.2f}): {e.explanation}")

        return "\n".join(lines)

