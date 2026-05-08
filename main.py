import sys
import json
import csv
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QComboBox, QGroupBox, QMessageBox, QProgressBar, QTabWidget,
    QHeaderView, QSplitter, QTextEdit, QStatusBar, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from sec_fetcher import SECFetcher
from database import Database
from parser import FilingParser
import config


class DataFetchWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, fetcher, parser, db, cik, institution_name):
        super().__init__()
        self.fetcher = fetcher
        self.parser = parser
        self.db = db
        self.cik = cik
        self.institution_name = institution_name
    
    def run(self):
        try:
            self.progress.emit(f"正在获取 {self.institution_name} 的13F文件...")
            
            holdings_xml, filing_date = self.fetcher.get_latest_13f_holdings(self.cik)
            
            if not holdings_xml:
                self.finished.emit(False, f"无法获取 {self.institution_name} 的持仓数据")
                return
            
            self.progress.emit("正在解析持仓数据...")
            
            holdings = self.parser.parse_infotable_xml(holdings_xml)
            
            if not holdings:
                self.finished.emit(False, f"无法解析 {self.institution_name} 的持仓数据")
                return
            
            self.progress.emit("正在保存到数据库...")
            
            institution = self.db.get_institution_by_cik(self.cik)
            if not institution:
                institution_id = self.db.add_institution(
                    name=self.institution_name,
                    cik=self.cik
                )
            else:
                institution_id = institution['id']
            
            accession_number = f"{self.cik}_{filing_date}"
            filing = self.db.get_filing_by_accession(accession_number)
            
            if filing:
                filing_id = filing['id']
            else:
                filing_id = self.db.add_filing(
                    institution_id=institution_id,
                    filing_date=filing_date,
                    accession_number=accession_number
                )
                
                for holding in holdings:
                    self.db.add_holding(filing_id, holding)
            
            self.finished.emit(True, f"成功获取 {self.institution_name} 的 {len(holdings)} 条持仓记录")
            
        except Exception as e:
            self.finished.emit(False, f"发生错误: {str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.fetcher = SECFetcher()
        self.db = Database()
        self.parser = FilingParser()
        self.worker = None
        self.current_holdings = []
        self.current_institution_name = ""
        
        self.init_ui()
        self.load_institutions()
        self.refresh_institution_list()
    
    def init_ui(self):
        self.setWindowTitle('知名投资机构持仓追踪器')
        self.setGeometry(100, 100, 1400, 900)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        toolbar_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('输入股票名称或代码搜索...')
        self.search_input.setMinimumWidth(300)
        self.search_input.returnPressed.connect(self.search_holdings)
        toolbar_layout.addWidget(self.search_input)
        
        search_btn = QPushButton('搜索')
        search_btn.clicked.connect(self.search_holdings)
        toolbar_layout.addWidget(search_btn)
        
        toolbar_layout.addStretch()
        
        export_csv_btn = QPushButton('导出CSV')
        export_csv_btn.clicked.connect(self.export_to_csv)
        toolbar_layout.addWidget(export_csv_btn)
        
        export_excel_btn = QPushButton('导出Excel')
        export_excel_btn.clicked.connect(self.export_to_excel)
        toolbar_layout.addWidget(export_excel_btn)
        
        export_all_btn = QPushButton('导出所有机构')
        export_all_btn.clicked.connect(self.export_all_institutions)
        toolbar_layout.addWidget(export_all_btn)
        
        refresh_btn = QPushButton('刷新列表')
        refresh_btn.clicked.connect(self.refresh_institution_list)
        toolbar_layout.addWidget(refresh_btn)
        
        main_layout.addLayout(toolbar_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        institution_group = QGroupBox("投资机构列表")
        institution_layout = QVBoxLayout(institution_group)
        
        self.institution_table = QTableWidget()
        self.institution_table.setColumnCount(3)
        self.institution_table.setHorizontalHeaderLabels(['机构名称', '类型', '状态'])
        self.institution_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.institution_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.institution_table.cellClicked.connect(self.on_institution_selected)
        institution_layout.addWidget(self.institution_table)
        
        btn_layout = QHBoxLayout()
        
        self.update_btn = QPushButton('更新选中机构数据')
        self.update_btn.clicked.connect(self.update_selected_institution)
        btn_layout.addWidget(self.update_btn)
        
        self.update_all_btn = QPushButton('更新所有机构数据')
        self.update_all_btn.clicked.connect(self.update_all_institutions)
        btn_layout.addWidget(self.update_all_btn)
        
        institution_layout.addLayout(btn_layout)
        
        left_layout.addWidget(institution_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel('就绪')
        left_layout.addWidget(self.status_label)
        
        splitter.addWidget(left_panel)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        tab_widget = QTabWidget()
        
        holdings_tab = QWidget()
        holdings_layout = QVBoxLayout(holdings_tab)
        
        self.holdings_table = QTableWidget()
        self.holdings_table.setColumnCount(6)
        self.holdings_table.setHorizontalHeaderLabels([
            '股票名称', '股票代码', '市值(千美元)', '股数', '类型', '投票权(独占)'
        ])
        self.holdings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.holdings_table.setSortingEnabled(True)
        holdings_layout.addWidget(self.holdings_table)
        
        self.filing_info_label = QLabel('选择一个机构查看持仓详情')
        self.filing_info_label.setFont(QFont('Arial', 10))
        holdings_layout.addWidget(self.filing_info_label)
        
        tab_widget.addTab(holdings_tab, "持仓详情")
        
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        stats_layout.addWidget(self.stats_text)
        
        tab_widget.addTab(stats_tab, "统计信息")
        
        right_layout.addWidget(tab_widget)
        
        splitter.addWidget(right_panel)
        
        splitter.setSizes([400, 1000])
        
        main_layout.addWidget(splitter)
        
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage('准备就绪')
    
    def load_institutions(self):
        try:
            with open(config.INSTITUTIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.institutions_data = data.get('institutions', [])
        except Exception as e:
            QMessageBox.warning(self, '警告', f'加载机构列表失败: {e}')
            self.institutions_data = []
    
    def refresh_institution_list(self):
        self.institution_table.setRowCount(len(self.institutions_data))
        
        for row, inst in enumerate(self.institutions_data):
            name_item = QTableWidgetItem(inst['name'])
            name_item.setData(Qt.UserRole, inst['cik'])
            self.institution_table.setItem(row, 0, name_item)
            
            type_map = {
                'company': '公司',
                'hedge_fund': '对冲基金',
                'asset_manager': '资产管理',
                'bank': '银行',
                'family_office': '家族办公室',
                'individual': '个人',
                'venture_capital': '风投',
                'sovereign_fund': '主权基金'
            }
            type_text = type_map.get(inst.get('type', ''), inst.get('type', '未知'))
            
            region = inst.get('region', '')
            region_map = {
                'china': '🇨🇳',
                'asia': '🌏',
                '': ''
            }
            region_icon = region_map.get(region, '')
            
            display_type = f"{region_icon} {type_text}".strip()
            self.institution_table.setItem(row, 1, QTableWidgetItem(display_type))
            
            db_inst = self.db.get_institution_by_cik(inst['cik'])
            if db_inst:
                filings = self.db.get_filings_by_institution(db_inst['id'])
                if filings:
                    status_item = QTableWidgetItem(f'已更新 ({filings[0]["filing_date"]})')
                    status_item.setBackground(QColor(200, 255, 200))
                else:
                    status_item = QTableWidgetItem('待更新')
                    status_item.setBackground(QColor(255, 255, 200))
            else:
                status_item = QTableWidgetItem('待更新')
                status_item.setBackground(QColor(255, 255, 200))
            
            self.institution_table.setItem(row, 2, status_item)
    
    def on_institution_selected(self, row, col):
        cik = self.institution_table.item(row, 0).data(Qt.UserRole)
        self.show_institution_holdings(cik)
    
    def show_institution_holdings(self, cik):
        institution = self.db.get_institution_by_cik(cik)
        
        if not institution:
            self.filing_info_label.setText('该机构数据尚未更新，请先更新数据')
            self.holdings_table.setRowCount(0)
            self.stats_text.clear()
            self.current_holdings = []
            self.current_institution_name = ""
            return
        
        holdings = self.db.get_latest_holdings(institution['id'])
        
        if not holdings:
            self.filing_info_label.setText('该机构暂无持仓数据')
            self.holdings_table.setRowCount(0)
            self.stats_text.clear()
            self.current_holdings = []
            self.current_institution_name = ""
            return
        
        self.current_holdings = holdings
        self.current_institution_name = institution['name']
        
        filing_date = holdings[0].get('filing_date', '未知')
        self.filing_info_label.setText(
            f'{institution["name"]} - 报告日期: {filing_date} - 共 {len(holdings)} 个持仓'
        )
        
        self.holdings_table.setRowCount(len(holdings))
        
        total_value = 0
        
        for row, holding in enumerate(holdings):
            self.holdings_table.setItem(row, 0, QTableWidgetItem(holding.get('issuer_name', '')))
            self.holdings_table.setItem(row, 1, QTableWidgetItem(holding.get('cusip', '')))
            
            value = holding.get('value', 0) or 0
            total_value += value
            value_item = QTableWidgetItem(f'{value:,.0f}')
            value_item.setData(Qt.UserRole, value)
            self.holdings_table.setItem(row, 2, value_item)
            
            shares = holding.get('shares', 0) or 0
            self.holdings_table.setItem(row, 3, QTableWidgetItem(f'{shares:,.0f}'))
            
            self.holdings_table.setItem(row, 4, QTableWidgetItem(holding.get('title_of_class', '')))
            
            sole = holding.get('voting_authority_sole', 0) or 0
            self.holdings_table.setItem(row, 5, QTableWidgetItem(f'{sole:,.0f}'))
        
        self.holdings_table.sortItems(2, Qt.DescendingOrder)
        
        stats_text = f"=== {institution['name']} 持仓统计 ===\n\n"
        stats_text += f"报告日期: {filing_date}\n"
        stats_text += f"持仓数量: {len(holdings)}\n"
        stats_text += f"总市值: ${total_value:,.0f} 千美元\n\n"
        
        stats_text += "=== 前10大持仓 ===\n"
        for i, holding in enumerate(holdings[:10], 1):
            value = holding.get('value', 0) or 0
            pct = (value / total_value * 100) if total_value > 0 else 0
            stats_text += f"{i}. {holding.get('issuer_name', '')} - ${value:,.0f}K ({pct:.1f}%)\n"
        
        self.stats_text.setText(stats_text)
    
    def update_selected_institution(self):
        selected_rows = self.institution_table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, '提示', '请先选择一个机构')
            return
        
        row = selected_rows[0].row()
        cik = self.institution_table.item(row, 0).data(Qt.UserRole)
        name = self.institution_table.item(row, 0).text()
        
        self.start_fetch(cik, name)
    
    def update_all_institutions(self):
        reply = QMessageBox.question(
            self, '确认', 
            f'确定要更新所有 {len(self.institutions_data)} 个机构的数据吗？这可能需要较长时间。',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.update_index = 0
            self.update_next_institution()
    
    def update_next_institution(self):
        if self.update_index >= len(self.institutions_data):
            self.status_label.setText('所有机构更新完成')
            self.refresh_institution_list()
            return
        
        inst = self.institutions_data[self.update_index]
        self.status_label.setText(f'正在更新 {self.update_index + 1}/{len(self.institutions_data)}: {inst["name"]}')
        self.start_fetch(inst['cik'], inst['name'], auto_next=True)
    
    def start_fetch(self, cik, name, auto_next=False):
        self.auto_next = auto_next
        self.update_btn.setEnabled(False)
        self.update_all_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        
        self.worker = DataFetchWorker(self.fetcher, self.parser, self.db, cik, name)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_fetch_finished)
        self.worker.start()
    
    def on_progress(self, message):
        self.status_label.setText(message)
    
    def on_fetch_finished(self, success, message):
        self.progress_bar.setVisible(False)
        self.update_btn.setEnabled(True)
        self.update_all_btn.setEnabled(True)
        
        if success:
            self.statusBar().showMessage(message)
            self.refresh_institution_list()
        else:
            QMessageBox.warning(self, '错误', message)
        
        if hasattr(self, 'auto_next') and self.auto_next:
            self.update_index += 1
            self.update_next_institution()
    
    def search_holdings(self):
        keyword = self.search_input.text().strip()
        if not keyword:
            return
        
        results = self.db.search_holdings_by_issuer(keyword)
        
        if not results:
            QMessageBox.information(self, '提示', f'未找到包含 "{keyword}" 的持仓')
            return
        
        self.current_holdings = results
        self.current_institution_name = f"搜索结果: {keyword}"
        
        self.holdings_table.setRowCount(len(results))
        
        for row, holding in enumerate(results):
            self.holdings_table.setItem(row, 0, QTableWidgetItem(holding.get('issuer_name', '')))
            self.holdings_table.setItem(row, 1, QTableWidgetItem(holding.get('cusip', '')))
            
            value = holding.get('value', 0) or 0
            value_item = QTableWidgetItem(f'{value:,.0f}')
            value_item.setData(Qt.UserRole, value)
            self.holdings_table.setItem(row, 2, value_item)
            
            shares = holding.get('shares', 0) or 0
            self.holdings_table.setItem(row, 3, QTableWidgetItem(f'{shares:,.0f}'))
            
            self.holdings_table.setItem(row, 4, QTableWidgetItem(holding.get('title_of_class', '')))
            
            sole = holding.get('voting_authority_sole', 0) or 0
            self.holdings_table.setItem(row, 5, QTableWidgetItem(f'{sole:,.0f}'))
        
        self.filing_info_label.setText(f'搜索结果: 找到 {len(results)} 条包含 "{keyword}" 的持仓')
    
    def export_to_csv(self):
        if not self.current_holdings:
            QMessageBox.warning(self, '提示', '没有可导出的数据，请先选择一个机构')
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, '保存CSV文件',
            f'{self.current_institution_name}_{datetime.now().strftime("%Y%m%d")}.csv',
            'CSV文件 (*.csv)'
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['股票名称', 'CUSIP代码', '市值(千美元)', '股数', '类型', '投票权(独占)', '投票权(共享)', '投票权(无)'])
                
                for h in self.current_holdings:
                    writer.writerow([
                        h.get('issuer_name', ''),
                        h.get('cusip', ''),
                        h.get('value', 0) or 0,
                        h.get('shares', 0) or 0,
                        h.get('title_of_class', ''),
                        h.get('voting_authority_sole', 0) or 0,
                        h.get('voting_authority_shared', 0) or 0,
                        h.get('voting_authority_none', 0) or 0
                    ])
            
            QMessageBox.information(self, '成功', f'数据已导出到:\n{filename}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'导出失败: {str(e)}')
    
    def export_to_excel(self):
        if not self.current_holdings:
            QMessageBox.warning(self, '提示', '没有可导出的数据，请先选择一个机构')
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, '保存Excel文件',
            f'{self.current_institution_name}_{datetime.now().strftime("%Y%m%d")}.xlsx',
            'Excel文件 (*.xlsx)'
        )
        
        if not filename:
            return
        
        try:
            import pandas as pd
            
            df = pd.DataFrame(self.current_holdings)
            
            columns_map = {
                'issuer_name': '股票名称',
                'cusip': 'CUSIP代码',
                'value': '市值(千美元)',
                'shares': '股数',
                'title_of_class': '类型',
                'voting_authority_sole': '投票权(独占)',
                'voting_authority_shared': '投票权(共享)',
                'voting_authority_none': '投票权(无)',
                'filing_date': '报告日期'
            }
            
            export_cols = ['issuer_name', 'cusip', 'value', 'shares', 'title_of_class', 
                          'voting_authority_sole', 'voting_authority_shared', 'voting_authority_none']
            
            if 'filing_date' in df.columns:
                export_cols.append('filing_date')
            
            df_export = df[[c for c in export_cols if c in df.columns]]
            df_export = df_export.rename(columns={k: v for k, v in columns_map.items() if k in df_export.columns})
            
            df_export.to_excel(filename, index=False, engine='openpyxl')
            
            QMessageBox.information(self, '成功', f'数据已导出到:\n{filename}')
        except ImportError:
            QMessageBox.warning(self, '错误', '导出Excel需要安装openpyxl库\n请运行: pip install openpyxl')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'导出失败: {str(e)}')
    
    def export_all_institutions(self):
        all_data = []
        
        for inst in self.institutions_data:
            db_inst = self.db.get_institution_by_cik(inst['cik'])
            if db_inst:
                holdings = self.db.get_latest_holdings(db_inst['id'])
                for h in holdings:
                    h['institution_name'] = inst['name']
                    all_data.append(h)
        
        if not all_data:
            QMessageBox.warning(self, '提示', '没有可导出的数据，请先更新机构数据')
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, '保存所有机构数据',
            f'所有机构持仓_{datetime.now().strftime("%Y%m%d")}.csv',
            'CSV文件 (*.csv)'
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['机构名称', '股票名称', 'CUSIP代码', '市值(千美元)', '股数', '类型', '报告日期'])
                
                for h in all_data:
                    writer.writerow([
                        h.get('institution_name', ''),
                        h.get('issuer_name', ''),
                        h.get('cusip', ''),
                        h.get('value', 0) or 0,
                        h.get('shares', 0) or 0,
                        h.get('title_of_class', ''),
                        h.get('filing_date', '')
                    ])
            
            QMessageBox.information(self, '成功', f'已导出 {len(all_data)} 条记录到:\n{filename}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'导出失败: {str(e)}')
    
    def closeEvent(self, event):
        self.db.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    font = QFont('Microsoft YaHei', 9)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
