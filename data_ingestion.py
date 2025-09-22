import duckdb
import time
import os
import pandas as pd
from dotenv import load_dotenv
from stravalib.client import Client
import polyline
import requests
from datetime import datetime, timedelta
import argparse

# Load .env
load_dotenv()

# Connect to DuckDB
con = duckdb.connect("running.duckdb")

# Create tables if not exist
con.execute("""
CREATE TABLE IF NOT EXISTS runs (
    activity_id BIGINT PRIMARY KEY,
    start_date_local TIMESTAMP,
    run_name TEXT,
    distance_km DOUBLE,
    moving_time_min DOUBLE,
    pace_min_per_km DOUBLE,
    total_elevation_gain_m DOUBLE,
    summary_polyline TEXT,
    average_heartrate DOUBLE,
    max_heartrate DOUBLE,
    latitude DOUBLE, 
    longitude DOUBLE, 
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

con.execute("""
CREATE TABLE IF NOT EXISTS run_streams (
    activity_id BIGINT,
    stream_index INT,
    heartrate DOUBLE,
    velocity_smooth DOUBLE,
    time_sec INT,
    distance_m DOUBLE
)
""")

con.execute("""
CREATE TABLE IF NOT EXISTS weather_by_run (
    activity_id BIGINT PRIMARY KEY,
    timestamp TEXT,
    lat DOUBLE,
    lon DOUBLE,
    temp_c DOUBLE,
    humidity_pct DOUBLE
)
""")


def refresh_strava_token():
    response = requests.post(
        url="https://www.strava.com/oauth/token",
        data={
            "client_id": os.getenv("STRAVA_CLIENT_ID"),
            "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
            "grant_type": "refresh_token",
            "refresh_token": os.getenv("STRAVA_REFRESH_TOKEN"),
        }
    )
    response.raise_for_status()
    tokens = response.json()
    return tokens["access_token"], tokens["refresh_token"], tokens["expires_at"]

def get_activity_streams(client, activity_id):
    try:
        streams = client.get_activity_streams(
            activity_id,
            types=["heartrate", "velocity_smooth", "time", "distance"],
            resolution='high'
        )
        data = {}
        for stream_type in ["heartrate", "velocity_smooth", "time", "distance"]:
            data[stream_type] = streams[stream_type].data if stream_type in streams else None
        return data
    except Exception as e:
        print(f"❌ Error fetching streams for {activity_id}: {e}")
        return None
    
def fetch_weather(lat, lon, timestamp):
    date_str = timestamp.split("T")[0]
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={date_str}&end_date={date_str}"
        f"&hourly=temperature_2m,relative_humidity_2m"
        f"&timezone=auto"
    )
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        target_hour = timestamp[:13]  # e.g. '2025-09-20T07'
        for i, t in enumerate(data['hourly']['time']):
            if t.startswith(target_hour):
                return {
                    "temp_c": data['hourly']['temperature_2m'][i],
                    "humidity_pct": data['hourly']['relative_humidity_2m'][i],
                }
    except Exception as e:
        print(f"⚠️ Weather fetch failed for {timestamp} @ {lat},{lon}: {e}")
    return None

def sync_activities(limit=None, full_sync=False):
    access_token, refresh_token, token_expires_at = refresh_strava_token()

    client = Client(access_token=access_token)
    client.refresh_token = refresh_token
    client.token_expires_at = token_expires_at
    client.token_expires = True  # Force token refresh

    count_new = 0
    count_updated = 0

    activities = list(client.get_activities(limit=limit))
    print(f"Total activities pulled: {len(activities)}")

    for activity in activities:
        if activity.type != "Run":
            continue

        start_date_local = activity.start_date_local.replace(tzinfo=None)
        distance_km = round(float(activity.distance) / 1000, 2)
        moving_time_min = round(float(activity.moving_time) / 60, 2)
        pace_min_per_km = round(moving_time_min / distance_km, 2) if distance_km > 0 else None
        elevation = round(activity.total_elevation_gain or 0, 2)

        # Decode polyline for lat/lon
        if activity.map and activity.map.summary_polyline:
            try:
                first_point = polyline.decode(activity.map.summary_polyline)[0]
                lat, lon = first_point[0], first_point[1]
            except:
                lat = lon = None
        else:
            lat = lon = None

        data = {
            "activity_id": activity.id,
            "run_name": activity.name,
            "start_date_local": start_date_local,
            "distance_km": distance_km,
            "moving_time_min": moving_time_min,
            "pace_min_per_km": pace_min_per_km,
            "total_elevation_gain_m": elevation,
            "summary_polyline": activity.map.summary_polyline if activity.map else None,
            "average_heartrate": activity.average_heartrate,
            "max_heartrate": activity.max_heartrate,
            "latitude": lat,
            "longitude": lon
        }

        exists = con.execute("SELECT COUNT(*) FROM runs WHERE activity_id = ?", (data["activity_id"],)).fetchone()[0]

        if exists:
            con.execute("""
                UPDATE runs SET
                    start_date_local = ?,
                    run_name = ?,
                    distance_km = ?,
                    moving_time_min = ?,
                    pace_min_per_km = ?,
                    total_elevation_gain_m = ?,
                    summary_polyline = ?,
                    average_heartrate = ?,
                    max_heartrate = ?,
                    latitude = ?,
                    longitude = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE activity_id = ?
            """, (
                data["start_date_local"],
                data["run_name"],
                data["distance_km"],
                data["moving_time_min"],
                data["pace_min_per_km"],
                data["total_elevation_gain_m"],
                data["summary_polyline"],
                data["average_heartrate"],
                data["max_heartrate"],
                data["latitude"],
                data["longitude"],
                data["activity_id"]
            ))
            count_updated += 1
        else:
            con.execute("""
                INSERT INTO runs (
                    activity_id, start_date_local, run_name, distance_km,
                    moving_time_min, pace_min_per_km, total_elevation_gain_m,
                    summary_polyline, average_heartrate, max_heartrate,
                    latitude, longitude
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["activity_id"],
                data["start_date_local"],
                data["run_name"],
                data["distance_km"],
                data["moving_time_min"],
                data["pace_min_per_km"],
                data["total_elevation_gain_m"],
                data["summary_polyline"],
                data["average_heartrate"],
                data["max_heartrate"],
                data["latitude"],
                data["longitude"]
            ))
            count_new += 1

        # Insert stream data
        streams = get_activity_streams(client, activity.id)
        if streams and streams["time"]:
            zipped = zip(
                range(len(streams["time"])),
                streams["heartrate"] or [None] * len(streams["time"]),
                streams["velocity_smooth"] or [None] * len(streams["time"]),
                streams["time"],
                streams["distance"] or [None] * len(streams["time"])
            )
            con.execute("DELETE FROM run_streams WHERE activity_id = ?", (activity.id,))
            con.executemany("""
                INSERT INTO run_streams (
                    activity_id, stream_index, heartrate,
                    velocity_smooth, time_sec, distance_m
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, [(activity.id, i, hr, v, t, d) for i, hr, v, t, d in zipped])

        # Weather ingestion
                # Weather ingestion
        if lat is not None and lon is not None and start_date_local:
            timestamp = start_date_local.isoformat()
            existing = con.execute(
                "SELECT temp_c, humidity_pct FROM weather_by_run WHERE activity_id = ?",
                (activity.id,)
            ).fetchone()

            if not existing:
                # No weather yet — fetch and insert if available
                weather = fetch_weather(lat, lon, timestamp)
                if weather and weather["temp_c"] is not None and weather["humidity_pct"] is not None:
                    con.execute("""
                        INSERT INTO weather_by_run 
                        (activity_id, timestamp, lat, lon, temp_c, humidity_pct)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        activity.id, timestamp, lat, lon,
                        weather["temp_c"], weather["humidity_pct"]
                    ))
                    print(f"✅ Weather added for {activity.id}")
                else:
                    print(f"❌ Weather not available for {activity.id} — will retry later.")
                time.sleep(0.5)

            elif existing[0] is None or existing[1] is None:
                # Weather row exists but has nulls — retry
                weather = fetch_weather(lat, lon, timestamp)
                if weather and weather["temp_c"] is not None and weather["humidity_pct"] is not None:
                    con.execute("""
                        UPDATE weather_by_run
                        SET temp_c = ?, humidity_pct = ?
                        WHERE activity_id = ?
                    """, (weather["temp_c"], weather["humidity_pct"], activity.id))
                    print(f"🔁 Weather updated for {activity.id}")
                    time.sleep(0.5)
                else:
                    print(f"⚠️ Still no weather for {activity.id}, keeping NULLs.")
            else:
                print(f"⏭️ Weather already exists and complete for {activity.id}")
        
    print(f"✅ Sync complete! New: {count_new}, Updated: {count_updated}")


