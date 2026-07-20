from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QFont, QColor, QKeyEvent, QFocusEvent
from PyQt6.QtWidgets import (
    QAbstractItemView, QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget, QLabel, QApplication)
from qfluentwidgets import TableWidget, LineEdit, FluentWindow, InfoBarIcon, IconWidget
from typing import TYPE_CHECKING, Optional
import pandas as pd

if TYPE_CHECKING:
    from ..view.main_window import MainWindow
    from .market_watch_window import MarketWatchWindow


class KeyElfTableWidget(TableWidget):
    """键盘精灵表格"""

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont()
        font.setPointSize(12)
        self.setFont(font)
        self.setFixedWidth(320)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setColumnCount(3)  # 代码/指标类、名称、类型
        self.setSortingEnabled(False)
        self.resizeColumnsToContents()
        self.doubleClicked.connect(parent._on_double_click)


class KeyElfLineEdit(LineEdit):
    """键盘精灵搜索输入框"""

    def __init__(self, key_win: 'KeyElfWindow'):
        super().__init__()
        self.setFixedHeight(28)
        self.key_win = key_win
        self.keytable = key_win.keytable

        # 加载搜索数据
        self._load_search_data()

        self.textChanged.connect(self._on_text_changed)

    def _load_search_data(self):
        """加载搜索数据（合约、股票、指标）"""
        self.symbol_data = []  # 合约/股票数据
        self.indicator_data = []  # 指标数据

        # 从 MarketWatchWindow 的 symbol_search_data 属性加载合约/股票数据
        try:
            if self.key_win.market_watch_window and hasattr(self.key_win.market_watch_window, 'symbol_search_data'):
                symbol_search_data = self.key_win.market_watch_window.symbol_search_data
                if symbol_search_data is not None and len(symbol_search_data) > 0:
                    # 直接使用 MarketWatchWindow 的搜索数据
                    self.symbol_data = symbol_search_data
                else:
                    # 如果 MarketWatchWindow 的数据为空，从数据库加载
                    from ..common.database_manager import get_db_manager
                    db_manager = get_db_manager()
                    if db_manager:
                        search_df = db_manager.get_search_table()
                        if search_df is not None and not search_df.empty:
                            # 转换为列表格式：[code, name, type, exchange]
                            self.symbol_data = search_df.values.tolist()
        except Exception as e:
            print(f"[KeyElfLineEdit] 加载合约数据失败: {e}")

        # 从 minibt_object 加载指标数据
        try:
            if self.key_win.main_window and hasattr(self.key_win.main_window, 'minibt_object'):
                minibt_object = self.key_win.main_window.minibt_object
                if minibt_object:
                    indicator_classes = minibt_object.get_indicator_classes()
                    for class_name in indicator_classes:
                        indicators = minibt_object.get_indicators(class_name)
                        for indicator in indicators:
                            if len(indicator) >= 2:
                                name, description = indicator[0], indicator[1]
                                # 格式：[指标类名, 指标名, "指标"]
                                self.indicator_data.append([class_name, name, "指标"])
        except Exception as e:
            print(f"[KeyElfLineEdit] 加载指标数据失败: {e}")

        # 合并数据
        self.all_data = self.symbol_data + self.indicator_data

        # 创建搜索索引（小写）
        self.code_lower = [str(item[0]).lower() for item in self.all_data]
        self.name_lower = [str(item[1]).lower() for item in self.all_data]

    def _on_text_changed(self):
        """文本变化时搜索"""
        text = self.text().lower().strip()
        if not text:
            self._clear_table()
            return

        # 搜索匹配项
        matched_items = []
        for i, (code_lower, name_lower) in enumerate(zip(self.code_lower, self.name_lower)):
            if text in code_lower or text in name_lower:
                matched_items.append(self.all_data[i])

        if matched_items:
            self._set_table_data(matched_items)
            self.keytable.selectRow(0)
        else:
            self._clear_table()

    def _set_table_data(self, items):
        """设置表格数据"""
        self._clear_table()
        for item in items:
            row = self.keytable.rowCount()
            self.keytable.insertRow(row)
            for j, value in enumerate(item[:3]):
                item_ = QTableWidgetItem(str(value))
                item_.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
                self.keytable.setItem(row, j, item_)

    def _clear_table(self):
        """清空表格"""
        count = self.keytable.rowCount()
        if count > 0:
            for row in range(count - 1, -1, -1):
                self.keytable.removeRow(row)


