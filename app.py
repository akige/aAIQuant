from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import requests
import json
import os
from datetime import datetime, timedelta
import time
from threading import Thread
from dotenv import load_dotenv
import ccxt
import asyncio
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import websockets
import threading
import yfinance as yf
from cachetools import TTLCache

load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading')

# 要追踪的股票列表
STOCKS = ['MSTR', '^IXIC', 'NVDA', 'TSLA']

# 要追踪的加密货币列表
CRYPTO = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'XRP/USDT', 'BNB/USDT', 'ADA/USDT', 'XLM/USDT']

# 初始化币安交易所接口
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'spot',
        'adjustForTimeDifference': True,
    }
})

# 配置请求会话
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

# 添加K线数据缓存
kline_cache = TTLCache(maxsize=100, ttl=60)

def get_stock_data(symbol):
    """从Yahoo Finance获取股票数据"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 使用Yahoo Finance的实时行情API，添加包含盘前盘后数据的参数
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d&includePrePost=true'
        response = session.get(url, headers=headers, timeout=10)
        data = response.json()
        
        if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
            result = data['chart']['result'][0]
            meta = result['meta']
            
            # 获取市场状态和交易时段
            current_trading_period = meta.get('currentTradingPeriod', {})
            current_time = int(time.time())
            
            # 判断是否为指数
            is_index = symbol.startswith('^')
            
            # 判断当前是否在盘前
            is_pre_market = (
                'pre' in current_trading_period and
                current_time >= current_trading_period['pre']['start'] and
                current_time < current_trading_period['pre']['end']
            )
            
            # 判断当前是否在盘后
            is_post_market = (
                'post' in current_trading_period and
                current_time >= current_trading_period['post']['start'] and
                current_time < current_trading_period['post']['end']
            )
            
            # 判断当前是否在常规交易时段
            is_regular_market = (
                'regular' in current_trading_period and
                current_time >= current_trading_period['regular']['start'] and
                current_time < current_trading_period['regular']['end']
            )
            
            # 设置市场状态
            if is_pre_market:
                market_state = 'PRE'
            elif is_regular_market:
                market_state = 'REGULAR'
            elif is_post_market:
                market_state = 'POST'
            else:
                market_state = 'CLOSED'
            
            # 获取价格数据
            current_price = meta.get('regularMarketPrice', 0)
            previous_close = meta.get('previousClose', current_price)
            
            # 计算常规交易时段涨跌幅
            regular_change = ((current_price - previous_close) / previous_close * 100) if previous_close > 0 else 0
            
            # 获取盘前盘后数据
            extended_price = 0
            extended_change = 0
            
            # 获取时间戳和价格数据
            timestamps = result.get('timestamp', [])
            indicators = result.get('indicators', {})
            quotes = indicators.get('quote', [{}])[0]
            
            if timestamps and quotes:
                # 获取开盘、高位、低位和收盘价
                opens = quotes.get('open', [])
                closes = quotes.get('close', [])
                
                # 找到最新的有效价格
                latest_price = None
                for i in range(len(timestamps)-1, -1, -1):
                    if closes[i] is not None:
                        latest_price = closes[i]
                        break
                    elif opens[i] is not None:
                        latest_price = opens[i]
                        break
                
                if latest_price is not None:
                    if market_state in ['PRE', 'POST']:
                        # 对于指数，使用最新价格作为扩展价格，并相对于前收盘价计算涨跌幅
                        if is_index:
                            extended_price = latest_price
                            if previous_close > 0:
                                extended_change = ((extended_price - previous_close) / previous_close * 100)
                        # 对于普通股票，使用最新价格作为扩展价格，并相对于收盘价计算涨跌幅
                        else:
                            extended_price = latest_price
                            if current_price > 0:
                                extended_change = ((extended_price - current_price) / current_price * 100)
                
                print(f"调试 - {symbol} 盘前/盘后数据:")
                print(f"市场状态: {market_state}")
                print(f"常规价格: {current_price}")
                print(f"前收盘价: {previous_close}")
                print(f"盘前/盘后价格: {extended_price}")
                print(f"盘前/盘后涨跌幅: {extended_change}%")
                print(f"最新价格时间戳: {datetime.fromtimestamp(timestamps[-1]).strftime('%Y-%m-%d %H:%M:%S')}")

            return {
                'symbol': symbol,
                'price': extended_price if extended_price > 0 else current_price,
                'change_percent': regular_change,
                'extended_hours_change': extended_change,
                'market_state': market_state,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'stock'
            }
    except Exception as e:
        print(f"Error fetching stock data for {symbol}: {str(e)}")
        print(f"Error details: {str(e.__class__.__name__)}")
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text[:500]}")
    return None

def get_crypto_data(symbol):
    """从币安获取加密货币数据"""
    try:
        ticker = exchange.fetch_ticker(symbol)
        return {
            'symbol': symbol.split('/')[0],
            'price': float(ticker['last']),
            'change_percent': float(ticker['percentage']),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'crypto'
        }
    except Exception as e:
        print(f"Error fetching crypto data for {symbol}: {str(e)}")
        return None

def get_all_crypto_data():
    """批量获取所有加密货币数据"""
    all_data = []
    try:
        tickers = exchange.fetch_tickers(CRYPTO)
        for symbol in CRYPTO:
            if symbol in tickers:
                ticker = tickers[symbol]
                all_data.append({
                    'symbol': symbol.split('/')[0],
                    'price': float(ticker['last']),
                    'change_percent': float(ticker['percentage']),
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'crypto'
                })
    except Exception as e:
        print(f"Error fetching crypto data: {str(e)}")
    return all_data

def fetch_initial_stock_data():
    """并行获取初始股票数据"""
    with ThreadPoolExecutor(max_workers=len(STOCKS)) as executor:
        futures = [executor.submit(get_stock_data, symbol) for symbol in STOCKS]
        results = []
        for future in futures:
            try:
                result = future.result(timeout=15)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"Error getting stock data: {str(e)}")
        return results

async def background_update():
    """后台更新数据"""
    stock_update_times = {symbol: 0 for symbol in STOCKS}
    error_counts = {symbol: 0 for symbol in STOCKS}
    update_interval = 2  # 减少到2秒更新一次
    
    # 计算每个股票的初始更新时间偏移，使其错开
    for i, symbol in enumerate(STOCKS):
        stock_update_times[symbol] = time.time() - (update_interval * i / len(STOCKS))
    
    # 首次启动时立即获取股票数据
    print("Fetching initial stock data...")
    initial_stock_data = fetch_initial_stock_data()
    if initial_stock_data:
        print(f"Initial stock data received: {len(initial_stock_data)} stocks")
        socketio.emit('market_update', {'data': initial_stock_data}, namespace='/')

    while True:
        try:
            current_time = time.time()
            updates = []
            
            for symbol in STOCKS:
                if current_time - stock_update_times[symbol] >= update_interval:
                    try:
                        stock_data = get_stock_data(symbol)
                        if stock_data:
                            error_counts[symbol] = 0
                            updates.append(stock_data)
                        else:
                            error_counts[symbol] += 1
                            if error_counts[symbol] >= 3:
                                error_counts[symbol] = 0
                                await asyncio.sleep(0.5)
                    except Exception as e:
                        error_counts[symbol] += 1
                    finally:
                        stock_update_times[symbol] = current_time
            
            # 批量发送更新数据
            if updates:
                socketio.emit('market_update', {'data': updates}, namespace='/')
            
            # 使用异步休眠
            await asyncio.sleep(0.05)
            
        except Exception as e:
            await asyncio.sleep(0.2)

async def binance_websocket_handler():
    """处理币安WebSocket连接"""
    uri = "wss://stream.binance.com:9443/ws"
    symbols = [s.replace('/', '').lower() for s in CRYPTO]
    subscribe_message = {
        "method": "SUBSCRIBE",
        "params": [f"{symbol}@ticker" for symbol in symbols],
        "id": 1
    }
    
    reconnect_delay = 0.2
    max_reconnect_delay = 2
    updates_buffer = []
    last_emit_time = 0
    emit_interval = 0.1
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                await websocket.send(json.dumps(subscribe_message))
                reconnect_delay = 0.2
                
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        data = json.loads(message)
                        
                        if 'e' in data and data['e'] == '24hrTicker':
                            symbol = data['s']
                            base_symbol = symbol.replace('USDT', '')
                            if f"{base_symbol}/USDT" in CRYPTO:
                                crypto_data = {
                                    'symbol': base_symbol,
                                    'price': float(data['c']),
                                    'change_percent': float(data['P']),
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'type': 'crypto',
                                    'market_state': 'REGULAR'
                                }
                                
                                updates_buffer.append(crypto_data)
                                current_time = time.time()
                                
                                # 当缓冲区有数据且达到发送间隔时，批量发送
                                if updates_buffer and current_time - last_emit_time >= emit_interval:
                                    socketio.emit('market_update', {'data': updates_buffer}, namespace='/')
                                    updates_buffer = []
                                    last_emit_time = current_time
                                
                    except asyncio.TimeoutError:
                        if updates_buffer:
                            socketio.emit('market_update', {'data': updates_buffer}, namespace='/')
                            updates_buffer = []
                        break
                    except websockets.exceptions.ConnectionClosed:
                        break
                    except Exception as e:
                        continue
                        
        except Exception as e:
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)

def start_binance_websocket():
    """启动币安WebSocket连接"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(binance_websocket_handler())

