# coding: utf-8
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from qfluentwidgets import (
    LineEdit, CheckBox, BodyLabel, TitleLabel,
    MessageBoxBase, PrimaryPushButton, InfoBar, InfoBarPosition,
    ComboBox, PushButton
)
from typing import TYPE_CHECKING

from ..common.config import cfg

if TYPE_CHECKING:
    from ..view.main_window import MainWindow

# 导入 MooTDX 服务器列表
# try:
#     from mootdx.consts import HQ_HOSTS
# except ImportError:
    # 默认服务器列表（如果 mootdx 未安装）
HQ_HOSTS = [
    ("长城国瑞电信1", "218.85.139.19", 7709),
    ("长城国瑞电信2", "218.85.139.20", 7709),
    ("长城国瑞网通", "58.23.131.163", 7709),
    ("上证云成都电信一", "218.6.170.47", 7709),
    ("上证云北京联通一", "123.125.108.14", 7709),
    ("上海电信主站Z1", "180.153.18.170", 7709),
    ("上海电信主站Z2", "180.153.18.171", 7709),
    ("上海电信主站Z80", "180.153.18.172", 80),
    ("北京联通主站Z1", "202.108.253.130", 7709),
    ("北京联通主站Z2", "202.108.253.131", 7709),
    ("北京联通主站Z80", "202.108.253.139", 80),
    ("杭州电信主站J1", "60.191.117.167", 7709),
    ("杭州电信主站J2", "115.238.56.198", 7709),
    ("杭州电信主站J3", "218.75.126.9", 7709),
    ("杭州电信主站J4", "115.238.90.165", 7709),
    ("杭州联通主站J1", "124.160.88.183", 7709),
    ("杭州联通主站J2", "60.12.136.250", 7709),
    ("杭州华数主站J1", "218.108.98.244", 7709),
    ("杭州华数主站J2", "218.108.47.69", 7709),
    ("义乌移动主站J1", "223.94.89.115", 7709),
    ("青岛联通主站W1", "218.57.11.101", 7709),
    ("青岛电信主站W1", "58.58.33.123", 7709),
    ("深圳电信主站Z1", "14.17.75.71", 7709),
    ("云行情上海电信Z1", "114.80.63.12", 7709),
    ("云行情上海电信Z2", "114.80.63.35", 7709),
    ("上海电信主站Z3", "180.153.39.51", 7709),
    ('招商证券深圳行情', '119.147.212.81', 7709),
    ('华泰证券(南京电信)', '221.231.141.60', 7709),
    ('华泰证券(上海电信)', '101.227.73.20', 7709),
    ('华泰证券(上海电信二)', '101.227.77.254', 7709),
    ('华泰证券(深圳电信)', '14.215.128.18', 7709),
    ('华泰证券(武汉电信)', '59.173.18.140', 7709),
    ('华泰证券(天津联通)', '60.28.23.80', 7709),
    ('华泰证券(沈阳联通)', '218.60.29.136', 7709),
    ('华泰证券(南京联通)', '122.192.35.44', 7709),
    ('华泰证券(南京联通)', '122.192.35.44', 7709),
    ('安信', '112.95.140.74', 7709),
    ('安信', '112.95.140.92', 7709),
    ('安信', '112.95.140.93', 7709),
    ('安信', '114.80.149.19', 7709),
    ('安信', '114.80.149.21', 7709),
    ('安信', '114.80.149.22', 7709),
    ('安信', '114.80.149.91', 7709),
    ('安信', '114.80.149.92', 7709),
    ('安信', '121.14.104.60', 7709),
    ('安信', '121.14.104.66', 7709),
    ('安信', '123.126.133.13', 7709),
    ('安信', '123.126.133.14', 7709),
    ('安信', '123.126.133.21', 7709),
    ('安信', '211.139.150.61', 7709),
    ('安信', '59.36.5.11', 7709),
    ('广发', '119.29.19.242', 7709),
    ('广发', '123.138.29.107', 7709),
    ('广发', '123.138.29.108', 7709),
    ('广发', '124.232.142.29', 7709),
    ('广发', '183.57.72.11', 7709),
    ('广发', '183.57.72.12', 7709),
    ('广发', '183.57.72.13', 7709),
    ('广发', '183.57.72.15', 7709),
    ('广发', '183.57.72.21', 7709),
    ('广发', '183.57.72.22', 7709),
    ('广发', '183.57.72.23', 7709),
    ('广发', '183.57.72.24', 7709),
    ('广发', '183.60.224.177', 7709),
    ('广发', '183.60.224.178', 7709),
    ('国泰君安', '113.105.92.100', 7709),
    ('国泰君安', '113.105.92.101', 7709),
    ('国泰君安', '113.105.92.102', 7709),
    ('国泰君安', '113.105.92.103', 7709),
    ('国泰君安', '113.105.92.104', 7709),
    ('国泰君安', '113.105.92.99', 7709),
    ('国泰君安', '117.34.114.13', 7709),
    ('国泰君安', '117.34.114.14', 7709),
    ('国泰君安', '117.34.114.15', 7709),
    ('国泰君安', '117.34.114.16', 7709),
    ('国泰君安', '117.34.114.17', 7709),
    ('国泰君安', '117.34.114.18', 7709),
    ('国泰君安', '117.34.114.20', 7709),
    ('国泰君安', '117.34.114.27', 7709),
    ('国泰君安', '117.34.114.30', 7709),
    ('国泰君安', '117.34.114.31', 7709),
    ('国信', '182.131.3.252', 7709),
    ('国信', '183.60.224.11', 7709),
    ('国信', '58.210.106.91', 7709),
    ('国信', '58.63.254.216', 7709),
    ('国信', '58.63.254.219', 7709),
    ('国信', '58.63.254.247', 7709),
    ('海通', '123.125.108.90', 7709),
    ('海通', '175.6.5.153', 7709),
    ('海通', '182.118.47.151', 7709),
    ('海通', '182.131.3.245', 7709),
    ('海通', '202.100.166.27', 7709),
    ('海通', '222.161.249.156', 7709),
    ('海通', '42.123.69.62', 7709),
    ('海通', '58.63.254.191', 7709),
    ('海通', '58.63.254.217', 7709),
    ('华林', '120.55.172.97', 7709),
    ('华林', '139.217.20.27', 7709),
    ('华林', '202.100.166.21', 7709),
    ('华林', '202.96.138.90', 7709),
    ('华林', '218.106.92.182', 7709),
    ('华林', '218.106.92.183', 7709),
    ('华林', '220.178.55.71', 7709),
    ('华林', '220.178.55.86', 7709),



]


