import streamlit as st
import duckdb
import pandas as pd
import polyline
import folium
from streamlit.components.v1 import html
from datetime import timedelta


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
col2.metric("⏱️ Pace (min/km)", f"{run['pace_min_per_km']:.2f}")
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
