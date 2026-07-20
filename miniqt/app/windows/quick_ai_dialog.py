# coding:utf-8
"""
Quick AI 对话框：通过 JS 注入直接操作隐藏的 PiAgentWindow 页面中的
ChatInput 输入框，键入消息并触发发送。由 agent_done 信号驱动完成检测。
"""
import json

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, QPoint, QEvent
from PyQt6.QtGui import QFont

from qfluentwidgets import (
    BodyLabel, PushButton, PrimaryPushButton,
    IndeterminateProgressBar, TextEdit,
)

from .pi_agent_window import get_active_pi_agent

# ── 调试开关 ─────────────────────────────────────────────────
_DEBUG = True


def _dbg(msg: str):
    if _DEBUG:
        print(f"[QuickAI] {msg}", flush=True)


# ================================================================
# Quick AI 对话框
# ================================================================

class QuickAIDialog(QDialog):
    """
    Quick AI 对话框（无标题栏，支持拖动）
    - 打开即处于就绪状态，可直接输入对话
    - 发送时通过 JS 注入操作 PiAgentWindow 页面的 ChatInput
    - 等待 agent_done 信号自动关闭
    - 中断后回到就绪状态
    """

    def __init__(self, file_path: str, file_content: str, cwd: str,
                 is_dark: bool = False, parent=None):
        super().__init__(parent=parent)
        self._file_path = file_path
        self._file_content = file_content
        self._cwd = cwd
        self._is_dark = is_dark
        self._success = False
        self._drag_pos: QPoint | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowTitle("Quick AI")
        self.setFixedSize(480, 150)

        self._init_ui()
        self._apply_qss()
        self._input.installEventFilter(self)
        self._input.setFocus()

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            ke = event
            if ke.key() == Qt.Key.Key_Return or ke.key() == Qt.Key.Key_Enter:
                if not (ke.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self._on_send()
                    return True
        return super().eventFilter(obj, event)

    # ── UI 初始化 ─────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(8)

        self._input = TextEdit(self)
        self._input.setAcceptRichText(False)
        self._input.setPlaceholderText("输入你想要 AI 对当前文件做的修改...")
        self._input.setMaximumHeight(80)
        self._input.setMinimumHeight(60)
        self._input.setFont(QFont("Microsoft YaHei", 11))
        layout.addWidget(self._input)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        self._status_label = BodyLabel("", self)
        self._status_label.setFixedHeight(30)
        bottom_layout.addWidget(self._status_label, 1)

        self._abort_btn = PushButton("中断", self)
        self._abort_btn.setFixedSize(60, 30)
        self._abort_btn.clicked.connect(self._on_abort)
        self._abort_btn.setVisible(False)
        bottom_layout.addWidget(self._abort_btn)

        self._cancel_btn = PushButton("取消", self)
        self._cancel_btn.setFixedSize(60, 30)
        self._cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self._cancel_btn)

        self._send_btn = PrimaryPushButton("发送", self)
        self._send_btn.setFixedSize(60, 30)
        self._send_btn.setDefault(True)
        self._send_btn.clicked.connect(self._on_send)
        bottom_layout.addWidget(self._send_btn)

        layout.addLayout(bottom_layout)

        self._progress = IndeterminateProgressBar(self)
        self._progress.setFixedHeight(6)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

    def _apply_qss(self):
        if self._is_dark:
            self.setStyleSheet("""
                QDialog { background: #2B2B2B; border: 1px solid #555; border-radius: 10px; }
            """)
        else:
            self.setStyleSheet("""
                QDialog { background: #FFFFFF; border: 1px solid #CCC; border-radius: 10px; }
            """)

    # ── 拖动支持 ──────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    # ── 键盘事件 ───────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    # ── 发送（JS 注入到 PiAgentWindow 页面） ─────────────────────

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if not text:
            return
        _dbg(f"用户发送: {text[:80]}...")

        pi_agent = get_active_pi_agent()
        if not pi_agent or not pi_agent.is_page_loaded:
            _dbg("Pi Agent 页面未加载")
            self._status_label.setText("Pi Agent 页面未加载")
            return

        # 切换到处理 UI
        self._input.setEnabled(False)
        self._send_btn.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._abort_btn.setVisible(True)
        self._abort_btn.setEnabled(True)
        self._progress.setVisible(True)
        self._status_label.setText("AI 正在处理...")

        # 连接 agent_done 信号
        pi_agent.agent_done.connect(self._on_agent_done)

        # 构建 prompt（让 AI 自己读取文件，不附带文件内容）
        prompt = (
            f"请先读取文件 {self._file_path}，然后根据以下需求进行修改：\n\n"
            f"{text}\n\n"
            f"请直接使用编辑工具修改该文件，完成修改后简要说明改动。"
        )

        # 通过 JS 注入消息到 PiAgentWindow 页面的 ChatInput 并触发发送
        msg_json = json.dumps(prompt, ensure_ascii=False)
        js = f"""\
(function(){{
    console.log('[QuickAI_JS] 开始注入消息...');
    var ta = document.querySelector('textarea[data-pi-input]');
    if (!ta) {{
        // 降级：查找页面中最可能的 chat textarea
        var allTa = document.querySelectorAll('textarea');
        ta = allTa.length === 1 ? allTa[0] : (allTa.length > 0 ? allTa[0] : null);
    }}
    if (!ta) {{ console.log('__PI_QUICKAI_ERROR__:textarea_not_found'); return; }}
    console.log('[QuickAI_JS] 找到textarea，设置值...');
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    nativeSetter.call(ta, {msg_json});
    ta.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }}));
    console.log('[QuickAI_JS] 值已设置，80ms后点击发送');
    setTimeout(function(){{
        var btn = document.querySelector('button[data-pi-send]');
        if (!btn) {{
            // 降级：查找"发送"按钮
            var allBtns = document.querySelectorAll('button');
            for (var i = 0; i < allBtns.length; i++) {{
                if (allBtns[i].textContent.trim() === '发送' && !allBtns[i].disabled) {{
                    btn = allBtns[i]; break;
                }}
            }}
        }}
        console.log('[QuickAI_JS] 发送按钮:', {{found: !!btn, disabled: btn ? btn.disabled : null}});
        if (btn && !btn.disabled) {{
            btn.click();
            console.log('[QuickAI_JS] 已点击发送');
        }} else {{
            console.log('__PI_QUICKAI_ERROR__:send_btn_not_ready');
        }}
    }}, 80);
}})();
"""
        page = pi_agent.web_view.page()
        page.runJavaScript(js)

        _dbg("JS 已注入，等待 agent_done...")

    def _on_agent_done(self):
        """agent 处理完成"""
        _dbg("agent_done 收到，处理完成")
        self._success = True
        self._disconnect_agent_done()
        self.accept()

    def _disconnect_agent_done(self):
        pi_agent = get_active_pi_agent()
        if pi_agent:
            try:
                pi_agent.agent_done.disconnect(self._on_agent_done)
            except Exception:
                pass

    # ── 中断 ────────────────────────────────────────────────────

    def _on_abort(self):
        _dbg("用户点击中断")
        self._abort_btn.setEnabled(False)
        self._status_label.setText("正在中断...")

        # 通过 JS 点击页面上的停止按钮
        pi_agent = get_active_pi_agent()
        if pi_agent:
            pi_agent.web_view.page().runJavaScript("""
                (function(){
                    var btn = document.querySelector('button[data-pi-send]');
                    // 查找停止按钮（ChatInput 中 .stopBtn 之类的）
                    // 通常该按钮在对话框中的某处，有 StopIcon
                    var allBtns = document.querySelectorAll('button');
                    for (var i = 0; i < allBtns.length; i++) {
                        var b = allBtns[i];
                        if (b.textContent.trim() === '停止' || b.title === '停止') {
                            if (!b.disabled) b.click();
                            return;
                        }
                    }
                })();
            """)

        self._disconnect_agent_done()
        self._progress.setVisible(False)
        self._input.setEnabled(True)
        self._send_btn.setVisible(True)
        self._cancel_btn.setVisible(True)
        self._abort_btn.setVisible(False)
        self._input.setFocus()

    # ── 关闭 ────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._disconnect_agent_done()
        super().closeEvent(event)

    @property
    def was_successful(self) -> bool:
        return self._success
