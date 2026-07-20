from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMdiArea, QMdiSubWindow, QSplitter, QLabel, QHBoxLayout, QSizePolicy, QApplication
from PyQt6.QtCore import Qt, QPoint, QObject, QEvent
from qfluentwidgets import (FluentWindow, SubtitleLabel, CardWidget, PushButton,
                            LargeTitleLabel, InfoBar, InfoBarPosition, RoundMenu,
                            Action, FluentIcon, CommandBar, TransparentDropDownPushButton,
                            TransparentPushButton)
from typing import TYPE_CHECKING
from .chart_interface import LightChartWindow
from .strategy_backtest_window import _ToggleButtonSplitter

if TYPE_CHECKING:
    from ..view.main_window import MainWindow


class _KeyElfGlobalFilter(QObject):
    """全局事件过滤器，处理 WebView 抢占焦点的情况"""

    def __init__(self, market_watch: 'MarketWatchWindow'):
        super().__init__()
        self.market_watch = market_watch

    def eventFilter(self, obj, event):
        # 只处理键盘按下事件
        if event.type() == QEvent.Type.KeyPress:
            # 检查是否是空格键
            if event.key() == Qt.Key.Key_Space:
                # 检查 MarketWatchWindow 是否可见且有当前图表
                if (self.market_watch.isVisible() and
                        self.market_watch.key_elf_enabled and
                        self.market_watch.current_widget is not None):
                    # 触发键盘精灵
                    self.market_watch.show_key_elf()
                    return True  # 消费事件
        return super().eventFilter(obj, event)


