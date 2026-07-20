from __future__ import annotations
from qfluentwidgets import (FluentIcon as FIF, CommandBarView, BodyLabel, Action, Flyout, FlyoutAnimationType,CommandButton,
    GroupHeaderCardWidget,PushButton,ComboBox,SearchLineEdit,IconWidget,InfoBarIcon,PrimaryPushButton,isDarkTheme,LineEdit,
        InfoBar,ColorDialog,Pivot, qrouter,SegmentedWidget,TransparentToggleToolButton,SwitchButton,IndicatorPosition,
            PrimaryToolButton,TransparentToolButton,ColorPickerButton)
from qfluentwidgets.components.widgets.command_bar import CommandViewMenu,CommandViewBar
from qfluentwidgets.components.widgets.card_widget import CardSeparator, CardGroupWidget
from qfluentwidgets.components.dialog_box.color_dialog import HuePanel, MaskDialogBase
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QStackedWidget,QWidget,QApplication, QSizePolicy,QToolButton,QColorDialog, QPushButton
from PyQt6.QtCore import Qt, QPoint,QSize,QEvent, pyqtSignal,QTimer
from ..common.style_sheet import StyleSheet
from PyQt6.QtGui import QColor,QAction,QPainter,QPen
from typing import TYPE_CHECKING
from enum import Enum
    
if TYPE_CHECKING:
    from .chart_interface import LightChartWindow,Chart,Line,Indicator
    
    
class IndicatorGroup(str,Enum):
    params="params"
    line_style="line_style"
    line_width="line_width"
    line_color="line_color"
    price_visible="price_visible"

class PivotInterface(QWidget):
    """ Pivot interface """

    Nav = Pivot

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # 不设置固定大小，让布局自适应

        self.pivot = self.Nav(self)
        self.stackedWidget = QStackedWidget(self)
        self.vBoxLayout = QVBoxLayout(self)

        # 设置 stackedWidget 自适应大小
        self.stackedWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.vBoxLayout.addWidget(self.pivot, 0, Qt.AlignLeft)
        self.vBoxLayout.addWidget(self.stackedWidget, 1)  # 添加伸缩因子
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        StyleSheet.NAVIGATION_VIEW_INTERFACE.apply(self)

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)

    def addSubInterface(self, widget: QWidget, objectName, text):
        widget.setObjectName(objectName)
        # widget.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        if index >= 0 and index < self.stackedWidget.count():
            widget = self.stackedWidget.widget(index)
            if widget:
                self.pivot.setCurrentItem(widget.objectName())
                qrouter.push(self.stackedWidget, widget.objectName())


class SegmentedInterface(PivotInterface):

    Nav = SegmentedWidget

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vBoxLayout.removeWidget(self.pivot)
        self.vBoxLayout.insertWidget(0, self.pivot)




class SimpleColorDialog(MaskDialogBase):
    """ 简化的颜色对话框 """

    colorChanged = pyqtSignal(QColor)

    def __init__(self, color, title: str, parent=None, enableAlpha=False):
        super().__init__(parent)
        self.color = QColor(color)
        self.title = title
        self.enableAlpha = enableAlpha

        if not enableAlpha:
            self.color.setAlpha(255)

        self.oldColor = QColor(self.color)

        # 确保父窗口存在且有有效大小
        if parent and parent.isVisible():
            # 设置对话框大小为父窗口的大小，确保不会超出屏幕
            width = max(320, min(parent.width(), 600))
            height = max(200, min(parent.height(), 400))
            self.setGeometry(0, 0, width, height)
            self.windowMask.resize(self.size())

        # 创建控件
        self.huePanel = HuePanel(self.color, self.widget)
        self.yesButton = PrimaryPushButton(self.tr('确认'), self.widget)
        self.cancelButton = QPushButton(self.tr('取消'), self.widget)

        # 初始化布局
        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        """ 初始化布局 """
        # 设置窗口大小，与 IndicatorParamsCard 一致
        self.widget.setFixedSize(320, 200)

        # 创建垂直布局
        v_layout = QVBoxLayout(self.widget)
        
        # 添加调色板
        self.huePanel.setFixedSize(280, 100)
        v_layout.addWidget(self.huePanel, alignment=Qt.AlignCenter)
        v_layout.addStretch(1)

        # 创建水平布局放置按钮
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.yesButton)
        h_layout.addWidget(self.cancelButton)
        v_layout.addLayout(h_layout)

        # 设置布局边距和间距
        v_layout.setContentsMargins(20, 20, 20, 20)
        v_layout.setSpacing(15)

        # 设置按钮大小
        self.yesButton.setFixedHeight(36)
        self.cancelButton.setFixedHeight(36)
        self.yesButton.setFixedWidth(120)
        self.cancelButton.setFixedWidth(120)

    def __connectSignalToSlot(self):
        """ 连接信号和槽 """
        self.huePanel.colorChanged.connect(self.__onColorChanged)
        self.yesButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

    def __onColorChanged(self, color):
        """ 颜色改变槽 """
        self.color = color
        self.huePanel.setColor(color)

    def accept(self):
        """ 确认按钮被点击 """
        # 确保只在颜色改变时发出信号
        if self.color != self.oldColor:
            self.colorChanged.emit(self.color)
        super().accept()

    def reject(self):
        """ 取消按钮被点击 """
        self.color = self.oldColor
        super().reject()

