# 数据编辑功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现完整的二进制数据编辑功能，包括键盘输入、编辑模式切换、复制/剪切/粘贴、新建文件。

**Architecture:** 在现有 MVC 架构基础上，扩展 HexView 的键盘事件处理，添加 ClipboardManager 管理剪贴板操作，通过 UndoStack 记录所有编辑操作支持撤销/重做。

**Tech Stack:** PyQt6, Python 3.10+

---

## Task 1: 编辑模式切换（覆盖/插入）

**Files:**
- Modify: `src/ui/views/hex_view.py`
- Modify: `src/ui/main_window.py`

**Step 1: 在 HexView 中添加编辑模式状态**

在 `HexView` 类的 `__init__` 方法中添加编辑模式状态变量：

```python
# Edit mode: 'overwrite' or 'insert'
self._edit_mode = 'overwrite'  # Default to overwrite mode
```

**Step 2: 添加编辑模式切换方法**

在 `HexView` 类中添加：

```python
def toggle_edit_mode(self):
    """Toggle between overwrite and insert mode."""
    self._edit_mode = 'insert' if self._edit_mode == 'overwrite' else 'overwrite'
    # Emit signal for status bar update
    if hasattr(self, 'edit_mode_changed'):
        self.edit_mode_changed.emit(self._edit_mode)
    return self._edit_mode

def get_edit_mode(self) -> str:
    """Get current edit mode."""
    return self._edit_mode
```

**Step 3: 添加编辑模式切换信号**

在 `HexView` 类的信号定义区域添加：

```python
edit_mode_changed = pyqtSignal(str)  # 'overwrite' or 'insert'
```

**Step 4: 在 keyPressEvent 中处理 Insert 键**

修改 `keyPressEvent` 方法，添加 Insert 键处理：

```python
def keyPressEvent(self, event):
    """Handle key press."""
    # Handle Insert key for mode toggle
    if event.key() == Qt.Key.Key_Insert:
        self.toggle_edit_mode()
        return

    # Let parent handle most keys
    super().keyPressEvent(event)

    # Emit cursor moved signal
    offset = self.get_offset_at_cursor()
    self.cursor_moved.emit(offset)
```

**Step 5: 在主窗口状态栏显示编辑模式**

在 `HexEditorMainWindow` 类中添加状态栏更新：

```python
def _update_edit_mode_display(self, mode: str):
    """Update status bar with current edit mode."""
    # Find or create edit mode label in status bar
    if not hasattr(self, '_edit_mode_label'):
        self._edit_mode_label = self.statusBar().findChild QLabel, "edit_mode_label")
        if not self._edit_mode_label:
            self._edit_mode_label = QLabel("OVR")
            self._edit_mode_label.setObjectName("edit_mode_label")
            self.statusBar().addPermanentWidget(self._edit_mode_label)

    self._edit_mode_label.setText("INS" if mode == 'insert' else "OVR")
```

**Step 6: 连接信号**

在主窗口的 `_connect_signals` 方法中添加：

```python
# Connect edit mode change signal
if hasattr(self._hex_view, 'edit_mode_changed'):
    self._hex_view.edit_mode_changed.connect(self._update_edit_mode_display)
```

**Step 7: 测试验证**

1. 启动程序，验证状态栏显示 "OVR"
2. 按 Insert 键，验证状态栏切换为 "INS"
3. 再次按 Insert 键，验证切换回 "OVR"
4. 打开文件，验证模式不影响数据显示

**Step 8: Commit**

```bash
git add src/ui/views/hex_view.py src/ui/main_window.py
git commit -m "feat: 添加编辑模式切换功能（覆盖/插入）

- Insert 键切换覆盖和插入模式
- 状态栏显示当前模式 OVR/INS
- 添加 edit_mode_changed 信号

Co-Authored-By: Claude (glm-5) <noreply@anthropic.com>"
```

---

## Task 2: 键盘输入 - 十六进制区域

