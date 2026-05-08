import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'investments.db')

SEC_USER_AGENT = "InvestmentTracker/1.0 (contact@example.com)"
SEC_BASE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"

INSTITUTIONS_FILE = os.path.join(BASE_DIR, 'institutions.json')
