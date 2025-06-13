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

from openai import OpenAI

from streamlit.components.v1 import html

# Load .env
load_dotenv()
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# Page config
st.set_page_config(page_title="Road to Sydney Marathon 🏃‍♀️", layout="wide")

# Hide Streamlit sidebar and style table
st.markdown("""
    <style>
        [data-testid="stSidebar"], [data-testid="stSidebarNav"] {
            display: none;
        }
        .css-1d391kg {
            margin-left: 0 !important;
        }

        table {
            border-collapse: collapse;
            width: 100%;
            table-layout: fixed;
        }
        th, td {
            text-align: center;
            vertical-align: middle;
            padding: 8px;
            font-size: 14px;
        }
        th {
            background-color: #f4f4f4;
            font-weight: 600;
            text-align: center !important;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
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

# Load and filter data
df = con.execute("SELECT * FROM runs ORDER BY start_date_local DESC").fetchdf()
df["start_date_local"] = pd.to_datetime(df["start_date_local"], format="%Y-%m-%d %H:%M:%S")
df = df[df["start_date_local"] >= pd.to_datetime("2020-01-01")]

# Add week_start
df["week_start"] = df["start_date_local"] - pd.to_timedelta(df["start_date_local"].dt.weekday, unit="d")
df["week_start"] = df["week_start"].dt.date

# Page title and countdown
st.title("Road to Sydney Marathon 🏃‍♀️")

marathon_date = datetime.date(2025, 8, 31)
today = datetime.date.today()
days_remaining = (marathon_date - today).days
st.markdown(f"### ⏳ Countdown: **{days_remaining} days** until Sydney Marathon 🏅🎉")

last_run_date = df["start_date_local"].max()
st.markdown(f"### 🕓 Last Synced Run: `{last_run_date.strftime('%Y-%m-%d %H:%M:%S')}`")


# Heatmap
st.header("🔥 Heatmap of All Runs")
m = folium.Map(zoom_start=12)
all_points = []

for _, row in df.iterrows():
    if pd.notna(row["summary_polyline"]):
        all_points.extend(polyline.decode(row["summary_polyline"]))

if all_points:
    HeatMap(all_points, radius=8, blur=6, min_opacity=0.5).add_to(m)
    lats, lons = zip(*all_points)
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
else:
    st.warning("No GPS data available to display heatmap.")

m.save("map.html")
with open("map.html", "r") as f:
    folium_map = f.read()
html(folium_map, height=350)

# Monthly trends
df["year_month"] = df["start_date_local"].dt.to_period("M").astype(str)
df_trend = df.groupby("year_month").agg({"distance_km": "sum"}).reset_index()
df_pace_trend = df.groupby("year_month").agg({"pace_min_per_km": "mean"}).reset_index()

chart_distance = alt.Chart(df_trend).mark_bar().encode(
    x=alt.X("year_month", title="Month"),
    y=alt.Y("distance_km", title="Total Distance (km)"),
    tooltip=["year_month", "distance_km"]
).properties(width=350, height=300)

chart_pace = alt.Chart(df_pace_trend).mark_line(point=True).encode(
    x=alt.X("year_month", title="Month"),
    y=alt.Y("pace_min_per_km", title="Average Pace (min/km)"),
    tooltip=["year_month", "pace_min_per_km"]
).properties(width=350, height=300)

# Weekly totals and cumulative
df_week = df.groupby("week_start").agg(
    distance_km=("distance_km", "sum"),
    num_runs=("distance_km", "count")
).reset_index().sort_values("week_start")

df_week["cumulative_distance"] = df_week["distance_km"].cumsum()

chart_week = alt.Chart(df_week).mark_bar().encode(
    x=alt.X("week_start:T", title="Week Starting", axis=alt.Axis(format="%Y-%m-%d", labelAngle=-45)),
    y=alt.Y("distance_km", title="Total Distance (km)"),
    tooltip=["week_start", "distance_km", "num_runs"]
).properties(width=700, height=300)

chart_cumulative = alt.Chart(df_week).mark_line(point=True).encode(
    x="week_start:T",
    y="cumulative_distance",
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
st.altair_chart(chart_week)

st.header("📈 Cumulative Distance (per Week)")
st.altair_chart(chart_cumulative)

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
    "moving_time_min": "Moving Time",
    "pace_min_per_km": "Pace (min/km)",
    "total_elevation_gain_m": "Elevation Gain (m)",
    "average_heartrate": "Avg HR",
    "max_heartrate": "Max HR"
})

df_display["View"] = df_display["activity_id"].apply(
    lambda rid: f'<a href="details?run_id={rid}" target="_blank" title="View details"><i class="fas fa-eye"></i></a>'
)
df_display.drop(columns=["activity_id"], inplace=True)
df_display["Max HR"] = df_display["Max HR"].round(0).astype("Int64")

# Format time and pace
def format_pace(p):
    if pd.isna(p): return ""
    m, s = divmod(int(p * 60), 60)
    return f"{m} min {s} sec"

def format_duration(m_float):
    if pd.isna(m_float): return ""
    total_sec = int(m_float * 60)
    h, rem = divmod(total_sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h} hr {m} min {s} sec" if h > 0 else f"{m} min {s} sec"

df_display["Pace (min/km)"] = df_display["Pace (min/km)"].apply(format_pace)
df_display["Moving Time"] = df_display["Moving Time"].apply(format_duration)

# Generate summary stats to send to Groq
summary_stats = {
    "weekly_distance_km": round(df[df["start_date_local"] >= pd.Timestamp.today() - pd.Timedelta(days=7)]["distance_km"].sum(), 2),
    "longest_run_km": round(df["distance_km"].max(), 2),
    "average_pace_min_per_km": round(df["pace_min_per_km"].mean(), 2),
    "average_hr": round(df["average_heartrate"].mean(), 1),
    "run_count_last_7_days": len(df[df["start_date_local"] >= pd.Timestamp.today() - pd.Timedelta(days=7)]),
    "goal": "Prepare for Sydney Marathon on August 31, 2025"
}

# Render
st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

# Summary stats for Groq
cutoff = pd.to_datetime(datetime.datetime.now().date() - datetime.timedelta(days=7))
recent_runs = df[df["start_date_local"] >= cutoff]
if recent_runs.empty:
    st.warning("🚨 No runs detected in the past 7 days. Consider syncing your latest Strava activities.")

summary_stats = {
    "weekly_distance_km": round(recent_runs["distance_km"].sum(), 2),
    "longest_run_km": round(df["distance_km"].max(), 2),
    "average_pace_min_per_km": round(df["pace_min_per_km"].mean(), 2),
    "average_hr": round(df["average_heartrate"].mean(), 1),
    "run_count_last_7_days": len(recent_runs),
    "goal": "Prepare for Sydney Marathon on August 31, 2025"
}

# Query Groq for AI-generated insight
try:
    with st.spinner("🧠 Analyzing your training with Groq..."):
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a friendly running coach helping a runner train for a marathon."},
                {"role": "user", "content": f"Based on these stats: {summary_stats}, give 3 short, specific training insights for this runner. Focus on recent progress and next steps."}
            ]
        )
        insight_text = response.choices[0].message.content
        st.markdown("### 🧠 AI Coach's Insight")
        st.info(insight_text)
except Exception as e:
    st.warning(f"⚠️ Unable to fetch insights from Groq: {e}")