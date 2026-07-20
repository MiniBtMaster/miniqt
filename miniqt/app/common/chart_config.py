# coding:utf-8
"""
图表配置模块
用于管理图表相关的配置项，包括颜色设置等
"""
from qfluentwidgets import qconfig, QConfig, ConfigItem, ConfigSerializer, RangeConfigItem, RangeValidator, OptionsConfigItem, OptionsValidator
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor


class ColorSerializer(ConfigSerializer):
    """颜色序列化器，将QColor转换为字符串"""

    def serialize(self, color):
        """将颜色对象序列化为字符串"""
        if isinstance(color, QColor):
            # 转换为RGBA字符串格式
            return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha() / 255:.2f})"
        return str(color)

    def deserialize(self, value):
        """将字符串反序列化为颜色对象"""
        return value


class ChartConfig(QConfig):
    """图表配置类"""

    # signals
    chartConfigChanged = pyqtSignal()

    # 图表工具箱显示
    showToolBox = ConfigItem("Chart", "ShowToolBox", False)

    # 鼠标标签颜色
    mouseLabelColor = ConfigItem(
        "Chart",
        "MouseLabelColor",
        "rgba(50, 50, 50, 0.8)",
        serializer=ColorSerializer()
    )

    # 上涨颜色（牛市颜色）
    bullColor = ConfigItem(
        "Chart",
        "BullColor",
        "rgba(39, 157, 130, 100)",
        serializer=ColorSerializer()
    )

    # 下跌颜色（熊市颜色）
    bearColor = ConfigItem(
        "Chart",
        "BearColor",
        "rgba(200, 97, 100, 100)",
        serializer=ColorSerializer()
    )

    # 图表更新设置
    maxWorkers = OptionsConfigItem("ChartUpdate", "MaxWorkers", 4, OptionsValidator([1, 2, 4, 8]), restart=True)
    klineUpdateInterval = OptionsConfigItem("ChartUpdate", "KlineUpdateInterval", 50, OptionsValidator([10, 50, 100, 200, 500]), restart=True)
    indicatorUpdateInterval = OptionsConfigItem("ChartUpdate", "IndicatorUpdateInterval", 500, OptionsValidator([100, 500, 1000, 1500, 2000]), restart=True)
    
    # 期货数据长度
    futuresDataLength = OptionsConfigItem("ChartData", "FuturesDataLength", 1000, OptionsValidator([500, 1000, 2000, 3000, 5000]), restart=True)
    
    # 股票更新设置
    stockKlineUpdateInterval = OptionsConfigItem("ChartUpdate", "StockKlineUpdateInterval", 3000, OptionsValidator([1000, 3000, 5000, 8000, 10000]), restart=True)
    stockIndicatorUpdateInterval = OptionsConfigItem("ChartUpdate", "StockIndicatorUpdateInterval", 3000, OptionsValidator([1000, 3000, 5000, 8000, 10000]), restart=True)

    # 行情数据是否在每次启动时更新
    updateMarketOnStartup = ConfigItem("ChartData", "UpdateMarketOnStartup", False)

    # 默认配置值（用于恢复默认）
    DEFAULT_CONFIG = {
        "ShowToolBox": False,
        "MouseLabelColor": "rgba(50, 50, 50, 0.8)",
        "BullColor": "rgba(39, 157, 130, 100)",
        "BearColor": "rgba(200, 97, 100, 100)",
        "MaxWorkers": 4,
        "KlineUpdateInterval": 50,
        "IndicatorUpdateInterval": 500,
        "FuturesDataLength": 1000,
        "StockKlineUpdateInterval": 3000,
        "StockIndicatorUpdateInterval": 3000,
        "UpdateMarketOnStartup": False
    }

    def resetToDefault(self):
        """恢复默认配置"""
        self.showToolBox.value = self.DEFAULT_CONFIG["ShowToolBox"]
        self.mouseLabelColor.value = self.DEFAULT_CONFIG["MouseLabelColor"]
        self.bullColor.value = self.DEFAULT_CONFIG["BullColor"]
        self.bearColor.value = self.DEFAULT_CONFIG["BearColor"]
        self.maxWorkers.value = self.DEFAULT_CONFIG["MaxWorkers"]
        self.klineUpdateInterval.value = self.DEFAULT_CONFIG["KlineUpdateInterval"]
        self.indicatorUpdateInterval.value = self.DEFAULT_CONFIG["IndicatorUpdateInterval"]
        self.futuresDataLength.value = self.DEFAULT_CONFIG["FuturesDataLength"]
        self.stockKlineUpdateInterval.value = self.DEFAULT_CONFIG["StockKlineUpdateInterval"]
        self.stockIndicatorUpdateInterval.value = self.DEFAULT_CONFIG["StockIndicatorUpdateInterval"]
        self.updateMarketOnStartup.value = self.DEFAULT_CONFIG["UpdateMarketOnStartup"]
        # 保存配置
        self.save()
        # 发送配置变更信号
        self.chartConfigChanged.emit()

    def save(self):
        """保存配置到文件（直接写入，避免依赖全局 qconfig._cfg 单例）"""
        import json
        from pathlib import Path
        
        file = getattr(self, 'file', Path('app/config/chart_config.json'))
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file, "w", encoding="utf-8") as f:
            json.dump(self.toDict(), f, ensure_ascii=False, indent=4)


# 创建全局配置实例
chart_cfg = ChartConfig()
# 加载配置文件
qconfig.load('app/config/chart_config.json', chart_cfg)
