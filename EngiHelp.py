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

# ======================= Константы и настройки =======================
SCRIPT_VERSION = "v0.9.2"
AUTHOR = "Автор: Кирилл Рутенко"
EMAIL = "Эл. почта: xkiladx@gmail.com"
DESCRIPTION = (
    "EngiHelp — инструмент для работы с INI-файлами R-Keeper.\n"
    "Возможности:\n"
    "- Управление UseDBSync и UseSQL в INI-файлах\n"
    "- Автоматическая синхронизация параметров Station и Server из wincash.ini и RKEEPER.INI с учётом времени изменений\n"
    "- Проверка и копирование необходимых INI-файлов\n"
    "- Удобный выбор и сохранение пути к каталогу R-Keeper\n"
    "- Запуск и остановка ключевых сервисов (refsrv.exe, midserv.exe, rk7man.exe, wincash.bat и др.)\n"
    "- Очистка папки base с сохранением важных файлов\n"
    "- Поддержка мультиконфигураций через EngiHelp_config.json\n"
    "- Автообновление интерфейса по текущим файлам конфигурации\n"
)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # путь к скрипту
CONFIG_FILE = os.path.join(str(Path.home()), "Documents", "EngiHelp_config.json")
# Если файл конфигурации отсутствует — создаём с пустой структурой
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"auto_update": True}, f, indent=4, ensure_ascii=False)
FILES = ["RKEEPER.INI", "wincash.ini", "rk7srv.INI", "rk7man.ini"]

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
WINDOW_HEIGHT = 444
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
def load_config_paths():
    if not os.path.exists(CONFIG_FILE):
        return [], False

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            return [], False
        
    auto_update = config.get("auto_update", False)
    paths = [
        v for k, v in sorted(config.items())
        if k.startswith("ini_dir") and isinstance(v, str) and v.strip()
    ]
    return paths, auto_update

"""
print("Текущая рабочая директория:", os.getcwd())
print("Ожидаемый путь к EngiHelp_config.json:", os.path.abspath("cEngiHelp_config.json"))
"""

def save_config_path(new_path):
    # Заменяем все обратные слэши на прямые
    new_path = new_path.replace("\\", "/")
    
    # Загружаем текущие пути и обновляем их
    paths, _ = load_config_paths()
    if new_path in paths:
        paths.remove(new_path)
    paths.insert(0, new_path)
    paths = paths[:3]

    # Формируем конфигурацию с обновленными путями
    config = {f"ini_dir{i}": path for i, path in enumerate(paths)}
    
    # Добавляем флаг автообновления в конфигурацию
    config["auto_update"] = auto_update_var.get()

    # Сохраняем конфигурацию в JSON-файл
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    # Обновляем список путей в комбобоксе
    if 'path_entry' in globals():
        path_entry['values'] = paths

# ======================= Вспомогательные функции =======================
def extract_task_id_from_rk7srv_ini(ini_path):
    if not os.path.exists(ini_path):
        return None
    try:
        with open(ini_path, 'r', encoding='cp1251') as file:
            for line in file:
                line = line.strip()
                if line.lower().startswith("udbfile") or line.lower().startswith("workmodules"):
                    match = re.search(r'base_(\d+)', line)
                    if match:
                        return match.group(1)
    except Exception as e:
        print(f"Ошибка при чтении rk7srv.INI: {e}")
    return None

# ======================= Определение путей и начальных переменных =======================
ini_paths, auto_update_enabled = load_config_paths()
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
            if re.match(r'^\s*\[DBSYNC\]\s*$', line, re.IGNORECASE):
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
                if re.match(r'^\s*\[DBSYNC\]\s*$', line, re.IGNORECASE):
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

