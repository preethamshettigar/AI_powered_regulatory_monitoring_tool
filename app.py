# app.py
"""
Regulatory Monitoring Tool for Glomopay with AI Analysis
Fetches RBI (RSS) and IFSCA (Selenium) updates, analyzes with Groq AI.

Run: python app.py [--reset] [--skip-selenium]
"""

import os
import sqlite3
import argparse
import time
import json
import re

import feedparser
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ---------------------------- CONFIGURATION ----------------------------
DB_PATH = "regulatorydata.db"
RBI_RSS_URL = "https://www.rbi.org.in/notifications_rss.xml"
IFSCA_URL = "https://ifsca.gov.in/Legal/Index/wF6kttc1JR8="
GROQ_MODEL = "llama-3.1-8b-instant"

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ---------------------------- DATABASE SETUP ----------------------------
def init_db(reset=False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if reset:
        c.execute("DROP TABLE IF EXISTS updates")
        print("🗑️  Dropped existing table.")
    c.execute('''
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            published_date TEXT,
            raw_text TEXT,
            summary TEXT,
            relevance TEXT,
            why_glomo TEXT,
            action_items TEXT,
            reviewed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def insert_update(source, title, url, published_date, raw_text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO updates (source, title, url, published_date, raw_text)
            VALUES (?, ?, ?, ?, ?)
        ''', (source, title, url, published_date, raw_text))
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def update_analysis(update_id, summary, relevance, why_glomo, action_items):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE updates 
        SET summary=?, relevance=?, why_glomo=?, action_items=?
        WHERE id=?
    ''', (summary, relevance, why_glomo, action_items, update_id))
    conn.commit()
    conn.close()

def get_db_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT source, COUNT(*) FROM updates GROUP BY source")
    stats = dict(c.fetchall())
    conn.close()
    return stats

# ---------------------------- TEXT TRUNCATION ----------------------------
def truncate_description(text, max_chars=4000):
    if not text:
        return ""
    match = re.search(r'Yours faithfully', text, re.IGNORECASE)
    if match:
        text = text[:match.start()].strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text

# ---------------------------- AI ANALYSIS ----------------------------
def analyze_with_groq(source, title, raw_text):
    prompt = f"""
“You are a senior compliance analyst at Glomopay with deep knowledge of the company's operations and regulatory obligations.


About Glomopay

How does Glomo work?
Glomo enables businesses to collect, disburse, and manage funds by providing the necessary payment infrastructure end-to-end. empower businesses to accept payments and disburse funds to their customers through various payment methods and integration options.

What businesses is Glomo suitable for?
Glomo specializes in providing customized payment solutions for a variety of business sectors, including:
1. For Financial Institutions: Services are tailored for FMEs, brokers, insurance companies, and other financial services to streamline payment operations and enhance security.
2. For Global Businesses: Support GCCs, ASPs, and education institutions with solutions that facilitate smooth cross-border payments and operational efficiency.
3. For Marketplaces: Global e-commerce site or selling digital products, Glomo offers robust payment solutions to handle transactions securely and efficiently.

Core Products : 
Outward remittances under LRS (Indians sending up to USD 250,000/year abroad for education, travel, investment)
Checkout : prebuilt checkout form on your website, app, or agent.
Payment-link : Share a secure payment link with your customers over email or SMS and start collecting payments globally. 
Subscriptions : Build, launch, and scale recurring revenue with flexible billing. Automate invoicing, payments, and recovery so you can focus on growth.
Send payouts to anyone, worldwide : Payouts to customers, affiliates, vendors, and global teams through one API.
Verify Identities for Global Businesses : Modular KYC and KYB stack for cross-border payments. Confirm user identity in seconds with ID checks, selfie verification, and AML monitoring.
Global Treasury : Receive, hold, convert, and disburse funds across 60+ currencies from a single platform. Built for businesses that operate across borders and need full control over their treasury.

Primary regulators:
IFSCA (International Financial Services Centres Authority) : (primary regulator - GIFT City)
RBI (Reserve Bank of India):(LRS, FEMA, KYC)
FATF (Financial Action Task Force): (AML/CTF standards, grey/black lists)
FEMA (Foreign Exchange Management Act, 1999)
MCA (Ministry of Corporate Affairs):
SEBI (Securities and Exchange Board of India): capital market intermediaries in the IFSC,

REGULATORY CIRCULAR TO ANALYSE : 

Analyze the following regulatory update from
Source: {source}
Title: {title}
Content: {raw_text}

ANALYSIS TASKS : 

Perform all 4 tasks below and respond ONLY 
in the JSON format specified at the end.

TASK 1 : RELEVANCE SCORING

Relevance score to Glomopay's operations.

Score HIGH if circular contains :
Keywords like LRS, outward remittances, KYC, FATF,  IFSCA, FEMA
IFSCA Payment Services Regulations
LRS limits or documentation requirements
KYC rules for PSPs or payment institutions
FATF grey/black list countries
FEMA provisions for outward remittances

Score MEDIUM if circular contains:
Updates about AML/CTF guidelines for financial institutions
RBI forex operational guidelines
IFSCA reporting requirement changes
Multi-currency permitted list updates

Score LOW if circular contains :
SEBI circulars not specific to IFSC payments
RBI circulars for domestic banks only
MCA routine compliance circulars
General GIFT City updates

Score NOT_RELEVANT if circular contains : 
Circulars about insurance, mutual funds
Domestic UPI/NEFT/RTGS guidelines
Credit card regulations
Cooperative bank guidelines



TASK 2 :  PLAIN SUMMARY
Summarise the circular in plain English
Note : 
Maximum 80 words total.
Do not copy paste from the circular subject line


TASK 3 - WHY IT MATTERS TO GLOMOPAY

ONLY complete this task if the relevance score is HIGH or MEDIUM.
If LOW or NOT_RELEVANT write "It doesn't affect Glomopay".

Write 2-3 sentences that:
Name the specific Glomopay operation might get affected,areas like Financial Institutions, Global Businesses,Marketplaces and core products

Examples: 
If it affects LRS then,
Glomopay processes outward remittances under LRS for customers sending money abroad. This circular changes X which directly affects onboarding flow/transaction limits.
If it affects KYC then,
Every customer Glomopay onboards requires KYC verification. This circular introduces new requirement which means Glomopay must collect specific data/document from all new/existing customers


STRICT RULES:
- Every sentence must be specific to Glomopay context

TASK 4  ACTION : 

One specific, actionable step for the compliance team (e.g., "Update KYC form field X by Y date" or "No action required"

if relevance is HIGH or MEDIUM then write down the action steps 
Else If LOW or NOT_RELEVANT write "No action required".


OUTPUT FORMAT : 

Output strictly as JSON with these keys:
{{"relevance": "...", "summary": "...", "why_glomo": "...", "action": "..."}}

Regulatory Update:
Title: {title}
{raw_text}

"""
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.1
        )
        content = response.choices[0].message.content
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            json_str = content[start:end+1]
            return json.loads(json_str)
        return None
    except Exception as e:
        print(f"   ⚠️ AI analysis failed: {e}")
        return None

def analyze_and_update(update_id, source, title, raw_text):
    print(f"   🔍 Analyzing: {title[:50]}...")
    result = analyze_with_groq(source, title, raw_text)
    if result:
        update_analysis(
            update_id,
            result.get('summary', ''),
            result.get('relevance', 'LOW'),
            result.get('why_glomo', ''),
            result.get('action', '')
        )
        print(f"      ✅ Relevance: {result.get('relevance', 'UNKNOWN')}")
        return True
    else:
        print(f"      ⚠️ Analysis skipped due to error.")
        return False

# ---------------------------- RBI RSS FETCHER ----------------------------
def fetch_rbi_feed():
    print("📡 Fetching RBI RSS feed...")
    feed = feedparser.parse(RBI_RSS_URL)
    new_entries = 0
    analyzed = 0

    for entry in feed.entries:
        title = entry.title
        url = entry.link
        published = entry.get('published', '')
        summary = entry.get('summary', '')
        raw_text = f"Title: {title}\nPublished: {published}\nSummary: {summary}"
        # Truncate to avoid token limits
        raw_text = truncate_description(raw_text)

        update_id = insert_update("RBI", title, url, published, raw_text)
        if update_id is None:
            continue
        new_entries += 1

        if analyze_and_update(update_id, "RBI", title, raw_text):
            analyzed += 1

    return new_entries, analyzed

# ---------------------------- IFSCA SELENIUM SCRAPER ----------------------------
def fetch_ifsca_with_selenium():
    """Scrape IFSCA circulars using Selenium and analyze with AI."""
    print("🌐 Scraping IFSCA circulars via Selenium...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    new_entries = 0
    analyzed = 0
    
    try:
        driver.get(IFSCA_URL)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table#tblLegalFront tbody tr td"))
        )
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find('table', {'id': 'tblLegalFront'})
        if not table:
            print("⚠️ Table 'tblLegalFront' not found after loading.")
            return 0, 0
        
        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 3:
                continue
            date = cols[1].get_text(strip=True)
            title = cols[2].get_text(strip=True)
            link_tag = row.find('a', href=True)
            if not link_tag:
                continue
            url = link_tag['href']
            if url.startswith('/'):
                url = f"https://ifsca.gov.in{url}"
            
            raw_text = f"Title: {title}\nPublished Date: {date}\nSource URL: {url}"
            update_id = insert_update("IFSCA", title, url, date, raw_text)
            if update_id is None:
                continue
            new_entries += 1

            if analyze_and_update(update_id, "IFSCA", title, raw_text):
                analyzed += 1

    except Exception as e:
        print(f"❌ Selenium error: {e}")
    finally:
        driver.quit()
    
    return new_entries, analyzed


# Add this function before main()
def display_all_circulars():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT id, source, title, published_date, url,
               summary, relevance, why_glomo, action_items, reviewed
        FROM updates ORDER BY created_at DESC
    ''')
    entries = c.fetchall()
    conn.close()

    if not entries:
        print("\n📭 No circulars in database.")
        return

    print("\n" + "="*80)
    print("REGULATORY CIRCULARS")
    print("="*80)

    for entry in entries:
        (id_, source, title, pub_date, url,
         summary, relevance, why_glomo, action_items, reviewed) = entry

        print(f"\nCIRCULAR TITLE: {title}")
        print(f"Source: {source} | Date: {pub_date or 'N/A'}")
        print(f"Relevance: {relevance or 'PENDING'}")
        print(f"\nPLAIN SUMMARY:")
        print(f"{summary or 'Not yet analyzed.'}")
        print(f"\nWHY IT MATTERS TO GLOMOPAY:")
        print(f"{why_glomo or 'Not yet analyzed.'}")
        print(f"\nACTION ITEMS:")
        print(f"{action_items or 'No action specified.'}")
        print(f"\n[ ] Mark as Reviewed :    [📎 Download PDF] : {url}")
        print("-" * 80)

