import tkinter as tk
from tkinter import messagebox, ttk
import os
import re
import shutil
import traceback
from collections import Counter

SCRIPT_VERSION = "v0.1.6"
AUTHOR = "Автор: Кирилл Рутенко"
DESCRIPTION = "Описание: Скрипт для изменения параметров UseDBSync и UseSQL."

FILES = ["RKEEPER.INI", "wincash.ini", "rk7srv.INI"]
INI_FILE_USESQL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rk7srv.INI")


def get_usedbsync_values():
    base_path = os.path.dirname(os.path.abspath(__file__))
    values = {}
    for filename in FILES:
        path = os.path.join(base_path, filename)
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
            full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
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
    base_path = os.path.dirname(os.path.abspath(__file__))
    found, missing = [], []
    for filename in FILES:
        full_path = os.path.join(base_path, filename)
        if os.path.isfile(full_path):
            found.append(filename)
        else:
            missing.append(filename)
    return found, missing


def on_check():
    found, missing = check_files()
    if missing:
        messagebox.showwarning("Внимание", f"Файлы не найдены: {', '.join(missing)}")
    else:
        # Обновление значения чекбоксов
        usedbsync_var.set(int(detect_consensus_value()))
        usesql_var.set(int(get_usesql_value()))
        messagebox.showinfo("Успех", "Все необходимые файлы найдены.")

def toggle_usedbsync():
    value = "1" if usedbsync_var.get() else "0"
    run_update(value)


def toggle_usesql():
    value = "1" if usesql_var.get() else "0"
    run_update_usesql_value(value)


def run_update(value):
    base_path = os.path.dirname(os.path.abspath(__file__))
    failed = []
    for filename in FILES:
        full_path = os.path.join(base_path, filename)
        success = update_ini_file(full_path, value, "UseDBSync")
        if not success:
            failed.append(filename)
    if failed:
        messagebox.showwarning("Внимание", f"Не удалось обновить: {', '.join(failed)}")


def run_update_usesql_value(value):
    success = update_ini_file(INI_FILE_USESQL, value, "UseSQL")
    if not success:
        messagebox.showwarning("Ошибка", "Не удалось обновить UseSQL в rk7srv.INI")
        


# GUI
root = tk.Tk()
root.title("EngiHelp")
root.geometry("400x240")  # уменьшенное окно

# Центрирование окна по курсору
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
cursor_x = root.winfo_pointerx()
cursor_y = root.winfo_pointery()
window_width = 400
window_height = 240
x = cursor_x - window_width // 2
y = cursor_y - window_height // 2
x = max(0, min(screen_width - window_width, x))
y = max(0, min(screen_height - window_height, y))
root.geometry(f"{window_width}x{window_height}+{x}+{y}")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

# Вкладка 1 — Настройки
settings_tab = tk.Frame(notebook)
notebook.add(settings_tab, text="Параметры")

usedbsync_var = tk.IntVar(value=int(detect_consensus_value()))
usesql_var = tk.IntVar(value=int(get_usesql_value()))

cb1 = tk.Checkbutton(settings_tab, variable=usedbsync_var, text="UseDBSync", command=toggle_usedbsync, anchor="w", width=20, justify="left")
cb1.pack(padx=10, pady=(20, 5), anchor="w")

cb2 = tk.Checkbutton(settings_tab, variable=usesql_var, text="UseSQL", command=toggle_usesql, anchor="w", width=20, justify="left")
cb2.pack(padx=10, pady=(0, 10), anchor="w")

check_btn = tk.Button(settings_tab, text="Проверить файлы", command=on_check, justify="left", anchor="nw")
check_btn.pack(padx=10, pady=10, anchor="nw", expand=True)

# Вкладка 2 — Информация
info_tab = tk.Frame(notebook)
notebook.add(info_tab, text="О программе")

info_label = tk.Label(info_tab, text=f"{DESCRIPTION}\n{AUTHOR}\n{SCRIPT_VERSION}", justify="left", anchor="nw")
info_label.pack(padx=10, pady=10, anchor="nw", fill="both", expand=True)

# Обновление переноса текста при изменении размера
info_label.bind('<Configure>', lambda e: info_label.config(wraplength=e.width - 20))

root.mainloop()