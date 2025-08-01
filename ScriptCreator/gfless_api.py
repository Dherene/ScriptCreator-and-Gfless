import ctypes
import os
import sys
import time
import subprocess
from typing import Optional

import psutil
from PyQt5.QtCore import QSettings


def _get_dll_path() -> str:
    """Return the path to gfless.dll, accounting for PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(base, "gfless.dll"))


def _get_injector_path() -> str:
    """Return the path to Injector.exe next to the executable (even in PyInstaller)."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(base, "Injector.exe"))


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


_dll = ctypes.CDLL(_get_dll_path())

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

    cmd = [injector, str(proc.pid), dll_path]
    print("Running injector:", " ".join(f'"{c}"' if ' ' in c else c for c in cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        return False

    # give the process a moment to load the DLL
    time.sleep(1)
    return is_dll_injected(proc.pid if proc else None, exe_name, os.path.basename(dll_path))


def ensure_injected(pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe") -> bool:
    """Ensure gfless.dll is injected, injecting if necessary."""
    if is_dll_injected(pid, exe_name):
        print("gfless.dll already injected")
        return True
    print("Injecting gfless.dll...")
    if inject_dll(pid, exe_name):
        print("gfless.dll injected successfully")
        return True
    print("Failed to inject gfless.dll")
    return False


def _settings() -> QSettings:
    """Return QSettings object used for persistent config."""
    return QSettings('PBapi', 'Script Creator')


def save_config(lang: int, server: int, channel: int, character: int) -> None:
    """Persist selected server parameters."""
    s = _settings()
    s.setValue("serverLanguage", lang)
    s.setValue("server", server)
    s.setValue("channel", channel)
    s.setValue("character", character)


def load_config() -> tuple[int, int, int, int]:
    """Load saved server parameters."""
    s = _settings()
    lang = int(s.value("serverLanguage", 0))
    server = int(s.value("server", 0))
    channel = int(s.value("channel", 0))
    character = int(s.value("character", 0))
    return lang, server, channel, character


def login_from_config(delay: float = 1.0, *, pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe") -> None:
    """Login using parameters stored in QSettings."""
    lang, server, channel, character = load_config()
    login(lang, server, channel, character, delay=delay, pid=pid, exe_name=exe_name)

_dll.Gfless_SelectLanguage.argtypes = [ctypes.c_int]
_dll.Gfless_SelectServer.argtypes = [ctypes.c_int]
_dll.Gfless_SelectChannel.argtypes = [ctypes.c_int]
_dll.Gfless_SelectCharacter.argtypes = [ctypes.c_int]
_dll.Gfless_ClickStart.argtypes = []

def select_language(lang: int):
    """Select game language."""
    _dll.Gfless_SelectLanguage(lang)

def select_server(server: int):
    """Select game server."""
    _dll.Gfless_SelectServer(server)

def select_channel(channel: int):
    """Select game channel."""
    _dll.Gfless_SelectChannel(channel)

def select_character(char_index: int):
    """Select character slot."""
    _dll.Gfless_SelectCharacter(char_index)

def click_start():
    """Click start button after character selection."""
    _dll.Gfless_ClickStart()

def login(lang: int, server: int, channel: int, character: int, delay: float = 1.0, *, pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe"):
    """Login sequence using the exported DLL functions."""
    ensure_injected(pid, exe_name)
    select_language(lang)
    time.sleep(delay)
    select_server(server)
    time.sleep(delay)
    select_channel(channel)
    time.sleep(delay)
    select_character(character)
    time.sleep(delay)
    click_start()