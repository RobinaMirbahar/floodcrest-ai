"""FloodCrest AI Agent Orchestrator — Google BigQuery StandardSQL + Gemma 4 (Open Weights)."""

from __future__ import annotations

import os
from typing import Any, Optional

from floodcrest_agent.bigquery_engine import get_bigquery_warehouse
from floodcrest_agent.guardrails import floodcrest_adk_before_tool_guardrail
from floodcrest_agent.schemas import FloodDispatchAdvisory
from floodcrest_agent.tools import (
    UNDERPASS_BASINS,
    compute_floodcrest_dispatch,
    get_live_cloudburst_and_channel_telemetry,
    get_underpass_hydraulic_profile,
)

SYSTEM_INSTRUCTION = """You are FloodCrest AI, an urban flash-flood, underpass barrier, and retention-spillway safety agent
powered by Google BigQuery StandardSQL and open-weights Gemma 4.

MANDATORY SAFETY WORKFLOW:
1. Query `get_underpass_hydraulic_profile` and BigQuery warehouse rollup (`get_bigquery_warehouse`) for real Copernicus DEM sump geometry, catchment area, pump capacity, and historical rainfall peaks.
2. Query `get_live_cloudburst_and_channel_telemetry` for live rainfall intensity, retention basin fill %, and downstream river discharge.
3. Execute `compute_floodcrest_dispatch` to enforce the 4 deterministic hydraulic safety interlocks:
   - Gate 1: 30 cm engine-stall inundation countdown (`<= 20 min` -> immediate drop-arm barrier lock).
   - Gate 2: Downstream channel surcharge cap (`<= 95%` safe channel capacity so spillway openings never flood downstream homes).
   - Gate 3: Preemptive commuter diversion (`<= 45 min` or `>= 80%` retention fill) & N+1 pump duty ramp.
   - Gate 4: High-ground OSRM evacuation vector verification.
Never invent hydraulic capacities or override deterministic barrier closures."""


def build_gemma_bigquery_adk_agent(model_name: Optional[str] = None) -> Any:
    """Build the Google ADK LlmAgent backed by Gemma 4 + BigQuery tools when google-adk is installed."""
    resolved_model = model_name or os.environ.get("FLOODCREST_MODEL", "ollama_chat/gemma4:27b")
    try:
        from google.adk.agents import LlmAgent  # type: ignore
        from google.adk.models.lite_llm import LiteLlm  # type: ignore

        llm = LiteLlm(model=resolved_model) if ("/" in resolved_model and not resolved_model.startswith("gemini")) else resolved_model
        return LlmAgent(
            name="floodcrest_bigquery_gemma_agent",
            model=llm,
            description="Urban flash-flood underpass countdown, BigQuery hydrology & spillway safety agent.",
            instruction=SYSTEM_INSTRUCTION,
            tools=[
                get_underpass_hydraulic_profile,
                get_live_cloudburst_and_channel_telemetry,
                compute_floodcrest_dispatch,
            ],
            before_tool_callback=floodcrest_adk_before_tool_guardrail,
            output_schema=FloodDispatchAdvisory,
            output_key="flood_dispatch_advisory",
        )
    except ImportError:
        return None


def run_floodcrest_dispatch(
    basin_id: str,
    cloudburst_mm_hr: Optional[float] = None,
    retention_basin_fill_pct: Optional[float] = None,
    downstream_river_cms: Optional[float] = None,
    pump_availability_ratio: float = 1.0,
) -> FloodDispatchAdvisory:
    """Execute the complete BigQuery + Gemma 4 + 4-Gate Hydraulic Interlock pipeline."""
    spec = get_underpass_hydraulic_profile(basin_id)
    bq_rollup = get_bigquery_warehouse().get_basin_warehouse_rollup(spec["basin_id"])
    telem = get_live_cloudburst_and_channel_telemetry(
        basin_id=spec["basin_id"],
        override_rain_mm_hr=cloudburst_mm_hr,
        override_retention_pct=retention_basin_fill_pct,
        override_downstream_cms=downstream_river_cms,
        override_pump_ratio=pump_availability_ratio,
    )
    res = compute_floodcrest_dispatch(
        basin_id=spec["basin_id"],
        cloudburst_mm_hr=telem["cloudburst_mm_hr"],
        retention_basin_fill_pct=telem["retention_basin_fill_pct"],
        downstream_river_cms=telem["downstream_river_cms"],
        pump_availability_ratio=telem["pump_availability_ratio"],
    )
    dec = res["decision"]
    summary = (
        f"BigQuery peak 45d channel flow={bq_rollup.get('peak_45d_cms', 0.0)} m3/s | "
        f"Inflow={dec['inflow_m3_min']} m3/min vs Pump={dec['effective_pump_m3_min']} m3/min | "
        f"30cm Stall Countdown={dec['minutes_to_30cm_stall_flood']} min | "
        f"Spillway Gate={dec['approved_spillway_gate_pct']}% (Desired {dec['desired_spillway_gate_pct']}%)."
    )
    return FloodDispatchAdvisory(
        basin_id=spec["basin_id"],
        underpass_name=spec["underpass_name"],
        dispatch_status=dec["dispatch_status"],
        minutes_to_30cm_stall_flood=dec["minutes_to_30cm_stall_flood"],
        approved_spillway_gate_pct=dec["approved_spillway_gate_pct"],
        pump_duty_pct=dec["pump_duty_pct"],
        road_barriers_closed=dec["road_barriers_closed"],
        approved_commuter_speed_kmh=dec["approved_commuter_speed_kmh"],
        assigned_route_label=res["assigned_route_label"],
        route_distance_km=res["route_distance_km"],
        extra_evac_km=res["extra_evac_km"],
        downstream_surcharge_interlock=dec["downstream_surcharge_interlock"],
        vms_sign_banner=res["vms_sign_banner"],
        hydraulic_summary=summary,
        tools_invoked=[
            "bigquery_warehouse.get_basin_warehouse_rollup",
            "get_underpass_hydraulic_profile",
            "get_live_cloudburst_and_channel_telemetry",
            "compute_floodcrest_dispatch",
        ],
    )
