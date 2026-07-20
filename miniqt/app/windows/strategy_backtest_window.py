# coding:utf-8
"""策略回测窗口 - 上方为代码编辑器，下方为终端"""

import os
import sys
from turtle import left
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QSizePolicy,
                               QAbstractItemView, QSplitterHandle, QPushButton,
                               QLabel)
from PyQt6.QtCore import Qt, QRectF, QSize, pyqtSignal, QUrl, QTimer, QRect, QThread, QObject
from PyQt6.QtGui import QPainter, QIcon, QFont, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from .code_editor_window import CodeEditorWindow
from qfluentwidgets import (isDarkTheme, ScrollArea, StrongBodyLabel, ToolButton, FluentIcon,
                            TitleLabel, TransparentToolButton, CardWidget, FlowLayout,
                            CaptionLabel, BodyLabel, TableWidget, ProgressBar, InfoBar, InfoBarPosition)
from qfluentwidgets import Action, FluentIcon as FIF
from ..common.style_sheet import StyleSheet
from ..common.config import cfg

# JSON 文件检测间隔（毫秒）
JSON_CHECK_INTERVAL = 500
# JSON 文件检测超时时间（秒）
JSON_CHECK_TIMEOUT = 60


class TabToolButton(TransparentToolButton):
    """ Tab tool button """

    def _postInit(self):
        self.setFixedSize(32, 24)
        self.setIconSize(QSize(12, 12))

    def _drawIcon(self, icon, painter: QPainter, rect: QRectF, state=QIcon.State.Off):
        color = '#eaeaea' if isDarkTheme() else '#484848'
        icon = icon.icon(color=color)
        super()._drawIcon(icon, painter, rect, state)


class BacktestResultInterface(ScrollArea):
    """ 回测结果展示界面 """

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        # self.toolBar = ToolBar(title, subtitle, self)
        self.vBoxLayout = QVBoxLayout(self.view)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # self.setViewportMargins(0, self.toolBar.height(), 0, 0)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setSpacing(10)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.setContentsMargins(6, 6, 6, 6)

        self.view.setObjectName('view')
        StyleSheet.GALLERY_INTERFACE.apply(self)

        # 添加标题标签
        self.title_label = TitleLabel(title, self)
        self.vBoxLayout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignTop)

    def addwidget(self, widget: QWidget, stretch=0):
        # 如果存在标题标签，先删除
        if hasattr(self, 'title_label') and self.title_label is not None:
            self.vBoxLayout.removeWidget(self.title_label)
            self.title_label.deleteLater()
            self.title_label = None
        self.vBoxLayout.addWidget(widget, stretch, Qt.AlignmentFlag.AlignTop)
        return widget

    def scrollToCard(self, index: int):
        """ scroll to example card """
        w = self.vBoxLayout.itemAt(index).widget()
        self.verticalScrollBar().setValue(w.y())

    def setDarkTheme(self, is_dark: bool):
        """设置主题"""
        self._is_dark_theme = is_dark
        # 刷新样式表
        self.setStyleSheet("")


class ResultCard(QWidget):
    def __init__(self, widget: QWidget, title="回测结果", parent=None):
        super().__init__(parent=parent)
        self.vBoxLayout = QVBoxLayout(self)
        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        self.titleLabel = StrongBodyLabel(title, self)
        self.deleteBtn = ToolButton(FluentIcon.DELETE.icon(), self)
        self.deleteBtn.setToolTip('删除')
        hlayout.addWidget(self.titleLabel)

        hlayout.addStretch(1)

        hlayout.addWidget(self.deleteBtn)

        self.vBoxLayout.addLayout(hlayout)

        self.vBoxLayout.addWidget(widget)

        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)

        self.vBoxLayout.setSpacing(0)