class ServerTestThread(QThread):
    """服务器测试线程（避免UI卡顿）"""
    
    # 信号定义
    test_progress = pyqtSignal(str, str)  # (服务器名称, 测试结果)
    test_success = pyqtSignal(str, str, int)  # (服务器名称, IP, 端口)
    test_finished = pyqtSignal()  # 所有测试完成
    
    def __init__(self, servers):
        super().__init__()
        self.servers = servers
        self._stopped = False
    
    def run(self):
        """线程运行：逐个测试服务器（每个服务器最多5秒）"""
        from mootdx.quotes import Quotes
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        
        for server_name, host, port in self.servers:
            if self._stopped:
                break
            
            self.test_progress.emit(server_name, "测试中...")
            
            try:
                # 用独立线程测试，10秒超时
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._test_server, host, port)
                    result = future.result(timeout=5)
                
                if result:
                    self.test_progress.emit(server_name, "✅ 可用")
                    self.test_success.emit(server_name, host, port)
                    self._stopped = True
                    break
                else:
                    self.test_progress.emit(server_name, "❌ 失败")
                    
            except TimeoutError:
                self.test_progress.emit(server_name, "⏱ 超时")
            except Exception as e:
                self.test_progress.emit(server_name, f"❌ 失败")
        
        self.test_finished.emit()
    
    @staticmethod
    def _test_server(host: str, port: int) -> bool:
        """测试单个服务器是否可用（两阶段验证，10秒超时由外层控制）"""
        from mootdx.quotes import Quotes
        
        client = Quotes.factory(
            market='std',
            server=(host, port),
            bestip=False,
            heartbeat=False,
            timeout=5
        )
        # 一阶段：基础连通性检查
        count = client.stock_count(market=1)  # 上交所
        if not isinstance(count, int) or count <= 0:
            return False
        
        # 二阶段：真实数据请求验证（stock_count 成功不代表能正常服务数据）
        try:
            test_data = client.bars(symbol='601988', frequency='day', offset=10)
            if test_data is None or len(test_data) == 0:
                return False
        except Exception:
            return False
        
        return True
    
    def stop(self):
        """停止测试"""
        self._stopped = True


