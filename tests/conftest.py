import pytest

from PyQt6.QtWidgets import QApplication

from src.app import OpenHexApp
from src.models.file_handle import FileState
from src.utils.i18n import set_language


def _discard_top_level_widgets():
    """Destroy windows without triggering save-confirm dialogs."""
    app = QApplication.instance()
    if app is None:
        return

    for widget in list(app.topLevelWidgets()):
        editor = getattr(widget, "_hex_editor", None)
        document_model = getattr(editor, "_document_model", None)
        if document_model is not None:
            for document in document_model.documents:
                document.file_state = FileState.UNCHANGED
        widget.close()
    app.processEvents()


@pytest.fixture(autouse=True)
def reset_app_state():
    """Keep tests isolated from persisted application settings and windows."""
    app = OpenHexApp.instance()
    _discard_top_level_widgets()
    app.settings.clear()
    app.settings.sync()
    set_language("en")

    yield

    _discard_top_level_widgets()
    app.settings.clear()
    app.settings.sync()
    set_language("en")


@pytest.fixture
def stats():
    """Compatibility fixture for legacy script-style tests."""
    return {"passed": 0, "failed": 0, "tests": []}
