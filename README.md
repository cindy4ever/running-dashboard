# 🏃 Road to Sydney Marathon Dashboard

A personal running dashboard powered by Streamlit, DuckDB, and Strava data.  
Track your training toward the Sydney Marathon on **August 31, 2025** with heatmaps, trends, and detailed run insights.

---

## 📦 Features

- 🔄 Sync the latest runs from Strava
- 🗺️ Interactive heatmap of all routes (Folium)
- 📊 Monthly & weekly trends for distance and pace
- 📈 Cumulative training progress
- 📋 Clean run table with eye-icon links to per-run detail pages
- 🧭 Detail pages show distance, pace, elevation, duration, and interactive maps
- ✅ Works locally and on Streamlit Cloud

---

## 🧰 Tech Stack

- [Streamlit](https://streamlit.io/)
- [DuckDB](https://duckdb.org/)
- [Folium](https://python-visualization.github.io/folium/)
- [Altair](https://altair-viz.github.io/)
- [Strava API](https://developers.strava.com/)
- [Font Awesome](https://fontawesome.com/)

---

## 🛠 Setup

1. **Clone the repo**

```bash
git clone https://github.com/your-username/running-dashboard.git
cd running-dashboard
```

2. **Create and activate a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Create a `.env` file with your Strava credentials**

```env
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
```

5. **Sync data from Strava**

```bash
python get_strava_data.py
```

6. **Launch the dashboard locally**

```bash
streamlit run app.py
```

Visit [http://localhost:8501](http://localhost:8501) in your browser.

---

## 🌐 Deployment

Deployable on [Streamlit Cloud](https://streamlit.io/cloud).  
Make sure your `running.duckdb` and `.env` values are configured securely.

---

### ▶️ Live App

👉 [View the live dashboard](https://running-dashboard-countdown-to-sydney.streamlit.app/)

---

## 📂 Project Structure

```
.
├── app.py               # Main dashboard
├── details.py           # Per-run detail view
├── get_strava_data.py   # Script to sync runs from Strava
├── running.duckdb       # DuckDB file storing all activity data
├── .env                 # Strava credentials (excluded from version control)
├── requirements.txt
└── README.md
```

---


## ✨ Credits

Built by Cindy 
Inspired by a love for running, data, and Sydney 🐨