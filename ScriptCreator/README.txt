# ScriptCreator

Use `generate_exe.bat` to package the application with PyInstaller. The script runs `generate_build_info.py` and then invokes `pyinstaller` using `main.spec`.
After the build completes, the resulting executable and `gfless.dll` will be located in `dist\main`.

`gfless_api.login` now accepts an optional `pid` argument to identify the game process when its executable name is unpredictable.