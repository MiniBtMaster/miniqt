# coding:utf-8
"""策略向导对话框 - 从模板生成策略代码"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox


class StrategyWizardDialog(QDialog):
    """策略向导对话框（占位）"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("策略向导")
        self.resize(600, 400)
        self._code = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self._editor = QTextEdit(self)
        self._editor.setPlaceholderText("策略代码将在此生成...")
        layout.addWidget(self._editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        self._code = self._editor.toPlainText()
        self.accept()

    def get_strategy_code(self) -> str:
        """获取生成的策略代码"""
        return self._code
