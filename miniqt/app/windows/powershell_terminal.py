
from PyQt6.QtCore import QTimer, pyqtSignal, QThread
import os
import sys
import time
if sys.platform == 'win32':
    from winpty import PtyProcess
else:
    import pty

from .terminal_base import Terminal


class LocalTerm(Terminal):
    """ 本地程序终端 """

    # 执行完成信号，参数为 (file_path, output)
    finishedSignal = pyqtSignal(str, str)
    
    # 主题配色方案名称
    LIGHT_THEME = "Homebrew Light"
    DARK_THEME = "Horizon Dark"

    def __init__(self, parent=None, bg_img=None, scheme=None, is_dark_theme: bool = True):
        # 根据主题选择配色方案
        if scheme is None:
            scheme = self.DARK_THEME if is_dark_theme else self.LIGHT_THEME
        
        super().__init__(parent, bg_img, scheme)
        self._is_dark_theme = is_dark_theme
        self.adjustSize()
        prog = "powershell" if sys.platform == "win32" else "bash"
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timerCallback)
        
        # 缓冲区，用于收集输出
        self._output_buffer = ""
        self._last_command = ""
        
        # 用于确认命令真正执行完成的计数器
        self._prompt_seen_count = 0
        self._pending_command = ""

        try:
            if sys.platform == 'win32':
                # Windows 使用 winpty
                self.proc = PtyProcess.spawn(prog, backend=1)
                self.proc.fileobj.setblocking(False)
            else:
                # Unix 使用 pty.fork
                pid, fd = pty.fork()
                if pid == 0:
                    # 子进程执行目标程序
                    os.execvp(prog, [prog])
                else:
                    # 父进程保存 fd
                    self.proc_pid = pid
                    self.proc_fd = fd

            self.timer.start(10)
        except Exception as e:
            self.display(f"Exception: {e}\n")

    def close(self):
        if sys.platform == 'win32':
            self.proc.close(force=True)
        else:
            try:
                os.close(self.proc_fd)
            except Exception:
                pass
        super().close()

    def sendData(self, data: str):
        if sys.platform == 'win32':
            self.proc.write(data)
        else:
            os.write(self.proc_fd, data.encode())
        
        # 记录发送的命令（非回车命令才记录）
        if '\r' in data or '\n' in data:
            self._last_command = data.strip()
            self._output_buffer = ""

    def timerCallback(self):
        data = ''
        try:
            if sys.platform == 'win32':
                data = self.proc.read()
            else:
                # 非阻塞读取伪终端输出
                import select
                r, _, _ = select.select([self.proc_fd], [], [], 0)
                if r:
                    data = os.read(self.proc_fd, 1024).decode(errors="ignore")
        except Exception:
            pass

        if data:
            self.display(data)
            self._output_buffer += data
            
            # 检测命令执行完成（PowerShell prompt 模式）
            # 检测 PS C:\...> 或 PS ...> 格式
            import re
            prompt_pattern = r'PS\s+[A-Za-z]:[\\/][^>]*>'
            has_prompt = re.search(prompt_pattern, data)
            
            if has_prompt:
                if self._last_command:
                    # 第一次检测到 prompt，记录待处理命令，等待确认
                    self._pending_command = self._last_command
                    self._last_command = ""
                    self._prompt_seen_count = 1
                elif self._pending_command:
                    # 第二次检测到 prompt，确认命令真正执行完成
                    self._prompt_seen_count += 1
                    if self._prompt_seen_count >= 2:
                        # 命令执行完成，发射信号
                        self.finishedSignal.emit(self._pending_command, self._output_buffer)
                        self._pending_command = ""
                        self._output_buffer = ""
                        self._prompt_seen_count = 0
            
            self.timer.start(0)
        else:
            # 无数据时，检查是否有待确认的 pending 命令
            if self._pending_command and self._prompt_seen_count >= 1:
                # 如果已经检测到一次 prompt 且后续无输出，说明命令已完成
                self.finishedSignal.emit(self._pending_command, self._output_buffer)
                self._pending_command = ""
                self._output_buffer = ""
                self._prompt_seen_count = 0
            self.timer.start(10)

    def setTheme(self, is_dark: bool):
        """设置终端主题
        
        Args:
            is_dark: True 为深色主题，False 为浅色主题
        """
        self._is_dark_theme = is_dark
        scheme = self.DARK_THEME if is_dark else self.LIGHT_THEME
        from .util import Color
        self.scheme = Color().getScheme(scheme)
        
        # 更新调色板
        from PyQt6.QtGui import QPalette, QColor
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(self.scheme['Background']))
        base_color = QColor(self.scheme['Background'])
        if self.bg_img:
            base_color.setAlpha(20)
        palette.setColor(QPalette.ColorRole.Base, base_color)
        palette.setColor(QPalette.ColorRole.Text, QColor(self.scheme['Foreground']))
        self.setPalette(palette)

    @property
    def is_dark_theme(self) -> bool:
        """获取当前是否为深色主题"""
        return self._is_dark_theme

    def write_msg(self, msg: str):
        """向终端发送一条消息

        Args:
            msg: 要显示的文本消息
        """
        self.display(msg + '\n')


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication()

    # Windows 下用 powershell，Linux/macOS 下用 bash
    #prog = "powershell" if sys.platform == "win32" else "bash"
    term = LocalTerm()
    term.show()

    app.exec()
