import requests
import time
import re
from typing import Optional, Dict, List, Tuple
from lxml import html
import config


class SECFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'InvestmentTracker/1.0 (your-email@example.com)',
            'Accept': 'application/json, text/html, application/xml'
        })
        self.last_request_time = 0
        self.min_request_interval = 0.5

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, url: str, params: Dict = None) -> Optional[requests.Response]:
        self._rate_limit()
        try:
            print(f"请求: {url}")
            response = self.session.get(url, params=params, timeout=60)
            print(f"状态码: {response.status_code}")
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return None

    def get_13f_filings(self, cik: str) -> List[Dict]:
        cik_padded = cik.zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        
        response = self._make_request(url)
        if not response:
            return []
        
        try:
            data = response.json()
        except Exception as e:
            print(f"JSON解析失败: {e}")
            return []
        
        filings = data.get('filings', {}).get('recent', {})
        forms = filings.get('form', [])
        dates = filings.get('filingDate', [])
        accessions = filings.get('accessionNumber', [])
        primary_docs = filings.get('primaryDocument', [])
        
        result = []
        for i, form in enumerate(forms):
            if form in ['13F-HR', '13F-HR/A']:
                result.append({
                    'form': form,
                    'date': dates[i] if i < len(dates) else None,
                    'accession_number': accessions[i] if i < len(accessions) else None,
                    'primary_document': primary_docs[i] if i < len(primary_docs) else None
                })
        
        return result

    def get_13f_holdings(self, cik: str, accession_number: str) -> Optional[str]:
        cik_padded = cik.zfill(10)
        accession_clean = accession_number.replace('-', '')
        
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession_clean}/index.json"
        
        response = self._make_request(index_url)
        if not response:
            return None
        
        try:
            index_data = response.json()
        except:
            print("无法解析index.json")
            return None
        
        directory = index_data.get('directory', {})
        items = directory.get('item', [])
        
        print(f"找到 {len(items)} 个文件")
        
        xml_files = []
        for item in items:
            name = item.get('name', '')
            if name.lower().endswith('.xml'):
                xml_files.append(name)
        
        for name in xml_files:
            name_lower = name.lower()
            if 'info' in name_lower:
                xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession_clean}/{name}"
                xml_response = self._make_request(xml_url)
                if xml_response:
                    content = xml_response.text
                    if 'infoTable' in content or 'informationTable' in content.lower():
                        print(f"找到信息表文件: {name}")
                        return content
        
        for name in xml_files:
            if 'primary' not in name.lower():
                xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession_clean}/{name}"
                xml_response = self._make_request(xml_url)
                if xml_response:
                    content = xml_response.text
                    if 'infoTable' in content or 'informationTable' in content.lower():
                        print(f"找到信息表文件: {name}")
                        return content
        
        for item in items:
            name = item.get('name', '')
            if name.lower().endswith(('.htm', '.html')):
                html_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession_clean}/{name}"
                html_response = self._make_request(html_url)
                if html_response:
                    content = html_response.text
                    if 'informationTable' in content or 'CUSIP' in content:
                        print(f"找到HTML信息表文件: {name}")
                        return self._extract_xml_from_html(content)
        
        return None

    def _extract_xml_from_html(self, html_content: str) -> Optional[str]:
        patterns = [
            r'<informationTable[^>]*>.*?</informationTable>',
            r'<INFORMATIONTABLE[^>]*>.*?</INFORMATIONTABLE>'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None

    def get_latest_13f_holdings(self, cik: str) -> Tuple[Optional[str], Optional[str]]:
        print(f"获取CIK {cik} 的13F文件列表...")
        filings = self.get_13f_filings(cik)
        
        if not filings:
            print("未找到13F文件")
            return None, None
        
        print(f"找到 {len(filings)} 个13F文件")
        
        for filing in filings:
            accession_number = filing.get('accession_number')
            filing_date = filing.get('date')
            
            if not accession_number:
                continue
            
            print(f"尝试获取 {accession_number} 的持仓数据...")
            holdings_xml = self.get_13f_holdings(cik, accession_number)
            
            if holdings_xml:
                return holdings_xml, filing_date
        
        return None, None

    def search_company(self, name: str) -> List[Dict]:
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {'q': name}
        
        response = self._make_request(url, params)
        if not response:
            return []
        
        try:
            data = response.json()
            results = []
            for item in data.get('hits', {}).get('hits', [])[:10]:
                source = item.get('_source', {})
                results.append({
                    'cik': source.get('cik'),
                    'name': source.get('entity')
                })
            return results
        except:
            return []