class LocalTermPlaceholder(QWidget):
    """终端占位符，当LocalTerm不可用时显示"""

    # 占位符也需要信号接口
    finishedSignal = None

    def __init__(self, parent=None, is_dark_theme: bool = True):
        super().__init__(parent=parent)
        from PyQt6.QtWidgets import QVBoxLayout, QLabel
        layout = QVBoxLayout(self)
        label = QLabel("终端加载中...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self._is_dark_theme = is_dark_theme

    @property
    def is_dark_theme(self) -> bool:
        return self._is_dark_theme

    def setTheme(self, is_dark: bool):
        self._is_dark_theme = is_dark


def get_local_term():
    """获取LocalTerm类，如果导入失败则返回占位符"""
    try:
        from .powershell_terminal import LocalTerm
        return LocalTerm
    except ImportError:
        return LocalTermPlaceholder


def create_web_view(html_path: str, parent=None) -> QWebEngineView:
    """创建用于显示HTML的WebEngineView"""
    view = QWebEngineView(parent)

    # 配置WebEngineSettings
    settings = view.settings()
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

    # 加载HTML文件
    file_url = QUrl.fromLocalFile(html_path)
    view.setUrl(file_url)

    # 设置最小高度，确保内容可见
    view.setMinimumHeight(500)

    return view


class _SplitterHandle(QSplitterHandle):
    """自定义 QSplitterHandle，支持折叠按钮
    
    根据 collapse_direction 参数决定是否绘制折叠按钮：
    - None: 只绘制透明背景，不绘制按钮（无折叠功能）
    - 'left'/'right'/'up'/'down': 绘制按钮，点击时折叠对应方向的窗口
    """

    def __init__(self, orientation, parent=None, collapse_direction=None):
        super().__init__(orientation, parent)
        self.collapsed = False
        self.collapse_direction = collapse_direction
        self._is_hovering = False
        self._saved_sizes = None
        self._mouse_press_pos = None  # 记录鼠标按下位置，用于区分拖拽和点击

    def enterEvent(self, event):
        self._is_hovering = True
        self.update()

    def leaveEvent(self, event):
        self._is_hovering = False
        self.update()

    def paintEvent(self, event):
        """绘制 handle 背景，以及折叠按钮（如果有）"""
        painter = QPainter(self)
        rect = self.rect()

        try:
            from qfluentwidgets import isDarkTheme
            is_dark = isDarkTheme()
        except ImportError:
            is_dark = False

        # 绘制 handle 背景（深色/浅色主题自适应）
        if is_dark:
            handle_color = QColor(100, 150, 200, 50) if self._is_hovering else QColor(255, 255, 255, 20)
        else:
            handle_color = QColor(100, 150, 200, 65) if self._is_hovering else QColor(0, 0, 0, 15)
        painter.fillRect(rect, handle_color)

        # 只有配置了折叠方向才绘制按钮
        if self.collapse_direction:
            parent_splitter = self.parent()
            if isinstance(parent_splitter, QSplitter):
                # 按钮尺寸（根据 splitter 方向）
                if parent_splitter.orientation() == Qt.Orientation.Horizontal:
                    bw, bh = 4, 20
                else:
                    bw, bh = 20, 4

                btn_rect = QRect(
                    (rect.width() - bw) // 2,
                    (rect.height() - bh) // 2,
                    bw, bh
                )

                # 根据折叠状态选择按钮颜色（用色差表示）
                if self.collapsed:
                    btn_color = QColor(100, 150, 200, 180) if is_dark else QColor(100, 150, 200, 200)
                else:
                    btn_color = QColor(80, 160, 220, 100) if is_dark else QColor(70, 140, 200, 130)

                if self._is_hovering:
                    btn_color = QColor(btn_color.red(), btn_color.green(), btn_color.blue(),
                                       min(btn_color.alpha() + 30, 255))

                painter.fillRect(btn_rect, btn_color)

        painter.end()

    def mousePressEvent(self, event):
        """记录鼠标按下位置"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """点击 handle 时触发折叠（只有点击而非拖拽时）"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否是点击而非拖拽（移动距离小于5像素）
            if self._mouse_press_pos is not None:
                release_pos = event.pos()
                distance = ((release_pos.x() - self._mouse_press_pos.x()) ** 2 +
                           (release_pos.y() - self._mouse_press_pos.y()) ** 2) ** 0.5
                # 只有移动距离小于5像素时才触发折叠
                if distance < 1e-8 and self.collapse_direction:
                    parent_splitter = self.parent()
                    if isinstance(parent_splitter, QSplitter):
                        self.hide_relative_widget(parent_splitter)
            self._mouse_press_pos = None

    def hide_relative_widget(self, splitter):
        """根据方向参数折叠/展开对应窗口
        
        方向参数说明：
            - 'left': 隐藏左边窗口 (sizes = [0, total])
            - 'right': 隐藏右边窗口 (sizes = [total, 0])
            - 'up': 隐藏上边窗口 (sizes = [0, total])
            - 'down': 隐藏下边窗口 (sizes = [total, 0])
        """
        current_sizes = splitter.sizes()

        if self.collapsed:
            # 展开：恢复保存的 sizes
            self.collapsed = False
            if self._saved_sizes is not None:
                splitter.setSizes(self._saved_sizes)
        else:
            # 折叠：保存当前 sizes 并设置折叠状态
            self.collapsed = True
            self._saved_sizes = current_sizes

            total_size = sum(current_sizes)
            if self.collapse_direction in ('left', 'up'):
                new_sizes = [0, total_size]
            elif self.collapse_direction in ('right', 'down'):
                new_sizes = [total_size, 0]
            else:
                return

            splitter.setSizes(new_sizes)

        self.update()


class _ToggleButtonSplitter(QSplitter):
    """自定义 QSplitter，支持折叠功能
    
    使用方式：
    1. 无折叠按钮：创建后不调用 set_collapse_direction，handle 只显示透明背景
    2. 有折叠按钮：调用 set_collapse_direction(direction)，handle 会绘制折叠按钮
    
    示例：
        # 无折叠按钮（用于 market_watch_window.py）
        splitter = _ToggleButtonSplitter(Qt.Orientation.Horizontal)
        
        # 有折叠按钮（用于 strategy_backtest_window.py）
        splitter = _ToggleButtonSplitter(Qt.Orientation.Horizontal)
        splitter.set_collapse_direction('left')  # 隐藏左边窗口
    """

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(4)
        self.collapse_direction = None
        self._handles = []

    def createHandle(self):
        """创建 handle，传递折叠方向参数"""
        handle = _SplitterHandle(self.orientation(), self, self.collapse_direction)
        self._handles.append(handle)
        return handle

    def set_collapse_direction(self, direction):
        """设置折叠方向
        
        Args:
            direction: 方向参数，可选值：
                - None: 无折叠按钮（默认）
                - 'left': 隐藏左边窗口
                - 'right': 隐藏右边窗口
                - 'up': 隐藏上边窗口
                - 'down': 隐藏下边窗口
        """
        self.collapse_direction = direction
        # 更新所有已创建的 handle 的方向参数
        for handle in self._handles:
            if isinstance(handle, _SplitterHandle):
                handle.collapse_direction = direction


class BacktestResultPanel(QWidget):
    """回测结果展示面板 —— 复刻 light_chart_replay.ResultPanel 的完整指标集"""

    # 与 light_chart_replay.ResultPanel.METRIC_GROUPS 完全对齐
    METRIC_GROUPS = {
        "收益指标": [
            ("profit", "最终收益"), ("return", "累计收益率"),
            ("total_fee", "总手续费"), ("payoff_ratio", "盈亏比"),
            ("avg_return", "平均收益"), ("avg_win", "平均盈利"),
        ],
        "风险指标": [
            ("sharpe", "夏普比率"), ("drawdown", "最大回撤"),
            ("var", "风险价值(VaR)"), ("risk_return", "风险收益比"),
        ],
        "交易指标": [
            ("winrate", "胜率"), ("wins", "盈利次数"),
            ("losses", "亏损次数"), ("profit_ratio", "收益比率"),
            ("trades", "交易次数"), ("avg_loss", "平均亏损"),
        ],
    }

    def __init__(self, parent=None, dark: bool = False):
        super().__init__(parent=parent)
        self._dark = dark
        self._is_dark_theme = dark  # 供 ReplayWindow.isdark 属性读取
        self._card_widgets: dict[str, QWidget] = {}
        # ★ 多策略支持
        # {s_idx: {metrics, equity, dd, trades, ...}}
        self._strategy_results: dict[int, dict] = {}
        self._strategy_names: list[str] = []           # 策略名称列表
        self._current_strategy_idx: int = -1            # 当前显示的策略索引
        self._init_ui()

    def _init_ui(self):
        # 延迟导入：EquityCurveChart 仅在回测执行时真正需要
        try:
            from minibt.strategy.light_chart_replay import EquityCurveChart
            _equity_chart_available = True
        except ImportError as e:
            EquityCurveChart = None
            _equity_chart_available = False
            print(f"[BacktestResultPanel] 权益曲线图表不可用: {e}")
        from qfluentwidgets import isDarkTheme

        self.setObjectName("BacktestResultPanel")

        # 垂直分割器：上方分析区 | 下方K线图
        self.splitter = _ToggleButtonSplitter(Qt.Orientation.Vertical, self)
        self.splitter.set_collapse_direction('up')

        # 上方：分析区域（指标 + 权益曲线）
        self.analysis_widget = QWidget(self)
        self.analysis_widget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred)
        analysis_layout = QVBoxLayout(self.analysis_widget)
        analysis_layout.setContentsMargins(10, 4, 10, 4)
        analysis_layout.setSpacing(4)
        analysis_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._title_label = TitleLabel("回测结果", self)
        analysis_layout.addWidget(self._title_label)

        # 指标卡片（FlowLayout）
        metrics_container = QWidget(self)
        metrics_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        metrics_container.setMaximumHeight(160)
        self._metrics_flow = FlowLayout(metrics_container, needAni=True, isTight=True)
        self._metrics_flow.setContentsMargins(0, 0, 0, 0)
        self._metrics_flow.setSpacing(4)
        self._metrics_flow.setVerticalSpacing(4)

        for group_name, metrics in self.METRIC_GROUPS.items():
            for key, title in metrics:
                card = self._make_metric_card(key, title, "--")
                self._card_widgets[key] = card
                self._metrics_flow.addWidget(card)

        analysis_layout.addWidget(metrics_container)

        # --- 权益曲线图 ---
        if EquityCurveChart is not None:
            self.equity_chart = EquityCurveChart(self)
            self.equity_chart.setMinimumHeight(120)
            self.equity_chart.setSizePolicy(
                QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.equity_chart.set_dark(self._dark)
        else:
            self.equity_chart = QLabel("权益曲线不可用\n(回测执行后自动显示)", self)
            self.equity_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.equity_chart.setMinimumHeight(80)
            self.equity_chart.setStyleSheet("color: #999; background: rgba(128,128,128,0.1);")
        analysis_layout.addWidget(self.equity_chart, 1)  # stretch=1，允许权益曲线扩展

        # --- 交易明细简表（已迁移到 ReplayWindow.chart_stack）---
        self.trade_table = None  # 不再在此面板使用

        # --- K线图表区域（ReplayWindow 嵌入容器）---
        self.chart_container = QWidget(self)
        self.chart_container.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_container.setMinimumHeight(200)
        self.chart_container_layout = QVBoxLayout(self.chart_container)
        self.chart_container_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_container_layout.setSpacing(0)
        # 占位提示
        self._chart_placeholder = TitleLabel(
            "K线图表（回测完成后显示）", self.chart_container)
        self._chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chart_placeholder.setStyleSheet("color: #999; font-size: 13px;")
        self.chart_container_layout.addWidget(self._chart_placeholder)
        self._replay_window = None   # ReplayWindow 实例（回测后创建）

        # 添加到 Splitter
        self.splitter.addWidget(self.analysis_widget)
        self.splitter.addWidget(self.chart_container)
        # stretch factor: 分析区和K线图均可拖动调整
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        # 初始比例：分析区约 35%，K线图 65%
        self.splitter.setSizes([350, 650])

        # 折叠按钮：分析区在上，折叠方向为 'up'（隐藏上方分析区）
        # self.splitter.set_handle_button(
        #     0, collapse_direction='up',
        #     tooltip="隐藏/显示分析区", toggled_widget=self.analysis_widget)
        # # 按钮配置完成后，重新应用样式（使有按钮的 splitter 使用宽 handle + 透明背景）
        # self._apply_splitter_style(self.splitter)

        # 将 splitter 作为主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.splitter)

    def resizeEvent(self, event):
        """窗口大小改变时，保持合理比例"""
        super().resizeEvent(event)

    def showEvent(self, event):
        """首次显示时初始化比例"""
        super().showEvent(event)
        if hasattr(self, 'splitter') and self.splitter:
            # 强制设置初始比例：分析区 35%，K线图 65%
            QTimer.singleShot(0, lambda: self.splitter.setSizes([350, 650]))

    def _apply_splitter_style(self, splitter: QSplitter):
        """为 QSplitter 设置固定宽度的间隙样式
        
        对于 _ToggleButtonSplitter，无论有没有折叠按钮，都使用 _SplitterHandle.paintEvent 绘制，
        不使用样式表（否则样式冲突）。
        """
        from qfluentwidgets import isDarkTheme
        
        # 判断是否是 _ToggleButtonSplitter（无论有没有按钮）
        is_toggle_splitter = isinstance(splitter, _ToggleButtonSplitter)
        
        splitter.setHandleWidth(4)
        splitter.setChildrenCollapsible(False)
        
        if is_toggle_splitter:
            # _ToggleButtonSplitter 的 handle 都是 _SplitterHandle，通过 paintEvent 绘制
            # 必须清除样式表，否则 QSS 引擎会干扰子控件渲染
            splitter.setStyleSheet("")
        else:
            # 普通 QSplitter 使用样式表绘制 handle
            if isDarkTheme():
                bg_color = "rgba(255, 255, 255, 0.08)"
            else:
                bg_color = "rgba(0, 0, 0, 0.06)"
            splitter.setStyleSheet(f"""
                QSplitter::handle {{
                    background-color: {bg_color};
                    border: none;
                }}
                QSplitter::handle:hover {{
                    background-color: rgba(100, 150, 200, 0.25);
                }}
                QSplitter::handle:pressed {{
                    background-color: rgba(100, 150, 200, 0.4);
                }}
            """)

    def _make_metric_card(self, key: str, title: str, value: str) -> QWidget:
        """创建单个指标卡片（复刻 ResultPanel）"""
        card = CardWidget(self)
        card.setMinimumWidth(90)
        card.setMaximumWidth(140)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 4, 8, 4)
        cl.setSpacing(2)
        lbl_title = CaptionLabel(title)
        cl.addWidget(lbl_title)
        lbl_val = BodyLabel(value)
        lbl_val.setFont(QFont('Consolas', 12, QFont.Weight.Bold))
        lbl_val.setObjectName(f"card_val_{key}")
        cl.addWidget(lbl_val)
        return card

    def set_dark(self, dark: bool):
        """设置暗色主题"""
        self._dark = dark
        if hasattr(self, 'equity_chart') and hasattr(self.equity_chart, 'set_dark'):
            self.equity_chart.set_dark(dark)
        if hasattr(self, '_replay_window') and self._replay_window is not None:
            rw = self._replay_window
            if hasattr(rw, 'isdark'):
                # 遍历所有 chart 设置主题
                for chart in rw.all_charts.values():
                    if hasattr(chart, 'setTheme'):
                        chart.setTheme()

    def load_result_from_strategy(self, s, strategy_name: str = ""):
        """直接从策略实例加载回测结果（使用策略统一缓存的 _backtest_metrics）

        - 所有指标（含 wins/losses/win_rate）来自 _compute_backtest_metrics
        - 交易明细表来自 Broker 历史记录
        """
        import numpy as np

        try:
            # --- 1. 更新标题 ---
            title = f"回测结果 - {strategy_name}" if strategy_name else "回测结果"
            self._title_label.setText(title)

            # --- 2. 提取权益曲线 ---
            equity_values = []
            try:
                if hasattr(s, 'profits') and s.profits is not None:
                    ps = s.profits
                    equity_values = (ps.values.tolist() if hasattr(ps, 'values')
                                     else list(ps))
            except Exception:
                pass
            eq_arr = np.array(
                equity_values, dtype=float) if equity_values else np.array([1.0])

            # 回撤曲线（用于权益图表显示）
            dd_vals = []
            if len(eq_arr) > 1:
                peak = np.maximum.accumulate(eq_arr)
                dd_vals = ((eq_arr - peak) / np.where(peak >
                           0, peak, 1.0) * 100).tolist()
            if hasattr(self.equity_chart, 'set_data'):
                self.equity_chart.set_data(
                    list(equity_values), list(dd_vals) if dd_vals else [0.0])

            # --- 3. 提取账户信息 ---
            acc = getattr(s, '_account', None)
            total_fee = float(
                getattr(acc, 'total_commission', 0)) if acc else 0.0

            # --- 4. 使用策略统一计算的回测指标（wins/losses 已基于 Broker 真实交易）---
            m = s._compute_backtest_metrics()
            if m is None:
                self._update_card("profit", "0.00")
                self._update_card("return", "0.00%")
                self._update_card("total_fee", f"{total_fee:.2f}")
                self._update_card("sharpe", "0.0000")
                self._update_card("drawdown", "0.00%")
                print(f"[回测结果] 策略 [{strategy_name}] 收益数据无波动")
                return

            final_return = m['final_return']
            compounded = m['compounded']
            sharpe_val = m['sharpe']
            max_dd = m['max_drawdown']
            var_val = m['value_at_risk']
            risk_ret = m['risk_return_ratio']
            payoff = m['profit_factor']
            pratio = m['profit_ratio']
            avg_ret = m['avg_return']
            avg_win = m['avg_win']
            avg_loss = m['avg_loss']
            # 以下基于 Broker 真实交易统计（_get_broker_trade_stats）
            wins_n = m['wins']
            losses_n = m['losses']
            win_rate = m['win_rate']       # 小数（如 0.35）
            trade_count = m['trade_count']

            # --- 5. 更新卡片（百分比指标使用 Python % 格式，自动乘100）---
            self._update_card("profit", f"{final_return:+.2f}")
            self._update_card("return", f"{compounded:+.2%}")
            self._update_card("total_fee", f"{total_fee:.2f}")
            self._update_card("avg_return", f"{avg_ret:+.4f}")
            self._update_card("avg_win", f"{avg_win:.4f}")
            self._update_card("avg_loss", f"{avg_loss:.4f}")
            self._update_card("payoff_ratio", f"{payoff:.4f}")
            self._update_card("profit_ratio", f"{pratio:.4f}")

            self._update_card("sharpe", f"{sharpe_val:.4f}")
            self._update_card("drawdown", f"{abs(max_dd):.2%}")
            self._update_card("var", f"{var_val:.6f}")
            self._update_card("risk_return", f"{risk_ret:.4f}")

            self._update_card("wins", str(wins_n))
            self._update_card("losses", str(losses_n))
            self._update_card("winrate", f"{win_rate:.2%}")
            self._update_card("trades", str(trade_count))

            # --- 6. 交易明细表（已迁移到 ReplayWindow.chart_stack）---
            trade_records = self._extract_trades_from_broker(s)
            # 交易明细不再在此面板展示

            # print(f"[回测结果] 策略 [{strategy_name}] 结果已更新: "
            #       f"收益={final_return:+.2f}, 交易={trade_count}笔, "
            #       f"胜率={win_rate:.2%}, "
            #       f"夏普={sharpe_val:.2f}, 最大回撤={abs(max_dd):.2%}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[BacktestResultPanel] 加载策略实例结果失败: {e}")

    def _extract_strategy_data(self, s, strategy_name: str = "") -> dict | None:
        """从策略实例提取所有回测数据

        - 所有指标来自 _compute_backtest_metrics（wins/losses 已基于 Broker 交易）
        - 交易明细表来自 Broker 历史记录

        Returns:
            dict 或 None: 包含策略完整回测数据的字典，失败返回 None
        """
        import numpy as np

        try:
            acc = getattr(s, '_account', None)
            total_fee = float(
                getattr(acc, 'total_commission', 0)) if acc else 0.0

            # 权益曲线
            equity_values = []
            try:
                if hasattr(s, 'profits') and s.profits is not None:
                    ps = s.profits
                    equity_values = (ps.values.tolist() if hasattr(ps, 'values')
                                     else list(ps))
            except Exception:
                pass
            eq_arr = np.array(
                equity_values, dtype=float) if equity_values else np.array([1.0])

            # 回撤曲线
            dd_vals = []
            if len(eq_arr) > 1:
                peak = np.maximum.accumulate(eq_arr)
                dd_vals = ((eq_arr - peak) / np.where(peak >
                           0, peak, 1.0) * 100).tolist()

            # Broker 交易明细（仅用于交易表格展示）
            trade_records = self._extract_trades_from_broker(s)

            # 使用策略统一计算的指标（wins/losses/win_rate 已基于 Broker 真实交易）
            m = s._compute_backtest_metrics()

            if m is None:
                return {
                    "strategy_name": strategy_name,
                    "equity_values": list(equity_values),
                    "dd_vals": list(dd_vals) if dd_vals else [0.0],
                    "total_fee": total_fee,
                    "profit": 0.0,
                    "return_pct": 0.0,
                    "trade_records": trade_records,
                    "trade_count": 0,
                    "wins": 0, "losses": 0,
                    "avg_return": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                    "payoff_ratio": 0.0, "profit_ratio": 0.0,
                    "sharpe": 0.0, "drawdown": 0.0,
                    "var": 0.0, "risk_return": 0.0,
                    "winrate": 0.0,
                }

            return {
                "strategy_name": strategy_name,
                "equity_values": list(equity_values),
                "dd_vals": list(dd_vals) if dd_vals else [0.0],
                "total_fee": total_fee,
                "profit": m['final_return'],
                "return_pct": m['compounded'],
                "trade_records": trade_records,
                "trade_count": m['trade_count'],
                "wins": m['wins'],
                "losses": m['losses'],
                "avg_return": m['avg_return'],
                "avg_win": m['avg_win'],
                "avg_loss": m['avg_loss'],
                "payoff_ratio": m['profit_factor'],
                "profit_ratio": m['profit_ratio'],
                "sharpe": m['sharpe'],
                "drawdown": m['max_drawdown'],
                "var": m['value_at_risk'],
                "risk_return": m['risk_return_ratio'],
                "winrate": m['win_rate'],  # 小数（如 0.35）
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[BacktestResultPanel] 提取策略 [{strategy_name}] 数据失败: {e}")
            return None

    def load_results_from_strategies(self, strategies: list, optimization_df_data: list = None):
        """加载多个策略的回测结果（支持多策略切换展示）

        参数:
            strategies: 策略实例列表
            optimization_df_data: 优化 trial 数据（从 CSV 读取的列表），有数据时显示优化结果表格

        流程：
        1. 遍历每个策略实例，提取数据缓存到 _strategy_results
        2. 显示第一个策略的结果
        3. 嵌入 ReplayWindow（传入所有策略实例 + 优化数据）
        4. 连接策略切换信号 → 自动更新上方指标/权益曲线/交易表
        """
        if not strategies:
            print("[回测结果] 策略列表为空")
            return

        # 1. 提取并缓存每个策略的数据
        self._strategy_results.clear()
        self._strategy_names.clear()

        for idx, s in enumerate(strategies):
            sname = s.__class__.__name__
            data = self._extract_strategy_data(s, sname)
            if data is not None:
                self._strategy_results[idx] = data
                self._strategy_names.append(sname)

        if not self._strategy_results:
            print("[回测结果] 所有策略数据提取均失败")
            return

        # print(f"[回测结果] 已加载 {len(self._strategy_results)} 个策略的结果: "
        #       f"{', '.join(self._strategy_names)}")

        # 2. 显示第一个策略的结果
        self._current_strategy_idx = 0
        self._display_cached_result(0)

        # 3. 嵌入 K 线图表（传入所有策略 + 优化数据 + 交易记录）
        trade_records_by_strategy = {
            idx: d.get("trade_records", [])
            for idx, d in self._strategy_results.items()
        }
        self._embed_replay_window_multi(strategies, optimization_df_data, trade_records_by_strategy)

    def _display_cached_result(self, idx: int):
        """根据缓存的策略数据显示结果到 UI"""
        if idx not in self._strategy_results:
            # print(f"[回测结果] 策略索引 {idx} 无缓存数据")
            return

        d = self._strategy_results[idx]
        sname = d["strategy_name"]
        self._current_strategy_idx = idx

        # 标题
        title = f"回测结果 - {sname}"
        if len(self._strategy_names) > 1:
            title += f" ({idx + 1}/{len(self._strategy_names)})"
        self._title_label.setText(title)

        # 权益曲线
        if hasattr(self.equity_chart, 'set_data'):
            self.equity_chart.set_data(d["equity_values"], d["dd_vals"])

        # 指标卡片（return_pct/drawdown 是 quantstats 原始小数值，winrate 已乘100）
        self._update_card("profit", f"{d['profit']:+.2f}")
        self._update_card("return", f"{d['return_pct']:+.2%}")
        self._update_card("total_fee", f"{d['total_fee']:.2f}")
        self._update_card("avg_return", f"{d['avg_return']:+.4f}")
        self._update_card("payoff_ratio", f"{d['payoff_ratio']:.4f}")
        self._update_card("avg_win", f"{d['avg_win']:.4f}")
        self._update_card("wins", str(d["wins"]))
        self._update_card("losses", str(d["losses"]))
        self._update_card("profit_ratio", f"{d['profit_ratio']:.4f}")
        self._update_card("avg_loss", f"{d['avg_loss']:.4f}")
        self._update_card("sharpe", f"{d['sharpe']:.4f}")
        self._update_card("drawdown", f"{abs(d['drawdown']):.2%}")
        self._update_card("var", f"{d['var']:.6f}")
        self._update_card("risk_return", f"{d['risk_return']:.4f}")
        self._update_card("trades", str(d["trade_count"]))
        self._update_card("winrate", f"{d['winrate']:.2%}")

    def switch_to_strategy(self, idx: int):
        """切换显示指定策略的回测结果（由 ReplayWindow 策略切换触发）"""
        if idx == self._current_strategy_idx:
            return
        if idx in self._strategy_results:
            sname = self._strategy_names[idx] if idx < len(
                self._strategy_names) else f"#{idx}"
            # print(f"[回测结果] 切换到策略 [{sname}] (idx={idx})")
            self._display_cached_result(idx)
        # else:
        #     print(f"[回测结果] 切换失败: 索引 {idx} 无缓存数据")

    def _extract_trades_from_broker(self, s) -> list:
        """从策略实例的 Broker 历史记录提取完整平仓交易列表。

        使用仓位状态机检测完整的「开仓→平仓」周期：
        - FLAT → 有仓位：记录入场（entry_index, entry_equity, direction）
        - 有仓位 → FLAT：记录出场（计算 round-trip pnl = exit_equity - entry_equity）
        - 仓位同方向变化（加/减仓）：跳过，不计为独立交易
        - 反向翻转（多→空 / 空→多）：先平旧仓再开新仓，记为一笔完整交易

        Returns:
            list[dict]: 每笔完整交易的字典，含 direction, time, price0, pnl, fee
        """
        trades = []
        try:
            acc = getattr(s, '_account', None)
            if not acc or not hasattr(acc, 'brokers'):
                return trades

            # 获取权益曲线（用于计算每笔交易的平仓盈亏）
            equity_values = []
            try:
                if hasattr(s, 'profits') and s.profits is not None:
                    ps = s.profits
                    equity_values = (ps.values.tolist() if hasattr(ps, 'values')
                                     else list(ps))
            except Exception:
                pass
            eq_arr = equity_values if equity_values else None

            for broker_idx, broker in enumerate(acc.brokers):
                if not hasattr(broker, 'history_queue'):
                    continue

                history = list(broker.history_queue.queue)
                if not history or len(history) < 2:
                    continue

                # ---- 仓位状态机：跟踪完整的 开仓→平仓 周期 ----
                # 状态: 'flat' | 'long' | 'short'
                state = 'flat'
                entry_index = 0       # 入场时的 history 索引
                entry_equity = None   # 入场时权益值
                entry_direction = ''  # 入场方向

                for i, record in enumerate(history):
                    if len(record) < 6:
                        continue
                    # [balance, pos_value, pos_size, profit, cum_profits, fee]
                    _, _, pos_size, profit, cum_profit, fee = (
                        float(record[0]), float(record[1]), int(record[2]),
                        float(record[3]), float(record[4]), float(record[5]))

                    # 当前权益值（从 cum_profits + 初始资金推算，或从 equity 曲线取）
                    current_equity = cum_profit
                    if eq_arr is not None and i < len(eq_arr):
                        current_equity = float(eq_arr[i])

                    if pos_size == 0:
                        # 当前无仓位
                        if state != 'flat':
                            # 平仓！记录一笔完整交易
                            trade_pnl = ((current_equity - entry_equity)
                                         if entry_equity is not None else profit)
                            trades.append({
                                "direction": entry_direction,
                                "time": f"{entry_index}→{i}",
                                "price0": f"{current_equity:.2f}",
                                "price1": "--",
                                "pnl": trade_pnl,
                                "fee": fee,
                            })
                            state = 'flat'
                            entry_equity = None
                        # state=='flat' 且 pos==0: 保持空仓，无操作
                    elif pos_size > 0:
                        if state == 'flat':
                            # 开多
                            state = 'long'
                            entry_index = i
                            entry_equity = current_equity
                            entry_direction = "多"
                        elif state == 'short':
                            # 空翻多：先平空仓，再开多仓
                            trade_pnl = ((current_equity - entry_equity)
                                         if entry_equity is not None else profit)
                            trades.append({
                                "direction": "空(平)",
                                "time": f"{entry_index}→{i}",
                                "price0": f"{current_equity:.2f}",
                                "price1": "--",
                                "pnl": trade_pnl,
                                "fee": fee,
                            })
                            state = 'long'
                            entry_index = i
                            entry_equity = current_equity
                            entry_direction = "多"
                        # state=='long' && pos>0: 持有多仓（加仓/减仓），忽略
                    else:  # pos_size < 0
                        if state == 'flat':
                            # 开空
                            state = 'short'
                            entry_index = i
                            entry_equity = current_equity
                            entry_direction = "空"
                        elif state == 'long':
                            # 多翻空：先平多仓，再开空仓
                            trade_pnl = ((current_equity - entry_equity)
                                         if entry_equity is not None else profit)
                            trades.append({
                                "direction": "多(平)",
                                "time": f"{entry_index}→{i}",
                                "price0": f"{current_equity:.2f}",
                                "price1": "--",
                                "pnl": trade_pnl,
                                "fee": fee,
                            })
                            state = 'short'
                            entry_index = i
                            entry_equity = current_equity
                            entry_direction = "空"
                        # state=='short' && pos<0: 持有空仓（加仓/减仓），忽略

                # 如果回测结束时仍有持仓，按最后一根K线强制平仓
                if state != 'flat' and eq_arr is not None and len(eq_arr) > 0:
                    last_eq = float(eq_arr[-1])
                    trade_pnl = (
                        last_eq - entry_equity) if entry_equity is not None else 0.0
                    trades.append({
                        "direction": f"{entry_direction}(平)",
                        "time": f"{entry_index}→{len(history)-1}",
                        "price0": f"{last_eq:.2f}",
                        "price1": "--",
                        "pnl": trade_pnl,
                        "fee": 0.0,
                    })

        except Exception as e:
            print(f"[BacktestResultPanel] 提取交易记录失败: {e}")

        return trades

    def _embed_replay_window(self, s, strategy_name: str):
        """在图表容器中嵌入 ReplayWindow（display_only 模式，隐藏控制栏）"""
        try:
            from minibt.strategy.light_chart_replay import ReplayWindow

            # 清理旧的 ReplayWindow（手动触发清理，避免 QPaintDevice 错误）
            if self._replay_window is not None:
                old_rw = self._replay_window
                try:
                    old_rw.replay_timer.pause_replay()
                    for chart in old_rw.all_charts.values():
                        try:
                            chart.cleanup()
                        except Exception:
                            pass
                    old_rw.all_charts.clear()
                    if hasattr(old_rw, '_chart_widgets'):
                        old_rw._chart_widgets.clear()
                except Exception:
                    pass
                # 从布局中移除
                self.chart_container_layout.removeWidget(old_rw)
                old_rw.setParent(None)
                old_rw.deleteLater()
                self._replay_window = None

            # 移除占位提示
            if hasattr(self, '_chart_placeholder') and self._chart_placeholder is not None:
                self._chart_placeholder.hide()

            # 创建 ReplayWindow（display_only=True 隐藏 ReplayInfoWindow 控制栏）
            rw = ReplayWindow(
                parent=self.chart_container,
                strategies=[s],
                initial_candles=max(getattr(s, 'min_start_length', 300), 300),
                backtest_completed=True,
                display_only=True,
            )
            self._replay_window = rw

            # 嵌入到容器中
            self.chart_container_layout.addWidget(rw)
            # 设置主题
            is_dark = getattr(self.parent(), '_is_dark_theme',
                              False) if self.parent() else False
            if hasattr(rw, 'setTheme'):
                try:
                    rw.setTheme()
                except Exception:
                    pass

            # print(f"[回测结果] K线图表已嵌入")



        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[回测结果] 嵌入 K线图表失败: {e}")
            if hasattr(self, '_chart_placeholder') and self._chart_placeholder is not None:
                self._chart_placeholder.setText(f"K线图表加载失败: {e}")

    def _embed_replay_window_multi(self, strategies: list, optimization_df_data: list = None, trade_records_by_strategy: dict = None):
        """在图表容器中嵌入 ReplayWindow（多策略模式）

        与 _embed_replay_window 的区别：
        - 接收多个策略实例，ReplayWindow 会自动创建 strategySegmentedWidget
        - 连接策略切换信号到 BacktestResultPanel.switch_to_strategy()
          使用 monkey-patch 方式拦截 _on_strategy_selected 回调
        """
        try:
            from minibt.strategy.light_chart_replay import ReplayWindow

            # 清理旧的 ReplayWindow（手动触发清理，避免 QPaintDevice 错误）
            if self._replay_window is not None:
                old_rw = self._replay_window
                try:
                    old_rw.replay_timer.pause_replay()
                    for chart in old_rw.all_charts.values():
                        try:
                            chart.cleanup()
                        except Exception:
                            pass
                    old_rw.all_charts.clear()
                    if hasattr(old_rw, '_chart_widgets'):
                        old_rw._chart_widgets.clear()
                except Exception:
                    pass
                # 从布局中移除
                self.chart_container_layout.removeWidget(old_rw)
                old_rw.setParent(None)
                old_rw.deleteLater()
                self._replay_window = None

            # 移除占位提示
            if hasattr(self, '_chart_placeholder') and self._chart_placeholder is not None:
                self._chart_placeholder.hide()

            # 取所有策略中最大的 min_start_length
            max_start = max((getattr(s, 'min_start_length', 300)
                            for s in strategies), default=300)

            # 创建 ReplayWindow（传入所有策略实例 + 优化数据 + 交易记录）
            rw = ReplayWindow(
                parent=self.chart_container,
                strategies=strategies,
                initial_candles=max(max_start, 300),
                backtest_completed=True,
                display_only=True,
                optimization_df_data=optimization_df_data,
                trade_records_by_strategy=trade_records_by_strategy,
            )
            self._replay_window = rw

            # ★ 连接策略切换信号：monkey-patch _on_strategy_selected 以联动上方结果面板
            original_on_strategy_selected = rw._on_strategy_selected

            def _on_strategy_switched(s_idx: int):
                """包装函数：先执行原始切换逻辑，再更新结果面板"""
                original_on_strategy_selected(s_idx)
                # 联动更新上方的指标/权益曲线/交易表
                self.switch_to_strategy(s_idx)

            rw._on_strategy_selected = _on_strategy_switched

            # 嵌入到容器中
            self.chart_container_layout.addWidget(rw)
            # 设置主题
            is_dark = getattr(self.parent(), '_is_dark_theme',
                              False) if self.parent() else False
            if hasattr(rw, 'setTheme'):
                try:
                    rw.setTheme()
                except Exception:
                    pass

            # print(f"[回测结果] K线图表已嵌入 (多策略模式, {len(strategies)} 个策略)")



        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[回测结果] 嵌入 K线图表失败: {e}")
            if hasattr(self, '_chart_placeholder') and self._chart_placeholder is not None:
                self._chart_placeholder.setText(f"K线图表加载失败: {e}")

    def load_result(self, plot_data: dict, strategy_name: str = ""):
        """从 pickle 数据加载并展示回测结果（与 ResultPanel._refresh 对齐）"""
        import traceback
        try:
            # --- 更新标题 ---
            title = f"回测结果 - {strategy_name}" if strategy_name else "回测结果"
            self._title_label.setText(title)

            # --- 提取权益数据 ---
            equity_info = plot_data.get(
                "equity", {}) if isinstance(plot_data, dict) else {}
            equity_vals = equity_info.get(
                "values", []) if isinstance(equity_info, dict) else []
            dd_vals = equity_info.get("drawdowns", []) if isinstance(
                equity_info, dict) else []

            # --- 更新权益图表 ---
            if hasattr(self.equity_chart, 'set_data'):
                if equity_vals and len(equity_vals) > 0:
                    self.equity_chart.set_data(
                        list(equity_vals), list(dd_vals) if dd_vals else None)
                else:
                    self.equity_chart.set_data([1.0], [0.0])

            # --- 计算所有指标 ---
            eq_arr = np.array(
                equity_vals, dtype=float) if equity_vals else np.array([1.0])
            initial = eq_arr[0] if len(eq_arr) > 0 else 1.0
            final = eq_arr[-1] if len(eq_arr) > 0 else initial

            # ===== 收益指标 =====
            profit_val = final - initial
            ret_pct = (profit_val / initial * 100.0) if initial > 0 else 0.0
            self._update_card("profit", f"{profit_val:+.2f}")
            self._update_card("return", f"{ret_pct:+.2f}%")

            # 总手续费
            total_fee = 0.0
            account_info = plot_data.get(
                "account", {}) if isinstance(plot_data, dict) else {}
            if isinstance(account_info, dict):
                total_fee = float(account_info.get("total_commission", 0.0))
            elif hasattr(account_info, 'total_commission'):
                total_fee = float(account_info.total_commission)
            self._update_card("total_fee", f"{total_fee:.2f}")

            # 平均收益（每笔）
            trade_data = self._extract_trades(plot_data, eq_arr)
            trade_count = len(trade_data)
            avg_ret = profit_val / trade_count if trade_count > 0 else 0.0
            self._update_card("avg_return", f"{avg_ret:+.4f}")

            # 盈亏比 / 平均盈利 / 平均亏损
            win_pnls = [t.get('pnl', 0)
                        for t in trade_data if t.get('pnl', 0) > 0]
            loss_pnls = [t.get('pnl', 0)
                         for t in trade_data if t.get('pnl', 0) <= 0]
            wins_n = len(win_pnls)
            losses_n = len(loss_pnls)
            self._update_card("wins", str(wins_n))
            self._update_card("losses", str(losses_n))

            avg_win = np.mean(win_pnls) if win_pnls else 0.0
            avg_loss = abs(np.mean(loss_pnls)) if loss_pnls else 0.0
            payoff = (avg_win / avg_loss) if avg_loss > 0 else 0.0
            self._update_card("payoff_ratio", f"{payoff:.4f}")
            self._update_card("avg_win", f"{avg_win:.4f}")
            self._update_card("avg_loss", f"{avg_loss:.4f}")

            # 收益比率 = wins / trades
            pratio = wins_n / trade_count if trade_count > 0 else 0.0
            self._update_card("profit_ratio", f"{pratio:.4f}")

            # ===== 风险指标 =====
            sharpe_val = self._calc_sharpe(eq_arr)
            self._update_card("sharpe", f"{sharpe_val:.4f}")

            max_dd = 0.0
            if dd_vals:
                max_dd = abs(min(dd_vals))  # drawdowns 已是百分比
            elif len(eq_arr) > 1:
                peak = np.maximum.accumulate(eq_arr)
                dd = (eq_arr - peak) / np.where(peak > 0, peak, 1.0)
                max_dd = abs(float(np.min(dd) * 100.0))
            self._update_card("drawdown", f"{max_dd:.2f}%")

            # 风险价值 VaR (95%, 基于收益率)
            var_val = 0.0
            if len(eq_arr) > 1:
                rets = np.diff(eq_arr) / (np.abs(eq_arr[:-1]) + 1e-8)
                var_val = float(np.percentile(rets, 5))  # 5% 分位数
            self._update_card("var", f"{var_val:.6f}")

            # 风险收益比 = |max_dd%| / |return%|
            risk_ret = (max_dd / abs(ret_pct)) if abs(ret_pct) > 1e-8 else 0.0
            self._update_card("risk_return", f"{risk_ret:.4f}")

            # ===== 交易指标 =====
            self._update_card("trades", str(trade_count))
            win_rate = (wins_n / trade_count *
                        100.0) if trade_count > 0 else 0.0
            self._update_card("winrate", f"{win_rate:.2f}%")

            # --- 刷新交易明细表 ---
        # 交易明细已迁移到 ReplayWindow.chart_stack

        except Exception as e:
            traceback.print_exc()
            print(f"[BacktestResultPanel] 加载回测结果失败: {e}")

    def _update_card(self, key: str, value: str):
        card = self._card_widgets.get(key)
        if card:
            lbl = card.findChild(BodyLabel, f"card_val_{key}")
            if lbl:
                lbl.setText(value)

    @staticmethod
    def _calc_sharpe(equity: np.ndarray, times: list = None) -> float:
        """计算年化夏普比率"""
        if len(equity) < 2:
            return 0.0
        rets = np.diff(equity) / (np.abs(equity[:-1]) + 1e-8)
        std = np.std(rets)
        if std == 0:
            return 0.0
        ann_factor = np.sqrt(252)
        # 如果是日线或小时线数据，可根据 times 调整因子
        return float(np.mean(rets) / std * ann_factor)

    @staticmethod
    def _extract_trades(plot_data: dict, equity: np.ndarray) -> list:
        """从 pickle 数据/权益变化粗略提取交易记录"""
        trades = []
        try:
            contracts = plot_data.get("contracts", {})
            if not contracts:
                return trades

            for contract_key, cdata in contracts.items():
                results = cdata.get("results", [])
                for r in results:
                    if isinstance(r, dict):
                        # 尝试获取成交记录
                        trades_list = r.get("trades", [])
                        if trades_list:
                            for tr in trades_list:
                                trades.append({
                                    "direction": tr.get("direction", ""),
                                    "time": str(tr.get("time", "")),
                                    "price0": tr.get("price0", tr.get("price", "")),
                                    "price1": tr.get("price1", ""),
                                    "pnl": tr.get("pnl", tr.get("profit", 0)),
                                    "fee": tr.get("fee", tr.get("commission", 0)),
                                })
        except Exception:
            pass
        return trades

    def _refresh_trade_table(self, trade_data: list):
        """交易明细已迁移到 ReplayWindow.chart_stack，此方法保留作为兼容接口"""
        pass


class _OptimizationWorker(QObject):
    """后台参数优化工作类 — 在 QThread 中运行，避免阻塞 UI"""

    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)   # current_trial, total_trials
    finished_signal = pyqtSignal(list, list)  # (final_instances, optimization_df_data)
    error_signal = pyqtSignal(str)

    def __init__(self, file_path: str,term):
        super().__init__()
        self.file_path = file_path
        self.term=term

    def run(self):
        """在后台线程中执行参数优化 + 回测"""
        import io
        import traceback
        from minibt.bt import Bt
        from minibt.utils import OpConfig

        def _log(msg: str):
            self.log_signal.emit(msg)

        try:
            self._run_impl(_log, Bt, OpConfig, io, traceback)
        except Exception as e:
            _log(f"[优化] 未捕获异常: {e}")
            _log(traceback.format_exc())
            self.error_signal.emit(f"优化异常: {e}")

    def _run_impl(self, _log, Bt, OpConfig, io, traceback):

        _log(f"[优化] 开始参数优化: {self.file_path}")

        # 语法检查
        syntax_ok, syntax_msg = StrategyBacktestWindow._check_python_syntax(self.file_path)
        if not syntax_ok:
            _log(f"[优化] 语法错误: {syntax_msg}")
            self.error_signal.emit(f"语法错误: {syntax_msg}")
            return

        # 加载策略
        strategy_classes = StrategyBacktestWindow._load_strategy_from_file(self.file_path,self.term)
        if not strategy_classes:
            _log("[优化] 错误: 未在文件中找到 Strategy 子类")
            self.error_signal.emit("未找到 Strategy 子类")
            return

        # 查找第一个带有有效 op_config 的策略
        opt_cls = None
        opt_cfg = None
        for cls in strategy_classes:
            cfg = getattr(cls, 'op_config', None)
            if cfg is not None and isinstance(cfg, dict) and 'params' in cfg and cfg['params']:
                opt_cls = cls
                opt_cfg = cfg
                break

        if opt_cls is None:
            _log("[优化] 未找到带 op_config 的策略，回退为普通回测")
            # 使用普通回测
            self._do_normal_backtest(strategy_classes, _log)
            return

        _log(f"[优化] 使用策略: {opt_cls.__name__}")
        _log(f"[优化] 方法: {opt_cfg.get('op_method', 'optuna')}, "
             f"目标: {opt_cfg.get('target', 'profit_ratio')}, "
             f"参数: {opt_cfg['params']}")

        bt = Bt(auto=True)
        bt.addstrategy(opt_cls)
        for s_cls in bt.strategies:
            s_cls._light_chart = True

        # 注入进度回调（仅 optuna 支持）
        # opconfig 可能是 dict 或 OptunaConfig namedtuple
        raw_opconfig = opt_cfg.get('opconfig', {})
        n_trials = 0
        if isinstance(raw_opconfig, tuple) and len(raw_opconfig) == 2:
            # OptunaConfig namedtuple: (optimize_kwargs, study_kwargs)
            optimize_kwargs = raw_opconfig[0]  # dict 引用，可直接修改
            n_trials = optimize_kwargs.get('n_trials', 0)
        elif isinstance(raw_opconfig, dict):
            n_trials = raw_opconfig.get('n_trials', raw_opconfig.get('ngen', 0))

        if n_trials and opt_cfg.get('op_method', 'optuna') == 'optuna':
            class _ProgressCallback:
                def __init__(self, total, emitter):
                    self.total = total
                    self.emitter = emitter

                def __call__(self, study, trial):
                    self.emitter.emit(trial.number + 1, self.total)

            if isinstance(raw_opconfig, tuple) and len(raw_opconfig) == 2:
                cb = raw_opconfig[0].get('callbacks')
                if cb is None:
                    cb = []
                    raw_opconfig[0]['callbacks'] = cb
                cb.append(
                    _ProgressCallback(n_trials, self.progress_signal))
            elif isinstance(raw_opconfig, dict):
                cb = raw_opconfig.get('callbacks')
                if cb is None:
                    cb = []
                    raw_opconfig['callbacks'] = cb
                cb.append(
                    _ProgressCallback(n_trials, self.progress_signal))

        # 配置优化
        bt.optstrategy(
            opt_cfg.get('target', 'profit_ratio'),
            opt_cfg.get('weights', 1.),
            opconfig=raw_opconfig,
            op_method=opt_cfg.get('op_method', 'optuna'),
            show_bar=False,
            **opt_cfg['params']
        )

        # 执行优化 + 回测（bt.run 会自动先优化再回测）
        _capture = io.StringIO()
        _old_stdout = sys.stdout
        _old_stderr = sys.stderr
        try:
            sys.stdout = _capture
            sys.stderr = _capture
            bt.run(isplot=False, close_api=False, model='sequential')
        except Exception:
            traceback.print_exc(file=_capture)
            _log("[优化] 执行异常")
        finally:
            sys.stdout = _old_stdout
            sys.stderr = _old_stderr
            captured = _capture.getvalue()
            if captured.strip():
                for line in captured.split('\n'):
                    if line.strip():
                        _log(line.rstrip())

        # 收集结果
        final_instances = []
        optimization_df_data = []  # 优化 trial 表格数据

        for s in bt.strategies:
            try:
                if hasattr(s, 'profits') and s.profits is not None:
                    final_instances.append(s)
            except Exception:
                pass

        # 收集优化 trial 数据（从 CSV 读取，仅优化模式）
        if opt_cls is not None:
            try:
                import glob, csv
                target_first = opt_cfg.get('target', 'profit_ratio')
                if isinstance(target_first, (list, tuple)):
                    target_first = target_first[0]
                op_path = getattr(bt, '_Bt__op_path', None)
                if not op_path:
                    import minibt as _minibt_pkg
                    op_path = os.path.join(os.path.dirname(_minibt_pkg.__file__), 'op_params')
                csv_pattern = os.path.join(op_path, f'opt_{opt_cls.__name__}_{target_first}*.csv')
                csv_files = glob.glob(csv_pattern)
                if csv_files:
                    csv_files.sort(key=os.path.getmtime, reverse=True)
                    with open(csv_files[0], 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        optimization_df_data = [row for row in reader]
                    _log(f"[优化] 已收集 {len(optimization_df_data)} 条 trial 数据")
            except Exception as e:
                _log(f"[优化] 读取 trial 数据失败: {e}")

        if not final_instances:
            _log("[优化] 所有策略均执行失败")
            self.error_signal.emit("优化执行失败")
            return

        # 显示最优参数
        if hasattr(bt, '_Bt__isoptimize') and final_instances:
            best = final_instances[0]
            _log(f"[优化] 完成，最优参数: {dict(best.params)}")

        _log(f"[优化] 最终 {len(final_instances)} 个策略就绪")
        self.finished_signal.emit(final_instances, optimization_df_data)

    def _do_normal_backtest(self, strategy_classes, _log):
        """回退为普通回测"""
        import io
        import traceback
        from minibt.bt import Bt

        bt = Bt(auto=True)
        for cls in strategy_classes:
            bt.addstrategy(cls)
        for s_cls in bt.strategies:
            s_cls._light_chart = True

        _capture = io.StringIO()
        _old_stdout = sys.stdout
        _old_stderr = sys.stderr
        try:
            sys.stdout = _capture
            sys.stderr = _capture
            bt.run(isplot=False, close_api=False, model='sequential')
        except Exception:
            traceback.print_exc(file=_capture)
        finally:
            sys.stdout = _old_stdout
            sys.stderr = _old_stderr
            captured = _capture.getvalue()
            if captured.strip():
                for line in captured.split('\n'):
                    if line.strip():
                        _log(line.rstrip())

        final_instances = []
        for s in bt.strategies:
            try:
                if hasattr(s, 'profits') and s.profits is not None:
                    final_instances.append(s)
            except Exception:
                pass

        if final_instances:
            self.finished_signal.emit(final_instances, [])  # 普通回测无优化数据
        else:
            self.error_signal.emit("回测未产生结果")


class _BacktestWorker(QObject):
    """后台回测工作类 — 在 QThread 中运行，避免阻塞 UI"""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, file_path: str,term ):
        super().__init__()
        self.file_path = file_path
        self.term = term

    def run(self):
        """在后台线程中执行完整回测流程"""
        import io
        import traceback
        from minibt.bt import Bt

        def _log(msg: str):
            self.log_signal.emit(msg)

        _log(f"[回测] 开始进程内回测: {self.file_path}")

        # 语法检查
        syntax_ok, syntax_msg = StrategyBacktestWindow._check_python_syntax(self.file_path)
        if not syntax_ok:
            _log(f"[回测] 语法错误: {syntax_msg}")
            self.error_signal.emit(f"语法错误: {syntax_msg}")
            return

        # 加载策略
        strategy_classes = StrategyBacktestWindow._load_strategy_from_file(self.file_path,self.term)
        if not strategy_classes:
            _log("[回测] 错误: 未在文件中找到 Strategy 子类")
            self.error_signal.emit("未找到 Strategy 子类")
            return

        names = [c.__name__ for c in strategy_classes]
        _log(f"[回测] 发现 {len(names)} 个策略: {', '.join(names)}")

        final_api = None

        # ================================================================
        # 第1层：原生多策略
        # ================================================================
        bt = Bt(auto=True)
        for cls in strategy_classes:
            bt.addstrategy(cls)
        for s_cls in bt.strategies:
            s_cls._light_chart = True

        _log(f"[回测] 第1层: 原生多策略模式 ({len(bt.strategies)} 个策略, sequential)...")

        # 重定向 stdout/stderr 以捕获 bt.run() 输出
        _capture = io.StringIO()
        _old_stdout = sys.stdout
        _old_stderr = sys.stderr
        try:
            sys.stdout = _capture
            sys.stderr = _capture
            bt.run(isplot=False, close_api=False, model='sequential')
            if bt._api:
                final_api = bt._api
        except Exception:
            traceback.print_exc(file=_capture)
            _log("[回测] 第1层: 部分或全部策略异常")
        finally:
            sys.stdout = _old_stdout
            sys.stderr = _old_stderr
            captured = _capture.getvalue()
            if captured.strip():
                for line in captured.split('\n'):
                    if line.strip():
                        _log(line.rstrip())

        # 收集第1层成功的结果
        results = []
        failed_indices = []
        for i, s in enumerate(bt.strategies):
            try:
                ok = hasattr(s, 'profits') and s.profits is not None
            except Exception:
                ok = False
            if ok:
                results.append((i, s))
            else:
                failed_indices.append(i)

        if failed_indices:
            _log(f"[回测] 第1层完成: {len(results)} 成功, {len(failed_indices)} 失败 "
                 f"({', '.join(names[i] for i in failed_indices)})")

            # ================================================================
            # 第2层：对失败策略逐个用独立 Bt 重试
            # ================================================================
            for fi in failed_indices:
                cls = strategy_classes[fi]
                cname = cls.__name__
                try:
                    bt2 = Bt(auto=True)
                    bt2.addstrategy(cls)
                    for sc in bt2.strategies:
                        sc._light_chart = True
                    _capture2 = io.StringIO()
                    _old_stdout2 = sys.stdout
                    _old_stderr2 = sys.stderr
                    try:
                        sys.stdout = _capture2
                        sys.stderr = _capture2
                        bt2.run(isplot=False, close_api=False, model='sequential')
                        if bt2._api:
                            final_api = bt2._api
                    finally:
                        sys.stdout = _old_stdout2
                        sys.stderr = _old_stderr2
                        captured2 = _capture2.getvalue()
                        if captured2.strip():
                            for line in captured2.split('\n'):
                                if line.strip():
                                    _log(line.rstrip())

                    if bt2.strategies:
                        s2 = bt2.strategies[0]
                        try:
                            ok2 = hasattr(s2, 'profits') and s2.profits is not None
                        except Exception:
                            ok2 = False
                        if ok2:
                            results.append((fi, s2))
                            _log(f"[回测]   [{cname}] 隔离重试成功")
                        else:
                            _log(f"[回测]   [{cname}] 隔离重试仍无结果，已跳过")
                    else:
                        _log(f"[回测]   [{cname}] 未生成实例")

                except Exception as e2:
                    _log(f"[回测]   [{cname}] 隔离重试失败: {e2}")

        # 按原始索引排序
        results.sort(key=lambda x: x[0])
        final_instances = [s for _, s in results]

        if not final_instances:
            _log("[回测] 所有策略均执行失败")
            self.error_signal.emit("所有策略均执行失败")
            return

        _log(f"[回测] 最终: {len(final_instances)} 个策略就绪: "
             f"{', '.join(s.__class__.__name__ for s in final_instances)}")

        self.finished_signal.emit(final_instances)


