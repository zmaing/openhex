# HexForge 功能测试清单

## 一、文件操作 (File Menu)

### 1.1 新建文件
- [ ] `File → New` 或 `Ctrl+N` - 创建新空白文件
- [ ] 验证新标签页出现，显示空白内容
- [ ] 可以编辑新文件

### 1.2 打开文件
- [ ] `File → Open` 或 `Ctrl+O` - 打开文件对话框
- [ ] 选择二进制文件
- [ ] 验证文件内容正确显示在 Hex View 中
- [ ] 验证文件信息面板更新（名称、大小、类型）

### 1.3 打开文件夹
- [ ] `File → Open Folder` - 打开文件夹对话框
- [ ] 验证左侧文件树显示文件夹内容
- [ ] 可以点击文件树中的文件打开

### 1.4 保存文件
- [ ] 修改文件内容后 `File → Save` 或 `Ctrl+S`
- [ ] 验证文件保存成功
- [ ] 验证保存后内容一致

### 1.5 另存为
- [ ] `File → Save As` 或 `Ctrl+Shift+S`
- [ ] 选择新保存位置
- [ ] 验证文件保存到新位置

### 1.6 关闭文件
- [ ] `File → Close` 或点击标签页 × 按钮
- [ ] 验证文件关闭
- [ ] 提示保存未保存的修改

### 1.7 退出
- [ ] `File → Exit` 或 `Ctrl+Q`
- [ ] 验证程序退出

---

## 二、编辑操作 (Edit Menu)

### 2.1 撤销/重做
- [ ] `Edit → Undo` 或 `Ctrl+Z` - 撤销
- [ ] `Edit → Redo` 或 `Ctrl+Y` - 重做
- [ ] 验证撤销/重做功能正常

### 2.2 查找
- [ ] `Edit → Find` 或 `Ctrl+F` - 打开查找对话框
- [ ] 输入搜索内容（Hex 模式）
- [ ] 输入搜索内容（Text 模式）
- [ ] 输入搜索内容（Regex 模式）
- [ ] 点击 `Find Next` - 查找下一个
- [ ] 点击 `Find Previous` - 查找上一个
- [ ] 验证找到匹配项并高亮显示
- [ ] 验证未找到时提示

### 2.3 替换
- [ ] 在查找对话框切换到 `Replace` 选项卡
- [ ] 输入查找内容
- [ ] 输入替换内容
- [ ] 点击 `Replace` - 替换当前
- [ ] 点击 `Replace All` - 替换全部
- [ ] 验证替换功能正常
- [ ] 验证取消替换时提示

### 2.4 批量编辑
- [ ] `Edit → Batch Edit → Fill` - 填充
- [ ] `Edit → Batch Edit → Increment` - 递增
- [ ] `Edit → Batch Edit → Decrement` - 递减
- [ ] `Edit → Batch Edit → Invert` - 取反
- [ ] `Edit → Batch Edit → Reverse` - 反转
- [ ] 验证批量编辑功能正常

### 2.5 跳转到偏移
- [ ] `Edit → Go To` 或 `Ctrl+G` - 打开跳转对话框
- [ ] 输入十进制偏移地址
- [ ] 输入十六进制偏移地址（带 0x 前缀）
- [ ] 验证光标跳转到指定位置

---

## 三、视图操作 (View Menu)

### 3.1 排列模式 (Arrangement)
- [ ] `View → Arrangement → Equal Frame` - 等长帧模式
- [ ] `View → Arrangement → Header Length` - 头长度模式
- [ ] `View → Arrangement → Custom` - 自定义模式
- [ ] 打开自定义对话框设置参数
- [ ] 验证显示模式切换正常

### 3.2 显示模式 (Display Mode)
- [ ] `View → Display Mode → Hexadecimal` - 十六进制
- [ ] `View → Display Mode → Binary` - 二进制
- [ ] `View → Display Mode → ASCII` - ASCII 文本
- [ ] `View → Display Mode → Octal` - 八进制
- [ ] 验证显示格式切换正常

