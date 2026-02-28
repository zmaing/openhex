#!/usr/bin/env python3
"""
HexForge - AI Enhanced Binary Editor

A powerful binary file editor with AI capabilities for analyzing,
editing, and understanding binary data.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Main entry point for HexForge."""
    from src.app import HexForgeApp
    from src.main import HexForgeMainWindow

    app = HexForgeApp.instance()
    window = HexForgeMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
