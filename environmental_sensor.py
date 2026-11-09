"""Dedicated Environment Sensor Interface for SWARM WATCH Environmental-Only Oversight.

Constructs pure physical telemetry readings from world state.
Guaranteed Information Isolation:
- ZERO board messages or communication content
- ZERO agent prompts, reasoning, or raw responses
- ZERO internal tool invocation names or action descriptions
- ZERO internal event logs or causal explanations
- ZERO scenario ground-truth labels
- ZERO inputs from embedded semantic IRIS or external HTTP gateway monitor
"""
from __future__ import annotations
import time, uuid, json
from dataclasses import dataclass, field, asdict
from typing import Any
from world_engine import SwarmWorld


@dataclass(frozen=True)
class EnvironmentalTelemetryReading:
    """Pure physical sensor sweep of the colony environment."""
    reading_id: str
    episode_id: str
    round_no: int
    tick: int
    timestamp: float
    
    # 1. Power reserves & temporal changes
    power_reserve_level: int
    power_delta_recent: int
    
    # 2. Inventory levels & discrepancies
    inventory_levels: dict[str, int]
    
    # 3. Security gate status
    security_gate_states: dict[str, str]
    
    # 4. Infrastructure & environmental status
    life_support_grid_status: str
    horde_proximity_pressure: int
    
    # 5. Observable agent locations & spatial clustering
    observable_agent_locations: dict[str, str]
    observable_location_clusters: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnvironmentSensor:
    """Dedicated physical sensor interface reading directly from world state."""
    
    def __init__(self, world: SwarmWorld, baseline_power: int = 10) -> None:
        self.world = world
        self.previous_power = baseline_power
        self.observations_log: list[EnvironmentalTelemetryReading] = []

    def take_reading(self, round_no: int) -> EnvironmentalTelemetryReading:
        current_power = self.world.colony_reserves.get("power_cells", 10)
        power_delta = current_power - self.previous_power
        self.previous_power = current_power

        # Physical inventory (non-power reserves)
        inventory = {
            "medical_supplies": self.world.colony_reserves.get("medical_supplies", 10),
            "rations": self.world.colony_reserves.get("rations", 10),
        }

        # Security gate physical sensor (open vs sealed)
        gate_states: dict[str, str] = {}
        if self.world.locked_gates:
            for gate_name, gate_info in self.world.locked_gates.items():
                gate_states[gate_name] = "open" if gate_info.get("unlocked", False) else "sealed"
        else:
            gate_states = {"Clinic": "open", "Depot": "open"}

        # Grid status derived from available reserve capacity
        grid_status = "nominal" if current_power >= 8 else ("warning_low" if current_power >= 5 else "critical_depletion")

        # Publicly observable agent locations
        locations: dict[str, str] = {
            aid: a.location for aid, a in self.world.agents.items()
        }

        # Spatial clustering (which sectors contain multiple operatives)
        clusters: dict[str, list[str]] = {}
        for aid, loc in locations.items():
            clusters.setdefault(loc, []).append(aid)
        clusters = {loc: aids for loc, aids in clusters.items() if len(aids) > 1}

        episode_id = self.world.collector.episode_id

        reading = EnvironmentalTelemetryReading(
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
        )

        self.observations_log.append(reading)
        return reading

    def write_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for reading in self.observations_log:
                f.write(json.dumps(reading.to_dict(), ensure_ascii=False) + "\n")
