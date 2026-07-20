# coding:utf-8
"""
pi-agent-web 服务管理器（共享单例）。
Quick AI 和 Pi Agent 窗口共享同一个 PiServiceManager 实例，
确保服务只启动一次，避免端口冲突。
"""

import subprocess
import sys
import time
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Optional

# pi-agent-web 默认端口
PI_WEB_PORT = 30141
PI_WEB_URL = f"http://127.0.0.1:{PI_WEB_PORT}"


def _get_pip_install_path() -> Optional[Path]:
    """通过导入 miniqt 包获取其在 site-packages 中的安装路径"""
    try:
        import miniqt as _miniqt_pkg
        p = Path(_miniqt_pkg.__file__).parent / "app" / "pi-angent-web"
        if p.is_dir() and (p / "package.json").is_file():
            return p
    except Exception:
        pass
    return None


class PiServiceManager:
    """管理 pi-agent-web 后台进程生命周期"""

    def __init__(self):
        self._pi_web_proc: Optional[subprocess.Popen] = None
        self._ready = False
        self._pi_web_dir: Optional[str] = None

    # ── 查找 ──────────────────────────────────────────────

    @staticmethod
    def find_pi_web_dir() -> Optional[str]:
        """
        查找 pi-angent-web 源码目录（pip 安装或 dev 克隆后均可用）
        miniqt/app/pi-angent-web 始终随包分发。
        """
        candidates = [
            # 方式 1: 相对当前模块的位置（dev 和 pip 都适用）
            Path(__file__).parent.parent / "pi-angent-web",
            # 方式 2: 从 miniqt 包的安装路径查找（pip 安装场景）
            _get_pip_install_path(),
            # 方式 3: cwd 下的常见开发目录
            Path.cwd() / "miniqt" / "app" / "pi-angent-web",
            Path.cwd() / "pi-angent-web",
        ]
        for p in candidates:
            if p and p.is_dir() and (p / "package.json").is_file():
                return str(p.resolve())
        return None

    # ── 依赖检查 ──────────────────────────────────────────

    def check_dependencies(self) -> tuple:
        """
        检查依赖环境，返回 (ok, msg)
        - (True, dir_path)      : 环境就绪
        - (False, "NOT_FOUND_NODE")     : 未安装 Node.js
        - (False, "NOT_FOUND")          : 未找到 pi-angent-web 目录
        - (False, "NEEDS_INSTALL")      : 找到源码但 node_modules 未安装
        """
        node_path = shutil.which("node.exe" if sys.platform == "win32" else "node")
        if not node_path:
            return False, "NOT_FOUND_NODE"

        pi_web_dir = self.find_pi_web_dir()
        if not pi_web_dir:
            return False, "NOT_FOUND"

        self._pi_web_dir = pi_web_dir

        if not os.path.isdir(os.path.join(pi_web_dir, "node_modules")):
            return False, "NEEDS_INSTALL"

        return True, pi_web_dir

    # ── 启动 / 停止 ───────────────────────────────────────

    def start(self) -> tuple:
        """
        启动 pi-agent-web 服务（非阻塞，立即返回）
        如果服务已在运行（is_ready），直接返回，不会重启。
        返回 (True, msg) 或 (False, error_msg)
        """
        if not self._pi_web_dir:
            self._pi_web_dir = self.find_pi_web_dir()
            if not self._pi_web_dir:
                return False, "未找到 pi-angent-web 目录"

        # 如果服务已在运行，直接复用
        if self.is_ready():
            print("[PiService] 服务已在运行，复用现有实例")
            return True, self._pi_web_dir

        # 如果之前的子进程还在运行，等待它就绪
        if self._pi_web_proc is not None and self._pi_web_proc.poll() is None:
            print("[PiService] 子进程仍在运行，等待就绪...")
            return True, self._pi_web_dir

        # 启动前清理端口（仅当服务确实不可达时才清理残留进程）
        self._kill_port_process()

        if not os.path.isdir(os.path.join(self._pi_web_dir, "node_modules")):
            return False, "pi-angent-web 依赖未安装"

        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            env = os.environ.copy()
            env["NEXT_PUBLIC_EMBEDDED"] = "true"

            self._pi_web_proc = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=self._pi_web_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                shell=True if sys.platform == "win32" else False,
                creationflags=creationflags,
                env=env,
            )
            print(f"[PiService] pi-agent-web 已启动, PID={self._pi_web_proc.pid}, dir={self._pi_web_dir}")
            self._start_time = time.time()
            return True, self._pi_web_dir

        except Exception as e:
            return False, f"启动失败: {e}"

    def ensure_running(self, wait_seconds: int = 60) -> tuple:
        """
        确保服务正在运行（阻塞式，适合在非 Qt 线程中调用）。
        如果服务未运行则自动启动并等待就绪。
        返回 (True, msg) 或 (False, error_msg)
        """
        # 先尝试快速连接
        if self.is_ready():
            return True, "服务已在运行"

        # 检查依赖
        ok, msg = self.check_dependencies()
        if not ok:
            return False, msg

        # 启动服务
        ok, msg = self.start()
        if not ok:
            return False, msg

        # 阻塞等待服务就绪
        waited = 0
        while waited < wait_seconds:
            if self.is_ready():
                print(f"[PiService] 服务就绪 (等待 {waited}s)")
                return True, "服务已就绪"
            time.sleep(1)
            waited += 1

        return False, f"服务启动超时（{wait_seconds}秒）"

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
            killed = set()
            for line in result.stdout.splitlines():
                if f":{PI_WEB_PORT}" in line and "LISTENING" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid in killed:
                            continue
                        killed.add(pid)
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


# ── 全局单例 ──────────────────────────────────────────────

_pi_service_instance: Optional[PiServiceManager] = None


def get_pi_service() -> PiServiceManager:
    """获取 PiServiceManager 全局单例"""
    global _pi_service_instance
    if _pi_service_instance is None:
        _pi_service_instance = PiServiceManager()
    return _pi_service_instance