def on_task_selected(event):
    selected_task_id = task_id_var.get()
    if not selected_task_id:
        return

    product_root = find_product_root(path_var.get())
    if not product_root:
        messagebox.showerror("Ошибка", "Не удалось определить корневую папку продукта.")
        return

    tasks_file = os.path.join(str(Path.home()), "Documents", "tasks.json")
    if not os.path.exists(tasks_file):
        return

    try:
        with open(tasks_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось загрузить задачи:\n{e}")
        return

    if selected_task_id not in tasks:
        return

    task_info = tasks[selected_task_id]
    if "ini_settings" not in task_info:
        return

    ini_settings = task_info["ini_settings"]
    ini_path = task_info["ini_path"]

    # Формируем путь к rk7srv.INI один раз
    rk7srv_ini_path = os.path.join(ini_path, "rk7srv.INI")
    if not os.path.exists(rk7srv_ini_path):
        messagebox.showerror("Ошибка", f"Файл rk7srv.INI не найден:\n{rk7srv_ini_path}")
        return

    # Применяем UseDBSync
    if "UseDBSync" in ini_settings:
        for filename, value in ini_settings["UseDBSync"].items():
            #if filename.lower() == "rk7man.ini":
                #continue  # Пропускаем rk7man.ini
            full_path = os.path.join(ini_path, filename)
            if os.path.exists(full_path):
                update_ini_file(full_path, str(value), "UseDBSync")

    # Применяем UseSQL
    if "UseSQL" in ini_settings:
        update_ini_file(rk7srv_ini_path, str(ini_settings["UseSQL"]), "USESQL")

    # Применяем Station и Server
    if "Station" in ini_settings and "Server" in ini_settings:
        station_var.set(ini_settings["Station"])
        server_var.set(ini_settings["Server"])
        save_wincash_params()  # Сохраняем значения в wincash.ini и RKEEPER.INI

    # Получаем путь к base_XXX из tasks.json и обновляем UDBFILE и WorkModules
    base_path = task_info["base_path"]
    base_dir = os.path.basename(base_path)
    update_rk7srv_ini(rk7srv_ini_path, base_dir)

    #messagebox.showinfo("Успех", f"Параметры для задачи {selected_task_id} применены!")

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

    # Проверяем, запущен ли процесс refsrv.exe
    refsrv_running = False
    for proc in psutil.process_iter(['name']):
        if proc.info['name'].lower() == "refsrv.exe":
            refsrv_running = True
            break

    if refsrv_running:
        messagebox.showwarning(
            "Предупреждение",
            "Процесс refsrv.exe запущен и может блокировать файлы.\n"
            "Сначала будет attempted копирование файла rk7.udb для проверки."
        )

    # Пробуем скопировать rk7.udb для проверки блокировки
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
                        time.sleep(1)  # Даем время на завершение процесса
            else:
                return
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось проверить блокировку файлов:\n{e}")
            return

    # Формируем имя для копии папки
    new_base_path = os.path.join(product_root, f"base_{task_id}")
    # Проверяем, существует ли уже папка с таким именем
    if os.path.exists(new_base_path):
        if messagebox.askyesno(
            "Предупреждение",
            f"Папка {new_base_path} уже существует. Перезаписать?"
        ):
            try:
                shutil.rmtree(new_base_path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить существующую папку:\n{e}")
                return
        else:
            return

    # Копируем папку base
    try:
        shutil.copytree(base_path, new_base_path)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось скопировать папку base:\n{e}")
        return
    
    # Собираем параметры INI
    ini_settings = get_ini_settings(path_var.get())

    # Путь к файлу tasks.json в папке "Документы"
    tasks_file = os.path.join(str(Path.home()), "Documents", "tasks.json")
    tasks = {}
    # Загружаем существующие задачи, если файл существует
    if os.path.exists(tasks_file):
        try:
            with open(tasks_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)
        except json.JSONDecodeError:
            tasks = {}

    # Добавляем новую задачу с параметрами INI
    tasks[task_id] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_path": new_base_path,
        "ini_path": path_var.get().replace("\\", "/"),
        "status": "copied",
        "ini_settings": ini_settings  # Сохраняем параметры
    }

    # Перемещаем текущую задачу в начало словаря
    tasks = {task_id: tasks[task_id], **{k: v for k, v in tasks.items() if k != task_id}}

    # Сохраняем обновлённый список задач
    try:
        with open(tasks_file, "w", encoding="utf-8") as f:
            # json.dump({"auto_update": True}, f, indent=4, ensure_ascii=False)
            json.dump(tasks, f, indent=4, ensure_ascii=False)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось сохранить информацию о задаче:\n{e}")
        return

    task_id_combobox['values'] = load_task_ids()
    messagebox.showinfo("Успех", f"Папка base успешно скопирована как {new_base_path}!\nИнформация о задаче сохранена в tasks.json.")
    base_dir = os.path.basename(new_base_path)  # Например, "base_666"
    rk7srv_ini_path = os.path.join(path_var.get(), "rk7srv.INI")
    update_rk7srv_ini(rk7srv_ini_path, base_dir)

# Загрузка номеров задач
def load_task_ids():
    tasks_file = os.path.join(str(Path.home()), "Documents", "tasks.json")
    if not os.path.exists(tasks_file):
        return []

    try:
        with open(tasks_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)
            return list(tasks.keys())
    except Exception:
        return []

def delete_task():
    selected_task_id = task_id_var.get().strip()
    if not selected_task_id:
        messagebox.showwarning("Предупреждение", "Выберите задачу для удаления!")
        return

    tasks_file = os.path.join(str(Path.home()), "Documents", "tasks.json")
    if not os.path.exists(tasks_file):
        messagebox.showwarning("Предупреждение", "Файл с задачами не найден!")
        return

    try:
        with open(tasks_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось загрузить задачи:\n{e}")
        return

    if selected_task_id not in tasks:
        messagebox.showwarning("Предупреждение", f"Задача {selected_task_id} не найдена!")
        return

    if messagebox.askyesno("Подтверждение", f"Удалить задачу {selected_task_id}?"):
        del tasks[selected_task_id]
        try:
            with open(tasks_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=4, ensure_ascii=False)
            task_id_combobox['values'] = load_task_ids()
            task_id_var.set("")
            messagebox.showinfo("Успех", f"Задача {selected_task_id} удалена!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось удалить задачу:\n{e}")


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
ini_paths, auto_update_enabled = load_config_paths()
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

def apply_path(event=None):
    global ini_path, INI_FILE_USESQL
    ini_path = path_var.get()
    INI_FILE_USESQL = os.path.join(ini_path, "rk7srv.INI")
    if not os.path.isdir(ini_path):
        messagebox.showerror("Ошибка", f"Путь не найден:\n{ini_path}")
        return

    save_config_path(ini_path)
    load_wincash_params() # Сначала считываем значения из файлов
    on_check()
    # update_ini_info_by_priority() Данный вызов создает баг с [Config] STATION= в wincash.ini
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
def delete_midbase_files():
    parent_path = os.path.dirname(os.path.dirname(ini_path))
    midbase_path = os.path.normpath(os.path.join(parent_path, "MIDBASE")).replace("\\", "/")

    if not os.path.isdir(midbase_path):
        messagebox.showerror("Ошибка", f"Папка MIDBASE не найдена:\n{midbase_path}")
        return

    confirm_deletion_midbase(midbase_path)

def confirm_deletion_midbase(midbase_path):
    win = tk.Toplevel(root)
    win.title("Подтверждение удаления")
    win.transient(root)
    win.grab_set()
    win.focus_force()

    if icon_path:
        win.iconbitmap(icon_path)

    win.update_idletasks()
    w, h = 360, 122
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

    msg = "Вы действительно хотите удалить всё содержимое папки MIDBASE?"
    tk.Label(win, text=msg, justify="left", wraplength=w-20).pack(padx=10, pady=(10, 5))

    do_backup_var = tk.BooleanVar(value=False)
    tk.Checkbutton(win, text="Создать резервную копию", variable=do_backup_var).pack(anchor="w", padx=12, pady=(0, 5))

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=5)

    def on_delete():
        win.destroy()
        if do_backup_var.get():
            proceed_with_backup_and_deletion(midbase_path, [])
        else:
            proceed_with_deletion([], midbase_path, backup_path=None)

    tk.Button(btn_frame, text="Удалить", command=on_delete).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=win.destroy).pack(side="left", padx=5)

