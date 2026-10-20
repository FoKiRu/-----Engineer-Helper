# ======================= Импорты =======================
from tkinter import filedialog, ttk
from pathlib import Path
from collections import Counter
from functools import partial
from datetime import datetime
import tkinter as tk
import os
import re
import shutil
import traceback
import json
import psutil
import subprocess
import time
import threading
import logging
import requests
import sys
import tempfile
import ctypes
import webbrowser
import keyboard
import queue
import tkinter.font as tkfont

# ======================= Модули (опционально) =======================
MODULES_AVAILABLE = False
_MOD_VERSION = None

try:
    MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
    if os.path.isdir(MODULE_DIR):
        sys.path.insert(0, MODULE_DIR)
        try:
            from modules.config import SCRIPT_VERSION as _MOD_VERSION
            from modules.utils import format_size as _fmt_size
            MODULES_AVAILABLE = True
            print(f"[OK] Модули загружены (utils: format_size)")
        except ImportError as e:
            print(f"[WARN] Модули не загружены: {e}")
except Exception as e:
    print(f"[WARN] Ошибка загрузки модулей: {e}")

# ======================= Константы и настройки =======================
if MODULES_AVAILABLE and '_MOD_VERSION' in dir():
    SCRIPT_VERSION = _MOD_VERSION
else:
    SCRIPT_VERSION = "v1.9.5.25"

AUTHOR = "Автор: Кирилл Рутенко"
EMAIL = "Эл. почта: k.rutenko@rkeeper.ru, xkiladx@gmail.com"
DESCRIPTION = (
    "EngiHelp — утилита для быстрого управления настройками R-Keeper.\n"
    "С её помощью можно:\n"
    "- находить и открывать нужный каталог R-Keeper\n"
    "- просматривать и редактировать INI-файлы\n"
    "- включать и отключать UseDBSync и UseSQL\n"
    "- автоматически синхронизировать параметры Station и Server\n"
    "- копировать недостающие INI-файлы из папки bin\\win\\ini\n"
    "- сохранять и удалять задачи с привязкой к базе и MIDBASE\n"
    "- очищать папки base и MIDBASE с возможностью резервной копии\n"
    "- запускать и останавливать основные сервисы R-Keeper\n"
    "- переключать версию RK и переносить данные между версиями\n"
    "- автоматически сохранять последние пути и настройки\n"
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(str(Path.home()), "Documents", "EngiHelp_data.json")
OLD_CONFIG_FILE = os.path.join(str(Path.home()), "Documents", "EngiHelp_config.json")
OLD_TASKS_FILE = os.path.join(str(Path.home()), "Documents", "tasks.json")
FILES = ["RKEEPER.INI", "wincash.ini", "rk7srv.INI", "rk7man.ini"]

# ======================= GitHub URL =======================
GITHUB_URL = "https://raw.githubusercontent.com/FoKiRu/-----Engineer-Helper/main/.gitignore"

# ======================= GUI константы =======================
WINDOW_WIDTH = 412
WINDOW_HEIGHT = 510
WINDOW_OFFSET_X = 223
WINDOW_OFFSET_Y = 100
CENTERED_WINDOW_MAX_WIDTH = 500

# ======================= Cloud RK7man константы =======================
CLOUD_CONNECTIONS_FILE = "cloud_connections.txt"
MAX_SAVED_CONNECTIONS = 5
CLOUD_RK7MAN_PATTERN = re.compile(r'^([A-Za-z0-9_]+)\s*=\s*([^\s:=]+):(\d{1,5})$')

# ======================= Функции проверки GitHub =======================

def check_gitignore_status():
    """
    Функция для получения первой строки из файла .gitignore на GitHub.
    Если первая строка равна "0", программа продолжит выполнение,
    если "1", программа завершит выполнение.
    Если запрос не удался (timeout, блокировка и т.д.) — запускается с предупреждением.
    """
    try:
        response = requests.get(GITHUB_URL, timeout=5)
        response.raise_for_status()
        first_line = response.text.splitlines()[0].strip()

        if first_line == "0":
            return True
        elif first_line == "1":
            return False
        else:
            print(f"Неожиданный формат в .gitignore: {first_line}. Программа запускается.")
            return True
    except requests.RequestException as e:
        print(f"[WARN] Не удалось проверить статус на GitHub: {e}")
        print("[WARN] Программа запускается в обход проверки.")
        return True

# ======================= Функция иконки =======================

def extract_icon_to_temp():
    """Получает путь к иконке приложения."""
    exe_path = sys.executable
    temp_dir = tempfile.gettempdir()
    icon_path = os.path.join(temp_dir, "Иконка EngiHelp.ico")

    if not os.path.exists(icon_path):
        try:
            with open(icon_path, "wb") as icon_file:
                shutil.copyfile(exe_path, icon_path)
        except Exception as e:
            print(f"Не удалось извлечь иконку: {e}")
            return None

    return icon_path

# ======================= Проверка и запуск =======================

def check_and_start():
    """Проверяет статус в .gitignore и запускает приложение."""
    if not check_gitignore_status():
        print("Программа не будет запущена.")
        sys.exit()

    print("Программа запускается.")
    return True

# Запускаем проверку при импорте модуля
check_and_start()

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# ======================= Вспомогательные функции =======================

def find_product_root(selected_path):
    """
    Определяет корневую папку продукта (например INST0.00.0.0000)
    и проверяет наличие INI-файлов в bin/win.
    Возвращает путь к корню продукта или None.
    """
    original = selected_path

    if os.path.basename(original).lower() == "win":
        parent = os.path.dirname(original)
        if os.path.basename(parent).lower() == "bin":
            root = os.path.dirname(parent)
        else:
            return None
    elif os.path.basename(original).lower() == "bin":
        root = os.path.dirname(original)
    else:
        root = original

    bin_win = os.path.join(root, "bin", "win")
    if all(os.path.isfile(os.path.join(bin_win, f)) for f in FILES):
        return root

    return None

def get_short_path_name(long_path):
    """Получает короткий 8.3 путь для Windows."""
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.kernel32.GetShortPathNameW(long_path, buf, 260)
    return buf.value

# ======================= Импорты из modules/*.py =======================
# version_updater - проверка и скачивание новых версий RK

def get_version_updater_functions():
    """Возвращает функции для работы с обновлениями версий."""
    try:
        from .version_updater import (
            check_rk_updates, download_version, extract_zip,
            find_latest_local_version, compare_versions
        )
        return {
            'check_rk_updates': check_rk_updates,
            'download_version': download_version,
            'extract_zip': extract_zip,
            'find_latest_local_version': find_latest_local_version,
            'compare_versions': compare_versions,
        }
    except ImportError as e:
        print(f"[WARN] version_updater не загружен: {e}")
        return {}