class StrategyBacktestWindow(QWidget):
    """策略回测窗口 - 左侧代码编辑器+终端，右侧回测结果展示"""

    def __init__(self, parent=None, is_dark_theme: bool = None):
        super().__init__(parent=parent)
        self.setObjectName("StrategyBacktestWindow")
        self.main_window = parent

        # 让 CodeEditorWindow.runPython() 能通过 codeEditorInterface 找到本窗口的终端
        self.codeEditorInterface = self

        # 如果未指定主题，使用系统主题
        if is_dark_theme is None:
            is_dark_theme = isDarkTheme()
        self._is_dark_theme: bool = is_dark_theme

        # 主布局
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        # ==== 外层水平三分割器：文件树 | 代码+终端 | 回测结果 ====
        # 比例 1:5:5 = [1, 5, 5] * 比例因子
        self.mainSplitter = _ToggleButtonSplitter(
            Qt.Orientation.Horizontal, self)
        self.mainSplitter.set_collapse_direction('left')
        
        # self._apply_splitter_style(self.mainSplitter)

        # --- 面板 0：文件树（从 CodeEditorWindow 提取） ---
        self.code_editor = CodeEditorWindow(parent, is_dark_theme)
        self.file_tree = self.code_editor.treeWidget  # TreeWidget 引用
        self.mainSplitter.addWidget(self.file_tree)

        # 将 Run 按钮改为进程内回测
        self._rewire_run_button()

        # --- 面板 1：左侧垂直分割器（代码编辑器 + 终端） ---
        self.leftSplitter = _ToggleButtonSplitter(Qt.Orientation.Vertical, self)
        self.leftSplitter.set_collapse_direction('down')
        self.leftSplitter.addWidget(self.code_editor)
        
        # 下方：终端
        LocalTerm = get_local_term()
        self.terminal = LocalTerm(self, is_dark_theme=is_dark_theme)
        self.leftSplitter.addWidget(self.terminal)
        self.leftSplitter.setStretchFactor(0, 4)
        self.leftSplitter.setStretchFactor(1, 1)
        self.leftSplitter.setSizes([500, 100])

        # --- 面板 2：右侧水平分割器（左侧区域 + 回测结果） ---
        self.rightSplitter = _ToggleButtonSplitter(Qt.Orientation.Horizontal, self)
        self.rightSplitter.set_collapse_direction('right')
        self.rightSplitter.addWidget(self.leftSplitter)

        # 直接创建 BacktestResultPanel（QWidget），通过 splitter 拖拽自由调整大小
        self._result_panel = BacktestResultPanel(
            parent=self, dark=self._is_dark_theme)
        self.rightSplitter.addWidget(self._result_panel)
        self.rightSplitter.setSizes([1, 0])  # 初始状态：收起回测结果面板
        self._result_panel_expanded = False
        
        self.mainSplitter.addWidget(self.rightSplitter)
        self.mainSplitter.setSizes([100, 1000])
        # mainSplitter 是水平方向：
        #   handle 0 (文件树 | 代码+终端): 隐藏左侧文件树，折叠方向='left'
        # self.mainSplitter.set_handle_button(
        #     0, collapse_direction='left',
        #     tooltip="隐藏/显示文件树", toggled_widget=self.file_tree)
        # #   handle 1 (代码+终端 | 回测结果): 隐藏右侧回测结果，折叠方向='right'
        # self.mainSplitter.set_handle_button(
        #     1, collapse_direction='right',
        #     tooltip="隐藏/显示回测结果", toggled_widget=self._result_panel)

        # leftSplitter (垂直): handle 0 (代码 | 终端)
        #   隐藏下方终端，折叠方向='down'
        # self.leftSplitter.set_handle_button(
        #     0, collapse_direction='down',
        #     tooltip="隐藏/显示终端", toggled_widget=self.terminal)

        # 按钮配置完成后，重新应用样式（使有按钮的 splitter 使用宽 handle + 透明背景）
        # self._apply_splitter_style(self.mainSplitter)
        # self._apply_splitter_style(self.leftSplitter)

        # 折叠按钮将在 StrategyBacktestWindow.showEvent 中统一延迟初始化
        # （等待布局完全稳定后再注入，避免 QSplitter 初始化 BUG）

        # 信号连接
        if hasattr(self.terminal, 'finishedSignal') and self.terminal.finishedSignal is not None:
            self.terminal.finishedSignal.connect(self.onTerminalFinished)
        # 终端右键菜单：切换至文件树路径
        if hasattr(self.terminal, 'cd_to_file_tree_path'):
            self.terminal.cd_to_file_tree_path.connect(self._on_terminal_cd_to_file_tree)
        if hasattr(self.code_editor, 'tabInterface') and hasattr(self.code_editor.tabInterface, 'subprocessFinished'):
            self.code_editor.tabInterface.subprocessFinished.connect(
                self.onSubprocessFinished)

        # 创建固定的 BacktestResultPanel 已在 rightSplitter 中完成
        
        # ── Pi Agent 窗口（延迟启动，首次点击时才初始化服务） ──
        from .pi_agent_window import PiAgentWindow, set_active_pi_agent
        self.pi_agent_window = PiAgentWindow(self, auto_start=False)
        set_active_pi_agent(self.pi_agent_window)

        # 外层分割器：PiAgentWindow (可折叠) | 原有 mainSplitter
        self.outerSplitter = _ToggleButtonSplitter(Qt.Orientation.Horizontal, self)
        self.outerSplitter.addWidget(self.pi_agent_window)
        self.outerSplitter.addWidget(self.mainSplitter)
        self.outerSplitter.setSizes([0, 1000])  # PiAgentWindow 初始隐藏
        self.outerSplitter.set_collapse_direction('left')
        self.mainLayout.addWidget(self.outerSplitter)

        # 连接 Pi Agent 切换信号
        self.code_editor.toggle_pi_agent.connect(self._toggle_pi_agent)

        # 连接 Pi Agent 页面刷新信号（仅刷新页面，不重启服务）
        self.code_editor.reload_pi_agent.connect(self._reload_pi_agent)
        # 连接 Pi Agent 服务重载信号（完全重启服务）
        self.code_editor.reload_pi_service.connect(self._reload_pi_service)

        # 连接代码编辑器回测按钮信号
        self.code_editor.run_backtest.connect(self._run_backtest_in_process)

        # 连接 Pi Agent 文件打开信号：点击左侧文件树在 CodeEditor 中打开文件
        self.pi_agent_window.open_file_requested.connect(self._on_pi_open_file)

        # 连接 Pi Agent 服务启动成功信号：页面加载完成后再标记为已启动
        self.pi_agent_window.service_started.connect(self._on_pi_service_started)

        # 连接 Pi Agent 文件树刷新信号：同步刷新 CodeEditor 文件树
        self.pi_agent_window.refresh_file_tree_requested.connect(self._on_pi_refresh_files)

        # 连接 Pi Agent 同步文件夹信号：编辑器切换文件夹
        self.pi_agent_window.sync_folder_requested.connect(self._on_pi_sync_folder)

        # 连接 Pi Agent 文件变更信号：Agent 写入/编辑文件后刷新代码编辑器
        self.pi_agent_window.file_changed_requested.connect(self._on_pi_file_changed)
        # [已禁用] Agent 执行 Python 代码时不再自动触发 PyQt 回测
        # self.pi_agent_window.run_backtest_requested.connect(self._on_pi_run_backtest)

        # 反向同步：编辑器切换文件夹 → 通知 pi-web
        self.code_editor.folder_changed.connect(self._on_editor_folder_changed)

        # 优化进度条（初始隐藏）
        self.opt_progress = ProgressBar(self)
        self.opt_progress.setVisible(False)
        self.opt_progress.setFixedHeight(6)
        self.opt_progress.setRange(0, 100)
        self.opt_progress.setValue(0)
        self.mainLayout.addWidget(self.opt_progress)

        # 初始化 Pickle 检测定时器
        self._pickle_check_timer = QTimer(self)
        self._pickle_check_timer.timeout.connect(self._check_pickle_file)
        self._pickle_check_start_time = 0
        self._pending_strategy_path = None

        # 延迟初始化：终端 cd 到文件树当前路径
        QTimer.singleShot(1500, self._init_terminal_cd)

        # ★ 预初始化 lightweight_charts Chart 类
        # 必须在任何 QWebEngineView 创建前完成 monkey-patch，否则：
        #   先启动 pi-agent-web（创建 QWebEngineView #1）→ 再回测时会因
        #   Chromium GPU 上下文初始化顺序不兼容导致 segfault 闪退。
        # 在窗口构造阶段调用 get_chart_class() 确保 patching 先于一切。
        self._pre_init_chart_class()

    # def showEvent(self, event):
    #     """首次显示时：等待 miniqt 布局稳定后，统一初始化所有 splitter 折叠按钮"""
    #     super().showEvent(event)
    #     QTimer.singleShot(500, _ToggleButtonSplitter.init_all_splitter_buttons)

    @property
    def result_panel(self) -> 'BacktestResultPanel':
        """获取固定的回测结果面板"""
        return getattr(self, '_result_panel', None)

    def _toggle_pi_agent(self):
        """切换 Pi Agent 窗口显示/隐藏（首次显示时启动服务）"""
        sizes = self.outerSplitter.sizes()
        if sizes[0] <= 10:
            # 首次显示时启动服务（不在此处标记已启动，等页面加载成功后再标记）
            if not getattr(self, '_pi_agent_started', False):
                self.pi_agent_window.start()
            self.outerSplitter.setSizes([400, max(1, sizes[0] + sizes[1] - 400)])
        else:
            # 隐藏 PiAgentWindow
            total = sizes[0] + sizes[1]
            self.outerSplitter.setSizes([0, total])

    def _on_pi_service_started(self, success: bool):
        """Pi Agent 服务首次连接成功时标记为已启动"""
        if success:
            self._pi_agent_started = True

    def _reload_pi_agent(self):
        """重新加载 Pi Agent 页面（仅刷新 webview，不重启服务）"""
        if hasattr(self, 'pi_agent_window'):
            self.pi_agent_window.web_view.reload()

    def _reload_pi_service(self):
        """完全重启 pi-agent-web 服务（stop + restart）"""
        if hasattr(self, 'pi_agent_window'):
            self.pi_agent_window._reload_service()

    def _on_pi_open_file(self, file_path: str, file_name: str):
        """处理 Pi Agent 文件树点击，在 CodeEditor 的 TabInterface 中打开文件"""
        if os.path.isfile(file_path):
            self.code_editor.tabInterface.addEditorTab(file_path)

    def _on_pi_refresh_files(self):
        """处理 Pi Agent 文件树刷新，同步刷新 CodeEditor 的文件树"""
        if hasattr(self, 'code_editor'):
            self.code_editor.refreshFileTree()

    def _on_pi_sync_folder(self, folder_path: str):
        """处理 Pi Agent 同步文件夹，将编辑器文件树切换到指定目录"""
        if hasattr(self, 'code_editor'):
            self.code_editor.syncToFolder(folder_path)

    def _on_pi_file_changed(self, paths: list):
        """处理 Pi Agent 写入/编辑文件通知。
        对每个被修改的文件：如果已在编辑器中打开则刷新内容，否则打开新标签页。
        同时刷新文件树以显示新文件。"""
        if not hasattr(self, 'code_editor'):
            return
        for file_path in paths:
            if os.path.isfile(file_path):
                self.code_editor.tabInterface.refreshOrOpenFile(file_path)
        # 刷新文件树，让新创建的文件可见
        self.code_editor.refreshFileTree()

    # [已禁用] Agent 执行的 Python 代码是其自身的工具调用，PyQt 不需要自动运行回测
    # def _on_pi_run_backtest(self, file_path: str):
    #     """处理 Pi Agent 运行回测请求。
    #     模型通过 bash 执行 python *.py 时触发：先在编辑器中打开文件，再自动执行回测。"""
    #     if not hasattr(self, 'code_editor') or not os.path.isfile(file_path):
    #         return
    #     # 在编辑器中打开文件
    #     self.code_editor.tabInterface.refreshOrOpenFile(file_path)
    #     # 切换到该文件为当前标签页
    #     self.code_editor.tabInterface.switchToFile(file_path)
    #     # 执行回测
    #     self._run_backtest_in_process()

    def _on_editor_folder_changed(self, folder_path: str):
        """编辑器切换文件夹时，同步到 pi-web 并让终端切换到该目录"""
        if hasattr(self, 'pi_agent_window'):
            self.pi_agent_window.set_pi_cwd(folder_path)
        # 终端跟进 cd 到对应路径
        if hasattr(self, 'terminal') and hasattr(self.terminal, 'sendData'):
            self.terminal.sendData(f'cd "{folder_path}"\r')

    def _on_terminal_cd_to_file_tree(self):
        """终端右键菜单：将终端切换到文件树的当前目录"""
        if hasattr(self, 'code_editor') and hasattr(self.code_editor, 'root_directory'):
            path = self.code_editor.root_directory
            if path and hasattr(self, 'terminal') and hasattr(self.terminal, 'sendData'):
                self.terminal.sendData(f'cd "{path}"\r')

    def _init_terminal_cd(self):
        """初始化时：终端 cd 到文件树当前路径"""
        if hasattr(self, 'code_editor') and hasattr(self.code_editor, 'root_directory'):
            path = self.code_editor.root_directory
            if path and hasattr(self, 'terminal') and hasattr(self.terminal, 'sendData'):
                self.terminal.sendData(f'cd "{path}"\r')

    def _pre_init_chart_class(self):
        """预初始化 lightweight_charts Chart 类，确保 monkey-patch 在任何 QWebEngineView 创建前完成
        
        先启动 pi-agent-web 再回测时会闪退（无报错 segfault），根因是：
        pi-agent-web 的 QWebEngineView 先初始化 Chromium GPU 上下文，
        然后 lightweight_charts 在 get_chart_class() 中 monkey-patch 并创建新的
        QWebEngineView 时产生 GPU 上下文冲突。
        
        在窗口构造阶段提前调用 get_chart_class() 完成 patching，
        确保 Chromium 初始化顺序一致，避免冲突。
        """
        try:
            from minibt.strategy.light_chart_replay import get_chart_class
            get_chart_class()
        except Exception:
            pass  # 预初始化失败不影响窗口正常使用

    @property
    def is_dark_theme(self) -> bool:
        return self._is_dark_theme

    @is_dark_theme.setter
    def is_dark_theme(self, value: bool):
        self._is_dark_theme = value
        if hasattr(self, 'code_editor'):
            self.code_editor.is_dark_theme = value
        if hasattr(self, 'terminal'):
            self.terminal.setTheme(value)
        if hasattr(self, '_result_panel') and self._result_panel:
            self._result_panel.set_dark(value)
        # 主题切换时更新 Splitter 间隙样式
        for sp in [getattr(self, 'outerSplitter', None),
                   getattr(self, 'mainSplitter', None),
                   getattr(self, 'leftSplitter', None),
                   getattr(self, 'rightSplitter', None),
                   getattr(self, 'codeSplitter', None)]:
            if sp is not None:
                self._apply_splitter_style(sp)

    def _apply_splitter_style(self, splitter: QSplitter):
        """为 QSplitter 设置固定宽度的间隙样式（深色/浅色通用）

        对于 _ToggleButtonSplitter，无论有没有折叠按钮，都使用 _SplitterHandle.paintEvent 绘制，
        不使用样式表（否则样式冲突）。
        """
        from qfluentwidgets import isDarkTheme
        
        # 判断是否是 _ToggleButtonSplitter（无论有没有按钮）
        is_toggle_splitter = isinstance(splitter, _ToggleButtonSplitter)
        
        splitter.setHandleWidth(4)
        splitter.setChildrenCollapsible(False)

        if is_toggle_splitter:
            # _ToggleButtonSplitter 的 handle 都是 _SplitterHandle，通过 paintEvent 绘制
            # 必须清除样式表，否则 QSS 引擎会干扰子控件渲染
            splitter.setStyleSheet("")
        else:
            # 普通 QSplitter 使用样式表绘制 handle
            # 深浅通用：半透明中性灰，在两种主题下都有良好对比度
            if isDarkTheme():
                bg_color = "rgba(255, 255, 255, 0.08)"
            else:
                bg_color = "rgba(0, 0, 0, 0.06)"
            splitter.setStyleSheet(f"""
                QSplitter::handle {{
                    background-color: {bg_color};
                    border: none;
                }}
                QSplitter::handle:hover {{
                    background-color: rgba(100, 150, 200, 0.25);
                }}
                QSplitter::handle:pressed {{
                    background-color: rgba(100, 150, 200, 0.4);
                }}
            """)

    def get_code_editor(self):
        """获取代码编辑器窗口"""
        return self.code_editor

    def get_terminal(self):
        """获取终端窗口"""
        return self.terminal

    def closeEvent(self, event):
        """关闭窗口时停止后台回测/优化线程及 Pi Agent 服务"""
        for attr in ('_backtest_thread', '_opt_thread'):
            try:
                t = getattr(self, attr, None)
                if t is not None and t.isRunning():
                    t.quit()
                    t.wait(3000)
            except RuntimeError:
                pass
        # 停止 Pi Agent 服务
        if hasattr(self, 'pi_agent_window') and self.pi_agent_window:
            self.pi_agent_window.close()
        super().closeEvent(event)

    def get_result_view(self) -> 'BacktestResultPanel':
        """获取固定的回测结果面板（QWidget，可通过 splitter 拖拽调整大小）"""
        return getattr(self, '_result_panel', None)

    def onTerminalFinished(self, command: str, output: str):
        """终端命令执行完成回调"""
        # print(f"命令执行完成: {command}")
        # print(f"输出: {output[:500]}...")  # 只打印前500字符

        # 检测是否是回测命令（包含 .py 文件执行）
        if command.endswith('.py"') or command.endswith('.py'):
            # 获取当前打开的策略文件
            current_editor = self.code_editor.tabInterface.getCurrentEditor()
            if current_editor:
                file_path = getattr(current_editor, 'file_path', None)
                if file_path:
                    # 保存策略路径并启动 Pickle 检测定时器
                    self._pending_strategy_path = file_path
                    self._pickle_check_start_time = 0
                    self._pickle_check_timer.start(JSON_CHECK_INTERVAL)
                    # print(f"开始检测回测结果 Pickle 文件...")

    def _openBacktestResult(self, html_path: str):
        """打开回测结果 HTML 文件，使用 QWebEngineView 内嵌显示（旧版接口，已废弃）"""
        pass

    def _createBacktestResultFromData(self, strategy_path: str, output: str):
        """从回测数据创建结果窗口"""
        # print(f"策略: {strategy_path}")
        # print("回测数据解析逻辑待实现...")
        pass

    def _display_result_from_data(self, plot_data: dict, strategy_name: str):
        """直接从数据字典更新固定回测结果面板（无需创建新面板）"""
        panel = self._result_panel
        if panel:
            panel.load_result(plot_data, strategy_name)
        #     print(f"[回测结果] 面板已更新: {strategy_name}")
        # else:
        #     print("[回测结果] 错误: 固定面板不存在")

    def onSubprocessFinished(self, file_path: str, return_code: int):
        """子进程运行完成回调"""
        print(f"子进程执行完成: {file_path}, 返回码: {return_code}")

        # 检测是否是 Python 文件
        if file_path and file_path.lower().endswith('.py'):
            # 启动 Pickle 检测定时器
            self._pending_strategy_path = file_path
            self._pickle_check_start_time = 0
            self._pickle_check_timer.start(JSON_CHECK_INTERVAL)
            # print(f"开始检测回测结果 Pickle 文件...")

    def _check_pickle_file(self):
        """定时检查 JSON 回测结果文件是否已生成（子进程回测完成后由 Strategy 生成）"""
        self._pickle_check_start_time += JSON_CHECK_INTERVAL
        if self._pickle_check_start_time >= JSON_CHECK_TIMEOUT * 1000:
            print("回测结果 JSON 检测超时")
            self._stop_pickle_check()
            return

        json_path = self._backtest_result_path()
        if os.path.exists(json_path):
            # print(f"检测到回测结果文件: {json_path}")
            self._stop_pickle_check()
            self._load_static_charts(json_path)

    def _stop_pickle_check(self):
        """停止检测定时器"""
        if self._pickle_check_timer.isActive():
            self._pickle_check_timer.stop()
        self._pending_strategy_path = None

    @staticmethod
    def _backtest_result_path() -> str:
        """回测结果 JSON 文件路径"""
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "..", "..", "minibt", "strategy", "backtest_result.json")
        return os.path.normpath(p)

    def _load_static_charts(self, json_path: str = None):
        """加载 JSON 回测结果并展示到固定面板"""
        import json
        import traceback
        import pandas as pd

        if json_path is None:
            json_path = self._backtest_result_path()

        if not os.path.exists(json_path):
            # print("回测结果 JSON 文件不存在")
            return

        # ----- JSON 反序列化器：将 __type__ 标记还原为 DataFrame/Series -----
        def _from_json_safe(obj):
            """递归还原 JSON 数据中标记的 DataFrame/Series/numpy 数组"""
            if isinstance(obj, dict):
                type_tag = obj.get('__type__')
                if type_tag == 'DataFrame':
                    cols = obj.get('columns', [])
                    data = obj.get('data', {})
                    return pd.DataFrame({c: data[c] for c in cols if c in data})
                elif type_tag == 'Series':
                    return pd.Series(obj.get('data', []))
                return {k: _from_json_safe(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_from_json_safe(v) for v in obj]
            return obj

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            plot_data = _from_json_safe(raw_data)

            strategy_name = plot_data.get("strategy_name", "Unknown") if isinstance(
                plot_data, dict) else "Unknown"
            # print(f"加载回测结果: {strategy_name}")



            self._display_result_from_data(plot_data, strategy_name)

            try:
                os.remove(json_path)
                print(f"已删除回测结果文件: {json_path}")
            except Exception as e:
                print(f"删除文件失败: {e}")

        except Exception as e:
            traceback.print_exc()
            print(f"加载 JSON 失败: {e}")

    # ============================================================
    # 进程内回测（参考 Bt.addstrategy + signal_backtest._build_strategy_result）
    # ============================================================
    def _rewire_run_button(self):
        """将 TabInterface 的 Run 菜单改接为进程内回测 + 参数优化 + 子进程运行"""
        tab = self.code_editor.tabInterface
        if not hasattr(tab, 'runMenu'):
            return
        tab.runMenu.clear()
        # 添加"运行（进程内回测）"
        action = Action(FIF.PLAY, "运行（进程内回测）", self)
        action.triggered.connect(self._run_backtest_in_process)
        tab.runMenu.addAction(action)
        # 添加"参数优化"
        action_opt = Action(FIF.SYNC, "参数优化", self)
        action_opt.triggered.connect(self._run_optimization)
        tab.runMenu.addAction(action_opt)
        # 添加"运行（子进程运行）"
        tab.runMenu.addSeparator()
        action_sub = Action(FIF.ADD, "运行（子进程运行）", self)
        action_sub.triggered.connect(lambda: tab.runPython(sys.executable))
        tab.runMenu.addAction(action_sub)

    def _run_backtest_in_process(self):
        """进程内回测：在后台线程中动态加载策略类并执行回测，避免 UI 卡死"""
        current_editor = self.code_editor.tabInterface.getCurrentEditor()
        if not current_editor:
            return

        file_path = getattr(current_editor, 'file_path', None)
        if not file_path or not file_path.lower().endswith('.py'):
            print("[回测] 请先保存 Python 文件")
            return

        # 保存文件
        current_editor.save()

        # 禁用运行按钮，防止重复点击
        tab = self.code_editor.tabInterface
        if hasattr(tab.tabBar, 'runbutn'):
            tab.tabBar.runbutn.setEnabled(False)

        # 启动后台线程执行回测
        self._backtest_thread = QThread(self)
        self._backtest_worker = _BacktestWorker(file_path,self.get_terminal())
        self._backtest_worker.moveToThread(self._backtest_thread)

        self._backtest_worker.log_signal.connect(self._on_backtest_log)
        self._backtest_worker.finished_signal.connect(self._on_backtest_finished)
        self._backtest_worker.error_signal.connect(self._on_backtest_error)

        self._backtest_thread.started.connect(self._backtest_worker.run)
        self._backtest_worker.finished_signal.connect(self._backtest_thread.quit)
        self._backtest_worker.error_signal.connect(self._backtest_thread.quit)
        self._backtest_thread.finished.connect(self._backtest_thread.deleteLater)

        self._backtest_thread.start()

    def _on_backtest_log(self, msg: str):
        """接收后台线程的日志并输出到终端"""
        term = self.get_terminal()
        if hasattr(term, 'write_msg'):
            term.write_msg(msg)

    def _on_backtest_finished(self, final_instances: list):
        """后台回测完成，更新结果面板"""
        # 恢复运行按钮
        tab = self.code_editor.tabInterface
        if hasattr(tab.tabBar, 'runbutn'):
            tab.tabBar.runbutn.setEnabled(True)

        panel = self._result_panel
        if panel:
            # 首次出结果时展开回测结果面板
            if not getattr(self, '_result_panel_expanded', False):
                self._result_panel_expanded = True
                self.rightSplitter.setSizes([500, 500])
            panel.load_results_from_strategies(final_instances)

    def _on_backtest_error(self, error_msg: str):
        """后台回测出错"""
        # 恢复运行按钮
        tab = self.code_editor.tabInterface
        if hasattr(tab.tabBar, 'runbutn'):
            tab.tabBar.runbutn.setEnabled(True)

        term = self.get_terminal()
        if hasattr(term, 'write_msg'):
            term.write_msg(f"[回测] 错误: {error_msg}")
        
        # InfoBar 提醒
        title = "语法错误" if "语法" in error_msg else "回测错误"
        InfoBar.error(title, error_msg, duration=5000, parent=self, position=InfoBarPosition.TOP_RIGHT)

    # ============================================================
    # 参数优化
    # ============================================================
    def _run_optimization(self):
        """参数优化：在后台线程中执行 optimize + backtest，避免 UI 卡死"""
        current_editor = self.code_editor.tabInterface.getCurrentEditor()
        if not current_editor:
            return

        file_path = getattr(current_editor, 'file_path', None)
        if not file_path or not file_path.lower().endswith('.py'):
            print("[优化] 请先保存 Python 文件")
            return

        current_editor.save()

        # 禁用运行按钮
        tab = self.code_editor.tabInterface
        if hasattr(tab.tabBar, 'runbutn'):
            tab.tabBar.runbutn.setEnabled(False)

        # 显示进度条
        if hasattr(self, 'opt_progress'):
            self.opt_progress.setValue(0)
            self.opt_progress.setVisible(True)

        # 启动后台线程
        self._opt_thread = QThread(self)
        self._opt_worker = _OptimizationWorker(file_path,self.get_terminal())
        self._opt_worker.moveToThread(self._opt_thread)

        self._opt_worker.log_signal.connect(self._on_opt_log)
        self._opt_worker.progress_signal.connect(self._on_opt_progress)
        self._opt_worker.finished_signal.connect(self._on_opt_finished)
        self._opt_worker.error_signal.connect(self._on_opt_error)

        self._opt_thread.started.connect(self._opt_worker.run)
        self._opt_worker.finished_signal.connect(self._opt_thread.quit)
        self._opt_worker.error_signal.connect(self._opt_thread.quit)
        self._opt_thread.finished.connect(self._opt_thread.deleteLater)

        self._opt_thread.start()

    def _on_opt_log(self, msg: str):
        """优化日志输出到终端"""
        term = self.get_terminal()
        if hasattr(term, 'write_msg'):
            term.write_msg(msg)

    def _on_opt_progress(self, current: int, total: int):
        """更新优化进度条"""
        if hasattr(self, 'opt_progress') and total > 0:
            self.opt_progress.setRange(0, total)
            self.opt_progress.setValue(current)

    def _on_opt_finished(self, final_instances: list, optimization_df_data: list = None):
        """优化完成，更新结果面板"""
        # 恢复运行按钮 + 隐藏进度条
        tab = self.code_editor.tabInterface
        if hasattr(tab.tabBar, 'runbutn'):
            tab.tabBar.runbutn.setEnabled(True)
        if hasattr(self, 'opt_progress'):
            self.opt_progress.setVisible(False)

        panel = self._result_panel
        if panel and final_instances:
            # 首次出结果时展开回测结果面板
            if not getattr(self, '_result_panel_expanded', False):
                self._result_panel_expanded = True
                self.rightSplitter.setSizes([500, 500])
            panel.load_results_from_strategies(final_instances, optimization_df_data or [])
            # 显示最优参数提示
            best = final_instances[0]
            if hasattr(best, 'params'):
                InfoBar.success(
                    '优化完成',
                    f"最优参数: {dict(best.params)}",
                    duration=5000,
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self
                )

    def _on_opt_error(self, error_msg: str):
        """优化出错"""
        tab = self.code_editor.tabInterface
        if hasattr(tab.tabBar, 'runbutn'):
            tab.tabBar.runbutn.setEnabled(True)
        if hasattr(self, 'opt_progress'):
            self.opt_progress.setVisible(False)

        term = self.get_terminal()
        if hasattr(term, 'write_msg'):
            term.write_msg(f"[优化] 错误: {error_msg}")
        
        # InfoBar 提醒
        title = "语法错误" if "语法" in error_msg else "优化错误"
        InfoBar.error(title, error_msg, duration=5000, parent=self, position=InfoBarPosition.TOP_RIGHT)

    @staticmethod
    def _check_python_syntax(file_path: str):
        """检查 Python 文件的语法是否正确"""
        import py_compile
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            compile(source, file_path, 'exec')
            return True, ""
        except SyntaxError as e:
            line_info = f"行 {e.lineno}: {e.msg}"
            if e.text:
                code_line = e.text.strip()
                line_info += f"\n  >>> {code_line}"
            return False, line_info

    @staticmethod
    def _load_strategy_from_file(file_path: str,term):
        """从 .py 文件动态加载所有 Strategy 子类"""
        import importlib
        import importlib.util
        from pathlib import Path
        from minibt.strategy.strategy import Strategy

        py_file = Path(file_path)
        if py_file.suffix.lower() != '.py':
            return []

        module_name = py_file.stem
        file_dir = str(py_file.parent.resolve())

        # 清除模块缓存
        keys_to_remove = [k for k in list(sys.modules.keys())
                          if k == module_name or k.endswith(f'.{module_name}')]
        for k in keys_to_remove:
            del sys.modules[k]

        if file_dir not in sys.path:
            sys.path.insert(0, file_dir)

        module = None
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            spec = importlib.util.spec_from_file_location(
                module_name, str(py_file.resolve()))
            if spec is None or spec.loader is None:
                # print(f"[回测] 无法导入文件: {py_file}")
                return []
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                print(f"[回测] 执行模块失败: {e}")
                return []
        except Exception as e:
            print(f"[回测] 导入模块失败: {e}")
            return []

        # 查找所有 Strategy 子类
        found_classes = []
        for attr_name in dir(module):
            obj = getattr(module, attr_name, None)
            if (isinstance(obj, type)
                    and issubclass(obj, Strategy)
                    and obj is not Strategy):
                found_classes.append(obj)

        if not found_classes:
            term.write_msg("[回测] 模块中没有找到 Strategy 子类")
        else:
            term.write_msg(f"[回测] 找到 {len(found_classes)} 个策略: "
                                        f"{', '.join(c.__name__ for c in found_classes)}")

        return found_classes

    def _display_result_from_strategy_instance(self, s, strategy_name: str):
        """委托给 BacktestResultPanel.load_result_from_strategy"""
        panel = self._result_panel
        if panel:
            panel.load_result_from_strategy(s, strategy_name)
        # else:
        #     print("[回测结果] 错误: 固定面板不存在")

    def _removeResultCard(self, card: ResultCard):
        """从面板移除结果卡片（旧版接口）"""
        panel = self.get_result_view()
        if hasattr(panel, 'vBoxLayout') and panel.vBoxLayout:
            panel.vBoxLayout.removeWidget(card)
        card.hide()
        card.deleteLater()