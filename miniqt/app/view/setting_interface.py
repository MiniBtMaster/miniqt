# coding:utf-8
from qfluentwidgets import (SettingCardGroup, SwitchSettingCard, FolderListSettingCard,
                            OptionsSettingCard, PushSettingCard,
                            HyperlinkCard, PrimaryPushSettingCard, ScrollArea,
                            ComboBoxSettingCard, ExpandLayout, Theme, CustomColorSettingCard,
                            setTheme, setThemeColor, RangeSettingCard, isDarkTheme,
                            NavigationInterface, NavigationItemPosition, SubtitleLabel, InfoBarPosition,
                            qconfig)
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar, MessageBox
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QStandardPaths
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QWidget, QLabel, QFileDialog, QHBoxLayout, QStackedWidget

from ..common.config import cfg, HELP_URL, FEEDBACK_URL, AUTHOR, VERSION, YEAR, isWin11
from ..common.chart_config import chart_cfg
from ..common.data_config import data_cfg
from ..common.signal_bus import signalBus
from ..common.style_sheet import StyleSheet
import os


# =============================================================================
# SystemSettingInterface (原 gallery SettingInterface)
# =============================================================================

class SystemSettingInterface(ScrollArea):
    """ System setting interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # setting label
        self.settingLabel = QLabel('设置', self)

        # 本地文件
        self.musicInThisPCGroup = SettingCardGroup(
            '本地文件', self.scrollWidget)
        self.musicFolderCard = FolderListSettingCard(
            cfg.musicFolders,
            '本地库',
            directory=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MusicLocation),
            parent=self.musicInThisPCGroup
        )
        self.downloadFolderCard = PushSettingCard(
            '选择文件夹',
            FIF.DOWNLOAD,
            '下载目录',
            cfg.get(cfg.downloadFolder),
            self.musicInThisPCGroup
        )

        # 个性化
        self.personalGroup = SettingCardGroup(
            '个性化', self.scrollWidget)
        # self.micaCard = SwitchSettingCard(
        #     FIF.TRANSPARENT,
        #     '云母效果',
        #     '为窗口和界面应用半透明效果',
        #     cfg.micaEnabled,
        #     self.personalGroup
        # )
        self.themeCard = OptionsSettingCard(
            cfg.pendingThemeMode,
            FIF.BRUSH,
            '应用主题',
            '更改应用外观',
            texts=[
                '浅色', '深色',
                '使用系统设置'
            ],
            parent=self.personalGroup
        )
        self.themeColorCard = CustomColorSettingCard(
            cfg.themeColor,
            FIF.PALETTE,
            '主题颜色',
            '更改应用主题颜色',
            self.personalGroup
        )
        # self.zoomCard = OptionsSettingCard(
        #     cfg.dpiScale,
        #     FIF.ZOOM,
        #     '界面缩放',
        #     '更改控件和字体大小',
        #     texts=[
        #         "100%", "125%", "150%", "175%", "200%",
        #         '使用系统设置'
        #     ],
        #     parent=self.personalGroup
        # )
        # self.languageCard = ComboBoxSettingCard(
        #     cfg.language,
        #     FIF.LANGUAGE,
        #     '语言',
        #     '设置界面首选语言',
        #     texts=['简体中文', '繁體中文', 'English', '使用系统设置'],
        #     parent=self.personalGroup
        # )

        # 材质
        # self.materialGroup = SettingCardGroup(
        #     '材质', self.scrollWidget)
        # self.blurRadiusCard = RangeSettingCard(
        #     cfg.blurRadius,
        #     FIF.ALBUM,
        #     '亚克力模糊半径',
        #     '半径越大，图像越模糊',
        #     self.materialGroup
        # )

        # 软件更新
        self.updateSoftwareGroup = SettingCardGroup(
            '软件更新', self.scrollWidget)
        self.updateOnStartUpCard = SwitchSettingCard(
            FIF.UPDATE,
            '启动时检查更新',
            '新版本更稳定，功能更丰富',
            configItem=cfg.checkUpdateAtStartUp,
            parent=self.updateSoftwareGroup
        )

        # 关于
        self.aboutGroup = SettingCardGroup('关于', self.scrollWidget)
        self.helpCard = HyperlinkCard(
            HELP_URL,
            '打开帮助页面',
            FIF.HELP,
            '帮助',
            '发现新功能和了解 minibt 的使用技巧',
            self.aboutGroup
        )
        self.feedbackCard = PrimaryPushSettingCard(
            '提交反馈',
            FIF.FEEDBACK,
            '提交反馈',
            '帮助我们改进 minibt，欢迎提供反馈',
            self.aboutGroup
        )
        self.aboutCard = PrimaryPushSettingCard(
            '检查更新',
            FIF.INFO,
            '关于',
            '© 版权所有 ' + f" {YEAR}, {AUTHOR}. " +
            '版本' + " " + VERSION,
            self.aboutGroup
        )

        self.__initWidget()

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName('systemSettingInterface')

        # initialize style sheet
        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)

        # self.micaCard.setEnabled(isWin11())

        # initialize layout
        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        self.settingLabel.move(36, 30)

        # add cards to group
        self.musicInThisPCGroup.addSettingCard(self.musicFolderCard)
        self.musicInThisPCGroup.addSettingCard(self.downloadFolderCard)

        # self.personalGroup.addSettingCard(self.micaCard)
        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.themeColorCard)
        # self.personalGroup.addSettingCard(self.zoomCard)
        # self.personalGroup.addSettingCard(self.languageCard)

        # self.materialGroup.addSettingCard(self.blurRadiusCard)

        self.updateSoftwareGroup.addSettingCard(self.updateOnStartUpCard)

        self.aboutGroup.addSettingCard(self.helpCard)
        self.aboutGroup.addSettingCard(self.feedbackCard)
        self.aboutGroup.addSettingCard(self.aboutCard)

        # add setting card group to layout
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.musicInThisPCGroup)
        self.expandLayout.addWidget(self.personalGroup)
        # self.expandLayout.addWidget(self.materialGroup)
        self.expandLayout.addWidget(self.updateSoftwareGroup)
        self.expandLayout.addWidget(self.aboutGroup)

    def __showRestartTooltip(self):
        """ show restart tooltip """
        InfoBar.success(
            self.tr('Updated successfully'),
            self.tr('Configuration takes effect after restart'),
            duration=1500,
            parent=self
        )

    def __onDownloadFolderCardClicked(self):
        """ download folder card clicked slot """
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Choose folder"), "./")
        if not folder or cfg.get(cfg.downloadFolder) == folder:
            return

        cfg.set(cfg.downloadFolder, folder)
        self.downloadFolderCard.setContent(folder)

    def __connectSignalToSlot(self):
        """ connect signal to slot """
        cfg.appRestartSig.connect(self.__showRestartTooltip)

        # music in the pc
        self.downloadFolderCard.clicked.connect(self.__onDownloadFolderCardClicked)

        # personalization - 主题切换仅保存配置，不即时切换
        self.themeCard.optionChanged.connect(self.__onThemeModeChanged)
        self.themeColorCard.colorChanged.connect(lambda c: setThemeColor(c))
        # self.micaCard.checkedChanged.connect(signalBus.micaEnableChanged)

        # about
        self.feedbackCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_URL)))

    def __onThemeModeChanged(self, configItem):
        """主题模式变更时仅保存配置并提示（不即时切换）"""
        # 同步到 qconfig.themeMode（仅赋值，不触发主题切换）
        theme_value = cfg.get(cfg.pendingThemeMode)
        qconfig.themeMode.value = theme_value
        qconfig.save()
        InfoBar.success(
            '主题切换成功',
            '重启程序生效',
            duration=3000,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self.window()
        )


# =============================================================================
# DataSettingInterface (从 miniqt 迁移，PySide6 → PyQt6)
# =============================================================================

class DataSettingInterface(ScrollArea):
    """ Data setting interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setting_interface: SettingInterface = parent
        self.scrollWidget = SubtitleLabel()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # setting label
        self.settingLabel = SubtitleLabel("数据设置", self)

        # data folders
        self.dataFolderGroup = SettingCardGroup("数据存储", self.scrollWidget)
        # self.dataFolderCard = PushSettingCard(
        #     '选择文件夹',
        #     FIF.FOLDER,
        #     "数据存储目录",
        #     cfg.get(cfg.downloadFolder),
        #     self.dataFolderGroup
        # )

        # data refresh
        self.dataRefreshGroup = SettingCardGroup('数据刷新', self.scrollWidget)
        self.dataRefreshCard = PushSettingCard(
            '5秒',
            FIF.ADD_TO,
            '数据刷新频率',
            '设置数据自动刷新的频率',
            parent=self.dataRefreshGroup
        )

        # data export
        self.dataExportGroup = SettingCardGroup('数据导出', self.scrollWidget)
        self.dataExportCard = PushSettingCard(
            '导出数据',
            FIF.DATE_TIME,
            '导出数据',
            '将数据导出为CSV或Excel格式',
            self.dataExportGroup
        )

        # data source
        self.dataSourceGroup = SettingCardGroup('数据源', self.scrollWidget)
        self.useLocalDataCard = SwitchSettingCard(
            FIF.FOLDER,
            '使用本地数据',
            '启用后将优先使用本地存储的数据',
            cfg.useLocalData,
            self.dataSourceGroup
        )

        # # Llama.cpp设置
        # self.llamaCppGroup = SettingCardGroup('Llama.cpp设置', self.scrollWidget)

        # self.llamaCppModelPathCard = PushSettingCard(
        #     '选择路径',
        #     FIF.FOLDER,
        #     "模型文件路径",
        #     data_cfg.get(data_cfg.llamaCppModelPath),
        #     self.llamaCppGroup
        # )

        # self.llamaCppConversationsPathCard = PushSettingCard(
        #     '选择路径',
        #     FIF.FOLDER,
        #     "会话记录保存路径",
        #     data_cfg.get(data_cfg.llamaCppConversationsPath),
        #     self.llamaCppGroup
        # )

        # # Ollama设置
        # self.ollamaGroup = SettingCardGroup('Ollama设置', self.scrollWidget)

        # self.ollamaPathCard = PushSettingCard(
        #     '选择路径',
        #     FIF.FOLDER,
        #     "Ollama路径",
        #     data_cfg.get(data_cfg.ollamaPath),
        #     self.ollamaGroup
        # )

        # self.ollamaMaxLoadedModelsCard = RangeSettingCard(
        #     data_cfg.ollamaMaxLoadedModels,
        #     FIF.LAYOUT,
        #     '最大加载模型数量',
        #     '同时加载的最大模型数量',
        #     self.ollamaGroup
        # )

        # self.ollamaMaxMemoryCard = PushSettingCard(
        #     '设置',
        #     FIF.ACCEPT,
        #     '最大内存使用',
        #     data_cfg.get(data_cfg.ollamaMaxMemory),
        #     self.ollamaGroup
        # )

        # self.ollamaNumParallelCard = RangeSettingCard(
        #     data_cfg.ollamaNumParallel,
        #     FIF.SEND,
        #     '并行处理请求数量',
        #     '并行处理请求的数量',
        #     self.ollamaGroup
        # )

        # self.ollamaKeepAliveCard = PushSettingCard(
        #     '设置',
        #     FIF.DATE_TIME,
        #     '保持加载的时间',
        #     data_cfg.get(data_cfg.ollamaKeepAlive),
        #     self.ollamaGroup
        # )

        # self.ollamaContextLengthCard = RangeSettingCard(
        #     data_cfg.ollamaContextLength,
        #     FIF.MENU,
        #     '上下文窗口大小',
        #     '上下文窗口大小（token数）',
        #     self.ollamaGroup
        # )

        # self.ollamaNumThreadsCard = RangeSettingCard(
        #     data_cfg.ollamaNumThreads,
        #     FIF.ACCEPT,
        #     '线程数量',
        #     '处理请求时使用的线程数量',
        #     self.ollamaGroup
        # )

        # self.ollamaHostCard = RangeSettingCard(
        #     data_cfg.ollamaHost,
        #     FIF.GLOBE,
        #     '服务端口',
        #     'Ollama服务监听的端口',
        #     self.ollamaGroup
        # )

        # self.ollamaApplyCard = PushSettingCard(
        #     '应用',
        #     FIF.SYNC,
        #     '应用设置',
        #     '点击应用设置并重启Ollama服务',
        #     self.ollamaGroup
        # )

        self.__initWidget()

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName('dataSettingInterface')

        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)

        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        self.settingLabel.move(36, 30)

        # self.dataFolderGroup.addSettingCard(self.dataFolderCard)
        # self.dataFolderGroup.addSettingCard(self.ollamaModelsCard)
        self.dataRefreshGroup.addSettingCard(self.dataRefreshCard)
        self.dataExportGroup.addSettingCard(self.dataExportCard)
        self.dataSourceGroup.addSettingCard(self.useLocalDataCard)

        # self.llamaCppGroup.addSettingCard(self.llamaCppModelPathCard)
        # self.llamaCppGroup.addSettingCard(self.llamaCppConversationsPathCard)

        # self.ollamaGroup.addSettingCard(self.ollamaPathCard)
        # self.ollamaGroup.addSettingCard(self.ollamaMaxLoadedModelsCard)
        # self.ollamaGroup.addSettingCard(self.ollamaMaxMemoryCard)
        # self.ollamaGroup.addSettingCard(self.ollamaNumParallelCard)
        # self.ollamaGroup.addSettingCard(self.ollamaKeepAliveCard)
        # self.ollamaGroup.addSettingCard(self.ollamaContextLengthCard)
        # self.ollamaGroup.addSettingCard(self.ollamaNumThreadsCard)
        # self.ollamaGroup.addSettingCard(self.ollamaHostCard)
        # self.ollamaGroup.addSettingCard(self.ollamaApplyCard)

        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.dataFolderGroup)
        self.expandLayout.addWidget(self.dataRefreshGroup)
        self.expandLayout.addWidget(self.dataExportGroup)
        self.expandLayout.addWidget(self.dataSourceGroup)
        # self.expandLayout.addWidget(self.llamaCppGroup)
        # self.expandLayout.addWidget(self.ollamaGroup)

    def __connectSignalToSlot(self):
        self.useLocalDataCard.checkedChanged.connect(lambda checked: cfg.useLocalDataChanged.emit(checked))
        # self.llamaCppModelPathCard.clicked.connect(self.__onLlamaCppModelPathCardClicked)
        # self.llamaCppConversationsPathCard.clicked.connect(self.__onLlamaCppConversationsPathCardClicked)
        # self.ollamaPathCard.clicked.connect(self.__onOllamaPathCardClicked)
        # self.ollamaMaxMemoryCard.clicked.connect(self.__onOllamaMaxMemoryCardClicked)
        # self.ollamaKeepAliveCard.clicked.connect(self.__onOllamaKeepAliveCardClicked)
        # self.ollamaApplyCard.clicked.connect(self.__onOllamaApplyCardClicked)

    # def __onLlamaCppModelPathCardClicked(self):
    #     folder = QFileDialog.getExistingDirectory(
    #         self, "选择Llama.cpp模型文件夹",
    #         data_cfg.get(data_cfg.llamaCppModelPath))
    #     if folder:
    #         data_cfg.set(data_cfg.llamaCppModelPath, folder)
    #         data_cfg.save()
    #         self.llamaCppModelPathCard.setContent(folder)

    def __onLlamaCppConversationsPathCardClicked(self):
        folder = QFileDialog.getExistingDirectory(
            self, "选择会话记录保存路径",
            data_cfg.get(data_cfg.llamaCppConversationsPath))
        if folder:
            data_cfg.set(data_cfg.llamaCppConversationsPath, folder)
            data_cfg.save()
            self.llamaCppConversationsPathCard.setContent(folder)
            signalBus.llamaConversationsPathChanged.emit(folder)

    def __onOllamaPathCardClicked(self):
        folder = QFileDialog.getExistingDirectory(
            self, "选择Ollama路径", data_cfg.get(data_cfg.ollamaPath))
        if folder:
            data_cfg.set(data_cfg.ollamaPath, folder)
            data_cfg.save()
            self.ollamaPathCard.setContent(folder)

    def __onOllamaMaxMemoryCardClicked(self):
        w = MessageBox("设置最大内存", "请输入最大内存使用（例如：10gb, 512mb）：", self)
        w.yesButton.setText("确定")
        w.cancelButton.setText("取消")
        if w.exec():
            text = w.textEdit.toPlainText().strip()
            if text:
                data_cfg.set(data_cfg.ollamaMaxMemory, text)
                data_cfg.save()
                self.ollamaMaxMemoryCard.setContent(text)

    def __onOllamaKeepAliveCardClicked(self):
        w = MessageBox("设置保持加载时间", "请输入保持加载的时间（例如：5m, 1h, 30s）：", self)
        w.yesButton.setText("确定")
        w.cancelButton.setText("取消")
        if w.exec():
            text = w.textEdit.toPlainText().strip()
            if text:
                data_cfg.set(data_cfg.ollamaKeepAlive, text)
                data_cfg.save()
                self.ollamaKeepAliveCard.setContent(text)

    def __onOllamaApplyCardClicked(self):
        import subprocess
        import os
        import time

        w = MessageBox("应用设置", "应用设置将重启Ollama服务，是否继续？", self)
        w.yesButton.setText("确定")
        w.cancelButton.setText("取消")

        if w.exec():
            try:
                print("正在结束Ollama进程...")
                subprocess.run(['taskkill', '/f', '/im', 'ollama.exe'],
                               capture_output=True, text=True)
                time.sleep(2)

                ollama_path = data_cfg.get(data_cfg.ollamaPath)
                os.environ['OLLAMA_MAX_LOADED_MODELS'] = str(data_cfg.get(data_cfg.ollamaMaxLoadedModels))
                os.environ['OLLAMA_MAX_MEMORY'] = data_cfg.get(data_cfg.ollamaMaxMemory)
                os.environ['OLLAMA_NUM_PARALLEL'] = str(data_cfg.get(data_cfg.ollamaNumParallel))
                os.environ['OLLAMA_KEEP_ALIVE'] = data_cfg.get(data_cfg.ollamaKeepAlive)
                os.environ['OLLAMA_CONTEXT_LENGTH'] = str(data_cfg.get(data_cfg.ollamaContextLength))
                os.environ['OLLAMA_NUM_THREADS'] = str(data_cfg.get(data_cfg.ollamaNumThreads))
                os.environ['OLLAMA_HOST'] = f"127.0.0.1:{data_cfg.get(data_cfg.ollamaHost)}"
                print("Ollama环境变量已设置")

                if os.path.isdir(ollama_path):
                    ollama_exe = os.path.join(ollama_path, "ollama.exe")
                else:
                    ollama_exe = ollama_path

                if not os.path.exists(ollama_exe):
                    InfoBar.error('启动失败', '找不到 ollama.exe，请检查 Ollama 路径',
                                  duration=3000, position=InfoBarPosition.TOP, parent=self)
                    return

                subprocess.Popen(
                    [ollama_exe, 'serve'],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    env=os.environ.copy()
                )
                print("Ollama服务已启动")

                InfoBar.success('应用成功', 'Ollama设置已应用并重启服务',
                                duration=3000, position=InfoBarPosition.TOP, parent=self)
            except Exception as e:
                print(f"应用设置时出错: {str(e)}")
                InfoBar.error('应用失败', f'应用设置时出错: {str(e)}',
                              duration=3000, position=InfoBarPosition.TOP, parent=self)


