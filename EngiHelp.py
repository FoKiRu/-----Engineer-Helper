# ======================= Импорты =======================
from tkinter import messagebox, filedialog, ttk
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

# ======================= Константы и настройки =======================
SCRIPT_VERSION = "v1.2.4"
AUTHOR = "Автор: Кирилл Рутенко"
EMAIL = "Эл. почта: k.rutenko@rkeeper.ru"
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
        return {"settings": {"auto_update": True, "recent_paths": []}, "tasks": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Убедимся, что все ключи на месте
            if "settings" not in data:
                data["settings"] = {"auto_update": True, "recent_paths": []}
            if "tasks" not in data:
                data["tasks"] = {}
            return data
    except (json.JSONDecodeError, IOError):
        # В случае ошибки возвращаем пустую структуру
        return {"settings": {"auto_update": True, "recent_paths": []}, "tasks": {}}

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
    new_data = {"settings": {"auto_update": True, "recent_paths": []}, "tasks": {}}
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
    """
    try:
        response = requests.get(GITHUB_URL)
        response.raise_for_status()  # Проверка на успешный ответ (200)
        # Чтение первой строки
        first_line = response.text.splitlines()[0].strip()

        if first_line == "0":
            return True  # Программа может продолжить выполнение
        elif first_line == "1":
            return False  # Программа не будет запускаться
        else:
            print(f"Неожиданный формат в .gitignore: {first_line}. Программа не будет запускаться.")
            return False
    except requests.RequestException as e:
        print(f"Ошибка при запросе к GitHub: {e}")
        return False

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
WINDOW_WIDTH = 397
WINDOW_HEIGHT = 430
WINDOW_OFFSET_X = 230
WINDOW_OFFSET_Y = 140

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
    return paths, auto_update


def save_settings_and_path(new_path):
    new_path = new_path.replace("\\", "/")
    data = load_data()
    
    # Обновляем список путей
    paths = data["settings"].get("recent_paths", [])
    if new_path in paths:
        paths.remove(new_path)
    paths.insert(0, new_path)
    data["settings"]["recent_paths"] = paths[:3] # Оставляем только 3 последних

    # Обновляем флаг автообновления
    data["settings"]["auto_update"] = auto_update_var.get()
    
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
                # Ищем base_ что угодно (буквы или цифры) до конца пути или символа
                if line.lower().startswith("udbfile") or line.lower().startswith("workmodules"):
                    # [a-zA-Z0-9_]+ захватывает и цифры, и буквы, и подчеркивания
                    match = re.search(r'base_([a-zA-Z0-9_]+)', line)
                    if match:
                        return match.group(1)
    except Exception as e:
        print(f"Ошибка при чтении rk7srv.INI: {e}")
    return None

# ======================= Определение путей и начальных переменных =======================
ini_paths, auto_update_enabled = load_settings_and_paths()
ini_path = ini_paths[0] if ini_paths else ""
auto_update_var = tk.BooleanVar(value=auto_update_enabled)
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

# Открываем номер задачи в SD
def open_task_in_sd():
    task_id = task_id_var.get()
    if task_id:
        url = f'https://sd.rkeeper.ru/sd/operator/#esearch:full:serviceCall:ALL_OBJECTS!{{%22query%22:%22serviceCall@number:{task_id}%22}}'
        webbrowser.open(url)
    else:
        messagebox.showwarning("Предупреждение", "Номер задачи не найден")


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
        return True

def toggle_usedbsync():
    value = "1" if usedbsync_var.get() else "0"
    run_update(value)

def toggle_usesql():
    value = "1" if usesql_var.get() else "0"
    run_update_usesql_value(value)

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
        messagebox.showwarning("Внимание", f"Не удалось обновить: {', '.join(failed)}")

def run_update_usesql_value(value):
    success = update_ini_file(INI_FILE_USESQL, value, "USESQL")
    if not success:
        messagebox.showwarning("Ошибка", "Не удалось обновить UseSQL в rk7srv.INI")

# Кнопка "Открыть путь"
def open_explorer_to_root():
    product_root = find_product_root(path_var.get())
    if not product_root:
        messagebox.showwarning("Ошибка", "Не удалось определить корневую папку продукта.")
        return
    try:
        os.startfile(product_root)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось открыть проводник:\n{e}")

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
    selected_task_id = task_id_var.get()
    if not selected_task_id:
        return

    data = load_data()
    tasks = data.get("tasks", {})

    if selected_task_id not in tasks:
        return

    task_info = tasks[selected_task_id]

    # === ПРОВЕРКА НА НЕСКОЛЬКО ВЕРСИЙ ===
    versions = task_info.get("versions", {})
    if len(versions) > 1:
        show_version_selection_dialog(selected_task_id, task_info, versions)
        return

    # --- ЛОГИКА ПЕРЕМЕЩЕНИЯ ЗАДАЧИ НАВЕРХ ---
    if list(tasks.keys())[0] != selected_task_id:
        selected_task_info = tasks.pop(selected_task_id)
        sorted_tasks = {selected_task_id: selected_task_info, **tasks}
        data["tasks"] = sorted_tasks
        save_data(data)
        task_id_combobox['values'] = list(sorted_tasks.keys())
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
        messagebox.showerror("Ошибка", f"Файл rk7srv.INI не найден:\n{rk7srv_ini_path}")
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

    # Применяем base_path
    base_path = task_info.get("base_path", "")
    if base_path:
        base_dir = os.path.basename(base_path)
        update_rk7srv_ini(rk7srv_ini_path, base_dir)

    # === ПРИМЕНЯЕМ midbase_path ===
    midbase_path = task_info.get("midbase_path", "")
    if midbase_path:
        midbase_folder_name = os.path.basename(midbase_path)
        update_rkeeper_ini_basepath(ini_path_from_task, midbase_folder_name)
        print(f"[OK] Применён MIDBASE: {midbase_folder_name}")

    # Обновляем чекбоксы в UI
    on_check()

    print(f"Параметры для задачи {selected_task_id} применены!")

# Функция по обновлению rk7srv.INI для директории по задачи
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
        messagebox.showwarning("Предупреждение", "Сначала выберите задачу!")
        return

    data = load_data()
    tasks = data.get("tasks", {})

    if selected_task_id not in tasks:
        messagebox.showwarning("Предупреждение", f"Задача {selected_task_id} не найдена!")
        return

    task_info = tasks[selected_task_id]
    current_ini_path = task_info.get("ini_path", path_var.get())

    # Извлекаем текущую версию
    current_version = extract_rk_version_from_path(current_ini_path)
    if not current_version:
        messagebox.showerror("Ошибка",
            "Не удалось определить текущую версию RK из пути.\n"
            "Ожидается папка вида INST7.25.09.2004")
        return

    # Ищем доступные версии
    available_versions = find_available_rk_versions(current_ini_path)
    other_versions = [v for v in available_versions if v != current_version]

    if not other_versions:
        messagebox.showinfo("Информация",
            f"Других версий RK не найдено.\n"
            f"Текущая версия: {current_version}\n"
            f"Директория поиска: {os.path.dirname(find_product_root(current_ini_path))}")
        return

    # === Диалог выбора версии ===
    select_win = tk.Toplevel(root)
    select_win.title("Сменить версию RK")
    select_win.transient(root)
    select_win.grab_set()
    select_win.focus_force()

    if icon_path:
        select_win.iconbitmap(icon_path)

    w, h = 300, 180
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    select_win.geometry(f"{w}x{h}+{x}+{y}")

    tk.Label(select_win, text=(
        f"Задача: {selected_task_id}\n"
        f"Текущая версия: {current_version}\n\n"
        f"Выберите версию для переноса базы:"
    ), justify="left").pack(padx=10, pady=(10, 5))

    version_var = tk.StringVar()
    version_combo = ttk.Combobox(
        select_win, textvariable=version_var,
        values=other_versions, state="readonly", width=30
    )
    version_combo.pack(padx=10, pady=5)
    if other_versions:
        version_combo.current(0)

    tk.Label(select_win, text=(
        "⚠ Процессы refsrv.exe и rk7man.exe будут закрыты!"
    ), fg="red", font=("TkDefaultFont", 8)).pack(padx=10, pady=(5, 0))

    def on_confirm():
        target_version = version_var.get()
        if not target_version:
            messagebox.showwarning("Предупреждение", "Выберите версию!")
            return
        select_win.destroy()
        perform_version_change(selected_task_id, current_version, target_version)

    btn_frame = tk.Frame(select_win)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Перенести", command=on_confirm, width=12).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=select_win.destroy, width=12).pack(side="left", padx=5)


def perform_version_change(task_id, current_version, target_version):
    """Выполняет перенос базы задачи в другую версию RK."""
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
        messagebox.showerror("Ошибка", f"Папка bin/win не найдена:\n{target_bin_win}")
        return

    # Завершаем процессы
    kill_processes_for_version_change()

    # Пути к base
        # Получаем путь к base текущей задачи
    current_base_path = task_info.get("base_path")
    if not current_base_path or not os.path.isdir(current_base_path):
        messagebox.showerror("Ошибка",
            f"Папка base для задачи не найдена:\n{current_base_path}")
        return
    base_folder_name = os.path.basename(current_base_path)
    target_base_path = os.path.join(target_product_root, base_folder_name).replace("\\", "/")

        # Копируем папку base в целевую версию
    try:
        if os.path.exists(target_base_path):
            if not messagebox.askyesno("Предупреждение",
                f"Папка уже существует:\n{target_base_path}\n\nПерезаписать?"):
                return
            shutil.rmtree(target_base_path)

        shutil.copytree(current_base_path, target_base_path)
        print(f"Base скопирована: {current_base_path} -> {target_base_path}")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось скопировать base:\n{e}")
        return

    # MIDBASE
    current_midbase = task_info.get("midbase_path")
    target_midbase_path = None
    
    if current_midbase:
        # Определяем путь, где должна быть новая midbase
        target_midbase_path = os.path.join(target_product_root, os.path.basename(current_midbase)).replace("\\", "/")
        
        # Удаляем старую, если есть
        if os.path.exists(target_midbase_path):
            shutil.rmtree(target_midbase_path)
            
        # Создаем пустую директорию вместо копирования
        try:
            os.makedirs(target_midbase_path)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать пустую папку midbase: {e}")
            return


    # === ОБНОВЛЕНИЕ JSON СТРУКТУРЫ ===
    if "versions" not in task_info:
        task_info["versions"] = {}

    # Сохраняем текущую версию в словарь версий, если её там нет
    if current_version not in task_info["versions"]:
        task_info["versions"][current_version] = {
            "ini_path": current_ini_path,
            "base_path": current_base_path,
            "midbase_path": task_info.get("midbase_path"),
            "ini_settings": task_info.get("ini_settings", {})
        }

    # Создаем запись для новой версии
    new_version_data = {
        "ini_path": target_ini_path_normalized,
        "base_path": target_base_path,
        "ini_settings": task_info.get("ini_settings", {}).copy()
    }
    if target_midbase_path:
        new_version_data["midbase_path"] = target_midbase_path

    task_info["versions"][target_version] = new_version_data
    
    # Обновляем основные параметры задачи на новую версию
    task_info["ini_path"] = target_ini_path_normalized
    task_info["base_path"] = target_base_path
    if target_midbase_path:
        task_info["midbase_path"] = target_midbase_path

    tasks[task_id] = task_info
    data["tasks"] = tasks
    save_data(data)

    # Обновляем INI файлы в целевой папке
    for f in FILES:
        src = os.path.join(current_ini_path, f)
        dst = os.path.join(target_bin_win, f)
        if os.path.isfile(src): shutil.copy2(src, dst)

    update_rk7srv_ini(os.path.join(target_bin_win, "rk7srv.INI"), base_folder_name)
    
    # Обновляем UI
    path_var.set(target_ini_path_normalized)
    apply_path(update_task=False)
    messagebox.showinfo("Успех", f"База перенесена в версию {target_version}")


# ======================= Выбор версии при переключении задачи =======================

def show_version_selection_dialog(task_id, task_info, versions):
    """Диалог выбора версии при выборе задачи с несколькими версиями."""
    select_win = tk.Toplevel(root)
    select_win.title("Выбор версии RK")
    select_win.transient(root)
    select_win.grab_set()
    select_win.focus_force()

    if icon_path:
        select_win.iconbitmap(icon_path)

    # Обратный порядок версий
    version_list = list(reversed(sorted(versions.keys())))

    # Определяем текущую версию
    current_ver = extract_rk_version_from_path(task_info.get("ini_path", ""))

    # Динамическая высота
    row_height = 28
    base_height = 140
    h = base_height + len(version_list) * row_height
    w = 260
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    select_win.geometry(f"{w}x{h}+{x}+{y}")
    select_win.resizable(False, False)

    # Заголовок по центру
    tk.Label(select_win, text=(
        f"Задача {task_id} имеет несколько версий RK.\n"
        f"Выберите версию для работы:"
    ), justify="center", anchor="center").pack(padx=10, pady=(15, 5), fill="x")

    # === Переменная выбора ===
    version_var_local = tk.StringVar()

    if current_ver in version_list:
        version_var_local.set(current_ver)
    elif version_list:
        version_var_local.set(version_list[0])

    # Внешний фрейм-контейнер — центрируется в окне
    center_container = tk.Frame(select_win)
    center_container.pack(pady=5, expand=True)  # expand=True → центр по вертикали/горизонтали

    # Внутренний фрейм — версии внутри него по левому краю
    radio_frame = tk.Frame(center_container)
    radio_frame.pack()

    for ver in version_list:
        # Без "INS" / "INST" — только номер версии
        label_text = ver
        if ver == current_ver:
            label_text += "  ◀ текущая"

        rb = tk.Radiobutton(
            radio_frame,
            text=label_text,
            variable=version_var_local,
            value=ver,
            anchor="w",  # текст внутри кнопки — по левому краю
            font=("TkDefaultFont", 9, "bold" if ver == current_ver else "normal")
        )
        rb.pack(anchor="w", pady=2)  # кнопки прижаты влево внутри фрейма

    # === Кнопки ===
    def on_select():
        selected_ver = version_var_local.get()
        if not selected_ver:
            return
        select_win.destroy()
        apply_task_version(task_id, selected_ver)

    def on_cancel():
        select_win.destroy()

    btn_frame = tk.Frame(select_win)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Выбрать", command=on_select, width=12).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=on_cancel, width=12).pack(side="left", padx=5)


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
        messagebox.showerror("Ошибка", f"Информация о версии {selected_version} не найдена.")
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

    task_id_combobox['values'] = list(tasks.keys())

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

    base_path = version_info.get("base_path", "")
    if base_path and os.path.exists(rk7srv_ini_path):
        base_dir = os.path.basename(base_path)
        update_rk7srv_ini(rk7srv_ini_path, base_dir)

    # === MIDBASE ===
    midbase_path = version_info.get("midbase_path", "")
    if midbase_path:
        midbase_folder_name = os.path.basename(midbase_path)
        update_rkeeper_ini_basepath(ini_path_from_version, midbase_folder_name)

    on_check()

# Фрейм для метки, кнопки "Открыть" и поля для номера задачи
label_and_open_frame = tk.Frame(settings_tab)
label_and_open_frame.pack(fill="x", padx=9, pady=(10, 0), ipady=0)

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
task_id_combobox.bind("<<ComboboxSelected>>", on_task_selected)

# Привяжите сохранение к событию изменения текста в поле (опционально)
task_id_var.trace_add("write", lambda *args: save_task_id_to_file())

def save_task_id_to_file():
    task_id = task_id_var.get().strip()
    if not task_id:
        return  # Если поле пустое, ничего не сохраняем

    product_root = find_product_root(path_var.get())
    if not product_root:
        messagebox.showerror("Ошибка", "Не удалось определить корневую папку продукта.")
        return

    task_id_file = os.path.join(product_root, "ID задачи.txt")
    try:
        with open(task_id_file, "w", encoding="utf-8") as f:
            f.write(task_id)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось сохранить номер задачи:\n{e}")

# Функция по сбору параметров
def get_ini_settings(ini_path):
    """Сбор параметров UseDBSync, UseSQL, Station, Server из INI-файлов."""
    settings = {
        "UseDBSync": get_usedbsync_values(),
        "UseSQL": get_usesql_value(),
        "Station": station_var.get(),
        "Server": server_var.get()
    }
    return settings

# Сохранения номера задачи в файл
def save_task_id():
    task_id = task_id_var.get().strip()
    if not task_id:
        messagebox.showwarning("Предупреждение", "Поле 'Номер задачи' пустое!")
        return

    product_root = find_product_root(path_var.get())
    if not product_root:
        messagebox.showerror("Ошибка", "Не удалось определить корневую папку продукта.")
        return

    base_path = os.path.join(product_root, "base")
    if not os.path.exists(base_path):
        messagebox.showerror("Ошибка", f"Папка {base_path} не найдена!")
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
                if messagebox.askyesno(
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
                messagebox.showerror("Ошибка", f"Не удалось проверить блокировку:\n{e}")
                return

    # === Папка base_(task_id) ===
    new_base_path = os.path.join(product_root, f"base_{task_id}")
    if os.path.exists(new_base_path):
        if messagebox.askyesno("Предупреждение", f"Папка {new_base_path} уже существует. Перезаписать?"):
            try:
                shutil.rmtree(new_base_path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить существующую папку:\n{e}")
                return
        else:
            return

    try:
        shutil.copytree(base_path, new_base_path)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось скопировать папку base:\n{e}")
        return

    # === Папка MIDBASE_(task_id) - ВСЕГДА СОЗДАЁТСЯ ПУСТОЙ ===
    midbase_folder_name = f"MIDBASE_{task_id}"
    midbase_path = os.path.join(product_root, midbase_folder_name)

    if os.path.exists(midbase_path):
        if not messagebox.askyesno(
            "Предупреждение",
            f"Папка {midbase_path} уже существует. Перезаписать?"
        ):
            return
        else:
            try:
                shutil.rmtree(midbase_path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить {midbase_path}:\n{e}")
                return

    # Создаём пустую папку MIDBASE
    try:
        os.makedirs(midbase_path, exist_ok=True)
        print(f"[OK] Создана пустая папка MIDBASE: {midbase_path}")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось создать папку MIDBASE:\n{e}")
        return

    # Обновляем BasePath в RKEEPER.INI
    update_rkeeper_ini_basepath(path_var.get(), midbase_folder_name)

    # Собираем параметры INI
    ini_settings = get_ini_settings(path_var.get())

    # Сохраняем в JSON
    data = load_data()
    tasks = data.get("tasks", {})

    task_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_path": new_base_path.replace("\\", "/"),
        "midbase_path": midbase_path.replace("\\", "/"),
        "ini_path": path_var.get().replace("\\", "/"),
        "status": "copied",
        "ini_settings": ini_settings
    }

    tasks[task_id] = task_entry
    tasks = {task_id: tasks[task_id], **{k: v for k, v in tasks.items() if k != task_id}}
    data["tasks"] = tasks
    save_data(data)

    task_id_combobox['values'] = load_task_ids()

    # Обновляем rk7srv.INI
    base_dir = os.path.basename(new_base_path)
    rk7srv_ini_path = os.path.join(path_var.get(), "rk7srv.INI")
    update_rk7srv_ini(rk7srv_ini_path, base_dir)

    messagebox.showinfo(
        "Успех",
        f"Папка base скопирована как {new_base_path}!\n"
        f"Пустая папка MIDBASE создана: {midbase_path}"
    )

# Загрузка номеров задач
def load_task_ids():
    data = load_data()
    return list(data.get("tasks", {}).keys())

def delete_task():
    selected_task_id = task_id_var.get().strip()
    if not selected_task_id:
        messagebox.showwarning("Предупреждение", "Выберите задачу для удаления!")
        return

    data = load_data()
    tasks = data.get("tasks", {})

    if selected_task_id not in tasks:
        messagebox.showwarning("Предупреждение", f"Задача {selected_task_id} не найдена!")
        return

    task_info = tasks[selected_task_id]

    # === Собираем ВСЕ пути base и midbase (основной + из всех версий) ===
    all_paths = set()

    # Основной base_path
    main_base = task_info.get("base_path")
    if main_base:
        all_paths.add(os.path.normpath(main_base))

    # Основной midbase_path
    main_midbase = task_info.get("midbase_path")
    if main_midbase:
        all_paths.add(os.path.normpath(main_midbase))

    # base_path и midbase_path из каждой версии
    versions = task_info.get("versions", {})
    for ver_name, ver_info in versions.items():
        ver_base = ver_info.get("base_path")
        if ver_base:
            all_paths.add(os.path.normpath(ver_base))
        
        ver_midbase = ver_info.get("midbase_path")
        if ver_midbase:
            all_paths.add(os.path.normpath(ver_midbase))

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

    if not messagebox.askyesno("Подтверждение удаления", confirm_msg):
        return

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

    # Если хотя бы одна папка не удалилась — предупреждаем, но продолжаем
    if failed_paths:
        error_details = "\n".join(f"• {p}: {err}" for p, err in failed_paths)
        action = messagebox.askyesno(
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
    task_id_var.set("")

    # Формируем итоговое сообщение
    result_msg = f"Задача {selected_task_id} удалена!"
    if deleted_paths:
        result_msg += f"\n\nУдалено папок: {len(deleted_paths)}"
    if failed_paths:
        result_msg += f"\nНе удалось удалить: {len(failed_paths)}"

    messagebox.showinfo("Успех", result_msg)


# Кнопка "Сохранить"
tk.Button(
    label_and_open_frame,
    text="Сохранить",
    command=save_task_id, # Функция сохранения номера здачи
    font=("TkDefaultFont", 8)
).grid(row=0, column=4, padx=(5, 0), sticky="w")

# Выбор пути
path_frame = tk.Frame(settings_tab)
path_frame.pack(fill="x", padx=10, pady=(5, 0))
path_var = tk.StringVar()
ini_paths, auto_update_enabled = load_settings_and_paths()
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
                    messagebox.showerror("Ошибка", f"Не удалось скопировать {f}:\n{e}")
        if copied:
            messagebox.showinfo("Файлы скопированы", f"Скопированы из bin\\win\\ini:\n{', '.join(copied)}")

    # Теперь проверяем наличие файлов и определяем корень продукта
    product_root = find_product_root(selected)
    if not product_root:
        messagebox.showerror("Ошибка", "Выбран некорректный путь.\nТребуется папка, содержащая bin/win с INI-файлами.")
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
    global ini_path, INI_FILE_USESQL
    
    new_path = path_var.get()
    if not os.path.isdir(new_path):
        messagebox.showerror("Ошибка", f"Путь не найден:\n{new_path}")
        return

    # Обновляем глобальные переменные
    ini_path = new_path
    INI_FILE_USESQL = os.path.join(ini_path, "rk7srv.INI")

    # Сохраняем выбранный путь в конфиг
    save_settings_and_path(ini_path)
    
    # --- ЛОГИКА АВТОЗАГРУЗКИ ЗАДАЧИ ---
    if update_task: # Выполняем только если разрешено
        latest_task_id = find_latest_task_for_path(ini_path)
        
        if latest_task_id:
            print(f"Найден последний ID задачи ({latest_task_id}) для пути {ini_path}. Применяем настройки.")
            task_id_var.set(latest_task_id)
            on_task_selected(None) 
        else:
            print(f"Для пути {ini_path} сохраненных задач не найдено. Загружаем из INI-файлов.")
            task_id_var.set("") 
            load_wincash_params()
            on_check()
    else:
        # Если обновление задачи не требуется, просто загружаем данные из INI
        load_wincash_params()
        on_check()
    # --- КОНЕЦ ЛОГИКИ ---
    
    task_id_combobox['values'] = load_task_ids()

path_entry.bind("<<ComboboxSelected>>", apply_path) # Обновление после выбора пути из списка

"""
# Кнопка "Открыть путь"
def open_explorer_to_root():
    product_root = find_product_root(path_var.get())
    if not product_root:
        messagebox.showwarning("Ошибка", "Не удалось определить корневую папку продукта.")
        return
    try:
        os.startfile(product_root)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось открыть проводник:\n{e}")

tk.Button(settings_tab, text="Открыть путь", command=open_explorer_to_root).pack(padx=10, pady=(0, 0), anchor="w")
"""


"""
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
        messagebox.showinfo("Проверка", "Программа запущена.")
    else:
        messagebox.showwarning("Проверка", "Программа не найдена.")
"""

# ======================= Удаление MIDBASE =======================
def get_task_data(task_id):
    """Получает данные задачи из JSON конфигурации"""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get(task_id)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось прочитать конфигурацию:\n{e}")
        return None

def delete_midbase_files():
    selected_task_id = task_id_var.get().strip()
    if not selected_task_id:
        messagebox.showwarning("Внимание", "Сначала выберите задачу, для которой нужно удалить MIDBASE.")
        return

    # Получаем данные из JSON
    base_path = get_current_task_base_path(selected_task_id)
    
    if not base_path:
        messagebox.showerror("Ошибка", f"Задача {selected_task_id} не найдена.")
        return
    
    # Если есть в JSON - берём оттуда
    task_data = get_task_data(selected_task_id)
    midbase_path = task_data.get("midbase_path") if task_data else None
    
    # Если в JSON нет - строим путь автоматически
    if not midbase_path:
        parent_path = os.path.dirname(base_path)
        midbase_path = os.path.normpath(os.path.join(parent_path, f"MIDBASE_{selected_task_id}")).replace("\\", "/")

    if not os.path.isdir(midbase_path):
        messagebox.showerror("Ошибка", f"Папка MIDBASE не найдена:\n{midbase_path}")
        return

    # Для MIDBASE нет защищённых файлов - удаляем всё
    protected_files = []

    # Создаем колбэки с уже определенным путем
    callback_with_backup = partial(proceed_with_backup_and_deletion, midbase_path, protected_files)
    callback_without_backup = partial(proceed_with_deletion, protected_files, midbase_path, backup_path=None)

    # Вызываем окно подтверждения (используем существующую функцию)
    confirm_deletion_with_options(
        protected_files,
        midbase_path,
        callback_with_backup,
        callback_without_backup
    )
    
def confirm_deletion_with_options(protected_files, base_path, callback_with_backup, callback_without_backup):
    win = tk.Toplevel(root)
    win.title("Подтверждение очистки")
    win.transient(root)
    win.grab_set()
    win.focus_force()

    if icon_path:
        win.iconbitmap(icon_path)

    win.update_idletasks()
    w = 380
    h = 180
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

    msg = f"Вы действительно хотите очистить папку:\n{base_path}"
    
    # Добавляем информацию о защищённых файлах только если они есть
    if protected_files:
        msg += f"\n\nБудут оставлены: {', '.join(protected_files)}"
    
    tk.Label(win, text=msg, justify="left", wraplength=w-20).pack(padx=10, pady=(10, 5))

    do_backup_var = tk.BooleanVar(value=False)
    tk.Checkbutton(win, text="Создать резервную копию", variable=do_backup_var).pack(anchor="w", padx=12, pady=(0, 5))

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=5)

    def on_delete():
        win.destroy()
        if do_backup_var.get():
            callback_with_backup()
        else:
            callback_without_backup()

    tk.Button(btn_frame, text="Очистить", command=on_delete).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=win.destroy).pack(side="left", padx=5)

# ======================= Удаление base =======================
def delete_unwanted_files():
    selected_task_id = task_id_var.get().strip()
    if not selected_task_id:
        messagebox.showwarning("Внимание", "Сначала выберите задачу, для которой нужно очистить папку base.")
        return

    # Используем нашу новую функцию для получения правильного пути
    base_path = get_current_task_base_path(selected_task_id)

    if not base_path or not os.path.isdir(base_path):
        messagebox.showerror("Ошибка", f"Папка base для задачи {selected_task_id} не найдена:\n{base_path}")
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

# Окно с предупреждением и исключением
# Окно с предупреждением и исключением
def confirm_deletion_with_options(protected_files, base_path, callback_with_backup, callback_without_backup):
    win = tk.Toplevel(root)
    win.title("Подтверждение очистки")
    win.transient(root)
    win.grab_set()
    win.focus_force()

    if icon_path:
        win.iconbitmap(icon_path)

    win.update_idletasks()
    w = 380 # Немного шире для длинных путей
    h = 180
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

    # Обновленное сообщение, показывающее, какая папка будет очищена
    msg = (
        f"Вы действительно хотите очистить папку:\n{base_path}\n\n"
        f"Будут оставлены: {', '.join(protected_files)}"
    )
    tk.Label(win, text=msg, justify="left", wraplength=w-20).pack(padx=10, pady=(10, 5))

    do_backup_var = tk.BooleanVar(value=False)
    tk.Checkbutton(win, text="Создать резервную копию", variable=do_backup_var).pack(anchor="w", padx=12, pady=(0, 5))

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=5)

    def on_delete():
        win.destroy()
        if do_backup_var.get():
            callback_with_backup()
        else:
            callback_without_backup()

    tk.Button(btn_frame, text="Очистить", command=on_delete).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=win.destroy).pack(side="left", padx=5)


def proceed_with_backup_and_deletion(base_path, protected_files):
    copying_win = tk.Toplevel(root)
    copying_win.title("Подождите")
    copying_win.transient(root)
    copying_win.grab_set()
    tk.Label(copying_win, text="Создаётся резервная копия папки base...").pack(padx=20, pady=20)
    copying_win.update()

    if icon_path:
        copying_win.iconbitmap(icon_path)

    # Центрируем окно относительно главного
    copying_win.update_idletasks()
    w = 260
    h = 60
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    copying_win.geometry(f"{w}x{h}+{x}+{y}")

    def run():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(os.path.dirname(base_path), f"base_backup_{timestamp}")
        try:
            shutil.copytree(base_path, backup_path)
        except Exception as e:
            root.after(0, lambda: (copying_win.destroy(), messagebox.showerror("Ошибка", f"Не удалось создать резервную копию:\n{e}")))
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
            messagebox.showerror("Ошибка", f"Не удалось удалить: {item_path}\n{e}")

    if deleted_items:
        msg = f"Удалено: {', '.join(deleted_items)}"
        if backup_path:
            msg += f"\n\nРезервная копия создана:\n{backup_path}"
        centered_info("Удаление завершено", msg)
    else:
        centered_info("Удаление файлов и папок", "Нет элементов для удаления или все элементы защищены.")


def centered_info(title, message):
    win = tk.Toplevel(root)
    win.title(title)
    win.transient(root)
    win.grab_set()
    win.focus_force()

    if icon_path:
        win.iconbitmap(icon_path)

    tk.Label(win, text=message, justify="left", wraplength=360).pack(padx=20, pady=15)
    tk.Button(win, text="OK", command=win.destroy, width=15).pack(pady=(0, 10))

    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    win.geometry(f"+{x}+{y}")

# ======================= Запуск / рестарт Ref, Mid Srv =======================
def run_or_restart_process(exe_name):
    exe_path = os.path.join(ini_path, exe_name)
    if not os.path.isfile(exe_path):
        messagebox.showerror("Ошибка", f"Файл не найден:\n{exe_path}")
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
        messagebox.showerror("Ошибка запуска", str(e))

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
        messagebox.showerror("Ошибка", f"Файл не найден:\n{bat_path}")
        return
    try:
        os.startfile(bat_path)
    except Exception as e:
        messagebox.showerror("Ошибка запуска", str(e))

# ======================= Запуск wincash.bat =======================
def run_wincash_bat():
    def run_bat():
        bat_path = os.path.join(ini_path, "wincash.bat")
        
        # Проверка наличия файла
        if not os.path.isfile(bat_path):
            messagebox.showerror("Ошибка", f"Файл не найден:\n{bat_path}")
            return
        
        try:
            # Запуск .bat файла с выводом ошибок
            print(f"[DEBUG] Попытка запуска: {bat_path}")
            result = subprocess.run([bat_path], capture_output=True, text=True, shell=True, cwd=ini_path)

            # Проверка результата
            if result.returncode != 0:
                # Если код завершения не 0, выводим ошибку
                print(f"[ERROR] Ошибка при выполнении bat файла: {result.stderr}")
                messagebox.showerror("Ошибка запуска", f"Ошибка при запуске {bat_path}:\n{result.stderr}")
            else:
                # Если всё прошло успешно, выводим результат
                print(f"[INFO] bat файл выполнен успешно:\n{result.stdout}")
        except Exception as e:
            # Обработка исключений
            messagebox.showerror("Ошибка запуска", f"Не удалось запустить {bat_path}:\n{str(e)}")

    # Запуск функции в отдельном потоке
    threading.Thread(target=run_bat, daemon=True).start()

# DOSCASH.EXE нужно закрыть перед запуском если есть

def run_refsrv_and_rk7man():
    run_or_restart_process("refsrv.exe")
    time.sleep(1.5)
    run_rk7man()

# ======================= Запуск MidServ + WinCash =======================
def run_midserv_and_wincash():
    run_or_restart_process("midserv.exe")
    time.sleep(1.5)
    run_wincash_bat()

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

def kill_rk7man_process():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == "rk7man.exe":
                proc.terminate()
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def kill_refsrv_process():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == "refsrv.exe":
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
tk.Button(frame_refsrv_rk7man, text="❌", command=lambda: kill_refsrv_process() or kill_rk7man_process(), width=2)\
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
tk.Button(frame_refsrv, text="Refsrv", command=lambda: run_or_restart_process("refsrv.exe"), width=15)\
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
tk.Button(frame_rk7man, text="RK7man", command=run_rk7man, width=15)\
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
tk.Button(frame_midserv, text="MidServ", command=lambda: run_or_restart_process("midserv.exe"), width=15)\
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
tk.Button(frame_win_cash, text="WinCash", command=run_wincash_bat, width=15)\
    .pack(side="left")  # Кнопка расположена слева в фрейме

tk.Button(frame_win_cash, text="📄", command=partial(open_log_file, "cash.stk"), width=3)\
    .pack(side="left")

# Кнопка Close для WinCash
tk.Button(frame_win_cash, text="❌", command=kill_doscash_process, width=2)\
    .pack(side="left")  # Кнопка расположена справа в том же фрейме


# Переключатели
usesql_var = tk.IntVar(value=int(get_usesql_value()))
usedbsync_var = tk.IntVar(value=int(detect_consensus_value()))

flags_frame = tk.Frame(settings_tab)
flags_frame.pack(padx=10, pady=(0, 5), fill="x")

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

# 3-й столбец можно оставить пустым
flags_frame.grid_columnconfigure(0, weight=1)
flags_frame.grid_columnconfigure(1, weight=1)
flags_frame.grid_columnconfigure(2, weight=1)

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
            messagebox.showerror("Ошибка", f"Не удалось сохранить wincash.ini:\n{e}")
    
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
            messagebox.showerror("Ошибка", f"Не удалось сохранить RKEEPER.INI:\n{e}")

def apply_network_ids():
    task_id = task_id_var.get().strip()
    if not task_id:
        messagebox.showwarning("Предупреждение", "Сначала выберите или сохраните задачу!")
        return

    station_value = station_var.get().strip()
    server_value = server_var.get().strip()

    data = load_data()
    tasks = data.get("tasks", {})

    if task_id not in tasks:
        messagebox.showwarning("Предупреждение", f"Задача {task_id} не найдена в EngiHelp_data.json")
        return

    # Обновляем ini_settings внутри задачи
    if "ini_settings" not in tasks[task_id]:
        tasks[task_id]["ini_settings"] = {}

    tasks[task_id]["ini_settings"]["Station"] = station_value
    tasks[task_id]["ini_settings"]["Server"] = server_value

    # Если хотите, чтобы в json всегда были актуальные значения в самой задаче
    data["tasks"] = tasks
    save_data(data)

    # Дополнительно применяем в реальные ini-файлы
    save_wincash_params()

    messagebox.showinfo("Успех", f"Данные сохранены для задачи {task_id}")

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
                messagebox.showerror("Ошибка", f"Не удалось скопировать {f}:\n{e}")
    if copied:
        messagebox.showinfo("Файлы скопированы", f"Скопированы из bin\\win\\ini:\n{', '.join(copied)}")
    elif not missing:
        messagebox.showinfo("Все файлы на месте", "Все необходимые INI-файлы уже присутствуют.")
    else:
        messagebox.showwarning("Нет файлов", "Отсутствующие файлы не найдены даже в bin\\win\\ini.")

def on_check_with_message():
    found, missing = check_files()

    if missing:  # не исключаем rk7man.ini
        if messagebox.askyesno("Внимание", f"Файлы не найдены: {', '.join(missing)}\nДобавить из папки ini?"):
            copy_missing_ini_files()
            on_check()
            update_ini_info_by_priority()
    else:
        messagebox.showinfo("Успех", "Все необходимые файлы найдены.")

def show_product_folders():
    product_root = find_product_root(path_var.get())
    if not product_root:
        messagebox.showwarning("Ошибка", "Корневая папка продукта не определена.")
        return
    
    try:
        items = os.listdir(product_root)
        folders = [name for name in items if os.path.isdir(os.path.join(product_root, name))]
        if folders:
            messagebox.showinfo("Папки в корне продукта", "\n".join(folders))
        else:
            messagebox.showinfo("Папки в корне продукта", "Папки не найдены.")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось получить список папок:\n{e}")

# ======================= Панель с кнопками "Проверить файлы", "Показать папки" и "Clear Base" =======================
check_folder_frame = tk.Frame(settings_tab)
check_folder_frame.pack(padx=10, pady=10, anchor="w", fill="x")

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
                messagebox.showwarning("Ошибка", "Не удалось определить версию на GitHub.")
            return
        remote_version = f"v{match.group(1)}"
        current_version = version.parse(SCRIPT_VERSION.lstrip('v'))
        remote_version = version.parse(remote_version.lstrip('v'))

        if remote_version <= current_version:
            if not silent:
                messagebox.showinfo("Актуальная версия", f"Установлена последняя версия: {SCRIPT_VERSION}")
            return

        if not messagebox.askyesno("Обновление", f"Доступна новая версия: {remote_version}\nОбновить сейчас?"):
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
            messagebox.showerror("Ошибка", f"Не удалось обновить:\n{e}")

# Info tab
info_tab = tk.Frame(notebook)
notebook.add(info_tab, text="О программе")

info_label = tk.Label(info_tab, text=f"{DESCRIPTION}\n{AUTHOR}\n{EMAIL}\n{SCRIPT_VERSION}", justify="left", anchor="nw")
info_label.pack(padx=10, pady=10, anchor="nw", fill="both", expand=True)
info_label.bind('<Configure>', lambda e: info_label.config(wraplength=e.width - 20))

tk.Checkbutton(info_tab, text="Проверять обновления при запуске", variable=auto_update_var)\
    .pack(padx=10, pady=(10, 5), anchor="w")

# Обёртка для ручной проверки через кнопку
tk.Button(info_tab, text="Проверить обновление", command=lambda: check_for_updates(silent=False))\
    .pack(padx=10, pady=(0, 10), anchor="w")

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

on_check()
root.deiconify()
root.mainloop()

# pyinstaller --onefile --windowed --icon=".\.ico\иконка EngiHelp.ico" EngiHelp.py
# pyinstaller --onefile --windowed --icon=".\.ico\иконка EngiHelp.ico" --hidden-import=tkinter --clean EngiHelp.py | очищает кэш перед сборкой.