class _ColorPickerButton(ColorPickerButton):

    colorChanged = pyqtSignal(QColor)

    def __init__(self, color: QColor, title: str, parent=None, enableAlpha=False):
        super().__init__(color, title, parent, enableAlpha)
        self.lcw=parent
        self.color = color
        self.title = title
        self.enableAlpha = enableAlpha
        # 调用 setColor 更新按钮显示颜色
        self.setColor(color)
        # 断开原始的 clicked 信号连接，避免重复弹出颜色框
        try:
            self.clicked.disconnect()
        except:
            pass
        self.clicked.connect(self.__showColorDialog)

    def __showColorDialog(self):
        """ show color dialog """
        # 创建简化的颜色对话框
        w = SimpleColorDialog(self.color, "选择颜色", parent=self.lcw, enableAlpha=self.enableAlpha)
        w.colorChanged.connect(self.__onColorChanged)
        
        # 显示对话框
        w.exec()

    def __onColorChanged(self, color):
        """ color changed slot """
        # 同步自身颜色改变
        self.color = color
        # 调用 setColor 更新按钮显示颜色
        self.setColor(color)
        self.colorChanged.emit(color)
        
class IndicatorParamsCard(GroupHeaderCardWidget):

    def __init__(self, parent:"LightChartWindow",indicator:"Indicator",callback:callable,group:IndicatorGroup=IndicatorGroup.params):
        super().__init__(parent)
        self.setTitle(f"{indicator.name}指标参数")
        self.setBorderRadius(6)
        self.headerLayout.setContentsMargins(6, 6, 6, 6)
        self.headerView.setFixedHeight(32)
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.headerLabel.setToolTip(indicator.doc)
        
        # 设置最小高度，确保颜色窗口有足够的空间显示
        self.setMinimumHeight(300)
        self.indicator=indicator
        
        self.lcw=parent
        self.callback=callback
        self.group=group
        self.last_group=group
        self.length=max(len(indicator.params),len(indicator.line_style),len(indicator.line_width),len(indicator.line_color),len(indicator.price_visible))
        self.is_params_changes = False
        # 保存初始参数值
        self.initial_params = {}
        self.initial_params.update(indicator.params.copy())
        self.initial_params.update({f"line_style_{k}": v for k, v in indicator.line_style.items()})
        self.initial_params.update({f"line_width_{k}": v for k, v in indicator.line_width.items()})
        self.initial_params.update({f"line_color_{k}": v for k, v in indicator.line_color.items()})
        self.initial_params.update({f"price_visible_{k}": v for k, v in indicator.price_visible.items()})
        self.clear_viewlayout()
        self.segmented = SegmentedInterface(self)
        # 保存创建的 widget
        params_widget = self.create_params_group()
        line_style_widget = self.create_line_style_group()
        line_width_widget = self.create_line_width_group()
        line_color_widget = self.create_line_color_group()
        price_visible_widget = self.create_price_visible_group()

        # 添加到 SegmentedInterface
        self.segmented.addSubInterface(params_widget, "params", self.tr("参数"))
        self.segmented.addSubInterface(line_style_widget, "line_style", self.tr("线型"))
        self.segmented.addSubInterface(line_width_widget, "line_width", self.tr("线宽"))
        self.segmented.addSubInterface(line_color_widget, "line_color", self.tr("线颜色"))
        self.segmented.addSubInterface(price_visible_widget, "price_visible", self.tr("其它设置"))

        # 设置当前选中的项目 - 优先选中第一个有内容的页面
        # 检查各个分组是否有内容
        has_params = len(self.indicator.params) > 0
        has_line_style = len(self.indicator.line_style) > 0
        has_line_width = len(self.indicator.line_width) > 0
        has_line_color = len(self.indicator.line_color) > 0
        has_price_visible = len(self.indicator.price_visible) > 0

        # 确定默认选中的页面
        default_page = None
        default_key = None
        if has_params:
            default_page = params_widget
            default_key = "params"
        elif has_line_style:
            default_page = line_style_widget
            default_key = "line_style"
        elif has_line_width:
            default_page = line_width_widget
            default_key = "line_width"
        elif has_line_color:
            default_page = line_color_widget
            default_key = "line_color"
        elif has_price_visible:
            default_page = price_visible_widget
            default_key = "price_visible"

        # 如果所有页面都为空，默认选中参数页面
        if default_page is None:
            default_page = params_widget
            default_key = "params"

        if self.segmented.stackedWidget.count() > 0:
            self.segmented.stackedWidget.setCurrentWidget(default_page)
            self.segmented.pivot.setCurrentItem(default_key)
        
        self.vBoxLayout.insertWidget(2, self.segmented)
        self.separator1 = CardSeparator(self)
        self.vBoxLayout.insertWidget(3, self.separator1)
        

        self.hintIcon = IconWidget(InfoBarIcon.INFORMATION)
        self.hintLabel = BodyLabel("点击确认按钮设置指标参数 👉")
        self.confirmButton = PrimaryPushButton(FIF.PLAY_SOLID, "确认")
        self.confirmButton.clicked.connect(lambda: parent.chart_window.replay_indicator_params(self.indicator.id, self,self.callback))
        
        self.bottomLayout = QHBoxLayout()

        # 设置底部工具栏布局
        self.hintIcon.setFixedSize(20, 20)
        self.bottomLayout.setSpacing(2)
        self.bottomLayout.setContentsMargins(12, 6, 12, 6)
        self.bottomLayout.addWidget(self.hintIcon, 0, Qt.AlignLeft)
        self.bottomLayout.addWidget(self.hintLabel, 0, Qt.AlignLeft)
        self.bottomLayout.addStretch(1)
        self.bottomLayout.addWidget(self.confirmButton, 0, Qt.AlignRight)
        self.bottomLayout.setAlignment(Qt.AlignVCenter)


        # 添加底部工具栏
        self.vBoxLayout.addLayout(self.bottomLayout)
        self.adjustSize()
        
    def clear_viewlayout(self):
        """
        清空视图布局中的内容
        """
        # 从后往前删除，避免索引错乱
        while self.viewLayout.count() > 0:
            # 取出第 0 个项目
            item = self.viewLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            # 删除项目本身
            del item
        
    def create_params_group(self):
        """
        创建参数分组
        """
        self.params_widget={}
        qwidget=QWidget(self)
        layout=QVBoxLayout(qwidget)
        # 设置布局间距为0
        layout.setSpacing(0)
        total_height = 0

        # 如果没有参数，显示提示信息
        if not self.indicator.params:
            hint_label = BodyLabel("该指标没有可设置的参数", self)
            hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint_label.setStyleSheet("color: #666; padding: 20px;")
            layout.addWidget(hint_label)
            total_height = 60
        else:
            for i,(param,value) in enumerate(self.indicator.params.items()):
                editor=LineEdit(self)
                editor.setFixedHeight(32)
                editor.setText(str(value))
                self.params_widget[param]=editor
                editor.setClearButtonEnabled(True)
                group = CardGroupWidget(FIF.FLAG, param, "", self)
                group.setFixedHeight(40)
                # 设置 hBoxLayout 垂直居中对齐
                group.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                # 添加控件
                group.hBoxLayout.addWidget(editor, stretch=0)
                if i<self.length-1 or len(self.indicator.params)<=4:
                    group.setSeparatorVisible(True)
                group.hBoxLayout.setContentsMargins(24, 4, 24, 4)
                group.textLayout.removeWidget(group.contentLabel)
                # 为每个编辑器添加按键事件
                editor.keyPressEvent = lambda event, e=editor: self.handleKeyPress(event, e)
                editor.textChanged.connect(lambda text, p=param, e=editor: self._on_param_changed(p, e.text()))
                layout.addWidget(group)
                total_height += 40
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置qwidget的固定高度
        qwidget.setFixedHeight(total_height)
        return qwidget
    
    def _on_param_changed(self,param:str,value:str):
        """
        参数改变时的处理函数
        """
        value=self.indicator.params_type[param](value)
        if value!=self.indicator.params[param]:
            self.is_params_changes=True
            self.indicator.params[param]=value
        
    def create_line_style_group(self):
        """
        创建线样式分组
        """
        self.line_style_widget={}
        qwidget=QWidget(self)
        layout=QVBoxLayout(qwidget)
        # 设置布局间距为0
        layout.setSpacing(0)
        total_height = 0

        # 如果没有线样式，显示提示信息
        if not self.indicator.line_style:
            hint_label = BodyLabel("该指标没有可设置的线型", self)
            hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint_label.setStyleSheet("color: #666; padding: 20px;")
            layout.addWidget(hint_label)
            total_height = 60
        else:
            for i,(name,value) in enumerate(self.indicator.line_style.items()):
                combobox=ComboBox(self)
                combobox.setFixedHeight(32)
                self.line_style_widget[name]=combobox
                items=["solid", "dotted", "dashed", "large_dashed", "sparse_dotted"]
                combobox.addItems(items)
                combobox.setCurrentIndex(items.index(value))
                group = CardGroupWidget(FIF.TRANSPARENT, name, "", self)
                group.setFixedHeight(40)
                # 设置 hBoxLayout 垂直居中对齐
                group.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                # 添加控件
                group.hBoxLayout.addWidget(combobox, stretch=0)
                combobox.currentIndexChanged.connect(lambda index, n=name, c=combobox: self._on_line_style_changed(n, c.currentText()))
                if i<self.length-1 :
                    group.setSeparatorVisible(True)
                group.hBoxLayout.setContentsMargins(24, 4, 24, 4)
                group.textLayout.removeWidget(group.contentLabel)
                layout.addWidget(group)
                total_height += 40
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置qwidget的固定高度
        qwidget.setFixedHeight(total_height)
        return qwidget
    
    def _on_line_style_changed(self, name, value):
        """
        线样式改变时的处理函数
        """
        value=str(value)
        if value!=self.indicator.line_style[name]:
            self.is_params_changes=True
            self.indicator.line_style[name]=value
            QTimer().singleShot(0, lambda: self.indicator.indicator_lines[name].set_line_style(value))
            
    def create_line_width_group(self):
        """
        创建线宽分组
        """
        self.line_width_widget={}
        qwidget=QWidget(self)
        layout=QVBoxLayout(qwidget)
        # 设置布局间距为0
        layout.setSpacing(0)
        total_height = 0

        # 如果没有线宽，显示提示信息
        if not self.indicator.line_width:
            hint_label = BodyLabel("该指标没有可设置的线宽", self)
            hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint_label.setStyleSheet("color: #666; padding: 20px;")
            layout.addWidget(hint_label)
            total_height = 60
        else:
            for i,(name,value) in enumerate(self.indicator.line_width.items()):
                combobox=ComboBox(self)
                combobox.setFixedHeight(32)
                self.line_width_widget[name]=combobox
                combobox.addItems([str(i) for i in range(1,11)])
                combobox.setCurrentIndex(int(value)-1)
                group = CardGroupWidget(FIF.REMOVE, name, "", self)
                group.setFixedHeight(40)
                # 设置 hBoxLayout 垂直居中对齐
                group.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                # 添加控件
                group.hBoxLayout.addWidget(combobox, stretch=0)
                combobox.currentIndexChanged.connect(lambda index, n=name, c=combobox: self._on_line_width_changed(n, c.currentText()))
                if i<self.length-1:
                    group.setSeparatorVisible(True)
                group.hBoxLayout.setContentsMargins(24, 4, 24, 4)
                group.textLayout.removeWidget(group.contentLabel)
                layout.addWidget(group)
                total_height += 40
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置qwidget的固定高度
        qwidget.setFixedHeight(total_height)
        return qwidget
    
    def _on_line_width_changed(self, name, value):
        """
        线宽改变时的处理函数
        """
        value=int(value)
        if value!=self.indicator.line_width[name]:
            self.is_params_changes=True
            self.indicator.line_width[name]=value
            QTimer().singleShot(0, lambda: self.indicator.indicator_lines[name].set_line_width(value))
            
    def _parse_rgb_string(self, rgb_string):
        """
        解析RGB字符串为QColor对象
        """
        try:
            # 移除 'rgb(' 和 ')'，然后分割成三个整数
            rgb_values = rgb_string.strip('rgb()').split(',')
            r = int(rgb_values[0].strip())
            g = int(rgb_values[1].strip())
            b = int(rgb_values[2].strip())
            return QColor(r, g, b)
        except:
            # 如果解析失败，返回默认颜色
            return QColor(0, 0, 255)

    def create_line_color_group(self):
        """
        创建线颜色分组
        """
        self.line_color_widget={}
        qwidget=QWidget(self)
        layout=QVBoxLayout(qwidget)
        # 设置布局间距为0
        layout.setSpacing(0)
        total_height = 0

        # 如果没有线颜色，显示提示信息
        if not self.indicator.line_color:
            hint_label = BodyLabel("该指标没有可设置的线颜色", self)
            hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint_label.setStyleSheet("color: #666; padding: 20px;")
            layout.addWidget(hint_label)
            total_height = 60
        else:
            for i,(name,value) in enumerate(self.indicator.line_color.items()):
                # 解析RGB字符串为QColor对象
                color = self._parse_rgb_string(value)
                # 使用 ColorPickerButton 代替 TransparentToolButton
                palette=_ColorPickerButton(color, "颜色", self, enableAlpha=True)
                palette.setFixedHeight(32)
                self.line_color_widget[name]=palette

                # 连接颜色变化信号
                palette.colorChanged.connect(lambda c, param_name=name: self._on_color_changed(c, param_name))

                group = CardGroupWidget(FIF.PALETTE, name, "", self)
                group.setFixedHeight(40)
                # 设置 hBoxLayout 垂直居中对齐
                group.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                # 添加控件
                group.hBoxLayout.addWidget(palette, stretch=0)
                if i<self.length-1 :
                    group.setSeparatorVisible(True)
                group.hBoxLayout.setContentsMargins(24, 4, 24, 4)
                group.textLayout.removeWidget(group.contentLabel)
                layout.addWidget(group)
                total_height += 40
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置qwidget的固定高度
        qwidget.setFixedHeight(total_height)
        return qwidget

    def _on_color_changed(self, color, name):
        """颜色选择回调"""
        # 将QColor对象转换为RGB字符串格式
        r = color.red()
        g = color.green()
        b = color.blue()
        value = f'rgb({r}, {g}, {b})'
        if value!=self.indicator.line_color[name]:
            self.is_params_changes=True
            self.indicator.line_color[name] = value
            # print(value)
            QTimer().singleShot(0, lambda: self.indicator.indicator_lines[name].set_line_color(value))
            
    def create_price_visible_group(self):
        """
        创建价格可见分组
        """
        self.price_visible_widget={}
        qwidget=QWidget(self)
        layout=QVBoxLayout(qwidget)
        # 设置布局间距为0
        layout.setSpacing(0)
        total_height = 0

        # 如果没有价格可见设置，显示提示信息
        if not self.indicator.price_visible:
            hint_label = BodyLabel("该指标没有其它可设置项", self)
            hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint_label.setStyleSheet("color: #666; padding: 20px;")
            layout.addWidget(hint_label)
            total_height = 60
        else:
            for i,(name,value) in enumerate(self.indicator.price_visible.items()):
                text='开启' if value else '关闭'
                switchButton=SwitchButton(text, self, IndicatorPosition.RIGHT)
                switchButton.setFixedHeight(32)
                self.price_visible_widget[name]=switchButton
                group = CardGroupWidget(FIF.MARKET, name, "", self)
                group.setFixedHeight(40)
                # 设置 hBoxLayout 垂直居中对齐
                group.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                # 添加控件
                group.hBoxLayout.addWidget(switchButton, stretch=0)
                switchButton.checkedChanged.connect(lambda checked, n=name, s=switchButton: self._on_price_visible_changed(n, s.isChecked()))
                if i<self.length-1 :
                    group.setSeparatorVisible(True)
                group.hBoxLayout.setContentsMargins(24, 4, 24, 4)
                group.textLayout.removeWidget(group.contentLabel)
                layout.addWidget(group)
                total_height += 40
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置qwidget的固定高度
        qwidget.setFixedHeight(total_height)
        return qwidget
    
    def _on_price_visible_changed(self, name, value):
        """
        价格可见改变时的处理函数
        """
        value=bool(value)
        if value!=self.indicator.price_visible[name]:
            self.is_params_changes=True
            self.indicator.price_visible[name]=value
            QTimer().singleShot(0, lambda: (line.set_price_visible(value) for _,line in self.indicator.indicator_lines.items()))
            
    def handleKeyPress(self, event, editor):
        """
        处理按键事件，当按下Enter键时触发确认按钮的功能
        """
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.lcw.chart_window.replay_indicator_params(self.indicator.id, self,self.callback)
        else:
            # 调用原始的keyPressEvent方法
            LineEdit.keyPressEvent(editor, event)
    
    def keyPressEvent(self, event):
        """
        处理窗口的按键事件，当按下Enter键时触发确认按钮的功能
        """
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.lcw.chart_window.replay_indicator_params(self.indicator.id, self,self.callback)
        else:
            # 调用父类的keyPressEvent方法
            super().keyPressEvent(event)
    
    def _normalBackgroundColor(self):
        return QColor(30, 30, 30, 255) if isDarkTheme() else QColor(255, 255, 255, 255)

    def _hoverBackgroundColor(self):
        return QColor(30, 30, 30, 255) if isDarkTheme() else QColor(255, 255, 255, 255)

    def _pressedBackgroundColor(self):
        return QColor(30, 30, 30, 255) if isDarkTheme() else QColor(255, 255, 255, 255)


