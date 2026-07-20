# coding:utf-8
from __future__ import annotations
from typing import Dict, List, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from typing import TYPE_CHECKING
import time, os
if TYPE_CHECKING:
    from ..view.main_window import MainWindow, TqApi

INS_CLASS_MAP = [
    {
        "FUTURE": "期货",
        "CONT": "主连",
        # "COMBINE": "组合",
        "INDEX": "指数",
        # "OPTION": "期权",
        "STOCK": "股票",
    },
    {
        "CONT_MAIN": "主力"  # 使用不同的键名，避免覆盖 CONT（主连）
    }]
EXCHANGE_ID_MAP = {
        "CFFEX": "中金所",
        "SHFE": "上期所",
        "DCE": "大商所",
        "CZCE": "郑商所",
        "INE": "能源交易所(原油)",
        "GFEX": "广州期货交易所",
        "SSE": "上交所",
        "SZSE": "深交所",
        "KQD": "外盘主连",
    }

class TqObject(QObject):
    """天勤对象，用于管理交易所主力合约信息"""

    # 信号：主力合约列表更新完成
    cont_quotes_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window: MainWindow = parent
        self.exchanges: Dict[str, dict[str, list[str]]] = {}

    @property
    def api(self) -> TqApi:
        return self.main_window.tq_api

    def update_cont_quotes(self):
        """更新所有交易所的主力连续合约列表"""
        if self.exchanges:
            self.cont_quotes_updated.emit()
            return
        try:
            # 检查api是否可用
            if not self.api:
                print("TqApi未初始化，无法更新主力合约列表")
                # 发送空信号，避免阻塞
                self.cont_quotes_updated.emit()
                return

            all_quotes = {}
            for i, ins_class_map in enumerate(INS_CLASS_MAP):
                if i == 0:
                    for ins_class, ins_class_name in ins_class_map.items():
                        all_quotes[ins_class_name] = {}
                        for exchange_id, exchange_name in EXCHANGE_ID_MAP.items():
                            cont_quotes = self.api.query_quotes(ins_class, exchange_id)
                            all_quotes[ins_class_name][exchange_name] = list(cont_quotes)
                else:
                    for ins_class, ins_class_name in ins_class_map.items():
                        all_quotes[ins_class_name] = {}
                        for exchange_id, exchange_name in EXCHANGE_ID_MAP.items():
                            if exchange_id in ["SSE", "SZSE", "KQD"]:
                                all_quotes[ins_class_name][exchange_name] = []
                                continue
                            symbollist = self.api.query_cont_quotes(exchange_id)
                            all_quotes[ins_class_name][exchange_name] = list(symbollist)

            # 合并为一个字典，key 为中文交易所名称，value 为合约列表
            self.exchanges = all_quotes

            # 发送信号通知更新完成
            self.cont_quotes_updated.emit()

            # print(f"更新主力合约列表成功: {self.exchanges}")
        except Exception as e:
            print(f"更新主力合约列表失败: {e}")

    def get_symbol_info(self, ins_class: str, exchange: str) -> list[str]:
        """获取合约信息

        Args:
            ins_class: 合约类型
            exchange: 交易所名称

        Returns:
            list[str]: 合约信息，包含各种属性
        """
        return self.exchanges[ins_class][exchange]

    def get_ins_class(self) -> list[str]:
        """获取合约类型
        """
        return list(self.exchanges.keys())

    def get_exchanges(self, ins_class: str) -> List[str]:
        """获取所有交易所名称"""
        return list(self.exchanges[ins_class].keys())

    def get_cont_quotes(self, exchange: str) -> List[str]:
        """获取指定交易所的主力连续合约列表"""
        return self.exchanges.get(exchange, [])

    def get_all_cont_quotes(self) -> List[str]:
        """获取所有主力连续合约列表"""
        all_quotes = []
        for quotes in self.exchanges.values():
            all_quotes.extend(quotes)
        return all_quotes
