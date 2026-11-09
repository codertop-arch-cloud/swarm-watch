"""Dedicated Environment Sensor Interface for SWARM WATCH: GHOST PROTOCOL.

Streams pure physical telemetry and publicly observable movements/transitions.
Guaranteed Information Isolation:
- ZERO board messages or communication content
- ZERO agent prompts, reasoning, or raw responses
- ZERO internal tool invocation names (no action descriptions)
- ZERO internal event logs or causal explanations
- ZERO scenario ground-truth labels
- ZERO inputs from embedded semantic IRIS or external HTTP gateway monitor
"""
from __future__ import annotations
import json, time, uuid
from dataclasses import dataclass, field, asdict
from typing import Any
from world_engine import SwarmWorld


@dataclass(frozen=True)
class GhostProtocolReading:
    """Pure physical and publicly observable telemetry reading."""
    reading_id: str
    episode_id: str
    round_no: int
    tick: int
    timestamp: float

    # 1. Power reserves & temporal changes
    power_reserve_level: int
    power_delta_recent: int

    # 2. Inventory levels
    inventory_levels: dict[str, int]

    # 3. Security gate states
    security_gate_states: dict[str, str]

    # 4. Infrastructure & environmental status
    life_support_grid_status: str
    horde_proximity_pressure: int

    # 5. Observable agent locations & spatial clustering
    observable_agent_locations: dict[str, str]
    observable_location_clusters: dict[str, list[str]]

    # 6. Observable public movements & infrastructure transitions (NO private tools or prompts)
    observable_movements: list[dict[str, Any]]
    observable_infra_events: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GhostProtocolSensor:
    """Sensor interface streaming physical world state to observers and temporal graphs."""

    def __init__(self, world: SwarmWorld, baseline_power: int = 10) -> None:
        self.world = world
        self.previous_power = baseline_power
        self.previous_locations: dict[str, str] = {aid: "Outpost" for aid in self.world.agents}
        self.previous_gate_states: dict[str, str] = {}
        self.readings_log: list[GhostProtocolReading] = []

    def take_reading(self, round_no: int) -> GhostProtocolReading:
        current_power = self.world.colony_reserves.get("power_cells", 10)
        power_delta = current_power - self.previous_power
        self.previous_power = current_power

        inventory = {
            "medical_supplies": self.world.colony_reserves.get("medical_supplies", 10),
            "rations": self.world.colony_reserves.get("rations", 10),
        }

        # Gate states
        gate_states: dict[str, str] = {}
        if self.world.locked_gates:
            for gate_name, gate_info in self.world.locked_gates.items():
                gate_states[gate_name] = "open" if gate_info.get("unlocked", False) else "sealed"
        else:
            gate_states = {"Clinic": "open", "Depot": "open"}

        # Observable gate transitions
        infra_events = []
        for g_name, g_state in gate_states.items():
            prev_s = self.previous_gate_states.get(g_name, g_state)
            if prev_s != g_state:
                infra_events.append({
                    "infra": g_name,
                    "transition": f"{prev_s}->{g_state}",
                    "tick": self.world.tick,
                })
        self.previous_gate_states = dict(gate_states)

        grid_status = "nominal" if current_power >= 8 else ("warning_low" if current_power >= 5 else "critical_depletion")

        # Observable agent locations
        locations: dict[str, str] = {
            aid: a.location for aid, a in self.world.agents.items()
        }

        # Observable movements since last sweep
        movements = []
        for aid, loc in locations.items():
            prev_loc = self.previous_locations.get(aid, "Outpost")
            if loc != prev_loc:
                movements.append({
                    "agent_id": aid,
                    "from_location": prev_loc,
                    "to_location": loc,
                    "tick": self.world.tick,
                })
        self.previous_locations = dict(locations)

        # Spatial clusters
        clusters: dict[str, list[str]] = {}
        for aid, loc in locations.items():
            clusters.setdefault(loc, []).append(aid)
        clusters = {loc: aids for loc, aids in clusters.items() if len(aids) > 1}

        episode_id = self.world.collector.episode_id

        reading = GhostProtocolReading(
            reading_id=str(uuid.uuid4()),
            episode_id=episode_id,
            round_no=round_no,
            tick=self.world.tick,
            timestamp=time.time(),
            power_reserve_level=current_power,
            power_delta_recent=power_delta,
            inventory_levels=inventory,
            security_gate_states=gate_states,
            life_support_grid_status=grid_status,
            horde_proximity_pressure=self.world.zombie_horde_aggressiveness,
            observable_agent_locations=locations,
            observable_location_clusters=clusters,
            observable_movements=movements,
            observable_infra_events=infra_events,
        )
        self.readings_log.append(reading)
        return reading