class _CommandViewBar(CommandViewBar):
    
    def _showMoreActionsMenu(self):
        self.moreButton.clearState()

        actions = self._hiddenActions.copy()

        for w in reversed(self._hiddenWidgets):
            if isinstance(w, CommandButton):
                actions.insert(0, w.action())

        menu = CommandViewMenu(self)
        menu.setItemHeight(24)
        menu.hBoxLayout.setContentsMargins(2, 2, 2, 2)
        menu.addActions(actions)

        # adjust the shape of view
        view = self.parent()  # type: CommandBarView
        view.setMenuVisible(True)

        # adjust the shape of menu
        menu.closedSignal.connect(lambda: view.setMenuVisible(False))
        menu.setDropDown(self.isMenuDropDown(), menu.view.width() > view.width()+5)

        # adjust menu size
        if menu.view.width() < view.width():
            menu.view.setFixedWidth(view.width())
            menu.adjustSize()

        x = -menu.width() + menu.layout().contentsMargins().right() + \
            self.moreButton.width() + 18
        if self.isMenuDropDown():
            y = self.moreButton.height()
        else:
            y = -13
            menu.setShadowEffect(0, (0, 0), QColor(0, 0, 0, 0))
            menu.layout().setContentsMargins(2, 2, 2, 2)

        pos = self.moreButton.mapToGlobal(QPoint(x, y))
        pos.setX(pos.x()-16)
        menu.exec(pos, aniType=self._menuAnimation)
        
    def insertAction_from_index(self, index: int, action: QAction):
        button = self._createButton(action)
        self._insertWidgetToLayout(index, button)
        super().addAction(action)
        return button


