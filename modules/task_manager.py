# ======================= task_manager.py =======================
# Управление задачами

import os
import re
import shutil
from datetime import datetime

import psutil

from .data_manager import load_data, save_data
from .ini_utils import update_rkeeper_ini_basepath, get_ini_settings, update_rk7srv_ini, get_port_value_for_path
from .shortcuts import create_task_shortcuts

# ======================= Вспомогательные функции =======================

def extract_task_id_from_rk7srv_ini(ini_path):
    """Извлекает task_id из rk7srv.INI."""
    if not os.path.exists(ini_path):
        return None
    try:
        with open(ini_path, 'r', encoding='cp1251') as file:
            for line in file:
                line = line.strip()
                if line.lower().startswith("udbfile") or line.lower().startswith("workmodules"):
                    match = re.search(r'([a-zA-Z0-9_]+)[/\\]base[/\\]', line)
                    if match:
                        return match.group(1)
                    match = re.search(r'base_([a-zA-Z0-9_]+)', line)
                    if match:
                        return match.group(1)
    except Exception as e:
        print(f"Ошибка при чтении rk7srv.INI: {e}")
    return None

def find_product_root(selected_path):
    """Определяет корневую папку продукта (INST...)."""
    original = selected_path

    if os.path.basename(original).lower() == "win":
        parent = os.path.dirname(original)
        if os.path.basename(parent).lower() == "bin":
            root = os.path.dirname(parent)
        else:
            return None
    elif os.path.basename(original).lower() == "bin":
        root = os.path.dirname(original)
    else:
        root = original

    from . import FILES
    bin_win = os.path.join(root, "bin", "win")
    if all(os.path.isfile(os.path.join(bin_win, f)) for f in FILES):
        return root

    return None

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

# ======================= Создание задачи и подписи =======================

def create_task_for_version(task_id, version_path):
    """
    Создаёт новую задачу для указанной версии RK.
    Копирует base, создаёт пустую MIDBASE, обновляет INI и сохраняет в JSON.
    """
    task_id = task_id.strip()
    if not task_id:
        return False, "Номер задачи не может быть пустым"

    product_root = find_product_root(version_path)
    if not product_root:
        return False, "Не удалось определить корневую папку продукта"

    base_path = os.path.join(product_root, "base")
    if not os.path.exists(base_path):
        return False, f"Папка base не найдена: {base_path}"

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
                return False, "Файлы в папке base заблокированы процессом refsrv.exe"
            except Exception as e:
                return False, f"Ошибка проверки блокировки: {e}"

    # Проверяем, не существует ли уже задача с таким ID
    data = load_data()
    tasks = data.get("tasks", {})
    if task_id in tasks:
        return False, f"Задача {task_id} уже существует"

    # === Папка {task_id}/base ===
    task_folder = os.path.join(product_root, task_id)
    new_base_path = os.path.join(task_folder, "base")

    if os.path.exists(new_base_path):
        return False, f"Папка {new_base_path} уже существует"

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
        return False, f"Не удалось скопировать файлы base: {e}"

    # === Папка {task_id}/MIDBASE - ВСЕГДА СОЗДАЁТСЯ ПУСТОЙ ===
    midbase_path = os.path.join(task_folder, "MIDBASE")
    midbase_ini_name = os.path.join(task_id, "MIDBASE")

    try:
        os.makedirs(midbase_path, exist_ok=True)
    except Exception as e:
        return False, f"Не удалось создать папку MIDBASE: {e}"

    # Обновляем BasePath в RKEEPER.INI
    update_rkeeper_ini_basepath(version_path, midbase_ini_name)

    # Собираем параметры INI
    ini_settings = get_ini_settings(version_path)

    # Сохраняем в JSON
    task_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_path": new_base_path.replace("\\", "/"),
        "midbase_path": midbase_path.replace("\\", "/"),
        "ini_path": version_path.replace("\\", "/"),
        "status": "copied",
        "ini_settings": ini_settings,
        "versions": {}
    }

    tasks[task_id] = task_entry
    tasks = {task_id: tasks[task_id], **{k: v for k, v in tasks.items() if k != task_id}}
    data["tasks"] = tasks
    save_data(data)

    # Обновляем rk7srv.INI
    base_dir = os.path.join(task_id, "base")
    rk7srv_ini_path = os.path.join(version_path, "rk7srv.INI")
    update_rk7srv_ini(rk7srv_ini_path, base_dir)

    # Создаём ярлыки
    create_task_shortcuts(task_folder, version_path)

    return True, f"Задача {task_id} создана"

