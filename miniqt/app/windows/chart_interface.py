# coding:utf-8
# https://github.com/louisnw01/lightweight-charts-python
# https://tradingview.github.io/lightweight-charts/
# https://lightweight-charts-python.readthedocs.io/en/latest/index.html

from __future__ import annotations
import json
import sys
import os
import pandas as pd

from functools import partial
from itertools import cycle
import inspect
# 添加项目根目录到Python路径，确保从当前项目导入minibt
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))
from minibt.other import FILED, FilteredOutputRedirector
from minibt.utils import Colors as btcolors, OrderedDict, _time
from typing import TYPE_CHECKING, Union, Iterable,Optional,Callable
from ..common.chart_config import chart_cfg
#with FilteredOutputRedirector():
from qfluentwidgets import (isDarkTheme, Theme, FluentWindow, TransparentToolButton, RoundMenu, Action,
                            FluentIcon, FluentStyleSheet, FluentTitleBar, TableWidget, CaptionLabel,
                            Dialog, SearchLineEdit, ListWidget, PushButton,
                            BodyLabel, DoubleSpinBox, TitleLabel, SwitchButton, PrimaryPushButton,
                            ComboBox,  CardWidget, ScrollArea, ColorDialog,
                            InfoBar, InfoBarPosition, HyperlinkLabel)
from lightweight_charts import util
from lightweight_charts.util import Events, JSEmitter,as_enum,jbool,LINE_STYLE
from lightweight_charts.abstract import Line, Candlestick, AbstractChart, SeriesCommon
from lightweight_charts.drawings import HorizontalLine
from lightweight_charts.toolbox import ToolBox, json

# ---- Monkey-patch: NaN 断线处理（多系列分割法）----
# lightweight-charts 的 LineSeries 会跨 NaN 间隙连线，无法通过空白数据点实现断线。
# 此补丁采用多系列分割法：检测 NaN 位置，将数据分割为多个连续片段，
# 每个片段用独立的 Line 系列显示，实现真正的断线效果。
import numpy as _np

_original_series_set = SeriesCommon.set

def _split_df_by_nan(df, value_col='value'):
    """
    将 DataFrame 根据 NaN 值分割成多个连续片段。
    返回：[(片段索引, DataFrame片段), ...]
    """
    if df.empty or value_col not in df.columns:
        return [(0, df)]

    # 找出 NaN 位置
    is_nan = df[value_col].isna()
    segments = []
    segment_start = None

    for i in range(len(df)):
        if not is_nan.iloc[i]:
            # 有效值：如果还没开始片段，开始新片段
            if segment_start is None:
                segment_start = i
        else:
            # NaN 值：如果有正在进行的片段，结束它
            if segment_start is not None:
                segments.append((len(segments), df.iloc[segment_start:i].copy()))
                segment_start = None

    # 处理最后一个片段
    if segment_start is not None:
        segments.append((len(segments), df.iloc[segment_start:].copy()))

    return segments

def _patched_series_set(self, df=None, format_cols=True):
    """补丁版 set()：Line 数据含 NaN 时用多系列分割法实现断线。"""
    # 清理之前的分段线（如果存在）
    if hasattr(self, '_segment_lines') and self._segment_lines:
        for seg_line in self._segment_lines:
            try:
                # 清空分段线的数据
                seg_line.run_script(f'{seg_line.id}.series.setData([]); ')
            except Exception:
                pass
        self._segment_lines = []

    if df is None or df.empty:
        return _original_series_set(self, df, format_cols)

    # 仅处理 Line（不处理 Histogram）
    if not isinstance(self, Line):
        return _original_series_set(self, df, format_cols)

    # 检测值列是否有 NaN
    val_cols = [c for c in df.columns if c != 'time']
    has_nan = val_cols and any(
        str(df[c].dtype).startswith('float') and df[c].isna().any()
        for c in val_cols
    )

    # 无 NaN 或只有一个片段：直接用原方法
    if not has_nan:
        return _original_series_set(self, df, format_cols)

    # 格式化 DataFrame
    if format_cols:
        df_formatted = self._df_datetime_format(df, exclude_lowercase=self.name)
    else:
        df_formatted = df.copy()

    if self.name:
        if self.name not in df_formatted:
            raise NameError(f'No column named "{self.name}".')
        df_formatted = df_formatted.rename(columns={self.name: 'value'})

    # 分割 DataFrame
    segments = _split_df_by_nan(df_formatted, 'value')

    # 如果只有一个片段（全是有效值），用原方法（需先重命名回原列名）
    if len(segments) <= 1:
        self.data = df_formatted.copy()
        self._last_bar = df_formatted.iloc[-1] if len(df_formatted) > 0 else None
        df_renamed = df_formatted.rename(columns={'value': self.name})
        return _original_series_set(self, df_renamed, format_cols=False)

    # 多片段：第一个片段用原 Line，其他片段创建新的 Line 系列
    self._segment_lines = []

    for seg_idx, seg_df in segments:
        if seg_idx == 0:
            # 第一个片段：用原 Line 对象
            self.data = df_formatted.copy()
            self._last_bar = df_formatted.iloc[-1] if len(df_formatted) > 0 else None
            # 修复：将 value 列重命名回原列名，避免 NameError
            seg_df_renamed = seg_df.rename(columns={'value': self.name})
            _original_series_set(self, seg_df_renamed, format_cols=False)
        else:
            # 其他片段：创建新的 Line 系列
            # 使用原 Line 的样式（color），其他参数用默认值
            seg_line = self._chart.create_line(
                name=f"{self.name}_seg{seg_idx}",
                color=self.color if hasattr(self, 'color') else 'rgba(214, 237, 255, 0.6)',
                style='solid',
                width=2,
                price_line=False,
                price_label=False
            )
            # 修复：将 value 列重命名为分段线的列名
            seg_df_renamed = seg_df.rename(columns={'value': seg_line.name})
            # 设置分段数据
            _original_series_set(seg_line, seg_df_renamed, format_cols=False)
            self._segment_lines.append(seg_line)

# SeriesCommon.set = _patched_series_set
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QUrl, QObject, QThread, QMetaObject, QEvent, Q_ARG, pyqtSlot, QMutex, QPoint
from PyQt6.QtGui import QColor, QFont, QPainter, QIcon, QPen, QGuiApplication, QCursor
from PyQt6.QtWidgets import (QApplication,  QSplitter, QWidget, QVBoxLayout, QSizePolicy,
                             QHBoxLayout, QAbstractItemView, QTableWidgetItem, QHeaderView,)
from ..common.chart_data import chart_data_manager
from ..windows.indicator_card_window import createIndicatorCardMenu
import minibt, traceback



if TYPE_CHECKING:
    from ..view.main_window import MainWindow
    from lightweight_charts.widgets import QtChart
    from ..windows.market_watch_window import MarketWatchWindow
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from .indicator_card_window import IndicatorParamsCard

# 延迟导入Chart类
#ChartClass :Optional["QtChart"] = None
def _delete(self):
    """
    Irreversibly deletes the line, as well as the object that contains the line.
    修复PySide6与lightweight_charts的兼容性问题
    """
    self._chart._lines.remove(self) if self in self._chart._lines else None
    self.run_script(f'''
        (function() {{
            try {{
                var legendItem = {self._chart.id}.legend._lines.find((line) => line.series == {self.id}.series);
                
                if (legendItem) {{
                    {self._chart.id}.legend._lines = {self._chart.id}.legend._lines.filter((item) => item !== legendItem);
                    
                    if (legendItem.row) {{
                        if (legendItem.row.parentNode) {{
                            legendItem.row.parentNode.removeChild(legendItem.row);
                        }} else if (legendItem.row.remove) {{
                            legendItem.row.remove();
                        }}
                    }}
                }}
                
                if ({self.id} && {self.id}.series) {{
                    {self._chart.id}.chart.removeSeries({self.id}.series);
                }}
                delete {self.id};
            }} catch(err) {{
                // 忽略删除指标时的错误
            }}
        }})();
    ''')
    
setattr(Line, 'delete', _delete)

def set_line_style(self:Line,style:str):
    """设置指标线样式"""
    self.run_script(f'''
        if ({self.id} && {self.id}.series) {{
            {self.id}.series.applyOptions({{
                lineStyle: '{as_enum(style,LINE_STYLE)}'
            }});
        }}
    ''')
setattr(Line, 'set_line_style', set_line_style)
def set_line_width(self:Line,width:float):
    """设置指标线宽度"""
    self.run_script(f'''
        if ({self.id} && {self.id}.series) {{
            {self.id}.series.applyOptions({{
                lineWidth: {width}
            }});
        }}
    ''')
setattr(Line, 'set_line_width', set_line_width)
def set_line_color(self:Line,color:str):
    """设置指标线颜色"""
    self.run_script(f'''
        if ({self.id} && {self.id}.series) {{
            {self.id}.series.applyOptions({{
                color: '{color}'
            }});
        }}
    ''')
setattr(Line, 'set_line_color', set_line_color)
def set_price_visible(self:Line,visible:bool):
    """设置指标线价格是否可见"""
    self.run_script(f'''
        if ({self.id} && {self.id}.series) {{
            {self.id}.series.applyOptions({{
                priceVisible: {jbool(visible)}
            }});
        }}
    ''')
setattr(Line, 'set_price_visible', set_price_visible)


def set_indicator_id(self, indicator_id: int):
    """
    为Line对象设置indicator_id属性（JS属性）
    
    参数:
        indicator_id: 指标ID
    """
    self.run_script(f'''
        if ({self.id} && {self.id}.series) {{
            {self.id}.series.indicator_id = {indicator_id};
        }}
    ''')

setattr(Line, 'set_indicator_id', set_indicator_id)

def is_visible(self:Line):
    """获取指标线的可视状态"""
    return getattr(self, '_visible', True)

def hide_data(self:Line):
    """隐藏指标线"""
    self._toggle_data(False)
    self._visible = False

def show_data(self:Line):
    """显示指标线"""
    self._toggle_data(True)
    self._visible = True

setattr(Line, 'is_visible', is_visible)
setattr(Line, 'hide_data', hide_data)
setattr(Line, 'show_data', show_data)

def init_line_visibility(self:Line):
    """初始化指标线的可视状态"""
    # 默认情况下，指标线是可见的
    if not hasattr(self, '_visible'):
        self._visible = True

setattr(Line, 'init_line_visibility', init_line_visibility)

def watch_cursor_change(self):
    """
    监听主图上的鼠标移动事件，识别具体是哪个指标标签
    
    功能：
    1. 使用事件委托方式监听 legend 容器的鼠标事件
    2. 当鼠标进入某个 legend 行时，返回该行的信息（指标名称、颜色等）和鼠标位置
    3. 当鼠标离开所有 legend 行时，返回 "leave"
    """
    chart = self.search._chart
    salt = chart.id[chart.id.index('.')+1:]
    self.cursor_change = JSEmitter(chart, f'cursor_change{salt}',
                lambda o: chart.run_script(f'''
                (function() {{
                    const salt = "{salt}";
                    const chartObj = {chart.id};
                    const key = `_main_cursor_${{salt}}`;
                    // console.log('Main chart cursor watcher starting for:', chartObj.id);
                    if (window[key]) {{
                        // console.log('Main chart cursor watcher already initialized, skipping');
                        return;
                    }}
                    window[key] = true;

                    function watch() {{
                        // console.log('Main chart watch() function called');
                        const legend = chartObj.legend;
                        if (!legend || !legend.div || !legend._lines) {{
                            // console.log('Main chart legend not ready, retrying...');
                            return setTimeout(watch, 500);
                        }}

                        // console.log('Main chart legend found, linesArray:', legend._lines);
                        const legendDiv = legend.div;
                        let currentHoveredIndex = -1;

                        // 为 legend 容器添加事件监听（事件委托）
                        function handleMouseMove(e) {{
                            try {{
                                const target = e.target;
                                let foundIndex = -1;
                                
                                // 查找当前鼠标在哪个指标行上
                                const linesArray = legend._lines;
                                if (!linesArray) return;
                                
                                for (let i = 0; i < linesArray.length; i++) {{
                                    const legendItem = linesArray[i];
                                    if (!legendItem || !legendItem.row) continue;
                                    
                                    if (legendItem.row.contains(target)) {{
                                        foundIndex = i;
                                        break;
                                    }}
                                }}
                                
                                // 如果鼠标进入了新的指标行
                                if (foundIndex !== -1 && foundIndex !== currentHoveredIndex) {{
                                    currentHoveredIndex = foundIndex;
                                    const legendItem = linesArray[foundIndex];
                                    
                                    // console.log('Main chart mouseenter event triggered for index:', foundIndex);
                                    // console.log('Main chart legend items:', linesArray);
                                    // console.log('Current legend item:', legendItem);
                                    // console.log('Current legend item series:', legendItem.series);
                                    
                                    if (!legendItem || !legendItem.row) return;
                                    
                                    e.stopPropagation();
                                    document.body.style.cursor = "pointer";
                                    
                                    // 获取鼠标相对于webview的坐标
                                    const webview = document.querySelector('webview') || document.body;
                                    const rect = webview.getBoundingClientRect();
                                    const x = e.clientX - rect.left;
                                    const y = e.clientY - rect.top;
                                    
                                    // 获取指标信息
                                    const row = legendItem.row;
                                    const textContent = row.textContent || row.innerText || "";
                                    const color = legendItem.color || "";
                                    const seriesName = legendItem.name || "";
                                    
                                    // 尝试获取更多信息
                                    let lineId = "";
                                    let indicatorId = -1;
                                    // let isVisible = true;
                                    if (legendItem.series && legendItem.series._internal) {{
                                        lineId = legendItem.series._internal._id || "";
                                        // console.log('Current legend item series internal:', legendItem.series._internal);
                                    }}
                                    
                                    // 获取indicator_id
                                    if (legendItem.series && legendItem.series.indicator_id !== undefined) {{
                                        indicatorId = legendItem.series.indicator_id;
                                        // console.log('Current legend item indicator_id:', indicatorId);
                                    }}
                                    
                                    // 获取指标线的可视状态
                                    // if (legendItem.series && legendItem.series.options) {{
                                    //     isVisible = legendItem.series.options.visible !== false;
                                    //     // console.log('Current legend item visible:', isVisible);
                                    // }}
                                    
                                    // 构建返回数据（包含坐标）
                                    const info = JSON.stringify({{
                                        type: "enter",
                                        index: foundIndex,
                                        text: textContent.trim(),
                                        color: color,
                                        name: seriesName,
                                        lineId: lineId,
                                        indicatorId: indicatorId,
                                        x: x,
                                        y: y
                                    }});
                                    
                                    // console.log('Main chart calling callbackFunction with info:', info);
                                    window.callbackFunction(`cursor_change${{salt}}_~_${{info}}`);
                                }}
                            }} catch(err) {{
                                // 忽略删除指标后的 null 引用错误
                                // console.log('handleMouseMove error:', err);
                            }}
                        }}

                        function handleMouseOut(e) {{
                            try {{
                                const target = e.target;
                                const relatedTarget = e.relatedTarget;
                                const linesArray = legend._lines;
                                if (!linesArray) return;
                                
                                let leavingFromIndex = -1;
                                let enteringToIndex = -1;
                                
                                // 查找鼠标离开的指标行
                                for (let i = 0; i < linesArray.length; i++) {{
                                    const legendItem = linesArray[i];
                                    if (!legendItem || !legendItem.row) continue;
                                    
                                    if (legendItem.row.contains(target)) {{
                                        leavingFromIndex = i;
                                        break;
                                    }}
                                }}
                                
                                // 查找鼠标进入的指标行
                                if (relatedTarget) {{
                                    for (let i = 0; i < linesArray.length; i++) {{
                                        const legendItem = linesArray[i];
                                        if (!legendItem || !legendItem.row) continue;
                                        
                                        if (legendItem.row.contains(relatedTarget)) {{
                                            enteringToIndex = i;
                                            break;
                                        }}
                                    }}
                                }}
                                
                                // 如果鼠标离开了所有指标行
                                if (leavingFromIndex !== -1 && enteringToIndex === -1) {{
                                    // console.log('Main chart mouseleave event triggered');
                                    currentHoveredIndex = -1;
                                    e.stopPropagation();
                                    document.body.style.cursor = "default";
                                    window.callbackFunction('cursor_change' + salt + '_~_${{"type": "leave"}}');
                                }}
                            }} catch(err) {{
                                // 忽略删除指标后的 null 引用错误
                                // console.log('handleMouseOut error:', err);
                            }}
                        }}

                        // 移除旧的事件监听器（避免重复绑定）
                        legendDiv.removeEventListener('mousemove', handleMouseMove);
                        legendDiv.removeEventListener('mouseout', handleMouseOut);
                        
                        // 添加事件监听器到 legend 容器
                        legendDiv.addEventListener('mousemove', handleMouseMove);
                        legendDiv.addEventListener('mouseout', handleMouseOut);

                        // console.log('Main chart cursor watcher initialized for:', chartObj.id);
                    }}

                    watch();
                }})();
                '''),
                wrapper=lambda f, c, a: f(c, a)
            )
setattr(Events, 'watch_cursor_change', watch_cursor_change)


def watch_main_chart_cursor(self):
    """
    监听主图上的鼠标移动事件，识别具体是哪个指标标签
    
    功能：
    1. 使用事件委托方式监听 legend 容器的鼠标事件
    2. 当鼠标进入某个 legend 行时，返回该行的信息（指标名称、颜色等）和鼠标位置
    3. 当鼠标离开所有 legend 行时，返回 "leave"
    """
    chart = self.search._chart
    salt = chart.id[chart.id.index('.')+1:]
    self.main_chart_cursor_change = JSEmitter(chart, f'main_chart_cursor_change{salt}',
                lambda o: chart.run_script(f'''
                (function() {{
                    const salt = "{salt}";
                    const chartObj = {chart.id};
                    const key = `_main_cursor_${{salt}}`;
                    // console.log('Main chart cursor watcher starting for:', chartObj.id);
                    if (window[key]) {{
                        // console.log('Main chart cursor watcher already initialized, skipping');
                        return;
                    }}
                    window[key] = true;

                    function watch() {{
                        // console.log('Main chart watch() function called');
                        const legend = chartObj.legend;
                        if (!legend || !legend.div || !legend._lines) {{
                            // console.log('Main chart legend not ready, retrying...');
                            return setTimeout(watch, 500);
                        }}

                        // console.log('Main chart legend found, linesArray:', legend._lines);
                        const legendDiv = legend.div;
                        let currentHoveredIndex = -1;

                        // 为 legend 容器添加事件监听（事件委托）
                        function handleMouseMove(e) {{
                            try {{
                                const target = e.target;
                                let foundIndex = -1;
                                
                                // 查找当前鼠标在哪个指标行上
                                const linesArray = legend._lines;
                                if (!linesArray) return;
                                
                                for (let i = 0; i < linesArray.length; i++) {{
                                    const legendItem = linesArray[i];
                                    if (!legendItem || !legendItem.row) continue;
                                    
                                    if (legendItem.row.contains(target)) {{
                                        foundIndex = i;
                                        break;
                                    }}
                                }}
                                
                                // 如果鼠标进入了新的指标行
                                if (foundIndex !== -1 && foundIndex !== currentHoveredIndex) {{
                                    currentHoveredIndex = foundIndex;
                                    const legendItem = linesArray[foundIndex];
                                    
                                    // console.log('Main chart mouseenter event triggered for index:', foundIndex);
                                    // console.log('Main chart legend items:', linesArray);
                                    // console.log('Current legend item:', legendItem);
                                    // console.log('Current legend item series:', legendItem.series);
                                    
                                    if (!legendItem || !legendItem.row) return;
                                    
                                    e.stopPropagation();
                                    document.body.style.cursor = "pointer";
                                    
                                    // 获取鼠标相对于webview的坐标
                                    const webview = document.querySelector('webview') || document.body;
                                    const rect = webview.getBoundingClientRect();
                                    const x = e.clientX - rect.left;
                                    const y = e.clientY - rect.top;
                                    
                                    // 获取指标信息
                                    const row = legendItem.row;
                                    const textContent = row.textContent || row.innerText || "";
                                    const color = legendItem.color || "";
                                    const seriesName = legendItem.name || "";
                                    
                                    // 尝试获取更多信息
                                    let lineId = "";
                                    if (legendItem.series && legendItem.series._internal) {{
                                        lineId = legendItem.series._internal._id || "";
                                        // console.log('Current legend item series internal:', legendItem.series._internal);
                                    }}
                                    
                                    // 构建返回数据（包含坐标）
                                    const info = JSON.stringify({{
                                        type: "enter",
                                        index: foundIndex,
                                        text: textContent.trim(),
                                        color: color,
                                        name: seriesName,
                                        lineId: lineId,
                                        x: x,
                                        y: y
                                    }});
                                    
                                    // console.log('Main chart calling callbackFunction with info:', info);
                                    window.callbackFunction(`main_chart_cursor_change${{salt}}_~_${{info}}`);
                                }}
                            }} catch(err) {{
                                // 忽略删除指标后的 null 引用错误
                                // console.log('handleMouseMove error:', err);
                            }}
                        }}

                        function handleMouseOut(e) {{
                            try {{
                                const target = e.target;
                                const relatedTarget = e.relatedTarget;
                                const linesArray = legend._lines;
                                if (!linesArray) return;
                                
                                let leavingFromIndex = -1;
                                let enteringToIndex = -1;
                                
                                // 查找鼠标离开的指标行
                                for (let i = 0; i < linesArray.length; i++) {{
                                    const legendItem = linesArray[i];
                                    if (!legendItem || !legendItem.row) continue;
                                    
                                    if (legendItem.row.contains(target)) {{
                                        leavingFromIndex = i;
                                        break;
                                    }}
                                }}
                                
                                // 查找鼠标进入的指标行
                                if (relatedTarget) {{
                                    for (let i = 0; i < linesArray.length; i++) {{
                                        const legendItem = linesArray[i];
                                        if (!legendItem || !legendItem.row) continue;
                                        
                                        if (legendItem.row.contains(relatedTarget)) {{
                                            enteringToIndex = i;
                                            break;
                                        }}
                                    }}
                                }}
                                
                                // 如果鼠标离开了所有指标行
                                if (leavingFromIndex !== -1 && enteringToIndex === -1) {{
                                    // console.log('Main chart mouseleave event triggered');
                                    currentHoveredIndex = -1;
                                    e.stopPropagation();
                                    document.body.style.cursor = "default";
                                    window.callbackFunction('main_chart_cursor_change' + salt + '_~_${{"type": "leave"}}');
                                }}
                            }} catch(err) {{
                                // 忽略删除指标后的 null 引用错误
                                // console.log('handleMouseOut error:', err);
                            }}
                        }}

                        // 移除旧的事件监听器（避免重复绑定）
                        legendDiv.removeEventListener('mousemove', handleMouseMove);
                        legendDiv.removeEventListener('mouseout', handleMouseOut);
                        
                        // 添加事件监听器到 legend 容器
                        legendDiv.addEventListener('mousemove', handleMouseMove);
                        legendDiv.addEventListener('mouseout', handleMouseOut);

                        // console.log('Main chart cursor watcher initialized for:', chartObj.id);
                    }}

                    watch();
                }})();
                '''),
                wrapper=lambda f, c, a: f(c, a)
            )
setattr(Events, 'watch_main_chart_cursor', watch_main_chart_cursor)

def right_click(self):
    """
    监听图表右击鼠标事件
    
    功能：
    1. 监听图表区域的 contextmenu（右击）事件
    2. 返回 chart.id 和鼠标位置（相对于webview的坐标）
    """
    chart = self.search._chart
    salt = chart.id[chart.id.index('.')+1:]
    self.right_click = JSEmitter(chart, f'right_click{salt}',
                lambda o: chart.run_script(f'''
                (function() {{
                    const salt = "{salt}";
                    const chartObj = {chart.id};
                    const key = `_right_click_${{salt}}`;
                    if (window[key]) return;
                    window[key] = true;

                    // 监听图表div的contextmenu事件
                    const chartDiv = chartObj.div;
                    if (!chartDiv) {{
                        // console.log('Chart div not found for right click');
                        return;
                    }}

                    chartDiv.addEventListener('contextmenu', function(e) {{
                        e.preventDefault();
                        
                        // 获取鼠标相对于webview的坐标
                        const webview = document.querySelector('webview') || document.body;
                        const rect = webview.getBoundingClientRect();
                        const x = e.clientX - rect.left;
                        const y = e.clientY - rect.top;
                        
                        window.callbackFunction(`right_click${{salt}}_~_${{chartObj.id}};;;${{x}};;;${{y}}`);
                    }});

                    // console.log('Right click watcher initialized for:', chartObj.id);
                }})();
                '''),
                wrapper=lambda f, c, *args: f(c, *args)
            )
setattr(Events, 'right_click', right_click)

def get_chart_class()->Optional[QtChart]:
    """
    延迟导入Chart类（PyQt6）
    """
    #global ChartClass, QtChart
    # if ChartClass is None:
    # 确保QApplication实例存在
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # 先导入PyQt6的QtWebEngineWidgets模块，确保使用的是PyQt6
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtCore import Qt, QObject, pyqtSlot, QUrl, QTimer
    from lightweight_charts.util import parse_event_message
    def emit_callback(window, string):
        func, args = parse_event_message(window, string)
        # 直接同步调用，避免 asyncio 与天勤冲突
        func(*args)
    # 定义一个使用PyQt6 QObject的Bridge类
    class Bridge(QObject):
        # 添加光标变化信号
        # cursorChanged = pyqtSignal(str)
        def __init__(self, chart):
            super().__init__()
            self.win = chart.win

        @pyqtSlot(str)
        def callback(self, message):
            emit_callback(self.win, message)
            
        # 新增槽函数，用于接收前端光标变化事件
        # @pyqtSlot(str)
        # def onCursorChanged(self, cursor_type):
        #     """前端调用此方法传递光标类型：'ibeam' 或 'arrow'"""
        #     self.cursorChanged.emit(cursor_type)

    # 手动设置lightweight_charts.widgets模块的using_pyside6变量为False（使用PyQt6）
    import lightweight_charts
    lightweight_charts.using_pyside6 = False

    # 导入lightweight_charts.widgets模块
    import lightweight_charts.widgets

    # 直接使用我们导入的PyQt6模块，而不是让lightweight_charts.widgets模块自己导入
    lightweight_charts.widgets.QWebEngineView = QWebEngineView
    lightweight_charts.widgets.QWebChannel = QWebChannel
    lightweight_charts.widgets.QObject = QObject
    lightweight_charts.widgets.Slot = pyqtSlot
    lightweight_charts.widgets.QUrl = QUrl
    lightweight_charts.widgets.QTimer = QTimer
    lightweight_charts.widgets.Qt = Qt
    lightweight_charts.widgets.Bridge = Bridge

    # 获取Chart类
    ChartClass = lightweight_charts.widgets.QtChart
    QtChart = ChartClass
    return ChartClass


Colors: list[str] = ['fuchsia', 'lime', 'olive', 'blue', 'purple', 'silver', 'teal', 'aqua',
                     'green', 'maroon', 'navy', 'red']

SETTING_FILE_PATH = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "setting.json")


def get_default_settings() -> dict:
    """返回默认配置，用于文件不存在/数据损坏时兜底
    优先从ChartConfig读取默认值
    """
    return {
        "drawings": {},
        "price_alerts": {},
        "istool": chart_cfg.showToolBox.value,
        "mouse_label_color": chart_cfg.mouseLabelColor.value,
        "candlestick_colors": {
            "bear_color": chart_cfg.bearColor.value,
            "bull_color": chart_cfg.bullColor.value
        },
        "splitter_sizes": [174, 1868],
    }


def get_colors() -> cycle:
    """指标初始颜色"""
    return cycle(Colors)


class Indicator:
    """ Indicator class """
    def __init__(self,id:int, ind_cls:str, name:str, params:dict={}):
        self.id = id
        self.indicator_cls = ind_cls
        self.is_tradingview = ind_cls=="TradingView"
        self.name = name
        self.ind_cls = getattr(minibt,ind_cls)
        ind = getattr(self.ind_cls,self.name)
        # 获取指标函数的默认参数
        
        sig = inspect.signature(ind)
        self.default_params = {
            k: v.default
            for k, v in sig.parameters.items()
            if v.default is not inspect.Parameter.empty and k != 'self' and k != 'kwargs'
        }
        self.params_type={
            k: type(v)
            for k, v in self.default_params.items()
        }
        if not params:
            self.params = self.default_params.copy()
        else:
            new_params = self.default_params.copy()
            for k,v in params.items():
                if k in self.default_params:
                    new_params[k]=v
            self.params=new_params
        doc = ind.__doc__
        doc = doc.replace("\n","<br>")
        self.doc = doc.replace(" ","&nbsp;")
        self.chart_id:str=""
        self.line_color:dict={}
        self.price_visible:dict={}
        self.line_width:dict={}
        self.line_style:dict={}
        self.indicator_lines:dict[str,Line]={}
        # self.overlaps = {}

    def __str__(self):
        return f"{self.id} - {self.indicator_cls} - {self.name} - {self.params}"

    def __repr__(self):
        return self.__str__()

    def calculate_indicators(self,df:pd.DataFrame)->Union[minibt.IndFrame,minibt.IndSeries]:
        """计算指标"""
        if self.is_tradingview:
            df = df.copy()
            df.datetime=df.time.apply(minibt.utils.time_to_datetime)
            df.columns=minibt.FILED.ALL
            # print(df.head())
            df = minibt.KLine(df)
        cls=self.ind_cls(df)
        indicator = getattr(cls,self.name)(**self.params)
        return indicator
    
