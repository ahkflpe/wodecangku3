## 04 项目核心成果描述

我构建了一个基于Python+PyQt5的知名投资机构持仓追踪器桌面应用。通过自动抓取美国SEC EDGAR系统的公开13F报告，收集并解析全球39家知名投资机构（巴菲特伯克希尔、桥水基金、高瓴资本、淡马锡、软银等）的股票持仓数据。

**核心逻辑流**：
1. **数据获取层** (sec_fetcher.py)：调用SEC API获取机构13F文件列表，智能定位持仓XML文件
2. **数据解析层** (parser.py)：解析XML格式的持仓数据，提取股票名称、CUSIP、市值、股数等信息
3. **数据存储层** (database.py)：SQLite本地存储，支持历史数据追溯和多机构对比
4. **GUI展示层** (main.py)：PyQt5构建的桌面应用，支持机构选择、持仓查看、搜索和CSV/Excel导出

项目已实现从数据抓取到可视化展示的完整流程，帮助用户快速分析全球顶级投资机构的投资动向。

---

## 05 使用证明与影响力证明

### GitHub项目地址
https://github.com/ahkflpe/wodecangku3

### 功能截图
见截图文件夹：
- `01_主界面.png` - 应用程序主界面，展示39家投资机构列表
- `02_持仓详情.png` - 查看机构持仓详情，包括股票名称、市值、股数
- `03_导出功能.png` - 数据导出功能展示

### 终端运行日志
```
# 安装依赖
pip install -r requirements.txt

# 运行程序
python main.py
```

## 技术栈
- Python 3.12 + PyQt5
- SQLite本地存储
- requests + lxml数据获取
- pandas/openpyxl导出

## 数据来源
美国证券交易委员会(SEC) EDGAR系统公开13F报告
