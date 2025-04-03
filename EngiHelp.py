import tkinter as tk
from tkinter import messagebox
import os
import re
import shutil
import traceback
from collections import Counter

SCRIPT_VERSION = "v0.1.2"
AUTHOR = "Автор: Кирилл Рутенко"
DESCRIPTION = "Описание: Скрипт для изменения параметров UseDBSync и USESQL."

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
        return ""
    counts = Counter(values.values())
    consensus = counts.most_common(1)[0][0]
    for filename, value in values.items():
        if value != consensus:
            full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
            update_ini_file(full_path, consensus, "UseDBSync")
    return consensus


def get_usesql_value():
    if not os.path.isfile(INI_FILE_USESQL):
        return ""
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
    return ""


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
        messagebox.showinfo("Успех", "Все необходимые файлы найдены.")


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
    else:
        messagebox.showinfo("Успех", "Параметр UseDBSync успешно обновлён во всех файлах.")


def run_update_usesql():
    value = usesql_var.get()
    if value not in ("0", "1"):
        messagebox.showerror("Ошибка", "Введите 0 или 1 для USESQL")
        return
    success = update_ini_file(INI_FILE_USESQL, value, "USESQL")
    if success:
        messagebox.showinfo("Успех", "Параметр USESQL обновлён в rk7srv.INI")
    else:
        messagebox.showwarning("Ошибка", "Не удалось обновить USESQL в rk7srv.INI")


def on_submit():
    value = value_var.get()
    if value not in ("0", "1"):
        messagebox.showerror("Ошибка", "Введите 0 или 1")
    else:
        run_update(value)


# GUI
root = tk.Tk()
root.title("UseDBSync Configurator")
root.geometry("600x320")

# Центрирование окна по курсору
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
cursor_x = root.winfo_pointerx()
cursor_y = root.winfo_pointery()
window_width = 600
window_height = 320
x = cursor_x - window_width // 2
y = cursor_y - window_height // 2
x = max(0, min(screen_width - window_width, x))
y = max(0, min(screen_height - window_height, y))
root.geometry(f"{window_width}x{window_height}+{x}+{y}")

main_frame = tk.Frame(root)
main_frame.pack(pady=10, padx=10, fill="both", expand=True)

left_frame = tk.Frame(main_frame)
left_frame.pack(side="left", expand=True, anchor="n")

right_frame = tk.Frame(main_frame)
right_frame.pack(side="right", expand=True, anchor="n")

# Левая колонка (UseDBSync)
current_value = detect_consensus_value()
value_var = tk.StringVar(value=current_value)
tk.Label(left_frame, text="Введите 0 или 1 для UseDBSync:").pack()
tk.Entry(left_frame, textvariable=value_var, width=5, justify="center").pack(pady=5)
tk.Button(left_frame, text="Применить UseDBSync", command=on_submit).pack(pady=5)

# Правая колонка (USESQL)
current_usesql = get_usesql_value()
usesql_var = tk.StringVar(value=current_usesql)
tk.Label(right_frame, text="Введите 0 или 1 для USESQL:").pack()
tk.Entry(right_frame, textvariable=usesql_var, width=5, justify="center").pack(pady=5)
tk.Button(right_frame, text="Применить USESQL", command=run_update_usesql).pack(pady=5)

# Нижняя панель с информацией и проверкой
bottom_frame = tk.Frame(root)
bottom_frame.pack(fill="x", side="bottom", padx=10, pady=5)

check_btn = tk.Button(bottom_frame, text="Проверить наличие файлов", command=on_check)
check_btn.pack(side="left")

info_label = tk.Label(bottom_frame, text=f"{DESCRIPTION}\n{AUTHOR}\n{SCRIPT_VERSION}", justify="left")
info_label.pack(side="right")

root.mainloop()