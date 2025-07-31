import ctypes
import time

_dll = ctypes.CDLL('gfless.dll')

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

def login(lang: int, server: int, channel: int, character: int, delay: float = 1.0):
    """Login sequence using the exported DLL functions."""
    select_language(lang)
    time.sleep(delay)
    select_server(server)
    time.sleep(delay)
    select_channel(channel)
    time.sleep(delay)
    select_character(character)
    time.sleep(delay)
    click_start()