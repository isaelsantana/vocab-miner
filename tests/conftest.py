"""
Mock Anki / Qt before any test imports vocab_miner.
This allows running tests outside of Anki's Python environment.
"""
import sys
from unittest.mock import MagicMock


class _FakeQThread:
    """Minimal QThread stand-in so AIWorker can inherit from it."""
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass


class _FakeSignal:
    """Minimal pyqtSignal stand-in (descriptor not needed for unit tests)."""
    def __init__(self, *types):
        pass

    def emit(self, *args):
        pass

    def connect(self, fn):
        pass


_qt_mock = MagicMock()
_qt_mock.QThread = _FakeQThread
_qt_mock.pyqtSignal = _FakeSignal

# Register mocks before vocab_miner is imported
for _mod in ("aqt", "aqt.utils", "aqt.qt"):
    sys.modules.setdefault(_mod, _qt_mock)
