# ======================= Импорты =======================
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from pathlib import Path
from collections import Counter
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
from PyInstaller.utils.hooks import collect_data_files
from functools import partial

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

# ======================= Константы и настройки =======================
SCRIPT_VERSION = "v0.7.7"
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
    "- Поддержка мультиконфигураций через config.json\n"
    "- Автообновление интерфейса по текущим файлам конфигурации\n"
)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # путь к скрипту
CONFIG_FILE = "config.json"
FILES = ["RKEEPER.INI", "wincash.ini", "rk7srv.INI", "rk7man.ini"]

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
WINDOW_WIDTH = 389
WINDOW_HEIGHT = 465
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

# =================== Работа с config.json (мульти-пути) =============
def load_config_paths():
    if not os.path.exists(CONFIG_FILE):
        return []

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            return []

    return [v for k, v in sorted(config.items()) if k.startswith("ini_dir")]

"""
print("Текущая рабочая директория:", os.getcwd())
print("Ожидаемый путь к config.json:", os.path.abspath("config.json"))
"""

def save_config_path(new_path):
    # Заменяем все обратные слэши на прямые
    new_path = new_path.replace("\\", "/")
    
    # Загружаем текущие пути и обновляем их
    paths = load_config_paths()
    if new_path in paths:
        paths.remove(new_path)
    paths.insert(0, new_path)
    paths = paths[:3]

    # Формируем конфигурацию с обновленными путями
    config = {f"ini_dir{i}": path for i, path in enumerate(paths)}
    
    # Сохраняем конфигурацию в JSON-файл
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    # Обновляем список путей в комбобоксе
    if 'path_entry' in globals():
        path_entry['values'] = paths


# ======================= Определение путей и начальных переменных =======================
ini_paths = load_config_paths()
ini_path = ini_paths[0] if ini_paths else ""
INI_FILE_USESQL=os.path.join(ini_path, "rk7srv.INI")

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
            for line in lines:
                match = re.match(r'^\s*UseDBSync\s*=\s*(\d+)', line, re.IGNORECASE)
                if match:
                    values[filename] = match.group(1)
                    break
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
        shutil.copy2(filepath, filepath + ".bak")

        filename = os.path.basename(filepath).lower()

        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='cp1251') as file:
                lines = file.readlines()

        updated = False
        new_lines = []
        key_found = False

        for line in lines:
            if re.match(fr'^\s*{key}\s*=.*', line, re.IGNORECASE):
                new_lines.append(f"{key}={value}\n")
                key_found = True
                updated = True
            else:
                new_lines.append(line)

        # если параметр не найден
        if not key_found:
            if filename == "rk7man.ini":
                # ничего не добавляем
                pass
            else:
                # добавляем секцию и параметр
                new_lines.append("\n[DBSYNC]\n")
                new_lines.append(f"{key}={value}\n")
                updated = True

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
    for filename in FILES:
        if filename.lower() == "rk7man.ini":
            continue
        full_path = os.path.join(ini_path, filename)
        success = update_ini_file(full_path, value, "UseDBSync")
        if not success:
            failed.append(filename)
    if failed:
        messagebox.showwarning("Внимание", f"Не удалось обновить: {', '.join(failed)}")

def run_update_usesql_value(value):
    success = update_ini_file(INI_FILE_USESQL, value, "UseSQL")
    if not success:
        messagebox.showwarning("Ошибка", "Не удалось обновить UseSQL в rk7srv.INI")

# Выбор пути
path_frame = tk.Frame(settings_tab)
path_frame.pack(fill="x", padx=10, pady=(10, 0))
tk.Label(path_frame, text="Путь к RK7:").pack(anchor="w")
path_var = tk.StringVar()
ini_paths = load_config_paths()
if ini_paths:
    path_var.set(ini_paths[0])

# Автосохранение вручную введённого пути
path_var.trace_add("write", lambda *args: save_config_path(path_var.get()))
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

tk.Button(path_frame, text="Обзор", command=browse_path).pack(side="left", padx=5)

# Cинхронизацию параметров из INI-файлов с учётом приоритета по времени изменения.
def update_ini_info_by_priority():
    wincash_path = os.path.join(ini_path, "wincash.ini")
    rkeeper_path = os.path.join(ini_path, "RKEEPER.INI")

    # Если ни один не существует
    if not os.path.isfile(wincash_path) and not os.path.isfile(rkeeper_path):
        return

    # Получаем времена изменения
    wincash_mtime = os.path.getmtime(wincash_path) if os.path.isfile(wincash_path) else 0
    rkeeper_mtime = os.path.getmtime(rkeeper_path) if os.path.isfile(rkeeper_path) else 0

    # Если wincash.ini новее или равен
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
                if key_lower == "station":
                    if value != station_var.get():
                        station_var.set(value)
                elif key_lower == "server":
                    if value != server_var.get():
                        server_var.set(value)
    else:
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
                if value and value != server_var.get():
                    server_var.set(value)
                break

