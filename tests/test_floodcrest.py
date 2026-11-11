"""Unit tests verifying FloodCrest AI BigQuery SQL read-only guardrails, Rational Method countdowns,
downstream surcharge spillway caps, and 100% agreement across all 80 benchmark scenarios.
"""

import csv
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from floodcrest_agent.agent import run_floodcrest_dispatch
from floodcrest_agent.bigquery_engine import get_bigquery_warehouse, validate_readonly_bigquery_sql
from floodcrest_agent.guardrails import evaluate_floodcrest_interlocks
from floodcrest_agent.tools import UNDERPASS_BASINS


def test_bigquery_readonly_guardrail_blocks_dml_and_ddl() -> None:
    assert validate_readonly_bigquery_sql("SELECT basin_id FROM dispatch_benchmark_80 LIMIT 5").startswith("SELECT")
    for bad_sql in [
        "DROP TABLE dispatch_benchmark_80;",
        "DELETE FROM usgs_flashflood_15min WHERE 1=1;",
        "UPDATE hourly_cloudburst_runoff SET precipitation_mm_hr = 0;",
        "INSERT INTO glofas_basin_daily VALUES ('x');",
    ]:
        with pytest.raises(ValueError):
            validate_readonly_bigquery_sql(bad_sql)


def test_bigquery_warehouse_executes_real_tables() -> None:
    wh = get_bigquery_warehouse()
    df = wh.execute_readonly_sql("SELECT COUNT(*) AS n FROM underpass_dem_profiles")
    assert int(df.iloc[0]["n"]) >= 240
    rollup = wh.get_basin_warehouse_rollup("FLD-001")
    assert rollup["hourly_obs"] > 50


def test_sub_20min_cloudburst_locks_drop_arm_barriers() -> None:
    advisory = run_floodcrest_dispatch(
        basin_id="FLD-001",
        cloudburst_mm_hr=115.0,
        retention_basin_fill_pct=93.0,
        downstream_river_cms=135.0,
        pump_availability_ratio=1.0,
    )
    assert advisory.dispatch_status == "EMERGENCY_LOCK_BARRIERS_EVACUATE"
    assert advisory.road_barriers_closed is True
    assert advisory.minutes_to_30cm_stall_flood <= 20.0
    assert advisory.extra_evac_km > 0.0


def test_downstream_surcharge_caps_spillway_gate() -> None:
    # Karachi FLD-003 safe channel limit = 140 m3/s; 95% ceiling = 133.0 m3/s.
    # At 134.4 m3/s river flow, available headroom is 0 -> desired 85% gate MUST clamp to 0%!
    advisory = run_floodcrest_dispatch(
        basin_id="FLD-003",
        cloudburst_mm_hr=74.0,
        retention_basin_fill_pct=89.0,
        downstream_river_cms=134.4,
        pump_availability_ratio=1.0,
    )
    assert advisory.downstream_surcharge_interlock is True
    assert advisory.approved_spillway_gate_pct == 0
    assert advisory.road_barriers_closed is True


def test_nominal_dry_weather_keeps_underpass_open() -> None:
    advisory = run_floodcrest_dispatch(
        basin_id="FLD-001",
        cloudburst_mm_hr=6.0,
        retention_basin_fill_pct=30.0,
        downstream_river_cms=55.0,
        pump_availability_ratio=1.0,
    )
    assert advisory.dispatch_status == "NOMINAL_DRAINAGE_OPEN"
    assert advisory.road_barriers_closed is False
    assert advisory.pump_duty_pct == 25


def test_all_80_benchmark_scenarios_match_100_percent() -> None:
    bench_csv = ROOT_DIR / "dataset" / "floodcrest_dispatch_benchmark_80.csv"
    assert bench_csv.exists()
    with bench_csv.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 80

    for r in rows:
        spec = UNDERPASS_BASINS[r["basin_id"]]
        p_mult = 0.50 if "50PCT" in r["pump_health_state"] else 1.0
        dec = evaluate_floodcrest_interlocks(
            basin_id=r["basin_id"],
            catchment_area_km2=spec["catchment_area_km2"],
            impervious_runoff_coeff=spec["impervious_runoff_coeff"],
            sump_storage_area_m2=spec["sump_storage_area_m2"],
            installed_pump_capacity_m3_min=spec["installed_pump_capacity_m3_min"],
            downstream_safe_channel_cms=spec["downstream_safe_channel_cms"],
            cloudburst_mm_hr=float(r["cloudburst_mm_hr"]),
            retention_basin_fill_pct=float(r["retention_basin_fill_pct"]),
            downstream_river_cms=float(r["downstream_river_cms"]),
            pump_availability_ratio=p_mult,
        )
        assert dec.dispatch_status == r["gold_dispatch_status"]
        assert dec.approved_spillway_gate_pct == int(r["approved_spillway_gate_pct"])
        assert str(dec.road_barriers_closed).lower() == str(r["road_barriers_closed"]).lower()