**Files:**
- Modify: `src/ui/views/hex_view.py`
- Modify: `src/models/file_handle.py`

**Step 1: 添加光标 nibble（半字节）支持**

在 `HexView` 类中添加：

```python
def __init__(self, parent=None):
    # ... existing code ...
    # Nibble position within current byte (0=high, 1=low)
    self._nibble_pos = 0  # 0 = high nibble, 1 = low nibble
    self._cursor_byte_offset = 0  # Current byte offset in file
```

**Step 2: 添加获取当前光标位置方法**

```python
def get_cursor_position(self) -> tuple:
    """Get current cursor position as (byte_offset, nibble_pos, column)."""
    index = self.currentIndex()
    if not index.isValid():
        return (0, 0, 0)
    return (self._cursor_byte_offset, self._nibble_pos, index.column())
```

**Step 3: 添加十六进制输入处理方法**

```python
def _handle_hex_input(self, char: str):
    """Handle hex character input in hex column."""
    # Validate input
    if char.upper() not in '0123456789ABCDEF':
        return

    char = char.upper()
    byte_offset = self._cursor_byte_offset
    nibble = self._nibble_pos

    # Get current byte value
    if byte_offset >= self._model._file_size:
        # Extend file if in insert mode or at end
        if self._edit_mode == 'insert' or byte_offset == self._model._file_size:
            # Add a new byte
            self._file_handle.insert(byte_offset, bytes([0]))
        else:
            return

    # Read current byte
    current_byte = self._model._data[byte_offset]

    # Calculate new byte value
    nibble_value = int(char, 16)
    if nibble == 0:
        # High nibble
        new_byte = (nibble_value << 4) | (current_byte & 0x0F)
    else:
        # Low nibble
        new_byte = (current_byte & 0xF0) | nibble_value

    # Write the byte
    self._file_handle.write(byte_offset, bytes([new_byte]))

    # Move cursor
    if nibble == 0:
        # Move to low nibble
        self._nibble_pos = 1
    else:
        # Move to next byte's high nibble
        self._nibble_pos = 0
        self._cursor_byte_offset = byte_offset + 1
        # Move selection to next row if needed
        self._move_cursor_to_byte(self._cursor_byte_offset)

    # Refresh display
    self._model.set_data(self._file_handle.read(0, self._file_handle.file_size))
    self.viewport().update()
```

**Step 4: 添加光标移动到指定字节方法**

```python
def _move_cursor_to_byte(self, byte_offset: int):
    """Move cursor to specified byte offset."""
    bytes_per_row = self._model._bytes_per_row
    row = byte_offset // bytes_per_row
    # Set current index
    index = self._model.index(row, 0)
    self.setCurrentIndex(index)
    self.scrollTo(index)
```

**Step 5: 修改 keyPressEvent 处理字符输入**

```python
def keyPressEvent(self, event):
    """Handle key press."""
    # Handle Insert key for mode toggle
    if event.key() == Qt.Key.Key_Insert:
        self.toggle_edit_mode()
        return

    # Handle hex input
    if event.text() and event.text()[0].isalnum():
        char = event.text()[0]
        index = self.currentIndex()
        if index.isValid() and index.column() == 0:
            # In hex column
            self._handle_hex_input(char)
            return

    # Handle backspace
    if event.key() == Qt.Key.Key_Backspace:
        self._handle_backspace()
        return

    # Let parent handle most keys
    super().keyPressEvent(event)

    # Emit cursor moved signal
    offset = self.get_offset_at_cursor()
    self.cursor_moved.emit(offset)
```

**Step 6: 添加退格键处理**

```python
def _handle_backspace(self):
    """Handle backspace key."""
    if self._nibble_pos == 1:
        # Move to high nibble
        self._nibble_pos = 0
    elif self._cursor_byte_offset > 0:
        # Move to previous byte's low nibble
        self._cursor_byte_offset -= 1
        self._nibble_pos = 1
        self._move_cursor_to_byte(self._cursor_byte_offset)
    self.viewport().update()
```

