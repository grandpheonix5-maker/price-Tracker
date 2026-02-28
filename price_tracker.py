from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import schedule
import time
from datetime import datetime
import re

TARGETS_FILE = "targets.json"
STATE_FILE = "state.json"

# Email Configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = 'grandpheonix5@gmail.com'
SMTP_PASSWORD = 'azmraafkqtfnaizm'
ALERT_EMAIL = 'grandpheonix5@gmail.com'
SENDER_EMAIL = 'grandpheonix5@gmail.com'

def load_json(filepath, default_value):
    if not os.path.exists(filepath):
        return default_value
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return default_value

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def parse_price(price_str):
    # Extract numeric part from string like '£51.77'
    match = re.search(r'[\d.,]+', price_str)
    if match:
        return float(match.group(0).replace(',', ''))
    return None

def send_alert(target_name, url, old_price, new_price):
    subject = f"Price Drop Alert: {target_name}"
    body = f"The price for '{target_name}' has dropped!\n\nOld Price: {old_price}\nCurrent Price: {new_price}\nLink: {url}"
    
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = ALERT_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    print(f"\n[{datetime.now().isoformat()}] ALERT TRIGGERED: {subject}")
    print(body)
    
    # Send email
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully to " + ALERT_EMAIL)
        time.sleep(3) # Prevent Google from rate-limiting multiple emails in quick succession
    except Exception as e:
        print(f"Failed to send email: {e}")

def run_scraper():
    print(f"\n--- Starting scrape run at {datetime.now().isoformat()} ---")
    targets = load_json(TARGETS_FILE, [])
    state = load_json(STATE_FILE, {})
    
    new_state = state.copy()

    for item in targets:
        url = item['url']
        name = item.get('name', 'Unknown Item')
        selector = item.get('css_selector', 'span.price')
        
        try:
            # Run in Chrome
            options = Options()
            options.add_argument("--headless=new")  # Run Chrome in headless mode (no visible window)
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            
            print(f"[{name}] Opening Chrome for URL: {url}")
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(30)
            
            try:
                driver.get(url)
                # optionally wait a bit for javascript to load
                time.sleep(2)
                
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                price_element = soup.select_one(selector)
            finally:
                driver.quit() # Ensure the browser closes
            
            
            if not price_element:
                print(f"[{name}] Could not find price element with selector: {selector}")
                continue
                
            raw_price = price_element.text.strip()
            current_price = parse_price(raw_price)
            
            if current_price is None:
                print(f"[{name}] Extracted price text could not be parsed: {raw_price}")
                continue

            print(f"[{name}] Current price: {current_price}")
            
            # Compare with previous state
            previous_price = state.get(url, {}).get('price')
            
            if previous_price is not None:
                if current_price < previous_price:
                    send_alert(name, url, previous_price, current_price)
                elif current_price > previous_price:
                    print(f"[{name}] Price increased from {previous_price} to {current_price}")
                else:
                    print(f"[{name}] Price is stable at {current_price}")
            else:
                print(f"[{name}] Initial price recorded.")
                
            new_state[url] = {
                "name": name,
                "price": current_price,
                "last_checked": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"[{name}] Error during Chrome scraping: {e}")

    # Save updated state
    save_json(STATE_FILE, new_state)
    print("--- Run complete ---")

if __name__ == "__main__":
    print("Price Tracker started. Press Ctrl+C to stop.")

    # Run once immediately on startup
    run_scraper()

    # Schedule to run every 10 minutes
    schedule.every(10).minutes.do(run_scraper)
    print("Scheduler active. Next run in 10 minutes...")

    while True:
        schedule.run_pending()
        time.sleep(1)