import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import duckdb

# Connect to your local DuckDB
con = duckdb.connect("running.duckdb")

def ingest_oura_data(start_date=None, end_date=None):
    token = os.getenv("OURA_API_TOKEN")
    if not token:
        print("❌ OURA_API_TOKEN not found.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.utcnow().date()
    if not start_date:
        start_date = (today - timedelta(days=7)).isoformat()
    if not end_date:
        end_date = today.isoformat()

    endpoints = {
        "readiness": "https://api.ouraring.com/v2/usercollection/daily_readiness",
        "sleep": "https://api.ouraring.com/v2/usercollection/sleep",
        "activity": "https://api.ouraring.com/v2/usercollection/daily_activity"
    }

    for name, url in endpoints.items():
        print(f"📡 Fetching Oura {name} data...")
        try:
            resp = requests.get(url, headers=headers, params={
                "start_date": start_date,
                "end_date": end_date
            })
            resp.raise_for_status()
            data = resp.json().get("data", [])
            if not data:
                print(f"⚠️ No {name} data returned.")
                continue

            df = pd.DataFrame(data)

            # Add fallback timestamp columns
            if "timestamp" not in df.columns:
                if "day" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["day"])
                elif "bedtime_start" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["bedtime_start"])

            # Normalize columns
            if name == "sleep" and "duration" in df.columns:
                df["total_sleep_duration"] = df["duration"] / 60  # seconds → minutes

            # Ensure datetime format
            for col in df.columns:
                if df[col].dtype == object and df[col].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}").any():
                    df[col] = pd.to_datetime(df[col], errors="ignore")

            # Convert large digit fields to string (DuckDB can't handle 20+ digits as int)
            for col in df.columns:
                if df[col].astype(str).str.fullmatch(r"\d{20,}").any():
                    df[col] = df[col].astype(str)

            # Store into DuckDB
            con.execute(f"DROP TABLE IF EXISTS oura_{name}")
            con.execute(f"CREATE TABLE oura_{name} AS SELECT * FROM df")

            print(f"✅ Ingested Oura {name}: {len(df)} rows")

        except Exception as e:
            print(f"❌ Error fetching {name}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Pull full history")
    parser.add_argument("--start_date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end_date", type=str, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.full:
        print("🔁 Running full Strava sync...")
        sync_activities(limit=None, full_sync=True)

        print("🔁 Running full Oura backfill...")
        ingest_oura_data(start_date=args.start_date, end_date=args.end_date)
    else:
        sync_activities(limit=30)
        ingest_oura_data()