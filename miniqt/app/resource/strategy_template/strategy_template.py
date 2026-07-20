# -*- coding: utf-8 -*-
"""
策略模板 - minibt 交易策略开发模板

使用说明：
1. 将此模板复制到你的策略目录
2. 重命名文件（如：my_strategy.py）
3. 修改策略类名（如：MyStrategy → YourStrategyName）
4. 在 __init__ 中定义你的数据和指标
5. 在 next 方法中实现你的交易逻辑

示例数据：
- LocalDatas.test: 测试数据
- LocalDatas.l2601: 豆粕期货数据
- LocalDatas.pp2601: 聚丙烯期货数据
- LocalDatas.pp2601_60: 聚丙烯期货60分钟数据

常用指标：
- self.kline.close: 收盘价
- self.kline.open: 开盘价
- self.kline.high: 最高价
- self.kline.low: 最低价
- self.kline.volume: 成交量
- self.kline.position: 当前持仓（正数为多，负数为空）

止损方式（BtStop）：
- BtStop.SegmentationTracking: 分段跟踪止损
- BtStop.Trailing: 移动止损
- BtStop.Fixed: 固定止损

交易方法：
- self.kline.buy(stop=止损方式): 开多仓
- self.kline.sell(stop=止损方式): 开空仓
- self.kline.close(): 平仓
"""

from minibt import *


class MyStrategy(Strategy):
    """
    自定义交易策略类
    
    继承自 Strategy，需要实现 __init__ 和 next 方法
    """
    
    def __init__(self):
        """
        策略初始化方法
        
        在此方法中定义：
        1. 数据源（K线数据）
        2. 技术指标
        3. 策略参数
        """
        # 获取K线数据，LocalDatas.test 是测试数据，可替换为其他数据源
        self.kline = self.get_kline(LocalDatas.test)
        
        # 示例：添加技术指标
        # self.cci = CCI(self.kline)
        # self.macd = MACD(self.kline)
        # self.atr = ATR(self.kline)
        
        # 示例：设置最小启动长度（指标计算所需的最小K线数）
        # self.min_start_length = 30
        
    def next(self):
        """
        策略主逻辑方法
        
        每次收到新的K线数据时调用此方法，实现交易决策逻辑
        """
        # 示例：获取当前价格
        # current_close = self.kline.close[-1]
        # current_high = self.kline.high[-1]
        # current_low = self.kline.low[-1]
        
        # 示例：获取当前持仓
        # position = self.kline.position
        
        # 示例：开多仓（当满足条件时）
        # if not position and 开多条件:
        #     self.kline.buy(stop=BtStop.SegmentationTracking)
        
        # 示例：开空仓（当满足条件时）
        # if not position and 开空条件:
        #     self.kline.sell(stop=BtStop.SegmentationTracking)
        
        # 示例：平仓（当满足条件时）
        # if position and 平仓条件:
        #     self.kline.close()
        ...