class StockLoginThread(QThread):
    """股票登录后台线程（避免连接超时阻塞 UI）"""

    login_progress = pyqtSignal(str)     # 进度消息
    login_success = pyqtSignal(object)   # StockApi 实例
    login_failed = pyqtSignal(str)       # 错误消息

    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port

    def run(self):
        """后台执行：创建 StockApi → 连接 → 两阶段验证"""
        from ..common.stock_api import StockApi

        stock_api = None
        try:
            # 创建并连接
            self.login_progress.emit("正在创建客户端...")
            stock_api = StockApi(fast_init=True, host=self.host, port=self.port)
            stock_api._init_client()

            if not stock_api._initialized or stock_api._client is None:
                raise Exception("MooTDX 客户端初始化失败")

            # 一阶段：基础连通性检查
            self.login_progress.emit("正在验证服务器连通性...")
            count = stock_api._client.stock_count(market=1)
            if not isinstance(count, int) or count <= 0:
                raise Exception("stock_count 返回无效")

            # 二阶段：真实数据验证
            self.login_progress.emit("正在获取行情数据...")
            test_data = stock_api._client.bars(symbol='601988', frequency='day', offset=10)
            if test_data is None or len(test_data) == 0:
                raise Exception("bars 返回空数据")

        except Exception as e:
            print(f"[StockLoginThread] 连接验证失败: {e}")
            if stock_api:
                try:
                    stock_api.close()
                except Exception:
                    pass
            self.login_failed.emit(str(e))
            return

        # 验证通过
        self.login_success.emit(stock_api)