**Step 7: 更新鼠标点击时计算字节偏移**

在 `mousePressEvent` 中添加：

```python
# Update cursor byte offset
self._cursor_byte_offset = self._calculate_cursor_byte_offset(event.pos())
self._nibble_pos = 0  # Reset to high nibble on click
```

**Step 8: 测试验证**

1. 打开测试文件
2. 点击十六进制区域第一个字节
3. 键入 "A"，验证高4位变为 A
4. 键入 "B"，验证完整字节变为 AB，光标移到下一字节
5. 键入 "0123456789ABCDEF"，验证正常输入
6. 键入 "GHIJK"，验证无响应
7. 按退格键，验证光标回退
8. 按 Insert 切换到插入模式，验证末尾输入时文件增大

**Step 9: Commit**

```bash
git add src/ui/views/hex_view.py
git commit -m "feat: 实现十六进制区域键盘输入

- 支持 0-9, A-F 输入
- 支持 nibble（半字节）级别光标定位
- 支持退格键删除
- 支持覆盖和插入模式

Co-Authored-By: Claude (glm-5) <noreply@anthropic.com>"
```

---

## Task 3: 键盘输入 - ASCII 区域

**Files:**
- Modify: `src/ui/views/hex_view.py`

**Step 1: 添加 ASCII 输入处理方法**

```python
def _handle_ascii_input(self, char: str):
    """Handle ASCII character input in ASCII column."""
    # Only accept ASCII characters (32-126)
    byte_value = ord(char)
    if byte_value < 32 or byte_value > 126:
        return

    byte_offset = self._cursor_byte_offset

    # Handle file size
    if byte_offset >= self._model._file_size:
        if self._edit_mode == 'insert' or byte_offset == self._model._file_size:
            self._file_handle.insert(byte_offset, bytes([0]))
        else:
            return

    # Write the character's byte value
    self._file_handle.write(byte_offset, bytes([byte_value]))

    # Move to next byte
    self._cursor_byte_offset = byte_offset + 1
    self._nibble_pos = 0
    self._move_cursor_to_byte(self._cursor_byte_offset)

    # Refresh display
    self._model.set_data(self._file_handle.read(0, self._file_handle.file_size))
    self.viewport().update()
```

**Step 2: 修改 keyPressEvent 支持 ASCII 列输入**

```python
def keyPressEvent(self, event):
    """Handle key press."""
    # Handle Insert key for mode toggle
    if event.key() == Qt.Key.Key_Insert:
        self.toggle_edit_mode()
        return

    # Handle text input
    if event.text():
        char = event.text()[0]
        index = self.currentIndex()
        if index.isValid():
            if index.column() == 0:
                # In hex column
                self._handle_hex_input(char)
                return
            elif index.column() == 1:
                # In ASCII column
                self._handle_ascii_input(char)
                return

    # Handle backspace
    if event.key() == Qt.Key.Key_Backspace:
        self._handle_backspace()
        return

    # Let parent handle most keys
    super().keyPressEvent(event)

    # Emit cursor moved signal
    offset = self.get_offset_at_cursor()
    self.cursor_moved.emit(offset)
```

**Step 3: 测试验证**

1. 打开测试文件
2. 点击 ASCII 区域
3. 键入 "Hello"，验证十六进制区域显示 "48 65 6C 6C 6F"
4. 键入中文字符，验证无响应
5. 在 ASCII 区域按退格键，验证删除字符

**Step 4: Commit**

```bash
git add src/ui/views/hex_view.py
git commit -m "feat: 实现 ASCII 区域键盘输入

- 支持可打印 ASCII 字符输入（32-126）
- 自动转换为对应字节值
- 光标自动移动到下一字节

Co-Authored-By: Claude (glm-5) <noreply@anthropic.com>"
```

---

## Task 4: 新建文件

