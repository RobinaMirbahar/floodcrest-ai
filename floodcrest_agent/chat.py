"""Gemma 4 + Google BigQuery Analytical Hydrology & Safety Copilot for FloodCrest AI."""

from __future__ import annotations

import os
from typing import Any, Dict

from floodcrest_agent.bigquery_engine import BIGQUERY_PRODUCTION_SQL_CATALOG, get_bigquery_warehouse
from floodcrest_agent.schemas import FloodDispatchAdvisory
from floodcrest_agent.tools import UNDERPASS_BASINS


def answer_floodcrest_query(
    query: str,
    basin_id: str,
    advisory: FloodDispatchAdvisory,
    telem: Dict[str, Any],
) -> str:
    """Answer operator hydrology, BigQuery SQL, spillway surcharge, or evacuation questions."""
    spec = UNDERPASS_BASINS.get(basin_id, UNDERPASS_BASINS["FLD-001"])
    bq = get_bigquery_warehouse()
    rollup = bq.get_basin_warehouse_rollup(spec["basin_id"])
    q_low = (query or "").lower()

    # Optional live Gemma 4 / Gemini API call when GEMINI_API_KEY is configured
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        try:
            from google import genai  # type: ignore

            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are FloodCrest AI (Google BigQuery + Gemma 4 Urban Flood Safety Copilot).\n"
                f"Active Basin: {spec['underpass_name']} ({spec['city_country']})\n"
                f"Telemetry: Rain={telem['cloudburst_mm_hr']} mm/hr, Retention={telem['retention_basin_fill_pct']}%, "
                f"Downstream={telem['downstream_river_cms']}/{spec['downstream_safe_channel_cms']} m3/s.\n"
                f"Guardrail Verdict: {advisory.dispatch_status}, Countdown={advisory.minutes_to_30cm_stall_flood} min, "
                f"Approved Spillway Gate={advisory.approved_spillway_gate_pct}%, Route={advisory.assigned_route_label} ({advisory.route_distance_km} km).\n"
                f"BigQuery 45d Peak Discharge={rollup.get('peak_45d_cms')} m3/s, Max Observed Rain={rollup.get('max_observed_rain_mm_hr')} mm/hr.\n"
                f"Operator Question: {query}\n"
                "Provide a concise, accurate 3-bullet engineering answer without em dashes."
            )
            resp = client.models.generate_content(model="gemma-3-27b-it", contents=prompt)
            if resp and getattr(resp, "text", None):
                return resp.text.strip()
        except Exception:
            pass

    if "sql" in q_low or "bigquery" in q_low or "noaa" in q_low:
        sql_snip = BIGQUERY_PRODUCTION_SQL_CATALOG["SPILLWAY_SURCHARGE_TRAP_AUDIT"]["bigquery_sql"]
        return (
            f"**BigQuery Analytical Warehouse Rollup (`{spec['basin_id']}`):**\n"
            f"- **45-Day GloFAS Peak Flow:** `{rollup.get('peak_45d_cms', 0.0)} m3/s` (Safe Channel Cap: `{spec['downstream_safe_channel_cms']} m3/s`)\n"
            f"- **Observed Hourly Rain Peak:** `{rollup.get('max_observed_rain_mm_hr', 0.0)} mm/hr` | Mean Topsoil Saturation: `{rollup.get('avg_soil_moisture', 0.0)} m3/m3`\n"
            f"- **Read-Only Guardrail Verified StandardSQL:**\n```sql\n{sql_snip}\n```"
        )

    if "spillway" in q_low or "surcharge" in q_low or "downstream" in q_low:
        cap_note = (
            "ACTIVE: Gate opening was clamped so downstream river discharge stays at or below 95% channel capacity."
            if advisory.downstream_surcharge_interlock
            else "WITHIN HEADROOM: Downstream river has sufficient capacity for the requested spillway release."
        )
        return (
            f"**Downstream River Surcharge Interlock (`{spec['city_country']}`):**\n"
            f"- **Live River Flow:** `{telem['downstream_river_cms']} m3/s` vs Safe Limit `{spec['downstream_safe_channel_cms']} m3/s` (`95%` hard ceiling = `{spec['downstream_safe_channel_cms']*0.95:.1f} m3/s`)\n"
            f"- **Approved Spillway Gate:** `{advisory.approved_spillway_gate_pct}%` | **Pump Station Duty:** `{advisory.pump_duty_pct}%`\n"
            f"- **Interlock Verdict:** {cap_note}"
        )

    if "evac" in q_low or "osrm" in q_low or "route" in q_low or "detour" in q_low:
        return (
            f"**OSRM High-Ground Evacuation Vector (`{spec['short_label']}`):**\n"
            f"- **Primary Depressed Underpass:** `{spec['primary_route_km']:.2f} km` ({'LOCKED BY DROP-ARM BARRIERS' if advisory.road_barriers_closed else 'OPEN'})\n"
            f"- **Verified High-Ground Arterial:** `{spec['evac_road_name']}` (`{spec['evac_route_km']:.2f} km`, `+{spec['evac_route_km'] - spec['primary_route_km']:.2f} km`)\n"
            f"- **Approved Commuter Speed:** `{advisory.approved_commuter_speed_kmh} km/h`"
        )

    return (
        f"**Rational Method & 30 cm Stall Countdown (`{spec['underpass_name']}`):**\n"
        f"- **Micro-Catchment Storm Inflow vs. Pumps:** `{advisory.hydraulic_summary}`\n"
        f"- **Time to 30 cm Engine-Stall Depth:** `{advisory.minutes_to_30cm_stall_flood} min` (`<= 20 min` triggers immediate emergency barrier lock)\n"
        f"- **Active Dispatch Verdict:** `{advisory.dispatch_status}` | Barriers Closed: `{advisory.road_barriers_closed}`"
    )
