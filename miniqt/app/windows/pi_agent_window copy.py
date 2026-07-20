# coding:utf-8
"""
Pi Agent 窗口：嵌入 pi-agent-web 的 PyQt6 窗口
打开窗口即自动启动服务并加载页面
"""

import subprocess
import sys
import time
import os
import urllib.request
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

# pi-agent-web 默认端口
PI_WEB_PORT = 30141
PI_WEB_URL = f"http://127.0.0.1:{PI_WEB_PORT}"


class PiServiceManager:
    """管理 pi-agent-web 后台进程生命周期"""

    def __init__(self):
        self._pi_web_proc: Optional[subprocess.Popen] = None
        self._ready = False

    @staticmethod
    def find_local_pi_web() -> Optional[str]:
        """查找本地 pi-angent-web 源码目录"""
        candidates = [
            Path(__file__).parent.parent / "pi-angent-web",
            Path.cwd() / "miniqt" / "app" / "pi-angent-web",
            Path.cwd() / "pi-angent-web",
        ]
        for p in candidates:
            if p.is_dir() and (p / "package.json").is_file():
                return str(p.resolve())
        return None

    def check_dependencies(self) -> tuple:
        """检查依赖环境，返回 (ok, message)"""
        # 检查 Node.js
        node_path = None
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            node_exe = os.path.join(path_dir, "node.exe" if sys.platform == "win32" else "node")
            if os.path.isfile(node_exe):
                node_path = node_exe
                break
        if not node_path:
            return False, "未安装 Node.js，请先安装 Node.js (https://nodejs.org/)"

        # 检查 pi-angent-web 目录
        local_dir = self.find_local_pi_web()
        if not local_dir:
            return False, "未找到 pi-angent-web 源码目录"

        # 检查 node_modules
        node_modules = os.path.join(local_dir, "node_modules")
        if not os.path.isdir(node_modules):
            return False, "pi-angent-web 依赖未安装，请执行:\ncd miniqt/app/pi-angent-web && npm install"

        return True, local_dir

    def start(self) -> tuple:
        """
        启动 pi-agent-web 服务（非阻塞，立即返回）
        返回 (True, local_dir) 或 (False, error_msg)
        """
        local_dir = self.find_local_pi_web()
        if not local_dir:
            return False, "未找到 pi-angent-web 源码目录"

        # 启动前清理端口
        self._kill_port_process()

        node_modules = os.path.join(local_dir, "node_modules")
        if not os.path.isdir(node_modules):
            return False, "pi-angent-web 依赖未安装"

        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

            # 设置嵌入模式环境变量，跳过 Maddie 登录认证
            env = os.environ.copy()
            env["NEXT_PUBLIC_EMBEDDED"] = "true"

            self._pi_web_proc = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=local_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True if sys.platform == "win32" else False,
                creationflags=creationflags,
                env=env,
            )
            print(f"[PiService] pi-agent-web 已启动, PID={self._pi_web_proc.pid}")
            self._start_time = time.time()
            return True, local_dir

        except Exception as e:
            return False, f"启动失败: {e}"

    def is_ready(self) -> bool:
        """检查 HTTP 服务是否就绪"""
        try:
            req = urllib.request.Request(PI_WEB_URL, method="HEAD")
            urllib.request.urlopen(req, timeout=2)
            self._ready = True
            return True
        except Exception:
            return False

    def stop(self):
        """停止服务"""
        self._ready = False

        if self._pi_web_proc is not None and self._pi_web_proc.poll() is None:
            try:
                self._pi_web_proc.terminate()
                self._pi_web_proc.wait(timeout=5)
                print("[PiService] pi-agent-web 已停止")
            except Exception:
                try:
                    self._pi_web_proc.kill()
                except Exception:
                    pass
        self._pi_web_proc = None

        # 确保端口释放
        self._kill_port_process()

    def _kill_port_process(self):
        """杀死占用端口的进程（Windows）"""
        if sys.platform != "win32":
            return
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                encoding="gbk",
                errors="replace",
            )
            for line in result.stdout.splitlines():
                if f":{PI_WEB_PORT}" in line and "LISTENING" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        print(f"[PiService] 杀死占用端口 {PI_WEB_PORT} 的进程 PID={pid}")
                        subprocess.run(
                            ["taskkill", "/PID", pid, "/F"],
                            capture_output=True,
                            check=False,
                        )
        except Exception as e:
            print(f"[PiService] 清理端口失败: {e}")

    @property
    def url(self) -> str:
        return PI_WEB_URL