# ======================= Удаление base =======================
def delete_unwanted_files():
    # Получаем родительскую директорию для пути, исключая папку bin/win
    parent_path = os.path.dirname(os.path.dirname(ini_path))  # Убираем bin/win
    # Формируем и нормализуем путь к папке base, заменяем обратные слэши на прямые
    base_path = os.path.normpath(os.path.join(parent_path, "base")).replace("\\", "/")

    if not os.path.isdir(base_path):
        messagebox.showerror("Ошибка", f"Папка base не найдена:\n{base_path}")
        return

    # Список файлов и папок, которые НЕ должны быть удалены
    protected_files = [
        "drvlocalize", "workmods", "dealerpresets.udb",
        "ral.dat", "rk7.udb", "upgradedevices.abs", "upgradepresets.abs"
    ]

    confirm_deletion_with_options(
        protected_files,
        callback_proceed=lambda: proceed_with_backup_and_deletion(base_path, protected_files)
    )

# Окно с предупреждением и исключением
def confirm_deletion_with_options(protected_files, callback_proceed):
    win = tk.Toplevel(root)
    win.title("Подтверждение удаления")
    win.transient(root)
    win.grab_set()
    win.focus_force()

    if icon_path:
        win.iconbitmap(icon_path)

    win.update_idletasks()
    w = 360
    h = 170
    x = root.winfo_x() + (root.winfo_width() - w) // 2
    y = root.winfo_y() + (root.winfo_height() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

    msg = (
        "Вы действительно хотите очистить папку Base и оставить следующие папки и файлы:\n\n"
        + ", ".join(protected_files)
    )
    tk.Label(win, text=msg, justify="left", wraplength=w-20).pack(padx=10, pady=(10, 5))

    do_backup_var = tk.BooleanVar(value=False)
    tk.Checkbutton(win, text="Создать резервную копию", variable=do_backup_var).pack(anchor="w", padx=12, pady=(0, 5))

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=5)

    def on_delete():
        win.destroy()
        if do_backup_var.get():
            callback_proceed()  # с резервной копией
        else:
            base_path = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(ini_path)), "base")).replace("\\", "/")
            proceed_with_deletion(protected_files, base_path, backup_path=None)  # без резервной копии

    tk.Button(btn_frame, text="Удалить", command=on_delete).pack(side="left", padx=5)
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

