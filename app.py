"""Race Roster data platform demo: the gold layer as a stakeholder would see it."""
import json
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Race Roster Lakehouse", layout="wide")
DB = "data/race_roster.duckdb"
if not Path(DB).exists():
    st.error("Run `python -m src.run_all` first."); st.stop()
con = duckdb.connect(DB, read_only=True)
q = lambda s: con.execute(s).df()
load = lambda f: json.loads(Path(f"results/{f}").read_text())

st.title("Race Roster lakehouse")
st.caption("Registrations, payments and fundraising -> dlt bronze -> dbt silver -> gold. Synthetic data, real measured results.")

tab1, tab2, tab3, tab4 = st.tabs(["Event stories", "Registration pace", "Trust: quality & reconciliation", "Cost & AI"])

with tab1:
    sc = q("select * from gold.gold_event_scorecard order by net_revenue desc")
    c = st.columns(4)
    c[0].metric("Events", len(sc)); c[1].metric("Confirmed registrations", f"{int(sc.participants.sum()):,}")
    c[2].metric("Avg fill rate", f"{sc.fill_rate_pct.mean():.1f}%"); c[3].metric("Funds raised", f"${sc.funds_raised.sum():,.0f}")
    rev = q("select revenue_month, currency, net_revenue from gold.gold_revenue_monthly order by 1")
    st.subheader("Net revenue over time")
    st.bar_chart(rev.pivot_table(index="revenue_month", columns="currency", values="net_revenue").fillna(0))
    st.subheader("Price tier performance")
    st.dataframe(q("select * from gold.gold_price_tier_performance order by distance_name, tier_name"), hide_index=True, use_container_width=True)
    st.subheader("Event scorecard")
    st.dataframe(sc, hide_index=True, use_container_width=True)

with tab2:
    races = q("select distinct race_id, event_name || ' - ' || distance_name as label from gold.gold_registration_pace order by 2")
    pick = st.selectbox("Race", races.label)
    rid = int(races[races.label == pick].race_id.iloc[0])
    pace = q(f"select days_before_race, pct_of_capacity from gold.gold_registration_pace where race_id={rid} order by days_before_race desc")
    st.line_chart(pace.set_index("days_before_race").sort_index(ascending=False))
    st.caption("% of capacity sold vs days before race day. Jumps line up with Early Bird and Regular price deadlines.")

with tab3:
    ql = load("quality.json"); rp = load("replay_check.json")
    r = ql["revenue_reconciliation"]
    c = st.columns(3)
    c[0].metric("Events reconciled to the cent", f"{r['events_matched_to_cent']} / {r['events_checked']}")
    c[1].metric("Duplicate webhooks: bronze -> silver", f"{ql['duplicate_webhooks_in_bronze']:,} -> {ql['duplicate_webhooks_in_silver']}")
    c[2].metric("Gold revenue unchanged after full replay", "Yes" if rp["replay_safe"] else "No")
    st.dataframe(pd.DataFrame(ql["dmf_metrics"]), hide_index=True, use_container_width=True)
    st.caption("Net revenue recomputed in plain Python from the raw webhook file and compared to gold. Any gap fails CI.")

with tab4:
    fo = load("finops_benchmark.json"); fc = load("forecast_eval.json")
    c = st.columns(2)
    c[0].metric("Rows scanned: raw vs gold (4 dashboard questions)", f"{fo['total_raw_rows_scanned']:,} -> {fo['total_gold_rows_scanned']:,}")
    c[1].metric("Median speedup querying gold", f"{fo['median_speedup_x']}x")
    st.dataframe(pd.DataFrame(fo["questions"]), hide_index=True, use_container_width=True)
    st.subheader("AI use case: forecast final registrations at the midpoint")
    st.dataframe(pd.DataFrame({"naive (double midpoint)": fc["naive_double_midpoint"],
                               "gradient boosting": fc["gradient_boosting"]}).T, use_container_width=True)
