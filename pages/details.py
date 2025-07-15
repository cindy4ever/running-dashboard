import streamlit as st
import altair as alt
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

def get_streaming_data(con, run_id):
    query = f"""
        SELECT time_sec, heartrate, velocity_smooth
        FROM run_streams
        WHERE activity_id = {run_id}
        ORDER BY time_sec
    """
    df_stream = con.execute(query).fetchdf()

    df_stream["pace"] = 1000 / (df_stream["velocity_smooth"] * 60)  # Convert m/s to min/km
    df_stream = df_stream[(df_stream["pace"] < 20) & (df_stream["pace"] > 2)]  # Filter noisy data
    df_stream = df_stream[(df_stream["heartrate"] > 60) & (df_stream["heartrate"] < 220)]
    return df_stream

def plot_strava_style_chart(df_stream):
    if df_stream.empty or "velocity_smooth" not in df_stream or "heartrate" not in df_stream:
        st.warning("⚠️ No streaming pace or heart rate data found.")
        return

    df_stream = df_stream.copy()
    df_stream = df_stream.sort_values("time_sec")

    # Compute cumulative distance (km) from velocity and time
    df_stream["delta_time"] = df_stream["time_sec"].diff().fillna(0)
    df_stream["delta_dist_m"] = df_stream["velocity_smooth"] * df_stream["delta_time"]
    df_stream["distance_km"] = df_stream["delta_dist_m"].cumsum() / 1000

    # Convert velocity to pace in min/km
    df_stream["pace"] = 1000 / (df_stream["velocity_smooth"] * 60)
    df_stream = df_stream[(df_stream["pace"] > 3) & (df_stream["pace"] < 12)]  # filter outliers

    # Smooth both pace and heart rate
    df_stream["pace_smooth"] = df_stream["pace"].rolling(window=7, min_periods=1).mean()
    df_stream["hr_smooth"] = df_stream["heartrate"].rolling(window=7, min_periods=1).mean()

    # 🎽 Pace chart (top)
    pace_chart = alt.Chart(df_stream).mark_line(color="steelblue").encode(
        x=alt.X("distance_km", title="Distance (km)"),
        y=alt.Y("pace_smooth", title="Pace (min/km)", scale=alt.Scale(zero=False, reverse=True)),
        tooltip=["distance_km", "pace_smooth"]
    ).properties(height=180)

    # ❤️ Heart rate chart (bottom)
    hr_chart = alt.Chart(df_stream).mark_line(color="crimson").encode(
        x=alt.X("distance_km", title="Distance (km)"),
        y=alt.Y("hr_smooth", title="Heart Rate (bpm)", scale=alt.Scale(zero=False)),
        tooltip=["distance_km", "hr_smooth"]
    ).properties(height=180)

    # 🧱 Stack vertically
    st.altair_chart(alt.vconcat(pace_chart, hr_chart).resolve_scale(y='independent'), use_container_width=True)

    if df_stream.empty or 'velocity_smooth' not in df_stream or 'heartrate' not in df_stream:
        st.warning("No streaming data available for chart.")
        return

    # Compute derived metrics
    df_stream = df_stream.copy()
    df_stream = df_stream.sort_values("time_sec")
    df_stream["distance_km"] = (df_stream["velocity_smooth"].fillna(0) * df_stream["time_sec"]).cumsum() / 1000
    df_stream["pace"] = 1000 / (df_stream["velocity_smooth"] * 60)
    df_stream = df_stream[(df_stream["pace"] > 3) & (df_stream["pace"] < 12)]  # remove spikes

    # Optional smoothing with rolling average
    df_stream["pace_smooth"] = df_stream["pace"].rolling(window=5, min_periods=1).mean()
    df_stream["hr_smooth"] = df_stream["heartrate"].rolling(window=5, min_periods=1).mean()

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
run_type_row = con.execute("SELECT run_type FROM run_types WHERE activity_id = ?", (int(run_id),)).fetchone()
run_type = run_type_row[0] if run_type_row else "unknown"

# Title
st.title(f"🏃‍♀️ {run['run_name']}")
st.markdown(f"**🏷️ Run Type:** `{run_type}`")
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

st.subheader("📈 Streaming Pace and Heart Rate")
df_stream = get_streaming_data(con, run_id)
if not df_stream.empty:
    plot_strava_style_chart(df_stream)


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
    "run_type": run_type,
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
                f"You are a bilingual marathon running coach analyzing this workout: {run_summary}. Prepare for Sydney Marathon Aug 31 2025. "
                "Do NOT summarize the data. Instead, give 3 short coaching insights or training tips. "
                "Each should help the runner improve fitness, avoid injury, or prepare for their marathon. "
                "First, list the 3 bullet points in English. "
                "Then, repeat the exact same 3 insights in Simplified Chinese. Use 简体中文 only — do not use Vietnamese or any other language."
                "Use modern, simple vocabulary. Do NOT include any headings or labels — just clean bullet points."
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