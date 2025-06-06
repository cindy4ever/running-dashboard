# get_strava_data.py

import duckdb
import os
import pandas as pd
from dotenv import load_dotenv
from stravalib.client import Client
import polyline
import requests
import pytz
import argparse


# Load .env
load_dotenv()

# Connect to DuckDB
con = duckdb.connect("running.duckdb")

# Create table if not exists
con.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        activity_id BIGINT PRIMARY KEY,
        start_date_local TIMESTAMP,
        name TEXT,
        distance_km DOUBLE,
        moving_time_min DOUBLE,
        pace_min_per_km DOUBLE,
        total_elevation_gain_m DOUBLE,
        summary_polyline TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# Auto-refresh Strava token
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

    print("✅ Refreshed Strava token:", tokens["access_token"])
    print("Token expires at:", tokens["expires_at"])

    return tokens["access_token"], tokens["refresh_token"], tokens["expires_at"]

# Sync activities into DuckDB
def sync_activities(limit=None):
    # Auto-refresh token
    access_token, refresh_token, token_expires_at = refresh_strava_token()

    client = Client(access_token=access_token)
    client.refresh_token = refresh_token
    client.token_expires_at = token_expires_at  # ✅ Silences the warning!

    count_new = 0
    count_updated = 0

    # Pacific timezone
    pacific = pytz.timezone("America/Los_Angeles")

    #First pull activities as a list
    activities = list(client.get_activities(limit=limit))
    print(f"Total activities pulled: {len(activities)}")

    for activity in activities:
        if activity.type != "Run":
            continue  # only keep Runs

        # Timezone conversion — safe
        pacific = pytz.timezone('America/Los_Angeles')
        start_date_pacific = activity.start_date.astimezone(pacific)

        # Safe conversions
        distance_km = round(float(activity.distance) / 1000, 2)
        moving_time_min = round(float(activity.moving_time) / 60, 2)
        pace_min_per_km = round(moving_time_min / distance_km, 2) if distance_km > 0 else None
        total_elevation_gain_m = round(activity.total_elevation_gain, 2) if activity.total_elevation_gain is not None else 0.0  

        data = {
            "activity_id": activity.id,
            "name": activity.name,
            "start_date_local": start_date_pacific,
            "distance_km": distance_km,
            "moving_time_min": moving_time_min,
            "pace_min_per_km": pace_min_per_km,
            "total_elevation_gain_m": total_elevation_gain_m,
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