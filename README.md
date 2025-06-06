# 🏃‍♂️ Running Dashboard (Strava → DuckDB → Streamlit)

A simple personal running dashboard:

✅ Pulls runs from **Strava API**  
✅ Stores data in **DuckDB**  
✅ Dashboard built with **Streamlit**  
✅ "Sync latest 100 runs" button  
✅ Full history sync supported  

---

## 🚀 Project Structure

```
/running-dashboard
├── app.py
├── get_strava_data.py
├── .env
├── requirements.txt
├── running.duckdb  # auto-created after first sync
└── README.md
```

---

## ⚙️ Setup

### 1️⃣ Create `.env`

```env
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_ACCESS_TOKEN=your_access_token
```

---

### 2️⃣ Create and activate virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🏃‍♂️ Run Full History Sync

Pull entire Strava run history into DuckDB:

```bash
python get_strava_data.py --full
```

---

## 🖥️ Run Streamlit Dashboard

```bash
streamlit run app.py
```

---

## 🔄 Sync Latest 100 Runs (via Button)

In Streamlit app:  
Click:  

```
🔄 Sync latest 100 runs from Strava
```

This will pull **latest 100 runs** and update DuckDB.

---

## 💾 DuckDB Table Schema

| Column                 | Type   |
|------------------------|--------|
| activity_id            | BIGINT (PRIMARY KEY) |
| start_date_local       | DATE   |
| name                   | TEXT   |
| distance_km            | DOUBLE |
| moving_time_min        | DOUBLE |
| pace_min_per_km        | DOUBLE |
| total_elevation_gain_m | DOUBLE |
| summary_polyline       | TEXT   |
| updated_at             | TIMESTAMP |

---

## 🌟 Next Iterations (Optional)

✅ Map rendering (Folium heatmap, PyDeck)  
✅ Trend charts (pace, distance)  
✅ Token refresh flow  
✅ Deploy to **Streamlit Cloud**  
✅ More advanced filters  

---

## Notes

- **Sync button** is safe to run multiple times — uses `activity_id` as primary key → no duplicates.
- If you sync more runs into Strava (e.g. from Apple Watch), running sync will pull them in automatically.

---

🚴‍♂️ Enjoy your personal running dashboard! 🚀✨
