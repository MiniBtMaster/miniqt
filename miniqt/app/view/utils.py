from __future__ import annotations
from collections import deque
from typing import Iterable



class FixedSizeQueue:
    def __init__(self, max_size, value=False, values: Iterable = None):
        self.queue = deque(maxlen=max_size)
        if not (values and isinstance(values, Iterable)):
            values = [False,]*max_size
        self.add_items(list(values))
        if isinstance(value, bool):
            self.add(value)

    def add(self, item) -> FixedSizeQueue:
        """添加单个元素"""
        self.queue.append(item)
        return self

    def add_items(self, items: Iterable) -> FixedSizeQueue:
        """批量添加元素"""
        self.queue.extend(items)
        return self

    def values(self) -> list:
        """获取队列中所有元素（列表形式）"""
        return list(self.queue)

    def clear(self) -> FixedSizeQueue:
        """清空队列"""
        self.queue.clear()
        return self

    @property
    def any(self) -> bool:
        return any(self.queue)