def start_background_update():
    """启动后台更新"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(background_update())

@app.route('/')
def index():
    """渲染主页"""
    return render_template('index.html', stocks=STOCKS, crypto=[c.split('/')[0] for c in CRYPTO])

# 添加K线图相关的路由
@app.route('/detail/<symbol>')
def detail(symbol):
    is_stock = not symbol.startswith('^')
    return render_template('detail.html', symbol=symbol, is_stock=is_stock)

@app.route('/api/kline/<symbol>/<timeframe>')
def get_kline_data(symbol, timeframe):
    print(f"Processing kline request for {symbol}, timeframe: {timeframe}, is_crypto: {symbol in ['ADA', 'XLM', 'DOGE', 'BTC']}")
    try:
        # 将timeframe转换为yfinance格式
        timeframe_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d'
        }
        yf_timeframe = timeframe_map.get(timeframe, '1d')
        
        # 为加密货币添加-USD后缀
        if symbol in ['ADA', 'XLM', 'DOGE', 'BTC']:
            yf_symbol = f"{symbol}-USD"
        else:
            yf_symbol = symbol
            
        # 获取历史数据
        ticker = yf.Ticker(yf_symbol)
        
        # 根据timeframe设置适当的时间范围
        if timeframe in ['1m', '5m', '15m', '30m']:
            period = "1d"
        elif timeframe in ['1h', '4h']:
            period = "5d"
        else:
            period = "60d"
            
        df = ticker.history(period=period, interval=yf_timeframe)
        
        if df.empty:
            print(f"No data received for {symbol} with timeframe {timeframe}")
            return []
            
        # 转换数据格式
        klines = []
        for index, row in df.iterrows():
            kline = {
                'time': int(index.timestamp() * 1000),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': float(row['Volume'])
            }
            klines.append(kline)
            
        print(f"Retrieved {len(klines)} klines for {symbol}")
        if klines:
            print(f"First kline: {klines[0]}")
            
        return klines
        
    except Exception as e:
        print(f"Error fetching yfinance kline data: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error details: {e.__dict__}")
        return []

if __name__ == '__main__':
    # 启动WebSocket连接
    websocket_thread = Thread(target=start_binance_websocket)
    websocket_thread.daemon = True
    websocket_thread.start()
    
    # 启动后台更新线程
    update_thread = Thread(target=start_background_update)
    update_thread.daemon = True
    update_thread.start()
    
    # 启动Flask应用
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)