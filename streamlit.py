# streamlit.py
import streamlit as st
import sqlite3
import pandas as pd
import subprocess
import sys
import os

DB_PATH = "regulatorydata.db"  # Must match the database used by app.py

def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('''
        SELECT id, source, title, published_date, summary, relevance,
               why_glomo, action_items, reviewed, url
        FROM updates
        ORDER BY created_at DESC
    ''', conn)
    conn.close()
    return df

def toggle_reviewed(update_id, reviewed):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE updates SET reviewed = ? WHERE id = ?", (1 if reviewed else 0, update_id))
    conn.commit()
    conn.close()

def run_backend():
    """Execute app.py to fetch and analyze new circulars."""
    with st.spinner("Fetching and analyzing new circulars... This may take 2-3 minutes."):
        result = subprocess.run(
            [sys.executable, "app.py"],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode != 0:
            st.error(f"Backend error:\n{result.stderr}")
        else:
            st.success("Fetch complete!")

# --- UI ---
st.set_page_config(page_title="Glomopay Compliance Monitor", layout="wide")
st.title("📋 Regulatory Intelligence Dashboard")
st.caption("AI‑powered monitoring for RBI & IFSCA circulars")

if "fetch_clicked" not in st.session_state:
    st.session_state.fetch_clicked = False

with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🔄 Fetch & Analyze New Circulars", use_container_width=True):
        st.session_state.fetch_clicked = True
    st.divider()

    df = load_data()
    if not df.empty:
        st.subheader("🔍 Filters")
        sources = st.multiselect("Source", df['source'].unique(), default=df['source'].unique())
        relevances = st.multiselect("Relevance", ["HIGH", "MEDIUM", "LOW", "NOT_RELEVANT"],
                                    default=["HIGH", "MEDIUM", "LOW", "NOT_RELEVANT"])
        show_unreviewed = st.checkbox("Show only unreviewed")
        filtered_df = df[df['source'].isin(sources) & df['relevance'].isin(relevances)]
        if show_unreviewed:
            filtered_df = filtered_df[filtered_df['reviewed'] == 0]
    else:
        filtered_df = df

if st.session_state.fetch_clicked:
    run_backend()
    st.session_state.fetch_clicked = False
    st.rerun()

if df.empty:
    st.info("No circulars in database. Click 'Fetch & Analyze' to get started.")
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Circulars", len(df))
    col2.metric("Pending Review", len(df[df['reviewed'] == 0]))
    col3.metric("HIGH Relevance", len(df[df['relevance'] == 'HIGH']))
    col4.metric("MEDIUM Relevance", len(df[df['relevance'] == 'MEDIUM']))
    st.divider()

    for _, row in filtered_df.iterrows():
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"### {row['title']}")
                st.caption(f"{row['source']} | {row['published_date']}")
            with col2:
                color = {"HIGH": "red", "MEDIUM": "orange", "LOW": "green", "NOT_RELEVANT": "grey"}.get(row['relevance'], "grey")
                st.markdown(f"**:{color}[{row['relevance']}]**")
            with col3:
                reviewed = st.checkbox("Reviewed", value=bool(row['reviewed']), key=f"rev_{row['id']}")
                if reviewed != bool(row['reviewed']):
                    toggle_reviewed(row['id'], reviewed)
                    st.rerun()
            with st.expander("🔎 AI Analysis"):
                st.markdown(f"**📝 Summary:** {row['summary']}")
                st.markdown(f"**🎯 Why it matters to Glomopay:** {row['why_glomo']}")
                st.markdown(f"**✅ Action Items:** {row['action_items']}")
                st.link_button("📎 View Source Circular", row['url'])
            st.divider()