class PiAgentWindow(QWidget):
    """Pi Agent 窗口：打开即自动启动服务并加载页面"""

    service_started = pyqtSignal(bool)

    def __init__(self, parent=None, auto_start=True):
        super().__init__(parent=parent)
        self._service = PiServiceManager()
        self._poll_timer: Optional[QTimer] = None
        self._retry_count = 0
        self._max_retries = 60
        self._load_retry_count = 0
        self._max_load_retries = 5
        self._init_ui()

        # 打开窗口即自动启动
        if auto_start:
            QTimer.singleShot(100, self._auto_start)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # WebView
        self.web_view = QWebEngineView(self)
        self.web_view.loadFinished.connect(self._on_load_finished)
        layout.addWidget(self.web_view)

        # 加载提示（居中覆盖层）
        self._loading_label = QLabel("正在启动 Pi Agent 服务...", self)
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setFont(QFont("Microsoft YaHei", 14))
        self._loading_label.setStyleSheet(
            "background: rgba(30, 30, 30, 230); color: #CCCCCC; border-radius: 8px; padding: 20px;"
        )
        self._loading_label.setFixedSize(400, 120)
        self._loading_label.hide()

    def _auto_start(self):
        """自动启动服务"""
        self.start()

    def start(self):
        """手动启动服务（公开方法）"""
        # 防止重复启动
        if self._poll_timer is not None and self._poll_timer.isActive():
            return
        if self._service._pi_web_proc is not None and self._service._pi_web_proc.poll() is None:
            return

        # 1. 检查环境
        ok, msg = self._service.check_dependencies()
        if not ok:
            self._loading_label.setText(f"环境错误\n{msg}")
            self._loading_label.show()
            self._center_loading()
            return

        print(f"[PiAgent] 环境检查通过: {msg}")

        # 2. 显示加载提示
        self._loading_label.setText("正在启动 Pi Agent 服务...\n首次启动可能需要 10-30 秒")
        self._loading_label.show()
        self._center_loading()

        # 3. 启动服务（非阻塞）
        ok, msg = self._service.start()
        if not ok:
            self._loading_label.setText(f"启动失败\n{msg}")
            self._center_loading()
            return

        print(f"[PiAgent] pi-agent-web 进程已启动: {msg}")

        # 4. 用 QTimer 轮询等待服务就绪
        self._retry_count = 0
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_ready)
        self._poll_timer.start(1000)  # 每秒轮询一次

    def _poll_ready(self):
        """轮询检查 HTTP 服务是否就绪"""
        self._retry_count += 1

        if self._service.is_ready():
            self._poll_timer.stop()
            print(f"[PiAgent] pi-agent-web 已就绪: {PI_WEB_URL}")
            self._loading_label.setText("服务已启动，正在加载页面...")
            self._center_loading()
            # 稍等一会儿确保服务完全稳定
            QTimer.singleShot(500, self._load_url)
            return

        # 超时
        if self._retry_count >= self._max_retries:
            self._poll_timer.stop()
            self._loading_label.setText(
                f"服务启动超时 ({self._max_retries}秒)\n请检查 pi-agent-web 是否正常运行"
            )
            self._center_loading()
            print(f"[PiAgent] 服务启动超时 ({self._max_retries}秒)")
            return

        # 更新进度提示
        self._loading_label.setText(
            f"正在启动 Pi Agent 服务...\n等待服务就绪 ({self._retry_count}s)"
        )
        self._center_loading()

    def _load_url(self):
        """加载 URL"""
        self._load_retry_count = 0
        print(f"[PiAgent] 加载 URL: {PI_WEB_URL}")
        self.web_view.setUrl(QUrl(PI_WEB_URL))

    def _on_load_finished(self, success: bool):
        """页面加载完成"""
        print(f"[PiAgent] loadFinished: success={success}, url={self.web_view.url().toString()}")
        if success:
            self._loading_label.hide()
            self.service_started.emit(True)
            print(f"[PiAgent] 页面加载成功: {PI_WEB_URL}")
        else:
            self._load_retry_count += 1
            if self._load_retry_count < self._max_load_retries:
                print(f"[PiAgent] 页面加载失败，重试 {self._load_retry_count}/{self._max_load_retries}...")
                QTimer.singleShot(2000, self._load_url)
            else:
                self._loading_label.setText(f"页面加载失败 (已重试{self._max_load_retries}次)")
                self._center_loading()
                print(f"[PiAgent] 页面加载失败，已达最大重试次数")

    def _center_loading(self):
        """居中加载提示"""
        w, h = self.width(), self.height()
        lw, lh = self._loading_label.width(), self._loading_label.height()
        self._loading_label.move((w - lw) // 2, (h - lh) // 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._loading_label.isVisible():
            self._center_loading()

    def closeEvent(self, event):
        print("[PiAgent] 关闭窗口，停止服务...")
        self._service.stop()
        super().closeEvent(event)
