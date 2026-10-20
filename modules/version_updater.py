# version_updater.py - Проверка и скачивание новых версий RK из облака

import os
import re
import shutil
import tempfile
import zipfile
import urllib.request
import urllib.error
from typing import Optional, Tuple, List, Dict

# ======================= Константы =======================

CLOUD_BASE_URL = "https://files-rkcloud.ucs.ru/d/65231391cff842d49a1a/?p="
CLOUD_LIST_SUFFIX = "&mode=list"
CLOUD_DOWNLOAD_URL = "https://files-rkcloud.ucs.ru/d/65231391cff842d49a1a/files/?p="

# ======================= Парсинг версий =======================

def parse_version_string(version: str) -> Tuple[int, ...]:
    """Парсит строку версии в кортеж чисел для сравнения.
    Пример: '7.26.08.2005' -> (7, 26, 8, 2005)
    """
    parts = version.split('.')
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return (0, 0, 0, 0)

def format_version_for_display(major: str, minor: str, patch: str, build: str) -> str:
    """Форматирует версию для отображения.
    Пример: ('7', '26', '08', '2005') -> '7.26.08.2005'
    """
    return f"{major}.{minor}.{patch}.{build}"

def extract_version_from_zip_name(zip_name: str) -> Optional[str]:
    """Извлекает версию из имени ZIP файла.
    Пример: 'INST7.26.08.2005.ZIP' -> '7.26.08.2005'
    """
    match = re.match(r'^INST(.+)\.ZIP$', zip_name, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def extract_base_version(full_version: str) -> str:
    """Извлекает базовую версию без билда.
    Пример: '7.26.08.2005' -> '7.26.08'
    """
    parts = full_version.split('.')
    if len(parts) >= 3:
        return '.'.join(parts[:3])
    return full_version

def find_latest_local_version(versions: List[str]) -> Optional[str]:
    """Находит самую свежую локальную версию из списка.
    Версия формата: 7.26.05.2008
    """
    if not versions:
        return None
    parsed = [(v, parse_version_string(v)) for v in versions]
    parsed.sort(key=lambda x: x[1], reverse=True)
    return parsed[0][0]

def compare_versions(local: str, remote: str) -> int:
    """Сравнивает две версии.
    Returns: -1 если local < remote, 0 если равны, 1 если local > remote
    """
    local_parsed = parse_version_string(local)
    remote_parsed = parse_version_string(remote)
    if local_parsed < remote_parsed:
        return -1
    elif local_parsed > remote_parsed:
        return 1
    return 0

# ======================= HTTP запросы =======================

def fetch_cloud_list(path: str) -> Optional[str]:
    """Загружает HTML страницу со списком файлов."""
    url = CLOUD_BASE_URL + path + CLOUD_LIST_SUFFIX
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode('utf-8', errors='ignore')
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[ERROR] Не удалось загрузить {url}: {e}")
        return None

def parse_folder_list(html: str) -> List[Dict[str, str]]:
    """Парсит HTML список папок/файлов.
    Возвращает список dict с 'name', 'type' ('folder'/'file'), 'path'.
    """
    results = []

    # Ищем папки: <a href="?p=/rk7/versions/7.25.00&mode=list" class="normal">7.25.00</a>
    folder_pattern = re.compile(
        r'href="\?p=(/rk7/versions/[^&"]+)&mode=list"[^>]*>([^<]+)</a>',
        re.IGNORECASE
    )
    for match in folder_pattern.finditer(html):
        path = match.group(1)
        name = match.group(2).strip()
        results.append({
            'name': name,
            'type': 'folder',
            'path': path
        })

    # Ищем ZIP файлы в ссылках или просто в тексте
    # Примеры форматов:
    # <a href="?p=/rk7/versions/7.26.00/7.26.08/7.26.08.05/INST7.26.08.2005.ZIP&dl=1">INST7.26.08.2005.ZIP</a>
    # <a href="...INST7.26.08.2005.ZIP...">...</a>
    zip_pattern = re.compile(r'INST(\d+\.\d+\.\d+\.\d+)\.ZIP', re.IGNORECASE)

    # Ищем ссылки на скачивание с dl=1
    zip_link_pattern = re.compile(
        r'href="[^"]*(\?p=[^"&]*INST[^"&]+\.ZIP)&dl=1"[^>]*>([^<]*INST[^<]*\.ZIP)</a>',
        re.IGNORECASE
    )
    for match in zip_link_pattern.finditer(html):
        path = match.group(1)
        name = match.group(2)
        m = zip_pattern.search(name)
        if m:
            results.append({
                'name': name.strip(),
                'type': 'file',
                'version': m.group(1),
                'path': path
            })

    # Ищем просто упоминания INST*.ZIP в тексте
    for match in zip_pattern.finditer(html):
        version = match.group(1)
        name = f'INST{version}.ZIP'
        # Проверяем, не добавили ли уже
        if not any(r.get('version') == version for r in results):
            results.append({
                'name': name,
                'type': 'file',
                'version': version,
                'path': None  # Путь будет построен позже
            })

    return results

# ======================= Навигация по версиям =======================

def find_latest_cloud_version(current_base_version: str) -> Optional[Dict[str, str]]:
    """Находит самую свежую доступную версию в облаке.

    Структура папок в облаке:
    /rk7/versions/7.26.00/7.26.08/7.26.08.05/INST7.26.08.2005.ZIP

    Алгоритм:
    1. Парсим текущую версию (7.26.08.2002) -> база 7.26.08
    2. Ищем в облаке папку мажорной версии (7.26.00)
    3. Ищем внутри папку минорной версии (7.26.08)
    4. Находим самый свежий билд (7.26.08.05)
    5. Проваливаемся в папку билда и ищем ZIP

    Returns: {'version': '7.26.08.2005', 'zip_name': 'INST7.26.08.2005.ZIP', 'download_path': '/rk7/...'}
    """
    current_parts = current_base_version.split('.')
    if len(current_parts) < 3:
        print(f"[ERROR] Неверный формат версии: {current_base_version}")
        return None

    major, minor = current_parts[0], current_parts[1]  # 7, 26

    # 1. Получаем список мажорных папок (7.26.00, 7.25.00, etc)
    html = fetch_cloud_list("/rk7/versions")
    if not html:
        return None

    folders = parse_folder_list(html)
    major_folders = [f for f in folders if f['type'] == 'folder']

    # 2. Ищем папку с нужным мажорным номером
    target_major_pattern = f"{major}.{minor}."
    target_major_folder = None
    for f in major_folders:
        if f['name'].startswith(target_major_pattern):
            target_major_folder = f
            break

    if not target_major_folder:
        print(f"[INFO] Папка {target_major_pattern}* не найдена в облаке")
        return None

    print(f"[INFO] Найдена мажорная папка: {target_major_folder['name']}")

    # 3. Проваливаемся в мажорную папку и ищем минорные
    html = fetch_cloud_list(target_major_folder['path'])
    if not html:
        return None

    minor_folders = parse_folder_list(html)
    minor_folders = [f for f in minor_folders if f['type'] == 'folder']

    # 4. Ищем нужную минорную версию (7.26.08)
    target_minor_pattern = current_base_version  # 7.26.08
    target_minor_folder = None
    for f in minor_folders:
        if f['name'].startswith(target_minor_pattern + '.') or f['name'] == target_minor_pattern:
            target_minor_folder = f
            break

    if not target_minor_folder:
        print(f"[INFO] Минорная папка {target_minor_pattern}.x не найдена")
        return None

    print(f"[INFO] Найдена минорная папка: {target_minor_folder['name']}")

    # 5. Проваливаемся в минорную папку и ищем билды
    html = fetch_cloud_list(target_minor_folder['path'])
    if not html:
        return None

    build_folders = parse_folder_list(html)
    build_folders = [f for f in build_folders if f['type'] == 'folder']

    if not build_folders:
        # Проверяем, нет ли ZIP файлов в текущей папке
        zip_files = [f for f in parse_folder_list(html) if f['type'] == 'file']
        if zip_files:
            zip_files.sort(key=lambda x: parse_version_string(x.get('version', '0')), reverse=True)
            latest = zip_files[0]
            return {
                'version': latest['version'],
                'zip_name': latest['name'],
                'download_path': f"{target_minor_folder['path']}/{latest['name']}"
            }
        print(f"[INFO] Билды не найдены в {target_minor_folder['name']}")
        return None

    # 6. Находим самый свежий билд (сортируем по версии)
    build_folders.sort(key=lambda x: parse_version_string(x.get('name', '0')), reverse=True)
    latest_build_folder = build_folders[0]
    print(f"[INFO] Найден свежий билд: {latest_build_folder['name']}")

    # 7. Проваливаемся в папку билда и ищем ZIP
    html = fetch_cloud_list(latest_build_folder['path'])
    if not html:
        return None

    zip_files = [f for f in parse_folder_list(html) if f['type'] == 'file']
    if not zip_files:
        print(f"[INFO] ZIP не найден в папке билда {latest_build_folder['name']}")
        return None

    # Берем первый (самый свежий) ZIP
    latest_zip = zip_files[0]
    version = latest_zip.get('version', '')
    if not version:
        m = re.match(r'INST(.+)\.ZIP', latest_zip['name'], re.IGNORECASE)
        if m:
            version = m.group(1)

    # Используем путь из ZIP или строим его
    zip_path = latest_zip.get('path') or f"{latest_build_folder['path']}/{latest_zip['name']}"

    return {
        'version': version,
        'zip_name': latest_zip['name'],
        'download_path': zip_path
    }

# ======================= Скачивание =======================

def download_version(
    cloud_path: str,
    zip_name: str,
    target_dir: str,
    progress_callback=None
) -> Tuple[bool, str]:
    """Скачивает ZIP архив с версией RK.

    Args:
        cloud_path: Путь к файлу на облаке (включая имя файла)
        zip_name: Имя ZIP файла
        target_dir: Директория для сохранения
        progress_callback: Функция обратного вызова (filename, downloaded, total)

    Returns:
        (success, message)
    """
    # download_path уже содержит полный путь включая имя файла
    download_url = CLOUD_DOWNLOAD_URL + cloud_path + "&dl=1"
    output_path = os.path.join(target_dir, zip_name)

    try:
        def reporthook(block_num, block_size, total_size):
            if progress_callback and total_size > 0:
                downloaded = block_num * block_size
                progress_callback(zip_name, downloaded, total_size)

        print(f"[DOWNLOAD] {download_url}")
        print(f"[DOWNLOAD] -> {output_path}")

        req = urllib.request.Request(
            download_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )

        urllib.request.urlretrieve(download_url, output_path, reporthook)

        # Проверяем что скачалось
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"[DOWNLOAD] Успешно: {zip_name} ({size} bytes)")
            return True, output_path
        else:
            return False, "Файл не был создан"

    except Exception as e:
        print(f"[ERROR] Ошибка скачивания: {e}")
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        return False, str(e)

