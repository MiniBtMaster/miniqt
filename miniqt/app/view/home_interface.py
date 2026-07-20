# coding:utf-8
import os
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from qfluentwidgets import ScrollArea, isDarkTheme, FluentIcon
from ..common.config import cfg, HELP_URL, REPO_URL, EXAMPLE_URL, FEEDBACK_URL
from ..common.icon import Icon, FluentIconBase
from ..components.link_card import LinkCardView
from ..components.sample_card import SampleCardView
from ..common.style_sheet import StyleSheet

_res_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BannerWidget(QWidget):
    """ Banner widget """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(336)

        self.vBoxLayout = QVBoxLayout(self)
        self.galleryLabel = QLabel('Mini Quant Trader', self)
        self.banner = QPixmap(os.path.join(_res_dir, 'resource', 'images', 'miniqt_home_dark.png' if isDarkTheme() else 'miniqt_home_light.png'))
        self.linkCardView = LinkCardView(self)

        self.galleryLabel.setObjectName('galleryLabel')

        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 20, 0, 0)
        self.vBoxLayout.addWidget(self.galleryLabel)
        self.vBoxLayout.addWidget(self.linkCardView, 1, Qt.AlignmentFlag.AlignBottom)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.linkCardView.addCard(
            FluentIcon.GITHUB,
            'GitHub仓库',
            'miniqt的GitHub仓库',
            'https://github.com/MiniBtMaster/miniqt'
        )

        self.linkCardView.addCard(
            FluentIcon.CODE,
            'PyPI仓库',
            '通过pip安装miniqt包',
            'https://pypi.org/project/miniqt/'
        )

        self.linkCardView.addCard(
            FluentIcon.GLOBE,
            '在线教程',
            '详细的miniqt使用教程和文档',
            'https://www.minibt.cn'
        )

        self.linkCardView.addCard(
            FluentIcon.BOOK_SHELF,
            '知乎专栏',
            '量化交易相关知识和策略分享',
            'https://zhuanlan.zhihu.com/column/c_1942555756558783128'
        )

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        path = QPainterPath()
        path.setFillRule(Qt.FillRule.WindingFill)
        w, h = self.width(), self.height()
        path.addRoundedRect(QRectF(0, 0, w, h), 10, 10)
        path.addRect(QRectF(0, h-50, 50, 50))
        path.addRect(QRectF(w-50, 0, 50, 50))
        path.addRect(QRectF(w-50, h-50, 50, 50))
        path = path.simplified()

        # init linear gradient effect
        gradient = QLinearGradient(0, 0, 0, h)

        # draw background color
        if not isDarkTheme():
            gradient.setColorAt(0, QColor(207, 216, 228, 255))
            gradient.setColorAt(1, QColor(207, 216, 228, 0))
        else:
            gradient.setColorAt(0, QColor(0, 0, 0, 255))
            gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.fillPath(path, QBrush(gradient))

        # draw banner image
        pixmap = self.banner.scaled(
            self.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        painter.fillPath(path, QBrush(pixmap))


class HomeInterface(ScrollArea):
    """ Home interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.banner = BannerWidget(self)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)

        self.__initWidget()
        self.loadSamples()

    def __initWidget(self):
        self.view.setObjectName('view')
        self.setObjectName('homeInterface')
        StyleSheet.HOME_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 10)
        self.vBoxLayout.setSpacing(10)
        self.vBoxLayout.addWidget(self.banner)

    def loadSamples(self):
        """ load samples """

        # ── 快捷入口 ──
        quickEntryView = SampleCardView("快捷入口", self.view)
        quickEntryView.addSampleCard(
            icon=FluentIcon.DOCUMENT,
            title="行情报价",
            content="查看各交易所主力合约实时行情数据",
            routeKey="marketQuoteInterface",
            index=0
        )
        quickEntryView.addSampleCard(
            icon=FluentIcon.CODE,
            title="策略回测",
            content="创建和运行量化策略回测，分析策略表现",
            routeKey="strategyBacktestInterface",
            index=0
        )
        quickEntryView.addSampleCard(
            icon=FluentIcon.GLOBE,
            title="minibt官网",
            content="访问 minibt 官方网站，获取最新资讯和文档",
            routeKey="officialWebsiteInterface",
            index=0
        )
        quickEntryView.addSampleCard(
            icon=FluentIcon.SETTING,
            title="系统设置",
            content="配置应用主题、数据源、图表参数等选项",
            routeKey="settingInterface",
            index=0
        )
        self.vBoxLayout.addWidget(quickEntryView)

        # ── 登录接口 ──
        loginView = SampleCardView("登录接口", self.view)
        loginView.addSampleCard(
            icon=FluentIcon.COPY,
            title="期货登录",
            content="登录天勤期货账户，获取实时行情数据",
            routeKey="loginFutures",
            index=0
        )
        loginView.addSampleCard(
            icon=FluentIcon.CUT,
            title="股票登录",
            content="登录股票交易账户，获取股票实时行情",
            routeKey="loginStocks",
            index=0
        )
        self.vBoxLayout.addWidget(loginView)

        # ── 开发工具 ──
        toolsView = SampleCardView("开发工具", self.view)
        toolsView.addSampleCard(
            icon=FluentIcon.COMMAND_PROMPT,
            title="终端窗口",
            content="打开交互式终端窗口，执行系统命令",
            routeKey="terminalWindow",
            index=0
        )
        toolsView.addSampleCard(
            icon=FluentIcon.BOOK_SHELF,
            title="Jupyter窗口",
            content="启动 Jupyter Notebook 交互式编程环境",
            routeKey="jupyterWindow",
            index=0
        )
        toolsView.addSampleCard(
            icon=FluentIcon.BOOK_SHELF,
            title="JupyterLab窗口",
            content="启动 JupyterLab 高级交互式开发环境",
            routeKey="jupyterLabWindow",
            index=0
        )
        # toolsView.addSampleCard(
        #     icon=FluentIcon.ACCEPT,
        #     title="测试图表",
        #     content="打开测试图表窗口，验证图表显示功能",
        #     routeKey="testChart",
        #     index=0
        # )
        self.vBoxLayout.addWidget(toolsView)
        self.vBoxLayout.addStretch()
