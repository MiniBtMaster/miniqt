# coding:utf-8
import os
import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QHBoxLayout, QPushButton
from PyQt6.QtCore import QProcess, QUrl, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from qfluentwidgets import TitleLabel, FluentIcon, PushButton


class JupyterLabWindow(QWidget):
    """ 基于WebEngine的JupyterLab窗口 """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("JupyterLabWindow")
        self.setWindowTitle("JupyterLab")
        
        # 初始化布局
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(10, 10, 10, 10)
        
        # 创建加载状态标签
        self.statusLabel = QLabel("正在启动JupyterLab服务器...", self)
        
        # 创建进度条
        self.progressBar = QProgressBar(self)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        
        # 创建WebEngine视图
        self.webView = QWebEngineView(self)
        # 配置WebEngineView，确保能够正确显示JupyterLab
        settings = self.webView.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, True)  # 可选
        # 允许跨域请求（重要）
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        # 布局设置
        self.mainLayout.addWidget(self.statusLabel)
        self.mainLayout.addWidget(self.progressBar)
        self.mainLayout.addWidget(self.webView)
        
        # 隐藏WebView，直到服务器启动
        self.webView.hide()
        
        # 初始化服务器进程
        self.serverProcess = None
        self.serverUrl = None
        
        # 启动JupyterLab服务器
        self.startJupyterLabServer()
        
        self.jupyterReady = False
        
        # 连接URL变化信号，用于处理JavaScript回调
        self.webView.urlChanged.connect(self.onUrlChanged)
    
    def startJupyterLabServer(self):
        """ 启动JupyterLab服务器 """
        # 检查jupyter是否已安装
        import subprocess
        import sys
        
        # print("检查Jupyter安装情况...")
        # print(f"Python可执行文件: {sys.executable}")
        
        # 尝试使用python -m jupyter来启动
        try:
            result = subprocess.run([sys.executable, "-m", "jupyter", "--version"], 
                                  capture_output=True, text=True, timeout=5)
            # print(f"Jupyter版本检查输出: {result.stdout}")
            if result.returncode == 0:
                # print("Jupyter已安装")
                
                # 安装必要的扩展
                # print("安装必要的JupyterLab扩展...")
                try:
                    # 安装jupyter-matplotlib扩展
                    subprocess.run([sys.executable, "-m", "pip", "install", "jupyter-matplotlib"], 
                                  capture_output=True, text=True, timeout=30)
                    print("jupyter-matplotlib安装成功")
                except Exception as e:
                    print(f"安装扩展时出错: {str(e)}")
            else:
                print(f"Jupyter版本检查失败: {result.stderr}")
        except Exception as e:
            print(f"检查Jupyter安装时出错: {str(e)}")
        
        # 创建服务器进程
        self.serverProcess = QProcess(self)
        self.serverProcess.readyReadStandardOutput.connect(self.onServerOutput)
        self.serverProcess.readyReadStandardError.connect(self.onServerError)
        self.serverProcess.finished.connect(self.onServerFinished)
        
        # 启动JupyterLab服务器，不打开浏览器
        print("开始启动JupyterLab服务器...")
        # 使用python -m jupyter来启动，避免PATH问题
        self.serverProcess.start(sys.executable, [
            "-m", "jupyter", "lab",
            "--no-browser",
            "--port=8888",
            "--NotebookApp.allow_origin='*'",
            "--NotebookApp.disable_check_xsrf=True"  # 可选，有时可避免跨站问题
        ])
        # 检查进程是否成功启动
        if not self.serverProcess.waitForStarted(5000):
            error = "无法启动JupyterLab服务器，请检查是否已安装jupyter"
            print(error)
            self.statusLabel.setText(error)
            self.progressBar.hide()
            return
        
        print("JupyterLab服务器进程已启动")
        
        # 设置进度条更新定时器
        self.progressTimer = QTimer(self)
        self.progressTimer.timeout.connect(self.updateProgress)
        self.progressTimer.start(100)
        self.progressValue = 0
        
        # 设置超时定时器，防止服务器启动时间过长
        self.timeoutTimer = QTimer(self)
        self.timeoutTimer.setSingleShot(True)
        self.timeoutTimer.timeout.connect(self.onServerTimeout)
        self.timeoutTimer.start(30000)  # 30秒超时
    
    def updateProgress(self):
        """ 更新进度条 """
        self.progressValue += 5
        if self.progressValue > 95:
            self.progressValue = 95
        self.progressBar.setValue(self.progressValue)
    
    def onServerOutput(self):
        """ 处理服务器输出 """
        output = self.serverProcess.readAllStandardOutput().data().decode()
        
        # 过滤掉不必要的输出
        lines = output.split('\n')
        filtered_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 只保留重要信息
            if any(keyword in line for keyword in ['http://', 'https://', 'Control-C', 'To access the server', 'server started', 'ServerApp']):
                filtered_lines.append(line)
        
        if filtered_lines:
            filtered_output = ' '.join(filtered_lines)
            print(f"JupyterLab服务器输出: {filtered_output}")
            
            # 显示服务器输出到状态标签
            if len(filtered_output) > 100:
                filtered_output = filtered_output[:100] + "..."
            self.statusLabel.setText(f"服务器启动中: {filtered_output}")
        
        # 查找服务器URL，支持不同端口
        match = re.search(r'http://(localhost|127\.0\.0\.1):(\d+)/lab\?token=([a-f0-9]+)', output)
        if match:
            host = match.group(1)
            port = match.group(2)
            token = match.group(3)
            self.serverUrl = f"http://{host}:{port}/lab?token={token}"
            print(f"JupyterLab服务器URL: {self.serverUrl}")
            
            # 加载JupyterLab界面
            self.loadJupyterLab()
    
    def onServerError(self):
        """ 处理服务器 stderr 输出（JupyterLab 默认输出到 stderr，不一定是错误）"""
        try:
            data = self.serverProcess.readAllStandardError().data()
            if not data:
                return
            error = data.decode('utf-8', errors='replace')
        except Exception as e:
            print(f"处理服务器输出时出错: {str(e)}")
            return

        # 检查 stderr 中是否包含服务器 URL（JupyterLab 常输出到 stderr）
        match = re.search(r'http://(localhost|127\.0\.0\.1):(\d+)/lab\?token=([a-f0-9]+)', error)
        if match and not self.serverUrl:
            host = match.group(1)
            port = match.group(2)
            token = match.group(3)
            self.serverUrl = f"http://{host}:{port}/lab?token={token}"
            print(f"服务器就绪，URL: {self.serverUrl}")
            self.loadJupyterLab()
            return

        # 如果已经成功加载，忽略后续 stderr 输出
        if self.serverUrl:
            return

        # 检查是否有真正的错误（[E]rror 或 [C]ritical 级别）
        has_real_error = any(
            re.search(r'^\[[EC]', line.strip())
            for line in error.split('\n') if line.strip()
        )

        # 过滤输出用于日志
        lines = error.split('\n')
        important_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            level_match = re.match(r'^\[([IWEC])\]', line)
            if level_match:
                level = level_match.group(1)
                if level in ('I', 'W'):
                    # 只打印不显示
                    if level == 'W' or 'npm' in line.lower():
                        print(f"JupyterLab: {line[:120]}")
                    important_lines.append(line)
            elif any(kw in line.lower() for kw in ['error', 'fail', 'traceback']):
                important_lines.append(line)

        if has_real_error:
            print(f"JupyterLab 错误: {error[:200]}")
            self.statusLabel.setText("服务器启动失败，请检查 Jupyter 安装")
            # 停止进度条
            if hasattr(self, 'progressTimer'):
                self.progressTimer.stop()
            if hasattr(self, 'timeoutTimer'):
                self.timeoutTimer.stop()
            self.progressBar.hide()
    
    def onServerFinished(self, exitCode, exitStatus):
        """ 处理服务器结束 """
        print(f"JupyterLab服务器结束，退出码: {exitCode}")
        self.statusLabel.setText("JupyterLab服务器已关闭")
    
    def onServerTimeout(self):
        """ 处理服务器启动超时 """
        print("JupyterLab服务器启动超时")
        self.statusLabel.setText("服务器启动超时，请检查网络连接或尝试重新启动")
        self.progressBar.hide()
        
        # 终止服务器进程
        if self.serverProcess and self.serverProcess.state() == QProcess.ProcessState.Running:
            self.serverProcess.terminate()
            self.serverProcess.waitForFinished(1000)
    
    def loadJupyterLab(self):
        """ 加载JupyterLab界面 """
        if self.serverUrl:
            print(f"加载JupyterLab界面: {self.serverUrl}")
            # 停止进度条更新
            if hasattr(self, 'progressTimer'):
                self.progressTimer.stop()
            self.progressBar.setValue(100)
            
            # 停止超时定时器
            if hasattr(self, 'timeoutTimer'):
                self.timeoutTimer.stop()
            
            # 清除状态标签文本并隐藏
            self.statusLabel.setText("")
            self.statusLabel.hide()
            self.progressBar.hide()
            
            # 设置用户代理
            profile = self.webView.page().profile()
            profile.setHttpUserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # 先连接信号，再设置URL，最后显示
            self.webView.loadFinished.connect(self.onPageLoadFinished)
            self.webView.setUrl(QUrl(self.serverUrl))
            self.webView.show()
            print("WebView已显示")
            
    def onPageLoadFinished(self, ok):
        if ok:
            # 注入错误捕获脚本
            error_js = """
            window.onerror = function(message, source, lineno, colno, error) {
                console.log('JS Error: ' + message + ' at ' + source + ':' + lineno);
            };
            """
            self.webView.page().runJavaScript(error_js)
            
            # 延迟执行，确保JupyterLab完全加载
            QTimer.singleShot(2000, self.initializeJupyterLab)
            
            QTimer.singleShot(3000, self.checkMenuBar)  # 3秒后检查菜单栏
    
    def initializeJupyterLab(self):
        """ 初始化JupyterLab相关功能 """
        # 注入检测 JupyterLab 应用就绪的脚本
        check_js = """
        if (window.jupyterapp) {
            document.dispatchEvent(new Event('jupyter-ready'));
        } else {
            var observer = new MutationObserver(function(mutations) {
                if (window.jupyterapp) {
                    document.dispatchEvent(new Event('jupyter-ready'));
                    observer.disconnect();
                }
            });
            observer.observe(document, {childList: true, subtree: true});
        }
        """
        self.webView.page().runJavaScript(check_js)
        
        # 注册Python回调
        self.registerPythonCallbacks()
        
        self.jupyterReady = True
    
    def registerPythonCallbacks(self):
        """ 注册Python回调函数 """
        js = """
        window.pycall = function(funcName, ...args) {
            console.log('调用Python函数:', funcName, args);
            // 使用自定义协议与Python通信
            document.location.href = `pycall://${funcName}?args=${JSON.stringify(args)}`;
        }
        """
        self.webView.page().runJavaScript(js)
    
    def onUrlChanged(self, url):
        """ 处理URL变化，捕获JavaScript回调 """
        url_str = url.toString()
        if url_str.startswith("pycall://"):
            # 处理回调
            import urllib.parse
            path = url_str.replace("pycall://", "")
            if "?" in path:
                func_name, query = path.split("?", 1)
                args = urllib.parse.parse_qs(query).get("args", ["[]"])[0]
                import json
                try:
                    args = json.loads(args)
                    # 可以在这里添加其他回调处理
                except Exception as e:
                    print(f"处理回调时出错: {e}")
    

    def checkMenuBar(self):
        js = """
        var menuBar = document.querySelector('#jp-main-menu');
        if (menuBar) {
            console.log('Menu bar exists');
        } else {
            console.log('Menu bar not found, forcing resize');
            window.dispatchEvent(new Event('resize'));
        }
        """
        self.webView.page().runJavaScript(js)
    
    def closeEvent(self, event):
        """ 窗口关闭时清理服务器进程 """
        if self.serverProcess:
            # 先尝试正常终止
            if self.serverProcess.state() == QProcess.ProcessState.Running:
                print("正在终止JupyterLab服务器...")
                # 先发送终止信号
                self.serverProcess.terminate()
                # 增加等待时间，确保进程有足够时间终止
                if not self.serverProcess.waitForFinished(1000):
                    print("正常终止失败，尝试强制终止...")
                    # 如果正常终止失败，强制终止
                    self.serverProcess.kill()
            # 无论进程状态如何，都确保清理
            del self.serverProcess
            print("JupyterLab服务器进程已清理")
        event.accept()
