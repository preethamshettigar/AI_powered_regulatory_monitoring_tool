

# AI-Powered Regulatory Monitoring Tool for Glomopay

Built to monitor RBI and IFSCA circulars, analyzes relevance using AI, and provides an interactive Streamlit dashboard.

📺 **Demo Video (Loom):** https://www.loom.com/share/d6484696265b4c488e0158507b3ba7c2

## 🚀 Quick Start (Pre-Populated Demo)

The repository includes a pre-built database (`regulatorydata.db`) with **20 analyzed circulars** (10 RBI + 10 IFSCA). No API key required for this demo.

1. **Clone the repository** or **extract the ZIP file**.
   ```bash
   git clone https://github.com/preethamshettigar/AI_powered_regulatory_monitoring_tool.git
   cd AI_powered_regulatory_monitoring_tool
   ```


2. **Create and activate a virtual environment** (recommended):
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Mac/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the dashboard**:
   ```bash
   streamlit run streamlit_app.py
   ```

5. **Explore the dashboard** – filter by source/relevance, expand AI analysis cards, mark circulars as reviewed.

> 💡 **No API key needed** – the demo runs entirely offline with the included database.

---

## 🔧 Live Fetching (Requires Groq API Key)

To fetch **new** circulars from RBI and IFSCA with AI analysis:

1. **Get a free Groq API key** at [console.groq.com](https://console.groq.com/keys).

2. **Create a `.env` file** in the project folder (use `.env.example` as template):
   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```

3. **Run the backend fetcher**:
   ```bash
   python app.py --reset
   ```
   - `--reset` clears the old database and fetches everything fresh.
   - Omit `--reset` to only add **new** circulars (duplicates are skipped).
   - Add `--skip-selenium` to temporarily skip IFSCA scraping (faster testing).

4. **Refresh the dashboard** or restart Streamlit.

## 📂 Project Structure

| File | Purpose |
| :--- | :--- |
| `app.py` | Backend: fetches RBI (RSS) & IFSCA (Selenium), calls Groq AI, stores in SQLite. |
| `streamlit_app.py` | Dashboard UI with filters, review tracking, and "Fetch & Analyze" button. |
| `requirements.txt` | Python dependencies. |
| `.env.example` | Template for Groq API key. |
| `regulatorydata.db` | Pre-populated SQLite database for instant demo. |
| `.gitignore` | Excludes secrets, virtual env, and temporary files. |

## 📦 Dependencies

- Python 3.8+
- Chrome browser (for Selenium)
- Groq API key (optional for live fetching)

See `requirements.txt` for full Python package list.

---

