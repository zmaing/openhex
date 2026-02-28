# HexForge 功能测试任务列表

## 一、文件操作

### 1.1 新建文件
- [ ] 点击 File → New 或 Ctrl+N 创建新文件
- [ ] 验证新文件标签页出现

### 1.2 打开文件
- [ ] 点击 File → Open 或 Ctrl+O 打开文件对话框
- [ ] 选择文件后验证文件内容显示
- [ ] 验证文件信息面板更新

### 1.3 打开文件夹
- [ ] 点击 File → Open Folder
- [ ] 验证左侧文件树显示文件夹内容

### 1.4 保存文件
- [ ] 修改文件内容后点击 File → Save 或 Ctrl+S
- [ ] 验证文件保存成功

### 1.5 另存为
- [ ] 点击 File → Save As 或 Ctrl+Shift+S
- [ ] 验证可以保存到新位置

### 1.6 关闭文件
- [ ] 点击 File → Close 或点击标签页关闭按钮
- [ ] 验证文件关闭

### 1.7 退出
- [ ] 点击 File → Exit 或 Ctrl+Q
- [ ] 验证程序退出

---

## 二、编辑操作

### 2.1 撤销/重做
- [ ] 点击 Edit → Undo 或 Ctrl+Z
- [ ] 点击 Edit → Redo 或 Ctrl+Y
- [ ] 验证撤销/重做功能正常

### 2.2 查找
- [ ] 点击 Edit → Find 或 Ctrl+F
- [ ] 验证查找对话框打开
- [ ] 输入搜索内容点击 Find Next
- [ ] 验证找到匹配项

### 2.3 替换
- [ ] 在查找对话框切换到 Replace 选项卡
- [ ] 输入查找内容和替换内容
- [ ] 点击 Replace 或 Replace All
- [ ] 验证替换功能正常

### 2.4 批量编辑
- [ ] 点击 Edit → Batch Edit → Fill
- [ ] 验证填充功能
- [ ] 测试 Increment/Decrement/Invert/Reverse

### 2.5 跳转到偏移
- [ ] 点击 Edit → Go To 或 Ctrl+G
- [ ] 输入偏移地址
- [ ] 验证光标跳转到指定位置

---

## 三、视图操作

### 3.1 排列模式
- [ ] 点击 View → Arrangement → Equal Frame
- [ ] 点击 View → Arrangement → Header Length
- [ ] 点击 View → Arrangement → Custom
- [ ] 验证显示模式切换

### 3.2 显示模式
- [ ] 点击 View → Display Mode → Hexadecimal
- [ ] 点击 View → Display Mode → Binary
- [ ] 点击 View → Display Mode → ASCII
- [ ] 点击 View → Display Mode → Octal
- [ ] 验证显示格式切换

### 3.3 面板显示
- [ ] 点击 View → File Tree 切换文件树显示
- [ ] 点击 View → AI Panel 切换 AI 面板显示
- [ ] 验证面板显示/隐藏

### 3.4 折叠功能
- [ ] 点击 View → Folding → Auto-Detect Regions
- [ ] 点击 View → Folding → Fold All
- [ ] 点击 View → Folding → Unfold All

---

## 四、导航操作

### 4.1 书签
- [ ] 点击 Go → Toggle Bookmark 或 Ctrl+F2 添加书签
- [ ] 点击 Go → Next Bookmark 或 F2 跳转到下一个书签
- [ ] 点击 Go → Previous Bookmark 或 Shift+F2 跳转到上一个书签

### 4.2 前进/后退
- [ ] 点击 Go → Back 或 Alt+Left
- [ ] 点击 Go → Forward 或 Alt+Right
- [ ] 验证导航历史

---

## 五、工具

### 5.1 文件比较
- [ ] 点击 Tools → Compare Files
- [ ] 验证比较功能

### 5.2 校验和计算
- [ ] 点击 Tools → Calculate Checksum
- [ ] 验证校验和计算

---

## 六、AI 功能

### 6.1 数据分析
- [ ] 打开文件
- [ ] 点击 AI → Analyze Data
- [ ] 验证 AI 分析结果

### 6.2 模式检测
- [ ] 点击 AI → Detect Patterns
- [ ] 验证模式检测功能

### 6.3 代码生成
- [ ] 点击 AI → Generate Parsing Code
- [ ] 验证代码生成

### 6.4 AI 设置
- [ ] 点击 AI → AI Settings
- [ ] 验证设置对话框

---

## 七、设置

### 7.1 语言切换
- [ ] 点击 Preferences → Language → English
- [ ] 重启程序验证英文界面
- [ ] 点击 Preferences → Language → 中文
- [ ] 重启程序验证中文界面

### 7.2 排列设置
- [ ] 点击 View → Arrangement → Custom
- [ ] 修改 Bytes per frame
- [ ] 修改 Header length
- [ ] 验证设置应用

---

## 八、其他

### 8.1 关于
- [ ] 点击 Help → About
- [ ] 验证关于对话框

### 8.2 多标签页
- [ ] 打开多个文件
- [ ] 验证标签页切换
- [ ] 验证关闭单个/全部标签页

### 8.3 状态栏
- [ ] 验证状态栏显示偏移地址
- [ ] 验证状态栏显示选区大小
- [ ] 验证状态栏显示文件大小

---

## 需要修复的问题

### 问题 1: 工具栏图标
- [ ] 彩色方块图标需要改为系统图标或更好的图标

### 问题 2: 国际化
- [ ] 部分对话框和面板未完全中文化
- [ ] 切换语言后需要完全重启才能生效

### 问题 3: 布局设置持久化
- [ ] 验证 bytes_per_row 设置在不同文件间持久化
- [ ] 验证重新打开文件后保持之前的设置

---

## 优先测试顺序

1. **基础功能** (必须能正常工作)
   - 打开/保存文件
   - 查找功能
   - 视图切换

2. **核心编辑**
   - 撤销/重做
   - 跳转功能

3. **界面**
   - 语言切换
   - 面板显示

4. **高级功能**
   - AI 功能
   - 折叠功能
   - 多视图
