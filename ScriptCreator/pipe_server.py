"""Simple named pipe server for the modified Gfless DLL.

This utility listens on the ``MiServidor`` pipe and responds to the
commands issued by the DLL.  Values are provided via command line
arguments so the behaviour can be easily customised.
"""

from __future__ import annotations

import argparse
import win32pipe
import win32file
import win32security
import pywintypes


PIPE_NAME = r"\\.\pipe\MiServidor"


def serve(
    lang: int,
    server: int,
    channel: int,
    character: int,
    *,
    auto_login: bool = False,
    disable_nosmall: bool = False,
) -> None:
    """Handle a single client on ``PIPE_NAME``."""

    sa = win32security.SECURITY_ATTRIBUTES()
    sd = win32security.SECURITY_DESCRIPTOR()
    # Allow any process to connect so elevation differences are not an issue
    sd.SetSecurityDescriptorDacl(True, None, False)
    sa.SECURITY_DESCRIPTOR = sd

    pipe = win32pipe.CreateNamedPipe(
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
    try:
        win32pipe.ConnectNamedPipe(pipe, None)
        while True:
            try:
                data = win32file.ReadFile(pipe, 255)[1].decode("ascii")
            except pywintypes.error:
                break
            command = data.strip().split()[-1]
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
        try:
            win32file.CloseHandle(pipe)
        except pywintypes.error:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve login parameters to the modified Gfless DLL"
    )
    parser.add_argument("--lang", type=int, default=0, help="server language")
    parser.add_argument("--server", type=int, default=0, help="server index")
    parser.add_argument("--channel", type=int, default=0, help="channel index")
    parser.add_argument(
        "--character", type=int, default=0, help="character slot index"
    )
    parser.add_argument("--auto-login", action="store_true", help="enable autologin")
    parser.add_argument(
        "--disable-nosmall", action="store_true", help="disable Nosmall loading"
    )
    args = parser.parse_args()

    serve(
        args.lang,
        args.server,
        args.channel,
        args.character,
        auto_login=args.auto_login,
        disable_nosmall=args.disable_nosmall,
    )


if __name__ == "__main__":
    main()
