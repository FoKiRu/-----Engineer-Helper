# ======================= cloud_rk7man.py =======================
# Логика Cloud RK7man

import os
import re
import tempfile
import threading
import subprocess
import time
import webbrowser
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog

import psutil

from .dialogs import _center_window, centered_error, centered_info
from .process_utils import get_process_by_name
from .task_manager import extract_rk_version_from_path
from .data_manager import load_data, save_data
from . import (
    CLOUD_RK7MAN_PATTERN, CLOUD_CONNECTIONS_FILE, MAX_SAVED_CONNECTIONS
)

# ======================= История подключений =======================
# История хранится в EngiHelp_data.json (settings.cloud_connections) и общая
# для всех версий RK. Старый cloud_connections.txt в папке версии подхватывается
# один раз при первом обращении.

def _load_legacy_cloud_connections(ini_path):
    """Читает строки из старого cloud_connections.txt в папке версии RK."""
    if not ini_path:
        return []
    file_path = os.path.join(ini_path, CLOUD_CONNECTIONS_FILE)
    if not os.path.isfile(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

def load_saved_cloud_connections(ini_path=None):
    """Возвращает сохранённые строки подключения (не более MAX_SAVED_CONNECTIONS)."""
    data = load_data()
    connections = data["settings"].get("cloud_connections", [])
    if not connections:
        legacy = _load_legacy_cloud_connections(ini_path)
        if legacy:
            connections = list(dict.fromkeys(legacy))[:MAX_SAVED_CONNECTIONS]
            data["settings"]["cloud_connections"] = connections
            save_data(data)
    return connections[:MAX_SAVED_CONNECTIONS]

def save_cloud_connection(connection_string):
    """Ставит строку подключения первой в историю, убирая дубликат и оставляя 5 последних."""
    data = load_data()
    connections = data["settings"].get("cloud_connections", [])
    connections = [c for c in connections if c != connection_string]
    connections.insert(0, connection_string)
    data["settings"]["cloud_connections"] = connections[:MAX_SAVED_CONNECTIONS]
    save_data(data)

# ======================= Парсинг =======================

def parse_cloud_rk7man_string(raw):
    """Разбирает строку вида RK7SRV_622020001=srv01.rkcloud.ucs.ru:50072.
    Возвращает (server_name, host, port) или None."""
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

# ======================= Генерация конфига =======================

def apply_cloud_rk7man_config(ini_path, server_name, host, port):
    """Читает rk7man.ini, применяет облачные настройки и записывает во временный файл.
    Возвращает (temp_path, None) при успехе или (None, error_message) при ошибке."""
    rk7man_path = os.path.join(ini_path, "rk7man.ini")
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

        cloud_log_dir = os.path.join(ini_path, "Cloud_log")
        os.makedirs(cloud_log_dir, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.ini', prefix='rk7man_cloud_', dir=cloud_log_dir)
        try:
            has_dbsync_section = any(re.match(r'^\s*\[DBSYNC\]', l, re.IGNORECASE) for l in new_lines)
            has_usedbsync = any(re.match(r'^\s*UseDBSync\s*=', l, re.IGNORECASE) for l in new_lines)

            if has_dbsync_section and has_usedbsync:
                final2 = []
                for line in new_lines:
                    if re.match(r'^\s*UseDBSync\s*=', line, re.IGNORECASE):
                        final2.append("UseDBSync=0\n")
                    else:
                        final2.append(line)
                new_lines = final2
            elif has_dbsync_section and not has_usedbsync:
                final2 = []
                for line in new_lines:
                    final2.append(line)
                    if re.match(r'^\s*\[DBSYNC\]', line, re.IGNORECASE):
                        final2.append("UseDBSync=0\n")
                new_lines = final2
            else:
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

# ======================= Запуск =======================

def launch_cloud_rk7man(tmp_ini_path, target_ini, keep_cloud_files):
    """Запускает rk7man.exe напрямую с временным ini-файлом в качестве аргумента,
    без изменения реального rk7man.ini. Рабочая директория — там, где лежит rk7man.exe,
    иначе исполняемый файл выдаёт ошибку. Возвращает True, если процесс запущен."""
    exe_path = os.path.join(target_ini, "rk7man.exe")
    if not os.path.isfile(exe_path):
        centered_error("Ошибка", f"Файл не найден:\n{exe_path}")
        return

    ini_path_norm = os.path.normpath(target_ini).lower()
    for proc, exe_dir in get_process_by_name('rk7man.exe'):
        if exe_dir == ini_path_norm:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    time.sleep(0.5)

    try:
        proc = subprocess.Popen([exe_path, tmp_ini_path], cwd=target_ini)
    except Exception as e:
        centered_error("Ошибка запуска", str(e))
        return False

    if not keep_cloud_files:
        def _cleanup_after_exit():
            proc.wait()
            try:
                os.remove(tmp_ini_path)
            except OSError:
                pass
        threading.Thread(target=_cleanup_after_exit, daemon=True).start()
    return True

# ======================= UI диалог =======================

def cloud_rk7man_dialog(root, ini_path, keep_cloud_files_var, icon_path=None):
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

    saved_connections = load_saved_cloud_connections(ini_path)

    tk.Label(
        frame,
        text="Введите строку подключения к облачному серверу",
        justify="center"
    ).pack(padx=15, pady=(15, 0))

    hint = tk.Frame(frame)
    hint.pack(padx=15, pady=(0, 5))

    link_font = tkfont.nametofont("TkDefaultFont").copy()
    link_font.configure(underline=True)

    tk.Label(hint, text="(строку можно взять у").pack(side="left")
    link = tk.Label(hint, text="бота", fg="blue", cursor="hand2", font=link_font)
    link.pack(side="left")
    link.bind("<Button-1>", lambda e: webbrowser.open("https://t.me/rkcloud_bot"))
    tk.Label(hint, text="):").pack(side="left")

    tk.Label(
        frame,
        text=f"Шаблон: ИМЯ_СЕРВЕРА=хост:порт  |  В списке — {MAX_SAVED_CONNECTIONS} последних запусков",
        justify="left",
        fg="gray40",
        font=("TkDefaultFont", 8)
    ).pack(padx=15, pady=(0, 5))

    connection_var = tk.StringVar()
    connection_combo = ttk.Combobox(
        frame,
        textvariable=connection_var,
        values=saved_connections,
        state="normal",
        width=55
    )
    connection_combo.pack(padx=15, pady=(0, 5))

    def on_connection_select(event):
        """При выборе из шторки — подставляем значение."""
        selected = connection_var.get()
        if selected:
            run_btn.focus_set()

    connection_combo.bind("<<ComboboxSelected>>", on_connection_select)

    def on_version_flag_change():
        """Обновляем состояние полей при смене флага."""
        is_disabled = use_current_version_var.get()
        version_combo.config(state="disabled" if is_disabled else "readonly")
        browse_btn.config(state="disabled" if is_disabled else "normal")
        if is_disabled:
            current_ver = extract_rk_version_from_path(ini_path)
            version_var.set(current_ver if current_ver else "")
        else:
            version_var.set("")
            connection_var.set("")

    # Чекбокс для выбора версии запуска
    use_current_version_var = tk.BooleanVar(value=True)

    version_row_frame = tk.Frame(frame)
    version_row_frame.pack(fill="x", padx=15, pady=(5, 5), anchor="w")

    use_current_version_var.trace_add("write", lambda *_: on_version_flag_change())

    version_checkbox = tk.Checkbutton(
        version_row_frame,
        text="Запускать rk7man с текущей выбранной версии",
        variable=use_current_version_var,
        justify="left"
    )
    version_checkbox.pack(side="left")

    # Поле выбора версии
    version_input_frame = tk.Frame(frame)
    version_input_frame.pack(fill="x", padx=15, pady=(0, 10))

    tk.Label(version_input_frame, text="Версия RK:", anchor="w").pack(side="left")

    def on_browse_version():
        """Открывает диалог выбора папки с версиями."""
        new_dir = filedialog.askdirectory(
            title="Выберите папку с версиями RK",
            initialdir=os.path.dirname(os.path.dirname(ini_path))
        )
        if new_dir:
            new_versions = []
            try:
                for item in os.listdir(new_dir):
                    full_path = os.path.join(new_dir, item)
                    if os.path.isdir(full_path):
                        match = re.match(r'^INST(.+)$', item, re.IGNORECASE)
                        if match:
                            bin_win = os.path.join(full_path, "bin", "win")
                            if os.path.isdir(bin_win):
                                new_versions.append(match.group(1))
            except Exception as e:
                print(f"Ошибка сканирования: {e}")

            if new_versions:
                new_versions = sorted(new_versions, reverse=True)
                version_combo['values'] = new_versions
                version_combo.current(0)
            else:
                centered_info("Информация", "Версии RK не найдены в выбранной папке.")

    browse_btn = tk.Button(version_input_frame, text="Обзор", command=on_browse_version, width=6, state="disabled")
    browse_btn.pack(side="right", padx=(5, 0))

    # Шторка с версиями
    version_var = tk.StringVar()
    version_combo = ttk.Combobox(
        version_input_frame,
        textvariable=version_var,
        values=[],
        state="disabled",
        width=20
    )
    version_combo.pack(side="left", padx=(5, 0), fill="x", expand=True)

    def on_version_combo_select(event):
        """При выборе версии из шторки."""
        pass  # Можно добавить дополнительную логику при необходимости

    version_combo.bind("<<ComboboxSelected>>", on_version_combo_select)

    # Инициализация
    on_version_flag_change()

    def get_target_ini_path():
        """Возвращает ini_path для запуска rk7man."""
        if use_current_version_var.get():
            return ini_path
        target_ver = version_var.get()
        if not target_ver:
            centered_error("Ошибка", "Выберите версию RK для запуска.")
            return None
        parent_dir = os.path.dirname(os.path.dirname(ini_path))
        target_path = os.path.join(parent_dir, f"INST{target_ver}", "bin", "win")
        if os.path.isdir(target_path):
            return target_path
        centered_error("Ошибка", f"Папка версии не найдена:\n{target_path}")
        return None

    def on_run():
        parsed = parse_cloud_rk7man_string(connection_var.get())
        if not parsed:
            centered_error(
                "Ошибка",
                "Строка не подходит по формату.\n"
                "Ожидается: ИМЯ_СЕРВЕРА=хост:порт\n"
                "Пример: RK7SRV_622020001=srv01.rkcloud.ucs.ru:50072"
            )
            return
        server_name, host, port = parsed
        connection_string = connection_var.get().strip()

        target_ini = get_target_ini_path()
        if target_ini is None:
            return

        win.destroy()
        tmp_ini_path, err = apply_cloud_rk7man_config(target_ini, server_name, host, port)
        if not tmp_ini_path:
            centered_error("Ошибка", f"Не удалось подготовить настройки:\n{err}")
            return
        if launch_cloud_rk7man(tmp_ini_path, target_ini, keep_cloud_files_var.get()):
            save_cloud_connection(connection_string)

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
        connection_var.set(clipboard_text.strip())
        run_btn.focus_set()
    else:
        connection_combo.focus_set()
        connection_combo.icursor(tk.END)

    _center_window(win)

    win.focus_force()
    win.deiconify()
