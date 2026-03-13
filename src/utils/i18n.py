"""
Internationalization (i18n) module for openhex.

Supports Chinese (zh) and English (en) languages.
"""

from typing import Dict

# Translation dictionaries
_translations: Dict[str, Dict[str, str]] = {
    "en": {
        # Menu - File
        "menu_file": "&File",
        "menu_new": "&New",
        "menu_open": "&Open...",
        "menu_open_folder": "Open &Folder...",
        "menu_save": "&Save",
        "menu_save_as": "Save &As...",
        "menu_close": "&Close",
        "menu_exit": "E&xit",

        # Menu - Edit
        "menu_edit": "&Edit",
        "menu_undo": "&Undo",
        "menu_redo": "&Redo",
        "menu_find": "&Find...",
        "menu_filter": "&Filter...",
        "menu_ai_search": "&AI Search...",
        "menu_replace": "&Replace...",
        "menu_batch_edit": "Batch Edit",
        "menu_fill": "&Fill...",
        "menu_increment": "&Increment",
        "menu_decrement": "&Decrement",
        "menu_invert": "&Invert",
        "menu_reverse": "Re&verse",
        "menu_goto": "&Go To...",

        # Menu - View
        "menu_view": "&View",
        "menu_arrangement": "Arrangement",
        "menu_equal_frame": "Equal Frame",
        "menu_header_length": "Header Length",
        "menu_custom": "Custom...",
        "menu_display_mode": "Display Mode",
        "menu_hexadecimal": "Hexadecimal",
        "menu_binary": "Binary",
        "menu_ascii": "ASCII",
        "menu_octal": "Octal",
        "menu_file_tree": "File Tree",
        "menu_ai_panel": "AI Panel",
        "menu_value_panel": "Value Panel",
        "menu_structure_panel": "Structure Parsing",
        "menu_folding": "Folding",
        "menu_auto_detect": "Auto-Detect Regions",
        "menu_fold_all": "Fold All",
        "menu_unfold_all": "Unfold All",
        "menu_multi_view": "Multi-View",
        "menu_new_view": "New View",
        "menu_sync_scroll": "Sync Scroll",
        "menu_sync_cursor": "Sync Cursor",

        # Menu - Go
        "menu_go": "&Go",
        "menu_back": "Back",
        "menu_forward": "Forward",
        "menu_toggle_bookmark": "Toggle Bookmark",
        "menu_next_bookmark": "Next Bookmark",
        "menu_prev_bookmark": "Previous Bookmark",

        # Menu - Tools
        "menu_tools": "&Tools",
        "menu_compare": "Compare Files...",
        "menu_checksum": "Calculate Checksum...",

        # Menu - AI
        "menu_ai": "&AI",
        "menu_analyze": "Analyze Data...",
        "menu_detect_patterns": "Detect Patterns...",
        "menu_generate_code": "Generate Parsing Code...",
        "menu_ai_settings": "AI Settings...",

        # Menu - Help
        "menu_help": "&Help",
        "menu_about": "&About",

        # Menu - Preferences
        "menu_preferences": "&Preferences",
        "menu_language": "Language",

        # Status
        "status_ready": "Ready",
        "status_offset": "Offset: {}",
        "status_selection": "Sel: {} bytes",
        "status_size": "Size: {}",
        "status_saved": "Saved",
        "status_caption_offset": "Offset",
        "status_caption_selection": "Selection",
        "status_caption_layout": "Layout",
        "status_caption_encoding": "Encoding",
        "status_caption_size": "Size",
        "status_caption_view": "View",
        "status_caption_edit": "Edit",
        "status_arrangement_equal": "Frame {}",
        "status_arrangement_header": "Header {}",
        "status_arrangement_custom": "Custom {}",
        "workspace_state_modified": "Modified",
        "workspace_state_draft": "Draft",
        "workspace_unsaved": "Unsaved draft",
        "workspace_panels_count": "{} Panels",
        "workspace_ruler_scale": "Byte Scale",
        "workspace_ruler_window": "Window {}-{}",

        # Panels
        "panel_file_info": "File Information",
        "panel_data_inspector": "Data Inspector",
        "panel_ai_assistant": "AI Assistant",
        "panel_data_tab": "Data",
        "panel_info_tab": "Info",
        "panel_value_tab": "Value",
        "panel_ai_tab": "AI",
        "panel_structure_tab": "Structure",
        "panel_data_tab_short": "Data",
        "panel_info_tab_short": "Info",
        "panel_value_tab_short": "Value",
        "panel_ai_tab_short": "AI",
        "panel_structure_tab_short": "Struct",
        "panel_layout_adaptive": "Adaptive",
        "panel_layout_tabs": "Tabs",
        "panel_layout_vertical": "Split Up/Down",
        "panel_layout_horizontal": "Split Left/Right",
        "panel_structure_title": "Structure Parsing",
        "panel_structure_offset": "Row Offset:",
        "panel_structure_display": "Display:",
        "panel_structure_hex": "Hex",
        "panel_structure_decimal": "Decimal",
        "panel_structure_field": "Field",
        "panel_structure_value": "Value",
        "panel_structure_new_config": "New Config...",
        "panel_structure_manage_config": "Manage Configs...",
        "panel_structure_new_title": "New Structure Config",
        "panel_structure_edit_title": "Edit Structure Config",
        "panel_structure_manage_title": "Manage Structure Configs",
        "panel_structure_manage_saved": "Saved configs",
        "panel_structure_edit": "Edit",
        "panel_structure_delete": "Delete",
        "panel_structure_delete_confirm": "Delete config \"{}\"?",
        "panel_structure_name": "Config Name",
        "panel_structure_definition": "C Struct Definition",
        "panel_structure_confirm": "Confirm",
        "panel_structure_cancel": "Cancel",
        "panel_structure_name_placeholder": "Enter config name",
        "panel_structure_definition_placeholder": "Paste a C struct definition",
        "panel_structure_invalid_name": "Config name is required.",
        "panel_structure_invalid_definition": "C struct definition is required.",
        "panel_structure_duplicate_name": "A config with that name already exists.",
        "panel_structure_parse_error": "Failed to parse struct: {}",

        # Dialogs
        "dialog_arrangement": "Arrangement Settings",
        "dialog_bytes_per_frame": "Bytes per frame:",
        "dialog_header_length": "Header length:",
        "dialog_preferences": "Preferences",
        "dialog_language": "Language:",
        "dialog_english": "English",
        "dialog_chinese": "Chinese (中文)",

        # Find/Replace Dialog
        "dialog_find_replace": "Find / Replace",
        "dialog_filter": "Row Filter",
        "tab_find": "Find",
        "tab_replace": "Replace",
        "tab_results": "Results",
        "label_find": "Find:",
        "label_replace_with": "Replace with:",
        "label_replace": "Replace:",
        "placeholder_find": "Enter search pattern...",
        "placeholder_replace": "Enter replacement text...",
        "label_direction": "Direction:",
        "label_up": "Up",
        "label_down": "Down",
        "label_options": "Options:",
        "label_case_sensitive": "Case sensitive",
        "label_whole_word": "Whole word",
        "label_wrap_around": "Wrap around",
        "no_results": "No results",
        "results_found": "{} results found",
        "btn_find_prev": "Find Previous",
        "btn_find_next": "Find Next",
        "btn_replace": "Replace",
        "btn_replace_all": "Replace All",
        "btn_close": "Close",
        "label_forward": "Forward",
        "label_backward": "Backward",
        "label_search_mode": "Search Mode",
        "mode_hex": "Hex (e.g., 48 65 6C 6C 6F)",
        "mode_text": "Text",
        "mode_regex": "Regex",
        "placeholder_replace": "Enter replacement...",
        "label_replace_action": "Replace:",
        "btn_replace_next": "Replace Next",
        "label_prompt_replace_all": "Prompt on replace all",
        "filter_description": "Write row filters with C-like syntax. Use data[x] to read the byte at offset x within the current row, for example: data[0] > 1 or data[0] & 1 == 1.",
        "filter_create_group": "Create Filter Condition",
        "filter_input_placeholder": "Enter one condition, for example: data[0] > 1",
        "filter_add_condition": "Add Condition",
        "filter_saved_group": "Saved Group:",
        "filter_saved_group_placeholder": "Select a saved group...",
        "filter_active_group": "Active Filter Conditions",
        "filter_active_hint": "Rows must satisfy every active condition to remain visible.",
        "filter_history_group": "Condition History",
        "filter_history_hint": "Double-click or select a condition to import it into the active list.",
        "filter_import_condition": "Import Selected",
        "filter_remove_selected": "Remove Selected",
        "filter_clear_active": "Clear",
        "filter_save_combo": "Save Current Group",
        "filter_apply": "Filter",
        "filter_empty_error": "Please enter a filter condition.",
        "filter_invalid_error": "Invalid filter condition: {}",
        "filter_save_empty_error": "Add at least one active filter before saving a group.",
        "filter_group_name": "Group name:",
        "filter_group_name_empty_error": "Please enter a group name.",
        "filter_overwrite_group": "A saved group named \"{}\" already exists. Overwrite it?",
        "filter_no_active_view": "No active view",
        "filter_status_applied": "Showing {}/{} rows after filtering.",
        "filter_status_cleared": "Cleared row filters.",

        # File info
        "info_name": "Name:",
        "info_size": "Size:",
        "info_type": "Type:",
        "info_path": "Path:",
        "info_checksums": "Checksums",
        "info_md5": "MD5:",
        "info_sha256": "SHA256:",

        # Data inspector
        "inspector_offset": "Offset:",
        "inspector_hex": "Hex:",
        "inspector_signed": "Signed:",
        "inspector_unsigned": "Unsigned:",
        "inspector_binary": "Binary:",
        "inspector_ascii": "ASCII:",
        "inspector_octal": "Octal:",

        # AI Panel
        "ai_not_configured": "Not configured",
        "ai_analyze_btn": "Analyze Data",
        "ai_detect_btn": "Detect Patterns",
        "ai_gen_code_btn": "Generate Code",
    },
    "zh": {
        # Menu - File
        "menu_file": "文件(&F)",
        "menu_new": "新建(&N)",
        "menu_open": "打开文件(&O)...",
        "menu_open_folder": "打开文件夹(&F)...",
        "menu_save": "保存(&S)",
        "menu_save_as": "另存为(&A)...",
        "menu_close": "关闭(&C)",
        "menu_exit": "退出(&X)",

        # Menu - Edit
        "menu_edit": "编辑(&E)",
        "menu_undo": "撤销(&U)",
        "menu_redo": "重做(&R)",
        "menu_find": "查找(&F)...",
        "menu_filter": "过滤(&L)...",
        "menu_ai_search": "AI搜索(&A)...",
        "menu_replace": "替换(&R)...",
        "menu_batch_edit": "批量编辑",
        "menu_fill": "填充(&F)...",
        "menu_increment": "递增(&I)",
        "menu_decrement": "递减(&D)",
        "menu_invert": "取反(&I)",
        "menu_reverse": "反转(&V)",
        "menu_goto": "转到(&G)...",

        # Menu - View
        "menu_view": "视图(&V)",
        "menu_arrangement": "排列方式",
        "menu_equal_frame": "等长帧",
        "menu_header_length": "头长度",
        "menu_custom": "自定义(&C)...",
        "menu_display_mode": "显示模式",
        "menu_hexadecimal": "十六进制",
        "menu_binary": "二进制",
        "menu_ascii": "ASCII",
        "menu_octal": "八进制",
        "menu_file_tree": "文件树",
        "menu_ai_panel": "AI面板",
        "menu_value_panel": "Value面板",
        "menu_structure_panel": "结构解析",
        "menu_folding": "折叠",
        "menu_auto_detect": "自动检测区域",
        "menu_fold_all": "全部折叠",
        "menu_unfold_all": "全部展开",
        "menu_multi_view": "多视图",
        "menu_new_view": "新建视图",
        "menu_sync_scroll": "同步滚动",
        "menu_sync_cursor": "同步光标",

        # Menu - Go
        "menu_go": "转到(&G)",
        "menu_back": "后退",
        "menu_forward": "前进",
        "menu_toggle_bookmark": "切换书签",
        "menu_next_bookmark": "下一个书签",
        "menu_prev_bookmark": "上一个书签",

        # Menu - Tools
        "menu_tools": "工具(&T)",
        "menu_compare": "比较文件...",
        "menu_checksum": "计算校验和...",

        # Menu - AI
        "menu_ai": "AI",
        "menu_analyze": "分析数据...",
        "menu_detect_patterns": "检测模式...",
        "menu_generate_code": "生成解析代码...",
        "menu_ai_settings": "AI设置...",

        # Menu - Help
        "menu_help": "帮助(&H)",
        "menu_about": "关于(&A)",

        # Menu - Preferences
        "menu_preferences": "首选项(&P)",
        "menu_language": "语言",

        # Status
        "status_ready": "就绪",
        "status_offset": "偏移: {}",
        "status_selection": "选区: {} 字节",
        "status_size": "大小: {}",
        "status_saved": "已保存",
        "status_caption_offset": "偏移",
        "status_caption_selection": "选区",
        "status_caption_layout": "布局",
        "status_caption_encoding": "编码",
        "status_caption_size": "大小",
        "status_caption_view": "视图",
        "status_caption_edit": "编辑",
        "status_arrangement_equal": "等长帧 {}",
        "status_arrangement_header": "头长度 {}",
        "status_arrangement_custom": "自定义 {}",
        "workspace_state_modified": "已修改",
        "workspace_state_draft": "草稿",
        "workspace_unsaved": "未保存草稿",
        "workspace_panels_count": "{} 个面板",
        "workspace_ruler_scale": "字节刻度",
        "workspace_ruler_window": "窗口 {}-{}",

        # Panels
        "panel_file_info": "文件信息",
        "panel_data_inspector": "数据检查器",
        "panel_ai_assistant": "AI助手",
        "panel_data_tab": "数据",
        "panel_info_tab": "Info",
        "panel_value_tab": "Value",
        "panel_ai_tab": "AI",
        "panel_structure_tab": "结构解析",
        "panel_data_tab_short": "数据",
        "panel_info_tab_short": "信息",
        "panel_value_tab_short": "值",
        "panel_ai_tab_short": "AI",
        "panel_structure_tab_short": "结构",
        "panel_layout_adaptive": "自适应",
        "panel_layout_tabs": "标签页",
        "panel_layout_vertical": "上下拆分",
        "panel_layout_horizontal": "左右拆分",
        "panel_structure_title": "结构解析",
        "panel_structure_offset": "行偏移:",
        "panel_structure_display": "显示:",
        "panel_structure_hex": "十六进制",
        "panel_structure_decimal": "十进制",
        "panel_structure_field": "字段",
        "panel_structure_value": "值",
        "panel_structure_new_config": "新建配置...",
        "panel_structure_manage_config": "管理配置...",
        "panel_structure_new_title": "新建结构解析配置",
        "panel_structure_edit_title": "修改结构解析配置",
        "panel_structure_manage_title": "管理结构解析配置",
        "panel_structure_manage_saved": "已保存配置",
        "panel_structure_edit": "修改",
        "panel_structure_delete": "删除",
        "panel_structure_delete_confirm": "确定删除配置“{}”吗？",
        "panel_structure_name": "配置名称",
        "panel_structure_definition": "C语言结构体定义",
        "panel_structure_confirm": "确认",
        "panel_structure_cancel": "取消",
        "panel_structure_name_placeholder": "输入配置名称",
        "panel_structure_definition_placeholder": "粘贴 C 语言结构体定义",
        "panel_structure_invalid_name": "请输入配置名称。",
        "panel_structure_invalid_definition": "请输入 C 语言结构体定义。",
        "panel_structure_duplicate_name": "已存在同名配置。",
        "panel_structure_parse_error": "结构体解析失败: {}",

        # Dialogs
        "dialog_arrangement": "排列设置",
        "dialog_bytes_per_frame": "每帧字节数:",
        "dialog_header_length": "头长度:",
        "dialog_preferences": "首选项",
        "dialog_language": "语言:",
        "dialog_english": "English (英语)",
        "dialog_chinese": "中文",

        # Find/Replace Dialog
        "dialog_find_replace": "查找/替换",
        "dialog_filter": "行过滤",
        "tab_find": "查找",
        "tab_replace": "替换",
        "tab_results": "结果",
        "label_find": "查找:",
        "label_replace_with": "替换为:",
        "label_replace": "替换:",
        "placeholder_find": "输入搜索模式...",
        "placeholder_replace": "输入替换文本...",
        "label_direction": "方向:",
        "label_up": "向上",
        "label_down": "向下",
        "label_options": "选项:",
        "label_case_sensitive": "区分大小写",
        "label_whole_word": "全词匹配",
        "label_wrap_around": "循环搜索",
        "no_results": "无结果",
        "results_found": "找到 {} 个结果",
        "btn_find_prev": "查找上一个",
        "btn_find_next": "查找下一个",
        "btn_replace": "替换",
        "btn_replace_all": "全部替换",
        "btn_close": "关闭",
        "label_forward": "向前",
        "label_backward": "向后",
        "label_search_mode": "搜索模式",
        "mode_hex": "十六进制 (如: 48 65 6C 6C 6F)",
        "mode_text": "文本",
        "mode_regex": "正则",
        "placeholder_replace": "输入替换内容...",
        "label_replace_action": "替换:",
        "btn_replace_next": "替换下一个",
        "label_prompt_replace_all": "全部替换时提示",
        "filter_description": "使用类 C 语法编写行过滤条件。用 data[x] 读取当前行偏移 x 的字节，例如：data[0] > 1 或 data[0] & 1 == 1。",
        "filter_create_group": "创建过滤条件",
        "filter_input_placeholder": "输入一条条件，例如：data[0] > 1",
        "filter_add_condition": "添加条件",
        "filter_saved_group": "已保存组合:",
        "filter_saved_group_placeholder": "选择已保存的过滤组合...",
        "filter_active_group": "当前生效的过滤条件",
        "filter_active_hint": "左侧条件会同时生效，只有满足全部规则的行会显示。",
        "filter_history_group": "历史过滤条件",
        "filter_history_hint": "双击或选中后导入到左侧当前生效列表。",
        "filter_import_condition": "导入选中项",
        "filter_remove_selected": "移除选中",
        "filter_clear_active": "清空",
        "filter_save_combo": "保存当前过滤组合",
        "filter_apply": "过滤",
        "filter_empty_error": "请输入过滤条件。",
        "filter_invalid_error": "过滤条件无效: {}",
        "filter_save_empty_error": "请先添加至少一条当前生效的过滤条件。",
        "filter_group_name": "组合名称:",
        "filter_group_name_empty_error": "请输入组合名称。",
        "filter_overwrite_group": "已存在名为“{}”的过滤组合，是否覆盖？",
        "filter_no_active_view": "当前没有可过滤的视图",
        "filter_status_applied": "过滤后显示 {}/{} 行",
        "filter_status_cleared": "已清除过滤条件",

        # File info
        "info_name": "名称:",
        "info_size": "大小:",
        "info_type": "类型:",
        "info_path": "路径:",
        "info_checksums": "校验和",
        "info_md5": "MD5:",
        "info_sha256": "SHA256:",

        # Data inspector
        "inspector_offset": "偏移:",
        "inspector_hex": "十六进制:",
        "inspector_signed": "有符号:",
        "inspector_unsigned": "无符号:",
        "inspector_binary": "二进制:",
        "inspector_ascii": "ASCII:",
        "inspector_octal": "八进制:",

        # AI Panel
        "ai_not_configured": "未配置",
        "ai_analyze_btn": "分析数据",
        "ai_detect_btn": "检测模式",
        "ai_gen_code_btn": "生成代码",
    }
}

# Current language
_current_language = "en"


def set_language(lang: str):
    """Set the current language."""
    global _current_language
    if lang in _translations:
        _current_language = lang


def get_language() -> str:
    """Get the current language."""
    return _current_language


def tr(key: str, *args) -> str:
    """
    Translate a key to the current language.

    Args:
        key: The translation key
        *args: Optional format arguments

    Returns:
        Translated string
    """
    global _current_language
    if _current_language not in _translations:
        _current_language = "en"

    text = _translations.get(_current_language, {}).get(key, key)

    if args:
        try:
            text = text.format(*args)
        except Exception:
            pass

    return text


def get_available_languages():
    """Get list of available languages."""
    return list(_translations.keys())


def get_language_display_name(lang: str) -> str:
    """Get display name for a language."""
    names = {
        "en": "English",
        "zh": "中文"
    }
    return names.get(lang, lang)
