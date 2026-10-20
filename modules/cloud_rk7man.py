# ======================= cloud_rk7man.py =======================
# Логика Cloud RK7man

import os
import re
import shutil
import tempfile
import threading
import subprocess
import time
from . import (
    CLOUD_RK7MAN_PATTERN, CLOUD_CONNECTIONS_FILE, MAX_SAVED_CONNECTIONS
)

# ======================= Файлы подключений =======================

def get_cloud_connections_file_path(ini_path):
    """Возвращает путь к файлу cloud_connections.txt в корне папки версии RK."""
    return os.path.join(ini_path, CLOUD_CONNECTIONS_FILE)

def load_saved_cloud_connections(ini_path):
    """Загружает сохранённые строки подключения из файла (максимум 5)."""
    file_path = get_cloud_connections_file_path(ini_path)
    if not os.path.isfile(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
            return lines[:MAX_SAVED_CONNECTIONS]
    except Exception:
        return []

def save_cloud_connection(ini_path, connection_string):
    """Сохраняет строку подключения, удаляя дубликаты и оставляя 5 последних."""
    file_path = get_cloud_connections_file_path(ini_path)
    connections = load_saved_cloud_connections(ini_path)

    connections = [c for c in connections if c != connection_string]
    connections.insert(0, connection_string)
    connections = connections[:MAX_SAVED_CONNECTIONS]

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(connections))
    except Exception as e:
        print(f"[WARN] Не удалось сохранить подключение: {e}")

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

def launch_cloud_rk7man(tmp_ini_path, version_ini_path, keep_cloud_files):
    """Запускает rk7man.exe напрямую с временным ini-файлом."""
    target_ini = version_ini_path
    exe_path = os.path.join(target_ini, "rk7man.exe")
    if not os.path.isfile(exe_path):
        return False, f"Файл не найден:\n{exe_path}"

    import psutil
    ini_path_norm = os.path.normpath(target_ini).lower()
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == 'rk7man.exe':
                exe_dir = os.path.normpath(os.path.dirname(proc.exe())).lower()
                if exe_dir == ini_path_norm:
                    proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    time.sleep(0.5)

    try:
        proc = subprocess.Popen([exe_path, tmp_ini_path], cwd=target_ini)
    except Exception as e:
        return False, str(e)

    if not keep_cloud_files:
        def _cleanup_after_exit():
            proc.wait()
            try:
                os.remove(tmp_ini_path)
            except OSError:
                pass
        threading.Thread(target=_cleanup_after_exit, daemon=True).start()

    return True, None

# ======================= UI диалог =======================

