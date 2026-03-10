# openhex

**AI Enhanced Binary Editor** (v0.1)

A powerful binary file editor built with PyQt6, featuring AI-powered analysis, pattern detection, code generation, and flexible selection modes for precise binary editing.

## 功能特性

### 核心编辑功能
- **多种选择模式**：连续选择、列选择、块选择、行选择
  - 🔵 **连续选择 (Continuous)**：默认模式，像文本编辑器一样选择连续字节区域
  - 📊 **列选择 (Column)**：选择所有行的同一列位置
  - ⬜ **块选择 (Block)**：矩形区域选择，支持非连续字节选择
  - 📝 **行选择 (Row)**：选择整行数据
- **多显示模式**：十六进制、二进制、八进制、ASCII
- **大文件支持**：虚拟滚动，支持 GB 级别文件
- **撤销/重做**：完整的编辑历史支持

### 文件管理
- **文件浏览器**：类似 VSCode 的文件树导航
- **多种布局模式**：
  - 等长帧模式 (Equal Frame)：每行固定字节数
  - 头长度模式 (Header Length)：自定义头部 + 数据区域

### AI 增强功能
- **本地 AI**：支持 Ollama 本地模型
- **云端 AI**：支持 OpenAI/Anthropic API
- **智能分析**：模式检测、结构推断、异常识别
- **代码生成**：支持 C、Python、Rust 等语言的解析代码生成

## 选择模式详解

### 1. 连续选择模式 (Continuous)
默认选择模式。用户可以像在普通文本编辑器中一样，通过鼠标拖动选择连续的字节区域。

**使用方式**：
- 点击起始位置
- 拖动到结束位置
- 释放鼠标完成选择

### 2. 列选择模式 (Column)
选择所有行的同一列位置。适用于需要对齐的二进制数据编辑。

**使用方式**：
- 切换到列选择模式
- 点击某一列的任意位置
- 该列的所有字节将被选中

### 3. 块选择模式 (Block)
矩形区域选择，支持选择多行中的连续字节列。

**使用方式**：
- 切换到块选择模式
- 点击起始位置
- 拖动到结束位置
- 形成矩形选择区域

### 4. 行选择模式 (Row)
快速选择整行数据。

**使用方式**：
- 切换到行选择模式
- 点击任意行
- 整行数据被选中

## 项目架构

```
openhex/
├── openhex.py              # 应用程序入口点
├── config/                   # 配置文件目录
├── src/
│   ├── models/              # 数据模型
│   │   └── hex_model.py     # 十六进制数据模型
│   ├── core/               # 核心逻辑
│   │   └── parser/         # 二进制解析器
│   ├── ai/                 # AI 集成模块
│   ├── ui/                 # 用户界面
│   │   ├── views/
│   │   │   └── hex_view.py # 十六进制视图组件（包含选择模式逻辑）
│   │   └── widgets/        # 自定义控件
│   └── utils/              # 工具函数
└── tests/                  # 测试用例
```

### 核心组件

#### HexView (hex_view.py)
核心视图组件，负责：
- 二进制数据的可视化显示
- 四种选择模式的实现
- 高亮渲染逻辑
- 鼠标事件处理

#### HexModel (hex_model.py)
数据模型，负责：
- 文件数据管理
- 选择范围存储
- 行偏移计算
- 布局模式处理

## 环境要求

- Python 3.10+
- PyQt6 >= 6.6.0
- macOS（当前针对 macOS 优化）

## 安装运行

```bash
# 克隆仓库
cd openhex

# 安装依赖
pip install -r requirements.txt

# 运行程序
python3 openhex.py
```

## AI 配置

### 本地 AI (Ollama)
1. 安装 [Ollama](https://ollama.ai)
2. 拉取模型：`ollama pull qwen:7b`
3. 在 openhex 设置中配置

### 云端 AI
1. 获取 OpenAI 或 Anthropic API Key
2. 在 openhex AI 设置中配置

## 构建应用

```bash
# 构建 macOS 应用
bash build_app.sh

# 构建 DMG 安装包
bash build_app.sh --dmg
```

## 开发说明

### 选择模式实现

选择模式的核心逻辑位于 `src/ui/views/hex_view.py`：

1. **选择模式定义** (line ~742):
   - `SELECTION_CONTINUOUS`：连续选择
   - `SELECTION_COLUMN`：列选择
   - `SELECTION_BLOCK`：块选择
   - `SELECTION_ROW`：行选择

2. **高亮渲染** (line ~618):
   - 使用 `selection_range` 数据
   - 在 paint 事件中绘制高亮矩形
   - 考虑水平滚动偏移

3. **鼠标事件处理**:
   - `mousePressEvent`：记录选择起始位置
   - `mouseMoveEvent`：更新选择区域
   - `mouseReleaseEvent`：完成选择

### 测试

```bash
# 运行选择模式测试
python3 test_selection.py
```

## 更新日志

### v0.1 (2026-03-03)
- 实现四种选择模式：连续选择、列选择、块选择、行选择
- 优化高亮渲染，支持水平滚动
- 修复选择模式下的多个 bug
- 添加虚拟滚动支持大文件

## 许可证

MIT License
