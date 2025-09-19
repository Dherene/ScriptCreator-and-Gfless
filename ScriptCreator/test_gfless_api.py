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
    module._create_pipe = lambda *a, **k: object()
    def _serve_pipe_stub(*args, **kwargs):
        module._current_pipe = None
        module._server_thread = None
        if module._pipe_guard.locked():
            module._pipe_guard.release()

    module._serve_pipe = _serve_pipe_stub
    return module, writes

def test_update_login_sends_new_values():
    gfless_api, writes = _load_module()
    gfless_api.is_dll_injected = lambda *a, **k: True
    gfless_api.ensure_injected = lambda *a, **k: True

    gfless_api.update_login(1, 2, 3, 0)

    assert writes == [b"Relogin 1 2 3 1"]


def test_update_login_with_character_minus_one():
    gfless_api, writes = _load_module()
    gfless_api.is_dll_injected = lambda *a, **k: True
    gfless_api.ensure_injected = lambda *a, **k: True

    gfless_api.update_login(1, 2, 3, -1)

    assert writes == [b"Relogin 1 2 3 0"]


def test_login_force_reinject_reinjects_without_relogin():
    gfless_api, writes = _load_module()
    gfless_api.is_dll_injected = lambda *a, **k: True
    calls = []

    def ensure_injected(pid=None, exe_name="NostaleClientX.exe", *, force=False):
        calls.append((pid, exe_name, force))
        return True

    gfless_api.ensure_injected = ensure_injected

    gfless_api.login(
        1,
        2,
        3,
        -1,
        pid=42,
        exe_name="custom.exe",
        force_reinject=True,
    )

    assert calls == [(42, "custom.exe", True)]
    assert writes == []