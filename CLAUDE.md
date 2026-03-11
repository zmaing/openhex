# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

openhex is an **AI-Enhanced Binary Editor** (hex editor) for macOS, built with PyQt6. It features AI-powered analysis, pattern detection, code generation, and efficient handling of large files via memory-mapped files.

## Commands

### Running the Application

```bash
cd /Users/zhanghaoli/Documents/git/openhex
pip install -r requirements.txt
python3 openhex.py
```

### Building macOS App

```bash
cd /Users/zhanghaoli/Documents/git/openhex
bash build_app.sh                  # Builds to dist/openhex.app
bash build_app.sh --dmg            # Builds DMG installer
```

### Running Tests

```bash
cd /Users/zhanghaoli/Documents/git/openhex
python3 tests/test_quick.py        # Quick test (requires display or offscreen mode)
python3 tests/test_search_engine.py
python3 tests/test_undo_stack.py
```

Set `QT_QPA_PLATFORM=offscreen` for headless testing.

## Architecture

```
openhex/
├── openhex.py          # Entry point (wrapper)
├── src/
│   ├── app.py           # OpenHexApp class
│   ├── main.py          # OpenHexMainWindow (main UI)
│   ├── core/           # Data handling layer
│   │   ├── data_model.py      # Display modes (HEX, BINARY, ASCII, OCTAL)
│   │   ├── search_engine.py   # Hex/text search
│   │   └── parser/            # Binary parsers
│   ├── ai/             # AI integration (Ollama, OpenAI, Anthropic)
│   ├── models/         # Data models (cursor, selection, undo stack)
│   ├── ui/             # PyQt6 UI components
│   │   ├── panels/    # File browser, file info, data value panels
│   │   ├── dialogs/   # Goto, find/replace, AI settings dialogs
│   │   └── views/     # Hex view, minimap, diff view
│   ├── utils/         # Utilities (logger, encoding, i18n)
│   └── plugins/       # Plugin system
└── tests/              # Test scripts
```

### Key Patterns

- **Data/UI Separation**: Core logic in `src/core/`, UI in `src/ui/`
- **MVC Pattern**: Models for data, views for display
- **Signal/Slot**: PyQt6 signals for component communication
- **Memory-Mapped Files**: Efficient large file handling via `mmap`
- **Virtual Scrolling**: Efficient rendering for large files

### AI Integration

Located in `src/ai/`:
- **Local**: Ollama support
- **Cloud**: OpenAI and Anthropic API support
- Features: Pattern detection, structure inference, code generation (C, Python, Rust)

### Keyboard Shortcuts

- `Ctrl+O`: Open file
- `Ctrl+S`: Save file
- `Ctrl+Shift+S`: Save As
- `Ctrl+F`: Focus search box
- `Ctrl+G`: Jump to address
- `Ctrl+Q`: Quit

## Dependencies

- Python 3.10+
- PyQt6 >= 6.6.0
- httpx >= 0.27.0
- aiohttp >= 3.9.0
- pydantic >= 2.0.0
