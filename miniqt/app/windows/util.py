import os
import sys
import yaml
import re
import time
from enum import Enum
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *

__all__ = [
    "Color",
    "Cursor",
    "QTextEdit",
    "VT100Paser",
    "pyqtSignal",
    "Highlighter",
    "QTextCharFormat",
    "QColor",
    "QKeySequence",
    "QShortcut",
    "QPalette",
    "QPixmap",
    "QGuiApplication",
    "QApplication",
    "Qt",
    "QFont",
    "QFontMetrics",
    "QResizeEvent",
    "QInputMethodEvent",
    "QTextCursor",
    "QKeyEvent",
    "QWheelEvent",
    "QMouseEvent",
    "QClipboard",
    "QLineEdit",
    "QIcon",
    "Erase",
    "QLabel"
]


class Color():
    """ 终端配色方案 """
    def __init__(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.argv[0])
        else:
            base_dir = os.path.dirname(os.path.dirname(__file__))
        
        self.schemes_dir = os.path.join(base_dir, "schemes")

        self.great_scheme_bright = ["Homebrew Light"]
        self.great_scheme_dark = ["Horizon Dark"]

    def getSchemes(self):
        schemes = []
        names = os.listdir(self.schemes_dir)
        for name in names:
            schemes.append(os.path.splitext(name)[0])
        return schemes

    def getScheme(self, scheme):
        with open(os.path.join(self.schemes_dir, f'{scheme}.yml'), 'r') as file:
            scheme_dict = yaml.safe_load(file)

        scheme = {}
        for key, value in scheme_dict.items():
            if key == 'color_01':
                scheme.update({'Black': value, '30': value})
            elif key == 'color_02':
                scheme.update({'Red': value, '31': value})
            elif key == 'color_03':
                scheme.update({'Green': value, '32': value})
            elif key == 'color_04':
                scheme.update({'Yellow': value, '33': value})
            elif key == 'color_05':
                scheme.update({'Blue': value, '34': value})
            elif key == 'color_06':
                scheme.update({'Magenta': value, '35': value})
            elif key == 'color_07':
                scheme.update({'Cyan': value, '36': value})
            elif key == 'color_08':
                scheme.update({'White': value, '37': value})
            elif key == 'color_09':
                scheme.update({'Bright Black': value, '40': value})
            elif key == 'color_10':
                scheme.update({'Bright Red': value, '41': value})
            elif key == 'color_11':
                scheme.update({'Bright Green': value, '42': value})
            elif key == 'color_12':
                scheme.update({'Bright Yellow': value, '43': value})
            elif key == 'color_13':
                scheme.update({'Bright Blue': value, '44': value})
            elif key == 'color_14':
                scheme.update({'Bright Magenta': value, '45': value})
            elif key == 'color_15':
                scheme.update({'Bright Cyan': value, '46': value})
            elif key == 'color_16':
                scheme.update({'Bright White': value, '47': value})
            elif key == 'background':
                scheme.update({'Background': value})
            elif key == 'foreground':
                scheme.update({'Foreground': value})
            elif key == 'cursor':
                scheme.update({'Cursor': value})
        return scheme
                
class Cursor(Enum):
    """ 终端光标控制 """
    Up          = 1     # 按行数向上移动光标
    Down        = 2     # 按行数向下移动光标
    Left        = 3     # 按列数向左移动光标
    Right       = 4     # 按列数向右移动光标
    StartOfLine = 5     # 移动光标到行首
    SetPosition = 6     # 移动光标到指定（行，列）
    SetRow      = 7     # 移动光标到指定行
    SetColumn   = 8     # 移动光标到指定列

class Erase(Enum):
    """ 擦除终端内容 """
    Up          = 1     # 擦除光标到屏幕顶部内容
    Down        = 2     # 擦除光标到屏幕底部内容
    Line        = 3     # 擦除当前整行的内容
    Screen      = 4     # 擦除整个屏幕
    EndofLine   = 5     # 擦除光标到行尾内容
    StartofLine = 6     # 擦除光标到行首内容
    Character   = 7     # 删除光标处的字符

