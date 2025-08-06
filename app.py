# app.py
DISABLE_SYNC = True

import streamlit as st
import duckdb
import os
from dotenv import load_dotenv
from data_ingestion import sync_activities, ingest_oura_data

import folium
from folium.plugins import HeatMap

import pandas as pd
import numpy as np
import altair as alt
import polyline
import datetime

from openai import OpenAI
from streamlit.components.v1 import html
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from scipy.stats import zscore

# Load .env
load_dotenv()
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# Page config
st.set_page_config(page_title="Road to Sydney Marathon 🏃‍♀️", layout="wide")

# Hide sidebar and add styles
st.markdown("""
    <style>
        [data-testid="stSidebar"], [data-testid="stSidebarNav"] { display: none; }
        .css-1d391kg { margin-left: 0 !important; }
        table { border-collapse: collapse; width: 100%; table-layout: fixed; }
        th, td { text-align: center; vertical-align: middle; padding: 8px; font-size: 14px; }
        th { background-color: #f4f4f4; font-weight: 600; text-align: center !important; }
        tr:nth-child(even) { background-color: #f9f9f9; }
    </style>
""", unsafe_allow_html=True)

# Font and icons
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC&display=swap" rel="stylesheet">
<style> html, body, div, p, span, td { font-family: 'Noto Sans SC', sans-serif !important; } </style>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
""", unsafe_allow_html=True)

# Boot logic: full sync if no DB, incremental otherwise
DUCKDB_PATH = os.path.abspath("running.duckdb")
START_DATE = "2025-02-18"
TODAY = datetime.datetime.now().strftime("%Y-%m-%d")

def duckdb_exists():
    return os.path.exists(DUCKDB_PATH)

is_new_db = not duckdb_exists()




# Connect to DB
con = duckdb.connect(DUCKDB_PATH)
df = con.execute("SELECT * FROM runs ORDER BY start_date_local DESC").fetchdf()
df["start_date_local"] = pd.to_datetime(df["start_date_local"], format="%Y-%m-%d %H:%M:%S")
df = df[df["start_date_local"] >= pd.to_datetime("2020-01-01")]

# Enhanced streaming data analysis

streaming_features_df = con.execute("""
    WITH hr_changes AS (
        SELECT 
            activity_id,
            time_sec,
            heartrate,
            velocity_smooth,
            heartrate - LAG(heartrate) OVER (PARTITION BY activity_id ORDER BY time_sec) AS hr_change
        FROM run_streams
        WHERE velocity_smooth > 0 AND velocity_smooth < 20  -- Filter out unrealistic speeds
        AND heartrate > 0 AND heartrate < 250  -- Filter out unrealistic heart rates
    )
    SELECT 
        activity_id,
        -- Pace variability (coefficient of variation) - with bounds checking
        CASE
            WHEN COUNT(*) > 10 AND AVG(velocity_smooth) > 0 AND AVG(velocity_smooth) < 20 THEN 
                CASE 
                    WHEN AVG(1000 / (velocity_smooth * 60)) > 0 AND STDDEV_POP(1000 / (velocity_smooth * 60)) IS NOT NULL THEN
                        LEAST(STDDEV_POP(1000 / (velocity_smooth * 60)) / AVG(1000 / (velocity_smooth * 60)), 2.0)
                    ELSE NULL
                END
            ELSE NULL
        END AS pace_cv,
        
        -- Heart rate variability - with bounds checking
        CASE
            WHEN COUNT(heartrate) > 10 AND AVG(heartrate) BETWEEN 50 AND 220 THEN 
                CASE 
                    WHEN STDDEV_POP(heartrate) IS NOT NULL THEN
                        LEAST(STDDEV_POP(heartrate) / AVG(heartrate), 1.0)
                    ELSE NULL
                END
            ELSE NULL
        END AS hr_cv,
        
        -- Effort spikes (sudden HR increases > 15 bpm) - FIXED
        COUNT(CASE WHEN hr_change > 15 THEN 1 END) * 1.0 / NULLIF(COUNT(*), 0) AS effort_spike_rate,
        
        -- Time in high intensity (assuming max HR ~190)
        COUNT(CASE WHEN heartrate > 141 THEN 1 END) * 1.0 / NULLIF(COUNT(heartrate), 0) AS high_intensity_pct,
        
        -- Work-to-rest ratio for intervals
        CASE 
            WHEN COUNT(CASE WHEN heartrate > 141 THEN 1 END) > 0 THEN
                COUNT(CASE WHEN heartrate > 141 THEN 1 END) * 1.0 / 
                NULLIF(COUNT(CASE WHEN heartrate <= 141 AND heartrate > 0 THEN 1 END), 0)
            ELSE 0
        END AS work_rest_ratio,
        
        -- Average streaming data for validation
        AVG(velocity_smooth) AS avg_velocity_smooth,
        AVG(heartrate) AS avg_heartrate_stream
        
    FROM hr_changes
    GROUP BY activity_id