def relocate_task(task_id, version_folder):
    """Меняет пути задачи после ручного переноса её папки.
    version_folder — папка версии RK (INST..., либо её bin или bin/win); в ней ищется
    папка задачи {версия}/{задача}/base (rk7srv.INI ссылается на базу путём ..\\..\\{задача}\\base).
    Обновляются ini_path, base_path и midbase_path задачи и её активной версии;
    если задачу перенесли в другую версию RK — запись версии переименовывается.
    Возвращает (успех, сообщение)."""
    # Корень версии: выбранная папка, либо на уровень-два выше, если выбрали bin или bin/win.
    # INI-файлов в bin/win может ещё не быть (их добавляют позже) — достаточно самой папки bin/win.
    product_root = os.path.normpath(version_folder)
    if os.path.basename(product_root).lower() == "win":
        product_root = os.path.dirname(product_root)
    if os.path.basename(product_root).lower() == "bin":
        product_root = os.path.dirname(product_root)
    if not os.path.isdir(os.path.join(product_root, "bin", "win")):
        return False, f"Выбранная папка не является папкой версии RK (нет папки bin\\win):\n{version_folder}"
    folder = os.path.join(product_root, task_id)
    base_path = os.path.join(folder, "base")
    if not os.path.isdir(base_path):
        return False, (f"В версии {os.path.basename(product_root)} задачи {task_id} нет —\n"
                       f"не найдена папка {base_path}")

    def _fwd(p):
        return p.replace("\\", "/")

    new_ini_path = _fwd(os.path.join(product_root, "bin", "win"))
    new_base_path = _fwd(base_path)
    midbase_dir = os.path.join(folder, "MIDBASE")
    new_midbase_path = _fwd(midbase_dir) if os.path.isdir(midbase_dir) else None

    data = load_data()
    task_info = data.get("tasks", {}).get(task_id)
    if task_info is None:
        return False, f"Задача {task_id} не найдена"

    old_ini_norm = _norm_path(task_info.get("ini_path"))
    versions = task_info.get("versions", {})
    old_key = next((k for k, v in versions.items() if _norm_path(v.get("ini_path")) == old_ini_norm), None)
    new_key = extract_rk_version_from_path(new_ini_path)

    for entry in [task_info] + ([versions[old_key]] if old_key else []):
        entry["ini_path"] = new_ini_path
        entry["base_path"] = new_base_path
        if new_midbase_path:
            entry["midbase_path"] = new_midbase_path
        else:
            entry.pop("midbase_path", None)
    if old_key and new_key and new_key != old_key:
        versions[new_key] = versions.pop(old_key)

    save_data(data)
    return True, f"Пути задачи {task_id} обновлены:\n{new_base_path}"

def find_last_running_task(exe_dir: str) -> tuple[bool, str | None]:
    """Определяет задачу, с базой которой последней работал refsrv из exe_dir (bin/win).
    rk7srv.INI для этого не годится — его могли перенастроить на другую задачу
    уже после запуска refsrv. Поэтому ищем самый свежий RefEvents.dat среди
    баз версии: {корень}/{задача}/base и {корень}/base (база без задачи).
    Возвращает (найдено, task_id); task_id = None — последней была база без задачи."""
    product_root = os.path.dirname(os.path.dirname(os.path.normpath(exe_dir)))
    latest_mtime, latest_task, found = None, None, False
    try:
        candidates = [(None, os.path.join(product_root, "base"))]
        for item in os.listdir(product_root):
            if item.lower() not in ("base", "bin"):
                candidates.append((item, os.path.join(product_root, item, "base")))
        for task_id, base_dir in candidates:
            events_file = os.path.join(base_dir, "RefEvents.dat")
            if not os.path.isfile(events_file):
                continue
            mtime = os.path.getmtime(events_file)
            if latest_mtime is None or mtime > latest_mtime:
                latest_mtime, latest_task, found = mtime, task_id, True
    except OSError as e:
        print(f"Ошибка поиска RefEvents.dat: {e}")
    return found, latest_task

def _norm_path(p):
    return os.path.normpath(p).replace("\\", "/").lower() if p else ""

