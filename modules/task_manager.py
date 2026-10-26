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

def version_root_from_folder(folder):
    """Корень версии RK для выбранной папки: сама папка, либо на уровень-два выше,
    если выбрали bin или bin/win. None — если в корне нет bin/win.
    INI-файлов в bin/win может ещё не быть (их добавляют позже) — достаточно самой папки."""
    product_root = os.path.normpath(folder)
    if os.path.basename(product_root).lower() == "win":
        product_root = os.path.dirname(product_root)
    if os.path.basename(product_root).lower() == "bin":
        product_root = os.path.dirname(product_root)
    return product_root if os.path.isdir(os.path.join(product_root, "bin", "win")) else None

def version_root_from_ini_path(ini_path):
    """Корень версии по пути bin/win (без проверки, что он существует)."""
    return os.path.dirname(os.path.dirname(os.path.normpath(ini_path))) if ini_path else ""

def _version_key_for_root(product_root):
    """Ключ версии в task_info["versions"] по папке версии: INST7.26.04.2000 -> 7.26.04.2000."""
    name = os.path.basename(os.path.normpath(product_root))
    m = re.match(r'^INST(.+)$', name, re.IGNORECASE)
    return m.group(1) if m else name

def _is_missing(path):
    return bool(path) and not os.path.isdir(path)

def get_missing_versions(task_info):
    """Ключи версий задачи, папка base которых не найдена на диске.
    Для задачи без versions — [None], если не найдена её base."""
    versions = task_info.get("versions", {})
    if not versions:
        return [None] if _is_missing(task_info.get("base_path")) else []
    return [k for k, v in versions.items() if _is_missing(v.get("base_path"))]

def relocate_task(task_id, version_folder, version_key=None):
    """Меняет пути задачи после ручного переноса её папки.
    version_folder — папка версии RK (INST..., либо её bin или bin/win); в ней ищется
    папка задачи {версия}/{задача}/base (rk7srv.INI ссылается на базу путём ..\\..\\{задача}\\base).
    Папки старого формата base_{задача} / MIDBASE_{задача} переводятся в новый (с ярлыками),
    в папке задачи нового формата без ярлыков ярлыки создаются.
    version_key — какую версию задачи перенести (None — активную). Обновляются ini_path,
    base_path и midbase_path этой версии, а если она активная — и самой задачи;
    если задачу перенесли в другую версию RK — запись версии переименовывается.
    Возвращает (успех, сообщение, ключ версии после переноса)."""
    product_root = version_root_from_folder(version_folder)
    if not product_root:
        return False, f"Выбранная папка не является папкой версии RK (нет папки bin\\win):\n{version_folder}", None

    data = load_data()
    task_info = data.get("tasks", {}).get(task_id)
    if task_info is None:
        return False, f"Задача {task_id} не найдена", None
    versions = task_info.get("versions", {})
    if version_key is None:
        old_ini_norm = _norm_path(task_info.get("ini_path"))
        version_key = next((k for k, v in versions.items() if _norm_path(v.get("ini_path")) == old_ini_norm), None)
    elif version_key not in versions:
        return False, f"У задачи {task_id} нет версии {version_key}", None
    else:
        old_ini_norm = _norm_path(versions[version_key].get("ini_path"))
    new_key = _version_key_for_root(product_root) if version_key else None
    if version_key and new_key != version_key and new_key in versions:
        return False, f"У задачи {task_id} уже есть версия {new_key}", None

    ok, result = _prepare_task_folder(product_root, task_id)
    if not ok:
        return False, result, None
    paths, notes = result

    entries = [versions[version_key]] if version_key else []
    if not versions or _norm_path(task_info.get("ini_path")) == old_ini_norm:
        entries.append(task_info)  # переносится активная версия — меняем и пути самой задачи
    for entry in entries:
        _set_entry_paths(entry, paths)
    if version_key and new_key != version_key:
        versions[new_key] = versions.pop(version_key)

    save_data(data)
    return True, "\n\n".join([f"Пути задачи {task_id} обновлены:\n{paths['base_path']}"] + notes), new_key