def apply_path(event=None):
    global ini_path, INI_FILE_USESQL
    ini_path = path_var.get()
    INI_FILE_USESQL = os.path.join(ini_path, "rk7srv.INI")

    if not os.path.isdir(ini_path):
        messagebox.showerror("Ошибка", f"Путь не найден:\n{ini_path}")
        return

    save_config_path(ini_path)
    on_check()
    update_ini_info_by_priority()

path_entry.bind("<<ComboboxSelected>>", apply_path) # Обновление после выбора пути из списка

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

def delete_unwanted_files():
    # Получаем родительскую директорию для пути, исключая папку bin/win
    parent_path = os.path.dirname(os.path.dirname(ini_path))  # Убираем bin/win

    # Формируем путь к папке base
    base_path = os.path.join(parent_path, "base")

    # Нормализуем путь и заменяем обратные слэши на прямые
    base_path = os.path.normpath(base_path).replace("\\", "/")

    # Список файлов и папок, которые НЕ должны быть удалены
    protected_files = [
        "drvlocalize",
        "workmods",
        "dealerpresets.udb",
        "ral.dat",
        "rk7.udb",
        "upgradedevices.abs",
        "upgradepresets.abs"
    ]
    
    # Показываем окно подтверждения перед удалением
    if not messagebox.askyesno(
        "Подтверждение удаления",
        f"Вы действительно хотите очистить папку Base и оставить следующие папки и файлы:\n"
        f"{', '.join(protected_files)}?"
    ):
        return  # Если пользователь нажал "Нет", отменяем удаление

    # Перебираем все файлы и папки в папке base
    deleted_items = []
    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)

        # Если это файл, и он не в списке исключений, удаляем его
        if os.path.isfile(item_path) and item not in protected_files:
            try:
                os.remove(item_path)
                deleted_items.append(item)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить файл: {item_path}")
        
        # Если это папка, и она не в списке исключений, удаляем её
        elif os.path.isdir(item_path) and item not in protected_files:
            try:
                shutil.rmtree(item_path)
                deleted_items.append(item)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить папку: {item_path}")

    # Показываем сообщение о том, какие файлы и папки были удалены
    if not deleted_items:
        messagebox.showinfo("Удаление файлов и папок", "Нет элементов для удаления или все элементы защищены.")

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
                new_lines.append(f"STATION={station_var.get()}\n")
            elif line.strip().lower().startswith("server ="):
                new_lines.append(f"Server ={server_value}\n")
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
info_frame = tk.LabelFrame(settings_tab, text="Config's")
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
check_folder_frame.pack(padx=10, pady=10, anchor="w", fill="x")  # Убедимся, что контейнер также расширяется по ширине

# Кнопка для проверки наличия файлов
check_btn = tk.Button(check_folder_frame, text="Проверить файлы", command=on_check_with_message)
check_btn.pack(side="left", padx=5, fill="x", expand=True)  # fill="x" и expand=True для равномерного распределения

# Кнопка для отображения папок
show_folders_btn = tk.Button(check_folder_frame, text="Показать папки", command=show_product_folders)
show_folders_btn.pack(side="left", padx=5, fill="x", expand=True)  # fill="x" и expand=True для равномерного распределения

# Кнопка для удаления файла
clear_base_btn = tk.Button(check_folder_frame, text="Clear Base", command=delete_unwanted_files)
clear_base_btn.pack(side="left", padx=5, fill="x", expand=True)  # fill="x" и expand=True для равномерного распределения

def get_short_path_name(long_path):
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.kernel32.GetShortPathNameW(long_path, buf, 260)
    return buf.value

# Проверка версии
def check_for_updates():
    try:
        url = "https://github.com/FoKiRu/-----Engineer-Helper/raw/main/dist/EngiHelp.exe"
        response = requests.get(url, timeout=10)
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
        messagebox.showerror("Ошибка", f"Не удалось обновить:\n{e}")

# Info tab
info_tab = tk.Frame(notebook)
notebook.add(info_tab, text="О программе")

info_label = tk.Label(info_tab, text=f"{DESCRIPTION}\n{AUTHOR}\n{EMAIL}\n{SCRIPT_VERSION}", justify="left", anchor="nw")
info_label.pack(padx=10, pady=10, anchor="nw", fill="both", expand=True)
info_label.bind('<Configure>', lambda e: info_label.config(wraplength=e.width - 20))

# Кнопка проверки обновления
tk.Button(info_tab, text="Проверить обновление", command=check_for_updates)\
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

on_check()
root.deiconify()
root.mainloop()

# pyinstaller --onefile --windowed --icon="иконка EngiHelp.ico" EngiHelp.py