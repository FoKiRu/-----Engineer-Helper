# ======================= Импорты =======================
from tkinter import filedialog, ttk
from pathlib import Path
from collections import Counter
from PyInstaller.utils.hooks import collect_data_files
from functools import partial
from datetime import datetime
from ctypes import wintypes
from packaging import version
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
import queue #Улучшенная проверка refsrv.exe


# ======================= Константы и настройки =======================
SCRIPT_VERSION = "v1.9.3.12"
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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # путь к скрипту
DATA_FILE = os.path.join(str(Path.home()), "Documents", "EngiHelp_data.json")
OLD_CONFIG_FILE = os.path.join(str(Path.home()), "Documents", "EngiHelp_config.json")
OLD_TASKS_FILE = os.path.join(str(Path.home()), "Documents", "tasks.json")
FILES = ["RKEEPER.INI", "wincash.ini", "rk7srv.INI", "rk7man.ini"]

# ======================= Работа с единым файлом данных =======================

def load_data():
    """Загружает данные из единого JSON-файла."""
    if not os.path.exists(DATA_FILE):
        return {"settings": {"auto_update": True, "task_from_version": False, "keep_cloud_files": False, "recent_paths": []}, "tasks": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Убедимся, что все ключи на месте
            if "settings" not in data:
                data["settings"] = {"auto_update": True, "task_from_version": False, "keep_cloud_files": False, "recent_paths": []}
            if "keep_cloud_files" not in data["settings"]:
                data["settings"]["keep_cloud_files"] = False
            if "tasks" not in data:
                data["tasks"] = {}
            return data
    except (json.JSONDecodeError, IOError):
        # В случае ошибки возвращаем пустую структуру
        return {"settings": {"auto_update": True, "task_from_version": False, "keep_cloud_files": False, "recent_paths": []}, "tasks": {}}

def save_data(data):
    """Сохраняет данные в единый JSON-файл."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Ошибка сохранения данных: {e}")

def migrate_old_configs():
    """
    Проверяет наличие старых файлов конфигурации и переносит их данные в новый
    единый файл, если он еще не существует.
    """
    if os.path.exists(DATA_FILE):
        return # Новый файл уже есть, миграция не нужна

    print("Миграция старых конфигурационных файлов...")
    new_data = {"settings": {"auto_update": True, "task_from_version": False, "recent_paths": []}, "tasks": {}}
    migrated = False

    # Миграция из EngiHelp_config.json
    if os.path.exists(OLD_CONFIG_FILE):
        try:
            with open(OLD_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                new_data["settings"]["auto_update"] = config.get("auto_update", True)
                paths = [
                    v for k, v in sorted(config.items())
                    if k.startswith("ini_dir") and isinstance(v, str) and v.strip()
                ]
                new_data["settings"]["recent_paths"] = paths
                migrated = True
        except Exception as e:
            print(f"Не удалось мигрировать {OLD_CONFIG_FILE}: {e}")

    # Миграция из tasks.json
    if os.path.exists(OLD_TASKS_FILE):
        try:
            with open(OLD_TASKS_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)
                new_data["tasks"] = tasks
                migrated = True
        except Exception as e:
            print(f"Не удалось мигрировать {OLD_TASKS_FILE}: {e}")

    if migrated:
        save_data(new_data)
        print("Миграция завершена. Создан новый файл: EngiHelp_data.json")
        # Опционально: удалить старые файлы после успешной миграции
        # if os.path.exists(OLD_CONFIG_FILE): os.remove(OLD_CONFIG_FILE)
        # if os.path.exists(OLD_TASKS_FILE): os.remove(OLD_TASKS_FILE)

# Вызываем миграцию при старте программы
migrate_old_configs()

# ======================= Проверка URL файла .gitignore на GitHub =======================
GITHUB_URL = "https://raw.githubusercontent.com/FoKiRu/-----Engineer-Helper/main/.gitignore"

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

# Проверяем статус в .gitignore
if not check_gitignore_status():
    print("Программа не будет запущена.")
    sys.exit()  # Завершаем программу

# Если первая строка в .gitignore равна "0", продолжаем выполнение программы
print("Программа запускается.")

# ==============================================

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Функция для извлечения иконки из .exe и сохранения во временную папку
def extract_icon_to_temp():
    # Получаем путь к текущему .exe файлу
    exe_path = sys.executable
    
    # Указываем путь, куда извлечем иконку
    temp_dir = tempfile.gettempdir()
    icon_path = os.path.join(temp_dir, "Иконка EngiHelp.ico")
    
    # Проверяем, если иконка уже существует, не извлекаем заново
    if not os.path.exists(icon_path):
        try:
            # Скопируем иконку из .exe в временную папку
            with open(icon_path, "wb") as icon_file:
                # Открываем файл .exe и ищем иконку (этот шаг можно адаптировать под конкретный случай)
                shutil.copyfile(exe_path, icon_path)
        except Exception as e:
            print(f"Не удалось извлечь иконку: {e}")
            return None
    
    return icon_path

# === GUI ===
root = tk.Tk()
root.withdraw()
root.title(f"EngiHelp {SCRIPT_VERSION}")

# Извлечение иконки и применение к окну
icon_path = extract_icon_to_temp()
if icon_path:
   root.iconbitmap(icon_path)  # Применяем иконку к главному окну

# Размеры главного окна
WINDOW_WIDTH = 412
WINDOW_HEIGHT = 510
WINDOW_OFFSET_X = 223
WINDOW_OFFSET_Y = 100   

# Центрирование окна
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
cursor_x = root.winfo_pointerx()
cursor_y = root.winfo_pointery()
x = max(0, min(screen_width - WINDOW_WIDTH, cursor_x - WINDOW_OFFSET_X))
y = max(0, min(screen_height - WINDOW_HEIGHT, cursor_y - WINDOW_OFFSET_Y))

root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

settings_tab = tk.Frame(notebook)
notebook.add(settings_tab, text="Параметры")

# =================== Работа с EngiHelp_config.json (мульти-пути) =============
def load_settings_and_paths():
    data = load_data()
    settings = data.get("settings", {})
    paths = settings.get("recent_paths", [])
    auto_update = settings.get("auto_update", True)
    task_from_version = settings.get("task_from_version", True)
    keep_cloud_files = settings.get("keep_cloud_files", True)
    return paths, auto_update, task_from_version, keep_cloud_files


def save_settings_and_path(new_path):
    new_path = new_path.replace("\\", "/")
    data = load_data()
    
    # Обновляем список путей
    paths = data["settings"].get("recent_paths", [])
    if new_path in paths:
        paths.remove(new_path)
    paths.insert(0, new_path)
    data["settings"]["recent_paths"] = paths[:3] # Оставляем только 3 последних

    # Обновляем флаги настроек
    if 'auto_update_var' in globals():
        data["settings"]["auto_update"] = auto_update_var.get()
    if 'task_from_version_var' in globals():
        data["settings"]["task_from_version"] = task_from_version_var.get()
    if 'keep_cloud_files_var' in globals():
        data["settings"]["keep_cloud_files"] = keep_cloud_files_var.get()

    save_data(data)
    
    # Обновляем выпадающий список в интерфейсе
    if 'path_entry' in globals():
        path_entry['values'] = data["settings"]["recent_paths"]


def find_latest_task_for_path(target_path):
    """Находит самый последний сохраненный ID задачи для указанного пути."""
    data = load_data()
    tasks = data.get("tasks", {})
    
    # Задачи уже отсортированы (самая новая вверху) благодаря логике сохранения.
    # Поэтому первый найденный результат и будет самым последним.
    for task_id, task_info in tasks.items():
        if task_info.get("ini_path") == target_path:
            return task_id  # Нашли, возвращаем ID
            
    return None  # Для этого пути задач не найдено

def find_tasks_for_path(target_path):
    """
    Находит ВСЕ сохранённые ID задач, привязанные к указанному пути версии.
    Учитывает как основной ini_path задачи, так и пути из её versions.
    Порядок сохраняется как в файле данных (самая свежая задача — первая).
    """
    if not target_path:
        return []

    def _norm(p):
        return os.path.normpath(p).replace("\\", "/").lower() if p else ""

    target_norm = _norm(target_path)
    data = load_data()
    tasks = data.get("tasks", {})

    found = []
    for task_id, task_info in tasks.items():
        paths = {_norm(task_info.get("ini_path"))}
        for ver_info in task_info.get("versions", {}).values():
            paths.add(_norm(ver_info.get("ini_path")))
        if target_norm in paths:
            found.append(task_id)

    return found

def get_current_task_base_path(task_id):
    """Возвращает путь к папке base для указанного ID задачи."""
    if not task_id:
        return None
    data = load_data()
    task_info = data.get("tasks", {}).get(task_id)
    if not task_info:
        return None
    return task_info.get("base_path")

# ======================= Вспомогательные функции =======================
def extract_task_id_from_rk7srv_ini(ini_path):
    if not os.path.exists(ini_path):
        return None
    try:
        with open(ini_path, 'r', encoding='cp1251') as file:
            for line in file:
                line = line.strip()
                if line.lower().startswith("udbfile") or line.lower().startswith("workmodules"):
                    # Новый формат: ..\..\{task_id}\base\...
                    match = re.search(r'([a-zA-Z0-9_]+)[/\\]base[/\\]', line)
                    if match:
                        return match.group(1)
                    # Старый формат (обратная совместимость): base_{task_id}
                    match = re.search(r'base_([a-zA-Z0-9_]+)', line)
                    if match:
                        return match.group(1)
    except Exception as e:
        print(f"Ошибка при чтении rk7srv.INI: {e}")
    return None

# ======================= Определение путей и начальных переменных =======================
ini_paths, auto_update_enabled, task_from_version_enabled, keep_cloud_files_enabled = load_settings_and_paths()
ini_path = ini_paths[0] if ini_paths else ""
auto_update_var = tk.BooleanVar(value=auto_update_enabled)
# Флаг "Выбор задачи из выбора версии": при смене версии RK предлагать выбрать задачу
task_from_version_var = tk.BooleanVar(value=task_from_version_enabled)
# Флаг "Сохранять временные файлы Cloud RK7man": не удалять .ini после запуска
keep_cloud_files_var = tk.BooleanVar(value=keep_cloud_files_enabled)
INI_FILE_USESQL = os.path.join(ini_path, "rk7srv.INI")

# Создаём task_id_var ЗДЕСЬ, до первого использования
task_id_var = tk.StringVar()

# Извлекаем номер задачи из rk7srv.INI при старте
if ini_path and os.path.exists(INI_FILE_USESQL):
    task_id = extract_task_id_from_rk7srv_ini(INI_FILE_USESQL)
    print(f"[DEBUG] Извлечённый номер задачи: {task_id}")  # Отладка
    if task_id:
        task_id_var.set(task_id)  # Теперь task_id_var существует
    else:
        task_id_var.set("")
else:
    task_id_var.set("")

# Инициализируем _prev_task_id для корректного сохранения при смене задачи
_prev_task_id = task_id_var.get().strip()

# Версия RK, уже выбранная пользователем при выборе версии из списка путей.
# Если задана — on_task_selected не показывает диалог выбора версии,
# а сразу применяет эту версию (иначе получилась бы тавтология:
# выбрали версию -> выбрали задачу -> опять выбираем версию).
_forced_version = None

# Открываем номер задачи в SD
def open_task_in_sd():
    task_id = task_id_var.get()
    if task_id:
        url = f'https://sd.rkeeper.ru/sd/operator/#esearch:full:serviceCall:ALL_OBJECTS!{{%22query%22:%22serviceCall@number:{task_id}%22}}'
        webbrowser.open(url)
    else:
        centered_warning("Предупреждение", "Номер задачи не найден")


# ======================= Логика определения корня продукта =======================
def find_product_root(selected_path):
    """
    Определяет корневую папку продукта (например INST0.00.0.0000)
    и проверяет наличие INI-файлов в bin/win.
    Возвращает путь к корню продукта или None.
    """
    original = selected_path

    # Если выбран bin/win — поднимаемся на два уровня
    if os.path.basename(original).lower() == "win":
        parent = os.path.dirname(original)
        if os.path.basename(parent).lower() == "bin":
            root = os.path.dirname(parent)
        else:
            return None
    # Если выбран bin — поднимаемся на один уровень
    elif os.path.basename(original).lower() == "bin":
        root = os.path.dirname(original)
    # Если сразу INST7... — проверим, есть ли bin/win
    else:
        root = original

    bin_win = os.path.join(root, "bin", "win")
    if all(os.path.isfile(os.path.join(bin_win, f)) for f in FILES):
        return root

    return None

# ======================= Работа с INI-файлами =======================
def get_usedbsync_values():
    values = {}
    for filename in FILES:
        path = os.path.join(ini_path, filename)
        if not os.path.isfile(path):
            continue
        try:
            try:
                with open(path, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                with open(path, 'r', encoding='cp1251') as file:
                    lines = file.readlines()
            found = False
            for line in lines:
                match = re.match(r'^\s*UseDBSync\s*=\s*(\d+)', line, re.IGNORECASE)
                if match:
                    values[filename] = match.group(1)
                    found = True
                    break
            if not found and filename != "rk7srv.INI":
                values[filename] = "1"
        except Exception:
            continue
    return values

def detect_consensus_value():
    values = get_usedbsync_values()
    if not values:
        return "0"
    counts = Counter(values.values())
    consensus = counts.most_common(1)[0][0]
    for filename, value in values.items():
        if value != consensus:
            full_path = os.path.join(ini_path, filename)
            update_ini_file(full_path, consensus, "UseDBSync")
    return consensus

def get_usesql_value():
    if not os.path.isfile(INI_FILE_USESQL):
        return "0"
    try:
        try:
            with open(INI_FILE_USESQL, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            with open(INI_FILE_USESQL, 'r', encoding='cp1251') as file:
                lines = file.readlines()
        for line in lines:
            match = re.match(r'^\s*USESQL\s*=\s*(\d+)', line, re.IGNORECASE)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "0"

def get_port_value():
    """Читает PORT из секции [TCPSOC] файла rk7srv.INI."""
    rk7srv_path = os.path.join(ini_path, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return ""
    try:
        try:
            with open(rk7srv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(rk7srv_path, 'r', encoding='cp1251') as f:
                lines = f.readlines()
        in_tcpsoc = False
        for line in lines:
            stripped = line.strip()
            if re.match(r'^\[TCPSOC\]', stripped, re.IGNORECASE):
                in_tcpsoc = True
                continue
            if in_tcpsoc:
                if stripped.startswith('['):
                    break
                m = re.match(r'^\s*PORT\s*=\s*(\d+)', stripped, re.IGNORECASE)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return ""

def get_refserver_name():
    """Читает имя сервера из [REFSERVER] Server = ... в rk7srv.INI."""
    rk7srv_path = os.path.join(ini_path, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return ""
    try:
        try:
            with open(rk7srv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(rk7srv_path, 'r', encoding='cp1251') as f:
                lines = f.readlines()
        in_refserver = False
        for line in lines:
            stripped = line.strip()
            if re.match(r'^\[REFSERVER\]', stripped, re.IGNORECASE):
                in_refserver = True
                continue
            if in_refserver:
                if stripped.startswith('['):
                    break
                m = re.match(r'^\s*Server\s*=\s*(\S+)', stripped, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return ""

def set_port_rk7srv(ini_path_val, port):
    """Устанавливает PORT=port в секции [TCPSOC] файла rk7srv.INI."""
    rk7srv_path = os.path.join(ini_path_val, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return False
    try:
        try:
            with open(rk7srv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            enc = 'utf-8'
        except UnicodeDecodeError:
            with open(rk7srv_path, 'r', encoding='cp1251') as f:
                lines = f.readlines()
            enc = 'cp1251'

        new_lines = []
        in_tcpsoc = False
        port_updated = False
        tcpsoc_found = False

        for line in lines:
            stripped = line.strip()
            if re.match(r'^\[TCPSOC\]', stripped, re.IGNORECASE):
                in_tcpsoc = True
                tcpsoc_found = True
                new_lines.append(line)
                continue
            if in_tcpsoc:
                if stripped.startswith('['):
                    # Выходим из секции — если PORT не нашли, добавляем перед новой секцией
                    if not port_updated:
                        new_lines.append(f"PORT={port}\n")
                        port_updated = True
                    in_tcpsoc = False
                elif re.match(r'^\s*PORT\s*=', stripped, re.IGNORECASE):
                    new_lines.append(f"PORT={port}\n")
                    port_updated = True
                    continue
            new_lines.append(line)

        if not tcpsoc_found:
            new_lines.append(f"\n[TCPSOC]\nPORT={port}\n")
        elif not port_updated:
            new_lines.append(f"PORT={port}\n")

        shutil.copy2(rk7srv_path, rk7srv_path + ".bak")
        with open(rk7srv_path, 'w', encoding=enc) as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"[ERR] set_port_rk7srv: {e}")
        return False

def set_port_rk7man(ini_path_val, server_name, port):
    """Устанавливает {server_name}=127.0.0.1:{port} в секции [TCPDNS] файла rk7man.ini."""
    rk7man_path = os.path.join(ini_path_val, "rk7man.ini")
    if not os.path.isfile(rk7man_path):
        return False
    try:
        try:
            with open(rk7man_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            enc = 'utf-8'
        except UnicodeDecodeError:
            with open(rk7man_path, 'r', encoding='cp1251') as f:
                lines = f.readlines()
            enc = 'cp1251'

        new_lines = []
        in_tcpdns = False
        entry_updated = False
        tcpdns_found = False

        for line in lines:
            stripped = line.strip()
            if re.match(r'^\[TCPDNS\]', stripped, re.IGNORECASE):
                in_tcpdns = True
                tcpdns_found = True
                new_lines.append(line)
                continue
            if in_tcpdns:
                if stripped.startswith('['):
                    if not entry_updated:
                        new_lines.append(f"{server_name}=127.0.0.1:{port}\n")
                        entry_updated = True
                    in_tcpdns = False
                elif re.match(rf'^\s*{re.escape(server_name)}\s*=', stripped, re.IGNORECASE):
                    new_lines.append(f"{server_name}=127.0.0.1:{port}\n")
                    entry_updated = True
                    continue
            new_lines.append(line)

        if not tcpdns_found:
            new_lines.append(f"\n[TCPDNS]\n{server_name}=127.0.0.1:{port}\n")
        elif not entry_updated:
            new_lines.append(f"{server_name}=127.0.0.1:{port}\n")

        shutil.copy2(rk7man_path, rk7man_path + ".bak")
        with open(rk7man_path, 'w', encoding=enc) as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"[ERR] set_port_rk7man: {e}")
        return False

def apply_port(ini_path_val, port):
    """Применяет порт в rk7srv.INI [TCPSOC] и rk7man.ini [TCPDNS]."""
    if not port:
        return
    server_name = get_refserver_name()
    ok1 = set_port_rk7srv(ini_path_val, port)
    if server_name:
        ok2 = set_port_rk7man(ini_path_val, server_name, port)
    else:
        ok2 = False
        print("[WARN] apply_port: имя сервера из [REFSERVER] не найдено, rk7man.ini не обновлён")
    print(f"[PORT] rk7srv={ok1}, rk7man={ok2}, server='{server_name}', port={port}")

# ======================= Cloud RK7man =======================
CLOUD_RK7MAN_PATTERN = re.compile(r'^([A-Za-z0-9_]+)\s*=\s*([^\s:=]+):(\d{1,5})$')

def parse_cloud_rk7man_string(raw):
    """Разбирает строку вида RK7SRV_622020001=srv01.rkcloud.ucs.ru:50072.
    Возвращает (server_name, host, port) или None, если формат не подходит."""
    if not raw:
        return None
    m = CLOUD_RK7MAN_PATTERN.match(raw.strip())
    if not m:
        return None
    server_name, host, port_str = m.group(1), m.group(2), m.group(3)
    port = int(port_str)
    if not (1 <= port <= 65535):
        return None
    return server_name, host, port

def apply_cloud_rk7man_config(ini_path_val, server_name, host, port):
    """Читает rk7man.ini, применяет облачные настройки в памяти и записывает
    во временный файл рядом с оригиналом. Реальный rk7man.ini не изменяется.
    Возвращает (temp_path, None) при успехе или (None, error_message) при ошибке."""
    rk7man_path = os.path.join(ini_path_val, "rk7man.ini")
    if not os.path.isfile(rk7man_path):
        return None, "Файл rk7man.ini не найден"
    try:
        try:
            with open(rk7man_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            enc = 'utf-8'
        except UnicodeDecodeError:
            with open(rk7man_path, 'r', encoding='cp1251') as f:
                lines = f.readlines()
            enc = 'cp1251'

        old_server = None
        for line in lines:
            m = re.match(r'^\s*Server\s*=\s*(\S+)', line, re.IGNORECASE)
            if m:
                old_server = m.group(1).strip()
                break

        new_lines = []
        tcpdns_updated = False
        for line in lines:
            stripped = line.strip()
            if re.match(r'^\s*Server\s*=', stripped, re.IGNORECASE):
                new_lines.append(f"Server={server_name}\n")
            elif re.match(r'^\s*PORT\s*=', stripped, re.IGNORECASE):
                new_lines.append(f"PORT={port}\n")
            elif old_server and re.match(rf'^\s*{re.escape(old_server)}\s*=', stripped, re.IGNORECASE):
                new_lines.append(f"{server_name}={host}:{port}\n")
                tcpdns_updated = True
            else:
                new_lines.append(line)

        if not tcpdns_updated:
            final_lines = []
            in_tcpdns = False
            inserted = False
            for line in new_lines:
                stripped = line.strip()
                if in_tcpdns and stripped.startswith('[') and not inserted:
                    final_lines.append(f"{server_name}={host}:{port}\n")
                    inserted = True
                    in_tcpdns = False
                final_lines.append(line)
                if re.match(r'^\[TCPDNS\]', stripped, re.IGNORECASE):
                    in_tcpdns = True
            if in_tcpdns and not inserted:
                final_lines.append(f"{server_name}={host}:{port}\n")
                inserted = True
            if not inserted:
                final_lines.append(f"\n[TCPDNS]\n{server_name}={host}:{port}\n")
            new_lines = final_lines

        cloud_log_dir = os.path.join(ini_path_val, "Cloud_log")
        os.makedirs(cloud_log_dir, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.ini', prefix='rk7man_cloud_', dir=cloud_log_dir)
        try:
            # Гарантируем наличие [DBSYNC] UseDBSync=0 в временном файле
            has_dbsync_section = any(re.match(r'^\s*\[DBSYNC\]', l, re.IGNORECASE) for l in new_lines)
            has_usedbsync = any(re.match(r'^\s*UseDBSync\s*=', l, re.IGNORECASE) for l in new_lines)

            if has_dbsync_section and has_usedbsync:
                # Секция есть и ключ есть — принудительно выставляем 0
                final2 = []
                for line in new_lines:
                    if re.match(r'^\s*UseDBSync\s*=', line, re.IGNORECASE):
                        final2.append("UseDBSync=0\n")
                    else:
                        final2.append(line)
                new_lines = final2
            elif has_dbsync_section and not has_usedbsync:
                # Секция есть, ключа нет — вставляем ключ сразу после [DBSYNC]
                final2 = []
                for line in new_lines:
                    final2.append(line)
                    if re.match(r'^\s*\[DBSYNC\]', line, re.IGNORECASE):
                        final2.append("UseDBSync=0\n")
                new_lines = final2
            else:
                # Секции нет — добавляем в конец
                if new_lines and not new_lines[-1].endswith('\n'):
                    new_lines.append('\n')
                new_lines.append("\n[DBSYNC]\nUseDBSync=0\n")

            with os.fdopen(tmp_fd, 'w', encoding=enc) as f:
                f.writelines(new_lines)
        except Exception:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
            raise
        return tmp_path, None
    except Exception as e:
        return None, str(e)

def launch_cloud_rk7man(tmp_ini_path):
    """Запускает rk7man.exe напрямую с временным ini-файлом в качестве аргумента,
    без изменения реального rk7man.ini. Рабочая директория — там, где лежит rk7man.exe,
    иначе исполняемый файл выдаёт ошибку."""
    exe_path = os.path.join(ini_path, "rk7man.exe")
    if not os.path.isfile(exe_path):
        centered_error("Ошибка", f"Файл не найден:\n{exe_path}")
        return

    ini_path_norm = os.path.normpath(ini_path).lower()
    for proc, exe_dir in _get_process_by_name('rk7man.exe'):
        if exe_dir == ini_path_norm:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    time.sleep(0.5)

    try:
        proc = subprocess.Popen([exe_path, tmp_ini_path], cwd=ini_path)
    except Exception as e:
        centered_error("Ошибка запуска", str(e))
        return

    if not keep_cloud_files_var.get():
        def _cleanup_after_exit():
            proc.wait()
            try:
                os.remove(tmp_ini_path)
            except OSError:
                pass
        threading.Thread(target=_cleanup_after_exit, daemon=True).start()

def cloud_rk7man_dialog():
    """Окно для ввода строки подключения к облачному серверу и запуска rk7man.exe."""
    if not ini_path or not os.path.isfile(os.path.join(ini_path, "rk7man.ini")):
        centered_error("Ошибка", "Файл rk7man.ini не найден в текущем пути.")
        return

    win = tk.Toplevel(root)
    win.withdraw()
    win.title("Cloud RK7man")

    if icon_path:
        win.iconbitmap(icon_path)

    win.transient(root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Введите строку подключения к облачному серверу\n(строку можно взять у бота):",
        justify="left"
    ).pack(padx=15, pady=(15, 5))

    tk.Label(
        frame,
        text="Шаблон: ИМЯ_СЕРВЕРА=хост:порт",
        justify="left",
        fg="gray40",
        font=("TkDefaultFont", 8)
    ).pack(padx=15, pady=(0, 8))

    entry_var = tk.StringVar()
    entry = tk.Entry(frame, textvariable=entry_var, width=45)
    entry.pack(padx=15, pady=(0, 10))

    def on_run():
        parsed = parse_cloud_rk7man_string(entry_var.get())
        if not parsed:
            centered_error(
                "Ошибка",
                "Строка не подходит по формату.\n"
                "Ожидается: ИМЯ_СЕРВЕРА=хост:порт\n"
                "Пример: RK7SRV_622020001=srv01.rkcloud.ucs.ru:50072"
            )
            return
        server_name, host, port = parsed
        win.destroy()
        tmp_ini_path, err = apply_cloud_rk7man_config(ini_path, server_name, host, port)
        if not tmp_ini_path:
            centered_error("Ошибка", f"Не удалось подготовить настройки:\n{err}")
            return
        launch_cloud_rk7man(tmp_ini_path)

    def on_enter_key(event):
        on_run()

    win.bind("<Return>", on_enter_key)

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=(0, 15))
    run_btn = tk.Button(btn_frame, text="Запустить", command=on_run, width=12)
    run_btn.pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=win.destroy, width=12).pack(side="left", padx=5)

    # Если в буфере обмена лежит строка нужного формата — сразу подставляем её
    # и выделяем кнопку "Запустить", чтобы Enter сразу запускал процесс.
    # Иначе просто активируем поле ввода с мигающим курсором для Ctrl+V.
    try:
        clipboard_text = win.clipboard_get()
    except tk.TclError:
        clipboard_text = ""

    if parse_cloud_rk7man_string(clipboard_text):
        entry_var.set(clipboard_text.strip())
        run_btn.focus_set()
    else:
        entry.focus_set()
        entry.icursor(tk.END)

    _center_window(win)

    win.focus_force()
    win.deiconify()
# ======================= Конец Cloud RK7man =======================

def update_ini_file(filepath, value, key):
    try:
        # Создаем бэкап только если файл существует
        if os.path.exists(filepath):
            shutil.copy2(filepath, filepath + ".bak")
        
        lines = []
        # Пытаемся прочитать файл, если он существует
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='cp1251') as file:
                    lines = file.readlines()

        updated = False
        new_lines = []
        key_found = False
        dbsync_section_exists = False

        # Проверяем наличие секции [DBSYNC]
        for line in lines:
            if re.match(r'^\s*\[DBSYNC\]\s*$', line, re.IGNORECASE): # ИСПРАВЛЕНО
                dbsync_section_exists = True
                break

        # Обновляем или добавляем строки
        for line in lines:
            if re.match(fr'^\s*{key}\s*=.*', line, re.IGNORECASE):
                new_lines.append(f"{key}={value}\n")
                key_found = True
                updated = True
            else:
                new_lines.append(line)

        # Если ключ не найден, добавляем его
        if not key_found:
            # Если секции [DBSYNC] нет, добавляем ее
            if not dbsync_section_exists:
                # Добавляем пустую строку перед секцией для красоты
                if new_lines and not new_lines[-1].endswith('\n'):
                    new_lines.append('\n')
                new_lines.append("\n[DBSYNC]\n")
            
            # Ищем место для вставки параметра (сразу после [DBSYNC])
            inserted = False
            final_lines = []
            for line in new_lines:
                final_lines.append(line)
                if re.match(r'^\s*\[DBSYNC\]\s*$', line, re.IGNORECASE): # ИСПРАВЛЕНО
                    final_lines.append(f"{key}={value}\n")
                    inserted = True
            
            if inserted:
                new_lines = final_lines
            else: # Если секция была добавлена в конец, просто добавляем ключ
                 new_lines.append(f"{key}={value}\n")

            updated = True

        # Записываем изменения в файл
        with open(filepath, 'w', encoding='cp1251') as file:
            file.writelines(new_lines)

        return updated

    except Exception as e:
        print(f"[ОШИБКА] {filepath}: {e}")
        traceback.print_exc()
        return False

def update_rkeeper_ini_basepath(ini_path, midbase_folder_name):
    """Обновляет параметр BasePath в секции [Config] файла RKEEPER.INI."""
    rkeeper_path = os.path.join(ini_path, "RKEEPER.INI")
    if not os.path.isfile(rkeeper_path):
        print(f"[WARN] RKEEPER.INI не найден: {rkeeper_path}")
        return False
    try:
        try:
            with open(rkeeper_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(rkeeper_path, 'r', encoding='cp1251') as f:
                lines = f.readlines()

        new_lines = []
        updated = False
        for line in lines:
            if re.match(r'^\s*BasePath\s*=', line, re.IGNORECASE):
                new_lines.append(f"BasePath = ..\\..\\{midbase_folder_name}\n")
                updated = True
            else:
                new_lines.append(line)

        # Если параметр не найден — добавляем в секцию [Config]
        if not updated:
            final_lines = []
            in_config = False
            inserted = False
            for line in new_lines:
                final_lines.append(line)
                if re.match(r'^\s*\[Config\]\s*$', line, re.IGNORECASE):
                    in_config = True
                elif in_config and re.match(r'^\s*\[', line) and not inserted:
                    # Вставляем перед следующей секцией
                    final_lines.insert(-1, f"BasePath = ..\\..\\{midbase_folder_name}\n")
                    inserted = True
                    in_config = False
            if not inserted:
                final_lines.append(f"BasePath = ..\\..\\{midbase_folder_name}\n")
            new_lines = final_lines

        with open(rkeeper_path, 'w', encoding='cp1251') as f:
            f.writelines(new_lines)

        print(f"[OK] RKEEPER.INI обновлён: BasePath = ..\\..\\{midbase_folder_name}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка обновления RKEEPER.INI: {e}")
        return False

def check_files():
    found, missing = [], []
    for filename in FILES:
        full_path = os.path.join(ini_path, filename)
        """
        # 🔍 DEBUG: печатаем путь и факт существования
        print(f"[DEBUG] Проверяем файл: {filename} => {full_path}")
        print(f"[DEBUG] Существует? {'Да' if os.path.isfile(full_path) else 'Нет'}")
        """
        if os.path.isfile(full_path):
            found.append(filename)
        else:
            missing.append(filename)

    return found, missing

def on_check():
    found, missing = check_files()
    filtered_missing = [f for f in missing if f.lower() != "rk7man.ini"]
    
    # Отключаем кнопки, если файлы отсутствуют
    if filtered_missing:
        usedbsync_cb.config(state="disabled", fg="gray")
        usesql_cb.config(state="disabled", fg="gray")
        clear_base_btn.config(state="disabled")  # Отключаем кнопку "Clear Base"
        return False
    else:
        usedbsync_cb.config(state="normal", fg="black")
        usesql_cb.config(state="normal", fg="black")
        clear_base_btn.config(state="normal")  # Включаем кнопку "Clear Base"
        usedbsync_var.set(int(detect_consensus_value()))
        usesql_var.set(int(get_usesql_value()))
        port_var.set(get_port_value())
        return True

# ============================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ (с оптимизацией)
# ============================================================
_refsrv_state = {
    'cancel_event': threading.Event(),
    'lock': threading.Lock(),
    'result_queue': queue.Queue(),
    'asked_paths': set(),
    'poll_id': None,
    'active_thread': None,
}


# ============================================================
# ОПТИМИЗИРОВАННЫЙ ВОРКЕР - поиск через tasklist
# ============================================================
def _check_refsrv_worker(selected_path: str, cancel: threading.Event) -> None:
    """Ищет refsrv.exe в фоновом потоке (оптимизированный способ)."""
    
    sel_norm = os.path.normpath(selected_path).lower()
    
    try:
        # ✅ СПОСОБ 1: Быстрый поиск через tasklist
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq refsrv.exe', '/FO', 'CSV'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if cancel.is_set():
                _refsrv_state['result_queue'].put(("cancelled", sel_norm))
                return
            
            if result.returncode == 0 and 'refsrv.exe' in result.stdout:
                lines = result.stdout.strip().split('\n')
                
                # Парсим CSV: "refsrv.exe","PID"
                if len(lines) > 1:
                    try:
                        parts = lines[1].split(',')
                        pid_str = parts[1].strip('"')
                        pid = int(pid_str)
                        
                        # Получаем полный путь
                        try:
                            proc = psutil.Process(pid)
                            exe_path = proc.exe()
                            exe_dir_norm = os.path.normpath(os.path.dirname(exe_path)).lower()
                            
                            if exe_dir_norm == sel_norm:
                                _refsrv_state['result_queue'].put(("found", sel_norm, pid))
                                return
                        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                            pass
                    except (ValueError, IndexError):
                        pass
            
            _refsrv_state['result_queue'].put(("not_found", sel_norm))
            return
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Если tasklist не работает, падаем на psutil
            logging.debug("tasklist не доступен, используем psutil")
            pass

        _refsrv_state['result_queue'].put(("not_found", sel_norm))
        
    except Exception:
        logging.exception("Ошибка в _check_refsrv_worker")
        _refsrv_state['result_queue'].put(("error", selected_path))


# ============================================================
# 2. ОПРОС ОЧЕРЕДИ из главного потока
# ============================================================
def _poll_refsrv_queue() -> None:
    """Читает результаты из очереди в главном потоке."""
    try:
        while True:
            msg = _refsrv_state['result_queue'].get_nowait()
            _handle_refsrv_result(msg)
    except queue.Empty:
        pass

    # Проверяем, жив ли поток
    with _refsrv_state['lock']:
        thread_alive = (
            _refsrv_state['active_thread'] is not None
            and _refsrv_state['active_thread'].is_alive()
        )

    if thread_alive or not _refsrv_state['result_queue'].empty():
        _refsrv_state['poll_id'] = root.after(100, _poll_refsrv_queue)
    else:
        _refsrv_state['poll_id'] = None


# ============================================================
# 3. ОБРАБОТКА РЕЗУЛЬТАТА
# ============================================================
def _handle_refsrv_result(msg: tuple) -> None:
    """Разбирает сообщение из очереди."""
    status = msg[0]

    if status == "cancelled":
        logging.debug("refsrv check cancelled for: %s", msg[1])
        return

    if status == "not_found":
        logging.debug("refsrv not found in: %s", msg[1])
        return

    if status == "error":
        logging.warning("refsrv check error for path: %s", msg[1])
        return

    if status == "found":
        sel_norm = msg[1]
        pid = msg[2]

        if sel_norm in _refsrv_state['asked_paths']:
            return

        _refsrv_state['asked_paths'].add(sel_norm)
        _ask_restart_refsrv(pid, sel_norm)


def _ask_restart_refsrv(pid: int, exe_dir_norm: str) -> None:
    """Показывает диалог с предложением перезапуска."""
    answer = centered_askyesno(
        "Перезапуск refsrv.exe",
        "Процесс refsrv.exe запущен из каталога, который вы только что выбрали.\n"
        "Для того чтобы изменения UseSQL вступили в силу, необходимо перезапустить процесс.\n\n"
        "Перезапустить сейчас?"
    )
    if answer:
        _restart_refsrv_by_pid(pid, exe_dir_norm)


# ============================================================
# 4. ПЕРЕЗАПУСК ПРОЦЕССА
# ============================================================
def _restart_refsrv_by_pid(pid: int, exe_dir_norm: str) -> None:
    """Завершает и перезапускает refsrv.exe."""
    exe_path = os.path.join(exe_dir_norm, "refsrv.exe")

    try:
        proc = psutil.Process(pid)
        try:
            exe_path = proc.exe()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

        try:
            proc.terminate()
            threading.Thread(
                target=_wait_and_start_refsrv,
                args=(proc, exe_path),
                daemon=True,
                name="refsrv-restart"
            ).start()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            _launch_refsrv(exe_path)

    except psutil.NoSuchProcess:
        _launch_refsrv(exe_path)
    except Exception as e:
        logging.error("Ошибка при перезапуске refsrv.exe (pid=%s): %s", pid, e)
        centered_error("Ошибка", f"Не удалось перезапустить refsrv.exe:\n{e}")


def _wait_and_start_refsrv(proc: psutil.Process, exe_path: str) -> None:
    """Ждёт завершения процесса и запускает его снова."""
    try:
        proc.wait(timeout=5)
    except (psutil.TimeoutExpired, psutil.AccessDenied, psutil.NoSuchProcess):
        time.sleep(2)
    except Exception as e:
        logging.error("Ошибка при ожидании процесса: %s", e)
        time.sleep(2)

    _launch_refsrv(exe_path)


def _launch_refsrv(exe_path: str) -> None:
    """Запускает refsrv.exe с параметром -desktop."""
    try:
        subprocess.Popen(
            f'start "" "{exe_path}" -desktop',
            shell=True
        )
        logging.info("refsrv.exe запущен: %s", exe_path)
    except Exception as e:
        logging.error("Не удалось запустить refsrv.exe: %s", e)


# ============================================================
# 5. УПРАВЛЕНИЕ ПРОВЕРКОЙ
# ============================================================
def _stop_refsrv_check() -> None:
    """Останавливает текущую проверку refsrv."""
    with _refsrv_state['lock']:
        _refsrv_state['cancel_event'].set()
        if _refsrv_state['active_thread'] and _refsrv_state['active_thread'].is_alive():
            _refsrv_state['active_thread'].join(timeout=0.5)


def check_refsrv_and_ask_restart(selected_path: str) -> None:
    """Запускает фоновую проверку refsrv.exe."""
    sel_norm = os.path.normpath(selected_path).lower()

    with _refsrv_state['lock']:
        # Отменяем предыдущую проверку
        _refsrv_state['cancel_event'].set()

        old_thread = _refsrv_state['active_thread']
        if old_thread and old_thread.is_alive():
            old_thread.join(timeout=0.5)

        # Сбрасываем флаг и очищаем очередь
        _refsrv_state['cancel_event'].clear()
        while not _refsrv_state['result_queue'].empty():
            try:
                _refsrv_state['result_queue'].get_nowait()
            except queue.Empty:
                break

        # Запускаем новый поток
        t = threading.Thread(
            target=_check_refsrv_worker,
            args=(selected_path, _refsrv_state['cancel_event']),
            daemon=True,
            name=f"refsrv-check-{sel_norm}"
        )
        _refsrv_state['active_thread'] = t
        t.start()

    # Запускаем опрос очереди
    if _refsrv_state['poll_id'] is None:
        _refsrv_state['poll_id'] = root.after(100, _poll_refsrv_queue)


def _reset_refsrv_cache_for_path(selected_path: str) -> None:
    """Сбрасывает кеш для пути."""
    sel_norm = os.path.normpath(selected_path).lower()
    _refsrv_state['asked_paths'].discard(sel_norm)


def _check_refsrv_on_disable(selected_path: str) -> None:
    """Проверяет refsrv при снятии флага UseSQL."""
    sel_norm = os.path.normpath(selected_path).lower()
    
    try:
        # Быстрый поиск через tasklist
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq refsrv.exe', '/FO', 'CSV'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0 and 'refsrv.exe' in result.stdout:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    try:
                        parts = lines[1].split(',')
                        pid_str = parts[1].strip('"')
                        pid = int(pid_str)
                        
                        proc = psutil.Process(pid)
                        exe_dir_norm = os.path.normpath(os.path.dirname(proc.exe())).lower()
                        
                        if exe_dir_norm == sel_norm:
                            answer = centered_askyesno(
                                "Перезапуск refsrv.exe",
                                "Процесс refsrv.exe всё ещё запущен.\n"
                                "Перезапустить его для применения изменений?"
                            )
                            if answer:
                                _restart_refsrv_by_pid(pid, exe_dir_norm)
                            return
                    except (ValueError, IndexError, psutil.NoSuchProcess):
                        pass
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Резервный поиск через psutil
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info.get('name', '').lower() != 'refsrv.exe':
                continue
            
            try:
                exe_dir_norm = os.path.normpath(os.path.dirname(proc.exe())).lower()
                if exe_dir_norm == sel_norm:
                    answer = centered_askyesno(
                        "Перезапуск refsrv.exe",
                        "Процесс refsrv.exe всё ещё запущен.\n"
                        "Перезапустить его для применения изменений?"
                    )
                    if answer:
                        _restart_refsrv_by_pid(proc.pid, exe_dir_norm)
                    return
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                continue
                
    except Exception as e:
        logging.error("Ошибка при проверке refsrv при снятии флага: %s", e)

#======================Начало / Запуск рефа с параметром UpgradeAnyTime======================
def set_upgrade_anytime(value: str) -> bool:
    """Устанавливает UpgradeAnyTime=value в секцию [REFSERVER] файла rk7srv.INI.
    Алгоритм:
      1. Если строка UpgradeAnyTime уже есть в [REFSERVER] — обновляет её.
      2. Если секция [REFSERVER] есть, но параметра нет — вставляет строку
         последней в секции (перед следующей секцией или в конце файла).
      3. Если секции [REFSERVER] нет — добавляет секцию и параметр в конец файла.
    """
    ini_file = os.path.join(ini_path, "rk7srv.INI")
    if not os.path.isfile(ini_file):
        centered_error("Ошибка", f"Файл rk7srv.INI не найден:\n{ini_file}")
        return False
    try:
        try:
            with open(ini_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(ini_file, 'r', encoding='cp1251') as f:
                lines = f.readlines()

        # --- Проход 1: ищем позиции секции и параметра ---
        refserver_start = None   # индекс строки [REFSERVER]
        param_line_idx  = None   # индекс строки UpgradeAnyTime=... внутри секции
        next_section_idx = None  # индекс первой секции ПОСЛЕ [REFSERVER]

        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'^\[REFSERVER\]', stripped, re.IGNORECASE):
                refserver_start = i
            elif re.match(r'^\[', stripped) and not stripped.startswith(';;'):
                if refserver_start is not None and next_section_idx is None:
                    next_section_idx = i
            if refserver_start is not None and next_section_idx is None:
                if re.match(r'^\s*UpgradeAnyTime\s*=', stripped, re.IGNORECASE):
                    param_line_idx = i

        # --- Проход 2: формируем новый список строк ---
        new_lines = list(lines)

        if refserver_start is None:
            # Секции [REFSERVER] нет — добавляем в конец
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines.append('\n')
            new_lines.append("\n[REFSERVER]\n")
            new_lines.append(f"UpgradeAnyTime={value}\n")

        elif param_line_idx is not None:
            # Параметр уже есть — просто заменяем строку
            new_lines[param_line_idx] = f"UpgradeAnyTime={value}\n"

        else:
            # Секция есть, параметра нет — вставляем перед следующей секцией,
            # но ПОСЛЕ всех пустых строк, которые идут в конце [REFSERVER]
            if next_section_idx is not None:
                insert_at = next_section_idx
                # Двигаемся назад, пока строки пустые — вставляем перед ними
                while insert_at > 0 and new_lines[insert_at - 1].strip() == "":
                    insert_at -= 1
            else:
                insert_at = len(new_lines)
            new_lines.insert(insert_at, f"UpgradeAnyTime={value}\n")

        with open(ini_file, 'w', encoding='cp1251') as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        centered_error("Ошибка", f"Не удалось обновить rk7srv.INI:\n{e}")
        return False


def upgrade_anytime_refsrv():
    """Устанавливает UpgradeAnyTime=1, запускает refsrv.exe, затем сбрасывает в 0."""
    refsrv_exe = os.path.join(ini_path, "refsrv.exe")
    if not os.path.isfile(refsrv_exe):
        centered_error("Ошибка", f"Файл refsrv.exe не найден:\n{refsrv_exe}")
        return

    # Шаг 1: UpgradeAnyTime=1
    if not set_upgrade_anytime("1"):
        return

    # Шаг 2: Запуск refsrv.exe
    try:
        subprocess.Popen(
            f'start "" "{refsrv_exe}" -desktop',
            shell=True
        )
        logging.info("refsrv.exe запущен (UpgradeAnyTime)")
    except Exception as e:
        centered_error("Ошибка", f"Не удалось запустить refsrv.exe:\n{e}")
        set_upgrade_anytime("0")  # Сбрасываем даже при ошибке запуска
        return

    # Шаг 3: Ждём немного (чтобы процесс успел стартовать) и сбрасываем в 0
    def reset_flag():
        time.sleep(3)
        set_upgrade_anytime("0")
        logging.info("UpgradeAnyTime сброшен в 0")

    threading.Thread(target=reset_flag, daemon=True, name="upgrade-anytime-reset").start()
#======================Конец / Запуск рефа с параметром UpgradeAnyTime======================

def toggle_usesql():
    """Обработчик чек-бокса UseSQL."""
    value = "1" if usesql_var.get() else "0"
    run_update_usesql_value(value)
    save_usesql_to_json(value)

    if value == "1":
        # Галочка поставлена — проверяем refsrv.exe
        check_refsrv_and_ask_restart(ini_path)
    else:
        # Галочка снята — сбрасываем кеш и отменяем проверку
        _check_refsrv_on_disable(ini_path)
        _reset_refsrv_cache_for_path(ini_path)
        _stop_refsrv_check()
        
def toggle_usedbsync():
    """Обработчик чек-бокса UseDBSync."""
    value = "1" if usedbsync_var.get() else "0"
    run_update(value)
    save_usedbsync_to_json(value)

    # Если активен дефолтный режим (задача не выбрана) — сохраняем изменение в дефолты
    sync_default_settings_if_no_task()

def run_update(value):
    failed = []
    # Теперь rk7man.ini обрабатывается вместе со всеми
    for filename in FILES:
        full_path = os.path.join(ini_path, filename)
        if not os.path.exists(full_path): # Проверку на существование файла
            continue
        success = update_ini_file(full_path, value, "UseDBSync")
        if not success:
            failed.append(filename)
    if failed:
        centered_warning("Внимание", f"Не удалось обновить: {', '.join(failed)}")

def run_update_usesql_value(value):
    success = update_ini_file(INI_FILE_USESQL, value, "USESQL")
    if not success:
        centered_warning("Ошибка", "Не удалось обновить UseSQL в rk7srv.INI")

def save_usesql_to_json(value):
    """Сохраняет текущее значение UseSQL в JSON: в выбранную задачу,
    либо в дефолтные настройки директории, если задача не выбрана."""
    task_id = task_id_var.get().strip()
    if task_id:
        data = load_data()
        if task_id in data.get("tasks", {}):
            if "ini_settings" not in data["tasks"][task_id]:
                data["tasks"][task_id]["ini_settings"] = {}
            data["tasks"][task_id]["ini_settings"]["UseSQL"] = value
            save_data(data)
            print(f"[UseSQL] Сохранено значение {value} для задачи {task_id}")
    else:
        save_default_ini_settings(ini_path)

def save_usedbsync_to_json(value):
    """Сохраняет текущее значение UseDBSync в JSON: в выбранную задачу,
    либо в дефолтные настройки директории, если задача не выбрана."""
    task_id = task_id_var.get().strip()
    if task_id:
        data = load_data()
        if task_id in data.get("tasks", {}):
            if "ini_settings" not in data["tasks"][task_id]:
                data["tasks"][task_id]["ini_settings"] = {}
            if "UseDBSync" not in data["tasks"][task_id]["ini_settings"]:
                data["tasks"][task_id]["ini_settings"]["UseDBSync"] = {}
            # UseDBSync хранится по файлам, поэтому проставляем значение всем файлам,
            # которые реально существуют в текущей директории (аналогично run_update)
            for filename in FILES:
                full_path = os.path.join(ini_path, filename)
                if os.path.exists(full_path):
                    data["tasks"][task_id]["ini_settings"]["UseDBSync"][filename] = value
            save_data(data)
            print(f"[UseDBSync] Сохранено значение {value} для задачи {task_id}")
    else:
        save_default_ini_settings(ini_path)

# Кнопка "Открыть путь"
def open_explorer_to_root():
    if not path_var.get().strip():
        centered_warning("Предупреждение", "Путь не выбран.\nНажмите 'Обзор' для выбора пути к RK7.")
        return

    task_id = task_id_var.get().strip()
    # if not task_id:
    #     centered_warning("Ошибка", "Сначала выберите задачу!")
    #     return

    product_root = find_product_root(path_var.get())
    if not product_root:
        centered_warning("Ошибка", "Не удалось определить корневую папку продукта.")
        return

    task_folder = os.path.join(product_root, task_id)
    if not os.path.isdir(task_folder):
        if os.path.isdir(product_root):
            try:
                os.startfile(product_root)
            except OSError:
                centered_warning(
                    "Ошибка", 
                    f"Папка задачи не найдена: {task_folder}"
                )
                pass
        return

    try:
        os.startfile(task_folder)
    except Exception as e:
        centered_error("Ошибка", f"Не удалось открыть проводник:\n{e}")

def apply_path_silent():
    """
    Обновляет глобальные переменные ini_path и INI_FILE_USESQL
    по текущему значению path_var БЕЗ автозагрузки задачи.
    Используется при переключении между задачами одной версии.
    """
    global ini_path, INI_FILE_USESQL
    new_path = path_var.get()
    if os.path.isdir(new_path):
        ini_path = new_path
        INI_FILE_USESQL = os.path.join(ini_path, "rk7srv.INI")
        save_settings_and_path(ini_path)

def on_task_selected(event):
    global _prev_task_id, _forced_version

    # Версия, уже выбранная пользователем на шаге выбора версии.
    # Забираем и сразу сбрасываем — она действует только на один вызов.
    forced_version = _forced_version
    _forced_version = None

    # Запоминаем старую задачу ДО обновления
    old_task_id = _prev_task_id

    # Перед сменой сохраняем данные ПРЕДЫДУЩЕЙ задачи
    if old_task_id:
        apply_network_ids_silent_for_task(old_task_id)
        apply_ini_flags_silent_for_task(old_task_id)

    selected_task_id = task_id_var.get()
    if not selected_task_id:
        # Пустая строка — применяем дефолтные настройки выбранной директории версии
        apply_default_ini_settings(ini_path)
        _prev_task_id = ""
        return

    data = load_data()
    tasks = data.get("tasks", {})

    if selected_task_id not in tasks:
        return

    task_info = tasks[selected_task_id]

    # === ПРОВЕРКА НА НЕСКОЛЬКО ВЕРСИЙ ===
    versions = task_info.get("versions", {})
    if len(versions) > 1:
        # Версия уже выбрана пользователем на предыдущем шаге — применяем её
        # без повторного диалога (иначе: выбрали версию -> задачу -> опять версию).
        if forced_version and forced_version in versions:
            _prev_task_id = selected_task_id
            apply_task_version(selected_task_id, forced_version)
            return
        # Не обновляем _prev_task_id — это сделает диалог при подтверждении
        show_version_selection_dialog(selected_task_id, task_info, versions, old_task_id)
        return

    # Если нет нескольких версий — обновляем _prev_task_id сразу
    _prev_task_id = selected_task_id

    # --- ЛОГИКА ПЕРЕМЕЩЕНИЯ ЗАДАЧИ НА ВТОРУЮ ПОЗИЦИЮ (после пустой строки) ---
    task_keys = list(tasks.keys())
    if not task_keys or task_keys[0] != selected_task_id:
        selected_task_info = tasks.pop(selected_task_id)
        sorted_tasks = {selected_task_id: selected_task_info, **tasks}
        data["tasks"] = sorted_tasks
        save_data(data)
        task_id_combobox['values'] = [""] + list(sorted_tasks.keys())
        tasks = sorted_tasks

    task_info = tasks[selected_task_id]

    # --- ОБНОВЛЕНИЕ ГЛАВНОГО ПУТИ ---
    task_ini_path = task_info.get("ini_path")
    if task_ini_path:
        # ИСПРАВЛЕНИЕ БАГА: всегда применяем путь и настройки,
        # даже если путь совпадает с текущим
        path_var.set(task_ini_path)
        apply_path_silent()  # Обновляем глобальные переменные без автозагрузки задачи

    if "ini_settings" not in task_info:
        return

    ini_settings = task_info["ini_settings"]
    ini_path_from_task = task_info["ini_path"]

    rk7srv_ini_path = os.path.join(ini_path_from_task, "rk7srv.INI")
    if not os.path.exists(rk7srv_ini_path):
        centered_error("Ошибка", f"Файл rk7srv.INI не найден:\n{rk7srv_ini_path}")
        return

    # Применяем UseDBSync
    if "UseDBSync" in ini_settings:
        for filename, value in ini_settings["UseDBSync"].items():
            full_path = os.path.join(ini_path_from_task, filename)
            if os.path.exists(full_path):
                update_ini_file(full_path, str(value), "UseDBSync")

    # Применяем UseSQL
    if "UseSQL" in ini_settings:
        update_ini_file(rk7srv_ini_path, str(ini_settings["UseSQL"]), "USESQL")

    # Применяем Station/Server
    if "Station" in ini_settings and "Server" in ini_settings:
        # Временно отключаем trace чтобы не было двойного сохранения
        station_var.set(ini_settings["Station"])
        server_var.set(ini_settings["Server"])
        save_wincash_params()

    # Применяем Port
    if "Port" in ini_settings and ini_settings["Port"]:
        apply_port(ini_path_from_task, str(ini_settings["Port"]))
        port_var.set(str(ini_settings["Port"]))

    # Применяем base_path
    base_path = task_info.get("base_path", "")
    if base_path:
        # Новый формат: .../197034/base  -> передаём "197034\\base"
        # Старый формат: .../base_197034 -> передаём "base_197034" (обратная совместимость)
        base_name = os.path.basename(base_path)
        base_parent = os.path.basename(os.path.dirname(base_path))
        base_dir = os.path.join(base_parent, base_name) if base_name == "base" else base_name
        update_rk7srv_ini(rk7srv_ini_path, base_dir)

    # === ПРИМЕНЯЕМ midbase_path ===
    midbase_path = task_info.get("midbase_path", "")
    if midbase_path:
        mid_name = os.path.basename(midbase_path)
        mid_parent = os.path.basename(os.path.dirname(midbase_path))
        midbase_folder_name = os.path.join(mid_parent, mid_name) if mid_name == "MIDBASE" else mid_name
        update_rkeeper_ini_basepath(ini_path_from_task, midbase_folder_name)
        print(f"[OK] Применён MIDBASE: {midbase_folder_name}")

    # Обновляем чекбоксы в UI
    on_check()

    print(f"Параметры для задачи {selected_task_id} применены!")

# Функция по обновлению rk7srv.INI для директории по задачи
# base_dir теперь ожидается в формате "{task_id}\\base"
def update_rk7srv_ini(ini_path, base_dir):
    try:
        # Читаем файл в кодировке cp1251
        with open(ini_path, 'r', encoding='cp1251') as file:
            lines = file.readlines()

        new_lines = []
        for line in lines:
            # Ищем строки, начинающиеся с UDBFILE или WorkModules, игнорируя пробелы
            if re.match(r'^\s*UDBFILE\s*=', line, re.IGNORECASE):
                new_lines.append(f"UDBFILE            = ..\\..\\{base_dir}\\rk7.udb\n")
            elif re.match(r'^\s*WorkModules\s*=', line, re.IGNORECASE):
                new_lines.append(f"WorkModules        = ..\\..\\{base_dir}\\workmods\n")
            else:
                new_lines.append(line)

        # Сохраняем изменения
        with open(ini_path, 'w', encoding='cp1251') as file:
            file.writelines(new_lines)

        print("Файл успешно обновлён!")
    except Exception as e:
        print(f"Ошибка при обновлении файла: {e}")


# ======================= Смена версии RK =======================

def extract_rk_version_from_path(path):
    """Извлекает версию RK из имени папки INST в пути."""
    product_root = find_product_root(path)
    if not product_root:
        return None
    folder_name = os.path.basename(product_root)
    match = re.match(r'^INST(.+)$', folder_name, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def find_available_rk_versions(path):
    """Находит все доступные версии INST в родительской директории."""
    product_root = find_product_root(path)
    if not product_root:
        return []
    parent_dir = os.path.dirname(product_root)
    versions = []
    try:
        for item in os.listdir(parent_dir):
            full_path = os.path.join(parent_dir, item)
            if os.path.isdir(full_path):
                match = re.match(r'^INST(.+)$', item, re.IGNORECASE)
                if match:
                    version_str = match.group(1)
                    bin_win = os.path.join(full_path, "bin", "win")
                    if os.path.isdir(bin_win):
                        versions.append(version_str)
    except Exception as e:
        print(f"Ошибка сканирования версий: {e}")
    return versions


def kill_processes_for_version_change():
    """Завершает процессы refsrv.exe и rk7man.exe."""
    killed = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if name and name.lower() in ('refsrv.exe', 'rk7man.exe'):
                proc.terminate()
                killed.append(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if killed:
        time.sleep(2)
    return killed


def change_rk_version():
    """Главная функция кнопки 'Сменить версию RK'."""
    selected_task_id = task_id_var.get().strip()
    if not selected_task_id:
        centered_warning("Предупреждение", "Сначала выберите задачу!")
        return

    data = load_data()
    tasks = data.get("tasks", {})

    if selected_task_id not in tasks:
        centered_warning("Предупреждение", f"Задача {selected_task_id} не найдена!")
        return

    task_info = tasks[selected_task_id]
    current_ini_path = task_info.get("ini_path", path_var.get())

    # Извлекаем текущую версию
    current_version = extract_rk_version_from_path(current_ini_path)
    if not current_version:
        centered_error("Ошибка",
            "Не удалось определить текущую версию RK из пути.\n"
            "Ожидается папка вида INST7.25.09.2004")
        return

    # Ищем доступные версии
    available_versions = find_available_rk_versions(current_ini_path)
    other_versions = [v for v in available_versions if v != current_version]
    other_versions = sorted(other_versions, reverse=True)  # новые версии сверху

    if not other_versions:
        centered_info("Информация",
            f"Других версий RK не найдено.\n"
            f"Текущая версия: {current_version}\n"
            f"Директория поиска: {os.path.dirname(find_product_root(current_ini_path))}")
        return

    # === Диалог выбора версии ===
    select_win = tk.Toplevel(root)
    select_win.withdraw()
    select_win.title("Сменить версию RK")

    if icon_path:
        select_win.iconbitmap(icon_path)

    select_win.transient(root)
    select_win.grab_set()

    frame = tk.Frame(select_win)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=(
        f"Задача: {selected_task_id}\n"
        f"Текущая версия: {current_version}\n\n"
        f"Выберите версию для переноса базы:"
    ), justify="left").pack(padx=10, pady=(10, 5))

    version_var = tk.StringVar()
    version_combo = ttk.Combobox(
        frame, textvariable=version_var,
        values=other_versions, state="readonly", width=30
    )
    version_combo.pack(padx=10, pady=5)
    if other_versions:
        version_combo.current(0)

    tk.Label(frame, text=(
        "⚠ Процессы refsrv.exe и rk7man.exe будут закрыты!"
    ), fg="red", font=("TkDefaultFont", 8)).pack(padx=10, pady=(5, 0))

    def on_confirm():
        target_version = version_var.get()
        if not target_version:
            centered_warning("Предупреждение", "Выберите версию!")
            return
        select_win.destroy()
        perform_version_change(selected_task_id, current_version, target_version)

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Перенести", command=on_confirm, width=12).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=select_win.destroy, width=12).pack(side="left", padx=5)

    _center_window(select_win)

    select_win.focus_force()
    select_win.deiconify()


def perform_version_change(task_id, current_version, target_version):
    """Выполняет перенос базы задачи в другую версию RK с заменой только rk7.udb."""
    data = load_data()
    tasks = data.get("tasks", {})
    task_info = tasks.get(task_id)
    if not task_info: return

    current_ini_path = task_info.get("ini_path", path_var.get())
    current_product_root = find_product_root(current_ini_path)
    parent_dir = os.path.dirname(current_product_root)

    # Пути к целевой версии
    target_product_root = os.path.join(parent_dir, f"INST{target_version}")
    target_bin_win = os.path.join(target_product_root, "bin", "win")
    target_ini_path_normalized = target_bin_win.replace("\\", "/")

    if not os.path.isdir(target_bin_win):
        centered_error("Ошибка", f"Папка bin/win не найдена:\n{target_bin_win}")
        return

    # Завершаем процессы
    kill_processes_for_version_change()

    # Пути к base
    current_base_path = task_info.get("base_path")
    if not current_base_path or not os.path.isdir(current_base_path):
        centered_error("Ошибка", f"Папка base для задачи не найдена:\n{current_base_path}")
        return
    
    # Новый формат: .../197034/base
    base_name = os.path.basename(current_base_path)  # "base" или "base_197034"
    base_parent = os.path.basename(os.path.dirname(current_base_path))  # task_id или product_root
    current_product_root_name = os.path.basename(current_product_root)
    if base_name == "base":
        if base_parent == current_product_root_name:
            # Текущая base дефолтная, без привязки к номеру задачи (.../bin/../base).
            # Исходную папку не трогаем, а в целевой версии создаём base уже с номером задачи.
            target_task_folder = os.path.join(target_product_root, task_id)
            target_base_path = os.path.join(target_task_folder, "base").replace("\\", "/")
            base_folder_name = os.path.join(task_id, "base")  # для INI
        else:
            # Новый формат: создаём {task_id}/base в целевом продукте
            target_task_folder = os.path.join(target_product_root, base_parent)
            target_base_path = os.path.join(target_task_folder, "base").replace("\\", "/")
            base_folder_name = os.path.join(base_parent, "base")  # для INI
    else:
        # Старый формат: base_197034 — конвертируем в новый формат {task_id}/base
        target_task_folder = os.path.join(target_product_root, task_id)
        target_base_path = os.path.join(target_task_folder, "base").replace("\\", "/")
        base_folder_name = os.path.join(task_id, "base")  # для INI
    target_base_template = os.path.join(target_product_root, "base")  # Шаблонная папка base в новой версии

    # Список файлов-шаблонов (измените имена, если нужно)
    template_files = ["drvlocalize", "workmods", "dealerpresets.udb", "upgradedevices.abs", "upgradepresets.abs"]

    try:
        # Создаем новую папку base для задачи
        if os.path.exists(target_base_path):
            if not centered_askyesno("Предупреждение", f"Папка уже существует:\n{target_base_path}\n\nПерезаписать?"):
                return
            shutil.rmtree(target_base_path)
        os.makedirs(target_base_path)

        # 1. Копируем файлы-шаблоны из папки base целевой версии
        if os.path.exists(target_base_template):
            for item in template_files:
                src_item = os.path.join(target_base_template, item)
                dst_item = os.path.join(target_base_path, item)
                if os.path.exists(src_item):
                    if os.path.isdir(src_item):
                        shutil.copytree(src_item, dst_item)
                    else:
                        shutil.copy2(src_item, dst_item)
        
        # 2. Копируем только rk7.udb из старой базы
        src_udb = os.path.join(current_base_path, "rk7.udb")
        dst_udb = os.path.join(target_base_path, "rk7.udb")
        if os.path.exists(src_udb):
            shutil.copy2(src_udb, dst_udb)
        else:
            centered_warning("Внимание", "Файл rk7.udb не найден в исходной базе!")

        print(f"Base перенесена: {target_base_path}")
    except Exception as e:
        centered_error("Ошибка", f"Не удалось перенести базу:\n{e}")
        return

    # MIDBASE (создаем пустую, как и было)
    current_midbase = task_info.get("midbase_path")
    target_midbase_path = None
    if current_midbase:
        mid_name = os.path.basename(current_midbase)  # "MIDBASE" или "MIDBASE_197034"
        mid_parent = os.path.basename(os.path.dirname(current_midbase))
        if mid_name == "MIDBASE":
            if mid_parent == current_product_root_name:
                # Текущая MIDBASE дефолтная, без привязки к номеру задачи.
                # В целевой версии создаём MIDBASE уже с номером задачи.
                target_task_folder = os.path.join(target_product_root, task_id)
                target_midbase_path = os.path.join(target_task_folder, "MIDBASE").replace("\\", "/")
            else:
                # Новый формат: {task_id}/MIDBASE
                target_task_folder = os.path.join(target_product_root, mid_parent)
                target_midbase_path = os.path.join(target_task_folder, "MIDBASE").replace("\\", "/")
        else:
            # Старый формат: MIDBASE_197034 — конвертируем в новый формат {task_id}/MIDBASE
            target_task_folder = os.path.join(target_product_root, task_id)
            target_midbase_path = os.path.join(target_task_folder, "MIDBASE").replace("\\", "/")
        if os.path.exists(target_midbase_path): shutil.rmtree(target_midbase_path)
        os.makedirs(target_midbase_path, exist_ok=True)

    # === ОБНОВЛЕНИЕ JSON СТРУКТУРЫ ===
    if "versions" not in task_info: task_info["versions"] = {}
    if current_version not in task_info["versions"]:
        task_info["versions"][current_version] = {
            "ini_path": current_ini_path,
            "base_path": current_base_path,
            "midbase_path": task_info.get("midbase_path"),
            "ini_settings": task_info.get("ini_settings", {})
        }

    new_version_data = {
        "ini_path": target_ini_path_normalized,
        "base_path": target_base_path,
        "ini_settings": task_info.get("ini_settings", {}).copy()
    }
    if target_midbase_path: new_version_data["midbase_path"] = target_midbase_path

    task_info["versions"][target_version] = new_version_data
    task_info["ini_path"] = target_ini_path_normalized
    task_info["base_path"] = target_base_path
    if target_midbase_path: task_info["midbase_path"] = target_midbase_path

    tasks[task_id] = task_info
    data["tasks"] = tasks
    save_data(data)

    # Обновляем INI файлы в целевой папке
    for f in FILES:
        src = os.path.join(current_ini_path, f)
        dst = os.path.join(target_bin_win, f)
        if os.path.isfile(src): shutil.copy2(src, dst)

    update_rk7srv_ini(os.path.join(target_bin_win, "rk7srv.INI"), base_folder_name)

    # Создаём ярлыки для новой версии (указывают на target_bin_win)
    create_task_shortcuts(target_task_folder, target_bin_win)

    path_var.set(target_ini_path_normalized)
    apply_path(update_task=False)
    centered_info("Успех", f"База перенесена в версию {target_version}")


# ======================= Выбор версии при переключении задачи =======================

def delete_task_version(task_id, del_ver, select_win):
    """Удаляет версию из task_info["versions"] в JSON и папки base/MIDBASE с диска."""
    data = load_data()
    tasks = data.get("tasks", {})
    task_info = tasks.get(task_id)
    if not task_info:
        return
    versions = task_info.get("versions", {})
    ver_data = versions.get(del_ver)
    if not ver_data:
        return

    # Собираем папки для удаления
    paths_to_delete = []
    if ver_data.get("base_path"):
        paths_to_delete.append(ver_data["base_path"])
    if ver_data.get("midbase_path"):
        paths_to_delete.append(ver_data["midbase_path"])
        # Если MIDBASE лежит внутри папки {task_id} (новый формат) — удаляем и родителя если пусто
        mid_path = ver_data["midbase_path"]
        mid_name = os.path.basename(mid_path)
        if mid_name == "MIDBASE":
            mid_parent = os.path.dirname(mid_path)
            mid_parent_name = os.path.basename(mid_parent)
            # Это новый формат {task_id}/MIDBASE?
            if mid_parent_name == del_ver or mid_parent_name == task_id:
                # Проверяем, есть ли что-то кроме base и MIDBASE
                if os.path.isdir(mid_parent):
                    children = set(os.listdir(mid_parent))
                    if children <= {"base", "MIDBASE"}:
                        paths_to_delete.append(mid_parent)
    # Аналогично для base
    base_path = ver_data.get("base_path", "")
    if base_path:
        base_name = os.path.basename(base_path)
        if base_name == "base":
            base_parent = os.path.dirname(base_path)
            base_parent_name = os.path.basename(base_parent)
            if base_parent_name == del_ver or base_parent_name == task_id:
                if os.path.isdir(base_parent):
                    children = set(os.listdir(base_parent))
                    if children <= {"base", "MIDBASE"}:
                        if base_parent not in paths_to_delete:
                            paths_to_delete.append(base_parent)

    existing = [p for p in paths_to_delete if os.path.exists(p)]
    confirm_msg = f"Удалить версию {del_ver} из задачи {task_id}?"
    if existing:
        confirm_msg += f"\n\nБудут удалены папки ({len(existing)} шт.):\n" + "\n".join(existing)
    confirm_msg += "\n\nВосстановить будет невозможно."

    if not centered_askyesno("Удаление версии", confirm_msg):
        return

    # Удаляем папки с диска
    failed = []
    for p in existing:
        try:
            shutil.rmtree(p)
            print(f"Папка удалена: {p}")
        except Exception as e:
            failed.append((p, str(e)))
            print(f"Ошибка удаления {p}: {e}")

    if failed:
        err_detail = "\n".join(f"• {p}: {e}" for p, e in failed)
        centered_warning("Частичная ошибка", f"Не удалось удалить некоторые папки:\n{err_detail}")

    # Удаляем версию из JSON
    del versions[del_ver]
    if not versions:
        centered_info("Информация", "У задачи больше нет дополнительных версий.")
        select_win.destroy()
        return

    save_data(data)
    select_win.destroy()
    show_version_selection_dialog(task_id, task_info, versions, None)


def show_version_selection_dialog(task_id, task_info, versions, prev_task_id):
    """Диалог выбора версии при выборе задачи с несколькими версиями."""
    select_win = tk.Toplevel(root)
    select_win.withdraw()
    select_win.title("Выбор версии RK")

    if icon_path:
        select_win.iconbitmap(icon_path)

    version_list = list(reversed(sorted(versions.keys())))
    current_ver = extract_rk_version_from_path(task_info.get("ini_path", ""))

    select_win.transient(root)
    select_win.grab_set()

    frame = tk.Frame(select_win)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=(
        f"Задача {task_id} имеет несколько версий RK.\n"
        f"Выберите версию для работы:"
    ), justify="center").pack(padx=10, pady=(10, 5))

    version_var_local = tk.StringVar()
    if current_ver in version_list:
        version_var_local.set(current_ver)
    elif version_list:
        version_var_local.set(version_list[0])

    center_container = tk.Frame(frame)
    center_container.pack(pady=5, expand=True)

    radio_frame = tk.Frame(center_container)
    radio_frame.pack()

    for ver in version_list:
        label_text = ver
        if ver == current_ver:
            label_text += "  ◀ текущая"

        ver_row = tk.Frame(radio_frame)
        ver_row.pack(anchor="w", pady=2, fill="x")

        rb = tk.Radiobutton(
            ver_row,
            text=label_text,
            variable=version_var_local,
            value=ver,
            anchor="w",
            font=("TkDefaultFont", 9, "bold" if ver == current_ver else "normal")
        )
        rb.pack(side="left")

        tk.Button(
            ver_row, text="✕", width=2, relief="flat", fg="red",
            command=partial(delete_task_version, task_id, ver, select_win)
        ).pack(side="right", padx=(5, 0))

    def on_select():
        selected_ver = version_var_local.get()
        if not selected_ver:
            return
        if prev_task_id:
            apply_network_ids_silent_for_task(prev_task_id)
            apply_ini_flags_silent_for_task(prev_task_id)
        global _prev_task_id
        _prev_task_id = task_id
        select_win.destroy()
        apply_task_version(task_id, selected_ver)

    def on_cancel():
        select_win.destroy()

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Выбрать", command=on_select, width=12).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=on_cancel, width=12).pack(side="left", padx=5)

    _center_window(select_win)

    select_win.focus_force()
    select_win.deiconify()


def apply_task_version(task_id, selected_version):
    """Применяет настройки конкретной версии для задачи."""
    data = load_data()
    tasks = data.get("tasks", {})
    task_info = tasks.get(task_id)

    if not task_info:
        return

    versions = task_info.get("versions", {})
    version_info = versions.get(selected_version)

    if not version_info:
        centered_error("Ошибка", f"Информация о версии {selected_version} не найдена.")
        return

    task_info["ini_path"] = version_info["ini_path"]
    task_info["base_path"] = version_info["base_path"]
    if "ini_settings" in version_info:
        task_info["ini_settings"] = version_info["ini_settings"]
    # Переносим midbase_path если есть
    if "midbase_path" in version_info:
        task_info["midbase_path"] = version_info["midbase_path"]

    tasks.pop(task_id)
    tasks = {task_id: task_info, **tasks}
    data["tasks"] = tasks
    save_data(data)

    task_id_combobox['values'] = [""] + list(tasks.keys())

    path_var.set(version_info["ini_path"])
    apply_path_silent()

    ini_settings = version_info.get("ini_settings", {})
    ini_path_from_version = version_info["ini_path"]
    rk7srv_ini_path = os.path.join(ini_path_from_version, "rk7srv.INI")

    if "UseDBSync" in ini_settings:
        for filename, value in ini_settings["UseDBSync"].items():
            full_path = os.path.join(ini_path_from_version, filename)
            if os.path.exists(full_path):
                update_ini_file(full_path, str(value), "UseDBSync")

    if "UseSQL" in ini_settings:
        if os.path.exists(rk7srv_ini_path):
            update_ini_file(rk7srv_ini_path, str(ini_settings["UseSQL"]), "USESQL")

    if "Station" in ini_settings and "Server" in ini_settings:
        station_var.set(ini_settings["Station"])
        server_var.set(ini_settings["Server"])
        save_wincash_params()

    if "Port" in ini_settings and ini_settings["Port"]:
        apply_port(ini_path_from_version, str(ini_settings["Port"]))
        port_var.set(str(ini_settings["Port"]))

    base_path = version_info.get("base_path", "")
    if base_path and os.path.exists(rk7srv_ini_path):
        base_name = os.path.basename(base_path)
        base_parent = os.path.basename(os.path.dirname(base_path))
        base_dir = os.path.join(base_parent, base_name) if base_name == "base" else base_name
        update_rk7srv_ini(rk7srv_ini_path, base_dir)

    # === MIDBASE ===
    midbase_path = version_info.get("midbase_path", "")
    if midbase_path:
        mid_name = os.path.basename(midbase_path)
        mid_parent = os.path.basename(os.path.dirname(midbase_path))
        midbase_folder_name = os.path.join(mid_parent, mid_name) if mid_name == "MIDBASE" else mid_name
        update_rkeeper_ini_basepath(ini_path_from_version, midbase_folder_name)

    # Обновляем _prev_task_id после успешного применения версии
    global _prev_task_id
    _prev_task_id = task_id

    on_check()


def show_task_selection_dialog(version_path, task_list, fallback_task_id=None):
    """
    Диалог выбора задачи при выборе версии RK.
    Зеркало show_version_selection_dialog: там к задаче предлагаются версии,
    здесь к версии предлагаются задачи.
    Работает при включённом флаге "Выбор задачи из выбора версии".
    """
    select_win = tk.Toplevel(root)
    select_win.withdraw()
    select_win.title("Выбор задачи")

    if icon_path:
        select_win.iconbitmap(icon_path)

    # version_key — точный ключ версии (как в task_info["versions"]), может быть None.
    # version_label — то, что показываем пользователю.
    version_key = extract_rk_version_from_path(version_path)
    version_label = version_key or os.path.basename(version_path)
    current_task = task_id_var.get().strip()

    select_win.transient(root)
    select_win.grab_set()

    frame = tk.Frame(select_win)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=(
        f"Версия {version_label} имеет несколько задач.\n"
        f"Выберите задачу для работы:"
    ), justify="center").pack(padx=10, pady=(10, 5))

    task_var_local = tk.StringVar()
    if current_task in task_list:
        task_var_local.set(current_task)
    elif task_list:
        task_var_local.set(task_list[0])

    center_container = tk.Frame(frame)
    center_container.pack(pady=5, expand=True)

    radio_frame = tk.Frame(center_container)
    radio_frame.pack()

    for tid in task_list:
        label_text = tid
        if tid == current_task:
            label_text += "  ◀ текущая"

        tk.Radiobutton(
            radio_frame,
            text=label_text,
            variable=task_var_local,
            value=tid,
            anchor="w",
            font=("TkDefaultFont", 9, "bold" if tid == current_task else "normal")
        ).pack(anchor="w", pady=2, fill="x")

    def _load_task(selected_tid):
        """Применяет задачу: через trace, либо напрямую если значение не изменилось."""
        global _forced_version
        # Версия уже выбрана пользователем на предыдущем шаге — фиксируем её,
        # чтобы on_task_selected не спрашивал версию повторно.
        _forced_version = version_key

        task_id_combobox['values'] = load_task_ids()
        if task_id_var.get().strip() == selected_tid:
            # trace не сработает — применяем настройки напрямую
            on_task_selected(None)
        else:
            task_id_var.set(selected_tid)

    def on_select():
        selected_tid = task_var_local.get()
        if not selected_tid:
            return
        select_win.destroy()
        _load_task(selected_tid)

    def on_cancel():
        select_win.destroy()
        # Отмена — грузим параметры из INI-файлов выбранной версии без привязки к задаче
        if fallback_task_id:
            _load_task(fallback_task_id)
        else:
            load_wincash_params()
            on_check()

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Выбрать", command=on_select, width=12).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=on_cancel, width=12).pack(side="left", padx=5)

    _center_window(select_win)

    select_win.focus_force()
    select_win.deiconify()

import keyboard

# ======================= Поддержка копирования при русской раскладке =======================

def get_focused_widget():
    """Получает текущий сфокусированный виджет"""
    try:
        return root.focus_get()
    except:
        return None

def is_our_focus():
    """Проверяет, находится ли фокус в нашем приложении"""
    try:
        widget = root.focus_get()
        return widget is not None
    except:
        return False

def copy_text_global():
    """Копирование текста при Ctrl+C (работает при любой раскладке)"""
    if not is_our_focus():
        return
    def _do_copy():
        try:
            widget = root.focus_get()
            if widget and hasattr(widget, 'selection_get'):
                text = widget.selection_get()
                root.clipboard_clear()
                root.clipboard_append(text)
        except:
            pass
    root.after(0, _do_copy)

def paste_text_global():
    """Вставка текста при Ctrl+V (работает при любой раскладке)"""
    if not is_our_focus():
        return
    def _do_paste():
        try:
            widget = root.focus_get()
            if widget and hasattr(widget, 'delete') and hasattr(widget, 'insert'):
                text = root.clipboard_get()
                widget.delete(0, tk.END)
                widget.insert(0, text)
        except:
            pass
    root.after(0, _do_paste)

def cut_text_global():
    """Вырезание текста при Ctrl+X (работает при любой раскладке)"""
    if not is_our_focus():
        return
    def _do_cut():
        try:
            widget = root.focus_get()
            if widget and hasattr(widget, 'selection_get') and hasattr(widget, 'delete'):
                text = widget.selection_get()
                root.clipboard_clear()
                root.clipboard_append(text)
                widget.delete(0, tk.END)
        except:
            pass
    root.after(0, _do_cut)

def setup_global_hotkeys():
    """Регистрирует глобальные горячие клавиши"""
    keyboard.add_hotkey('ctrl+c', copy_text_global)
    keyboard.add_hotkey('ctrl+v', paste_text_global)
    keyboard.add_hotkey('ctrl+x', cut_text_global)

def on_closing():
    """Очищает горячие клавиши перед закрытием"""
    try:
        keyboard.remove_all_hotkeys()
    except:
        pass
    root.destroy()
# ======================= КОНЕЦ ПОДДЕРЖКИ КОПИРОВАНИЯ =======================

# Группа: путь к RK7 и задача
path_task_frame = tk.LabelFrame(settings_tab, text="Путь и задача")
path_task_frame.pack(padx=10, pady=(10, 0), fill="x")

# Фрейм для метки, кнопки "Открыть" и поля для номера задачи
label_and_open_frame = tk.Frame(path_task_frame)
label_and_open_frame.pack(fill="x", padx=5, pady=(5, 0), ipady=0)

# Левая часть: метка "Путь к RK7:" и кнопка "Открыть"
tk.Label(
    label_and_open_frame,
    text="Путь к RK7:",
    font=("TkDefaultFont", 9)
).grid(row=0, column=0, sticky="w")

# Кнопка "Открыть" (на той же строке, справа от метки)
tk.Button(
    label_and_open_frame,
    text="Открыть",
    command=open_explorer_to_root,
    font=("TkDefaultFont", 8)
).grid(row=0, column=1, padx=(1, 0), sticky="w")


# Фрейм для метки и комбобокса
task_id_frame = tk.Frame(label_and_open_frame)
task_id_frame.grid(row=0, column=2, columnspan=2, padx=(10, 0), sticky="w")

tk.Label(
    task_id_frame,
    text="Номер задачи:",
    font=("TkDefaultFont", 9)
).pack(side="left")

# Combobox для номера задачи
#task_id_var = tk.StringVar() # создается ранее в коде
task_id_combobox = ttk.Combobox(
    task_id_frame,
    textvariable=task_id_var,
    width=7,
    font=("TkDefaultFont", 9)
)
task_id_combobox.pack(side="left", padx=(1, 0))
# trace_add на task_id_var заменяет <<ComboboxSelected>> — работает и при смене, и при выборе той же задачи

def _on_click(event):
    # Стрелка находится в правой части, проверяем координату x
    widget_width = task_id_combobox.winfo_width()
    #print(f"[DEBUG] клик x={event.x}, ширина виджета={widget_width}")
    if event.x > widget_width - 20:  # клик по стрелке
        #print("[DEBUG] клик по СТРЕЛКЕ")
        def _scroll_to_top():
            try:
                task_id_combobox.tk.eval(f'set popdown [ttk::combobox::PopdownWindow {task_id_combobox}]; $popdown.f.l yview moveto 0')
                #print("[DEBUG] scroll выполнен")
            except Exception as e:
                print(f"[DEBUG] Ошибка: {e}")
        task_id_combobox.after(50, _scroll_to_top)

task_id_combobox.bind("<ButtonPress-1>", _on_click)

# --- Инициализация значений при первом запуске ---
_initial_task_values = [""] + list(load_data().get("tasks", {}).keys())
task_id_combobox['values'] = _initial_task_values
_current_task = task_id_var.get().strip()
if _current_task and _current_task in _initial_task_values:
    # Задача из INI есть в списке — показываем её
    task_id_combobox.current(_initial_task_values.index(_current_task))
elif len(_initial_task_values) > 1:
    # Задачи в JSON есть — показываем первую реальную (индекс 1, после пустой строки)
    task_id_combobox.current(1)
    task_id_var.set(_initial_task_values[1])
else:
    # Задач нет вообще — показываем пустую строку
    task_id_combobox.current(0)

def _on_task_id_change(*_):
    """Callback для trace_add — вызывается при любом изменении task_id_var."""
    current_value = task_id_var.get()
    stripped_value = current_value.strip()
    if stripped_value != current_value:
        task_id_var.set(stripped_value)
        return  # trace сработает повторно уже с очищенным значением

    on_task_selected(None)

_prev_task_id = task_id_var.get().strip()
task_id_var.trace_add("write", _on_task_id_change)

def save_task_id_to_file():
    task_id = task_id_var.get().strip()
    if not task_id:
        return  # Если поле пустое, ничего не сохраняем

    product_root = find_product_root(path_var.get())
    if not product_root:
        centered_error("Ошибка", "Не удалось определить корневую папку продукта.")
        return
"""
    task_id_file = os.path.join(product_root, "ID задачи.txt")
    try:
        with open(task_id_file, "w", encoding="utf-8") as f:
            f.write(task_id)
    except Exception as e:
        centered_error("Ошибка", f"Не удалось сохранить номер задачи:\n{e}")
"""

def get_usedbsync_values_for_path(path):
    """Читает UseDBSync из всех INI-файлов для указанного пути."""
    values = {}
    for filename in FILES:
        file_path = os.path.join(path, filename)
        if os.path.isfile(file_path):
            try:
                value = _read_ini_key(file_path, "UseDBSync", "DBSYNC")
                values[filename] = value if value else "0"
            except Exception:
                values[filename] = "0"
    return values

def get_usesql_value_for_path(ini_path_val):
    """Читает USESQL из rk7srv.INI для указанного пути."""
    rk7srv_path = os.path.join(ini_path_val, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return "0"
    try:
        value = _read_ini_key(rk7srv_path, "USESQL", None)
        return value if value else "0"
    except Exception:
        return "0"

def get_port_value_for_path(ini_path_val):
    """Читает PORT из секции [TCPSOC] файла rk7srv.INI для указанного пути."""
    rk7srv_path = os.path.join(ini_path_val, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return ""
    try:
        return _read_ini_key(rk7srv_path, "PORT", "TCPSOC") or ""
    except Exception:
        return ""

def _read_ini_key(filepath, key, section):
    """Читает значение ключа key из секции section файла filepath."""
    try:
        with open(filepath, 'r', encoding='cp1251') as f:
            in_section = section is None
            for line in f:
                line = line.strip()
                if section and re.match(rf'^\[{section}\]\s*$', line, re.IGNORECASE):
                    in_section = True
                    continue
                if section and re.match(r'^\[.*\]\s*$', line):
                    in_section = False
                if in_section and re.match(rf'^\s*{key}\s*=\s*(.*)$', line, re.IGNORECASE):
                    return line.split('=', 1)[1].strip()
    except Exception:
        pass
    return None

def get_station_server_for_path(ini_path_val):
    """Читает Station и Server из wincash.ini для указанного пути."""
    wincash_path = os.path.join(ini_path_val, "wincash.ini")
    station, server = "", ""
    if os.path.isfile(wincash_path):
        try:
            with open(wincash_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(wincash_path, 'r', encoding='cp1251') as f:
                content = f.read()
        for line in content.splitlines():
            l = line.strip()
            if l.lower().startswith("station="):
                station = l.split("=", 1)[-1].strip()
            elif l.lower().startswith("server ="):
                server = l.split("=", 1)[-1].strip()
    return station, server

def get_ini_settings(ini_path):
    """Сбор параметров UseDBSync, UseSQL, Station, Server, Port, UDBFILE, WorkModules из INI-файлов."""
    station, server = get_station_server_for_path(ini_path)
    settings = {
        "UseDBSync": get_usedbsync_values_for_path(ini_path),
        "UseSQL": get_usesql_value_for_path(ini_path),
        "Station": station,
        "Server": server,
        "Port": get_port_value_for_path(ini_path),
    }
    # Добавляем UDBFILE и WorkModules из rk7srv.INI
    rk7srv = get_rk7srv_udb_workmodules(ini_path)
    if rk7srv:
        settings["UDBFILE"] = rk7srv.get("UDBFILE")
        settings["WorkModules"] = rk7srv.get("WorkModules")
    return settings

def get_rk7srv_udb_workmodules(ini_path_val):
    """Читает UDBFILE и WorkModules из rk7srv.INI."""
    rk7srv_path = os.path.join(ini_path_val, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return None
    try:
        with open(rk7srv_path, 'r', encoding='cp1251') as f:
            content = f.read()
        result = {}
        for line in content.splitlines():
            m = re.match(r'^\s*(UDBFILE|WorkModules)\s*=\s*(.*)$', line, re.IGNORECASE)
            if m:
                result[m.group(1)] = m.group(2).strip()
        return result if result else None
    except Exception as e:
        print(f"Ошибка чтения rk7srv.INI: {e}")
        return None

def _apply_rk7srv_udf_workmodules(rk7srv_ini_path, ini_settings):
    """Восстанавливает UDBFILE и WorkModules в rk7srv.INI из сохранённых дефолтных значений."""
    udbfile = ini_settings.get("UDBFILE")
    workmodules = ini_settings.get("WorkModules")
    if not udbfile and not workmodules:
        return
    try:
        with open(rk7srv_ini_path, 'r', encoding='cp1251') as f:
            lines = f.readlines()

        new_lines = []
        udbfile_written = False
        workmodules_written = False

        for line in lines:
            if re.match(r'^\s*UDBFILE\s*=', line, re.IGNORECASE):
                if udbfile:
                    new_lines.append(f"UDBFILE            = {udbfile}\n")
                    udbfile_written = True
                else:
                    new_lines.append(line)
            elif re.match(r'^\s*WorkModules\s*=', line, re.IGNORECASE):
                if workmodules:
                    new_lines.append(f"WorkModules        = {workmodules}\n")
                    workmodules_written = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        with open(rk7srv_ini_path, 'w', encoding='cp1251') as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"Ошибка восстановления UDBFILE/WorkModules: {e}")

# ======================= Дефолтные настройки директории версии =======================

def save_default_ini_settings(ini_path_val=None):
    """Сохраняет текущие параметры INI как дефолтные для данной директории версии."""
    global ini_path
    if ini_path_val is None:
        ini_path_val = ini_path
    if not ini_path_val:
        return
    key = ini_path_val.replace("\\", "/").rstrip("/")
    settings = get_ini_settings(ini_path_val)
    data = load_data()
    if "defaults" not in data:
        data["defaults"] = {}
    data["defaults"][key] = {
        "ini_path": ini_path_val.replace("\\", "/"),
        "ini_settings": settings,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_data(data)
    print(f"[OK] Дефолтные настройки сохранены для: {ini_path_val}")

def load_default_ini_settings(ini_path_val=None):
    """Загружает дефолтные настройки для данной директории версии."""
    global ini_path
    if ini_path_val is None:
        ini_path_val = ini_path
    if not ini_path_val:
        return None
    key = ini_path_val.replace("\\", "/").rstrip("/")
    data = load_data()
    return data.get("defaults", {}).get(key)

def apply_default_ini_settings(ini_path_val=None):
    """Применяет сохранённые дефолтные настройки в INI-файлы."""
    global ini_path
    if ini_path_val is None:
        ini_path_val = ini_path
    default_entry = load_default_ini_settings(ini_path_val)
    if not default_entry:
        # Дефолтных настроек нет — просто обновляем UI
        load_wincash_params()
        on_check()
        return
    ini_settings = default_entry.get("ini_settings", {})
    rk7srv_ini_path = os.path.join(ini_path_val, "rk7srv.INI")
    # Применяем UseDBSync
    if "UseDBSync" in ini_settings:
        for filename, value in ini_settings["UseDBSync"].items():
            full_path = os.path.join(ini_path_val, filename)
            if os.path.exists(full_path):
                update_ini_file(full_path, str(value), "UseDBSync")
    # Применяем UseSQL
    if "UseSQL" in ini_settings and os.path.exists(rk7srv_ini_path):
        update_ini_file(rk7srv_ini_path, str(ini_settings["UseSQL"]), "USESQL")
    # Восстанавливаем UDBFILE и WorkModules в rk7srv.INI
    if os.path.exists(rk7srv_ini_path):
        _apply_rk7srv_udf_workmodules(rk7srv_ini_path, ini_settings)
    # Применяем Station/Server
    if "Station" in ini_settings and "Server" in ini_settings:
        station_var.set(ini_settings["Station"])
        server_var.set(ini_settings["Server"])
        save_wincash_params()
    on_check()
    print(f"[OK] Дефолтные настройки применены для: {ini_path_val}")

# ======================= Конец дефолтных настроек =======================

def sync_default_settings_if_no_task():
    """Если выбрана пустая задача (дефолтный режим) — пересохраняет
    текущие параметры INI как дефолтные для активной директории версии."""
    if not task_id_var.get().strip():
        save_default_ini_settings(ini_path)

# Сохранения номера задачи в файл
def save_task_id():
    task_id = task_id_var.get().strip()
    if not task_id:
        centered_warning("Предупреждение", "Поле 'Номер задачи' пустое!")
        return

    product_root = find_product_root(path_var.get())
    if not product_root:
        centered_error("Ошибка", "Не удалось определить корневую папку продукта.")
        return

    base_path = os.path.join(product_root, "base")
    if not os.path.exists(base_path):
        centered_error("Ошибка", f"Папка {base_path} не найдена!")
        return

    # Проверяем блокировку refsrv.exe
    refsrv_running = any(
        p.info['name'].lower() == "refsrv.exe"
        for p in psutil.process_iter(['name'])
    )

    if refsrv_running:
        test_file = os.path.join(base_path, "rk7.udb")
        if os.path.exists(test_file):
            try:
                shutil.copy2(test_file, os.path.join(product_root, "rk7.udb.test"))
                os.remove(os.path.join(product_root, "rk7.udb.test"))
            except PermissionError:
                if centered_askyesno(
                    "Предупреждение",
                    "Файлы в папке base заблокированы процессом refsrv.exe.\n"
                    "Закрыть процесс и продолжить?"
                ):
                    for proc in psutil.process_iter(['name']):
                        if proc.info['name'].lower() == "refsrv.exe":
                            proc.terminate()
                            time.sleep(1)
                else:
                    return
            except Exception as e:
                centered_error("Ошибка", f"Не удалось проверить блокировку:\n{e}")
                return

    # === Папка {task_id}/base ===
    task_folder = os.path.join(product_root, task_id)
    new_base_path = os.path.join(task_folder, "base")
    if os.path.exists(new_base_path):
        if centered_askyesno("Предупреждение", f"Папка {new_base_path} уже существует. Перезаписать?"):
            try:
                shutil.rmtree(new_base_path)
            except Exception as e:
                centered_error("Ошибка", f"Не удалось удалить существующую папку:\n{e}")
                return
        else:
            return

    try:
        shutil.copytree(base_path, new_base_path)
    except Exception as e:
        centered_error("Ошибка", f"Не удалось скопировать папку base:\n{e}")
        return

    # === Папка {task_id}/MIDBASE - ВСЕГДА СОЗДАЁТСЯ ПУСТОЙ ===
    midbase_path = os.path.join(task_folder, "MIDBASE")
    # Путь для записи в INI: {task_id}\MIDBASE
    midbase_ini_name = os.path.join(task_id, "MIDBASE")

    if os.path.exists(midbase_path):
        if not centered_askyesno(
            "Предупреждение",
            f"Папка {midbase_path} уже существует. Перезаписать?"
        ):
            return
        else:
            try:
                shutil.rmtree(midbase_path)
            except Exception as e:
                centered_error("Ошибка", f"Не удалось удалить {midbase_path}:\n{e}")
                return

    # Создаём пустую папку MIDBASE
    try:
        os.makedirs(midbase_path, exist_ok=True)
        print(f"[OK] Создана пустая папка MIDBASE: {midbase_path}")
    except Exception as e:
        centered_error("Ошибка", f"Не удалось создать папку MIDBASE:\n{e}")
        return

    # Обновляем BasePath в RKEEPER.INI (передаём {task_id}\MIDBASE)
    update_rkeeper_ini_basepath(path_var.get(), midbase_ini_name)

    # Собираем параметры INI
    ini_settings = get_ini_settings(path_var.get())

    # Сохраняем в JSON
    data = load_data()
    tasks = data.get("tasks", {})

    # Сохраняем versions из существующей записи (если есть)
    existing_versions = {}
    if task_id in tasks and "versions" in tasks[task_id]:
        existing_versions = tasks[task_id]["versions"]

    task_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_path": new_base_path.replace("\\", "/"),
        "midbase_path": midbase_path.replace("\\", "/"),
        "ini_path": path_var.get().replace("\\", "/"),
        "status": "copied",
        "ini_settings": ini_settings,
        "versions": existing_versions
    }

    tasks[task_id] = task_entry
    tasks = {task_id: tasks[task_id], **{k: v for k, v in tasks.items() if k != task_id}}
    data["tasks"] = tasks
    save_data(data)

    task_id_combobox['values'] = load_task_ids()
    task_id_combobox.current(1)  # Всегда показывать пустую строку первой при открытии

    # Обновляем rk7srv.INI: передаём путь {task_id}\base
    base_dir = os.path.join(task_id, "base")
    rk7srv_ini_path = os.path.join(path_var.get(), "rk7srv.INI")
    update_rk7srv_ini(rk7srv_ini_path, base_dir)

    # Создаём ярлыки
    create_task_shortcuts(task_folder, path_var.get())

    centered_info(
        "Успех",
        f"Папка base скопирована как {new_base_path}!\n"
        f"Пустая папка MIDBASE создана: {midbase_path}"
    )

def create_task_shortcuts(task_folder, bin_win_path):
    """Создаёт ярлыки и ярлык папки win в папке задачи."""
    try:
        # 1. Ярлык папки win
        win_folder = bin_win_path  # это и есть путь к папке win
        if os.path.isdir(win_folder):
            create_folder_lnk(os.path.join(task_folder, "..win.lnk"), win_folder)

        # 2. refsrv.exe с ключом /desktop
        refsrv_src = os.path.join(bin_win_path, "refsrv.exe")
        if os.path.isfile(refsrv_src):
            create_lnk(os.path.join(task_folder, "refsrv.lnk"), refsrv_src, "/desktop")

        # 3. MIDSERV.exe с ключом /desktop
        midsrv_src = os.path.join(bin_win_path, "MIDSERV.exe")
        if os.path.isfile(midsrv_src):
            create_lnk(os.path.join(task_folder, "MIDSERV.lnk"), midsrv_src, "/desktop")

        # 4. rk7man.bat без ключа
        rk7man_src = os.path.join(bin_win_path, "rk7man.bat")
        if os.path.isfile(rk7man_src):
            create_lnk(os.path.join(task_folder, "rk7man.lnk"), rk7man_src, "")

        # 5. wincash.bat без ключа
        wincash_src = os.path.join(bin_win_path, "wincash.bat")
        if os.path.isfile(wincash_src):
            create_lnk(os.path.join(task_folder, "wincash.lnk"), wincash_src, "")

        print(f"[OK] Ярлыки созданы в {task_folder}")
    except Exception as e:
        print(f"[WARN] Не удалось создать ярлыки: {e}")

def create_folder_lnk(lnk_path, target_folder):
    """Создаёт ярлык папки (.lnk) через PowerShell."""
    if os.path.exists(lnk_path):
        return
    try:
        # Рабочая папка — родитель target_folder (bin), обратные слеши
        bin_folder = os.path.dirname(target_folder).replace("/", "\\")
        # Для папок нужен завершающий слеш
        target_folder_escaped = target_folder.replace("/", "\\")
        if not target_folder_escaped.endswith("\\"):
            target_folder_escaped += "\\"
        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{lnk_path}")
$Shortcut.TargetPath = "{target_folder_escaped}"
$Shortcut.WorkingDirectory = "{bin_folder}"
$Shortcut.Description = "..win"
$Shortcut.Save()
'''
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode != 0:
            print(f"[WARN] PowerShell error: {result.stderr}")
    except Exception as e:
        print(f"[WARN] create_folder_lnk failed: {e}")

def create_lnk(lnk_path, target, arguments):
    """Создаёт .lnk файл через PowerShell."""
    if os.path.exists(lnk_path):
        return
    try:
        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{lnk_path}")
$Shortcut.TargetPath = "{target}"
$Shortcut.Arguments = "{arguments}"
$Shortcut.WorkingDirectory = "{os.path.dirname(target)}"
$Shortcut.Save()
'''
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode != 0:
            print(f"[WARN] PowerShell error: {result.stderr}")
    except Exception as e:
        print(f"[WARN] create_lnk failed: {e}")

# Загрузка номеров задач
def load_task_ids():
    data = load_data()
    return [""] + list(data.get("tasks", {}).keys())

def delete_task():
    selected_task_id = task_id_var.get().strip()
    if not selected_task_id:
        centered_warning("Предупреждение", "Выберите задачу для удаления!")
        return

    data = load_data()
    tasks = data.get("tasks", {})

    if selected_task_id not in tasks:
        centered_warning("Предупреждение", f"Задача {selected_task_id} не найдена!")
        return

    task_info = tasks[selected_task_id]

    # === Собираем ВСЕ пути base и midbase (основной + из всех версий) ===
    all_paths = set()
    task_folders = set()  # Папки {task_id}, которые нужно удалить если они окажутся пустыми

    def _collect_path(p):
        """  Добавляет путь в all_paths и, если это новый формат (base/MIDBASE внутри {task_id}),
             запоминает родительскую папку для последующей проверки. """
        if not p:
            return
        norm = os.path.normpath(p)
        all_paths.add(norm)
        leaf = os.path.basename(norm)
        if leaf in ("base", "MIDBASE"):
            task_folders.add(os.path.dirname(norm))

    # Основной base_path
    _collect_path(task_info.get("base_path"))

    # Основной midbase_path
    _collect_path(task_info.get("midbase_path"))

    # base_path и midbase_path из каждой версии
    versions = task_info.get("versions", {})
    for _, ver_info in versions.items():
        _collect_path(ver_info.get("base_path"))
        _collect_path(ver_info.get("midbase_path"))

    # Добавляем родительские папки {task_id}, которые содержат только base/MIDBASE
    for tf in task_folders:
        if os.path.isdir(tf):
            children = set(os.listdir(tf))
            if children <= {"base", "MIDBASE"}:  # папка содержит только эти подпапки
                all_paths.add(tf)

    # === Формируем сообщение для подтверждения ===
    existing_paths = [p for p in all_paths if os.path.exists(p)]

    confirm_msg = f"Удалить задачу {selected_task_id} из списка?"
    if existing_paths:
        paths_list = "\n".join(existing_paths)
        confirm_msg += (
            f"\n\nБудут удалены папки ({len(existing_paths)} шт.):\n{paths_list}"
        )
    if versions:
        ver_list = ", ".join(versions.keys())
        confirm_msg += f"\n\nВерсии RK в задаче: {ver_list}"

    if not centered_askyesno("Подтверждение удаления", confirm_msg):
        return

    # === Шаг 0: Восстанавливаем дефолтные INI-настройки для всех связанных путей ===
    ini_paths_to_restore = set()
    # Основной ini_path
    if task_info.get("ini_path"):
        ini_paths_to_restore.add(task_info["ini_path"])
    # ini_path из каждой версии
    for _, ver_info in versions.items():
        if ver_info.get("ini_path"):
            ini_paths_to_restore.add(ver_info["ini_path"])

    for ip in ini_paths_to_restore:
        apply_default_ini_settings(ip)
        print(f"[OK] Дефолтные настройки восстановлены для: {ip}")

    # === Шаг 1: Удаляем ВСЕ папки base и midbase с диска ===
    failed_paths = []
    deleted_paths = []

    for path in existing_paths:
        try:
            shutil.rmtree(path)
            deleted_paths.append(path)
            print(f"Папка удалена: {path}")
        except Exception as e:
            failed_paths.append((path, str(e)))
            print(f"Ошибка удаления {path}: {e}")

    # === Шаг 1.5: Удаляем папку {task_id} с ярлыками ===
    product_root = find_product_root(path_var.get())
    if product_root:
        task_folder_to_delete = os.path.join(product_root, selected_task_id)
        if os.path.isdir(task_folder_to_delete):
            try:
                shutil.rmtree(task_folder_to_delete)
                print(f"Папка задачи удалена: {task_folder_to_delete}")
            except Exception as e:
                print(f"Ошибка удаления папки задачи {task_folder_to_delete}: {e}")

    # Если хотя бы одна папка не удалилась — предупреждаем, но продолжаем
    if failed_paths:
        error_details = "\n".join(f"• {p}: {err}" for p, err in failed_paths)
        action = centered_askyesno(
            "Частичная ошибка",
            f"Не удалось удалить некоторые папки:\n{error_details}\n\n"
            f"Всё равно удалить запись о задаче из списка?"
        )
        if not action:
            return

    # === Шаг 2: Удаляем запись из JSON ===
    del tasks[selected_task_id]
    data["tasks"] = tasks
    save_data(data)

    # === Шаг 3: Обновляем интерфейс ===
    task_id_combobox['values'] = load_task_ids()
    task_id_combobox.current(0)  # Выбираем пустую строку
    task_id_var.set("")

    # Формируем итоговое сообщение
    result_msg = f"Задача {selected_task_id} удалена!"
    if deleted_paths:
        result_msg += f"\n\nУдалено папок: {len(deleted_paths)}"
    if failed_paths:
        result_msg += f"\nНе удалось удалить: {len(failed_paths)}"

    centered_info("Успех", result_msg)


# Кнопка "Сохранить"
tk.Button(
    label_and_open_frame,
    text="Сохранить",
    command=save_task_id, # Функция сохранения номера здачи
    font=("TkDefaultFont", 8)
).grid(row=0, column=4, padx=(5, 0), sticky="w")

# Выбор пути
path_frame = tk.Frame(path_task_frame)
path_frame.pack(fill="x", padx=5, pady=(5, 5))
path_var = tk.StringVar()
ini_paths, auto_update_enabled, task_from_version_enabled, keep_cloud_files_enabled = load_settings_and_paths()
if ini_paths:
    path_var.set(ini_paths[0])
path_entry = ttk.Combobox(path_frame, textvariable=path_var, values=ini_paths)
path_entry.pack(side="left", fill="x", expand=True)





def browse_path():
    selected = filedialog.askdirectory()
    if not selected:
        return
    selected = os.path.normpath(selected).replace("\\", "/")

    # Попробуем найти bin/win и подготовиться к проверке файлов
    bin_win_path = None
    if os.path.basename(selected).lower() == "win":
        parent = os.path.dirname(selected)
        if os.path.basename(parent).lower() == "bin":
            bin_win_path = selected
    elif os.path.basename(selected).lower() == "bin":
        bin_win_path = os.path.join(selected, "win")
    else:
        bin_win_path = os.path.join(selected, "bin", "win")

    # Список файлов, которые нужно проверить (включая rk7man.ini)
    required_files = FILES

    # Копируем отсутствующие файлы из bin/win/ini
    if os.path.isdir(bin_win_path):
        missing = [f for f in required_files if not os.path.isfile(os.path.join(bin_win_path, f))]
        bin_win_ini = os.path.join(bin_win_path, "ini")
        copied = []
        for f in missing:
            source = os.path.join(bin_win_ini, f)
            target = os.path.join(bin_win_path, f)
            if os.path.isfile(source):
                try:
                    shutil.copy2(source, target)
                    copied.append(f)
                except Exception as e:
                    centered_error("Ошибка", f"Не удалось скопировать {f}:\n{e}")
        if copied:
            centered_info("Файлы скопированы", f"Скопированы из bin\\win\\ini:\n{', '.join(copied)}")

    # Теперь проверяем наличие файлов и определяем корень продукта
    product_root = find_product_root(selected)
    if not product_root:
        centered_error("Ошибка", "Выбран некорректный путь.\nТребуется папка, содержащая bin/win с INI-файлами.")
        return
    
    path_var.set(os.path.join(product_root, "bin", "win").replace("\\", "/"))
    apply_path()

tk.Button(path_frame, text="Обзор", command=browse_path, font=("TkDefaultFont", 8)).pack(side="left", padx=5)


# Cинхронизация параметров из INI-файлов с приоритетом по дате изменения
def update_ini_info_by_priority():
    wincash_path = os.path.join(ini_path, "wincash.ini")
    rkeeper_path = os.path.join(ini_path, "RKEEPER.INI")

    # Если оба файла отсутствуют — выход
    if not os.path.isfile(wincash_path) and not os.path.isfile(rkeeper_path):
        return

    # Получаем времена изменения
    wincash_mtime = os.path.getmtime(wincash_path) if os.path.isfile(wincash_path) else 0
    rkeeper_mtime = os.path.getmtime(rkeeper_path) if os.path.isfile(rkeeper_path) else 0

    # Если wincash.ini новее — приоритет за ним
    if wincash_mtime >= rkeeper_mtime:
        try:
            with open(wincash_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(wincash_path, 'r', encoding='cp1251') as f:
                lines = f.readlines()

        for line in lines:
            line = line.strip()
            if "=" in line:
                key, value = map(str.strip, line.split("=", 1))
                key_lower = key.lower()
                # Обновляем переменные, если значения отличаются
                if key_lower == "station" and value != station_var.get():
                    station_var.set(value)
                elif key_lower == "server" and value != server_var.get():
                    server_var.set(value)

    else:
        # Иначе приоритет за RKEEPER.INI — извлекаем client = MID
        try:
            with open(rkeeper_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(rkeeper_path, "r", encoding="cp1251") as f:
                lines = f.readlines()

        for line in lines:
            if line.strip().lower().startswith("client"):
                _, value = line.split("=", 1)
                value = value.strip()
                if value:
                    if value != server_var.get():
                        server_var.set(value)
                break

        # Если station (CASH) всё ещё пуст — пробуем взять из wincash.ini
        if not station_var.get() and os.path.isfile(wincash_path):
            try:
                with open(wincash_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                with open(wincash_path, 'r', encoding='cp1251') as f:
                    lines = f.readlines()
            for line in lines:
                if line.strip().lower().startswith("station="):
                    station_var.set(line.strip().split("=", 1)[-1].strip())
                    break

    # Отладочная информация — какой файл был выбран приоритетным
    # print("[DEBUG] Используем", "wincash.ini" if wincash_mtime >= rkeeper_mtime else "RKEEPER.INI")

def apply_path(event=None, update_task=True): # Добавлен параметр update_task
    global ini_path, INI_FILE_USESQL, _forced_version

    new_path = path_var.get()
    if not os.path.isdir(new_path):
        centered_error("Ошибка", f"Путь не найден:\n{new_path}")
        return

    # Обновляем глобальные переменные
    ini_path = new_path
    INI_FILE_USESQL = os.path.join(ini_path, "rk7srv.INI")

    # Сохраняем выбранный путь в конфиг
    save_settings_and_path(ini_path)
    
    # --- ЛОГИКА АВТОЗАГРУЗКИ ЗАДАЧИ ---
    if update_task: # Выполняем только если разрешено
        latest_task_id = find_latest_task_for_path(ini_path)

        # === ФЛАГ "Выбор задачи из выбора версии" ===
        # Если включён и для версии есть несколько задач — предлагаем выбрать задачу
        if task_from_version_var.get():
            path_tasks = find_tasks_for_path(ini_path)
            if len(path_tasks) > 1:
                task_id_combobox['values'] = load_task_ids()
                show_task_selection_dialog(ini_path, path_tasks, latest_task_id)
                return

        if latest_task_id:
            print(f"Найден последний ID задачи ({latest_task_id}) для пути {ini_path}. Применяем настройки.")
            # Версия уже однозначно определена выбранной директорией — фиксируем её,
            # чтобы on_task_selected не спрашивал версию повторно, даже если у задачи
            # есть несколько версий (директория и есть выбор версии).
            _forced_version = extract_rk_version_from_path(ini_path)
            # ВАЖНО: task_id_var.set() сам вызывает on_task_selected через trace.
            # Явный вызов нужен только если значение не изменилось (trace не сработает),
            # иначе настройки применятся дважды (и диалог выбора версии откроется 2 раза).
            if task_id_var.get().strip() == latest_task_id:
                on_task_selected(None)
            else:
                task_id_var.set(latest_task_id)
        else:
            print(f"Для пути {ini_path} сохраненных задач не найдено. Загружаем из INI-файлов.")
            task_id_var.set("") 
            load_wincash_params()
            on_check()
            # Папка без задач = дефолтная настройка версии — сохраняем текущие параметры INI
            save_default_ini_settings(ini_path)
    else:
        # Если обновление задачи не требуется, просто загружаем данные из INI
        load_wincash_params()
        on_check()
    # --- КОНЕЦ ЛОГИКИ ---
    
    task_id_combobox['values'] = load_task_ids()
    #task_id_combobox.current(0)  # Всегда показывать пустую строку первой при открытии

path_entry.bind("<<ComboboxSelected>>", apply_path) # Обновление после выбора пути из списка


def is_process_running(process_name):
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() == process_name.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def check_program_process():
    if is_process_running("refsrv.exe"):
        centered_info("Проверка", "Программа запущена.")
    else:
        centered_warning("Проверка", "Программа не найдена.")

# ======================= Удаление MIDBASE =======================
def get_task_data(task_id):
    """Получает данные задачи из JSON конфигурации"""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("tasks", {}).get(task_id)
    except Exception as e:
        centered_error("Ошибка", f"Не удалось прочитать конфигурацию:\n{e}")
        return None

def delete_midbase_files():
    selected_task_id = task_id_var.get().strip()
    if not selected_task_id:
        centered_warning("Внимание", "Сначала выберите задачу, для которой нужно удалить MIDBASE.")
        return

    # Получаем данные из JSON
    base_path = get_current_task_base_path(selected_task_id)

    if not base_path:
        centered_error("Ошибка", f"Задача {selected_task_id} не найдена.")
        return

    # Если есть в JSON - берём оттуда
    task_data = get_task_data(selected_task_id)
    midbase_path = task_data.get("midbase_path") if task_data else None

    # Если в JSON нет - строим путь автоматически
    if not midbase_path:
        parent_path = os.path.dirname(base_path)
        # Новый формат: {task_id}/MIDBASE
        new_format_path = os.path.normpath(os.path.join(parent_path, "MIDBASE"))
        # Старый формат: MIDBASE_{task_id}
        old_format_path = os.path.normpath(os.path.join(os.path.dirname(parent_path), f"MIDBASE_{selected_task_id}"))
        if os.path.isdir(new_format_path):
            midbase_path = new_format_path.replace("\\", "/")
        else:
            midbase_path = old_format_path.replace("\\", "/")

    if not os.path.isdir(midbase_path):
        centered_error("Ошибка", f"Папка MIDBASE не найдена:\n{midbase_path}")
        return

    # Для MIDBASE нет защищённых файлов - удаляем всё
    protected_files = []

    # Вызываем окно подтверждения с тремя флагами
    confirm_midbase_deletion(
        protected_files,
        midbase_path
    )

def confirm_midbase_deletion(protected_files, base_path):
    """Диалог очистки MIDBASE с тремя флагами."""
    win = tk.Toplevel(root)
    win.withdraw()
    win.title("Подтверждение очистки")

    if icon_path:
        win.iconbitmap(icon_path)

    win.transient(root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)

    msg = f"Вы действительно хотите очистить папку:\n{base_path}"
    tk.Label(frame, text=msg, justify="left").pack(padx=10, pady=(10, 5))

    # Флаги
    keep_work_udb_var = tk.BooleanVar(value=False)
    keep_archive_backup_var = tk.BooleanVar(value=False)
    do_backup_var = tk.BooleanVar(value=False)

    tk.Checkbutton(frame, text="Сохранить WORK.UDB", variable=keep_work_udb_var).pack(anchor="w", padx=12, pady=(0, 2))
    tk.Checkbutton(frame, text="Сохранить Archive, Backup и refsdata.udb", variable=keep_archive_backup_var).pack(anchor="w", padx=12, pady=(0, 2))
    tk.Checkbutton(frame, text="Создать резервную копию", variable=do_backup_var).pack(anchor="w", padx=12, pady=(0, 5))

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=5)

    def on_delete():
        win.destroy()
        keep_work_udb = keep_work_udb_var.get()
        keep_archive_backup = keep_archive_backup_var.get()
        do_backup = do_backup_var.get()

        protected = []
        if keep_work_udb:
            protected.append("WORK.UDB")
        if keep_archive_backup:
            protected.extend(["Archive", "Backup", "refsdata.udb"])

        callback_with_backup = partial(proceed_with_backup_and_deletion, base_path, protected)
        callback_without_backup = partial(proceed_with_deletion, protected, base_path, backup_path=None)

        if do_backup:
            callback_with_backup()
        else:
            callback_without_backup()

    tk.Button(btn_frame, text="Очистить", command=on_delete).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=win.destroy).pack(side="left", padx=5)

    _center_window(win)

    win.focus_force()
    win.deiconify()

def confirm_deletion_with_options(protected_files, base_path, callback_with_backup, callback_without_backup):
    win = tk.Toplevel(root)
    win.withdraw()
    win.title("Подтверждение очистки")

    if icon_path:
        win.iconbitmap(icon_path)

    win.transient(root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)

    msg = f"Вы действительно хотите очистить папку:\n{base_path}"
    if protected_files:
        msg += f"\n\nБудут оставлены: {', '.join(protected_files)}"

    tk.Label(frame, text=msg, justify="left").pack(padx=10, pady=(10, 5))

    do_backup_var = tk.BooleanVar(value=False)
    tk.Checkbutton(frame, text="Создать резервную копию", variable=do_backup_var).pack(anchor="w", padx=12, pady=(0, 5))

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=5)

    def on_delete():
        win.destroy()
        if do_backup_var.get():
            callback_with_backup()
        else:
            callback_without_backup()

    tk.Button(btn_frame, text="Очистить", command=on_delete).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=win.destroy).pack(side="left", padx=5)

    _center_window(win)

    win.focus_force()
    win.deiconify()

# ======================= Удаление base =======================
def delete_unwanted_files():
    selected_task_id = task_id_var.get().strip()
    if not selected_task_id:
        centered_warning("Внимание", "Сначала выберите задачу, для которой нужно очистить папку base.")
        return

    # Используем нашу новую функцию для получения правильного пути
    base_path = get_current_task_base_path(selected_task_id)

    if not base_path or not os.path.isdir(base_path):
        centered_error("Ошибка", f"Папка base для задачи {selected_task_id} не найдена:\n{base_path}")
        return

    # Список файлов и папок, которые НЕ должны быть удалены
    protected_files = [
        "drvlocalize", "workmods", "dealerpresets.udb",
        "ral.dat", "rk7.udb", "upgradedevices.abs", "upgradepresets.abs"
    ]

    # Создаем колбэки с уже определенным путем
    callback_with_backup = partial(proceed_with_backup_and_deletion, base_path, protected_files)
    callback_without_backup = partial(proceed_with_deletion, protected_files, base_path, backup_path=None)

    # Вызываем окно подтверждения
    confirm_deletion_with_options(
        protected_files,
        base_path,  # Передаем путь для отображения в сообщении
        callback_with_backup,
        callback_without_backup
    )


def proceed_with_backup_and_deletion(base_path, protected_files):
    copying_win = tk.Toplevel(root)
    copying_win.withdraw()
    copying_win.title("Подождите")

    if icon_path:
        copying_win.iconbitmap(icon_path)

    copying_win.transient(root)
    copying_win.grab_set()

    frame = tk.Frame(copying_win)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text="Создаётся резервная копия папки base...").pack(padx=15, pady=15)

    _center_window(copying_win)

    copying_win.deiconify()
    copying_win.update()

    def run():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(os.path.dirname(base_path), f"base_backup_{timestamp}")
        try:
            shutil.copytree(base_path, backup_path)
        except Exception as e:
            root.after(0, lambda: (copying_win.destroy(), centered_error("Ошибка", f"Не удалось создать резервную копию:\n{e}")))
            return

        root.after(0, lambda: (copying_win.destroy(), proceed_with_deletion(protected_files, base_path, backup_path)))

    threading.Thread(target=run, daemon=True).start()

def proceed_with_deletion(protected_files, base_path, backup_path=None):
    deleted_items = []

    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)

        if item in protected_files:
            continue

        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
                deleted_items.append(item)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
                deleted_items.append(item)
        except Exception as e:
            centered_error("Ошибка", f"Не удалось удалить: {item_path}\n{e}")

    if deleted_items:
        msg = f"Удалено: {', '.join(deleted_items)}"
        if backup_path:
            msg += f"\n\nРезервная копия создана:\n{backup_path}"
        centered_info("Удаление завершено", msg)
    else:
        centered_info("Удаление файлов и папок", "Нет элементов для удаления или все элементы защищены.")


# Максимальная ширина всплывающих окон: если текст в Label не влезает,
# он переносится на новую строку (wraplength), а не растягивает окно.
CENTERED_WINDOW_MAX_WIDTH = 500

def _wrap_labels(widget, wraplength):
    if isinstance(widget, tk.Label):
        widget.config(wraplength=wraplength)
    for child in widget.winfo_children():
        _wrap_labels(child, wraplength)

def _center_window(win, max_width=CENTERED_WINDOW_MAX_WIDTH, min_width=280):
    """Центрирует Toplevel-окно относительно root с ограничением максимальной ширины."""
    win.update_idletasks()
    w = win.winfo_reqwidth()
    if w > max_width:
        _wrap_labels(win, max_width - 40)
        win.update_idletasks()
        w = win.winfo_reqwidth()
    w = max(min(w, max_width), min_width)
    h = win.winfo_reqheight()
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")
    win.resizable(False, False)


def centered_info(title, message):
    """Центрированное информационное окно."""
    win = tk.Toplevel(root)
    win.withdraw()
    win.title(title)

    if icon_path:
        win.iconbitmap(icon_path)

    win.transient(root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=message, justify="left").pack(padx=15, pady=(15, 10))
    tk.Button(frame, text="OK", command=win.destroy, width=12).pack(pady=(0, 15))

    _center_window(win)

    win.focus_force()
    win.deiconify()


def centered_warning(title, message):
    """Центрированное окно предупреждения."""
    win = tk.Toplevel(root)
    win.withdraw()
    win.title(title)

    if icon_path:
        win.iconbitmap(icon_path)

    win.transient(root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=message, justify="left").pack(padx=15, pady=(15, 10))
    tk.Button(frame, text="OK", command=win.destroy, width=12).pack(pady=(0, 15))

    _center_window(win)

    win.focus_force()
    win.deiconify()


def centered_error(title, message):
    """Центрированное окно ошибки."""
    win = tk.Toplevel(root)
    win.withdraw()
    win.title(title)

    if icon_path:
        win.iconbitmap(icon_path)

    win.transient(root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=message, justify="left").pack(padx=15, pady=(15, 10))
    tk.Button(frame, text="OK", command=win.destroy, width=12).pack(pady=(0, 15))

    _center_window(win)

    win.focus_force()
    win.deiconify()


def centered_askyesno(title, message):
    """Центрированное окно с вопросом Да/Нет. Возвращает True/False."""
    result = [None]

    def on_yes():
        result[0] = True
        win.destroy()

    def on_no():
        result[0] = False
        win.destroy()

    win = tk.Toplevel(root)
    win.withdraw()
    win.title(title)

    if icon_path:
        win.iconbitmap(icon_path)

    win.transient(root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=message, justify="left").pack(padx=15, pady=(15, 10))

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=(0, 15))
    tk.Button(btn_frame, text="Да", command=on_yes, width=10).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Нет", command=on_no, width=10).pack(side="left", padx=5)

    _center_window(win)

    win.focus_force()
    win.deiconify()
    win.wait_window()
    return result[0]


def centered_askokcancel(title, message):
    """Центрированное окно с вопросом OK/Отмена. Возвращает True/False."""
    result = [None]

    def on_ok():
        result[0] = True
        win.destroy()

    def on_cancel():
        result[0] = False
        win.destroy()

    win = tk.Toplevel(root)
    win.withdraw()
    win.title(title)

    if icon_path:
        win.iconbitmap(icon_path)

    win.transient(root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=message, justify="left").pack(padx=15, pady=(15, 10))

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=(0, 15))
    tk.Button(btn_frame, text="OK", command=on_ok, width=10).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=on_cancel, width=10).pack(side="left", padx=5)

    _center_window(win)

    win.focus_force()
    win.deiconify()
    win.wait_window()
    return result[0]

# ======================= Запуск / рестарт Ref, Mid Srv =======================
def run_or_restart_process(exe_name):
    exe_path = os.path.join(ini_path, exe_name)
    if not os.path.isfile(exe_path):
        centered_error("Ошибка", f"Файл не найден:\n{exe_path}")
        return

    # ЗАвершение процесса
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and proc.info['name'].lower() == exe_name.lower():
            try:
                proc.terminate()
            except Exception:
                pass

    #Рестарт с параметром -desktop
    try:
        subprocess.Popen(f'start \"\" \"{exe_path}\" -desktop', shell=True)
    except Exception as e:
        centered_error("Ошибка запуска", str(e))

def start_refsrv_only():
    """Запускает refsrv.exe из текущей директории, закрывая только свой экземпляр."""
    exe_path = os.path.join(ini_path, "refsrv.exe")
    if not os.path.isfile(exe_path):
        centered_error("Ошибка", f"Файл не найден:\n{exe_path}")
        return

    ini_path_norm = os.path.normpath(ini_path).lower()

    # Закрываем только refsrv из текущей директории
    for proc, exe_dir in _get_process_by_name('refsrv.exe'):
        if exe_dir == ini_path_norm:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    time.sleep(0.5)

    # Запускаем новый экземпляр
    try:
        subprocess.Popen(f'start "" "{exe_path}" -desktop', shell=True)
    except Exception as e:
        centered_error("Ошибка запуска", str(e))

def start_rk7man_only():
    """Запускает rk7man.bat из текущей директории, закрывая только свой экземпляр."""
    ini_path_norm = os.path.normpath(ini_path).lower()

    # Закрываем только rk7man из текущей директории
    for proc, exe_dir in _get_process_by_name('rk7man.exe'):
        if exe_dir == ini_path_norm:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    time.sleep(0.5)

    bat_path = os.path.join(ini_path, "rk7man.bat")
    if not os.path.isfile(bat_path):
        centered_error("Ошибка", f"Файл не найден:\n{bat_path}")
        return
    try:
        subprocess.Popen(f'start "" cmd /c "{bat_path}"', shell=True, cwd=ini_path)
    except Exception as e:
        centered_error("Ошибка запуска", str(e))

# ======================= Запуск rk7man.bat =======================
def run_rk7man():
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and proc.info['name'].lower() == "rk7man.exe":
            try:
                proc.terminate()
            except Exception:
                pass

    time.sleep(1.5)

    bat_path = os.path.join(ini_path, "rk7man.bat")
    if not os.path.isfile(bat_path):
        centered_error("Ошибка", f"Файл не найден:\n{bat_path}")
        return
    try:
        os.startfile(bat_path)
    except Exception as e:
        centered_error("Ошибка запуска", str(e))

# ======================= Запуск wincash.bat =======================
def run_wincash_bat():
    def run_bat():
        bat_path = os.path.join(ini_path, "wincash.bat")
        
        # Проверка наличия файла
        if not os.path.isfile(bat_path):
            centered_error("Ошибка", f"Файл не найден:\n{bat_path}")
            return
        
        try:
            # Запуск .bat файла с выводом ошибок
            print(f"[DEBUG] Попытка запуска: {bat_path}")
            result = subprocess.run([bat_path], capture_output=True, text=True, shell=True, cwd=ini_path)

            # Проверка результата
            if result.returncode != 0:
                # Если код завершения не 0, выводим ошибку
                print(f"[ERROR] Ошибка при выполнении bat файла: {result.stderr}")
                centered_error("Ошибка запуска", f"Ошибка при запуске {bat_path}:\n{result.stderr}")
            else:
                # Если всё прошло успешно, выводим результат
                print(f"[INFO] bat файл выполнен успешно:\n{result.stdout}")
        except Exception as e:
            # Обработка исключений
            centered_error("Ошибка запуска", f"Не удалось запустить {bat_path}:\n{str(e)}")

    # Запуск функции в отдельном потоке
    threading.Thread(target=run_bat, daemon=True).start()

# DOSCASH.EXE нужно закрыть перед запуском если есть

def run_refsrv_and_rk7man():
    ini_path_norm = os.path.normpath(ini_path).lower()
    current_port = get_port_value()

    # Проверяем, занят ли текущий порт другим refsrv (не из текущей директории)
    if current_port:
        used_ports = _get_used_ports()
        if int(current_port) in used_ports:
            # Проверяем, есть ли refsrv на этом порту из другой директории
            conflict = False
            for proc, exe_dir in _get_process_by_name('refsrv.exe'):
                if exe_dir != ini_path_norm:
                    ports = _get_process_listening_ports(proc.pid)
                    if int(current_port) in ports:
                        conflict = True
                        break

            if conflict:
                # Пробуем текущий +1, +2, +3...
                new_port = int(current_port) + 1
                while new_port in used_ports and new_port < int(current_port) + 100:
                    new_port += 1

                if new_port < int(current_port) + 100:
                    server_name = get_refserver_name()
                    if set_port_rk7srv(ini_path, str(new_port)):
                        set_port_rk7man(ini_path, server_name, str(new_port))
                        print(f"[PORT] Смена порта: {current_port} -> {new_port}")
                else:
                    centered_error("Ошибка", "Не удалось найти свободный порт")

    start_refsrv_only()
    time.sleep(1.5)
    start_rk7man_only()

def start_midserv_only():
    """Запускает midserv.exe из текущей директории, закрывая только свой экземпляр."""
    exe_path = os.path.join(ini_path, "midserv.exe")
    if not os.path.isfile(exe_path):
        centered_error("Ошибка", f"Файл не найден:\n{exe_path}")
        return

    ini_path_norm = os.path.normpath(ini_path).lower()

    # Закрываем только midserv из текущей директории
    for proc, exe_dir in _get_process_by_name('midserv.exe'):
        if exe_dir == ini_path_norm:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    time.sleep(0.5)

    try:
        subprocess.Popen(f'start "" "{exe_path}" -desktop', shell=True)
    except Exception as e:
        centered_error("Ошибка запуска", str(e))

def start_wincash_only():
    """Запускает wincash.bat из текущей директории, закрывая только свой экземпляр."""
    ini_path_norm = os.path.normpath(ini_path).lower()

    # Закрываем только doscash из текущей директории
    for proc, exe_dir in _get_process_by_name('doscash.exe'):
        if exe_dir == ini_path_norm:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    time.sleep(0.5)

    bat_path = os.path.join(ini_path, "wincash.bat")
    if not os.path.isfile(bat_path):
        centered_error("Ошибка", f"Файл не найден:\n{bat_path}")
        return
    try:
        subprocess.run([bat_path], shell=True, cwd=ini_path)
    except Exception as e:
        centered_error("Ошибка запуска", str(e))


# ======================= Запуск MidServ + WinCash =======================
def run_midserv_and_wincash():
    start_midserv_only()
    time.sleep(1.5)
    start_wincash_only()

# ======================= Закрыть процес =======================
def kill_midserv_process():
    # Проходим по всем процессам
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == "midserv.exe":
                proc.terminate()  # Завершаем процесс
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def _get_used_ports() -> set[int]:
    """Возвращает множество портов, которые уже используются (LISTEN)."""
    used = set()
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr and conn.status == 'LISTEN':
                used.add(conn.laddr.port)
    except (psutil.AccessDenied, OSError):
        pass
    return used


def _find_free_port(start_port: int = 6000, max_attempts: int = 100) -> int | None:
    """Находит первый свободный порт начиная с start_port."""
    used = _get_used_ports()
    for port in range(start_port, start_port + max_attempts):
        if port not in used:
            return port
    return None


def _get_process_listening_ports(pid: int) -> list[int]:
    """Возвращает список портов, которые слушает процесс с данным PID."""
    ports = []
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.pid == pid and conn.laddr and conn.status == 'LISTEN':
                ports.append(conn.laddr.port)
    except (psutil.AccessDenied, OSError):
        pass
    return ports


def _read_port_from_ini(ini_dir: str) -> str | None:
    """Читает PORT из [TCPSOC] rk7srv.INI в указанной директории."""
    ini_file = os.path.join(ini_dir, "rk7srv.INI")
    if not os.path.isfile(ini_file):
        return None
    try:
        try:
            with open(ini_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(ini_file, 'r', encoding='cp1251') as f:
                lines = f.readlines()
        in_tcpsoc = False
        for line in lines:
            stripped = line.strip()
            if re.match(r'^\[TCPSOC\]', stripped, re.IGNORECASE):
                in_tcpsoc = True
                continue
            if in_tcpsoc:
                if stripped.startswith('['):
                    break
                m = re.match(r'^\s*PORT\s*=\s*(\d+)', stripped, re.IGNORECASE)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def _get_process_by_name(name: str) -> list[tuple[psutil.Process, str]]:
    """Возвращает список (process, exe_dir) для всех процессов с данным именем."""
    results = []
    try:
        result = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and name.lower() in result.stdout.lower():
            for line in result.stdout.strip().split('\n'):
                if name.lower() not in line.lower():
                    continue
                try:
                    parts = line.split(',')
                    pid_str = parts[1].strip('"')
                    pid = int(pid_str)
                    proc = psutil.Process(pid)
                    exe_dir = os.path.normpath(os.path.dirname(proc.exe())).lower()
                    results.append((proc, exe_dir))
                except (ValueError, IndexError, psutil.NoSuchProcess):
                    pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info.get('name', '').lower() != name.lower():
            continue
        try:
            exe_dir = os.path.normpath(os.path.dirname(proc.exe())).lower()
            if not any(p.pid == proc.pid for p, _ in results):
                results.append((proc, exe_dir))
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
    return results


def _get_task_label_for_dir(exe_dir: str) -> str | None:
    """Определяет ID задачи и версию RK для процесса, запущенного из exe_dir
    (на основе rk7srv.INI в этой папке). Возвращает строку вида
    'задача 197034, версия 7.0.0.1234' или None, если не удалось определить."""
    if not exe_dir:
        return None
    ini_file = os.path.join(exe_dir, "rk7srv.INI")
    task_id = extract_task_id_from_rk7srv_ini(ini_file)
    version = extract_rk_version_from_path(exe_dir)
    if not task_id and not version:
        return None
    parts = []
    if task_id:
        parts.append(f"задача {task_id}")
    if version:
        parts.append(f"версия {version}")
    return ", ".join(parts)


def _get_port_info(ports: list[int]) -> str:
    """Возвращает строку с информацией о том, какие процессы слушают на данных портах."""
    if not ports:
        return ""
    info_parts = []
    for port in ports:
        proc_names = set()
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port and conn.status == 'LISTEN' and conn.pid:
                    try:
                        p = psutil.Process(conn.pid)
                        proc_names.add(f"{p.name()} (PID {conn.pid})")
                    except psutil.NoSuchProcess:
                        pass
        except (psutil.AccessDenied, OSError):
            pass
        if proc_names:
            info_parts.append(f"  {port}: {', '.join(proc_names)}")
        else:
            info_parts.append(f"  {port}: (неизвестно)")
    return "\n".join(info_parts)


def _get_rk7man_port_info(pid: int) -> str:
    """Возвращает информацию о портах, к которым подключён процесс."""
    connected = []
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.pid == pid and conn.status == 'ESTABLISHED' and conn.raddr:
                port = conn.raddr.port
                proc_info = ""
                try:
                    for c in psutil.net_connections(kind='inet'):
                        if c.laddr.port == port and c.status == 'LISTEN' and c.pid:
                            p = psutil.Process(c.pid)
                            proc_info = f" ({p.name()} PID {c.pid})"
                            break
                except (psutil.AccessDenied, OSError, psutil.NoSuchProcess):
                    pass
                connected.append(f"  {port}: подключён{proc_info}")
    except (psutil.AccessDenied, OSError):
        pass
    return "\n".join(connected) if connected else "  (нет активных подключений)"


def kill_refsrv_and_rk7man():
    """Комбинированное закрытие refsrv + rk7man: если оба из текущей директории —
    сразу закрывает, иначе показывает окно с информацией о всех процессах."""
    ini_path_norm = os.path.normpath(ini_path).lower()

    refsrv_procs = _get_process_by_name('refsrv.exe')
    rk7man_procs = _get_process_by_name('rk7man.exe')

    refsrv_same = [p for p, d in refsrv_procs if d == ini_path_norm]
    refsrv_other = [(p, d) for p, d in refsrv_procs if d != ini_path_norm]
    rk7man_same = [p for p, d in rk7man_procs if d == ini_path_norm]
    rk7man_other = [(p, d) for p, d in rk7man_procs if d != ini_path_norm]

    # Если оба из той же директории — сразу закрываем без запроса
    if refsrv_same and rk7man_same:
        refsrv_same[0].terminate()
        rk7man_same[0].terminate()
        return

    # Если хотя бы один из другой директории или не запущен — показываем информацию
    msg_lines = []

    # Собираем процессы для закрытия
    to_close = {'refsrv': refsrv_same + [p for p, _ in refsrv_other],
                'rk7man': rk7man_same + [p for p, _ in rk7man_other]}

    if refsrv_same:
        msg_lines.append("✓ refsrv.exe (текущая директория)")
    elif refsrv_other:
        proc, exe_dir = refsrv_other[0]
        task_label = _get_task_label_for_dir(exe_dir)
        task_suffix = f"\n  {task_label}" if task_label else ""
        ports = _get_process_listening_ports(proc.pid)
        if ports:
            port_info = _get_port_info(ports)
            msg_lines.append(f"⚠ refsrv.exe ({exe_dir}):\n{port_info}{task_suffix}")
        else:
            ini_port = _read_port_from_ini(exe_dir)
            msg_lines.append(f"⚠ refsrv.exe ({exe_dir})\n  Порт из INI: {ini_port or 'не найден'}{task_suffix}")
    else:
        msg_lines.append("✗ refsrv.exe (не запущен)")

    msg_lines.append("")

    if rk7man_same:
        msg_lines.append("✓ rk7man.exe (текущая директория)")
    elif rk7man_other:
        proc, exe_dir = rk7man_other[0]
        port_info = _get_rk7man_port_info(proc.pid)
        msg_lines.append(f"⚠ rk7man.exe ({exe_dir}):\n{port_info}")
    else:
        msg_lines.append("✗ rk7man.exe (не запущен)")

    msg_lines.append("")
    msg_lines.append("Закрыть запущенные процессы?")

    answer = centered_askyesno("Закрыть refsrv + rk7man", "\n".join(msg_lines))
    if not answer:
        return

    # Закрываем только запущенные процессы
    for proc in to_close['refsrv']:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    for proc in to_close['rk7man']:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def kill_refsrv_process():
    """Закрывает refsrv.exe: если запущен — спрашивает и закрывает,
    если не запущен из текущего ini_path — показывает порт и предлагает закрыть."""
    ini_path_norm = os.path.normpath(ini_path).lower()
    procs = _get_process_by_name('refsrv.exe')

    same_dir = [(p, d) for p, d in procs if d == ini_path_norm]
    other_dir = [(p, d) for p, d in procs if d != ini_path_norm]

    if same_dir:
        same_dir[0][0].kill()
        return

    if other_dir:
        proc, exe_dir = other_dir[0]
        task_label = _get_task_label_for_dir(exe_dir)
        task_suffix = f"\n{task_label}" if task_label else ""
        ports = _get_process_listening_ports(proc.pid)
        if ports:
            port_info = _get_port_info(ports)
            msg = f"refsrv.exe запущен:\n{port_info}\n({exe_dir}){task_suffix}\n\nЗакрыть его?"
        else:
            ini_port = _read_port_from_ini(exe_dir)
            msg = f"refsrv.exe запущен ({exe_dir})\nПорт из INI: {ini_port or 'не найден'}{task_suffix}\nЗакрыть его?"
        answer = centered_askyesno("Закрыть refsrv.exe", msg)
        if answer:
            proc.kill()
        return

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == "refsrv.exe":
                proc.kill()
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def kill_rk7man_process():
    """Закрывает rk7man.exe: если запущен — спрашивает и закрывает,
    если не запущен из текущего ini_path — показывает, к какому порту подключён."""
    ini_path_norm = os.path.normpath(ini_path).lower()
    procs = _get_process_by_name('rk7man.exe')

    same_dir = [(p, d) for p, d in procs if d == ini_path_norm]
    other_dir = [(p, d) for p, d in procs if d != ini_path_norm]

    if same_dir:
        same_dir[0][0].kill()
        return

    if other_dir:
        proc, exe_dir = other_dir[0]
        port_info = _get_rk7man_port_info(proc.pid)
        msg = f"rk7man.exe запущен:\n{port_info}\n({exe_dir})\n\nЗакрыть его?"
        answer = centered_askyesno("Закрыть rk7man.exe", msg)
        if answer:
            proc.kill()
        return

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == "rk7man.exe":
                proc.kill()
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if other_dir:
        proc, exe_dir = other_dir[0]
        connected_ports = []
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.pid == proc.pid and conn.status == 'ESTABLISHED' and conn.raddr:
                    connected_ports.append(str(conn.raddr.port))
        except (psutil.AccessDenied, OSError):
            pass

        if connected_ports:
            port_str = ", ".join(connected_ports)
            msg = f"rk7man.exe подключён к порту: {port_str}\n({exe_dir})\nЗакрыть его?"
        else:
            msg = f"rk7man.exe запущен ({exe_dir})\nЗакрыть его?"
        answer = centered_askyesno("Закрыть rk7man.exe", msg)
        if answer:
            proc.terminate()
        return

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == "rk7man.exe":
                proc.terminate()
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def kill_doscash_process():
    # Проходим по всем процессам
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Если имя процесса совпадает с 'DOSCASH.EXE', завершаем его
            if proc.info['name'].lower() == "doscash.exe":
                proc.terminate()  # Завершаем процесс
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


# ======================= Запуск / запуск+группы =======================
launch_frame = tk.LabelFrame(settings_tab, text="Запуск")
launch_frame.pack(padx=10, pady=(10, 10), fill="x")

# 3 колонки в launch_frame
col1 = tk.Frame(launch_frame)
col2 = tk.Frame(launch_frame)
col3 = tk.Frame(launch_frame)

col1.grid(row=0, column=0, sticky="nw", padx=5, pady=5)
col2.grid(row=0, column=1, sticky="nw", padx=5, pady=5)
col3.grid(row=0, column=2, sticky="nw", padx=5, pady=5)

# Строка 0: две комбинированные кнопки
# Создаем фрейм для Refsrv + RK7man
frame_refsrv_rk7man = tk.Frame(col1)
frame_refsrv_rk7man.pack(anchor="w", pady=(0, 4))

# Онлайн лог с 200 строками
def open_log_file(log_name):
    log_path = os.path.join(ini_path, log_name)
    cmd = f'start powershell -NoExit -Command "Get-Content \'{log_path}\' -Tail 200 -Wait"'
    subprocess.Popen(cmd, shell=True)

def open_multiple_logs(*log_names):
    log_paths = [os.path.join(ini_path, name) for name in log_names]
    jobs = [f"Start-job {{ Get-Content -Path '{p}' -Tail 200 -Wait }}" for p in log_paths]
    cmd = " ; ".join(jobs) + "; Receive-Job -Wait -AutoremoveJob *"
    full_cmd = f'start powershell -NoExit -Command \"{cmd}\"'
    subprocess.Popen(full_cmd, shell=True)

# Кнопка Refsrv + RK7man
tk.Button(frame_refsrv_rk7man, text="Refsrv + RK7man", command=run_refsrv_and_rk7man, width=15)\
    .pack(side="left")

tk.Button(frame_refsrv_rk7man, text="📄", command=lambda: open_multiple_logs("refsrv.stk", "rk7man.stk"), width=3)\
    .pack(side="left")


# Кнопка Close для Refsrv + RK7man
tk.Button(frame_refsrv_rk7man, text="❌", command=kill_refsrv_and_rk7man, width=2)\
    .pack(side="left")

# Создаем фрейм для MidServ + WinCash
frame_midserv_wincash = tk.Frame(col2)
frame_midserv_wincash.pack(anchor="w", pady=(0, 4))

# Кнопка MidServ + WinCash
tk.Button(frame_midserv_wincash, text="MidServ + WinCash", command=run_midserv_and_wincash, width=15)\
    .pack(side="left")

tk.Button(frame_midserv_wincash, text="📄", command=lambda: open_multiple_logs("midsrv.stk", "cash.stk"), width=3)\
    .pack(side="left")

# Кнопка Close для MidServ + WinCash
tk.Button(frame_midserv_wincash, text="❌", command=lambda: kill_midserv_process() or kill_doscash_process(), width=2)\
    .pack(side="left")

# Строка 1: одиночные кнопки
# Создаем фрейм для Refsrv
frame_refsrv = tk.Frame(col1)
frame_refsrv.pack(anchor="w", pady=2)

# Кнопка Refsrv
tk.Button(frame_refsrv, text="Refsrv", command=start_refsrv_only, width=15)\
    .pack(side="left")

tk.Button(frame_refsrv, text="📄", command=partial(open_log_file, "refsrv.stk"), width=3)\
    .pack(side="left")

# Кнопка Close для Refsrv
tk.Button(frame_refsrv, text="❌", command=kill_refsrv_process, width=2)\
    .pack(side="left")

# Создаем фрейм для RK7man
frame_rk7man = tk.Frame(col1)
frame_rk7man.pack(anchor="w", pady=2)

# Кнопка RK7man
tk.Button(frame_rk7man, text="RK7man", command=start_rk7man_only, width=15)\
    .pack(side="left")

tk.Button(frame_rk7man, text="📄", command=partial(open_log_file, "rk7man.stk"), width=3)\
    .pack(side="left")

# Кнопка Close для RK7man
tk.Button(frame_rk7man, text="❌", command=kill_rk7man_process, width=2)\
    .pack(side="left")

# Строка 2: одиночные кнопки
# Создаем фрейм для MidServ
frame_midserv = tk.Frame(col2)  
frame_midserv.pack(anchor="w", pady=2)  # Размещаем фрейм с выравниванием по левой стороне

# Кнопка MidServ
tk.Button(frame_midserv, text="MidServ", command=start_midserv_only, width=15)\
    .pack(side="left")  # Кнопка расположена слева в фрейме

tk.Button(frame_midserv, text="📄", command=partial(open_log_file, "midsrv.stk"), width=3)\
    .pack(side="left")

# Кнопка Close для MidServ
tk.Button(frame_midserv, text="❌", command=kill_midserv_process, width=2)\
    .pack(side="left")  # Кнопка расположена справа в том же фрейме

# Создаем фрейм для WinCash
frame_win_cash = tk.Frame(col2)  
frame_win_cash.pack(anchor="w", pady=2)  # Размещаем фрейм с выравниванием по левой стороне

# Кнопка WinCash
tk.Button(frame_win_cash, text="WinCash", command=start_wincash_only, width=15)\
    .pack(side="left")  # Кнопка расположена слева в фрейме

tk.Button(frame_win_cash, text="📄", command=partial(open_log_file, "cash.stk"), width=3)\
    .pack(side="left")

# Кнопка Close для WinCash
tk.Button(frame_win_cash, text="❌", command=kill_doscash_process, width=2)\
    .pack(side="left")  # Кнопка расположена справа в том же фрейме


# Переключатели
usesql_var = tk.IntVar(value=int(get_usesql_value()))
usedbsync_var = tk.IntVar(value=int(detect_consensus_value()))
port_var = tk.StringVar(value=get_port_value())

flags_lf = tk.LabelFrame(settings_tab, text="Параметры INI")
flags_lf.pack(padx=10, pady=(0, 5), fill="x")

flags_frame = tk.Frame(flags_lf)
flags_frame.pack(padx=5, pady=5, fill="x")

usesql_cb = tk.Checkbutton(
    flags_frame,
    variable=usesql_var,
    text="UseSQL",
    command=toggle_usesql,
    anchor="w"
)
usesql_cb.grid(row=0, column=0, sticky="w", padx=(0, 10))

usedbsync_cb = tk.Checkbutton(
    flags_frame,
    variable=usedbsync_var,
    text="UseDBSync",
    command=toggle_usedbsync,
    anchor="w"
)
usedbsync_cb.grid(row=0, column=1, sticky="w", padx=(0, 10))

# Поле ввода порта
port_inner = tk.Frame(flags_frame)
port_inner.grid(row=0, column=2, sticky="w", padx=(0, 3))

tk.Label(port_inner, text="Port:").pack(side="left")
port_entry = tk.Entry(port_inner, textvariable=port_var, width=4)
port_entry.pack(side="left", padx=(3, 3))

def adjust_port(delta):
    port = port_var.get().strip()
    if not port.isdigit():
        centered_warning("Порт", "Введите корректный номер порта (только цифры)")
        return
    new_port = max(1, min(65535, int(port) + delta))
    port = str(new_port)
    port_var.set(port)
    apply_port(ini_path, port)
    # Сохраняем в ini_settings задачи
    task_id = task_id_var.get().strip()
    if task_id:
        data = load_data()
        if task_id in data.get("tasks", {}):
            if "ini_settings" not in data["tasks"][task_id]:
                data["tasks"][task_id]["ini_settings"] = {}
            data["tasks"][task_id]["ini_settings"]["Port"] = port
            save_data(data)
            print(f"[PORT] Сохранён порт {port} для задачи {task_id}")

port_spin_frame = tk.Frame(port_inner)
port_spin_frame.pack(side="left")

tk.Button(port_spin_frame, text="▲", width=1, font=("Arial", 4),
          command=partial(adjust_port, 1)).pack(side="top")
tk.Button(port_spin_frame, text="▼", width=1, font=("Arial", 4),
          command=partial(adjust_port, -1)).pack(side="top")

upgrade_anytime_btn = tk.Button(
    flags_frame,
    text="UpgradeAnyTime",
    command=upgrade_anytime_refsrv,
    anchor="w"
)
upgrade_anytime_btn.grid(row=0, column=3, sticky="w", padx=(7, 0))

flags_frame.grid_columnconfigure(0, weight=0)
flags_frame.grid_columnconfigure(1, weight=0)
flags_frame.grid_columnconfigure(2, weight=0)
flags_frame.grid_columnconfigure(3, weight=1)

# ======================= Параметры из wincash.ini =======================
station_var = tk.StringVar()
server_var = tk.StringVar()

def load_wincash_params():
    wincash_path = os.path.join(ini_path, "wincash.ini")
    if not os.path.isfile(wincash_path):
        return
    try:
        with open(wincash_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
    except UnicodeDecodeError:
        with open(wincash_path, 'r', encoding='cp1251') as file:
            lines = file.readlines()

    for line in lines:
        if line.strip().lower().startswith("station="):
            station_var.set(line.strip().split("=", 1)[-1])
        elif line.strip().lower().startswith("server ="):
            server_var.set(line.strip().split("=", 1)[-1])
    task_id_combobox["values"] = load_task_ids()
    #task_id_combobox.current(0)


def save_wincash_params():
    wincash_path = os.path.join(ini_path, "wincash.ini")
    rkeeper_path = os.path.join(ini_path, "RKEEPER.INI")
    server_value = server_var.get()
    
    # --- Обновление wincash.ini ---
    if os.path.isfile(wincash_path):
        try:
            with open(wincash_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            with open(wincash_path, 'r', encoding='cp1251') as file:
                lines = file.readlines()

        new_lines = []
        for line in lines:
            if line.strip().lower().startswith("station="):
                val = station_var.get().strip()
                new_lines.append(f"STATION={val}\n" if val else line)
            elif line.strip().lower().startswith("server ="):
                val = server_var.get().strip()
                new_lines.append(f"Server ={val}\n" if val else line)
            else:
                new_lines.append(line)

        try:
            with open(wincash_path, 'w', encoding='cp1251') as file:
                file.writelines(new_lines)
        except Exception as e:
            centered_error("Ошибка", f"Не удалось сохранить wincash.ini:\n{e}")
    
    # --- Обновление RKEEPER.INI (Client = ...) ---
    if os.path.isfile(rkeeper_path):
        try:
            with open(rkeeper_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            with open(rkeeper_path, 'r', encoding='cp1251') as file:
                lines = file.readlines()

        new_rk_lines = []
        client_updated = False
        for line in lines:
            if re.match(r"^\s*Client\s*=", line, re.IGNORECASE):
                new_rk_lines.append(f"Client = {server_value}\n")
                client_updated = True
            else:
                new_rk_lines.append(line)

        if not client_updated:
            new_rk_lines.append(f"\nClient = {server_value}\n")

        try:
            with open(rkeeper_path, 'w', encoding='cp1251') as file:
                file.writelines(new_rk_lines)
        except Exception as e:
            centered_error("Ошибка", f"Не удалось сохранить RKEEPER.INI:\n{e}")

def apply_network_ids():
    task_id = task_id_var.get().strip()

    if not task_id:
        centered_warning("Предупреждение", "Сначала выберите или сохраните задачу!")
        return

    apply_network_ids_silent()
    centered_info("Успех", f"Данные сохранены для задачи {task_id}")

def apply_network_ids_silent():
    """Сохраняет Station и Server в JSON без показа messagebox (для фонового сохранения при смене задачи)."""
    task_id = task_id_var.get().strip()
    apply_network_ids_silent_for_task(task_id)

def apply_network_ids_silent_for_task(task_id):
    """Сохраняет Station и Server в JSON для указанной задачи (без messagebox)."""
    if not task_id:
        return

    station_value = station_var.get().strip()
    server_value = server_var.get().strip()

    data = load_data()
    tasks = data.get("tasks", {})

    if task_id not in tasks:
        return

    task_data = tasks[task_id]

    # Обновляем ini_settings внутри основной задачи
    if "ini_settings" not in task_data:
        task_data["ini_settings"] = {}

    task_data["ini_settings"]["Station"] = station_value
    task_data["ini_settings"]["Server"] = server_value

    # Если у задачи есть версии - обновляем только АКТИВНУЮ версию (по ini_path)
    versions = task_data.get("versions", {})
    if versions:
        active_ini_path = task_data.get("ini_path", "")
        for _, version_data in versions.items():
            if version_data.get("ini_path") == active_ini_path:
                # Нашли активную версию - обновляем её
                if "ini_settings" not in version_data:
                    version_data["ini_settings"] = {}
                version_data["ini_settings"]["Station"] = station_value
                version_data["ini_settings"]["Server"] = server_value
                break  # Нашли активную версию, выходим

    data["tasks"] = tasks
    save_data(data)

    # Дополнительно применяем в реальные ini-файлы
    save_wincash_params()

def apply_ini_flags_silent_for_task(task_id):
    """Сохраняет UseSQL и UseDBSync в JSON для указанной задачи (при смене задачи)."""
    if not task_id:
        return

    data = load_data()
    tasks = data.get("tasks", {})

    if task_id not in tasks:
        return

    task_data = tasks[task_id]
    if "ini_settings" not in task_data:
        task_data["ini_settings"] = {}

    # UseSQL
    task_data["ini_settings"]["UseSQL"] = "1" if usesql_var.get() else "0"

    # UseDBSync — хранится пофайлово, проходим по реально существующим файлам
    if "UseDBSync" not in task_data["ini_settings"]:
        task_data["ini_settings"]["UseDBSync"] = {}
    usedbsync_value = "1" if usedbsync_var.get() else "0"
    for filename in FILES:
        full_path = os.path.join(ini_path, filename)
        if os.path.exists(full_path):
            task_data["ini_settings"]["UseDBSync"][filename] = usedbsync_value

    # Если у задачи есть версии - обновляем только АКТИВНУЮ версию
    versions = task_data.get("versions", {})
    if versions:
        active_ini_path = task_data.get("ini_path", "")
        for _, version_data in versions.items():
            if version_data.get("ini_path") == active_ini_path:
                if "ini_settings" not in version_data:
                    version_data["ini_settings"] = {}
                version_data["ini_settings"]["UseSQL"] = task_data["ini_settings"]["UseSQL"]
                version_data["ini_settings"]["UseDBSync"] = task_data["ini_settings"]["UseDBSync"]
                break

    data["tasks"] = tasks
    save_data(data)

# === UI ===
info_frame = tk.LabelFrame(settings_tab, text="Сетевые ID")
info_frame.pack(padx=10, pady=(5, 10), fill="x", ipadx=2, ipady=2)

tk.Label(info_frame, text="MID:").grid(row=0, column=0, sticky="w", padx=(5, 0), pady=3)
tk.Entry(info_frame, textvariable=server_var).grid(row=0, column=1, sticky="ew", padx=5, pady=3)

tk.Label(info_frame, text="CASH:").grid(row=1, column=0, sticky="w", padx=(5, 0), pady=3)
tk.Entry(info_frame, textvariable=station_var).grid(row=1, column=1, sticky="ew", padx=5, pady=3)

apply_btn = tk.Button(info_frame, text="Применить", command=apply_network_ids)
apply_btn.grid(row=0, column=2, rowspan=2, sticky="ns", padx=(8, 5), pady=5)

info_frame.grid_columnconfigure(1, weight=1)
info_frame.grid_columnconfigure(2, minsize=90)

# Автосохранение при любом изменении (если хотите оставить)
station_var.trace_add("write", lambda *args: save_wincash_params())
server_var.trace_add("write", lambda *args: save_wincash_params())



# Автозагрузка значений при старте
load_wincash_params()

# Подсказка при наведении на кнопку "Проверить файлы"
def create_tooltip(widget, text):
    tooltip = None

    def on_enter(event):
        nonlocal tooltip
        x = widget.winfo_rootx() + widget.winfo_width() + 10
        y = widget.winfo_rooty()
        tooltip = tk.Toplevel(widget)
        tooltip.overrideredirect(True)
        tooltip.geometry(f"+{x}+{y}")
        label = tk.Label(tooltip, text=text, bg="lightyellow", relief="solid", borderwidth=1, justify="left", padx=5, pady=3)
        label.pack()

    def on_leave(event):
        nonlocal tooltip
        if tooltip:
            tooltip.destroy()
            tooltip = None

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)

def copy_missing_ini_files():
    bin_win_path = ini_path
    bin_win_ini = os.path.join(bin_win_path, "ini")
    missing = [f for f in FILES if not os.path.isfile(os.path.join(bin_win_path, f))]
    copied = []
    for f in missing:
        source = os.path.join(bin_win_ini, f)
        target = os.path.join(bin_win_path, f)
        if os.path.isfile(source):
            try:
                shutil.copy2(source, target)
                copied.append(f)
            except Exception as e:
                centered_error("Ошибка", f"Не удалось скопировать {f}:\n{e}")
    if copied:
        centered_info("Файлы скопированы", f"Скопированы из bin\\win\\ini:\n{', '.join(copied)}")
    elif not missing:
        centered_info("Все файлы на месте", "Все необходимые INI-файлы уже присутствуют.")
    else:
        centered_warning("Нет файлов", "Отсутствующие файлы не найдены даже в bin\\win\\ini.")

def on_check_with_message():
    found, missing = check_files()

    if missing:  # не исключаем rk7man.ini
        if centered_askyesno("Внимание", f"Файлы не найдены: {', '.join(missing)}\nДобавить из папки ini?"):
            copy_missing_ini_files()
            on_check()
            update_ini_info_by_priority()
    else:
        centered_info("Успех", "Все необходимые файлы найдены.")

def show_product_folders():
    product_root = find_product_root(path_var.get())
    if not product_root:
        centered_warning("Ошибка", "Корневая папка продукта не определена.")
        return
    
    try:
        items = os.listdir(product_root)
        folders = [name for name in items if os.path.isdir(os.path.join(product_root, name))]
        if folders:
            centered_info("Папки в корне продукта", "\n".join(folders))
        else:
            centered_info("Папки в корне продукта", "Папки не найдены.")
    except Exception as e:
        centered_error("Ошибка", f"Не удалось получить список папок:\n{e}")

# ======================= Панель с кнопками "Проверить файлы", "Показать папки" и "Clear Base" =======================
task_actions_lf = tk.LabelFrame(settings_tab, text="Управление задачей")
task_actions_lf.pack(padx=10, pady=(0, 10), fill="x")

check_folder_frame = tk.Frame(task_actions_lf)
check_folder_frame.pack(padx=5, pady=5, anchor="w", fill="x")

# Первый ряд: "Открыть задачу в SD", "Clear MIDBASE", "Clear Base"
check_btn = tk.Button(check_folder_frame, text="Открыть задачу в SD", command=open_task_in_sd)
check_btn.grid(row=0, column=0, padx=5, sticky="ew")

show_folders_btn = tk.Button(check_folder_frame, text="Очистить MIDBASE", command=delete_midbase_files)
show_folders_btn.grid(row=0, column=1, padx=5, sticky="ew")

clear_base_btn = tk.Button(check_folder_frame, text="Очистить Base", command=delete_unwanted_files)
clear_base_btn.grid(row=0, column=2, padx=5, sticky="ew")

# Второй ряд: "Удалить задачу" (под "Проверить файлы")
delete_task_btn = tk.Button(check_folder_frame, text="Удалить задачу", command=delete_task)
delete_task_btn.grid(row=1, column=0, padx=5, sticky="ew", pady=(5, 0))

# Кнопка "Сменить версию RK" (рядом с "Удалить задачу")
change_version_btn = tk.Button(check_folder_frame, text="Сменить версию RK", command=change_rk_version)
change_version_btn.grid(row=1, column=1, padx=5, sticky="ew", pady=(5, 0))

# Кнопка "Cloud RK7man" (экспериментальная, под "Очистить Base")
cloud_rk7man_btn = tk.Button(check_folder_frame, text="Cloud RK7man", command=cloud_rk7man_dialog)
cloud_rk7man_btn.grid(row=1, column=2, padx=5, sticky="ew", pady=(5, 0))

# Настройка весов строк и столбцов для равномерного распределения
check_folder_frame.grid_columnconfigure(0, weight=1)
check_folder_frame.grid_columnconfigure(1, weight=1)
check_folder_frame.grid_columnconfigure(2, weight=1)



def get_short_path_name(long_path):
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.kernel32.GetShortPathNameW(long_path, buf, 260)
    return buf.value

# Проверка версии
def check_for_updates(silent=False):
    url_exe = "https://github.com/FoKiRu/-----Engineer-Helper/raw/main/dist/EngiHelp.exe"
    url_py = "https://raw.githubusercontent.com/FoKiRu/-----Engineer-Helper/main/EngiHelp.py"
    try:
        version_response = requests.get(url_py, timeout=5)
        version_response.raise_for_status()
        match = re.search(r'SCRIPT_VERSION\s*=\s*"v([\d.]+)"', version_response.text)
        if not match:
            if not silent:
                centered_warning("Ошибка", "Не удалось определить версию на GitHub.")
            return
        remote_version = f"v{match.group(1)}"
        current_version = version.parse(SCRIPT_VERSION.lstrip('v'))
        remote_version = version.parse(remote_version.lstrip('v'))

        if remote_version <= current_version:
            if not silent:
                centered_info("Актуальная версия", f"Установлена последняя версия: {SCRIPT_VERSION}")
            return

        if not centered_askyesno("Обновление", f"Доступна новая версия: {remote_version}\nОбновить сейчас?"):
            return

        response = requests.get(url_exe, timeout=10)
        response.raise_for_status()
        temp_dir = tempfile.gettempdir()
        temp_exe = os.path.join(temp_dir, "EngiHelp_updated.exe")
        with open(temp_exe, "wb") as f:
            f.write(response.content)
        current_exe = sys.executable
        short_exe = get_short_path_name(current_exe)
        bat_path = os.path.join(temp_dir, "restart_engihelp.bat")
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
        subprocess.Popen(['cmd', '/c', bat_path], shell=False)
        root.destroy()
    except Exception as e:
        if not silent:
            centered_error("Ошибка", f"Не удалось обновить:\n{e}")

# ======================= Вкладка "Настройки" =======================
prefs_tab = tk.Frame(notebook)
notebook.add(prefs_tab, text="Настройки")

def save_prefs_flags(*_):
    """Сохраняет флаги настроек в файл данных при их переключении."""
    data = load_data()
    data["settings"]["auto_update"] = auto_update_var.get()
    data["settings"]["task_from_version"] = task_from_version_var.get()
    data["settings"]["keep_cloud_files"] = keep_cloud_files_var.get()
    save_data(data)

tk.Checkbutton(
    prefs_tab,
    text="Проверять обновления при запуске",
    variable=auto_update_var,
    command=save_prefs_flags
).pack(padx=10, pady=(10, 5), anchor="w")

tk.Checkbutton(
    prefs_tab,
    text="Выбор задачи из выбора версии",
    variable=task_from_version_var,
    command=save_prefs_flags
).pack(padx=10, pady=(0, 2), anchor="w")

desc_label = tk.Label(
    prefs_tab,
    text=("При выборе версии RK будет предложено выбрать задачу из этой версии. "
          "Если флаг выключен — применяется последняя используемая задача."),
    justify="left",
    fg="gray40",
    font=("TkDefaultFont", 8),
    wraplength=350,      # ширина в пикселях, под окно
    anchor="w"
)
desc_label.pack(padx=(30, 10), pady=(0, 10), anchor="w", fill="x")

tk.Checkbutton(
    prefs_tab,
    text="Сохранять временные файлы Cloud RK7man",
    variable=keep_cloud_files_var,
    command=save_prefs_flags
).pack(padx=10, pady=(0, 2), anchor="w")

cloud_files_desc_label = tk.Label(
    prefs_tab,
    text=("Временные .ini файлы Cloud RK7man хранятся в папке Cloud_log. "
          "Если флаг выключен — файл удаляется после закрытия rk7man.exe."),
    justify="left",
    fg="gray40",
    font=("TkDefaultFont", 8),
    wraplength=350,
    anchor="w"
)
cloud_files_desc_label.pack(padx=(30, 10), pady=(0, 10), anchor="w", fill="x")

# Info tab
info_tab = tk.Frame(notebook)
notebook.add(info_tab, text="О программе")

info_label = tk.Label(info_tab, text=f"{DESCRIPTION}\n{AUTHOR}\n{EMAIL}\n{SCRIPT_VERSION}", justify="left", anchor="nw")
info_label.pack(padx=10, pady=10, anchor="nw", fill="both", expand=True)
info_label.bind('<Configure>', lambda e: info_label.config(wraplength=e.width - 20))

# Обёртка для ручной проверки через кнопку (справа)
tk.Button(info_tab, text="Проверить обновление", command=lambda: check_for_updates(silent=False))\
    .pack(padx=10, pady=(0, 10), anchor="e")

def update_every_1_seconds():
    # Обновляем информацию о WinCash и RKEEPER по приоритету
    update_ini_info_by_priority()
    # Проверяем файлы и обновляем состояние
    on_check()
    # Планируем следующее обновление через 1000 миллисекунд (1 секунд)
    root.after(1000, update_every_1_seconds)

# Вызовем эту функцию для начала цикла обновлений
root.after(1000, update_every_1_seconds)

# Проверка автообновления при старте
if auto_update_var.get():
    root.after(1000, lambda: check_for_updates(silent=True))

# === Инициализация глобальных горячих клавиш ===
root.protocol("WM_DELETE_WINDOW", on_closing)
setup_global_hotkeys()

on_check()
root.deiconify()
root.mainloop()


# pyinstaller --onefile --windowed --icon=".\.ico\иконка EngiHelp.ico" --hidden-import=tkinter --clean EngiHelp.py