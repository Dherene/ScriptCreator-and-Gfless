# ScriptCreator

Esta carpeta contiene la aplicacion principal y los scripts para compilarla en Windows.

## Generar el ejecutable

Edite primero las variables `DIST_DIR` y `SRC_DIR` dentro de `generate_exe.bat` para que apunten a las rutas deseadas. Luego ejecute:

```
generate_exe.bat [CLAVE] [DIAS]
```

- **CLAVE**: clave de licencia opcional. Si se omite se crea una nueva.
- **DIAS**: validez en dias, por defecto 30.

El script ejecuta `generate_build_info.py` para crear `build_info.py` con la informacion de licencia y despues compila el programa con PyInstaller. El resultado (`ScriptCreator.exe` junto a los archivos de licencia) se guarda en `DIST_DIR`.

## Otras herramientas

- `license_tool.py` permite crear o extender licencias desde la linea de comandos.
  - `python license_tool.py create <dias>`
  - `python license_tool.py extend <clave> <dias>`
- `generate_build_info.py` se usa internamente y normalmente no necesita ejecutarse manualmente.

## Dependencias

Para que la función de cerrar el cliente funcione correctamente se requiere el módulo `psutil`. Puede instalarlo ejecutando:

```
pip install psutil
```

Para finalizar el cliente automáticamente es recomendable ejecutar el programa
con privilegios de administrador, de lo contrario `taskkill` podría devolver
"Acceso denegado".