class VT100Paser:
    """ vt100终端控制转义序列解析器 """

    def __init__(self):
        pass

    def parse(self, seq: str):
        """ 解析输入的序列，要求编码格式是utf-8 """
        pattern = r'\x1b\[([?0-9;]*[A-Za-z~])|\r|\n|\x08|\a'
        matches = re.finditer(pattern, seq)
        update_text_cost = 0
        control_cost = 0

        last_pos = 0
        for match in matches:
            # print(f"start:{match.start()} end:{match.end()}")
            text = seq[last_pos:match.start()]
            if text:
                t0 = time.time()
                self.updateText(text)
                t1 = time.time()
                update_text_cost += t1-t0
            last_pos = match.end()
            # print(match.group().encode())
            t0 = time.time()
            matched_group = match.group()
            if matched_group == '\r':
                self.moveCursor(Cursor.StartOfLine)
            elif matched_group == '\n':
                self.moveCursor(Cursor.Down)
            elif matched_group == '\b':
                self.moveCursor(Cursor.Left)
            elif matched_group == '\a':
                self.ringBell()
            else:
                self.escapeSeqHandler(match.group(1)[-1:], re.split(";", match.group(1)[:-1]), match.group())
            t1 = time.time()
            control_cost += t1-t0
        text = seq[last_pos:]
        if text:
            t0 = time.time()
            self.updateText(text)
            t1 = time.time()
            update_text_cost += t1-t0
        return f"text:{update_text_cost*1000:.2f}ms control:{control_cost*1000:.2f}ms"


    def escapeSeqHandler(self, flag, argv, match):
        # print(flag, argv)
        if flag == 'm':
            # 设置显示属性
            self.setDisplayAttributes(argv)
        elif flag in ('H', 'f'):
            # 光标控制
            pos = (int(argv[0]),int(argv[1])) if argv[0] else (1,1)
            self.moveCursor(Cursor.SetPosition, pos=pos)
        elif flag == 'A':
            cnt = int(argv[0]) if argv[0] else 1
            self.moveCursor(Cursor.Up, cnt)
        elif flag == 'B':
            cnt = int(argv[0]) if argv[0] else 1
            self.moveCursor(Cursor.Down, cnt)
        elif flag == 'C':
            cnt = int(argv[0]) if argv[0] else 1
            self.moveCursor(Cursor.Right, cnt)
        elif flag == 'D':
            cnt = int(argv[0]) if argv[0] else 1
            self.moveCursor(Cursor.Left, cnt)
        elif flag == '~':
            # 删除光标处的字符 (\x1b[3~])
            self.eraseText(Erase.Character)
        elif flag == 'G':
            cnt = int(argv[0]) if argv[0] else 1
            self.moveCursor(Cursor.SetColumn, cnt)
        elif flag == 'J':
            # 擦除文本
            if argv[0] == '' or argv[0] == '0':
                self.eraseText(Erase.Down)
            elif argv[0] == '1':
                self.eraseText(Erase.Up)
            elif argv[0] == '2':
                self.eraseText(Erase.Screen) 
        elif flag == 'K':
            if argv[0] == '' or argv[0] == '0':
                self.eraseText(Erase.EndofLine)
            elif argv[0] == '1':
                self.eraseText(Erase.StartofLine)
            elif argv[0] == '2':
                self.eraseText(Erase.Line)
        else:
            pass
            # print(f"Unknown: {match.encode()}")

    # 以下的方法需要终端重载实现
    def updateText(self, text: str):
        print(text)

    def setDisplayAttributes(self, attrs: list):
        print("set attr", attrs)

    def eraseText(self, action):
        print(action)

    def moveCursor(self, action, cnt=1, pos=(0,0)):
        """(row, col)"""
        print(action, cnt, pos)

    def ringBell(self):
        print("ring")


class Highlighter(QSyntaxHighlighter):
    """ 语法高亮器 """
    def __init__(self, color, parent=None):
        super(Highlighter, self).__init__(parent)
        self.highlighting_rules = []

        # 命令关键字 - 使用亮绿色
        command_format = QTextCharFormat()
        command_format.setForeground(QColor(color["Green"]))
        # command_pattern = r'\$\s+([^\s]+)|#\s+([^\s]+)'
        command_pattern = r'[#$;|]\s+([^\s]+)'
        self.highlighting_rules.append((QRegularExpression(command_pattern), command_format, "command"))

        # 路径 - 使用亮蓝色
        path_format = QTextCharFormat()
        path_format.setForeground(QColor(color["Blue"]))
        self.highlighting_rules.append((QRegularExpression(r'/\S+'), path_format, "path"))

        # 参数 - 使用亮黄色
        param_format = QTextCharFormat()
        param_format.setForeground(QColor(color["Yellow"]))
        self.highlighting_rules.append((QRegularExpression(r'\s-{1,2}[a-zA-Z]+'), param_format, "param"))

        # 字符串 - 使用亮品红色
        string_format = QTextCharFormat()
        string_format.setForeground(QColor(color["Red"]))
        self.highlighting_rules.append((QRegularExpression(r'[\"\'].*?[\"\']'), string_format, "string"))

        # 用户名/主机名 - 使用青色
        # user_host_format = QTextCharFormat()
        # user_host_format.setForeground(cyan)
        # self.highlighting_rules.append((QRegularExpression(r'\b\w+@[\w.-]+\b'), user_host_format))

        # 异常关键字 - 使用亮红色
        exception_format = QTextCharFormat()
        exception_format.setForeground(QColor(color["Bright Red"]))
        exception_keywords = ["error", "err", "false",
                              "no", "not", "nok",
                              "fail", "failure", "failed"]
        self.highlighting_rules.append((QRegularExpression(r'\b(?:' + '|'.join(exception_keywords) + r')\b', QRegularExpression.PatternOption.CaseInsensitiveOption), exception_format, "exception"))

        # 积极关键字 - 使用亮绿色
        positive_format = QTextCharFormat()
        positive_format.setForeground(QColor(color["Bright Green"]))
        positive_keywords = ["ok", "true",
                              "success", "successful", "successfully"]
        self.highlighting_rules.append((QRegularExpression(r'\b(?:' + '|'.join(positive_keywords) + r')\b', QRegularExpression.PatternOption.CaseInsensitiveOption), positive_format, "positive"))

    def highlightBlock(self, text):
        for pattern, fmt, syntax in self.highlighting_rules:
            expression = QRegularExpression(pattern)
            match = expression.match(text)
            while match.hasMatch():
                if syntax == "command":
                    start = match.capturedStart(1)
                    length = match.capturedLength(1)
                else:
                    start = match.capturedStart()
                    length = match.capturedLength()
                self.setFormat(start, length, fmt)
                match = expression.match(text, start + length)


        
        

