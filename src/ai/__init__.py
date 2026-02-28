"""
AI Package

AI integration for data analysis and code generation.
"""

from .base import AIBase, AISettings
from .local import LocalAI
from .cloud import CloudAI
from .analyzer import AIAnalyzer
from .search import AISearch
from .coder import CodeGenerator
from .manager import AIManager

__all__ = [
    "AIBase",
    "AISettings",
    "LocalAI",
    "CloudAI",
    "AIAnalyzer",
    "AISearch",
    "CodeGenerator",
    "AIManager",
]
