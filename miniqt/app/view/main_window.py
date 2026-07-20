# coding: utf-8
from __future__ import annotations
import os
import time
import traceback
import sys
import io
from functools import partial
from typing import TYPE_CHECKING, Optional, Any

from PyQt6.QtCore import Qt, QLocale, QTranslator, pyqtSignal, QUrl, QSize, QTimer, QPoint, QThread, QMutex, QObject
from PyQt6.QtGui import QIcon, QDesktopServices, QColor, QCursor, QAction
from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QMenu
from PyQt6.QtWebEngineWidgets import QWebEngineView

from qfluentwidgets import (NavigationItemPosition, setTheme, Theme, FluentWindow, TransparentToolButton,
                            setThemeColor, FluentIcon, RoundMenu, InfoBar, InfoBarPosition,
                            NavigationAvatarWidget, qrouter, SubtitleLabel, setFont, InfoBadge,
                            SingleDirectionScrollArea, FluentTranslator, FlyoutAnimationType,
                            InfoBadgePosition, FluentBackgroundTheme, MSFluentTitleBar, RoundMenu,
                            Action, PushButton, MessageBox,
                            SplashScreen, isDarkTheme, TransparentToolButton, TabBar,
                            TransparentDropDownToolButton, TextEdit, MessageDialog)
from qfluentwidgets import FluentIcon as FIF

from .utils import FixedSizeQueue
from .home_interface import HomeInterface
from .gallery_interface import GalleryInterface
from .market_quote_interface import MarketQuoteInterface  # 步骤6
from .setting_interface import SettingInterface  # 步骤5启用
from ..windows.strategy_backtest_window import StrategyBacktestWindow  # 步骤7
from ..login.LoginWindow import LoginWindow
from ..common.config import ZH_SUPPORT_URL, EN_SUPPORT_URL, cfg
from ..common.icon import Icon
from ..common.signal_bus import signalBus
from ..common.translator import Translator
from ..common.tq_object import TqObject
from ..common import resource

if TYPE_CHECKING:
    from tqsdk import TqApi
    from ..common.stock_api import StockApi
    from ..common.stock_api_qtimer import StockApiQTimer
    import minibt
    from ..windows.chart_interface import Chart
MarketWatchWindow=None

# =============================================================================
# 辅助类
# =============================================================================

class OutputRedirector:
    """输出重定向器，用于捕获print输出"""
    def __init__(self, write_callback):
        self.write_callback = write_callback

    def write(self, text):
        if text.strip():
            self.write_callback(text)

    def flush(self):
        pass


class TerminalOutputWindow(SingleDirectionScrollArea):
    """终端输出窗口"""
    def __init__(self, parent=None):
        super().__init__(parent=parent, orient=Qt.Orientation.Vertical)
        self.setObjectName("terminal_output_window")
        self.output_text = TextEdit(self)
        self.output_text.setReadOnly(True)
        self.setWidget(self.output_text)
        self._redirector = OutputRedirector(self._append_text)

    def _append_text(self, text):
        self.output_text.append(text)
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


class AdvancedWebBrowserWindow(QWebEngineView):
    """高级网页浏览器窗口"""
    def __init__(self, url: str = "https://www.minibt.cn", parent=None):
        super().__init__(parent)
        self.url = url
        self.setObjectName("official_website")
        self.load_url()

    def load_url(self):
        self.load(QUrl(self.url))

class MiniBtInitWorker(QObject):
    """MiniBt初始化工作线程，在后台执行耗时的导入和指标数据加载"""
    
    init_finished = pyqtSignal(object, dict)
    init_failed = pyqtSignal(str)
    
    def run(self):
        """在后台线程执行初始化"""
        try:
            import minibt
            indicator_data = self._load_indicator_data(minibt)
            self.init_finished.emit(minibt, indicator_data)
        except Exception as e:
            error_msg = f"minibt初始化失败: {e}"
            print(error_msg)
            self.init_failed.emit(error_msg)
    
    def _load_indicator_data(self, minibt):
        """加载指标数据（在后台线程执行）"""
        indicator_data = {}
        try:
            if not hasattr(minibt, 'IndicatorClass'):
                print("minibt模块没有IndicatorClass属性，无法加载指标数据")
                return indicator_data

            IndicatorClass = minibt.IndicatorClass
            for attr_name in dir(IndicatorClass):
                if not attr_name.startswith('_') and attr_name not in ["Pair", "Factors", "FinTa", "TuLip"]:
                    attr = getattr(IndicatorClass, attr_name)
                    if hasattr(attr, '__class__') and attr.__class__.__name__ == 'type':
                        NON_KLINE_INDICATORS = []
                        if hasattr(attr, 'NON_KLINE_INDICATORS'):
                            NON_KLINE_INDICATORS = attr.NON_KLINE_INDICATORS
                        class_name = attr_name
                        indicators = []
                        for indicator_name in dir(attr):
                            if not indicator_name.startswith('_') and indicator_name not in NON_KLINE_INDICATORS:
                                try:
                                    indicator = getattr(attr, indicator_name)
                                    if callable(indicator):
                                        doc = indicator.__doc__ if indicator.__doc__ else ""
                                        indicators.append([indicator_name, doc])
                                except Exception:
                                    continue
                        indicator_data[class_name] = indicators
            
            tradingview = minibt.indicators.tradingview.TradingView
            indicators = []
            for indicator_name in dir(tradingview):
                if not indicator_name.startswith('_'):
                    try:
                        indicator = getattr(tradingview, indicator_name)
                        if callable(indicator):
                            doc = indicator.__doc__ if indicator.__doc__ else ""
                            indicators.append([indicator_name, doc])
                    except Exception:
                        continue
            indicator_data["TradingView"] = indicators
            
            #print(f"成功加载指标数据，共 {len(indicator_data)} 个指标类")
        except Exception as e:
            print(f"加载指标数据失败: {e}")
            import traceback
            traceback.print_exc()
        
        return indicator_data


