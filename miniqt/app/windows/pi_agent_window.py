# coding:utf-8
"""
Pi Agent 窗口：嵌入 pi-agent-web 的 PyQt6 窗口
打开窗口即自动启动服务并加载页面
"""

import subprocess
import sys
import os
import shutil
import json as json_lib
import urllib.request
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFileDialog
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QFont

from qfluentwidgets import RoundMenu, Action, FluentIcon

from ..common.pi_service import (
    get_pi_service, PiServiceManager, PI_WEB_URL, PI_WEB_PORT,
)


class _PiAgentWebPage(QWebEnginePage):
    """自定义 WebPage，拦截 console.log 消息以处理文件打开请求"""

    def __init__(self, pi_agent_window, parent=None):
        super().__init__(parent)
        self._pi_agent_window = pi_agent_window

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        """重写此方法拦截 console.log 消息"""
        if message.startswith("__PI_OPEN_FILE__:"):
            try:
                data = json_lib.loads(message[len("__PI_OPEN_FILE__:"):])
                file_path = data.get("path", "")
                file_name = data.get("name", "")
                if file_path and file_name:
                    self._pi_agent_window.open_file_requested.emit(file_path, file_name)
            except Exception:
                pass
        elif message.startswith("__PI_REFRESH_FILES__"):
            self._pi_agent_window.refresh_file_tree_requested.emit()
        elif message.startswith("__PI_SYNC_FOLDER__:"):
            try:
                data = json_lib.loads(message[len("__PI_SYNC_FOLDER__:"):])
                cwd = data.get("cwd", "")
                if cwd and os.path.isdir(cwd):
                    self._pi_agent_window.sync_folder_requested.emit(cwd)
            except Exception:
                pass
        elif message.startswith("__PI_FILE_CHANGED__:"):
            try:
                data = json_lib.loads(message[len("__PI_FILE_CHANGED__:"):])
                paths = data.get("paths", [])
                if paths:
                    self._pi_agent_window.file_changed_requested.emit(paths)
            except Exception:
                pass
        elif message.startswith("__PI_RUN_BACKTEST__:"):
            try:
                data = json_lib.loads(message[len("__PI_RUN_BACKTEST__:"):])
                path = data.get("path", "")
                if path:
                    self._pi_agent_window.run_backtest_requested.emit(path)
            except Exception:
                pass
        elif message.startswith("__PI_AGENT_DONE__"):
            self._pi_agent_window.agent_done.emit()

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        """拦截导航请求"""
        return True