def add_found_task_version(task_id, version_folder):
    """Задача найдена ещё в одной версии RK (после ручного переноса) — добавляет эту версию
    в task_info["versions"] с настройками INI задачи. Активная версия не меняется.
    Если такая версия у задачи уже есть, но её папка не найдена — обновляет её пути.
    Возвращает (успех, сообщение)."""
    product_root = version_root_from_folder(version_folder)
    if not product_root:
        return False, f"Папка не является папкой версии RK (нет папки bin\\win):\n{version_folder}"
    data = load_data()
    task_info = data.get("tasks", {}).get(task_id)
    if task_info is None:
        return False, f"Задача {task_id} не найдена"
    versions = task_info.setdefault("versions", {})
    key = _version_key_for_root(product_root)
    if key in versions and not _is_missing(versions[key].get("base_path")):
        return True, f"Версия {key} уже есть у задачи {task_id}"

    ok, result = _prepare_task_folder(product_root, task_id)
    if not ok:
        return False, result
    paths, notes = result

    if not versions and task_info.get("ini_path"):
        # У задачи была одна версия без списка versions — заносим в список и её
        current_key = _version_key_for_root(version_root_from_ini_path(task_info["ini_path"]))
        versions[current_key] = {k: task_info[k] for k in ("ini_path", "base_path", "midbase_path")
                                 if task_info.get(k)}
        versions[current_key]["ini_settings"] = task_info.get("ini_settings", {})
    entry = versions.setdefault(key, {"ini_settings": dict(task_info.get("ini_settings", {}))})
    _set_entry_paths(entry, paths)
    save_data(data)
    return True, "\n\n".join([f"Задаче {task_id} добавлена версия {key}:\n{paths['base_path']}"] + notes)

def _prepare_task_folder(product_root, task_id):
    """Проверяет папку задачи в версии: старый формат base_{задача} переводит в новый,
    в папке нового формата без ярлыков создаёт ярлыки.
    Возвращает (True, (пути для записи в JSON, заметки)) или (False, ошибка)."""
    bin_win = os.path.join(product_root, "bin", "win")
    folder = os.path.join(product_root, task_id)
    base_path = os.path.join(folder, "base")
    notes = []
    if not os.path.isdir(base_path):
        # Старый формат base_{задача} / MIDBASE_{задача} — переводим в {задача}/base и {задача}/MIDBASE
        ok, result = convert_old_task_folders(product_root, task_id)
        if not ok:
            return False, result
        if result is None:
            return False, (f"В версии {os.path.basename(product_root)} задачи {task_id} нет —\n"
                           f"не найдены папки {base_path} и "
                           f"{os.path.join(product_root, 'base_' + task_id)}")
        notes.append(result)
    elif not os.path.isfile(os.path.join(folder, "refsrv.lnk")):
        create_task_shortcuts(folder, bin_win)
        notes.append("Созданы ярлыки в папке задачи.")

    def _fwd(p):
        return p.replace("\\", "/")

    midbase_dir = os.path.join(folder, "MIDBASE")
    if not os.path.isdir(midbase_dir):
        try:
            os.makedirs(midbase_dir)
            notes.append(f"Создана пустая папка {task_id}\\MIDBASE.")
        except OSError as e:
            notes.append(f"Не удалось создать {midbase_dir}: {e}")
    paths = {
        "ini_path": _fwd(bin_win),
        "base_path": _fwd(base_path),
        "midbase_path": _fwd(midbase_dir) if os.path.isdir(midbase_dir) else None,
    }
    return True, (paths, notes)

def ensure_task_midbase(task_id):
    """У задачи или её версии нет midbase_path (папки MIDBASE не было при переносе) —
    создаёт пустую {задача}/MIDBASE рядом с base и записывает путь в JSON.
    Только для нового формата и только если папка base на месте. True — что-то изменено."""
    data = load_data()
    task_info = data.get("tasks", {}).get(task_id)
    if not task_info:
        return False
    changed = False
    for entry in [task_info] + list(task_info.get("versions", {}).values()):
        base_path = entry.get("base_path")
        if not base_path or not os.path.isdir(base_path) or os.path.basename(os.path.normpath(base_path)) != "base":
            continue
        midbase_dir = os.path.join(os.path.dirname(os.path.normpath(base_path)), "MIDBASE")
        if entry.get("midbase_path") and _norm_path(entry["midbase_path"]) == _norm_path(midbase_dir) \
                and os.path.isdir(midbase_dir):
            continue
        try:
            os.makedirs(midbase_dir, exist_ok=True)
        except OSError as e:
            print(f"[MIDBASE] Не удалось создать {midbase_dir}: {e}")
            continue
        entry["midbase_path"] = midbase_dir.replace("\\", "/")
        changed = True
    if changed:
        save_data(data)
    return changed

def _set_entry_paths(entry, paths):
    """Записывает пути из _prepare_task_folder в запись задачи или её версии."""
    entry["ini_path"] = paths["ini_path"]
    entry["base_path"] = paths["base_path"]
    if paths["midbase_path"]:
        entry["midbase_path"] = paths["midbase_path"]
    else:
        entry.pop("midbase_path", None)