class IndicatorManager(QObject):
    """ Indicator window manager - 不继承QObject，避免信号传递问题 """
    def __init__(self):
        super().__init__()
        self.num=0
        self.indicators : list[Indicator] = []
        

    def addIndicator(self,ind_cls:str, name:str, params:dict={}):
        """ Add indicator to manager """
        self.indicators.append(Indicator(self.num,ind_cls, name, params))
        self.num += 1

    def removeIndicator(self, indicator_id):
        """ Remove indicator from manager by id """
        self.indicators = [ind for ind in self.indicators if ind.id != indicator_id]

    def getIndicators(self)->list[Indicator]:
        """ Get all indicators """
        return self.indicators
    
    def getIndicator(self,indicator_id:int)->Indicator:
        """ Get indicator by id """
        return next((ind for ind in self.indicators if ind.id==indicator_id), None)
    
    def calculate_indicators(self,df:pd.DataFrame)->dict[int,Union[minibt.IndFrame,minibt.IndSeries]]:
        """更新指标"""
        indicators = {}
        for indicator in self.indicators:
            indicators[indicator.id] = indicator.calculate_indicators(df)
        return indicators
    
    def calculate_target_indicator(self,df:pd.DataFrame,indicator_id:int,params:dict={})->Union[minibt.IndFrame,minibt.IndSeries]:
        """更新指标"""
        indicator = next((ind for ind in self.indicators if ind.id==indicator_id), None)
        if indicator:
            if params:
                for k,v in params.items():
                    if k in indicator.params:
                        indicator.params[k]=v
            return indicator.calculate_indicators(df)
        return None
    
    def calculate_last_indicators(self,df:pd.DataFrame)->Union[minibt.IndFrame,minibt.IndSeries,None]:
        """计算最新指标"""
        if not self.indicators:
            # print("指标管理器中没有指标，无法计算最新指标")
            return None
        return self.indicators[-1].calculate_indicators(df)
    
    @property
    def last_indicator(self)->Indicator:
        """获取最新指标"""
        if not self.indicators:
            # print("指标管理器中没有指标，无法获取最新指标")
            return None
        return self.indicators[-1]
    
    def get_main_chart_indicators(self,chart_id:str)->list[Indicator]:
        """获取主图表指标"""
        return [ind for ind in self.indicators if ind.chart_id==chart_id]
    
    def get_sub_chart_indicators(self,chart_id:str)->list[Indicator]:
        """获取子图表指标"""    
        return [ind for ind in self.indicators if ind.chart_id!=chart_id]

class PriceAlertSettingDialog(Dialog):
    """
    简洁版价格预警设置对话框（基于自定义 Dialog 基类）
    核心功能：启用开关、预警类型、上下破价格设置
    """
    alertSettingsChanged = pyqtSignal(object) 

    def __init__(self, title="", content="", parent: LightChartWindow = None, current_settings: dict = None):
        """
        初始化对话框（调用基类构造方法，后续替换默认布局内容）
        :param parent: 父窗口
        :param current_settings: 现有预警设置（可选）
        """
        super().__init__(title=title, content=content, parent=parent)
        self.linght_chart_window = parent
        self.current_settings = current_settings
        self.setFixedSize(420, 360)
        self.setResizeEnabled(False)
        self._clean_base_widgets()
        self._init_alert_ui()
        self._init_signals()
        self._load_current_settings()

    def _clean_base_widgets(self):
        """
        清理基类默认控件（不修改基类源码，仅在子类中移除无用控件）
        避免默认标题/内容标签与预警设置控件冲突
        """
        # 移除基类默认的 titleLabel 和 contentLabel
        if hasattr(self, 'titleLabel') and self.titleLabel:
            self.textLayout.removeWidget(self.titleLabel)
            self.titleLabel.hide()
            self.titleLabel.deleteLater()

        if hasattr(self, 'contentLabel') and self.contentLabel:
            self.textLayout.removeWidget(self.contentLabel)
            self.contentLabel.hide()
            self.contentLabel.deleteLater()

        # 移除基类默认的 yesButton 和 cancelButton（替换为自定义按钮）
        if hasattr(self, 'yesButton') and self.yesButton:
            self.buttonLayout.removeWidget(self.yesButton)
            self.yesButton.hide()
            self.yesButton.deleteLater()

        if hasattr(self, 'cancelButton') and self.cancelButton:
            self.buttonLayout.removeWidget(self.cancelButton)
            self.cancelButton.hide()
            self.cancelButton.deleteLater()

    def _init_alert_ui(self):
        """
        初始化预警设置UI（复用基类的 textLayout 和 vBoxLayout，无重复布局）
        """
        # 1. 核心设置卡片（承载所有预警功能，添加到基类的 textLayout 中）
        core_card = CardWidget(self)
        card_layout = QVBoxLayout(core_card)
        card_layout.setSpacing(18)
        card_layout.setContentsMargins(20, 20, 20, 20)

        # 1.1 预警启用开关
        self.enable_switch = SwitchButton("启用价格预警", core_card)
        card_layout.addWidget(self.enable_switch)

        # 1.2 预警类型选择
        type_layout = QHBoxLayout()
        type_label = BodyLabel("预警类型：", core_card)
        self.alert_combo = ComboBox(core_card)
        self.alert_combo.addItems(["双向预警", "上破预警", "下破预警"])
        type_layout.addWidget(type_label)
        type_layout.addStretch()
        type_layout.addWidget(self.alert_combo)
        card_layout.addLayout(type_layout)

        # 1.3 上破价格设置
        up_layout = QHBoxLayout()
        up_label = BodyLabel("上破价格：", core_card)
        self.up_spin = DoubleSpinBox(core_card)
        self.up_spin.setRange(0, 1000000)
        self.up_spin.setDecimals(4)
        self.up_spin.setFixedWidth(180)
        up_layout.addWidget(up_label)
        up_layout.addStretch()
        up_layout.addWidget(self.up_spin)
        card_layout.addLayout(up_layout)

        # 1.4 下破价格设置
        down_layout = QHBoxLayout()
        down_label = BodyLabel("下破价格：", core_card)
        self.down_spin = DoubleSpinBox(core_card)
        self.down_spin.setRange(0, 1000000)
        self.down_spin.setDecimals(4)
        self.down_spin.setFixedWidth(180)
        down_layout.addWidget(down_label)
        down_layout.addStretch()
        down_layout.addWidget(self.down_spin)
        card_layout.addLayout(down_layout)

        # 2. 复用基类的 textLayout，添加核心卡片（无新布局，避免冲突）
        self.textLayout.addWidget(core_card, 0, Qt.AlignTop)
        self.textLayout.setSpacing(20)
        self.textLayout.setContentsMargins(24, 24, 24, 24)

        # 3. 复用基类的 buttonGroup 和 buttonLayout，添加自定义按钮
        self.cancel_btn = PushButton("Cancel", self.buttonGroup)
        self.confirm_btn = PrimaryPushButton("OK", self.buttonGroup)
        self.confirm_btn.setIcon(FluentIcon.ACCEPT.icon())

        # 重新布局自定义按钮
        self.buttonLayout.setSpacing(12)
        self.buttonLayout.setContentsMargins(24, 24, 24, 24)
        self.buttonLayout.addStretch()
        self.buttonLayout.addWidget(self.cancel_btn)
        self.buttonLayout.addWidget(self.confirm_btn)

        # 4. 初始状态更新（禁用输入框）
        self._update_widget_status(self.enable_switch.isChecked())

    def _init_signals(self):
        """绑定信号槽（仅关联预警功能所需信号，不改动基类逻辑）"""
        # 启用开关状态变更
        self.enable_switch.checkedChanged.connect(self._update_widget_status)
        # 预警类型变更
        self.alert_combo.currentIndexChanged.connect(
            self._on_alert_type_changed)
        # 自定义按钮点击事件
        self.cancel_btn.clicked.connect(self.reject)
        self.confirm_btn.clicked.connect(self._on_confirm_clicked)

    def _load_current_settings(self):
        """加载现有设置（填充到控件中）"""
        # 启用状态
        self.enable_switch.setChecked(
            self.current_settings.get('enabled', False))
        # 预警类型
        type_map = {'both': 0, 'up': 1, 'down': 2}
        current_type = self.current_settings.get('alert_type', 'both')
        self.alert_combo.setCurrentIndex(type_map.get(current_type, 0))
        # 价格设置
        self.up_spin.setValue(self.current_settings.get('up_price', 0.0))
        self.down_spin.setValue(self.current_settings.get('down_price', 0.0))

    def _update_widget_status(self, is_enabled: bool):
        """更新控件启用状态（跟随总开关）"""
        self.alert_combo.setEnabled(is_enabled)
        self.up_spin.setEnabled(is_enabled)
        self.down_spin.setEnabled(is_enabled)

        # 同步更新预警类型对应的输入框状态
        if is_enabled:
            self._on_alert_type_changed(self.alert_combo.currentIndex())

    def _on_alert_type_changed(self, index: int):
        """预警类型变更处理（控制输入框可用性）"""
        if not self.enable_switch.isChecked():
            return

        # 0: 双向预警, 1: 上破预警, 2: 下破预警
        if index == 1:  # 上破预警
            self.up_spin.setEnabled(True)
            self.down_spin.setEnabled(False)
            self.down_spin.setValue(0.0)
        elif index == 2:  # 下破预警
            self.up_spin.setEnabled(False)
            self.up_spin.setValue(0.0)
            self.down_spin.setEnabled(True)
        else:  # 双向预警
            self.up_spin.setEnabled(True)
            self.down_spin.setEnabled(True)

    def _validate_input(self) -> bool:
        """验证输入合法性（简洁校验，只保留核心规则）"""
        if not self.enable_switch.isChecked():
            return True

        up_price = self.up_spin.value()
        down_price = self.down_spin.value()
        alert_index = self.alert_combo.currentIndex()

        # 上破预警校验
        if alert_index == 1 and up_price <= 0:
            self._show_info_bar("警告", "上破价格必须大于0！", "warning")
            return False

        # 下破预警校验
        if alert_index == 2 and down_price <= 0:
            self._show_info_bar("警告", "下破价格必须大于0！", "warning")
            return False

        # 双向预警校验
        if alert_index == 0 and up_price > 0 and down_price > 0 and up_price <= down_price:
            self._show_info_bar("警告", "上破价格必须大于下破价格！", "warning")
            return False

        return True

    def _get_current_settings(self) -> dict:
        """获取当前控件中的设置（组装为字典）"""
        type_map = {0: 'both', 1: 'up', 2: 'down'}
        return {
            'enabled': self.enable_switch.isChecked(),
            'alert_type': type_map.get(self.alert_combo.currentIndex(), 'both'),
            'up_price': self.up_spin.value(),
            'down_price': self.down_spin.value()
        }

    def _on_confirm_clicked(self):
        """确认按钮点击处理（校验→发射信号→关闭对话框）"""
        if not self._validate_input():
            return

        # 获取当前设置并发射信号
        current_settings = self._get_current_settings()
        self.alertSettingsChanged.emit(current_settings)

        # 显示成功提示
        self._show_info_bar("成功", "价格预警设置已保存！", "success")

        # 关闭对话框
        self.accept()

    def _show_info_bar(self, title: str, content: str, info_type: str):
        """
        正确使用自定义 InfoBar 类显示提示框
        :param title: 提示标题
        :param content: 提示内容
        :param info_type: 提示类型（success/warning/info/error）
        """
        # 配置默认参数（与自定义 InfoBar 类匹配）
        duration = 2000
        position = InfoBarPosition.TOP_RIGHT
        orient = Qt.Horizontal
        is_closable = True

        # 根据提示类型调用对应的 InfoBar 类方法
        if info_type == "success":
            InfoBar.success(
                title=title,
                content=content,
                orient=orient,
                isClosable=is_closable,
                duration=duration,
                position=position,
                parent=self
            )
        elif info_type == "warning":
            InfoBar.warning(
                title=title,
                content=content,
                orient=orient,
                isClosable=is_closable,
                duration=duration,
                position=position,
                parent=self
            )
        elif info_type == "error":
            InfoBar.error(
                title=title,
                content=content,
                orient=orient,
                isClosable=is_closable,
                duration=duration,
                position=position,
                parent=self
            )
        else:  # 默认 info 类型
            InfoBar.info(
                title=title,
                content=content,
                orient=orient,
                isClosable=is_closable,
                duration=duration,
                position=position,
                parent=self
            )


class LightChartWindow(QWidget):
    """整体图表窗口"""
    current_contract: str

    def __init__(self, parent: MainWindow = None, market_watch_window: MarketWatchWindow = None, symbol: str = "", cycle: int = 60, length: int = 1000, enable_subwindow_menu: bool = False, is_static: bool = False, symbol_type: str = "FUTURES", period_milliseconds: int = None, **kwargs):
        # 调用QWidget的父类构造函数，传递parent参数
        super().__init__(parent=parent)
        self.main_window = parent
        self.market_watch_window = market_watch_window
        #assert symbol, "symbol不能为空"
        self.symbol = symbol
        self.current_contract = symbol
        self.cycle = cycle
        self.length = length
        self.enable_subwindow_menu = enable_subwindow_menu
        self.is_static = is_static  # 静态图表模式（用于回测结果展示）
        self.symbol_type = symbol_type  # 股票类型：STOCK 或 FUTURES
        self.is_stock = (symbol_type == "STOCK")
        self.period_milliseconds = period_milliseconds if period_milliseconds else cycle * 1000

        for _,v in kwargs.items():
            if isinstance(v,QWidget):
                setattr(self,v.objectName(),v)
        # self.price_scale_widthes: dict[str, int] = {}
        self.price_scale_widthes: dict[str, int] = {}
        self.visible_range = {}
        self.setObjectName(f"{symbol}_{self.cycle}")
        # from PySide6.QtWidgets import QSizePolicy as QSP
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.load_settings()
        self.__initWidget()
        self.installEventFilter(self)
        chart_cfg.chartConfigChanged.connect(self._on_chart_config_changed)
        
    def __initWidget(self):
        """初始化组件和布局"""
        # 整体垂直布局
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 绘图工具栏
        # self.drawing_toolbar = self._create_drawing_toolbar()
        # outer_layout.addWidget(self.drawing_toolbar)

        # 水平区域：图表 + 分隔线
        inner_layout = QHBoxLayout()
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)

        self.chart_window = self._create_chart()
        self.separator = self.addSeparator()
        inner_layout.addWidget(self.chart_window.get_webview(), stretch=1)
        inner_layout.addWidget(self.separator)
        outer_layout.addLayout(inner_layout, stretch=1)

    def _create_drawing_toolbar(self):
        """创建绘图工具栏"""
        toolbar = QWidget(self)
        toolbar.setFixedHeight(32)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        style_bg = 'background-color:rgba(30,30,46,0.95);border-bottom:1px solid #313244;'
        toolbar.setStyleSheet(style_bg)

        self.btn_draw_toggle = TransparentToolButton(FluentIcon.EDIT, self)
        self.btn_draw_toggle.setToolTip('绘图工具 (切换)')
        self.btn_draw_toggle.setFixedSize(28, 28)
        self.btn_draw_toggle.clicked.connect(self._toggle_drawing_tools)
        layout.addWidget(self.btn_draw_toggle)

        self.btn_draw_clear = TransparentToolButton(FluentIcon.DELETE, self)
        self.btn_draw_clear.setToolTip('清除所有画线')
        self.btn_draw_clear.setFixedSize(28, 28)
        self.btn_draw_clear.clicked.connect(self._clear_all_drawings)
        layout.addWidget(self.btn_draw_clear)

        layout.addStretch()
        return toolbar

    def _toggle_drawing_tools(self):
        """切换绘图工具显示"""
        if self.chart_window:
            self.chart_window._tool()

    def _clear_all_drawings(self):
        """清除所有画线"""
        if self.chart_window:
            self.chart_window._clear_all_drawings()

    def addSeparator(self):
        # 添加竖分隔线
        separator = QWidget()
        separator.setFixedWidth(1)
        # 根据主题设置分隔线颜色
        dark = False
        try:
            # if self.main_window and hasattr(self.main_window, 'is_dark_theme'):
            #     dark = self.main_window.is_dark_theme
            dark = isDarkTheme()
        except Exception as e:
            print(f"获取主题时出错: {e}")
        if dark:
            separator.setStyleSheet("background-color: #333333;")
        else:
            separator.setStyleSheet("background-color: #e0e0e0;")
        return separator
    
    def setSeparatorTheme(self, dark: bool=None):
        if dark is None:
            try:
                # if self.main_window and hasattr(self.main_window, 'is_dark_theme'):
                #     dark = self.main_window.is_dark_theme
                # else:
                #     dark = False
                dark = isDarkTheme()
            except Exception as e:
                print(f"获取主题时出错: {e}")
                dark = False
        # 确保分隔线是竖线
        self.separator.setFixedWidth(1)
        if dark:
            self.separator.setStyleSheet("background-color: #333333;")
        else:
            self.separator.setStyleSheet("background-color: #e0e0e0;")

    def _create_chart(self, strategy=None) -> Chart:
        """创建新图表实例（工厂方法，统一封装）"""
        # 传递None作为widget参数，避免PyQt5和PySide6的类型不兼容问题
        chart = Chart(
            self,
            symbol=self.symbol,
            cycle=self.cycle,
            length=self.length,
            is_static=self.is_static
        )
        # 设置webview的父控件为self
        chart.get_webview().setParent(self)
        
        # 图表更新器已经在Chart.__init__中初始化了，不需要再次初始化
        # chart.init_chart_updater()
        
        # 将图表添加到主窗口的更新管理器（非静态模式）
        if not self.is_static and self.main_window and hasattr(self.main_window, 'add_chart_to_updater'):
            self.main_window.add_chart_to_updater(chart)
            # print(f"图表 {self.symbol} 已添加到更新管理器")
        
        return chart

    def init_from_contract_data(self, contract_data: dict, account_info: dict = None):
        """从合约数据直接初始化图表（静态模式）

        转发调用到内部 Chart 实例。
        由 StrategyBacktestWindow._create_static_chart_window 调用。
        """
        self.chart_window.init_from_contract_data(contract_data, account_info)

    def _do_chart_replacement(self, strategy: Strategy):
        """执行图表替换：加载新图表到固定容器"""
        self.chart_window = self._create_chart(strategy)
        new_webview = self.chart_window.get_webview()
        if new_webview:
            self.chart_container.layout().addWidget(new_webview)
        self.current_strategy = strategy
        QApplication.processEvents()
        
    def setTheme(self, dark: bool=None):
        """设置图表主题"""
        if dark is None:
            dark = isDarkTheme()#self.main_window.is_dark_theme
        if self.chart_window:
            self.chart_window.setTheme(dark)
        self.setSeparatorTheme(dark)

    def replace_chart(self, strategy: Strategy):
        """
        外部调用的策略切换入口（线程安全、校验前置）
        :param strategy: 目标策略对象，为None则不执行切换
        """
        QTimer.singleShot(50, lambda: self._start_chart_replacement(strategy))

    def _start_chart_replacement(self, strategy: Strategy):
        """切换流程主控：清理旧资源 -> 创建新图表"""
        # 安全清理旧组件
        self._safe_clear_container()
        # 加载新图表
        self._do_chart_replacement(strategy)

    def _safe_clear_container(self):
        """安全清空图表容器：释放旧组件、清理布局、回收内存"""
        # 1. 清理旧Chart对象资源
        if self.chart_window:
            try:
                # 调用业务层清理方法（定时器、网络、API连接）
                self.chart_window.cleanup()
            except Exception as e:
                print(f"清理旧图表资源失败: {str(e)}")

            # 2. 从布局中移除WebView组件
            old_webview = self.chart_window.get_webview()
            if old_webview and old_webview.parent() == self.chart_container:
                self.chart_container.layout().removeWidget(old_webview)
                old_webview.setParent(None)
                old_webview.deleteLater()

            # 3. 释放图表对象引用
            self.chart_window = None

        # 4. 清空布局所有组件（兜底处理）
        layout = self.chart_container.layout()
        while layout.count() > 0:
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    # 修改LightChartWindow的load_settings方法
    def load_settings(self, default: bool = False):
        """从 chart_data.json 加载数据，从 setting.json 加载配置"""
        # 从ChartDataManager加载数据
        self.drawings = chart_data_manager.drawings.get(self.symbol, {})
        self.price_alert = chart_data_manager.price_alerts.get(self.symbol, {})
        
        # 加载配置项
        self.mouse_label_color: str = chart_cfg.mouseLabelColor.value
        self.istool: bool = chart_cfg.showToolBox.value
        self.bear_color: str = chart_cfg.bearColor.value
        self.bull_color: str = chart_cfg.bullColor.value

    def eventFilter(self, obj, event):
        """事件过滤器，处理键盘快捷键"""
        # 只处理键盘按下事件
        if event.type() == QEvent.Type.KeyPress:
            # 获取当前激活的webview
            webview = self.chart_window.get_webview()

            # 确保事件来自webview或者窗口本身
            if obj == webview or obj == self:
                key = event.key()
                # modifiers = event.modifiers()

                # ========== 完善键盘事件映射 ==========
                # 放大：上箭头 或 + 键
                if key == Qt.Key.Key_Up or key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
                    self.chart_window.zoom_in()
                    return True  # 拦截事件，避免传递给其他组件
                # 缩小：下箭头 或 - 键
                elif key == Qt.Key.Key_Down or key == Qt.Key.Key_Minus:
                    self.chart_window.zoom_out()
                    return True
                # 向左平移：左箭头
                elif key == Qt.Key.Key_Left:
                    self.chart_window.pan_left()
                    return True
                # 向右平移：右箭头
                elif key == Qt.Key.Key_Right:
                    self.chart_window.pan_right()
                    return True
                elif key == Qt.Key.Key_Space:
                    self.chart_window.center_on_latest()
                    return True

        # 其他事件交给父类处理
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        """清理图表资源"""
        # 从主窗口的更新管理器中移除图表
        if self.main_window and hasattr(self.main_window, 'remove_chart_from_updater'):
            self.main_window.remove_chart_from_updater(self.chart_window)
            # print(f"图表 {self.symbol} 已从更新管理器移除")
        
        # 停止图表更新器
        # if hasattr(self.chart_window, 'stop_chart_updater'):
        #     self.chart_window.stop_chart_updater()
        
        self.chart_window.cleanup()
        if hasattr(self, 'cursor_check_timer'):
            self.cursor_check_timer.stop()
        super().closeEvent(event)
        
    @property
    def is_update(self)-> bool:
        """检查图表是否正在更新"""
        return self.main_window.is_update
    
    def reload_chart(self, cycle):
        """
        重新加载图表数据
        
        Args:
            period_milliseconds: 周期（毫秒）
        """
        if self.chart_window:
            # 相同周期无需切换
            if cycle == self.cycle:
                return
            
            # 股票周期校验：只允许 StockApi.PERIOD_TO_FREQUENCY 中的周期
            if self.is_stock:
                from ..common.stock_api import StockApi
                if cycle not in StockApi.PERIOD_TO_FREQUENCY:
                    from qfluentwidgets import InfoBar, InfoBarPosition
                    period_name = f"{cycle}秒" if cycle < 3600 else f"{cycle//3600}小时"
                    InfoBar.warning(
                        '周期不支持',
                        f"股票数据源不支持 {period_name} 周期，请选择其他周期",
                        duration=3000,
                        parent=self,
                        position=InfoBarPosition.TOP_RIGHT
                    )
                    return
                
                # 先取消旧周期的订阅
                if hasattr(self, 'main_window') and \
                   hasattr(self.main_window, 'stock_api') and self.main_window.stock_api:
                    try:
                        self.main_window.stock_api.unsubscribe(self.symbol, self.cycle)
                    except Exception as e:
                        print(f"[chart] 取消旧周期订阅失败: {e}")
            self.cycle = cycle
            self.chart_window.reload_chart(cycle)
            
    def _tool(self):
        """调用前端工具箱方法"""
        self.chart_window._tool()
        
        
    def kline_update(self):
        """更新K线数据"""
        self.chart_window.kline_update()
        
    def indicator_update(self):
        """更新指标数据"""
        self.chart_window.indicator_update()
    
    # def send_indicator_operation(self, ind_cls: str, name: str, params: dict = {}):
    #     """
    #     发送指标操作
    #     :param ind_cls: 指标类名
    #     :param name: 指标名称
    #     :param params: 指标参数
    #     """
    #     if self.chart_window:
    #         self.chart_window.send_indicator_operation(ind_cls, name, params)

    def _on_chart_config_changed(self):
        """图表配置变更时的回调"""
        # 更新颜色设置
        self.mouse_label_color = chart_cfg.mouseLabelColor.value
        self.bear_color = chart_cfg.bearColor.value
        self.bull_color = chart_cfg.bullColor.value
        self.istool = chart_cfg.showToolBox.value
        
        # 如果图表已初始化，更新图表样式
        if hasattr(self, 'chart_window') and self.chart_window:
            try:
                # 更新K线颜色
                self.chart_window.candle_style(
                    up_color=self.bull_color,
                    down_color=self.bear_color
                )
                # 更新鼠标标签颜色
                self.chart_window.set_crosshair_label_background(
                    self.chart_window.chart, 
                    self.mouse_label_color
                )
                if self.istool:
                    self.chart_window.init_toolbox()
                else:
                    self.chart_window.remove_toolbox()
            except Exception as e:
                print(f"更新图表配置失败: {e}")
    
    # def send_indicator_operation(self, operation: str, ind_cls: str, name: str, params: dict = None):
    #     """
    #     通过 LightChartWindow 发送指标操作信号
    #     :param operation: 操作类型 ('add')
    #     :param ind_cls: 指标类名
    #     :param name: 指标名称
    #     :param params: 指标参数字典
    #     """
    #     if self.chart_window:
    #         self.chart_window.send_indicator_operation(operation, ind_cls, name, params)
    
    def remove_indicator(self, indicator_id: int):
        """
        通过 LightChartWindow 移除指标
        :param indicator_id: 要移除的指标ID
        """
        if self.chart_window:
            # self.chart_window.remove_indicator(indicator_id)
            self.chart_window.chart_updater._is_indicator_calculating = True
            # 从指标管理器移除指标
            self.chart_window.chart_updater.remove_indicator(indicator_id)
            # 从图表上移除指标
            self.chart_window.remove_indicator(indicator_id)
            self.chart_window.chart_updater._is_indicator_calculating = False
            # print(f"已从指标管理器和图表更新器移除指标: {indicator_id}")
            QTimer.singleShot(500, self.reset_cursor_change)
    
    def add_indicator_to_manager(self, class_name: str, indicator_name: str, params: dict = None):
        """
        添加指标到指标管理器
        :param class_name: 指标类名
        :param indicator_name: 指标名称
        :param params: 指标参数字典，默认为空字典
        """
        if not params:
            params = {}
        
        if self.chart_window:
            # 1. 添加指标前将 ChartUpdater._is_indicator_calculating 设置为 True
            # 确保指标管理器指标计算为跳过状态
            if hasattr(self.chart_window, 'chart_updater') and self.chart_window.chart_updater:
                # 确保计算状态为 True
                self.chart_window.chart_updater._is_indicator_calculating = True
                # print(f"已设置 _is_indicator_calculating 为 True")
            
            # 2. 添加指标到指标管理器
            # print(f"添加指标到指标管理器: {class_name}.{indicator_name}")
            self.chart_window.send_indicator_operation(class_name, indicator_name, params)
            # print(self.chart_window.chart_updater.worker.indicator_manager.indicators)
            # 3. 计算指标并初始化指标显示
            # print(f"计算指标并初始化显示: {class_name}.{indicator_name}")
            # 直接从指标管理器计算指标并显示
            if hasattr(self.chart_window, 'chart_updater') and self.chart_window.chart_updater:
                worker = self.chart_window.chart_updater.worker
                if worker and hasattr(worker, 'indicator_manager'):
                    # 获取当前K线数据
                    if hasattr(self.chart_window, '_kline') and self.chart_window._kline is not None:
                        kline_data = self.chart_window.get_new_kline()
                        # 计算指标
                        indicator = self.chart_window.chart_updater.worker.indicator_manager.calculate_last_indicators(kline_data)
                    # 检查指标是否计算成功
                    if indicator is None:
                        # print("指标计算失败，可能是指标管理器中没有指标")
                        # 等待一段时间后重新尝试
                        QTimer.singleShot(100, lambda: self._retry_add_indicator(class_name, indicator_name, params))
                        return
                    # 检查指标管理器中是否有指标
                    if not self.chart_window.chart_updater.worker.indicator_manager.indicators:
                        # print("指标管理器中没有指标，无法获取指标ID")
                        # 等待一段时间后重新尝试
                        QTimer.singleShot(100, lambda: self._retry_add_indicator(class_name, indicator_name, params))
                        return
                    indicator_id = self.chart_window.chart_updater.worker.indicator_manager.indicators[-1].id
                    try:
                        self.chart_window.add_indicator(indicator_id, indicator, kline_data)
                        # print(f"已显示指标: {indicator_name}")
                        QTimer.singleShot(500, self.chart_window._on_indicator_loaded)
                    except Exception as e:
                        print(f"显示指标时出错: {str(e)}")
                        
                        # 等待一段时间后重新尝试
                        QTimer.singleShot(100, lambda: self._retry_add_indicator(class_name, indicator_name, params))
            
            # 4. 再恢复 ChartUpdater._is_indicator_calculating 为 False
            if hasattr(self.chart_window, 'chart_updater') and self.chart_window.chart_updater:
                self.chart_window.chart_updater._is_indicator_calculating = False
                # print(f"已恢复 _is_indicator_calculating 为 False")
    
    def _retry_add_indicator(self, class_name, indicator_name, params):
        """重新尝试添加指标"""
        # print(f"重新尝试添加指标: {class_name}.{indicator_name}")
        # 检查指标管理器中是否有指标
        if hasattr(self.chart_window, 'chart_updater') and self.chart_window.chart_updater:
            worker = self.chart_window.chart_updater.worker
            if worker and hasattr(worker, 'indicator_manager') and worker.indicator_manager.indicators:
                # 获取当前K线数据
                if hasattr(self.chart_window, '_kline') and self.chart_window._kline is not None:
                    kline_data = self.chart_window.get_new_kline()
                    # 计算指标
                    indicator = worker.indicator_manager.calculate_last_indicators(kline_data)
                    if indicator is not None:
                        indicator_id = worker.indicator_manager.indicators[-1].id
                        try:
                            self.chart_window.add_indicator(indicator_id, indicator, kline_data)
                            # print(f"已显示指标: {indicator_name}")
                            QTimer.singleShot(500, self.chart_window._on_indicator_loaded)
                        except Exception as e:
                            print(f"显示指标时出错: {str(e)}")
            # else:
            #     print("指标管理器中仍然没有指标，无法重新尝试")
        