class MarketWatchWindow(QWidget):
    """看盘模块窗口"""

    def __init__(self, parent=None, symbol: str = "", cycle: int = 60, length: int = 1000, is_stock: bool = False):
        super().__init__(parent)
        if symbol:
            self.setObjectName(f"{symbol}")
        else:
            self.setObjectName(f"MarketWatchWindow")
        self.main_window: MainWindow = parent
        self.symbol = symbol
        self.cycle = cycle
        self.length = length
        self.is_stock = is_stock
        # 记录插入位置
        self.insert_position = "right"  # 默认右侧
        # 初始化窗口计数
        self.window_count = 0

        # 初始化主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 创建工具栏
        self.create_toolbar()

        # 创建QSplitter作为主框架
        self.main_splitter = _ToggleButtonSplitter(Qt.Orientation.Horizontal, self)
        self.main_splitter.setHandleWidth(4)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # 启用右键菜单
        self.main_splitter.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.main_splitter.customContextMenuRequested.connect(self.show_context_menu)
        self.main_layout.addWidget(self.main_splitter, stretch=1)

        # 检查API是否已连接
        is_api_connected = False
        if self.is_stock:
            # 股票模式：检查 stock_api
            if hasattr(self.main_window, 'stock_api') and self.main_window.stock_api is not None:
                is_api_connected = True
            elif hasattr(self.main_window, 'login_status') and self.main_window.login_status.get('stock', False):
                is_api_connected = True
        else:
            # 期货模式：检查 tq_api
            if hasattr(self.main_window, 'tq_api') and self.main_window.tq_api is not None:
                is_api_connected = True
            elif hasattr(self.main_window, 'login_status') and self.main_window.login_status.get('futures', False):
                is_api_connected = True

        # 如果API已连接且提供了合约名称，则直接打开K线窗口
        if is_api_connected and self.symbol:
            # 检查是否是第一个板块，如果是则销毁初始提示窗口并显示工具栏
            if self.window_count == 0 and hasattr(self, 'initial_prompt_window') and self.initial_prompt_window:
                self.initial_prompt_window.setParent(None)
                self.initial_prompt_window.deleteLater()
                self.initial_prompt_window = None

            # 增加窗口计数
            self.window_count += 1
            self._update_close_button_state()

            # 创建K线窗口
            symbol_type = "STOCK" if self.is_stock else "FUTURES"
            content_widget = LightChartWindow(
                self.main_window, self, symbol=self.symbol, cycle=self.cycle, length=self.length,
                enable_subwindow_menu=True, marketWatchWindow=self, symbol_type=symbol_type
            )
            # 显示工具栏和分隔线
            self.toolbar.show()
            self.separator.show()
            # 启用右键菜单
            content_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            content_widget.customContextMenuRequested.connect(lambda pos, widget=content_widget: self.show_context_menu(pos, widget))

            # 添加点击事件，设置最后点击的窗口
            original_mouse_press = content_widget.mousePressEvent

            def custom_mouse_press(event):
                self.set_last_clicked_widget(content_widget)
                if original_mouse_press:
                    original_mouse_press(event)
            content_widget.mousePressEvent = custom_mouse_press

            # 添加到主Splitter
            self.main_splitter.addWidget(content_widget)

            # 设置为当前窗口和最后点击的窗口
            self.set_last_clicked_widget(content_widget)

            # 平铺子窗口
            self.tile_sub_windows()

            # 更新关闭按钮状态
            self._update_close_button_state()
        else:
            # 创建初始空白提示窗口
            self.create_initial_prompt_window()

            # 记录当前右键点击的子窗口和最后点击的板块窗口
            self.current_widget = None
            self.last_clicked_widget = None

        # 记录上下文菜单位置
        self.context_menu_position = QPoint()

        # 键盘精灵相关属性
        self.key_elf_enabled = True  # 是否允许打开键盘精灵
        self.key_elf_window = None  # 键盘精灵窗口引用
        self.symbol_search_data = None  # 合约搜索数据（用于键盘精灵）

        # 初始化搜索数据
        self._init_symbol_search_data()

        # 安装全局事件过滤器（处理 WebView 抢占焦点的情况）
        self._key_elf_global_filter = _KeyElfGlobalFilter(self)
        QApplication.instance().installEventFilter(self._key_elf_global_filter)

    def keyPressEvent(self, event):
        """键盘事件处理"""
        # 检查是否是空格键
        if event.key() == Qt.Key.Key_Space:
            # 检查键盘精灵是否启用且有当前图表
            if self.key_elf_enabled and self.current_widget is not None:
                self.show_key_elf()
                event.accept()
                return
        # 其他键盘事件传递给父类
        super().keyPressEvent(event)

    def _init_symbol_search_data(self):
        """初始化合约搜索数据"""
        try:
            from ..common.database_manager import get_db_manager
            db_manager = get_db_manager()

            if db_manager is None:
                return

            # 先尝试从搜索表获取数据
            search_df = db_manager.get_search_table()

            if search_df is not None and not search_df.empty:
                # 搜索表有数据，直接使用
                self.symbol_search_data = search_df.values.tolist()
                # print(f"[MarketWatchWindow] 从搜索表加载了 {len(self.symbol_search_data)} 条合约数据")
            else:
                # 搜索表没有数据，从 symbol_info 表创建
                symbol_info_df = db_manager.get_symbol_info()

                if symbol_info_df is not None and not symbol_info_df.empty:
                    # 从 symbol_info 创建搜索数据
                    search_data = []
                    for _, row in symbol_info_df.iterrows():
                        code = row.get('instrument_id', '')
                        name = row.get('instrument_name', '')
                        type_str = row.get('ins_class', '')
                        exchange = row.get('exchange_id', '')

                        if code and name:
                            search_data.append([code, name, type_str, exchange])

                    self.symbol_search_data = search_data

                    # 同时保存到数据库搜索表
                    if search_data:
                        import pandas as pd
                        new_search_df = pd.DataFrame(search_data, columns=['code', 'name', 'type', 'exchange'])
                        db_manager.save_symbol_info(symbol_info_df)  # 这会自动更新搜索表

                    # print(f"[MarketWatchWindow] 从 symbol_info 创建了 {len(self.symbol_search_data)} 条搜索数据")
                else:
                    # symbol_info 表也没有数据，搜索数据为空
                    self.symbol_search_data = []
                    # print("[MarketWatchWindow] 数据库中没有合约数据")

        except Exception as e:
            print(f"[MarketWatchWindow] 初始化搜索数据失败: {e}")
            self.symbol_search_data = []

    def create_toolbar(self):
        """创建工具栏"""
        # 创建CommandBar
        self.toolbar = CommandBar(self)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # 第一组工具：周期选择
        period_texts = ["30秒", "1分", "5分", "15分", "30分", "1时", "1日", "自"]
        periods = [30, 60, 5 * 60, 15 * 60, 30 * 60, 60 * 60, 60 * 60 * 24, None]
        width = [55, 48, 48, 52, 52, 45, 45, 35]
        for text, period, w in zip(period_texts, periods, width):
            button = TransparentPushButton(text, self)
            button.setFixedWidth(w)
            if period is not None:
                button.clicked.connect(lambda checked, p=period: self.on_period_button_clicked(p))
            else:
                # "自"按钮：点击显示自定义周期菜单
                button.clicked.connect(self._show_custom_period_menu)
            self.toolbar.addWidget(button)
        
        # 保存"自"按钮引用，用于菜单定位
        self.custom_period_button = button

        self.toolbar.addSeparator()

        # 第二组工具：功能按钮
        indicator_button = TransparentPushButton("指标", self, FluentIcon.INFO)
        indicator_button.setFixedHeight(34)
        from .indicator_window import IndicatorWindow

        def on_indicator_button_clicked():
            indicator_window = IndicatorWindow(self.main_window, self)
            indicator_window.show()
        indicator_button.clicked.connect(on_indicator_button_clicked)
        self.toolbar.addWidget(indicator_button)

        draw_action = Action(FluentIcon.ERASE_TOOL, "画线")
        draw_action.triggered.connect(self._on_draw_line_button_clicked)
        self.toolbar.addAction(draw_action)

        draw_clear_action = Action(FluentIcon.DELETE, "清除画线")
        draw_clear_action.triggered.connect(self._on_draw_line_clear_button_clicked)
        self.toolbar.addAction(draw_clear_action)

        self.insert_button = TransparentPushButton("插入位置", self, FluentIcon.LAYOUT)
        self.insert_button.clicked.connect(self._show_insert_position_menu)
        self.insert_button.setFixedHeight(34)
        self.toolbar.addWidget(self.insert_button)

        self.add_button = TransparentPushButton("添加板块", self, FluentIcon.ADD)
        self.add_button.clicked.connect(self._show_add_section_menu)
        self.add_button.setFixedHeight(34)
        self.toolbar.addWidget(self.add_button)

        self.close_action = Action(FluentIcon.CLOSE, "关闭")
        self.close_action.triggered.connect(self._on_close_button_clicked)
        self.toolbar.addAction(self.close_action)

        self._update_close_button_state()

        # self.toolbar.addHiddenActions([
        #     Action(FluentIcon.SETTING, "设置", shortcut="Ctrl+S"),
        #     Action(FluentIcon.HELP, "帮助", shortcut="F1")
        # ])

        self.main_layout.addWidget(self.toolbar)

        self.separator = QWidget()
        self.separator.setFixedHeight(1)
        from qfluentwidgets import isDarkTheme
        if isDarkTheme():
            self.separator.setStyleSheet("background-color: #333333;")
        else:
            self.separator.setStyleSheet("background-color: #e0e0e0;")
        self.main_layout.addWidget(self.separator)
        self.separator.hide()
        self.toolbar.hide()

    def _on_draw_line_button_clicked(self):
        """处理画线按钮点击事件"""
        widget = self.get_last_clicked_widget()
        if hasattr(widget, '_tool'):
            widget._tool()

    def _on_draw_line_clear_button_clicked(self):
        """处理清除画线按钮点击事件"""
        widget = self.get_last_clicked_widget()
        if hasattr(widget, '_clear_all_drawings'):
            widget._clear_all_drawings()

    def create_initial_prompt_window(self):
        """创建初始空白提示窗口"""
        prompt_widget = QWidget()
        layout = QVBoxLayout(prompt_widget)

        prompt_label = LargeTitleLabel("请添加板块")
        prompt_label.setWordWrap(True)
        prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(prompt_label)

        info_label = SubtitleLabel("右键点击空白处添加板块")
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)

        prompt_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        prompt_widget.customContextMenuRequested.connect(lambda pos, widget=prompt_widget: self.show_context_menu(pos, widget))

        self.main_splitter.addWidget(prompt_widget)
        self.initial_prompt_window = prompt_widget

    def add_market_watch_window(self, contract_name, period_milliseconds=60000):
        """添加看盘子窗口"""
        if self.window_count == 0 and self.initial_prompt_window:
            self.initial_prompt_window.setParent(None)
            self.initial_prompt_window.deleteLater()
            self.initial_prompt_window = None
            self.toolbar.show()
            self.separator.show()

        if self.window_count == 0:
            if hasattr(self.main_window, 'login_status'):
                if not self.main_window.login_status.get('futures', False):
                    InfoBar.warning(
                        '登录提示',
                        '请先登录期货账户后添加看盘板块',
                        duration=2000,
                        position=InfoBarPosition.TOP_RIGHT,
                        parent=self
                    )
                    if hasattr(self.main_window, 'show_login_window'):
                        self.main_window.show_login_window()
                    return None
            else:
                if hasattr(self.main_window, 'tq_api') and self.main_window.tq_api is None:
                    InfoBar.warning(
                        '登录提示',
                        '请先登录期货账户后添加看盘板块',
                        duration=2000,
                        position=InfoBarPosition.TOP_RIGHT,
                        parent=self
                    )
                    if hasattr(self.main_window, 'show_login_window'):
                        self.main_window.show_login_window()
                    return None

        if self.window_count >= 9:
            InfoBar.warning(
                '已达到最大板块数量',
                '最多可创建9个板块',
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )
            return None

        self.window_count += 1
        self._update_close_button_state()
        content_widget = self.create_content_widget(contract_name, period_milliseconds)

        # 根据插入位置添加窗口
        self._insert_widget_at_position(content_widget)

        # 只更新 last_clicked_widget，不更新 current_widget
        self.last_clicked_widget = content_widget

        self.tile_sub_windows()
        self._update_close_button_state()

        return content_widget

    def create_content_widget(self, contract_name, period_milliseconds=60000):
        """创建子窗口内容"""
        symbol_type = "STOCK" if self.is_stock else "FUTURES"
        content_widget = LightChartWindow(
            self.main_window, self, symbol=contract_name, cycle=self.cycle, length=self.length,
            period_milliseconds=period_milliseconds, enable_subwindow_menu=True,
            symbol_type=symbol_type
        )
        content_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        content_widget.customContextMenuRequested.connect(lambda pos, widget=content_widget: self.show_context_menu(pos, widget))

        original_mouse_press = content_widget.mousePressEvent

        def custom_mouse_press(event):
            self.set_last_clicked_widget(content_widget)
            if original_mouse_press:
                original_mouse_press(event)
        content_widget.mousePressEvent = custom_mouse_press
        return content_widget

    def _insert_widget_at_position(self, new_widget):
        """根据 insert_position 决定新窗口的插入位置

        - left/right: 在水平 splitter 中直接插入（同一行，左右排列）
        - top/bottom: 在水平 splitter 中创建嵌套垂直 splitter（上下排列）
        """
        if self.main_splitter.count() == 0:
            self.main_splitter.addWidget(new_widget)
            return

        ref_widget = self.current_widget or self.last_clicked_widget
        if ref_widget is None:
            self.main_splitter.addWidget(new_widget)
            return

        ref_index = self.main_splitter.indexOf(ref_widget)
        if ref_index < 0:
            self.main_splitter.addWidget(new_widget)
            return

        position = self.insert_position

        # 判断插入方向需要的 splitter 方向
        if position in ('left', 'right'):
            new_orientation = Qt.Orientation.Horizontal  # 水平 splitter
            before = (position == 'left')
        else:  # top, bottom
            new_orientation = Qt.Orientation.Vertical    # 垂直 splitter
            before = (position == 'top')

        if self.main_splitter.orientation() == new_orientation:
            # 方向一致：直接在相同 splitter 中插入
            if before:
                self.main_splitter.insertWidget(ref_index, new_widget)
            else:
                self.main_splitter.insertWidget(ref_index + 1, new_widget)
        else:
            # 方向不一致：创建嵌套 splitter
            old_sizes = self.main_splitter.sizes()
            ref_size = old_sizes[ref_index]

            new_splitter = _ToggleButtonSplitter(new_orientation)
            new_splitter.setHandleWidth(4)
            new_splitter.setChildrenCollapsible(False)
            new_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            # 先只加入 new_widget（ref_widget 还在 main_splitter 中）
            new_splitter.addWidget(new_widget)

            # replaceWidget 原子替换：ref_widget 被移除，new_splitter 插入
            self.main_splitter.replaceWidget(ref_index, new_splitter)

            # ref_widget 现在已从 main_splitter 移除，安全地加入 new_splitter
            if before:
                new_splitter.insertWidget(0, ref_widget)
            else:
                new_splitter.addWidget(ref_widget)

            # 恢复原来位置的 size
            new_sizes = self.main_splitter.sizes()
            if ref_index < len(new_sizes):
                new_sizes[ref_index] = ref_size
                self.main_splitter.setSizes(new_sizes)

            # 新 splitter 内部均分
            new_splitter.setSizes([ref_size // 2, ref_size // 2])

    def _find_parent_splitter(self, widget):
        """向上查找 widget 所在的 QSplitter"""
        parent = widget.parent()
        while parent is not None:
            if isinstance(parent, QSplitter):
                return parent
            parent = parent.parent()
        return None

    def tile_sub_windows(self):
        """平铺子窗口"""
        def tile_splitter(splitter):
            count = splitter.count()
            if count > 0:
                if splitter.orientation() == Qt.Orientation.Horizontal:
                    total_size = splitter.width()
                else:
                    total_size = splitter.height()

                if total_size <= 0:
                    return

                size = total_size // count
                sizes = [size for _ in range(count)]
                sizes[-1] = total_size - sum(sizes[:-1])
                splitter.setSizes(sizes)

                for i in range(count):
                    widget = splitter.widget(i)
                    if isinstance(widget, QSplitter):
                        tile_splitter(widget)

        tile_splitter(self.main_splitter)

    def set_last_clicked_widget(self, widget):
        """设置最后点击的板块窗口，同时更新当前窗口"""
        self.last_clicked_widget = widget
        self.current_widget = widget
        # print(f"self.last_clicked_widget: {self.last_clicked_widget}")

    def get_last_clicked_widget(self):
        """获取最后点击的板块窗口"""
        return self.last_clicked_widget

    def on_period_button_clicked(self, period):
        """周期按钮点击事件处理"""
        widget = self.get_last_clicked_widget()
        if hasattr(widget, 'reload_chart'):
            widget.reload_chart(period)

    def show_key_elf(self, initial_text: str = ""):
        """显示键盘精灵窗口"""
        if not self.key_elf_enabled:
            return

        self.key_elf_enabled = False

        from .keyelf_window import KeyElfWindow
        self.key_elf_window = KeyElfWindow(self, self.main_window, initial_text)

    def show_context_menu(self, pos, widget=None):
        """显示右键菜单"""
        self.context_menu_position = pos

        if widget:
            self.set_last_clicked_widget(widget)
        else:
            widget_at = self.main_splitter.childAt(pos)
            if widget_at:
                while widget_at.parent() != self.main_splitter and widget_at.parent() is not None:
                    widget_at = widget_at.parent()
                self.set_last_clicked_widget(widget_at)
            else:
                self.current_widget = None

        # 尝试获取 webview 作为菜单父类（与 light_chart.py 一致）
        menu_parent = self.current_widget#widget if widget else self.main_splitter
        print(menu_parent,type(menu_parent))
        if widget and hasattr(widget, 'chart_window') and hasattr(widget.chart_window, 'get_webview'):
            menu_parent = widget.chart_window.get_webview()
            print(menu_parent)

        menu = RoundMenu("", menu_parent)

        is_logged_in = self.main_window.login_status.get("futures", False)

        if not is_logged_in:
            login_menu = RoundMenu("登录", parent=menu)
            futures_action = Action("期货", parent=login_menu)
            futures_action.triggered.connect(self.main_window.show_login_window)
            login_menu.addAction(futures_action)
            menu.addMenu(login_menu)
        else:
            insert_menu = RoundMenu("插入位置", parent=menu)

            left_action = Action("左侧", parent=insert_menu)
            left_action.triggered.connect(lambda: self.set_insert_position("left"))
            if self.insert_position == "left":
                left_action.setIcon(FluentIcon.ACCEPT.icon())
            else:
                left_action.setIcon(FluentIcon.CLOSE.icon())

            right_action = Action("右侧", parent=insert_menu)
            right_action.triggered.connect(lambda: self.set_insert_position("right"))
            if self.insert_position == "right":
                right_action.setIcon(FluentIcon.ACCEPT.icon())
            else:
                right_action.setIcon(FluentIcon.CLOSE.icon())

            top_action = Action("上方", parent=insert_menu)
            top_action.triggered.connect(lambda: self.set_insert_position("top"))
            if self.insert_position == "top":
                top_action.setIcon(FluentIcon.ACCEPT.icon())
            else:
                top_action.setIcon(FluentIcon.CLOSE.icon())

            bottom_action = Action("下方", parent=insert_menu)
            bottom_action.triggered.connect(lambda: self.set_insert_position("bottom"))
            if self.insert_position == "bottom":
                bottom_action.setIcon(FluentIcon.ACCEPT.icon())
            else:
                bottom_action.setIcon(FluentIcon.CLOSE.icon())

            insert_menu.addAction(left_action)
            insert_menu.addAction(right_action)
            insert_menu.addAction(top_action)
            insert_menu.addAction(bottom_action)

            add_menu = RoundMenu("添加板块", parent=menu)
            kline_menu = RoundMenu("K线图", parent=add_menu)

            if self.main_window and hasattr(self.main_window, 'tq_object') and hasattr(self.main_window.tq_object, 'exchanges'):
                tq_object = self.main_window.tq_object
                ins_class = "主力"
                if ins_class in tq_object.exchanges:
                    exchanges_data = tq_object.exchanges[ins_class]
                    for exchange, contracts in exchanges_data.items():
                        exchange_menu = RoundMenu(exchange, parent=kline_menu)
                        for contract in contracts:
                            contract_action = Action(contract, parent=exchange_menu)
                            contract_action.triggered.connect(lambda checked, c=contract: self.add_market_watch_window(c))
                            exchange_menu.addAction(contract_action)
                        kline_menu.addMenu(exchange_menu)

            add_menu.addMenu(kline_menu)
            menu.addMenu(insert_menu)
            menu.addMenu(add_menu)

            if self.current_widget and self.window_count > 1:
                close_action = Action("关闭", parent=menu)
                close_action.triggered.connect(self.close_current_widget)
                menu.addAction(close_action)

        if widget:
            menu.exec(menu_parent.mapToGlobal(pos))
        else:
            menu.exec(self.main_splitter.mapToGlobal(pos))

    def set_insert_position(self, position):
        """设置插入位置"""
        self.insert_position = position

    def _on_close_button_clicked(self):
        """关闭按钮点击事件处理"""
        widget = self.get_last_clicked_widget()
        if widget and self.window_count > 1:
            try:
                widget.objectName()
                self.current_widget = widget
                self.close_current_widget()
                self._update_close_button_state()
            except RuntimeError:
                self.last_clicked_widget = None

    def _update_close_button_state(self):
        """更新关闭按钮的状态"""
        if self.window_count <= 1:
            self.close_action.setEnabled(False)
        else:
            self.close_action.setEnabled(True)

    def _show_insert_position_menu(self):
        """显示插入位置菜单"""
        menu = RoundMenu(parent=self.insert_button)
        current_position = self.insert_position

        left_action = Action("左侧")
        left_action.triggered.connect(lambda: self.set_insert_position("left"))
        if current_position == "left":
            left_action.setIcon(FluentIcon.ACCEPT.icon())
        else:
            left_action.setIcon(FluentIcon.CLOSE.icon())

        right_action = Action("右侧")
        right_action.triggered.connect(lambda: self.set_insert_position("right"))
        if current_position == "right":
            right_action.setIcon(FluentIcon.ACCEPT.icon())
        else:
            right_action.setIcon(FluentIcon.CLOSE.icon())

        top_action = Action("上方")
        top_action.triggered.connect(lambda: self.set_insert_position("top"))
        if current_position == "top":
            top_action.setIcon(FluentIcon.ACCEPT.icon())
        else:
            top_action.setIcon(FluentIcon.CLOSE.icon())

        bottom_action = Action("下方")
        bottom_action.triggered.connect(lambda: self.set_insert_position("bottom"))
        if current_position == "bottom":
            bottom_action.setIcon(FluentIcon.ACCEPT.icon())
        else:
            bottom_action.setIcon(FluentIcon.CLOSE.icon())

        menu.addAction(left_action)
        menu.addAction(right_action)
        menu.addAction(top_action)
        menu.addAction(bottom_action)

        menu.exec(self.insert_button.mapToGlobal(self.insert_button.rect().bottomLeft()))

    def _show_add_section_menu(self):
        """显示添加板块菜单"""
        menu = RoundMenu(parent=self.add_button)
        kline_menu = RoundMenu("K线图", parent=menu)

        if self.main_window and hasattr(self.main_window, 'tq_object') and hasattr(self.main_window.tq_object, 'exchanges'):
            tq_object = self.main_window.tq_object
            ins_class = "主力"
            if ins_class in tq_object.exchanges:
                exchanges_data = tq_object.exchanges[ins_class]
                for exchange, contracts in exchanges_data.items():
                    exchange_menu = RoundMenu(exchange, parent=kline_menu)
                    for contract in contracts:
                        contract_action = Action(contract, parent=exchange_menu)
                        contract_action.triggered.connect(lambda checked, c=contract: self.add_market_watch_window(c))
                        exchange_menu.addAction(contract_action)
                    kline_menu.addMenu(exchange_menu)

        menu.addMenu(kline_menu)
        menu.addAction(Action("行情表"))
        menu.addAction(Action("列表"))

        menu.exec(self.add_button.mapToGlobal(self.add_button.rect().bottomLeft()))

    def _show_custom_period_menu(self):
        """显示自定义周期菜单 - 根据股票/期货显示不同选项"""
        widget = self.get_last_clicked_widget()

        # 如果没有选中的图表，显示提示
        if widget is None:
            InfoBar.warning(
                '请先选择图表',
                '请点击一个图表板块后再选择周期',
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )
            return

        # 检查图表是否有 is_stock 属性
        is_stock = False
        if hasattr(widget, 'is_stock'):
            is_stock = widget.is_stock

        menu = RoundMenu(parent=self.custom_period_button)

        if is_stock:
            # 股票图表：显示周、月、季、年线
            from ..common.stock_api import StockApi

            stock_periods = [
                (604800, "周线"),      # 1周
                (2419200, "月线"),     # 约28天
                (7776000, "季线"),     # 约3个月
                (31536000, "年线"),    # 约365天
            ]

            for period, name in stock_periods:
                # 只显示 StockApi 支持的周期
                if period in StockApi.PERIOD_TO_FREQUENCY:
                    action = Action(name, parent=menu)
                    action.triggered.connect(lambda checked, p=period: self.on_period_button_clicked(p))
                    menu.addAction(action)
        else:
            # 期货图表：显示秒级、分钟级、小时级、自定义
            futures_periods = [
                (3, "3秒"),
                (5, "5秒"),
                (10, "10秒"),
                (15, "15秒"),
                (180, "3分"),
                (600, "10分"),
                (7200, "2时"),
            ]

            for period, name in futures_periods:
                action = Action(name, parent=menu)
                action.triggered.connect(lambda checked, p=period: self.on_period_button_clicked(p))
                menu.addAction(action)

            # 添加分隔线
            menu.addSeparator()

            # 自定义周期选项
            custom_action = Action("自定义", parent=menu)
            custom_action.triggered.connect(self._show_custom_period_input)
            menu.addAction(custom_action)

        menu.exec(self.custom_period_button.mapToGlobal(self.custom_period_button.rect().bottomLeft()))

    def _show_custom_period_input(self):
        """显示自定义周期输入对话框"""
        from qfluentwidgets import MessageBoxBase, SubtitleLabel, LineEdit, BodyLabel

        class CustomPeriodDialog(MessageBoxBase):
            """自定义周期输入对话框"""

            def __init__(self, parent=None):
                super().__init__(parent)
                self.titleLabel = SubtitleLabel('自定义周期', self)
                self.viewLayout.addWidget(self.titleLabel)

                # 输入框
                self.input_edit = LineEdit(self)
                self.input_edit.setPlaceholderText('请输入周期（秒）')
                self.input_edit.setClearButtonEnabled(True)
                # 回车键触发确认
                self.input_edit.returnPressed.connect(self._on_enter_pressed)
                self.viewLayout.addWidget(self.input_edit)

                # 提示标签
                self.tip_label = BodyLabel('单位：秒（例如：120 表示 2分钟）', self)
                self.viewLayout.addWidget(self.tip_label)

                # 设置按钮文本
                self.yesButton.setText('确认')
                self.cancelButton.setText('取消')

                # 确认按钮点击验证
                self.yesButton.clicked.disconnect()
                self.yesButton.clicked.connect(self._on_yes_clicked)

                # 最小宽度
                self.widget.setMinimumWidth(300)

            def get_period(self) -> int:
                """获取输入的周期值"""
                try:
                    text = self.input_edit.text().strip()
                    if text:
                        return int(text)
                    return 0
                except ValueError:
                    return 0

            def validate(self) -> bool:
                """验证输入是否有效"""
                period = self.get_period()
                if period <= 0:
                    InfoBar.warning(
                        '输入无效',
                        '请输入正整数周期值',
                        duration=2000,
                        position=InfoBarPosition.TOP_RIGHT,
                        parent=self.parent()
                    )
                    return False
                return True

            def _on_enter_pressed(self):
                """回车键按下时触发确认"""
                if self.validate():
                    self.accept()

            def _on_yes_clicked(self):
                """确认按钮点击时验证并接受"""
                if self.validate():
                    self.accept()

        # 创建并显示对话框
        dialog = CustomPeriodDialog(self)
        if dialog.exec():
            period = dialog.get_period()
            if period > 0:
                self.on_period_button_clicked(period)

    def close_current_widget(self):
        """关闭当前子窗口"""
        if self.current_widget:
            main_window_size = self.size()
            parent = self.current_widget.parent()

            if isinstance(parent, QSplitter):
                index = parent.indexOf(self.current_widget)
                if index != -1:
                    current_widget = self.current_widget
                    if current_widget:
                        # 先触发 closeEvent → Chart.cleanup() → 停止 worker
                        current_widget.close()
                        current_widget.setParent(None)
                        current_widget.deleteLater()
                        self.window_count -= 1

                    if parent.count() == 1:
                        remaining_widget = parent.widget(0)
                        grand_parent = parent.parent()
                        if isinstance(grand_parent, QSplitter):
                            grand_index = grand_parent.indexOf(parent)
                            if grand_index != -1:
                                parent.setParent(None)
                                grand_parent.insertWidget(grand_index, remaining_widget)
                                parent.deleteLater()
                    elif parent.count() == 0:
                        grand_parent = parent.parent()
                        if isinstance(grand_parent, QSplitter):
                            grand_index = grand_parent.indexOf(parent)
                            if grand_index != -1:
                                parent.setParent(None)
                                parent.deleteLater()

            self.resize(main_window_size)
            self.tile_sub_windows()
            self._update_close_button_state()

    def switch_chart_symbol(self, new_symbol: str, type_str: str = ""):
        """切换当前图表的合约/股票代码

        关闭当前 LightChartWindow，在同一位置创建新图表。

        Args:
            new_symbol: 新合约/股票代码
            type_str: 合约类型（用于判断 STOCK 还是 FUTURES）
        """
        if not self.current_widget:
            InfoBar.warning(
                title="无法切换",
                content="当前没有活动图表",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                parent=self
            )
            return

        parent = self.current_widget.parent()
        if not isinstance(parent, QSplitter):
            return

        index = parent.indexOf(self.current_widget)
        if index == -1:
            return

        # 根据 type_str 判断 symbol_type：优先从类型字段推导，其次从窗口属性推导
        type_upper = type_str.upper() if type_str else ""
        if type_upper in ("STOCK", "ASHARE", "股票"):
            symbol_type = "STOCK"
        elif type_upper in ("FUTURES", "期货", "CONT_MAIN", "OPTION", "COMBINE",
                           "FUTURES_OPTION", "FUTURES_COMBINE",
                           "SPREAD_MONTH", "SPREAD_INTERCOMMODITY",
                           "INDEX", "STOCK_OPTION"):
            symbol_type = "FUTURES"
        else:
            # 无法从类型推导，回退到窗口属性
            symbol_type = "STOCK" if self.is_stock else "FUTURES"

        try:
            # 保存当前 widget 引用
            old_widget = self.current_widget

            # 创建新图表（复用当前周期和长度）
            content_widget = LightChartWindow(
                self.main_window, self, symbol=new_symbol,
                cycle=self.cycle, length=self.length,
                enable_subwindow_menu=True, symbol_type=symbol_type
            )
            content_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            content_widget.customContextMenuRequested.connect(
                lambda pos, widget=content_widget: self.show_context_menu(pos, widget))

            # 鼠标点击事件
            original_mouse_press = content_widget.mousePressEvent

            def custom_mouse_press(event):
                self.set_last_clicked_widget(content_widget)
                if original_mouse_press:
                    original_mouse_press(event)
            content_widget.mousePressEvent = custom_mouse_press

            # 替换旧 widget
            old_widget.close()
            old_widget.setParent(None)
            old_widget.deleteLater()

            parent.insertWidget(index, content_widget)
            self.current_widget = content_widget
            self.last_clicked_widget = content_widget

            self.tile_sub_windows()
        except Exception as e:
            InfoBar.error(
                title="切换失败",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                parent=self
            )

    def close_all_sub_windows(self):
        """关闭所有子窗口"""
        def close_all(splitter):
            for i in range(splitter.count()):
                widget = splitter.widget(i)
                if isinstance(widget, QSplitter):
                    close_all(widget)
                else:
                    if isinstance(widget, LightChartWindow):
                        widget.close()
                    else:
                        widget.deleteLater()

        close_all(self.main_splitter)
        self.window_count = 0

    def setTheme(self, dark: bool = None):
        if dark is None:
            dark = self.main_window.is_dark_theme
        if dark:
            self.separator.setStyleSheet("background-color: #333333;")
        else:
            self.separator.setStyleSheet("background-color: #e0e0e0;")
        for i in range(self.main_splitter.count()):
            self.main_splitter.widget(i).setTheme(dark)

    def closeEvent(self, e):
        """关闭事件处理"""
        # 移除全局事件过滤器
        if hasattr(self, '_key_elf_global_filter'):
            QApplication.instance().removeEventFilter(self._key_elf_global_filter)
        self.close_all_sub_windows()
        super().closeEvent(e)

    def get_current_section(self):
        """获取当前板块窗口"""
        return self.current_widget

    def add_sub_window(self, contract_name=None, period_milliseconds=60000):
        """添加子窗口（使用 _insert_widget_at_position）"""
        if self.window_count >= 9:
            InfoBar.warning(
                '已达到最大板块数量',
                '最多可创建9个板块',
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )
            return

        self.window_count += 1
        self._update_close_button_state()
        if contract_name is None:
            contract_name = f"合约{self.window_count}"

        new_widget = self.create_content_widget(contract_name, period_milliseconds)
        self._insert_widget_at_position(new_widget)

        # 只更新 last_clicked_widget，不更新 current_widget
        self.last_clicked_widget = new_widget
        self.tile_sub_windows()
        self._update_close_button_state()

    def add_sub_window_direction(self, direction, contract_name=None, period_milliseconds=60000):
        """在指定方向添加子窗口"""
        if self.window_count >= 9:
            InfoBar.warning(
                '已达到最大板块数量',
                '最多可创建9个板块',
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )
            return

        self.window_count += 1
        self._update_close_button_state()
        if contract_name is None:
            contract_name = f"合约{self.window_count}"

        new_widget = self.create_content_widget(contract_name, period_milliseconds)

        if self.current_widget:
            try:
                parent = self.current_widget.parent()
                if isinstance(parent, QSplitter):
                    index = parent.indexOf(self.current_widget)
                    if index != -1:
                        temp_widget = QWidget()
                        parent.insertWidget(index, temp_widget)
                        self.current_widget.setParent(None)

                        if direction in ["left", "right"]:
                            new_splitter = QSplitter(Qt.Orientation.Horizontal)
                            new_splitter.setHandleWidth(0)
                            if direction == "left":
                                new_splitter.addWidget(new_widget)
                                new_splitter.addWidget(self.current_widget)
                            else:
                                new_splitter.addWidget(self.current_widget)
                                new_splitter.addWidget(new_widget)
                        else:
                            new_splitter = QSplitter(Qt.Orientation.Vertical)
                            new_splitter.setHandleWidth(0)
                            if direction == "top":
                                new_splitter.addWidget(new_widget)
                                new_splitter.addWidget(self.current_widget)
                            else:
                                new_splitter.addWidget(self.current_widget)
                                new_splitter.addWidget(new_widget)

                        temp_widget.setParent(None)
                        temp_widget.deleteLater()
                        parent.insertWidget(index, new_splitter)

                        if direction in ["left", "right"]:
                            parent_width = parent.width()
                            new_splitter.setSizes([parent_width // 2, parent_width // 2])
                        else:
                            parent_height = parent.height()
                            new_splitter.setSizes([parent_height // 2, parent_height // 2])

                        new_splitter.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                        new_splitter.customContextMenuRequested.connect(self.show_context_menu)
                else:
                    self.main_splitter.addWidget(new_widget)
            except RuntimeError:
                self.main_splitter.addWidget(new_widget)
        else:
            self.main_splitter.addWidget(new_widget)

        self.set_last_clicked_widget(new_widget)
        self.tile_sub_windows()