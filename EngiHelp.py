# ======================= Импорты =======================
from tkinter import filedialog, ttk
from functools import partial
from datetime import datetime
import tkinter as tk
import os
import re
import shutil
import psutil
import subprocess
import time
import threading
import logging
import requests
import sys
import tempfile
import webbrowser
import keyboard
import queue
import ctypes
import ctypes.wintypes
from packaging import version

# ======================= Модули =======================
# Папка modules лежит рядом со скриптом (в exe — распаковывается PyInstaller'ом)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules import check_gitignore_status, extract_icon_to_temp, get_short_path_name
from modules import dialogs
from modules.dialogs import _center_window, centered_info, centered_warning, centered_error
from modules.dialogs import centered_askyesno, centered_askchecklist, centered_askchoice, centered_askselect
from modules.data_manager import load_data, save_data, load_settings_and_paths, get_task_data
from modules.data_manager import save_settings_and_path as _save_recent_path
from modules.data_manager import find_latest_task_for_path, find_tasks_for_path, get_current_task_base_path, load_task_ids
from modules.data_manager import get_task_base_paths, task_folder_exists
from modules.ini_utils import set_port_rk7srv, set_port_rk7man, apply_port
from modules.ini_utils import FILES, detect_consensus_value, get_usesql_value, get_port_value, get_port_value_for_path
from modules.ini_utils import get_refserver_name, update_ini_file, update_rkeeper_ini_basepath
from modules.ini_utils import update_rk7srv_ini, get_ini_settings, check_files, apply_rk7srv_udf_workmodules
from modules.ini_utils import get_rk7srv_udb_workmodules, get_usedbsync_values
from modules.process_utils import kill_midserv, kill_doscash
from modules.process_utils import kill_processes_for_version_change, get_used_ports, get_process_by_name, is_process_running
from modules.process_utils import get_port_info, get_rk7man_port_info, get_process_listening_ports
from modules.process_utils import launch_refsrv, wait_and_launch_refsrv
from modules.cloud_rk7man import cloud_rk7man_dialog
from modules.shortcuts import create_task_shortcuts
from modules.task_manager import extract_task_id_from_rk7srv_ini, find_product_root
from modules.task_manager import extract_rk_version_from_path, find_available_rk_versions
from modules.task_manager import create_task_for_version
from modules.task_manager import find_running_task_by_ports, find_last_running_task, _main_refsrv_port
from modules.task_manager import relocate_task, add_found_task_version, find_task_in_versions, get_missing_versions
from modules.task_manager import ensure_task_midbase
from modules.task_manager import find_missing_entries_in_version, move_version_settings
from modules.task_manager import version_root_from_folder, version_root_from_ini_path
from modules.version_updater import check_rk_updates, download_version, extract_zip
from modules.backups import DEFAULT_BACKUPS_KEEP, all_base_paths, find_old_backups, delete_backups
from modules.backups import format_size
from modules.changelog import CHANGELOG

# ======================= Константы и настройки =======================
SCRIPT_VERSION = "v2.0.1.0"  #Формат: vМajor.Minor.Patch.Build
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

# ======================= Проверка URL файла .gitignore на GitHub =======================
# Проверяем статус в .gitignore
if not check_gitignore_status():
    print("Программа не будет запущена.")
    sys.exit()  # Завершаем программу

# Если первая строка в .gitignore равна "0", продолжаем выполнение программы
print("Программа запускается.")

# ==============================================

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# === GUI ===
root = tk.Tk()
root.withdraw()
root.title(f"EngiHelp {SCRIPT_VERSION}")

# Извлечение иконки и применение к окну
icon_path = extract_icon_to_temp()
if icon_path:
   root.iconbitmap(icon_path)  # Применяем иконку к главному окну
dialogs.init(root, icon_path)  # root и иконка для всех centered_* окон

# Размеры главного окна (слева — панель со списком задач, если включена в «Настройках»)
BASE_WINDOW_WIDTH = 412
TASK_PANEL_WIDTH = 70
show_task_panel_var = tk.BooleanVar(value=load_data()["settings"].get("show_task_panel", True))

def get_window_width():
    """Ширина главного окна с учётом панели задач."""
    return BASE_WINDOW_WIDTH + (TASK_PANEL_WIDTH if show_task_panel_var.get() else 0)

WINDOW_WIDTH = get_window_width()
WINDOW_HEIGHT = 510
WINDOW_OFFSET_X = 223
WINDOW_OFFSET_Y = 100   

def _is_point_on_monitor(px, py):
    """True, если точка попадает на один из подключённых мониторов."""
    try:
        point = ctypes.wintypes.POINT(px, py)
        return bool(ctypes.windll.user32.MonitorFromPoint(point, 0))  # 0 = MONITOR_DEFAULTTONULL
    except Exception:
        return False

def _load_window_position():
    """Возвращает сохранённую позицию главного окна (x, y) или None,
    если её нет или заголовок окна оказался бы за пределами мониторов."""
    pos = load_data()["settings"].get("window_pos")
    if not (isinstance(pos, list) and len(pos) == 2 and all(isinstance(v, int) for v in pos)):
        return None
    px, py = pos
    if _is_point_on_monitor(px + 20, py + 10) or _is_point_on_monitor(px + WINDOW_WIDTH - 20, py + 10):
        return px, py
    return None

def save_window_position():
    """Сохраняет позицию главного окна, чтобы при запуске открыть его там же."""
    try:
        if root.state() != "normal":
            return
        m = re.match(r'^\d+x\d+\+(-?\d+)\+(-?\d+)$', root.geometry())
        if not m:
            return
        data = load_data()
        data["settings"]["window_pos"] = [int(m.group(1)), int(m.group(2))]
        save_data(data)
    except Exception as e:
        print(f"[WARN] Не удалось сохранить позицию окна: {e}")

# Позиция окна: там, где закрыли в прошлый раз, иначе — у курсора
saved_pos = _load_window_position()
if saved_pos:
    x, y = saved_pos
else:
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    cursor_x = root.winfo_pointerx()
    cursor_y = root.winfo_pointery()
    x = max(0, min(screen_width - WINDOW_WIDTH, cursor_x - WINDOW_OFFSET_X))
    y = max(0, min(screen_height - WINDOW_HEIGHT, cursor_y - WINDOW_OFFSET_Y))

root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

# Панель задач слева (заполняется в refresh_task_panel, показ — toggle_task_panel)
task_panel = tk.Frame(root, width=TASK_PANEL_WIDTH)
if show_task_panel_var.get():
    task_panel.pack(side="left", fill="y")
task_panel.pack_propagate(False)
tk.Label(task_panel, text="Задачи", font=("TkDefaultFont", 8, "bold")).pack(pady=(4, 2))
# Рамка вокруг списка с фоном списка — даёт отступ текста от левого края
task_list_frame = tk.Frame(task_panel, relief="solid", borderwidth=1)
task_list_frame.pack(fill="both", expand=True, padx=(4, 2), pady=(0, 4))
task_listbox = tk.Listbox(
    task_list_frame,
    activestyle="none",
    exportselection=False,
    borderwidth=0,
    highlightthickness=0,
    font=("TkDefaultFont", 9)
)
task_list_frame.config(background=task_listbox.cget("background"))
task_listbox.pack(fill="both", expand=True, padx=(10, 0))

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

settings_tab = tk.Frame(notebook)
notebook.add(settings_tab, text="Параметры")

# =================== Работа с EngiHelp_config.json (мульти-пути) =============
# load_settings_and_paths импортирована из modules.data_manager

def save_settings_and_path(new_path):
    data = load_data()

    # Обновляем флаги настроек
    if 'auto_update_var' in globals():
        data["settings"]["auto_update"] = auto_update_var.get()
    if 'task_from_version_var' in globals():
        data["settings"]["task_from_version"] = task_from_version_var.get()
    if 'keep_cloud_files_var' in globals():
        data["settings"]["keep_cloud_files"] = keep_cloud_files_var.get()

    # Добавляем путь в историю (3 последних) и сохраняем
    data = _save_recent_path(new_path, data)

    # Обновляем выпадающий список в интерфейсе
    if 'path_entry' in globals():
        path_entry['values'] = data["settings"]["recent_paths"]
# find_latest_task_for_path, find_tasks_for_path, get_current_task_base_path импортированы из modules.data_manager
# extract_task_id_from_rk7srv_ini, find_product_root, extract_rk_version_from_path, find_available_rk_versions импортированы из modules.task_manager

# ======================= Определение путей и начальных переменных =======================
ini_paths, auto_update_enabled, task_from_version_enabled, keep_cloud_files_enabled, delete_zip_after_extract_enabled = load_settings_and_paths()
ini_path = ini_paths[0] if ini_paths else ""
auto_update_var = tk.BooleanVar(value=auto_update_enabled)
# Флаг "Выбор задачи из выбора версии": при смене версии RK предлагать выбрать задачу
task_from_version_var = tk.BooleanVar(value=task_from_version_enabled)
# Флаг "Сохранять временные файлы Cloud RK7man": не удалять .ini после запуска
keep_cloud_files_var = tk.BooleanVar(value=keep_cloud_files_enabled)
# Флаг "Удалять ZIP после распаковки"
delete_zip_after_extract_var = tk.BooleanVar(value=delete_zip_after_extract_enabled)
# Флаг "Удалять старые бэкапы базы" и сколько последних бэкапов хранить у каждой задачи
clean_backups_var = tk.BooleanVar(value=load_data()["settings"].get("clean_backups", False))
backups_keep_var = tk.IntVar(value=load_data()["settings"].get("backups_keep", DEFAULT_BACKUPS_KEEP))
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

# ======================= Работа с INI-файлами (импортировано из modules.ini_utils) =======================

# Cloud RK7man (окно, запуск, конфиг) — modules/cloud_rk7man.py