def cloud_rk7man_dialog(root, ini_path, keep_cloud_files_var, icon_path=None, extract_rk_version_func=None):
    """Окно для ввода строки подключения к облачному серверу и запуска rk7man.exe."""
    from functools import partial
    import tkinter as tk
    import tkinter.ttk as ttk
    import tkinter.font as tkfont
    import webbrowser

    if not ini_path or not os.path.isfile(os.path.join(ini_path, "rk7man.ini")):
        return

    # Импортируем dialogs для работы с ними
    from .ui import centered_error, centered_info

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
    history_values = [""] + saved_connections

    tk.Label(frame, text="Введите строку подключения к облачному серверу", justify="center").pack(padx=15, pady=(15, 0))

    hint = tk.Frame(frame)
    hint.pack(padx=15, pady=(0, 5))

    link_font = tkfont.nametofont("TkDefaultFont").copy()
    link_font.configure(underline=True)

    tk.Label(hint, text="(строку можно взять у").pack(side="left")
    link = tk.Label(hint, text="бота", fg="blue", cursor="hand2", font=link_font)
    link.pack(side="left")
    link.bind("<Button-1>", lambda e: webbrowser.open("https://t.me/rkcloud_bot"))
    tk.Label(hint, text="):").pack(side="left")

    tk.Label(frame, text="Шаблон: ИМЯ_СЕРВЕРА=хост:порт  |  История подключений в списке",
             justify="left", fg="gray40", font=("TkDefaultFont", 8)).pack(padx=15, pady=(0, 5))

    connection_var = tk.StringVar()
    connection_combo = ttk.Combobox(frame, textvariable=connection_var, values=history_values, state="normal", width=55)
    connection_combo.pack(padx=15, pady=(0, 5))

    def on_connection_select(event):
        selected = connection_var.get()
        if selected:
            run_btn.focus_set()

    connection_combo.bind("<<ComboboxSelected>>", on_connection_select)

    # Чекбокс для выбора версии запуска
    use_current_version_var = tk.BooleanVar(value=True)
    version_var = tk.StringVar()

    def on_version_flag_change():
        """Обновляем состояние полей при смене флага."""
        is_disabled = use_current_version_var.get()
        version_combo.config(state="disabled" if is_disabled else "readonly")
        browse_btn.config(state="disabled" if is_disabled else "normal")
        if is_disabled:
            if extract_rk_version_func:
                current_ver = extract_rk_version_func(ini_path)
                version_var.set(current_ver if current_ver else "")
        else:
            version_var.set("")
            connection_var.set("")

    use_current_version_var.trace_add("write", lambda *_: on_version_flag_change())

    version_row_frame = tk.Frame(frame)
    version_row_frame.pack(fill="x", padx=15, pady=(5, 5), anchor="w")

    version_checkbox = tk.Checkbutton(
        version_row_frame,
        text="Запускать rk7man с текущей выбранной версии",
        variable=use_current_version_var,
        justify="left"
    )
    version_checkbox.pack(side="left")

    version_input_frame = tk.Frame(frame)
    version_input_frame.pack(fill="x", padx=15, pady=(0, 10))

    tk.Label(version_input_frame, text="Версия RK:", anchor="w").pack(side="left")

    def on_browse_version():
        """Открывает диалог выбора папки с версиями."""
        new_dir = tk.filedialog.askdirectory(
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
                centered_info(root, "Информация", "Версии RK не найдены в выбранной папке.")

    browse_btn = tk.Button(version_input_frame, text="Обзор", command=on_browse_version, width=6, state="disabled")
    browse_btn.pack(side="right", padx=(5, 0))

    version_combo = ttk.Combobox(
        version_input_frame, textvariable=version_var, values=[], state="disabled", width=20
    )
    version_combo.pack(side="left", padx=(5, 0), fill="x", expand=True)

    def on_version_combo_select(event):
        pass

    version_combo.bind("<<ComboboxSelected>>", on_version_combo_select)
    on_version_flag_change()

    def get_target_ini_path():
        """Возвращает ini_path для запуска rk7man."""
        if use_current_version_var.get():
            return ini_path
        target_ver = version_var.get()
        if not target_ver:
            centered_error(root, "Ошибка", "Выберите версию RK для запуска.")
            return None
        parent_dir = os.path.dirname(os.path.dirname(ini_path))
        target_path = os.path.join(parent_dir, f"INST{target_ver}", "bin", "win")
        if os.path.isdir(target_path):
            return target_path
        centered_error(root, "Ошибка", f"Папка версии не найдена:\n{target_path}")
        return None

    def on_run():
        parsed = parse_cloud_rk7man_string(connection_var.get())
        if not parsed:
            centered_error(root, "Ошибка",
                "Строка не подходит по формату.\n"
                "Ожидается: ИМЯ_СЕРВЕРА=хост:порт\n"
                "Пример: RK7SRV_622020001=srv01.rkcloud.ucs.ru:50072"
            )
            return
        server_name, host, port = parsed
        connection_string = connection_var.get().strip()

        save_cloud_connection(ini_path, connection_string)

        target_ini = get_target_ini_path()
        if target_ini is None:
            return

        win.destroy()
        tmp_ini_path, err = apply_cloud_rk7man_config(target_ini, server_name, host, port)
        if not tmp_ini_path:
            centered_error(root, "Ошибка", f"Не удалось подготовить настройки:\n{err}")
            return
        success, err = launch_cloud_rk7man(tmp_ini_path, target_ini, keep_cloud_files_var.get())
        if not success:
            centered_error(root, "Ошибка", f"Не удалось запустить rk7man:\n{err}")

    def on_save():
        """Сохраняет подключение без запуска."""
        parsed = parse_cloud_rk7man_string(connection_var.get())
        if not parsed:
            centered_error(root, "Ошибка",
                "Строка не подходит по формату.\n"
                "Ожидается: ИМЯ_СЕРВЕРА=хост:порт\n"
                "Пример: RK7SRV_622020001=srv01.rkcloud.ucs.ru:50072"
            )
            return
        connection_string = connection_var.get().strip()
        save_cloud_connection(ini_path, connection_string)
        connection_combo['values'] = [""] + load_saved_cloud_connections(ini_path)
        connection_combo.set("")
        centered_info(root, "Сохранено", "Подключение сохранено в историю.")

    def on_enter_key(event):
        on_run()

    win.bind("<Return>", on_enter_key)

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=(0, 15))
    run_btn = tk.Button(btn_frame, text="Запустить", command=on_run, width=12)
    run_btn.pack(side="left", padx=5)
    save_btn = tk.Button(btn_frame, text="Сохранить", command=on_save, width=12)
    save_btn.pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=win.destroy, width=12).pack(side="left", padx=5)

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

    from .ui.dialogs import _center_window
    _center_window(win, root)
    win.focus_force()
    win.deiconify()
