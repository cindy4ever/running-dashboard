import streamlit as st
import duckdb
import pandas as pd
import polyline
import folium
from streamlit.components.v1 import html
from datetime import timedelta

from dotenv import load_dotenv
from openai import OpenAI
import os

load_dotenv()
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


# Set page config
st.set_page_config(
    page_title="Run Details",
    page_icon="🏃",
    layout="wide",
)

# Hide Streamlit sidebar completely
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
        .css-1d391kg {  /* Adjust main area width */
            margin-left: 0 !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Add Home button to return to dashboard
st.markdown(
    """
    <div style='text-align: right; margin-bottom: 10px;'>
        <a href="/" target="_self" style='text-decoration: none;'>
            <button style='padding: 6px 16px; font-size: 15px; border: none; background-color: #4CAF50; color: white; border-radius: 6px; cursor: pointer;'>
                🏠 Home
            </button>
        </a>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC&display=swap" rel="stylesheet">
<style>
  html, body, div, p, span, td {
    font-family: 'Noto Sans SC', 'Microsoft YaHei', 'PingFang SC', sans-serif !important;
  }
</style>
""", unsafe_allow_html=True)


# Connect to DuckDB
con = duckdb.connect("running.duckdb")

# Parse query parameters
params = st.query_params
run_id = params.get("run_id")

if not run_id:
    st.error("No run ID provided in the URL.")
    st.stop()

# Load the run
df = con.execute("SELECT * FROM runs WHERE activity_id = ?", (int(run_id),)).fetchdf()
if df.empty:
    st.error("Run not found.")
    st.stop()

run = df.iloc[0]

# Title
st.title(f"🏃‍♀️ {run['run_name']}")
st.markdown(f"**📅 {run['start_date_local'].strftime('%A, %B %d, %Y at %H:%M')}**")


# Summary metrics
# Summary metrics
col1, col2, col3, col4 = st.columns(4)

col1.metric("📏 Distance (km)", f"{run['distance_km']:.2f}")
pace_float = run["pace_min_per_km"]
pace_min = int(pace_float)
pace_sec = int(round((pace_float - pace_min) * 60))
col2.metric("⏱️ Pace", f"{pace_min} min {pace_sec} sec/km")
col3.metric("⛰️ Elevation (m)", f"{run['total_elevation_gain_m']:.0f}")

# Convert and show duration
duration_min = run["moving_time_min"]
total_seconds = int(duration_min * 60)
duration_str = str(timedelta(seconds=total_seconds))
col4.metric("⏳ Duration", duration_str)


# Route Map using OpenStreetMap + auto-centering
if run["summary_polyline"]:
    try:
        points = polyline.decode(run["summary_polyline"])
        m = folium.Map(
            location=[0, 0],  # Placeholder until we set bounds
            zoom_start=14,
            tiles="OpenStreetMap"
        )
        folium.PolyLine(points, color="blue", weight=4).add_to(m)

        # Auto-center based on route bounds
        m.fit_bounds([min(points), max(points)])

        html(m.get_root().render(), height=500, width=1000)
    except Exception as e:
        st.error(f"Error rendering map: {e}")
else:
    st.warning("No GPS route data available for this run.")

# Build a concise summary of the run
run_summary = {
    "name": run["run_name"],
    "distance_km": round(run["distance_km"], 2),
    "pace_min_per_km": round(run["pace_min_per_km"], 2),
    "duration_min": round(run["moving_time_min"], 1),
    "elevation_gain_m": int(run["total_elevation_gain_m"]),
    "avg_hr": int(run["average_heartrate"]) if not pd.isna(run["average_heartrate"]) else "N/A",
    "max_hr": int(run["max_heartrate"]) if not pd.isna(run["max_heartrate"]) else "N/A",
    "date": run["start_date_local"].strftime("%Y-%m-%d")
}

# Create concise instruction prompt

con.execute("""
    CREATE TABLE IF NOT EXISTS insights (
        activity_id BIGINT PRIMARY KEY,
        insight TEXT
    )
""")
cached = con.execute("SELECT insight FROM insights WHERE activity_id = ?", (int(run_id),)).fetchone()

if cached:
    st.markdown("### 🧠 AI Coach's Insight for This Run")
    st.info(cached[0])
else:
    try:
        with st.spinner("🧠 Generating AI coach's insights..."):
            prompt = (
                f"You are a marathon running coach analyzing this workout: {run_summary}. "
                "Give 3 short, actionable coaching insights in bullet points. "
                "Avoid repeating stats. Instead, explain what to adjust, improve, or learn. "
                "Assume the runner is training for Sydney marathon in Aug 31st."
                "make it concise and practical, focusing on recent progress and next steps."
                "in both English and simplified Chinese, with the English first, then Chinese."
                "Do not label the languages or add headings. Just alternate lines."
            )

            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are a concise, practical, and supportive marathon coach."},
                    {"role": "user", "content": prompt}
                ]
            )

            insight_text = response.choices[0].message.content
            formatted = insight_text.replace("•", "\n\n•").strip()

            # Save insight to DuckDB
            con.execute("INSERT INTO insights (activity_id, insight) VALUES (?, ?)", (int(run_id), formatted))

            st.markdown("### 🧠 AI Coach's Insight for This Run")
            st.info(formatted)

    except Exception as e:
        st.warning(f"⚠️ Unable to fetch insight from Groq: {e}")