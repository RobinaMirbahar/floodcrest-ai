# -*- coding: utf-8 -*-
"""
FloodCrest AI — Urban Cloudburst, Spillway & Underpass Flash-Flood Safety Platform
Powered by Google BigQuery StandardSQL, Open-Weights Gemma 4, USGS 15-Min Gauges & Keyless OSRM Routing.
Author: Robina Mirbahar
"""

import json
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from floodcrest_agent.agent import run_floodcrest_dispatch
from floodcrest_agent.bigquery_engine import BIGQUERY_PRODUCTION_SQL_CATALOG, get_bigquery_warehouse
from floodcrest_agent.chat import answer_floodcrest_query
from floodcrest_agent.tools import (
    UNDERPASS_BASINS,
    get_live_cloudburst_and_channel_telemetry,
    get_underpass_hydraulic_profile,
)

st.set_page_config(
    page_title="FloodCrest AI | Google BigQuery + Gemma 4 Urban Flood Safety",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def render_html(raw_html: str) -> None:
    compact = "".join(line.strip() for line in raw_html.splitlines() if line.strip())
    st.markdown(compact, unsafe_allow_html=True)


# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
if "basin_id" not in st.session_state:
    st.session_state["basin_id"] = "FLD-001"
if "rain_mm_hr" not in st.session_state:
    st.session_state["rain_mm_hr"] = 68.0
if "retention_pct" not in st.session_state:
    st.session_state["retention_pct"] = 81.0
if "downstream_cms" not in st.session_state:
    st.session_state["downstream_cms"] = 125.8
if "pump_ratio" not in st.session_state:
    st.session_state["pump_ratio"] = 1.0
if "map_mode" not in st.session_state:
    st.session_state["map_mode"] = "BASIN"
if "sql_key" not in st.session_state:
    st.session_state["sql_key"] = "USGS_ROLLING_SURGE_WINDOW"
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = [
        {
            "role": "assistant",
            "content": "🌊 **FloodCrest AI (BigQuery + Gemma 4) Online.** Tap any cloudburst preset above or ask about the 30 cm vehicle-stall countdown, downstream river surcharge cap, or BigQuery StandardSQL analytics.",
        }
    ]

# ---------------------------------------------------------
# Distinct Oceanic-Cyan & Deep-Hydrology Mobile-Responsive CSS
# ---------------------------------------------------------
render_html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

:root { color-scheme: dark; }
html, body, .stApp {
    background: radial-gradient(circle at 80% 0%, #0d2538 0%, #07131f 52%, #040b14 100%) !important;
    color: #f0f9ff !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.block-container {
    padding-top: 1.15rem !important;
    padding-bottom: 2.2rem !important;
    max-width: 1440px !important;
}
header[data-testid="stHeader"] { background: transparent !important; }

div[data-testid="stButton"] > button {
    background: rgba(12, 29, 46, 0.88) !important;
    color: #e0f2fe !important;
    border: 1px solid rgba(56, 189, 248, 0.24) !important;
    border-radius: 10px !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    min-height: 42px !important;
    padding: 0.45rem 0.85rem !important;
    transition: all 0.18s ease !important;
}
div[data-testid="stButton"] > button:hover {
    border-color: #22d3ee !important;
    background: rgba(14, 42, 66, 0.96) !important;
    color: #ffffff !important;
    transform: translateY(-1px);
}
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #0284c7 0%, #06b6d4 100%) !important;
    color: #ffffff !important;
    border: 1px solid rgba(103, 232, 249, 0.7) !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 14px rgba(6, 182, 212, 0.32) !important;
}

.fc-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    background: rgba(10, 25, 41, 0.82);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(56, 189, 248, 0.20);
    border-radius: 16px;
    padding: 14px 20px;
    margin-bottom: 16px;
}
.fc-brand { display: flex; align-items: center; gap: 12px; }
.fc-icon {
    width: 40px; height: 40px; border-radius: 11px;
    background: linear-gradient(135deg, #0284c7, #06b6d4);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; box-shadow: 0 4px 12px rgba(6, 182, 212, 0.38);
}
.fc-title { font-size: 1.18rem; font-weight: 800; color: #ffffff; letter-spacing: -0.01em; }
.fc-sub { font-size: 0.78rem; color: #94a3b8; }
.fc-badges { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.fc-pill {
    font-size: 11.5px; font-weight: 600; padding: 5px 11px; border-radius: 999px;
    background: rgba(15, 35, 56, 0.9); border: 1px solid rgba(56, 189, 248, 0.25); color: #bae6fd;
}
.fc-pill-live {
    background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.45); color: #34d399;
}

.fc-banner {
    border-radius: 18px; padding: 20px 24px; margin-bottom: 16px; border: 1px solid;
    display: grid; grid-template-columns: 1.38fr 1fr; gap: 18px; align-items: center;
}
.fc-crit { background: linear-gradient(135deg, rgba(153, 27, 27, 0.40) 0%, rgba(10, 25, 41, 0.94) 100%); border-color: rgba(248, 113, 113, 0.58); }
.fc-warn { background: linear-gradient(135deg, rgba(146, 64, 14, 0.38) 0%, rgba(10, 25, 41, 0.94) 100%); border-color: rgba(251, 191, 36, 0.55); }
.fc-safe { background: linear-gradient(135deg, rgba(6, 95, 70, 0.38) 0%, rgba(10, 25, 41, 0.94) 100%); border-color: rgba(52, 211, 153, 0.50); }

.fc-eyebrow { font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #22d3ee; margin-bottom: 4px; }
.fc-h1 { font-size: clamp(1.2rem, 2.2vw, 1.65rem); font-weight: 800; color: #ffffff; line-height: 1.2; margin-bottom: 8px; }
.fc-led {
    font-family: 'JetBrains Mono', monospace; background: #030811; border: 2px solid #1e3a5f;
    border-radius: 12px; padding: 13px 16px; text-align: center; box-shadow: inset 0 0 18px rgba(0,0,0,0.88);
}

.fc-kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }
.fc-card {
    background: rgba(10, 25, 41, 0.82); border: 1px solid rgba(56, 189, 248, 0.18);
    border-radius: 14px; padding: 16px 18px;
}
.fc-card-top { display: flex; justify-content: space-between; font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 8px; }
.fc-card-val { font-family: 'JetBrains Mono', monospace; font-size: 1.32rem; font-weight: 700; color: #ffffff; margin-bottom: 8px; }
.fc-bar-bg { width: 100%; height: 7px; background: rgba(30, 58, 95, 0.7); border-radius: 999px; overflow: hidden; margin-bottom: 7px; }
.fc-bar-fill { height: 100%; border-radius: 999px; }
.fc-card-sub { font-size: 11.5px; color: #cbd5e1; }

.fc-gates { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 14px; }
.fc-gate { border-radius: 12px; padding: 12px 14px; background: rgba(10, 25, 41, 0.85); border: 1px solid rgba(56, 189, 248, 0.2); }
.fc-gate-trip { border-color: rgba(248, 113, 113, 0.65); background: rgba(127, 29, 29, 0.24); }
.fc-gate-ok { border-color: rgba(52, 211, 153, 0.38); }
.fc-sec { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.09em; color: #7dd3fc; margin: 6px 0 10px 0; }

@media (max-width: 1024px) {
    .fc-banner { grid-template-columns: 1fr; }
    .fc-kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
    .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; padding-top: 0.7rem !important; }
    .fc-kpi-grid { grid-template-columns: 1fr; gap: 10px; }
    .fc-gates { grid-template-columns: 1fr; }
    div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    div[data-testid="column"] { min-width: 47% !important; flex: 1 1 47% !important; }
}
</style>
""")

# ---------------------------------------------------------
# 1. Top Navigation Header
# ---------------------------------------------------------
render_html("""
<div class="fc-nav">
  <div class="fc-brand">
    <div class="fc-icon">🌊</div>
    <div>
      <div class="fc-title">FloodCrest AI</div>
      <div class="fc-sub">Urban Cloudburst, Underpass Barrier &amp; Spillway Safety Platform • Google BigQuery + Gemma 4</div>
    </div>
  </div>
  <div class="fc-badges">
    <span class="fc-pill">Google BigQuery StandardSQL</span>
    <span class="fc-pill">Gemma 4 (Open Weights)</span>
    <span class="fc-pill">USGS + GloFAS + Copernicus DEM</span>
    <span class="fc-pill fc-pill-live">● Hydrology Telemetry Online</span>
  </div>
</div>
""")

# ---------------------------------------------------------
# 2. 1-Tap Cloudburst & Spillway Scenario Presets
# ---------------------------------------------------------
render_html('<div class="fc-sec">⚡ Simulate Real Urban Cloudburst &amp; Spillway Scenarios (1-Tap Presets)</div>')
p1, p2, p3, p4, p5 = st.columns(5)
with p1:
    if st.button("🚨 Houston 68 mm/hr Sump Surge", use_container_width=True):
        st.session_state.update({"basin_id": "FLD-001", "rain_mm_hr": 68.0, "retention_pct": 81.0, "downstream_cms": 125.8, "pump_ratio": 1.0, "map_mode": "BASIN"})
        st.rerun()
with p2:
    if st.button("🌊 Downstream Surcharge Trap", use_container_width=True):
        st.session_state.update({"basin_id": "FLD-003", "rain_mm_hr": 74.0, "retention_pct": 89.0, "downstream_cms": 134.4, "pump_ratio": 1.0, "map_mode": "BASIN"})
        st.rerun()
with p3:
    if st.button("⚙️ Single-Pump Failure (50%)", use_container_width=True):
        st.session_state.update({"basin_id": "FLD-008", "rain_mm_hr": 95.0, "retention_pct": 88.0, "downstream_cms": 152.0, "pump_ratio": 0.50, "map_mode": "BASIN"})
        st.rerun()
with p4:
    if st.button("🌧️ London 34 mm/hr Storm Watch", use_container_width=True):
        st.session_state.update({"basin_id": "FLD-006", "rain_mm_hr": 34.0, "retention_pct": 60.0, "downstream_cms": 62.0, "pump_ratio": 1.0, "map_mode": "BASIN"})
        st.rerun()
with p5:
    if st.button("✅ Clear Dry-Weather Drainage", use_container_width=True):
        st.session_state.update({"basin_id": "FLD-001", "rain_mm_hr": 8.0, "retention_pct": 35.0, "downstream_cms": 64.0, "pump_ratio": 1.0, "map_mode": "BASIN"})
        st.rerun()

# ---------------------------------------------------------
# 3. Mobile-Friendly Basin & Pump Selector Bar
# ---------------------------------------------------------
BASIN_LABELS = {
    k: f"[{v['city_country'].split(',')[-1].strip()}] {v['short_label']}"
    for k, v in UNDERPASS_BASINS.items()
}
PUMP_LABELS = {
    1.0: "All Stormwater Pumps Online (100% N+1 Capacity)",
    0.75: "1 Auxiliary Pump Degraded (75% Capacity)",
    0.50: "Primary Pump Trip — Emergency Single Bank (50% Capacity)",
}

c_sel1, c_sel2, c_sel3 = st.columns([1.65, 1.25, 0.9])
with c_sel1:
    sel_bid = st.selectbox(
        "📍 Monitored Global Urban Underpass Basin (US • Pakistan • UAE • UK • Azerbaijan • South Korea)",
        options=list(UNDERPASS_BASINS.keys()),
        index=list(UNDERPASS_BASINS.keys()).index(st.session_state["basin_id"]),
        format_func=lambda bid: BASIN_LABELS[bid],
    )
    if sel_bid != st.session_state["basin_id"]:
        b_spec = UNDERPASS_BASINS[sel_bid]
        st.session_state.update({
            "basin_id": sel_bid,
            "rain_mm_hr": float(b_spec["default_rain_mm_hr"]),
            "retention_pct": float(b_spec["default_retention_pct"]),
            "downstream_cms": float(b_spec["default_ds_cms"]),
            "map_mode": "BASIN",
        })
        st.rerun()

with c_sel2:
    curr_p = st.session_state["pump_ratio"] if st.session_state["pump_ratio"] in PUMP_LABELS else 1.0
    sel_p = st.selectbox(
        "⚙️ Sump Pump Station Availability",
        options=list(PUMP_LABELS.keys()),
        index=list(PUMP_LABELS.keys()).index(curr_p),
        format_func=lambda r: PUMP_LABELS[r],
    )
    if sel_p != st.session_state["pump_ratio"]:
        st.session_state["pump_ratio"] = sel_p
        st.rerun()

with c_sel3:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    w_lbl = "📍 Zoom to Active Sump" if st.session_state["map_mode"] == "WORLD" else "🌍 View All 8 Global Cities"
    if st.button(w_lbl, type="primary" if st.session_state["map_mode"] == "WORLD" else "secondary", use_container_width=True):
        st.session_state["map_mode"] = "WORLD" if st.session_state["map_mode"] == "BASIN" else "BASIN"
        st.rerun()

spec = get_underpass_hydraulic_profile(st.session_state["basin_id"])

with st.expander("🎛️ Fine-Tune Cloudburst Intensity (mm/hr), Retention Basin Fill % & Downstream River Flow", expanded=False):
    s1, s2, s3 = st.columns(3)
    with s1:
        st.session_state["rain_mm_hr"] = st.slider("Cloudburst Rainfall Intensity (mm/hr)", 0.0, 160.0, float(st.session_state["rain_mm_hr"]), 2.0)
    with s2:
        st.session_state["retention_pct"] = st.slider("Retention Basin Fill (%)", 10.0, 100.0, float(st.session_state["retention_pct"]), 1.0)
    with s3:
        max_slider_cms = round(float(spec["downstream_safe_channel_cms"]) * 1.15, 1)
        st.session_state["downstream_cms"] = st.slider(
            f"Downstream Channel Flow (m3/s • Safe Limit {spec['downstream_safe_channel_cms']} m3/s)",
            10.0,
            max_slider_cms,
            min(float(st.session_state["downstream_cms"]), max_slider_cms),
            1.0,
        )

# ---------------------------------------------------------
# Execute BigQuery + Gemma 4 + 4-Gate Hydraulic Interlocks
# ---------------------------------------------------------
telem = get_live_cloudburst_and_channel_telemetry(
    basin_id=spec["basin_id"],
    override_rain_mm_hr=st.session_state["rain_mm_hr"],
    override_retention_pct=st.session_state["retention_pct"],
    override_downstream_cms=st.session_state["downstream_cms"],
    override_pump_ratio=st.session_state["pump_ratio"],
)
advisory = run_floodcrest_dispatch(
    basin_id=spec["basin_id"],
    cloudburst_mm_hr=telem["cloudburst_mm_hr"],
    retention_basin_fill_pct=telem["retention_basin_fill_pct"],
    downstream_river_cms=telem["downstream_river_cms"],
    pump_availability_ratio=telem["pump_availability_ratio"],
)
bq_warehouse = get_bigquery_warehouse()
bq_rollup = bq_warehouse.get_basin_warehouse_rollup(spec["basin_id"])

# ---------------------------------------------------------
# 4. Verdict Banner & Underpass Drop-Arm Barrier LED Sign
# ---------------------------------------------------------
is_crit = advisory.road_barriers_closed
is_warn = advisory.dispatch_status == "FLOOD_WATCH_PUMPS_HIGH_SPEED_40KMH"
b_cls = "fc-crit" if is_crit else ("fc-warn" if is_warn else "fc-safe")
led_col = "#f87171" if is_crit else ("#fbbf24" if is_warn else "#34d399")

status_human = {
    "EMERGENCY_LOCK_BARRIERS_EVACUATE": "🛑 SUB-20-MIN FLASH FLOOD — DROP-ARM BARRIERS LOCKED & EVACUATION ACTIVE",
    "CLOSE_UNDERPASS_PREEMPTIVE_DIVERT": "⛔ PREEMPTIVE UNDERPASS CLOSURE — PUMPS AT 100% & HIGH-GROUND DETOUR",
    "FLOOD_WATCH_PUMPS_HIGH_SPEED_40KMH": "⚠️ CONVECTIVE STORM WATCH — PUMPS RAMPED TO 85% & SPEED CLAMPED 40 KM/H",
    "NOMINAL_DRAINAGE_OPEN": "✅ DRAINAGE NOMINAL — UNDERPASS OPEN & PUMPS ON STANDBY",
}.get(advisory.dispatch_status, advisory.dispatch_status)

cd_txt = f"{advisory.minutes_to_30cm_stall_flood:.1f} min" if advisory.minutes_to_30cm_stall_flood < 900 else "No Accumulation (>999 min)"

render_html(f"""
<div class="fc-banner {b_cls}">
  <div>
    <div class="fc-eyebrow">{spec['basin_id']} • {spec['city_country']} • DEM Invert: {spec['underpass_invert_elevation_m']} m</div>
    <div class="fc-h1">{spec['underpass_name']}</div>
    <div style="font-size:13.5px;font-weight:700;color:{led_col};margin-bottom:6px;">{status_human}</div>
    <div style="font-size:12.5px;color:#cbd5e1;">
      30 cm Stall Countdown: <b>{cd_txt}</b> &nbsp;•&nbsp;
      Spillway Gate: <b>{advisory.approved_spillway_gate_pct}%</b> &nbsp;•&nbsp;
      BigQuery 45d Peak: <b>{bq_rollup.get('peak_45d_cms', 0.0)} m³/s</b>
    </div>
  </div>
  <div class="fc-led">
    <div style="font-size:10px;letter-spacing:0.14em;color:#64748b;margin-bottom:5px;">LIVE UNDERPASS PORTAL LED GANTRY SIGN</div>
    <div style="font-size:13px;font-weight:700;color:{led_col};">{advisory.vms_sign_banner}</div>
  </div>
</div>
""")

# ---------------------------------------------------------
# 5. 4 Visual Progress-Meter Hydrology Cards
# ---------------------------------------------------------
cd_pct = 100 if advisory.minutes_to_30cm_stall_flood <= 20 else (
    max(15, int(100 - (advisory.minutes_to_30cm_stall_flood / 90.0) * 100))
    if advisory.minutes_to_30cm_stall_flood < 900 else 12
)
cd_col = "#ef4444" if advisory.minutes_to_30cm_stall_flood <= 45 else "#10b981"

ds_pct = min(100, int((telem["downstream_river_cms"] / max(spec["downstream_safe_channel_cms"], 1.0)) * 100))
ds_col = "#ef4444" if advisory.downstream_surcharge_interlock else ("#f59e0b" if ds_pct >= 80 else "#10b981")

pump_col = "#38bdf8" if advisory.pump_duty_pct >= 85 else "#10b981"
evac_col = "#22d3ee" if advisory.extra_evac_km > 0 else "#10b981"

render_html(f"""
<div class="fc-kpi-grid">
  <div class="fc-card">
    <div class="fc-card-top"><span>⏱️ 30 cm Engine-Stall Timer</span><span>Rational Method</span></div>
    <div class="fc-card-val">{cd_txt}</div>
    <div class="fc-bar-bg"><div class="fc-bar-fill" style="width:{cd_pct}%;background:{cd_col};"></div></div>
    <div class="fc-card-sub">Rain: {telem['cloudburst_mm_hr']} mm/hr • Sump {int(spec['sump_storage_area_m2'])} m²</div>
  </div>
  <div class="fc-card">
    <div class="fc-card-top"><span>🌊 Downstream Channel Cap</span><span>≤95% Interlock</span></div>
    <div class="fc-card-val">{telem['downstream_river_cms']:.1f} <span style="font-size:13px;color:#94a3b8;">/ {spec['downstream_safe_channel_cms']:.0f} m³/s</span></div>
    <div class="fc-bar-bg"><div class="fc-bar-fill" style="width:{ds_pct}%;background:{ds_col};"></div></div>
    <div class="fc-card-sub">{'Spillway Clamped to ' + str(advisory.approved_spillway_gate_pct) + '% (Surcharge Lock)' if advisory.downstream_surcharge_interlock else f'Spillway Gate Approved at {advisory.approved_spillway_gate_pct}%'}</div>
  </div>
  <div class="fc-card">
    <div class="fc-card-top"><span>⚙️ Sump Pump Bank Duty</span><span>N+1 Station</span></div>
    <div class="fc-card-val">{advisory.pump_duty_pct}% <span style="font-size:13px;color:#94a3b8;">({int(spec['installed_pump_capacity_m3_min']*telem['pump_availability_ratio'])} m³/min)</span></div>
    <div class="fc-bar-bg"><div class="fc-bar-fill" style="width:{advisory.pump_duty_pct}%;background:{pump_col};"></div></div>
    <div class="fc-card-sub">Retention Basin Fill: {telem['retention_basin_fill_pct']:.0f}%</div>
  </div>
  <div class="fc-card">
    <div class="fc-card-top"><span>🗺️ High-Ground OSRM Route</span><span>Evacuation</span></div>
    <div class="fc-card-val">{advisory.route_distance_km:.2f} km <span style="font-size:13px;color:#22d3ee;">@ {advisory.approved_commuter_speed_kmh} km/h</span></div>
    <div class="fc-bar-bg"><div class="fc-bar-fill" style="width:{100 if advisory.extra_evac_km > 0 else 50}%;background:{evac_col};"></div></div>
    <div class="fc-card-sub">{f'High-Ground Crest (+{advisory.extra_evac_km:.2f} km)' if advisory.extra_evac_km > 0 else 'Primary Underpass Open'}</div>
  </div>
</div>
""")

# ---------------------------------------------------------
# 6. Split View: Live Keyless Dark OSRM Evacuation Map + 4-Gate Status & Copilot
# ---------------------------------------------------------
col_map, col_ops = st.columns([1.52, 1.0], gap="medium")

with col_map:
    m_hdr = "🌍 Global 8-City Urban Flash-Flood Network" if st.session_state["map_mode"] == "WORLD" else f"🗺️ Live OSRM High-Ground Evacuation — {spec['short_label']}"
    render_html(f'<div class="fc-sec">{m_hdr}</div>')

    nodes_json = json.dumps([
        {
            "id": k,
            "name": v["underpass_name"],
            "city": v["city_country"],
            "lat": v["latitude"],
            "lon": v["longitude"],
            "pump": v["installed_pump_capacity_m3_min"],
            "cap": v["downstream_safe_channel_cms"],
        }
        for k, v in UNDERPASS_BASINS.items()
    ])
    olat, olon = round(spec["latitude"] + 0.011, 5), round(spec["longitude"] - 0.011, 5)
    dlat, dlon = round(spec["latitude"] - 0.011, 5), round(spec["longitude"] + 0.011, 5)
    diverted_js = "true" if advisory.road_barriers_closed else "false"
    world_js = "true" if st.session_state["map_mode"] == "WORLD" else "false"

    leaflet_html = f"""<!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
      <style>
        * {{ box-sizing: border-box; }}
        body {{ margin:0; padding:0; background:#07131f; font-family:'Plus Jakarta Sans', sans-serif; }}
        #wrap {{ position:relative; width:100%; height:450px; border:1px solid rgba(56,189,248,0.25); border-radius:14px; overflow:hidden; background:#07131f; }}
        #map {{ width:100%; height:100%; background:#07131f; }}
        .hud-top {{
          position:absolute; top:10px; left:50px; right:10px; z-index:999;
          display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;
          background:rgba(10,25,41,0.90); border:1px solid rgba(56,189,248,0.28); border-radius:10px;
          padding:7px 12px; color:#f0f9ff; font-size:11.5px; font-weight:600; backdrop-filter:blur(8px);
        }}
        .hud-bot {{
          position:absolute; bottom:10px; left:10px; right:10px; z-index:999;
          display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; pointer-events:none;
        }}
        .hud-btn {{
          pointer-events:auto; background:rgba(10,25,41,0.94); color:#e0f2fe;
          border:1px solid rgba(34,211,238,0.6); border-radius:8px; padding:6px 11px; font-size:11.5px; font-weight:600; cursor:pointer;
        }}
        .hud-leg {{
          pointer-events:auto; background:rgba(10,25,41,0.92); border:1px solid rgba(56,189,248,0.25);
          border-radius:8px; padding:6px 11px; color:#e0f2fe; font-size:11.5px; font-weight:600;
        }}
        .leaflet-tile {{ filter: invert(100%) hue-rotate(185deg) brightness(92%) contrast(93%); }}
        .leaflet-popup-content-wrapper, .leaflet-popup-tip {{
          background:#0a1929 !important; color:#f0f9ff !important; border:1px solid #0284c7; border-radius:10px;
        }}
      </style>
    </head>
    <body>
      <div id="wrap">
        <div id="map"></div>
        <div class="hud-top">
          <div>🌊 <b>{spec['short_label']}</b></div>
          <div style="color:#7dd3fc;font-family:monospace;">{spec['latitude']:.4f}, {spec['longitude']:.4f}</div>
        </div>
        <div class="hud-bot">
          <div style="display:flex;gap:6px;">
            <button class="hud-btn" onclick="zoomBasin()">📍 Basin View</button>
            <button class="hud-btn" onclick="zoomWorld()">🌍 All 8 Global Cities</button>
          </div>
          <div class="hud-leg">
            <span style="color:#f87171;">- - Flooded Sump</span> &nbsp;|&nbsp;
            <span style="color:#34d399;">━━ High-Ground Crest</span>
          </div>
        </div>
      </div>
      <script>
        const nodes = {nodes_json};
        const blat = {spec['latitude']}, blon = {spec['longitude']};
        const olat = {olat}, olon = {olon};
        const dlat = {dlat}, dlon = {dlon};
        const elat = {spec['evac_waypoint_lat']}, elon = {spec['evac_waypoint_lon']};
        const diverted = {diverted_js};
        const startWorld = {world_js};

        const map = L.map('map', {{ attributionControl: false }}).setView(startWorld ? [28.0, 22.0] : [blat, blon], startWorld ? 2 : 13);
        L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }}).addTo(map);

        nodes.forEach(n => {{
          const isCurr = n.id === "{spec['basin_id']}";
          const col = isCurr ? (diverted ? '#ef4444' : '#10b981') : '#06b6d4';
          const m = L.circleMarker([n.lat, n.lon], {{
            radius: isCurr ? 10 : 6, color: '#ffffff', weight: isCurr ? 2.5 : 1.5, fillColor: col, fillOpacity: 0.95
          }}).addTo(map);
          m.bindPopup(`<div style="font-size:12px;line-height:1.4;"><b>${{n.name}}</b><br/><span style="color:#7dd3fc;">${{n.city}}</span><br/>Pump Bank: <b>${{n.pump}} m³/min</b> • Channel Cap: <b>${{n.cap}} m³/s</b></div>`);
          if (isCurr && !startWorld) m.openPopup();
        }});

        L.circleMarker([olat, olon], {{radius:6, color:'#38bdf8', fillColor:'#38bdf8', fillOpacity:0.95}}).addTo(map).bindPopup('🚗 Commuter Entry');
        L.circleMarker([dlat, dlon], {{radius:6, color:'#a855f7', fillColor:'#a855f7', fillOpacity:0.95}}).addTo(map).bindPopup('🏁 Safe Destination');

        let basinBounds = L.latLngBounds([[olat, olon], [blat, blon], [dlat, dlon], [elat, elon]]);

        async function drawRoutes() {{
          try {{
            const r1 = await fetch(`https://router.project-osrm.org/route/v1/driving/${{olon}},${{olat}};${{blon}},${{blat}};${{dlon}},${{dlat}}?overview=full&geometries=geojson`);
            const j1 = await r1.json();
            if (j1.routes && j1.routes[0]) {{
              const l1 = L.geoJSON(j1.routes[0].geometry, {{
                style: {{ color: diverted ? '#ef4444' : '#10b981', weight: diverted ? 3.5 : 5.5, dashArray: diverted ? '7,7' : null, opacity: 0.92 }}
              }}).addTo(map);
              if (!diverted && !startWorld) map.fitBounds(l1.getBounds(), {{padding:[34,34]}});
            }}
            if (diverted) {{
              const r2 = await fetch(`https://router.project-osrm.org/route/v1/driving/${{olon}},${{olat}};${{elon}},${{elat}};${{dlon}},${{dlat}}?overview=full&geometries=geojson`);
              const j2 = await r2.json();
              if (j2.routes && j2.routes[0]) {{
                const l2 = L.geoJSON(j2.routes[0].geometry, {{
                  style: {{ color: '#10b981', weight: 5.5, opacity: 0.96 }}
                }}).addTo(map);
                L.circleMarker([elat, elon], {{radius:6, color:'#10b981', fillColor:'#10b981', fillOpacity:1}})
                  .addTo(map).bindPopup('✅ High-Ground Crest: {spec["evac_road_name"]}');
                if (!startWorld) map.fitBounds(l2.getBounds(), {{padding:[34,34]}});
              }}
            }}
          }} catch (e) {{
            if (!startWorld) map.fitBounds(basinBounds, {{padding:[34,34]}});
          }}
        }}
        drawRoutes();

        window.zoomBasin = function() {{ map.fitBounds(basinBounds, {{padding:[34,34]}}); }};
        window.zoomWorld = function() {{ map.setView([28.0, 22.0], 2); }};
      </script>
    </body>
    </html>"""
    components.html(leaflet_html, height=460)

with col_ops:
    render_html('<div class="fc-sec">🛡️ 4-Gate Hydraulic &amp; Spillway Interlock Checklist</div>')

    g1 = advisory.minutes_to_30cm_stall_flood <= 20.0
    g2 = advisory.downstream_surcharge_interlock
    g3 = advisory.road_barriers_closed
    g4 = telem["pump_availability_ratio"] < 1.0

    render_html(f"""
    <div class="fc-gates">
      <div class="fc-gate {'fc-gate-trip' if g1 else 'fc-gate-ok'}">
        <div style="font-size:11px;color:#94a3b8;font-weight:600;">GATE 1 • 30 CM STALL TIMER</div>
        <div style="font-size:13px;font-weight:700;color:{'#f87171' if g1 else '#34d399'};margin-top:3px;">
          {'🔴 SUB-20 MIN INUNDATION' if g1 else '🟢 ABOVE 20-MIN THRESHOLD'}
        </div>
      </div>
      <div class="fc-gate {'fc-gate-trip' if g2 else 'fc-gate-ok'}">
        <div style="font-size:11px;color:#94a3b8;font-weight:600;">GATE 2 • SPILLWAY SURCHARGE</div>
        <div style="font-size:13px;font-weight:700;color:{'#fbbf24' if g2 else '#34d399'};margin-top:3px;">
          {'🟡 CAPPED AT ≤95% RIVER' if g2 else '🟢 WITHIN CHANNEL CAP'}
        </div>
      </div>
      <div class="fc-gate {'fc-gate-trip' if g3 else 'fc-gate-ok'}">
        <div style="font-size:11px;color:#94a3b8;font-weight:600;">GATE 3 • DROP-ARM BARRIERS</div>
        <div style="font-size:13px;font-weight:700;color:{'#f87171' if g3 else '#34d399'};margin-top:3px;">
          {'🔴 BARRIERS LOCKED' if g3 else '🟢 PORTAL OPEN'}
        </div>
      </div>
      <div class="fc-gate {'fc-gate-trip' if g4 else 'fc-gate-ok'}">
        <div style="font-size:11px;color:#94a3b8;font-weight:600;">GATE 4 • PUMP REDUNDANCY</div>
        <div style="font-size:13px;font-weight:700;color:{'#fbbf24' if g4 else '#34d399'};margin-top:3px;">
          {f'🟡 DEGRADED ({int(telem["pump_availability_ratio"]*100)}%)' if g4 else '🟢 FULL N+1 ONLINE'}
        </div>
      </div>
    </div>
    """)

    render_html('<div class="fc-sec">🤖 Gemma 4 + BigQuery Hydrology Copilot</div>')
    qa1, qa2 = st.columns(2)
    quick_q = None
    with qa1:
        if st.button("⏱️ Explain Stall Timer", use_container_width=True):
            quick_q = "Explain the Rational Method inflow vs pump capacity and 30 cm engine-stall countdown."
        if st.button("🌊 Spillway ≤95% Cap", use_container_width=True):
            quick_q = "Why did the downstream river surcharge interlock cap or allow the spillway gate?"
    with qa2:
        if st.button("🔍 BigQuery SQL Rollup", use_container_width=True):
            quick_q = "Show the read-only Google BigQuery StandardSQL hydrology audit for this basin."
        if st.button("🛣️ High-Ground OSRM", use_container_width=True):
            quick_q = "Compare the flooded underpass route vs the verified high-ground OSRM evacuation detour."

    chat_box = st.container(height=205)
    with chat_box:
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    u_prompt = st.chat_input("Ask Gemma 4 about BigQuery flood SQL, spillway gates, or evacuation...")
    active_q = quick_q or u_prompt
    if active_q:
        st.session_state["chat_history"].append({"role": "user", "content": active_q})
        ans = answer_floodcrest_query(active_q, spec["basin_id"], advisory, telem)
        st.session_state["chat_history"].append({"role": "assistant", "content": ans})
        st.rerun()

# ---------------------------------------------------------
# 7. Interactive Google BigQuery StandardSQL Explorer & Open-Source Tables (Zero Raw JSON!)
# ---------------------------------------------------------
render_html('<div class="fc-sec" style="margin-top:14px;">📊 Google BigQuery StandardSQL Analytics &amp; Real Hydrological Corpus</div>')
tab_bq, tab_usgs, tab_dem = st.tabs([
    "🔎 Live BigQuery StandardSQL Studio (Read-Only Guardrail)",
    "🌊 USGS 15-Minute Urban Flash-Flood Gauges (1,433 Rows)",
    "⛰️ Global OSM + Copernicus 90m DEM Underpass Inventory (248 Spans)",
])

with tab_bq:
    q_choice = st.selectbox(
        "Select Verified Google BigQuery StandardSQL Analytical Query",
        options=list(BIGQUERY_PRODUCTION_SQL_CATALOG.keys()),
        format_func=lambda k: BIGQUERY_PRODUCTION_SQL_CATALOG[k]["title"],
    )
    entry = BIGQUERY_PRODUCTION_SQL_CATALOG[q_choice]
    st.code(entry["bigquery_sql"], language="sql")
    res_df = bq_warehouse.execute_readonly_sql(entry["local_sql"])
    st.dataframe(res_df, use_container_width=True, hide_index=True)

with tab_usgs:
    usgs_p = Path(__file__).resolve().parent / "dataset" / "usgs_urban_flashflood_15min_telemetry.csv"
    if usgs_p.exists():
        st.dataframe(pd.read_csv(usgs_p).head(40), use_container_width=True, hide_index=True)

with tab_dem:
    dem_p = Path(__file__).resolve().parent / "dataset" / "urban_underpass_dem_hydraulic_profiles.csv"
    if dem_p.exists():
        st.dataframe(pd.read_csv(dem_p).head(40), use_container_width=True, hide_index=True)
