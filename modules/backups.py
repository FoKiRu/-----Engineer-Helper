# ======================= backups.py =======================
# Автоматические бэкапы базы, которые делает refsrv:
# {base задачи}\backups\databases\ГГГГ.ММ.ДД.at.ЧЧ.ММ\ (rk7.udb, check.udb, rk7log.udb ...)
# Лишние старые бэкапы удаляются — остаются последние N по каждой папке base.

import os
import re
import shutil

from .data_manager import load_data, get_task_base_paths

# Имя папки бэкапа: 2026.03.31.at.15.02 — удаляются только папки с таким именем
BACKUP_DIR_RE = re.compile(r'^\d{4}\.\d{2}\.\d{2}\.at\.\d{2}\.\d{2}$')
DEFAULT_BACKUPS_KEEP = 5

def backups_dir(base_path):
    """Папка с бэкапами базы задачи."""
    return os.path.join(base_path, "backups", "databases")

def list_backups(base_path):
    """Папки бэкапов в base задачи — новые первыми (порядок по дате в имени папки,
    а не по дате изменения: при копировании версии она у всех одинаковая)."""
    folder = backups_dir(base_path)
    try:
        names = [e.name for e in os.scandir(folder)
                 if e.is_dir(follow_symlinks=False) and BACKUP_DIR_RE.match(e.name)]
    except OSError:
        return []
    return [os.path.join(folder, n) for n in sorted(names, reverse=True)]

def _folder_size(path):
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for name in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return total

def all_base_paths(task_ids=None):
    """Папки base всех задач (или только task_ids) со всеми их версиями, которые есть на диске."""
    tasks = load_data().get("tasks", {})
    result = []
    for task_id, task_info in tasks.items():
        if task_ids is not None and task_id not in task_ids:
            continue
        for path in get_task_base_paths(task_info):
            if os.path.isdir(path) and path not in result:
                result.append(path)
    return result

def find_old_backups(base_paths, keep):
    """Бэкапы сверх последних keep в каждой папке base. Возвращает [(путь, размер)]."""
    old = []
    for base_path in base_paths:
        for path in list_backups(base_path)[keep:]:
            old.append((path, _folder_size(path)))
    return old

def delete_backups(backups):
    """Удаляет папки бэкапов. Возвращает (удалено, освобождено байт, ошибки)."""
    deleted, freed, errors = 0, 0, []
    for path, size in backups:
        try:
            shutil.rmtree(path)
            deleted += 1
            freed += size
        except OSError as e:
            errors.append(f"{path}: {e}")
    return deleted, freed, errors

def format_size(size):
    for unit in ("Б", "КБ", "МБ"):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} ГБ"
