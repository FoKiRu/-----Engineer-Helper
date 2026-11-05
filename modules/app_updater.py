import os
import re
import subprocess
import tempfile

import requests
from packaging import version

from . import get_short_path_name

EXE_URL = "https://github.com/FoKiRu/-----Engineer-Helper/raw/main/dist/EngiHelp.exe"
SOURCE_URL = "https://raw.githubusercontent.com/FoKiRu/-----Engineer-Helper/main/EngiHelp.py"


def fetch_remote_version():
    response = requests.get(SOURCE_URL, timeout=5)
    response.raise_for_status()
    match = re.search(r'SCRIPT_VERSION\s*=\s*"v([\d.]+)"', response.text)
    return match.group(1) if match else None


def is_newer_version(remote_version, current_version):
    return version.parse(remote_version.lstrip("v")) > version.parse(current_version.lstrip("v"))


def download_update():
    response = requests.get(EXE_URL, timeout=10)
    response.raise_for_status()
    temp_exe = os.path.join(tempfile.gettempdir(), "EngiHelp_updated.exe")
    with open(temp_exe, "wb") as f:
        f.write(response.content)
    return temp_exe


def restart_with_update(temp_exe, current_exe):
    short_exe = get_short_path_name(current_exe)
    bat_path = os.path.join(tempfile.gettempdir(), "restart_engihelp.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(f"""@echo off
        chcp 65001 >nul
        echo Обновление завершено.
        echo Ожидание завершения старой версии...
        :waitloop
        tasklist | find /i "{os.path.basename(short_exe)}" >nul
        if not errorlevel 1 (
            timeout /t 1 >nul
            goto waitloop
        )
        echo Замена файла...
        copy /y "{temp_exe}" "{short_exe}"
        start "" "{short_exe}"
        echo Запуск новой версии примерно через:
        for /l %%i in (8,-1,1) do (
            echo %%i...
            timeout /t 1 >nul
        )
        """)
    subprocess.Popen(["cmd", "/c", bat_path], shell=False)
