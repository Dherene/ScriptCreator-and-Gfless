import os
import platform
import sys

import pytest

# Allow importing gfless_api from the ScriptCreator package
sys.path.insert(0, os.path.abspath("ScriptCreator"))

gfless_api = pytest.importorskip(
    "gfless_api", reason="Windows-only dependencies are missing"
)


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_detect_kernel32():
    assert gfless_api.is_dll_injected(pid=os.getpid(), dll_name="kernel32.dll")


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_missing_dll():
    assert not gfless_api.is_dll_injected(
        pid=os.getpid(), dll_name="definitely_not_here.dll"
    )
