# coding:utf-8
import sys
import warnings
import asyncio

# 优先使用本地 minibt（而非 pip 安装的旧版本）
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 过滤 QFont 警告
warnings.filterwarnings("ignore", message="QFont::setPointSize: Point size <= 0 (-1), must be greater than 0")

from PyQt6.QtCore import Qt, QTranslator, qInstallMessageHandler, QtMsgType
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import FluentTranslator

from app.common.config import cfg
from app.view.main_window import MainWindow


# 自定义消息处理器来过滤 QFont 等无关警告
def qt_message_handler(msg_type, context, message):
    if "QFont::setPointSize" in message:
        return
    if "Warning: UpdateLayeredWindowIndirect" in message:
        return
    # 其他消息正常输出
    if msg_type == QtMsgType.QtDebugMsg:
        print(f"Debug: {message}")
    elif msg_type == QtMsgType.QtInfoMsg:
        print(f"Info: {message}")
    elif msg_type == QtMsgType.QtWarningMsg:
        print(f"Warning: {message}")
    elif msg_type == QtMsgType.QtCriticalMsg:
        print(f"Critical: {message}")
    elif msg_type == QtMsgType.QtFatalMsg:
        print(f"Fatal: {message}")


# 安装 Qt 消息处理器
qInstallMessageHandler(qt_message_handler)


# enable dpi scale
if cfg.get(cfg.dpiScale) != "Auto":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    os.environ["QT_SCALE_FACTOR"] = str(cfg.get(cfg.dpiScale))

# create application
app = QApplication(sys.argv)
app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

# 集成 qasync 事件循环（支持 asyncSlot 装饰器）
try:
    from qasync import QEventLoop
    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)
    print("qasync 事件循环已集成")
except ImportError:
    print("qasync 未安装，使用默认事件循环")
    event_loop = None

# internationalization
locale = cfg.get(cfg.language).value
translator = FluentTranslator(locale)
galleryTranslator = QTranslator()
galleryTranslator.load(locale, "gallery", ".", ":/gallery/i18n")

app.installTranslator(translator)
app.installTranslator(galleryTranslator)

# disable mica effect to avoid style issues
cfg.set(cfg.micaEnabled, False)

# create main window
w = MainWindow()
w.show()

# 运行应用
if event_loop:
    with event_loop:
        event_loop.run_forever()
else:
    app.exec()