# coding:utf-8
from __future__ import annotations
import traceback
from PyQt6.QtCore import Qt, QThread, QTimer, QEvent, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidgetItem, QSizePolicy, QAbstractItemView

from qfluentwidgets import (SegmentedWidget, TableWidget,
                            SingleDirectionScrollArea, RoundMenu, Action, FluentIcon)

from ..common.config import cfg
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from .main_window import MainWindow, TqApi
    import pandas as pd


class UpdateTableDataThread(QThread):
    """更新表格数据的线程"""
    update_ui_signal = pyqtSignal(object)

    def __init__(self, parent, symbol_info=None):
        super().__init__()
        self.mqi: MarketQuoteInterface = parent
        self.symbol_info: Optional["pd.DataFrame"] = symbol_info
        self.update_ui_signal.connect(self.mqi.update_table_ui)

    def run(self):
        # print("UpdateTableDataThread 开始运行")
        try:
            # print("准备更新表格数据")
            self.update_ui_signal.emit(self.symbol_info)
            # print("已发送更新UI信号")
        except Exception as e:
            traceback.print_exc()
            print("【MarketQuoteInterface】查询合约信息失败：", e)
            print("异常堆栈：", traceback.format_exc())
        # print("UpdateTableDataThread 运行结束")


class MarketQuoteInterface(QWidget):
    """行情报价界面"""

    def __init__(self, parent: 'MainWindow' = None):
        super().__init__(parent)
        self.main_window: 'MainWindow' = parent
        self.setObjectName('marketQuoteInterface')
        self.update_thread = None
        self.is_update_exchange_segments = False
        self.exchanges: dict[str, dict[str, 'pd.DataFrame']] = {}
        # 记录哪些类型和交易所已经保存到数据库
        self.saved_to_db: dict[str, set] = {}  # {ins_class: set(exchange_id, ...)}
        # 内存缓存：缓存已加载的数据表，避免频繁从数据库读取
        self.cached_symbol_info: dict[str, dict[str, 'pd.DataFrame']] = {}  # {ins_class: {exchange: DataFrame}}
        self.__initWidget()

        # 尝试从数据库加载数据
        self.load_data_from_db()

    def on_cont_quotes_updated(self):
        """主力合约列表更新完成后的处理"""
        if not self.is_update_exchange_segments:
            self.update_exchange_segments()
            self.is_update_exchange_segments = True

    def update_table_ui(self, symbol_info):
        """在主线程中更新表格 UI"""
        # print("开始更新表格 UI")
        # print(f"数据是否为空: {symbol_info is None or symbol_info.empty}")

        # 禁用排序，避免行数设置问题
        self.tableWidget.setSortingEnabled(False)

        if symbol_info is not None and not symbol_info.empty:
            # print(f"数据行数: {len(symbol_info)}")
            # print(f"数据列名: {symbol_info.columns.tolist()}")
            rename_map = {
                'instrument_id': '代码',
                'instrument_name': '名称',
                'ins_class': '类型',
                'exchange_id': '交易所',
                'product_id': '品种',
                'price_tick': '最小跳价',
                'volume_multiple': '合约乘数',
                'open_limit': '开仓限额',
                'max_limit_order_volume': '限价最大手数',
                'max_market_order_volume': '市价最大手数',
                'min_limit_order_volume': '限价最小手数',
                'min_market_order_volume': '市价最小手数',
                'open_max_market_order_volume': '开仓市价最大手数',
                'open_max_limit_order_volume': '开仓限价最大手数',
                'open_min_market_order_volume': '开仓市价最小手数',
                'open_min_limit_order_volume': '开仓限价最小手数',
                'underlying_symbol': '标的合约',
                'strike_price': '行权价',
                'expired': '已退市',
                'expire_datetime': '到期时间',
                'expire_rest_days': '剩余天数',
                'delivery_year': '交割年',
                'delivery_month': '交割月',
                'last_exercise_datetime': '最后行权',
                'exercise_year': '行权年',
                'exercise_month': '行权月',
                'option_class': '期权方向',
                'upper_limit': '涨停价',
                'lower_limit': '跌停价',
                'pre_settlement': '昨结算',
                'pre_open_interest': '昨持仓',
                'pre_close': '昨收盘',
                'trading_time_day': '白盘时段',
                'trading_time_night': '夜盘时段',
                'update_time': '更新时间'
            }
            renamed_df = symbol_info.rename(columns=rename_map)
            # print("重命名后的数据:")
            # print(renamed_df.head())

            columns = ['序号'] + renamed_df.columns.tolist()
            # print(f"表格列数: {len(columns)}")
            # print(f"表格列名: {columns}")

            # 先设置行数为0，再设置正确的行数，确保多余行被删除
            self.tableWidget.setRowCount(0)
            self.tableWidget.setColumnCount(len(columns))
            self.tableWidget.setHorizontalHeaderLabels(columns)
            self.tableWidget.setRowCount(len(renamed_df))
            # print(f"表格行数: {len(renamed_df)}")

            for row, (_, info_row) in enumerate(renamed_df.iterrows()):
                index_item = QTableWidgetItem(str(row + 1))
                self.tableWidget.setItem(row, 0, index_item)

                for col, key in enumerate(renamed_df.columns):
                    value = str(info_row[key])
                    item = QTableWidgetItem(value)

                    if key in ('最新价', '涨跌幅'):
                        try:
                            val = float(value.replace('%', ''))
                            if val > 0:
                                item.setForeground(Qt.GlobalColor.red)
                            elif val < 0:
                                item.setForeground(Qt.GlobalColor.green)
                        except ValueError:
                            pass

                    self.tableWidget.setItem(row, col + 1, item)
            # print("表格数据填充完成")
        else:
            columns = ['序号', '代码', '名称', '类型', '最新价', '开盘价', '最高价', '最低价', '成交量', '涨跌幅']
            self.tableWidget.setColumnCount(len(columns))
            self.tableWidget.setHorizontalHeaderLabels(columns)
            # 先清空内容，再删除所有行，确保彻底清除
            self.tableWidget.clearContents()
            self.tableWidget.setRowCount(0)
            # print("表格数据为空")

        for i in range(self.tableWidget.columnCount()):
            self.tableWidget.resizeColumnToContents(i)
        self.tableWidget.horizontalHeader().setStretchLastSection(True)
        self.updateTableFontColor()

        # 数据填充完成后重新启用排序
        self.tableWidget.setSortingEnabled(True)

    def __initWidget(self):
        self.vBoxLayout = QVBoxLayout(self)

        # 主要分类 SegmentedWidget
        self.segmentedWidget = SegmentedWidget(self)
        self.segmentedWidget.addItem("合约类型", self.tr("合约类型"))

        self.mainSegmentedScrollArea = SingleDirectionScrollArea(
            orient=Qt.Orientation.Horizontal, parent=self)
        self.mainSegmentedScrollArea.setWidget(self.segmentedWidget)
        self.mainSegmentedScrollArea.enableTransparentBackground()
        self.mainSegmentedScrollArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mainSegmentedScrollArea.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.segmentedWidget.adjustSize()
        self.mainSegmentedScrollArea.setFixedHeight(self.segmentedWidget.height())

        # 交易所分类 SegmentedWidget
        self.subsegmentedWidget = SegmentedWidget(self)
        self.subsegmentedWidget.addItem("交易所", self.tr("交易所"))

        self.subSegmentedScrollArea = SingleDirectionScrollArea(
            orient=Qt.Orientation.Horizontal, parent=self)
        self.subSegmentedScrollArea.setWidget(self.subsegmentedWidget)
        self.subSegmentedScrollArea.enableTransparentBackground()
        self.subSegmentedScrollArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.subSegmentedScrollArea.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.subsegmentedWidget.adjustSize()
        self.subSegmentedScrollArea.setFixedHeight(self.subsegmentedWidget.height())

        # 表格
        self.tableWidget = TableWidget(self)
        self.tableWidget.installEventFilter(self)  # 在表格上安装事件过滤器
        self.tableWidget.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tableWidget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tableWidget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tableWidget.setSortingEnabled(True)  # 启用列排序
        self.tableWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # 启用右键菜单
        self.tableWidget.customContextMenuRequested.connect(self.show_context_menu)
        self.tableWidget.horizontalHeader().setStretchLastSection(True)

        self.vBoxLayout.addWidget(self.mainSegmentedScrollArea)
        self.vBoxLayout.addWidget(self.subSegmentedScrollArea)
        self.vBoxLayout.addWidget(self.tableWidget)
        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)

        self.updateTableFontColor()

    def update_exchange_segments(self):
        """更新SegmentedWidget为交易所名称"""
        # print("开始更新交易所 segments")

        if self.main_window and self.main_window.tq_object and self.main_window.tq_object.exchanges:
            self.segmentedWidget.clear()
            self.subsegmentedWidget.clear()

            # 从 tq_object 获取中文类型名列表，转换为英文类型名作为 routeKey
            from ..common.tq_object import INS_CLASS_MAP, EXCHANGE_ID_MAP

            # 合并所有映射字典
            ins_class_en_to_cn = {}
            for map_dict in INS_CLASS_MAP:
                ins_class_en_to_cn.update(map_dict)

            # 获取中文类型名列表
            ins_classes_cn = self.main_window.tq_object.get_ins_class()

            # 使用英文作为 routeKey，中文作为 text
            for ins_class_cn in ins_classes_cn:
                # 找到对应的英文键
                ins_class_en = None
                for en, cn in ins_class_en_to_cn.items():
                    if cn == ins_class_cn:
                        ins_class_en = en
                        break
                if ins_class_en:
                    self.segmentedWidget.addItem(
                        routeKey=ins_class_en,
                        text=ins_class_cn,
                        onClick=self.__onSegmentedChanged
                    )

            if ins_classes_cn:
                exchanges_cn = self.main_window.tq_object.get_exchanges(ins_classes_cn[0])
                # 使用英文作为 routeKey，中文作为 text
                for exchange_cn in exchanges_cn:
                    # 找到对应的英文键
                    exchange_en = None
                    for en, cn in EXCHANGE_ID_MAP.items():
                        if cn == exchange_cn:
                            exchange_en = en
                            break
                    if exchange_en:
                        self.subsegmentedWidget.addItem(
                            routeKey=exchange_en,
                            text=exchange_cn,
                            onClick=self.__onSegmentedChanged
                        )

                # 设置默认选中项
                first_ins_class_en = None
                for en, cn in ins_class_en_to_cn.items():
                    if cn == ins_classes_cn[0]:
                        first_ins_class_en = en
                        break

                first_exchange_en = None
                for en, cn in EXCHANGE_ID_MAP.items():
                    if cn == exchanges_cn[0]:
                        first_exchange_en = en
                        break

                if first_ins_class_en and first_exchange_en:
                    self.segmentedWidget.setCurrentItem(first_ins_class_en)
                    self.subsegmentedWidget.setCurrentItem(first_exchange_en)
                    self.__onSegmentedChanged()

            # 保存映射表到数据库
            self._save_maps_to_db()

            self.main_window.create_tq_api_qtimer()
        else:
            print("没有获取到交易所数据")

        self.is_update_exchange_segments = False
        # print("交易所 segments 更新完成")

    def _save_maps_to_db(self):
        """保存映射表到数据库"""
        try:
            from ..common.database_manager import get_db_manager
            from ..common.tq_object import INS_CLASS_MAP, EXCHANGE_ID_MAP

            db_manager = get_db_manager()
            if db_manager is None:
                return

            # 合并 INS_CLASS_MAP 的所有字典
            merged_ins_class_map = {}
            for map_dict in INS_CLASS_MAP:
                merged_ins_class_map.update(map_dict)

            # 保存合约类型映射表
            db_manager.save_ins_class_map(merged_ins_class_map)
            # 保存交易所映射表
            db_manager.save_exchange_id_map(EXCHANGE_ID_MAP)
            # print(f"[_save_maps_to_db] 已保存映射表: {len(merged_ins_class_map)} 个合约类型, {len(EXCHANGE_ID_MAP)} 个交易所")
        except Exception as e:
            print(f"[_save_maps_to_db] 保存映射表失败: {e}")

    def __onSegmentedChanged(self):
        QTimer.singleShot(100, self.__update_table)

    def __update_table(self):
        """更新表格数据"""
        ins_class = self.segmentedWidget.currentRouteKey()
        exchange = self.subsegmentedWidget.currentRouteKey()
        if ins_class not in self.exchanges:
            self.exchanges[ins_class] = {}
        if exchange not in self.exchanges[ins_class]:
            self.exchanges[ins_class][exchange] = None
        # print(f"ins_class changed to: {ins_class}, exchange changed to: {exchange}")

        self.tableWidget.clearContents()
        self.stop_update_thread()

        # 优先从内存缓存中获取数据
        symbol_info = self._get_from_cache(ins_class, exchange)
        if symbol_info is not None:
            # print(f"从缓存获取数据: {len(symbol_info)} 条")
            self.exchanges[ins_class][exchange] = symbol_info
        else:
            # 缓存中没有数据，需要从其他来源获取
            if self.main_window.tq_api:
                # 已登录天勤：从天勤API获取数据
                symbol_info = self._get_from_tq_api(ins_class, exchange)
                if symbol_info is not None:
                    # 保存到数据库
                    self._save_symbol_info_to_db(ins_class, exchange, symbol_info)
                    # 保存到缓存
                    self._save_to_cache(ins_class, exchange, symbol_info)
                    # 标记为已保存到数据库
                    if ins_class not in self.saved_to_db:
                        self.saved_to_db[ins_class] = set()
                    self.saved_to_db[ins_class].add(exchange)
                    self.exchanges[ins_class][exchange] = symbol_info
                    # print(f"从天勤API获取数据并缓存: {len(symbol_info)} 条")
            else:
                # 未登录天勤：从数据库获取数据
                symbol_info = self._load_symbol_info_from_db(ins_class, exchange)
                if symbol_info is not None:
                    # 保存到缓存
                    self._save_to_cache(ins_class, exchange, symbol_info)
                    self.exchanges[ins_class][exchange] = symbol_info
                    # print(f"从数据库获取数据并缓存: {len(symbol_info)} 条")

        if symbol_info is None:
            # print(f"获取到 {len(symbol_info)} 条数据")
            # print(symbol_info.head())
            print("未获取到数据")

        if symbol_info is not None:
            # print("准备创建 UpdateTableDataThread")
            self.update_thread = UpdateTableDataThread(self, symbol_info)
            # print("已创建 UpdateTableDataThread")
            self.update_thread.finished.connect(self.stop_update_thread)
            # print("已连接 finished 信号")
            self.update_thread.start()
            # print("已启动 UpdateTableDataThread")
        else:
            print("symbol_info 为 None，不创建线程")

    def stop_update_thread(self):
        """停止更新线程"""
        if self.update_thread:
            self.update_thread.terminate()
            self.update_thread.deleteLater()
            self.update_thread = None

    def _get_from_cache(self, ins_class: str, exchange: str) -> Optional['pd.DataFrame']:
        """从内存缓存获取数据"""
        if ins_class in self.cached_symbol_info and exchange in self.cached_symbol_info[ins_class]:
            return self.cached_symbol_info[ins_class][exchange]
        return None

    def _save_to_cache(self, ins_class: str, exchange: str, symbol_info: 'pd.DataFrame'):
        """保存数据到内存缓存"""
        if ins_class not in self.cached_symbol_info:
            self.cached_symbol_info[ins_class] = {}
        self.cached_symbol_info[ins_class][exchange] = symbol_info
        # print(f"[_save_to_cache] 已缓存 {ins_class}/{exchange}: {len(symbol_info)} 条数据")

    def _get_from_tq_api(self, ins_class: str, exchange: str) -> Optional['pd.DataFrame']:
        """从天勤API获取数据

        Args:
            ins_class: 英文合约类型（如 FUTURE, CONT_MAIN）
            exchange: 英文交易所ID（如 SHFE, DCE）
        """
        try:
            from ..common.tq_object import INS_CLASS_MAP, EXCHANGE_ID_MAP

            # 合并所有映射字典，获取英文->中文映射
            ins_class_en_to_cn = {}
            for map_dict in INS_CLASS_MAP:
                ins_class_en_to_cn.update(map_dict)

            # 转换为中文类型名和交易所名
            ins_class_cn = ins_class_en_to_cn.get(ins_class, ins_class)
            exchange_cn = EXCHANGE_ID_MAP.get(exchange, exchange)

            # 使用中文值查询 tq_object.exchanges
            if ins_class_cn in self.main_window.tq_object.exchanges and \
                    exchange_cn in self.main_window.tq_object.exchanges[ins_class_cn]:
                symbol_list = self.main_window.tq_object.exchanges[ins_class_cn][exchange_cn]
                if symbol_list:
                    symbol_info = self.main_window.tq_api.query_symbol_info(symbol_list)
                    # print(f"[_get_from_tq_api] 从天勤API获取数据: {len(symbol_info)} 条")
                    return symbol_info
            else:
                # tq_object.exchanges 中没有数据，通过天勤API在线获取
                # 对于主力合约（CONT_MAIN），使用 query_cont_quotes 获取每个品种唯一的主力合约
                if ins_class == "CONT_MAIN" and exchange not in ("SSE", "SZSE", "KQD"):
                    try:
                        symbollist = list(self.main_window.tq_api.query_cont_quotes(exchange))
                        if symbollist:
                            # 更新 tq_object.exchanges
                            if ins_class_cn not in self.main_window.tq_object.exchanges:
                                self.main_window.tq_object.exchanges[ins_class_cn] = {}
                            self.main_window.tq_object.exchanges[ins_class_cn][exchange_cn] = symbollist
                            symbol_info = self.main_window.tq_api.query_symbol_info(symbollist)
                            if symbol_info is not None and not symbol_info.empty:
                                return symbol_info
                    except Exception as e:
                        print(f"[_get_from_tq_api] query_cont_quotes 失败: {e}")

                # 使用 query_symbol_info 过滤（其他类型）
                all_symbols = self.main_window.tq_api.query_symbol_info()
                if all_symbols is not None:
                    filter_ins_class = ins_class
                    if ins_class == "CONT_MAIN":
                        filter_ins_class = "FUTURE"

                    filtered_symbols = all_symbols[
                        (all_symbols['ins_class'] == filter_ins_class) &
                        (all_symbols['exchange_id'] == exchange)
                    ]
                    if not filtered_symbols.empty:
                        # 更新 tq_object.exchanges（使用中文键）
                        if ins_class_cn not in self.main_window.tq_object.exchanges:
                            self.main_window.tq_object.exchanges[ins_class_cn] = {}
                        self.main_window.tq_object.exchanges[ins_class_cn][exchange_cn] = \
                            filtered_symbols['instrument_id'].tolist()
                        # print(f"[_get_from_tq_api] 从天勤API过滤数据: {len(filtered_symbols)} 条")
                        return filtered_symbols
            return None
        except Exception as e:
            print(f"[_get_from_tq_api] 从天勤API获取数据失败: {e}")
            return None

    def _save_symbol_info_to_db(self, ins_class: str, exchange: str, symbol_info: 'pd.DataFrame'):
        """保存合约信息到数据库

        Args:
            ins_class: 英文合约类型（如 FUTURE, CONT_MAIN）
            exchange: 英文交易所ID（如 SHFE, DCE）
            symbol_info: 合约信息DataFrame
        """
        try:
            from ..common.database_manager import get_db_manager, SaveSymbolInfoThread

            db_manager = get_db_manager()
            if db_manager is None:
                print("[_save_symbol_info_to_db] 数据库管理器为空")
                return

            # 复制 DataFrame，避免修改原始数据
            symbol_info_copy = symbol_info.copy()

            # 替换 ins_class 和 exchange_id 字段为传入的英文值
            symbol_info_copy['ins_class'] = ins_class
            symbol_info_copy['exchange_id'] = exchange

            # print(f"[_save_symbol_info_to_db] 保存 {ins_class}/{exchange} 的数据到数据库: {len(symbol_info_copy)} 条")

            # 使用线程保存数据，避免阻塞UI
            self.save_db_thread = SaveSymbolInfoThread(db_manager, symbol_info_copy)
            # self.save_db_thread.save_finished.connect(
            #     lambda success: print(f"[_save_symbol_info_to_db] 保存{'成功' if success else '失败'}")
            # )
            self.save_db_thread.start()
        except Exception as e:
            print(f"[_save_symbol_info_to_db] 保存数据失败: {e}")
            import traceback
            traceback.print_exc()

    def _load_symbol_info_from_db(self, ins_class: str, exchange: str) -> Optional['pd.DataFrame']:
        """从数据库加载合约信息"""
        try:
            from ..common.database_manager import get_db_manager

            db_manager = get_db_manager()
            if db_manager is None:
                # print("[_load_symbol_info_from_db] 数据库管理器为空")
                return None

            symbol_info = db_manager.get_symbol_info(ins_class, exchange)
            if symbol_info is not None and not symbol_info.empty:
                # print(f"[_load_symbol_info_from_db] 从数据库加载 {ins_class}/{exchange}: {len(symbol_info)} 条")
                return symbol_info
            else:
                # print(f"[_load_symbol_info_from_db] 数据库中没有 {ins_class}/{exchange} 的数据")
                return None
        except Exception as e:
            print(f"[_load_symbol_info_from_db] 加载数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def eventFilter(self, obj, event):
        """事件过滤器，用于处理表格的滚轮事件"""
        if event.type() == QEvent.Type.Wheel:
            if obj == self.tableWidget:
                # 获取滚轮滚动的方向
                delta = event.angleDelta().y()
                # 获取垂直滚动条
                v_scroll = self.tableWidget.verticalScrollBar()
                # 根据滚轮方向调整滚动条位置
                if delta > 0:
                    # 向上滚动
                    v_scroll.setValue(v_scroll.value() - v_scroll.singleStep() * 3)
                else:
                    # 向下滚动
                    v_scroll.setValue(v_scroll.value() + v_scroll.singleStep() * 3)
                return True
        return super().eventFilter(obj, event)

    def updateTableFontColor(self):
        """更新表格中所有单元格的字体颜色"""
        from qfluentwidgets import Theme
        current_theme = cfg.get(cfg.themeMode)
        is_dark = current_theme == Theme.DARK

        for row in range(self.tableWidget.rowCount()):
            for col in range(self.tableWidget.columnCount()):
                item = self.tableWidget.item(row, col)
                if item:
                    current_color = item.foreground().color()
                    is_special_color = (
                        current_color == QColor(Qt.GlobalColor.red) or
                        current_color == QColor(Qt.GlobalColor.green)
                    )
                    if not is_special_color:
                        if is_dark:
                            item.setForeground(QColor("#ffffff"))
                        else:
                            item.setForeground(QColor("#000000"))

    def on_cell_double_clicked(self, row, column):
        """双击表格单元格创建图表"""
        if self.main_window:
            try:
                # 检查item是否存在
                symbol_item = self.tableWidget.item(row, 1)
                type_item = self.tableWidget.item(row, 3)

                if symbol_item is None or type_item is None:
                    # 空白行，直接返回
                    return

                # 代码列是第1列（第0列是序号）
                symbol = symbol_item.text()
                is_stock = type_item.text()=="STOCK"
                self.main_window.start_minibt_chart(symbol, is_stock=is_stock)
            except Exception as e:
                print(f"创建图表失败：{e}")
                traceback.print_exc()

    def get_main_contracts(self) -> dict:
        """获取主力合约列表
        
        Returns:
            dict: {交易所名: [合约列表]}，如 {"上期所": ["SHFE.ni2609", ...]}
        """
        if not self.main_window or not hasattr(self.main_window, 'tq_object'):
            return {}
        if not self.main_window.tq_object or not self.main_window.tq_object.exchanges:
            return {}
        
        # 主力合约存储在 tq_object.exchanges["主力"] 中
        main_contracts = self.main_window.tq_object.exchanges.get("主力", {})
        return main_contracts

    def load_data_from_db(self):
        """从数据库加载数据"""
        try:
            from ..common.database_manager import get_db_manager, DatabaseInitThread

            # 使用线程初始化数据库并加载数据
            self.db_init_thread = DatabaseInitThread()
            self.db_init_thread.init_finished.connect(self._on_db_init_finished)
            self.db_init_thread.start()
        except Exception as e:
            print(f"从数据库加载数据失败: {e}")
            traceback.print_exc()

    def _on_db_init_finished(self, success: bool):
        """数据库初始化完成后的回调"""
        if not success:
            print("数据库初始化失败")
            return

        try:
            from ..common.database_manager import get_db_manager

            db_manager = get_db_manager()

            # 检查数据库中是否有数据
            if not db_manager.has_data():
                print("数据库中没有数据")
                return

            # 从数据库加载映射表
            ins_class_map = db_manager.get_ins_class_map()
            exchange_id_map = db_manager.get_exchange_id_map()
            # print(f"从数据库加载映射表: {len(ins_class_map)} 个合约类型, {len(exchange_id_map)} 个交易所")

            # 从数据库加载合约信息
            symbol_info = db_manager.get_symbol_info()
            if symbol_info is not None and not symbol_info.empty:
                # print(f"从数据库加载了 {len(symbol_info)} 条合约信息")

                # 打印数据的前几行，帮助调试
                # print(f"数据列名: {symbol_info.columns.tolist()}")
                # print(f"ins_class唯一值: {symbol_info['ins_class'].unique()}")
                # print(f"exchange_id唯一值: {symbol_info['exchange_id'].unique()}")

                # 按合约类型和交易所分组
                for ins_class in symbol_info['ins_class'].unique():
                    if ins_class not in self.exchanges:
                        self.exchanges[ins_class] = {}

                    ins_class_data = symbol_info[symbol_info['ins_class'] == ins_class]
                    for exchange_id in ins_class_data['exchange_id'].unique():
                        exchange_data = ins_class_data[ins_class_data['exchange_id'] == exchange_id]
                        self.exchanges[ins_class][exchange_id] = exchange_data
                        # 保存到缓存
                        self._save_to_cache(ins_class, exchange_id, exchange_data)
                        # print(f"已加载数据: {ins_class}/{exchange_id}, 共 {len(exchange_data)} 条")

                # 更新交易所分类（使用数据库中的映射表）
                self._update_segments_from_db_data(ins_class_map, exchange_id_map)

        except Exception as e:
            print(f"加载数据失败: {e}")
            traceback.print_exc()

    def _update_segments_from_db_data(self, ins_class_map: dict, exchange_id_map: dict):
        """从数据库数据更新交易所分类（使用数据库中的映射表）"""
        try:
            if self.exchanges:
                self.segmentedWidget.clear()
                self.subsegmentedWidget.clear()

                # 添加所有合约类型（从映射表）
                for ins_class_en, ins_class_cn in ins_class_map.items():
                    self.segmentedWidget.addItem(
                        routeKey=ins_class_en,
                        text=ins_class_cn,
                        onClick=self.__onSegmentedChanged
                    )

                # 添加所有交易所（从映射表）
                for exchange_id_en, exchange_id_cn in exchange_id_map.items():
                    self.subsegmentedWidget.addItem(
                        routeKey=exchange_id_en,
                        text=exchange_id_cn,
                        onClick=self.__onSegmentedChanged
                    )

                # 设置默认选中项
                ins_classes = list(self.exchanges.keys())
                if ins_classes:
                    self.segmentedWidget.setCurrentItem(ins_classes[0])
                    exchanges = list(self.exchanges[ins_classes[0]].keys())
                    if exchanges:
                        self.subsegmentedWidget.setCurrentItem(exchanges[0])
                        self.__onSegmentedChanged()

                # print("从数据库数据更新交易所分类完成")
        except Exception as e:
            print(f"更新交易所分类失败: {e}")
            traceback.print_exc()

    def show_context_menu(self, pos):
        """显示右键菜单"""
        # 获取当前选中的行
        current_row = self.tableWidget.currentRow()
        if current_row < 0:
            return

        # 获取当前选中的合约代码
        try:
            # 代码列是第1列（第0列是序号）
            symbol_item = self.tableWidget.item(current_row, 1)
            if symbol_item is None:
                return
            symbol = symbol_item.text()
        except Exception:
            return

        # 创建右键菜单
        menu = RoundMenu(parent=self)

        # 周期选项
        period_texts = ["30秒", "1分", "5分", "15分", "1时", "1日"]
        periods = [30, 60, 5*60, 15*60, 60*60, 60*60*24]

        for text, period in zip(period_texts, periods):
            action = Action(text, parent=menu)
            action.triggered.connect(lambda checked, s=symbol, p=period: self._on_period_selected(s, p))
            menu.addAction(action)

        # 显示菜单
        menu.exec(self.tableWidget.mapToGlobal(pos))

    def _on_period_selected(self, symbol: str, period: int):
        """选择周期后创建图表"""
        if self.main_window:
            try:
                # 调用主窗口创建图表，传入周期参数
                self.main_window.start_minibt_chart(symbol, cycle=period)
            except Exception as e:
                print(f"创建图表失败：{e}")
                traceback.print_exc()