""").fetchdf()

# Merge enhanced streaming features
df = df.merge(streaming_features_df, on="activity_id", how="left")

# Calculate streaming pace
df["pace_min_per_km_stream"] = np.where(
    df["avg_velocity_smooth"] > 0,
    1000 / (df["avg_velocity_smooth"] * 60),
    np.nan
)

class ImprovedRunClassifier:
    def __init__(self):
        self.scaler = RobustScaler()
        self.model = None
        self.cluster_names = {}
        self.is_trained = False
    
    def extract_features(self, df):
        """Extract comprehensive features for better classification"""
        features = pd.DataFrame()
        features["activity_id"] = df["activity_id"] 
        
        # Basic features
        features['distance_km'] = df['distance_km']
        features['duration_min'] = df['moving_time_min']
        features['avg_pace'] = df['pace_min_per_km'].fillna(df['pace_min_per_km_stream'])
        features['elevation_gain'] = df['total_elevation_gain_m'].fillna(0)
        features['avg_hr'] = df['average_heartrate'].fillna(df['avg_heartrate_stream'])
        
        # Streaming-based features (the key to better classification)
        features['pace_variability'] = df['pace_cv'].fillna(0)
        features['hr_variability'] = df['hr_cv'].fillna(0)
        features['effort_spikes'] = df['effort_spike_rate'].fillna(0)
        features['high_intensity_time'] = df['high_intensity_pct'].fillna(0)
        features['work_rest_ratio'] = df['work_rest_ratio'].fillna(0)
        
        # Derived features
        features['pace_per_km_norm'] = features['avg_pace'] / features['avg_pace'].median()
        features['distance_duration_ratio'] = features['distance_km'] / (features['duration_min'] / 60)
        features['hr_intensity'] = np.where(
            features['avg_hr'] > 0,
            features['avg_hr'] / 185,  # Normalize to estimated max HR
            0
        )
        
        # Composite features for better separation
        features['variability_score'] = (
            features['pace_variability'] * 0.4 + 
            features['hr_variability'] * 0.3 + 
            features['effort_spikes'] * 0.3
        )
        
        features['intensity_score'] = (
            features['hr_intensity'] * 0.6 + 
            features['high_intensity_time'] * 0.4
        )
        
        # Fill remaining NaN values
        features = features.fillna(features.median())
        
        return features
    
    def find_optimal_clusters(self, features, max_k=6):
        """Find optimal number of clusters using silhouette score"""
        if len(features) < 10:
            return 5  # Increased default clusters
        
        X_scaled = self.scaler.fit_transform(features)
        
        scores = []
        K_range = range(3, min(max_k + 1, len(X_scaled) // 2))  # Start with 3 clusters minimum
        
        for k in K_range:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)
            if len(set(labels)) > 1:
                score = silhouette_score(X_scaled, labels)
                scores.append(score)
            else:
                scores.append(0)
        
        if scores:
            optimal_k = K_range[np.argmax(scores)]
            return optimal_k
        return 5
    
    def classify_runs(self, features):
        """Main classification method using rule-based approach first, then clustering"""
        if len(features) < 5:
            return ['unknown'] * len(features)
    
        run_types = ['unknown'] * len(features)
    
        for i, row in features.iterrows():
            distance = row['distance_km']
            variability = row['variability_score']
            intensity = row['intensity_score']
            work_rest = row['work_rest_ratio']
            high_intensity_pct = row['high_intensity_time']
            pace = row['avg_pace']
            activity_id = row['activity_id']
        
            skip_interval_check = distance > 6  # ✅ Hard rule: intervals must be ≤ 6km

            # 🧠 Debug
            # if activity_id in [14980216184]:  # Add more IDs if needed
            #     print(f"\n=== DEBUG: Activity {activity_id} ===")
            #     print(f"Distance: {distance}")
            #     print(f"Variability: {variability}")
            #     print(f"Intensity: {intensity}")
            #     print(f"Work/Rest: {work_rest}")
            #     print(f"High Intensity %: {high_intensity_pct}")
            #     print(f"Pace: {pace}")

            
            # ✅ Rule-based logic
            if distance >= 15:
                run_types[i] = 'long run'
            elif not skip_interval_check and variability > 0.25 and work_rest > 0.23 and high_intensity_pct > 0.18:
                run_types[i] = 'interval'
            elif not skip_interval_check and variability > 0.3 and pace < 5.5 and intensity < 0.5:
                run_types[i] = 'interval'
            elif distance <= 6 and variability < 0.2 and intensity < 0.6:
                run_types[i] = 'easy run'
            elif distance >= 5 and 5.5 <= pace <= 6.3 and variability < 0.25:
                run_types[i] = 'tempo run'
            elif 4 < distance <= 12 and variability > 0.4:
                run_types[i] = 'tempo run'
            elif distance <= 8 and intensity > 0.75:
                run_types[i] = 'speed work'
            elif distance > 6 and variability > 0.3 and intensity > 0.5:
                run_types[i] = 'tempo run'  # fallback for misclassified long intervals
            elif distance <= 6 and variability > 0.3 and intensity < 0.5:
                run_types[i] = 'interval'
            else:
                continue  # Let clustering handle unknowns

            # ✅ Optional debug output
            # if activity_id in [14980216184]:
            #     print(f"Assigned Type: {run_types[i]}")
            #     print("===============================")

        # Clustering for unknowns
        unknown_indices = [i for i, rt in enumerate(run_types) if rt == 'unknown']
        if len(unknown_indices) > 3:
            unknown_features = features.iloc[unknown_indices]
            X_scaled = self.scaler.fit_transform(unknown_features)
            n_clusters = min(4, len(unknown_features))
            self.model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = self.model.fit_predict(X_scaled)
            cluster_names = self._analyze_unknown_clusters(unknown_features, cluster_labels)

            for idx, cluster_id in enumerate(cluster_labels):
                original_idx = unknown_indices[idx]
                run_types[original_idx] = cluster_names.get(cluster_id, 'recovery run')

        run_types = ['recovery run' if rt == 'unknown' else rt for rt in run_types]
        self.is_trained = True
        return run_types

    
    def _analyze_unknown_clusters(self, features, labels):
        """Analyze clusters for unknown runs and assign names"""
        cluster_names = {}
        
        for cluster_id in np.unique(labels):
            mask = labels == cluster_id
            cluster_data = features[mask]
            
            # Calculate cluster characteristics
            avg_distance = cluster_data['distance_km'].mean()
            avg_variability = cluster_data['variability_score'].mean()
            avg_intensity = cluster_data['intensity_score'].mean()
            avg_work_rest = cluster_data['work_rest_ratio'].mean()
            
            # Assign names based on cluster characteristics
            if avg_distance >= 15:
                name = "long run"
            elif avg_distance <= 6 and avg_work_rest > 0.15 and avg_variability > 0.3:
                name = "interval"
            elif avg_intensity > 0.7:
                name = "tempo run"
            elif avg_distance < 8 and avg_variability < 0.2 and avg_intensity < 0.5:
                name = "easy run"
            else:
                name = "recovery run"

            
            cluster_names[cluster_id] = name
        
        return cluster_names

# Enhanced streaming data analysis with better bounds checking
def get_enhanced_streaming_features(con):
    """Get enhanced streaming features with better error handling"""
    try:
        streaming_features_df = con.execute("""
            WITH hr_changes AS (
                SELECT 
                    activity_id,
                    time_sec,
                    heartrate,
                    velocity_smooth,
                    heartrate - LAG(heartrate) OVER (PARTITION BY activity_id ORDER BY time_sec) AS hr_change
                FROM run_streams
                WHERE velocity_smooth > 0.5 AND velocity_smooth < 15  -- More realistic speed bounds
                AND heartrate BETWEEN 60 AND 220  -- Realistic HR bounds
            ),
            activity_stats AS (
                SELECT 
                    activity_id,
                    COUNT(*) as total_points,
                    AVG(velocity_smooth) as avg_velocity,
                    AVG(heartrate) as avg_hr,
                    STDDEV_POP(velocity_smooth) as vel_stddev,
                    STDDEV_POP(heartrate) as hr_stddev
                FROM hr_changes
                GROUP BY activity_id
                HAVING COUNT(*) > 20  -- Need sufficient data points
            )
            SELECT 
                h.activity_id,
                
                -- Pace variability (coefficient of variation)
                CASE
                    WHEN s.avg_velocity > 0 AND s.vel_stddev IS NOT NULL THEN 
                        LEAST(s.vel_stddev / s.avg_velocity, 1.5)
                    ELSE 0
                END AS pace_cv,
                
                -- Heart rate variability
                CASE
                    WHEN s.avg_hr > 0 AND s.hr_stddev IS NOT NULL THEN 
                        LEAST(s.hr_stddev / s.avg_hr, 0.8)
                    ELSE 0
                END AS hr_cv,
                
                -- Effort spikes (sudden HR increases > 10 bpm)
                COUNT(CASE WHEN h.hr_change > 10 THEN 1 END) * 1.0 / s.total_points AS effort_spike_rate,
                
                -- Time in high intensity (>80% estimated max HR)
                COUNT(CASE WHEN h.heartrate > 141 THEN 1 END) * 1.0 / s.total_points AS high_intensity_pct,
                
                -- Work-to-rest ratio for intervals
                CASE 
                    WHEN COUNT(CASE WHEN h.heartrate <= 141 AND h.heartrate > 0 THEN 1 END) > 0 THEN
                        COUNT(CASE WHEN h.heartrate > 141 THEN 1 END) * 1.0 / 
                        COUNT(CASE WHEN h.heartrate <= 141 AND h.heartrate > 0 THEN 1 END)
                    ELSE 0
                END AS work_rest_ratio,
                
                -- Average values for validation
                s.avg_velocity AS avg_velocity_smooth,
                s.avg_hr AS avg_heartrate_stream
                
            FROM hr_changes h
            JOIN activity_stats s ON h.activity_id = s.activity_id
            GROUP BY h.activity_id, s.avg_velocity, s.avg_hr, s.vel_stddev, s.hr_stddev, s.total_points
        """).fetchdf()
        
        return streaming_features_df
        
    except Exception as e:
        print(f"Error getting streaming features: {e}")
        # Return empty dataframe with expected columns
        return pd.DataFrame(columns=[
            'activity_id', 'pace_cv', 'hr_cv', 'effort_spike_rate', 
            'high_intensity_pct', 'work_rest_ratio', 'avg_velocity_smooth', 'avg_heartrate_stream'
        ])

# Usage in your main app:
# Replace the existing streaming features query with:
# streaming_features_df = get_enhanced_streaming_features(con)

# Then use the improved classifier:
classifier = ImprovedRunClassifier()

if len(df) >= 5:
    with st.spinner("🤖 Applying improved ML classification..."):
        features = classifier.extract_features(df)
        run_types = classifier.classify_runs(features)
        df['run_type'] = run_types
        
        con.execute("""
            CREATE TABLE IF NOT EXISTS run_types (
                activity_id BIGINT PRIMARY KEY,
                run_type TEXT,
                classified_at TIMESTAMP
            )
        """)

        # Insert or update classified run types
        now = datetime.datetime.utcnow().isoformat()

        for activity_id, run_type in zip(df["activity_id"], df["run_type"]):
            con.execute("""
                INSERT INTO run_types (activity_id, run_type, classified_at)
                VALUES (?, ?, ?)
                ON CONFLICT(activity_id) DO UPDATE SET 
                    run_type = excluded.run_type,
                    classified_at = excluded.classified_at
            """, (activity_id, run_type, now))

        
        # Show improved classification summary
        type_counts = pd.Series(run_types).value_counts()
        # st.success(f"✅ Classified {len(df)} runs into {len(type_counts)} types")
        
        # # Classification overview
        # with st.expander("🔍 Improved Classification Overview"):
        #     col1, col2 = st.columns(2)
        #     with col1:
        #         st.write("**Run Type Distribution:**")
        #         for run_type, count in type_counts.items():
        #             st.write(f"• {run_type.title()}: {count} runs")
            
        #     with col2:
        #         st.write("**Classification Rules Applied:**")
        #         st.write("• Distance ≥20km → Long Run")
        #         st.write("• Distance ≤4km + High Variability → Interval")
        #         st.write("• Distance ≤6km + Low Variability → Easy Run")
        #         st.write("• 4-12km + High Variability → Tempo Run")
        #         st.write("• Short Distance + High Intensity → Speed Work")
        #         st.write("• Remaining → ML Clustering")

# Add week_start
st.title("Road to Sydney Marathon 🏃‍♀️")
marathon_date = datetime.date(2025, 8, 31)
today = datetime.date.today()
days_remaining = (marathon_date - today).days
st.markdown(f"### ⏳ Countdown: **{days_remaining} days** until Sydney Marathon 🏅🎉")

st.markdown("### 🔄 Manual Sync Controls")

sync_cols = st.columns([1.5, 1.5, 1.2, 1.2])

if is_new_db:
    with sync_cols[0]:
        if st.button("🚨 Full Historical Sync"):
            with st.spinner("Performing full sync from 2025-02-18..."):
                sync_activities(limit=None, after=START_DATE, before=TODAY)
                ingest_oura_data(start_date=START_DATE, end_date=TODAY)
                st.success("✅ Full history sync complete.")
                st.experimental_rerun()
else:
    with sync_cols[0]:
        if st.button("🔁 Sync Last 30 Strava Runs + Oura"):
            with st.spinner("Syncing recent Strava and Oura data..."):
                sync_activities(limit=200)
                ingest_oura_data()
                st.success("✅ Latest data synced.")
                st.experimental_rerun()
    with sync_cols[1]:
        if st.button("🩺 Sync Oura Only"):
            with st.spinner("Syncing latest Oura data..."):
                ingest_oura_data()
                st.success("✅ Oura data synced.")
    with sync_cols[2]:
        if st.button("🏃 Sync Strava Only"):
            with st.spinner("Syncing recent Strava runs..."):
                sync_activities(limit=50)
                st.success("✅ Strava data synced.")
    with sync_cols[3]:
        if st.button("🚨 Full History Sync"):
            with st.spinner("Performing full sync from 2025-02-18..."):
                sync_activities(limit=None, full_sync=True)
                ingest_oura_data(start_date=START_DATE, end_date=TODAY)
                st.success("✅ Full history sync complete.")
                st.rerun()

# ✅ 2. Safe display of last run date
if "start_date_local" in df.columns and not df.empty:
    last_run_date = df["start_date_local"].max()
    if pd.notna(last_run_date):
        st.markdown(f"### 🕓 Last Run Recorded: `{last_run_date.strftime('%Y-%m-%d %H:%M:%S')}`")
    else:
        st.markdown("### 🕓 Last Run Recorded: `No data available`")
else:
    st.markdown("### 🕓 Last Run Recorded: `No runs found`")

# ✅ 3. Week start column (only after df is validated)
if not df.empty and "start_date_local" in df.columns:
    df["week_start"] = df["start_date_local"] - pd.to_timedelta(df["start_date_local"].dt.weekday, unit="d")
    df["week_start"] = df["week_start"].dt.date

# Heatmap
st.header("🔥 Heatmap of All Runs")

# Build folium map
m = folium.Map(
    zoom_start=12,
    tiles="OpenStreetMap",
    width="100%",
    height="100%"
)
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

# Full standalone HTML (fixes narrow map issue)
html_content = m.get_root().render()

# Responsive wrapper with CSS
map_html = f"""
<style>
    .map-wrapper {{
        position: relative;
        width: 100%;
        padding-bottom: 65%;  /* desktop aspect ratio */
        height: 0;
    }}
    .map-wrapper > div {{
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
    }}
    @media (max-width: 768px) {{
        .map-wrapper {{
            padding-bottom: 90%; /* taller for mobile */
        }}
    }}
