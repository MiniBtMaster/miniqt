# coding:utf-8
import sys
from enum import Enum

from PyQt6.QtCore import QLocale, pyqtSignal
from qfluentwidgets import (qconfig, QConfig, ConfigItem, OptionsConfigItem, BoolValidator,
                            OptionsValidator, RangeConfigItem, RangeValidator,
                            FolderListValidator, Theme, FolderValidator, ConfigSerializer, __version__)
from qfluentwidgets.common.config import EnumSerializer


class Language(Enum):
    """ Language enumeration """

    CHINESE_SIMPLIFIED = QLocale(QLocale.Language.Chinese, QLocale.Country.China)
    CHINESE_TRADITIONAL = QLocale(QLocale.Language.Chinese, QLocale.Country.HongKong)
    ENGLISH = QLocale(QLocale.Language.English)
    AUTO = QLocale()


class LanguageSerializer(ConfigSerializer):
    """ Language serializer """

    def serialize(self, language):
        return language.value.name() if language != Language.AUTO else "Auto"

    def deserialize(self, value: str):
        return Language(QLocale(value)) if value != "Auto" else Language.AUTO


def isWin11():
    return sys.platform == 'win32' and sys.getwindowsversion().build >= 22000


class Config(QConfig):
    """ Config of application """

    # signals
    useLocalDataChanged = pyqtSignal(bool)

    # folders
    musicFolders = ConfigItem(
        "Folders", "LocalMusic", [], FolderListValidator())
    downloadFolder = ConfigItem(
        "Folders", "Download", "app/download", FolderValidator())

    # main window
    micaEnabled = ConfigItem("MainWindow", "MicaEnabled", isWin11(), BoolValidator())
    dpiScale = OptionsConfigItem(
        "MainWindow", "DpiScale", "Auto", OptionsValidator([1, 1.25, 1.5, 1.75, 2, "Auto"]), restart=True)
    language = OptionsConfigItem(
        "MainWindow", "Language", Language.AUTO, OptionsValidator(Language), LanguageSerializer(), restart=True)

    # Material
    blurRadius  = RangeConfigItem("Material", "AcrylicBlurRadius", 15, RangeValidator(0, 40))

    # software update
    checkUpdateAtStartUp = ConfigItem("Update", "CheckUpdateAtStartUp", True, BoolValidator())

    # data setting
    useLocalData = ConfigItem("Data", "UseLocalData", True, BoolValidator())
    
    # 股票服务器记录
    stockServerHost = ConfigItem("Stock", "ServerHost", "")
    stockServerPort = ConfigItem("Stock", "ServerPort", 7709)

    # 期货登录账号（初始为空）
    futuresUsername = ConfigItem("Futures", "Username", "")
    futuresPassword = ConfigItem("Futures", "Password", "")
    futuresRememberPassword = ConfigItem("Futures", "RememberPassword", False, BoolValidator())

    # 仅用于保存主题偏好到文件，不触发即时切换
    # (与 qconfig.themeMode 同 group/name 但不同对象，QConfig.set 的 is 判断会跳过主题切换)
    pendingThemeMode = OptionsConfigItem(
        "QFluentWidgets", "ThemeMode", Theme.LIGHT, OptionsValidator(Theme), EnumSerializer(Theme))


YEAR = 2025
AUTHOR = "minibt"
VERSION = __version__
HELP_URL = "https://www.minibt.cn"
REPO_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets"
EXAMPLE_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets/tree/PyQt6/examples"
FEEDBACK_URL = "https://github.com/minibt/minibt/issues"
RELEASE_URL = "https://github.com/zhiyiYo/PyQt-Fluent-Widgets/releases/latest"
ZH_SUPPORT_URL = "https://qfluentwidgets.com/zh/price/"
EN_SUPPORT_URL = "https://qfluentwidgets.com/price/"


cfg = Config()
cfg.themeMode.value = Theme.LIGHT
qconfig.load('app/config/config.json', cfg)
# 同步 pendingThemeMode 的初始值（用于设置界面显示，不触发即时切换）
cfg.pendingThemeMode.value = cfg.themeMode.value