**Files:**
- Modify: `src/models/document.py`
- Modify: `src/ui/main_window.py`

**Step 1: 在 DocumentModel 中添加新建文件方法**

```python
def create_new_document(self) -> FileHandle:
    """Create a new empty document."""
    # Generate unique title
    self._new_file_counter = getattr(self, '_new_file_counter', 0) + 1
    title = f"Untitled-{self._new_file_counter}"

    # Create empty file handle
    file_handle = FileHandle()
    file_handle._file_path = None
    file_handle._file_name = title
    file_handle._state = FileState.NEW
    file_handle._data = bytearray()
    file_handle._file_size = 0

    # Add to documents
    self._documents.append(file_handle)
    self.document_opened.emit(file_handle)

    return file_handle
```

**Step 2: 在 FileHandle 中确保支持空文件**

检查 `FileHandle` 类是否支持空数据，必要时添加：

```python
def __init__(self):
    # ... existing code ...
    self._data = bytearray()
    self._file_size = 0
    self._state = FileState.NEW
```

**Step 3: 在主窗口添加新建文件菜单处理**

```python
def _new_file(self):
    """Create a new empty file."""
    doc = self._document_model.create_new_document()
    self._switch_to_document(doc)
    # Update tab
    self._add_tab_for_document(doc)
```

**Step 4: 连接 Ctrl+N 快捷键**

确保菜单中 File → New 的快捷键为 Ctrl+N

**Step 5: 测试验证**

1. 按 Ctrl+N，验证新标签页创建
2. 验证标签标题为 "Untitled-1"
3. 验证文件大小为 0
4. 直接键入数据，验证文件大小增加
5. 创建多个新文件，验证编号递增
6. 按 Ctrl+S 保存，验证弹出"另存为"对话框

**Step 6: Commit**

```bash
git add src/models/document.py src/ui/main_window.py
git commit -m "feat: 实现新建文件功能

- Ctrl+N 创建空白文件
- 自动生成 Untitled-N 标题
- 支持直接输入数据
- 保存时弹出另存为对话框

Co-Authored-By: Claude (glm-5) <noreply@anthropic.com>"
```

---

## Task 5: 复制功能

**Files:**
- Create: `src/utils/clipboard_manager.py`
- Modify: `src/ui/main_window.py`
- Modify: `src/ui/views/hex_view.py`

**Step 1: 创建 ClipboardManager 类**

```python
# src/utils/clipboard_manager.py
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject

class ClipboardManager(QObject):
    """Manage clipboard operations for hex data."""

    @staticmethod
    def copy_hex(data: bytes) -> str:
        """Format bytes as hex string with spaces."""
        return ' '.join(f'{b:02X}' for b in data)

    @staticmethod
    def copy_binary(data: bytes) -> str:
        """Format bytes as binary string."""
        return ' '.join(f'{b:08b}' for b in data)

    @staticmethod
    def copy_octal(data: bytes) -> str:
        """Format bytes as octal string."""
        return ' '.join(f'{b:03o}' for b in data)

    @staticmethod
    def copy_ascii(data: bytes) -> str:
        """Format bytes as ASCII string."""
        return ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)

    @staticmethod
    def copy_to_clipboard(text: str):
        """Copy text to system clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    @staticmethod
    def get_from_clipboard() -> str:
        """Get text from system clipboard."""
        clipboard = QApplication.clipboard()
        return clipboard.text()
```

**Step 2: 在 HexView 中添加获取选区数据方法**

```python
def get_selection_data(self) -> bytes:
    """Get bytes from current selection."""
    if not self._model._selection_ranges:
        return b''

    # Get all selected bytes
    all_bytes = []
    for start, end in self._model._selection_ranges:
        for offset in range(start, end + 1):
            if offset < self._model._file_size:
                all_bytes.append(self._model._data[offset])

    return bytes(all_bytes)
```

**Step 3: 在 HexView 中添加复制方法**