</style>
<div class="map-wrapper">
    <div>
        {html_content}
    </div>
</div>
"""

# Render in Streamlit
st.components.v1.html(map_html, height=700, scrolling=False)

# # Enhanced Training Analysis with Run Types
# st.header("🏃‍♀️ Training Analysis by Run Type")

# if 'run_type' in df.columns and len(df) > 0:
#     # Run type distribution
#     type_summary = df.groupby('run_type').agg({
#         'distance_km': ['count', 'sum', 'mean'],
#         'moving_time_min': 'mean',
#         'pace_min_per_km': 'mean'
#     }).round(2)
    
#     type_summary.columns = ['Count', 'Total Distance (km)', 'Avg Distance (km)', 'Avg Duration (min)', 'Avg Pace (min/km)']
    
#     st.subheader("📊 Run Type Summary")
#     st.dataframe(type_summary)
    
#     # Training balance chart
#     col1, col2 = st.columns(2)
    
#     with col1:
#         st.subheader("Training Distribution")
#         type_counts = df['run_type'].value_counts()
#         chart_types = alt.Chart(pd.DataFrame({'run_type': type_counts.index, 'count': type_counts.values})).mark_arc().encode(
#             theta=alt.Theta(field="count", type="quantitative"),
#             color=alt.Color(field="run_type", type="nominal"),
#             tooltip=['run_type', 'count']
#         )
#         st.altair_chart(chart_types, use_container_width=True)
    
#     with col2:
#         st.subheader("Weekly Training Mix")
#         weekly_types = df.groupby(['week_start', 'run_type']).size().reset_index(name='count')
#         chart_weekly = alt.Chart(weekly_types).mark_bar().encode(
#             x=alt.X('week_start:T', title='Week'),
#             y=alt.Y('count:Q', title='Number of Runs'),
#             color=alt.Color('run_type:N', title='Run Type'),
#             tooltip=['week_start', 'run_type', 'count']
#         ).properties(width=400, height=300)
#         st.altair_chart(chart_weekly, use_container_width=True)

# Trends
st.header("📊 Monthly Trends")
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

col1, col2 = st.columns(2)
with col1:
    st.subheader("Distance per Month")
    st.altair_chart(chart_distance)
with col2:
    st.subheader("Pace per Month")
    st.altair_chart(chart_pace)

# Weekly totals
df_week = df.groupby("week_start").agg(
    distance_km=("distance_km", "sum"),
    num_runs=("distance_km", "count")
).reset_index().sort_values("week_start")
df_week["cumulative_distance"] = df_week["distance_km"].cumsum()

# Weekly distance chart
chart_week = alt.Chart(df_week).mark_bar().encode(
    x=alt.X("week_start:T", title="Week Starting", axis=alt.Axis(format="%Y-%m-%d", labelAngle=-45)),
    y=alt.Y("distance_km", title="Total Distance (km)"),
    tooltip=["week_start", "distance_km", "num_runs"]
).properties(width=700, height=300)

# Cumulative distance chart
chart_cumulative = alt.Chart(df_week).mark_line(point=True).encode(
    x="week_start:T",
    y="cumulative_distance",
    tooltip=["week_start", "cumulative_distance"]
).properties(width=700, height=300)

# Show headers directly above each chart
st.header("📊 Weekly Distance")
st.altair_chart(chart_week, use_container_width=True)

st.header("📈 Cumulative Distance (per Week)")
st.altair_chart(chart_cumulative, use_container_width=True)

# Enhanced Run Table with better run types
st.markdown("## 📋 Run Table")
df_display = df[[
    "start_date_local", "run_name", "distance_km", "moving_time_min",
    "pace_min_per_km", "total_elevation_gain_m", "average_heartrate", "activity_id", "run_type"
]].copy()

df_display = df_display.rename(columns={
    "start_date_local": "Start Date",
    "run_name": "Run Name",
    "distance_km": "Distance (km)",
    "moving_time_min": "Moving Time",
    "pace_min_per_km": "Pace (min/km)",
    "total_elevation_gain_m": "Elevation Gain (m)",
    "average_heartrate": "Avg HR",
    "run_type": "Run Type"
})

df_display["View"] = df_display["activity_id"].apply(
    lambda rid: f'<a href="details?run_id={rid}" target="_blank" title="View details"><i class="fas fa-eye"></i></a>'
)
df_display.drop(columns=["activity_id"], inplace=True)

# Format helpers
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
df_display["Run Type"] = df_display["Run Type"].str.title()

st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

# Enhanced AI summary with run type analysis
cutoff = pd.to_datetime(datetime.datetime.now().date() - datetime.timedelta(days=7))
recent_runs = df[df["start_date_local"] >= cutoff]

# Enhanced summary stats including run type distribution
run_type_dist = df['run_type'].value_counts().to_dict() if 'run_type' in df.columns else {}
recent_run_types = recent_runs['run_type'].value_counts().to_dict() if len(recent_runs) > 0 and 'run_type' in recent_runs.columns else {}

summary_stats = {
    "weekly_distance_km": round(recent_runs["distance_km"].sum(), 2),
    "longest_run_km": round(df["distance_km"].max(), 2),
    "average_pace_min_per_km": round(df["pace_min_per_km"].mean(), 2),
    "average_hr": round(df["average_heartrate"].mean(), 1),
    "run_count_last_7_days": len(recent_runs),
    "total_runs": len(df),
    "run_type_distribution": run_type_dist,
    "recent_run_types": recent_run_types,
    "goal": "Prepare for Sydney Marathon on August 31, 2025"
}

if recent_runs.empty:
    st.warning("🚨 No runs detected in the past 7 days. Consider syncing your latest Strava activities.")
else:
    try:
        with st.spinner("🧠 Analyzing your training with Groq..."):
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are a bilingual marathon running coach with expertise in training periodization."},
                    {"role": "user",
                     "content": (
                        f"Based on these comprehensive stats: {summary_stats}, give 3 short, specific training insights for this marathon runner. "
                        "Consider their run type distribution and training balance. "
                        "First, list the 3 bullet points in English. "
                        "Then, list the same 3 insights translated into Chinese using 简体中文. "
                        "Use modern, simple vocabulary. Do not include section headings or labels."
                    )}
                ]
            )
            insight_text = response.choices[0].message.content.strip()
            lines = [line for line in insight_text.split("\n") if not line.lower().startswith(("english", "chinese", "insight"))]
            formatted_output = "\n\n".join(lines)
            st.markdown("### 🧠 AI Coach's Insight")
            st.markdown(formatted_output)
    except Exception as e:
        st.warning(f"⚠️ Unable to fetch insight from Groq: {e}")