def find_missing_entries_in_version(old_root):
    """Записи задач, которые указывают на версию old_root и чья папка base не найдена.
    Возвращает список (task_id, ключ версии или None — задача без versions)."""
    old_norm = _norm_path(old_root)
    result = []
    for task_id, task_info in load_data().get("tasks", {}).items():
        versions = task_info.get("versions", {})
        candidates = list(versions.items()) if versions else [(None, task_info)]
        for key, entry in candidates:
            if (_norm_path(version_root_from_ini_path(entry.get("ini_path"))) == old_norm
                    and _is_missing(entry.get("base_path"))):
                result.append((task_id, key))
    return result

def move_version_settings(old_root, new_root):
    """После переноса версии целиком: дефолтные настройки версии (defaults) и путь
    в истории путей переводятся со старого bin/win на новый."""
    old_ini = _norm_path(os.path.join(old_root, "bin", "win"))
    new_ini = os.path.join(new_root, "bin", "win").replace("\\", "/")
    data = load_data()
    changed = False
    defaults = data.get("defaults", {})
    for key in list(defaults):
        if _norm_path(key) == old_ini and new_ini not in defaults:
            entry = defaults.pop(key)
            entry["ini_path"] = new_ini
            defaults[new_ini] = entry
            changed = True
    recent = data.get("settings", {}).get("recent_paths", [])
    for i, p in enumerate(recent):
        if _norm_path(p) == old_ini:
            recent[i] = new_ini
            changed = True
    if changed:
        data["settings"]["recent_paths"] = list(dict.fromkeys(recent))
        save_data(data)
    return changed

def find_version_roots(folder, max_depth=3):
    """Папки версий RK (в которых есть bin/win) — сама folder или вложенные в неё
    на глубину до max_depth уровней. Внутрь найденной версии поиск не идёт."""
    roots = []

    def _walk(path, depth):
        if os.path.isdir(os.path.join(path, "bin", "win")):
            roots.append(path)
            return
        if depth >= max_depth:
            return
        try:
            with os.scandir(path) as entries:
                subdirs = sorted(e.path for e in entries if e.is_dir(follow_symlinks=False))
        except OSError:
            return
        for sub in subdirs:
            _walk(sub, depth + 1)

    _walk(os.path.normpath(folder), 0)
    return roots

def find_task_in_versions(folder, task_id):
    """Ищет папку задачи во всех версиях RK внутри folder (или в самой folder, если это версия).
    Возвращает (список (корень версии, старый_формат), сколько версий проверено);
    старый_формат=True — найдена base_{задача} вместо {задача}/base."""
    roots = find_version_roots(folder)
    found = []
    for product_root in roots:
        if os.path.isdir(os.path.join(product_root, task_id, "base")):
            found.append((product_root, False))
        elif os.path.isdir(os.path.join(product_root, f"base_{task_id}")):
            found.append((product_root, True))
    return found, len(roots)

def convert_old_task_folders(product_root, task_id):
    """Переводит папки задачи старого формата в новый:
    {корень}/base_{задача}   -> {корень}/{задача}/base
    {корень}/MIDBASE_{задача} -> {корень}/{задача}/MIDBASE (нет — создаётся пустая)
    и создаёт ярлыки в папке задачи.
    Возвращает (True, описание) после перевода, (True, None) — папок старого формата нет,
    (False, ошибка) — перенести не удалось (например, база занята refsrv)."""
    old_base = os.path.join(product_root, f"base_{task_id}")
    if not os.path.isdir(old_base):
        return True, None
    old_midbase = os.path.join(product_root, f"MIDBASE_{task_id}")
    folder = os.path.join(product_root, task_id)
    new_base = os.path.join(folder, "base")
    new_midbase = os.path.join(folder, "MIDBASE")
    try:
        os.makedirs(folder, exist_ok=True)
        shutil.move(old_base, new_base)
        if os.path.isdir(old_midbase) and not os.path.exists(new_midbase):
            shutil.move(old_midbase, new_midbase)
            midbase_note = f"MIDBASE_{task_id} → {task_id}\\MIDBASE"
        else:
            os.makedirs(new_midbase, exist_ok=True)
            midbase_note = f"создана пустая {task_id}\\MIDBASE"
    except Exception as e:
        return False, (f"Не удалось перевести папки задачи {task_id} в новый формат "
                       f"(возможно, база занята refsrv.exe):\n{e}")
    create_task_shortcuts(folder, os.path.join(product_root, "bin", "win"))
    return True, (f"Папки старого формата переведены в новый:\n"
                  f"base_{task_id} → {task_id}\\base, {midbase_note}, созданы ярлыки.")

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
