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


_current_pipe: Optional[int] = None
_server_thread: Optional[threading.Thread] = None
_pipe_guard = threading.Lock()


def _get_dll_path() -> str:
    """Return the path to ``GflessDLL.dll`` searching common locations."""
    candidates = []
    if getattr(sys, "frozen", False):
        # when packaged with PyInstaller ``sys.executable`` points to the exe
        candidates.append(os.path.join(os.path.dirname(sys.executable), "GflessDLL.dll"))
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "GflessDLL.dll"))  # type: ignore[attr-defined]

    # source tree or one-folder mode
    candidates.append(os.path.join(os.path.dirname(__file__), "GflessDLL.dll"))

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


def is_dll_injected(pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe", dll_name: str = "GflessDLL.dll") -> bool:
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
    """Inject GflessDLL.dll into the given process using Injector.exe."""
    proc = _find_game_process(pid, exe_name)
    if not proc:
        raise RuntimeError(f"{exe_name} process not found")

    injector = _get_injector_path()
    dll_path = _get_dll_path()

    if not os.path.exists(injector):
        raise FileNotFoundError("Injector.exe not found")
    if not os.path.exists(dll_path):
        raise FileNotFoundError("GflessDLL.dll not found")

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
    """Inject GflessDLL.dll if needed.

    Parameters
    ----------
    force:
        When ``True`` the DLL is injected even if already loaded. This is
        useful when changing login parameters because the game only applies
        them immediately after injection.
    """

    if not force and is_dll_injected(pid, exe_name):
        print("GflessDLL.dll already injected")
        return True

    print("Injecting GflessDLL.dll...")
    if inject_dll(pid, exe_name):
        print("GflessDLL.dll injected successfully")
        return True

    print("Failed to inject GflessDLL.dll")
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
    character = int(s.value("default_character", -1))
    s.endGroup()
    return lang, server, channel, character


def login_from_config(delay: float = 1.0, *, pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe") -> None:
    """Login using parameters stored in QSettings."""
    lang, server, channel, character = load_config()
    login(lang, server, channel, character, delay=delay, pid=pid, exe_name=exe_name)

PIPE_NAME = r"\\.\pipe\MiServidor"

def _terminate_login_servers() -> None:
    """Terminate any known processes that could own ``PIPE_NAME``.

    The official launcher (``GflessClient.exe``) must remain open, so we keep
    a list of protected executables and skip them when cleaning up stale pipe
    servers.
    """

    protected = {"gflessclient.exe"}
    # ``names`` contains executables that are safe to terminate automatically.
    # It is intentionally empty so the launcher stays alive even when
    # reinjecting the DLL.
    names = set()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info["name"]
            if not name or proc.pid == os.getpid():
                continue

            name = name.lower()
            if name in protected:
                continue

            if name in names:
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

    # retry a few times in case a previous instance is still shutting down
    for _ in range(3):
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
            if exc.winerror in (5, 231):
                # either access denied or pipe already exists/busy
                _terminate_login_servers()
                time.sleep(0.5)
                continue
            raise
    return None


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
        required = {
            "DisableNosmall",
            "AutoLogin",
            "ServerLanguage",
            "Server",
            "Channel",
            "Character",
        }
        served = set()
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
            try:
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
                    continue
            except pywintypes.error as exc:
                if exc.winerror == 232:
                    # Pipe closed while responding; stop the server gracefully.
                    break
                raise
            served.add(command)
            if required.issubset(served):
                try:
                    win32pipe.DisconnectNamedPipe(pipe)
                except pywintypes.error:
                    pass
                break
    finally:
        try:
            win32file.CloseHandle(pipe)
        except pywintypes.error:
            pass
        global _current_pipe, _server_thread
        if _current_pipe == pipe:
            _current_pipe = None
        if _server_thread is threading.current_thread():
            _server_thread = None
        if _pipe_guard.locked():
            _pipe_guard.release()


def _start_pipe_server(
    lang: int,
    server: int,
    channel: int,
    character: int,
    *,
    auto_login: bool = True,
    disable_nosmall: bool = False,
) -> None:
    """Start a background thread to serve login parameters.

    The caller must acquire ``_pipe_guard`` before invoking this helper.  The
    guard is released automatically once the server thread finishes so that
    subsequent login attempts wait for the handshake to complete.
    """

    pipe = _create_pipe()
    if pipe is None:
        raise RuntimeError(
            "Another Gfless instance is providing login parameters "
            "and could not be closed automatically."
        )

    server_thread = threading.Thread(
        target=_serve_pipe,
        args=(
            pipe,
            lang,
            server,
            channel,
            character,
        ),
        kwargs={
            "auto_login": auto_login,
            "disable_nosmall": disable_nosmall,
        },
        daemon=True,
    )
    global _current_pipe, _server_thread
    _current_pipe = pipe
    _server_thread = server_thread
    server_thread.start()


def _send_relogin_command(
    lang: Optional[int] = None,
    server: Optional[int] = None,
    channel: Optional[int] = None,
    character: Optional[int] = None,
) -> None:
    """Send a ``Relogin`` command through ``PIPE_NAME``.

    When all parameters are provided, they are expected to be **1-based**
    and will be sent alongside the ``Relogin`` command.  Otherwise a plain
    ``Relogin`` command is issued for backward compatibility.
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
        if None not in (lang, server, channel, character):
            message = f"Relogin {lang} {server} {channel} {character}".encode(
                "ascii"
            )
        else:
            message = b"Relogin"
        win32file.WriteFile(handle, message)
    finally:
        win32file.CloseHandle(handle)


def close_login_pipe() -> None:
    """Close the active login pipe and stop its thread if running."""
    global _current_pipe, _server_thread
    if _current_pipe is None:
        return
    pipe = _current_pipe
    thread = _server_thread
    _current_pipe = None
    _server_thread = None
    try:
        win32file.CloseHandle(pipe)
    except Exception:
        pass
    if thread is not None:
        # ``join`` raises ``RuntimeError`` if the thread was never started,
        # which can happen when an earlier failure stops the login pipe
        # before the worker thread gets scheduled.  Guard against this to
        # avoid bubbling the error up to the scripting engine and silently
        # releasing the pipe instead.
        if thread.is_alive():
            # allow the server thread time to exit so the pipe is released
            thread.join(timeout=2.0)
    # ensure no external login servers keep the pipe busy
    _terminate_login_servers()

def login(
    lang: int,
    server: int,
    channel: int,
    character: int,
    delay: float = 1.0,
    *,
    pid: Optional[int] = None,
    exe_name: str = "NostaleClientX.exe",
    force_reinject: bool = False,
):
    """Inject the DLL and respond to its login parameter requests.

    The character index is zero-based; ``-1`` means staying at the
    selection screen.  The DLL expects ``0`` to remain in the selection or
    ``1``–``4`` to pick a character, so we map it automatically.
    """

    dll_character = 0 if character == -1 else character + 1

    if is_dll_injected(pid, exe_name) and not force_reinject:
        try:
            update_login(
                lang,
                server,
                channel,
                character,
                pid=pid,
                exe_name=exe_name,
            )
            return
        except RuntimeError:
            close_login_pipe()

    _pipe_guard.acquire()
    guard_released = False
    try:
        close_login_pipe()

        try:
            _start_pipe_server(
                lang,
                server,
                channel,
                dll_character,
                auto_login=True,
                disable_nosmall=False,
            )
            guard_released = True
        except pywintypes.error as exc:
            if exc.winerror == 231:
                raise RuntimeError(
                    "Another Gfless instance is providing login parameters "
                    "and could not be closed automatically."
                ) from exc
            raise
            
        try:
            if is_dll_injected(pid, exe_name):
                _send_relogin_command(lang, server, channel, dll_character)
            else:
                if not ensure_injected(pid, exe_name):
                    raise RuntimeError("Failed to inject GflessDLL.dll")
        except Exception:
            close_login_pipe()
            raise
    finally:
        if not guard_released and _pipe_guard.locked():
            _pipe_guard.release()


def update_login(
    lang: int,
    server: int,
    channel: int,
    character: int,
    *,
    pid: Optional[int] = None,
    exe_name: str = "NostaleClientX.exe",
    force_reinject: bool = False,
) -> None:
    """Update login parameters reusing an existing ``GflessDLL.dll`` injection.

    Parameters
    ----------
    lang:
        Language/region index to log in.
    server:
        Server index within ``lang``.
    channel:
        Channel index within ``server``.
    character:
        Character slot index (0-based); ``-1`` means staying at the
        character selection screen.
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

    dll_character = 0 if character == -1 else character + 1

    _pipe_guard.acquire()
    guard_released = False
    try:
        close_login_pipe()

        try:
            _start_pipe_server(
                lang,
                server,
                channel,
                dll_character,
                auto_login=True,
                disable_nosmall=False,
            )
            guard_released = True
        except pywintypes.error as exc:
            if exc.winerror == 231:
                raise RuntimeError(
                    "Another Gfless instance is providing login parameters "
                    "and could not be closed automatically."
                ) from exc
            raise

        try:
            ensure_injected(pid, exe_name, force=force_reinject)
            _send_relogin_command(lang, server, channel, dll_character)
        except Exception:
            close_login_pipe()
            raise
    finally:
        if not guard_released and _pipe_guard.locked():
            _pipe_guard.release()