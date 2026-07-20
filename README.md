# MiniQT 介绍

## 概述

MiniQT 是一款基于 minibt 与 PyQt6-Fluent-Widgets（Fluent Design 设计风格）开发的量化交易可视化桌面应用，集成了天勤量化（TqSdk）API、多周期 K 线图表、策略回测引擎以及 DuckDB 本地数据库，旨在为量化交易者提供一个功能完善、界面美观、易于扩展的交易分析与策略开发平台。

MiniQT 支持期货、股票、指数等多种金融品种的实时行情展示、历史数据查询与离线缓存，并提供可视化策略回测、交互式开发工具（Jupyter / JupyterLab / 终端）、系统设置等模块，帮助用户高效完成从行情监控、策略研究到回测验证的全流程量化交易工作。


## 📚 相关资源

- **GitHub 仓库**：[https://github.com/MiniBtMaster/miniqt](https://github.com/MiniBtMaster/miniqt)
- **PyPI 仓库**：[https://pypi.org/project/miniqt/](https://pypi.org/project/miniqt/)
- **在线教程**：[https://www.minibt.cn](https://www.minibt.cn)
- **联系邮箱**：407841129@qq.com

---

## 主界面概览

MiniQT 启动后默认进入主界面，采用 Fluent Design 设计风格，提供清晰的模块化导航。

![miniqt 主界面](https://minibt-img.oss-cn-shenzhen.aliyuncs.com/plot/6_1.png)

### 顶部 Banner

展示项目名称 "Mini Quant Trader" 与 K 线背景图。

### 资源链接区

提供外部资源链接，方便用户快速访问相关文档和社区：

| 链接            | 描述                         | 跳转目标                              |
| --------------- | ---------------------------- | ------------------------------------- |
| **GitHub 仓库** | 最新的量化交易框架和策略示例 | 访问 GitHub 查看项目源码与更新日志    |
| **PyPI 仓库**   | 通过 pip 安装 miniqt         | `pip install miniqt` 一键安装最新版本 |
| **在线教程**    | 详细的 miniqt 使用教程和文档 | 从零开始学习 miniqt 的各项功能        |
| **知乎专栏**    | 量化交易相关知识和策略分享   | 深入了解量化交易策略与实战经验        |

---

## 快捷入口

快捷入口区是 miniqt 四大核心功能模块的快速访问入口，每个卡片对应一个完整的子模块：

### 行情报价
- **功能**：查看各交易所主力合约的实时行情数据
- **模块路径**：`miniqt/app/view/market_quote_interface.py`
- **核心特性**：
  - 支持期货、股票、指数、主连、主力等多种合约类型
  - 按交易所分组（中金所、上期所、大商所、郑商所、上交所、深交所、能源所等）
  - 实时显示代码、名称、最新价、开盘价、最高价、最低价、成交量、涨跌幅等字段
  - 支持列排序、右键菜单快速打开 K 线图
  - 集成 DuckDB 本地数据库

![miniqt 行情报价界面](https://minibt-img.oss-cn-shenzhen.aliyuncs.com/plot/6_2.png)

### 策略回测
- **功能**：创建和运行量化策略回测，分析策略表现
- **模块路径**：`miniqt/app/windows/strategy_backtest_window.py`
- **核心特性**：
  - 可视化回测参数配置
  - 支持多策略并行回测
  - 回测结果图表化展示
  - 详细的回测报告（收益率、最大回撤、夏普比率等）
  - **Pi Agent 智能助手**：集成 pi-agent-web，AI 辅助策略开发
    - AI 对话：与 AI 模型自然语言交互，辅助编写策略代码、分析回测结果、调试错误
    - 文件自动同步：AI 写入或编辑策略文件后，自动在代码编辑器中打开/刷新
    - 文件树双向同步：Pi Agent 文件树与代码编辑器文件树实时双向同步
    - 主题联动：跟随 MiniQT 深色/浅色主题自动切换
    - 快捷 AI（F2）：在代码编辑器中一键调起 AI，直接对当前文件提出修改需求
    - 会话管理：支持多会话切换、历史会话恢复
  
![miniqt 策略回测界面](https://minibt-img.oss-cn-shenzhen.aliyuncs.com/plot/6_4.png)

### K线图表
- **功能**：查看各交易所主力合约的 K 线图，分析价格趋势
- **模块路径**：`miniqt/app/view/kline_chart_interface.py`
- **核心特性**：
  - 支持期货、股票、指数、主连、主力等多种合约类型
  - 按交易所分组（中金所、上期所、大商所、郑商所、上交所、深交所、能源所等）
  - 实时显示 K 线图，支持缩放、平移等交互操作
  - 支持列排序、右键菜单快速打开 K 线图
  - 集成 DuckDB 本地数据库

![miniqt 多图表布局窗口](https://minibt-img.oss-cn-shenzhen.aliyuncs.com/plot/6_11.png)

### miniqt 官网
- **功能**：访问 miniqt 官方网站，获取最新资讯和文档
- **模块路径**：`miniqt/app/view/official_website.py`
- **核心特性**：
  - 内置浏览器组件
  - 直接访问官方网站内容
  - 支持相关社区和文档跳转

### 系统设置
- **功能**：配置应用主题、数据源、图表参数等选项
- **模块路径**：`miniqt/app/view/setting_interface.py`
- **核心特性**：
  - 主题切换（亮色/暗色）
  - 数据源配置
  - 图表样式自定义
  - 全局参数调整

---

## 登录入口

登录入口区提供两种登录方式，满足不同用户场景：

### 期货登录
- **功能**：登录天勤期货交易账户
- **模块路径**：`miniqt/app/view/future_login_interface.py`
- **核心特性**：
  - 登录天勤期货账户，获取实时行情数据
  - 支持实盘交易接口
  - 登录后自动同步所有合约信息到本地数据库

### 股票登录
- **功能**：登录股票交易账户
- **模块路径**：`miniqt/app/view/stock_login_interface.py`
- **核心特性**：
  - 登录股票交易账户
  - 获取股票实时行情
  <!-- - 支持股票实盘交易
  - 登录后自动同步股票信息到本地数据库 -->

---

## 开发工具

开发工具区为开发者和高级用户提供便捷的开发与调试工具：

### 终端窗口
- **功能**：打开交互式终端窗口，执行系统命令
- **模块路径**：`miniqt/app/view/terminal_interface.py`
- **核心特性**：
  - 内置终端模拟器
  - 支持常用的系统命令
  - 方便开发者进行调试和测试

### Jupyter 窗口
- **功能**：启动 Jupyter Notebook 交互式编程环境
- **模块路径**：`miniqt/app/view/jupyter_interface.py`
- **核心特性**：
  - 集成 Jupyter Notebook
  - 支持 Python 交互式编程
  - 方便进行数据分析和策略验证

### JupyterLab 窗口
- **功能**：启动 JupyterLab 交互式开发环境
- **模块路径**：`miniqt/app/view/jupyterlab_interface.py`
- **核心特性**：
  - 集成 JupyterLab
  - 比 Jupyter Notebook 更强大的开发环境
  - 支持文件浏览器、终端、文本编辑器等扩展功能

### 测试图表
- **功能**：打开测试图表窗口，验证图表显示功能
- **模块路径**：`miniqt/app/view/test_chart_interface.py`
- **核心特性**：
  - 用于测试图表组件是否正常工作
  - 展示图表基本功能
  - 方便开发调试图表相关功能

---

## 侧边导航栏

主窗口左侧为侧边导航栏，可快速切换到各个子模块：

| 导航项       | 图标 | 描述             |
| ------------ | ---- | ---------------- |
| **Home**     | 🏠    | 返回主界面       |
| **行情报价** | 📄    | 进入行情报价窗口 |
| **策略回测** | 💻    | 进入策略回测窗口 |
| **官网**     | 🌐    | 打开 miniqt 官网 |
| **设置**     | ⚙️    | 进入系统设置     |


---

## 安装

```bash
# 通过源码安装（开发模式）
pip install -e .

# 通过 PyPI 安装
pip install miniqt
```

## 使用

```bash
# 通过命令行启动
miniqt run
miniqt

# 或通过 Python 模块启动
python -m miniqt run
python -m miniqt
```

## 项目结构

```
miniqt/
├── app/
│   ├── common/          # 公共模块（数据库、天勤对象等）
│   ├── components/      # UI组件
│   ├── view/            # 主界面视图
│   └── windows/         # 子窗口（图表、回测等）
├── resource/            # 资源文件（图片、图标等）
├── __main__.py          # 启动入口
├── pyproject.toml       # 项目配置
└── requirements.txt     # 依赖列表
```

## 依赖

- Python >= 3.12
- PyQt6 >= 6.4.0
- PyQt6-Fluent-Widgets >= 1.11.1
- tqsdk >= 3.4.10
- duckdb >= 0.9.0
- mootdx >= 0.11.7

详见 [requirements.txt](requirements.txt)

## 许可证

MIT License