# coding:utf-8
from qfluentwidgets import (
    NavigationInterface, NavigationItemPosition, FluentIcon as FIF,
    SearchLineEdit, FluentWindow, MSFluentTitleBar, TableWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QAbstractItemView,
    QTableWidgetItem, QApplication
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..view.main_window import MainWindow
    from ..windows.market_watch_window import MarketWatchWindow
    from ..windows.chart_interface import LightChartWindow



class IndicatorInterface(QWidget):
    """ Indicator interface - 简化版，直接继承QWidget """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # indicator table
        self.indicatorTable = TableWidget(self)
        self.indicatorTable.setObjectName('indicatorTable')
        self.indicatorTable.setColumnCount(2)
        # 隐藏表头
        self.indicatorTable.horizontalHeader().setVisible(False)
        self.indicatorTable.verticalHeader().setVisible(False)
        self.indicatorTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # 设置选择行为为选择整行
        self.indicatorTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        # 设置选择模式为单选
        self.indicatorTable.setSelectionMode(QAbstractItemView.SingleSelection)
        # 禁用右键菜单
        self.indicatorTable.setContextMenuPolicy(Qt.NoContextMenu)
        # 设置第一列自适应宽度，第二列自动拉伸
        self.indicatorTable.horizontalHeader().setSectionResizeMode(0, self.indicatorTable.horizontalHeader().ResizeMode.ResizeToContents)
        self.indicatorTable.horizontalHeader().setStretchLastSection(True)
        # 设置表格属性
        self.indicatorTable.setAlternatingRowColors(True)
        self.indicatorTable.setShowGrid(False)
        # 启用鼠标悬停显示tooltip
        self.indicatorTable.setMouseTracking(True)
        
        # 添加表格到布局
        layout.addWidget(self.indicatorTable)

    def addIndicator(self, name, description):
        """ Add indicator to table """
        row = self.indicatorTable.rowCount()
        self.indicatorTable.insertRow(row)
        
        # 处理描述：只显示第一段，删除#内容，跳过空行
        display_description = self._process_description(description)
        
        # 创建表格项
        name_item = QTableWidgetItem(name)
        desc_item = QTableWidgetItem(display_description)
        
        # 设置tooltip显示完整描述（只在指标名称上显示）
        if description:
            formatted_description = description.replace('\n', '<br>')
            tooltip_text = f"<b>{name}</b><br>{formatted_description}"
        else:
            tooltip_text = name
        name_item.setToolTip(tooltip_text)
        
        # 设置项
        self.indicatorTable.setItem(row, 0, name_item)
        self.indicatorTable.setItem(row, 1, desc_item)
        
        # 设置行高
        self.indicatorTable.setRowHeight(row, 30)
    
    def _process_description(self, description):
        """处理描述文本"""
        if not description:
            return ""
        
        # 按回车分割段落
        paragraphs = description.split('\n')
        
        # 找到第一个非空段落
        for para in paragraphs:
            # 去除空格
            para = para.strip()
            # 移除所有#符号及其后的空格
            para = para.replace('#', '').strip()
            # 限制显示长度
            if para:
                if len(para) > 50:
                    return para[:50] + "..."
                return para
        
        return ""


class SearchResultsInterface(QWidget):
    """搜索结果接口"""
    
    # 定义信号
    indicatorSelected = pyqtSignal(str, str)  # 指标类型, 指标名称

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # search results table
        self.resultsTable = TableWidget(self)
        self.resultsTable.setObjectName('resultsTable')
        self.resultsTable.setColumnCount(3)
        # 隐藏表头
        self.resultsTable.horizontalHeader().setVisible(False)
        self.resultsTable.verticalHeader().setVisible(False)
        self.resultsTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # 设置选择行为为选择整行
        self.resultsTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        # 设置选择模式为单选
        self.resultsTable.setSelectionMode(QAbstractItemView.SingleSelection)
        # 禁用右键菜单
        self.resultsTable.setContextMenuPolicy(Qt.NoContextMenu)
        # 设置列宽
        self.resultsTable.horizontalHeader().setSectionResizeMode(0, self.resultsTable.horizontalHeader().ResizeMode.ResizeToContents)
        self.resultsTable.horizontalHeader().setSectionResizeMode(1, self.resultsTable.horizontalHeader().ResizeMode.ResizeToContents)
        self.resultsTable.horizontalHeader().setStretchLastSection(True)
        # 设置表格属性
        self.resultsTable.setAlternatingRowColors(True)
        self.resultsTable.setShowGrid(False)
        
        # 添加表格到布局
        layout.addWidget(self.resultsTable)
    
    def clearResults(self):
        """清空搜索结果"""
        self.resultsTable.setRowCount(0)
    
    def addResult(self, class_name, name, description):
        """添加搜索结果"""
        row = self.resultsTable.rowCount()
        self.resultsTable.insertRow(row)
        
        # 处理描述
        display_description = self._process_description(description)
        
        # 创建表格项
        class_item = QTableWidgetItem(class_name)
        name_item = QTableWidgetItem(name)
        desc_item = QTableWidgetItem(display_description)
        
        # 设置tooltip
        if description:
            formatted_description = description.replace('\n', '<br>')
            tooltip_text = f"<b>{name}</b><br>{formatted_description}"
        else:
            tooltip_text = name
        name_item.setToolTip(tooltip_text)
        
        # 设置项
        self.resultsTable.setItem(row, 0, class_item)
        self.resultsTable.setItem(row, 1, name_item)
        self.resultsTable.setItem(row, 2, desc_item)
        
        # 设置行高
        self.resultsTable.setRowHeight(row, 30)
    
    def _process_description(self, description):
        """处理描述文本"""
        if not description:
            return ""
        
        # 按回车分割段落
        paragraphs = description.split('\n')
        
        # 找到第一个非空段落
        for para in paragraphs:
            # 去除空格
            para = para.strip()
            # 移除所有#符号及其后的空格
            para = para.replace('#', '').strip()
            # 限制显示长度
            if para:
                if len(para) > 50:
                    return para[:50] + "..."
                return para
        
        return ""


class IndicatorWindow(FluentWindow):
    """ Indicator window """

    # 定义信号
    indicatorSelected = pyqtSignal(str, str)  # 指标类型, 指标名称

    def __init__(self, parent=None,market_watch_window=None):
        # 运行MSFluentWindow的初始化
        super().__init__(parent)
        
        # 保存主窗口引用
        self.main_window: MainWindow = parent
        self.market_watch_window :MarketWatchWindow = market_watch_window
        
        # 移除默认的NavigationBar，使用NavigationInterface
        self.navigationInterface.deleteLater()
        
        # 创建新的导航接口
        self.navigationInterface = NavigationInterface(
            self, showMenuButton=False, showReturnButton=False, collapsible=False
        )

        # create search bar
        self.searchBar = SearchLineEdit(self)
        self.searchBar.setPlaceholderText("搜索指标")
        self.searchBar.setFixedHeight(40)
        self.setMicaEffectEnabled(False)
        self.navigationInterface.setAcrylicEnabled(False)

        # create sub interfaces
        self.indicator_interfaces = {}
        self.search_results_interface = SearchResultsInterface(self)
        self.search_results_interface.setObjectName("search_results")
        self._load_indicator_data()

        # reinitialize layout
        self.initLayout()

        # add items to navigation interface
        self.initNavigation()

        self.initWindow()
        
        # connect signal to slot
        self.connectSignalToSlot()
    
    def _load_indicator_data(self):
        """加载指标数据"""
        # 从主窗口的minibt_object中获取指标数据
        if self.main_window and hasattr(self.main_window, 'minibt_object') and self.main_window.minibt_object:
            minibt_object = self.main_window.minibt_object
            # 获取所有指标类
            indicator_classes = minibt_object.get_indicator_classes()
            
            for class_name in indicator_classes:
                # 创建指标接口
                interface = IndicatorInterface(self)
                interface.setObjectName(class_name)
                # 获取该类的指标
                indicators = minibt_object.get_indicators(class_name)
                # 添加指标到表格
                for indicator in indicators:
                    if len(indicator) >= 2:
                        name, description = indicator[0], indicator[1]
                        interface.addIndicator(name, description)
                # 存储接口
                self.indicator_interfaces[class_name] = interface
        else:
            # 如果没有minibt_object，使用默认指标
            self.indicator_interfaces = {}
    
    def _search_indicators(self, keyword):
        """搜索指标"""
        # 清空搜索结果
        self.search_results_interface.clearResults()
        
        if not keyword or not self.main_window or not hasattr(self.main_window, 'minibt_object') or not self.main_window.minibt_object:
            return
        
        minibt_object = self.main_window.minibt_object
        # 获取所有指标类
        indicator_classes = minibt_object.get_indicator_classes()
        
        for class_name in indicator_classes:
            # 获取该类的指标
            indicators = minibt_object.get_indicators(class_name)
            # 搜索指标
            for indicator in indicators:
                if len(indicator) >= 2:
                    name, description = indicator[0], indicator[1]
                    # 只在指标名称中搜索
                    if keyword.lower() in name.lower():
                        self.search_results_interface.addResult(class_name, name, description)
    
    def _switch_to_search_results(self):
        """切换到搜索结果界面"""
        self.stackedWidget.setCurrentWidget(self.search_results_interface)
        self.navigationInterface.setCurrentItem("search_results")

    def _switch_to_normal_view(self):
        """切换到正常视图"""
        if self.indicator_interfaces:
            first_interface = next(iter(self.indicator_interfaces.values()))
            self.stackedWidget.setCurrentWidget(first_interface)
    
    def _on_search_text_changed(self, text):
        """搜索文本变化时的处理"""
        if text:
            self._search_indicators(text)
            self._switch_to_search_results()
        else:
            self._switch_to_normal_view()

    def initLayout(self):
        # clear existing layout
        for i in reversed(range(self.hBoxLayout.count())):
            widget = self.hBoxLayout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        # main layout
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setContentsMargins(0, 48, 0, 0)
        
        # 创建垂直布局容器
        mainContainer = QWidget()
        mainLayout = QVBoxLayout(mainContainer)
        mainLayout.setSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        
        # 添加搜索栏到顶部
        mainLayout.addWidget(self.searchBar)
        
        # 创建下方的水平布局（导航 + 表格）
        bottomLayout = QHBoxLayout()
        bottomLayout.setSpacing(0)
        bottomLayout.setContentsMargins(0, 0, 0, 0)
        
        # 左侧导航
        leftWidget = QWidget()
        leftLayout = QVBoxLayout(leftWidget)
        leftLayout.addWidget(self.navigationInterface)
        leftLayout.setContentsMargins(0, 0, 0, 0)
        
        # 添加到下方布局
        bottomLayout.addWidget(leftWidget)
        bottomLayout.addWidget(self.stackedWidget, 1)
        
        # 添加下方布局到主布局
        mainLayout.addLayout(bottomLayout, 1)
        
        # 添加主容器到窗口
        self.hBoxLayout.addWidget(mainContainer)

    def initNavigation(self):
        # set expand width
        self.navigationInterface.setExpandWidth(150)
        self.navigationInterface.expand()

        # add navigation items
        first_interface = None
        for class_name, interface in self.indicator_interfaces.items():
            self.addSubInterface(interface, FIF.ADD_TO, class_name)
            if first_interface is None:
                first_interface = interface
        
        # 添加搜索结果接口
        self.addSubInterface(self.search_results_interface, FIF.SEARCH, "搜索结果")
        # 隐藏搜索结果导航项
        # search_item = self.navigationInterface.widget("search_results")
        # if search_item:
        #     search_item.hide()

        # set default interface
        if first_interface:
            self.stackedWidget.setCurrentWidget(first_interface)
            self.navigationInterface.setCurrentItem(first_interface.objectName())

    def addSubInterface(self, interface, icon, text: str):
        """ add sub interface """
        if not interface.objectName():
            interface.setObjectName(text)

        self.stackedWidget.addWidget(interface)
        self.navigationInterface.addItem(
            routeKey=interface.objectName(),
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(interface)
        )

    def switchTo(self, widget):
        """ switch to sub interface """
        self.stackedWidget.setCurrentWidget(widget)
        self.navigationInterface.setCurrentItem(widget.objectName())

    def initWindow(self):
        # self.resize(960, 660)
        self.setFixedSize(960, 660)
        self.setObjectName('indicatorWindow')
        self.setWindowTitle('指标模板')
        # 设置窗口标志，只显示关闭按钮
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.titleBar.minBtn.hide()
        self.titleBar.maxBtn.hide()
        
        
        # 将窗口设置到屏幕中央
        desktop = QApplication.screens()[0].availableGeometry()
        x = (desktop.width() - self.width()) // 2
        y = (desktop.height() - self.height()) // 2
        self.move(x, y)

    def connectSignalToSlot(self):
        """ connect signal to slot """
        # 连接所有指标接口的信号
        for class_name, interface in self.indicator_interfaces.items():
            interface.indicatorTable.cellClicked.connect(
                lambda row, col, cn=class_name, itf=interface: self.indicatorSelected.emit(cn, itf.indicatorTable.item(row, 0).text())
            )
            # 添加双击事件
            interface.indicatorTable.cellDoubleClicked.connect(
                lambda row, col, cn=class_name, itf=interface: self._on_indicator_double_clicked(cn, itf.indicatorTable.item(row, 0).text())
            )

        # 连接搜索结果接口的信号
        self.search_results_interface.resultsTable.cellClicked.connect(
            lambda row, col, itf=self.search_results_interface: self.indicatorSelected.emit(
                itf.resultsTable.item(row, 0).text(),
                itf.resultsTable.item(row, 1).text()
            )
        )
        # 添加双击事件
        self.search_results_interface.resultsTable.cellDoubleClicked.connect(
            lambda row, col, itf=self.search_results_interface: self._on_indicator_double_clicked(
                itf.resultsTable.item(row, 0).text(),
                itf.resultsTable.item(row, 1).text()
            )
        )
        
        # 连接搜索栏信号
        self.searchBar.textChanged.connect(self._on_search_text_changed)
    
    def _on_indicator_double_clicked(self, class_name, indicator_name):
        """处理指标双击事件"""
        # print(f"双击指标: {class_name}.{indicator_name}")
        
        # 检查 market_watch_window 是否存在
        if self.market_watch_window:
            #print(f"通过 LightChartWindow 添加指标: {class_name}.{indicator_name}")
            # 调用添加指标的方法
            self.market_watch_window.last_clicked_widget.add_indicator_to_manager(class_name, indicator_name, {})


if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = IndicatorWindow()
    window.show()
    sys.exit(app.exec())
