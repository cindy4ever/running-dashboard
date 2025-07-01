import duckdb
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

def sync_activities(limit=None, full_sync=False):
    access_token, refresh_token, token_expires_at = refresh_strava_token()

    client = Client(access_token=access_token)
    client.refresh_token = refresh_token
    client.token_expires_at = token_expires_at
    client.token_expires = True # Force token refresh

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

    print(f"✅ Sync complete! New: {count_new}, Updated: {count_updated}")


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
            response = requests.get(url, headers=headers, params={
                "start_date": start_date,
                "end_date": end_date
            })
            response.raise_for_status()
            data = response.json().get("data", [])
            if not data:
                print(f"⚠️ No {name} data returned from Oura.")
                continue

            df = pd.DataFrame(data)
            for col in df.columns:
                if df[col].dtype == object and df[col].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}").any():
                    df[col] = pd.to_datetime(df[col], errors="ignore")

            con.execute(f"CREATE TABLE IF NOT EXISTS oura_{name} AS SELECT * FROM df LIMIT 0")
            con.execute(f"DELETE FROM oura_{name} WHERE day BETWEEN '{start_date}' AND '{end_date}'")
            con.execute(f"INSERT INTO oura_{name} SELECT * FROM df")

            print(f"✅ Ingested Oura {name} data: {len(df)} records.")
        except Exception as e:
            print(f"❌ Error fetching {name} data: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Pull full history")
    parser.add_argument("--start_date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end_date", type=str, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.full:
        print("🔁 Running full Strava sync...")
        sync_activities(limit=None, after=args.start_date, before=args.end_date)

        print("🔁 Running full Oura backfill...")
        ingest_oura_data(start_date=args.start_date, end_date=args.end_date)
    else:
        sync_activities(limit=30)
        ingest_oura_data()
