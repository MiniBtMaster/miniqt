# -*- coding: utf-8 -*-
"""
参数优化模板 - minibt 策略参数优化模板

使用说明：
1. 将此模板复制到你的策略目录
2. 重命名文件（如：my_strategy_opt.py）
3. 修改策略类名（如：OPTStrategy → YourStrategyName）
4. 设置待优化的参数（params）
5. 配置优化选项（op_config）
6. 实现策略逻辑（__init__ 和 next 方法）

参数优化配置：
- op_config: OpConfig 对象，用于配置优化参数
  - target: 优化目标列表，可选值 ['profit', 'sharpe', 'max_drawdown', 'win_rate']
  - weights: 各目标的权重，与 target 一一对应
  - opconfig: 优化器配置，如 OptunaConfig(n_trials=100)
  - op_method: 优化方法，可选 'optuna'
  - params: 待优化参数范围，格式如 dict(length=(5, 21, 1))

优化参数格式：
- dict(param_name=(min_value, max_value, step))
- min_value: 参数最小值
- max_value: 参数最大值
- step: 参数步长（可选，默认为1）

优化目标说明：
- profit: 收益最大化
- sharpe: 夏普比率最大化
- max_drawdown: 最大回撤最小化
- win_rate: 胜率最大化

注意事项：
1. 优化参数必须在 params 字典中定义
2. 在策略中通过 self.p.param_name 使用优化参数
3. 优化会运行多次回测，耗时较长
4. 建议先设置较小的 n_trials 进行测试
"""

from minibt import *


class OPTStrategy(Strategy):
    """
    支持参数优化的策略类
    
    继承自 Strategy，需要设置 params、op_config 和实现 __init__、next 方法
    """
    
    # 策略参数（待优化的参数）
    params = dict(
        length=10,      # 参数1：计算周期，默认值为10
        multiplier=1.0  # 参数2：乘数，默认值为1.0
    )
    
    # 参数优化配置
    op_config = OpConfig(
        # 优化目标：收益、夏普比率、最大回撤
        target=['profit', 'sharpe', 'max_drawdown'],
        # 各目标的权重（总和不一定要为1，权重越大越重要）
        weights=(1., 1., 1.),
        # 优化器配置：使用 Optuna，运行10次试验
        opconfig=OptunaConfig(n_trials=10),
        # 优化方法：optuna
        op_method='optuna',
        # 待优化参数范围：(最小值, 最大值, 步长)
        params=dict(
            length=(5, 21, 1),      # length 参数范围：5到21，步长1
            # multiplier=(0.5, 2.0, 0.1)  # multiplier 参数范围：0.5到2.0，步长0.1
        )
    )

    def __init__(self) -> None:
        """
        策略初始化方法
        
        在此方法中定义：
        1. 数据源（K线数据）
        2. 技术指标（使用优化参数）
        3. 其他策略配置
        """
        # 设置最小启动长度（指标计算所需的最小K线数）
        self.min_start_length = 300
        
        # 获取K线数据
        self.kline = self.get_kline(LocalDatas.test)
        
        # 使用优化参数创建指标
        # 示例：self.indicator = SomeIndicator(self.kline, length=self.p.length)
        
        # 示例信号（优化时可以隐藏不需要显示的信号）
        # self.long_signal = ...
        # self.short_signal = ...
        
        # 禁用信号显示（优化时不需要在图表上显示信号）
        # self.long_signal.isplot = False
        # self.short_signal.isplot = False

    def next(self):
        """
        策略主逻辑方法
        
        每次收到新的K线数据时调用此方法，实现交易决策逻辑
        使用 self.p.param_name 获取优化参数值
        """
        # 获取当前持仓
        if not self.kline.position:
            # 使用优化参数判断开仓条件
            # if self.long_signal.new:
            #     self.kline.buy(stop=BtStop.SegmentationTracking)
            # elif self.short_signal.new:
            #     self.kline.sell(stop=BtStop.SegmentationTracking)
            ...
