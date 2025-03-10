# aAIQuant

实时股票和加密货币行情追踪系统，支持美股和加密货币的实时价格、K线图表显示。

## 功能特点

- 实时追踪美股价格和涨跌幅
- 实时追踪加密货币价格和涨跌幅
- 支持K线图表显示
- 支持盘前盘后交易数据
- WebSocket实时数据更新
- 自动错误恢复机制

## 安装要求

- Python 3.7+
- pip

## 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/akige/aAIQuant.git
cd aAIQuant
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 运行应用
```bash
python app.py
```

4. 访问应用
打开浏览器访问 http://localhost:8000

## 配置说明

- `STOCKS`: 在 app.py 中配置要追踪的股票代码
- `CRYPTO`: 在 app.py 中配置要追踪的加密货币代码

## 许可证

MIT License