class MiniBtObject(QObject):
    """MiniBt对象，用于管理指标信息"""
    
    initialized = pyqtSignal()

    def __init__(self, minibt: Any, indicator_data: dict = None):
        super().__init__()
        self.minibt :minibt= minibt
        if indicator_data is not None:
            self.indicator_data = indicator_data
        else:
            self.indicator_data = {}
            self._load_indicator_data()

    def _load_indicator_data(self):
        """加载指标数据"""
        try:
            if not hasattr(self.minibt, 'IndicatorClass'):
                print("minibt模块没有IndicatorClass属性，无法加载指标数据")
                return

            IndicatorClass = self.minibt.IndicatorClass
            # 遍历IndicatorClass的所有属性
            for attr_name in dir(IndicatorClass):
                if not attr_name.startswith('_') and attr_name not in  ["Pair","Factors","FinTa","TuLip"]:
                    attr = getattr(IndicatorClass, attr_name)
                    
                    # 检查是否是类
                    if hasattr(attr, '__class__') and attr.__class__.__name__ == 'type':
                        NON_KLINE_INDICATORS=[]
                        if hasattr(attr, 'NON_KLINE_INDICATORS'):
                            NON_KLINE_INDICATORS = attr.NON_KLINE_INDICATORS
                        # 获取类名作为键
                        class_name = attr_name
                        # 获取指标信息
                        indicators = []
                        # 遍历类的属性，获取指标名称和文档
                        for indicator_name in dir(attr):
                            if not indicator_name.startswith('_') and indicator_name not in NON_KLINE_INDICATORS:
                                try:
                                    indicator = getattr(attr, indicator_name)
                                    # 检查是否是函数或方法
                                    if callable(indicator):
                                        # 获取文档
                                        doc = indicator.__doc__ if indicator.__doc__ else ""
                                        indicators.append(
                                            [indicator_name, doc])
                                except Exception as e:
                                    # 某些属性可能无法访问，跳过
                                    # print(f"跳过属性 {indicator_name}: {e}")
                                    continue
                        # 存储到字典中
                        self.indicator_data[class_name] = indicators
            tradingview = self.minibt.indicators.tradingview.TradingView
            # 获取指标信息
            indicators = []
            # 遍历类的属性，获取指标名称和文档
            for indicator_name in dir(tradingview):
                if not indicator_name.startswith('_'):
                    try:
                        indicator = getattr(tradingview, indicator_name)
                        # 检查是否是函数或方法
                        if callable(indicator):
                            # 获取文档
                            doc = indicator.__doc__ if indicator.__doc__ else ""
                            indicators.append(
                                [indicator_name, doc])
                    except Exception as e:
                        # 某些属性可能无法访问，跳过
                        # print(f"跳过属性 {indicator_name}: {e}")
                        continue
            # 存储到字典中
            self.indicator_data["TradingView"] = indicators
                        # print(f"类 {class_name} 加载了 {len(indicators)} 个指标")

            # print(f"成功加载指标数据，共 {len(self.indicator_data)} 个指标类")
            # 打印每个类的指标数量
            # for class_name, indicators in self.indicator_data.items():
                # print(f"  - {class_name}: {len(indicators)} 个指标")
        except Exception as e:
            print(f"加载指标数据失败: {e}")
            import traceback
            traceback.print_exc()

    def get_indicator_classes(self):
        """获取所有指标类名"""
        return list(self.indicator_data.keys())

    def get_indicators(self, class_name):
        """获取指定类的指标列表"""
        return self.indicator_data.get(class_name, [])

# =============================================================================
# ChartUpdateManager
# =============================================================================