class KeyElfWindow(FluentWindow):
    """键盘精灵窗口"""

    def __init__(self, parent: 'MarketWatchWindow', main_window: 'MainWindow', initial_text: str = ""):
        super().__init__()
        # 隐藏不需要的组件（不要删除，避免 nativeEvent 访问已删除对象）
        self.navigationInterface.hide()
        self.stackedWidget.hide()

        # 隐藏标题栏按钮（不要删除，避免 RuntimeError）
        self.titleBar.maxBtn.hide()
        self.titleBar.minBtn.hide()

        height = self.titleBar.maxBtn.height()
        self.titleBar.titleLabel.setText('键盘精灵')

        # 设置窗口属性
        self.market_watch_window = parent
        self.main_window = main_window
        self.current_row = None
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(320, 450)

        # 创建布局
        vlayout = QVBoxLayout()
        self.keytable = KeyElfTableWidget(self)
        self.search_edit = KeyElfLineEdit(self)
        self.search_edit.setFixedHeight(height)
        self.search_edit.setText(initial_text)

        vlayout.addWidget(self.search_edit)
        vlayout.addWidget(self.keytable)
        vlayout.setContentsMargins(5, height, 5, 5)
        vlayout.setSpacing(5)

        self.hBoxLayout.addLayout(vlayout)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)

        # 设置位置到 MarketWatchWindow 的右下角
        if parent:
            parent_rect = parent.geometry()
            parent_pos = parent.mapToGlobal(parent_rect.bottomRight())
            # 计算窗口位置（右下角偏移一点）
            x = parent_pos.x() - self.width() - 10
            y = parent_pos.y() - self.height() - 10
            self.move(x, y)
        else:
            # 如果没有父窗口，则显示在屏幕右下角
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.width() - self.width() - 5, screen.height() - self.height() - 5)

        self.titleBar.setFixedHeight(height)

        # 显示窗口
        self.show()

        # 延迟设置焦点（确保窗口显示后焦点在搜索框）
        QTimer.singleShot(100, lambda: self._set_focus_to_search_edit(initial_text))

    def _set_focus_to_search_edit(self, initial_text: str = ""):
        """设置焦点到搜索框"""
        self.search_edit.setFocus()
        self.search_edit.setCursorPosition(len(initial_text))
        # 激活窗口以确保焦点生效
        self.activateWindow()

    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        # 每次显示时都设置焦点到搜索框
        QTimer.singleShot(50, lambda: self._set_focus_to_search_edit())

    def _on_double_click(self):
        """双击表格行执行操作"""
        row = self.keytable.currentRow()
        if row < 0:
            return

        try:
            code_or_class = self.keytable.item(row, 0).text().strip()
            name = self.keytable.item(row, 1).text().strip()
            type_str = self.keytable.item(row, 2).text().strip()

            if not code_or_class or not name:
                return

            # 获取当前图表窗口
            current_widget = self.market_watch_window.current_widget
            if current_widget is None or not hasattr(current_widget, 'chart_window'):
                return

            chart_window = current_widget.chart_window

            if type_str == "指标":
                # 添加指标到当前图表
                current_widget.add_indicator_to_manager(code_or_class, name, {})
            else:
                # 切换合约/股票 - 暂不支持
                # TODO: 实现合约切换功能
                print(f"[KeyElfWindow] 切换合约功能暂未实现: {code_or_class} ({name})")

            self.close()
        except Exception as e:
            print(f"[KeyElfWindow] 双击操作失败: {e}")

    def keyPressEvent(self, event):
        """键盘事件处理"""
        if event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return:
            if self.search_edit.text():
                if self.keytable.rowCount() > 0:
                    self._on_double_click()
            else:
                self.close()
        elif event.key() == Qt.Key.Key_Down:
            if self.keytable.rowCount() > 1:
                row = self.keytable.currentRow()
                self.keytable.selectRow(min(row + 1, self.keytable.rowCount() - 1))
        elif event.key() == Qt.Key.Key_Up:
            if self.keytable.rowCount() > 1:
                row = self.keytable.currentRow()
                self.keytable.selectRow(max(row - 1, 0))
        elif event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_Right:
            self.search_edit.setFocus()
            self.search_edit.setCursorPosition(len(self.search_edit.text()))
        elif event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event):
        """关闭事件"""
        # 重新启用键盘精灵快捷键
        if hasattr(self.market_watch_window, 'key_elf_enabled'):
            self.market_watch_window.key_elf_enabled = True
        super().closeEvent(event)