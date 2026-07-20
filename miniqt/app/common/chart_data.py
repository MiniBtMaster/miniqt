# coding:utf-8
"""
图表数据管理模块
用于管理图表的画线数据和价格预警数据
"""
import json
import os


class ChartDataManager:
    """图表数据管理器"""
    
    def __init__(self):
        """初始化数据管理器"""
        self.data_file = 'app/config/chart_data.json'
        self._drawings = {}
        self._price_alerts = {}
        self.load_data()
    
    def load_data(self):
        """从文件加载数据"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._drawings = data.get('drawings', {})
                    self._price_alerts = data.get('price_alerts', {})
        except Exception as e:
            print(f"加载图表数据失败: {e}")
            # 加载失败时使用空数据
            self._drawings = {}
            self._price_alerts = {}
    
    def save_data(self):
        """保存数据到文件"""
        try:
            # 确保config目录存在
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            
            data = {
                'drawings': self._drawings,
                'price_alerts': self._price_alerts
            }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存图表数据失败: {e}")
    
    @property
    def drawings(self):
        """获取画线数据"""
        return self._drawings
    
    @drawings.setter
    def drawings(self, value):
        """设置画线数据"""
        if isinstance(value, dict):
            self._drawings = value
            self.save_data()
    
    @property
    def price_alerts(self):
        """获取价格预警数据"""
        return self._price_alerts
    
    @price_alerts.setter
    def price_alerts(self, value):
        """设置价格预警数据"""
        if isinstance(value, dict):
            self._price_alerts = value
            self.save_data()
    
    def get_drawings(self, contract):
        """获取指定合约的画线数据"""
        return self._drawings.get(contract, [])
    
    def set_drawings(self, contract, drawings):
        """设置指定合约的画线数据"""
        self._drawings[contract] = drawings
        self.save_data()
    
    def get_price_alerts(self, contract):
        """获取指定合约的价格预警数据"""
        return self._price_alerts.get(contract, {})
    
    def set_price_alerts(self, contract, alerts):
        """设置指定合约的价格预警数据"""
        self._price_alerts[contract] = alerts
        self.save_data()
    
    def clear_drawings(self, contract=None):
        """清除画线数据
        
        Args:
            contract: 合约代码，如果为None则清除所有合约的画线数据
        """
        if contract:
            if contract in self._drawings:
                del self._drawings[contract]
        else:
            self._drawings = {}
        self.save_data()
    
    def clear_price_alerts(self, contract=None):
        """清除价格预警数据
        
        Args:
            contract: 合约代码，如果为None则清除所有合约的价格预警数据
        """
        if contract:
            if contract in self._price_alerts:
                del self._price_alerts[contract]
        else:
            self._price_alerts = {}
        self.save_data()
    
    def validate_data(self):
        """验证数据有效性"""
        # 确保drawings是字典，且值是列表
        if not isinstance(self._drawings, dict):
            self._drawings = {}
        else:
            # 清理无效的画线数据
            valid_drawings = {}
            for contract, data in self._drawings.items():
                if isinstance(data, list):
                    valid_drawings[contract] = data
            self._drawings = valid_drawings
        
        # 确保price_alerts是字典，且值是字典
        if not isinstance(self._price_alerts, dict):
            self._price_alerts = {}
        else:
            # 清理无效的预警数据
            valid_alerts = {}
            for contract, data in self._price_alerts.items():
                if isinstance(data, dict):
                    valid_alerts[contract] = data
            self._price_alerts = valid_alerts
        
        # 保存验证后的数据
        self.save_data()


# 创建全局数据管理器实例
chart_data_manager = ChartDataManager()
