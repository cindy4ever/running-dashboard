# 🏃 Road to Sydney Marathon Dashboard

A personal running dashboard powered by Streamlit, DuckDB, Strava, and Groq.  
Track your training toward the Sydney Marathon on **August 31, 2025** with heatmaps, trends, detailed run insights, and personalized AI coaching.

---

## 📦 Features

- 🔄 Sync the latest runs from Strava
- 🗺️ Interactive heatmap of all routes (Folium)
- 📊 Monthly & weekly trends for distance and pace
- 📈 Cumulative training progress
- 📋 Clean run table with one-click access to run detail pages
- 🧭 Detail pages show distance, pace, elevation, duration, and interactive maps
- 🧠 **Groq-powered AI Coach Insights**:
  - Dashboard: summarizes weekly progress + recommends next steps
  - Per-run: 3 specific bullet-point takeaways for each workout
- ✅ Works locally and on Streamlit Cloud

---

## 🧰 Tech Stack

- [Streamlit](https://streamlit.io/)
- [DuckDB](https://duckdb.org/)
- [Folium](https://python-visualization.github.io/folium/)
- [Altair](https://altair-viz.github.io/)
- [Strava API](https://developers.strava.com/)
- [Groq + OpenAI SDK](https://console.groq.com/)
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

4. **Create a `.env` file with your credentials**

```env
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
GROQ_API_KEY=your_groq_api_key
```

5. **Sync data from Strava**

```bash
python get_strava_data.py
```

6. **Launch the dashboard locally**

```bash
streamlit run app.py
```

---

## 🌐 Deployment

Deployable on [Streamlit Cloud](https://streamlit.io/cloud).  
Make sure your `.env` values and `running.duckdb` are set up in the cloud environment.

---

## 📂 Project Structure

```
.
├── app.py               # Main dashboard (overview, trends, insights)
├── pages/
│   └── details.py       # Per-run detail view with map + AI feedback
├── get_strava_data.py   # Script to sync runs from Strava
├── running.duckdb       # DuckDB file storing all activity data
├── .env                 # Strava + Groq credentials (excluded from version control)
├── requirements.txt
└── README.md
```

---

## ▶️ Live App

👉 [https://running-dashboard-countdown-to-sydney.streamlit.app](https://running-dashboard-countdown-to-sydney.streamlit.app)

---

## ✨ Credits

Built by [Your Name]  
Inspired by a love for running, data, and Sydney 🐨