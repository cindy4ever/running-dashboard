import os
import requests
import duckdb
import pandas as pd
from datetime import datetime, timedelta

from pace_prediction import fetch_training_data, build_and_train_model, predict_pace

con = duckdb.connect("running.duckdb")

def get_recent_runs(days=28):
    query = f"""
    SELECT r.activity_id, r.start_date_local, r.distance_km, r.pace_min_per_km,
           r.average_heartrate, w.temp_c, w.humidity_pct
    FROM runs r
    LEFT JOIN weather_by_run w ON r.activity_id = w.activity_id
    WHERE r.start_date_local >= CURRENT_DATE - INTERVAL {days} DAY
    ORDER BY r.start_date_local DESC
    """
    return con.execute(query).df()

def get_oura_sleep():
    try:
        return con.execute("SELECT * FROM oura_sleep ORDER BY day DESC LIMIT 5").df()
    except:
        return pd.DataFrame()

def get_oura_readiness():
    try:
        return con.execute("SELECT * FROM oura_readiness ORDER BY timestamp DESC LIMIT 7").df()
    except:
        return pd.DataFrame()

def summarize_runs(runs):
    summary = []
    recent = runs.head(7)
    for _, row in recent.iterrows():
        parts = [f"{row['start_date_local'].date()}: {row['distance_km']} km @ {row['pace_min_per_km']:.2f}/km"]
        if not pd.isna(row['average_heartrate']):
            parts.append(f"HR {int(row['average_heartrate'])} bpm")
        if not pd.isna(row['temp_c']) and not pd.isna(row['humidity_pct']):
            parts.append(f"{row['temp_c']}°C, {row['humidity_pct']}%")
        summary.append(" | ".join(parts))
    return summary

def summarize_oura(sleep_df, readiness_df):
    lines = []
    if not sleep_df.empty:
        lines.append("🛌 Oura Sleep (last 5 days):")
        for _, row in sleep_df.iterrows():
            day = pd.to_datetime(row["day"]).date()
            dur_hrs = int(row["total_sleep_duration"]) / 3600
            lines.append(f"- {day}: {dur_hrs:.1f} hrs sleep")

    if not readiness_df.empty:
        lines.append("\n🔋 Oura Readiness (last 7 days):")
        for _, row in readiness_df.iterrows():
            ts = pd.to_datetime(row["timestamp"]).date()
            lines.append(f"- {ts}: readiness score {row['score']}")
    return "\n".join(lines)

def get_predicted_paces_for_races():
    df = fetch_training_data()
    if df.empty:
        return "🚫 Not enough data to train prediction model."

    model = build_and_train_model(df)
    races = {
        "5K": 5.0,
        "10K": 10.0,
        "Half Marathon": 21.1,
        "Marathon": 42.2
    }

    lines = []
    for race, km in races.items():
        pace = predict_pace(model, distance_km=km)
        lines.append(f"- {race}: {pace:.2f} min/km")
    return "\n".join(lines)

def get_run_context(user_message=None):
    runs = get_recent_runs()
    sleep = get_oura_sleep()
    readiness = get_oura_readiness()

    if runs.empty:
        return "User has not logged any runs in the past 28 days."

    lines = [
        "You are an AI running coach. Use this personalized training context to answer clearly and practically.",
        "",
        "### METADATA ###",
        f"- Today’s date: {datetime.now().strftime('%B %d, %Y')}",
        "- Assistant name: CoachAI",
        "- User name: Cindy",
        "### END METADATA ###",
     "",
        "🏃‍♂️ Recent Runs (7 days):",
        *summarize_runs(runs),
        "",
        "📈 28-Day Summary:",
        f"- Longest run: {runs['distance_km'].max():.1f} km",
        f"- Fastest pace: {runs['pace_min_per_km'].min():.2f} min/km",
        f"- Avg HR: {runs['average_heartrate'].mean():.0f} bpm",
        "",
        "🌡️ Weather Summary:",
        f"- Temp range: {runs['temp_c'].min(skipna=True):.1f}–{runs['temp_c'].max(skipna=True):.1f}°C",
        f"- Humidity range: {runs['humidity_pct'].min(skipna=True):.0f}–{runs['humidity_pct'].max(skipna=True):.0f}%",
        "",
        summarize_oura(sleep, readiness),
    ]

    # Only include pace prediction if prompt is related
    if user_message and any(kw in user_message.lower() for kw in ["predict", "pace", "5k", "10k", "marathon"]):
        lines += ["", "🎯 Predicted Paces:", get_predicted_paces_for_races()]

    lines.append("\nAvoid vague advice like 'add more strength training'. Base suggestions on actual data.")

    return "\n".join(lines)

def send_to_llm(user_message, session_history, session_id=None):
    system_prompt = {
        "role": "system",
        "content": get_run_context(user_message)
    }

    messages = [system_prompt] + session_history + [{"role": "user", "content": user_message}]

    api_key = os.getenv("GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": "llama-3.3-70b-versatile",  
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"]
        print("Token usage:", resp.json().get("usage", {}))
    except Exception as e:
        reply = f"❌ LLM error: {e}"


    return reply, session_id