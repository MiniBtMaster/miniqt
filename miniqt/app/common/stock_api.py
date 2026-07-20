"""
股票数据API - 仿天勤接口风格
数据源：MooTDX（TCP直连通达信服务器）
"""

import pandas as pd
import threading
from typing import Optional, Dict, Any, List, Union, Literal
from datetime import datetime, time as dt_time, timedelta
from mootdx.quotes import Quotes
from mootdx.consts import MARKET_SH, MARKET_SZ, MARKET_BJ


class StockApi:
    """股票数据API - 仿天勤接口风格
    
    使用方式与天勤 TqApi 类似：
    - get_kline_serial(): 获取历史K线并注册订阅
    - wait_update(): 更新已订阅股票的实时数据
    
    数据源：MooTDX（TCP直连通达信服务器）
    """
    
    # 周期映射（秒 -> MooTDX frequency 参数）
    # MooTDX frequency 参数对照表：
    # '5m'=5分钟线, '15m'=15分钟线, '30m'=30分钟线, '1h'=1小时线
    # 'day'=日线, 'week'=周线, 'mon'=月线
    # 'ex_1m'=1分钟线, '1m'=1分钟线, 'dk'=日线
    # '3mon'=季线, 'year'=年线
    PERIOD_TO_FREQUENCY = {
        60: '1m',       # 1分钟
        300: '5m',      # 5分钟
        900: '15m',     # 15分钟
        1800: '30m',    # 30分钟
        3600: '1h',     # 1小时
        86400: 'day',   # 日线
        604800: 'week', # 周线
        2419200: 'mon', # 月线
        7776000: '3mon', # 季线（约3个月）
        31536000: 'year', # 年线（约365天）
    }
    # 市场代码映射
    MARKET_MAP = {
        'SH': 1,     # 上交所
        'SZ': 0,     # 深交所
        'SSE': 1,    # 上交所
        'SZSE': 0,   # 深交所
    }
    
    def __init__(
        self,
        fast_init: bool = False,
        host: str = None,
        port: int = None,
        timeout: int = 10
    ):
        """
        初始化股票API（仅支持 MooTDX 数据源）

        Args:
            fast_init: 是否使用快速初始化，默认 False
            host: MooTDX 服务器IP地址
            port: MooTDX 服务器端口

        推荐服务器地址（通达信）：
        - 119.147.212.81:7709  （深圳电信）
        - 113.105.73.20:7709   （深圳联通）
        - 218.75.126.9:7709    （上海电信）
        """
        # MooTDX 客户端（TCP直连通达信服务器）
        self._client = None
        # 已订阅股票的K线数据缓存：key = (code, period)
        self._subscribed_symbols: Dict[tuple, pd.DataFrame] = {}
        # 每个股票的配置：key = (code, period)
        self._symbol_configs: Dict[tuple, Dict[str, Any]] = {}
        # 数据更新锁
        self._lock = threading.Lock()
        # 是否有数据更新
        self._has_update = False
        # 初始化状态
        self._initialized = False
        # 快速初始化参数
        self._fast_init = fast_init
        self._host = host
        self._port = port
        self._timeout = timeout

        # === is_changing 相关属性 ===
        # 更新前每只股票最后一根K线的数据快照 {(code, period): {open, high, low, close, volume, datetime}}
        self._last_bar_snapshot: Dict[tuple, Dict] = {}

    def _init_client(self):
        """延迟初始化 MooTDX 客户端"""
        if self._client is None:
            try:
                if self._fast_init:
                    # 使用快速初始化（跳过测速）
                    self._init_client_fast(self._host, self._port)
                else:
                    # std=A股标准市场
                    # bestip=True 会自动测速选最快服务器（首次较慢，之后读取缓存）
                    # heartbeat=True 心跳保活防断线
                    self._client = Quotes.factory(market='std', bestip=True, heartbeat=True)
                    self._initialized = True
                    # print("[StockApi] MooTDX 客户端初始化成功")
            except Exception as e:
                print(f"[StockApi] MooTDX 初始化失败: {e}")
                self._initialized = False
    
    def _init_client_fast(self, host: str = None, port: int = None):
        """
        快速初始化 MooTDX 客户端（跳过自动测速）
        
        Args:
            host: 服务器IP地址（必填）
            port: 服务器端口（必填）
        
        推荐服务器地址（通达信官方行情服务器）：
        - 119.147.212.81:7709  （深圳电信）
        - 113.105.73.20:7709   （深圳联通）
        - 218.75.126.9:7709    （上海电信）
        """
        if self._client is None:
            try:
                if host and port:
                    # 指定服务器：直接连接，跳过测速（fast_init 核心优化）
                    # bestip=False + 提供 server 参数，避免内部读取空列表
                    server_addr = (host, port)
                    self._client = Quotes.factory(
                        market='std', server=server_addr, bestip=False,
                        heartbeat=True, timeout=self._timeout
                    )
                else:
                    # 未指定服务器：使用默认方式（自动测速）
                    self._client = Quotes.factory(
                        market='std', bestip=True, heartbeat=True, timeout=self._timeout
                    )
                
                self._initialized = True
                server_info = f"{host}:{port}" if host and port else "自动测速"
                print(f"[StockApi] MooTDX 客户端快速初始化成功（服务器: {server_info}）")
                
            except Exception as e:
                print(f"[StockApi] MooTDX 快速初始化失败: {e}")
                self._initialized = False
    
    # api bars
    def get_kline_serial(self, symbol: str, period: int, length: int=800) -> pd.DataFrame:
        """
        获取历史K线并注册订阅（使用 MooTDX 数据源）

        Args:
            symbol: 股票代码，支持格式：
                    - "000001"（纯代码，自动判断市场）
                    - "SH.600000" 或 "SZ.000001"（带交易所前缀）
                    - "600000.SH"（天勤格式）
            period: 周期（秒），支持的值：
                    - 60: 1分钟
                    - 300: 5分钟
                    - 900: 15分钟
                    - 1800: 30分钟
                    - 3600: 1小时
                    - 86400: 日线
            length: K线数量

        Returns:
            DataFrame: columns=['datetime', 'open', 'high', 'low', 'close', 'volume']
                      datetime 为纳秒时间戳（19位）
        """
        # 解析股票代码和市场
        code, market = self._parse_symbol(symbol)

        # === 检查是否已订阅，如果已订阅则直接返回缓存数据 ===
        with self._lock:
            for (sub_code, sub_period), cached_df in self._subscribed_symbols.items():
                if sub_code == code and sub_period == period:
                    return cached_df#.copy()

        df = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])

        # === 使用 MooTDX 数据源获取数据 ===
        # print(f"[StockApi] 使用 MooTDX 数据源获取 {code} K线数据")

        # 延迟初始化 MooTDX 客户端
        #self._init_client()

        if self._initialized and self._client:
            # 获取 MooTDX frequency 参数
            frequency = self.PERIOD_TO_FREQUENCY.get(period, 'day')

            try:
                # mootdx bars() 不需要 market 参数，市场会自动识别
                df = self._client.bars(
                    symbol=code,
                    frequency=frequency,
                    offset=length
                )

                # === 详细调试：打印原始返回值 ===
                #print(f"[StockApi] bars() 原始返回: type={type(df)}, is_None={df is None}, shape={df.shape if hasattr(df, 'shape') else 'N/A'}")
                # if df is not None and hasattr(df, 'head'):
                #     print(f"[StockApi] bars() 前3行:\n{df.head(3)}")

                if df is not None and not df.empty:
                    # 标准化数据格式
                    df = self._standardize_kline(df)
                # else:
                #     print(f"[StockApi] MooTDX 获取 {code} K线数据为空")

            except Exception as e:
                print(f"[StockApi] MooTDX 获取K线失败: {e}")
        else:
            print("[StockApi] MooTDX 客户端未初始化")

        # === 注册订阅（如果有数据） ===
        if not df.empty:
            frequency = self.PERIOD_TO_FREQUENCY.get(period, 'day')
            key = (code, period)
            with self._lock:
                self._subscribed_symbols[key] = df.copy()
                self._symbol_configs[key] = {
                    "period": period,
                    "length": length,
                    "frequency": frequency,
                    "market": market,
                }

        return df
    
    def wait_update(self, deadline: float = None) -> bool:
        """
        等待数据更新
        
        新周期：使用 bars() 获取完整K线，确保 OHLCV 准确
        非新周期：使用 quotes() 实时快照增量更新 close/high/low/volume
        
        Args:
            deadline: 超时时间（秒），None 表示立即返回
        
        Returns:
            bool: 是否有数据更新
        """
        if not self._initialized or not self._client:
            return False
        
        # 非交易时间直接返回 False
        if not self.is_trading_time():
            return False
        
        with self._lock:
            if not self._subscribed_symbols:
                return False
            
            # 获取所有已订阅的 (code, period) 对
            subscribed_items = list(self._subscribed_symbols.items())
        
        if not subscribed_items:
            return False
        
        # === 保存快照（供 is_changing 比较） ===
        self._last_bar_snapshot.clear()
        for key, df in subscribed_items:
            if not df.empty:
                last = df.iloc[-1]
                self._last_bar_snapshot[key] = {
                    'open': float(last['open']),
                    'high': float(last['high']),
                    'low': float(last['low']),
                    'close': float(last['close']),
                    'volume': float(last['volume']),
                    'datetime': int(last['datetime']),
                }
        
        has_update = False
        
        # === 全部使用 bars() 刷新数据 ===
        for key, _ in subscribed_items:
            code, period = key
            config = self._symbol_configs.get(key, {})
            frequency = config.get('frequency', 'day')
            max_length = config.get('length', 800)
            
            try:
                new_df = self._client.bars(
                    symbol=code,
                    frequency=frequency,
                    offset=max_length
                )
                
                if new_df is not None and not new_df.empty:
                    new_df = self._standardize_kline(new_df)
                    with self._lock:
                        self._subscribed_symbols[key] = new_df
                    has_update = True
            except Exception as e:
                print(f"[StockApi.wait_update] bars() 失败 ({code}, {period}s): {e}")
        
        self._has_update = has_update
        return has_update
    
    def is_changing(self, obj: Any, key: Union[str, List[str], None] = None) -> bool:
        """
        判断数据是否有更新（仿天勤 TqApi.is_changing）
        
        对比 wait_update 前后最后一行K线数据。
        
        Args:
            obj:
                - str: 股票代码，如 "000001"
                - pd.DataFrame: get_kline_serial 返回的K线数据
            key:
                - None: 检查所有字段 (open, high, low, close, volume)
                - str: 检查指定字段（如 'close'）
                - List[str]: 检查多个字段
        """
        if key is None:
            keys = ['open', 'high', 'low', 'close', 'volume']
        elif isinstance(key, str):
            keys = [key]
        else:
            keys = key
        
        if isinstance(obj, str):
            code = self._parse_symbol(obj)[0]
            return self._is_symbol_changing(code, keys)
        elif isinstance(obj, pd.DataFrame):
            if obj.empty:
                return False
            return self._is_df_changing(obj, keys)
        return False
    
    def _is_df_changing(self, df: pd.DataFrame, keys: List[str]) -> bool:
        """根据 DataFrame 实例精确匹配订阅周期后对比"""
        for key, subscribed_df in self._subscribed_symbols.items():
            if subscribed_df is df:
                old_bar = self._last_bar_snapshot.get(key)
                if old_bar is None:
                    return True
                last = df.iloc[-1]
                for field in keys:
                    if old_bar.get(field, 0) != float(last[field]):
                        return True
                return False
        return False
    
    def _is_symbol_changing(self, code: str, keys: List[str]) -> bool:
        """遍历该股票所有订阅周期，任一有变化即返回 True"""
        for key, df in self._subscribed_symbols.items():
            if key[0] == code and not df.empty:
                old_bar = self._last_bar_snapshot.get(key)
                if old_bar is None:
                    return True
                last = df.iloc[-1]
                for field in keys:
                    if old_bar.get(field, 0) != float(last[field]):
                        return True
        return False
    
    def get_quote(self, symbol: str, period: int = None) -> Optional[pd.DataFrame]:
        """
        获取已订阅股票的K线数据
        
        Args:
            symbol: 股票代码
            period: 周期（秒），None 表示返回第一个匹配周期的数据
        
        Returns:
            DataFrame: K线数据，如果未订阅则返回 None
        """
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            for key, df in self._subscribed_symbols.items():
                if key[0] == code:
                    if period is None or key[1] == period:
                        return df.copy()
        return None
    
    def is_trading_time(self) -> bool:
        """
        判断当前是否在A股交易时段
        
        A股交易时段：
        - 上午：9:30 - 11:30
        - 下午：13:00 - 15:00
        
        注意：仅判断时间和周末，不判断节假日
        
        Returns:
            bool: 是否在交易时段
        """
        now = datetime.now()
        
        # 检查是否是周末（5=周六, 6=周日）
        weekday = now.weekday()
        if weekday >= 5:
            return False
        
        current_time = now.time()
        
        # 上午交易时段
        morning_start = dt_time(9, 30)
        morning_end = dt_time(11, 30)
        
        # 下午交易时段
        afternoon_start = dt_time(13, 0)
        afternoon_end = dt_time(15, 0)
        
        is_morning = morning_start <= current_time <= morning_end
        is_afternoon = afternoon_start <= current_time <= afternoon_end
        
        return is_morning or is_afternoon
    
    def is_subscribed(self, symbol: str) -> bool:
        """检查股票是否已订阅（任意周期）"""
        code, _ = self._parse_symbol(symbol)
        for key in self._subscribed_symbols.keys():
            if key[0] == code:
                return True
        return False
    
    def unsubscribe(self, symbol: str, period: int = None):
        """取消订阅股票
        
        Args:
            symbol: 股票代码
            period: 周期，None 表示取消所有周期
        """
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            keys_to_remove = []
            for key in self._subscribed_symbols.keys():
                if key[0] == code:
                    if period is None or key[1] == period:
                        keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._subscribed_symbols[key]
                del self._symbol_configs[key]
    
    
        
    # api methods
    def quote(self, market='', symbol='', **kwargs) -> Optional[pd.DataFrame]:
        """
        获取已订阅股票的当前K线数据
        
        Args:
            symbol: 股票代码
        
        Returns:
            DataFrame: K线数据，如果未订阅则返回 None
        """
        # code, _ = self._parse_symbol(symbol)
        # with self._lock:
        #     return self._subscribed_symbols.get(code)
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.quote(symbol=code)
    
    def quotes(self, symbol=None, **kwargs) -> Optional[pd.DataFrame]:
        """
        查询五档行情

        Args:
            market: 市场ID
            symbol: 股票代码
        Returns:
            DataFrame: 五档行情数据，如果未订阅则返回 None
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.quotes(symbol=code)
    
    def stock_count(self, market:Literal[MARKET_SH, MARKET_SZ, MARKET_BJ]=MARKET_SH):
        """
        获取市场股票数量

        :param market: 股票市场代码 sh 上海， sz 深圳
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        with self._lock:
            return self._client.stock_count(market=market)
    
    def stock_all(self):
        """
        获取所有股票列表

        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        with self._lock:
            return self._client.stock_all()
    
    def index_bars(self, symbol='', frequency=9, start=0, offset=800, **kwargs):
        """
        获取指数k线

        :param symbol: 股票代码
        :param frequency: 数据频次
        :param start: 开始位置
        :param offset: 获取数量
        :return:
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.index_bars(symbol=code, frequency=frequency, start=start, offset=offset, **kwargs)
    
    def minute(self, symbol=None, **kwargs):
        """
        获取实时分时数据

        :param symbol: 股票代码
        :return: pd.DataFrame
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.minute(symbol=code, **kwargs)
    
    def minutes(self, symbol=None, date='20191023', **kwargs):
        """
        分时历史数据

        :param symbol:  股票代码
        :param date:    查询日期
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.minutes(symbol=code, date=date, **kwargs)
    
    def transaction(self, symbol='', start=0, offset=800, **kwargs):
        """
        查询分笔成交

        :param symbol:  股票代码
        :param start:   起始位置
        :param offset:  获取数量
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.transaction(symbol=code, start=start, offset=offset, **kwargs)
    
    def transactions(self, symbol='', start=0, offset=800, date='20170209', **kwargs):
        """
        查询历史分笔成交

        :param symbol:  股票代码
        :param start:   起始位置
        :param offset:  获取数量
        :param date:    查询日期
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.transactions(symbol=code, start=start, offset=offset, date=date, **kwargs)
    
    def F10C(self, symbol=''):  # noqa
        """
        查询公司信息目录

        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.F10C(symbol=code)
    
    def F10(self, symbol='', name=''):  # noqa
        """
        读取公司信息详情

        :param name: 公司 F10 标题
        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.F10(symbol=code, name=name)
    
    def xdxr(self, symbol='', **kwargs):
        """
        读取除权除息信息

        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.xdxr(symbol=code, **kwargs)
    
    def finance(self, symbol='000001', **kwargs):
        """
        读取财务信息

        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.finance(symbol=code, **kwargs)
    
    def k(self, symbol='', begin=None, end=None, **kwargs):
        """
        读取k线信息

        :param symbol:  股票代码
        :param begin:   开始日期
        :param end:     截止日期
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.k(symbol=code, begin=begin, end=end, **kwargs)
    
    def get_k_data(self, code, start_date, end_date):
        """
        获取k线数据

        :param code: 股票代码
        :param start_date: 开始日期
        :param end_date: 截止日期
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        with self._lock:
            return self._client.get_k_data(code, start_date, end_date)
    
    def index(self, symbol='000001', frequency=9, start=0, offset=800, **kwargs):
        """
        获取指数k线

        K线种类:
        - 0 5分钟K线
        - 1 15分钟K线
        - 2 30分钟K线
        - 3 1小时K线
        - 4 日K线
        - 5 周K线
        - 6 月K线
        - 7 1分钟
        - 8 1分钟K线
        - 9 日K线
        - 10 季K线
        - 11 年K线

        :param symbol:      股票代码
        :param frequency:   数据频次
        :param market:      证券市场
        :param start:       开始位置
        :param offset:      每次获取条数
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        code, _ = self._parse_symbol(symbol)
        with self._lock:
            return self._client.index(symbol=code, frequency=frequency, start=start, offset=offset, **kwargs)
    
    def block(self, tofile='block.dat', **kwargs):
        """
        获取证券板块信息

        :param tofile: 保存文件
        :return: pd.dataFrame or None
        """
        if not self._initialized or not self._client:
            return None
        with self._lock:
            return self._client.block(tofile=tofile, **kwargs)
        
    
    def close(self):
        """关闭API，清理资源"""
        with self._lock:
            self._subscribed_symbols.clear()
            self._symbol_configs.clear()
        
        # 关闭 MooTDX 连接
        if self._client:
            try:
                self._client.close()
                #print("[StockApi] MooTDX 连接已关闭")
            except Exception as e:
                print(f"[StockApi] 关闭连接错误: {e}")
        
        self._initialized = False
        self._client = None
    
    def _parse_symbol(self, symbol: str) -> tuple:
        """
        解析股票代码和市场
        
        Args:
            symbol: 股票代码
        
        Returns:
            tuple: (code, market)
        """
        # === 调试打印 ===
        #print(f"[StockApi._parse_symbol] 输入: {symbol}")
        
        if "." in symbol:
            parts = symbol.split(".")
            # 判断格式：SH.600000 或 600000.SH
            if parts[0] in self.MARKET_MAP:
                market = self.MARKET_MAP[parts[0]]
                code = parts[1]
            elif parts[1] in self.MARKET_MAP:
                market = self.MARKET_MAP[parts[1]]
                code = parts[0]
            else:
                # 默认根据代码判断市场
                code = parts[0] if parts[0].startswith('6') else parts[1]
                market = 1 if code.startswith('6') else 0
        else:
            code = symbol
            # 根据代码判断市场：6开头是上交所，其他是深交所
            market = 1 if code.startswith('6') else 0
        
        # === 调试打印 ===
        #print(f"[StockApi._parse_symbol] 输出: code={code}, market={market}")
        
        return code, market
    
    def _standardize_kline(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化K线数据格式
        
        MooTDX bars() 原始字段：datetime, open, close, high, low, vol, amount, volume, year, month, day, hour, minute
        其中 vol 为本根K线成交量，amount 为当日累计成交量，volume 同 vol
        转换为：datetime(纳秒时间戳，19位), open, high, low, close, volume
        """
        
        # 确保 datetime 是纳秒时间戳（19位，pd.to_datetime().astype('int64')）
        if 'datetime' in df.columns:
            if df['datetime'].dtype == 'object':
                # 字符串格式转时间戳
                df['datetime'] = pd.to_datetime(df['datetime'])
            
            # 获取第一个值判断当前格式
            first_val = df['datetime'].iloc[0]
            
            if hasattr(first_val, 'timestamp'):
                # datetime 对象：直接转为纳秒时间戳（19位）
                df['datetime'] = df['datetime'].astype('int64')
            elif first_val > 1e18:
                # 已经是纳秒格式（19位），不做转换
                pass
            elif first_val > 1e15 and first_val < 1e18:
                # 微秒格式（16位），转为纳秒
                df['datetime'] = df['datetime'] * 1000
            elif first_val > 1e11 and first_val < 1e14:
                # 毫秒格式（13位），转为纳秒
                df['datetime'] = df['datetime'] * 1_000_000
            elif first_val < 1e11:
                # 秒格式（10位），转为纳秒
                df['datetime'] = df['datetime'] * 1_000_000_000
        
        # 确保必要的列存在
        required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0.0
        
        # 只保留需要的列（与天勤一致，不包含amount）
        cols_to_keep = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        
        # 使用整数索引（reset_index）
        df = df[cols_to_keep].reset_index(drop=True)
        
        return df
    
    def _append_bar(self, df: pd.DataFrame, new_bar: Dict, max_length: int) -> pd.DataFrame:
        """
        添加新K线，保持长度
        
        Args:
            df: 原K线数据
            new_bar: 新K线
            max_length: 最大长度
        
        Returns:
            DataFrame: 更新后的K线数据
        """
        new_row = pd.DataFrame([new_bar])
        df = pd.concat([df, new_row], ignore_index=True)
        
        # 保持长度
        if len(df) > max_length:
            df = df.iloc[-max_length:].reset_index(drop=True)
        
        return df
    
        
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