usesql_cb = tk.Checkbutton(settings_tab, variable=usesql_var, text="UseSQL", command=toggle_usesql, anchor="w", width=20, justify='left')
usesql_cb.pack(padx=10, pady=(0, 5), anchor='w')

usedbsync_cb = tk.Checkbutton(settings_tab, variable=usedbsync_var, text="UseDBSync", command=toggle_usedbsync, anchor="w", width=20, justify='left')
usedbsync_cb.pack(padx=10, pady=(0, 5), anchor='w')

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



# === UI ===
info_frame = tk.LabelFrame(settings_tab, text="Сетевые ID")
info_frame.pack(padx=10, pady=(5, 10), fill="x")

tk.Label(info_frame, text="MID:").grid(row=0, column=0, sticky="w")
tk.Entry(info_frame, textvariable=server_var).grid(row=0, column=1, sticky="ew", padx=5)

tk.Label(info_frame, text="CASH:").grid(row=1, column=0, sticky="w")
tk.Entry(info_frame, textvariable=station_var).grid(row=1, column=1, sticky="ew", padx=5)

# Автосохранение при любом изменении
station_var.trace_add("write", lambda *args: save_wincash_params())
server_var.trace_add("write", lambda *args: save_wincash_params())

info_frame.grid_columnconfigure(1, weight=1)


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

# Первый ряд: "Проверить файлы", "Clear MIDBASE", "Clear Base"
check_btn = tk.Button(check_folder_frame, text="Проверить файлы", command=on_check_with_message)
check_btn.grid(row=0, column=0, padx=5, sticky="ew")

show_folders_btn = tk.Button(check_folder_frame, text="Clear MIDBASE", command=delete_midbase_files)
show_folders_btn.grid(row=0, column=1, padx=5, sticky="ew")

clear_base_btn = tk.Button(check_folder_frame, text="Clear Base", command=delete_unwanted_files)
clear_base_btn.grid(row=0, column=2, padx=5, sticky="ew")

# Второй ряд: "Удалить задачу" (под "Проверить файлы")
delete_task_btn = tk.Button(check_folder_frame, text="Удалить задачу", command=delete_task)
delete_task_btn.grid(row=1, column=0, padx=5, sticky="ew", pady=(5, 0))

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