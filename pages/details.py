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
prompt = (
    f"Here is a summary of a run: {run_summary}. "
    "Give 3 short training insights or suggestions as bullet points. Keep each under 20 words."
)

# Fetch insights from Groq
try:
    with st.spinner("🧠 Generating AI coach's insights... "):
        response = client.chat.completions.create(
            model="mistral-saba-24b",  # You can replace with another supported model
            messages=[
                {"role": "system", "content": "You are a helpful and concise running coach."},
                {"role": "user", "content": prompt}
            ]
        )
        insight_text = response.choices[0].message.content
        st.markdown("### 🧠 AI Coach's Insight for This Run")
        st.info(insight_text)
except Exception as e:
    st.warning(f"⚠️ Unable to fetch insight from Groq: {e}")