```python
def copy_selection(self):
    """Copy selection to clipboard based on current column and display mode."""
    from src.utils.clipboard_manager import ClipboardManager

    data = self.get_selection_data()
    if not data:
        return

    index = self.currentIndex()
    if index.column() == 1:
        # ASCII column - copy as text
        text = ClipboardManager.copy_ascii(data)
    else:
        # Hex column - format based on display mode
        mode = self._model._display_mode
        if mode == 'binary':
            text = ClipboardManager.copy_binary(data)
        elif mode == 'octal':
            text = ClipboardManager.copy_octal(data)
        else:
            text = ClipboardManager.copy_hex(data)

    ClipboardManager.copy_to_clipboard(text)
```

**Step 4: 在主窗口添加复制菜单**

确保 Edit → Copy 菜单项存在，快捷键 Ctrl+C，连接到：

```python
def _copy(self):
    """Copy selection to clipboard."""
    if hasattr(self._hex_view, 'copy_selection'):
        self._hex_view.copy_selection()
```

**Step 5: 测试验证**

1. 打开测试文件，选中几个字节
2. 按 Ctrl+C
3. 粘贴到文本编辑器，验证格式为 "00 01 02 FF"
4. 切换到二进制显示模式，复制，验证格式为二进制
5. 选中 ASCII 区域字符，复制，验证为纯文本

**Step 6: Commit**

```bash
git add src/utils/clipboard_manager.py src/ui/main_window.py src/ui/views/hex_view.py
git commit -m "feat: 实现复制功能

- 根据选中区域和显示模式智能选择格式
- 十六进制格式: \"00 01 02 FF\"
- 二进制格式: \"00000000 00000001\"
- ASCII 格式: 原始文本
- 快捷键 Ctrl+C

Co-Authored-By: Claude (glm-5) <noreply@anthropic.com>"
```

---

## Task 6: 粘贴功能

**Files:**
- Modify: `src/utils/clipboard_manager.py`
- Modify: `src/ui/main_window.py`
- Modify: `src/ui/views/hex_view.py`

**Step 1: 在 ClipboardManager 中添加格式识别**

```python
import re

@staticmethod
def parse_hex_string(text: str) -> bytes:
    """Parse hex string to bytes. Supports formats:
    - \"00 01 02 FF\"
    - \"00FF\"
    - \"00, 01, FF\"
    """
    # Remove common separators
    text = text.replace(',', ' ').replace(':', ' ')
    # Extract hex pairs
    hex_chars = re.findall(r'[0-9A-Fa-f]{2}', text)
    if len(hex_chars) * 2 != len(text.replace(' ', '').replace(',', '')):
        # Not pure hex
        return None
    return bytes(int(h, 16) for h in hex_chars)

@staticmethod
def parse_clipboard() -> bytes:
    """Parse clipboard content and return bytes."""
    text = ClipboardManager.get_from_clipboard()
    if not text:
        return b''

    # Try hex format first
    result = ClipboardManager.parse_hex_string(text)
    if result is not None:
        return result

    # Try as ASCII text
    try:
        return text.encode('ascii')
    except:
        return b''
```

**Step 2: 在 HexView 中添加粘贴方法**

```python
def paste_from_clipboard(self):
    """Paste clipboard content at cursor position."""
    from src.utils.clipboard_manager import ClipboardManager

    data = ClipboardManager.parse_clipboard()
    if not data:
        return

    byte_offset = self._cursor_byte_offset

    if self._edit_mode == 'overwrite':
        # Overwrite mode
        # Check if we have enough space
        end_offset = byte_offset + len(data)
        if end_offset > self._model._file_size:
            # Extend file
            extension = end_offset - self._model._file_size
            self._file_handle.insert(self._model._file_size, bytes(extension))
        self._file_handle.write(byte_offset, data)
    else:
        # Insert mode
        self._file_handle.insert(byte_offset, data)

    # Move cursor to end of pasted data
    self._cursor_byte_offset = byte_offset + len(data)
    self._nibble_pos = 0
    self._move_cursor_to_byte(self._cursor_byte_offset)

    # Refresh display
    self._model.set_data(self._file_handle.read(0, self._file_handle.file_size))
    self.viewport().update()
```