class LoginWindow(MessageBoxBase):
    """登录窗口"""

    def __init__(self, parent=None, is_stock=False):
        super().__init__(parent)
        self.main_window: "MainWindow" = parent
        self.is_stock = is_stock
        self.selected_host = None
        self.selected_port = None
        self._login_thread = None
        self.initUI()
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, False)

    def initUI(self):
        """初始化UI"""
        self.titleLabel = TitleLabel("Mini Quant Trader", self)
        self.viewLayout.addWidget(self.titleLabel, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.loginTypeLabel = PrimaryPushButton("期货登录" if not self.is_stock else "股票登录", self)
        self.viewLayout.addWidget(self.loginTypeLabel, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 登录状态显示（股票和期货共用）
        self.loginStatusLabel = BodyLabel("", self)
        self.loginStatusLabel.setVisible(False)
        self.viewLayout.addWidget(self.loginStatusLabel)

        if self.is_stock:
            # 股票登录：MooTDX 数据源（已简化，移除数据源选择）
            self.subtitleLabel = BodyLabel("MooTDX 行情服务器", self)
            self.viewLayout.addWidget(self.subtitleLabel, alignment=Qt.AlignmentFlag.AlignHCenter)
            
            # 提示信息
            self.tipLabel = BodyLabel("TCP直连、低延迟、适合实时行情\n请选择服务器", self)
            self.viewLayout.addWidget(self.tipLabel)
            
            # MooTDX 服务器选择
            self.serverLabel = BodyLabel("MooTDX 服务器", self)
            self.viewLayout.addWidget(self.serverLabel)
            
            self.serverComboBox = ComboBox(self)
            server_names = [host[0] for host in HQ_HOSTS]
            self.serverComboBox.addItems(server_names)
            
            # 从配置读取上次选择的服务器
            saved_host = cfg.stockServerHost.value
            saved_port = cfg.stockServerPort.value
            default_index = 0
            if saved_host:
                for i, (name, host, port) in enumerate(HQ_HOSTS):
                    if host == saved_host and port == saved_port:
                        default_index = i
                        break
            self.serverComboBox.setCurrentIndex(default_index)
            self.viewLayout.addWidget(self.serverComboBox)
            
            # 测试服务器按钮
            self.testServerBtn = PushButton("测试服务器", self)
            self.testServerBtn.clicked.connect(self.test_servers)
            self.viewLayout.addWidget(self.testServerBtn)
            
            # 测试进度显示
            self.testProgressLabel = BodyLabel("", self)
            self.testProgressLabel.setVisible(False)
            self.viewLayout.addWidget(self.testProgressLabel)

            # 测试线程（初始为 None）
            self.test_thread = None
            
            # 隐藏用户名和密码相关控件（不添加到布局）
            self.usernameLabel = None
            self.usernameEdit = None
            self.passwordLabel = None
            self.passwordEdit = None
            self.rememberCheckBox = None
            
        else:
            # 期货登录：显示用户名和密码
            self.subtitleLabel = BodyLabel("请登录您的天勤期货账号", self)
            self.viewLayout.addWidget(self.subtitleLabel, alignment=Qt.AlignmentFlag.AlignHCenter)

            self.usernameLabel = BodyLabel("用户名", self)
            self.viewLayout.addWidget(self.usernameLabel)

            self.usernameEdit = LineEdit(self)
            self.usernameEdit.setPlaceholderText("请输入用户名")
            self.usernameEdit.setText(cfg.futuresUsername.value)
            self.viewLayout.addWidget(self.usernameEdit)

            self.passwordLabel = BodyLabel("密码", self)
            self.viewLayout.addWidget(self.passwordLabel)

            self.passwordEdit = LineEdit(self)
            self.passwordEdit.setPlaceholderText("请输入密码")
            self.passwordEdit.setEchoMode(LineEdit.EchoMode.Password)
            self.passwordEdit.returnPressed.connect(self.onLogin)
            self.viewLayout.addWidget(self.passwordEdit)

            self.rememberCheckBox = CheckBox("记住密码", self)
            self.rememberCheckBox.setChecked(cfg.futuresRememberPassword.value)
            self.viewLayout.addWidget(self.rememberCheckBox)

            if cfg.futuresRememberPassword.value:
                self.passwordEdit.setText(cfg.futuresPassword.value)

        self.yesButton.setText("登录")
        self.cancelButton.setText("取消")

        # 断开 MessageBoxBase 默认的 yesButton 处理器（否则会立即关闭对话框）
        try:
            self.yesButton.clicked.disconnect()
        except Exception:
            pass
        self.yesButton.clicked.connect(self.onLogin)

        self.widget.setMinimumWidth(400)

    def test_servers(self):
        """测试所有服务器（后台线程）"""
        if not self.is_stock:
            return
        
        # 禁用测试按钮防止重复点击
        self.testServerBtn.setEnabled(False)
        self.testServerBtn.setText("测试中...")
        
        # 显示测试进度
        self.testProgressLabel.setVisible(True)
        self.testProgressLabel.setText("正在测试服务器...")
        
        # 创建测试线程
        self.test_thread = ServerTestThread(HQ_HOSTS)
        
        # 连接信号
        self.test_thread.test_progress.connect(self.on_test_progress)
        self.test_thread.test_success.connect(self.on_test_success)
        self.test_thread.test_finished.connect(self.on_test_finished)
        
        # 启动线程
        self.test_thread.start()

    def on_test_progress(self, server_name: str, result: str):
        """处理测试进度信号"""
        self.testProgressLabel.setText(f"{server_name}: {result}")

    def on_test_success(self, server_name: str, host: str, port: int):
        """处理测试成功信号（自动选中可用服务器）"""
        # 找到服务器索引并选中
        for i, (name, h, p) in enumerate(HQ_HOSTS):
            if name == server_name and h == host and p == port:
                self.serverComboBox.setCurrentIndex(i)
                break
        
        # 显示成功提示
        self.testProgressLabel.setText(f"✅ 找到可用服务器: {server_name}")
        
        # InfoBar 提示
        InfoBar.success(
            title="服务器测试成功",
            content=f"已自动选中可用服务器: {server_name}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def on_test_finished(self):
        """处理测试完成信号"""
        # 恢复测试按钮
        self.testServerBtn.setEnabled(True)
        self.testServerBtn.setText("测试服务器")
        
        # 停止线程
        if self.test_thread:
            self.test_thread.quit()
            self.test_thread.wait()
            self.test_thread = None

    def onLogin(self):
        """登录按钮点击事件"""
        if self.is_stock:
            # 如果正在登录中，先断开当前线程
            if self._login_thread and self._login_thread.isRunning():
                self._cleanup_login()

            # 股票登录：只使用 MooTDX 数据源
            self.selected_source = 'mootdx'
            
            # 获取用户选择的服务器
            server_index = self.serverComboBox.currentIndex()
            if server_index >= 0 and server_index < len(HQ_HOSTS):
                selected_server = HQ_HOSTS[server_index]
                self.selected_host = selected_server[1]  # IP地址
                self.selected_port = selected_server[2]  # 端口
                print(f"股票登录: 数据源={self.selected_source}, 服务器={selected_server[0]}, host={self.selected_host}, port={self.selected_port}")
            else:
                # 默认使用第一个服务器
                self.selected_host = HQ_HOSTS[0][1]
                self.selected_port = HQ_HOSTS[0][2]
                print(f"股票登录: 数据源={self.selected_source}, 默认服务器, host={self.selected_host}, port={self.selected_port}")

            # 关闭旧连接：避免重复登录时残留连接导致卡死（主线程操作）
            if self.main_window:
                if self.main_window.stock_api_qtimer:
                    self.main_window.stock_api_qtimer.stop()
                    self.main_window.stock_api_qtimer = None
                if self.main_window.stock_api:
                    self.main_window.stock_api.close()
                    self.main_window.stock_api = None

            # 禁用登录按钮，显示"连接中..."
            self.yesButton.setEnabled(False)
            self.yesButton.setText("连接中...")

            # 显示登录状态标签
            self.loginStatusLabel.setVisible(True)
            self.loginStatusLabel.setText("正在连接行情服务器...")

            # 启动后台线程执行连接验证
            self._login_thread = StockLoginThread(self.selected_host, self.selected_port)
            self._login_thread.login_progress.connect(self._on_login_progress)
            self._login_thread.login_success.connect(self._on_stock_login_success)
            self._login_thread.login_failed.connect(self._on_stock_login_failed)
            self._login_thread.start()
        else:
            # 期货登录：获取用户名和密码
            self.username = self.usernameEdit.text()
            self.password = self.passwordEdit.text()

            self.hide()
            # 使用QTimer延迟执行登录，让UI有机会更新
            QTimer.singleShot(100, self.doLogin)

    def doLogin(self):
        """执行期货登录操作"""
        try:
            # 期货登录：使用天勤API
            from tqsdk import TqApi, TqAuth, TqKq

            # 创建TqApi实例（这会建立连接，需要事件循环）
            api = TqApi(
                TqKq(),
                auth=TqAuth(self.username, self.password))

            if self.main_window:
                self.main_window.tq_api = api
                self.main_window.login_status.update({"futures": True})
            
            # 保存登录信息到配置
            cfg.futuresUsername.value = self.username
            cfg.futuresRememberPassword.value = self.rememberCheckBox.isChecked()
            if self.rememberCheckBox.isChecked():
                cfg.futuresPassword.value = self.password
            else:
                cfg.futuresPassword.value = ""
            cfg.save()
            
            # 登录成功
            self.onLoginSuccess()

        except Exception as e:
            error_msg = f"登录失败: {str(e)}"
            self.onLoginFailed(error_msg)

    def _on_login_progress(self, msg: str):
        """登录进度更新（回调，主线程）"""
        self.loginStatusLabel.setText(msg)

    def _on_stock_login_success(self, stock_api):
        """股票登录验证成功（回调，主线程）"""
        from ..common.stock_api_qtimer import StockApiQTimer

        # 窗口可能已被用户关闭
        if not self.isVisible():
            try:
                stock_api.close()
            except Exception:
                pass
            self._cleanup_login()
            return

        # 保存服务器选择到配置
        cfg.stockServerHost.value = self.selected_host
        cfg.stockServerPort.value = self.selected_port
        cfg.save()

        if self.main_window:
            self.main_window.stock_api = stock_api
            # 创建并启动股票API定时器 — 这才是真正连接成功的标志
            stock_api_qtimer = StockApiQTimer(self.main_window, interval_ms=3000)
            stock_api_qtimer.set_stock_api(stock_api)
            stock_api_qtimer.start()
            self.main_window.stock_api_qtimer = stock_api_qtimer
            self.main_window.login_status.update({"stock": True})

        self._cleanup_login()

        # 登录成功
        self.onLoginSuccess()

    def _on_stock_login_failed(self, error_msg: str):
        """股票登录验证失败（回调，主线程）"""
        # 窗口可能已被用户关闭
        if not self.isVisible():
            self._cleanup_login()
            return

        self._cleanup_login()

        # 显示错误
        self.onLoginFailed("连接失败，请重新选择服务器连接")

    def _cleanup_login(self):
        """清理登录线程和恢复按钮状态"""
        if self._login_thread and self._login_thread.isRunning():
            self._login_thread.quit()
            self._login_thread.wait(1000)
        self._login_thread = None
        self.yesButton.setEnabled(True)
        self.yesButton.setText("登录")
        self.cancelButton.setEnabled(True)
        self.loginStatusLabel.setVisible(False)

    def closeEvent(self, e):
        """关闭窗口时停止登录线程"""
        self._cleanup_login()
        super().closeEvent(e)

    def reject(self):
        """取消登录时停止登录线程"""
        self._cleanup_login()
        super().reject()

    def onLoginSuccess(self):
        """登录成功处理"""
        if self.main_window and hasattr(self.main_window, 'update_cont_quotes'):
            if self.is_stock:
                InfoBar.success(
                    '登录提示',
                    '股票行情服务器连接成功',
                    duration=2000,
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self.main_window
                )
                login_status_data = {"stock": True}
            else:
                InfoBar.warning(
                    '登录提示',
                    '登录成功，正在更新合约列表',
                    duration=2000,
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self.main_window
                )
                login_status_data = {"futures": True}
            self.main_window.login_status.update(login_status_data)
            self.main_window.update_cont_quotes()

        self.accept()

    def onLoginFailed(self, error_msg):
        """登录失败处理"""
        InfoBar.warning(
            '登录提示',
            f'登录失败：{error_msg}',
            duration=10000,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self.main_window
        )
        print(error_msg)
        self.show()