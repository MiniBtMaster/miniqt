"""
股票API定时器 - 类似天勤的 TqApiQTimer
用于驱动 StockApi.wait_update() 定时更新
支持交易时段检测 + 动态更新频率
"""

from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from typing import TYPE_CHECKING, Optional
from datetime import datetime, time as dt_time

from .chart_config import chart_cfg

if TYPE_CHECKING:
    from ..view.main_window import MainWindow
    from .stock_api import StockApi


class StockApiQTimer(QObject):
    """
    股票API定时器
    
    定时调用 StockApi.wait_update() 更新已订阅股票的实时数据
    
    特性：
    - 交易时段检测：只在交易时段内更新数据
    - 动态更新频率：盘中3秒，盘前盘后暂停或降低频率
    - 避免无效请求：非交易时段减少网络请求
    
    A股交易时段：
    - 上午：9:30 - 11:30
    - 下午：13:00 - 15:00
    """
    
    # 数据更新信号
    dataUpdated = pyqtSignal(bool)
    
    # A股交易时段
    MORNING_START = dt_time(9, 30)
    MORNING_END = dt_time(11, 30)
    AFTERNOON_START = dt_time(13, 0)
    AFTERNOON_END = dt_time(15, 0)
    
    # 更新频率配置（毫秒）
    PRE_MARKET_INTERVAL = 10000  # 盘前：10秒（检测交易时段）
    AFTER_MARKET_INTERVAL = 30000  # 盘后：30秒（检测下一个交易日）
    
    def __init__(self, main_window: 'MainWindow', interval_ms: int = None):
        """
        初始化定时器
        
        Args:
            main_window: 主窗口
            interval_ms: 定时器间隔（毫秒），None 表示自动根据时段调整
        """
        super().__init__(main_window)
        self.main_window = main_window
        self.stock_api: Optional['StockApi'] = None
        self._timer: Optional[QTimer] = None
        self._interval_ms = interval_ms  # 固定间隔（如果指定）
        self._auto_interval = interval_ms is None  # 自动调整间隔
        self._is_running = False
        self._update_count = 0
        self._last_trading_status = False  # 上一次的交易时段状态
        
    def set_stock_api(self, stock_api: 'StockApi'):
        """设置股票API实例"""
        self.stock_api = stock_api
    
    def start(self):
        """启动定时器"""
        if self._is_running:
            return
        
        if self.stock_api is None:
            print("[StockApiQTimer] stock_api 未设置，无法启动")
            return
        
        # 创建定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        
        # 根据交易时段设置初始间隔
        interval = self._get_current_interval()
        self._timer.start(interval)
        
        self._is_running = True
        self._update_count = 0
        self._last_trading_status = self.is_trading_time()
        
        trading_status = "交易时段" if self._last_trading_status else "非交易时段"
        print(f"[StockApiQTimer] 启动，当前{trading_status}，间隔 {interval}ms")
    
    def stop(self):
        """停止定时器"""
        if self._timer:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        
        self._is_running = False
        print(f"[StockApiQTimer] 停止，共更新 {self._update_count} 次")
    
    def set_interval(self, interval_ms: int):
        """设置定时器间隔（固定间隔模式）"""
        self._interval_ms = interval_ms
        self._auto_interval = False
        if self._timer and self._is_running:
            self._timer.setInterval(interval_ms)
    
    def set_auto_interval(self, auto: bool = True):
        """设置自动间隔模式"""
        self._auto_interval = auto
        if auto and self._timer and self._is_running:
            self._timer.setInterval(self._get_current_interval())
    
    def _get_current_interval(self) -> int:
        """获取当前应有的更新间隔"""
        if not self._auto_interval and self._interval_ms:
            return self._interval_ms
        
        # 自动根据交易时段调整
        if self.is_trading_time():
            return chart_cfg.stockKlineUpdateInterval.value
        elif self.is_pre_market():
            return self.PRE_MARKET_INTERVAL
        else:
            return self.AFTER_MARKET_INTERVAL
    
    def is_trading_time(self) -> bool:
        """
        判断当前是否在A股交易时段
        
        Returns:
            bool: 是否在交易时段
        """
        now = datetime.now()
        current_time = now.time()
        
        # 上午交易时段
        is_morning = self.MORNING_START <= current_time <= self.MORNING_END
        
        # 下午交易时段
        is_afternoon = self.AFTERNOON_START <= current_time <= self.AFTERNOON_END
        
        return is_morning or is_afternoon
    
    def is_pre_market(self) -> bool:
        """
        判断当前是否在盘前时段（开盘前30分钟）
        
        Returns:
            bool: 是否在盘前时段
        """
        now = datetime.now()
        current_time = now.time()
        
        # 盘前时段：9:00 - 9:30
        pre_market_start = dt_time(9, 0)
        pre_market_end = self.MORNING_START
        
        return pre_market_start <= current_time < pre_market_end
    
    def _on_timeout(self):
        """定时器超时回调"""
        if self.stock_api is None:
            return
        
        # 检查交易时段变化
        current_trading = self.is_trading_time()
        
        # 动态调整间隔
        if self._auto_interval:
            current_interval = self._get_current_interval()
            if self._timer.interval() != current_interval:
                self._timer.setInterval(current_interval)
                # status_change = "进入交易时段" if current_trading else "离开交易时段"
                # print(f"[StockApiQTimer] {status_change}，调整间隔为 {current_interval}ms")
        
        self._last_trading_status = current_trading
        
        # 非交易时段：跳过数据更新（但保持定时器运行以检测时段变化）
        if not current_trading:
            # 盘前时段：准备更新，但不请求实时数据
            if self.is_pre_market():
                # 可以在这里做一些盘前准备工作
                pass
            return
        
        try:
            # 调用 wait_update 更新数据缓存（图表由 ChartUpdateManager 独立定时器驱动）
            self.stock_api.wait_update()
        except Exception as e:
            print(f"[StockApiQTimer] wait_update 错误: {e}")
    
    def is_running(self) -> bool:
        """检查定时器是否运行"""
        return self._is_running
    
    def get_update_count(self) -> int:
        """获取更新次数"""
        return self._update_count
    
    def get_trading_status(self) -> str:
        """获取当前交易状态描述"""
        if self.is_trading_time():
            return "交易时段"
        elif self.is_pre_market():
            return "盘前时段"
        else:
            return "非交易时段"
    
    def pause(self):
        """暂停定时器（保持运行状态但不更新数据）"""
        if self._timer:
            self._timer.stop()
    
    def resume(self):
        """恢复定时器"""
        if self._timer and self._is_running:
            interval = self._get_current_interval()
            self._timer.start(interval)