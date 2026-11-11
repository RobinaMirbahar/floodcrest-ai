"""Pydantic v2 data contracts and structured hydraulic dispatch schemas for FloodCrest AI."""

from typing import List, Literal
from pydantic import BaseModel, Field

FloodDispatchStatus = Literal[
    "NOMINAL_DRAINAGE_OPEN",
    "FLOOD_WATCH_PUMPS_HIGH_SPEED_40KMH",
    "CLOSE_UNDERPASS_PREEMPTIVE_DIVERT",
    "EMERGENCY_LOCK_BARRIERS_EVACUATE",
]


class UnderpassBasinSpec(BaseModel):
    """Real DEM-anchored hydraulic specification for a monitored urban commuter underpass & retention basin."""

    basin_id: str
    underpass_name: str
    city_country: str
    latitude: float
    longitude: float
    evac_waypoint_lat: float
    evac_waypoint_lon: float
    catchment_area_km2: float = Field(..., gt=0)
    impervious_runoff_coeff: float = Field(..., gt=0, le=1.0)
    sump_storage_area_m2: float = Field(..., gt=0)
    installed_pump_capacity_m3_min: float = Field(..., gt=0)
    downstream_safe_channel_cms: float = Field(..., gt=0)


class FloodGuardrailDecision(BaseModel):
    """Deterministic urban hydrology, spillway surcharge, countdown, and barrier-lock output."""

    basin_id: str
    inflow_m3_min: float
    effective_pump_m3_min: float
    net_accumulation_m3_min: float
    minutes_to_30cm_stall_flood: float
    desired_spillway_gate_pct: int = Field(..., ge=0, le=100)
    approved_spillway_gate_pct: int = Field(..., ge=0, le=100)
    downstream_surcharge_interlock: bool
    road_barriers_closed: bool
    pump_duty_pct: int = Field(..., ge=0, le=100)
    approved_commuter_speed_kmh: int = Field(..., ge=0, le=80)
    dispatch_status: FloodDispatchStatus
    guardrail_notes: List[str]


class FloodDispatchAdvisory(BaseModel):
    """Validated structured JSON flood dispatch advisory emitted to pump stations, barriers & VMS signs."""

    basin_id: str
    underpass_name: str
    dispatch_status: FloodDispatchStatus
    minutes_to_30cm_stall_flood: float
    approved_spillway_gate_pct: int
    pump_duty_pct: int
    road_barriers_closed: bool
    approved_commuter_speed_kmh: int
    assigned_route_label: str
    route_distance_km: float
    extra_evac_km: float
    downstream_surcharge_interlock: bool
    vms_sign_banner: str
    hydraulic_summary: str
    tools_invoked: List[str]
