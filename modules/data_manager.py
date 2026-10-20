# data_manager.py - Управление данными JSON

import os
import json

# ======================= Константы =======================
DATA_FILE = os.path.join(os.path.expanduser("~"), "Documents", "EngiHelp_data.json")
OLD_CONFIG_FILE = os.path.join(os.path.expanduser("~"), "Documents", "EngiHelp_config.json")
OLD_TASKS_FILE = os.path.join(os.path.expanduser("~"), "Documents", "tasks.json")

# ======================= Работа с файлом данных =======================

def load_data():
    """Загружает данные из единого JSON-файла."""
    if not os.path.exists(DATA_FILE):
        return {
            "settings": {
                "auto_update": True,
                "task_from_version": False,
                "keep_cloud_files": False,
                "delete_zip_after_extract": True,
                "recent_paths": []
            },
            "tasks": {}
        }
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "settings" not in data:
                data["settings"] = {
                    "auto_update": True,
                    "task_from_version": False,
                    "keep_cloud_files": False,
                    "delete_zip_after_extract": True,
                    "recent_paths": []
                }
            if "keep_cloud_files" not in data["settings"]:
                data["settings"]["keep_cloud_files"] = False
            if "delete_zip_after_extract" not in data["settings"]:
                data["settings"]["delete_zip_after_extract"] = True
            if "tasks" not in data:
                data["tasks"] = {}
            return data
    except (json.JSONDecodeError, IOError):
        return {
            "settings": {
                "auto_update": True,
                "task_from_version": False,
                "keep_cloud_files": False,
                "delete_zip_after_extract": True,
                "recent_paths": []
            },
            "tasks": {}
        }

def save_data(data):
    """Сохраняет данные в единый JSON-файл."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Ошибка сохранения данных: {e}")

# ======================= Миграция =======================

def migrate_old_configs():
    """Переносит данные из старых файлов конфигурации."""
    if os.path.exists(DATA_FILE):
        return
    print("Миграция старых конфигурационных файлов...")
    new_data = {
        "settings": {
            "auto_update": True,
            "task_from_version": False,
            "recent_paths": []
        },
        "tasks": {}
    }
    migrated = False
    if os.path.exists(OLD_CONFIG_FILE):
        try:
            with open(OLD_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                new_data["settings"]["auto_update"] = config.get("auto_update", True)
                paths = [
                    v for k, v in sorted(config.items())
                    if k.startswith("ini_dir") and isinstance(v, str) and v.strip()
                ]
                new_data["settings"]["recent_paths"] = paths
                migrated = True
        except Exception as e:
            print(f"Не удалось мигрировать {OLD_CONFIG_FILE}: {e}")
    if os.path.exists(OLD_TASKS_FILE):
        try:
            with open(OLD_TASKS_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)
                new_data["tasks"] = tasks
                migrated = True
        except Exception as e:
            print(f"Не удалось мигрировать {OLD_TASKS_FILE}: {e}")
    if migrated:
        save_data(new_data)
        print("Миграция завершена. Создан новый файл: EngiHelp_data.json")

# ======================= Работа с путями =======================

def load_settings_and_paths():
    """Загружает настройки и историю путей."""
    data = load_data()
    settings = data.get("settings", {})
    paths = settings.get("recent_paths", [])
    auto_update = settings.get("auto_update", True)
    task_from_version = settings.get("task_from_version", True)
    keep_cloud_files = settings.get("keep_cloud_files", True)
    delete_zip_after_extract = settings.get("delete_zip_after_extract", True)
    return paths, auto_update, task_from_version, keep_cloud_files, delete_zip_after_extract

def save_settings_and_path(new_path, data=None):
    """Сохраняет путь в историю (максимум 3)."""
    new_path_norm = new_path.replace("\\", "/")
    if data is None:
        data = load_data()
    paths = data["settings"].get("recent_paths", [])
    if new_path_norm in paths:
        paths.remove(new_path_norm)
    paths.insert(0, new_path_norm)
    data["settings"]["recent_paths"] = paths[:3]
    save_data(data)
    return data

def find_latest_task_for_path(target_path):
    """Находит самый последний ID задачи для указанного пути."""
    data = load_data()
    tasks = data.get("tasks", {})
    for task_id, task_info in tasks.items():
        if task_info.get("ini_path") == target_path:
            return task_id
    return None

def find_tasks_for_path(target_path):
    """Находит ВСЕ ID задач для указанного пути."""
    if not target_path:
        return []
    def _norm(p):
        return os.path.normpath(p).replace("\\", "/").lower() if p else ""
    target_norm = _norm(target_path)
    data = load_data()
    tasks = data.get("tasks", {})
    found = []
    for task_id, task_info in tasks.items():
        paths = {_norm(task_info.get("ini_path", ""))}
        for ver_info in task_info.get("versions", {}).values():
            paths.add(_norm(ver_info.get("ini_path", "")))
        if target_norm in paths:
            found.append(task_id)
    return found

def get_current_task_base_path(task_id):
    """Возвращает путь к папке base для задачи."""
    if not task_id:
        return None
    data = load_data()
    task_info = data.get("tasks", {}).get(task_id)
    if not task_info:
        return None
    return task_info.get("base_path")

def get_task_data(task_id):
    """Получает данные задачи из JSON."""
    try:
        data = load_data()
        return data.get("tasks", {}).get(task_id)
    except Exception as e:
        print(f"Ошибка чтения конфигурации: {e}")
        return None

def load_task_ids():
    """Загружает список ID задач."""
    data = load_data()
    return [""] + list(data.get("tasks", {}).keys())

def save_task_entry(task_id, task_entry):
    """Сохраняет запись о задаче в JSON."""
    data = load_data()
    tasks = data.get("tasks", {})
    tasks[task_id] = task_entry
    # Перемещаем задачу на первую позицию
    ordered = {task_id: tasks[task_id]}
    for k, v in tasks.items():
        if k != task_id:
            ordered[k] = v
    data["tasks"] = ordered
    save_data(data)
    return ordered

def delete_task_entry(task_id):
    """Удаляет запись о задаче из JSON."""
    data = load_data()
    tasks = data.get("tasks", {})
    if task_id in tasks:
        del tasks[task_id]
        data["tasks"] = tasks
        save_data(data)

def update_task_settings(task_id, ini_settings=None, updates=None):
    """Обновляет настройки задачи."""
    data = load_data()
    tasks = data.get("tasks", {})
    if task_id in tasks:
        if ini_settings:
            tasks[task_id]["ini_settings"] = ini_settings
        if updates:
            tasks[task_id].update(updates)
        data["tasks"] = tasks
        save_data(data)

# Миграция при импорте
migrate_old_configs()