def extract_zip(zip_path: str, target_dir: str, delete_after: bool = True) -> Tuple[bool, str]:
    """Распаковывает ZIP архив.

    Args:
        zip_path: Путь к ZIP файлу
        target_dir: Директория для распаковки
        delete_after: Удалить ZIP после распаковки

    Returns:
        (success, extracted_folder_name или error_message)
    """
    try:
        # Имя выходной папки из имени ZIP файла (без .ZIP)
        zip_basename = os.path.splitext(os.path.basename(zip_path))[0]  # INST7.26.08.2005
        target_folder = os.path.join(target_dir, zip_basename)

        # Всегда создаём целевую папку
        os.makedirs(target_folder, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Просто распаковываем всё содержимое в целевую папку
            zip_ref.extractall(target_folder)

        # Удаляем ZIP если нужно
        if delete_after:
            try:
                os.remove(zip_path)
            except:
                pass

        return True, zip_basename

    except zipfile.BadZipFile:
        return False, "Неверный ZIP файл"
    except Exception as e:
        return False, str(e)


# ======================= Главная функция проверки =======================

def check_rk_updates(
    local_versions: List[str],
    current_version: str
) -> Optional[Dict[str, any]]:
    """Проверяет наличие обновлений в облаке.

    Args:
        local_versions: Список локальных версий (например ['7.26.05.2008', '7.26.08.2001', '7.26.08.2002'])
        current_version: Текущая выбранная версия (например '7.26.08.2002')

    Returns:
        Dict с информацией об обновлении или None если обновлений нет:
        {
            'current_version': '7.26.08.2002',
            'latest_version': '7.26.08.2005',
            'zip_name': 'INST7.26.08.2005.ZIP',
            'download_path': '/rk7/versions/7.26.00/7.26.08/7.26.08.05/INST7.26.08.2005.ZIP'
        }
    """
    # Определяем самую свежую локальную версию
    latest_local = find_latest_local_version(local_versions)
    if not latest_local:
        print("[INFO] Локальные версии не найдены")
        return None

    base_version = extract_base_version(latest_local)
    print(f"[INFO] Локальная базовая версия: {base_version} (самая свежая: {latest_local})")

    # Ищем в облаке
    cloud_info = find_latest_cloud_version(base_version)
    if not cloud_info:
        print("[INFO] Обновления не найдены в облаке")
        return None

    latest_cloud = cloud_info['version']
    print(f"[INFO] Облачная версия: {latest_cloud}")

    # Сравниваем
    cmp = compare_versions(latest_local, latest_cloud)
    if cmp >= 0:
        print(f"[INFO] Локальная ({latest_local}) >= Облачная ({latest_cloud})")
        return None

    print(f"[UPDATE] Доступна новая версия: {latest_cloud} (локальная: {latest_local})")

    return {
        'current_version': latest_local,
        'latest_version': latest_cloud,
        'zip_name': cloud_info['zip_name'],
        'download_path': cloud_info['download_path']
    }
