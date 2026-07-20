# coding:utf-8
# https://microsoft.github.io/monaco-editor/docs.html
from __future__ import annotations
import os,enum,subprocess,re,json,sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMenu, QSplitter, QTreeWidget, QTreeWidgetItem, QStackedWidget, QFrame, QHBoxLayout, QFileDialog, QInputDialog, QToolButton, QApplication, QPushButton, QTextEdit
from PyQt6.QtGui import QAction, QColor, QKeySequence, QShortcut, QKeyEvent, QCursor, QFont
from PyQt6.QtCore import QUrl, Qt, QFileInfo, QDir, pyqtSignal, QEvent, QTimer, QPoint
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile
from qfluentwidgets import (CommandBar, Action, FluentIcon as FIF, RoundMenu, TabBar, 
    TabCloseButtonDisplayMode, TreeWidget, isDarkTheme, MessageBox, InfoBar, InfoBarPosition,
    FluentIcon, TransparentDropDownPushButton)

import qtawesome as qta
from ..common.config import cfg
from ..common.data_config import data_cfg
from .chat_window import ChatWindow
from .quick_ai_dialog import QuickAIDialog
from typing import TYPE_CHECKING
from functools import partial
if TYPE_CHECKING:
    from ..view.main_window import MainWindow


# CodeEditorWindow 的状态文件路径
def get_editor_state_file():
    """获取编辑器状态文件路径"""
    # 优先使用用户配置目录
    config_dir = os.path.expanduser("~/.miniqt")
    if not os.path.exists(config_dir):
        # 回退到代码所在目录
        config_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(config_dir, "code_editor_state.json")


def get_monaco_language(file_path):
    """根据文件扩展名返回 Monaco Editor 语言标识符"""
    ext = os.path.splitext(file_path)[1].lower()
    lang_map = {
        '.py': 'python',
        '.pyw': 'python',
        '.js': 'javascript',
        '.mjs': 'javascript',
        '.cjs': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.jsx': 'javascript',
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.less': 'less',
        '.json': 'json',
        '.md': 'markdown',
        '.markdown': 'markdown',
        '.xml': 'xml',
        '.svg': 'xml',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.sh': 'shell',
        '.bash': 'shell',
        '.zsh': 'shell',
        '.bat': 'bat',
        '.cmd': 'bat',
        '.ps1': 'powershell',
        '.sql': 'sql',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.hxx': 'cpp',
        '.java': 'java',
        '.rs': 'rust',
        '.go': 'go',
        '.php': 'php',
        '.rb': 'ruby',
        '.r': 'r',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.kts': 'kotlin',
        '.cs': 'csharp',
        '.toml': 'ini',
        '.ini': 'ini',
        '.cfg': 'ini',
        '.conf': 'ini',
        '.dockerfile': 'dockerfile',
        '.gitignore': 'plaintext',
        '.env': 'plaintext',
        '.txt': 'plaintext',
        '.log': 'plaintext',
        '.csv': 'plaintext',
        '.lua': 'lua',
        '.pl': 'perl',
        '.pm': 'perl',
        '.dart': 'dart',
        '.vue': 'html',
        '.scala': 'scala',
        '.clj': 'clojure',
    }
    return lang_map.get(ext, 'plaintext')


# ── 文件图标映射 ──────────────────────────────────────────────
_FILE_ICON_MAP = {
    '.py': 'mdi6.language-python',
    '.pyw': 'mdi6.language-python',
    '.js': 'mdi6.language-javascript',
    '.mjs': 'mdi6.language-javascript',
    '.ts': 'mdi6.language-typescript',
    '.tsx': 'mdi6.language-typescript',
    '.jsx': 'mdi6.language-javascript',
    '.html': 'mdi6.language-html5',
    '.htm': 'mdi6.language-html5',
    '.css': 'mdi6.language-css3',
    '.scss': 'mdi6.language-css3',
    '.less': 'mdi6.language-css3',
    '.json': 'mdi6.code-json',
    '.md': 'mdi6.language-markdown',
    '.xml': 'mdi6.file-xml-box',
    '.yaml': 'mdi6.code-json',
    '.yml': 'mdi6.code-json',
    '.sql': 'mdi6.database',
    '.c': 'mdi6.language-c',
    '.cpp': 'mdi6.language-cpp',
    '.h': 'mdi6.language-c',
    '.hpp': 'mdi6.language-cpp',
    '.java': 'mdi6.language-java',
    '.go': 'mdi6.language-go',
    '.rs': 'mdi6.language-rust',
    '.php': 'mdi6.language-php',
    '.rb': 'mdi6.language-ruby',
    '.swift': 'mdi6.language-swift',
    '.kt': 'mdi6.language-kotlin',
    '.cs': 'mdi6.language-csharp',
    '.lua': 'mdi6.language-lua',
    '.dart': 'mdi6.language-dart',
    '.r': 'mdi6.language-r',
    '.sh': 'mdi6.bash',
    '.bash': 'mdi6.bash',
    '.ps1': 'mdi6.powershell',
    '.bat': 'mdi6.console',
    '.cmd': 'mdi6.console',
    '.toml': 'mdi6.cog',
    '.ini': 'mdi6.cog',
    '.cfg': 'mdi6.cog',
    '.txt': 'mdi6.file-document-outline',
    '.log': 'mdi6.file-document-outline',
    '.csv': 'mdi6.file-delimited-outline',
    '.gitignore': 'mdi6.git',
    '.dockerfile': 'mdi6.docker',
    '.env': 'mdi6.cog',
}
_KNOWN_EXTS = set(_FILE_ICON_MAP.keys())
# 明确要排除的二进制/媒体文件扩展名
_EXCLUDED_EXTS = {
    '.exe', '.dll', '.so', '.dylib', '.bin', '.obj', '.o', '.a', '.lib',
    '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.xz',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp',
    '.mp3', '.mp4', '.avi', '.mkv', '.mov', '.wav', '.flac', '.ogg',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.pyc', '.pyo', '.pyd', '.class', '.jar',
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    '.db', '.sqlite', '.sqlite3',
}


def get_file_icon_name(file_path):
    """根据文件扩展名返回 qta 图标名"""
    ext = os.path.splitext(file_path)[1].lower()
    return _FILE_ICON_MAP.get(ext, 'mdi6.file-outline')


def _is_windows_junction(path: str) -> bool:
    """
    检测 Windows junction / reparse point
    os.path.islink() 在某些 Python 版本中不能可靠检测 Windows junction，
    因此额外使用 os.stat() 检查 FILE_ATTRIBUTE_REPARSE_POINT (0x400)
    """
    if sys.platform != "win32":
        return False
    try:
        import stat
        attrs = os.stat(path).st_file_attributes
        return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, OSError):
        return False


def is_displayable_file(file_path):
    """判断文件是否应该在文件树中显示"""
    name = os.path.basename(file_path)
    if name.startswith('.'):
        return False
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _EXCLUDED_EXTS:
        return False
    # 已知文本/代码文件直接显示
    if ext in _KNOWN_EXTS:
        return True
    # 无扩展名或未知扩展名：尝试用文本模式读取来判断
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)
        return True
    except (UnicodeDecodeError, PermissionError, OSError):
        return False


# ── FileConfig: 文件夹级别编辑器状态持久化 ─────────────────────