class CustomToolBox(ToolBox):
    def __init__(self, chart: Chart):
        self.run_script = chart.run_script
        self.id = chart.id
        self.drawings = {}
        self.chart = chart
        self.window = chart.light_chart_window
        self._save_under = self.window
        # 绑定前端保存画线的回调
        chart.win.handlers[f'save_drawings{self.id}'] = self._save_drawings
        # 创建前端工具箱
        self.run_script(f'{self.id}.createToolBox()')

    def load_drawings(self, tag: str):
        """加载历史画线数据"""
        target_drawings = self.window.drawings.get(tag)
        if not target_drawings:
            target_drawings = self.drawings.get(tag)
        if not target_drawings:
            return
        self.run_script(
            f'if ({self.id}.toolBox) {self.id}.toolBox.loadDrawings({json.dumps(target_drawings)})'
        )

    def _save_drawings(self, drawings: str):
        """前端回调：持久化画线数据"""
        if not self._save_under:
            return
        parsed_drawings = json.loads(drawings)
        tag = self._save_under.current_contract
        self.drawings[tag] = parsed_drawings
        self.window.drawings[tag] = parsed_drawings

    def clear_drawings(self):
        """清空当前合约所有画线，保留工具实例"""
        js_script = f"""
        try {{
            if ({self.id}.toolBox) {{
                {self.id}.toolBox.clearDrawings();
            }}
        }} catch (e) {{
            console.error('清空画线失败：', e);
        }}
        """
        self.run_script(js_script)
        # 清理Python端缓存
        tag = self._save_under.current_contract
        self.drawings.pop(tag, None)
        self.window.drawings.pop(tag, None)

    def hide_toolbox(self):
        """
        核心方法：强制隐藏工具箱，屏蔽交互，兼容所有渲染场景
        替代DOM查找/移除，解决元素定位失败问题
        """
        js_script = f"""
        try {{
            // 1. 清空所有画线图形
            if ({self.id}.toolBox) {{
                {self.id}.toolBox.clearDrawings();
            }}
            // 2. 全局样式覆盖：隐藏所有lightweight-charts工具箱控件（通用选择器）
            const style = document.createElement('style');
            style.id = '{self.id}-toolbox-hide-style';
            style.textContent = `
                /* 隐藏工具箱容器、按钮、绘图面板 */
                .tv-lightweight-charts-toolbox,
                .tv-toolbox-container,
                [class*="toolbox"],
                [data-toolbox="true"] {{
                    display: none !important;
                    visibility: hidden !important;
                    pointer-events: none !important;
                    opacity: 0 !important;
                }}
            `;
            // 移除旧样式，插入新样式
            const oldStyle = document.getElementById('{self.id}-toolbox-hide-style');
            if (oldStyle) oldStyle.remove();
            document.head.appendChild(style);
            
            // 3. 置空JS引用，禁止后续调用
            {self.id}.toolBox = null;
            console.log('画线工具已隐藏并禁用');
        }} catch (e) {{
            console.error('隐藏工具箱失败：', e);
        }}
        """
        self.run_script(js_script)

    def show_toolbox(self):
        """重新显示工具箱，清理隐藏样式（用于重新初始化）"""
        js_script = f"""
        try {{
            // 移除隐藏样式
            const style = document.getElementById('{self.id}-toolbox-hide-style');
            if (style) style.remove();
            console.log('工具箱样式已恢复');
        }} catch (e) {{
            console.error('恢复工具箱样式失败：', e);
        }}
        """
        self.run_script(js_script)

    def cleanup(self):
        """完整资源清理：隐藏工具+清理数据+解绑事件"""
        self.hide_toolbox()
        # 清理Python端事件回调，防止内存泄漏
        handler_key = f'save_drawings{self.id}'
        if hasattr(self.chart.win, 'handlers') and handler_key in self.chart.win.handlers:
            del self.chart.win.handlers[handler_key]
        # 清空所有画线数据
        self.drawings.clear()
        self.window.drawings.clear()

class ChartUpdater(QObject):
    """
    图表更新管理器 - 常驻工作线程 + 定时数据获取模式
    用于处理K线和指标的异步计算与UI更新
    
    工作流程：
    1. ui_timer 定时触发 _fetch_and_process_data()
    2. 从 Chart 获取最新数据（通过回调函数）
    3. 将数据发送给 worker 线程计算
    4. 计算完成后自动更新 UI
    """
    # 信号定义
    kline_data_ready = pyqtSignal(object)       # K线计算完成信号
    indicator_data_ready = pyqtSignal(object)   # 指标计算完成信号
    calculation_error = pyqtSignal(str)      # 计算错误信号
    
    def __init__(self, parent:Chart=None, local_data_mode: bool = False):
        super().__init__(parent)
        self._chart_ref = parent           # Chart 实例引用
        self._is_running = False
        self._last_kline_data = None     # 上次K线数据（用于比较变化）
        self._last_indicator_data = None # 上次指标数据
        self._is_kline_calculating = False  # K线计算状态
        self._is_indicator_calculating = False  # 指标计算状态
        self._calculation_lock = QMutex()  # 计算状态锁
        self._local_data_mode = local_data_mode  # 本地数据模式
        self._init_worker_thread()
        
    def _init_worker_thread(self):
        """初始化常驻工作线程"""
        self.worker_thread = QThread(self)
        self.worker = ChartCalculationWorker(self._chart_ref)
        self.worker.moveToThread(self.worker_thread)
        
        # 连接工作线程信号
        self.worker.kline_calculated.connect(self._on_kline_calculated)
        self.worker.indicator_calculated.connect(self._on_indicator_calculated)
        self.worker.calculation_error.connect(self._on_calculation_error)
        
        self.worker_thread.start()
        
    def start(self):
        """
        启动更新管理器
        :param kline_interval: K线更新间隔（毫秒）
        :param indicator_interval: 指标更新间隔（毫秒）
        """
        # 注意：定时器现在由 ChartUpdateManager 统一管理
        # 这里只需要启动工作线程
        self._is_running = True
        
    def stop(self):
        """停止更新管理器"""
        self._is_running = False
        # 注意：定时器现在由 ChartUpdateManager 统一管理
        # 这里只需要停止工作线程
        self.worker_thread.quit()
        self.worker_thread.wait(5000)
        
    def _fetch_and_process_kline(self):
        """
        K线定时器回调 - 获取K线数据并发送给工作线程计算
        此方法在主线程执行
        注意：现在由 ChartUpdateManager 统一调用
        """
        if not self._is_running:
            return
        # 本地数据模式下跳过K线更新
        if self._local_data_mode:
            return
        # 获取K线数据并发送计算
        kline_data = self._chart_ref._fetch_kline_data()
        if kline_data is not None:
            self._send_kline_to_worker(kline_data)
            
    def _fetch_and_process_indicator(self):
        """
        指标定时器回调 - 获取指标数据并发送给工作线程计算
        此方法在主线程执行
        注意：现在由 ChartUpdateManager 统一调用
        """
        if not self._is_running:
            # print("_is_running 为 False，跳过")
            return
        # 本地数据模式下跳过指标更新
        if self._local_data_mode:
            return
        # 获取指标数据并发送计算
        indicator_data = self._chart_ref._fetch_indicator_data()
        if indicator_data is not None:
            self._send_indicator_to_worker(indicator_data)
            
    def _fetch_kline_data(self) -> pd.DataFrame:
        """
        获取K线原始数据
        :return: K线数据DataFrame，无数据返回 None
        """
        return self._chart_ref._fetch_kline_data()
        
    def _fetch_indicator_data(self) -> pd.DataFrame:
        """
        获取指标原始数据
        :return: 指标数据DataFrame，无数据返回 None
        """
        return self._chart_ref._fetch_indicator_data()
        
    def _send_kline_to_worker(self, raw_data: pd.DataFrame):
        """发送K线数据到工作线程"""
        self._calculation_lock.lock()
        try:
            if self._is_kline_calculating:
                # print("K线计算正在进行，跳过本次任务")
                return
            self._is_kline_calculating = True
        finally:
            self._calculation_lock.unlock()
        task = {
            'data': raw_data
        }
        self.worker.calculate_kline_signal.emit(task)
        
    def _send_indicator_to_worker(self, raw_data: pd.DataFrame):
        """发送指标数据到工作线程"""
        self._calculation_lock.lock()
        try:
            if self._is_indicator_calculating:
                # print("指标计算正在进行，跳过本次任务")
                return
            self._is_indicator_calculating = True
        finally:
            self._calculation_lock.unlock()
        result={
            'data': raw_data,
        }
        self.worker.calculate_indicator_signal.emit(result)
        
    def _on_kline_calculated(self, result: dict):
        """K线计算完成回调 - 在工作线程，即时触发UI更新"""
        # 重置计算状态
        self._calculation_lock.lock()
        try:
            self._is_kline_calculating = False
        finally:
            self._calculation_lock.unlock()
        self.kline_data_ready.emit(result)

    def _on_indicator_calculated(self, result: dict):
        """指标计算完成回调 - 在工作线程，即时触发UI更新"""
        # 重置计算状态
        self._calculation_lock.lock()
        try:
            self._is_indicator_calculating = False
        finally:
            self._calculation_lock.unlock()
        self.indicator_data_ready.emit(result)
        
    def set_indicator_calculated_status(self, status: bool=False):
        # 重置计算状态
        self._calculation_lock.lock()
        try:
            self._is_indicator_calculating = status
        finally:
            self._calculation_lock.unlock()

    def _on_calculation_error(self, error_msg: str):
        """计算错误回调"""
        # 重置计算状态，避免因错误导致计算状态一直为True
        self._calculation_lock.lock()
        try:
            self._is_kline_calculating = False
            self._is_indicator_calculating = False
        finally:
            self._calculation_lock.unlock()
        
        self.calculation_error.emit(error_msg)
    
    def send_indicator_operation(self, ind_cls: str,name:str, params: dict = {}):
        """
        发送指标操作信号给 worker
        :param ind_cls: 指标类名
        :param name: 指标实例名，用于唯一标识指标
        :param params: 参数字典
        """
        if hasattr(self, 'worker'):
            self.worker.indicator_operation_signal.emit(ind_cls,name, params)
    
    def remove_indicator(self, indicator_id: int):
        """
        发送移除指标信号给 worker
        :param indicator_id: 要移除的指标ID
        """
        if hasattr(self, 'worker'):
            self.worker.indicator_removed_signal.emit(indicator_id)


class ChartCalculationWorker(QObject):
    """
    图表计算工作类 - 在独立线程中运行
    负责K线和指标的复杂计算
    """
    # 信号定义
    calculate_kline_signal = pyqtSignal(object)       # 接收K线计算任务
    calculate_indicator_signal = pyqtSignal(object)   # 接收指标计算任务
    kline_calculated = pyqtSignal(object)          # K线计算完成 - 使用object避免复制
    indicator_calculated = pyqtSignal(object)      # 指标计算完成 - 使用object避免复制
    calculation_error = pyqtSignal(str)            # 计算错误
    # 指标操作信号
    indicator_operation_signal = pyqtSignal(str, str, object)  # 指标类, 指标名称, 参数
    indicator_removed_signal = pyqtSignal(int)      # 移除指标，参数是指标ID
    
    def __init__(self, chart_ref: Chart):
        super().__init__()
        self._chart_ref = chart_ref
        self._connect_signals()
        self.indicator_manager = IndicatorManager()
        
    def _connect_signals(self):
        """连接信号到槽函数"""
        self.calculate_kline_signal.connect(self._calculate_kline)
        self.calculate_indicator_signal.connect(self._calculate_indicator)
        # 使用 BlockingQueuedConnection：主线程 emit 后阻塞直到 worker 线程处理完毕，
        # 避免 add_indicator_to_manager 中 indicators[-1] 拿到上一个未更新的指标
        self.indicator_operation_signal.connect(self._on_indicator_operation, Qt.ConnectionType.BlockingQueuedConnection)
        self.indicator_removed_signal.connect(self._on_indicator_removed)
        
    def _calculate_kline(self, task: dict):
        """
        计算K线数据 - 在工作线程
        :param task: 任务字典 {type, data, timestamp, success}
        """
        # 检查任务是否有效
        try:
            # TODO: 实现K线计算逻辑
            # 例如：根据tick数据生成OHLC
            result = self._do_kline_calculation(task['data'])
            
            self.kline_calculated.emit(result)
        except Exception as e:
            self.calculation_error.emit(f"K线计算错误: {str(e)}")
            
    def _calculate_indicator(self, task: dict):
        """
        计算指标数据 - 在工作线程
        :param task: 任务字典 {type, name, data, parameters, timestamp, success, indicator_configs}
        """
        try:
            indicators = self.indicator_manager.calculate_indicators(task['data'])
            self.indicator_calculated.emit(indicators)
        except Exception as e:
            self.calculation_error.emit(f"指标计算错误: {str(e)}")
    
    @pyqtSlot(str, str, dict)
    def _on_indicator_operation(self, ind_cls: str, name: str, params: dict):
        """
        处理指标操作信号
        :param ind_cls: 指标类名
        :param name: 指标名称
        :param params: 指标参数字典
        """
        try:
            
            self.indicator_manager.addIndicator(ind_cls, name, params)
        except Exception as e:
            self.calculation_error.emit(f"添加指标错误: {str(e)}")
    
    @pyqtSlot(int)
    def _on_indicator_removed(self, indicator_id: int):
        """
        处理指标移除信号
        :param indicator_id: 要移除的指标ID
        """
        try:
            self.indicator_manager.removeIndicator(indicator_id)
        except Exception as e:
            self.calculation_error.emit(f"移除指标错误: {str(e)}")
            
    def _do_kline_calculation(self, raw_data: pd.DataFrame) -> dict:
        """
        执行K线具体计算
        :param raw_data: 原始行情数据
        :return: 计算后的K线数据
        """
        # TODO: 实现具体的K线计算逻辑
        try:
            kline = raw_data
            data = {}
            latest_tick_time = self._chart_ref.last_datetime
            chang = self._chart_ref.is_changing(
                self._chart_ref.chart, latest_tick_time)

            #更新频率高的条件放前面
            if chang == 0:
                series = kline.iloc[-1][FILED.TCV]
                series.index = FILED.TPV
                data["update_from_tick"]=series
            elif chang == 1:
                series = kline.iloc[-2][FILED.TCV]
                series.index = FILED.TPV
                data["update_from_tick"]=series
                data["update"]=kline.iloc[-1]
            else:
                data["update"]=kline.iloc[-1]
            return data
        except Exception as e:
            self.calculation_error.emit(f"K线计算错误: {str(e)}")
            return {}