def on_check():
    found, missing = check_files(ini_path)
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
        usedbsync_var.set(int(detect_consensus_value(ini_path)))
        usesql_var.set(int(get_usesql_value(ini_path)))
        port_var.set(get_port_value(ini_path))
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
                target=wait_and_launch_refsrv,
                args=(proc, exe_path),
                daemon=True,
                name="refsrv-restart"
            ).start()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            launch_refsrv(exe_path)

    except psutil.NoSuchProcess:
        launch_refsrv(exe_path)
    except Exception as e:
        logging.error("Ошибка при перезапуске refsrv.exe (pid=%s): %s", pid, e)
        centered_error("Ошибка", f"Не удалось перезапустить refsrv.exe:\n{e}")


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
def set_upgrade_anytime(value: str, ini_path_val=None) -> bool:
    """Устанавливает UpgradeAnyTime=value в секцию [REFSERVER] файла rk7srv.INI
    (папка ini_path_val, по умолчанию — текущая версия).
    Алгоритм:
      1. Если строка UpgradeAnyTime уже есть в [REFSERVER] — обновляет её.
      2. Если секция [REFSERVER] есть, но параметра нет — вставляет строку
         последней в секции (перед следующей секцией или в конце файла).
      3. Если секции [REFSERVER] нет — добавляет секцию и параметр в конец файла.
    """
    ini_file = os.path.join(ini_path_val or ini_path, "rk7srv.INI")
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
    """Перезапуск refsrv выбранной версии с UpgradeAnyTime=1:
    находит refsrv текущей задачи, убивает его, дожидается закрытия и запускает
    с UpgradeAnyTime=1 (после старта сбрасывается в 0). refsrv других задач не трогаются."""
    start_refsrv_only(upgrade_anytime=True)

def _reset_upgrade_anytime_after_start(ini_path_val, before_pids, attempts=30):
    """Ждёт появления нового refsrv из ini_path_val и через 3 секунды после его старта
    (refsrv должен успеть прочитать INI) сбрасывает UpgradeAnyTime в 0.
    Если процесс так и не появился — сбрасывает по истечении попыток."""
    exe_dir_norm = os.path.normpath(ini_path_val).lower()
    started = any(d == exe_dir_norm and p.pid not in before_pids
                  for p, d in get_process_by_name('refsrv.exe'))
    if started or attempts <= 0:
        def reset_flag():
            set_upgrade_anytime("0", ini_path_val)
            logging.info("UpgradeAnyTime сброшен в 0")
        root.after(3000 if started else 0, reset_flag)
        return
    root.after(500, lambda: _reset_upgrade_anytime_after_start(ini_path_val, before_pids, attempts - 1))
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

def _pick_version_with_task(task_id, search_folder, expected_name=None):
    """Ищет задачу во всех версиях RK внутри search_folder. Одна найденная версия — берёт её;
    несколько — берёт версию с сохранённым в задаче именем expected_name (INST...), а если такой
    среди найденных нет — даёт отметить несколько; ни одной — сообщает об этом.
    Возвращает список корней версий (первая — куда переносится потерянная версия задачи) или None."""
    root.config(cursor="watch")
    root.update_idletasks()
    try:
        found, checked = find_task_in_versions(search_folder, task_id)
    finally:
        root.config(cursor="")
    if not found:
        centered_error("Задача не найдена",
                       f"Задача {task_id} не найдена ни в одной версии RK внутри:\n{search_folder}\n\n"
                       f"Проверено версий: {checked}. Искались папки {task_id}\\base и base_{task_id}.")
        return None
    if len(found) == 1:
        return [found[0][0]]
    if expected_name:
        same_name = [r for r, _ in found if os.path.basename(r).lower() == expected_name.lower()]
        if len(same_name) == 1:
            return same_name
    options = [f"{os.path.relpath(r, search_folder)}" + ("  (старый формат base_" + task_id + ")" if old else "")
               for r, old in found]
    indexes = centered_askselect("Выбор версий",
                                 f"Задача {task_id} найдена в нескольких версиях. Отметьте, в каких она "
                                 f"должна быть (можно несколько) — каждая станет версией задачи:",
                                 options, multiple=True)
    return [found[i][0] for i in indexes] if indexes else None

def _handle_missing_task_folder(task_id, task_info, old_task_id, version_key=None):
    """Папка задачи (или одной её версии — version_key) не найдена: удалена или перенесена вручную.
    Предлагает указать новый путь, удалить задачу (версию) из списка или отменить выбор —
    тогда возвращается предыдущая задача."""
    versions = task_info.get("versions", {})
    if version_key:
        entry = versions.get(version_key, {})
        missing_paths = [entry.get("base_path", "")]
        what = f"Папка версии {version_key} задачи {task_id} не найдена"
        delete_text = "Удалить версию из задачи"
    else:
        entry = task_info
        missing_paths = get_task_base_paths(task_info)
        what = f"Папка задачи {task_id} не найдена"
        delete_text = "Удалить из списка"
    choice = centered_askchoice(
        "Папка задачи не найдена",
        f"{what} — вероятно, удалена или перенесена вручную:\n"
        f"{chr(10).join(missing_paths)}\n\nЕсли задачу перенесли — укажите папку с версиями RK, "
        f"задача будет найдена во всех версиях внутри.",
        ["Указать новый путь", delete_text, "Отмена"]
    )
    if choice == 0:
        if _relocate_missing_task(task_id, entry, version_key):
            return
    elif choice == 1:
        if version_key:
            root.after(0, lambda: _remove_missing_version(task_id, version_key))
        else:
            root.after(0, lambda: delete_task(confirm=False))
        return
    # Отмена — возвращаем предыдущую задачу (её настройки применятся заново)
    root.after(0, lambda: task_id_var.set(old_task_id or ""))

def _relocate_missing_task(task_id, entry, version_key):
    """Выбор папки с версиями, поиск в ней задачи и перенос путей. Если старая версия RK
    перенесена целиком — предлагает перенести и остальные её задачи. True — задача перенесена
    и будет применена по новым путям."""
    # Начинаем выбор с папки, где лежат версии (над старым INST...), или ближайшей существующей
    old_root = version_root_from_ini_path(entry.get("ini_path", ""))
    start_dir = os.path.dirname(old_root) if old_root else ""
    while start_dir and not os.path.isdir(start_dir) and os.path.dirname(start_dir) != start_dir:
        start_dir = os.path.dirname(start_dir)
    search_folder = filedialog.askdirectory(
        title=f"Папка с версиями RK — поиск задачи {task_id} (можно выбрать и саму версию INST...)",
        initialdir=start_dir or None
    )
    # Имя версии (INST...) уже сохранено в задаче — среди найденных берём её без вопроса
    expected_name = os.path.basename(old_root) if old_root else (f"INST{version_key}" if version_key else None)
    version_folders = (_pick_version_with_task(task_id, search_folder, expected_name)
                       if search_folder else None)
    if not version_folders:
        return False
    version_folder = version_folders[0]
    ok, message, new_key = relocate_task(task_id, version_folder, version_key)
    if not ok:
        centered_error("Не удалось изменить путь", message)
        return False
    print(f"[TASK] {message}")
    messages = [message]
    # Остальные отмеченные версии, где тоже есть папка задачи, — добавляем задаче как её версии
    for extra_folder in version_folders[1:]:
        extra_ok, extra_msg = add_found_task_version(task_id, extra_folder)
        print(f"[TASK] {extra_msg}")
        messages.append(extra_msg if extra_ok else f"{os.path.basename(extra_folder)}: {extra_msg}")

    # Остальные задачи, которые указывают на ту же старую версию и тоже потеряли папки
    new_root = version_root_from_folder(version_folder)
    others = [(t, k) for t, k in find_missing_entries_in_version(old_root) if t != task_id] if old_root else []
    if others:
        names = "\n".join(f"• {t}" + (f" (версия {k})" if k else "") for t, k in others)
        if centered_askyesno("Перенос версии",
                             f"В версии {old_root} есть ещё задачи без папок:\n{names}\n\n"
                             f"Перенести их пути тоже в {new_root}?"):
            for other_id, other_key in others:
                other_ok, other_msg, _ = relocate_task(other_id, new_root, other_key)
                print(f"[TASK] {other_msg}")
                messages.append(other_msg if other_ok else f"Задача {other_id}: {other_msg}")
    # Сама версия RK перенесена — переводим её дефолтные настройки и путь в истории
    if old_root and not os.path.isdir(old_root) and new_root and move_version_settings(old_root, new_root):
        if 'path_entry' in globals():
            path_entry['values'] = load_data()["settings"].get("recent_paths", [])
        messages.append(f"Настройки версии без задачи и история путей переведены на {new_root}")

    centered_info("Путь задачи изменён", "\n\n".join(messages))
    task_id_combobox['values'] = load_task_ids()

    # Применяем задачу уже по новым путям (нужная версия — без повторного выбора)
    def _apply():
        global _forced_version
        _forced_version = new_key
        task_id_var.set(task_id)
    root.after(0, _apply)
    return True

def _remove_missing_version(task_id, version_key):
    """Убирает из задачи версию, папки которой нет на диске (папки не удаляются — их уже нет).
    Если это была активная версия — активной становится другая. Затем задача выбирается заново."""
    data = load_data()
    task_info = data.get("tasks", {}).get(task_id)
    if not task_info or version_key not in task_info.get("versions", {}):
        return
    versions = task_info["versions"]
    removed = versions.pop(version_key)
    if os.path.normpath(removed.get("ini_path", "")).lower() == os.path.normpath(task_info.get("ini_path", "")).lower():
        # Активной делаем версию, папка которой есть на диске
        missing = set(get_missing_versions(task_info))
        new_active = next((k for k in versions if k not in missing), next(iter(versions), None))
        if new_active:
            for field in ("ini_path", "base_path", "midbase_path", "ini_settings"):
                if field in versions[new_active]:
                    task_info[field] = versions[new_active][field]
    save_data(data)
    print(f"[TASK] Версия {version_key} убрана из задачи {task_id}")
    task_id_var.set(task_id)

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

    # Нет папки MIDBASE (например, после переноса задачи) — создаём и записываем путь
    ensure_task_midbase(selected_task_id)
    clean_backups_in_background([selected_task_id])
    data = load_data()
    tasks = data.get("tasks", {})

    if selected_task_id not in tasks:
        return

    task_info = tasks[selected_task_id]

    # === ПРОВЕРКА, ЧТО ПАПКА ЗАДАЧИ СУЩЕСТВУЕТ ===
    # Папку могли удалить вручную — такую задачу применять нельзя (INI укажут на несуществующую базу)
    if not task_folder_exists(task_info):
        _prev_task_id = ""  # данные старой задачи уже сохранены выше, в удалённую ничего не пишем
        _handle_missing_task_folder(selected_task_id, task_info, old_task_id)
        return

    # === ПРОВЕРКА НА НЕСКОЛЬКО ВЕРСИЙ ===
    versions = task_info.get("versions", {})
    if len(versions) > 1:
        # Версия уже выбрана пользователем на предыдущем шаге — применяем её
        # без повторного диалога (иначе: выбрали версию -> задачу -> опять версию).
        if forced_version and forced_version in versions:
            if forced_version in get_missing_versions(task_info):
                _prev_task_id = ""  # в версию без папок ничего не пишем
                _handle_missing_task_folder(selected_task_id, task_info, old_task_id, forced_version)
                return
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
    if not ensure_ini_files(ini_path_from_task):
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

    # Применяем REFSERVER
    _apply_task_refserver(ini_path_from_task, ini_settings)

    # Применяем Port
    _apply_task_port(ini_path_from_task, ini_settings)

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