def get_file_config_path():
    """获取 file_config.json 路径（在 windows 目录下）"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'file_config.json')


class FileConfig:
    """管理文件夹级别的编辑器状态（打开的文件、活动标签等）"""

    def __init__(self):
        self._path = get_file_config_path()
        self._data = self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {'last_folder': '', 'folders': {}}

    def save(self):
        try:
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存 file_config.json 失败: {e}")

    def get_last_folder(self):
        return self._data.get('last_folder', '')

    def set_last_folder(self, folder_path):
        self._data['last_folder'] = os.path.normpath(folder_path)
        self.save()

    @staticmethod
    def _normalize_path(path: str) -> str:
        """路径标准化：统一斜杠和大小写（Windows 不区分大小写）"""
        return os.path.normpath(os.path.normcase(path))

    def get_folder_state(self, folder_path):
        """获取某个文件夹的保存状态，没有则返回 None"""
        key = self._normalize_path(folder_path)
        # 在所有 folders 中按标准化 key 匹配
        for stored_path, state in self._data.get('folders', {}).items():
            if self._normalize_path(stored_path) == key:
                return state
        return None

    def get_folder_paths_sorted_by_time(self):
        """获取所有文件夹路径，按 last_used_time 从新到旧排序"""
        folders = self._data.get('folders', {})
        if not folders:
            return []
        items = []
        for path, state in folders.items():
            t = state.get('last_used_time', '')
            items.append((t, path))
        items.sort(key=lambda x: x[0], reverse=True)
        return [path for _, path in items]

    def set_folder_state(self, folder_path, open_files, active_file=None):
        """保存某个文件夹的编辑器状态"""
        if 'folders' not in self._data:
            self._data['folders'] = {}
        from datetime import datetime
        # 标准化存储 key
        norm_path = os.path.normpath(folder_path)
        norm_key = self._normalize_path(folder_path)
        # 清理旧的非标准化重复条目
        for stored_path in list(self._data['folders'].keys()):
            if stored_path != norm_path and self._normalize_path(stored_path) == norm_key:
                del self._data['folders'][stored_path]
        self._data['folders'][norm_path] = {
            'open_files': open_files,
            'active_file': active_file,
            'last_used_time': datetime.now().isoformat(),
        }
        self._data['last_folder'] = norm_path
        self.save()

    def update_folder_used_time(self, folder_path):
        """仅更新文件夹的最后使用时间（不改变 open_files）"""
        key = self._normalize_path(folder_path)
        for stored_path in list(self._data.get('folders', {}).keys()):
            if self._normalize_path(stored_path) == key:
                from datetime import datetime
                self._data['folders'][stored_path]['last_used_time'] = datetime.now().isoformat()
                self._data['last_folder'] = stored_path
                self.save()
                return
        # 如果不存在，创建空记录
        self.set_folder_state(os.path.normpath(folder_path), [], '')

    def clean_invalid_folders(self):
        """清理已经不存在的文件夹记录"""
        folders = self._data.get('folders', {})
        invalid = [p for p in folders if not os.path.isdir(p)]
        for p in invalid:
            del folders[p]
        if invalid:
            self.save()


# ── UI 组件 ────────────────────────────────────────────────────

class HackWebView(QWebEngineView):
    """ 强制把键盘事件转发给父窗口 """
    def keyPressEvent(self, event):
        # 👇 核心：把按键丢给父窗口（TabInterface）处理
        self.parent().parent().keyPressEvent(event)
        # 继续传给网页
        super().keyPressEvent(event)
        
class EditorTabWidget(QWidget):
    """ 编辑器标签页组件 """
    
    def __init__(self, file_path, parent=None, is_dark_theme=False):
        super().__init__(parent)
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.setObjectName(self.file_name)
        self.is_dark_theme = is_dark_theme
        self.code_editor_window: CodeEditorWindow = parent  # 保存父窗口引用
        self.language = get_monaco_language(file_path)  # 根据文件扩展名检测语言

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 创建WebView
        self.webView = HackWebView(self)
        settings = self.webView.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        html_path = os.path.join(project_dir, 'code_editor.html')

        self.webView.loadFinished.connect(self.onLoadFinished)
        self.webView.setUrl(QUrl.fromLocalFile(html_path))

        self.layout.addWidget(self.webView)

        # WebView 加载状态标志
        self._webview_loaded = False

        # 加载文件内容
        if file_path and os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.content = f.read()
            except Exception as e:
                print(f"加载文件时出错: {e}")
                self.content = ""
        else:
            self.content = ""

    def onLoadFinished(self, ok):
        if ok:
            self._webview_loaded = True
            # 直接在初始化时设置主题，使用检测到的语言
            theme = 'vs-dark' if self.is_dark_theme else 'vs'
            self.webView.page().runJavaScript(
                f'initEditor({repr(self.content)}, {repr(self.language)}, {repr(theme)})'
            )
            self.webView.page().runJavaScript('enableCodeCompletion()')
            self.webView.page().runJavaScript('disableContextMenu()')

            # 连接自定义右键菜单
            self.webView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            if hasattr(self.code_editor_window, 'showContextMenu'):
                self.webView.customContextMenuRequested.connect(self.code_editor_window.showContextMenu)

            # 为 webView 安装事件过滤器，处理键盘事件
            # self.webView.installEventFilter(self)


    def setTheme(self, is_dark):
        """ 设置编辑器主题 """
        self.is_dark_theme = is_dark
        # 只有在 WebView 加载完成后才调用 JavaScript
        if self._webview_loaded:
            theme = 'vs-dark' if is_dark else 'vs'
            self.webView.page().runJavaScript(f'setTheme({repr(theme)})')
    
    def getCode(self):
        """ 获取编辑器内容 """
        result = [""]
        from PyQt6.QtCore import QEventLoop
        loop = QEventLoop()
        
        def callback(value):
            result[0] = value
            loop.quit()
        
        self.webView.page().runJavaScript('getCode()', 0, callback)
        loop.exec()
        return result[0]
    
    def setCode(self, code):
        """ 设置编辑器内容 """
        self.webView.page().runJavaScript(f'setCode({repr(code)})')

    def reloadContent(self):
        """ 从磁盘重新读取文件内容并更新编辑器（用于 Pi Agent 写入后刷新）"""
        if not self.file_path or not os.path.isfile(self.file_path):
            return
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                new_content = f.read()
            if new_content != self.content:
                self.content = new_content
                if self._webview_loaded:
                    self.setCode(new_content)
        except Exception as e:
            print(f"[EditorTab] 刷新文件内容失败: {e}")

    def save(self):
        """ 保存文件
        
        必须确保 WebView 已加载完成（_webview_loaded=True），否则 getCode() 会返回
        Monaco 编辑器的默认模板内容，导致文件原始内容被覆盖。
        """
        if not self.file_path:
            return False
        if not self._webview_loaded:
            return False  # 编辑器尚未初始化，拒绝保存以避免覆盖文件
        try:
            content = self.getCode()
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"文件已保存: {self.file_path}")
            return True
        except Exception as e:
            print(f"保存文件时出错: {e}")
            return False


def detect_python_versions():
    """检测系统已安装的Python版本"""
    python_versions = []
    
    # 检测 py launcher (Windows Python Launcher) - 最可靠的方式
    try:
        result = subprocess.run(['py', '--list'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                # 匹配格式: -3.12-64 * 或 -3.12 * 等
                match = re.search(r'-?(\d+\.\d+)(?:-\d+)?\s*\*?', line)
                if match:
                    version_short = match.group(1)  # 如 "3.12"
                    # 避免重复添加
                    if not any(v[0] == f'py -{version_short}' for v in python_versions):
                        python_versions.append((f'py -{version_short}', version_short))
    except:
        pass
    
    # 如果没检测到 py launcher，尝试检测常见版本
    if not python_versions:
        for version in ['3.12', '3.11', '3.10', '3.9', '3.8']:
            try:
                result = subprocess.run([f'py', f'-{version}', '--version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    version_match = re.search(r'Python (\d+\.\d+\.\d+)', result.stdout + result.stderr)
                    if version_match:
                        python_versions.append((f'py -{version}', version))
            except:
                continue
    
    # 兜底：检测默认 python
    if not python_versions:
        try:
            result = subprocess.run(['python', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version_match = re.search(r'Python (\d+\.\d+\.\d+)', result.stdout + result.stderr)
                if version_match:
                    python_versions.append(('python', version_match.group(1)))
        except:
            pass
    
    return python_versions if python_versions else [('python', 'unknown')]


class TabInterface(QWidget):
    """ 标签页界面 """

    tabs_changed = pyqtSignal()  # 标签页变化时发射

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.code_editor_window :CodeEditorWindow = parent  # 保存CodeEditorWindow引用
        self.tabCount = 1


        self.tabBar = TabBar(self)
        self.tabBar.runbutn = TransparentDropDownPushButton("运行", self, FluentIcon.PLAY)
        self.tabBar.runbutn.setToolTip("运行当前Python文件")
        self.runMenu = RoundMenu(parent=self)
        self._updateRunMenu()
        # 下拉按钮，点击显示菜单选择 Python 版本
        self.tabBar.runbutn.setMenu(self.runMenu)
        self.tabBar.widgetLayout.addWidget(self.tabBar.runbutn, 0, Qt.AlignmentFlag.AlignRight)
        
        self.stackedWidget = QStackedWidget(self)

        # 新建文件菜单
        self.newFileMenu = RoundMenu(parent=self)
        self._initNewFileMenu()

        # add items to pivot
        self.__initWidget()
    
    def _updateRunMenu(self):
        """更新运行菜单"""
        self.runMenu.clear()
        # 子进程运行（使用启动主程序的 Python 版本）
        action = Action(FIF.ADD, "运行（子进程运行）", self)
        action.triggered.connect(lambda: self.runPython(sys.executable))
        self.runMenu.addAction(action)
    
    def _initNewFileMenu(self):
        """初始化新建文件菜单"""
        self.newFileMenu.clear()
        
        # 策略模板
        action = Action(FIF.CODE, "策略模板", self)
        action.triggered.connect(lambda: self.createFileFromTemplate("strategy_template.py"))
        self.newFileMenu.addAction(action)
        
        # 指标模板
        action = Action(FIF.ACCEPT, "指标模板", self)
        action.triggered.connect(lambda: self.createFileFromTemplate("indicator_template.py"))
        self.newFileMenu.addAction(action)
        
        # 参数优化模板
        action = Action(FIF.SETTING, "参数优化模板", self)
        action.triggered.connect(lambda: self.createFileFromTemplate("optimization_template.py"))
        self.newFileMenu.addAction(action)

    def runPython(self, python_cmd: str):
        """运行当前编辑器中的Python文件，使用子进程执行"""
        import subprocess
        current_editor = self.getCurrentEditor()
        if not current_editor:
            InfoBar.warning("提示", "请先打开一个文件", duration=3000, parent=self).show()
            return
        
        file_path = getattr(current_editor, 'file_path', None)
        if not file_path:
            InfoBar.warning("提示", "请先保存文件后再运行", duration=3000, parent=self).show()
            return
        
        if not file_path.lower().endswith('.py'):
            InfoBar.warning("提示", "只支持运行 .py 文件", duration=3000, parent=self).show()
            return
        
        current_editor.save()
        
        file_dir = os.path.dirname(file_path)
        work_dir = file_dir if file_dir else None
        
        print(f"\n{'='*60}")
        print(f"子进程运行: {python_cmd} {file_path}")
        print(f"{'='*60}\n")
        
        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            is_windows = sys.platform == 'win32'
            
            if is_windows:
                file_path_quoted = f'"{file_path}"' if ' ' in file_path else file_path
                cmd_str = f'{python_cmd} {file_path_quoted}'
                proc = subprocess.Popen(
                    cmd_str, cwd=work_dir, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, env=env,
                    text=True, encoding='utf-8', errors='replace', shell=True
                )
            else:
                proc = subprocess.Popen(
                    [python_cmd, file_path], cwd=work_dir,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    env=env, text=True, encoding='utf-8', errors='replace'
                )
            
            for line in iter(proc.stdout.readline, ''):
                if line:
                    print(line.rstrip())
            
            proc.wait()
            print(f"\n{'='*60}")
            print(f"子进程运行完成，返回码: {proc.returncode}")
            print(f"{'='*60}\n")
        except Exception as e:
            print(f"子进程运行出错: {e}")
    
    def createFileFromTemplate(self, template_name: str):
        """从模板创建新文件"""
        import shutil
        
        # 获取模板路径
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resource', 'strategy_template')
        template_path = os.path.join(template_dir, template_name)
        
        if not os.path.exists(template_path):
            InfoBar.error("错误", f"模板文件不存在: {template_path}", duration=3000, parent=self).show()
            return
        
        # 获取当前目录
        current_dir = self.code_editor_window.currentFilePath
        if current_dir and os.path.isfile(current_dir):
            current_dir = os.path.dirname(current_dir)
        elif current_dir and os.path.isdir(current_dir):
            pass
        else:
            # 默认使用当前工作目录
            current_dir = os.getcwd()
        
        # 生成默认文件名
        base_name = os.path.splitext(template_name)[0]
        new_file_name = f"{base_name}.py"
        new_file_path = os.path.join(current_dir, new_file_name)
        
        # 如果文件已存在，添加序号
        counter = 1
        while os.path.exists(new_file_path):
            new_file_name = f"{base_name}_{counter}.py"
            new_file_path = os.path.join(current_dir, new_file_name)
            counter += 1
        
        # 复制模板文件到新位置
        try:
            shutil.copy2(template_path, new_file_path)
            
            # 在编辑器中打开新文件
            self.addEditorTab(new_file_path)
            
            InfoBar.success("成功", f"已创建文件: {new_file_name}", duration=3000, parent=self).show()
        except Exception as e:
            InfoBar.error("错误", f"创建文件失败: {str(e)}", duration=3000, parent=self).show()

    def __initWidget(self):
        self.initLayout()

        self.tabBar.setTabMaximumWidth(200)
        self.tabBar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.ON_HOVER)

        self.connectSignalToSlot()
    
    @property
    def is_dark_theme(self)-> bool:
        return self.code_editor_window.is_dark_theme

    def connectSignalToSlot(self):
        self.tabBar.tabCloseRequested.connect(self.removeTab)
        self.tabBar.tabAddRequested.connect(self.showNewFileMenu)
        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
    
    def showNewFileMenu(self):
        """显示新建文件菜单"""
        # 获取"+"按钮的位置并显示菜单
        add_button = self.tabBar.findChild(QPushButton)
        if add_button:
            self.newFileMenu.exec(add_button.mapToGlobal(add_button.rect().bottomLeft()))
        else:
            # 如果找不到按钮，在鼠标位置显示
            self.newFileMenu.exec(QCursor.pos())

    def initLayout(self):
        self.setMinimumHeight(400)
        
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.addWidget(self.tabBar)
        self.vBoxLayout.addWidget(self.stackedWidget)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(0)

    def addEditorTab(self, file_path):
        """ 添加编辑器标签页 """
        # 路径归一化（解决大小写、斜杠方向差异）
        file_path = os.path.normpath(os.path.normcase(file_path))

        # 检查是否已经打开了该文件
        for i in range(self.stackedWidget.count()):
            widget = self.stackedWidget.widget(i)
            if hasattr(widget, 'file_path'):
                existing = os.path.normpath(os.path.normcase(widget.file_path))
                if existing == file_path:
                    # 切换到已存在的标签页
                    self.stackedWidget.setCurrentWidget(widget)
                    return widget
        
        # 创建新的编辑器标签页，传递当前主题和CodeEditorWindow引用
        editor_widget = EditorTabWidget(file_path, self.code_editor_window, self.is_dark_theme)
        self.stackedWidget.addWidget(editor_widget)
        
        # 添加到标签栏
        file_name = os.path.basename(file_path)
        self.tabBar.addTab(
            routeKey=file_name,
            text=file_name,
            icon=FIF.CODE,
            onClick=lambda: self.stackedWidget.setCurrentWidget(editor_widget)
        )
        
        # 切换到新标签页
        self.stackedWidget.setCurrentWidget(editor_widget)
        self.tabs_changed.emit()
        return editor_widget

    def refreshOrOpenFile(self, file_path: str):
        """打开或刷新文件标签页（Pi Agent 写入/编辑后调用）。
        如果文件已经打开 → 刷新内容；否则 → 新建标签页打开。"""
        file_path = os.path.normpath(os.path.normcase(file_path))
        if not os.path.isfile(file_path):
            return

        # 查找已打开的标签页
        for i in range(self.stackedWidget.count()):
            widget = self.stackedWidget.widget(i)
            if hasattr(widget, 'file_path'):
                existing = os.path.normpath(os.path.normcase(widget.file_path))
                if existing == file_path:
                    # 已打开：从磁盘重新读取并更新编辑器内容
                    widget.reloadContent()
                    return

        # 未打开：新建标签页
        self.addEditorTab(file_path)

    def switchToFile(self, file_path: str):
        """切换到指定文件的标签页（需已经打开）。"""
        file_path = os.path.normpath(os.path.normcase(file_path))
        for i in range(self.stackedWidget.count()):
            widget = self.stackedWidget.widget(i)
            if hasattr(widget, 'file_path'):
                existing = os.path.normpath(os.path.normcase(widget.file_path))
                if existing == file_path:
                    self.stackedWidget.setCurrentIndex(i)
                    return

    def keyPressEvent(self, event):
        # Ctrl+I: Quick AI 编辑当前文件（仅当有打开的文件时生效）
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == 16777265:
            if self.code_editor_window.has_open_file:
                self.code_editor_window._on_quick_ai()
            event.accept()
            return

        # 其他按键正常传递
        super().keyPressEvent(event)
    
    
    def setTheme(self, is_dark):
        """ 为所有编辑器设置主题 """
        # 更新所有编辑器的主题
        for i in range(self.stackedWidget.count()):
            widget = self.stackedWidget.widget(i)
            if hasattr(widget, 'setTheme'):
                widget.setTheme(is_dark)

    def getCurrentEditor(self):
        """ 获取当前编辑器 """
        return self.stackedWidget.currentWidget()

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        if not widget:
            return

        self.tabBar.setCurrentTab(widget.objectName())
        
        # 切换标签页时，终端跟随切换到文件所在目录
        if hasattr(widget, 'file_path') and widget.file_path:
            file_dir = os.path.dirname(widget.file_path)
            if file_dir:
                main_wnd = self.code_editor_window.main_window
                if hasattr(main_wnd, 'get_terminal'):
                    term = main_wnd.get_terminal()
                    if term and hasattr(term, 'sendData'):
                        def _send():
                            try:
                                term.sendData(f'cd "{file_dir}"\r')
                            except Exception:
                                pass
                        QTimer.singleShot(300, _send)

    def removeTab(self, index):
        item = self.tabBar.tabItem(index)
        if not item:
            return
        
        widget = self.stackedWidget.widget(index)
        if widget:
            self.stackedWidget.removeWidget(widget)
            widget.deleteLater()
        
        self.tabBar.removeTab(index)
        self.tabs_changed.emit()

class CodeEditorWindow(QWidget):
    """ 基于Monaco Editor的代码编辑器窗口 """

    # 信号：切换 Pi Agent 窗口
    toggle_pi_agent = pyqtSignal()
    # 信号：重新加载 Pi Agent 页面（仅刷新页面，不重启服务）
    reload_pi_agent = pyqtSignal()
    reload_pi_service = pyqtSignal()  # 完全重启 pi-agent-web 服务
    # 信号：运行回测（当前标签页的 .py 文件）
    run_backtest = pyqtSignal()
    # 信号：文件夹切换（用于反向同步到 pi-web 文件树）
    folder_changed = pyqtSignal(str)

    def __init__(self, parent=None, is_dark_theme: bool = False):
        super().__init__(parent=parent)
        self.setObjectName("CodeEditorWindow")
        self.setWindowTitle("代码编辑器")
        self.main_window :MainWindow = parent  # 保存MainWindow引用
        self.file_config = FileConfig()  # 文件夹级别编辑器状态持久化
        
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)
        
        # 创建分割器
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setHandleWidth(0)  # 设置间隙为0
        
        # 右侧布局（先创建，因为左侧树形组件加载时需要 tabInterface）
        rightWidget = QWidget(self)
        rightLayout = QVBoxLayout(rightWidget)
        rightLayout.setContentsMargins(0, 0, 0, 0)
        rightLayout.setSpacing(0)
        
        # 右侧工具栏
        self.commandBar = self.createCommandBar()
        rightLayout.addWidget(self.commandBar)
        
        # 右侧标签页编辑器，传递当前主题
        self._is_dark_theme = is_dark_theme
        self.tabInterface = TabInterface(self)
        rightLayout.addWidget(self.tabInterface)
        
        # 左侧树形组件（在 tabInterface 之后创建，以便 loadFiles 中可以恢复文件）
        self.createTreeWidget()
        
        # 添加到分割器
        self.splitter.addWidget(self.treeWidget)
        self.splitter.addWidget(rightWidget)
        
        # 设置分割器比例
        self.splitter.setSizes([400, 700])
        
        # 添加分割器到主布局
        self.mainLayout.addWidget(self.splitter)
        
        # 创建上下文菜单
        self.createContextMenu()
        
        # 当前打开的文件路径
        self.currentFilePath = None
        
        # 同步主题
        self.setTheme(is_dark_theme)
        
        # 复制/剪切的文件或文件夹
        self.copied_items = []
        self.cut_items = []
        
        # 聊天窗口
        self.chat_window = None
        
        # 快速 AI 按钮状态跟随标签页变化
        self.tabInterface.tabs_changed.connect(self._update_quick_ai_button)
        self._update_quick_ai_button()  # 初始化时同步一次（loadFiles 在连接之前调用）
        
        # 连接主题颜色变化信号
        cfg.themeColor.valueChanged.connect(self.onThemeColorChanged)
    
    @property
    def is_dark_theme(self)-> bool:
        return self._is_dark_theme
    
    @is_dark_theme.setter
    def is_dark_theme(self, value: bool):
        self.setTheme(value)
        
    def createCommandBar(self):
        bar = CommandBar(self)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        action_open = Action(FIF.FOLDER, '打开', triggered=self.openFolder)
        action_open.setToolTip("打开文件夹")
        action_refresh = Action(FIF.SYNC, '刷新', triggered=self.refreshFileTree)
        action_refresh.setToolTip("刷新文件夹")
        action_add = Action(FIF.ADD, '新建', triggered=self.newFile)
        action_add.setToolTip("新建文件或文件夹")
        action_save = Action(FIF.SAVE, '保存', triggered=self.saveFile)
        action_save.setToolTip("保存当前文件")
        
        bar.addActions([
            action_open,
            action_refresh,
            action_add,
            action_save,
        ])
        bar.addSeparator()
        action_pi_agent = Action(FluentIcon.ROBOT, 'Pi Agent', triggered=self._on_toggle_pi_agent)
        action_pi_agent.setToolTip("切换Pi Agent窗口")
        action_reload_pi_agent = Action(FluentIcon.UPDATE, '刷新Pi', triggered=self._on_reload_pi_agent)
        action_reload_pi_agent.setToolTip("刷新当前Pi Agent窗口")
        
        bar.addActions([
            action_pi_agent,
            action_reload_pi_agent,
        ])
        # 快速 AI 按钮（需要打开文件时才可用）
        self._quick_ai_action = Action(FluentIcon.EDIT, '快速AI', triggered=self._on_quick_ai,shortcut="F2")
        self._quick_ai_action.setToolTip("快捷键F2")
        self._quick_ai_action.setEnabled(False)
        bar.addAction(self._quick_ai_action)
        bar.addSeparator()
        bar.addHiddenActions([
            # Action(FluentIcon.SETTING, "设置", shortcut="Ctrl+S"),
            Action(FluentIcon.ROBOT, "重载Pi Agent", triggered=self._on_reload_pi_service),
            Action(FluentIcon.HELP, "帮助", shortcut="F1", triggered=self._show_pi_agent_help),
            
        ])
        # bar.addActions([
        #     Action(FIF.CUT, '剪切'),
        #     Action(FIF.COPY, '复制'),
        #     Action(FIF.PASTE, '粘贴'),
        # # ])
        # # bar.addSeparator()
        # # bar.addActions([
        #     Action(FIF.ZOOM_IN, '放大'),
        #     Action(FIF.ZOOM_OUT, '缩小'),
        # # ])
        # # bar.addSeparator()
        # # bar.addActions([
        #     Action(FIF.CANCEL, '撤销'),
        #     # Action(FIF.ACCEPT, '重做'),
        # ])
        # bar.addSeparator()
        # bar.addActions([
        #     Action(FIF.EDIT, '搜索', triggered=self.find),
        #     Action(FIF.EDIT, '替换', triggered=self.replace),
        # ])
        # bar.addSeparator()
        # bar.addActions([
        #     Action(FIF.EDIT, '浅色主题', triggered=self.setLightTheme),
        #     Action(FIF.SAVE, '深色主题', triggered=self.setDarkTheme),
        # ])
        return bar
        
    def createEditor(self):
        # 不再需要单独的webView，使用TabInterface中的编辑器
        pass
        
    def createTreeWidget(self):
        """ 创建左侧树形组件 """
        self.treeWidget = TreeWidget(self)
        self.treeWidget.setHeaderLabel("文件浏览")
        self.treeWidget.itemDoubleClicked.connect(self.onTreeItemDoubleClicked)
        
        # 为树形组件添加右键菜单
        self.treeWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.treeWidget.customContextMenuRequested.connect(self.showTreeContextMenu)
        
        # 连接项目重命名信号
        self.treeWidget.itemChanged.connect(self.onItemChanged)
        
        # 加载当前目录的文件
        self.loadFiles()
    
    def loadFiles(self, directory=None):
        """ 加载目录文件树，根据 file_config.json 恢复上次打开的文件 """
        self.treeWidget.clear()

        # 从 file_config.json 读取上次使用的文件夹
        file_config = self.file_config
        last_folder_state = None

        # 确定要加载的目录
        if directory is not None:
            current_dir = directory
        else:
            current_dir = self._find_valid_recent_dir(file_config)

        # 如果找不到任何有效目录，不加载文件树
        if not current_dir or not os.path.isdir(current_dir):
            print("[CodeEditor] 无可用的文件夹路径，文件树为空")
            self.root_directory = ""
            return

        self.root_directory = current_dir
        last_folder_state = file_config.get_folder_state(current_dir)
        print(f"[CodeEditor] 加载文件树: {current_dir}")

        # 创建根节点
        root_item = QTreeWidgetItem([os.path.basename(current_dir)])
        root_item.setData(0, Qt.ItemDataRole.UserRole, current_dir)
        self.treeWidget.addTopLevelItem(root_item)

        # 递归加载文件
        self._loadDirectory(root_item, current_dir)

        # 选中并展开根节点
        self.treeWidget.setCurrentItem(root_item)
        self.treeWidget.expandItem(root_item)

        # 恢复上次打开的文件
        if last_folder_state:
            open_files = last_folder_state.get('open_files', [])
            active_file = last_folder_state.get('active_file', '')
            for file_path in open_files:
                if os.path.isfile(file_path):
                    self.tabInterface.addEditorTab(file_path)
            # 切换到上次活动的标签页
            if active_file:
                for i in range(self.tabInterface.stackedWidget.count()):
                    w = self.tabInterface.stackedWidget.widget(i)
                    if hasattr(w, 'file_path') and w.file_path == active_file:
                        self.tabInterface.stackedWidget.setCurrentWidget(w)
                        break
        # 更新最后使用时间和 last_folder
        file_config.update_folder_used_time(current_dir)

    @staticmethod
    def _find_valid_recent_dir(file_config) -> str:
        """
        从 file_config.json 的 folders 中按 last_used_time 从新到旧查找第一个存在的目录。
        如果 folders 中没有有效目录，返回空字符串。
        """
        for folder_path in file_config.get_folder_paths_sorted_by_time():
            if folder_path and os.path.isdir(folder_path):
                return folder_path
        return ""
    
    # 系统保护目录列表（Windows），这些目录通常无权限访问
    _SYSTEM_SKIP_DIRS = {'$RECYCLE.BIN', 'System Volume Information', '$WinREAgent',
                         'Config.Msi', 'MSOCache', 'Recovery', 'PerfLogs',
                         'Documents and Settings'}

    # 最大递归深度，防止 junction/reparse point 导致的死循环
    _MAX_LOAD_DEPTH = 20

    def _loadDirectory(self, parent_item, directory, depth=0):
        """ 递归加载目录，跳过 junction/reparse point 防止死循环 """
        if depth > self._MAX_LOAD_DEPTH:
            return

        try:
            theme_color = cfg.get(cfg.themeColor)

            items = sorted(os.listdir(directory), key=lambda x: (not os.path.isdir(os.path.join(directory, x)), x.lower()))
            for item in items:
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path):
                    # 跳过隐藏目录、系统保护目录
                    if item.startswith('.') or item in self._SYSTEM_SKIP_DIRS:
                        continue
                    # 跳过 junction / reparse point，防止循环或意外扫描巨型目录
                    if os.path.islink(item_path) or _is_windows_junction(item_path):
                        continue
                    dir_item = QTreeWidgetItem([item])
                    dir_item.setData(0, Qt.ItemDataRole.UserRole, item_path)
                    dir_icon = FIF.FOLDER.icon(color=theme_color)
                    dir_item.setIcon(0, dir_icon)
                    parent_item.addChild(dir_item)
                    try:
                        self._loadDirectory(dir_item, item_path, depth + 1)
                    except PermissionError:
                        pass
                elif os.path.isfile(item_path) and is_displayable_file(item_path):
                    file_item = QTreeWidgetItem([item])
                    file_item.setData(0, Qt.ItemDataRole.UserRole, item_path)
                    try:
                        icon_name = get_file_icon_name(item_path)
                        icon = qta.icon(icon_name, color=theme_color)
                        file_item.setIcon(0, icon)
                    except Exception:
                        file_icon = FIF.CODE.icon(color=theme_color)
                        file_item.setIcon(0, file_icon)
                    parent_item.addChild(file_item)
        except PermissionError:
            pass
        except Exception as e:
            print(f"加载目录时出错: {e}")
    
    def onTreeItemDoubleClicked(self, item, column):
        """ 双击树项事件 """
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path and os.path.isfile(file_path):
            # 使用TabInterface打开文件
            self.tabInterface.addEditorTab(file_path)
        
    def createContextMenu(self):
        """ 创建右键菜单 """

        self.contextMenu = RoundMenu()
        
        # 运行菜单
        runMenu = RoundMenu('运行', self)
        runMenu.setIcon(FIF.PLAY)
        runMenu.addAction(Action(FIF.PLAY, '运行当前文件', triggered=self.runCurrentFile))
        runMenu.addAction(Action(FIF.SEND, '运行（子进程运行）', triggered=lambda: self.tabInterface.runPython(sys.executable)))
        runMenu.addSeparator()
        runMenu.addAction(Action(FIF.COMMAND_PROMPT, '参数回测', triggered=self._on_run_backtest))
        self.contextMenu.addMenu(runMenu)

        # 添加保存功能
        self.contextMenu.addSeparator()
        self.contextMenu.addAction(Action(FIF.SAVE, '保存当前文件', triggered=self.saveFile))
        self.contextMenu.addAction(Action(FIF.SAVE, '保存所有文件', triggered=self.saveAllFiles))
        
        self.contextMenu.addSeparator()

        # 编辑操作（剪切、复制、粘贴、撤销）
        cut_action = Action(FIF.CUT, '剪切')
        cut_action.triggered.connect(self.cut)
        self.contextMenu.addAction(cut_action)

        copy_action = Action(FIF.COPY, '复制')
        copy_action.triggered.connect(self.copy)
        self.contextMenu.addAction(copy_action)

        paste_action = Action(FIF.PASTE, '粘贴')
        paste_action.triggered.connect(self.paste)
        self.contextMenu.addAction(paste_action)

        undo_action = Action(FIF.CANCEL, '撤销')
        undo_action.triggered.connect(self.undo)
        self.contextMenu.addAction(undo_action)

        redo_action = Action(FIF.SYNC, '重做')
        redo_action.triggered.connect(self.redo)
        self.contextMenu.addAction(redo_action)

        self.contextMenu.addSeparator()

        # 搜索和替换
        find_action = Action(FIF.EDIT, '搜索')
        find_action.triggered.connect(self.find)
        self.contextMenu.addAction(find_action)

        replace_action = Action(FIF.EDIT, '替换')
        replace_action.triggered.connect(self.replace)
        self.contextMenu.addAction(replace_action)

        self.contextMenu.addSeparator()

        # 放大缩小
        zoom_in_action = Action(FIF.ZOOM_IN, '放大')
        zoom_in_action.triggered.connect(self.zoomIn)
        self.contextMenu.addAction(zoom_in_action)

        zoom_out_action = Action(FIF.ZOOM_OUT, '缩小')
        zoom_out_action.triggered.connect(self.zoomOut)
        self.contextMenu.addAction(zoom_out_action)

        self.contextMenu.addSeparator()

        # 主题设置
        # themeMenu = RoundMenu('主题设置', self)
        # themeMenu.addAction(Action(FIF.EDIT, '浅色主题', triggered=self.setLightThemeForAll))
        # themeMenu.addAction(Action(FIF.SAVE, '深色主题', triggered=self.setDarkThemeForAll))

        # 编辑器配置
        configMenu = RoundMenu('编辑器配置', self)
        configMenu.setIcon(FIF.DEVELOPER_TOOLS)

        # 自动换行
        wordWrapAction = Action(FIF.ALIGNMENT, '自动换行', checkable=True)
        wordWrapAction.setChecked(False)
        wordWrapAction.triggered.connect(lambda checked: self.setWordWrapForAll(checked))
        configMenu.addAction(wordWrapAction)

        # 行号
        lineNumbersAction = Action(FIF.QUICK_NOTE, '显示行号', checkable=True)
        lineNumbersAction.setChecked(True)
        lineNumbersAction.triggered.connect(lambda checked: self.setLineNumbersForAll(checked))
        configMenu.addAction(lineNumbersAction)

        # 小地图
        minimapAction = Action(FIF.ZOOM, '显示小地图', checkable=True)
        minimapAction.setChecked(False)
        minimapAction.triggered.connect(lambda checked: self.setMinimapEnabledForAll(checked))
        configMenu.addAction(minimapAction)

        # 代码折叠
        foldingAction = Action(FIF.ARROW_DOWN, '启用代码折叠', checkable=True)
        foldingAction.setChecked(False)
        foldingAction.triggered.connect(lambda checked: self.setFoldingEnabledForAll(checked))
        configMenu.addAction(foldingAction)

        # 括号对着色
        bracketAction = Action(FIF.BRUSH, '括号对着色', checkable=True)
        bracketAction.setChecked(True)
        bracketAction.triggered.connect(lambda checked: self.setBracketColorizationForAll(checked))
        configMenu.addAction(bracketAction)

        # 渲染空白字符
        whitespaceAction = Action(FIF.FONT, '显示空白字符', checkable=True)
        whitespaceAction.setChecked(False)
        whitespaceAction.triggered.connect(lambda checked: self.setRenderWhitespaceForAll(checked))
        configMenu.addAction(whitespaceAction)

        # 粘贴时格式化
        formatAction = Action(FIF.EDIT, '粘贴时格式化代码', checkable=True)
        formatAction.setChecked(True)
        formatAction.triggered.connect(lambda checked: self.setFormatOnPasteForAll(checked))
        configMenu.addAction(formatAction)

        configMenu.addSeparator()

        # Tab 大小
        tabSizeMenu = RoundMenu('Tab 大小', self)
        tabSizeMenu.setIcon(FIF.ALIGNMENT)
        for ts in [2, 4, 8]:
            tabSizeMenu.addAction(Action(FIF.FONT, f'{ts} 空格', triggered=lambda _, s=ts: self.setTabSizeForAll(s)))
        configMenu.addMenu(tabSizeMenu)

        # 字体大小
        fontSizeMenu = RoundMenu('字体大小', self)
        fontSizeMenu.setIcon(FIF.FONT)
        for size in [10, 12, 13, 14, 16, 18, 20]:
            fontSizeMenu.addAction(Action(FIF.FONT, f'{size}px', triggered=lambda _, s=size: self.setFontSizeForAll(s)))
        configMenu.addMenu(fontSizeMenu)

        # 添加到主菜单
        # self.contextMenu.addMenu(themeMenu)
        self.contextMenu.addMenu(configMenu)

        
        
    def showContextMenu(self, pos):
        """ 显示右键菜单 """
        # 从当前编辑器获取WebView
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            globalPos = current_editor.webView.mapToGlobal(pos)
            self.contextMenu.exec(globalPos, ani=True)
    
    def showTreeContextMenu(self, pos):
        """ 显示树形组件的右键菜单 """
        # 获取当前选中的节点
        current_item = self.treeWidget.itemAt(pos)
        if not current_item:
            return
        
        # 获取节点路径
        item_path = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_path:
            return
        
        # 创建右键菜单
        menu = RoundMenu()
        
        # 检查是否是目录
        is_directory = os.path.isdir(item_path)
        
        if is_directory:
            # 文件夹菜单
            # 新建文件夹
            new_folder_action = Action(FIF.FOLDER, '新建文件夹', triggered=lambda: self.newFolder(current_item))
            menu.addAction(new_folder_action)
            
            # 新建文件
            new_file_action = Action(FIF.FILTER, '新建文件', triggered=lambda: self.newFileInFolder(current_item))
            menu.addAction(new_file_action)
            
            menu.addSeparator()
            
            # 重命名
            rename_action = Action(FIF.EDIT, '重命名', triggered=lambda: self.renameItem(current_item))
            menu.addAction(rename_action)
            
            # 复制
            copy_action = Action(FIF.COPY, '复制', triggered=lambda: self.copyItem(current_item))
            menu.addAction(copy_action)
            
            # 剪切
            cut_action = Action(FIF.CUT, '剪切', triggered=lambda: self.cutItem(current_item))
            menu.addAction(cut_action)
            
            # 粘贴
            if self.copied_items or self.cut_items:
                paste_action = Action(FIF.PASTE, '粘贴', triggered=lambda: self.pasteItem(current_item))
                menu.addAction(paste_action)
            
            menu.addSeparator()
            
            # 删除
            delete_action = Action(FIF.DELETE, '删除', triggered=lambda: self.deleteItem(current_item))
            menu.addAction(delete_action)
        else:
            # Python文件菜单
            # 新建文件
            new_file_action = Action(FIF.FILTER, '新建文件', triggered=lambda: self.newFileInSameFolder(current_item))
            menu.addAction(new_file_action)
            
            menu.addSeparator()
            
            # 复制
            copy_action = Action(FIF.COPY, '复制', triggered=lambda: self.copyItem(current_item))
            menu.addAction(copy_action)
            
            # 剪切
            cut_action = Action(FIF.CUT, '剪切', triggered=lambda: self.cutItem(current_item))
            menu.addAction(cut_action)
            
            # 粘贴
            if self.copied_items or self.cut_items:
                paste_action = Action(FIF.PASTE, '粘贴', triggered=lambda: self.pasteItem(current_item))
                menu.addAction(paste_action)
            
            menu.addSeparator()
            
            # 删除
            delete_action = Action(FIF.DELETE, '删除', triggered=lambda: self.deleteItem(current_item))
            menu.addAction(delete_action)
        
        # 显示菜单
        globalPos = self.treeWidget.mapToGlobal(pos)
        menu.exec(globalPos, ani=True)
    
    def newFolder(self, item):
        """ 在当前目录下新建文件夹 """
        # 获取当前目录路径
        directory = item.data(0, Qt.ItemDataRole.UserRole)
        if not os.path.isdir(directory):
            return
        
        # 生成新文件夹名
        new_folder_name = "新文件夹"
        counter = 1
        while os.path.exists(os.path.join(directory, new_folder_name)):
            new_folder_name = f"新文件夹_{counter}"
            counter += 1
        
        # 创建新文件夹
        new_folder_path = os.path.join(directory, new_folder_name)
        try:
            os.makedirs(new_folder_path)
            # print(f"新文件夹已创建: {new_folder_path}")
            
            # 重新加载文件树
            self.loadFiles(self.root_directory)
            
            # 找到并选中新创建的文件夹
            root_item = self.treeWidget.topLevelItem(0)
            if root_item:
                def find_new_folder(parent):
                    for i in range(parent.childCount()):
                        child = parent.child(i)
                        child_path = child.data(0, Qt.ItemDataRole.UserRole)
                        if child_path == new_folder_path:
                            return child
                        result = find_new_folder(child)
                        if result:
                            return result
                    return None
                
                new_folder_item = find_new_folder(root_item)
                if new_folder_item:
                    self.treeWidget.setCurrentItem(new_folder_item)
                    self.treeWidget.expandItem(new_folder_item)
                    # 开始编辑文件夹名称
                    self.treeWidget.editItem(new_folder_item, 0)
        except Exception as e:
            print(f"创建文件夹时出错: {e}")
    
    def newFileInFolder(self, item):
        """ 在当前目录下新建Python文件 """
        # 获取当前目录路径
        directory = item.data(0, Qt.ItemDataRole.UserRole)
        if not os.path.isdir(directory):
            return
        
        # 生成新文件名
        new_file_name = "new_file.py"
        counter = 1
        while os.path.exists(os.path.join(directory, new_file_name)):
            new_file_name = f"new_file_{counter}.py"
            counter += 1
        
        # 创建新文件
        new_file_path = os.path.join(directory, new_file_name)
        try:
            with open(new_file_path, 'w', encoding='utf-8') as f:
                f.write("")
            # print(f"新文件已创建: {new_file_path}")
            
            # 重新加载文件树
            self.loadFiles(self.root_directory)
            
            # 找到并选中新创建的文件
            root_item = self.treeWidget.topLevelItem(0)
            if root_item:
                def find_new_file(parent):
                    for i in range(parent.childCount()):
                        child = parent.child(i)
                        child_path = child.data(0, Qt.ItemDataRole.UserRole)
                        if child_path == new_file_path:
                            return child
                        result = find_new_file(child)
                        if result:
                            return result
                    return None
                
                new_file_item = find_new_file(root_item)
                if new_file_item:
                    self.treeWidget.setCurrentItem(new_file_item)
                    # 开始编辑文件名称
                    self.treeWidget.editItem(new_file_item, 0)
            
            # 打开新文件
            self.tabInterface.addEditorTab(new_file_path)
        except Exception as e:
            print(f"创建文件时出错: {e}")
    
    def findAndSelectItem(self, path):
        """ 查找并选中指定路径的节点 """
        def search_item(item, target_path):
            item_path = item.data(0, Qt.ItemDataRole.UserRole)
            if item_path == target_path:
                return item
            
            for i in range(item.childCount()):
                child_item = item.child(i)
                result = search_item(child_item, target_path)
                if result:
                    return result
            return None
        
        root_item = self.treeWidget.topLevelItem(0)
        if root_item:
            target_item = search_item(root_item, path)
            if target_item:
                self.treeWidget.setCurrentItem(target_item)
                self.treeWidget.expandItem(target_item)
    
    def renameItem(self, item):
        """ 重命名节点 """
        # 开始编辑节点名称
        self.treeWidget.editItem(item, 0)
    
    def copyItem(self, item):
        """ 复制节点 """
        item_path = item.data(0, Qt.ItemDataRole.UserRole)
        if item_path:
            # 清空剪切列表，只保留复制列表
            self.copied_items = [item_path]
            self.cut_items = []
            # print(f"已复制: {item_path}")
    
    def cutItem(self, item):
        """ 剪切节点 """
        item_path = item.data(0, Qt.ItemDataRole.UserRole)
        if item_path:
            # 清空复制列表，只保留剪切列表
            self.cut_items = [item_path]
            self.copied_items = []
            # print(f"已剪切: {item_path}")
    
    def pasteItem(self, item):
        """ 粘贴节点 """
        target_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not os.path.isdir(target_path):
            # 如果目标不是目录，使用其所在目录
            target_path = os.path.dirname(target_path)
        
        # 处理复制的项目
        if self.copied_items:
            for source_path in self.copied_items:
                self._copyItem(source_path, target_path)
        
        # 处理剪切的项目
        if self.cut_items:
            for source_path in self.cut_items:
                self._cutItem(source_path, target_path)
    
    def _copyItem(self, source_path, target_path):
        """ 复制项目到目标路径 """
        try:
            # 生成目标路径
            base_name = os.path.basename(source_path)
            dest_path = os.path.join(target_path, base_name)
            
            # 处理重名
            counter = 1
            while os.path.exists(dest_path):
                name, ext = os.path.splitext(base_name)
                dest_path = os.path.join(target_path, f"{name}_copy{counter}{ext}")
                counter += 1
            
            if os.path.isdir(source_path):
                # 复制文件夹
                import shutil
                shutil.copytree(source_path, dest_path)
                # print(f"已复制文件夹: {source_path} → {dest_path}")
            else:
                # 复制文件
                import shutil
                shutil.copy2(source_path, dest_path)
                print(f"已复制文件: {source_path} → {dest_path}")
            
            # 重新加载文件树
            self.loadFiles(self.root_directory)
        except Exception as e:
            print(f"复制失败: {e}")
    
    def _cutItem(self, source_path, target_path):
        """ 剪切项目到目标路径 """
        try:
            # 生成目标路径
            base_name = os.path.basename(source_path)
            dest_path = os.path.join(target_path, base_name)
            
            # 处理重名
            counter = 1
            while os.path.exists(dest_path):
                name, ext = os.path.splitext(base_name)
                dest_path = os.path.join(target_path, f"{name}_copy{counter}{ext}")
                counter += 1
            
            if os.path.isdir(source_path):
                # 移动文件夹
                import shutil
                shutil.move(source_path, dest_path)
                # print(f"已移动文件夹: {source_path} → {dest_path}")
            else:
                # 移动文件
                import shutil
                shutil.move(source_path, dest_path)
                print(f"已移动文件: {source_path} → {dest_path}")
            
            # 清空剪切列表
            self.cut_items = []
            
            # 重新加载文件树
            self.loadFiles(self.root_directory)
        except Exception as e:
            print(f"移动失败: {e}")
    
    def deleteItem(self, item):
        """ 删除节点 """
        item_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_path:
            return
        
        # 显示确认对话框
        title = "删除确认"
        if os.path.isdir(item_path):
            message = f"确定要删除文件夹 '{os.path.basename(item_path)}' 及其所有内容吗？"
        else:
            message = f"确定要删除文件 '{os.path.basename(item_path)}' 吗？"
        
        msg_box = MessageBox(title, message, self)
        if msg_box.exec() == MessageBox.Yes:
            try:
                if os.path.isdir(item_path):
                    # 删除文件夹
                    import shutil
                    shutil.rmtree(item_path)
                    # print(f"已删除文件夹: {item_path}")
                else:
                    # 删除文件
                    os.remove(item_path)
                    # print(f"已删除文件: {item_path}")
                
                # 重新加载文件树
                self.loadFiles(self.root_directory)
            except Exception as e:
                print(f"删除失败: {e}")
    
    def newFileInSameFolder(self, item):
        """ 在当前文件所在文件夹中新建Python文件 """
        # 获取当前文件所在目录
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        directory = os.path.dirname(file_path)
        
        # 生成新文件名
        new_file_name = "new_file.py"
        counter = 1
        while os.path.exists(os.path.join(directory, new_file_name)):
            new_file_name = f"new_file_{counter}.py"
            counter += 1
        
        # 创建新文件
        new_file_path = os.path.join(directory, new_file_name)
        try:
            with open(new_file_path, 'w', encoding='utf-8') as f:
                f.write("")
            # print(f"新文件已创建: {new_file_path}")
            
            # 重新加载文件树
            self.loadFiles(self.root_directory)
            
            # 找到并选中新创建的文件
            root_item = self.treeWidget.topLevelItem(0)
            if root_item:
                def find_new_file(parent):
                    for i in range(parent.childCount()):
                        child = parent.child(i)
                        child_path = child.data(0, Qt.ItemDataRole.UserRole)
                        if child_path == new_file_path:
                            return child
                        result = find_new_file(child)
                        if result:
                            return result
                    return None
                
                new_file_item = find_new_file(root_item)
                if new_file_item:
                    self.treeWidget.setCurrentItem(new_file_item)
                    # 开始编辑文件名称
                    self.treeWidget.editItem(new_file_item, 0)
            
            # 打开新文件
            self.tabInterface.addEditorTab(new_file_path)
        except Exception as e:
            print(f"创建文件时出错: {e}")
    
    def onItemChanged(self, item, column):
        """ 处理树形组件项目重命名事件 """
        if column != 0:
            return
        
        # 获取旧路径和新名称
        old_path = item.data(0, Qt.ItemDataRole.UserRole)
        new_name = item.text(0)
        
        if not old_path or not new_name:
            return
        
        # 生成新路径
        directory = os.path.dirname(old_path)
        new_path = os.path.join(directory, new_name)
        
        # 检查新路径是否已存在
        if os.path.exists(new_path):
            # 恢复旧名称
            old_name = os.path.basename(old_path)
            item.setText(0, old_name)
            # print(f"重命名失败: {new_name} 已存在")
            return
        
        try:
            # 重命名文件或文件夹
            os.rename(old_path, new_path)
            print(f"已重命名: {old_path} → {new_path}")
            
            # 更新节点的路径数据
            item.setData(0, Qt.ItemDataRole.UserRole, new_path)
            
            # 重新加载文件树
            self.loadFiles(self.root_directory)
        except Exception as e:
            # 恢复旧名称
            old_name = os.path.basename(old_path)
            item.setText(0, old_name)
            print(f"重命名失败: {e}")
        
    def onLoadFinished(self, ok):
        # 此方法不再需要，因为每个编辑器标签页都有自己的onLoadFinished
        pass
    
    def setLightTheme(self):
        """ 设置浅色主题 """
        self.setTheme(False)

    def setDarkTheme(self):
        """ 设置深色主题 """
        self.setTheme(True)
        
    def setTheme(self, dark):
        """ 设置所有编辑器主题 """
        self._is_dark_theme = dark
        self.tabInterface.setTheme(dark)
    
    def onThemeColorChanged(self):
        """ 主题颜色变化时的处理方法 """
        # 重新加载文件树，更新图标颜色
        self.loadFiles()
    
    def getCode(self):
        """ 获取编辑器内容 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            return current_editor.getCode()
        return ""
    
    def setCode(self, code):
        """ 设置编辑器内容 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.setCode(code)
    
    def setLanguage(self, language):
        """ 设置编辑器语言 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.webView.page().runJavaScript(f'setLanguage({repr(language)})')

    def _run_js(self, js_code):
        """ 在当前编辑器中执行 JavaScript 代码

        Args:
            js_code: 要执行的 JavaScript 代码字符串
        """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            # 先确保 WebView 有焦点
            current_editor.webView.setFocus()
            current_editor.webView.page().runJavaScript(js_code)

    def find(self):
        """ 搜索功能 - 调用 Monaco Editor 的 actions.find """
        self._run_js('find()')

    def replace(self):
        """ 替换功能 - 调用 Monaco Editor 的 startFindReplaceAction """
        self._run_js('find(null, true)')

    def cut(self):
        """ 剪切功能 """
        self._run_js('cutText()')

    def copy(self):
        """ 复制功能 """
        self._run_js('copyText()')

    def paste(self):
        """ 粘贴功能 - 通过 Qt 剪贴板读取文本，绕过浏览器安全限制 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            # 从 Qt 剪贴板读取文本
            clipboard = QApplication.clipboard()
            text = clipboard.text()
            if text:
                # 转义为 JS 安全字符串，通过 Monaco API 插入文本
                escaped = json.dumps(text)
                current_editor.webView.setFocus()
                current_editor.webView.page().runJavaScript(f'insertText({escaped})')
            else:
                # 剪贴板没有文本时，尝试图片或其他格式
                current_editor.webView.setFocus()
                current_editor.webView.page().runJavaScript('pasteText()')

    def undo(self):
        """ 撤销功能 """
        self._run_js('undoAction()')

    def redo(self):
        """ 重做功能 """
        self._run_js('redoAction()')

    def zoomIn(self):
        """ 放大字体 """
        self._run_js('zoomInAction()')

    def zoomOut(self):
        """ 缩小字体 """
        self._run_js('zoomOutAction()')

    def setMinimapEnabled(self, enabled):
        """ 配置小地图 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.webView.page().runJavaScript(f'setMinimapEnabled({str(enabled).lower()})')
    
    def setFontSize(self, size):
        """ 配置字体大小 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.webView.page().runJavaScript(f'setFontSize({size})')
    
    def setFoldingEnabled(self, enabled):
        """ 配置代码折叠 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.webView.page().runJavaScript(f'setFoldingEnabled({str(enabled).lower()})')
    
    def setFormatOnPaste(self, enabled):
        """ 配置粘贴时格式化代码 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.webView.page().runJavaScript(f'setFormatOnPaste({str(enabled).lower()})')

    def setWordWrap(self, enabled):
        """ 配置自动换行 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.webView.page().runJavaScript(f'setWordWrap({str(enabled).lower()})')

    def setLineNumbers(self, enabled):
        """ 配置行号 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.webView.page().runJavaScript(f'setLineNumbers({str(enabled).lower()})')

    def setBracketColorization(self, enabled):
        """ 配置括号对着色 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.webView.page().runJavaScript(f'setBracketColorization({str(enabled).lower()})')

    def setRenderWhitespace(self, enabled):
        """ 配置渲染空白字符 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.webView.page().runJavaScript(f'setRenderWhitespace({str(enabled).lower()})')

    def setTabSize(self, size):
        """ 配置 Tab 大小 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.webView.page().runJavaScript(f'setTabSize({size})')
    
    def setLightThemeForAll(self):
        """ 为所有编辑器设置浅色主题 """
        self.setTheme(False)

    def setDarkThemeForAll(self):
        """ 为所有编辑器设置深色主题 """
        self.setTheme(True)
    
    def setMinimapEnabledForAll(self, enabled):
        """ 为所有编辑器配置小地图 """
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget and hasattr(widget, 'webView'):
                widget.webView.page().runJavaScript(f'setMinimapEnabled({str(enabled).lower()})')
    
    def setFoldingEnabledForAll(self, enabled):
        """ 为所有编辑器配置代码折叠 """
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget and hasattr(widget, 'webView'):
                widget.webView.page().runJavaScript(f'setFoldingEnabled({str(enabled).lower()})')
    
    def setFormatOnPasteForAll(self, enabled):
        """ 为所有编辑器配置粘贴时格式化代码 """
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget and hasattr(widget, 'webView'):
                widget.webView.page().runJavaScript(f'setFormatOnPaste({str(enabled).lower()})')

    def setWordWrapForAll(self, enabled):
        """ 为所有编辑器配置自动换行 """
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget and hasattr(widget, 'webView'):
                widget.webView.page().runJavaScript(f'setWordWrap({str(enabled).lower()})')

    def setLineNumbersForAll(self, enabled):
        """ 为所有编辑器配置行号 """
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget and hasattr(widget, 'webView'):
                widget.webView.page().runJavaScript(f'setLineNumbers({str(enabled).lower()})')

    def setBracketColorizationForAll(self, enabled):
        """ 为所有编辑器配置括号对着色 """
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget and hasattr(widget, 'webView'):
                widget.webView.page().runJavaScript(f'setBracketColorization({str(enabled).lower()})')

    def setRenderWhitespaceForAll(self, enabled):
        """ 为所有编辑器配置渲染空白字符 """
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget and hasattr(widget, 'webView'):
                widget.webView.page().runJavaScript(f'setRenderWhitespace({str(enabled).lower()})')

    def setTabSizeForAll(self, size):
        """ 为所有编辑器配置 Tab 大小 """
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget and hasattr(widget, 'webView'):
                widget.webView.page().runJavaScript(f'setTabSize({size})')
    
    def setFontSizeForAll(self, size):
        """ 为所有编辑器配置字体大小 """
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget and hasattr(widget, 'webView'):
                widget.webView.page().runJavaScript(f'setFontSize({size})')
    
    def saveAllFiles(self):
        """ 保存所有打开的文件 """
        saved_count = 0
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget and hasattr(widget, 'save'):
                if widget.save():
                    saved_count += 1
        # print(f"已保存 {saved_count} 个文件")
    
    def dispose(self):
        """ 清理资源 """
        # 清理所有编辑器标签页
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if widget:
                widget.webView.page().runJavaScript('dispose()')
                widget.webView.deleteLater()
                widget.deleteLater()
        self.deleteLater()
    
    def loadFile(self, file_path):
        """ 加载文件内容到编辑器 """
        # 使用TabInterface打开文件
        self.tabInterface.addEditorTab(file_path)
        self.setWindowTitle(f"代码编辑器 - {os.path.basename(file_path)}")
    
    def saveFile(self):
        """ 保存当前编辑器内容到文件 """
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor:
            current_editor.save()
        else:
            # print("没有打开的文件") 
            return

    def runCurrentFile(self):
        """ 运行当前 Python 文件（使用当前 Python 解释器） """
        self.tabInterface.runPython(sys.executable)
    
        
    def newFile(self):
        """ 在当前选中节点下创建新的Python文件 """
        # 获取当前选中的节点
        current_item = self.treeWidget.currentItem()
        if not current_item:
            # print("请先选中一个目录或文件")
            return
        
        # 确定新建文件的目录
        item_path = current_item.data(0, Qt.ItemDataRole.UserRole)
        if os.path.isfile(item_path):
            # 如果选中的是文件，使用文件所在目录
            directory = os.path.dirname(item_path)
        else:
            # 如果选中的是目录，使用该目录
            directory = item_path
        
        # 生成新文件名
        new_file_name = "new_file.py"
        counter = 1
        while os.path.exists(os.path.join(directory, new_file_name)):
            new_file_name = f"new_file_{counter}.py"
            counter += 1
        
        # 创建新文件
        new_file_path = os.path.join(directory, new_file_name)
        try:
            with open(new_file_path, 'w', encoding='utf-8') as f:
                f.write("")
            # print(f"新文件已创建: {new_file_path}")
            
            # 重新加载文件树
            self.loadFiles()
            
            # 打开新文件
            self.tabInterface.addEditorTab(new_file_path)
        except Exception as e:
            print(f"创建文件时出错: {e}")
    
    def changeTerminalDirectory(self, directory: str, delay_ms: int = 500):
        """切换终端目录到指定路径（延迟执行以确保终端就绪）"""
        if hasattr(self, 'main_window') and self.main_window:
            if hasattr(self.main_window, 'get_terminal'):
                terminal = self.main_window.get_terminal()
                if terminal and hasattr(terminal, 'sendData'):
                    # 延迟发送 cd 命令，确保终端 shell 已就绪
                    def _send_cd():
                        try:
                            terminal.sendData(f'cd "{directory}"\r')
                            # print(f"终端已切换到: {directory}")
                        except Exception as ex:
                            print(f"终端切换目录失败: {ex}")
                    QTimer.singleShot(delay_ms, _send_cd)
                #else:
                    # print(f"[changeTerminalDirectory] 终端不可用")
            #else:
                # print(f"[changeTerminalDirectory] 未找到 get_terminal 方法")
        #else:
            # print(f"[changeTerminalDirectory] main_window 不可用")

    def _on_toggle_pi_agent(self):
        """切换 Pi Agent 窗口显示/隐藏"""
        self.toggle_pi_agent.emit()

    def _on_reload_pi_agent(self):
        """重新加载 Pi Agent 页面（仅刷新页面，不重启服务）"""
        self.reload_pi_agent.emit()

    def _on_reload_pi_service(self):
        """完全重启 pi-agent-web 服务"""
        self.reload_pi_service.emit()

    def _on_run_backtest(self):
        """运行当前标签页的 .py 文件作为回测策略"""
        self.run_backtest.emit()

    # ── Quick AI ──────────────────────────────────────────────

    @property
    def has_open_file(self) -> bool:
        """当前代码编辑器是否有打开的文件"""
        editor = self.tabInterface.getCurrentEditor()
        return editor is not None and bool(getattr(editor, 'file_path', None))

    def _update_quick_ai_button(self):
        """根据是否有打开的文件，更新快速 AI 按钮和快捷键的可用状态"""
        if hasattr(self, '_quick_ai_action'):
            self._quick_ai_action.setEnabled(self.has_open_file)

    def _on_quick_ai(self):
        """打开 Quick AI 对话框，通过隐藏的 PiAgentWindow 页面与 pi-agent-web 对话"""
        if not self.has_open_file:
            InfoBar.warning(
                "提示", "请先打开一个文件后再使用 Quick AI",
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self,
            ).show()
            return

        # 检查 Pi Agent 是否已加载
        from .pi_agent_window import get_active_pi_agent
        pi_agent = get_active_pi_agent()
        if not pi_agent or not pi_agent.is_page_loaded:
            InfoBar.warning(
                "提示", "Pi Agent 服务未启动，请先点击工具栏「Pi Agent」按钮完成连接后重试",
                duration=4000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self,
            ).show()
            return

        current_editor = self.tabInterface.getCurrentEditor()
        file_path = current_editor.file_path
        file_content = current_editor.getCode()
        file_dir = os.path.dirname(file_path)

        dlg = QuickAIDialog(
            file_path=file_path,
            file_content=file_content,
            cwd=file_dir,
            is_dark=self._is_dark_theme,
            parent=self.window(),
        )
        # 相对于代码编辑器居中定位
        editor_rect = self.rect()
        editor_top_left = self.mapToGlobal(editor_rect.topLeft())
        editor_center = editor_top_left + QPoint(
            editor_rect.width() // 2, editor_rect.height() // 2,
        )
        dlg.move(editor_center - QPoint(dlg.width() // 2, dlg.height() // 2))

        if dlg.exec() == dlg.DialogCode.Accepted:
            # AI 处理成功：刷新当前编辑器内容
            current_editor.reloadContent()
            InfoBar.success(
                "Quick AI", f"已更新: {os.path.basename(file_path)}",
                duration=3000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self,
            ).show()

    def _show_pi_agent_help(self):
        """显示 Pi Agent Web 环境配置帮助对话框"""
        from .pi_agent_window import PiAgentWindow
        from qfluentwidgets import TitleLabel, PrimaryPushButton, isDarkTheme as _is_dark
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit
        from PyQt6.QtGui import QFont

        guide_text = PiAgentWindow.get_setup_guide()
        dark = _is_dark()

        dialog = QDialog(self)
        dialog.setWindowTitle("Pi Agent Web 环境配置指引")
        dialog.resize(700, 540)
        dialog.setMinimumWidth(500)

        if dark:
            dialog.setStyleSheet("QDialog { background: #1E1E1E; }")
        else:
            dialog.setStyleSheet("QDialog { background: #FFFFFF; }")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title_label = TitleLabel("Pi Agent Web 环境配置指引", dialog)
        layout.addWidget(title_label)

        text_edit = QTextEdit(dialog)
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 10))
        text_edit.setPlainText(guide_text)
        if dark:
            text_edit.setStyleSheet(
                "QTextEdit { background: #252526; color: #D4D4D4; border: 1px solid #3E3E3E; "
                "border-radius: 6px; padding: 8px; }"
            )
        else:
            text_edit.setStyleSheet(
                "QTextEdit { background: #F5F5F5; color: #333333; border: 1px solid #D0D0D0; "
                "border-radius: 6px; padding: 8px; }"
            )
        layout.addWidget(text_edit, stretch=1)

        close_btn = PrimaryPushButton("确定", dialog)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        dialog.exec()

    def refreshFileTree(self):
        """刷新当前文件树（重新加载当前文件夹，不清除已打开的标签页）"""
        if hasattr(self, 'root_directory') and self.root_directory:
            # 重新加载文件树（保留标签页不关闭）
            self.loadFiles(self.root_directory)

    def syncToFolder(self, folder_path):
        """同步文件树到指定文件夹（无需弹窗）"""
        folder_path = os.path.normpath(os.path.normcase(folder_path))
        if not os.path.isdir(folder_path):
            return
        # 如果已经是同一个文件夹，跳过
        current = getattr(self, 'root_directory', '')
        if current and os.path.normpath(os.path.normcase(current)) == folder_path:
            return
        # 1. 仅保存切换前的路径设置
        self._saveCurrentFolderState()
        # 2. 保存并关闭所有标签页
        self.saveAllFiles()
        while self.tabInterface.stackedWidget.count() > 0:
            self.tabInterface.removeTab(0)
        # 3. 切换并加载（loadFiles 内部会从 config 恢复 open_files）
        self.root_directory = folder_path
        self.loadFiles(folder_path)
        # 通知 pi-web 同步文件夹
        self.folder_changed.emit(folder_path)

    def openFolder(self):
        """ 打开文件夹，重新加载文件树 """
        selected_folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if selected_folder:
            # 1. 仅保存切换前的路径设置
            self._saveCurrentFolderState()

            # 2. 保存并关闭所有标签页
            self.saveAllFiles()
            while self.tabInterface.stackedWidget.count() > 0:
                self.tabInterface.removeTab(0)

            # 3. 切换并加载（loadFiles 内部会从 config 恢复 open_files）
            self.root_directory = selected_folder
            self.loadFiles(selected_folder)

            # 4. 同步切换终端目录
            self.changeTerminalDirectory(selected_folder)
            # 通知 pi-web 同步文件夹
            self.folder_changed.emit(selected_folder)

    def _saveCurrentFolderState(self):
        """保存当前文件夹的编辑器状态到 file_config.json"""
        current_dir = self._getCurrentRootPath()
        if not current_dir:
            return
        open_files = self._getOpenFiles()
        active_file = ''
        current_editor = self.tabInterface.getCurrentEditor()
        if current_editor and hasattr(current_editor, 'file_path'):
            active_file = current_editor.file_path
        self.file_config.set_folder_state(current_dir, open_files, active_file)

    def _getCurrentRootPath(self):
        """获取当前树形视图的根路径"""
        if self.treeWidget.topLevelItemCount() > 0:
            root_item = self.treeWidget.topLevelItem(0)
            return root_item.data(0, Qt.ItemDataRole.UserRole) or ''
        return ''

    def _getOpenFiles(self):
        """获取所有打开的文件路径"""
        open_files = []
        for i in range(self.tabInterface.stackedWidget.count()):
            widget = self.tabInterface.stackedWidget.widget(i)
            if hasattr(widget, 'file_path') and widget.file_path:
                open_files.append(widget.file_path)
        return open_files
    
    def activate_chat_window(self):
        """ 激活聊天窗口 """
        # 关闭之前的聊天窗口（如果存在）
        if hasattr(self, 'chat_window') and self.chat_window:
            try:
                self.chat_window.close()
            except:
                pass
        
        # 创建新的聊天窗口
        self.chat_window = ChatWindow(self.tabInterface.stackedWidget.currentWidget(),self.main_window)
        # 连接聊天窗口的信号
        self.chat_window.message_sent.connect(self.on_chat_message_sent)
        
        # 连接 ClawAIWindow 的信号
        if hasattr(self.main_window, 'clawAIInterface'):
            claw_ai_window = self.main_window.clawAIInterface
            if hasattr(claw_ai_window, 'ai_response_received'):
                # 断开旧的连接，避免重复连接
                try:
                    claw_ai_window.ai_response_received.disconnect(self.on_ai_response_received)
                except:
                    pass
                # 连接新的信号
                claw_ai_window.ai_response_received.connect(self.on_ai_response_received)
        
        # 显示聊天窗口
        self.chat_window.show()
        self.chat_window.raise_()
        self.chat_window.activateWindow()
        # 设置聊天窗口位置为TabInterface高度一半
        tab_interface_height = self.tabInterface.height()
        self.chat_window.move(0, tab_interface_height // 2)
    
    def on_chat_message_sent(self, message: str):
        """ 处理聊天窗口发送的消息 """
        if not message:
            # 关闭聊天窗口
            if self.chat_window:
                self.chat_window.close()
                self.chat_window = None
            return
        # 获取当前编辑器的内容
        current_editor = self.tabInterface.getCurrentEditor()
        if not current_editor:
            # print("没有打开的编辑器")
            return
        
        # 获取当前文件路径和内容
        file_path = current_editor.file_path
        file_content = current_editor.getCode()
        cont_text="""
        并按如下要求进行规范：
        1，如果聊天内容中涉及代码方面的需求，需要根据用户的需求生成对应的代码，并完善注释。
        2，代码需要符合Python语法规范。
        3，代码需要符合Python的PEP8规范。
        4，并用```python```包裹你的代码块。
        5，代码必须以用户的文件内容为基础进行修改以满足用户的需求。
        6，原始代码必须保留，被修改的代码注释掉，注释中包含修改的原因，然后才进行修改。
        """
        # 拼接消息：文件内容 + 聊天内容 + 规范要求
        full_message = f"文件路径: {file_path}\n\n文件内容:\n{file_content}\n\n聊天内容:\n{message}\n\n{cont_text}"
        
        # 关闭聊天窗口
        # if self.chat_window:
        #     self.chat_window.close()
        #     self.chat_window = None
        # print(full_message)
        # 调用 ClawAIWindow 来处理消息
        if hasattr(self.main_window, 'clawAIInterface'):
            claw_ai_window = self.main_window.clawAIInterface
            claw_ai_window.chat_with_ai(full_message, partial(self.on_ai_response_received,file_content=file_content))
        else:
            # print("主窗口中没有 ClawAIInterface")
            return
    
        
    def on_ai_response_received(self, response: str,file_content:str):
        """ 接收 AI 模型的响应 """
        # 将响应写入当前编辑器
        if 'error' in response:
            InfoBar.warning(
                '更新提示',
                '更新失败',
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self
            )
            # 关闭聊天窗口
            if hasattr(self, 'chat_window') and self.chat_window:
                self.chat_window.close()
            return f"错误：{response.get('error', '未知错误')}"
        else:
            # 提取用```python```包裹的代码块
            import re
            code_match = re.search(r'```python\n(.*?)\n```', response, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
                self.setCode(code)
                # print(code)
                # print("设置代码成功")
            else:
                # 如果没有找到代码块，使用整个响应内容
                self.setCode(f"{file_content}\n\n{response.strip()}")
            # 关闭聊天窗口
            if hasattr(self, 'chat_window') and self.chat_window:
                # 关闭窗口
                self.chat_window.close()
        
    
    def closeEvent(self, event):
        """ 关闭窗口时清理资源（状态保存由 MainWindow.closeEvent 负责）"""
        # 关闭聊天窗口
        if self.chat_window:
            self.chat_window.close()
        self.dispose()
        super().closeEvent(event)
