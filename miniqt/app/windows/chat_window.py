# coding:utf-8
"""Chat对话框（占位）"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout


class ChatWindow(QDialog):
    """Chat对话框（占位）"""
    message_sent = pyqtSignal(str)

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent=parent)
        self.setWindowTitle("AI助手")
        self.resize(500, 400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self._output = QTextEdit(self)
        self._output.setReadOnly(True)
        layout.addWidget(self._output)
        hlayout = QHBoxLayout()
        self._input = QTextEdit(self)
        self._input.setMaximumHeight(80)
        hlayout.addWidget(self._input)
        send_btn = QPushButton("发送", self)
        send_btn.clicked.connect(self._on_send)
        hlayout.addWidget(send_btn)
        layout.addLayout(hlayout)

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if text:
            self.message_sent.emit(text)
            self._input.clear()