### 3.3 面板显示
- [ ] `View → File Tree` - 切换文件树显示
- [ ] `View → AI Panel` - 切换 AI 面板显示
- [ ] 验证面板显示/隐藏正常

### 3.4 折叠功能 (Folding)
- [ ] `View → Folding → Auto-Detect Regions` - 自动检测区域
- [ ] `View → Folding → Fold All` - 全部折叠
- [ ] `View → Folding → Unfold All` - 全部展开
- [ ] 验证折叠功能正常

### 3.5 多视图 (Multi-View)
- [ ] `View → Multi-View → New View` - 新建视图
- [ ] `View → Multi-View → Sync Scroll` - 同步滚动
- [ ] `View → Multi-View → Sync Cursor` - 同步光标
- [ ] 验证多视图功能正常

---

## 四、导航操作 (Go Menu)

### 4.1 书签
- [ ] `Go → Toggle Bookmark` 或 `Ctrl+F2` - 切换书签
- [ ] `Go → Next Bookmark` 或 `F2` - 下一个书签
- [ ] `Go → Previous Bookmark` 或 `Shift+F2` - 上一个书签
- [ ] 验证书签功能正常

### 4.2 前进/后退
- [ ] `Go → Back` 或 `Alt+Left` - 后退
- [ ] `Go → Forward` 或 `Alt+Right` - 前进
- [ ] 验证导航历史功能正常

---

## 五、工具 (Tools Menu)

### 5.1 文件比较
- [ ] `Tools → Compare Files` - 比较两个文件
- [ ] 验证比较功能正常

### 5.2 校验和计算
- [ ] `Tools → Calculate Checksum` - 计算校验和
- [ ] 验证 MD5、SHA1、SHA256 等校验和正确

---

## 六、AI 功能 (AI Menu)

### 6.1 数据分析
- [ ] `AI → Analyze Data` - 分析选中数据
- [ ] 验证 AI 分析结果

### 6.2 模式检测
- [ ] `AI → Detect Patterns` - 检测数据模式
- [ ] 验证模式检测功能

### 6.3 代码生成
- [ ] `AI → Generate Parsing Code` - 生成解析代码
- [ ] 验证代码生成功能

### 6.4 AI 设置
- [ ] `AI → AI Settings` - AI 设置对话框
- [ ] 验证设置可以保存

---

## 七、设置 (Preferences Menu)

### 7.1 语言切换
- [ ] `Preferences → Language → English` - 切换到英语
- [ ] 重启程序验证英文界面
- [ ] `Preferences → Language → 中文` - 切换到中文
- [ ] 重启程序验证中文界面
- [ ] 验证菜单显示中文
- [ ] 验证对话框显示中文

### 7.2 排列设置持久化
- [ ] 打开文件
- [ ] 修改 `View → Arrangement → Custom` 中的 Bytes per frame
- [ ] 关闭文件
- [ ] 重新打开同一文件
- [ ] 验证设置保持

---

## 八、帮助 (Help Menu)

### 8.1 关于
- [ ] `Help → About` - 关于对话框
- [ ] 验证版本信息正确

---

## 九、界面元素

### 9.1 工具栏
- [ ] 工具栏图标显示正常
- [ ] 工具栏按钮功能正常

### 9.2 状态栏
- [ ] 显示偏移地址
- [ ] 显示选区大小
- [ ] 显示文件大小

### 9.3 面板
- [ ] 文件信息面板正确显示文件信息
- [ ] 数据检查器面板正确显示数据值

---

## 测试优先级

### P0 - 必须正常工作
1. [ ] 打开文件
2. [ ] 保存文件
3. [ ] 查找功能
4. [ ] 视图模式切换
5. [ ] 十六进制显示正确

### P1 - 重要功能
1. [ ] 跳转功能
2. [ ] 撤销/重做
3. [ ] 多标签页
4. [ ] 排列模式切换

### P2 - 辅助功能
1. [ ] AI 功能
2. [ ] 文件比较
3. [ ] 折叠功能
4. [ ] 多视图
