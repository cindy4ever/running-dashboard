# app.py

import streamlit as st
import duckdb
import os
from dotenv import load_dotenv
from get_strava_data import sync_activities

import folium
from folium.plugins import HeatMap

import pandas as pd
import altair as alt
import polyline
import datetime

from streamlit.components.v1 import html

# Load .env
load_dotenv()

# Page config
st.set_page_config(page_title="Road to Sydney Marathon 🏃‍♀️", layout="wide")

# Hide Streamlit sidebar completely
st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
        .css-1d391kg {
            margin-left: 0 !important;
        }
    </style>
""", unsafe_allow_html=True)

# Inject Font Awesome
st.markdown("""
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
""", unsafe_allow_html=True)

# Connect to DuckDB
con = duckdb.connect("running.duckdb")

# Sync button
if st.button("🔄 Sync latest 100 runs from Strava"):
    sync_activities(limit=100)
    st.success("Sync complete!")

# Load runs from DuckDB
df = con.execute("SELECT * FROM runs ORDER BY start_date_local DESC").fetchdf()

# Filter: Keep only runs from 2020 onwards
df["start_date_local"] = pd.to_datetime(df["start_date_local"], format="%Y-%m-%d %H:%M:%S")
df = df[df["start_date_local"] >= pd.to_datetime("2020-01-01")]

# Add "week_start" column → start of week (Monday)
df["week_start"] = df["start_date_local"] - pd.to_timedelta(df["start_date_local"].dt.weekday, unit="d")
df["week_start"] = df["week_start"].dt.date  # always Monday

# Page title and countdown
st.title("Road to Sydney Marathon 🏃‍♀️")

marathon_date = datetime.date(2025, 8, 31)
today = datetime.date.today()
days_remaining = (marathon_date - today).days

st.markdown(f"### ⏳ Countdown: **{days_remaining} days** until Sydney Marathon 🏅🎉")

# Folium HeatMap → embedded via components.html
st.header("🔥 Heatmap of All Runs")

m = folium.Map(zoom_start=12)
all_points = []

for index, row in df.iterrows():
    if pd.notna(row["summary_polyline"]):
        coords = polyline.decode(row["summary_polyline"])
        all_points.extend(coords)

if all_points:
    HeatMap(all_points, radius=8, blur=6, min_opacity=0.5).add_to(m)

    lats = [lat for lat, lon in all_points]
    lons = [lon for lat, lon in all_points]

    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
else:
    st.warning("No GPS data available to display heatmap.")

m.save("map.html")
with open("map.html", "r") as f:
    folium_map = f.read()
html(folium_map, height=350)

# Monthly trends
df["year_month"] = df["start_date_local"].dt.to_period("M").astype(str)

df_trend = df.groupby("year_month").agg({"distance_km": "sum"}).reset_index().sort_values("year_month")
chart_distance = alt.Chart(df_trend).mark_bar().encode(
    x=alt.X("year_month", title="Month", sort=df_trend["year_month"].tolist()),
    y=alt.Y("distance_km", title="Total Distance (km)"),
    tooltip=["year_month", "distance_km"]
).properties(width=350, height=300)

df_pace_trend = df.groupby("year_month").agg({"pace_min_per_km": "mean"}).reset_index().sort_values("year_month")
chart_pace = alt.Chart(df_pace_trend).mark_line(point=True).encode(
    x=alt.X("year_month", title="Month", sort=df_pace_trend["year_month"].tolist()),
    y=alt.Y("pace_min_per_km", title="Average Pace (min/km)"),
    tooltip=["year_month", "pace_min_per_km"]
).properties(width=350, height=300)

# Weekly runs and distance
df_runs_week = (
    df.groupby("week_start")
    .agg(distance_km=("distance_km", "sum"), num_runs=("distance_km", "count"))
    .reset_index().sort_values("week_start")
)

chart_runs_week = alt.Chart(df_runs_week).mark_bar().encode(
    x=alt.X("week_start:T", title="Week Starting (Monday)", axis=alt.Axis(format="%Y-%m-%d", labelAngle=-45)),
    y=alt.Y("distance_km", title="Total Distance (km)"),
    tooltip=["week_start", "distance_km", "num_runs"]
).properties(width=700, height=300)

# Cumulative distance
df_cum_dist_week = df_runs_week.copy()
df_cum_dist_week["cumulative_distance"] = df_cum_dist_week["distance_km"].cumsum()

chart_cum_dist = alt.Chart(df_cum_dist_week).mark_line(point=True).encode(
    x=alt.X("week_start:T", title="Week Starting (Monday)", axis=alt.Axis(format="%Y-%m-%d", labelAngle=-45)),
    y=alt.Y("cumulative_distance", title="Cumulative Distance (km)"),
    tooltip=["week_start", "cumulative_distance"]
).properties(width=700, height=300)

# Charts
st.header("📊 Monthly Trends")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Distance per Month")
    st.altair_chart(chart_distance)
with col2:
    st.subheader("Pace per Month")
    st.altair_chart(chart_pace)

st.header("📊 Weekly Distance")
st.altair_chart(chart_runs_week)

st.header("📈 Cumulative Distance (per Week)")
st.altair_chart(chart_cum_dist)

# Run Table
st.markdown("## 📋 Run Table")

df_display = df[[
    "start_date_local", "run_name", "distance_km", "moving_time_min",
    "pace_min_per_km", "total_elevation_gain_m", "average_heartrate", "max_heartrate", "activity_id"
]].copy()

df_display = df_display.rename(columns={
    "start_date_local": "Start Date",
    "run_name": "Run Name",
    "distance_km": "Distance (km)",
    "moving_time_min": "Moving Time (min)",
    "pace_min_per_km": "Pace (min/km)",
    "total_elevation_gain_m": "Elevation Gain (m)",
    "average_heartrate": "Avg HR",
    "max_heartrate": "Max HR"
})

# Add "View" column with Font Awesome eye icon (relative link)
df_display["View"] = df_display["activity_id"].apply(
    lambda rid: f'<a href="details?run_id={rid}" target="_blank" title="View details"><i class="fas fa-eye"></i></a>'
)

df_display.drop(columns=["activity_id"], inplace=True)

df_display["Max HR"] = df_display["Max HR"].round(0).astype("Int64")

st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