# extract_rk_version_from_path и find_available_rk_versions импортированы из modules.task_manager

# ======================= Смена версии RK =======================

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

    # Определяем директорию поиска версий
    current_product_root = find_product_root(current_ini_path)
    if not current_product_root:
        centered_error("Ошибка", "Не удалось определить корневую папку продукта.")
        return
    versions_search_dir = os.path.dirname(current_product_root)

    # Ищем доступные версии
    available_versions = find_available_rk_versions(current_ini_path)
    other_versions = [v for v in available_versions if v != current_version]
    other_versions = sorted(other_versions, reverse=True)  # новые версии сверху

    if not other_versions:
        centered_info("Информация",
            f"Других версий RK не найдено.\n"
            f"Текущая версия: {current_version}\n"
            f"Директория поиска: {versions_search_dir}")
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

    # Переменная для хранения редактируемой директории поиска версий
    search_dir_var = tk.StringVar(value=versions_search_dir)

    # Заголовок с информацией о задаче и текущей версии
    tk.Label(frame, text=(
        f"Задача: {selected_task_id}\n"
        f"Текущая версия: {current_version}"
    ), justify="left").pack(padx=10, pady=(10, 5))

    # Блок с директорией поиска версий
    tk.Label(frame, text="Путь к папке с версиями из ZIP-архива:", anchor="w").pack(anchor="w", padx=10, pady=(8, 0))

    dir_input_frame = tk.Frame(frame)
    dir_input_frame.pack(fill="x", padx=10, pady=(3, 0))

    dir_entry = tk.Entry(dir_input_frame, textvariable=search_dir_var, width=40)
    dir_entry.pack(side="left", fill="x", expand=True)

    def on_browse_version_dir():
        """Открывает диалог выбора папки и обновляет список версий."""
        new_dir = filedialog.askdirectory(
            title="Выберите папку с версиями RK",
            initialdir=search_dir_var.get()
        )
        if new_dir:
            search_dir_var.set(new_dir)
            # Ищем версии в новой директории
            new_versions = []
            try:
                for item in os.listdir(new_dir):
                    full_path = os.path.join(new_dir, item)
                    if os.path.isdir(full_path):
                        match = re.match(r'^INST(.+)$', item, re.IGNORECASE)
                        if match:
                            version_str = match.group(1)
                            bin_win = os.path.join(full_path, "bin", "win")
                            if os.path.isdir(bin_win):
                                new_versions.append(version_str)
            except Exception as e:
                print(f"Ошибка сканирования директории: {e}")

            new_other_versions = [v for v in new_versions if v != current_version]
            new_other_versions = sorted(new_other_versions, reverse=True)

            if new_other_versions:
                version_var.set(new_other_versions[0])
                version_combo['values'] = new_other_versions
                warning_label.config(text="⚠ Процессы refsrv.exe и rk7man.exe будут закрыты!")
            else:
                warning_label.config(
                    text=f"⚠ Версий не найдено в: {os.path.basename(new_dir)}",
                    fg="orange"
                )

    tk.Button(dir_input_frame, text="Образ", command=on_browse_version_dir, width=6).pack(side="left", padx=(5, 0))

    # Подсказка о выборе версии
    tk.Label(frame, text="Выберите версию для переноса базы:", anchor="w").pack(anchor="w", padx=10, pady=(8, 0))

    version_var = tk.StringVar()
    version_combo = ttk.Combobox(
        frame, textvariable=version_var,
        values=other_versions, state="readonly", width=30
    )
    version_combo.pack(padx=10, pady=(5, 0))
    if other_versions:
        version_combo.current(0)

    warning_label = tk.Label(frame, text=(
        "⚠ Процессы refsrv.exe и rk7man.exe будут закрыты!"
    ), fg="red", font=("TkDefaultFont", 8))
    warning_label.pack(padx=10, pady=(5, 0))

    # Блок проверки обновлений
    update_frame = tk.Frame(frame)
    update_frame.pack(fill="x", padx=10, pady=(5, 0))

    update_status_var = tk.StringVar(value="")
    update_status_label = tk.Label(update_frame, textvariable=update_status_var, fg="green", font=("TkDefaultFont", 8))
    update_status_label.pack(side="left")

    checking_label = tk.Label(update_frame, text="Проверяем облако...", fg="gray", font=("TkDefaultFont", 8))

    def on_check_updates():
        """Проверяет наличие обновлений в облаке."""
        update_status_var.set("")
        checking_label.pack(side="left")
        btn_check_update.config(state="disabled")
        select_win.update()

        try:
            update_info = check_rk_updates(available_versions, current_version)
            checking_label.pack_forget()

            if update_info:
                latest = update_info['latest_version']
                update_status_var.set(f"✅ Доступна новая версия: {latest}")
                update_status_label.config(fg="green")

                if centered_askyesno("Обновление", (
                    f"Доступна новая версия RK: {latest}\n"
                    f"Текущая локальная: {update_info['current_version']}\n\n"
                    f"Скачать версию {latest}?"
                )):
                    on_download_update(update_info)
            else:
                update_status_var.set("✅ У вас последняя версия")
                update_status_label.config(fg="gray")

        except Exception as e:
            checking_label.pack_forget()
            update_status_var.set(f"❌ Ошибка проверки: {str(e)[:50]}")
            update_status_label.config(fg="red")
            print(f"[ERROR] Проверка обновлений: {e}")

        btn_check_update.config(state="normal")

    def on_download_update(update_info):
        """Скачивает обновление из облака."""
        zip_name = update_info['zip_name']
        download_path = update_info['download_path']

        # Спрашиваем куда сохранить
        target_dir = filedialog.askdirectory(
            title="Выберите папку для сохранения версии",
            initialdir=versions_search_dir
        )
        if not target_dir:
            return

        # Скачиваем
        def progress_callback(filename, downloaded, total):
            percent = int(downloaded * 100 / total) if total > 0 else 0
            update_status_var.set(f"📥 Скачивается: {percent}%")
            select_win.update()

        update_status_var.set(f"📥 Скачивается: 0%")
        update_status_label.config(fg="blue")
        btn_check_update.config(state="disabled")
        btn_transfer.config(state="disabled")
        select_win.update()

        success, result = download_version(download_path, zip_name, target_dir, progress_callback)

        if success:
            # Распаковываем
            update_status_var.set("📦 Распаковка...")
            select_win.update()

            success, extracted = extract_zip(result, target_dir, delete_zip_after_extract_var.get())
            if success:
                update_status_var.set(f"✅ Готово: {extracted}")
                update_status_label.config(fg="green")

                # Обновляем список версий
                if extracted:
                    new_path = os.path.join(target_dir, extracted)
                    if os.path.isdir(new_path):
                        search_dir_var.set(target_dir)
                        on_browse_version_dir()

                centered_info("Успех", f"Версия {update_info['latest_version']} скачана и распакована:\n{os.path.join(target_dir, extracted)}")
            else:
                update_status_var.set(f"❌ Ошибка распаковки: {extracted}")
                update_status_label.config(fg="red")
                centered_error("Ошибка", f"Не удалось распаковать:\n{extracted}")
        else:
            update_status_var.set(f"❌ Ошибка скачивания")
            update_status_label.config(fg="red")
            centered_error("Ошибка", f"Не удалось скачать:\n{result}")

        btn_check_update.config(state="normal")
        btn_transfer.config(state="normal")

    # Кнопка проверки обновлений (запускаем сразу при открытии)
    btn_check_update = tk.Button(frame, text="🔄 Проверить обновления", command=on_check_updates, width=20)
    btn_check_update.pack(pady=(5, 0))

    # Запускаем проверку через небольшую задержку
    select_win.after(200, on_check_updates)

    def on_confirm():
        target_version = version_var.get()
        if not target_version:
            centered_warning("Предупреждение", "Выберите версию!")
            return
        target_dir = search_dir_var.get()
        select_win.destroy()
        perform_version_change(selected_task_id, current_version, target_version, target_dir)

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=(5, 10))
    btn_transfer = tk.Button(btn_frame, text="Перенести", command=on_confirm, width=12)
    btn_transfer.pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=select_win.destroy, width=12).pack(side="left", padx=5)

    _center_window(select_win)

    select_win.focus_force()
    select_win.deiconify()


