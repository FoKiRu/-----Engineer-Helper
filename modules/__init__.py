# ======================= modules/__init__.py =======================
# Общие константы и утилиты пакета. Импорт пакета не должен иметь побочных
# эффектов (сетевых запросов, создания окон) — всё это делает EngiHelp.py.

import os
import re
import sys
import shutil
import ctypes
import tempfile
import requests

FILES = ["RKEEPER.INI", "wincash.ini", "rk7srv.INI", "rk7man.ini"]

# ======================= GitHub URL =======================
GITHUB_URL = "https://raw.githubusercontent.com/FoKiRu/-----Engineer-Helper/main/.gitignore"

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
            shutil.copyfile(exe_path, icon_path)
        except Exception as e:
            print(f"Не удалось извлечь иконку: {e}")
            return None

    return icon_path

# ======================= Вспомогательные функции =======================

def get_short_path_name(long_path):
    """Получает короткий 8.3 путь для Windows."""
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.kernel32.GetShortPathNameW(long_path, buf, 260)
    return buf.value
