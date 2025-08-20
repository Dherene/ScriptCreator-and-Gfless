import os
import sys
import time
import subprocess
import ctypes
from typing import Optional
import threading

import psutil
from PyQt5.QtCore import QSettings
import win32pipe
import win32file
import win32security
import pywintypes


def _get_dll_path() -> str:
    """Return the path to ``gfless.dll`` searching common locations."""
    candidates = []
    if getattr(sys, "frozen", False):
        # when packaged with PyInstaller ``sys.executable`` points to the exe
        candidates.append(os.path.join(os.path.dirname(sys.executable), "gfless.dll"))
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "gfless.dll"))  # type: ignore[attr-defined]

    # source tree or one-folder mode
    candidates.append(os.path.join(os.path.dirname(__file__), "gfless.dll"))

    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)

    # fallback to the first candidate for error reporting
    return os.path.abspath(candidates[0])


def _get_injector_path() -> str:
    """Return the path to ``Injector.exe`` searching common locations."""
    candidates = []
    if getattr(sys, "frozen", False):
        # when packaged with PyInstaller ``sys.executable`` points to the exe
        candidates.append(os.path.join(os.path.dirname(sys.executable), "Injector.exe"))
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "Injector.exe"))  # type: ignore[attr-defined]

    # source tree or one-folder mode
    candidates.append(os.path.join(os.path.dirname(__file__), "Injector.exe"))

    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)

    # fallback to the first candidate for error reporting
    return os.path.abspath(candidates[0])