class ChartUpdateManager:
    """
    全局图表更新管理器
    负责管理所有图表的更新，使用共享线程池避免线程过多
    """
    _instance = None
    is_update_status = True

    def __new__(cls, main_window=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_manager(main_window)
        return cls._instance

    def _init_manager(self, main_window=None):
        """初始化管理器"""
        from concurrent.futures import ThreadPoolExecutor
        from ..common.chart_config import chart_cfg

        # 主窗口引用
        self.main_window = main_window

        # 线程池，限制最大线程数
        self.max_workers = chart_cfg.maxWorkers.value
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # 图表列表
        self.charts: list[Chart] = []
        self.chart_lock = QMutex()

        # 轮询索引
        self.kline_index = 0      # K线更新索引
        self.indicator_index = 0  # 期货指标更新索引
        self.stock_indicator_index = 0  # 股票指标更新索引

        # 调度定时器
        self.kline_timer = QTimer()
        self.kline_timer.timeout.connect(self._update_kline)
        self.kline_interval = chart_cfg.klineUpdateInterval.value  # 期货K线更新间隔（毫秒）
        
        # 股票专用定时器（更低的更新频率，避免IP封禁）
        self.stock_kline_timer = QTimer()
        self.stock_kline_timer.timeout.connect(self._update_stock_kline)
        self.stock_kline_interval = chart_cfg.stockKlineUpdateInterval.value
        
        self.indicator_timer = QTimer()
        self.indicator_timer.timeout.connect(self._update_indicator)
        self.indicator_interval = chart_cfg.indicatorUpdateInterval.value  # 指标更新间隔（毫秒）
        
        # 股票专用指标定时器
        self.stock_indicator_timer = QTimer()
        self.stock_indicator_timer.timeout.connect(self._update_stock_indicator)
        self.stock_indicator_interval = chart_cfg.stockIndicatorUpdateInterval.value

    def start(self):
        """启动更新管理器"""
        self.kline_timer.start(self.kline_interval)
        self.stock_kline_timer.start(self.stock_kline_interval)
        self.indicator_timer.start(self.indicator_interval)
        self.stock_indicator_timer.start(self.stock_indicator_interval)

    def stop(self):
        """停止更新管理器"""
        self.kline_timer.stop()
        self.stock_kline_timer.stop()
        self.indicator_timer.stop()
        self.stock_indicator_timer.stop()
        self.executor.shutdown(wait=True)
        # print("图表更新管理器已停止")

    def add_chart(self, chart):
        """
        添加图表到更新队列
        :param chart: Chart实例
        """
        self.chart_lock.lock()
        try:
            if chart not in self.charts:
                self.charts.append(chart)
                # print(f"图表已添加到更新管理器，当前图表数: {len(self.charts)}")
        finally:
            self.chart_lock.unlock()

    def remove_chart(self, chart: Chart):
        """
        从更新队列中移除图表
        :param chart: Chart实例
        """
        self.chart_lock.lock()
        try:
            if chart in self.charts:
                self.charts.remove(chart)
                # print(f"图表已从更新管理器移除，当前图表数: {len(self.charts)}")
        finally:
            self.chart_lock.unlock()

    def _update_kline(self):
        """更新期货K线数据"""
        if not self.is_update_status:
            return

        self.chart_lock.lock()
        charts = [c for c in self.charts if not getattr(c, 'is_stock', False)]
        self.chart_lock.unlock()

        if not charts:
            return

        for chart in charts:
            self._update_chart_kline(chart)
    
    def _update_stock_kline(self):
        """更新股票K线数据（更低频率，避免IP封禁）"""
        if not self.is_update_status:
            return

        self.chart_lock.lock()
        charts = [c for c in self.charts if getattr(c, 'is_stock', False)]
        self.chart_lock.unlock()

        if not charts:
            return

        # 检查是否在股票交易时段
        if not self._is_stock_trading_time():
            return

        for chart in charts:
            self._update_chart_kline(chart)
    
    def _all_charts_are_stock(self, charts) -> bool:
        """检查所有图表是否都是股票图表"""
        for chart in charts:
            if not hasattr(chart, 'is_stock') or not chart.is_stock:
                return False
        return True
    
    def _is_stock_trading_time(self) -> bool:
        """检查是否在股票交易时段"""
        if hasattr(self.main_window, 'stock_api') and self.main_window.stock_api:
            return self.main_window.stock_api.is_trading_time()
        return True

    def _update_indicator(self):
        """更新期货指标数据"""
        if not self.is_update_status:
            return

        self.chart_lock.lock()
        charts = [c for c in self.charts if not getattr(c, 'is_stock', False)]
        self.chart_lock.unlock()

        if not charts:
            return

        # 轮询更新指标
        if charts:
            index = self.indicator_index % len(charts)
            chart = charts[index]
            self._update_chart_indicator(chart)
            self.indicator_index = (self.indicator_index + 1) % len(charts)
    
    def _update_stock_indicator(self):
        """更新股票指标数据（更低频率）"""
        if not self.is_update_status:
            return

        self.chart_lock.lock()
        charts = [c for c in self.charts if getattr(c, 'is_stock', False)]
        self.chart_lock.unlock()

        if not charts:
            return

        # 检查是否在股票交易时段
        if not self._is_stock_trading_time():
            return

        # 轮询更新指标
        if charts:
            index = self.stock_indicator_index % len(charts)
            chart = charts[index]
            self._update_chart_indicator(chart)
            self.stock_indicator_index = (self.stock_indicator_index + 1) % len(charts)

    def _update_chart_kline(self, chart):
        """
        更新单个图表的K线数据
        :param chart: Chart实例
        """
        try:
            # 提交到线程池处理
            future = self.executor.submit(self._process_chart_kline, chart)
            future.add_done_callback(lambda f: self._on_update_done(chart, f))
        except Exception as e:
            print(f"更新K线时出错: {str(e)}")

    def _update_chart_indicator(self, chart: Chart):
        """
        更新单个图表的指标数据
        :param chart: Chart实例
        """
        try:
            # 提交到线程池处理
            future = self.executor.submit(self._process_chart_indicator, chart)
            future.add_done_callback(lambda f: self._on_update_done(chart, f))
        except Exception as e:
            print(f"更新指标时出错: {str(e)}")

    def _process_chart_kline(self, chart: Chart):
        """
        在工作线程中处理K线更新
        :param chart: Chart实例
        """
        try:
            # 检查图表是否正在重新加载
            if chart._is_reloading:
                #print(f"图表 {chart.symbol} 正在重新加载，跳过本次K线更新任务")
                return False

            # 执行K线数据获取和计算
            chart.chart_updater._fetch_and_process_kline()
            return True
        except Exception as e:
            traceback.print_exc()
            print(f"处理K线更新时出错: {str(e)}")
            return False

    def _process_chart_indicator(self, chart: Chart):
        """
        在工作线程中处理指标更新
        :param chart: Chart实例
        """
        try:
            # 检查图表是否正在重新加载
            if chart._is_reloading:
                #print(f"图表 {chart.symbol} 正在重新加载，跳过本次指标更新任务")
                return False

            # 执行指标数据获取和计算
            chart.chart_updater._fetch_and_process_indicator()
            return True
        except Exception as e:
            traceback.print_exc()
            print(f"处理指标更新时出错: {str(e)}")
            return False

    def _on_update_done(self, chart: Chart, future: Future[bool]):
        """
        更新完成回调
        :param chart: Chart实例
        :param future: Future对象
        """
        try:
            success = future.result()
            if not success:
                # 如果更新失败，可能需要从队列中移除
                self.remove_chart(chart)
        except Exception as e:
            print(f"更新完成回调出错: {str(e)}")
    
    def request_stock_update(self):
        """
        请求股票图表更新
        由 StockApiQTimer 调用，用于更新股票图表
        """
        self.chart_lock.lock()
        charts = self.charts.copy()
        self.chart_lock.unlock()
        
        if not charts:
            return
        
        # 只更新股票图表
        for chart in charts:
            if hasattr(chart, 'is_stock') and chart.is_stock:
                self._update_chart_kline(chart)

    def get_chart_count(self):
        """
        获取当前图表数量
        :return: 图表数量
        """
        self.chart_lock.lock()
        count = len(self.charts)
        self.chart_lock.unlock()
        return count


# =============================================================================
# UpdateContQuotesThread
# =============================================================================

class UpdateContQuotesThread(QThread):
    """更新主力合约列表的线程"""

    def __init__(self, main_window):
        super().__init__()
        self.main_window: "MainWindow" = main_window
        self.updated = False

    def run(self):
        """执行更新任务"""
        try:
            # 注意：TqApi需要在主线程中运行，所以这里只设置标志
            # 实际更新在主线程中通过信号触发
            self.main_window.tq_object.update_cont_quotes()
        except Exception as e:
            print(f"更新主力合约列表失败: {e}")
            import traceback
            traceback.print_exc()


# =============================================================================
# CustomTitleBar
# =============================================================================

class CustomTitleBar(MSFluentTitleBar):
    """自定义标题栏，带标签栏和菜单"""

    def __init__(self, parent, width=36):
        super().__init__(parent)
        self.main_window: MainWindow = parent
        self.qobject: dict[str, QWidget] = dict()
        self.setFixedHeight(width)
        self.iconLabel.setFixedSize(32, 32)

        # 设置窗口图标
        logo_path = os.path.join(self.main_window.base_dir, 'app', 'resource', 'images', 'logo.png')
        if os.path.exists(logo_path):
            from PyQt6.QtGui import QPixmap, QTransform
            pixmap = QPixmap(logo_path)
            # 使用 QTransform 垂直翻转图片（倒置）
            transform = QTransform()
            transform.scale(-1, -1)  # 垂直翻转
            pixmap = pixmap.transformed(transform)
            self.iconLabel.setPixmap(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        # 菜单按钮
        self.toolButtonLayout = QHBoxLayout()
        color = QColor(206, 206, 206) if isDarkTheme() else QColor(96, 96, 96)
        self.menuButton = TransparentToolButton(FluentIcon.MENU.icon(color=color), self)
        self.menuButton.clicked.connect(lambda: self.createMenu())
        self.toolButtonLayout.setContentsMargins(0, 0, 0, 0)
        self.toolButtonLayout.addWidget(self.menuButton)
        self.hBoxLayout.insertLayout(4, self.toolButtonLayout)

        # 标签栏
        self.tabBar = TabBar(self)
        self.tabBar.itemLayout.setContentsMargins(0, 0, 0, 0)
        self.tabBar.setFixedHeight(width - 2)
        self.tabBar.setTabMaximumWidth(220)
        self.tabBar.setMovable(True)
        self.tabBar.setScrollable(True)
        self.tabBar.setTabShadowEnabled(True)
        # self.tabBar.currentChanged.connect(lambda i: print(self.tabBar.tabText(i)))
        self.hBoxLayout.insertWidget(5, self.tabBar, 1)
        self.hBoxLayout.setStretch(6, 0)
        self.hBoxLayout.insertSpacing(7, 0)

        # 在添加所有子控件后重新应用样式
        from qfluentwidgets import FluentStyleSheet
        FluentStyleSheet.FLUENT_WINDOW.apply(self)

        self.connectSignalToSlot()

    def canDrag(self, pos: QPoint):
        if not super().canDrag(pos):
            return False
        pos.setX(pos.x() - self.tabBar.x())
        return not self.tabBar.tabRegion().contains(pos)

    def addSubInterface(self, widget: QWidget, objectName, text, icon):
        widget.setObjectName(objectName)
        self.main_window.stackedWidget.addWidget(widget)
        self.tabBar.addTab(
            routeKey=objectName,
            text=text,
            icon=icon,
            onClick=lambda: self.main_window.stackedWidget.setCurrentWidget(widget)
        )
        self.tabBar.setTabToolTip(len(self.tabBar.items) - 1, text)
        self.tabBar.items[-1].setFixedWidth(160)
        self.qobject.update({objectName: widget})

    def addTab(self, widget: QWidget):
        name = widget.objectName()
        if hasattr(widget, "symbol"):
            name = f"{widget.symbol}"
        route_key = f"{name}{len(self.qobject)}"
        self.qobject.update({route_key: widget})
        self.addSubInterface(
            widget, route_key, name, QIcon())
        self._safe_set_current_widget(widget)

    def connectSignalToSlot(self):
        self.tabBar.tabCloseRequested.connect(self.removeTab)
        self.main_window.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        if hasattr(self.tabBar, 'addButton') and self.tabBar.addButton:
            self.tabBar.addButton.clicked.connect(self.createAddMenu)

    def onCurrentIndexChanged(self, index):
        widget = self.main_window.stackedWidget.widget(index)
        if not widget:
            return
        self.tabBar.setCurrentTab(widget.objectName())
        qrouter.push(self.main_window.stackedWidget, widget.objectName())

    def removeTab(self, index):
        item = self.tabBar.tabItem(index)
        if not item:
            return
        route_key = item.routeKey()
        widget = self.qobject.pop(route_key, None)
        if widget:
            self.main_window.stackedWidget.removeWidget(widget)
            self.tabBar.removeTab(index)
            # 关闭 widget，触发 closeEvent → Chart.cleanup() → 停止 worker + 清理指标
            widget.close()
            widget.deleteLater()
            # 如果没有 tab 了，跳转到主页
            if self.tabBar.count() == 0:
                self.main_window._navigateTo(self.main_window.homeInterface)

    # ---- 菜单 ----

    def login(self, is_stock):
        """登录窗口"""
        self._login_window = LoginWindow(self.main_window, is_stock)
        self._login_window.exec()
        self._login_window = None

    def createMenu(self):
        menu = RoundMenu(parent=self)

        logaction = Action(FluentIcon.COPY, self.tr('期货登录'))
        logaction.triggered.connect(partial(self.login, is_stock=False))
        menu.addAction(logaction)
        cut = Action(FluentIcon.CUT, self.tr('股票登录'))
        cut.triggered.connect(partial(self.login, is_stock=True))
        menu.addAction(cut)

        pos = QCursor.pos()
        self.menuButton.mapToGlobal(pos)
        menu.exec(pos, ani=True)

    def createAddMenu(self):
        """创建添加菜单"""
        menu = RoundMenu(parent=self)

        # 主力合约子菜单
        if hasattr(self.main_window, 'marketQuoteInterface'):
            main_contracts = self.main_window.marketQuoteInterface.get_main_contracts()
            if main_contracts:
                cont_menu = RoundMenu(self.tr("主力合约"), self)
                cont_menu.setIcon(FluentIcon.BOOK_SHELF)
                for exchange, contracts in main_contracts.items():
                    if contracts:
                        exchange_menu = RoundMenu(exchange, self)
                        for contract in contracts:
                            action = Action(contract)
                            action.triggered.connect(
                                lambda checked, c=contract: self.main_window.start_minibt_chart(c))
                            exchange_menu.addAction(action)
                        cont_menu.addMenu(exchange_menu)
                menu.addMenu(cont_menu)

        menu.addSeparator()

        # 终端窗口
        terminal_action = Action(FluentIcon.CODE, self.tr('终端窗口'))
        terminal_action.triggered.connect(self.showTerminalWindow)
        menu.addAction(terminal_action)

        # Jupyter窗口
        jupyter_action = Action(FluentIcon.CODE, self.tr('Jupyter窗口'))
        jupyter_action.triggered.connect(self.showJupyterWindow)
        menu.addAction(jupyter_action)

        # JupyterLab窗口
        jupyterlab_action = Action(FluentIcon.CODE, self.tr('JupyterLab窗口'))
        jupyterlab_action.triggered.connect(self.showJupyterLabWindow)
        menu.addAction(jupyterlab_action)

        menu.addSeparator()

        # Pi Agent 窗口（AI 编程助手）
        pi_agent_action = Action(FluentIcon.ROBOT, self.tr('Pi Agent (AI助手)'))
        pi_agent_action.triggered.connect(self.showPiAgentWindow)
        menu.addAction(pi_agent_action)

        # 显示菜单
        if hasattr(self.tabBar, 'addButton') and self.tabBar.addButton:
            pos = self.tabBar.addButton.mapToGlobal(self.tabBar.addButton.rect().bottomLeft())
            menu.exec(pos, ani=True)

    def showTerminalWindow(self):
        """显示终端窗口"""
        terminal_window = self.qobject.get("TerminalWindow")
        if not terminal_window:
            from ..windows.powershell_terminal import LocalTerm
            terminal_window = LocalTerm(self.main_window, is_dark_theme=isDarkTheme())
            self.addSubInterface(
                terminal_window, "TerminalWindow", "终端", FluentIcon.CODE)
        self._safe_set_current_widget(terminal_window)

    def showJupyterWindow(self):
        """显示Jupyter窗口"""
        jupyter_window = self.qobject.get("JupyterWindow")
        if not jupyter_window:
            try:
                from ..windows.jupyter_window import JupyterWindow as Jw
            except ImportError:
                print("Jupyter窗口模块不可用")
                return
            jupyter_window = Jw(self.main_window, is_dark_theme=isDarkTheme())
            self.addSubInterface(
                jupyter_window, "JupyterWindow", "Jupyter", FluentIcon.BOOK_SHELF)
        self._safe_set_current_widget(jupyter_window)

    def showJupyterLabWindow(self):
        """显示JupyterLab窗口"""
        jupyterlab_window = self.qobject.get("JupyterLabWindow")
        if not jupyterlab_window:
            try:
                from ..windows.jupyterlab_window import JupyterLabWindow as Jlw
            except ImportError:
                print("JupyterLab窗口模块不可用")
                return
            jupyterlab_window = Jlw(self.main_window)
            self.addSubInterface(
                jupyterlab_window, "JupyterLabWindow", "JupyterLab", FluentIcon.BOOK_SHELF)
        self._safe_set_current_widget(jupyterlab_window)

    def showPiAgentWindow(self):
        """显示 Pi Agent 窗口（AI 编程助手）"""
        pi_agent_window = self.qobject.get("PiAgentWindow")
        if not pi_agent_window:
            try:
                from ..windows.pi_agent_window import PiAgentWindow
            except ImportError as e:
                print(f"Pi Agent 窗口模块不可用: {e}")
                return
            pi_agent_window = PiAgentWindow(self.main_window)
            self.addSubInterface(
                pi_agent_window, "PiAgentWindow", "Pi Agent", FluentIcon.ROBOT)
            # 连接主题变化信号，自动同步 pi-web 主题
            cfg.themeMode.valueChanged.connect(lambda: pi_agent_window.sync_theme())
        self._safe_set_current_widget(pi_agent_window)

    def _safe_set_current_widget(self, widget):
        """安全切换当前 widget，处理 qfluentwidgets 滑动动画的兼容性问题"""
        try:
            self.main_window.stackedWidget.setCurrentWidget(widget)
        except TypeError:
            index = self.main_window.stackedWidget.indexOf(widget)
            if index >= 0:
                self.main_window.stackedWidget.setCurrentIndex(index)


# =============================================================================
# TqApiQTimer
# =============================================================================

class TqApiQTimer(QTimer):
    """天勤API定时器"""
    update_status_changed = pyqtSignal(bool)

    def __init__(self, parent: MainWindow = None):
        super().__init__(parent)
        self.main_window = parent
        self.setInterval(50)
        self.setSingleShot(False)
        self.update_queue = FixedSizeQueue(10, self.init_update())
        self._last_is_update = self.update_queue.any
        self.timeout.connect(self.wait_update)
        self.start()

    def init_update(self) -> bool:
        count = 0
        is_update = False
        start_time = time.time()
        while count < 100 and (time.time() - start_time) < 1.0:
            is_update = self.api.wait_update(1)
            count += 1
            if is_update:
                break
        return is_update

    @property
    def api(self) -> TqApi:
        return self.main_window.tq_api

    def wait_update(self) -> bool:
        is_update = self.main_window.tq_api.wait_update(1)
        if is_update:
            self.update_queue.add(is_update)
            current_is_update = True
        else:
            current_is_update = self._last_is_update

        if current_is_update != self._last_is_update:
            self._last_is_update = current_is_update
            self.update_status_changed.emit(current_is_update)
        return current_is_update

    @property
    def is_update(self) -> bool:
        return self._last_is_update


# =============================================================================
# MainWindow
# =============================================================================

def _pop(self):
    """ pop history """
    if not self.history:
        return

    item = self.history.pop()
    self.emptyChanged.emit(not bool(self.history))

    # 检查 stacked 对象是否已被删除
    try:
        # 尝试访问 stacked 对象，如果已被删除会抛出 RuntimeError
        if item.stacked is None:
            return
        # 检查对象是否有效
        item.stacked.objectName()
    except RuntimeError:
        # 对象已被删除，清理对应的历史记录
        if item.stacked in self.stackHistories:
            del self.stackHistories[item.stacked]
        return

    # 调用 StackedHistory.pop()
    try:
        if item.stacked in self.stackHistories:
            self.stackHistories[item.stacked].pop()
    except RuntimeError:
        # 如果 pop 过程中出错，清理历史记录
        if item.stacked in self.stackHistories:
            del self.stackHistories[item.stacked]

class MainWindow(FluentWindow):

    updateStatusChanged = pyqtSignal(bool)

    tq_api: Optional[TqApi] = None
    tq_object: Optional[TqObject] = None
    tq_api_qtimer: Optional[TqApiQTimer] = None
    stock_api: Optional['StockApi'] = None  # 股票数据API
    stock_api_qtimer: Optional['StockApiQTimer'] = None  # 股票API定时器
    _is_update: bool = False
    _is_update_mutex = QMutex()
    login_status: dict[str, bool] = {}
    chart_update_manager: Optional[ChartUpdateManager] = None

    def __init__(self):
        super().__init__()
        # 使用 lambda 包装 _pop 方法，避免 clicked 信号的 bool 参数被当作 self
        history = self.navigationInterface.panel.history
        history.pop = lambda: _pop(history)
        # 断开原有连接（使用 try-except 防止警告）
        try:
            self.navigationInterface.panel.returnButton.clicked.disconnect()
        except:
            pass
        self.navigationInterface.panel.returnButton.clicked.connect(history.pop)
        
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        # self.datas_path = os.path.join(self.base_dir, 'app', 'download', 'datas')
        self.title_height = 36
        self.setTitleBar(CustomTitleBar(self, self.title_height))
        self.titleBar: CustomTitleBar
        self.tabBar = self.titleBar.tabBar
        self.titleBar.tabBar.setMinimumHeight(self.title_height)
        self.widgetLayout.setContentsMargins(0, self.title_height, 0, 0)
        self.initWindow()

        # create sub interfaces — 只保留需要迁移的
        self.homeInterface = HomeInterface(self)
        self.marketQuoteInterface = MarketQuoteInterface(self)  # 步骤6
        self.settingInterface = SettingInterface(self)  # 步骤5
        self.strategyBacktestWindow = StrategyBacktestWindow(self)  # 步骤7

        # 初始化天勤对象
        self.tq_object = TqObject(self)

        # 图表窗口列表
        self.charts: list = []

        # 延迟初始化图表更新管理器，避免启动时耗时过长
        self.chart_update_manager = None

        self.connectSignalToSlot()

        # add items to navigation interface
        self.initNavigation()
        self.splashScreen.finish()
        self.setMicaEffectEnabled(False)
        
        # 延迟初始化耗时操作
        QTimer.singleShot(100, self._delayed_init)
        
    def _delayed_init(self):
        """延迟初始化耗时操作"""
        # 初始化图表更新管理器
        if self.chart_update_manager is None:
            self.chart_update_manager = ChartUpdateManager(main_window=self)
            self.chart_update_manager.start()
            # print("图表更新管理器已延迟初始化")
        
        # 尝试导入 minibt
        self._try_init_minibt_object()
        
    def _try_init_minibt_object(self):
        """尝试在后台线程异步导入并初始化 MiniBtObject"""
        self._minibt_init_thread = QThread()
        self._minibt_worker = MiniBtInitWorker()
        self._minibt_worker.moveToThread(self._minibt_init_thread)
        
        self._minibt_init_thread.started.connect(self._minibt_worker.run)
        self._minibt_worker.init_finished.connect(self._on_minibt_init_finished)
        self._minibt_worker.init_failed.connect(self._on_minibt_init_failed)
        self._minibt_init_thread.finished.connect(self._minibt_worker.deleteLater)
        self._minibt_init_thread.finished.connect(self._minibt_init_thread.deleteLater)
        
        self._minibt_init_thread.start()
        #print("[MiniBt] 开始在后台线程初始化 minibt 模块")

    def _on_minibt_init_finished(self, minibt, indicator_data):
        """minibt 初始化完成回调（在主线程执行）"""
        self.minibt_object = MiniBtObject(minibt, indicator_data)
        self._minibt_init_thread.quit()
        #print("[MiniBt] minibt 模块初始化完成")

    def _on_minibt_init_failed(self, error_msg):
        """minibt 初始化失败回调"""
        #print(f"[MiniBt] {error_msg}")
        self._minibt_init_thread.quit()
    
    def add_chart_to_updater(self, chart):
        """
        添加图表到更新管理器
        :param chart: Chart实例
        """
        if self.chart_update_manager:
            self.chart_update_manager.add_chart(chart)

    def remove_chart_from_updater(self, chart):
        """
        从更新管理器移除图表
        :param chart: Chart实例
        """
        if self.chart_update_manager:
            self.chart_update_manager.remove_chart(chart)

    def connectSignalToSlot(self):
        signalBus.micaEnableChanged.connect(self.setMicaEffectEnabled)
        signalBus.switchToSampleCard.connect(self.switchToSample)
        signalBus.supportSignal.connect(self.onSupport)

        # 连接使用本地数据设置变更信号
        cfg.useLocalDataChanged.connect(self.onUseLocalDataChanged)

        # 连接TqObject的主力合约更新信号到行情窗口
        if self.tq_object and self.marketQuoteInterface:
            self.tq_object.cont_quotes_updated.connect(
                self.marketQuoteInterface.on_cont_quotes_updated)

    def initNavigation(self):
        t = Translator()

        # ---- 导航项（只保留4项） ----
        self.addSubInterface(self.homeInterface, FIF.HOME, self.tr('Home'))

        # TODO 步骤6: 行情报价
        self.addSubInterface(self.marketQuoteInterface, FIF.DOCUMENT, "行情报价")

        # TODO 步骤7: 策略回测
        self.addSubInterface(self.strategyBacktestWindow, FIF.CODE, "策略回测")

        # ---- 以下为非迁移导航项，已注释 ----
        # self.addSubInterface(self.iconInterface, FIF.INFO, t.icons)
        # self.addSubInterface(self.basicInputInterface, FIF.CHECKBOX, t.basicInput)
        # self.addSubInterface(self.dateTimeInterface, FIF.DATE_TIME, t.dateTime)
        # self.addSubInterface(self.dialogInterface, FIF.MESSAGE, t.dialogs)
        # self.addSubInterface(self.layoutInterface, FIF.LAYOUT, t.layout)
        # self.addSubInterface(self.materialInterface, FIF.PALETTE, t.material)
        # self.addSubInterface(self.menuInterface, Icon.MENU, t.menus)
        # self.addSubInterface(self.navigationViewInterface, FIF.MENU, t.navigation)
        # self.addSubInterface(self.scrollInterface, FIF.SCROLL, t.scroll)
        # self.addSubInterface(self.statusInfoInterface, FIF.CHAT, t.statusInfo)
        # self.addSubInterface(self.textInterface, Icon.TEXT, t.text)
        # self.addSubInterface(self.viewInterface, Icon.GRID, t.view)

        # ---- 官网导航（底部） ----
        self.official_website = AdvancedWebBrowserWindow(
            "https://www.minibt.cn", self)
        self.addSubInterface(self.official_website, FluentIcon.GLOBE,
                             "minibt官网", NavigationItemPosition.BOTTOM)

        # ---- 设置导航（底部），步骤5 ----
        self.addSubInterface(
            self.settingInterface, FIF.SETTING, self.tr('Settings'), NavigationItemPosition.BOTTOM)

        # 绑定官网点击事件
        nav_item = self.navigationInterface.widget(self.official_website.objectName())
        if nav_item:
            nav_item.clicked.connect(self.official_website.load_url)

    def initWindow(self):
        self.resize(960, 780)
        self.setMinimumWidth(760)
        self.setWindowIcon(QIcon(':/gallery/images/logo.png'))
        self.setWindowTitle('MiniQT')

        # create splash screen
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(106, 106))
        self.splashScreen.raise_()

        desktop = QApplication.screens()[0].availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)
        self.show()
        QApplication.processEvents()

    def onSupport(self):
        language = cfg.get(cfg.language).value
        if language.name() == "zh_CN":
            QDesktopServices.openUrl(QUrl(ZH_SUPPORT_URL))
        else:
            QDesktopServices.openUrl(QUrl(EN_SUPPORT_URL))

    def onUseLocalDataChanged(self, use_local_data: bool):
        # print(f"使用本地数据设置已变更: {use_local_data}")
        ...

    def create_tq_api_qtimer(self) -> None:
        """创建天勤API定时器"""
        if self.tq_api_qtimer is None and self.tq_api:
            self.tq_api_qtimer = TqApiQTimer(self)
            self.tq_api_qtimer.update_status_changed.connect(self.on_update_status_changed)
            self.on_update_status_changed(self.tq_api_qtimer.is_update)

    def on_update_status_changed(self, is_update: bool):
        self._is_update_mutex.lock()
        self._is_update = is_update
        self._is_update_mutex.unlock()
        # 同步状态到 ChartUpdateManager，控制非交易时段跳过K线/指标更新
        if self.chart_update_manager:
            ChartUpdateManager.is_update_status = is_update

    def show_login_window(self,is_stock:bool=False):
        """显示登录窗口"""
        cont_tq=(not is_stock) and not self.tq_api
        cont_stock=is_stock and not self.stock_api
        if cont_tq or cont_stock:
            QTimer.singleShot(100, lambda: self.titleBar.login(is_stock=is_stock))
            return True

    def update_cont_quotes(self):
        """更新主力连续合约列表"""
        if self.tq_api and self.tq_object:
            # 直接在主线程中更新（TqApi需要在主线程中运行）
            if not self.marketQuoteInterface.is_update_exchange_segments:
                # 使用QTimer延迟执行，避免阻塞UI
                QTimer.singleShot(100, self._do_update_cont_quotes)

    def _do_update_cont_quotes(self):
        """执行更新主力合约列表"""
        try:
            if self.tq_object:
                self.tq_object.update_cont_quotes()
                # 保存映射表到数据库（只保存一次）
                self._save_maps_to_db()
                # 检查是否需要全量填充合约数据
                self._populate_all_contracts_if_fresh()
                # 检查是否设置了启动时更新行情数据
                self._update_market_on_startup()
        except Exception as e:
            print(f"更新主力合约列表失败: {e}")
            import traceback
            traceback.print_exc()

    def _update_market_on_startup(self):
        """如果设置了启动时更新行情，清除缓存以强制从天勤重新获取"""
        try:
            from ..common.chart_config import chart_cfg
            if chart_cfg.updateMarketOnStartup.value:
                self.marketQuoteInterface.cached_symbol_info.clear()
                print("[MainWindow] 已清除行情缓存，将在切换时从天勤重新获取")
        except Exception as e:
            print(f"[MainWindow] 启动更新行情检查失败: {e}")
    
    def _populate_all_contracts_if_fresh(self):
        """如果是全新数据库，全量填充所有合约数据（使用 QTimer 分段执行）"""
        try:
            from ..common.database_manager import get_db_manager
            db_manager = get_db_manager()
            if db_manager is None or not db_manager.is_fresh_database():
                return

            print("[MainWindow] 检测到全新数据库，开始全量填充合约数据...")

            # 构建 CN→EN 映射
            from ..common.tq_object import INS_CLASS_MAP, EXCHANGE_ID_MAP
            cn_to_en_ins_class = {}
            for map_dict in INS_CLASS_MAP:
                for en, cn in map_dict.items():
                    cn_to_en_ins_class[cn] = en
            cn_to_en_exchange = {cn: en for en, cn in EXCHANGE_ID_MAP.items()}

            # 初始化填充状态（在主线程中执行，避免与 qasync 冲突）
            self._populate_state = {
                'iterator': None,  # 迭代器：(ins_class_cn, exchange_cn, symbol_list)
                'cn_to_en_ins_class': cn_to_en_ins_class,
                'cn_to_en_exchange': cn_to_en_exchange,
                'success': 0,
                'fail': 0,
                'total': sum(len(exchange_dict) for exchange_dict in self.tq_object.exchanges.values()),
            }

            # 构建任务列表
            tasks = []
            for ins_class_cn, exchange_dict in self.tq_object.exchanges.items():
                for exchange_cn, symbol_list in exchange_dict.items():
                    if symbol_list:
                        tasks.append((ins_class_cn, exchange_cn, symbol_list))

            self._populate_state['tasks'] = tasks
            self._populate_state['index'] = 0

            # 使用 QTimer 分段执行（每次处理一个任务，间隔 10ms）
            QTimer.singleShot(10, self._populate_one_task)

        except Exception as e:
            print(f"[MainWindow] 全量填充启动失败: {e}")
            import traceback
            traceback.print_exc()

    def _populate_one_task(self):
        """执行一个填充任务（在主线程中运行，与 qasync 兼容）"""
        if not hasattr(self, '_populate_state') or self._populate_state is None:
            return

        state = self._populate_state
        tasks = state.get('tasks', [])
        index = state.get('index', 0)

        if index >= len(tasks):
            # 所有任务完成
            self._on_populate_all_finished()
            return

        # 获取当前任务
        ins_class_cn, exchange_cn, symbol_list = tasks[index]

        try:
            from ..common.database_manager import get_db_manager
            db_manager = get_db_manager()

            cn_to_en_ins_class = state['cn_to_en_ins_class']
            cn_to_en_exchange = state['cn_to_en_exchange']

            ins_class_en = cn_to_en_ins_class.get(ins_class_cn, ins_class_cn)
            db_ins_class = "FUTURE" if ins_class_en == "CONT_MAIN" else ins_class_en
            exchange_en = cn_to_en_exchange.get(exchange_cn, exchange_cn)

            # 在主线程中调用 tq_api（与 qasync 兼容）
            symbol_info = self.tq_api.query_symbol_info(symbol_list)
            if symbol_info is not None and not symbol_info.empty:
                symbol_info = symbol_info.copy()
                symbol_info['ins_class'] = db_ins_class
                symbol_info['exchange_id'] = exchange_en
                db_manager.save_symbol_info(symbol_info)
                state['success'] += 1
            else:
                state['fail'] += 1

        except Exception as e:
            print(f"[全量填充] {ins_class_cn}/{exchange_cn} 失败: {e}")
            state['fail'] += 1

        # 更新索引，继续下一个任务
        state['index'] = index + 1
        QTimer.singleShot(10, self._populate_one_task)

    def _on_populate_all_finished(self):
        """全量填充完成"""
        if not hasattr(self, '_populate_state') or self._populate_state is None:
            return

        state = self._populate_state
        success = state['success']
        fail = state['fail']
        total = state['total']

        # 标记填充完成
        from ..common.database_manager import get_db_manager
        db_manager = get_db_manager()
        if db_manager:
            db_manager.mark_database_populated()

        msg = f"合约数据全量填充完成: {success} 成功, {fail} 失败 (共 {total} 组)"
        print(f"[MainWindow] {msg}")

        # 刷新行情界面（如果已初始化）
        if hasattr(self, 'marketQuoteInterface'):
            self.marketQuoteInterface.on_cont_quotes_updated()

        # InfoBar 提醒
        InfoBar.success(
            '数据库初始化',
            msg,
            duration=3000,
            parent=self,
            position=InfoBarPosition.TOP_RIGHT
        )

        # 清理状态
        self._populate_state = None

    def _save_maps_to_db(self):
        """保存映射表到数据库"""
        try:
            from ..common.database_manager import get_db_manager

            db_manager = get_db_manager()
            if db_manager is None:
                print("[_save_maps_to_db] 数据库管理器为空")
                return

            # 保存合约类型映射表和交易所映射表
            from ..common.tq_object import INS_CLASS_MAP, EXCHANGE_ID_MAP
            ins_class_map = {}
            for mapping in INS_CLASS_MAP:
                ins_class_map.update(mapping)
            db_manager.save_ins_class_map(ins_class_map)
            db_manager.save_exchange_id_map(EXCHANGE_ID_MAP)
            #print(f"[_save_maps_to_db] 已保存映射表: {len(ins_class_map)} 个合约类型, {len(EXCHANGE_ID_MAP)} 个交易所")
        except Exception as e:
            print(f"[_save_maps_to_db] 保存映射表失败: {e}")
            import traceback
            traceback.print_exc()

    def updateMarketQuoteTableColor(self):
        """更新行情表格字体颜色"""
        try:
            if hasattr(self, 'marketQuoteInterface'):
                self.marketQuoteInterface.updateTableFontColor()
        except Exception as e:
            print(f"更新行情表格颜色失败: {e}")

    def start_minibt_chart(self, symbol="SHFE.ag2604", cycle: int = 60, length: int = 1000,is_stock:bool=False):
        """通过minibt创建策略并启动图表"""
        # 检查是否已登录期货接口
        if self.show_login_window(is_stock):
            return

        # 尝试导入MarketWatchWindow
        global MarketWatchWindow
        if MarketWatchWindow is None:
            try:
                from ..windows.market_watch_window import MarketWatchWindow as Mww
                MarketWatchWindow = Mww
            except Exception as e:
                print(f"导入市场观察窗口模块失败: {e}")
                return
        
        # === 股票数据验证：先尝试获取数据，再打开窗口 ===
        if is_stock:
            if not (hasattr(self, 'stock_api') and self.stock_api):
                # 先尝试获取数据（验证数据可用性）
            #     print(f"[MainWindow] 尝试获取股票 {symbol} {cycle}分钟 数据...")
            #     test_data = self.stock_api.get_kline_serial(symbol, cycle, length)
                
            #     if test_data is None or test_data.empty:
            #         # 数据为空，显示错误提示并阻止窗口创建
            #         print(f"[MainWindow] 无法获取股票 {symbol} 数据，阻止打开窗口")
            #         from qfluentwidgets import InfoBar, InfoBarPosition
            #         InfoBar.error(
            #             title="数据获取失败",
            #             content=f"无法获取股票 {symbol} 的K线数据，请检查网络或更换数据源",
            #             orient=Qt.Horizontal,
            #             isClosable=True,
            #             position=InfoBarPosition.TOP,
            #             duration=3000,
            #             parent=self
            #         )
            #         return  # 阻止窗口创建
            #     else:
            #         print(f"[MainWindow] 股票 {symbol} 数据验证成功，准备打开窗口")
            # else:
                print("[MainWindow] 股票API未初始化，无法验证数据")
                from qfluentwidgets import InfoBar, InfoBarPosition
                InfoBar.warning(
                    title="未登录",
                    content="请先登录股票账户",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                return
        
        # 检查是否已经存在具有相同symbol的MarketWatchWindow
        try:
            for route_key, chart_window in self.titleBar.qobject.items():
                if hasattr(chart_window, 'symbol'):
                    if chart_window.symbol == symbol:
                        # 切换到已存在的窗口
                        self.stackedWidget.setCurrentWidget(chart_window)
                        return
            # 如果不存在，创建新窗口
            chart_window = MarketWatchWindow(self, symbol, cycle, length,is_stock=is_stock)
            self.titleBar.addTab(chart_window)
        except Exception as e:
            print(f"创建市场观察窗口失败: {e}")
            import traceback
            traceback.print_exc()
        # from ..windows.chart_interface import LightChartWindow

        # # 测试图表：无合约时使用 test 作为唯一标识
        # obj_name = f"LightChart_{symbol if symbol else 'test'}_{cycle}"

        # # 单例：检查是否已存在同名图表窗口
        # if hasattr(self, '_chart_windows') and obj_name in self._chart_windows:
        #     chart_win = self._chart_windows[obj_name]
        #     self.stackedWidget.setCurrentWidget(chart_win)
        #     return

        # # 创建图表窗口
        # chart_win = LightChartWindow(self, symbol=symbol, cycle=cycle)
        # self.addSubInterface(
        #     chart_win, obj_name,
        #     symbol if symbol else "测试图表",
        #     FluentIcon.ACCEPT if not symbol else ":/resource/logo.svg")

        # # 记录以便复用
        # if not hasattr(self, '_chart_windows'):
        #     self._chart_windows = {}
        # self._chart_windows[obj_name] = chart_win

        # self.stackedWidget.setCurrentWidget(chart_win, False)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, 'splashScreen'):
            self.splashScreen.resize(self.size())

    def closeEvent(self, e):
        # 保存代码编辑器状态
        if hasattr(self, 'strategyBacktestWindow'):
            try:
                ce = self.strategyBacktestWindow.code_editor
                ce._saveCurrentFolderState()
                ce.file_config.clean_invalid_folders()
                self.strategyBacktestWindow.close()
            except Exception:
                pass
        try:
            for _, v in self.titleBar.qobject.items():
                v.close()
        except:
            pass
        # 关闭登录窗口（如果有正在运行的登录线程）
        if hasattr(self, '_login_window') and self._login_window:
            self._login_window.close()
            self._login_window = None
        if self.tq_api_qtimer:
            self.tq_api_qtimer.stop()
        if self.tq_api:
            self.tq_api.close()
            self.tq_api = None
        if self.stock_api:
            self.stock_api.close()
            self.stock_api = None
        super().closeEvent(e)

    def _onThemeChangedFinished(self):
        super()._onThemeChangedFinished()
        self.setMicaEffectEnabled(False)

    def switchToSample(self, routeKey, index):
        """ switch to sample or custom route from home interface """
        # 自定义路由映射（来自首页快捷入口）
        custom_routes = {
            "marketQuoteInterface": lambda: self._navigateTo(self.marketQuoteInterface),
            "strategyBacktestInterface": lambda: self._navigateTo(self.strategyBacktestWindow),
            "officialWebsiteInterface": lambda: self._navigateTo(self.official_website),
            "settingInterface": lambda: self._navigateTo(self.settingInterface),
            "loginFutures": lambda: self.titleBar.login(is_stock=False),
            "loginStocks": lambda: self.titleBar.login(is_stock=True),
            "terminalWindow": lambda: self.titleBar.showTerminalWindow(),
            "jupyterWindow": lambda: self.titleBar.showJupyterWindow(),
            "jupyterLabWindow": lambda: self.titleBar.showJupyterLabWindow(),
            "testChart": lambda: self.start_minibt_chart(),
        }
        if routeKey in custom_routes:
            custom_routes[routeKey]()
            return

        # 原有的 GalleryInterface 路由
        interfaces = self.findChildren(GalleryInterface)
        for w in interfaces:
            if w.objectName() == routeKey:
                self.stackedWidget.setCurrentWidget(w, False)
                w.scrollToCard(index)

    def _navigateTo(self, widget):
        """导航到指定页面并更新导航栏选中状态"""
        self.stackedWidget.setCurrentWidget(widget)
        self.navigationInterface.setCurrentItem(widget.objectName())
