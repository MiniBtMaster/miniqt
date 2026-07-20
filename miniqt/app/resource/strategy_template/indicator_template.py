# -*- coding: utf-8 -*-
"""
指标模板 - minibt 自定义技术指标开发模板

使用说明：
1. 将此模板复制到你的策略目录
2. 重命名文件（如：my_indicator.py）
3. 修改指标类名（如：CustomIndicator → YourIndicatorName）
4. 设置指标参数（params）
5. 在 next 方法中实现指标计算逻辑
6. 在策略中引用此指标

指标参数：
- isplot: 是否在图表上显示（True/False）
- params: 指标参数字典，格式如 dict(length=14)

指标输出：
- 返回值会自动保存到指标的 .new 属性中
- 使用 self.close[-1] 获取当前K线收盘价
- 使用 self.close[-2] 获取前一根K线收盘价
- 以此类推

常用K线数据：
- self.open: 开盘价
- self.high: 最高价
- self.low: 最低价
- self.close: 收盘价
- self.volume: 成交量

示例指标：
- CCI: 商品通道指标
- MACD: 异同移动平均线
- ATR: 平均真实波动幅度
- MA: 移动平均线
"""

from minibt import *


class CustomIndicator(BtIndicator):
    """
    自定义技术指标类
    
    继承自 BtIndicator，需要设置 isplot、params 和实现 next 方法
    """
    
    # 是否在图表上显示（True=显示，False=隐藏）
    isplot = True
    
    # 指标参数，可在参数优化时调整
    params = dict(
        length=14,      # 参数1：计算周期
        multiplier=1.0  # 参数2：乘数
    )

    def next(self):
        """
        指标计算方法
        
        每次收到新的K线数据时调用此方法，计算指标值
        返回值会自动保存到指标的 .new 属性中
        
        示例：计算简单移动平均线（SMA）
        return sum(self.close[-self.p.length:]) / self.p.length
        
        示例：计算RSI
        gains = sum(max(0, self.close[i] - self.close[i-1]) for i in range(-1, -self.p.length-1, -1))
        losses = sum(max(0, self.close[i-1] - self.close[i]) for i in range(-1, -self.p.length-1, -1))
        if losses == 0:
            return 100
        rs = gains / losses
        return 100 - (100 / (1 + rs))
        """
        # 获取参数值
        length = self.p.length
        multiplier = self.p.multiplier
        
        # 获取当前和历史数据
        # current_close = self.close[-1]
        # prev_close = self.close[-2]
        # current_high = self.high[-1]
        # current_low = self.low[-1]
        
        # 实现你的指标计算逻辑
        # indicator_value = ...
        
        # 返回指标值（会自动保存到 .new 属性）
        # return indicator_value
        ...


# 示例：在策略中使用自定义指标
class ExampleStrategy(Strategy):
    """
    使用自定义指标的策略示例
    """

    def __init__(self):
        # 设置最小启动长度（指标计算所需的最小K线数）
        self.min_start_length = 300
        
        # 获取K线数据
        self.kline = self.get_kline(LocalDatas.test)
        
        # 创建自定义指标实例
        self.custom_indicator = CustomIndicator(self.kline)
        
        # 示例：禁用指标显示（如果不需要在图表上显示）
        # self.custom_indicator.isplot = False

    def next(self):
        # 获取当前持仓
        if not self.kline.position:
            # 使用自定义指标的信号开仓
            # if self.custom_indicator.new > 某个阈值:
            #     self.kline.buy(stop=BtStop.SegmentationTracking)
            # elif self.custom_indicator.new < 某个阈值:
            #     self.kline.sell(stop=BtStop.SegmentationTracking)
            ...
