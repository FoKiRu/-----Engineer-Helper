# ======================= task_manager.py =======================
# Управление задачами

import os
import re
import shutil
from datetime import datetime
from functools import partial

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
