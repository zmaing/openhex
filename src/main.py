"""
HexForge Main Window

Main application window with menu bar, toolbar, and central widget.
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QStatusBar, QToolBar, QMenuBar, QMenu)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QActionGroup

import os

from .ui.main_window import HexEditorMainWindow
from .core.data_model import ArrangementMode
from .utils.i18n import tr


class HexForgeMainWindow(QMainWindow):
    """Main window for HexForge application."""

    def __init__(self):
        super().__init__()
        self._init_window()
        self._init_menus()
        self._init_toolbars()
        self._init_central_widget()
        self._init_status_bar()

    def _init_window(self):
        """Initialize window properties."""
        self.setWindowTitle("HexForge - AI Enhanced Binary Editor")
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        # Center window on screen
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

    def _init_menus(self):
        """Initialize menu bar."""
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu(tr("menu_file"))

        # New file
        new_action = QAction(tr("menu_new"), self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.setStatusTip("Create a new file" if self._get_current_language() == "en" else "创建新文件")
        new_action.triggered.connect(self._on_new_file)
        file_menu.addAction(new_action)

        # Open file
        open_action = QAction(tr("menu_open"), self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.setStatusTip("Open a file" if self._get_current_language() == "en" else "打开文件")
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)

        # Open folder (file browser)
        open_folder_action = QAction(tr("menu_open_folder"), self)
        open_folder_action.setStatusTip("Open a folder in the file browser" if self._get_current_language() == "en" else "在文件浏览器中打开文件夹")
        open_folder_action.triggered.connect(self._on_open_folder)
        file_menu.addAction(open_folder_action)

        file_menu.addSeparator()

        # Save
        save_action = QAction(tr("menu_save"), self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setStatusTip("Save file" if self._get_current_language() == "en" else "保存文件")
        save_action.triggered.connect(self._on_save_file)
        file_menu.addAction(save_action)

        # Save As
        save_as_action = QAction(tr("menu_save_as"), self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.setStatusTip("Save file as" if self._get_current_language() == "en" else "另存为")
        save_as_action.triggered.connect(self._on_save_file_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        # Close
        close_action = QAction(tr("menu_close"), self)
        close_action.setShortcut(QKeySequence.StandardKey.Close)
        close_action.setStatusTip("Close current file" if self._get_current_language() == "en" else "关闭当前文件")
        close_action.triggered.connect(self._on_close_file)
        file_menu.addAction(close_action)

        # Exit
        exit_action = QAction(tr("menu_exit"), self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.setStatusTip("Exit application" if self._get_current_language() == "en" else "退出应用")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit Menu
        edit_menu = menubar.addMenu(tr("menu_edit"))

        # Undo
        undo_action = QAction(tr("menu_undo"), self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.setStatusTip("Undo last action" if self._get_current_language() == "en" else "撤销上一步操作")
        undo_action.triggered.connect(self._on_undo)
        edit_menu.addAction(undo_action)

        # Redo
        redo_action = QAction(tr("menu_redo"), self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.setStatusTip("Redo last action" if self._get_current_language() == "en" else "重做上一步操作")
        redo_action.triggered.connect(self._on_redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        # Cut/Copy/Paste would be enabled if we implement clipboard
        # For now, they are disabled as hex editing is complex

        # Find
        find_action = QAction(tr("menu_find"), self)
        find_action.setShortcut(QKeySequence.StandardKey.Find)
        find_action.setStatusTip("Find in file" if self._get_current_language() == "en" else "在文件中查找")
        find_action.triggered.connect(self._on_find)
        edit_menu.addAction(find_action)

        # Natural Language Search
        nl_search_action = QAction(tr("menu_ai_search"), self)
        nl_search_action.setShortcut("Ctrl+Shift+F")
        nl_search_action.setStatusTip("Search using natural language" if self._get_current_language() == "en" else "使用自然语言搜索")
        nl_search_action.triggered.connect(self._on_nl_search)
        edit_menu.addAction(nl_search_action)

        # Replace
        replace_action = QAction(tr("menu_replace"), self)
        replace_action.setShortcut(QKeySequence.StandardKey.Replace)
        replace_action.setStatusTip("Replace in file" if self._get_current_language() == "en" else "在文件中替换")
        replace_action.triggered.connect(self._on_replace)
        edit_menu.addAction(replace_action)

        # Batch Edit submenu
        batch_menu = edit_menu.addMenu(self._tr("menu_batch_edit"))

        fill_action = QAction(self._tr("menu_fill"), self)
        fill_action.setShortcut("Ctrl+Shift+F")
        fill_action.setStatusTip("Fill selection with pattern" if self._get_current_language() == "en" else "用模式填充选区")
        fill_action.triggered.connect(self._on_batch_fill)
        batch_menu.addAction(fill_action)

        increment_action = QAction(self._tr("menu_increment"), self)
        increment_action.setShortcut("Ctrl+=")
        increment_action.setStatusTip("Increment bytes in selection" if self._get_current_language() == "en" else "递增选区中的字节")
        increment_action.triggered.connect(self._on_batch_increment)
        batch_menu.addAction(increment_action)

        decrement_action = QAction(self._tr("menu_decrement"), self)
        decrement_action.setShortcut("Ctrl+-")
        decrement_action.setStatusTip("Decrement bytes in selection" if self._get_current_language() == "en" else "递减选区中的字节")
        decrement_action.triggered.connect(self._on_batch_decrement)
        batch_menu.addAction(decrement_action)

        invert_action = QAction(self._tr("menu_invert"), self)
        invert_action.setStatusTip("Invert bits in selection" if self._get_current_language() == "en" else "取反选区中的位")
        invert_action.triggered.connect(self._on_batch_invert)
        batch_menu.addAction(invert_action)

        reverse_action = QAction(self._tr("menu_reverse"), self)
        reverse_action.setStatusTip("Reverse byte order in selection" if self._get_current_language() == "en" else "反转选区中的字节顺序")
        reverse_action.triggered.connect(self._on_batch_reverse)
        batch_menu.addAction(reverse_action)

        edit_menu.addSeparator()

        # Go To
        goto_action = QAction(self._tr("menu_goto"), self)
        goto_action.setShortcut("Ctrl+G")
        goto_action.setStatusTip("Go to offset" if self._get_current_language() == "en" else "跳转到偏移")
        goto_action.triggered.connect(self._on_goto)
        edit_menu.addAction(goto_action)

        # View Menu
        view_menu = menubar.addMenu(self._tr("menu_view"))

        # Arrangement modes
        arrange_menu = view_menu.addMenu(self._tr("menu_arrangement"))

        equal_frame_action = QAction(self._tr("menu_equal_frame"), self)
        equal_frame_action.setCheckable(True)
        # Use QActionGroup for mutually exclusive actions
        arrange_group = QActionGroup(self)

        equal_frame_action = QAction(self._tr("menu_equal_frame"), self)
        equal_frame_action.setCheckable(True)
        equal_frame_action.setChecked(True)
        equal_frame_action.triggered.connect(lambda: self._on_arrangement_changed("equal_frame"))
        arrange_group.addAction(equal_frame_action)
        arrange_menu.addAction(equal_frame_action)

        header_length_action = QAction(self._tr("menu_header_length"), self)
        header_length_action.setCheckable(True)
        header_length_action.triggered.connect(lambda: self._on_arrangement_changed("header_length"))
        arrange_group.addAction(header_length_action)
        arrange_menu.addAction(header_length_action)

        custom_action = QAction(self._tr("menu_custom"), self)
        custom_action.triggered.connect(self._on_custom_arrangement)
        arrange_menu.addAction(custom_action)

        # Store reference for updating
        self._arrange_equal_action = equal_frame_action
        self._arrange_header_action = header_length_action

        # Display modes
        display_menu = view_menu.addMenu(self._tr("menu_display_mode"))

        hex_action = QAction(self._tr("menu_hexadecimal"), self)
        hex_action.setCheckable(True)
        hex_action.setChecked(True)
        hex_action.triggered.connect(lambda: self._on_display_mode_changed("hex"))
        display_menu.addAction(hex_action)

        binary_action = QAction(self._tr("menu_binary"), self)
        binary_action.setCheckable(True)
        binary_action.triggered.connect(lambda: self._on_display_mode_changed("binary"))
        display_menu.addAction(binary_action)

        ascii_action = QAction(self._tr("menu_ascii"), self)
        ascii_action.setCheckable(True)
        ascii_action.triggered.connect(lambda: self._on_display_mode_changed("ascii"))
        display_menu.addAction(ascii_action)

        octal_action = QAction(self._tr("menu_octal"), self)
        octal_action.setCheckable(True)
        octal_action.triggered.connect(lambda: self._on_display_mode_changed("octal"))
        display_menu.addAction(octal_action)

        # Panels
        view_menu.addSeparator()
        show_file_tree_action = QAction(self._tr("menu_file_tree"), self)
        show_file_tree_action.setCheckable(True)
        show_file_tree_action.setChecked(True)
        show_file_tree_action.triggered.connect(self._on_toggle_file_tree)
        view_menu.addAction(show_file_tree_action)

        show_ai_panel_action = QAction(self._tr("menu_ai_panel"), self)
        show_ai_panel_action.setCheckable(True)
        show_ai_panel_action.triggered.connect(self._on_toggle_ai_panel)
        view_menu.addAction(show_ai_panel_action)

        # Folding submenu
        folding_menu = view_menu.addMenu(self._tr("menu_folding"))

        auto_detect_action = QAction(self._tr("menu_auto_detect"), self)
        auto_detect_action.triggered.connect(self._on_folding_detect)
        folding_menu.addAction(auto_detect_action)

        folding_menu.addSeparator()

        fold_all_action = QAction(self._tr("menu_fold_all"), self)
        fold_all_action.triggered.connect(self._on_fold_all)
        folding_menu.addAction(fold_all_action)

        unfold_all_action = QAction(self._tr("menu_unfold_all"), self)
        unfold_all_action.triggered.connect(self._on_unfold_all)
        folding_menu.addAction(unfold_all_action)

        # Multi-view submenu
        view_menu.addSeparator()
        multiview_menu = view_menu.addMenu(self._tr("menu_multi_view"))

        new_view_action = QAction(self._tr("menu_new_view"), self)
        new_view_action.setShortcut("Ctrl+Shift+N")
        new_view_action.setStatusTip("Open a new view of current file" if self._get_current_language() == "en" else "打开当前文件的新视图")
        new_view_action.triggered.connect(self._on_new_view)
        multiview_menu.addAction(new_view_action)

        multiview_menu.addSeparator()

        sync_scroll_action = QAction(self._tr("menu_sync_scroll"), self)
        sync_scroll_action.setCheckable(True)
        sync_scroll_action.setChecked(True)
        sync_scroll_action.triggered.connect(self._on_toggle_sync_scroll)
        multiview_menu.addAction(sync_scroll_action)

        sync_cursor_action = QAction(self._tr("menu_sync_cursor"), self)
        sync_cursor_action.setCheckable(True)
        sync_cursor_action.setChecked(True)
        sync_cursor_action.triggered.connect(self._on_toggle_sync_cursor)
        multiview_menu.addAction(sync_cursor_action)

        # Go Menu
        go_menu = menubar.addMenu(self._tr("menu_go"))

        # Back/Forward
        back_action = QAction(self._tr("menu_back"), self)
        back_action.setShortcut("Alt+Left")
        back_action.setStatusTip("Go back in navigation history" if self._get_current_language() == "en" else "在导航历史中后退")
        back_action.triggered.connect(self._on_go_back)
        go_menu.addAction(back_action)

        forward_action = QAction(self._tr("menu_forward"), self)
        forward_action.setShortcut("Alt+Right")
        forward_action.setStatusTip("Go forward in navigation history" if self._get_current_language() == "en" else "在导航历史中前进")
        forward_action.triggered.connect(self._on_go_forward)
        go_menu.addAction(forward_action)

        go_menu.addSeparator()

        toggle_bookmark_action = QAction(self._tr("menu_toggle_bookmark"), self)
        toggle_bookmark_action.setShortcut("Ctrl+F2")
        toggle_bookmark_action.setStatusTip("Toggle bookmark at cursor" if self._get_current_language() == "en" else "切换光标处的书签")
        toggle_bookmark_action.triggered.connect(self._on_toggle_bookmark)
        go_menu.addAction(toggle_bookmark_action)

        go_menu.addSeparator()

        next_bookmark_action = QAction(self._tr("menu_next_bookmark"), self)
        next_bookmark_action.setShortcut("F2")
        next_bookmark_action.setStatusTip("Go to next bookmark" if self._get_current_language() == "en" else "跳转到下一个书签")
        next_bookmark_action.triggered.connect(self._on_next_bookmark)
        go_menu.addAction(next_bookmark_action)

        prev_bookmark_action = QAction(self._tr("menu_prev_bookmark"), self)
        prev_bookmark_action.setShortcut("Shift+F2")
        prev_bookmark_action.setStatusTip("Go to previous bookmark" if self._get_current_language() == "en" else "跳转到上一个书签")
        prev_bookmark_action.triggered.connect(self._on_prev_bookmark)
        go_menu.addAction(prev_bookmark_action)

        # Tools Menu
        tools_menu = menubar.addMenu(self._tr("menu_tools"))

        compare_action = QAction(self._tr("menu_compare"), self)
        compare_action.setStatusTip("Compare two files" if self._get_current_language() == "en" else "比较两个文件")
        compare_action.triggered.connect(self._on_compare_files)
        tools_menu.addAction(compare_action)

        checksum_action = QAction(self._tr("menu_checksum"), self)
        checksum_action.setStatusTip("Calculate file checksum" if self._get_current_language() == "en" else "计算文件校验和")
        checksum_action.triggered.connect(self._on_checksum)
        tools_menu.addAction(checksum_action)

        # AI Menu
        ai_menu = menubar.addMenu(self._tr("menu_ai"))

        analyze_action = QAction(self._tr("menu_analyze"), self)
        analyze_action.setStatusTip("Analyze selected data with AI" if self._get_current_language() == "en" else "用AI分析选中的数据")
        analyze_action.triggered.connect(self._on_analyze)
        ai_menu.addAction(analyze_action)

        detect_pattern_action = QAction(self._tr("menu_detect_patterns"), self)
        detect_pattern_action.setStatusTip("Detect data patterns with AI" if self._get_current_language() == "en" else "用AI检测数据模式")
        detect_pattern_action.triggered.connect(self._on_detect_patterns)
        ai_menu.addAction(detect_pattern_action)

        generate_code_action = QAction(self._tr("menu_generate_code"), self)
        generate_code_action.setStatusTip("Generate code to parse selected data" if self._get_current_language() == "en" else "生成解析选中数据的代码")
        generate_code_action.triggered.connect(self._on_generate_code)
        ai_menu.addAction(generate_code_action)

        ai_menu.addSeparator()

        ai_settings_action = QAction(self._tr("menu_ai_settings"), self)
        ai_settings_action.setStatusTip("Configure AI settings" if self._get_current_language() == "en" else "配置AI设置")
        ai_settings_action.triggered.connect(self._on_ai_settings)
        ai_menu.addAction(ai_settings_action)

        # Preferences Menu
        prefs_menu = menubar.addMenu(self._tr("menu_preferences"))

        language_menu = prefs_menu.addMenu(self._tr("menu_language"))

        # English
        lang_en_action = QAction("English", self)
        lang_en_action.setCheckable(True)
        lang_en_action.triggered.connect(lambda: self._on_language_changed("en"))
        language_menu.addAction(lang_en_action)

        # Chinese
        lang_zh_action = QAction("中文", self)
        lang_zh_action.setCheckable(True)
        lang_zh_action.triggered.connect(lambda: self._on_language_changed("zh"))
        language_menu.addAction(lang_zh_action)

        # Check current language
        from .utils.i18n import get_language
        current_lang = get_language()
        if current_lang == "en":
            lang_en_action.setChecked(True)
        else:
            lang_zh_action.setChecked(True)

        # Help Menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.setStatusTip("About HexForge")
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _init_toolbars(self):
        """Initialize toolbars."""
        # Main toolbar
        main_toolbar = QToolBar("Main")
        main_toolbar.setMovable(False)
        main_toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(main_toolbar)

        # Add icon actions (icons will be loaded from theme)
        main_toolbar.addAction(self._get_icon("new"), "", self._on_new_file)
        main_toolbar.addAction(self._get_icon("open"), "", self._on_open_file)
        main_toolbar.addAction(self._get_icon("save"), "", self._on_save_file)
        main_toolbar.addSeparator()
        main_toolbar.addAction(self._get_icon("undo"), "", self._on_undo)
        main_toolbar.addAction(self._get_icon("redo"), "", self._on_redo)
        main_toolbar.addSeparator()
        main_toolbar.addAction(self._get_icon("find"), "", self._on_find)
        main_toolbar.addSeparator()

        # Arrangement parameter input
        from PyQt6.QtWidgets import QLabel, QSpinBox
        from PyQt6.QtCore import Qt

        # Length label and input - used for both EQUAL_FRAME (bytes per row) and HEADER_LENGTH (header bytes)
        length_label = QLabel("长度:")
        length_label.setStyleSheet("color: #cccccc;")
        main_toolbar.addWidget(length_label)

        self._length_spinbox = QSpinBox()
        self._length_spinbox.setRange(1, 65535)
        self._length_spinbox.setValue(32)
        self._length_spinbox.setMaximumWidth(80)
        self._length_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                padding: 2px;
            }
        """)
        self._length_spinbox.valueChanged.connect(self._on_arrangement_length_changed)
        main_toolbar.addWidget(self._length_spinbox)

        # Store references for updating
        self._toolbar_length_label = length_label

    def _init_central_widget(self):
        """Initialize central widget with hex editor."""
        self._hex_editor = HexEditorMainWindow()
        self.setCentralWidget(self._hex_editor)

    def _init_status_bar(self):
        """Initialize status bar."""
        self.statusBar().showMessage("Ready")
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #252526;
                color: #cccccc;
                border-top: 1px solid #3c3c3c;
            }
        """)

    def _get_icon(self, name: str) -> QIcon:
        """Get icon by name using system theme icons."""
        # Try to get system icons
        icon_map = {
            "new": "document-new",
            "open": "document-open",
            "save": "document-save",
            "undo": "edit-undo",
            "redo": "edit-redo",
            "find": "edit-find",
        }
        theme_name = icon_map.get(name)

        if theme_name:
            icon = QIcon.fromTheme(theme_name)
            if not icon.isNull():
                return icon

        # Fallback: create simple geometric icons
        from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QPainterPath

        size = 24
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen()
        pen.setWidth(2)

        if name == "new":
            # Plus icon
            pen.setColor(QColor("#4ec9b0"))
            painter.setPen(pen)
            painter.drawLine(12, 5, 12, 19)
            painter.drawLine(5, 12, 19, 12)
        elif name == "open":
            # Folder icon
            pen.setColor(QColor("#3794ff"))
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(4, 8)
            path.lineTo(4, 20)
            path.lineTo(20, 20)
            path.lineTo(20, 8)
            path.lineTo(12, 4)
            path.lineTo(4, 8)
            painter.drawPath(path)
            painter.drawLine(4, 8, 12, 4)
        elif name == "save":
            # Save icon (arrow down to disk)
            pen.setColor(QColor("#4ec9b0"))
            painter.setPen(pen)
            # Disk outline
            path = QPainterPath()
            path.moveTo(5, 6)
            path.lineTo(5, 18)
            path.lineTo(19, 18)
            path.lineTo(19, 6)
            path.lineTo(5, 6)
            painter.drawPath(path)
            # Arrow
            painter.drawLine(12, 10, 12, 15)
            painter.drawLine(9, 12, 12, 15)
            painter.drawLine(15, 12, 12, 15)
        elif name == "undo":
            # Undo arrow
            pen.setColor(QColor("#ce9178"))
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(16, 6)
            path.quadTo(8, 6, 8, 12)
            path.quadTo(8, 18, 16, 18)
            painter.drawPath(path)
            painter.drawLine(8, 12, 12, 8)
            painter.drawLine(8, 12, 12, 16)
        elif name == "redo":
            # Redo arrow
            pen.setColor(QColor("#ce9178"))
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(8, 6)
            path.quadTo(16, 6, 16, 12)
            path.quadTo(16, 18, 8, 18)
            painter.drawPath(path)
            painter.drawLine(16, 12, 12, 8)
            painter.drawLine(16, 12, 12, 16)
        elif name == "find":
            # Magnifying glass
            pen.setColor(QColor("#dcdcaa"))
            painter.setPen(pen)
            painter.drawEllipse(8, 8, 8, 8)
            painter.drawLine(14, 14, 19, 19)
        else:
            # Default circle
            pen.setColor(QColor("#ffffff"))
            painter.setPen(pen)
            painter.drawEllipse(6, 6, 12, 12)

        painter.end()
        return QIcon(pixmap)

    # File menu handlers
    def _on_new_file(self):
        """Handle new file action."""
        self._hex_editor.new_file()

    def _on_open_file(self):
        """Handle open file action."""
        self._hex_editor.open_file()

    def _on_open_folder(self):
        """Handle open folder action."""
        self._hex_editor.open_folder()

    def _on_save_file(self):
        """Handle save file action."""
        self._hex_editor.save_file()

    def _on_save_file_as(self):
        """Handle save file as action."""
        self._hex_editor.save_file_as()

    def _on_close_file(self):
        """Handle close file action."""
        self._hex_editor.close_current_file()

    # Edit menu handlers
    def _on_undo(self):
        """Handle undo action."""
        self._hex_editor.undo()

    def _on_redo(self):
        """Handle redo action."""
        self._hex_editor.redo()

    def _on_find(self):
        """Handle find action."""
        self._hex_editor.show_find_dialog()

    def _on_nl_search(self):
        """Handle natural language search action."""
        self._hex_editor.show_nl_search_dialog()

    def _on_replace(self):
        """Handle replace action."""
        self._hex_editor.show_replace_dialog()

    def _on_batch_fill(self):
        """Handle batch fill action."""
        self._hex_editor.show_batch_edit_dialog("fill")

    def _on_batch_increment(self):
        """Handle batch increment action."""
        self._hex_editor.batch_edit("increment")

    def _on_batch_decrement(self):
        """Handle batch decrement action."""
        self._hex_editor.batch_edit("decrement")

    def _on_batch_invert(self):
        """Handle batch invert action."""
        self._hex_editor.batch_edit("invert")

    def _on_batch_reverse(self):
        """Handle batch reverse action."""
        self._hex_editor.batch_edit("reverse")

    def _on_goto(self):
        """Handle goto action."""
        self._hex_editor.show_goto_dialog()

    # View menu handlers
    def _on_arrangement_changed(self, mode: str):
        """Handle arrangement mode change."""
        self._hex_editor.set_arrangement_mode(mode)

    def _on_custom_arrangement(self):
        """Handle custom arrangement."""
        self._hex_editor.show_arrangement_dialog()

    def _on_display_mode_changed(self, mode: str):
        """Handle display mode change."""
        self._hex_editor.set_display_mode(mode)

    def _on_arrangement_length_changed(self, value: int):
        """Handle arrangement length change.

        For EQUAL_FRAME mode: sets bytes per row (1-65535)
        For HEADER_LENGTH mode: sets header length in bytes (1-8)
        """
        # 根据当前模式判断是设置等长帧还是头长度
        if self._hex_editor._data_model.arrangement_mode == ArrangementMode.HEADER_LENGTH:
            # 头长度模式
            self._hex_editor.set_header_length(value)
        else:
            # 等长帧模式（默认）
            self._hex_editor.set_arrangement_length(value)

    def _on_toggle_file_tree(self):
        """Toggle file tree panel."""
        self._hex_editor.toggle_file_tree()

    def _on_toggle_ai_panel(self):
        """Toggle AI panel."""
        self._hex_editor.toggle_ai_panel()

    def _on_folding_detect(self):
        """Auto-detect folding regions."""
        self._hex_editor.detect_folding_regions()

    def _on_fold_all(self):
        """Fold all regions."""
        self._hex_editor.fold_all()

    def _on_unfold_all(self):
        """Unfold all regions."""
        self._hex_editor.unfold_all()

    def _on_new_view(self):
        """Open a new view."""
        self._hex_editor.open_new_view()

    def _on_toggle_sync_scroll(self, checked):
        """Toggle scroll synchronization."""
        self._hex_editor.set_sync_scroll(checked)

    def _on_toggle_sync_cursor(self, checked):
        """Toggle cursor synchronization."""
        self._hex_editor.set_sync_cursor(checked)

    # Go menu handlers
    def _on_next_bookmark(self):
        """Go to next bookmark."""
        self._hex_editor.go_to_next_bookmark()

    def _on_prev_bookmark(self):
        """Go to previous bookmark."""
        self._hex_editor.go_to_previous_bookmark()

    def _on_toggle_bookmark(self):
        """Toggle bookmark at cursor."""
        self._hex_editor.toggle_bookmark_at_cursor()

    def _on_go_back(self):
        """Go back in navigation history."""
        self._hex_editor.go_back()

    def _on_go_forward(self):
        """Go forward in navigation history."""
        self._hex_editor.go_forward()

    # Tools menu handlers
    def _on_compare_files(self):
        """Compare files."""
        self._hex_editor.compare_files()

    def _on_checksum(self):
        """Calculate checksum."""
        self._hex_editor.show_checksum_dialog()

    # AI menu handlers
    def _on_analyze(self):
        """Analyze selected data."""
        self._hex_editor.analyze_selection()

    def _on_detect_patterns(self):
        """Detect data patterns."""
        self._hex_editor.detect_patterns()

    def _on_generate_code(self):
        """Generate parsing code."""
        self._hex_editor.generate_parsing_code()

    def _on_ai_settings(self):
        """Show AI settings dialog."""
        self._hex_editor.show_ai_settings()

    def _on_language_changed(self, lang: str):
        """Handle language change."""
        from .utils.i18n import set_language
        from .utils.logger import logger
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import QSettings

        set_language(lang)

        # Save to settings - use QSettings directly
        s = QSettings("HexForge", "HexForge")
        s.setValue("language", lang)
        s.sync()

        logger.info(f"Language changed to: {lang}")

        # Rebuild menus to apply new language
        self.menuBar().clear()
        self._init_menus()

        # Show message that restart is needed
        msg = "Language changed. Please restart the application to apply changes." if lang == "en" else "语言已更改。请重启应用以应用更改。"
        QMessageBox.information(
            self,
            tr("dialog_preferences"),
            msg
        )

    def _get_current_language(self) -> str:
        """Get current language."""
        from .utils.i18n import get_language
        return get_language()

    def _tr(self, key: str) -> str:
        """Get translated string for current language."""
        from .utils.i18n import tr
        return tr(key)

    # Help menu handlers
    def _on_about(self):
        """Show about dialog."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "About HexForge",
            "<h1>HexForge</h1>"
            "<p>Version 1.0.0</p>"
            "<p>AI Enhanced Binary Editor</p>"
            "<p>Built with PyQt6</p>"
        )

    def closeEvent(self, event):
        """Handle window close event."""
        if self._hex_editor.close_all_files():
            event.accept()
        else:
            event.ignore()
