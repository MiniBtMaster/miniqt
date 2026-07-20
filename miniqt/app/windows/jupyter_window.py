# coding:utf-8
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QProcess
# 关键导入：引入 Jupyter Qt Console 的核心部件
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager


class JupyterWindow(QWidget):
    """ 基于 Jupyter Qt Console 的终端窗口 """

    def __init__(self, parent=None, is_dark_theme: bool = True):
        super().__init__(parent=parent)
        self.setObjectName("JupyterWindow")
        self._is_dark_theme = is_dark_theme

        # 创建主布局
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)

        # 1. 创建 Jupyter 内核管理器
        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel()
        # 获取内核客户端，用于后续通信
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()

        # 2. 创建并配置 Jupyter Widget
        self.jupyter_widget = RichJupyterWidget(self)
        # 重要：将内核客户端连接到 widget
        self.jupyter_widget.kernel_manager = self.kernel_manager
        self.jupyter_widget.kernel_client = self.kernel_client
        # 根据当前主题设置初始样式
        colors = 'linux' if is_dark_theme else 'lightbg'
        self.jupyter_widget.set_default_style(colors=colors)

        # 3. 将 Jupyter Widget 添加到布局中
        self.mainLayout.addWidget(self.jupyter_widget)

        # 初始化问候语（可选）
        self.jupyter_widget._append_plain_text("欢迎使用嵌入的 Jupyter 控制台！\n", before_prompt=True)
        self.jupyter_widget._append_plain_text("=" * 50 + "\n", before_prompt=True)

        # 设置初始工作目录
        self.set_initial_working_directory()

    def set_initial_working_directory(self):
        """ 设置内核的初始工作目录为当前应用目录 """
        current_dir = os.getcwd()
        # 通过内核执行 Python 命令来改变工作目录
        self.kernel_client.execute(f"import os; os.chdir(r'{current_dir}')")

    def change_style(self, dark_mode=True):
        """ 改变 Jupyter 控制台的样式

        参数
        ----------
        dark_mode : bool
            True 为深色主题，False 为浅色主题
        """
        colors = 'linux' if dark_mode else 'lightbg'
        self.jupyter_widget.set_default_style(colors=colors)

    def setTheme(self, dark):
        """ 改变 Jupyter 控制台的样式 """
        self.change_style(dark)

    def _close(self):
        """ 关闭 Jupyter 控制台 """
        if self.kernel_client:
            self.kernel_client.stop_channels()
        if self.kernel_manager:
            self.kernel_manager.shutdown_kernel()

    # 重要：析构时需要正确关闭内核和客户端
    def closeEvent(self, event):
        """ 窗口关闭时清理内核进程 """
        self._close()
        event.accept()