# =============================================================================
# ChartSettingInterface (从 miniqt 迁移，PySide6 → PyQt6)
# =============================================================================

class ChartSettingInterface(ScrollArea):
    """ Chart setting interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setting_interface: SettingInterface = parent
        self.scrollWidget = SubtitleLabel()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        self.settingLabel = SubtitleLabel("图表设置", self)

        # chart reset group
        self.chartResetGroup = SettingCardGroup("图表配置", self.scrollWidget)
        self.resetDefaultCard = PushSettingCard(
            '恢复默认',
            FIF.UPDATE,
            '恢复默认设置',
            '将所有图表设置恢复为默认值',
            self.chartResetGroup
        )

        self.futuresDataLengthCard = OptionsSettingCard(
            chart_cfg.futuresDataLength,
            FIF.DATE_TIME,
            '期货数据长度',
            '设置获取期货K线数据的长度（根数），越大加载越慢',
            [str(option) for option in chart_cfg.futuresDataLength.validator.options],
            self.chartResetGroup
        )

        # chart appearance
        self.chartAppearanceGroup = SettingCardGroup("图表外观", self.scrollWidget)
        self.toolBoxCard = SwitchSettingCard(
            FIF.ZOOM,
            '显示工具箱',
            '在图表上显示画线工具箱',
            chart_cfg.showToolBox,
            self.chartAppearanceGroup
        )

        # chart colors
        self.chartColorsGroup = SettingCardGroup('图表颜色', self.scrollWidget)

        self.mouseLabelColorCard = CustomColorSettingCard(
            chart_cfg.mouseLabelColor,
            FIF.PALETTE,
            '鼠标标签颜色',
            '设置鼠标悬停时标签的背景颜色',
            self.chartColorsGroup
        )

        self.bullColorCard = CustomColorSettingCard(
            chart_cfg.bullColor,
            FIF.UP,
            '上涨颜色',
            '设置K线上涨时的颜色（阳线）',
            self.chartColorsGroup
        )

        self.bearColorCard = CustomColorSettingCard(
            chart_cfg.bearColor,
            FIF.DOWN,
            '下跌颜色',
            '设置K线下跌时的颜色（阴线）',
            self.chartColorsGroup
        )

        # chart update
        self.chartUpdateGroup = SettingCardGroup('图表更新', self.scrollWidget)

        self.maxWorkersCard = OptionsSettingCard(
            chart_cfg.maxWorkers,
            FIF.DATE_TIME,
            '线程数',
            '设置图表更新的线程数',
            [str(option) for option in chart_cfg.maxWorkers.options],
            self.chartUpdateGroup
        )

        self.klineIntervalCard = OptionsSettingCard(
            chart_cfg.klineUpdateInterval,
            FIF.DATE_TIME,
            '期货K线更新频率(ms)',
            '设置期货K线数据的更新频率（毫秒）',
            [str(option) for option in chart_cfg.klineUpdateInterval.options],
            self.chartUpdateGroup
        )

        self.indicatorIntervalCard = OptionsSettingCard(
            chart_cfg.indicatorUpdateInterval,
            FIF.DATE_TIME,
            '期货指标更新频率(ms)',
            '设置期货指标数据的更新频率（毫秒）',
            [str(option) for option in chart_cfg.indicatorUpdateInterval.options],
            self.chartUpdateGroup
        )
        
        self.stockKlineIntervalCard = OptionsSettingCard(
            chart_cfg.stockKlineUpdateInterval,
            FIF.DATE_TIME,
            '股票K线更新频率(ms)',
            '设置股票K线数据的更新频率（毫秒），频率过高可能被服务器封禁IP',
            [str(option) for option in chart_cfg.stockKlineUpdateInterval.options],
            self.chartUpdateGroup
        )
        
        self.stockIndicatorIntervalCard = OptionsSettingCard(
            chart_cfg.stockIndicatorUpdateInterval,
            FIF.DATE_TIME,
            '股票指标更新频率(ms)',
            '设置股票指标数据的更新频率（毫秒）',
            [str(option) for option in chart_cfg.stockIndicatorUpdateInterval.options],
            self.chartUpdateGroup
        )

        self.applyCard = PushSettingCard(
            '应用',
            FIF.ACCEPT_MEDIUM,
            '应用设置',
            '点击应用按钮使设置立即生效',
            self.chartUpdateGroup
        )
        self.applyCard.button.setEnabled(False)

        # 行情数据管理
        self.marketDataGroup = SettingCardGroup('行情数据', self.scrollWidget)
        self.updateOnStartupCard = SwitchSettingCard(
            FIF.SYNC,
            '启动时更新行情',
            '每次启动并登录天勤后自动更新全部行情表格数据',
            chart_cfg.updateMarketOnStartup,
            self.marketDataGroup
        )

        self.__initWidget()

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName('chartSettingInterface')

        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)

        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        self.settingLabel.move(36, 30)
        self.chartResetGroup.addSettingCard(self.resetDefaultCard)
        self.chartResetGroup.addSettingCard(self.futuresDataLengthCard)
        self.chartAppearanceGroup.addSettingCard(self.toolBoxCard)
        self.chartColorsGroup.addSettingCard(self.mouseLabelColorCard)
        self.chartColorsGroup.addSettingCard(self.bullColorCard)
        self.chartColorsGroup.addSettingCard(self.bearColorCard)
        self.chartUpdateGroup.addSettingCard(self.maxWorkersCard)
        self.chartUpdateGroup.addSettingCard(self.klineIntervalCard)
        self.chartUpdateGroup.addSettingCard(self.indicatorIntervalCard)
        self.chartUpdateGroup.addSettingCard(self.stockKlineIntervalCard)
        self.chartUpdateGroup.addSettingCard(self.stockIndicatorIntervalCard)
        self.chartUpdateGroup.addSettingCard(self.applyCard)
        self.marketDataGroup.addSettingCard(self.updateOnStartupCard)

        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.chartResetGroup)
        self.expandLayout.addWidget(self.chartAppearanceGroup)
        self.expandLayout.addWidget(self.chartColorsGroup)
        self.expandLayout.addWidget(self.chartUpdateGroup)
        self.expandLayout.addWidget(self.marketDataGroup)

    def __onResetDefaultClicked(self):
        chart_cfg.resetToDefault()
        self.toolBoxCard.setChecked(chart_cfg.showToolBox.value)
        InfoBar.success('恢复成功', '图表设置已恢复为默认值', duration=1500, parent=self)

    def __connectSignalToSlot(self):
        self.resetDefaultCard.clicked.connect(self.__onResetDefaultClicked)

        self.mouseLabelColorCard.colorChanged.connect(lambda: chart_cfg.save())
        self.bullColorCard.colorChanged.connect(lambda: chart_cfg.save())
        self.bearColorCard.colorChanged.connect(lambda: chart_cfg.save())

        self.toolBoxCard.checkedChanged.connect(lambda: chart_cfg.save())

        def onUpdateSettingChanged():
            chart_cfg.save()
            self.applyCard.button.setEnabled(True)
            InfoBar.success('设置成功', '图表更新设置已保存', duration=1500, parent=self)

        self.maxWorkersCard.optionChanged.connect(onUpdateSettingChanged)
        self.klineIntervalCard.optionChanged.connect(onUpdateSettingChanged)
        self.indicatorIntervalCard.optionChanged.connect(onUpdateSettingChanged)
        self.stockKlineIntervalCard.optionChanged.connect(onUpdateSettingChanged)
        self.stockIndicatorIntervalCard.optionChanged.connect(onUpdateSettingChanged)
        self.futuresDataLengthCard.optionChanged.connect(onUpdateSettingChanged)

        self.updateOnStartupCard.checkedChanged.connect(lambda: chart_cfg.save())

        def onApplyClicked():
            chart_cfg.save()
            InfoBar.success('保存成功', '图表更新设置已保存，下次启动时生效',
                            duration=1500, parent=self)
            self.applyCard.button.setEnabled(False)

        self.applyCard.button.clicked.connect(onApplyClicked)


# =============================================================================
# SettingInterface 容器 (NavigationInterface + QStackedWidget)
# =============================================================================

class SettingInterface(QWidget):
    """ Setting interface with navigation """

    themeChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.navigationInterface = NavigationInterface(
            self, showMenuButton=False, showReturnButton=False, collapsible=False)
        self.stackWidget = QStackedWidget(self)

        # create sub interfaces
        self.systemSettingInterface = SystemSettingInterface(self)
        self.dataSettingInterface = DataSettingInterface(self)
        self.chartSettingInterface = ChartSettingInterface(self)

        self.initLayout()
        self.initNavigation()
        self.initWindow()

    def initLayout(self):
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.hBoxLayout.addWidget(self.navigationInterface)
        self.hBoxLayout.addWidget(self.stackWidget)
        self.hBoxLayout.setStretchFactor(self.stackWidget, 1)

    def initNavigation(self):
        self.navigationInterface.setExpandWidth(150)
        self.navigationInterface.expand()

        self.addSubInterface(self.systemSettingInterface, FIF.SETTING, '系统设置')
        self.addSubInterface(self.dataSettingInterface, FIF.ADD_TO, '数据设置')
        self.addSubInterface(self.chartSettingInterface, FIF.ADD_TO, '图表设置')

        self.stackWidget.setCurrentWidget(self.systemSettingInterface)

    def initWindow(self):
        self.resize(1200, 800)
        self.setObjectName('settingInterface')

    def addSubInterface(self, interface, icon, text: str):
        self.stackWidget.addWidget(interface)
        self.navigationInterface.addItem(
            routeKey=interface.objectName(),
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(interface)
        )

    def switchTo(self, widget):
        self.stackWidget.setCurrentWidget(widget)
        self.navigationInterface.setCurrentItem(widget.objectName())
