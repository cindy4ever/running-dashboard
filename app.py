# app.py

import streamlit as st
import duckdb
import os
from dotenv import load_dotenv
from get_strava_data import sync_activities

# Load .env
load_dotenv()

# Page config
st.set_page_config(page_title="Running Dashboard", layout="wide")

# Sync button
if st.button("🔄 Sync latest 100 runs from Strava"):
    sync_activities(limit=100)
    st.success("Sync complete!")

# Load runs from DuckDB
con = duckdb.connect("running.duckdb")
df = con.execute("SELECT * FROM runs ORDER BY start_date_local DESC").fetchdf()

# Show table
st.title("🏃‍♂️ My Running Dashboard")
st.dataframe(df)