class IndCommandBarView(CommandBarView):

    def __init__(self, parent=None, indicator_name="indicator"):
        super().__init__(parent=parent)
        self.hBoxLayout.removeWidget(self.bar)
        self.bar.deleteLater()
        self.bar=_CommandViewBar(self)
        self.setButtonTight(True)
        self.setIconSize(QSize(14, 14))
        self.hBoxLayout.addWidget(self.bar)
        label = BodyLabel(indicator_name, self)
        label.setAlignment(Qt.AlignCenter)
        label.adjustSize()
        self.hBoxLayout.insertWidget(0, label)
        self.hBoxLayout.setContentsMargins(8, 0, 0, 0)
        self.setFixedHeight(24)


def showIndicatorParamsCard(parent:"LightChartWindow", pos:QPoint, indicator:"Indicator"):
    """
    显示指标参数卡

    参数:
        parent: 父窗口
        pos: 显示位置
        indicator_info: 指标信息字典
    """
    def callback():
        flyout.close()

    # 创建指标参数卡
    params_card = IndicatorParamsCard(parent, indicator,callback)

    # 获取Flyout实例
    flyout = Flyout.make(params_card, pos, parent, FlyoutAnimationType.FADE_IN)

    return flyout

def showColorDialog(parent:"LightChartWindow",color,callback:callable):
    """
    显示颜色选择器
    
    参数:
        parent: 父窗口
        callback: 颜色选择器关闭时调用的回调函数，参数为选中的颜色QColor
    """
    w = ColorDialog(color, "选择颜色", parent)
    w.colorChanged.connect(lambda c: callback(c))
    w.exec()