def perform_version_change(task_id, current_version, target_version, target_dir=None):
    """Выполняет перенос базы задачи в другую версию RK с заменой только rk7.udb."""
    data = load_data()
    tasks = data.get("tasks", {})
    task_info = tasks.get(task_id)
    if not task_info: return

    current_ini_path = task_info.get("ini_path", path_var.get())
    current_product_root = find_product_root(current_ini_path)

    # Используем переданную директорию или вычисляем из текущего пути
    if target_dir:
        parent_dir = target_dir
    else:
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
    missing_versions = set(get_missing_versions(task_info))

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
        if ver in missing_versions:
            label_text += "  — папка не найдена"

        ver_row = tk.Frame(radio_frame)
        ver_row.pack(anchor="w", pady=2, fill="x")

        rb = tk.Radiobutton(
            ver_row,
            text=label_text,
            variable=version_var_local,
            value=ver,
            anchor="w",
            fg="red3" if ver in missing_versions else None,
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
        if selected_ver in missing_versions:
            # Папки версии нет — предлагаем указать новый путь или убрать версию
            _prev_task_id = ""
            select_win.destroy()
            _handle_missing_task_folder(task_id, task_info, prev_task_id, selected_ver)
            return
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
    ensure_task_midbase(task_id)
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
    if not ensure_ini_files(ini_path_from_version):
        return

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

    _apply_task_refserver(ini_path_from_version, ini_settings)

    _apply_task_port(ini_path_from_version, ini_settings)

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
        f"Выберите задачу или создайте новую:"
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

    # Блок для создания новой задачи
    new_task_frame = tk.Frame(frame)
    new_task_frame.pack(fill="x", padx=10, pady=(10, 5))

    tk.Label(new_task_frame, text="Или создайте новую задачу:", anchor="w").pack(anchor="w", pady=(0, 3))

    new_task_input_frame = tk.Frame(new_task_frame)
    new_task_input_frame.pack(fill="x")

    new_task_var = tk.StringVar()
    new_task_entry = tk.Entry(new_task_input_frame, textvariable=new_task_var, width=20)
    new_task_entry.pack(side="left", fill="x", expand=True)

    def on_create_new_task():
        new_task_id = new_task_var.get().strip()
        if not new_task_id:
            centered_warning("Предупреждение", "Введите номер задачи")
            return

        success, message = create_task_for_version(new_task_id, version_path)
        if success:
            # Обновляем список задач в диалоге
            task_id_combobox['values'] = load_task_ids()
            select_win.destroy()
            # Загружаем созданную задачу с уже выбранной версией
            _load_task(new_task_id)
        else:
            centered_warning("Ошибка", message)

    tk.Button(new_task_input_frame, text="Создать", command=on_create_new_task, width=8).pack(side="left", padx=(5, 0))

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
    """Сохраняет позицию окна и очищает горячие клавиши перед закрытием"""
    save_window_position()
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

# ======================= Панель задач слева =======================
_task_panel_state = None  # (задачи, задачи версии, выбранная) — перерисовываем только при изменениях

def refresh_task_panel():
    """Список задач на панели слева в том же порядке, что в «Номер задачи».
    Задачи текущей версии — обычным цветом, остальных версий — серым,
    задачи, папки которых не найдены на диске, — красным, задачи, у которых нет папок
    только части версий, — оранжевым; выбранная выделена."""
    global _task_panel_state
    if not show_task_panel_var.get():
        return
    tasks = [str(t) for t in task_id_combobox['values'] if str(t)]
    version_tasks = set(find_tasks_for_path(ini_path)) if ini_path else set()
    all_tasks = load_data().get("tasks", {})
    missing_tasks = {t for t in tasks if t in all_tasks and not task_folder_exists(all_tasks[t])}
    partly_missing = {t for t in tasks if t in all_tasks and t not in missing_tasks
                      and get_missing_versions(all_tasks[t])}
    selected = task_id_var.get().strip()
    state = (tuple(tasks), frozenset(version_tasks), frozenset(missing_tasks),
             frozenset(partly_missing), selected)
    if state == _task_panel_state:
        return
    _task_panel_state = state

    task_listbox.delete(0, "end")
    for i, task in enumerate(tasks):
        task_listbox.insert("end", task)
        if task in missing_tasks:
            task_listbox.itemconfig(i, foreground="red3")  # папка задачи удалена
        elif task in partly_missing:
            task_listbox.itemconfig(i, foreground="dark orange")  # нет папок у части версий
        elif task not in version_tasks:
            task_listbox.itemconfig(i, foreground="gray55")
    if selected in tasks:
        index = tasks.index(selected)
        task_listbox.selection_set(index)
        task_listbox.see(index)

def _on_task_panel_select(event):
    """Клик по задаче на панели — выбор задачи, как в списке «Номер задачи»."""
    selection = task_listbox.curselection()
    if not selection:
        return
    task_id_var.set(task_listbox.get(selection[0]))  # trace применит задачу
    refresh_task_panel()

task_listbox.bind("<<ListboxSelect>>", _on_task_panel_select)
refresh_task_panel()

def toggle_task_panel():
    """Показывает или скрывает панель задач и меняет ширину окна (позиция окна сохраняется)."""
    global _task_panel_state
    if show_task_panel_var.get():
        task_panel.pack(side="left", fill="y", before=notebook)
        _task_panel_state = None  # пока панель была скрыта, список не обновлялся
        refresh_task_panel()
    else:
        task_panel.pack_forget()
    root.geometry(f"{get_window_width()}x{WINDOW_HEIGHT}")
    save_prefs_flags()

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
        load_refserver_params()
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
        apply_rk7srv_udf_workmodules(rk7srv_ini_path, ini_settings)
    # Применяем Station/Server
    if "Station" in ini_settings and "Server" in ini_settings:
        station_var.set(ini_settings["Station"])
        server_var.set(ini_settings["Server"])
        save_wincash_params()
    # Применяем REFSERVER
    _apply_task_refserver(ini_path_val, ini_settings)
    # Применяем Port
    _apply_task_port(ini_path_val, ini_settings)
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

    # Список файлов и папок, которые нужно скопировать из base (без rk7.udb)
    files_to_copy = [
        "drvlocalize", "workmods", "dealerpresets.udb",
        "upgradedevices.abs", "upgradepresets.abs"
    ]

    try:
        # Создаем папку new_base_path
        os.makedirs(new_base_path, exist_ok=True)

        # Копируем только нужные файлы и папки
        for item in files_to_copy:
            src_item = os.path.join(base_path, item)
            dst_item = os.path.join(new_base_path, item)
            if os.path.exists(src_item):
                if os.path.isdir(src_item):
                    shutil.copytree(src_item, dst_item)
                else:
                    shutil.copy2(src_item, dst_item)
    except Exception as e:
        centered_error("Ошибка", f"Не удалось скопировать файлы base:\n{e}")
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

# load_task_ids импортирована из modules.data_manager

def delete_task(confirm=True):
    """Удаляет выбранную задачу: папки base/MIDBASE, папку задачи и запись в JSON.
    confirm=False — без окна подтверждения (уже спросили, например когда папка задачи не найдена)."""
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

    if confirm and not centered_askyesno("Подтверждение удаления", confirm_msg):
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

    # centered_info("Успех", result_msg)


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
ini_paths, auto_update_enabled, task_from_version_enabled, keep_cloud_files_enabled, _ = load_settings_and_paths()
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
        # find_latest_task_for_path смотрит только основной ini_path задачи,
        # find_tasks_for_path — ещё и пути её версий (task_info["versions"]).
        # Если задача привязана к версии только через versions — берём её.
        path_tasks = find_tasks_for_path(ini_path)
        latest_task_id = find_latest_task_for_path(ini_path) or (path_tasks[0] if path_tasks else None)

        # === ФЛАГ "Выбор задачи из выбора версии" ===
        # Если включён и для версии есть несколько задач — предлагаем выбрать задачу
        if task_from_version_var.get():
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

def check_program_process():
    if is_process_running("refsrv.exe"):
        centered_info("Проверка", "Программа запущена.")
    else:
        centered_warning("Проверка", "Программа не найдена.")

# ======================= Удаление MIDBASE =======================
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
            root.after(0, lambda err=e: (copying_win.destroy(), centered_error("Ошибка", f"Не удалось создать резервную копию:\n{err}")))
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

def start_refsrv_only(ask_if_running=True, upgrade_anytime=False):
    """Запускает refsrv.exe из текущей директории.
    Если этот же сервер (та же база) уже запущен — перезапускает его без вопросов.
    Если в версии работает refsrv другой задачи и ask_if_running=True — спрашивает:
    запустить ещё один рядом с работающим, перезапустить или отменить.
    При ask_if_running=False работающие экземпляры этой версии перезапускаются.
    upgrade_anytime=True — запуск с UpgradeAnyTime=1 (после старта сбрасывается в 0):
    без вопросов закрывается только refsrv текущей задачи, остальные не трогаются.
    Закрываемый refsrv сначала должен действительно завершиться — иначе запуск отменяется."""
    exe_path = os.path.join(ini_path, "refsrv.exe")
    if not os.path.isfile(exe_path):
        centered_error("Ошибка", f"Файл не найден:\n{exe_path}")
        return

    ini_path_norm = os.path.normpath(ini_path).lower()
    all_procs = get_process_by_name('refsrv.exe')
    same_dir = [(p, d) for p, d in all_procs if d == ini_path_norm]

    if not ask_if_running:
        to_close = same_dir
    else:
        to_close = [(p, d) for p, d in same_dir if _is_same_refsrv(p, d)]

    # Свой refsrv не закрывается, а порт занят другим — новый запустится на ближайшем свободном
    current_port, new_port = get_port_value(ini_path), None
    if not to_close and (same_dir or upgrade_anytime) and current_port.isdigit():
        used_ports = get_used_ports()
        if int(current_port) in used_ports:
            new_port = _find_free_port_near(int(current_port), used_ports)
            if new_port is None:
                centered_error("Ошибка", f"Порт {current_port} занят, а свободный порт рядом не найден.")
                return

    if upgrade_anytime:
        # Закрывается только refsrv текущей задачи (to_close), остальные не трогаем и не спрашиваем
        if new_port is not None:
            centered_warning("Порт", f"Порт {current_port} уже занят — refsrv будет запущен на порту {new_port}.")
    elif same_dir and not to_close:
        _, texts, port_details, port_label = _describe_refsrv_processes(same_dir)
        count = "уже запущен refsrv" if len(same_dir) == 1 else f"уже запущено refsrv: {len(same_dir)}"
        msg = f"В этой версии {count}:\n\n" + "\n\n".join(texts)
        if new_port is not None:
            msg += (f"\n\n⚠ Порт {current_port} из rk7srv.INI уже занят — "
                    f"новый refsrv будет запущен на порту {new_port}.")
        msg += "\n\nЗапустить ещё один?"
        choice = centered_askchoice("Refsrv уже запущен", msg,
                                    ["Запустить ещё", "Перезапустить", "Отмена"],
                                    details=port_details, details_label=port_label)
        if choice is None or choice == 2:
            return
        if choice == 1:
            to_close, new_port = same_dir, None

    if new_port is not None:
        _set_port(str(new_port))
        print(f"[PORT] Порт {current_port} занят, новый refsrv на порту {new_port}")

    if to_close:
        # Закрываем только refsrv из текущей директории и ждём, пока они действительно завершатся
        alive = _kill_and_wait([p for p, _ in to_close])
        if alive:
            pids = ", ".join(str(p.pid) for p in alive)
            centered_error("Ошибка", f"Не удалось закрыть refsrv.exe (PID {pids}).\nЗапуск отменён.")
            return

    # Имя REFSERVER не должно совпадать с именами уже запущенных refsrv
    closed_pids = {p.pid for p, _ in to_close}
    running = [(p, d) for p, d in all_procs if p.pid not in closed_pids]
    server_name = get_refserver_name(ini_path)
    taken_names = {get_running_refsrv_name(p, d) for p, d in running} - {""}
    if server_name and server_name.lower() in {n.lower() for n in taken_names}:
        new_name = _make_unique_refserver_name(server_name, taken_names, task_id_var.get().strip())
        _rename_refserver(new_name)
        print(f"[REFSERVER] Имя {server_name} уже занято, новый refsrv запускается как {new_name}")
        centered_warning("REFSERVER",
                         f"Сервер с именем {server_name} уже запущен.\n"
                         f"Для нового refsrv имя изменено на {new_name}.")
        server_name = new_name

    # UseDBSync=1 допустим только у одного запущенного refsrv
    if _rk7srv_dbsync(ini_path) == "1":
        dbsync_servers = [get_running_refsrv_name(p, d) or f"PID {p.pid}"
                          for p, d in running if get_running_refsrv_dbsync(p, d) == "1"]
        if dbsync_servers:
            usedbsync_var.set(0)
            toggle_usedbsync()  # пишет 0 во все INI, в задачу (или дефолты версии)
            task_id = task_id_var.get().strip()
            target = f"для задачи {task_id}" if task_id else "для этой версии"
            print(f"[UseDBSync] Уже запущен refsrv с UseDBSync=1 ({', '.join(dbsync_servers)}), {target} -> 0")
            centered_warning("UseDBSync",
                             f"Уже запущен RefServer с параметром UseDBSync = 1 "
                             f"({', '.join(dbsync_servers)}).\n"
                             f"Поэтому {target} параметр UseDBSync изменён на 0.")

    launch_ini_path = ini_path
    if upgrade_anytime and not set_upgrade_anytime("1", launch_ini_path):
        return

    # Запускаем новый экземпляр
    try:
        subprocess.Popen(f'start "" "{exe_path}" -desktop', shell=True)
    except Exception as e:
        centered_error("Ошибка запуска", str(e))
        if upgrade_anytime:
            set_upgrade_anytime("0", launch_ini_path)  # Сбрасываем даже при ошибке запуска
        return

    before_pids = {p.pid for p, _ in all_procs}
    if upgrade_anytime:
        logging.info("refsrv.exe запущен (UpgradeAnyTime)")
        root.after(500, lambda: _reset_upgrade_anytime_after_start(launch_ini_path, before_pids))

    launch = {"name": server_name, "udb": _current_udb(launch_ini_path),
              "dbsync": _rk7srv_dbsync(launch_ini_path)}
    root.after(500, lambda: _remember_refsrv_launch(ini_path_norm, before_pids, launch))

def _kill_and_wait(procs, timeout=10):
    """Убивает процессы и ждёт, пока они действительно завершатся.
    Возвращает список процессов, которые закрыть не удалось."""
    for proc in procs:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _, alive = psutil.wait_procs(procs, timeout=timeout)
    return alive

# ======================= Параметры запущенных refsrv =======================
# refsrv читает имя сервера и базу из rk7srv.INI при старте, а INI потом могут
# перенастроить на другую задачу. Поэтому при запуске из EngiHelp имя и база
# запоминаются (settings.refsrv_launches, ключ "pid:время старта").
# Для refsrv, запущенных не из EngiHelp, имя берётся из rk7srv.INI их папки,
# а задача — по порту процесса и RefEvents.dat.

def _refsrv_key(proc):
    try:
        return f"{proc.pid}:{int(proc.create_time())}"
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

def _get_refsrv_launch(proc):
    """Запомненные при запуске параметры refsrv: {"name", "udb"} или {}."""
    return load_data()["settings"].get("refsrv_launches", {}).get(_refsrv_key(proc)) or {}

def _current_udb(ini_path_val):
    """Полный путь к базе (UDBFILE) из rk7srv.INI, в нижнем регистре."""
    udb = (get_rk7srv_udb_workmodules(ini_path_val) or {}).get("UDBFILE")
    return os.path.normpath(os.path.join(ini_path_val, udb)).lower() if udb else ""

def get_running_refsrv_name(proc, exe_dir):
    """Имя REFSERVER, с которым запущен refsrv."""
    return _get_refsrv_launch(proc).get("name") or get_refserver_name(exe_dir)

def _rk7srv_dbsync(ini_path_val):
    """UseDBSync из rk7srv.INI ("1"/"0")."""
    return get_usedbsync_values(ini_path_val).get("rk7srv.INI", "0")

def get_running_refsrv_dbsync(proc, exe_dir):
    """UseDBSync, с которым запущен refsrv: запомненный при запуске, иначе из настроек
    его задачи для этой версии в JSON, иначе из rk7srv.INI его папки."""
    launch = _get_refsrv_launch(proc)
    if "dbsync" in launch:
        return launch["dbsync"]
    found, task_id = _running_refsrv_task(proc, exe_dir, get_process_listening_ports(proc.pid))
    if found and task_id:
        task_info = load_data().get("tasks", {}).get(task_id, {})
        exe_norm = os.path.normpath(exe_dir).lower()
        entries = list(task_info.get("versions", {}).values()) + [task_info]
        for entry in entries:
            if os.path.normpath(entry.get("ini_path", "")).lower() != exe_norm:
                continue
            value = (entry.get("ini_settings") or {}).get("UseDBSync")
            if isinstance(value, dict) and value.get("rk7srv.INI"):
                return str(value["rk7srv.INI"])
    return _rk7srv_dbsync(exe_dir)

def _is_same_refsrv(proc, exe_dir):
    """True — refsrv относится к выбранной задаче (задача не выбрана — работает с базой без задачи),
    то есть это тот же сервер, и его достаточно перезапустить.
    Сравнивается именно задача, а не UDBFILE из rk7srv.INI: INI могли перенастроить после запуска."""
    found, running_task = _running_refsrv_task(proc, exe_dir, get_process_listening_ports(proc.pid))
    current_task = task_id_var.get().strip() or None
    return found and (running_task or None) == current_task

def _remember_refsrv_launch(exe_dir_norm, before_pids, launch, attempts=20):
    """Ждёт появления нового refsrv из exe_dir_norm и запоминает, с какими именем и базой он запущен.
    Записи о завершённых процессах при этом удаляются."""
    procs = get_process_by_name('refsrv.exe')
    new_procs = [p for p, d in procs if d == exe_dir_norm and p.pid not in before_pids]
    if not new_procs:
        if attempts > 0:
            root.after(500, lambda: _remember_refsrv_launch(exe_dir_norm, before_pids, launch, attempts - 1))
        return
    alive_keys = {_refsrv_key(p) for p, _ in procs}
    data = load_data()
    launches = {k: v for k, v in data["settings"].get("refsrv_launches", {}).items() if k in alive_keys}
    for p in new_procs:
        key = _refsrv_key(p)
        if key:
            launches[key] = launch
    data["settings"]["refsrv_launches"] = launches
    save_data(data)

def _make_unique_refserver_name(name, taken_names, task_id):
    """Добавляет к имени _{номер задачи}; если и так занято (или задачи нет) — _2, _3 ..."""
    taken = {n.lower() for n in taken_names}
    suffix = f"_{task_id}"
    base = name if not task_id or name.lower().endswith(suffix.lower()) else name + suffix
    candidate, n = base, 2
    while candidate.lower() in taken:
        candidate = f"{base}_{n}"
        n += 1
    return candidate

def _rename_refserver(new_name):
    """Меняет имя REFSERVER: rk7srv.INI, RKEEPER.INI, rk7man.ini ([REFEDIT] и [TCPDNS]),
    поле «REFSERVER» и настройки задачи (или дефолты версии)."""
    refserver_var.set(new_name)  # trace сам пишет имя в rk7srv.INI, RKEEPER.INI и rk7man.ini [REFEDIT]
    port = get_port_value(ini_path)
    if port:
        apply_port(ini_path, port)  # запись {имя}=127.0.0.1:{порт} в [TCPDNS] rk7man.ini
    task_id = task_id_var.get().strip()
    if task_id:
        apply_network_ids_silent_for_task(task_id)
    else:
        sync_default_settings_if_no_task()

def start_rk7man_only():
    """Запускает rk7man.bat из текущей директории, закрывая только свой экземпляр."""
    ini_path_norm = os.path.normpath(ini_path).lower()

    # Закрываем только rk7man из текущей директории
    for proc, exe_dir in get_process_by_name('rk7man.exe'):
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

# ======================= Запуск wincash.bat =======================
# (функция run_wincash_bat удалена - использовалась start_wincash_only)

# DOSCASH.EXE нужно закрыть перед запуском если есть

def run_refsrv_and_rk7man():
    ini_path_norm = os.path.normpath(ini_path).lower()
    current_port = get_port_value(ini_path)

    # Проверяем, занят ли текущий порт другим refsrv (не из текущей директории)
    if current_port:
        used_ports = get_used_ports()
        if int(current_port) in used_ports:
            # Проверяем, есть ли refsrv на этом порту из другой директории
            conflict = False
            for proc, exe_dir in get_process_by_name('refsrv.exe'):
                if exe_dir != ini_path_norm:
                    ports = get_process_listening_ports(proc.pid)
                    if int(current_port) in ports:
                        conflict = True
                        break

            if conflict:
                # Пробуем текущий +1, +2, +3...
                new_port = int(current_port) + 1
                while new_port in used_ports and new_port < int(current_port) + 100:
                    new_port += 1

                if new_port < int(current_port) + 100:
                    server_name = get_refserver_name(ini_path)
                    if set_port_rk7srv(ini_path, str(new_port)):
                        set_port_rk7man(ini_path, server_name, str(new_port))
                        print(f"[PORT] Смена порта: {current_port} -> {new_port}")
                else:
                    centered_error("Ошибка", "Не удалось найти свободный порт")

    start_refsrv_only(ask_if_running=False)
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
    for proc, exe_dir in get_process_by_name('midserv.exe'):
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
    for proc, exe_dir in get_process_by_name('doscash.exe'):
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
        subprocess.Popen([bat_path], shell=True, cwd=ini_path)
    except Exception as e:
        centered_error("Ошибка запуска", str(e))


# ======================= Запуск MidServ + WinCash =======================
def run_midserv_and_wincash():
    start_midserv_only()
    root.after(1500, start_wincash_only)

# ======================= Закрыть процес =======================
def kill_midserv_process():
    """Завершает midserv.exe (обёртка для модульной функции)."""
    kill_midserv()

def _running_refsrv_task(proc, exe_dir, ports):
    """Задача, с базой которой работает refsrv: по запомненной при запуске базе,
    иначе по портам и RefEvents.dat, иначе по rk7srv.INI его папки.
    Возвращает (найдено, task_id); task_id = None — база без задачи."""
    udb = _get_refsrv_launch(proc).get("udb")
    if udb:
        m = re.search(r'([^\\/]+)[\\/]base[\\/][^\\/]+$', udb)
        if m and not m.group(1).lower().startswith("inst"):
            return True, m.group(1)
        m = re.search(r'[\\/]base_([^\\/]+)[\\/]', udb)  # старый формат base_{задача}
        return True, m.group(1) if m else None
    found, task_id = find_running_task_by_ports(exe_dir, ports)
    if not found:
        found, task_id = find_last_running_task(exe_dir)
    if not found:
        task_id = extract_task_id_from_rk7srv_ini(os.path.join(exe_dir, "rk7srv.INI"))
        found = bool(task_id)
    return found, task_id

def _describe_refsrv_processes(procs):
    """Описание refsrv-процессов для окна закрытия. procs — список (proc, exe_dir).
    Процессы упорядочиваются: сначала выбранная задача текущей версии, остальные — по времени
    запуска, новые сверху. Текст каждого — три строки: задача, имя сервера, процесс с путём и PID;
    порты уходят в свёрнутый блок.
    Возвращает (процессы в новом порядке, список текстов, текст портов, заголовок блока)."""
    selected_task = task_id_var.get().strip()
    ini_path_norm = os.path.normpath(ini_path).lower()

    rows = []
    for proc, exe_dir in procs:
        ports = get_process_listening_ports(proc.pid)
        found, task_id = _running_refsrv_task(proc, exe_dir, ports)
        is_selected = bool(selected_task) and task_id == selected_task and exe_dir == ini_path_norm
        try:
            started = proc.create_time()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            started = 0
        rows.append((proc, exe_dir, ports, found, task_id, is_selected, started))
    rows.sort(key=lambda r: (not r[5], -r[6]))

    ordered, texts, port_blocks, total_ports = [], [], [], 0
    for proc, exe_dir, ports, found, task_id, is_selected, started in rows:
        if task_id:
            task_line = f"Задача {task_id}"
        else:
            task_line = "Без задачи" if found else "Задача не определена"
        if is_selected:
            task_line += " (выбрана)"
        version = extract_rk_version_from_path(exe_dir)
        port = _main_refsrv_port(exe_dir, task_id, ports) or get_port_value_for_path(exe_dir)
        details = [part for part in (f"версия {version}" if version else "",
                                     f"порт {port}" if port else "") if part]
        if details:
            task_line += " · " + ", ".join(details)

        server_name = get_running_refsrv_name(proc, exe_dir)
        started_text = time.strftime("%d.%m %H:%M", time.localtime(started)) if started else ""
        lines = [
            task_line,
            f"Сервер: {server_name or 'не определён'}" + (f" · запущен {started_text}" if started_text else ""),
            f"refsrv.exe · {exe_dir} · PID {proc.pid}",
        ]
        ordered.append((proc, exe_dir))
        texts.append("\n".join(lines))
        if ports:
            total_ports += len(ports)
            port_lines = "\n".join(line.strip() for line in get_port_info(ports).splitlines())
            port_blocks.append(f"PID {proc.pid}:\n{port_lines}" if len(rows) > 1 else port_lines)
    if not port_blocks:
        return ordered, texts, None, None
    return ordered, texts, "\n\n".join(port_blocks), f"Порты refsrv ({total_ports})"

def _kill_checked(procs, checked):
    """Закрывает процессы, для которых в окне остался отмеченным флажок."""
    for proc, is_checked in zip(procs, checked):
        if proc is None or not is_checked:
            continue
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def kill_refsrv_and_rk7man():
    """Комбинированное закрытие refsrv + rk7man: если оба из текущей директории —
    сразу закрывает, иначе показывает окно со всеми процессами (флажки — что закрыть)."""
    ini_path_norm = os.path.normpath(ini_path).lower()

    refsrv_procs = get_process_by_name('refsrv.exe')
    rk7man_procs = get_process_by_name('rk7man.exe')

    refsrv_same = [p for p, d in refsrv_procs if d == ini_path_norm]
    refsrv_other = [(p, d) for p, d in refsrv_procs if d != ini_path_norm]
    rk7man_same = [p for p, d in rk7man_procs if d == ini_path_norm]
    rk7man_other = [(p, d) for p, d in rk7man_procs if d != ini_path_norm]

    # Если оба из той же директории (refsrv один) — сразу закрываем без запроса
    if len(refsrv_same) == 1 and rk7man_same:
        refsrv_same[0].terminate()
        rk7man_same[0].terminate()
        return

    # Иначе — окно с флажками: entries[i] — строка окна, procs[i] — её процесс (None — просто текст).
    # refsrv: выбранная задача первой, остальные — новые сверху; rk7man — текущей версии первыми.
    entries, procs = [], []
    refsrv_list = [(p, ini_path_norm) for p in refsrv_same] + refsrv_other
    rk7man_list = [(p, ini_path_norm) for p in rk7man_same] + rk7man_other

    # Порты refsrv показываем свёрнутым блоком — нужны редко
    refsrv_list, refsrv_texts, refsrv_ports, refsrv_ports_label = _describe_refsrv_processes(refsrv_list)
    for (p, _), text in zip(refsrv_list, refsrv_texts):
        entries.append((text, True))
        procs.append(p)
    if not refsrv_procs:
        entries.append(("✗ refsrv.exe (не запущен)", False))
        procs.append(None)

    for p, exe_dir in rk7man_list:
        port_info = "\n".join(line.strip() for line in get_rk7man_port_info(p.pid).splitlines())
        entries.append((f"rk7man.exe ({exe_dir})" + (f"\n{port_info}" if port_info else ""), True))
        procs.append(p)
    if not rk7man_procs:
        entries.append(("✗ rk7man.exe (не запущен)", False))
        procs.append(None)

    checked = centered_askchecklist("Закрыть refsrv + rk7man", entries, "Закрыть отмеченные процессы?",
                                    details=refsrv_ports, details_label=refsrv_ports_label)
    if checked:
        _kill_checked(procs, checked)


def kill_refsrv_process():
    """Закрывает refsrv.exe: если запущен из текущего ini_path — закрывает сразу,
    иначе показывает окно с процессами других версий (флажки — что закрыть)."""
    ini_path_norm = os.path.normpath(ini_path).lower()
    procs = get_process_by_name('refsrv.exe')

    same_dir = [(p, d) for p, d in procs if d == ini_path_norm]
    other_dir = [(p, d) for p, d in procs if d != ini_path_norm]

    if len(same_dir) == 1:
        same_dir[0][0].kill()
        return

    # Несколько refsrv в этой версии или только из других — окно с флажками:
    # выбранная задача первой, остальные — по времени запуска, новые сверху
    if same_dir or other_dir:
        listed, texts, port_details, port_label = _describe_refsrv_processes(same_dir + other_dir)
        checked = centered_askchecklist("Закрыть refsrv.exe", [(text, True) for text in texts],
                                        "Закрыть отмеченные процессы?",
                                        details=port_details, details_label=port_label)
        if checked:
            _kill_checked([p for p, _ in listed], checked)
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
    procs = get_process_by_name('rk7man.exe')

    same_dir = [(p, d) for p, d in procs if d == ini_path_norm]
    other_dir = [(p, d) for p, d in procs if d != ini_path_norm]

    if same_dir:
        same_dir[0][0].kill()
        return

    if other_dir:
        proc, exe_dir = other_dir[0]
        port_info = get_rk7man_port_info(proc.pid)
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
    """Завершает doscash.exe (обёртка для модульной функции)."""
    kill_doscash()


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
usesql_var = tk.IntVar(value=int(get_usesql_value(ini_path)))
usedbsync_var = tk.IntVar(value=int(detect_consensus_value(ini_path)))
port_var = tk.StringVar(value=get_port_value(ini_path))

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
    _set_port(str(new_port))

def _set_port(port):
    """Применяет порт в rk7srv.INI и rk7man.ini, обновляет поле порта
    и сохраняет его в ini_settings задачи (и её активной версии) или в дефолты версии."""
    port_var.set(port)
    apply_port(ini_path, port)
    task_id = task_id_var.get().strip()
    if task_id:
        _save_task_port(task_id, port)
    else:
        sync_default_settings_if_no_task()

def _find_free_port_near(port, used_ports, max_offset=100):
    """Ищет ближайший свободный порт: +1, -1, +2, -2 ... Возвращает None, если не найден."""
    for offset in range(1, max_offset + 1):
        for candidate in (port + offset, port - offset):
            if 1 <= candidate <= 65535 and candidate not in used_ports:
                return candidate
    return None

def _save_task_port(task_id, port, data=None):
    """Сохраняет Port в ini_settings задачи и её активной версии (по ini_path).
    Без версии apply_task_version при следующем переключении затёр бы порт старым.
    Если data передан — только изменяет его (сохранение делает вызывающий код)."""
    own_data = data is None
    if own_data:
        data = load_data()
    task_data = data.get("tasks", {}).get(task_id)
    if not task_data:
        return
    task_data.setdefault("ini_settings", {})["Port"] = port
    active_ini_path = task_data.get("ini_path", "")
    for version_data in task_data.get("versions", {}).values():
        if version_data.get("ini_path") == active_ini_path:
            version_data.setdefault("ini_settings", {})["Port"] = port
            break
    if own_data:
        save_data(data)
        print(f"[PORT] Сохранён порт {port} для задачи {task_id}")

def _apply_task_port(ini_path_val, ini_settings):
    """Применяет Port из ini_settings. Если у задачи порт не сохранён — берёт порт
    из дефолтных настроек версии, чтобы не остался порт предыдущей задачи."""
    port = ini_settings.get("Port")
    if not port:
        default_entry = load_default_ini_settings(ini_path_val) or {}
        port = default_entry.get("ini_settings", {}).get("Port")
    if port:
        apply_port(ini_path_val, str(port))
        port_var.set(str(port))

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
refserver_var = tk.StringVar()

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

def load_refserver_params(ini_path_val=None):
    """Читает имя REFSERVER из rk7srv.INI [REFSERVER] Server = ..."""
    global ini_path
    if ini_path_val is None:
        ini_path_val = ini_path
    rk7srv_path = os.path.join(ini_path_val, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return
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
                    refserver_var.set(m.group(1).strip())
                    break
    except Exception:
        pass

def _apply_task_refserver(ini_path_val, ini_settings):
    """Применяет REFSERVER из настроек задачи. Если в задаче имя не сохранено (пусто) —
    поле показывает имя из rk7srv.INI, а при смене задачи оно сохранится в задачу."""
    refserver_value = (ini_settings.get("REFSERVER") or "").strip()
    if refserver_value:
        refserver_var.set(refserver_value)
        save_refserver_params()
    else:
        refserver_var.set("")
        load_refserver_params(ini_path_val)

def save_refserver_params():
    """Сохраняет REFSERVER в rk7srv.INI, RKEEPER.INI и rk7man.ini."""
    ref_value = refserver_var.get().strip()
    if not ref_value:
        return

    # 1. rk7srv.INI [REFSERVER] Server = ...
    rk7srv_path = os.path.join(ini_path, "rk7srv.INI")
    if os.path.isfile(rk7srv_path):
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
            in_refserver = False
            server_updated = False
            for line in lines:
                stripped = line.strip()
                if re.match(r'^\[REFSERVER\]', stripped, re.IGNORECASE):
                    in_refserver = True
                    server_updated = False
                    new_lines.append(line)
                    continue
                if in_refserver:
                    if stripped.startswith('['):
                        # Вышли из секции - добавляем Server только если он ещё не был обновлён
                        if not server_updated:
                            new_lines.append(f"Server             = {ref_value}\n")
                        in_refserver = False
                    elif re.match(r'^\s*Server\s*=', stripped, re.IGNORECASE):
                        new_lines.append(f"Server             = {ref_value}\n")
                        server_updated = True
                        continue
                new_lines.append(line)

            if in_refserver and not server_updated:
                new_lines.append(f"Server             = {ref_value}\n")

            if not server_updated and not in_refserver:
                if new_lines and not new_lines[-1].endswith('\n'):
                    new_lines.append('\n')
                new_lines.append("\n[REFSERVER]\n")
                new_lines.append(f"Server             = {ref_value}\n")

            shutil.copy2(rk7srv_path, rk7srv_path + ".bak")
            with open(rk7srv_path, 'w', encoding=enc) as f:
                f.writelines(new_lines)
        except Exception as e:
            centered_error("Ошибка", f"Не удалось обновить rk7srv.INI:\n{e}")

    # 2. RKEEPER.INI [Config] RefServer = ...
    rkeeper_path = os.path.join(ini_path, "RKEEPER.INI")
    if os.path.isfile(rkeeper_path):
        try:
            try:
                with open(rkeeper_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                enc = 'utf-8'
            except UnicodeDecodeError:
                with open(rkeeper_path, 'r', encoding='cp1251') as f:
                    lines = f.readlines()
                enc = 'cp1251'

            new_lines = []
            in_config = False
            refserver_updated = False
            for line in lines:
                stripped = line.strip()
                if re.match(r'^\[Config\]', stripped, re.IGNORECASE):
                    in_config = True
                    refserver_updated = False
                    new_lines.append(line)
                    continue
                if in_config:
                    if stripped.startswith('['):
                        # Вышли из секции - добавляем RefServer только если он ещё не был обновлён
                        if not refserver_updated:
                            new_lines.append(f"RefServer = {ref_value}\n")
                        in_config = False
                    elif re.match(r'^\s*RefServer\s*=', stripped, re.IGNORECASE):
                        new_lines.append(f"RefServer = {ref_value}\n")
                        refserver_updated = True
                        continue
                new_lines.append(line)

            if in_config and not refserver_updated:
                new_lines.append(f"RefServer = {ref_value}\n")

            if not refserver_updated and not in_config:
                if new_lines and not new_lines[-1].endswith('\n'):
                    new_lines.append('\n')
                new_lines.append("\n[Config]\n")
                new_lines.append(f"RefServer = {ref_value}\n")

            shutil.copy2(rkeeper_path, rkeeper_path + ".bak")
            with open(rkeeper_path, 'w', encoding=enc) as f:
                f.writelines(new_lines)
        except Exception as e:
            centered_error("Ошибка", f"Не удалось обновить RKEEPER.INI:\n{e}")

    # 3. rk7man.ini [REFEDIT] Server=...
    rk7man_path = os.path.join(ini_path, "rk7man.ini")
    if os.path.isfile(rk7man_path):
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
            in_refedit = False
            server_updated = False
            for line in lines:
                stripped = line.strip()
                if re.match(r'^\[REFEDIT\]', stripped, re.IGNORECASE):
                    in_refedit = True
                    server_updated = False
                    new_lines.append(line)
                    continue
                if in_refedit:
                    if stripped.startswith('['):
                        # Вышли из секции - добавляем Server только если он ещё не был обновлён
                        if not server_updated:
                            new_lines.append(f"Server={ref_value}\n")
                        in_refedit = False
                    elif re.match(r'^\s*Server\s*=', stripped, re.IGNORECASE):
                        new_lines.append(f"Server={ref_value}\n")
                        server_updated = True
                        continue
                new_lines.append(line)

            if in_refedit and not server_updated:
                new_lines.append(f"Server={ref_value}\n")

            if not server_updated and not in_refedit:
                if new_lines and not new_lines[-1].endswith('\n'):
                    new_lines.append('\n')
                new_lines.append("\n[REFEDIT]\n")
                new_lines.append(f"Server={ref_value}\n")

            shutil.copy2(rk7man_path, rk7man_path + ".bak")
            with open(rk7man_path, 'w', encoding=enc) as f:
                f.writelines(new_lines)
        except Exception as e:
            centered_error("Ошибка", f"Не удалось обновить rk7man.ini:\n{e}")


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
    save_refserver_params()
    centered_info("Успех", f"Данные сохранены для задачи {task_id}")

def apply_network_ids_silent():
    """Сохраняет Station и Server в JSON без показа messagebox (для фонового сохранения при смене задачи)."""
    task_id = task_id_var.get().strip()
    apply_network_ids_silent_for_task(task_id)

def apply_network_ids_silent_for_task(task_id):
    """Сохраняет Station, Server и REFSERVER в JSON для указанной задачи (без messagebox)."""
    if not task_id:
        return

    station_value = station_var.get().strip()
    server_value = server_var.get().strip()
    refserver_value = refserver_var.get().strip()

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
    task_data["ini_settings"]["REFSERVER"] = refserver_value

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
                version_data["ini_settings"]["REFSERVER"] = refserver_value
                break  # Нашли активную версию, выходим

    data["tasks"] = tasks
    save_data(data)

    # Дополнительно применяем в реальные ini-файлы
    save_wincash_params()
    save_refserver_params()

def apply_ini_flags_silent_for_task(task_id):
    """Сохраняет UseSQL, UseDBSync и Port в JSON для указанной задачи (при смене задачи)."""
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

    # Port — текущий порт уходящей задачи (иначе при возврате к ней останется чужой)
    port = port_var.get().strip()
    if port.isdigit():
        _save_task_port(task_id, port, data)

    data["tasks"] = tasks
    save_data(data)

# === UI ===
info_frame = tk.LabelFrame(settings_tab, text="Сетевые ID")
info_frame.pack(padx=10, pady=(5, 10), fill="x", ipadx=2, ipady=2)

# Столбец 0: Метки MID и CASH
tk.Label(info_frame, text="MID:").grid(row=0, column=0, sticky="w", padx=(5, 0), pady=3)
tk.Label(info_frame, text="CASH:").grid(row=1, column=0, sticky="w", padx=(5, 0), pady=3)

# Столбец 1: Поля ввода MID и CASH
tk.Entry(info_frame, textvariable=server_var).grid(row=0, column=1, sticky="ew", padx=5, pady=3)
tk.Entry(info_frame, textvariable=station_var).grid(row=1, column=1, sticky="ew", padx=5, pady=3)

# Столбец 2: Метка REFSERVER
tk.Label(info_frame, text="REFSERVER:").grid(row=0, column=2, sticky="w", padx=(15, 0), pady=3)

# Столбец 3: Поле REFSERVER и кнопка "Применить"
tk.Entry(info_frame, textvariable=refserver_var, width=20).grid(row=0, column=3, sticky="ew", padx=5, pady=3)
apply_btn = tk.Button(info_frame, text="Применить", command=apply_network_ids)
apply_btn.grid(row=1, column=3, sticky="ew", padx=13, pady=2)

info_frame.grid_columnconfigure(1, weight=1)
info_frame.grid_columnconfigure(2, minsize=80)
info_frame.grid_columnconfigure(3, minsize=80)

# Автосохранение при любом изменении
station_var.trace_add("write", lambda *args: save_wincash_params())
server_var.trace_add("write", lambda *args: save_wincash_params())
refserver_var.trace_add("write", lambda *args: save_refserver_params())



# Автозагрузка значений при старте
load_wincash_params()
load_refserver_params()

def _copy_missing_ini_files(bin_win_path):
    """Копирует недостающие INI-файлы из bin\\win\\ini в bin\\win. Возвращает (missing, copied)."""
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
    return missing, copied

def ensure_ini_files(bin_win_path):
    """Перед применением задачи: если в версии нет INI-файлов — предлагает добавить их
    из bin\\win\\ini. True — rk7srv.INI на месте и задачу можно применять."""
    missing = [f for f in FILES if not os.path.isfile(os.path.join(bin_win_path, f))]
    if not missing:
        return True
    if centered_askyesno("Нет INI-файлов",
                         f"В версии нет файлов: {', '.join(missing)}\n{bin_win_path}\n\n"
                         f"Добавить из папки bin\\win\\ini и продолжить?"):
        _, copied = _copy_missing_ini_files(bin_win_path)
        print(f"[INI] Скопированы из bin\\win\\ini: {', '.join(copied) or 'ничего'}")
    if os.path.isfile(os.path.join(bin_win_path, "rk7srv.INI")):
        return True
    centered_error("Ошибка", f"Файл rk7srv.INI не найден:\n{os.path.join(bin_win_path, 'rk7srv.INI')}")
    return False

def copy_missing_ini_files():
    missing, copied = _copy_missing_ini_files(ini_path)
    if copied:
        centered_info("Файлы скопированы", f"Скопированы из bin\\win\\ini:\n{', '.join(copied)}")
    elif not missing:
        centered_info("Все файлы на месте", "Все необходимые INI-файлы уже присутствуют.")
    else:
        centered_warning("Нет файлов", "Отсутствующие файлы не найдены даже в bin\\win\\ini.")

def on_check_with_message():
    found, missing = check_files(ini_path)

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
cloud_rk7man_btn = tk.Button(check_folder_frame, text="Cloud RK7man", command=lambda: cloud_rk7man_dialog(root, ini_path, keep_cloud_files_var, icon_path))
cloud_rk7man_btn.grid(row=1, column=2, padx=5, sticky="ew", pady=(5, 0))

# Настройка весов строк и столбцов для равномерного распределения
check_folder_frame.grid_columnconfigure(0, weight=1)
check_folder_frame.grid_columnconfigure(1, weight=1)
check_folder_frame.grid_columnconfigure(2, weight=1)



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
        save_window_position()
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
    data["settings"]["delete_zip_after_extract"] = delete_zip_after_extract_var.get()
    data["settings"]["show_task_panel"] = show_task_panel_var.get()
    data["settings"]["clean_backups"] = clean_backups_var.get()
    data["settings"]["backups_keep"] = get_backups_keep()
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

tk.Checkbutton(
    prefs_tab,
    text="Удалять ZIP архив после распаковки версии",
    variable=delete_zip_after_extract_var,
    command=save_prefs_flags
).pack(padx=10, pady=(5, 2), anchor="w")

delete_zip_desc_label = tk.Label(
    prefs_tab,
    text="После скачивания и успешной распаковки версии RK, ZIP архив будет удалён.",
    justify="left",
    fg="gray40",
    font=("TkDefaultFont", 8),
    wraplength=350,
    anchor="w"
)
delete_zip_desc_label.pack(padx=(30, 10), pady=(0, 10), anchor="w", fill="x")

tk.Checkbutton(
    prefs_tab,
    text="Показывать панель задач",
    variable=show_task_panel_var,
    command=toggle_task_panel
).pack(padx=10, pady=(5, 2), anchor="w")

task_panel_desc_label = tk.Label(
    prefs_tab,
    text="Список задач слева от вкладок. Клик по задаче выбирает её; задачи других версий — серым.",
    justify="left",
    fg="gray40",
    font=("TkDefaultFont", 8),
    wraplength=350,
    anchor="w"
)
task_panel_desc_label.pack(padx=(30, 10), pady=(0, 10), anchor="w", fill="x")

# --- Старые бэкапы базы ---
def get_backups_keep():
    """Сколько последних бэкапов хранить (в поле могли ввести не число — тогда по умолчанию)."""
    try:
        return max(1, int(backups_keep_var.get()))
    except (tk.TclError, ValueError):
        return DEFAULT_BACKUPS_KEEP

def clean_backups_now(confirm=True):
    """Удаляет у всех задач бэкапы базы сверх последних N. С подтверждением — показывает,
    сколько будет удалено. Возвращает False, если пользователь отказался."""
    keep = get_backups_keep()
    root.config(cursor="watch")
    root.update_idletasks()
    try:
        old = find_old_backups(all_base_paths(), keep)
    finally:
        root.config(cursor="")
    if not old:
        if confirm:
            centered_info("Бэкапы базы", f"Лишних бэкапов нет — у каждой задачи не больше {keep}.")
        return True
    size = sum(s for _, s in old)
    if confirm and not centered_askyesno(
            "Удалить старые бэкапы?",
            f"У задач будет удалено старых бэкапов базы: {len(old)} ({format_size(size)}).\n"
            f"У каждой задачи останутся {keep} последних.",
            details="\n".join(p for p, _ in old), details_label="Список бэкапов"):
        return False
    root.config(cursor="watch")
    root.update_idletasks()
    try:
        deleted, freed, errors = delete_backups(old)
    finally:
        root.config(cursor="")
    print(f"[BACKUPS] Удалено {deleted} бэкапов, освобождено {format_size(freed)}")
    if confirm:
        message = f"Удалено бэкапов: {deleted}, освобождено {format_size(freed)}."
        if errors:
            message += "\n\nНе удалось удалить (возможно, файлы заняты refsrv):\n" + "\n".join(errors[:10])
        centered_info("Бэкапы базы", message)
    return True

def clean_backups_in_background(task_ids=None):
    """Тихая очистка в фоне — при запуске программы и при выборе задачи."""
    if not clean_backups_var.get():
        return
    keep = get_backups_keep()
    base_paths = all_base_paths(task_ids)  # JSON читаем здесь, а не в потоке

    def run():
        deleted, freed, errors = delete_backups(find_old_backups(base_paths, keep))
        if deleted or errors:
            print(f"[BACKUPS] Удалено {deleted} старых бэкапов ({format_size(freed)}), ошибок: {len(errors)}")
    threading.Thread(target=run, daemon=True).start()

def toggle_clean_backups():
    # При включении сразу показываем, что будет удалено; отказались — флаг снимается
    if clean_backups_var.get() and not clean_backups_now():
        clean_backups_var.set(False)
    save_prefs_flags()

tk.Checkbutton(
    prefs_tab,
    text="Удалять старые бэкапы базы",
    variable=clean_backups_var,
    command=toggle_clean_backups
).pack(padx=10, pady=(5, 2), anchor="w")

backups_keep_frame = tk.Frame(prefs_tab)
backups_keep_frame.pack(padx=(30, 10), pady=(0, 2), anchor="w")
tk.Label(backups_keep_frame, text="Хранить последних:").pack(side="left")
tk.Spinbox(backups_keep_frame, from_=1, to=100, width=4,
           textvariable=backups_keep_var).pack(side="left", padx=(5, 10))
backups_keep_var.trace_add("write", lambda *_: save_prefs_flags())
tk.Button(backups_keep_frame, text="Очистить сейчас", command=clean_backups_now).pack(side="left")

backups_desc_label = tk.Label(
    prefs_tab,
    text=("Бэкапы refsrv в папке base\\backups\\databases каждой задачи. "
          "Лишние старые удаляются при запуске программы и при выборе задачи."),
    justify="left",
    fg="gray40",
    font=("TkDefaultFont", 8),
    wraplength=350,
    anchor="w"
)
backups_desc_label.pack(padx=(30, 10), pady=(0, 10), anchor="w", fill="x")

# ======================= Вкладка "Что нового" =======================
changelog_tab = tk.Frame(notebook)
notebook.add(changelog_tab, text="Что нового")

changelog_scroll = tk.Scrollbar(changelog_tab, orient="vertical")
changelog_text = tk.Text(
    changelog_tab,
    wrap="word",
    font="TkDefaultFont",
    relief="flat",
    borderwidth=0,
    background=changelog_tab.cget("background"),
    cursor="arrow",
    padx=10,
    pady=8,
    yscrollcommand=changelog_scroll.set
)
changelog_scroll.config(command=changelog_text.yview)
changelog_scroll.pack(side="right", fill="y")
changelog_text.pack(side="left", fill="both", expand=True)

changelog_text.tag_configure("version", font=("TkDefaultFont", 9, "bold"), spacing1=8)
changelog_text.tag_configure("current", font=("TkDefaultFont", 8), foreground="green4")
changelog_text.tag_configure("date", font=("TkDefaultFont", 8), foreground="gray40")
changelog_text.tag_configure("item", lmargin1=8, lmargin2=20, spacing1=1)

for entry in CHANGELOG:
    changelog_text.insert("end", entry["version"], "version")
    if entry["version"] == SCRIPT_VERSION:
        changelog_text.insert("end", "  текущая", ("version", "current"))
    changelog_text.insert("end", f"  {entry['date']}\n", ("version", "date"))
    for item in entry["items"]:
        changelog_text.insert("end", f"•  {item}\n", "item")
changelog_text.config(state="disabled")

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
    # Обновляем список задач на панели слева (задачи могли добавить, удалить или сменить)
    refresh_task_panel()
    # Планируем следующее обновление через 1000 миллисекунд (1 секунд)
    root.after(1000, update_every_1_seconds)

# Вызовем эту функцию для начала цикла обновлений
root.after(1000, update_every_1_seconds)

# Проверка автообновления при старте
if auto_update_var.get():
    root.after(1000, lambda: check_for_updates(silent=True))

# Очистка старых бэкапов базы у всех задач (если включена в настройках)
root.after(3000, clean_backups_in_background)

# === Инициализация глобальных горячих клавиш ===
root.protocol("WM_DELETE_WINDOW", on_closing)
setup_global_hotkeys()

on_check()
root.deiconify()
root.mainloop()


# pyinstaller --onefile --windowed --icon=".\.ico\иконка EngiHelp.ico" --add-data "modules;modules" --hidden-import=tkinter --clean EngiHelp.py