class PiAgentWindow(QWidget):
    """Pi Agent 窗口：打开即自动启动服务并加载页面"""

    service_started = pyqtSignal(bool)
    agent_done = pyqtSignal()      # agent 处理完成
    open_file_requested = pyqtSignal(str, str)  # (file_path, file_name)
    refresh_file_tree_requested = pyqtSignal()  # 文件树刷新请求
    sync_folder_requested = pyqtSignal(str)  # 同步文件夹请求 (cwd)
    file_changed_requested = pyqtSignal(list)  # 文件写入/编辑请求 (paths)
    run_backtest_requested = pyqtSignal(str)  # 运行回测请求 (file_path)

    def __init__(self, parent=None, auto_start=True):
        super().__init__(parent=parent)
        self._service = get_pi_service()
        self._poll_timer: Optional[QTimer] = None
        self._retry_count = 0
        self._max_retries = 60
        self._load_retry_count = 0
        self._max_load_retries = 5
        self._page_loaded = False
        self._init_ui()

        # 打开窗口即自动启动
        if auto_start:
            QTimer.singleShot(100, self._auto_start)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 自定义 QWebEnginePage 拦截 console.log 消息
        self._pi_page = _PiAgentWebPage(self)

        # WebView
        self.web_view = QWebEngineView(self)
        self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.web_view.customContextMenuRequested.connect(self._on_context_menu)
        self.web_view.setPage(self._pi_page)
        self.web_view.loadFinished.connect(self._on_load_finished)
        layout.addWidget(self.web_view)

        # 加载提示（覆盖层，大小与 web_view 一致）
        self._loading_label = QLabel("正在启动 Pi Agent 服务...", self)
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._loading_label.setFont(QFont("Microsoft YaHei", 14))
        self._apply_loading_theme()
        self._loading_label.hide()

    def _apply_loading_theme(self):
        """根据当前主题设置 PiAgentWindow 背景和加载提示样式"""
        from qfluentwidgets import isDarkTheme
        if isDarkTheme():
            self.setStyleSheet("background: #1E1E1E;")
            self._loading_label.setStyleSheet(
                "background: rgba(30, 30, 30, 230); color: #CCCCCC; border-radius: 8px; padding: 20px;"
            )
        else:
            self.setStyleSheet("background: #FFFFFF;")
            self._loading_label.setStyleSheet(
                "background: rgba(255, 255, 255, 230); color: #333333; border-radius: 8px; padding: 20px; border: 1px solid #E0E0E0;"
            )

    def _auto_start(self):
        """自动启动服务"""
        self.start()

    # ── 错误码 → 用户提示文字 ──

    _ERROR_MESSAGES = {
        "NOT_FOUND_NODE": "未安装 Node.js，请先安装 Node.js\n下载地址: https://nodejs.org/",
        "NOT_FOUND": "未找到 pi-agent-web 目录\n请参考帮助文档配置环境\n（F1 → Pi Agent 环境配置）",
        "NEEDS_INSTALL": "",  # 动态填充，含实际路径
    }

    @classmethod
    def _needs_install_msg(cls, pi_web_dir: str) -> str:
        """生成"需要 npm install"的提示信息（含实际路径）"""
        return (
            f"pi-agent-web 依赖未安装\n\n"
            f"源码目录:\n  {pi_web_dir}\n\n"
            f"请在终端执行:\n\n"
            f"  CMD:\n"
            f"    cd /d \"{pi_web_dir}\" && npm install\n\n"
            f"  PowerShell:\n"
            f"    cd \"{pi_web_dir}\"; npm install"
        )

    @classmethod
    def get_setup_guide(cls) -> str:
        """获取 pi-agent-web 环境配置指引（帮助文档）"""
        # 检测 pi-angent-web 目录路径
        pi_web_dir = PiServiceManager.find_pi_web_dir()
        dir_info = pi_web_dir if pi_web_dir else "未找到（请检查 miniqt 安装）"

        guide = (
            "══════════════════════════════════════════\n"
            "   Pi Agent Web 环境配置指引\n"
            "══════════════════════════════════════════\n\n"
            "pi-agent-web 是 miniqt 内置的 Next.js Web 应用，\n"
            "已包含 pi coding agent（无需额外安装 pi）。\n"
            "源码位于 miniqt/app/pi-angent-web/ 目录，\n"
            "miniqt 通过内嵌浏览器加载其 Web 界面。\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  前置依赖\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  ● Node.js (>= 18)\n"
            "    下载: https://nodejs.org/\n"
            "    验证: node --version\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  安装步骤\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  无论 dev 模式还是 pip 模式，步骤相同：\n\n"
            "    1. 找到 pi-angent-web 目录\n"
            f"       当前: {dir_info}\n\n"
            "    2. 安装 npm 依赖\n"
            f"       CMD:\n"
            f"         cd /d \"{dir_info}\" && npm install\n"
            f"       PowerShell:\n"
            f"         cd \"{dir_info}\"; npm install\n\n"
            "    3. 启动 miniqt，打开 Pi Agent 窗口即可\n\n"
            "  ── 补充说明 ──\n"
            "  ● 开发模式 (git clone):\n"
            "    源码在 miniqt/app/pi-angent-web/\n\n"
            "  ● pip 安装模式 (pip install miniqt):\n"
            "    源码在 site-packages/miniqt/app/pi-angent-web/\n"
            "    可通过以下命令找到:\n"
            "      python -c \"import miniqt,os; "
            "print(os.path.dirname(miniqt.__file__))\"\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  当前环境检测结果\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        status = cls._detect_current_status()
        return guide + status

    @staticmethod
    def _detect_current_status() -> str:
        """检测当前环境并生成状态报告"""
        lines = []
        mgr = get_pi_service()

        # Node.js
        node = shutil.which("node.exe" if sys.platform == "win32" else "node")
        lines.append(f"  Node.js:    {'已安装' if node else '未安装'}")
        if node:
            try:
                result = subprocess.run(
                    [node, "--version"], capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                lines.append(f"              {result.stdout.strip()}")
            except Exception:
                pass

        # npm
        npm = shutil.which("npm")
        lines.append(f"  npm:        {'已安装' if npm else '未安装'}")
        if npm:
            try:
                result = subprocess.run(
                    [npm, "--version"], capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                lines.append(f"              v{result.stdout.strip()}")
            except Exception:
                pass

        # pi-angent-web 目录
        pi_web_dir = mgr.find_pi_web_dir()
        if pi_web_dir:
            lines.append(f"\n  pi-angent-web: {pi_web_dir}")
            node_modules = os.path.join(pi_web_dir, "node_modules")
            if os.path.isdir(node_modules):
                lines.append("  node_modules:  已安装 ✓")
            else:
                lines.append("  node_modules:  未安装 ✗（请执行 npm install）")
        else:
            lines.append("\n  pi-angent-web: 未找到 ✗")

        # 判断安装模式
        try:
            import miniqt as _pkg
            pkg_dir = Path(_pkg.__file__).parent
            is_pip = "site-packages" in str(pkg_dir)
            lines.append(f"\n  安装模式:    {'pip 安装' if is_pip else '开发模式'}")
        except Exception:
            lines.append("\n  安装模式:    未知")

        lines.append("\n  Pi Agent 是 pi-angent-web 的内置功能")
        lines.append("  不需要额外安装 pi")
        return "\n".join(lines)

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
            # 翻译错误码为用户提示
            if msg == "NEEDS_INSTALL" and self._service._pi_web_dir:
                err_msg = self._needs_install_msg(self._service._pi_web_dir)
            else:
                err_msg = self._ERROR_MESSAGES.get(msg, f"环境错误: {msg}")
            self._loading_label.setText(err_msg)
            self._loading_label.show()
            self._center_loading()
            return

        print(f"[PiAgent] 环境检查通过: {msg}")

        # 2. 显示加载提示
        self._apply_loading_theme()
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
        """加载 URL，通过 URL 参数传递主题和嵌入式配置"""
        self._load_retry_count = 0
        from qfluentwidgets import isDarkTheme
        mode = "dark" if isDarkTheme() else "light"
        # sidebar=0: 默认隐藏左侧栏, auto_session=1: 自动打开最近会话
        url = f"{PI_WEB_URL}?theme={mode}&sidebar=0&auto_session=1"
        print(f"[PiAgent] 加载 URL: {url}")
        self.web_view.setUrl(QUrl(url))

    def _on_load_finished(self, success: bool):
        """页面加载完成"""
        print(f"[PiAgent] loadFinished: success={success}, url={self.web_view.url().toString()}")
        if success:
            self._page_loaded = True
            self._loading_label.hide()
            self.service_started.emit(True)
            self.sync_theme()  # 同步 miniqt 主题到 pi-web
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

    @property
    def is_page_loaded(self) -> bool:
        """页面是否已加载完成"""
        return self._page_loaded

    def set_pi_cwd(self, cwd: str):
        """将编辑器的工作目录反向同步到 pi-web 文件树"""
        escaped = cwd.replace("\\", "\\\\").replace("'", "\\'")
        js = f"if(window.__setPiCwd) window.__setPiCwd('{escaped}')"
        self.web_view.page().runJavaScript(js)

    def sync_theme(self):
        from qfluentwidgets import isDarkTheme
        mode = "dark" if isDarkTheme() else "light"
        # 优先使用 React 暴露的 setPiTheme，未挂载时直接操作 DOM
        js = f'''
        (function(){{
            if(window.__setPiTheme) {{
                window.__setPiTheme("{mode}");
            }} else {{
                var d = document.documentElement;
                if("{mode}" === "dark") d.classList.add("dark");
                else d.classList.remove("dark");
                try {{ localStorage.setItem("pi-theme", "{mode}"); }} catch(e) {{}}
            }}
        }})();
        '''
        self.web_view.page().runJavaScript(js)

    def _on_context_menu(self, pos):
        """右键菜单"""
        custom_menu = RoundMenu("", self.web_view)

        # 重新加载
        action_reload = Action("重新加载", parent=custom_menu)
        action_reload.setIcon(FluentIcon.UPDATE.icon())
        custom_menu.addAction(action_reload)

        # 会话列表子菜单
        self.session_menu = RoundMenu("会话列表", parent=custom_menu)
        self.session_menu.setIcon(FluentIcon.FLAG.icon())
        custom_menu.addMenu(self.session_menu)
        self._load_session_list()

        custom_menu.addSeparator()

        # 顶部栏按钮
        action_sidebar = Action("左侧栏", parent=custom_menu)
        action_sidebar.setIcon(FluentIcon.MENU.icon())

        action_branch = Action("会话内分支", parent=custom_menu)
        action_branch.setIcon(FluentIcon.SHARE.icon())

        action_system = Action("系统", parent=custom_menu)
        action_system.setIcon(FluentIcon.SETTING.icon())

        action_sync = Action("同步", parent=custom_menu)
        action_sync.setIcon(FluentIcon.SYNC.icon())

        custom_menu.addAction(action_sidebar)
        custom_menu.addAction(action_branch)
        custom_menu.addAction(action_system)
        custom_menu.addAction(action_sync)
        custom_menu.addSeparator()

        # 左侧栏菜单
        action_new_session = Action("新建会话", parent=custom_menu)
        action_new_session.setIcon(FluentIcon.ADD.icon())

        action_set_dir = Action("设置目录", parent=custom_menu)
        action_set_dir.setIcon(FluentIcon.FOLDER.icon())

        custom_menu.addAction(action_new_session)
        custom_menu.addAction(action_set_dir)
        custom_menu.addSeparator()

        # 模型 / 技能
        action_models = Action("模型", parent=custom_menu)
        action_models.setIcon(FluentIcon.ROBOT.icon())

        action_skills = Action("技能", parent=custom_menu)
        action_skills.setIcon(FluentIcon.CODE.icon())

        custom_menu.addAction(action_models)
        custom_menu.addAction(action_skills)

        # 绑定槽函数
        action_reload.triggered.connect(self._reload_service)
        action_sidebar.triggered.connect(
            lambda: self.web_view.page().runJavaScript("window.__togglePiSidebar && window.__togglePiSidebar()"))
        action_branch.triggered.connect(
            lambda: self.web_view.page().runJavaScript("window.__togglePiBranches && window.__togglePiBranches()"))
        action_system.triggered.connect(
            lambda: self.web_view.page().runJavaScript("window.__togglePiSystem && window.__togglePiSystem()"))
        action_sync.triggered.connect(
            lambda: self.web_view.page().runJavaScript("window.__piSyncFolder && window.__piSyncFolder()"))
        action_new_session.triggered.connect(
            lambda: self.web_view.page().runJavaScript("window.__piNewSession && window.__piNewSession()"))
        action_set_dir.triggered.connect(self._on_set_directory)
        action_models.triggered.connect(
            lambda: self.web_view.page().runJavaScript("window.__togglePiModels && window.__togglePiModels()"))
        action_skills.triggered.connect(
            lambda: self.web_view.page().runJavaScript("window.__togglePiSkills && window.__togglePiSkills()"))

        custom_menu.exec(self.web_view.mapToGlobal(pos + QPoint(0, 10)))

    def _on_set_directory(self):
        """选择工作目录并同步到 pi-web 和代码编辑器"""
        folder = QFileDialog.getExistingDirectory(self, "选择工作目录")
        if folder:
            self.set_pi_cwd(folder)
            # 同步代码编辑器的文件树
            self.sync_folder_requested.emit(folder)

    def _reload_service(self):
        """断开当前服务并重新启动 pi-agent-web"""
        print("[PiAgent] 正在重新加载服务...")
        self._loading_label.setText("正在重新启动 Pi Agent 服务...")
        self._apply_loading_theme()
        self._center_loading()
        self._loading_label.show()
        # 停止当前服务
        self._service.stop()
        # 重新启动
        QTimer.singleShot(500, self.start)

    def _load_session_list(self):
        """从 pi-web API 直接获取会话列表并构建子菜单（同步 HTTP 调用，避免 JS 异步回调问题）"""
        self.session_menu.clear()
        sessions = self._fetch_sessions_from_api()

        if not sessions:
            no_session = Action("无会话记录", parent=self.session_menu)
            no_session.setEnabled(False)
            self.session_menu.addAction(no_session)
            return

        for s in sessions:
            sid = s.get("id", "")
            name = s.get("name") or s.get("firstMessage") or f"会话 {sid[:8]}"
            msg_count = s.get("messageCount", 0)
            label = f"{name} ({msg_count} msgs)" if msg_count else name
            session_action = Action(label, parent=self.session_menu)
            session_action.triggered.connect(
                lambda checked, session_id=sid: self._load_session(session_id)
            )
            self.session_menu.addAction(session_action)

    def _fetch_sessions_from_api(self):
        """通过 HTTP 直接调用 /api/sessions 接口获取会话列表"""
        try:
            req = urllib.request.Request(f"{PI_WEB_URL}/api/sessions")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json_lib.loads(resp.read().decode("utf-8"))
                return data.get("sessions", [])
        except Exception as e:
            print(f"[PiAgent] 获取会话列表失败: {e}")
            return []

    def _on_session_list_received(self, sessions):
        """处理会话列表数据并创建菜单项"""
        self.session_menu.clear()

        if not sessions:
            no_session = Action("无会话记录", parent=self.session_menu)
            no_session.setEnabled(False)
            self.session_menu.addAction(no_session)
            return

        for s in sessions:
            sid = s.get("id", "")
            name = s.get("name", f"会话 {sid[:8]}")
            msg_count = s.get("messageCount", 0)
            label = f"{name} ({msg_count} msgs)" if msg_count else name
            session_action = Action(label, parent=self.session_menu)
            session_action.triggered.connect(
                lambda checked, session_id=sid: self._load_session(session_id)
            )
            self.session_menu.addAction(session_action)

    def _load_session(self, session_id):
        """加载指定会话到当前对话框"""
        session_id_escaped = session_id.replace("\\", "\\\\").replace("'", "\\'")
        self.web_view.page().runJavaScript(
            f"if(window.__loadPiSession) window.__loadPiSession('{session_id_escaped}')"
        )

    def _center_loading(self):
        """使加载提示覆盖层与 web_view 大小一致"""
        if hasattr(self, 'web_view'):
            self._loading_label.setGeometry(self.web_view.geometry())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._center_loading()

    def close(self):
        print("[PiAgent] 关闭窗口，停止服务...")
        self._service.stop()


# ── 模块级全局引用（供 QuickAIDialog 获取当前活跃的 PiAgentWindow） ──

_active_pi_agent: Optional[PiAgentWindow] = None


def get_active_pi_agent() -> Optional[PiAgentWindow]:
    """获取当前活跃的 PiAgentWindow 实例"""
    return _active_pi_agent


def set_active_pi_agent(window: PiAgentWindow):
    """设置当前活跃的 PiAgentWindow 实例"""
    global _active_pi_agent
    _active_pi_agent = window
