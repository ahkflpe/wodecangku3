import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import re


class FilingParser:
    NAMESPACES = {
        'n1': 'http://www.sec.gov/edgar/document/thirteenf/informationtable',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    def parse_infotable_xml(self, xml_content: str) -> List[Dict]:
        holdings = []
        
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            print(f"XML解析错误: {e}")
            return holdings
        
        for info_table in root.iter():
            if 'infoTable' in info_table.tag or 'infotable' in info_table.tag.lower():
                holding = self._parse_info_table(info_table)
                if holding:
                    holdings.append(holding)
        
        if not holdings:
            holdings = self._parse_with_namespace(root)
        
        return holdings

    def _parse_with_namespace(self, root: ET.Element) -> List[Dict]:
        holdings = []
        
        for info_table in root.findall('.//n1:infoTable', self.NAMESPACES):
            holding = self._parse_info_table_ns(info_table)
            if holding:
                holdings.append(holding)
        
        if not holdings:
            for info_table in root.findall('.//{http://www.sec.gov/edgar/document/thirteenf/informationtable}infoTable'):
                holding = self._parse_info_table_ns(info_table)
                if holding:
                    holdings.append(holding)
        
        return holdings

    def _parse_info_table(self, info_table: ET.Element) -> Optional[Dict]:
        holding = {}
        
        for child in info_table:
            tag = self._get_local_tag(child.tag)
            text = child.text.strip() if child.text else None
            
            if tag == 'cusip':
                holding['cusip'] = text
            elif tag == 'nameOfIssuer':
                holding['issuer_name'] = text
            elif tag == 'titleOfClass':
                holding['title_of_class'] = text
            elif tag == 'value':
                holding['value'] = self._parse_float(text)
            elif tag == 'shrsPrnAmt':
                for subchild in child:
                    subtag = self._get_local_tag(subchild.tag)
                    subtext = subchild.text.strip() if subchild.text else None
                    if subtag == 'sshPrnamt':
                        holding['shares'] = self._parse_float(subtext)
                    elif subtag == 'sshPrnamtType':
                        holding['shares_type'] = subtext
            elif tag == 'putCall':
                holding['put_call'] = text
            elif tag == 'investmentDiscretion':
                holding['investment_discretion'] = text
            elif tag == 'otherManagers':
                holding['other_managers'] = text
            elif tag == 'votingAuthority':
                for subchild in child:
                    subtag = self._get_local_tag(subchild.tag)
                    subtext = subchild.text.strip() if subchild.text else None
                    if subtag == 'Sole':
                        holding['voting_authority_sole'] = self._parse_int(subtext)
                    elif subtag == 'Shared':
                        holding['voting_authority_shared'] = self._parse_int(subtext)
                    elif subtag == 'None':
                        holding['voting_authority_none'] = self._parse_int(subtext)
        
        if holding.get('cusip') and holding.get('issuer_name'):
            return holding
        return None

    def _parse_info_table_ns(self, info_table: ET.Element) -> Optional[Dict]:
        holding = {}
        
        def get_text(parent, tag):
            elem = parent.find(f'n1:{tag}', self.NAMESPACES)
            if elem is None:
                elem = parent.find(tag)
            return elem.text.strip() if elem is not None and elem.text else None
        
        holding['cusip'] = get_text(info_table, 'cusip')
        holding['issuer_name'] = get_text(info_table, 'nameOfIssuer')
        holding['title_of_class'] = get_text(info_table, 'titleOfClass')
        holding['value'] = self._parse_float(get_text(info_table, 'value'))
        
        shrs_elem = info_table.find('n1:shrsPrnAmt', self.NAMESPACES)
        if shrs_elem is None:
            shrs_elem = info_table.find('shrsPrnAmt')
        if shrs_elem is not None:
            holding['shares'] = self._parse_float(get_text(shrs_elem, 'sshPrnamt'))
            holding['shares_type'] = get_text(shrs_elem, 'sshPrnamtType')
        
        holding['put_call'] = get_text(info_table, 'putCall')
        holding['investment_discretion'] = get_text(info_table, 'investmentDiscretion')
        holding['other_managers'] = get_text(info_table, 'otherManagers')
        
        voting_elem = info_table.find('n1:votingAuthority', self.NAMESPACES)
        if voting_elem is None:
            voting_elem = info_table.find('votingAuthority')
        if voting_elem is not None:
            holding['voting_authority_sole'] = self._parse_int(get_text(voting_elem, 'Sole'))
            holding['voting_authority_shared'] = self._parse_int(get_text(voting_elem, 'Shared'))
            holding['voting_authority_none'] = self._parse_int(get_text(voting_elem, 'None'))
        
        if holding.get('cusip') and holding.get('issuer_name'):
            return holding
        return None

    def _get_local_tag(self, tag: str) -> str:
        if '}' in tag:
            return tag.split('}')[1]
        return tag

    def _parse_float(self, value: str) -> Optional[float]:
        if value:
            try:
                return float(value.replace(',', ''))
            except ValueError:
                pass
        return None

    def _parse_int(self, value: str) -> Optional[int]:
        if value:
            try:
                return int(value.replace(',', ''))
            except ValueError:
                pass
        return None

    def parse_primary_doc(self, xml_content: str) -> Dict:
        result = {}
        
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return result
        
        for elem in root.iter():
            tag = self._get_local_tag(elem.tag)
            if tag == 'reportCalendarOrQuarter':
                result['report_date'] = elem.text.strip() if elem.text else None
            elif tag == 'signatureDate':
                result['signature_date'] = elem.text.strip() if elem.text else None
        
        return result