def _task_base_and_port(task_info, exe_dir):
    """Возвращает (base_path, port) задачи для версии из exe_dir.
    Данные конкретной версии (task_info["versions"]) приоритетнее данных задачи."""
    exe_norm = _norm_path(exe_dir)
    entry = next((v for v in task_info.get("versions", {}).values()
                  if _norm_path(v.get("ini_path")) == exe_norm), None)
    if entry is None and _norm_path(task_info.get("ini_path")) == exe_norm:
        entry = task_info
    entry = entry or {}
    base_path = entry.get("base_path") or task_info.get("base_path")
    port = (entry.get("ini_settings") or {}).get("Port") or (task_info.get("ini_settings") or {}).get("Port")
    return base_path, str(port).strip() if port else None

def find_running_task_by_ports(exe_dir: str, ports) -> tuple[bool, str | None]:
    """Определяет задачу refsrv из exe_dir по портам процесса и RefEvents.dat.
    На одной версии может быть запущено несколько refsrv, поэтому:
    1) порт отсекает задачи, у которых в JSON сохранён другой порт;
       задачи с совпавшим портом приоритетнее задач без сохранённого порта;
    2) из кандидатов выбирается задача с самым свежим RefEvents.dat в её base.
    Возвращает (найдено, task_id)."""
    listening = {str(p) for p in (ports or [])}
    tasks = load_data().get("tasks", {})
    exe_norm = _norm_path(exe_dir)

    port_matched, port_unknown = [], []
    for task_id, task_info in tasks.items():
        paths = {_norm_path(task_info.get("ini_path"))}
        paths.update(_norm_path(v.get("ini_path")) for v in task_info.get("versions", {}).values())
        if exe_norm not in paths:
            continue
        base_path, port = _task_base_and_port(task_info, exe_dir)
        if listening and port:
            if port in listening:
                port_matched.append((task_id, base_path))
            # иначе у задачи другой порт — это не она
        else:
            port_unknown.append((task_id, base_path))
    candidates = port_matched or port_unknown

    latest_mtime, latest_task = None, None
    for task_id, base_path in candidates:
        events_file = os.path.join(base_path, "RefEvents.dat") if base_path else ""
        if os.path.isfile(events_file):
            mtime = os.path.getmtime(events_file)
            if latest_mtime is None or mtime > latest_mtime:
                latest_mtime, latest_task = mtime, task_id
    if latest_task:
        return True, latest_task
    if len(candidates) == 1:
        return True, candidates[0][0]
    return False, None

def get_task_label_for_dir(exe_dir: str, ports=None) -> str | None:
    """Определяет ID задачи и версию RK для refsrv, запущенного из exe_dir.
    Задача — по портам процесса и RefEvents.dat задач из JSON (find_running_task_by_ports),
    затем по самому свежему RefEvents.dat в папках версии (find_last_running_task),
    затем по rk7srv.INI. Возвращает строку вида
    'задача 197034, версия 7.0.0.1234, порт 3640' или None, если не удалось определить."""
    if not exe_dir:
        return None
    found, task_id = find_running_task_by_ports(exe_dir, ports)
    if not found:
        found, task_id = find_last_running_task(exe_dir)
    if not found:
        task_id = extract_task_id_from_rk7srv_ini(os.path.join(exe_dir, "rk7srv.INI"))
    version = extract_rk_version_from_path(exe_dir)
    port = _main_refsrv_port(exe_dir, task_id, ports)
    if not task_id and not version and not port:
        return None
    parts = []
    if task_id:
        parts.append(f"задача {task_id}")
    if version:
        parts.append(f"версия {version}")
    if port:
        parts.append(f"порт {port}")
    return ", ".join(parts)

def _main_refsrv_port(exe_dir, task_id, ports):
    """Основной порт RK среди слушаемых refsrv портов: сохранённый у задачи в JSON,
    иначе PORT из rk7srv.INI версии. None — если ни один из них refsrv не слушает."""
    listening = {str(p) for p in (ports or [])}
    if not listening:
        return None
    if task_id:
        task_info = load_data().get("tasks", {}).get(task_id)
        if task_info:
            _, task_port = _task_base_and_port(task_info, exe_dir)
            if task_port in listening:
                return task_port
    ini_port = get_port_value_for_path(exe_dir)
    if ini_port and str(ini_port).strip() in listening:
        return str(ini_port).strip()
    return None