**Step 3: 在主窗口添加粘贴菜单**

确保 Edit → Paste 菜单项存在，快捷键 Ctrl+V，连接到：

```python
def _paste(self):
    """Paste from clipboard."""
    if hasattr(self._hex_view, 'paste_from_clipboard'):
        self._hex_view.paste_from_clipboard()
```

**Step 4: 测试验证**

1. 复制 "00 01 02 FF" 到剪贴板
2. 在编辑器中粘贴，验证正确解析为 4 个字节
3. 复制 "Hello" 到剪贴板，粘贴，验证正确转换
4. 在插入模式粘贴，验证数据被插入
5. 在覆盖模式粘贴，验证数据被覆盖
6. 粘贴非法格式，验证无操作

**Step 5: Commit**

```bash
git add src/utils/clipboard_manager.py src/ui/main_window.py src/ui/views/hex_view.py
git commit -m "feat: 实现粘贴功能

- 自动识别十六进制字符串格式
- 支持 ASCII 文本粘贴
- 根据编辑模式选择覆盖或插入
- 快捷键 Ctrl+V

Co-Authored-By: Claude (glm-5) <noreply@anthropic.com>"
```

---

## Task 7: 剪切功能

**Files:**
- Modify: `src/ui/main_window.py`
- Modify: `src/ui/views/hex_view.py`

**Step 1: 在 HexView 中添加剪切方法**

```python
def cut_selection(self):
    """Cut selection to clipboard."""
    # First copy
    self.copy_selection()

    # Then delete selection
    if not self._model._selection_ranges:
        return

    # Delete from end to start to preserve offsets
    sorted_ranges = sorted(self._model._selection_ranges, key=lambda r: r[0], reverse=True)
    for start, end in sorted_ranges:
        length = end - start + 1
        self._file_handle.delete(start, length)

    # Clear selection
    self._model._selection_ranges = []
    self._cursor_byte_offset = sorted_ranges[-1][0] if sorted_ranges else 0

    # Refresh display
    self._model.set_data(self._file_handle.read(0, self._file_handle.file_size))
    self.viewport().update()
```

**Step 2: 在主窗口添加剪切菜单**

确保 Edit → Cut 菜单项存在，快捷键 Ctrl+X，连接到：

```python
def _cut(self):
    """Cut selection to clipboard."""
    if hasattr(self._hex_view, 'cut_selection'):
        self._hex_view.cut_selection()
```

**Step 3: 测试验证**

1. 选中一段数据，按 Ctrl+X
2. 验证选区数据被删除
3. 粘贴到其他位置，验证数据完整
4. 撤销操作，验证数据恢复

**Step 4: Commit**

```bash
git add src/ui/main_window.py src/ui/views/hex_view.py
git commit -m "feat: 实现剪切功能

- 复制选中数据到剪贴板
- 删除选区数据
- 快捷键 Ctrl+X
- 支持撤销

Co-Authored-By: Claude (glm-5) <noreply@anthropic.com>"
```

---

## 完成后更新 TODO.md

每个任务完成后，更新 TODO.md 中对应功能的状态为 "✅ 已完成"。

---

## 验收清单

- [ ] Insert 键切换覆盖/插入模式，状态栏显示 OVR/INS
- [ ] 十六进制区域支持 0-9, A-F 输入
- [ ] ASCII 区域支持可打印字符输入
- [ ] 复制根据区域和显示模式智能选择格式
- [ ] 粘贴自动识别十六进制/ASCII 格式
- [ ] 剪切 = 复制 + 删除
- [ ] 新建文件支持直接输入数据
- [ ] 所有编辑操作支持撤销/重做
