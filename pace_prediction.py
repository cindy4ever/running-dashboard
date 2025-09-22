# pace_prediction_model.py

import duckdb
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# Connect to DuckDB
con = duckdb.connect("running.duckdb")

def fetch_training_data():
    query = """
        SELECT 
            r.activity_id,
            r.distance_km,
            r.pace_min_per_km,
            r.average_heartrate,
            r.total_elevation_gain_m as total_elevation_gain,
            w.temp_c,
            w.humidity_pct,
            o.score AS readiness_score
        FROM runs r
        LEFT JOIN weather_by_run w ON r.activity_id = w.activity_id
        LEFT JOIN oura_readiness o ON DATE(r.start_date_local) = DATE(o.timestamp)
        WHERE r.pace_min_per_km IS NOT NULL AND r.distance_km > 1
    """
    df = con.execute(query).df()

    # Drop rows with any missing values
    df = df.dropna()

    return df

def build_and_train_model(df):
    feature_cols = [
        "distance_km",
        "average_heartrate",
        "total_elevation_gain",
        "temp_c",
        "humidity_pct",
        "readiness_score"
    ]

    X = df[feature_cols]
    y = df["pace_min_per_km"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    r2 = model.score(X_test, y_test)
    print(f"✅ Model trained. R² score on test set: {r2:.3f}")

    return model

def predict_pace(model, distance_km, hr=None, elev=None, temp=None, humid=None, readiness=None):
    input_data = pd.DataFrame([{
        "distance_km": distance_km,
        "average_heartrate": hr or 140,
        "total_elevation_gain": elev or 50,
        "temp_c": temp or 12,
        "humidity_pct": humid or 60,
        "readiness_score": readiness or 75
    }])

    prediction = model.predict(input_data)[0]
    return round(prediction, 2)

if __name__ == "__main__":
    df = fetch_training_data()
    model = build_and_train_model(df)

    # Example: predict pace for a 21.1km half marathon
    predicted_pace = predict_pace(
        model,
        distance_km=21.1,
        hr=145,
        elev=120,
        temp=14,
        humid=70,
        readiness=78
    )

    print(f"🏃‍♀️ Predicted pace: {predicted_pace} min/km")