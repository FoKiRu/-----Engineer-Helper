# ======================= Импорты =======================
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from pathlib import Path
from collections import Counter
from tkinter import messagebox
import os
import re
import shutil
import traceback
import json
import psutil
import subprocess
import time

# ======================= Константы и настройки =======================
SCRIPT_VERSION = "v0.4.20"
AUTHOR = "Автор: Кирилл Рутенко"
EMAIL = "Эл. почта: xkiladx@gmail.com"
DESCRIPTION = (
    "EngiHelp — инструмент для работы с INI-файлами R-Keeper:\n"
    "управление UseDBSync/UseSQL, запуск процессов, мультиподдержка версий,\n"
    "удобный выбор пути и конфигурация через config.json."
)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # путь к скрипту
CONFIG_FILE = "config.json"
FILES = ["RKEEPER.INI", "wincash.ini", "rk7srv.INI"]

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
    paths = load_config_paths()
    if new_path in paths:
        paths.remove(new_path)
    paths.insert(0, new_path)
    paths = paths[:3]

    config = {f"ini_dir{i}": path for i, path in enumerate(paths)}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

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
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='cp1251') as file:
                lines = file.readlines()
        updated = False
        with open(filepath, 'w', encoding='cp1251') as file:
            for line in lines:
                if re.match(fr'^\s*{key}\s*=.*', line, re.IGNORECASE):
                    file.write(f"{key}={value}\n")
                    updated = True
                else:
                    file.write(line)
            if not updated:
                file.write(f"\n{key}={value}\n")
        return True
    except Exception as e:
        print(f"[ОШИБКА] {filepath}: {e}")
        traceback.print_exc()
        return False

def check_files():
    found, missing = [], []
    for filename in FILES:
        full_path = os.path.join(ini_path, filename)
        if os.path.isfile(full_path):
            found.append(filename)
        else:
            missing.append(filename)
    return found, missing

def on_check():
    found, missing = check_files()
    if missing:
        usedbsync_cb.config(state="disabled", fg="gray")
        usesql_cb.config(state="disabled", fg="gray")
        return False
    else:
        usedbsync_cb.config(state="normal", fg="black")
        usesql_cb.config(state="normal", fg="black")
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

# === GUI ===
root = tk.Tk()
root.title("EngiHelp")
root.geometry("460x440")

# Центрирование окна
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
cursor_x = root.winfo_pointerx()
cursor_y = root.winfo_pointery()
x = max(0, min(screen_width - 460, cursor_x - 230))
y = max(0, min(screen_height - 440, cursor_y - 140))
root.geometry(f"460x440+{x}+{y}")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

settings_tab = tk.Frame(notebook)
notebook.add(settings_tab, text="Параметры")

# Выбор пути
path_frame = tk.Frame(settings_tab)
path_frame.pack(fill="x", padx=10, pady=(10, 0))
tk.Label(path_frame, text="Путь к INI-файлам:").pack(anchor="w")
path_var = tk.StringVar()
ini_paths = load_config_paths()
if ini_paths:
    path_var.set(ini_paths[0])

path_entry = ttk.Combobox(path_frame, textvariable=path_var, values=ini_paths)
path_entry.pack(side="left", fill="x", expand=True)


def browse_path():
    selected = filedialog.askdirectory()
    if selected:
        product_root = find_product_root(selected)
        if product_root:
            bin_win_path = os.path.join(product_root, "bin", "win")
            path_var.set(bin_win_path)
            apply_path()
        else:
            messagebox.showerror("Ошибка", "Выбран некорректный путь.\nТребуется папка, содержащая bin/win с INI-файлами.")

tk.Button(path_frame, text="Обзор", command=browse_path).pack(side="left", padx=5)

