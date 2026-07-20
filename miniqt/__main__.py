# coding:utf-8
import os
import sys
import warnings
# import asyncio
import contextlib
import click
from io import StringIO


def start_qt_application():
    """启动Qt应用程序的核心逻辑，返回退出码"""
    

    # 过滤 QFont 警告
    warnings.filterwarnings("ignore", message="QFont::setPointSize: Point size <= 0 (-1), must be greater than 0")

    # 导入阶段：捕获 TqSdk 等第三方库的冗余日志，避免污染启动输出
    f = StringIO()
    with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        from PyQt6.QtCore import Qt, QTranslator, qInstallMessageHandler, QtMsgType
        from PyQt6.QtGui import QFont  # noqa: F401
        from PyQt6.QtWidgets import QApplication
        from qfluentwidgets import FluentTranslator

        # 优先使用本地 minibt（而非 pip 安装的旧版本）
        _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)

        from miniqt.app.common.config import cfg
        from miniqt.app.view.main_window import MainWindow

    # 自定义消息处理器来过滤 QFont 等无关警告
    def qt_message_handler(msg_type, context, message):
        if "QFont::setPointSize" in message:
            return
        if "UpdateLayeredWindowIndirect" in message:
            return
        if "QBackingStore::endPaint()" in message:
            return
        # QPaintDevice 警告：WebView 销毁时 GPU 渲染管线竞态，不影响功能
        if "Cannot destroy paint device" in message:
            return
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

    # 忽略 QWebEngine SSL 证书警告
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--ignore-certificate-errors'

    # create application
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    # 集成 qasync 事件循环（支持 asyncSlot 装饰器）
    # 禁用：qasync 与天勤 wait_update 冲突
    # event_loop = None
    # try:
    #     from qasync import QEventLoop
    #     event_loop = QEventLoop(app)
    #     asyncio.set_event_loop(event_loop)
    #     # print("qasync 事件循环已集成")
    # except ImportError:
    #     print("qasync 未安装，使用默认事件循环")
    #     event_loop = None

    # internationalization
    locale = cfg.get(cfg.language).value
    translator = FluentTranslator(locale)
    galleryTranslator = QTranslator()
    galleryTranslator.load(locale, "gallery", ".", ":/gallery/i18n")

    # # PyQt6 兼容：FluentTranslator 可能不是 QTranslator 子类
    try:
        app.installTranslator(translator)
    except TypeError:
        try:
            translator.apply(app)
        except AttributeError:
            pass  # 降级：跳过翻译器安装
    app.installTranslator(galleryTranslator)

    # disable mica effect to avoid style issues
    cfg.set(cfg.micaEnabled, False)

    # create main window
    w = MainWindow()
    w.show()

    # 运行应用
    # if event_loop:
    #     with event_loop:
    #         event_loop.run_forever()
    #     return 0
    # else:
    return app.exec()


@click.group(invoke_without_command=True)
@click.option('--debug', is_flag=True, help='调试模式')
@click.pass_context
def cli(ctx, debug):
    """miniqt - 量化交易可视化界面"""
    if ctx.invoked_subcommand is None:
        # 无子命令时默认执行 run
        if debug:
            print("[DEBUG] 调试模式")
        print("启动miniqt界面...")
        exit_code = start_qt_application()
        sys.exit(exit_code)


@cli.command()
@click.option('--debug', is_flag=True, help='调试模式')
def run(debug):
    """启动miniqt图形界面"""
    if debug:
        print("🔧 调试模式")
    print("🚀 启动miniqt界面...")
    exit_code = start_qt_application()
    sys.exit(exit_code)


@cli.command()
def version():
    """显示版本信息"""
    try:
        from miniqt import __version__
        print(f"miniqt version {__version__}")
    except ImportError:
        print("miniqt version unknown")


if __name__ == "__main__":
    cli()
