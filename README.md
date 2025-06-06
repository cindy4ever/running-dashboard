# 🏃‍♀️ Running Dashboard — Road to Sydney Marathon 2025

This is a personal running dashboard powered by Strava API, DuckDB, and Streamlit.  
It tracks my runs and visualizes progress — towards Sydney Marathon 2025! 🏃‍♀️✨

---

## 📦 Features

✅ Pull run history from Strava API  
✅ Store in local DuckDB database  
✅ Sync new runs with one click  
✅ View heatmap of runs  
✅ View trends: pace, distance per week  
✅ Clean, simple dashboard (Streamlit)  

---

## ⚙️ Tech Stack

- Python 3.13  
- Strava API  
- DuckDB  
- Streamlit  
- Folium (for heatmap)  
- pandas, polyline  

---

## 🚀 Setup Instructions

### 1️⃣ Clone repo

```bash
git clone https://github.com/your_username/running-dashboard.git
cd running-dashboard
```

---

### 2️⃣ Create virtual env & install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### 3️⃣ Set up `.env`

```bash
cp .env.example .env
```

Fill in your Strava API credentials:

```env
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
```

---

### 4️⃣ First full sync

```bash
python get_strava_data.py --full
```

---

### 5️⃣ Run the dashboard

```bash
streamlit run app.py
```

---

## 🗂️ Project Structure

```text
├── app.py                  # Streamlit dashboard
├── get_strava_data.py      # Strava sync script
├── running.duckdb          # Local database (ignored in Git)
├── .env.example            # Example config
├── requirements.txt
├── README.md
├── .gitignore
└── map.html                # Generated at runtime (ignored in Git)
```

---

## 🚫 Git ignore

✅ `map.html` is ignored  
✅ `running.duckdb` is ignored  
✅ `.env` is ignored  

---

## 🎉 Roadmap / Future Ideas

- Auto-schedule background sync (CRON)  
- Deploy on Streamlit Cloud  
- Add run details page  
- Compare with training plan  
- Show VO2 max trend 🚴‍♀️✅  

---

## 📜 License

MIT License — for personal use 🚴‍♀️

---


Road to Sydney Marathon 2025 — 🏃‍♀️✨

---
