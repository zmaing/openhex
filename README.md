# HexForge

**AI Enhanced Binary Editor**

A powerful binary file editor built with PyQt6, featuring AI-powered analysis, pattern detection, and code generation.

## Features

- **Core Editing**: Open, edit, and save binary files with undo/redo support
- **Multiple Display Modes**: Hexadecimal, Binary, ASCII, and Octal views
- **Large File Support**: Efficient memory-mapped file access for GB-sized files
- **File Browser**: VSCode-like file tree for quick navigation
- **AI Integration**: Local (Ollama) and Cloud (OpenAI/Anthropic) AI providers
- **Smart Analysis**: Pattern detection, structure inference, and anomaly detection
- **Code Generation**: Generate parsing code in C, Python, and Rust

## Requirements

- Python 3.10+
- PyQt6 >= 6.6.0
- macOS (currently optimized for macOS)

## Installation

```bash
# Clone the repository
cd hex_forge

# Install dependencies
pip install -r requirements.txt

# Run
python3 hex_forge.py
```

## AI Setup

### Local AI (Ollama)
1. Install [Ollama](https://ollama.ai)
2. Pull a model: `ollama pull qwen:7b`
3. Configure in HexForge settings

### Cloud AI
1. Get API key from OpenAI or Anthropic
2. Configure in HexForge AI settings

## Building

```bash
# Build macOS app
bash build_app.sh

# Build DMG
bash build_app.sh --dmg
```

## Architecture

```
hex_forge/
├── hex_forge.py          # Entry point
├── config/                # Configuration
├── src/
│   ├── models/          # Data models
│   ├── core/            # Core logic
│   │   └── parser/      # Binary parsers
│   ├── ai/              # AI integration
│   ├── ui/              # User interface
│   └── utils/           # Utilities
└── tests/               # Tests
```

## License

MIT License
