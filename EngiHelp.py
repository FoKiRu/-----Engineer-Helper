import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
import re
import shutil
import traceback
import json
from collections import Counter
from pathlib import Path

# ======================= Константы и настройки =======================
SCRIPT_VERSION = "v0.1.12"
AUTHOR = "Автор: Кирилл Рутенко"
DESCRIPTION = "Описание: Скрипт для изменения параметров UseDBSync и UseSQL."
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # путь к скрипту
CONFIG_FILE = "config.json"


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
print("📁 Текущая рабочая директория:", os.getcwd())
print("📄 Ожидаемый путь к config.json:", os.path.abspath("config.json"))
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

FILES = ["RKEEPER.INI", "wincash.ini", "rk7srv.INI"]

ini_paths = load_config_paths()
ini_path = ini_paths[0] if ini_paths else ""
INI_FILE_USESQL=os.path.join(ini_path, "rk7srv.INI")

# ======================= Определение корня продукта =======================
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
root.geometry("460x280")

# Центрирование окна
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
cursor_x = root.winfo_pointerx()
cursor_y = root.winfo_pointery()
x = max(0, min(screen_width - 460, cursor_x - 230))
y = max(0, min(screen_height - 280, cursor_y - 140))
root.geometry(f"460x280+{x}+{y}")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

settings_tab = tk.Frame(notebook)
notebook.add(settings_tab, text="Параметры")

# Выбор пути
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

def apply_path():
    global ini_path, INI_FILE_USESQL
    ini_path = path_var.get()
    INI_FILE_USESQL = os.path.join(ini_path, "rk7srv.INI")
    save_config_path(ini_path)
    on_check()

tk.Button(settings_tab, text="Сохранить путь", command=apply_path).pack(padx=10, pady=(5, 10), anchor="w")

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

tk.Button(settings_tab, text="Показать папки продукта", command=show_product_folders).pack(padx=10, pady=(0, 10), anchor="w")

# Переключатели
usedbsync_var = tk.IntVar(value=int(detect_consensus_value()))
usesql_var = tk.IntVar(value=int(get_usesql_value()))

usedbsync_cb = tk.Checkbutton(settings_tab, variable=usedbsync_var, text="UseDBSync", command=toggle_usedbsync, anchor="w", width=20, justify='left')
usedbsync_cb.pack(padx=10, pady=(0, 5), anchor='w')

usesql_cb = tk.Checkbutton(settings_tab, variable=usesql_var, text="UseSQL", command=toggle_usesql, anchor="w", width=20, justify='left')
usesql_cb.pack(padx=10, pady=(0, 5), anchor='w')

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
info_label = tk.Label(info_tab, text=f"{DESCRIPTION}\n{AUTHOR}\n{SCRIPT_VERSION}", justify="left", anchor="nw")
info_label.pack(padx=10, pady=10, anchor="nw", fill="both", expand=True)
info_label.bind('<Configure>', lambda e: info_label.config(wraplength=e.width - 20))

on_check()
root.mainloop()
