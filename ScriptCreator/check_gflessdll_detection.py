"""Manual test for verifying GflessDLL.dll detection.

Run this script while ``NostaleClientX.exe`` is running.  It periodically
prints whether the Gfless DLL is detected in the game process.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath("ScriptCreator"))

import gfless_api  # noqa: E402


def main() -> None:
    while True:
        try:
            detected = gfless_api.is_dll_injected()
            print(f"GflessDLL.dll injected: {detected}")
        except PermissionError as exc:  # pragma: no cover - manual test
            print(f"Permission error: {exc}")
            break
        time.sleep(2)


if __name__ == "__main__":  # pragma: no cover - manual test
    main()