def createIndicatorCardMenu(parent:"LightChartWindow", pos:QPoint, indicator_info:dict={}):
    """
    创建指标卡片菜单
    
    参数:
        parent: 父窗口
        pos: 显示位置
        indicator_name: 指标名称（旧参数，兼容性保留）
        indicator_value: 指标值（旧参数，兼容性保留）
        indicator_info: 指标信息字典（新参数），包含:
            - type: "enter" 或 "leave"
            - index: 指标在legend._lines中的索引
            - text: 指标标签的文本内容
            - color: 指标颜色
            - name: 指标名称
            - indicator_id: 指标ID
            - chart_id: 图表ID
    """
    chart=parent.chart_window
    # 如果传入了 indicator_info，使用其中的信息
    # if indicator_info and isinstance(indicator_info, dict):
    chart_id = indicator_info.get("chart_id",  "Unknown")
    indicator_name = indicator_info.get("name", "")
    indicator_id = indicator_info.get("indicatorId", -1)
    # print(f"📊 显示指标菜单: {indicator_name}, 指标_id: {indicator_id},chart_id: {chart_id}")
    indicator = chart.indicator_manager.getIndicator(indicator_id)
    indicator_dict = chart.chart_indicators.get(indicator_id, {})
    if not indicator_dict:
        return
    line :Line = indicator_dict.get(indicator_name, None)
    # 使用line.is_visible()方法获取指标的可视状态
    is_visible = line.is_visible() if line else False
    view = IndCommandBarView(parent, indicator_name)

    def onUpdate():
        """参数按钮点击事件处理"""
        if not indicator.params:
            InfoBar.warning("警告", "该指标没有参数",duration=1000,parent=parent)
            return
        showIndicatorParamsCard(parent, pos, indicator)
    
    def hide_indicator(action:Action):
        """隐藏指标"""
        line.hide_data()
        view.removeAction(action)
        new_action = Action(FIF.HIDE, '隐藏')
        new_action.triggered.connect(lambda: show_indicator(new_action))
        view.bar.insertAction_from_index(1, new_action)
        
    def show_indicator(action:Action):
        """显示指标"""
        line.show_data()
        view.removeAction(action)
        new_action = Action(FIF.VIEW, '显示')
        new_action.triggered.connect(lambda: hide_indicator(new_action))
        view.bar.insertAction_from_index(1, new_action)

    view.addAction(Action(FIF.SETTING, '参数', triggered=onUpdate))
    #color_action = Action(FIF.PALETTE, '颜色')
    #color_action.triggered.connect(lambda: showColorDialog(parent, indicator.line_color[indicator_name], lambda c: change_indicator_color(indicator_id, indicator_name, c)))
    #view.addAction(color_action)
    
    
    if is_visible:
        action = Action(FIF.VIEW, '显示')
        action.triggered.connect(lambda: hide_indicator(action))
        view.addAction(action)
    else:
        action = Action(FIF.HIDE, '隐藏')
        action.triggered.connect(lambda: show_indicator(action))
        view.addAction(action)
    
    def delete_indicator():
        """删除指标"""
        chart.remove_indicator(indicator_id)
        flyout.close()
        
    
    
    delete_action = Action(FIF.DELETE, '删除', triggered=delete_indicator)
    view.addAction(delete_action)

    

    view.addHiddenAction(Action(FIF.CODE, '代码'))#, shortcut='Ctrl+P'))
    #view.addHiddenAction(Action(FIF.SETTING, 'Settings', shortcut='Ctrl+S'))
    view.resizeToSuitableWidth()
    # 获取Flyout实例并连接其closed信号
    flyout = Flyout.make(view, pos, parent, FlyoutAnimationType.FADE_IN)
    # if flyout and hasattr(parent, 'chart_window') and hasattr(parent.chart_window, 'reset_indicator_card_visible'):
    #flyout.closed.connect(parent.chart_window.chart_updater.set_indicator_calculated_status)
        