# ---------------------------- MAIN EXECUTION ----------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reset', action='store_true', help='Drop and recreate database')
    parser.add_argument('--skip-selenium', action='store_true', help='Skip IFSCA scraping (faster for testing)')
    parser.add_argument('--no-ai', action='store_true', help='Skip AI analysis (only fetch data)')
    args = parser.parse_args()

    print("🔧 Initializing database...")
    init_db(reset=args.reset)

    stats_before = get_db_stats()
    print(f"📊 Database before fetch: {stats_before}")

    # Fetch RBI
    rbi_new, rbi_analyzed = fetch_rbi_feed() if not args.no_ai else (fetch_rbi_feed()[0], 0)
    if args.no_ai:
        print(f"   ✅ RBI: {rbi_new} new entries added (AI skipped)")

    # Fetch IFSCA
    if not args.skip_selenium:
        ifsca_new, ifsca_analyzed = fetch_ifsca_with_selenium() if not args.no_ai else (fetch_ifsca_with_selenium()[0], 0)
        if args.no_ai:
            print(f"   ✅ IFSCA: {ifsca_new} new entries added (AI skipped)")
    else:
        ifsca_new, ifsca_analyzed = 0, 0
        print("⏭️  Skipping IFSCA scraping (--skip-selenium used)")

    stats_after = get_db_stats()
    print("\n📊 Database after fetch:")
    for source, count in stats_after.items():
        print(f"   - {source}: {count} entries")

    if not args.no_ai:
        print(f"\n✅ RBI: {rbi_new} new, {rbi_analyzed} analyzed")
        if not args.skip_selenium:
            print(f"✅ IFSCA: {ifsca_new} new, {ifsca_analyzed} analyzed")
                
                
    display_all_circulars()
    print("\n🎉 Data ingestion complete.")

if __name__ == "__main__":
    main()