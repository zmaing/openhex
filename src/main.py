"""
openhex Main Window

Main application window with menu bar, toolbar, and central widget.
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QStatusBar, QToolBar, QMenuBar, QMenu, QFrame,
                             QSizePolicy, QLabel)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QActionGroup, QColor, QPalette, QPainter

import os
import sys

from .ui.main_window import HexEditorMainWindow
from .ui.design_system import CHROME
from .core.data_model import ArrangementMode
from .utils.i18n import tr


class OpenHexMainWindow(QMainWindow):
    """Main window for openhex application."""

    def __init__(self):
        super().__init__()
        self._init_window()
        self._init_menus()
        self._init_toolbars()
        self._init_central_widget()
        self._init_status_bar()

    def _init_window(self):
        """Initialize window properties."""
        self.setObjectName("openhexMainWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(CHROME.workspace_bg))
        self.setPalette(palette)
        self.setWindowTitle("openhex - AI Enhanced Binary Editor")
        self.resize(1440, 920)
        self.setMinimumSize(1080, 720)
        if sys.platform == "darwin":
            self.setUnifiedTitleAndToolBarOnMac(True)

        # Center window on screen
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

    def paintEvent(self, event):
        """Fill the native window background so rounded OS corners never expose light defaults."""
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(CHROME.workspace_bg))
        super().paintEvent(event)

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

        filter_action = QAction(tr("menu_filter"), self)
        filter_action.setStatusTip("Filter rows in the current view" if self._get_current_language() == "en" else "过滤当前视图中的行")
        filter_action.triggered.connect(self._on_filter)
        edit_menu.addAction(filter_action)

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

        # Store reference for updating
        self._arrange_equal_action = equal_frame_action
        self._arrange_header_action = header_length_action

        # Display modes
        display_menu = view_menu.addMenu(self._tr("menu_display_mode"))
        self._display_mode_group = QActionGroup(self)
        self._display_mode_group.setExclusive(True)
        self._display_mode_group.triggered.connect(self._on_display_mode_action_triggered)
        self._display_mode_actions = {}

        display_mode_specs = [
            ("hex", self._tr("menu_hexadecimal"), True),
            ("binary", self._tr("menu_binary"), False),
            ("octal", self._tr("menu_octal"), False),
        ]

        for mode, label, checked in display_mode_specs:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(checked)
            action.setData(mode)
            action.setActionGroup(self._display_mode_group)
            display_menu.addAction(action)
            self._display_mode_actions[mode] = action

        ascii_action = QAction(self._tr("menu_ascii"), self)
        ascii_action.setCheckable(True)
        ascii_action.setChecked(True)
        ascii_action.toggled.connect(self._on_ascii_visibility_toggled)
        display_menu.addAction(ascii_action)
        self._ascii_visibility_action = ascii_action

        # Panels
        view_menu.addSeparator()
        show_file_tree_action = QAction(self._tr("menu_file_tree"), self)
        show_file_tree_action.setCheckable(True)
        show_file_tree_action.setChecked(True)
        show_file_tree_action.triggered.connect(self._on_toggle_file_tree)
        view_menu.addAction(show_file_tree_action)
        self._show_file_tree_action = show_file_tree_action

        show_ai_panel_action = QAction(self._tr("menu_ai_panel"), self)
        show_ai_panel_action.setCheckable(True)
        show_ai_panel_action.setChecked(False)
        show_ai_panel_action.triggered.connect(self._on_toggle_ai_panel)
        view_menu.addAction(show_ai_panel_action)
        self._show_ai_panel_action = show_ai_panel_action

        show_value_panel_action = QAction(self._tr("menu_value_panel"), self)
        show_value_panel_action.setCheckable(True)
        show_value_panel_action.setChecked(True)
        show_value_panel_action.triggered.connect(self._on_toggle_value_panel)
        view_menu.addAction(show_value_panel_action)
        self._show_value_panel_action = show_value_panel_action

        show_structure_panel_action = QAction(self._tr("menu_structure_panel"), self)
        show_structure_panel_action.setCheckable(True)
        show_structure_panel_action.setChecked(False)
        show_structure_panel_action.triggered.connect(self._on_toggle_structure_panel)
        view_menu.addAction(show_structure_panel_action)
        self._show_structure_panel_action = show_structure_panel_action

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
        about_action.setStatusTip("About openhex")
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _init_toolbars(self):
        """Initialize toolbars."""
        # Main toolbar
        main_toolbar = QToolBar("Main")
        main_toolbar.setObjectName("mainToolbar")
        main_toolbar.setMovable(False)
        main_toolbar.setFloatable(False)
        main_toolbar.setIconSize(QSize(14, 14))
        main_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        main_toolbar.setMinimumHeight(CHROME.toolbar_height + 2)
        main_toolbar.setStyleSheet(f"""
            QToolBar {{
                background: {CHROME.workspace_bg};
                border: none;
                border-bottom: 1px solid {CHROME.border};
                spacing: 0px;
                padding: 4px 8px 4px 8px;
            }}
            QWidget#toolbarHost {{
                background: transparent;
            }}
            QWidget#toolbarLeadingCluster {{
                background: transparent;
            }}
            QFrame#toolbarGroup,
            QFrame#toolbarFieldGroup {{
                background: {CHROME.surface};
                border: 1px solid {CHROME.border};
                border-radius: 8px;
                min-height: 30px;
            }}
            QFrame#toolbarFieldGroup {{
                padding-left: 3px;
                padding-right: 3px;
            }}
            QFrame#toolbarDivider {{
                background: {CHROME.border_strong};
                min-width: 1px;
                max-width: 1px;
                min-height: 14px;
                margin: 6px 1px;
            }}
            QToolButton#toolbarButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 7px;
                padding: 0;
                min-width: 26px;
                max-width: 26px;
                min-height: 26px;
                max-height: 26px;
            }}
            QToolButton#toolbarButton:hover {{
                background: {CHROME.surface_alt};
                border-color: {CHROME.border};
            }}
            QToolButton#toolbarButton:pressed {{
                background: {CHROME.surface_raised};
                border-color: {CHROME.border_strong};
            }}
            QLabel#toolbarLabel {{
                color: {CHROME.text_secondary};
                background: transparent;
                font-size: 10px;
                font-weight: 600;
                padding: 0 2px 0 6px;
            }}
            QSpinBox#toolbarSpinBox {{
                background: {CHROME.workspace_bg};
                color: {CHROME.text_primary};
                border: 1px solid {CHROME.border};
                border-radius: 7px;
                padding: 0 15px 0 7px;
                min-width: 54px;
                min-height: 26px;
                selection-background-color: {CHROME.accent};
                selection-color: {CHROME.text_primary};
            }}
            QSpinBox#toolbarSpinBox:hover {{
                border-color: {CHROME.text_muted};
            }}
            QSpinBox#toolbarSpinBox:focus {{
                border-color: {CHROME.accent};
            }}
            QSpinBox#toolbarSpinBox::up-button {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 10px;
                height: 8px;
                margin: 2px 3px 0 0;
                border: none;
                border-left: 1px solid {CHROME.border};
                border-top-right-radius: 4px;
                background: {CHROME.surface_alt};
            }}
            QSpinBox#toolbarSpinBox::down-button {{
                subcontrol-origin: padding;
                subcontrol-position: bottom right;
                width: 10px;
                height: 8px;
                margin: 0 3px 2px 0;
                border: none;
                border-left: 1px solid {CHROME.border};
                border-bottom-right-radius: 4px;
                background: {CHROME.surface_alt};
            }}
            QSpinBox#toolbarSpinBox::up-arrow,
            QSpinBox#toolbarSpinBox::down-arrow {{
                width: 5px;
                height: 5px;
            }}
        """)
        self.addToolBar(main_toolbar)

        # Arrangement parameter input
        from PyQt6.QtWidgets import QSpinBox, QAbstractSpinBox

        toolbar_host = QWidget(self)
        toolbar_host.setObjectName("toolbarHost")
        toolbar_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar_host.setMinimumHeight(CHROME.toolbar_height)
        host_layout = QHBoxLayout(toolbar_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)

        leading_cluster = QWidget(toolbar_host)
        leading_cluster.setObjectName("toolbarLeadingCluster")
        leading_layout = QHBoxLayout(leading_cluster)
        leading_layout.setContentsMargins(0, 0, 0, 0)
        leading_layout.setSpacing(6)

        file_group, file_layout = self._create_toolbar_group()
        self._add_toolbar_group_button(file_layout, "new", self._tr("menu_new"), self._on_new_file)
        self._add_toolbar_divider(file_layout)
        self._add_toolbar_group_button(file_layout, "open", self._tr("menu_open"), self._on_open_file)
        self._add_toolbar_divider(file_layout)
        self._add_toolbar_group_button(file_layout, "save", self._tr("menu_save"), self._on_save_file)
        leading_layout.addWidget(file_group)

        history_group, history_layout = self._create_toolbar_group()
        self._add_toolbar_group_button(history_layout, "undo", self._tr("menu_undo"), self._on_undo)
        self._add_toolbar_divider(history_layout)
        self._add_toolbar_group_button(history_layout, "redo", self._tr("menu_redo"), self._on_redo)
        leading_layout.addWidget(history_group)

        search_group, search_layout = self._create_toolbar_group()
        self._add_toolbar_group_button(search_layout, "find", self._tr("menu_find"), self._on_find)
        self._add_toolbar_divider(search_layout)
        self._filter_toolbar_button = self._create_toolbar_button("filter", self._tr("menu_filter"), self._on_filter)
        self._filter_toolbar_button.setStatusTip("Filter rows in the current view" if self._get_current_language() == "en" else "过滤当前视图中的行")
        search_layout.addWidget(self._filter_toolbar_button)
        leading_layout.addWidget(search_group)

        # Length label and input - used for both EQUAL_FRAME (bytes per row) and HEADER_LENGTH (header bytes)
        field_group = QFrame()
        field_group.setObjectName("toolbarFieldGroup")
        field_layout = QHBoxLayout(field_group)
        field_layout.setContentsMargins(3, 2, 3, 2)
        field_layout.setSpacing(4)

        length_label = QLabel("长度:")
        length_label.setObjectName("toolbarLabel")
        field_layout.addWidget(length_label)

        self._length_spinbox = QSpinBox()
        self._length_spinbox.setObjectName("toolbarSpinBox")
        self._length_spinbox.setRange(1, 65535)
        self._length_spinbox.setValue(32)
        self._length_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self._length_spinbox.setFrame(False)
        self._length_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._length_spinbox.setFixedWidth(64)
        self._length_spinbox.valueChanged.connect(self._on_arrangement_length_changed)
        field_layout.addWidget(self._length_spinbox)

        self._add_toolbar_divider(field_layout)

        start_offset_label = QLabel("Start:" if self._get_current_language() == "en" else "数据起点:")
        start_offset_label.setObjectName("toolbarLabel")
        field_layout.addWidget(start_offset_label)

        self._start_offset_spinbox = QSpinBox()
        self._start_offset_spinbox.setObjectName("toolbarSpinBox")
        self._start_offset_spinbox.setRange(0, 0)
        self._start_offset_spinbox.setValue(0)
        self._start_offset_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self._start_offset_spinbox.setFrame(False)
        self._start_offset_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._start_offset_spinbox.setFixedWidth(84)
        self._start_offset_spinbox.setToolTip(
            "Set the byte offset used as the display and arrangement start"
            if self._get_current_language() == "en"
            else "设置用于显示和排列起点的字节偏移"
        )
        self._start_offset_spinbox.setStatusTip(self._start_offset_spinbox.toolTip())
        self._start_offset_spinbox.valueChanged.connect(self._on_arrangement_start_offset_changed)
        field_layout.addWidget(self._start_offset_spinbox)

        leading_layout.addWidget(field_group)

        host_layout.addWidget(leading_cluster, 0, Qt.AlignmentFlag.AlignVCenter)
        host_layout.addStretch(1)
        main_toolbar.addWidget(toolbar_host)

        # Store references for updating
        self._toolbar_length_label = length_label
        self._toolbar_start_offset_label = start_offset_label
        self._toolbar_length_group = field_group

    def _create_toolbar_group(self):
        """Create a capsule toolbar group with a horizontal layout."""
        group = QFrame()
        group.setObjectName("toolbarGroup")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(2)
        return group, layout

    def _add_toolbar_group_button(self, layout, icon_name: str, tooltip: str, slot):
        """Append a toolbar button into a capsule group."""
        layout.addWidget(self._create_toolbar_button(icon_name, tooltip, slot))

    def _add_toolbar_divider(self, layout):
        """Append a subtle divider between toolbar controls."""
        divider = QFrame()
        divider.setObjectName("toolbarDivider")
        divider.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(divider)

    def _create_toolbar_button(self, icon_name: str, tooltip: str, slot):
        """Create a consistent toolbar button."""
        from PyQt6.QtWidgets import QToolButton

        button = QToolButton(self)
        button.setObjectName("toolbarButton")
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setIcon(self._get_icon(icon_name))
        button.setIconSize(QSize(14, 14))
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def _init_central_widget(self):
        """Initialize central widget with hex editor."""
        self._hex_editor = HexEditorMainWindow()
        self.setCentralWidget(self._hex_editor)
        self._hex_editor.side_panel_state_changed.connect(self._on_side_panel_state_changed)
        self._sync_side_panel_actions(
            self._hex_editor.is_ai_panel_visible(),
            self._hex_editor.is_value_panel_visible(),
            self._hex_editor.is_structure_panel_visible(),
        )

    def _init_status_bar(self):
        """Initialize status bar."""
        self.statusBar().showMessage("Ready")
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {CHROME.workspace_bg};
                color: {CHROME.text_muted};
                border: none;
                border-top: 1px solid {CHROME.border};
                padding: 0 8px;
                min-height: 22px;
                font-size: 10px;
            }}
            QStatusBar::item {{
                border: none;
                padding: 0 4px;
            }}
        """)

    def _get_icon(self, name: str) -> QIcon:
        """Return a unified linear icon for the toolbar."""
        icon = QIcon()
        states = (
            (QIcon.Mode.Normal, QIcon.State.Off, QColor(CHROME.text_secondary)),
            (QIcon.Mode.Active, QIcon.State.Off, QColor(CHROME.text_primary)),
            (QIcon.Mode.Selected, QIcon.State.Off, QColor(CHROME.text_primary)),
            (QIcon.Mode.Disabled, QIcon.State.Off, QColor(CHROME.text_muted)),
            (QIcon.Mode.Normal, QIcon.State.On, QColor(CHROME.accent_hover)),
            (QIcon.Mode.Active, QIcon.State.On, QColor(CHROME.text_primary)),
            (QIcon.Mode.Selected, QIcon.State.On, QColor(CHROME.text_primary)),
        )
        for mode, state, color in states:
            icon.addPixmap(self._create_toolbar_icon_pixmap(name, color), mode, state)
        return icon

    def _create_toolbar_icon_pixmap(self, name: str, color: QColor):
        """Render a toolbar icon using a shared 24px linear grid."""
        from PyQt6.QtGui import QPixmap, QPainter, QPen, QPainterPath

        size = 18
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(color)
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if name == "new":
            painter.drawLine(9, 4, 9, 14)
            painter.drawLine(4, 9, 14, 9)
        elif name == "open":
            path = QPainterPath()
            path.moveTo(5.5, 13.5)
            path.lineTo(13.5, 5.5)
            path.moveTo(10.0, 5.5)
            path.lineTo(13.5, 5.5)
            path.lineTo(13.5, 9.0)
            path.moveTo(5.5, 9.0)
            path.lineTo(5.5, 13.5)
            path.lineTo(10.0, 13.5)
            painter.drawPath(path)
        elif name == "save":
            path = QPainterPath()
            path.moveTo(5.5, 12.0)
            path.lineTo(5.5, 13.0)
            path.quadTo(5.5, 14.5, 7.0, 14.5)
            path.lineTo(11.0, 14.5)
            path.quadTo(12.5, 14.5, 12.5, 13.0)
            path.lineTo(12.5, 12.0)
            painter.drawPath(path)
            painter.drawLine(9, 4, 9, 10)
            painter.drawLine(8, 8, 9, 10)
            painter.drawLine(10, 8, 9, 10)
        elif name == "undo":
            path = QPainterPath()
            path.moveTo(12.5, 5.8)
            path.quadTo(7.2, 5.8, 7.2, 9.0)
            path.quadTo(7.2, 12.2, 11.2, 12.2)
            painter.drawPath(path)
            painter.drawLine(7, 9, 9, 7)
            painter.drawLine(7, 9, 9, 11)
        elif name == "redo":
            path = QPainterPath()
            path.moveTo(5.5, 5.8)
            path.quadTo(10.8, 5.8, 10.8, 9.0)
            path.quadTo(10.8, 12.2, 6.8, 12.2)
            painter.drawPath(path)
            painter.drawLine(11, 9, 9, 7)
            painter.drawLine(11, 9, 9, 11)
        elif name == "find":
            painter.drawEllipse(5, 5, 7, 7)
            painter.drawLine(11, 11, 13, 13)
        elif name == "filter":
            path = QPainterPath()
            path.moveTo(4.5, 5.5)
            path.lineTo(13.5, 5.5)
            path.lineTo(10.5, 9.0)
            path.lineTo(10.5, 11.8)
            path.lineTo(7.5, 13.5)
            path.lineTo(7.5, 9.0)
            path.closeSubpath()
            painter.drawPath(path)
        else:
            painter.drawEllipse(4, 4, 10, 10)

        painter.end()
        return pixmap

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

    def _on_filter(self):
        """Handle row filter action."""
        self._hex_editor.show_filter_dialog()

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

    def _on_display_mode_changed(self, mode: str):
        """Handle display mode change."""
        action = self._display_mode_actions.get(mode)
        if action is not None and not action.isChecked():
            action.setChecked(True)
        self._hex_editor.set_display_mode(mode)

    def _on_display_mode_action_triggered(self, action: QAction):
        """Handle display mode action selection."""
        mode = action.data()
        if isinstance(mode, str):
            self._on_display_mode_changed(mode)

    def _on_ascii_visibility_toggled(self, checked: bool):
        """Handle ASCII column visibility toggle."""
        self._hex_editor.set_ascii_visible(checked)

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

    def _on_arrangement_start_offset_changed(self, value: int):
        """Handle arrangement start offset change."""
        self._hex_editor.set_arrangement_start_offset(value)

    def _sync_arrangement_toolbar(
        self,
        *,
        mode: ArrangementMode | None = None,
        length_value: int | None = None,
        length_range: tuple[int, int] | None = None,
        start_offset: int | None = None,
        max_start_offset: int | None = None,
    ) -> None:
        """Synchronize arrangement controls without retriggering editor updates."""
        if hasattr(self, "_toolbar_length_label"):
            if mode == ArrangementMode.HEADER_LENGTH:
                self._toolbar_length_label.setText("Header:" if self._get_current_language() == "en" else "头长度:")
            elif mode is not None:
                self._toolbar_length_label.setText("Length:" if self._get_current_language() == "en" else "长度:")

        if hasattr(self, "_toolbar_start_offset_label"):
            self._toolbar_start_offset_label.setText("Start:" if self._get_current_language() == "en" else "数据起点:")

        if hasattr(self, "_length_spinbox"):
            blocked = self._length_spinbox.blockSignals(True)
            if length_range is not None:
                minimum, maximum = length_range
                self._length_spinbox.setRange(int(minimum), int(maximum))
            if length_value is not None:
                self._length_spinbox.setValue(int(length_value))
            self._length_spinbox.blockSignals(blocked)

        if hasattr(self, "_start_offset_spinbox"):
            blocked = self._start_offset_spinbox.blockSignals(True)
            maximum = max(0, int(max_start_offset if max_start_offset is not None else self._start_offset_spinbox.maximum()))
            self._start_offset_spinbox.setRange(0, maximum)
            if start_offset is not None:
                self._start_offset_spinbox.setValue(min(maximum, max(0, int(start_offset))))
            self._start_offset_spinbox.blockSignals(blocked)

    def _on_toggle_file_tree(self):
        """Toggle file tree panel."""
        self._hex_editor.toggle_file_tree()

    def _on_toggle_ai_panel(self):
        """Toggle AI panel."""
        self._hex_editor.toggle_ai_panel()

    def _on_toggle_value_panel(self):
        """Toggle Value panel."""
        self._hex_editor.toggle_value_panel()

    def _on_toggle_structure_panel(self):
        """Toggle structure panel."""
        self._hex_editor.toggle_structure_panel()

    def _on_side_panel_state_changed(
        self,
        ai_visible: bool,
        value_visible: bool,
        structure_visible: bool,
        layout_mode: str,
    ):
        """Sync menu check states with the embedded side panel controls."""
        self._sync_side_panel_actions(ai_visible, value_visible, structure_visible)

    def _sync_side_panel_actions(
        self,
        ai_visible: bool,
        value_visible: bool,
        structure_visible: bool,
    ):
        """Update panel menu actions without retriggering toggles."""
        for action, visible in (
            (
                getattr(self, "_show_ai_panel_action", None),
                ai_visible,
            ),
            (getattr(self, "_show_value_panel_action", None), value_visible),
            (getattr(self, "_show_structure_panel_action", None), structure_visible),
        ):
            if action is None:
                continue
            blocked = action.blockSignals(True)
            action.setChecked(visible)
            action.blockSignals(blocked)

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
        s = QSettings("openhex", "openhex")
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
            "About openhex",
            "<h1>openhex</h1>"
            "<p>Version 1.0.0</p>"
            "<p>AI Enhanced Binary Editor</p>"
            "<p>Built with PyQt6</p>"
        )

    def closeEvent(self, event):
        """Handle window close event."""
        hex_editor = getattr(self, "_hex_editor", None)
        if hex_editor is None:
            event.accept()
            return

        if hex_editor.close_all_files():
            hex_editor.shutdown()
            event.accept()
        else:
            event.ignore()