def update_wincash_info():
    win_ini = os.path.join(ini_path, "wincash.ini")
    station = ""
    server = ""

    if not os.path.isfile(win_ini):
        print(f"[!] Файл не найден: {win_ini}")
        return

    try:
        try:
            with open(win_ini, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(win_ini, "r", encoding="cp1251") as f:
                lines = f.readlines()

        for line in lines:
            line = line.strip()
            # Удаляем пробелы по краям ключей, и разделяем по первому "="
            if "=" in line:
                key, value = map(str.strip, line.split("=", 1))
                key_lower = key.lower()
                if key_lower == "station":
                    station = value
                elif key_lower == "server":
                    server = value

    except Exception as e:
        print(f"[!] Ошибка при чтении wincash.ini: {e}")
        return

    if station:
        station_var.set(station)
    if server:
        server_var.set(server)


def apply_path(event=None):
    global ini_path, INI_FILE_USESQL
    ini_path = path_var.get()
    INI_FILE_USESQL = os.path.join(ini_path, "rk7srv.INI")

    if not os.path.isdir(ini_path):
        messagebox.showerror("Ошибка", f"Путь не найден:\n{ini_path}")
        return

    save_config_path(ini_path)
    on_check()
    update_wincash_info()

path_entry.bind("<<ComboboxSelected>>", apply_path) # Обновление после выбора пути из списка
#tk.Button(settings_tab, text="Сохранить путь", command=apply_path).pack(padx=10, pady=(5, 10), anchor="w")

def show_product_folders():
    product_root = find_product_root(path_var.get())
    if not product_root:
        messagebox.showwarning("Ошибка", "Корневая папка продукта не определенна.")
        return
    
    try:
        items= os.listdir(product_root)
        folders = [name for name in items if os.path.isdir(os.path.join(product_root, name))]
        if folders:
            messagebox.showinfo("Папки в корне продукта", "\n".join(folders))
        else:
            messagebox.showinfo("Папки в корне продукта", "Папки не найдены.")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось получить список папок:\n{e}")

tk.Button(settings_tab, text="Показать папки", command=show_product_folders).pack(padx=10, pady=(0, 10), anchor="w")

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
    bat_path = os.path.join(ini_path, "wincash.bat")
    if not os.path.isfile(bat_path):
        messagebox.showerror("Ошибка", f"Файл не найден:\n{bat_path}")
        return
    try:
        os.startfile(bat_path)
    except Exception as e:
        messagebox.showerror("Ошибка запуска", str(e))

def run_refsrv_and_rk7man():
    run_or_restart_process("refsrv.exe")
    time.sleep(1.5)
    run_rk7man()

# ======================= Запуск MidServ + WinCash =======================
def run_midserv_and_wincash():
    run_or_restart_process("midserv.exe")
    run_wincash_bat()


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
tk.Button(col1, text="Refsrv + RK7man", command=run_refsrv_and_rk7man, width=22)\
    .pack(anchor="w", pady=(0, 4))
tk.Button(col2, text="MidServ + WinCash", command=run_midserv_and_wincash, width=22)\
    .pack(anchor="w", pady=(0, 4))

# Строка 1: одиночные кнопки
tk.Button(col1, text="Refsrv", command=lambda: run_or_restart_process("refsrv.exe"), width=22)\
    .pack(anchor="w", pady=2)
tk.Button(col1, text="RK7man", command=run_rk7man, width=22)\
    .pack(anchor="w", pady=2)

# Строка 2
tk.Button(col2, text="MidServ", command=lambda: run_or_restart_process("midserv.exe"), width=22)\
    .pack(anchor="w", pady=2)
tk.Button(col2, text="WinCash", command=run_wincash_bat, width=22)\
    .pack(anchor="w", pady=2)



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
    if not os.path.isfile(wincash_path):
        messagebox.showerror("Ошибка", "Файл wincash.ini не найден.")
        return
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
            new_lines.append(f"Server ={server_var.get()}\n")
        else:
            new_lines.append(line)

    try:
        with open(wincash_path, 'w', encoding='cp1251') as file:
            file.writelines(new_lines)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")

# === UI ===
info_frame = tk.LabelFrame(settings_tab, text="wincash.ini параметры")
info_frame.pack(padx=10, pady=(5, 10), fill="x")

tk.Label(info_frame, text="STATION:").grid(row=0, column=0, sticky="w")
tk.Entry(info_frame, textvariable=station_var).grid(row=0, column=1, sticky="ew", padx=5)

tk.Label(info_frame, text="Server:").grid(row=1, column=0, sticky="w")
tk.Entry(info_frame, textvariable=server_var).grid(row=1, column=1, sticky="ew", padx=5)


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

def on_check_with_message():
    result = on_check()
    if result:
        messagebox.showinfo("Успех", "Все необходимые файлы найдены.")
    else:
        messagebox.showwarning("Внимание", f"Файлы не найдены: {', '.join(check_files()[1])}")


check_btn = tk.Button(settings_tab, text="Проверить файлы", command=on_check_with_message)
check_btn.pack(padx=10, pady=10, anchor="w")
create_tooltip(check_btn, "Проверка наличия INI-файлов и обновление состояния параметров.")


# Info tab
info_tab = tk.Frame(notebook)
notebook.add(info_tab, text="О программе")
info_label = tk.Label(info_tab, text=f"{DESCRIPTION}\n{AUTHOR}\n{EMAIL}\n{SCRIPT_VERSION}", justify="left", anchor="nw")
info_label.pack(padx=10, pady=10, anchor="nw", fill="both", expand=True)
info_label.bind('<Configure>', lambda e: info_label.config(wraplength=e.width - 20))

on_check()
root.mainloop()