class Chart(QObject):
    """lightweight_charts Chart"""
    chart: QtChart
    toolbox: CustomToolBox
    position_horizontal_line: HorizontalLine
    chart_indicators: dict[str, dict[str, Line]]
    subcharts: dict[str, AbstractChart]
    data_thread: Optional[QThread]
    chart_updater: Optional[ChartUpdater]  # 图表更新管理器

    def __init__(self, widget: LightChartWindow = None, inner_width: float = 1.0, inner_height: float = 1.0,
                 scale_candles_only: bool = False, symbol: str = "", cycle: int = 60, is_static: bool = False, is_stock: bool = False, length: int = 1000):
        super().__init__()
        toolbox = False if widget is None or widget.istool is None else widget.istool
        # 获取Chart类
        ChartClass = get_chart_class()
        # 创建图表实例
        self.chart = ChartClass(None, inner_width, inner_height, scale_candles_only, toolbox)
        self.main_chart_id: str = self.chart.id
        self.chart.events.watch_cursor_change()
        # self.chart.events.right_click()  # 注释掉：会导致画线右键菜单与图表菜单同时出现
        # window=self.chart.win
        # def run_script(script, callback=None):
        #     window.run_script(script, 0, callback)
        # self.chart.run_script = run_script
        self.light_chart_window = widget
        self.symbol = symbol
        self.cycle = cycle
        self.length = length
        self.is_static = is_static  # 静态图表模式标志
        # 获取 is_stock 属性：优先从参数，其次从 widget
        if widget and hasattr(widget, 'symbol_type'):
            self.is_stock = widget.symbol_type == "STOCK"
        elif widget and hasattr(widget, 'is_stock'):
            self.is_stock = widget.is_stock
        else:
            self.is_stock = is_stock
        self.chart_indicators = {}
        self.subcharts = {}
        self.markers={}
        self.signal_indicators = {}
        self._signal_markers = {}  # (indicator_id, sk, time_key) -> marker_id 用于精确追踪信号标记
        self.toolbox = None
        self.chart_updater = None  # 图表更新管理器实例
        self.ind_colors = get_colors()
        if toolbox:
            self.toolbox = CustomToolBox(self)
        self._new_bar_event = False
        self._saved_visible_range = None
        self._webview_loadfinished = False
        self._is_update = False  # 初始化_is_update属性
        self._is_reloading = False  # 初始化_is_reloading属性
        self._indicator_card_visible=False
        self._is_subchart=False
        self._last_chart_id=self.main_chart_id
        webview = self.get_webview()
        # 启用鼠标跟踪（可选，但建议开启）
        # webview.setMouseTracking(True)
        # 连接光标变化信号
        # webview.cursorChanged.connect(self.on_cursor_change)
        
        webview.page().loadFinished.connect(self._on_webview_loaded)
        webview.setContextMenuPolicy(Qt.CustomContextMenu)
        webview.customContextMenuRequested.connect(
            self._on_webview_custom_context_menu)
        # webview.cursorChanged.connect(self.on_cursor_change)
        
        # 在WebView加载完成后添加错误处理
        #webview.page().loadFinished.connect(self._on_webview_loaded_with_error_handling)

        # 静态图表模式不启动图表更新管理器
        if not self.is_static:
            self.init_chart_updater()
        self._init_chart_data()
        
        # self._register_cursor_handler()   # 新增
        # self.chart.events.cursor_change += self.on_cursor_change
        
    # def on_cursor_change(self, cursor: QCursor):
    #     """当 WebView 内光标形状改变时自动调用"""
    #     try:
    #         shape = cursor.shape()
    #         print(f"当前光标形状: {shape}")
    #         if shape == Qt.IBeamCursor:
    #             print("✅ 鼠标悬停在指标标签上 (IBeamCursor)")
    #             # 你的业务逻辑，例如高亮指标
    #         elif shape == Qt.ArrowCursor:
    #             print("👈 鼠标离开指标标签 (ArrowCursor)")
    #         else:
    #             print(f"光标变为其他形状: {shape}")
    #     except Exception as e:
    #         print(f"光标变化处理错误: {str(e)}")
    
    @property
    def indicator_manager(self)->IndicatorManager:
        """获取指标管理器"""
        return self.chart_updater.worker.indicator_manager
    
    @property
    def main_chart_indicators(self)->list[Indicator]:
        """获取主图表指标"""
        return self.indicator_manager.get_main_chart_indicators(self.main_chart_id)
    
    @property
    def sub_chart_indicators(self) -> list[Indicator]:
        """获取子图表指标"""
        return self.indicator_manager.get_sub_chart_indicators(self.main_chart_id)
    
    @property
    def main_window(self):
        """获取主窗口"""
        if self.light_chart_window:
            return self.light_chart_window.main_window
        return None
    
    @property
    def api(self):
        """获取API实例（根据 is_stock 返回对应的 API）"""
        if self.is_stock:
            # 股票模式：返回 stock_api
            if self.main_window and hasattr(self.main_window, 'stock_api'):
                return self.main_window.stock_api
            return None
        else:
            # 期货模式：返回 tq_api
            if self.light_chart_window and hasattr(self.light_chart_window, 'api'):
                return self.light_chart_window.api
            return None
    
    def get_subchart_indicator(self, indicator_id: int)->Indicator:
        """获取子图表指标"""
        return self.indicator_manager.get_subchart_indicator(indicator_id)

    def _on_webview_loaded_with_error_handling(self, ok):
        """
        在WebView加载完成后添加错误处理
        """
        if ok:
            # 重新设置window.callbackFunction，确保window.pythonObject已经创建
            self.get_webview().page().runJavaScript('''
                if (window.pythonObject && typeof window.pythonObject.callback === 'function') {
                    window.callbackFunction = window.pythonObject.callback;
                    console.log('✅ 已重新设置window.callbackFunction');
                } else {
                    console.log('❌ window.pythonObject尚未创建，延迟设置callbackFunction');
                    // 延迟100ms后再次尝试
                    setTimeout(function() {
                        if (window.pythonObject && typeof window.pythonObject.callback === 'function') {
                            window.callbackFunction = window.pythonObject.callback;
                            console.log('✅ 延迟后已设置window.callbackFunction');
                        } else {
                            console.log('❌ 无法设置window.callbackFunction，window.pythonObject不存在');
                        }
                    }, 100);
                }
            ''', 0)#, lambda res: print("✅ 已尝试重新设置window.callbackFunction"))
            
            # 添加全局错误处理
            self._add_global_error_handler()

    def _add_global_error_handler(self):
        """
        添加全局错误处理，捕获并处理所有错误
        """
        error_handler_js = '''
        // 立即执行错误处理代码
        (function() {
            // 定义需要过滤的错误关键词
            const FILTERED_ERRORS = [
                'Value is null',
                'Cannot read properties of undefined',
                'Cannot read properties of null',
                'Cannot read property',
                'undefined is not an object',
                'null is not an object',
                'Uncaught Error'
            ];
            
            // 检查是否应该过滤错误
            function shouldFilterError(message) {
                if (!message) return false;
                const msg = String(message).toLowerCase();
                return FILTERED_ERRORS.some(keyword => 
                    String(message).includes(keyword) || msg.includes(keyword.toLowerCase())
                );
            }
            
            // 保存原始的console.error
            const originalConsoleError = console.error;
            
            // 重写console.error，过滤掉常见错误
            console.error = function(...args) {
                const message = args.join(' ');
                if (!shouldFilterError(message)) {
                    originalConsoleError.apply(console, args);
                }
            };
            
            // 重写window.onerror，捕获所有未处理的错误
            window.onerror = function(message, source, lineno, colno, error) {
                if (shouldFilterError(message)) {
                    return true;
                }
                // 其他错误仍然显示
                originalConsoleError.apply(console, ['Error:', message, source, lineno, colno, error]);
                return false;
            };
            
            // 添加error事件监听作为备用
            window.addEventListener('error', function(event) {
                if (shouldFilterError(event.message) || shouldFilterError(event.error)) {
                    event.preventDefault();
                    event.stopPropagation();
                }
            }, true);
            
            // 重写Promise的unhandledrejection事件
            window.addEventListener('unhandledrejection', function(event) {
                if (shouldFilterError(event.reason) || 
                    (event.reason && shouldFilterError(event.reason.message))) {
                    event.preventDefault();
                } else {
                    originalConsoleError.apply(console, ['Unhandled Rejection:', event.reason]);
                }
            });
            
            // 重写console.warn，过滤掉常见警告
            const originalConsoleWarn = console.warn;
            console.warn = function(...args) {
                const message = args.join(' ');
                if (!shouldFilterError(message)) {
                    originalConsoleWarn.apply(console, args);
                }
            };
            
            // 为window.bridge添加安全的callback方法
            if (!window.bridge || typeof window.bridge.callback !== 'function') {
                window.bridge = window.bridge || {};
                window.bridge.callback = function(message) {
                    console.log('Bridge callback called before initialization:', message);
                };
            }
            
            console.log('全局错误处理已添加');
        })();
        '''
        
        # 执行错误处理脚本
        self.get_webview().page().runJavaScript(error_handler_js, 0)#, lambda res: print("✅ 已添加全局错误处理"))

    def list_chart_elements(self):
        """
        列出图表中的所有元素，用于调试
        """
        js = '''
        // 列出window对象中的所有图表实例
        (function() {
            const chartInstances = [];
            for (const key in window) {
                if (typeof window[key] === 'object' && window[key] !== null) {
                    if (window[key].chart) {
                        chartInstances.push({
                            id: key,
                            hasDiv: !!window[key].div,
                            hasLegend: !!window[key].legend,
                            hasSeries: window[key].chart && window[key].chart.series ? window[key].chart.series().length : 0
                        });
                    }
                }
            }
            console.log('Chart instances:', chartInstances);
            return chartInstances;
        })();
        '''
        
        # def handle_result(result):
        #     # print("图表实例列表:")
        #     if result:
        #         for instance in result:
        #             print(f"  - ID: {instance['id']}, 有div: {instance['hasDiv']}, 有legend: {instance['hasLegend']}, 系列数: {instance['hasSeries']}")
        #     else:
        #         print("  没有找到图表实例")
        
        self.get_webview().page().runJavaScript(js, 0)#, handle_result)

    def delete_subchart(self, subchart_id: int):
        """
        删除副图
        
        Args:
            subchart_id: 副图ID
        """
        if subchart_id in self.subcharts:
            subchart = self.subcharts[subchart_id]
            subchart.resize(1., 0.)
            # 从DOM中移除副图的div元素
            id = subchart.id
            
            # 安全 JS：不存在/已删除也不会报错
            js = f"""
            if (typeof {id} !== 'undefined') {{
                console.log('删除副图:', {id});
                
                // 1. 隐藏副图的标签
                if ({id}.legend) {{
                    try {{
                        {id}.legend.applyOptions({{ visible: false }});
                        console.log('隐藏了副图标签');
                    }} catch (e) {{
                        console.log('Error hiding legend:', e);
                    }}
                }}
                
                // 2. 移除副图的所有系列
                if ({id}.chart && {id}.chart.series) {{
                    try {{
                        const series = {id}.chart.series();
                        console.log('副图系列数:', series.length);
                        series.forEach(function(series) {{
                            try {{
                                {id}.chart.removeSeries(series);
                                console.log('移除了系列:', series);
                            }} catch (e) {{
                                console.log('Error removing series:', e);
                            }}
                        }});
                    }} catch (e) {{
                        console.log('Error accessing series:', e);
                    }}
                }}
                
                // 3. 尝试从DOM中移除副图的div元素
                try {{
                    if ({id}.div && {id}.div.parentNode) {{
                        {id}.div.parentNode.removeChild({id}.div);
                        console.log('从DOM中移除了副图div');
                    }}
                }} catch (e) {{
                    console.log('Error removing subchart div:', e);
                }}
                
                // 4. 清理图表实例
                delete {id};
                console.log('删除了副图实例');
                "deleted";
            }} else {{
                console.log('副图不存在:', {id});
                "not_found";
            }}
            """

            # 正确的 runJavaScript 调用
            self.get_webview().page().runJavaScript(js, 0)#, lambda res: print(f"✅ 已删除副图 {id}，结果：{res}"))
            # 从subcharts字典中移除
            del self.subcharts[subchart_id]
            # print(f"从subcharts字典中移除了副图: {subchart_id}")
            # # 重新计算图表大小
            # if hasattr(self, '_resizes'):
            #     self._resizes()
            #     print("重新计算了图表大小")
            
            # # 重新同步所有剩余的副图与主图
            # try:
            #     main_chart_id = self.chart.id
            #     # 为每个副图重新建立同步关系
            #     sync_js = f"""
            #     (function() {{
            #         if (typeof Lib !== 'undefined' && Lib.Handler && typeof Lib.Handler.syncCharts === 'function') {{
            #             // 重新同步所有副图与主图
            #             {','.join([f"Lib.Handler.syncCharts({subchart.id}, {main_chart_id}, false); console.log('重新同步副图:', {subchart.id}, '与主图:', {main_chart_id});" for subchart_id, subchart in self.subcharts.items()])}
            #         }}
            #     }})();
            #     """
            #     self.get_webview().page().runJavaScript(sync_js, 0, lambda res: print("重新同步了所有副图与主图"))
            # except Exception as e:
            #     print(f"重新同步副图时出错: {e}")
            
            # 清理相关资源
            # 注意：由于PySide6的runJavaScript方法参数问题，我们不使用JavaScript来删除图表实例
            # 而是依赖Python的垃圾回收机制来清理资源
            
    def del_line(self,line):
        # print(line.id,self.chart.id,line in self.chart._lines)
        self.chart._lines.remove(line) if line in self.chart._lines else None
        self.get_webview().page().runJavaScript(f'''
            (function() {{
                var legendItem = {self.chart.id}.legend._lines.find((line) => line.series == {line.id}.series);
                
                if (legendItem) {{
                    {self.chart.id}.legend._lines = {self.chart.id}.legend._lines.filter((item) => item !== legendItem);
                    
                    if (legendItem.row) {{
                        if (legendItem.row.parentNode) {{
                            legendItem.row.parentNode.removeChild(legendItem.row);
                        }} else if (legendItem.row.remove) {{
                            legendItem.row.remove();
                        }}
                    }}
                }}
                
                {self.chart.id}.chart.removeSeries({line.id}.series);
                delete {line.id};
            }})();
        ''', 0)#, lambda res: print(f"✅ 已删除指标 {line.id}，结果：{res}"))
    
    def _delete_indicator(self,indicator_id):
        """
        删除最后一个指标副图
        """
        if self.chart_indicators:
            self.chart_updater._is_indicator_calculating = True
            self.chart_updater.remove_indicator(indicator_id)
            self.remove_indicator(indicator_id)
            self.chart_updater._is_indicator_calculating = False
            # 显示删除成功的提示
            #print(f"已删除指标副图: {indicator_id}")
    
    def _add_indicator_from_menu(self, class_name, indicator_name):
        """
        从菜单中添加指标
        :param class_name: 指标类名
        :param indicator_name: 指标名称
        """
        # print(f"添加指标: {class_name}.{indicator_name}")
        # 调用LightChartWindow的add_indicator_to_manager方法添加指标
        if self.light_chart_window:
            self.light_chart_window.add_indicator_to_manager(class_name, indicator_name, {})
    
    def init_chart_updater(self, kline_interval: int = 100, indicator_interval: int = 1000):
        """
        初始化图表更新管理器
        :param kline_interval: K线更新间隔（毫秒）
        :param indicator_interval: 指标更新间隔（毫秒）
        """
        if self.chart_updater is not None:
            self.chart_updater.stop()
            self.chart_updater.deleteLater()
        
        # 判断是否是本地数据模式（api不存在）
        local_data_mode = not hasattr(self, 'api') or self.api is None
        self.chart_updater = ChartUpdater(self, local_data_mode)
        
        # 连接信号到Chart的更新方法
        self.chart_updater.kline_data_ready.connect(self._update_kline_ui_from_worker)
        self.chart_updater.indicator_data_ready.connect(self._update_indicator_ui_from_worker)
        self.chart_updater.calculation_error.connect(self._on_chart_updater_error)
        self.chart_updater.start()
        # print(f"图表更新管理器已启动")

    def stop_chart_updater(self):
        """停止图表更新管理器"""
        if not self.is_static and hasattr(self.light_chart_window, 'main_window') and hasattr(self.light_chart_window.main_window, 'remove_chart_from_updater'):
            self.light_chart_window.main_window.remove_chart_from_updater(self)
        if self.chart_updater:
            self.chart_updater.stop()
            self.chart_updater.deleteLater()
            self.chart_updater = None
            # print("图表更新管理器已停止")
    
    def _fetch_kline_data(self) -> pd.DataFrame:
        """
        获取K线原始数据 - 供 ChartUpdater 定时调用
        
        数据获取逻辑（参考期货）：
        - 股票：使用 StockApi.wait_update() + get_changed_symbols() 检测变化
        - 期货：使用 TqApi.wait_update() + is_changing() 检测变化
        
        :return: K线数据DataFrame，无新数据返回 None
        """
        
        if not self.symbol:
            print("[Chart._fetch_kline_data] 无股票代码，返回 None")
            return None
        
        # === 股票数据更新逻辑 ===
        if self.is_stock:
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'stock_api') and self.main_window.stock_api:
                stock_api = self.main_window.stock_api

                # 有变化，获取最新K线数据（从订阅缓存中获取）
                kline = stock_api.get_kline_serial(self.symbol,self.cycle).copy()
                # print(f"chart {self.symbol} {self.cycle} {kline.iloc[-1]}")
                if kline is not None and not kline.empty:
                    # 股票数据时间已经是正确的，不需要时区调整
                    kline = kline[FILED.ALL]
                    kline.columns = FILED.TALL
                    return kline
            
            return None
        
        # === 期货数据更新逻辑（参考）===
        else:
            if self.api:
                # 使用天勤 API 的 is_changing 检测变化
                if not self.api.is_changing(self._kline):
                    # 没有变化，返回 None
                    return None
                
                # 有变化，获取最新K线
                kline = self.api.get_kline_serial(self.symbol, self.cycle, len(self.chart.candle_data)).copy()
                if kline is not None and not kline.empty:
                    # 期货数据需要时区调整
                    kline["datetime"] = kline["datetime"] + 8 * 3.6e12
                    kline = kline[FILED.ALL]
                    kline.columns = FILED.TALL
                    return kline
            
            return None

    def _fetch_indicator_data(self) -> pd.DataFrame:
        """
        获取指标原始数据 - 供 ChartUpdater 定时调用
        :return: 指标数据DataFrame，无新数据返回 None
        """
        # TODO: 实现获取指标计算所需的原始数据
        return self.kline

    def _on_chart_updater_error(self, error_msg: str):
        """ChartUpdater 计算错误回调"""
        # print(f"图表更新错误: \n{error_msg}")
        return

    @pyqtSlot(object)
    def _update_kline_ui_from_worker(self, result: dict):
        """
        从工作线程接收K线计算结果并更新UI
        此方法通过信号在主线程调用
        """
        # 检查图表是否仍然存在
        if self.chart is None:
            return
        
        # 实现K线UI更新逻辑
        if result:
            try:
                for k,v in result.items():
                    getattr(self.chart, k)(v)
            except:
                ...
            # except Exception as e:
            #     traceback.print_exc()
            #     print(f"更新K线数据时出错: {e}")

    @pyqtSlot(object)
    def _update_indicator_ui_from_worker(self, indicators: Union[dict,object]):
        """
        从工作线程接收指标计算结果并更新UI
        此方法通过信号在主线程调用
        """
        # 检查图表是否仍然存在
        if self.chart is None:
            return
        
        # 实现指标UI更新逻辑
        if indicators and isinstance(indicators, dict):
            try:
                self.indicator_update(indicators)
            except Exception as e:
                traceback.print_exc()
                print(f"更新指标数据时出错: {e}")

    @property
    def is_update(self)-> bool:
        """检查图表是否正在更新"""
        return self.light_chart_window.main_window.is_update
    
    # self.events.click += self.on_chart_click
    # self.events.range_change += self.on_range_change

    def on_chart_click(self, chart, time, price):
        """图表点击事件"""
        # print(f"图表{chart.id}点击: {time}, {price}")
        #print(f"self.light_chart_window: {self.light_chart_window}")
        # 设置当前点击的图表为当前子窗口
        if self.light_chart_window and hasattr(self.light_chart_window, 'market_watch_window'):
            marketWatchWindow = self.light_chart_window.market_watch_window
            if marketWatchWindow:
                marketWatchWindow.set_last_clicked_widget(self.light_chart_window)   



    # def on_range_change(self, chart, bars_before, bars_after):
    #     self._save_current_visible_range()
    
    @property
    def api(self):
        """获取API实例"""
        if self.light_chart_window and hasattr(self.light_chart_window, 'main_window'):
            if self.is_stock:
                return self.light_chart_window.main_window.stock_api
            return self.light_chart_window.main_window.tq_api
        return None
    
    def send_indicator_operation(self, ind_cls: str, name: str, params: dict = {}):
        """
        发送指标操作信号
        :param ind_cls: 指标类名
        :param name: 指标名称
        :param params: 指标参数字典
        """
        if self.chart_updater:
            self.chart_updater.send_indicator_operation(ind_cls,  name, params)
    
    # def _on_webview_loaded(self, success: bool):
    #     """WebView加载完成回调（增加图表初始化延迟，避开时序差）"""
    #     if success:
    #         QTimer.singleShot(500, self.loadsetting)
    #         # self.qtimer = QuoteQTimer(self)
    def _on_webview_loaded(self, ok):
        if not ok:
            return
        # self._on_webview_loaded_with_error_handling(ok)
        # self._inject_callback_function()
        #self._setup_cursor_monitoring()          # ✅ 替换为新的光标监测方法
        #self._setup_legend_click_events()          # ✅ 添加图例点击事件
        
        # 添加全局错误处理
        self._on_webview_loaded_with_error_handling(ok)
        
        # 添加控制台消息拦截
        webview = self.get_webview()
        webview.page().javaScriptConsoleMessage = self._on_javascript_console_message
        
        QTimer.singleShot(500, self.loadsetting)
    
    def _on_javascript_console_message(self, level, message, lineNumber, sourceID):
        """
        拦截 JavaScript 控制台消息，过滤掉 "Value is null" 相关错误
        """
        import PyQt6.QtWebEngineCore
        if level == PyQt6.QtWebEngineCore.QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorLevel:
            # 过滤掉常见错误
            filtered_keywords = ['Value is null', 'Cannot read properties', 'Uncaught Error']
            if any(keyword in message for keyword in filtered_keywords):
                return
        # 其他消息正常输出
        import sys
        print(f"[JS Console] {message}", file=sys.stderr)
    
    def _inject_cursor_event_script(self):
        """注入光标事件监听脚本（直接监听图例 DOM，精确识别指标标签）"""
        chart_global = self.chart.id          # 例如 window.abc
        chart_id_short = self.id              # 例如 abc
        
        inject_script = f"""
        (function() {{
            if (window._cursorInjected_{chart_id_short}) return;
            window._cursorInjected_{chart_id_short} = true;
            
            // 获取图例容器
            var legendDiv = {chart_global}.legend ? {chart_global}.legend.div : null;
            if (!legendDiv) {{
                console.warn('图例容器未找到，延迟尝试');
                // 如果图例还未创建，等待一下再尝试（可选）
                setTimeout(function() {{
                    legendDiv = {chart_global}.legend ? {chart_global}.legend.div : null;
                    if (legendDiv) {{
                        bindLegendEvents(legendDiv);
                    }} else {{
                        console.error('无法获取图例容器');
                    }}
                }}, 500);
                return;
            }}
            
            function bindLegendEvents(container) {{
                // 直接修改 body 光标样式
                function setCursor(type) {{
                    if (type === 'ibeam') {{
                        document.body.style.cursor = 'text';
                        document.body.style.setProperty('cursor', 'text', 'important');
                    }} else {{
                        document.body.style.cursor = '';
                        document.body.style.setProperty('cursor', '', '');
                    }}
                }}
                
                // 判断鼠标是否真正在指标行上（避免在空白区域触发）
                var currentIndicatorRow = null;
                
                container.addEventListener('mouseenter', function(e) {{
                    // 查找目标元素是否为图例行或其子元素
                    var target = e.target;
                    var row = null;
                    while (target && target !== container) {{
                        if (target.classList && (
                            target.classList.contains('legend-row') ||
                            target.classList.contains('tv-legend__item') ||
                            target.classList.contains('row')
                        )) {{
                            row = target;
                            break;
                        }}
                        target = target.parentElement;
                    }}
                    if (row) {{
                        currentIndicatorRow = row;
                        setCursor('ibeam');
                        // 通知 Python（可选）
                        if (typeof window.callbackFunction === 'function') {{
                            window.callbackFunction('cursor_change_{chart_id_short}_~_ibeam');
                        }}
                    }} else {{
                        setCursor('default');
                        if (typeof window.callbackFunction === 'function') {{
                            window.callbackFunction('cursor_change_{chart_id_short}_~_arrow');
                        }}
                    }}
                }}, true);
                
                container.addEventListener('mouseleave', function() {{
                    if (currentIndicatorRow) {{
                        currentIndicatorRow = null;
                        setCursor('default');
                        if (typeof window.callbackFunction === 'function') {{
                            window.callbackFunction('cursor_change_{chart_id_short}_~_arrow');
                        }}
                    }}
                }});
                
                console.log('光标事件已绑定到图例容器');
            }}
            
            bindLegendEvents(legendDiv);
        }})();
        """
        self.get_webview().page().runJavaScript(inject_script, 0)
            #lambda res: ...)# print("✅ 已注入光标事件监听脚本（基于图例）"))
    def __inject_cursor_event_script(self):
        """注入光标事件监听脚本"""
        # print("开始注入光标事件监听脚本")
        webview = self.get_webview()
        inject_script = """
        (function() {
            console.log('开始绑定光标事件');
            
            // 检查 window.bridge 是否存在
            console.log('window.bridge:', window.bridge);
            console.log('window.bridge.onCursorChanged:', window.bridge ? window.bridge.onCursorChanged : 'undefined');
            
            // 为 window.bridge 添加 onCursorChanged 方法
            if (window.bridge && !window.bridge.onCursorChanged) {
                window.bridge.onCursorChanged = function(cursor_type) {
                    console.log('window.bridge.onCursorChanged 被调用，光标类型:', cursor_type);
                    // 通过 callback 方法传递光标类型
                    window.callbackFunction(`cursor_changed_~_${cursor_type}`);
                };
                console.log('已为 window.bridge 添加 onCursorChanged 方法');
            }
            
            // 存储当前光标状态，避免重复触发事件
            let currentCursorState = null;
            
            function bindEvents() {
                console.log('执行绑定事件函数');
                
                // 查找所有可能的指标标签元素
                // 1. 查找所有包含指标名称的元素（例如 pta_ao）
                const allElements = document.querySelectorAll('*');
                console.log(`找到所有元素数量: ${allElements.length}`);
                
                // 筛选包含指标名称的元素
                const indicatorElements = [];
                allElements.forEach(el => {
                    const text = el.textContent || '';
                    if (text.includes('pta_ao') || text.includes('SMA') || text.includes('MACD')) {
                        indicatorElements.push(el);
                    }
                });
                
                console.log(`找到包含指标名称的元素数量: ${indicatorElements.length}`);
                indicatorElements.forEach(el => {
                    console.log('指标元素:', el, '类名:', el.className, '文本:', el.textContent);
                    
                    if (el._cursorBound) return;
                    el._cursorBound = true;
                    
                    // 添加鼠标事件监听
                    el.addEventListener('mouseenter', () => {
                        console.log('鼠标进入指标元素:', el.textContent);
                        if (window.bridge && window.bridge.onCursorChanged && currentCursorState !== 'ibeam') {
                            console.log('调用 window.bridge.onCursorChanged("ibeam")');
                            currentCursorState = 'ibeam';
                            window.bridge.onCursorChanged('ibeam');
                        } else {
                            console.log('window.bridge 不存在或没有 onCursorChanged 方法，或者光标状态未改变');
                        }
                    });
                    
                    el.addEventListener('mouseleave', () => {
                        console.log('鼠标离开指标元素:', el.textContent);
                        if (window.bridge && window.bridge.onCursorChanged && currentCursorState !== 'arrow') {
                            console.log('调用 window.bridge.onCursorChanged("arrow")');
                            currentCursorState = 'arrow';
                            window.bridge.onCursorChanged('arrow');
                        } else {
                            console.log('window.bridge 不存在或没有 onCursorChanged 方法，或者光标状态未改变');
                        }
                    });
                });
                
                // 2. 查找所有可能的指标标签元素（基于类名）
                const possibleClasses = ['.legend-item', '.lwc-legend-item', '.indicator-label', '.tv-legend__item', '.tv-legend-item'];
                possibleClasses.forEach(selector => {
                    const elements = document.querySelectorAll(selector);
                    console.log(`找到 ${selector} 元素数量: ${elements.length}`);
                    elements.forEach(el => {
                        console.log(`${selector} 元素:`, el, '文本:', el.textContent);
                        
                        if (el._cursorBound) return;
                        el._cursorBound = true;
                        
                        // 添加鼠标事件监听
                        el.addEventListener('mouseenter', () => {
                            console.log('鼠标进入指标元素:', el.textContent);
                            if (window.bridge && window.bridge.onCursorChanged && currentCursorState !== 'ibeam') {
                                console.log('调用 window.bridge.onCursorChanged("ibeam")');
                                currentCursorState = 'ibeam';
                                window.bridge.onCursorChanged('ibeam');
                            } else {
                                console.log('window.bridge 不存在或没有 onCursorChanged 方法，或者光标状态未改变');
                            }
                        });
                        
                        el.addEventListener('mouseleave', () => {
                            console.log('鼠标离开指标元素:', el.textContent);
                            if (window.bridge && window.bridge.onCursorChanged && currentCursorState !== 'arrow') {
                                console.log('调用 window.bridge.onCursorChanged("arrow")');
                                currentCursorState = 'arrow';
                                window.bridge.onCursorChanged('arrow');
                            } else {
                                console.log('window.bridge 不存在或没有 onCursorChanged 方法，或者光标状态未改变');
                            }
                        });
                    });
                });
            }
            
            // 立即执行一次绑定
            bindEvents();
            
            // 使用MutationObserver监听DOM变化，动态绑定新添加的指标标签
            const observer = new MutationObserver(bindEvents);
            observer.observe(document.body, { childList: true, subtree: true });
            console.log('已启动 MutationObserver 监听DOM变化');
        })();
        """
        webview.page().runJavaScript(inject_script, 0)#, lambda res: print("✅ 已注入光标事件监听脚本"))
        
        # 注册光标变化事件处理器（这部分已经在Chart初始化时完成，这里不需要重复注册）
        # if hasattr(self.chart, 'win'):
        #     self.chart.win.handlers['cursor_changed'] = self.on_cursor_change
        #     print("✅ 已注册光标变化事件处理器")
    
    def _inject_callback_function(self):
        self.get_webview().page().runJavaScript("""
            if (typeof window.callbackFunction !== 'function') {
                window.callbackFunction = function(msg) {
                    console.log('fallback callback:', msg);
                };
            }
        """)
    
    def _register_cursor_handler(self):
        """注册光标变化事件的 Python 回调"""
        try:
            if hasattr(self, 'chart') and self.chart is not None:
                if hasattr(self.chart, 'win') and self.chart.win is not None:
                    if hasattr(self.chart.win, 'handlers') and self.chart.win.handlers is not None:
                        handler_name = f'cursor_change_{self.id}'
                        def handler(chart, data):
                            self.on_cursor_change(chart, data)
                        self.chart.win.handlers[handler_name] = handler
                        # print(f"✅ 已注册光标处理器: {handler_name}")
            #         else:
            #             print("❌ 无法注册光标处理器：chart.win.handlers 不存在")
            #     else:
            #         print("❌ 无法注册光标处理器：chart.win 不存在")
            # else:
            #     print("❌ 无法注册光标处理器：chart 不存在")
        except Exception as e:
            print(f"❌ 注册光标处理器时出错: {str(e)}")

    # def on_cursor_change(self, chart, cursor_type):
    #     """光标变化事件处理（仅用于日志，光标样式已由 JS 直接修改）"""
    #     print(f"光标变化: {cursor_type}")
    #     if cursor_type == 'ibeam':
    #         print("✅ 鼠标悬停在指标标签上")
    #         # 这里可以添加其他业务逻辑，例如高亮指标面板
    #     elif cursor_type == 'arrow':
    #         print("👈 鼠标离开指标标签")
            
    def _on_indicator_loaded(self):
        """指标加载回调"""
        def handle_result(result):
            if result is not None and result > 0:
                width = int(result)
                self.light_chart_window.price_scale_widthes[self.symbol] = width
            if self.symbol in self.light_chart_window.price_scale_widthes:
                width = self.light_chart_window.price_scale_widthes[
                    self.symbol]
            for _, chart in self.subcharts.items():
                self.set_price_scale_fixed_width(chart, width)
            self.set_only_last_chart_xaxis_visible()
            self.add_chart_separator_lines()
            self._restore_visible_range()
            self.set_all_charts_crosshair_label_background()
            # if self.subcharts:
            #     list(self.subcharts.values())[-1].events.cursor_change += self.on_cursor_change
            # if self._is_cursor_over_indicator:
            #     self._is_cursor_over_indicator = False
            #     self.chart.events.cursor_change += self.on_cursor_change
            

        script = f'''
            (function() {{
                if (typeof {self.id} !== 'undefined' && {self.id}.chart && {self.id}.chart.priceScale) {{
                    return {self.id}.chart.priceScale("right").width();
                }}
                return null;
            }})();
        '''
        self.get_webview().page().runJavaScript(script,0, handle_result)
        QTimer.singleShot(1800, self._add_subchart_cursor_change_event)
        
    def loadsetting(self):
        """加载基本设置"""
        try:
            def handle_result(result):
                width=60
                if result is not None and result > 0:
                    width = int(result)
                    self.light_chart_window.price_scale_widthes[self.symbol] = width
                if self.symbol in self.light_chart_window.price_scale_widthes:
                    width = self.light_chart_window.price_scale_widthes[
                        self.symbol]
                for _, chart in self.subcharts.items():
                    self.set_price_scale_fixed_width(chart, width)
                self.set_only_last_chart_xaxis_visible()
                self.add_chart_separator_lines()
                self._restore_visible_range()
                self.set_all_charts_crosshair_label_background()
                
                # self.chart.events.cursor_change += self.on_cursor_change
                # self.chart.events.legend_click += self.on_legend_click
                self._on_alert_settings_changed(self.price_alert, False)
                # self.events.search += self.on_search
                self.events.click += self.on_chart_click
                # self.chart.events.right_click += self.on_right_click
                # self.events.legend_click += self.on_legend_click
                # self.events.cursor_change += self.on_cursor_change
            script = f'''
                (function() {{
                    if (typeof {self.id} !== 'undefined' && {self.id}.chart && {self.id}.chart.priceScale) {{
                        return {self.id}.chart.priceScale("right").width();
                    }}
                    return null;
                }})();
            '''
            self.get_webview().page().runJavaScript(script,0, handle_result)
            self._webview_loadfinished = True

            # 确保主图 legend 配置 lines=True，使主图叠加指标的标签正常显示
            self.setChartTheme()
        except Exception as e:
            print(f"加载基本设置时出错: {e}")
            
        # QTimer.singleShot(1000, self._add_cursor_change_event)
        QTimer.singleShot(1800, self._bind_all_cursor_events)
    # 统一绑定主图 + 所有副图光标事件
    # def _bind_all_cursor_events(self):
    #     self.events.cursor_change += self.on_cursor_change

    def on_right_click(self, chart, chart_id, x, y):
        """
        右击事件处理
        
        参数:
            chart: 触发事件的图表对象
            chart_id: 图表ID（字符串）
            x: 鼠标X坐标（屏幕坐标）
            y: 鼠标Y坐标（屏幕坐标）
        """
        self._last_chart_id=chart_id
        # print(f"右击图表: {chart_id}, 位置: ({x}, {y})")
        
        # 设置当前点击的图表为当前子窗口
        if self.light_chart_window and hasattr(self.light_chart_window, 'market_watch_window'):
            marketWatchWindow = self.light_chart_window.market_watch_window
            if marketWatchWindow:
                # print(f"[Chart.on_right_click] 设置当前子窗口: {self.light_chart_window}")
                marketWatchWindow.set_last_clicked_widget(self.light_chart_window)
        
        # 将屏幕坐标转换为QPoint
        # from PySide6.QtCore import QPoint
        # pos = QPoint(int(float(x)), int(float(y)))
        # # 调用右键菜单
        # self._on_webview_custom_context_menu(pos)
    
    def _bind_all_cursor_events(self):
        if hasattr(self, 'events'):
            self.events.cursor_change += self.on_cursor_change
        
    # def _on_cursor_change(self, chart: AbstractChart, legend_data):
    #     """
    #     legend_data:
    #     - dict: {{"text": "...", "html": "..."}}  （在指标标签上）
    #     - "null"                                  （离开标签）
    #     """
    #     if legend_data == "null":
    #         print("👉 鼠标离开指标标签")
    #         return

    #     try:
    #         legend = json.loads(legend_data)
    #         text = legend.get("text", "")
    #         print(f"🎯 鼠标悬停在指标标签上：{text}")
    #         print(f"   原始 HTML: {legend.get('html', '')}")
    #     except Exception as e:
    #         print(f"解析 legend 数据失败: {e}")
    
    def on_cursor_change(self, chart:AbstractChart, cursor_data):
        """
        光标变化事件处理
        
        参数:
            chart: 触发事件的图表对象
            cursor_data: JSON字符串，包含指标信息
                - type: "enter" 或 "leave"
                - index: 指标在legend._lines中的索引
                - text: 指标标签的文本内容
                - color: 指标颜色
                - name: 指标名称
                - lineId: 线条ID
                - x: 鼠标X坐标（相对于webview）
                - y: 鼠标Y坐标（相对于webview）
        """
        # 检查cursor_data是否为空
        if not cursor_data:
            # print(f"⚠️  空的cursor_data，图表: {chart.id}")
            return

        # 静态图表（回测等）没有 indicator_manager，跳过指示器卡片菜单
        if self.is_static:
            return
        
        try:
            # print(f"cursor_data: {cursor_data}")
            data = json.loads(cursor_data)
        except json.JSONDecodeError as e:
            # print(f"⚠️  JSON解析错误: {e}, 数据: {cursor_data}, 图表: {chart.id}")
            return
        # try:
        data.update({"chart_id":chart.id})
        event_type = data.get("type", "")
        
        if event_type == "leave":
            # print(f"👉 鼠标离开指标标签 | 图表: {chart.id}")
            return
        
        if event_type == "enter":
            # index = data.get("index", -1)
            # text = data.get("text", "")
            # color = data.get("color", "")
            # name = data.get("name", "")
            # line_id = data.get("lineId", "")
            # x = data.get("x", 0)
            # y = data.get("y", 0)
            # indicator_id=data.get("indicatorId", "")
            
            # print(f"🎯 鼠标进入指标标签:")
            # print(f"   图表: {chart.id}")
            # print(f"   索引: {index}")
            # print(f"   指标ID: {indicator_id}")
            # print(f"   文本: {text}")
            # print(f"   颜色: {color}")
            # print(f"   名称: {name}")
            # print(f"   线条ID: {line_id}")
            # print(f"   位置: ({x}, {y})")
            
            # 只有当指标卡窗口未显示时才打开
            if not self._indicator_card_visible:
                
                # 使用从JavaScript返回的坐标（相对于webview）
                #pos = QCursor.pos()
                y = data.get("y", 0)
                webview_pos = QPoint(10, int(float(y)))
                # 将webview相对坐标转换为全局坐标
                webview = self.get_webview()
                global_pos = webview.mapToGlobal(webview_pos)
                createIndicatorCardMenu(self.light_chart_window, global_pos, data)
                    
        # except json.JSONDecodeError:
        #     print(f"🎯 光标数据 = {cursor_data} | 图表 = {chart.id}")
        # except Exception as e:
        #     print(f"处理光标变化事件时出错: {e}")
        
    # def on_cursor_change(self, chart:AbstractChart, cursor_data):
    #     """
    #     光标变化事件处理
        
    #     参数:
    #         chart: 触发事件的图表对象
    #         cursor_data: JSON字符串，包含指标信息
    #             - type: "enter" 或 "leave"
    #             - index: 指标在legend._lines中的索引
    #             - text: 指标标签的文本内容
    #             - color: 指标颜色
    #             - name: 指标名称
    #             - lineId: 线条ID
    #             - x: 鼠标X坐标（相对于webview）
    #             - y: 鼠标Y坐标（相对于webview）
    #     """
    #     # 检查cursor_data是否为空
    #     if not cursor_data:
    #         print(f"🎯 光标数据为空 | 图表 = {chart.id}")
    #         self._indicator_card_visible = False
    #         return
            
    #     # 解析JSON数据
    #     try:
    #         data = json.loads(cursor_data)
    #         event_type = data.get("type", "")
    #     except json.JSONDecodeError as e:
    #         print(f"🎯 光标数据不是有效的JSON | 图表 = {chart.id}")
    #         print(f"   数据: {cursor_data}")
    #         print(f"   错误: {e}")
    #         self._indicator_card_visible = False
    #         return
        
    #     # 只有当指标卡窗口未显示时才打开
    #     if not self._indicator_card_visible:
    #         self._indicator_card_visible = True
        
    #     if event_type == "leave" and chart.id == self.main_chart_id:
    #         # 使用默认坐标
    #         y = data.get("y", 0)
    #         # 使用从JavaScript返回的坐标（相对于webview）
    #         #pos = QCursor.pos()
    #         webview_pos = QPoint(int(float(10)), int(float(y)))
    #         # 将webview相对坐标转换为全局坐标
    #         webview = self.get_webview()
    #         global_pos = webview.mapToGlobal(webview_pos)
    #         createIndicatorCardMenu(self.light_chart_window, global_pos, indicator_info=data)
    #         print(f"👉 鼠标离开指标标签 | 图表: {chart.id}")
    #         self._indicator_card_visible = False
    #         return
        
    #     if event_type == "enter":
    #         index = data.get("index", -1)
    #         text = data.get("text", "")
    #         color = data.get("color", "")
    #         name = data.get("name", "")
    #         line_id = data.get("lineId", "")
    #         x = data.get("x", 0)
    #         y = data.get("y", 0)
            
    #         print(f"🎯 鼠标进入指标标签:")
    #         print(f"   图表: {chart.id}")
    #         print(f"   索引: {index}")
    #         print(f"   文本: {text}")
    #         print(f"   颜色: {color}")
    #         print(f"   名称: {name}")
    #         print(f"   线条ID: {line_id}")
    #         print(f"   位置: ({x}, {y})")
                
    #         # 只有当指标卡窗口未显示时才打开
    #         if not self._indicator_card_visible:
    #             self._indicator_card_visible = True
    #             # 使用从JavaScript返回的坐标（相对于webview）
    #             #pos = QCursor.pos()
    #             webview_pos = QPoint(int(float(10)), int(float(y)))
    #             # 将webview相对坐标转换为全局坐标
    #             webview = self.get_webview()
    #             global_pos = webview.mapToGlobal(webview_pos)
    #             createIndicatorCardMenu(self.light_chart_window, global_pos, indicator_info=data)
    #             return
                    
    #     # 如果不是enter或leave事件，重置标志
    #     self._indicator_card_visible = False
            
    def creat_indicator_menu(self,y:int):
        # 只有当指标卡窗口未显示时才打开
        if not self._indicator_card_visible:
            self._indicator_card_visible = True
            # 使用从JavaScript返回的坐标（相对于webview）
            #pos = QCursor.pos()
            webview_pos = QPoint(int(float(10)), int(float(y)))
            # 将webview相对坐标转换为全局坐标
            webview = self.get_webview()
            global_pos = webview.mapToGlobal(webview_pos)
            createIndicatorCardMenu(self.light_chart_window, global_pos, indicator_info=data)
        
    def on_click(self, chart, *param):
        """点击事件处理"""
        # print(f"点击事件: {param}")
        
        # 设置当前点击的图表为当前子窗口
        if self.light_chart_window and hasattr(self.light_chart_window, 'marketWatchWindow'):
            marketWatchWindow = self.light_chart_window.marketWatchWindow
            if marketWatchWindow:
                # print(f"[Chart.on_click] 设置当前子窗口: {self.light_chart_window}")
                marketWatchWindow.set_last_clicked_widget(self.light_chart_window)
        
    def _add_cursor_change_event(self):
        self.events.cursor_change += self.on_cursor_change
        
    def _add_subchart_cursor_change_event(self):
        if self.subcharts and self._is_subchart:
            subchart=list(self.subcharts.values())[-1]
            subchart.events.watch_cursor_change()
            # subchart.events.right_click()  # 注释掉：会导致画线右键菜单与图表菜单同时出现
            subchart.events.cursor_change += self.on_cursor_change
            # subchart.events.right_click += self.on_right_click
    
    def set_candle_style(self) -> None:
        from minibt.utils import Colors as btcolors
        bull_color = self.light_chart_window.bull_color if self.light_chart_window else btcolors.bull_color
        bear_color = self.light_chart_window.bear_color if self.light_chart_window else btcolors.bear_color
        self.candle_style(up_color=bull_color,
                          down_color=bear_color)

    def set_default_candle_style(self) -> None:
        self.light_chart_window.bull_color = btcolors.bull_color
        self.light_chart_window.bear_color = btcolors.bear_color
        self.candle_style(up_color=btcolors.bull_color,
                          down_color=btcolors.bear_color)
        
        
    def reload_chart(self, cycle):
        """
        重新加载图表数据
        
        Args:
            cycle: 周期（秒）
        """
        # 设置正在重新加载标志
        self._is_reloading = True
        
        try:
            # 更新周期
            self.cycle = cycle
            self.light_chart_window.cycle = cycle
            
            self._init_chart_data()
            # self._init_data_thread()
        finally:
            # 无论成功失败，都设置重新加载标志为False
            self._is_reloading = False

    def _init_chart_data(self):
        """初始化图表"""
        self.current_index=0
        self.water_mark=None
        self.contract=self.symbol
        
        # 静态图表模式：数据由 init_from_contract_data 从外部传入
        # 不再在 _init_chart_data 中读取 pkl 文件
        if self.is_static:
            # print(f"📊 静态图表模式，等待外部传入合约数据（init_from_contract_data）")
            return
        
        # 根据合约类型选择数据源
        if self.is_stock:
            # 股票：使用 StockApi
            if hasattr(self.main_window, 'stock_api') and self.main_window.stock_api:
                stock_api = self.main_window.stock_api
                self._kline = stock_api.get_kline_serial(self.symbol, self.cycle).copy()
                # print(self._kline.head())
                # 检查数据是否为空
                if self._kline is None or self._kline.empty:
                    print(f"[Chart] 股票 {self.symbol} K线数据为空，无法打开图表")
                    # 显示错误提示（使用 InfoBar）
                    from qfluentwidgets import InfoBar, InfoBarPosition
                    if hasattr(self, 'main_window') and self.main_window:
                        InfoBar.error(
                            title="数据获取失败",
                            content=f"无法获取股票 {self.symbol} 的K线数据，请检查网络或更换数据源",
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP,
                            duration=3000,
                            parent=self.main_window
                        )
                    # 中止图表创建（不使用默认数据）
                    return
                
                df = self._kline.copy()
                # 股票数据时间已经是正确的，不需要时区调整
                df['time'] = df.datetime
                df = df[FILED.TALL]
                self.set(df, True)
            else:
                print(f"[Chart] 股票API未初始化，无法获取 {self.symbol} 数据")
                self._use_default_data()
                return
        else:
            # 期货：使用天勤API
            if self.api:
                self._kline = self.api.get_kline_serial(self.symbol, self.cycle, self.length).copy()
                # 检查数据是否为空
                if self._kline is None or self._kline.empty:
                    print(f"[Chart] 期货 {self.symbol} K线数据为空，无法打开图表")
                    # 显示错误提示（使用 InfoBar）
                    from qfluentwidgets import InfoBar, InfoBarPosition
                    if hasattr(self, 'main_window') and self.main_window:
                        InfoBar.error(
                            title="数据获取失败",
                            content=f"无法获取期货 {self.symbol} 的K线数据，请检查登录状态或网络连接",
                            orient=Qt.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP,
                            duration=3000,
                            parent=self.main_window
                        )
                    # 中止图表创建
                    return
                
                df = self._kline.copy()
                df['time'] = df.datetime+8*3.6e12  # 调整时区
                df = df[FILED.TALL]
                self.set(df, True)
            else:
                self._use_default_data()
        
        # if self.water_mark is not None:
        #     self.water_mark = self.water_mark.vars
        #     self.set_watermark(**self.water_mark)
        
        # import numpy as np
        # null_ind=pd.Series(np.full(len(df), np.nan),name="null_line")
        # line=self.chart.create_line(name="null_line",width=0,price_line=False,price_label=False)
        # data=pd.concat([df["time"], null_ind], axis=1)
        # line.set(data)
        self.set_candle_style()
        # self.strategy()
        # self.account_float_profit = self.account.float_profit
        # self.light_chart_window.info_window.set_account_info(
        #     self.strategy._get_account_info())
    
    def _use_default_data(self):
        """使用默认数据填充图表"""
        try:
            # 尝试使用 minibt/data/test/v2601_300.csv数据
            from minibt import LocalDatas
            df = LocalDatas.v2601_300.dataframe
            # 转换datetime列为时间戳
            df['datetime'] = pd.to_datetime(df['datetime'])
            # 调整时区（+8小时）
            df['time'] = df['datetime'].astype('int64') + 8*3.6e12
            # 只保留需要的列
            df = df[FILED.TALL]
            self.set(df, True)
            self._kline = df
        except Exception as e:
            print(f"[Chart] 加载默认数据失败: {e}")
            # 如果文件不存在，使用随机生成的数据
            import numpy as np
            dates = pd.date_range('2023-01-01', periods=100, freq='D')
            np.random.seed(42)
            open_prices = 100 + np.cumsum(np.random.randn(100) * 2)
            high_prices = open_prices + np.random.rand(100) * 3
            low_prices = open_prices - np.random.rand(100) * 3
            close_prices = open_prices + np.random.randn(100) * 2
            volume = np.random.randint(1000, 10000, 100)
            df = pd.DataFrame({
                'open': open_prices,
                'high': high_prices,
                'low': low_prices,
                'close': close_prices,
                'volume': volume
            })
            df.index = dates
            df['time'] = df.index.astype('int64') // 10**9
            self.set(df, True)
            self._kline = df
        # pos = self.position.pos
        # price = 0.
        # text = ""
        # color = btcolors.bear_color
        # if pos:
        #     price = self.position.open_price_long if pos > 0 else self.position.open_price_short
        #     profit = self.position.float_profit
        #     text = f"⬆️{profit}" if pos > 0 else f"⬇️{profit}"
        #     color = btcolors.bear_color if profit > 0 else btcolors.bull_color
        # self.position_horizontal_line = self.horizontal_line(
        #     price, color=color, width=3, style='dashed', text=text)
        

        # 直接添加指标到 indicator_manager，而不是通过信号
        # 这样可以确保指标在计算前被添加
        # worker = self.chart_updater.worker
        # if worker and hasattr(worker, 'indicator_manager'):
        #     worker.indicator_manager.addIndicator("PandasTa", "sma", {})
        #     worker.indicator_manager.addIndicator("PandasTa", "ebsw", {})
        #     worker.indicator_manager.addIndicator("PandasTa", "macd", {})
        #     for ind in worker.indicator_manager.getIndicators():
        #         print(f"  - {ind}")

        # # 计算指标
        # print("开始计算指标...")
        # indicators = worker.indicator_manager.calculate_indicators(df)
        # print(f"指标计算完成，结果数量: {len(indicators)}")
        # for ind_id, ind_value in indicators.items():
        #     print(f"  - 指标ID: {ind_id}, 类型: {type(ind_value)}")
        #     self.add_indicator(ind_id, ind_value,df)
        self.setChartTheme()
        # self._resizes()
        if self.toolbox and hasattr(self, 'symbol'):
            self.toolbox.load_drawings(tag=self.symbol)

    def _load_static_indicators(self, indicators_data: list):
        """加载静态指标数据（用于回测结果展示）
        
        数据格式与 add_indicator 中的 _get_plot_datas 一致：
        {
            "plot_id": int,
            "isplot": list[bool],
            "name": list[str],
            "lines": list[list[str]],
            "_lines": list[list[str]],
            "ind_names": list[str],
            "overlaps": list[bool],
            "categorys": list[str],
            "indicators": list[list[float]],
            "doubles": list[int] | bool,
            "plotinfo": dict,
            "span": dict,
            "signal": dict
        }
        """
        import numpy as np
        
        # print(f"📊 开始加载 {len(indicators_data)} 组指标数据")
        df=self._kline
        for indicator_id, ind_data in enumerate(indicators_data):
            try:
                plot_id = ind_data.get("plot_id", 0)
                isplot = ind_data.get("isplot", [True])
                name = ind_data.get("name", ["unknown"])
                lines = ind_data.get("lines", [])
                _lines = ind_data.get("_lines", [])
                ind_names = ind_data.get("ind_names", [])
                overlaps = ind_data.get("overlaps", [False])
                categorys = ind_data.get("categorys", ["indicator"])
                indicators = ind_data.get("indicators", [])
                doubles = ind_data.get("doubles", False)
                plotinfo = ind_data.get("plotinfo", {})
                _signal = ind_data.get("signal", {})
                lineinfo = plotinfo.get('linestyle', {})
                #print(f"indicators:{indicators}")
                #print(f"   [{indicator_id}] name={name}, lines={_lines}, doubles={doubles}, indicators_len={len(indicators)}")
                subchart_num=len(self.subcharts)
                lineinfo = plotinfo.get('linestyle', {})
                signal_info: dict = plotinfo.get('signalstyle', {})
                colors=dict()
                price_visible=dict()
                line_width=dict()
                line_style=dict()
                ind_dict = dict()
                _indicator=indicators
                if doubles:
                    # doubles 模式下 indicators 是 list[np.array, np.array]
                    # 合并为一个 DataFrame，方便下方 doubles 循环中按列名访问
                    if isinstance(_indicator, list) and len(_indicator) >= 2:
                        all_doubles_lines = []
                        all_doubles_arrays = []
                        for j in range(len(_indicator)):
                            # 为每个组的列名添加唯一后缀，避免跨组列名冲突
                            group_lines = _lines[j] if j < len(_lines) else [f'g{j}_{i}' for i in range(_indicator[j].shape[1])]
                            all_doubles_lines.append(group_lines)
                            if _indicator[j].ndim == 1:
                                all_doubles_arrays.append(_indicator[j].reshape(-1, 1))
                            else:
                                all_doubles_arrays.append(_indicator[j])
                        all_cols = all_doubles_lines[0] + all_doubles_lines[1]
                        indicator = pd.DataFrame(
                            np.column_stack(all_doubles_arrays),
                            columns=all_cols
                        )
                        isMDim = True
                    else:
                        indicator = pd.DataFrame()
                        isMDim = False
                else:
                    # 确保 _indicator 是 numpy array（兼容 list 输入）
                    if isinstance(_indicator, list):
                        _indicator = np.array(_indicator)
                    try:
                        if len(_indicator.shape)>1:
                            isMDim=True
                            indicator=pd.DataFrame(_indicator,columns=_lines)
                        else:
                            indicator=pd.Series(_indicator,name=_lines[0])
                            isMDim=False
                    except Exception:
                        isMDim=False
                        indicator=pd.Series(_indicator,name=_lines[0] if _lines else 'value')
                #print(indicator,_signal,signal_info)
                if doubles:
                    for j in range(2):
                        if any(isplot[j]):
                            cache_dict = {}
                            if overlaps[j]:
                                    chart:AbstractChart = self.chart
                                    # 每次添加主图指标时都重新注册鼠标移动事件
                                    # 先重置window[key]变量
                                    # salt = chart.id[chart.id.index('.')+1:]
                                    # key = f'_cursor_{salt}'
                                    # reset_js = f"window['{key}'] = false;"
                                    # self.get_webview().page().runJavaScript(reset_js, 0, lambda res: print("✅ 已重置主图鼠标事件监听器"))
                                    # # 然后重新注册事件监听
                                    # print("🔄 重新注册主图鼠标移动事件")
                                    # chart.events.watch_cursor_change()
                            else:
                                chart:AbstractChart = self.create_subchart(
                                    'bottom', sync=True)
                                # 添加测试性输出
                                #print(f"创建副图: ID={chart.id}, indicator_id={indicator_id}, name={name[j]}")
                                self.setSubChartTheme(chart, name[j])
                                self.subcharts.update({indicator_id: chart})
                                
                                # 确保副图与主图同步
                                # try:
                                #     main_chart_id = self.chart.id
                                    # 首先尝试同步缩放和鼠标移动
                                    # sync_js = f"""
                                    # (function() {{
                                    #     if (typeof Lib !== 'undefined' && Lib.Handler && typeof Lib.Handler.syncCharts === 'function') {{
                                    #         // 同步缩放和鼠标移动
                                    #         Lib.Handler.syncCharts(
                                    #             {chart.id},
                                    #             {main_chart_id},
                                    #             false
                                    #         );
                                    #         console.log('同步副图:', {chart.id}, '与主图:', {main_chart_id}, '缩放和鼠标移动');
                                    #     }}
                                    # }})();
                                    # """
                                    # self.get_webview().page().runJavaScript(sync_js, 0, lambda res: print(f"✅ 已同步副图 {chart.id} 与主图"))
                                # except Exception as e:
                                #     print(f"同步副图时出错: {e}")
                            for i, plot in enumerate(isplot[j]):
                                if plot:
                                    col = _lines[j][i]
                                    info = lineinfo[col]
                                    color = info.get(
                                        "line_color", None)
                                    if not color:
                                        color = next(self.ind_colors)
                                    colors[col]=color
                                    style = info.get('line_dash', 'solid')
                                    if style != "vbar" and style not in util.LINE_STYLE.__args__:
                                        style = 'solid'
                                    width = info.get("line_width", 2)
                                    price_line = info.get(
                                        "price_line", False)
                                    price_label = info.get(
                                        "price_label", False)

                                    if style == "vbar":
                                        # 创建柱状图
                                        line = chart.create_histogram(
                                            name=col, color=color, price_line=price_line, price_label=price_label)
                                        
                                        # 设置indicator_id
                                        line.set_indicator_id(indicator_id)

                                        # 准备数据
                                        hist_data = pd.concat(
                                            [df["time"], indicator[col]], axis=1)

                                        # 检查是否是MACD柱状图，如果是，添加颜色列
                                        # if "macdh" in col.lower():
                                            # 为MACD柱状图添加颜色列，正值为红色，负值为绿色
                                            # 绿色
                                        hist_data['color'] = btcolors.bear_color
                                        # 红色
                                        hist_data.loc[hist_data[col] > 0,
                                                        'color'] = btcolors.bull_color

                                        # 设置数据
                                        line.set(hist_data)

                                    else:
                                        line = partial(chart.create_line,
                                                        name=col, color=color, style=style, width=width, price_line=price_line, price_label=price_label)
                                        line.vdata = pd.concat(
                                            [df["time"], indicator[col]], axis=1)
                                        line.indicator_id = indicator_id  # 暂存indicator_id，稍后设置
                                    cache_dict[col] = line
                            else:
                                # vbar指标在前其它指标线在后，否则vbar柱体会挡住其它指标线
                                if cache_dict:
                                    new_dict = {}
                                    for _k, _v in cache_dict.items():
                                        if hasattr(_v, "vdata"):
                                            data = _v.vdata
                                            # indicator_id_temp = _v.indicator_id if hasattr(_v, 'indicator_id') else None
                                            _v = _v()
                                            _v.set(data)
                                            # 设置indicator_id
                                            # if indicator_id_temp is not None:
                                            _v.set_indicator_id(indicator_id)
                                            _v.init_line_visibility()
                                        new_dict.update({_k: _v})
                                    ind_dict.update(new_dict)
                    if ind_dict:
                        self.chart_indicators.update({indicator_id: ind_dict})
                else:
                    if any(isplot):
                        is_candles = "candles" in categorys
                        if not isMDim:
                            indicator = pd.DataFrame(
                                {_lines[0]: indicator})

                        if is_candles:
                            if set(indicator.columns) != set(FILED.OHLC):
                                print(f"蜡烛图指标列名必须为{FILED.OHLC}")
                            chart = self.create_subchart(
                                'bottom', sync=True)
                            self.setSubChartTheme(chart, name)
                            self.subcharts.update({indicator_id: chart})
                            candles_df = indicator.copy()
                            candles_df["time"] = df["time"]
                            candles_df = candles_df[FILED.TOHLC]
                            chart.set(candles_df)
                        else:
                            if overlaps:
                                chart:AbstractChart = self.chart
                            else:
                                chart:AbstractChart = self.create_subchart(
                                    'bottom', sync=True)
                                self.setSubChartTheme(chart, name)
                                self.subcharts.update({indicator_id: chart})

                            for i, plot in enumerate(isplot):
                                if plot:
                                    col = _lines[i]
                                    info = lineinfo[col]
                                    color = info.get(
                                        "line_color", None)
                                    if not color:
                                        color = next(self.ind_colors)
                                    style = info.get('line_dash', 'solid')
                                    if style != "vbar" and style not in util.LINE_STYLE.__args__:
                                        style = 'solid'
                                    width = info.get("line_width", 2)
                                    price_line = info.get(
                                        "price_line", False)
                                    price_label = info.get(
                                        "price_label", False)
                                    colors[col]=color
                                    price_visible["price_line"]=price_line
                                    price_visible["price_label"]=price_label
                                    line_width[col]=width
                                    line_style[col]=style
                                    if style == "vbar":
                                        # 创建柱状图
                                        line = chart.create_histogram(
                                            name=col, color=color, price_line=price_line, price_label=price_label)

                                        # 准备数据
                                        hist_data = pd.concat(
                                            [df["time"], indicator[col]], axis=1)

                                        # 检查是否是MACD柱状图，如果是，添加颜色列
                                        if "macdh" in col.lower():
                                            # 为MACD柱状图添加颜色列，正值为红色，负值为绿色
                                            # 绿色
                                            hist_data['color'] = btcolors.bear_color
                                            # 红色
                                            hist_data.loc[hist_data[col] > 0,
                                                            'color'] = btcolors.bull_color

                                        # 设置数据
                                        line.set(hist_data)
                                    else:
                                        line = partial(chart.create_line,
                                                        name=col, color=color, style=style, width=width, price_line=price_line, price_label=price_label)
                                        line.vdata = pd.concat(
                                            [df["time"], indicator[col]], axis=1)
                                    ind_dict[col] = line
                            else:
                                if ind_dict:
                                    new_dict = {}
                                    for _k, _v in ind_dict.items():
                                        if hasattr(_v, "vdata"):
                                            data = _v.vdata
                                            _v = _v()
                                            _v.set(data)
                                            # 设置indicator_id
                                            _v.set_indicator_id(indicator_id)
                                            _v.init_line_visibility()
                                        new_dict.update({_k: _v})
                                    ind_dict = new_dict
                        if ind_dict:
                            self.chart_indicators.update({indicator_id: ind_dict})
                # 交易信号：
                if signal_info:
                    signal_dict = {}
                    last_signal_dict = {}
                    all_markers = []

                    for signalname, signal_config in signal_info.items():
                        signalkey, signalcolor, signalmarker, signaloverlap, signalshow, signalsize, signallabel = list(
                            signal_config.values())
                        signal_series = indicator[signalname]
                        is_buy_signal = any([name in signalname for name in [
                                            "long", "exitshort"]]) or "low" in signalkey.lower()
                        signal_points = signal_series[signal_series > 0]
                        if is_buy_signal:
                            position = 'below'
                            shape = signalmarker if signalmarker in util.MARKER_SHAPE.__args__ else 'arrow_up'
                            color = signalcolor if signalcolor else btcolors.bear_color
                        else:
                            position = 'above'
                            shape = signalmarker if signalmarker in util.MARKER_SHAPE.__args__ else 'arrow_down'
                            color = signalcolor if signalcolor else btcolors.bull_color
                        text = signallabel.get("text", "") if isinstance(
                            signallabel, dict) else ""
                        signalconfig = dict(
                            position=position, shape=shape, color=color, text=text)

                        for idx in signal_points.index:
                            time_value = df.iloc[idx]['time']
                            # 将纳秒级时间戳转换为秒级时间戳（与图表内部格式一致）
                            # _single_datetime_format 期望接收可解析为datetime的值
                            if isinstance(time_value, (int, float)) and time_value > 1e15:
                                time_value = pd.to_datetime(time_value)
                            all_markers.append(
                                {"time": time_value, **signalconfig})
                        else:
                            if not signal_series.empty and signal_series.iloc[-1] > 0:
                                last_time_value = df.iloc[-1]['time']
                                if isinstance(last_time_value, (int, float)) and last_time_value > 1e15:
                                    last_time_value = pd.to_datetime(last_time_value)
                                last_signal_dict[signalname] = self.chart._single_datetime_format(
                                    last_time_value)
                        signal_dict.update({signalname: signalconfig})
                    #print(f"all_markers:{all_markers}")
                    if all_markers:
                        
                        all_markers.sort(key=lambda x: x["time"])
                        self.marker_list(all_markers)
                        if last_signal_dict:
                            count = 0
                            for markername in reversed(self.markers):
                                marker = self.markers[markername]
                                for lsd, lsv in last_signal_dict.items():
                                    if marker["time"] == lsv:
                                        signal_dict[lsd]["signal"] = markername
                                        self._signal_markers[(indicator_id, lsd, lsv)] = markername
                                        count += 1
                                if count == len(last_signal_dict):
                                    break

                    self.signal_indicators.update({indicator_id: signal_dict})
                    #print(self.signal_indicators)
                
                self._resizes()
                # last_indicator=self.indicator_manager.last_indicator
                # if last_indicator:
                #     last_indicator.chart_id=chart.id
                #     last_indicator.line_color=colors
                #     last_indicator.price_visible=price_visible
                #     last_indicator.line_width=line_width
                #     last_indicator.line_style=line_style
                #     last_indicator.indicator_lines=ind_dict
                    #last_indicator.signal_indicators.update(self.signal_indicators[indicator_id])
                self._is_subchart=len(self.subcharts)>subchart_num
                
                            
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"处理指标数据失败: {e}")
                continue

    def init_from_contract_data(self, contract_data: dict, account_info: dict = None):
        """从合约数据直接初始化图表（不重新读取pkl文件）

        由 StrategyBacktestWindow._create_static_chart_window 调用，
        在 Chart 构造完成后直接传入已解析好的合约数据。

        Args:
            contract_data: 单个合约的完整数据 {
                "symbol": str,
                "index": int,
                "kline": DataFrame,
                "indicators": list
            }
            account_info: 账户信息字典（可选）
        """
        # print(f"📊 init_from_contract_data: symbol={contract_data.get('symbol')}")
        df = contract_data.get("kline")
        indicators = contract_data.get("indicators", [])

        if df is not None and len(df) > 0:
            # print(f"📋 K线数据条数: {len(df)}")
            # print(f"📊 指标组数: {len(indicators)}")
            # if len(df) > 0:
            #     print(df.head())

            if indicators:
                for idx, ind in enumerate(indicators):
                    ind_name = ind.get('name', ['unknown'])
                    ind_indicators = ind.get('indicators', [])
                    doubles = ind.get('doubles', False)
                    overlaps = ind.get('overlaps', [])
                    isplot = ind.get('isplot', [])
                    _lines = ind.get('_lines', [])
                    # 详细打印每个指标的结构
                    ind_type = type(ind_indicators).__name__
                    ind_shape = getattr(ind_indicators, 'shape', len(ind_indicators) if hasattr(ind_indicators, '__len__') else 'N/A')
                    # print(f"   [{idx}] name={ind_name}, _lines={_lines}, doubles={doubles}, overlaps={overlaps}, isplot={isplot}")
                    # print(f"       indicators type={ind_type}, shape={ind_shape}")

            # 确保列顺序正确
            if 'time' in df.columns:
                df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
            self.set(df, True)
            self._kline = df

            # 添加指标数据
            if indicators:
                # print(f"开始加载{len(indicators)}组静态指标数据...")
                self._load_static_indicators(indicators)

            # print(f"✅ 静态图表数据已完全加载（通过 init_from_contract_data）")
            self.set_candle_style()
            self.setChartTheme()

    def add_indicator(self, indicator_id: int, indicator: Union[minibt.IndSeries,minibt.IndFrame],df:Optional[pd.DataFrame]=None):
        """添加指标"""
        if df is None:
            df=self.kline
        #is_reset_cursor_change=bool(list(filter(lambda x:x.chart_id==self.main_chart_id,self.indicator_manager.indicators)))
        #print(f"开始添加指标（ID): {indicator_id}")
        v=indicator
        plot_id, isplot, name, lines, _lines, ind_names, overlaps, \
            categorys, indicators, doubles, _ind_plotinfo, span, _signal = v._get_plot_datas()
        lineinfo = _ind_plotinfo.get('linestyle', {})
        signal_info: dict = _ind_plotinfo.get('signalstyle', {})
        indicator = v.pandas_object
        subchart_num=len(self.subcharts)
        colors=dict()
        price_visible=dict(price_line=False,price_label=False)
        line_width=dict()
        line_style=dict()
        ind_dict = dict()
        if doubles:
            for j in range(2):
                if any(isplot[j]):
                    cache_dict = {}
                    if overlaps[j]:
                            chart:AbstractChart = self.chart
                            # 每次添加主图指标时都重新注册鼠标移动事件
                            # 先重置window[key]变量
                            # salt = chart.id[chart.id.index('.')+1:]
                            # key = f'_cursor_{salt}'
                            # reset_js = f"window['{key}'] = false;"
                            # self.get_webview().page().runJavaScript(reset_js, 0, lambda res: print("✅ 已重置主图鼠标事件监听器"))
                            # # 然后重新注册事件监听
                            # print("🔄 重新注册主图鼠标移动事件")
                            # chart.events.watch_cursor_change()
                    else:
                        chart:AbstractChart = self.create_subchart(
                            'bottom', sync=True)
                        # 添加测试性输出
                        # print(f"创建副图: ID={chart.id}, indicator_id={indicator_id}, name={name[j]}")
                        self.setSubChartTheme(chart, name[j])
                        self.subcharts.update({indicator_id: chart})
                        
                        # 确保副图与主图同步
                        # try:
                        #     main_chart_id = self.chart.id
                            # 首先尝试同步缩放和鼠标移动
                            # sync_js = f"""
                            # (function() {{
                            #     if (typeof Lib !== 'undefined' && Lib.Handler && typeof Lib.Handler.syncCharts === 'function') {{
                            #         // 同步缩放和鼠标移动
                            #         Lib.Handler.syncCharts(
                            #             {chart.id},
                            #             {main_chart_id},
                            #             false
                            #         );
                            #         console.log('同步副图:', {chart.id}, '与主图:', {main_chart_id}, '缩放和鼠标移动');
                            #     }}
                            # }})();
                            # """
                            # self.get_webview().page().runJavaScript(sync_js, 0, lambda res: print(f"✅ 已同步副图 {chart.id} 与主图"))
                        # except Exception as e:
                        #     print(f"同步副图时出错: {e}")
                    for i, plot in enumerate(isplot[j]):
                        if plot:
                            col = _lines[j][i]
                            info = lineinfo[col]
                            color = info.get(
                                "line_color", None)
                            if not color:
                                color = next(self.ind_colors)
                            colors[col]=color
                            style = info.get('line_dash', 'solid')
                            if style != "vbar" and style not in util.LINE_STYLE.__args__:
                                style = 'solid'
                            width = info.get("line_width", 2)
                            # price_line = info.get(
                            #     "price_line", False)
                            # price_label = info.get(
                            #     "price_label", False)
                            line_width[col]=width
                            line_style[col]=style

                            if style == "vbar":
                                # 创建柱状图
                                line = chart.create_histogram(
                                    name=col, color=color, price_line=price_line, price_label=price_label)
                                
                                # 设置indicator_id
                                line.set_indicator_id(indicator_id)

                                # 准备数据
                                hist_data = pd.concat(
                                    [df["time"], indicator[col]], axis=1)

                                # 检查是否是MACD柱状图，如果是，添加颜色列
                                # if "macdh" in col.lower():
                                    # 为MACD柱状图添加颜色列，正值为红色，负值为绿色
                                    # 绿色
                                hist_data['color'] = btcolors.bear_color
                                # 红色
                                hist_data.loc[hist_data[col] > 0,
                                                'color'] = btcolors.bull_color

                                # 设置数据
                                line.set(hist_data)

                            else:
                                line = partial(chart.create_line,
                                                name=col, color=color, style=style, width=width, price_line=False, price_label=False)
                                line.vdata = pd.concat(
                                    [df["time"], indicator[col]], axis=1)
                                line.indicator_id = indicator_id  # 暂存indicator_id，稍后设置
                            cache_dict[col] = line
                    else:
                        # vbar指标在前其它指标线在后，否则vbar柱体会挡住其它指标线
                        if cache_dict:
                            new_dict = {}
                            for _k, _v in cache_dict.items():
                                if hasattr(_v, "vdata"):
                                    data = _v.vdata
                                    # indicator_id_temp = _v.indicator_id if hasattr(_v, 'indicator_id') else None
                                    _v = _v()
                                    _v.set(data)
                                    # 设置indicator_id
                                    # if indicator_id_temp is not None:
                                    _v.set_indicator_id(indicator_id)
                                    _v.init_line_visibility()
                                new_dict.update({_k: _v})
                            ind_dict.update(new_dict)
            if ind_dict:
                self.chart_indicators.update({indicator_id: ind_dict})
        else:
            if any(isplot):
                is_candles = v.iscandles
                if not v.isMDim:
                    indicator = pd.DataFrame(
                        {_lines[0]: indicator})

                if is_candles:
                    if set(indicator.columns) != set(FILED.OHLC):
                        print(f"蜡烛图指标列名必须为{FILED.OHLC}")
                    chart = self.create_subchart(
                        'bottom', sync=True)
                    self.setSubChartTheme(chart, name)
                    self.subcharts.update({indicator_id: chart})
                    candles_df = indicator.copy()
                    candles_df["time"] = df["time"]
                    candles_df = candles_df[FILED.TOHLC]
                    chart.set(candles_df)
                else:
                    if overlaps:
                        chart:AbstractChart = self.chart
                        # 每次添加主图指标时都重新注册鼠标移动事件
                        # 先重置window[key]变量
                        # salt = chart.id[chart.id.index('.')+1:]
                        # key = f'_cursor_{salt}'
                        # reset_js = f"window['{key}'] = false;"
                        # self.get_webview().page().runJavaScript(reset_js, 0, lambda res: print("✅ 已重置主图鼠标事件监听器"))
                        # # 然后重新注册事件监听
                        # print("🔄 重新注册主图鼠标移动事件")
                        # chart.events.watch_cursor_change()
                    else:
                        chart:AbstractChart = self.create_subchart(
                            'bottom', sync=True)
                        self.setSubChartTheme(chart, name)
                        self.subcharts.update({indicator_id: chart})
                        # 确保副图与主图同步
                        # try:
                        #     main_chart_id = self.chart.id
                            # 首先尝试同步缩放和鼠标移动
                            # sync_js = f"""
                            # (function() {{
                            #     if (typeof Lib !== 'undefined' && Lib.Handler && typeof Lib.Handler.syncCharts === 'function') {{
                            #         // 同步缩放和鼠标移动
                            #         Lib.Handler.syncCharts(
                            #             {chart.id},
                            #             {main_chart_id},
                            #             false
                            #         );
                            #         console.log('同步副图:', {chart.id}, '与主图:', {main_chart_id}, '缩放和鼠标移动');
                            #     }}
                            # }})();
                            # """
                            # self.get_webview().page().runJavaScript(sync_js, 0, lambda res: print(f"✅ 已同步副图 {chart.id} 与主图"))
                        # except Exception as e:
                        #     print(f"同步副图时出错: {e}")

                    for i, plot in enumerate(isplot):
                        if plot:
                            col = _lines[i]
                            info = lineinfo[col]
                            color = info.get(
                                "line_color", None)
                            if not color:
                                color = next(self.ind_colors)
                            style = info.get('line_dash', 'solid')
                            if style != "vbar" and style not in util.LINE_STYLE.__args__:
                                style = 'solid'
                            width = info.get("line_width", 2)
                            # price_line = info.get(
                            #     "price_line", False)
                            # price_label = info.get(
                            #     "price_label", False)
                            colors[col]=color
                            # price_visible["price_line"]=price_line
                            # price_visible["price_label"]=price_label
                            line_width[col]=width
                            line_style[col]=style
                            if style == "vbar":
                                # 创建柱状图
                                line = chart.create_histogram(
                                    name=col, color=color, price_line=False, price_label=False)

                                # 准备数据
                                hist_data = pd.concat(
                                    [df["time"], indicator[col]], axis=1)

                                # 检查是否是MACD柱状图，如果是，添加颜色列
                                if "macdh" in col.lower():
                                    # 为MACD柱状图添加颜色列，正值为红色，负值为绿色
                                    # 绿色
                                    hist_data['color'] = btcolors.bear_color
                                    # 红色
                                    hist_data.loc[hist_data[col] > 0,
                                                    'color'] = btcolors.bull_color

                                # 设置数据
                                line.set(hist_data)
                            else:
                                line = partial(chart.create_line,
                                                name=col, color=color, style=style, width=width, price_line=False, price_label=False)
                                line.vdata = pd.concat(
                                    [df["time"], indicator[col]], axis=1)
                            ind_dict[col] = line
                    else:
                        if ind_dict:
                            new_dict = {}
                            for _k, _v in ind_dict.items():
                                if hasattr(_v, "vdata"):
                                    data = _v.vdata
                                    _v = _v()
                                    _v.set(data)
                                    # 设置indicator_id
                                    _v.set_indicator_id(indicator_id)
                                    _v.init_line_visibility()
                                new_dict.update({_k: _v})
                            ind_dict = new_dict
                if ind_dict:
                    self.chart_indicators.update({indicator_id: ind_dict})
        # 交易信号：
        if signal_info:
            signal_dict = {}
            last_signal_dict = {}
            all_markers = []

            for signalname, signal_config in signal_info.items():
                signalkey, signalcolor, signalmarker, signaloverlap, signalshow, signalsize, signallabel = list(
                    signal_config.values())
                signal_series = indicator[signalname]
                is_buy_signal = any([name in signalname for name in [
                                    "long", "exitshort"]]) or "low" in signalkey.lower()
                signal_points = signal_series[signal_series > 0]
                if is_buy_signal:
                    position = 'below'
                    shape = signalmarker if signalmarker in util.MARKER_SHAPE.__args__ else 'arrow_up'
                    color = signalcolor if signalcolor else btcolors.bear_color
                else:
                    position = 'above'
                    shape = signalmarker if signalmarker in util.MARKER_SHAPE.__args__ else 'arrow_down'
                    color = signalcolor if signalcolor else btcolors.bull_color
                text = signallabel.get("text", "") if isinstance(
                    signallabel, dict) else ""
                signalconfig = dict(
                    position=position, shape=shape, color=color, text=text)

                for idx in signal_points.index:
                    time_value = df.iloc[idx]['time']
                    # 将纳秒级时间戳转换为秒级时间戳（与图表内部格式一致）
                    if isinstance(time_value, (int, float)) and time_value > 1e15:
                        time_value = pd.to_datetime(time_value)
                    all_markers.append(
                        {"time": time_value, **signalconfig})
                else:
                    if not signal_series.empty and signal_series.iloc[-1] > 0:
                        last_time_value = df.iloc[-1]['time']
                        if isinstance(last_time_value, (int, float)) and last_time_value > 1e15:
                            last_time_value = pd.to_datetime(last_time_value)
                        last_signal_dict[signalname] = self._single_datetime_format(
                            last_time_value)
                signal_dict.update({signalname: signalconfig})
            if all_markers:
                all_markers.sort(key=lambda x: x["time"])
                self.marker_list(all_markers)
                if last_signal_dict:
                    count = 0
                    for markername in reversed(self.markers):
                        marker = self.markers[markername]
                        for lsd, lsv in last_signal_dict.items():
                            if marker["time"] == lsv:
                                signal_dict[lsd]["signal"] = markername
                                self._signal_markers[(indicator_id, lsd, lsv)] = markername
                                count += 1
                        if count == len(last_signal_dict):
                            break

            self.signal_indicators.update({indicator_id: signal_dict})
        
        self._resizes()
        if hasattr(self, 'indicator_manager'):
            last_indicator = self.indicator_manager.last_indicator
            if last_indicator:
                last_indicator.chart_id = chart.id
                last_indicator.line_color = colors
            last_indicator.price_visible=price_visible
            last_indicator.line_width=line_width
            last_indicator.line_style=line_style
            last_indicator.indicator_lines=ind_dict
            # last_indicator.overlaps = overlaps
            # print(colors,price_visible,line_width,line_style,ind_dict,overlaps)
            #last_indicator.signal_indicators.update(self.signal_indicators[indicator_id])
        self._is_subchart=len(self.subcharts)>subchart_num
    
    def replay_indicator_params(self, indicator_id: int,indcard,callback:callable):#params:dict):
        """
        重放指标参数
        :param indicator_id: 要重放的指标ID
        :param params: 指标参数
        """
        QTimer.singleShot(0, lambda: self._replay_indicator_params(indicator_id,indcard,callback))
    
    def _replay_indicator_params(self, indicator_id: int,indcard:"IndicatorParamsCard",callback:callable):#params:dict):
        """
        重放指标参数
        :param indicator_id: 要重放的指标ID
        :param params: 指标参数
        """
        is_params_changed = indcard.is_params_changes
        #print(indicator_id,self.chart_indicators)
        if is_params_changed and indicator_id in self.chart_indicators:
            kline=self.get_new_kline()
            ind = self.indicator_manager.calculate_target_indicator(kline,indicator_id)
            value=ind.pandas_object
            if not ind.isMDim:
                value = pd.DataFrame(
                    {ind.lines[0]: value})
            indicator = self.chart_indicators[indicator_id]
            for col, line in indicator.items():
                data = pd.concat([kline["time"], value[col]], axis=1)
                line.set(data)
        # else:
        #     print(f"指标ID {indicator_id} 不存在")
        callback()
    
    
    def remove_indicator(self, indicator_id: int):
        """
        移除指标
        :param indicator_id: 要移除的指标ID
        """
        if self.chart:
            # 创建字典的副本以避免迭代时修改字典
            if indicator_id in self.chart_indicators:
                for index, ind_dict in list(self.chart_indicators.items()):
                    if index == indicator_id:
                        # print(index, ind_dict)
                        # 尝试删除每个指标线条（包括主图和副图中的指标线）
                        for _, _v in ind_dict.items():
                            # self.del_line(_v)
                            _v.delete()
                        # 从图表指标字典中移除
                        del self.chart_indicators[index]
                        # # 从subcharts字典中移除对应的副图
                        if index in self.subcharts:
                            # 调用delete_subchart方法删除副图
                            self.delete_subchart(index)
                        # if index in self.subcharts:
                        #     subchart = self.subcharts.pop(index)
                        #     subchart.resize(1., 0.)
                        # 重新计算图表大小
                        if hasattr(self, '_resizes'):
                            self._resizes()
                        
                        # 当删除主图指标时，重置window[key]变量
                        # 这样当重新添加指标时，watch_cursor_change会重新绑定事件
                        QTimer.singleShot(500, self.reset_cursor_change)
                
            # else:
            #     print(f"指标ID {indicator_id} 不存在")
                
    def reset_cursor_change(self):
        # print(f"当前指标图表ID: {self.main_chart_id}")
        # for indicator in self.indicator_manager.indicators:
            # print(indicator.chart_id)
        if not hasattr(self, 'indicator_manager'):
            return
        if not list(filter(lambda x:x.chart_id==self.main_chart_id,self.indicator_manager.indicators)):
            # print("🔄 重置主图鼠标事件监听器")
            chart = self.chart
            salt = chart.id[chart.id.index('.')+1:]
            key = f'_cursor_{salt}'
            reset_js = f"window['{key}'] = false;"
            self.get_webview().page().runJavaScript(reset_js, 0)#, lambda res: print("✅ 已重置主图鼠标事件监听器"))
                    
                    
    def reset_update_queue(self):
        self.update_queue.clear()
        self.update_queue.add(self.init_update())

    def monitor_loop(self):
        try:
            self.update_queue.add(
                self.api.wait_update(1))
        except Exception as e:
            print(f"监视器更新异常：{e}")

            
    def kline_loop(self):
        """行情更新函数"""
        try:
            self.update_queue.add(self.api.wait_update(1))
            self._is_update = self.update_queue.any
            if self._is_update:
                self.kline_update()
        except Exception as e:
            print(f"K线更新异常：{e}")

    def account_loop(self):
        """账户更新函数"""
        try:
            if self._is_update:
                self.account_update()
        except Exception as e:
            print(f"账户更新异常：{e}")

    def indicator_loop(self):
        """循环执行指标计算（不依赖K线更新，独立循环）"""
        try:
            if self._is_update:
                self.strategy()
                self.indicator_update()
        except Exception as e:
            print(f"指标更新异常：{e}")

    def is_changing(self, obj: Union[Candlestick, Line], ns) -> int:
        """判断是否更新,获取最新时间与图表最后更新时间的差转化为需要更新数据的K线数量"""
        if obj._last_bar is None:
            return -1
        return int((ns*1e-9-obj._last_bar["time"])/self.cycle)

    def is_key_changing(self, chart_obj: Union[Candlestick, Line], obj: pd.DataFrame, key: str = "close") -> bool:
        if chart_obj._last_bar is None:
            return False
        return chart_obj._last_bar[key] != obj[key]

    @property
    def datetime(self) -> pd.Series:
        # 股票数据时间已经是正确的，不需要时区调整
        if self.is_stock:
            return self._kline["datetime"].copy()
        else:
            # 期货数据需要时区调整
            return self._kline["datetime"].copy() + 8*3.6e12

    @property
    def new_datetime(self) -> pd.Series:
        if self.is_stock:
            return self._kline["datetime"].iloc[-2:].copy()
        else:
            return self._kline["datetime"].iloc[-2:].copy() + 8*3.6e12

    @property
    def last_datetime(self) -> int:
        if self.is_stock:
            return self._kline["datetime"].iloc[-1]
        else:
            return self._kline["datetime"].iloc[-1] + 8*3.6e12

    @property
    def kline(self) -> pd.DataFrame:
        kline = self._kline.copy()
        if self.is_stock:
            # 股票数据时间已经是正确的，不需要时区调整
            kline['time'] = kline.datetime
            kline = kline[FILED.TALL]
            return kline
        else:
            # 期货数据需要时区调整
            kline["datetime"] = kline["datetime"] + 8*3.6e12
            kline = kline[FILED.ALL]
            kline.columns = FILED.TALL
        return kline

    @property
    def new_kline(self) -> pd.DataFrame:
        kline = self._kline.iloc[-2:].copy()
        if self.is_stock:
            # 股票数据时间已经是正确的，不需要时区调整
            kline['time'] = kline.datetime
            kline = kline[FILED.TALL]
            return kline
        else:
            # 期货数据需要时区调整
            kline["datetime"] = kline["datetime"] + 8*3.6e12
            kline = kline[FILED.ALL]
            kline.columns = FILED.TALL
        return kline
    
    def get_new_kline(self) -> None:
        """处理K线数据"""
        if not self.symbol:
            return self._kline
        
        # 根据合约类型选择数据源
        if self.is_stock:
            # 股票：使用 StockApi
            if hasattr(self.main_window, 'stock_api') and self.main_window.stock_api:
                stock_api = self.main_window.stock_api
                kline = stock_api.get_kline_serial(self.symbol, self.cycle).copy()
                if kline is not None and not kline.empty:
                    kline = kline.copy()
                    # 股票数据时间已经是正确的，不需要时区调整
                    kline = kline[FILED.ALL]
                    kline.columns = FILED.TALL
                    return kline
            return self._kline
        else:
            # 期货：使用天勤API
            kline = self.api.get_kline_serial(self.symbol, self.cycle, len(self.chart.candle_data)).copy()
            # 期货数据需要时区调整
            kline["datetime"] = kline["datetime"] + 8*3.6e12
            kline = kline[FILED.ALL]
            kline.columns = FILED.TALL
            return kline

    def __fetch_kline_data(self):
        """获取K线数据（子线程执行）"""
        # latest_tick_time = self.last_datetime
        # chang = self.is_changing(
        #     self.chart, latest_tick_time)
        # kline = self.new_kline[FILED.ALL]
        
        kline = self._kline.iloc[self.test_index-2:self.test_index].copy()
        kline["datetime"] = kline["datetime"]+8*3.6e12
        kline = kline[FILED.ALL]
        chang=-1
        self.test_index+=1
        #更新频率高的条件放前面
        if chang == -1:
            # _last_bar 为 None，需要完整更新
            series = kline.iloc[-1]
            series.index = FILED.TALL
            self.update(series)
            # data["update"]=series
        elif chang == 0:
            series = kline.iloc[-1][FILED.DCV]
            series.index = FILED.TPV
            self.update_from_tick(series)
            # data["update_from_tick"]=series
        elif chang == 1:
            series = kline.iloc[-2][FILED.DCV]
            series.index = FILED.TPV
            self.update_from_tick(series)
            # data["update_from_tick"]=series
            series = kline.iloc[-1]
            series.index = FILED.TALL
            self.update(series)
            # data["update"]=series
        else:
            series = kline.iloc[-1]
            series.index = FILED.TALL
            self.update(series)
            # data["update"]=series
        
        

    def kline_update(self, data: dict) -> None:
        """K线更新函数"""
        if not data:
            return
        try:
            # print(f"K线更新：{self.last_datetime}")
            # print(self.chart,self.new_kline.iloc[-1])
            # print(data)
            for k,v in data.items():
                getattr(self,k)(v)
            # if "update_from_tick" in data:
            #     self.update_from_tick(data["update_from_tick"])
            # if "update" in data:
            #     self.update(data["update"])
            
        except Exception as e:
            print(f"K线更新异常：{e}")

    def account_update(self):
        pos = self.position.pos
        price = 0.
        if pos:
            price = self.position.open_price_long if pos > 0 else self.position.open_price_short
            profit = self.position.float_profit
            text = f"⬆️{profit}" if pos > 0 else f"⬇️{profit}"
            color = btcolors.bear_color if profit > 0 else btcolors.bull_color
            if self.position_horizontal_line.price != price:
                self.position_horizontal_line.update(price)
            self.position_horizontal_line.options(
                color=color, style='dashed', width=3, text=text)

        if price == 0. and self.position_horizontal_line.price != price:
            self.position_horizontal_line.update(price)
            self.position_horizontal_line.options(
                color=btcolors.bear_color, style='dashed', width=3)
        if self.account.float_profit or self.account_float_profit:
            self.light_chart_window.info_window.set_account_info(
                self.strategy._get_account_info())
            self.account_float_profit = self.account.float_profit

    def indicator_update(self,indicators:dict[str,Union[minibt.IndFrame,minibt.IndSeries]]):
        """指标更新"""
        datetime = self.new_datetime
        last_time = datetime.iloc[-1]
        for indicator_id, v in indicators.items():
            ischang = False  # 每个 indicator 独立计算 chang, 避免不同指标间复用导致状态错位
            if v.plot_id == self.current_index and (indicator_id in self.chart_indicators or indicator_id in self.subcharts):
                if v.iscandles:
                    chart = self.subcharts[indicator_id]
                    if not ischang:
                        chang = self.is_changing(chart, last_time)
                        ischang = True
                    if chang == 0:
                        series = pd.Series(
                            [last_time, v.iloc[-1][3]], index=FILED.TP)
                        chart.update_from_tick(series)
                    elif chang == 1:
                        series = pd.Series(
                            [datetime.iloc[-2], v.iloc[-2][3]], index=FILED.TP)
                        chart.update_from_tick(series)
                        series = pd.Series(
                            [datetime.iloc[-1], *v.iloc[-1].values], index=FILED.TOHLC)
                        chart.update(series)
                    else:
                        series = pd.Series(
                            [datetime.iloc[-1], *v.iloc[-1].values], index=FILED.TOHLC)
                        chart.update(series)

                else:
                    lines = self.chart_indicators[indicator_id]
                    if v.isMDim:
                        ind = v
                    else:
                        ind = pd.DataFrame({v.lines[0]: v.values})
                    for name in v.lines:
                        if name in lines:
                            line = lines[name]
                            if not ischang:
                                chang = self.is_changing(line, last_time)
                                ischang = True
                            values = ind[name].values
                            # 检查是否是MACD柱状图（vbar类型）
                            if hasattr(line, 'update') and "macdh" in name.lower():
                                # 对于MACD柱状图，使用update方法更新数据
                                if chang == 0 or chang > 1:
                                    # 创建包含颜色信息的Series
                                    value = values[-1]
                                    series = pd.Series(
                                        [datetime.iloc[-1], value],
                                        index=["time", name]
                                    )
                                    # 添加颜色信息：正值为bull_color，负值为bear_color
                                    series['color'] = btcolors.bull_color if value > 0 else btcolors.bear_color
                                    # 使用update方法更新数据
                                    line.update(series)
                                else:
                                    # 对于需要更新两个点的情况
                                    for j in range(-2, 0):
                                        value = values[j]
                                        series = pd.Series(
                                            [datetime.iloc[j], value],
                                            index=["time", name]
                                        )
                                        # 添加颜色信息：正值为bull_color，负值为bear_color
                                        series['color'] = btcolors.bull_color if value > 0 else btcolors.bear_color
                                        # 使用update方法更新数据
                                        line.update(series)
                            else:
                                # 普通指标线的更新逻辑
                                if chang == 0 or chang > 1:
                                    series = pd.Series(
                                        [datetime.iloc[-1], values[-1]], index=["time", name])
                                    line.update(series)
                                else:
                                    for j in range(-2, 0):
                                        series = pd.Series(
                                            [datetime.iloc[j], values[j]], index=["time", name])
                                        line.update(series)
                if indicator_id in self.signal_indicators:
                    signal: dict[str, dict] = self.signal_indicators[indicator_id]
                    for sk, sv in signal.items():
                        # chang == 0: 没有新K线，处理最新一根K线的信号变化
                        # chang == 1: 有1根新K线，处理倒数第二根（上一根已确认）的信号变化
                        # chang > 1: 批量添加多根K线，需要重放 chang-1..-2 之间的所有历史信号
                        seq = range(-2, -2)  # 默认空
                        if chang:
                            if chang == 1:
                                seq = range(-2, -1)  # 仅上一根
                            else:
                                seq = range(-chang, -1)  # 批量新增的所有历史K线
                        else:
                            seq = range(-1, 0)  # 仅最新一根

                        for idx in seq:
                            svalue = v[sk].values[idx]  # 该位置信号的值
                            time_value = datetime.iloc[idx]
                            if isinstance(time_value, (int, float)) and time_value > 1e15:
                                time_value = pd.to_datetime(time_value)

                            # 从 self._signal_markers 中按 (indicator_id, sk, time_key) 查找 marker_id
                            time_key = self._single_datetime_format(time_value)
                            marker_key = (indicator_id, sk, time_key)
                            last_signal = self._signal_markers.pop(marker_key, None)

                            if svalue > 0:
                                # 该位置有信号：若尚未创建过 marker 则创建，否则保留已有 marker
                                if last_signal is None:
                                    last_signal = self.marker(time_value, **sv)
                                self._signal_markers[marker_key] = last_signal
                            else:
                                # 该位置无信号：若有活跃 marker 则删除，并清理映射
                                if last_signal is not None:
                                    self.remove_marker(last_signal)

    

    def set_watermark(self, dark: bool, text: str="", font_size: int = 44,**kwargs):
        """设置水印"""
        color: str = 'rgba(180, 180, 200, 0.2)' if dark else 'rgba(75, 75, 55, 0.2)'
        self.watermark(text, font_size, color)

    def sub_legend_params(self, name, dark):
        """指标参数显示"""
        return dict(text=name, color='rgb(249, 249, 249)' if dark else 'rgb(6, 6, 6)', lines=True, font_size=14, color_based_on_candle=True)

    def _resizes(self):
        """指标窗口高度设置,主图占3,副图占1"""
        num=len(self.subcharts)
        if num == 0:
            self.resize(1, 1)
            return
        num = round(1./(3+num), 4)
        chart_size = 1.+5e-3
        for subchart in self.subcharts.values():
            subchart.resize(1., num)
            chart_size -= num
        self.resize(1., chart_size)

    def setTheme(self, dark: bool):
        """设置所有chart的样式"""
        charts = [self, *self.subcharts.values()]
        for chart in charts:
            self.setChartTheme(chart, dark)
        
        if self.water_mark:
            self.set_watermark(dark, **self.water_mark)
        if self._webview_loadfinished:
            self.add_chart_separator_lines(dark)

    def setChartTheme(self, chart: AbstractChart = None, dark: bool = None):
        """设置对应chart的样式"""
        # 只有在 WebView 加载完成后才执行
        if not self._webview_loadfinished:
            return

        if chart is None:
            chart = self
        if dark is None:
            try:
                # if self.main_window and hasattr(self.main_window, 'is_dark_theme'):
                #     dark = self.main_window.is_dark_theme
                # else:
                #     dark = False
                dark = isDarkTheme()
                
            except Exception as e:
                print(f"获取主题时出错: {e}")
                dark = False

        if dark:
            chart.layout(background_color='rgb(6, 6, 6)', text_color='rgb(249, 249, 249)', font_size=14,
                         font_family='Microsoft YaHei')  # 'Helvetica')
            chart.grid(color="rgb(26, 26, 26)")
            chart.legend(visible=True, font_size=14,
                         color='rgb(249, 249, 249)', lines=True)
        else:
            chart.layout(background_color='rgb(249, 249, 249)', text_color='rgb(6, 6, 6)', font_size=14,
                         font_family='Microsoft YaHei')  # 'Helvetica')
            chart.grid(color="rgb(229, 229, 229)")
            chart.legend(visible=True, font_size=14,
                         color='rgb(6, 6, 6)', lines=True)

    def setSubChartTheme(self, chart: AbstractChart, text: str = ""):
        """设置对应子图的样式"""
        # 只有在 WebView 加载完成后才执行
        if not self._webview_loadfinished:
            return

        try:
            # if self.main_window and hasattr(self.main_window, 'is_dark_theme'):
            #     dark = self.main_window.is_dark_theme
            # else:
            #     dark = False
            dark = isDarkTheme()
                
        except Exception as e:
            print(f"获取主题时出错: {e}")
            dark = False
        if dark:
            chart.layout(background_color='rgb(6, 6, 6)', text_color='rgb(249, 249, 249)', font_size=14,
                         font_family='Microsoft YaHei')  # 'Helvetica')
            chart.grid(color="rgb(26, 26, 26)")
            chart.legend(True, **self.sub_legend_params(text, dark))
        else:
            chart.layout(background_color='rgb(249, 249, 249)', text_color='rgb(6, 6, 6)', font_size=14,
                         font_family='Microsoft YaHei')  # 'Helvetica')
            chart.grid(color="rgb(229, 229, 229)")
            chart.legend(True, **self.sub_legend_params(text, dark))

    def _set_price_scale_fixed_width(self, chart: AbstractChart, target_width: int = None):
        """
        固定副图价格轴宽度，自动同步主图价格轴宽度
        :param chart: 主图实例（AbstractChart类型），用于获取主图价格轴宽度
        :param target_width: 可选参数，手动指定宽度；若为None，自动同步主图宽度
        :return: 无
        """
        chart.run_script(f'''
            {chart.id}.chart.priceScale("right").applyOptions({{
                minimumWidth: {target_width},
                width: {target_width} ,
                autoScale: false
            }});
        ''')

    def set_price_scale_fixed_width(self, chart: AbstractChart, target_width: int = None):
        """固定副图价格轴宽度（优化容错与性能，避免无效执行）"""
        target_width = target_width if (
            target_width is not None and target_width > 0) else 80

        if not chart or not hasattr(chart, 'id'):
            return

        script = f'''
            try {{
                var targetChart = {chart.id};
                if (targetChart && targetChart.chart && targetChart.chart.priceScale) {{
                    var priceScale = targetChart.chart.priceScale("right");
                    priceScale.applyOptions({{
                        minimumWidth: {target_width},
                        width: {target_width},
                        autoScale: false
                    }});
                }}
            }} catch (e) {{
                console.error("设置副图价格轴宽度失败：", e);
            }}
        '''
        chart.run_script(script)

    def set_only_last_chart_xaxis_visible(self):
        """
        遍历所有主图+副图，仅最后一个图表显示X轴时间，其余隐藏X轴
        """
        # 1. 收集所有图表：主图 + 所有副图
        all_charts = [self]  # 主图
        all_charts.extend(self.subcharts.values())  # 所有副图
        last_index = len(all_charts) - 1

        if not all_charts:
            return

        # 2. 遍历所有图表，仅最后一个显示X轴
        for idx, chart in enumerate(all_charts):
            # 仅最后一个图表显示X轴，其余隐藏
            is_visible = idx == last_index
            self._set_chart_xaxis_visible(chart, is_visible)

    def _set_chart_xaxis_visible(self, chart: AbstractChart, visible: bool):
        """
        控制单个图表的X轴显示/隐藏（修正lightweight-charts API调用方式）
        :param chart: 目标图表
        :param visible: True=显示X轴，False=隐藏X轴
        """
        chart.run_script(f'''
            try {{
                var targetChart = {chart.id};
                if (targetChart && targetChart.chart && targetChart.chart.timeScale) {{
                    targetChart.chart.timeScale().applyOptions({{
                        visible: {str(visible).lower()}
                    }});
                }}
            }} catch (e) {{
                console.error("设置图表X轴显示状态失败：", e);
            }}
        ''')

    def _get_market_watch_window(self):
        """
        获取MarketWatchWindow实例
        """
        # 首先检查light_chart_window是否有marketWatchWindow属性
        if hasattr(self.light_chart_window, 'market_watch_window'):
            return self.light_chart_window.market_watch_window
        return None

    def _set_insert_position(self, position):
        """
        设置插入位置
        
        Args:
            position: 插入位置（left, right, top, bottom）
        """
        market_watch = self._get_market_watch_window()
        if market_watch and hasattr(market_watch, 'set_insert_position'):
            market_watch.set_insert_position(position)

    def _add_kline_section(self, contract_name=None):
        """
        添加K线图板块
        
        Args:
            contract_name: 合约名称，如果为None则使用默认合约
        """
        market_watch = self._get_market_watch_window()
        if market_watch:
            # 设置当前控件为当前LightChartWindow
            market_watch.current_widget = self.light_chart_window
            
            if hasattr(market_watch, 'add_sub_window'):
                # 调用add_sub_window，传递合约名称，它会考虑插入位置
                market_watch.add_sub_window(contract_name)

    def _close_current_section(self):
        """
        关闭当前板块
        """
        market_watch = self._get_market_watch_window()
        if market_watch and hasattr(market_watch, 'close_current_widget'):
            # 设置当前控件为当前LightChartWindow
            market_watch.current_widget = self.light_chart_window
            market_watch.close_current_widget()

    def add_chart_separator_lines(self, dark: bool = None):
        """
        通过lightweight-charts的容器结构添加分隔线
        """
        if not self.subcharts:
            return
        border_color = "rgba(180, 180, 180, 0.3)" if dark else "rgba(80, 80, 80, 0.3)"

        # 构建一次性执行的JavaScript脚本
        script = f'''
        (function() {{
            try {{
                console.log("开始添加图表分隔线");
                
                // 查找所有lightweight-charts容器
                var chartContainers = document.querySelectorAll('.tv-lightweight-charts');
                console.log("找到图表容器数量:", chartContainers.length);
                
                if (chartContainers.length === 0) {{
                    console.warn("未找到任何lightweight-charts容器");
                    return;
                }}
                
                // 为每个图表容器添加分隔线
                for (var i = 0; i < chartContainers.length; i++) {{
                    var container = chartContainers[i];
                    var separatorId = 'chart_separator_' + i;
                    
                    // 移除已存在的分隔线
                    var existingSeparator = document.getElementById(separatorId);
                    if (existingSeparator) {{
                        existingSeparator.remove();
                    }}
                    
                    // 创建新的分隔线
                    var separator = document.createElement('div');
                    separator.id = separatorId;
                    separator.style.cssText = `
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 1px;
                        background-color: {border_color};
                        z-index: 1000;
                        pointer-events: none;
                    `;
                    
                    // 确保容器有相对定位
                    container.style.position = 'relative';
                    container.appendChild(separator);
                    
                    console.log("为图表容器", i, "添加分隔线成功");
                }}
                
                console.log("全部分隔线添加完成");
                
            }} catch (error) {{
                console.error("添加分隔线时出错:", error);
            }}
        }})();
        '''
        self.run_script(script)

    def _on_webview_custom_context_menu(self, pos):
        """
        自定义 WebView 右键菜单槽函数（添加图标 + 关于弹窗，适配自定义 Dialog）
        """
        # 静态图表（回测等）禁用右键菜单（缺少 indicator_manager 等运行时组件）
        if self.is_static:
            return
        webview = self.get_webview()
        custom_menu = RoundMenu("", webview)

        # 新增：添加子窗口相关菜单（如果启用）
        if hasattr(self.light_chart_window, 'enable_subwindow_menu') and self.light_chart_window.enable_subwindow_menu:
            # 获取MarketWatchWindow实例
            market_watch = self._get_market_watch_window()
            # 设置当前控件为当前LightChartWindow
            if market_watch:
                market_watch.current_widget = self.light_chart_window
            
            # 添加插入位置菜单项
            insert_menu = RoundMenu("插入位置", parent=custom_menu)#custom_menu.addMenu("插入位置")
            
            # 获取当前选中的插入位置
            current_position = "right"  # 默认右侧
            if market_watch and hasattr(market_watch, 'insert_position'):
                current_position = market_watch.insert_position
            
            # 添加方向菜单项
            left_action = Action("左侧", parent=insert_menu)
            left_action.triggered.connect(lambda: self._set_insert_position("left"))
            if current_position == "left":
                left_action.setIcon(FluentIcon.ACCEPT.icon())
            else:
                left_action.setIcon(FluentIcon.CLOSE.icon())
            
            right_action = Action("右侧", parent=insert_menu)
            right_action.triggered.connect(lambda: self._set_insert_position("right"))
            if current_position == "right":
                right_action.setIcon(FluentIcon.ACCEPT.icon())
            else:
                right_action.setIcon(FluentIcon.CLOSE.icon())
            
            top_action = Action("上方", parent=insert_menu)
            top_action.triggered.connect(lambda: self._set_insert_position("top"))
            if current_position == "top":
                top_action.setIcon(FluentIcon.ACCEPT.icon())
            else:
                top_action.setIcon(FluentIcon.CLOSE.icon())
            
            bottom_action = Action("下方", parent=insert_menu)
            bottom_action.triggered.connect(lambda: self._set_insert_position("bottom"))
            if current_position == "bottom":
                bottom_action.setIcon(FluentIcon.ACCEPT.icon())
            else:
                bottom_action.setIcon(FluentIcon.CLOSE.icon())
            insert_menu.addAction(left_action)
            insert_menu.addAction(right_action)
            insert_menu.addAction(top_action)
            insert_menu.addAction(bottom_action)
            # 添加板块菜单项
            add_menu = RoundMenu("添加板块", parent=custom_menu)#custom_menu.addMenu("添加板块")
            
            # 添加K线图菜单项（包含主力合约列表）
            kline_menu = RoundMenu("K线图", parent=add_menu)
            
            # 检查是否有exchanges数据
            main_window = getattr(self.light_chart_window, 'main_window', None)
            if main_window and hasattr(main_window, 'tq_object') and hasattr(main_window.tq_object, 'exchanges'):
                tq_object = main_window.tq_object
                # 指定ins_class为"主力"
                ins_class = "主力"
                if ins_class in tq_object.exchanges:
                    exchanges_data = tq_object.exchanges[ins_class]
                    for exchange, contracts in exchanges_data.items():
                        # 创建交易所菜单
                        exchange_menu = RoundMenu(exchange, parent=kline_menu)
                        # 添加合约列表
                        for contract in contracts:
                            contract_action = Action(contract, parent=exchange_menu)
                            # 触发添加K线窗口的方法
                            contract_action.triggered.connect(lambda checked, c=contract: self._add_kline_section(c))
                            exchange_menu.addAction(contract_action)
                        kline_menu.addMenu(exchange_menu)
            # else:
            #     # 如果没有exchanges数据，添加默认K线图选项
            #     default_action = Action("默认K线图", parent=kline_menu)
            #     default_action.triggered.connect(self._add_kline_section)
            #     kline_menu.addAction(default_action)
            
            add_menu.addMenu(kline_menu)
            
            custom_menu.addMenu(insert_menu)
            custom_menu.addMenu(add_menu)
            # 添加关闭菜单项
            # 只有当窗口数量大于1时才显示关闭菜单项
            if market_watch and hasattr(market_watch, 'window_count') and market_watch.window_count > 1:
                close_action = Action("关闭", parent=custom_menu)
                close_action.triggered.connect(self._close_current_section)
                custom_menu.addAction(close_action)
            custom_menu.addSeparator()

        action_reload = Action("重新加载", parent=custom_menu)
        action_reload.setIcon(FluentIcon.UPDATE.icon())

        action_refresh = Action("适应窗口", parent=custom_menu)
        action_refresh.setIcon(FluentIcon.FIT_PAGE.icon())  # 适配窗口图标

        action_restore_range = Action("恢复窗口", parent=custom_menu)
        action_restore_range.setIcon(
            FluentIcon.BACK_TO_WINDOW.icon())  # 恢复窗口图标

        action_show_latest_kline = Action("最近K线", parent=custom_menu)
        action_show_latest_kline.setIcon(
            FluentIcon.SYNC.icon())
        action_show_latest_kline.setToolTip(
            "快速切换到最新300根K线视图")

        action_clear = Action("清空画线", parent=custom_menu)
        action_clear.setIcon(FluentIcon.BROOM.icon())
        action_tool = Action(
            "关闭画线工具" if self.toolbox else "打开画线工具", parent=custom_menu)
        action_tool.setIcon(FluentIcon.CLEAR_SELECTION.icon(
        ) if self.toolbox else FluentIcon.ERASE_TOOL.icon())

        action_alert = Action("价格预警设置", parent=custom_menu)
        action_alert.setIcon(FluentIcon.MESSAGE.icon())

        action_alert_stats = Action("清除预警", parent=custom_menu)
        action_alert_stats.setIcon(FluentIcon.DELETE.icon())

        # 添加删除指标菜单项
        action_delete_indicator = Action("删除指标", parent=custom_menu)
        action_delete_indicator.setIcon(FluentIcon.DELETE.icon())

        # 添加指标菜单
        indicator_menu = RoundMenu("指标", parent=custom_menu)
        indicator_menu.setIcon(FluentIcon.ADD_TO.icon())
        
        # 从主窗口的minibt_object中获取指标数据
        main_window = getattr(self.light_chart_window, 'main_window', None)
        if main_window and hasattr(main_window, 'minibt_object') and main_window.minibt_object:
            minibt_object = main_window.minibt_object
            # 获取所有指标类
            indicator_classes = minibt_object.get_indicator_classes()
            
            for class_name in indicator_classes:
                # 创建指标类菜单
                class_menu = RoundMenu(class_name, parent=indicator_menu)
                # 获取该类的指标
                indicators = minibt_object.get_indicators(class_name)
                # 添加指标到菜单
                for indicator in indicators:
                    if len(indicator) >= 2:
                        name, description = indicator[0], indicator[1]
                        # 创建指标Action
                        indicator_action = Action(name, parent=class_menu)
                        # 绑定触发事件，在K线图中添加该指标
                        indicator_action.triggered.connect(lambda checked, cn=class_name, ind_name=name: self._add_indicator_from_menu(cn, ind_name))
                        class_menu.addAction(indicator_action)
                # 添加类菜单到指标菜单
                if class_menu.actions():
                    indicator_menu.addMenu(class_menu)
        
        mouse_color_action = Action("鼠标标签色", parent=custom_menu)
        mouse_color_action.setIcon(FluentIcon.PALETTE.icon())

        candle_style_meun = RoundMenu("蜡烛图样式", parent=custom_menu)
        candle_style_meun.setIcon(FluentIcon.BRUSH.icon())

        candle_style_bull_action = Action("上涨", parent=candle_style_meun)
        candle_style_bull_action.setIcon(FluentIcon.CARE_UP_SOLID.icon())
        candle_style_bull_action.triggered.connect(
            self.open_candle_style_bull_dialog)

        candle_style_bear_action = Action("下跌", parent=candle_style_meun)
        candle_style_bear_action.setIcon(FluentIcon.CARE_DOWN_SOLID.icon())
        candle_style_bear_action.triggered.connect(
            self.open_candle_style_bear_dialog)

        candle_style_meun.addAction(candle_style_bull_action)
        candle_style_meun.addAction(candle_style_bear_action)

        default_candle_style_action = Action("默认蜡烛图样式", parent=custom_menu)
        default_candle_style_action.setIcon(FluentIcon.LABEL.icon())
        default_candle_style_action.triggered.connect(
            self.set_default_candle_style)

        action_settings = Action("恢复默认设置", parent=custom_menu)
        action_settings.setIcon(FluentIcon.SETTING.icon())

        action_about = Action("关于", parent=custom_menu)
        action_about.setIcon(FluentIcon.INFO.icon())

        # 绑定槽函数
        action_reload.triggered.connect(
            lambda: self.light_chart_window.replace_chart())
        action_refresh.triggered.connect(self._fit_chart)
        action_restore_range.triggered.connect(self._restore_visible_range)
        action_show_latest_kline.triggered.connect(
            self._switch_to_latest_300_kline)

        action_clear.triggered.connect(self._clear_all_drawings)
        action_tool.triggered.connect(self._tool)
        action_alert.triggered.connect(self._show_price_alert_dialog)
        action_alert_stats.triggered.connect(self._reset_price_alert)
        mouse_color_action.triggered.connect(self.open_color_dialog)
        action_about.triggered.connect(self._show_about_dialog)
        action_settings.triggered.connect(self._set_default_setting)
        last_chart_id=self._last_chart_id
        indicator=list(filter(lambda x:x.chart_id==last_chart_id,self.indicator_manager.indicators))
        #print(indicator)
        if indicator:
            indicator_id=indicator[-1].id
            action_delete_indicator.triggered.connect(lambda: self._delete_indicator(indicator_id))
            action_delete_indicator.setEnabled(True)
        else:
            action_delete_indicator.setEnabled(False)
        
        

        # 根据状态启用/禁用菜单
        action_restore_range.setEnabled(self._saved_visible_range is not None)
        action_clear.setEnabled(
            self.symbol in self.light_chart_window.drawings)
        action_alert_stats.setEnabled(
            self.price_alert.get('enabled', False) and
            (self.price_alert.get('up_price', 0) > 0 or
             self.price_alert.get('down_price', 0) > 0)
        )

        # 组装菜单
        custom_menu.addAction(action_reload)
        custom_menu.addAction(action_show_latest_kline)
        custom_menu.addAction(action_refresh)
        custom_menu.addAction(action_restore_range)
        custom_menu.addSeparator()
        custom_menu.addAction(action_tool)
        custom_menu.addAction(action_clear)
        custom_menu.addSeparator()
        custom_menu.addMenu(indicator_menu)
        custom_menu.addAction(action_delete_indicator)
        custom_menu.addSeparator()
        custom_menu.addAction(action_alert)
        custom_menu.addAction(action_alert_stats)
        custom_menu.addSeparator()
        custom_menu.addAction(mouse_color_action)
        custom_menu.addMenu(candle_style_meun)
        custom_menu.addAction(default_candle_style_action)
        custom_menu.addSeparator()
        custom_menu.addAction(action_settings)
        custom_menu.addAction(action_about)

        # 显示菜单（向下偏移10像素）
        custom_menu.exec_(webview.mapToGlobal(pos + QPoint(0, 10)))

    def _clear_all_symbol_drawings(self, clear_all: bool = True):
        """
        清空画线
        :param clear_all: True-清空所有合约的画线；False-仅清空当前合约画线
        """
        # 1. 清理前端JS层所有绘图元素
        if self.toolbox:
            # 调用工具箱方法清空前端画布
            self.toolbox.clear_drawings()
            # 清空Python端缓存
            if clear_all:
                # 清空所有合约的绘图数据
                self.toolbox.drawings.clear()
                self.light_chart_window.drawings.clear()
            else:
                # 仅清空当前合约
                current_tag = self.light_chart_window.current_contract
                self.toolbox.drawings.pop(current_tag, None)
                self.light_chart_window.drawings.pop(current_tag, None)
        else:
            # 无工具箱实例时，直接执行JS清空画布
            current_tag = self.light_chart_window.current_contract
            self.run_script(
                f'if ({self.id}.toolBox) {self.id}.toolBox.clearDrawings()'
            )
            if clear_all:
                self.light_chart_window.drawings.clear()
            else:
                self.light_chart_window.drawings.pop(current_tag, None)

        # 2. 强制刷新前端视图，确保画线立即消失
        self.run_script(f"{self.id}.chart.applyOptions({'{'}{'}'});")

        QTimer.singleShot(100, self.light_chart_window.save_settings)

    def _set_default_setting(self):
        """重置为默认设置：清空所有画线+加载默认配置+重置样式+保存配置"""
        self._clear_all_symbol_drawings(clear_all=True)
        self.light_chart_window.load_settings(default=True)
        self.set_all_charts_crosshair_label_background()
        self.remove_toolbox()
        self.set_default_candle_style()
        self.light_chart_window.save_default_settings()
        InfoBar.success(
            title="重置成功",
            content="已恢复默认设置",
            duration=2000,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self.light_chart_window
        )

    def init_toolbox(self):
        """
        加载画线工具，无图表重载
        显示工具箱，重建实例，加载历史画线
        """
        # 已存在则直接返回，避免重复创建
        if self.toolbox is not None:
            return
        temp_tool = CustomToolBox(self)
        temp_tool.show_toolbox()
        del temp_tool
        self.toolbox = CustomToolBox(self)
        self.toolbox.load_drawings(tag=self.symbol)
        self.light_chart_window.istool = True

    def remove_toolbox(self):
        """
        删除画线工具：逻辑销毁+隐藏UI，不重载图表
        """
        if self.toolbox is None:
            return
        self.toolbox.cleanup()
        self.toolbox = None
        self.light_chart_window.istool = False

    def _tool(self):
        """
        切换画线工具开关，核心调用入口
        不重新加载图表，无缝切换
        """
        if self.toolbox is None:
            self.init_toolbox()
        else:
            self.remove_toolbox()

    def open_color_dialog(self):
        """打开颜色选择对话框"""
        dialog = ColorDialog(Qt.cyan, "选择鼠标标签颜色", self.light_chart_window)
        if dialog.exec():
            color = dialog.color
            self.light_chart_window.mouse_label_color = f'rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})'
            self.set_all_charts_crosshair_label_background()

    def open_candle_style_bull_dialog(self):
        """打开颜色选择对话框"""
        dialog = ColorDialog(Qt.cyan, "选择K线上涨颜色", self.light_chart_window)
        if dialog.exec():
            color = dialog.color
            self.light_chart_window.bull_color = f'rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})'
            self.set_candle_style()

    def open_candle_style_bear_dialog(self):
        """打开颜色选择对话框"""
        dialog = ColorDialog(Qt.cyan, "选择K线下跌颜色", self.light_chart_window)
        if dialog.exec():
            color = dialog.color
            self.light_chart_window.bear_color = f'rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})'
            self.set_candle_style()

    def _get_latest_minibt_version(self) -> str:
        """从PyPI获取miniqt最新版本号，失败则返回本地默认版本"""
        default_version = "v0.1.0"
        try:
            import requests
            import json
            # PyPI的JSON接口，直接返回包的最新信息
            url = "https://pypi.org/pypi/miniqt/json"
            # 设置超时，避免卡界面
            response = requests.get(url, timeout=5)
            response.raise_for_status()  # 捕获HTTP错误（如404、500）

            # 解析JSON获取最新版本号
            data = json.loads(response.text)
            latest_version = data["info"]["version"]
            return f"v{latest_version}"  # 格式化为 vx.x.x

        except requests.exceptions.RequestException as e:
            # 网络错误（超时、断网、接口不可用）
            print(f"获取最新版本失败（网络问题）：{e}")
            return default_version
        except (KeyError, json.JSONDecodeError) as e:
            # 接口格式变化/解析错误
            print(f"解析版本信息失败：{e}")
            return default_version

    def _show_about_dialog(self):
        """显示“关于”弹窗（适配自定义 Dialog，显示关闭按钮，可正常退出）"""
        about_dialog = Dialog("关于 MiniQt", "Mini Quant Trader",
                              parent=self.light_chart_window)
        about_dialog.setFixedSize(450, 420)

        self._clean_about_dialog_default_widgets(about_dialog)
        self._optimize_dialog_default_buttons(about_dialog)

        content_container = QWidget(about_dialog)
        main_layout = QVBoxLayout(content_container)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 20)

        title_card = CardWidget(content_container)
        title_layout = QVBoxLayout(title_card)
        title_layout.setContentsMargins(20, 16, 20, 16)

        app_title = TitleLabel("MiniBt", title_card)
        latest_version = self._get_latest_minibt_version()
        version_label = BodyLabel(f"版本: {latest_version}", title_card)

        title_layout.addWidget(app_title)
        title_layout.addWidget(version_label)
        main_layout.addWidget(title_card)

        link_card = CardWidget(content_container)
        link_layout = QVBoxLayout(link_card)
        link_layout.setContentsMargins(20, 16, 20, 16)
        link_layout.setSpacing(12)

        # GitHub 仓库
        github_link = HyperlinkLabel(QUrl("https://github.com/MiniBtMaster/miniqt"),
                                     "GitHub 仓库", link_card)
        link_layout.addWidget(github_link)

        # PyPI 仓库
        pypi_link = HyperlinkLabel(QUrl("https://pypi.org/project/miniqt/"),
                                   "PyPI 仓库", link_card)
        link_layout.addWidget(pypi_link)

        # 项目教程
        tutorial_link = HyperlinkLabel(QUrl("https://www.minibt.cn"),
                                       "项目教程", link_card)
        link_layout.addWidget(tutorial_link)

        # 联系邮箱
        email_label = BodyLabel("联系邮箱: 407841129@qq.com", link_card)
        link_layout.addWidget(email_label)

        main_layout.addWidget(link_card)

        about_dialog.vBoxLayout.insertWidget(
            1, content_container, 1, Qt.AlignTop)

        # 步骤 7：显示对话框
        about_dialog.exec_()

    def _switch_to_latest_300_kline(self,):
        """
        新增：切换到最新300根K线视图（核心功能实现）
        """
        length = len(self._kline)
        # 股票数据时间已经是正确的，不需要时区调整
        if self.is_stock:
            datetime = self._kline.datetime[[length-300, length-1]]
        else:
            # 期货数据需要时区调整
            datetime = self._kline.datetime[[length-300, length-1]] + 8*3.6e12
        start, end = datetime.tolist()
        from_ts = pd.to_datetime(start).timestamp()
        to_ts = pd.to_datetime(end).timestamp()
        self.run_script(f'''
        {self.id}.chart.timeScale().setVisibleRange({{
            from: {from_ts},
            to: {to_ts}
        }})
        ''')

    def _clean_about_dialog_default_widgets(self, dialog):
        """
        清理自定义 Dialog 的默认冗余控件（不修改原码，仅临时隐藏）
        避免默认标题/内容标签与自定义内容重叠
        """
        # 隐藏默认标题标签（windowTitleLabel 和 titleLabel）
        if hasattr(dialog, 'windowTitleLabel') and dialog.windowTitleLabel:
            dialog.windowTitleLabel.hide()
        if hasattr(dialog, 'titleLabel') and dialog.titleLabel:
            dialog.titleLabel.hide()

        # 隐藏默认内容标签（contentLabel）
        if hasattr(dialog, 'contentLabel') and dialog.contentLabel:
            dialog.contentLabel.hide()

        # 清理默认 textLayout 的间距，避免影响自定义内容布局
        if hasattr(dialog, 'textLayout'):
            dialog.textLayout.setSpacing(0)
            dialog.textLayout.setContentsMargins(0, 0, 0, 0)

    def _optimize_dialog_default_buttons(self, dialog):
        """
        优化自定义 Dialog 的默认按钮组
        """
        if hasattr(dialog, 'yesButton') and dialog.yesButton:
            dialog.yesButton.setText("关闭")
            dialog.yesButton.setIcon(FluentIcon.CLOSE.icon())
            dialog.yesButton.adjustSize()

        if hasattr(dialog, 'cancelButton') and dialog.cancelButton:
            dialog.cancelButton.hide()

        if hasattr(dialog, 'buttonGroup') and dialog.buttonGroup:
            dialog.buttonGroup.setFixedHeight(81)

    def _fit_chart(self):
        """适应窗口：将所有K线纳入可视范围，并记录之前的范围"""
        self._save_current_visible_range()
        self.fit()

    def _save_current_visible_range(self):
        """
        修复：通过异步回调获取当前可视范围
        """
        def handle_range_result(result):
            """处理JS返回的结果"""
            try:
                if result is not None and isinstance(result, str):
                    from_ts, to_ts = result.split(',')
                    self._saved_visible_range = (float(from_ts), float(to_ts))
                    self.light_chart_window.visible_range[self.symbol] = self._saved_visible_range
                else:
                    self._saved_visible_range = None
            except Exception as e:
                self._saved_visible_range = None

        get_range_script = f'''
            (function() {{
                try {{
                    const chart = {self.id};
                    if (!chart || !chart.chart) {{
                        console.error("图表实例未找到");
                        return null;
                    }}
                    
                    const timeScale = chart.chart.timeScale();
                    if (!timeScale) {{
                        console.error("timeScale未找到");
                        return null;
                    }}
                    
                    const visibleRange = timeScale.getVisibleRange();
                    if (!visibleRange) {{
                        console.error("无法获取可视范围");
                        return null;
                    }}
                    
                    console.log("可视范围:", visibleRange);
                    return visibleRange.from + "," + visibleRange.to;
                    
                }} catch (error) {{
                    console.error("获取可视范围时出错:", error);
                    return null;
                }}
            }})();
        '''
        webview = self.get_webview()
        if webview and webview.page():
            webview.page().runJavaScript(get_range_script, 0, handle_range_result)
        else:
            self._saved_visible_range = None

    def _restore_visible_range(self):
        """
        核心方法：恢复到 fit() 前保存的可视范围（右键菜单「恢复窗口」绑定此方法）
        """
        if not self._saved_visible_range:
            self._saved_visible_range = self.light_chart_window.visible_range.get(
                self.symbol, None)
        if not self._saved_visible_range:
            return
        from_ts, to_ts = self._saved_visible_range
        self.run_script(f'''
        {self.id}.chart.timeScale().setVisibleRange({{
            from: {from_ts},
            to: {to_ts}
        }})
        ''')

    def _clear_all_drawings(self):
        """清空所有画线（基于CustomToolBox的drawings数据）"""
        if not self.toolbox:
            return
        self.run_script(
            f'if ({self.id}.toolBox) {self.id}.toolBox.clearDrawings()')
        current_tag = self.light_chart_window.current_contract
        if current_tag in self.toolbox.drawings:
            del self.toolbox.drawings[current_tag]
        if current_tag in self.light_chart_window.drawings:
            del self.light_chart_window.drawings[current_tag]

    # 事件
    def _show_price_alert_dialog(self):
        """显示价格预警设置对话框 - 使用新版对话框"""
        # 创建对话框
        dialog = PriceAlertSettingDialog(
            "价格预警设置",
            "",
            self.light_chart_window,
            self.price_alert

        )
        # 连接信号
        dialog.alertSettingsChanged.connect(self._on_alert_settings_changed)
        # 显示对话框
        if dialog.exec_():
            ...

    @property
    def price_alert(self) -> dict:
        return self.light_chart_window.price_alert.get(self.contract, {})

    @price_alert.setter
    def price_alert(self, value):
        if isinstance(value, dict):
            self.light_chart_window.price_alert[self.contract] = value

    def _on_alert_settings_changed(self, settings: dict, showinfo: bool = True):
        """处理预警设置变化"""
        if not settings.get('enabled', False):
            self.price_alert = {}
            return
        if settings:
            up_price = settings.get('up_price', 0)
            down_price = settings.get('down_price', 0)
            if not any([up_price, down_price]):
                self.price_alert = {}
                return
        self.price_alert = settings
        self.set_on_new_bar_event()
        if showinfo:
            alert_type_text = {
                'both': '双向预警',
                'up': '上破预警',
                'down': '下破预警'
            }.get(settings.get('alert_type', 'both'), '双向预警')

            info_text = f"价格预警已启用 [{alert_type_text}]"

            up_price = settings.get('up_price', 0)
            down_price = settings.get('down_price', 0)

            if up_price > 0:
                info_text += f" 上破: {up_price:.4f}"
            if down_price > 0:
                info_text += f" 下破: {down_price:.4f}"

            InfoBar.info("价格预警设置成功", info_text, duration=2000,
                         position=InfoBarPosition.TOP_RIGHT, parent=self.light_chart_window)

    def set_on_new_bar_event(self):
        if not self._new_bar_event:
            self.events.new_bar += self.on_new_bar
            self._new_bar_event = True

    def on_new_bar(self, chart):
        """
        新K线生成回调：实用看盘功能
        1. 监控收盘价是否触发价格预警
        2. 打印最新收盘价（保留4位小数，便于精准监控）
        3. 触发预警时弹出提示并标记K线
        4. 自动重置预警（价格回归区间后）
        """
        if not self.price_alert:
            return
        latest_close = self._kline.iloc[-1].copy()['close']

        # 1. 检查价格预警配置
        alert_config = self.price_alert
        up_price = alert_config['up_price']
        down_price = alert_config['down_price']
        enabled = alert_config['enabled']

        # 2. 上破价格预警（未触发过且配置有效才提示）
        if up_price > 0 and latest_close >= up_price and enabled:
            self._trigger_price_alert(
                "上破预警",
                f"收盘价 {latest_close:.4f} 上破预警价格 {up_price:.4f}！"
            )
        # 3. 下破价格预警（未触发过且配置有效才提示）
        elif down_price > 0 and latest_close <= down_price and enabled:
            self._trigger_price_alert(
                "下破预警",
                f"收盘价 {latest_close:.4f} 下破预警价格 {down_price:.4f}！"
            )

    def _trigger_price_alert(self, title, content, duration=2000, position=InfoBarPosition.TOP_RIGHT):
        InfoBar.info(title, content, duration=duration,
                     position=position, parent=self.light_chart_window)

    def _reset_price_alert(self):
        self.price_alert = {}

    def on_search(self, chart, searched_string):
        """
        合约搜索回调：基于自定义 Dialog 适配，避免 contentWidget 报错
        """
        if not searched_string or not hasattr(self.light_chart_window, 'contract_dict'):
            return

        # 1. 筛选符合条件的合约（不区分大小写，模糊匹配）
        matched_contracts = []
        contract_dict = self.light_chart_window.contract_dict
        search_lower = searched_string.lower()

        for contract in contract_dict.keys():
            if search_lower in contract.lower():
                matched_contracts.append(contract)

        # 2. 无匹配结果，显示优雅提示
        if not matched_contracts:
            InfoBar.warning(
                title="无匹配结果",
                content=f"未找到包含「{searched_string}」的合约",
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.light_chart_window
            )
            return

        # 3. 单个匹配结果，直接切换合约并提示
        if len(matched_contracts) == 1:
            target_contract = matched_contracts[0]
            self._switch_contract_directly(target_contract)
            InfoBar.success(
                title="切换成功",
                content=f"已快速切换至合约「{target_contract}」",
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.light_chart_window
            )
            return

        # 4. 多个匹配结果，弹出适配自定义 Dialog 的 Fluent 风格对话框
        self._create_fluent_search_dialog(matched_contracts, searched_string)

    def _create_fluent_search_dialog(self, matched_contracts: list[str], searched_string: str):
        """
        创建适配自定义 Dialog 的 Fluent 风格对话框（核心修正：无 contentWidget）
        复用自定义 Dialog 的 vBoxLayout，清理默认文本控件，添加 QFluentWidgets 控件
        """
        dialog_title = f"找到 {len(matched_contracts)} 个匹配合约"
        self.search_dialog = Dialog(
            dialog_title, "", parent=self.light_chart_window)
        self.search_dialog.setFixedSize(450, 400)

        self._clean_custom_dialog_default_widgets()

        content_container = QWidget(self.search_dialog)
        main_layout = QVBoxLayout(content_container)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(24, 24, 24, 20)

        tip_card = CardWidget(content_container)
        tip_layout = QHBoxLayout(tip_card)
        tip_layout.setContentsMargins(16, 12, 16, 12)
        tip_label = BodyLabel(f"关键词：「{searched_string}」，可二次筛选缩小范围", tip_card)
        tip_layout.addWidget(tip_label, 0, Qt.AlignLeft)
        main_layout.addWidget(tip_card)

        self.filter_search = SearchLineEdit(content_container)
        self.filter_search.setPlaceholderText("再次筛选合约（模糊匹配）...")
        self.filter_search.setClearButtonEnabled(True)
        self.filter_search.textChanged.connect(
            lambda text: self._filter_contract_list_fluent(
                text, matched_contracts)
        )
        main_layout.addWidget(self.filter_search)

        scroll_area = ScrollArea(content_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")

        self.contract_list_fluent = ListWidget(scroll_area)
        self.contract_list_fluent.addItems(matched_contracts)
        self.contract_list_fluent.setSelectionMode(ListWidget.SingleSelection)
        self.contract_list_fluent.setCurrentRow(0)
        self.contract_list_fluent.itemDoubleClicked.connect(
            lambda item: self._confirm_contract_selection_fluent(item.text())
        )
        scroll_area.setWidget(self.contract_list_fluent)

        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(scroll_area, 1)

        btn_layout = QHBoxLayout()
        cancel_btn = PushButton("取消", content_container,
                                FluentIcon.CLOSE.icon())
        cancel_btn.clicked.connect(self.search_dialog.reject)
        confirm_btn = PrimaryPushButton(
            "确认选择", content_container, FluentIcon.ACCEPT.icon())
        confirm_btn.clicked.connect(self._confirm_contract_selection_fluent)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)
        btn_layout.setSpacing(12)
        main_layout.addLayout(btn_layout)

        self.search_dialog.vBoxLayout.insertWidget(
            1, content_container, 1, Qt.AlignTop)
        self.search_dialog.buttonGroup.hide()

        self.search_dialog.exec_()

    def _clean_custom_dialog_default_widgets(self):
        """
        清理自定义 Dialog 的默认控件（不修改原码，仅临时隐藏/移除）
        避免默认标题/内容标签与 QFluentWidgets 控件冲突
        """
        dialog = self.search_dialog
        if hasattr(dialog, 'windowTitleLabel') and dialog.windowTitleLabel:
            dialog.windowTitleLabel.hide()
        if hasattr(dialog, 'titleLabel') and dialog.titleLabel:
            dialog.titleLabel.hide()

        if hasattr(dialog, 'contentLabel') and dialog.contentLabel:
            dialog.contentLabel.hide()

        if hasattr(dialog, 'textLayout'):
            dialog.textLayout.setSpacing(0)
            dialog.textLayout.setContentsMargins(0, 0, 0, 0)

    def _filter_contract_list_fluent(self, filter_text: str, original_contracts: list[str]):
        """实时二次筛选合约列表"""
        self.contract_list_fluent.clear()
        if not filter_text:
            self.contract_list_fluent.addItems(original_contracts)
            self.contract_list_fluent.setCurrentRow(0)
            return

        filter_lower = filter_text.lower()
        filtered_contracts = [
            c for c in original_contracts if filter_lower in c.lower()
        ]
        self.contract_list_fluent.addItems(filtered_contracts)
        if filtered_contracts:
            self.contract_list_fluent.setCurrentRow(0)

    def _confirm_contract_selection_fluent(self, contract_text: str = None):
        """确认合约选择"""
        target_contract = None
        if contract_text:
            target_contract = contract_text
        else:
            current_item = self.contract_list_fluent.currentItem()
            if not current_item:
                InfoBar.warning(
                    title="选择错误",
                    content="请先选择一个合约再确认！",
                    duration=1500,
                    position=InfoBarPosition.TOP_RIGHT,
                    parent=self.search_dialog
                )
                return
            target_contract = current_item.text()

        self._switch_contract_directly(target_contract)
        self.search_dialog.accept()
        InfoBar.success(
            title="切换成功",
            content=f"已切换至合约「{target_contract}」，图表数据正在更新...",
            duration=2000,
            position=InfoBarPosition.TOP_RIGHT,
            parent=self.light_chart_window
        )

    def _switch_contract_directly(self, contract: str):
        """直接切换目标合约"""
        light_window = self.light_chart_window
        if contract not in light_window.contract_dict:
            InfoBar.error(
                title="切换失败",
                content=f"合约「{contract}」未配置对应的策略！",
                duration=2000,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self.light_chart_window
            )
            return
        light_window.current_contract = contract
        strategy = light_window.strategies[light_window.contract_dict[contract]]
        light_window.replace_chart(strategy)

    def set_crosshair_label_background(self, chart: AbstractChart, bg: str = 'rgba(30, 30, 30, 0.9)'):
        """
        设置十字线移动时X时间轴和Y价格轴标签的背景色
        :param dark: 是否为深色模式，默认使用全局主题设置
        """

        # 生成JS脚本
        script = f'''
        try {{
            const chart = {chart.id}.chart;
            if (chart && chart.applyOptions) {{
                chart.applyOptions({{
                    crosshair: {{
                        vertLine: {{
                            labelBackgroundColor: "{bg}"
                        }},
                        horzLine: {{
                            labelBackgroundColor: "{bg}"
                        }}
                    }}
                }});
            }}
        }} catch (e) {{
            console.error("设置十字线标签背景色失败:", e);
        }}
        '''
        chart.run_script(script)

    def set_all_charts_crosshair_label_background(self):
        """
        为所有图表（主图+副图）设置十字线标签背景色
        :param dark: 是否为深色模式，默认使用全局主题设置
        """
        bg = self.light_chart_window.mouse_label_color
        if bg:
            charts = [self, *self.subcharts.values()]
            for chart in charts:
                self.set_crosshair_label_background(chart, bg)

    def cleanup(self):
        """切换合约时的彻底清理逻辑（核心）"""
        # === 取消 StockApi 订阅 ===
        if getattr(self, 'is_stock', False) and hasattr(self, 'main_window') and \
           hasattr(self.main_window, 'stock_api') and self.main_window.stock_api:
            try:
                self.main_window.stock_api.unsubscribe(self.symbol, self.cycle)
            except Exception as e:
                print(f"[chart] 取消订阅失败: {e}")
        
        self.stop_chart_updater()
        # if hasattr(self, 'qtimer') and self.qtimer:
        #     try:
        #         self.qtimer.stop()
        #     except Exception as e:
        #         print(f"停止定时器时出错: {e}")
        #     finally:
        #         self.qtimer = None
        event_names = [
            f'search{self.id}',
            f'save_drawings{self.id}',
            f'click{self.id}',
            f'range_change{self.id}',
            f'new_bar{self.id}'
        ]

        for event_name in event_names:
            try:
                if hasattr(self.win, 'handlers') and event_name in self.win.handlers:
                    del self.win.handlers[event_name]
            except Exception as e:
                print(f"清理事件监听器异常:{e}")
        if hasattr(self.chart, 'events'):
            try:
                for event_name in ['click', 'range_change', 'search', 'new_bar']:
                    if hasattr(self.chart.events, event_name):
                        getattr(self.chart.events, event_name)._callable = []
                        setattr(self.chart.events, event_name, None)
                self.chart.events = None
            except Exception as e:
                print(f"清理 Emitter 事件异常:{e}")

        webview = self.get_webview()
        if webview:
            cleanup_js = f'''
            try {{
                // 1. 销毁图表实例
                if (typeof {self.id} !== 'undefined' && {self.id}.chart) {{
                    // 解绑所有事件
                    {self.id}.chart.unsubscribeClick();
                    {self.id}.chart.unsubscribeCrosshairMove();
                    {self.id}.chart.timeScale().unsubscribeVisibleLogicalRangeChange();
                    
                    // 移除所有系列和子图表
                    while ({self.id}.chart.seriesCount() > 0) {{
                        {self.id}.chart.removeSeries({self.id}.chart.seriesByIndex(0));
                    }}
                    
                    // 销毁图表
                    {self.id}.chart.destroy();
                    {self.id}.chart = null;
                }}
                
                // 2. 销毁工具箱
                if ({self.id}.toolBox) {{
                    {self.id}.toolBox = null;
                }}
                
                // 3. 清空整个图表对象
                {self.id} = null;
                
                // 4. 强制垃圾回收
                if (window.gc) {{ window.gc(); }}
            }} catch (e) {{
                console.error("JS层清理失败:", e);
            }}
            '''
            webview.page().runJavaScript(cleanup_js, 0)
            try:
                # 断开所有信号连接
                webview.page().loadFinished.disconnect(self._on_webview_loaded)
                webview.customContextMenuRequested.disconnect(
                    self._on_webview_custom_context_menu)

                # 停止页面加载
                webview.stop()
                webview.setUrl(QUrl("about:blank"))  # 清空页面

                # 清理页面
                page = webview.page()
                if page:
                    # page.history().clear()
                    page.deleteLater()

                # 设置空页面
                webview.setPage(None)

            except Exception as e:
                print(f"清理 WebView 时出错: {e}")
        for name, subchart in list(self.subcharts.items()):
            try:
                subchart_id = subchart.id
                if hasattr(self.win, 'handlers'):
                    keys_to_delete = []
                    for key in list(self.win.handlers.keys()):
                        if subchart_id in key:
                            keys_to_delete.append(key)
                    for key in keys_to_delete:
                        del self.win.handlers[key]
            except Exception as e:
                print(f"清理子图表 {name} 时出错: {e}")

        self.subcharts.clear()
        self.chart_indicators.clear()
        self.signal_indicators.clear()
        self._signal_markers.clear()
        self._kline = None
        self.toolbox = None
        self.light_chart_window = None
        # 清理图表引用，防止更新时出错
        self.chart = None
    
    def _setup_cursor_monitoring(self):
        """设置光标监测（简化版，直接监听文档鼠标事件）"""
        try:
            if hasattr(self, 'chart') and self.chart is not None:
                chart_id_short = self.id
                
                # 注入光标监测脚本
                inject_script = f"""
                (function() {{
                    console.log('开始设置光标监测');
                    
                    // 检查 window.callbackFunction 是否存在
                    if (typeof window.callbackFunction !== 'function') {{
                        console.warn('window.callbackFunction 不存在，创建默认函数');
                        window.callbackFunction = function(msg) {{
                            console.log('默认回调函数被调用:', msg);
                        }};
                    }}
                    
                    // 存储当前光标状态
                    var currentCursorState = 'default';
                    
                    // 鼠标移动事件处理
                    document.addEventListener('mousemove', function(e) {{
                        var target = e.target;
                        var isOverIndicator = false;
                        
                        // 检查目标元素或其父元素是否为指标标签
                        while (target) {{
                            if (target.classList) {{
                                // 检查常见的指标标签类名
                                if (
                                    target.classList.contains('legend-row') ||
                                    target.classList.contains('tv-legend__item') ||
                                    target.classList.contains('row') ||
                                    target.classList.contains('lwc-legend-item') ||
                                    target.classList.contains('indicator-label') ||
                                    target.classList.contains('legend-item')
                                ) {{
                                    isOverIndicator = true;
                                    break;
                                }}
                                
                                // 检查元素文本是否包含指标名称
                                var text = target.textContent || '';
                                if (text.includes('pta_ao') || text.includes('SMA') || text.includes('MACD') || text.includes('RSI') || text.includes('KDJ')) {{
                                    isOverIndicator = true;
                                    break;
                                }}
                            }}
                            target = target.parentElement;
                        }}
                        
                        // 根据鼠标位置更新光标状态
                        if (isOverIndicator && currentCursorState !== 'ibeam') {{
                            console.log('鼠标悬停在指标标签上');
                            document.body.style.cursor = 'text';
                            document.body.style.setProperty('cursor', 'text', 'important');
                            currentCursorState = 'ibeam';
                            // 通知 Python
                            window.callbackFunction('cursor_change_{chart_id_short}_~_ibeam');
                        }} else if (!isOverIndicator && currentCursorState !== 'default') {{
                            console.log('鼠标离开指标标签');
                            document.body.style.cursor = '';
                            document.body.style.setProperty('cursor', '', '');
                            currentCursorState = 'default';
                            // 通知 Python
                            window.callbackFunction('cursor_change_{chart_id_short}_~_arrow');
                        }}
                    }});
                    
                    console.log('光标监测已设置');
                }})();
                """
                
                self.get_webview().page().runJavaScript(inject_script, 0)
                    #lambda res: print("✅ 已设置光标监测"))
                
                # 注册光标变化事件处理器
                self._register_cursor_handler()
            # else:
            #     print("❌ 无法设置光标监测：chart 不存在")
        except Exception as e:
            print(f"❌ 设置光标监测时出错: {e}")
    
    def _setup_legend_click_events(self):
        """为图例项添加点击事件"""
        try:
            if hasattr(self, 'chart') and self.chart is not None:
                chart_id_short = self.id
                chart_global = self.chart.id
                
                # 注入图例点击事件脚本
                inject_script = f"""
                (function() {{
                    console.log('开始设置图例点击事件');
                    
                    // 检查 window.callbackFunction 是否存在
                    if (typeof window.callbackFunction !== 'function') {{
                        console.warn('window.callbackFunction 不存在，创建默认函数');
                        window.callbackFunction = function(msg) {{
                            console.log('默认回调函数被调用:', msg);
                        }};
                    }}
                    
                    // 为图例项添加点击事件
                    function addLegendClickListeners() {{
                        console.log('尝试添加图例点击监听器');
                        if (!{chart_global}.legend) {{
                            console.log('图例不存在，延迟尝试');
                            setTimeout(addLegendClickListeners, 100);
                            return;
                        }}
                        
                        console.log('图例存在，开始添加点击监听器');
                        // 遍历所有图例项
                        {chart_global}.legend._lines.forEach((legendItem, index) => {{
                            if (legendItem.row && !legendItem.row._clickBound) {{
                                console.log('为图例项添加点击监听器:', legendItem.series.name || `series_${{index}}`);
                                legendItem.row._clickBound = true;
                                legendItem.row.addEventListener('click', function() {{
                                    const seriesName = legendItem.series.name || `series_${{index}}`;
                                    console.log('图例项被点击:', seriesName);
                                    window.callbackFunction('legend_click_{chart_id_short}_~_${{seriesName}}');
                                }});
                            }}
                        }});
                        
                        // 使用MutationObserver监听新添加的图例项
                        const observer = new MutationObserver(function(mutations) {{
                            mutations.forEach(function(mutation) {{
                                mutation.addedNodes.forEach(function(node) {{
                                    if (node.classList && node.classList.contains('legend-row')) {{
                                        // 延迟一下，确保legendItem已经关联到DOM元素
                                        setTimeout(function() {{
                                            {chart_global}.legend._lines.forEach((legendItem) => {{
                                                if (legendItem.row === node && !legendItem.row._clickBound) {{
                                                    console.log('为新图例项添加点击监听器:', legendItem.series.name || 'unknown');
                                                    legendItem.row._clickBound = true;
                                                    legendItem.row.addEventListener('click', function() {{
                                                        const seriesName = legendItem.series.name || 'unknown';
                                                        console.log('新图例项被点击:', seriesName);
                                                        window.callbackFunction('legend_click_{chart_id_short}_~_${{seriesName}}');
                                                    }});
                                                }}
                                            }});
                                        }}, 100);
                                    }}
                                }});
                            }});
                        }});
                        
                        if ({chart_global}.legend.div) {{
                            console.log('开始观察图例容器的变化');
                            observer.observe({chart_global}.legend.div, {{ childList: true, subtree: true }});
                        }}
                    }}
                    
                    addLegendClickListeners();
                }})();
                """
                
                self.get_webview().page().runJavaScript(inject_script, 0)#,
                    #lambda res: print("✅ 已设置图例点击事件"))
                
                # 注册图例点击事件处理器
                self._register_legend_click_handler()
            # else:
            #     print("❌ 无法设置图例点击事件：chart 不存在")
        except Exception as e:
            print(f"❌ 设置图例点击事件时出错: {e}")
    
    def _register_legend_click_handler(self):
        """注册图例点击事件的 Python 回调"""
        try:
            if hasattr(self, 'chart') and self.chart is not None:
                if hasattr(self.chart, 'win') and self.chart.win is not None:
                    if hasattr(self.chart.win, 'handlers') and self.chart.win.handlers is not None:
                        handler_name = f'legend_click_{self.id}'
                        def handler(chart, series_name):
                            self.on_legend_click(chart, series_name)
                        self.chart.win.handlers[handler_name] = handler
                        # print(f"✅ 已注册图例点击处理器: {handler_name}")
                    # else:
                        #     print("❌ 无法注册图例点击处理器：chart.win.handlers 不存在")
                # else:
                    #     print("❌ 无法注册图例点击处理器：chart.win 不存在")
            # else:
                #     print("❌ 无法注册图例点击处理器：chart 不存在")
        except Exception as e:
            print(f"❌ 注册图例点击处理器时出错: {str(e)}")
    
    def on_legend_click(self, chart, series_name):
        """图例点击事件处理"""
        # print(f"图例项被点击: {series_name}")
        # 在这里添加你的业务逻辑
        # 例如，打开指标设置窗口，或执行其他操作

    def smart_pan(self, direction='left'):
        pure_id = self.id.replace(
            'window.', '') if 'window.' in self.id else self.id
        direction_map = {
            'left': {'scroll_delta': 15, 'range_multiplier': -0.1},
            'right': {'scroll_delta': -15, 'range_multiplier': 0.1}
        }
        if direction not in direction_map:
            return
        delta_config = direction_map[direction]

        js_script = f'''
            (function() {{
                try {{
                    const chart = window['{pure_id}'].chart;
                    if (!chart) return;
                    const timeScale = chart.timeScale();
                    let currentState = {{}};

                    try {{ currentState.scrollPos = timeScale.scrollPosition(); }} catch(e) {{}}
                    try {{
                        const range = timeScale.getVisibleRange();
                        if (range) currentState.visibleRange = {{from: range.from, to: range.to, width: range.to - range.from}};
                    }} catch(e) {{}}

                    if (currentState.scrollPos !== undefined) {{
                        const newPos = currentState.scrollPos + {delta_config['scroll_delta']};
                        timeScale.scrollToPosition(newPos, false);
                    }} else if (currentState.visibleRange) {{
                        const range = currentState.visibleRange;
                        const shift = range.width * {delta_config['range_multiplier']};
                        timeScale.setVisibleRange({{from: range.from + shift, to: range.to + shift}});
                    }} else {{
                        try {{
                            const logicalRange = timeScale.getVisibleLogicalRange();
                            if (logicalRange) {{
                                const barCount = logicalRange.to - logicalRange.from;
                                const shiftBars = Math.max(1, Math.ceil(barCount * 0.1));
                                const directionMultiplier = '{direction}' === 'left' ? 1 : -1;
                                timeScale.setVisibleLogicalRange({{
                                    from: logicalRange.from + shiftBars * directionMultiplier,
                                    to: logicalRange.to + shiftBars * directionMultiplier
                                }});
                            }}
                        }} catch(e) {{}}
                    }}
                }} catch(e) {{}}
            }})();
        '''
        self.get_webview().page().runJavaScript(js_script, 0)

    def pan_left_final(self):
        pure_id = self.id.replace(
            'window.', '') if 'window.' in self.id else self.id
        js_script = f'''
            (function() {{
                try {{
                    const chart = window['{pure_id}'].chart;
                    const timeScale = chart.timeScale();
                    const visibleRange = timeScale.getVisibleRange();
                    if (visibleRange) {{
                        const viewWidth = visibleRange.to - visibleRange.from;
                        const timeShift = viewWidth * 0.1;
                        timeScale.setVisibleRange({{
                            from: visibleRange.from - timeShift,
                            to: visibleRange.to - timeShift
                        }});
                    }}
                }} catch(e) {{}}
            }})();
        '''
        self.get_webview().page().runJavaScript(js_script, 0)

    def pan_right_final(self):
        pure_id = self.id.replace(
            'window.', '') if 'window.' in self.id else self.id
        js_script = f'''
            (function() {{
                try {{
                    const chart = window['{pure_id}'].chart;
                    const timeScale = chart.timeScale();
                    const visibleRange = timeScale.getVisibleRange();
                    if (visibleRange) {{
                        const viewWidth = visibleRange.to - visibleRange.from;
                        const timeShift = viewWidth * 0.1;
                        timeScale.setVisibleRange({{
                            from: visibleRange.from + timeShift,
                            to: visibleRange.to + timeShift
                        }});
                    }}
                }} catch(e) {{}}
            }})();
        '''
        self.get_webview().page().runJavaScript(js_script, 0)

    def pan_with_fixed_bars(self, direction='left'):
        pure_id = self.id.replace(
            'window.', '') if 'window.' in self.id else self.id
        js_script = f'''
            (function() {{
                try {{
                    const chart = window['{pure_id}'].chart;
                    const timeScale = chart.timeScale();
                    const logicalRange = timeScale.getVisibleLogicalRange();
                    if (!logicalRange) return;
                    const currentBars = logicalRange.to - logicalRange.from;
                    const shiftBars = Math.max(1, Math.ceil(currentBars * 0.1));
                    let newFrom, newTo;
                    if ('{direction}' === 'left') {{
                        newFrom = logicalRange.from + shiftBars;
                        newTo = logicalRange.to + shiftBars;
                    }} else {{
                        newFrom = Math.max(0, logicalRange.from - shiftBars);
                        newTo = logicalRange.to - shiftBars;
                    }}
                    if (newTo <= newFrom) newTo = newFrom + 1;
                    timeScale.setVisibleLogicalRange({{from: newFrom, to: newTo}});
                }} catch(e) {{}}
            }})();
        '''
        self.get_webview().page().runJavaScript(js_script, 0)

    def pan(self, direction='left', mode='time'):
        if direction not in ['left', 'right']:
            return
        if mode == 'time':
            self.pan_left_final() if direction == 'left' else self.pan_right_final()
        elif mode == 'bars':
            self.pan_with_fixed_bars(direction)
        elif mode == 'smart':
            self.smart_pan(direction)

    def pan_left(self):
        self.pan('right', 'smart')

    def pan_right(self):
        self.pan('left', 'smart')

    def zoom_in_wheel(self):
        pure_id = self.id.replace(
            'window.', '') if 'window.' in self.id else self.id
        js_script = f'''
            (function() {{
                try {{
                    const chartInstance = window['{pure_id}'];
                    if (!chartInstance || !chartInstance.chart) return;
                    const chart = chartInstance.chart;
                    const chartElement = chart.chartElement();
                    if (!chartElement) return;
                    const rect = chartElement.getBoundingClientRect();
                    const centerX = rect.left + rect.width / 2;
                    const centerY = rect.top + rect.height / 2;
                    const wheelEvent = new WheelEvent('wheel', {{
                        deltaX: 0, deltaY: -50, deltaMode: WheelEvent.DOM_DELTA_PIXEL,
                        clientX: centerX, clientY: centerY, view: window, bubbles: true, cancelable: true
                    }});
                    chartElement.dispatchEvent(wheelEvent);
                }} catch(e) {{}}
            }})();
        '''
        self.get_webview().page().runJavaScript(js_script, 0)

    def zoom_out_wheel(self):
        pure_id = self.id.replace(
            'window.', '') if 'window.' in self.id else self.id
        js_script = f'''
            (function() {{
                try {{
                    const chartInstance = window['{pure_id}'];
                    if (!chartInstance || !chartInstance.chart) return;
                    const chart = chartInstance.chart;
                    const chartElement = chart.chartElement();
                    if (!chartElement) return;
                    const rect = chartElement.getBoundingClientRect();
                    const centerX = rect.left + rect.width / 2;
                    const centerY = rect.top + rect.height / 2;
                    const wheelEvent = new WheelEvent('wheel', {{
                        deltaX: 0, deltaY: 50, deltaMode: WheelEvent.DOM_DELTA_PIXEL,
                        clientX: centerX, clientY: centerY, view: window, bubbles: true, cancelable: true
                    }});
                    chartElement.dispatchEvent(wheelEvent);
                }} catch(e) {{}}
            }})();
        '''
        self.get_webview().page().runJavaScript(js_script, 0)

    def zoom_smart(self, direction='in'):
        pure_id = self.id.replace(
            'window.', '') if 'window.' in self.id else self.id
        delta_config = {'in': {'deltaY': -80, 'factor': 0.9},
                        'out': {'deltaY': 80, 'factor': 1.1}}
        if direction not in delta_config:
            return
        config = delta_config[direction]

        js_script = f'''
            (function() {{
                try {{
                    const chartInstance = window['{pure_id}'];
                    if (!chartInstance || !chartInstance.chart) return;
                    const chart = chartInstance.chart;
                    const chartElement = chart.chartElement();
                    if (!chartElement) return;

                    try {{
                        const rect = chartElement.getBoundingClientRect();
                        const centerX = rect.left + rect.width / 2;
                        const centerY = rect.top + rect.height / 2;
                        const wheelEvent = new WheelEvent('wheel', {{
                            deltaX: 0, deltaY: {config['deltaY']}, deltaMode: WheelEvent.DOM_DELTA_PIXEL,
                            clientX: centerX, clientY: centerY, view: window, bubbles: true, cancelable: true
                        }});
                        if (chartElement.dispatchEvent(wheelEvent)) return;
                    }} catch(e) {{}}

                    try {{
                        const timeScale = chart.timeScale();
                        const range = timeScale.getVisibleRange();
                        if (range) {{
                            const currentWidth = range.to - range.from;
                            const newWidth = currentWidth * {config['factor']};
                            const center = (range.from + range.to) / 2;
                            timeScale.setVisibleRange({{from: center - newWidth/2, to: center + newWidth/2}});
                        }}
                    }} catch(e) {{}}
                }} catch(e) {{}}
            }})();
        '''
        self.get_webview().page().runJavaScript(js_script, 0)

    def zoom_at_position(self, direction='in', x_percent=0.5, y_percent=0.5):
        pure_id = self.id.replace(
            'window.', '') if 'window.' in self.id else self.id
        delta_map = {'in': -100, 'out': 100}
        if direction not in delta_map:
            return
        delta_y = delta_map[direction]

        js_script = f'''
            (function() {{
                try {{
                    const chartInstance = window['{pure_id}'];
                    if (!chartInstance || !chartInstance.chart) return;
                    const chart = chartInstance.chart;
                    const chartElement = chart.chartElement();
                    if (!chartElement) return;
                    const rect = chartElement.getBoundingClientRect();
                    const posX = rect.left + rect.width * {x_percent};
                    const posY = rect.top + rect.height * {y_percent};
                    const wheelEvent = new WheelEvent('wheel', {{
                        deltaX: 0, deltaY: {delta_y}, deltaMode: WheelEvent.DOM_DELTA_PIXEL,
                        clientX: posX, clientY: posY, view: window, bubbles: true, cancelable: true
                    }});
                    chartElement.dispatchEvent(wheelEvent);
                }} catch(e) {{}}
            }})();
        '''
        self.get_webview().page().runJavaScript(js_script, 0)

    def zoom(self, direction='in', method='wheel', position=None):
        if direction not in ['in', 'out']:
            return
        if method == 'wheel':
            self.zoom_in_wheel() if direction == 'in' else self.zoom_out_wheel()
        elif method == 'smart':
            self.zoom_smart(direction)
        elif method == 'position':
            x, y = position if position else (0.5, 0.5)
            self.zoom_at_position(direction, x, y)

    def zoom_in(self):
        self.zoom('in', 'smart')

    def zoom_out(self):
        self.zoom('out', 'smart')

    def center_on_latest_smart(self):
        pure_id = self.id.replace(
            'window.', '') if 'window.' in self.id else self.id
        js_script = f'''
            (function() {{
                try {{
                    const chartInstance = window['{pure_id}'];
                    if (!chartInstance || !chartInstance.chart) return;
                    const chart = chartInstance.chart;
                    const timeScale = chart.timeScale();
                    const currentRange = timeScale.getVisibleRange();
                    if (!currentRange) {{
                        timeScale.fitContent();
                        return;
                    }}
                    const currentWidth = currentRange.to - currentRange.from;
                    const series = chartInstance.series;
                    let latestTime = 0;
                    if (series && series.data) {{
                        const allData = series.data();
                        if (allData && allData.length > 0) latestTime = allData[allData.length-1].time;
                    }}
                    if (latestTime > 0) {{
                        timeScale.setVisibleRange({{from: latestTime - currentWidth, to: latestTime}});
                    }} else {{
                        timeScale.fitContent();
                    }}
                }} catch(e) {{}}
            }})();
        '''
        self.get_webview().page().runJavaScript(js_script, 0)

    def center_on_latest(self):
        return self.center_on_latest_smart()
    
    def get_webview(self)->Optional[QWebEngineView]:
        """获取webview实例"""
        return self.chart.get_webview()
    
    def run_script(self, script, run_last=False):
        """运行JavaScript脚本"""
        return self.chart.run_script(script, run_last)
    
    def set(self, df, keep_drawings=False):
        """设置图表数据"""
        return self.chart.set(df, keep_drawings)
    
    def update(self, series, _from_tick=False):
        """更新图表数据"""
        return self.chart.update(series, _from_tick)
    
    def update_from_tick(self, series):
        """从Tick更新图表数据"""
        return self.chart.update_from_tick(series)
    
    def fit(self):
        """调整图表以适应数据"""
        return self.chart.fit()
    
    def create_line(self, name='', color='rgba(214, 237, 255, 0.6)', style='solid', width=2, price_line=True, price_label=True, price_scale_id=None):
        """创建线条"""
        return self.chart.create_line(name, color, style, width, price_line, price_label, price_scale_id)
    
    def create_subchart(self, position='left', width=0.5, height=0.5, sync=None, scale_candles_only=False, sync_crosshairs_only=False, toolbox=False):
        """创建子图表"""
        return self.chart.create_subchart(position, width, height, sync, scale_candles_only, sync_crosshairs_only, toolbox)
    
    def time_scale(self, right_offset=0, min_bar_spacing=0.5, visible=True, time_visible=True, seconds_visible=False, border_visible=True, border_color=None):
        """设置时间轴"""
        return self.chart.time_scale(right_offset, min_bar_spacing, visible, time_visible, seconds_visible, border_visible, border_color)
    
    def layout(self, background_color='#000000', text_color=None, font_size=None, font_family=None):
        """设置布局"""
        return self.chart.layout(background_color, text_color, font_size, font_family)
    
    def grid(self, vert_enabled=True, horz_enabled=True, color='rgba(29, 30, 38, 5)', style='solid'):
        """设置网格"""
        return self.chart.grid(vert_enabled, horz_enabled, color, style)
    
    def crosshair(self, mode='normal', vert_visible=True, vert_width=1, vert_color=None, vert_style='large_dashed', vert_label_background_color='rgb(46, 46, 46)', horz_visible=True, horz_width=1, horz_color=None, horz_style='large_dashed', horz_label_background_color='rgb(55, 55, 55)'):
        """设置十字光标"""
        return self.chart.crosshair(mode, vert_visible, vert_width, vert_color, vert_style, vert_label_background_color, horz_visible, horz_width, horz_color, horz_style, horz_label_background_color)
    
    def candle_style(self, up_color='rgba(39, 157, 130, 100)', down_color='rgba(200, 97, 100, 100)', wick_visible=True, border_visible=True, border_up_color='', border_down_color='', wick_up_color='', wick_down_color=''):
        """设置蜡烛图样式"""
        return self.chart.candle_style(up_color, down_color, wick_visible, border_visible, border_up_color, border_down_color, wick_up_color, wick_down_color)
    
    def volume_config(self, scale_margin_top=0.8, scale_margin_bottom=0.0, up_color='rgba(83,141,131,0.8)', down_color='rgba(200,127,130,0.8)'):
        """设置成交量配置"""
        return self.chart.volume_config(scale_margin_top, scale_margin_bottom, up_color, down_color)
    
    def legend(self, visible=False, ohlc=True, percent=True, lines=True, color='rgb(191, 195, 203)', font_size=11, font_family='Monaco', text='', color_based_on_candle=False):
        """设置图例"""
        return self.chart.legend(visible, ohlc, percent, lines, color, font_size, font_family, text, color_based_on_candle)
    
    def watermark(self, text, font_size=44, color='rgba(180, 180, 200, 0.5)'):
        """添加水印"""
        return self.chart.watermark(text, font_size, color)
    
    def spinner(self, visible):
        """设置加载动画"""
        return self.chart.spinner(visible)
    
    def hotkey(self, modifier_key, keys, func):
        """设置热键"""
        return self.chart.hotkey(modifier_key, keys, func)
    
    def screenshot(self):
        """获取截图"""
        return self.chart.screenshot()
    
    def set_visible_range(self, start_time, end_time):
        """设置可见范围"""
        return self.chart.set_visible_range(start_time, end_time)
    
    def resize(self, width=None, height=None):
        """调整图表大小"""
        return self.chart.resize(width, height)
    
    def lines(self):
        """获取所有线条"""
        return self.chart.lines()
    
    def precision(self, precision):
        """设置精度"""
        return self.chart.precision(precision)
    
    def price_line(self, label_visible=True, line_visible=True, title=''):
        """设置价格线"""
        return self.chart.price_line(label_visible, line_visible, title)
    
    def clear_markers(self):
        """清除标记"""
        return self.chart.clear_markers()
    
    def horizontal_line(self, price, color='rgb(122, 146, 202)', width=2, style='solid', text='', axis_label_visible=True, func=None):
        """创建水平线"""
        return self.chart.horizontal_line(price, color, width, style, text, axis_label_visible, func)
    
    def remove_marker(self, marker_id):
        """移除标记"""
        return self.chart.remove_marker(marker_id)
    
    def marker(self, time=None, position='below', shape='arrow_up', color='#2196F3', text=''):
        """创建标记"""
        return self.chart.marker(time, position, shape, color, text)
    
    def marker_list(self, markers):
        """创建多个标记"""
        return self.chart.marker_list(markers)
    
    def hide_data(self):
        """隐藏数据"""
        return self.chart.hide_data()
    
    def show_data(self):
        """显示数据"""
        return self.chart.show_data()
    
    @property
    def id(self):
        """获取图表ID"""
        return self.chart.id
    
    @property
    def events(self):
        """获取图表事件"""
        return self.chart.events
    
    @property
    def win(self):
        """获取窗口实例"""
        return self.chart.win


def main(strategies, period_milliseconds: int = 1000):
    app = QApplication(sys.argv)
    w = MainWindow(strategies, period_milliseconds)
    w.show()
    app.exec()