def _find_game_process(pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe") -> Optional[psutil.Process]:
    """Return the process matching the given PID or executable name."""
    if pid is not None:
        try:
            return psutil.Process(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    exe_name = exe_name.lower()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == exe_name:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def is_dll_injected(pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe", dll_name: str = "gfless.dll") -> bool:
    """Return True if the DLL is loaded in the specified process."""
    proc = _find_game_process(pid, exe_name)
    if not proc:
        return False
    try:
        for m in proc.memory_maps():
            if os.path.basename(m.path).lower() == dll_name.lower():
                return True
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass
    return False


def inject_dll(pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe") -> bool:
    """Inject gfless.dll into the given process using Injector.exe."""
    proc = _find_game_process(pid, exe_name)
    if not proc:
        raise RuntimeError(f"{exe_name} process not found")

    injector = _get_injector_path()
    dll_path = _get_dll_path()

    if not os.path.exists(injector):
        raise FileNotFoundError("Injector.exe not found")
    if not os.path.exists(dll_path):
        raise FileNotFoundError("gfless.dll not found")

    cmd = [injector, str(proc.pid), dll_path]
    print("Running injector:", " ".join(f'"{c}"' if ' ' in c else c for c in cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        return False
    except OSError as exc:
        if getattr(exc, "winerror", None) == 740:
            # elevation required, retry via ShellExecute
            params = f"{proc.pid} \"{dll_path}\""
            print("Requesting elevated Injector.exe...")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", injector, params, None, 1)
        else:
            raise

    # give the process a moment to load the DLL
    time.sleep(1)
    return True


def ensure_injected(
    pid: Optional[int] = None,
    exe_name: str = "NostaleClientX.exe",
    *,
    force: bool = False,
) -> bool:
    """Inject gfless.dll if needed.

    Parameters
    ----------
    force:
        When ``True`` the DLL is injected even if already loaded. This is
        useful when changing login parameters because the game only applies
        them immediately after injection.
    """

    if not force and is_dll_injected(pid, exe_name):
        print("gfless.dll already injected")
        return True

    print("Injecting gfless.dll...")
    if inject_dll(pid, exe_name):
        print("gfless.dll injected successfully")
        return True

    print("Failed to inject gfless.dll")
    return False


def _settings() -> QSettings:
    """Return ``QSettings`` for the same registry keys as Gfless.

    The original launcher is a 32‑bit application and therefore stores
    its settings under ``Wow6432Node`` on 64‑bit systems.  When running a
    64‑bit Python build we need to explicitly open this path so that both
    applications read and write the very same values.
    """

    wow_path = (
        r"HKEY_CURRENT_USER\Software\Wow6432Node\Hatz Nostale\Gfless Client"
    )
    s = QSettings(wow_path, QSettings.NativeFormat)
    # If the key does not exist (e.g. 32‑bit Python), fall back to the
    # standard location.
    if not s.childKeys() and not s.childGroups():
        s = QSettings(r"HKEY_CURRENT_USER\Software\Hatz Nostale\Gfless Client",
                       QSettings.NativeFormat)
    return s


def save_config(lang: int, server: int, channel: int, character: int) -> None:
    """Persist selected server parameters using the same keys as Gfless."""
    s = _settings()
    s.beginGroup("MainWindow")
    s.setValue("default_serverlocation", lang)
    s.setValue("default_server", server)
    s.setValue("default_channel", channel)
    s.setValue("default_character", character)
    s.endGroup()
    s.sync()


def load_config() -> tuple[int, int, int, int]:
    """Load saved server parameters."""
    s = _settings()
    s.beginGroup("MainWindow")
    lang = int(s.value("default_serverlocation", 0))
    server = int(s.value("default_server", 0))
    channel = int(s.value("default_channel", 0))
    character = int(s.value("default_character", 0))
    s.endGroup()
    return lang, server, channel, character


def login_from_config(delay: float = 1.0, *, pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe") -> None:
    """Login using parameters stored in QSettings."""
    lang, server, channel, character = load_config()
    login(lang, server, channel, character, delay=delay, pid=pid, exe_name=exe_name)

PIPE_NAME = r"\\.\pipe\GflessClient"

def _terminate_login_servers() -> None:
    """Terminate any known processes that could own ``PIPE_NAME``."""
    # GflessClient.exe is the official launcher that also provides this pipe.
    names = {"gflessclient.exe"}
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() in names \
                    and proc.pid != os.getpid():
                proc.terminate()
                proc.wait(2)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            continue


def _create_pipe() -> Optional[int]:
    """Return a handle to ``PIPE_NAME`` or ``None`` if another server is running."""
    sa = win32security.SECURITY_ATTRIBUTES()
    sd = win32security.SECURITY_DESCRIPTOR()
    # allow Everyone to connect so an elevated process can access the pipe
    sd.SetSecurityDescriptorDacl(True, None, False)
    sa.SECURITY_DESCRIPTOR = sd

    try:
        return win32pipe.CreateNamedPipe(
            PIPE_NAME,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_BYTE
            | win32pipe.PIPE_READMODE_BYTE
            | win32pipe.PIPE_WAIT,
            1,
            255,
            255,
            0,
            sa,
        )
    except pywintypes.error as exc:
        if exc.winerror == 5:
            _terminate_login_servers()
            time.sleep(0.5)
            try:
                return win32pipe.CreateNamedPipe(
                    PIPE_NAME,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_BYTE
                    | win32pipe.PIPE_READMODE_BYTE
                    | win32pipe.PIPE_WAIT,
                    1,
                    255,
                    255,
                    0,
                    sa,
                )
            except pywintypes.error as exc2:
                if exc2.winerror == 5:
                    return None
                raise
        raise


def _serve_pipe(
    pipe: int,
    lang: int,
    server: int,
    channel: int,
    character: int,
    *,
    auto_login: bool = True,
    disable_nosmall: bool = False,
) -> None:
    """Respond to ``gfless.dll`` login requests on ``pipe``."""
    try:
        win32pipe.ConnectNamedPipe(pipe, None)
        while True:
            try:
                data = win32file.ReadFile(pipe, 255)[1].decode("ascii")
            except pywintypes.error:
                break
            parts = data.strip().split()
            if len(parts) != 2:
                win32file.WriteFile(pipe, b"0")
                continue
            command = parts[1]
            if command == "DisableNosmall":
                win32file.WriteFile(pipe, b"1" if disable_nosmall else b"0")
            elif command == "AutoLogin":
                win32file.WriteFile(pipe, b"1" if auto_login else b"0")
            elif command == "ServerLanguage":
                win32file.WriteFile(pipe, str(lang).encode())
            elif command == "Server":
                win32file.WriteFile(pipe, str(server).encode())
            elif command == "Channel":
                win32file.WriteFile(pipe, str(channel).encode())
            elif command == "Character":
                win32file.WriteFile(pipe, str(character).encode())
            else:
                win32file.WriteFile(pipe, b"0")
    finally:
        win32file.CloseHandle(pipe)


def _send_relogin_command() -> None:
    """Send a ``Relogin`` command through ``PIPE_NAME``.

    The injected DLL listens on this pipe for commands. When it receives
    ``Relogin`` it will reconnect to request the current login parameters,
    which are served by ``login`` or ``update_login``.
    """

    try:
        handle = win32file.CreateFile(
            PIPE_NAME,
            win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )
    except pywintypes.error as exc:
        raise RuntimeError(
            "Could not connect to Gfless pipe; is the DLL injected?"
        ) from exc
    try:
        win32file.WriteFile(handle, b"0 Relogin")
    finally:
        win32file.CloseHandle(handle)

def login(lang: int, server: int, channel: int, character: int, delay: float = 1.0, *, pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe"):
    """Inject the DLL and respond to its login parameter requests.

    The character index provided is zero-based as used by the UI. The DLL
    expects values from 1 to 4, so we adjust it automatically.
    """

    # the DLL expects characters numbered from 1, while the UI uses 0..3
    character += 1

    try:
        pipe = _create_pipe()
    except pywintypes.error as exc:
        if exc.winerror == 231:
            update_login(lang, server, channel, character, pid)
            return
        raise
    if pipe is None:
        raise RuntimeError(
            "Another Gfless instance is providing login parameters "
            "and could not be closed automatically."
        )

    server_thread = threading.Thread(
        target=_serve_pipe,
        args=(pipe, lang, server, channel, character),
        daemon=True,
    )
    server_thread.start()
    try:
        if is_dll_injected(pid, exe_name):
            _send_relogin_command()
        else:
            if not ensure_injected(pid, exe_name):
                raise RuntimeError("Failed to inject gfless.dll")
    finally:
        server_thread.join(timeout=10)


def update_login(
    lang: int,
    server: int,
    channel: int,
    character: int,
    *,
    pid: Optional[int] = None,
    exe_name: str = "NostaleClientX.exe",
) -> None:
    """Update login parameters reusing an existing ``gfless.dll`` injection.

    Parameters
    ----------
    lang:
        Language/region index to log in.
    server:
        Server index within ``lang``.
    channel:
        Channel index within ``server``.
    character:
        Character slot index (0-based) as used by the UI.
    pid:
        Optional process ID of the game client. Use this when running
        multiple clients simultaneously.
    exe_name:
        Executable name to locate the client process when ``pid`` is not
        provided.

    This helper allows script conditions (for example after receiving
    ``svrlist``) to switch server, channel or character without forcing a
    new DLL injection.
    """
    # the DLL expects characters numbered from 1, while the UI uses 0..3
    character += 1

    pipe = _create_pipe()
    if pipe is None:
        raise RuntimeError(
            "Another Gfless instance is providing login parameters "
            "and could not be closed automatically."
        )

    server_thread = threading.Thread(
        target=_serve_pipe,
        args=(pipe, lang, server, channel, character),
        daemon=True,
    )
    server_thread.start()

    # Reuse existing injection so the new parameters take effect
    ensure_injected(pid, exe_name, force=False)
    server_thread.join(timeout=10)