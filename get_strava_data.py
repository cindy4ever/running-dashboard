# get_strava_data.py

import duckdb
import pandas as pd
from stravalib import Client
import os
from dotenv import load_dotenv
import argparse
import pytz

# Load .env
load_dotenv()

# Strava credentials
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")

# Connect to Strava
client = Client()
client.access_token = ACCESS_TOKEN

# Connect to DuckDB
con = duckdb.connect("running.duckdb")

# Create table if not exists
con.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        activity_id BIGINT PRIMARY KEY,
        start_date_local DATE,
        name TEXT,
        distance_km DOUBLE,
        moving_time_min DOUBLE,
        pace_min_per_km DOUBLE,
        total_elevation_gain_m DOUBLE,
        summary_polyline TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

def sync_activities(limit=None):
    print(f"Running sync... limit = {limit}")

    # First pull activities as a list
    activities = list(client.get_activities(limit=limit))
    print(f"Total activities pulled: {len(activities)}")

    count_new = 0
    count_updated = 0

    for activity in activities:
        # Debug prints for ALL activities
        # print(f"Run: {activity.name}")
        # print(f"Type: {activity.type}")
        # print(f"Raw moving_time: {activity.moving_time} (type: {type(activity.moving_time)})")
        # print(f"Raw elapsed_time: {activity.elapsed_time} (type: {type(activity.elapsed_time)})")
        # print("-" * 50)

        # Only process "Run" activities
        if activity.type != "Run":
            continue

        # Safe moving_time with fallback
        try:
            moving_time_seconds = float(activity.moving_time)
            if moving_time_seconds < 1:
                raise ValueError("moving_time too small, fallback to elapsed_time")
        except Exception as e:
            print(f"Warning: Moving_time broken for {activity.name}, fallback to elapsed_time. Reason: {e}")
            moving_time_seconds = float(activity.elapsed_time)

        moving_time_min = moving_time_seconds / 60

        # Distance
        distance_km = float(activity.distance) / 1000

        # Pace
        pace_min_per_km = (
            moving_time_min / distance_km if distance_km > 0 else None
        )

        # Timezone conversion
        pacific = pytz.timezone('America/Los_Angeles')
        start_date_pacific = activity.start_date.astimezone(pacific)

        # Data dict
        data = {
            "activity_id": activity.id,
            "start_date_local": start_date_pacific.date(),
            "name": activity.name,
            "distance_km": distance_km,
            "moving_time_min": moving_time_min,
            "pace_min_per_km": pace_min_per_km,
            "total_elevation_gain_m": activity.total_elevation_gain,
            "summary_polyline": activity.map.summary_polyline if activity.map and activity.map.summary_polyline else None,
        }

        # Check if exists
        existing = con.execute("SELECT COUNT(*) FROM runs WHERE activity_id = ?", (data["activity_id"],)).fetchone()[0]

        if existing > 0:
            # Update
            con.execute("""
                UPDATE runs SET
                    start_date_local = ?,
                    name = ?,
                    distance_km = ?,
                    moving_time_min = ?,
                    pace_min_per_km = ?,
                    total_elevation_gain_m = ?,
                    summary_polyline = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE activity_id = ?
            """, (
                data["start_date_local"],
                data["name"],
                data["distance_km"],
                data["moving_time_min"],
                data["pace_min_per_km"],
                data["total_elevation_gain_m"],
                data["summary_polyline"],
                data["activity_id"]
            ))
            count_updated += 1
        else:
            # Insert
            con.execute("""
                INSERT INTO runs (
                    activity_id, start_date_local, name, distance_km,
                    moving_time_min, pace_min_per_km, total_elevation_gain_m, summary_polyline
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["activity_id"],
                data["start_date_local"],
                data["name"],
                data["distance_km"],
                data["moving_time_min"],
                data["pace_min_per_km"],
                data["total_elevation_gain_m"],
                data["summary_polyline"]
            ))
            count_new += 1

    print(f"Sync complete! New: {count_new}, Updated: {count_updated}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Pull full history")
    args = parser.parse_args()

    if args.full:
        print("Running full history sync...")
        sync_activities(limit=None)
    else:
        print("Running latest sync (100 runs)...")
        sync_activities(limit=100)
