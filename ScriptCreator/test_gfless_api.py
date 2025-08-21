import sys
import types
import importlib.util
from pathlib import Path


def _load_module():
    writes = []

    pywintypes = types.SimpleNamespace(error=Exception)

    handle = object()

    def CreateFile(*args, **kwargs):
        return handle

    def WriteFile(h, data):
        writes.append(data)
        return (0, None)

    def CloseHandle(h):
        pass

    win32file = types.SimpleNamespace(
        CreateFile=CreateFile,
        WriteFile=WriteFile,
        CloseHandle=CloseHandle,
        GENERIC_WRITE=0,
        OPEN_EXISTING=0,
    )
    win32pipe = types.SimpleNamespace()
    win32security = types.SimpleNamespace()
    PyQt5 = types.SimpleNamespace(QtCore=types.SimpleNamespace(QSettings=object))
    psutil = types.SimpleNamespace(
        process_iter=lambda *a, **k: [],
        NoSuchProcess=Exception,
        AccessDenied=Exception,
        Process=lambda pid: None,
    )

    sys.modules.update({
        "pywintypes": pywintypes,
        "win32file": win32file,
        "win32pipe": win32pipe,
        "win32security": win32security,
        "PyQt5": PyQt5,
        "PyQt5.QtCore": PyQt5.QtCore,
        "psutil": psutil,
    })

    spec = importlib.util.spec_from_file_location(
        "gfless_api", Path(__file__).resolve().parents[1] / "ScriptCreator" / "gfless_api.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, writes


def test_update_login_sends_new_values():
    gfless_api, writes = _load_module()
    gfless_api.is_dll_injected = lambda *a, **k: True
    gfless_api.ensure_injected = lambda *a, **k: True

    gfless_api.update_login(1, 2, 3, 0)

    assert writes == [b"Relogin 1 2 3 1"]