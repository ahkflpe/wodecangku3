import sqlite3
import os
from typing import List, Dict, Optional
from datetime import datetime
import config


class Database:
    def __init__(self):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        self.conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS institutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cik TEXT UNIQUE NOT NULL,
                description TEXT,
                type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS filings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id INTEGER NOT NULL,
                filing_date DATE NOT NULL,
                accession_number TEXT,
                report_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (institution_id) REFERENCES institutions(id),
                UNIQUE(institution_id, accession_number)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id INTEGER NOT NULL,
                cusip TEXT NOT NULL,
                issuer_name TEXT,
                title_of_class TEXT,
                value REAL,
                shares REAL,
                shares_type TEXT,
                put_call TEXT,
                investment_discretion TEXT,
                other_managers TEXT,
                voting_authority_sole INTEGER,
                voting_authority_shared INTEGER,
                voting_authority_none INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (filing_id) REFERENCES filings(id)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_holdings_cusip ON holdings(cusip)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_holdings_issuer ON holdings(issuer_name)
        ''')
        
        self.conn.commit()

    def add_institution(self, name: str, cik: str, description: str = None, type: str = None) -> int:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO institutions (name, cik, description, type)
            VALUES (?, ?, ?, ?)
        ''', (name, cik, description, type))
        self.conn.commit()
        return cursor.lastrowid

    def get_institution_by_cik(self, cik: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM institutions WHERE cik = ?', (cik,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_institutions(self) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM institutions ORDER BY name')
        return [dict(row) for row in cursor.fetchall()]

    def add_filing(self, institution_id: int, filing_date: str, accession_number: str, report_date: str = None) -> int:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO filings (institution_id, filing_date, accession_number, report_date)
            VALUES (?, ?, ?, ?)
        ''', (institution_id, filing_date, accession_number, report_date))
        self.conn.commit()
        return cursor.lastrowid

    def get_filing_by_accession(self, accession_number: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM filings WHERE accession_number = ?', (accession_number,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_filings_by_institution(self, institution_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM filings 
            WHERE institution_id = ? 
            ORDER BY filing_date DESC
        ''', (institution_id,))
        return [dict(row) for row in cursor.fetchall()]

    def add_holding(self, filing_id: int, holding_data: Dict) -> int:
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO holdings (
                filing_id, cusip, issuer_name, title_of_class, value, shares,
                shares_type, put_call, investment_discretion, other_managers,
                voting_authority_sole, voting_authority_shared, voting_authority_none
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            filing_id,
            holding_data.get('cusip'),
            holding_data.get('issuer_name'),
            holding_data.get('title_of_class'),
            holding_data.get('value'),
            holding_data.get('shares'),
            holding_data.get('shares_type'),
            holding_data.get('put_call'),
            holding_data.get('investment_discretion'),
            holding_data.get('other_managers'),
            holding_data.get('voting_authority_sole'),
            holding_data.get('voting_authority_shared'),
            holding_data.get('voting_authority_none')
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_holdings_by_filing(self, filing_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM holdings WHERE filing_id = ? ORDER BY value DESC
        ''', (filing_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_holdings_by_institution(self, institution_id: int, limit: int = 1) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT h.*, f.filing_date, f.report_date
            FROM holdings h
            JOIN filings f ON h.filing_id = f.id
            WHERE f.institution_id = ?
            ORDER BY f.filing_date DESC, h.value DESC
            LIMIT ?
        ''', (institution_id, limit * 100))
        return [dict(row) for row in cursor.fetchall()]

    def get_latest_holdings(self, institution_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT h.*, f.filing_date, f.report_date
            FROM holdings h
            JOIN filings f ON h.filing_id = f.id
            WHERE f.institution_id = ?
            AND f.filing_date = (
                SELECT MAX(filing_date) FROM filings WHERE institution_id = ?
            )
            ORDER BY h.value DESC
        ''', (institution_id, institution_id))
        return [dict(row) for row in cursor.fetchall()]

    def search_holdings_by_issuer(self, issuer_name: str) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT h.*, i.name as institution_name, f.filing_date
            FROM holdings h
            JOIN filings f ON h.filing_id = f.id
            JOIN institutions i ON f.institution_id = i.id
            WHERE h.issuer_name LIKE ?
            ORDER BY f.filing_date DESC, h.value DESC
        ''', (f'%{issuer_name}%',))
        return [dict(row) for row in cursor.fetchall()]

    def get_all_issuers(self) -> List[str]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT DISTINCT issuer_name FROM holdings 
            WHERE issuer_name IS NOT NULL 
            ORDER BY issuer_name
        ''')
        return [row['issuer_name'] for row in cursor.fetchall()]

    def close(self):
        self.conn.close()
