# coding:utf-8
"""
数据配置模块
用于管理数据相关的配置项，包括Ollama设置等
"""
from qfluentwidgets import qconfig, QConfig, ConfigItem, RangeConfigItem, RangeValidator, FolderValidator
from PyQt6.QtCore import QObject, pyqtSignal


class DataConfig(QConfig):
    """数据配置类"""

    # signals
    dataConfigChanged = pyqtSignal()

    # data source
    useLocalData = ConfigItem("Data", "UseLocalData", True)

    # Ollama setting
    ollamaPath = ConfigItem("Ollama", "Path", "app/ollama", FolderValidator())
    ollamaMaxLoadedModels = RangeConfigItem("Ollama", "MaxLoadedModels", 1, RangeValidator(1, 10))
    ollamaMaxMemory = ConfigItem("Ollama", "MaxMemory", "10gb")
    ollamaNumParallel = RangeConfigItem("Ollama", "NumParallel", 1, RangeValidator(1, 10))
    ollamaKeepAlive = ConfigItem("Ollama", "KeepAlive", "5m")
    ollamaContextLength = RangeConfigItem("Ollama", "ContextLength", 4096, RangeValidator(1024, 32768))
    ollamaNumThreads = RangeConfigItem("Ollama", "NumThreads", 6, RangeValidator(1, 32))
    ollamaModels = ConfigItem("Ollama", "Models", "D:\\ollama_models\\.ollama\\models\\", FolderValidator())
    ollamaHost = RangeConfigItem("Ollama", "Host", 11434, RangeValidator(1024, 65535))

    # Llama.cpp setting
    llamaCppModelPath = ConfigItem("LlamaCpp", "ModelPath", "D:\\models", FolderValidator())
    llamaCppConversationsPath = ConfigItem("LlamaCpp", "ConversationsPath", "app/llama", FolderValidator())

    # 默认配置值（用于恢复默认）
    DEFAULT_CONFIG = {
        "UseLocalData": True,
        "OllamaPath": "ollama",
        "OllamaMaxLoadedModels": 1,
        "OllamaMaxMemory": "10gb",
        "OllamaNumParallel": 1,
        "OllamaKeepAlive": "5m",
        "OllamaContextLength": 4096,
        "OllamaNumThreads": 6,
        "OllamaModels": "D:\\ollama_models",
        "OllamaHost": 11434,
        "LlamaCppModelPath": "D:\\models",
        "LlamaCppConversationsPath": "app/llama",
    }

    def resetToDefault(self):
        """恢复默认配置"""
        self.useLocalData.value = self.DEFAULT_CONFIG["UseLocalData"]
        self.ollamaPath.value = self.DEFAULT_CONFIG["OllamaPath"]
        self.ollamaMaxLoadedModels.value = self.DEFAULT_CONFIG["OllamaMaxLoadedModels"]
        self.ollamaMaxMemory.value = self.DEFAULT_CONFIG["OllamaMaxMemory"]
        self.ollamaNumParallel.value = self.DEFAULT_CONFIG["OllamaNumParallel"]
        self.ollamaKeepAlive.value = self.DEFAULT_CONFIG["OllamaKeepAlive"]
        self.ollamaContextLength.value = self.DEFAULT_CONFIG["OllamaContextLength"]
        self.ollamaNumThreads.value = self.DEFAULT_CONFIG["OllamaNumThreads"]
        self.ollamaModels.value = self.DEFAULT_CONFIG["OllamaModels"]
        self.ollamaHost.value = self.DEFAULT_CONFIG["OllamaHost"]
        self.llamaCppModelPath.value = self.DEFAULT_CONFIG["LlamaCppModelPath"]
        self.llamaCppConversationsPath.value = self.DEFAULT_CONFIG["LlamaCppConversationsPath"]
        # 保存配置
        self.save()
        # 发送配置变更信号
        self.dataConfigChanged.emit()

    def save(self):
        """保存配置到文件（直接写入，避免依赖全局 qconfig._cfg 单例）"""
        import json
        from pathlib import Path
        
        file = getattr(self, 'file', Path('app/config/data_config.json'))
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file, "w", encoding="utf-8") as f:
            json.dump(self.toDict(), f, ensure_ascii=False, indent=4)


# 创建全局配置实例
data_cfg = DataConfig()
# 加载配置文件
qconfig.load('app/config/data_config.json', data_cfg)
