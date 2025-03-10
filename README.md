# aAIQuant

实时股票和加密货币行情追踪系统，基于Python Flask和WebSocket技术构建，支持美股和加密货币的实时价格监控和K线图表显示。

## 功能特点

- 实时追踪美股价格和涨跌幅
  - 支持盘前盘后交易数据
  - 自动识别交易时段（盘前、盘中、盘后）
  - 支持指数追踪（如纳斯达克）
- 实时追踪加密货币价格和涨跌幅
  - 通过币安WebSocket实时更新
  - 支持多币种同时监控
- K线图表功能
  - 支持多个时间周期（1分钟到1天）
  - 交互式图表缩放和数据查看
  - 成交量显示
- 技术特性
  - WebSocket实时数据推送
  - 自动错误恢复机制
  - 数据缓存优化
  - 并发请求处理

## 项目结构

```
aAIQuant/
├── app.py              # 主程序文件
├── templates/          # HTML模板
│   ├── index.html     # 主页面
│   └── detail.html    # K线图表页面
├── static/            # 静态资源
│   ├── css/          # 样式文件
│   └── js/           # JavaScript文件
├── requirements.txt   # 项目依赖
└── .env              # 环境配置
```

## 技术栈

- 后端
  - Flask：Web框架
  - Flask-SocketIO：WebSocket支持
  - yfinance：股票数据API
  - ccxt：加密货币交易所API
  - websockets：WebSocket客户端
  - requests：HTTP客户端
  - python-dotenv：环境配置
  - cachetools：数据缓存

- 前端
  - Bootstrap：UI框架
  - TradingView：图表库
  - Socket.IO：实时通信
  - jQuery：DOM操作

## 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/akige/aAIQuant.git
cd aAIQuant
```

2. 创建并激活虚拟环境（可选）
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
创建 .env 文件并添加必要的配置：
```
BINANCE_API_KEY=your_binance_api_key
```

5. 运行应用
```bash
python app.py
```

6. 访问应用
打开浏览器访问 http://localhost:8000

## 配置说明

在 app.py 中可以配置：
- `STOCKS`：要追踪的股票代码列表
- `CRYPTO`：要追踪的加密货币代码列表

## 开发计划

- [ ] 添加更多技术指标
- [ ] 支持自定义股票和加密货币列表
- [ ] 添加价格提醒功能
- [ ] 支持更多交易所数据源
- [ ] 添加用户认证系统
- [ ] 优化移动端显示

## 许可证

MIT License