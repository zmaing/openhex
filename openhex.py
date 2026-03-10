#!/usr/bin/env python3
"""
openhex - AI Enhanced Binary Editor

A powerful binary file editor with AI capabilities for analyzing,
editing, and understanding binary data.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Main entry point for openhex."""
    from src.app import OpenHexApp
    from src.main import OpenHexMainWindow

    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
