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

st.markdown(f"### ⏳ Countdown: **{days_remaining} days** until Sydney Marathon 🏃‍♀️🎉")

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

# Save map to HTML
m.save("map.html")

with open("map.html", "r") as f:
    folium_map = f.read()

html(folium_map, height=350)

# Monthly trends
df["year_month"] = df["start_date_local"].dt.to_period("M").astype(str)

df_trend = df.groupby("year_month").agg({"distance_km": "sum"}).reset_index()
df_trend = df_trend.sort_values("year_month")

chart_distance = alt.Chart(df_trend).mark_bar().encode(
    x=alt.X("year_month", title="Month", sort=df_trend["year_month"].tolist()),
    y=alt.Y("distance_km", title="Total Distance (km)"),
    tooltip=["year_month", "distance_km"]
).properties(width=350, height=300)

df_pace_trend = df.groupby("year_month").agg({"pace_min_per_km": "mean"}).reset_index()
df_pace_trend = df_pace_trend.sort_values("year_month")

chart_pace = alt.Chart(df_pace_trend).mark_line(point=True).encode(
    x=alt.X("year_month", title="Month", sort=df_pace_trend["year_month"].tolist()),
    y=alt.Y("pace_min_per_km", title="Average Pace (min/km)"),
    tooltip=["year_month", "pace_min_per_km"]
).properties(width=350, height=300)

# Runs per week → Total Distance + Number of Runs
df_runs_week = (
    df.groupby("week_start")
    .agg(
        distance_km=("distance_km", "sum"),
        num_runs=("distance_km", "count")
    )
    .reset_index()
    .sort_values("week_start")
)

chart_runs_week = alt.Chart(df_runs_week).mark_bar().encode(
    x=alt.X(
        "week_start:T",
        title="Week Starting (Monday)",
        axis=alt.Axis(format="%Y-%m-%d", labelAngle=-45)
    ),
    y=alt.Y("distance_km", title="Total Distance (km)"),
    tooltip=["week_start", "distance_km", "num_runs"]
).properties(width=700, height=300)

# Cumulative distance per week
df_cum_dist_week = (
    df.groupby("week_start")
    .agg({"distance_km": "sum"})
    .reset_index()
    .sort_values("week_start")
)

df_cum_dist_week["cumulative_distance"] = df_cum_dist_week["distance_km"].cumsum()

chart_cum_dist = alt.Chart(df_cum_dist_week).mark_line(point=True).encode(
    x=alt.X(
        "week_start:T",
        title="Week Starting (Monday)",
        axis=alt.Axis(format="%Y-%m-%d", labelAngle=-45)
    ),
    y=alt.Y("cumulative_distance", title="Cumulative Distance (km)"),
    tooltip=["week_start", "cumulative_distance"]
).properties(width=700, height=300)

# Side by side charts
st.header("📊 Monthly Trends")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Distance per Month")
    st.altair_chart(chart_distance)

with col2:
    st.subheader("Pace per Month")
    st.altair_chart(chart_pace)

# Runs per week (full width)
st.header("📊 Weekly Distance")

st.altair_chart(chart_runs_week)

# Cumulative distance
st.header("📈 Cumulative Distance (per Week)")

st.altair_chart(chart_cum_dist)

# Run Table → clean, no index, rounded
st.header("📋 Run Table")

# Build display dataframe — correct columns, rounded
df_display = df[[
    "start_date_local",
    "name",
    "distance_km",
    "moving_time_min",
    "pace_min_per_km",
    "total_elevation_gain_m"
]].copy()

# Round numbers first
numeric_cols = ["distance_km", "moving_time_min", "pace_min_per_km", "total_elevation_gain_m"]
df_display[numeric_cols] = df_display[numeric_cols].round(2)
df_display[numeric_cols] = df_display[numeric_cols].applymap(lambda x: f"{x:.2f}")
# Rename columns
df_display = df_display.rename(columns={
    "start_date_local": "Start Date",
    "name": "Run Name",
    "distance_km": "Distance (km)",
    "moving_time_min": "Moving Time (min)",
    "pace_min_per_km": "Pace (min/km)",
    "total_elevation_gain_m": "Elevation Gain (m)"
})

# Display → clean table, no index
st.table(df_display.reset_index(drop=True))
