# Модульная структура EngiHelp

## Статус: В РАЗРАБОТКЕ

Проект разбит на независимые модули для упрощения поддержки и развития.

## Созданные модули

### modules/data_manager.py
Управление данными JSON:
- `load_data()` - загрузка данных
- `save_data(data)` - сохранение данных
- `migrate_old_configs()` - миграция старых конфигов
- `load_settings_and_paths()` - загрузка настроек
- `find_latest_task_for_path(path)` - поиск задачи
- `find_tasks_for_path(path)` - поиск всех задач
- `get_task_data(task_id)` - данные задачи
- `save_task_entry(task_id, entry)` - сохранение задачи
- `delete_task_entry(task_id)` - удаление задачи

### modules/ini_utils.py
Работа с INI-файлами:
- `FILES` - список INI файлов
- `get_usedbsync_values(path)` - UseDBSync из всех файлов
- `detect_consensus_value(path)` - консенсус UseDBSync
- `get_usesql_value(path)` - UseSQL из rk7srv.INI
- `get_port_value(path)` - PORT из rk7srv.INI
- `get_refserver_name(path)` - REFSERVER
- `get_station_server_for_path(path)` - Station и Server
- `update_ini_file(path, value, key)` - обновление ключа
- `update_rkeeper_ini_basepath(path, name)` - BasePath
- `update_rk7srv_ini(path, base_dir)` - UDBFILE и WorkModules
- `get_ini_settings(path)` - все настройки
- `check_files(path)` - проверка файлов

### modules/process_utils.py
Управление процессами:
- `start_refsrv(path)` - запуск refsrv
- `start_rk7man(path)` - запуск rk7man
- `start_midserv(path)` - запуск midserv
- `start_wincash(path)` - запуск wincash
- `kill_refsrv(path)` - закрытие refsrv
- `kill_rk7man(path)` - закрытие rk7man
- `kill_midserv()` - закрытие midserv
- `kill_doscash()` - закрытие doscash
- `is_process_running(name)` - проверка процесса
- `get_used_ports()` - занятые порты
- `get_process_by_name(name)` - поиск процесса
- `run_refsrv_and_rk7man(path)` - комбинированный запуск

### modules/shortcuts.py
Создание ярлыков:
- `create_task_shortcuts(task_folder, bin_win_path)` - все ярлыки
- `create_folder_lnk(lnk_path, target)` - ярлык папки
- `create_lnk(lnk_path, target, args)` - ярлык файла

### modules/changelog.py
История изменений для вкладки «Что нового»:
- `CHANGELOG` - список версий (новые сверху): `version`, `date`, `items`
- При каждом повышении `SCRIPT_VERSION` добавляется запись в начало списка

## Использование

```python
# Импорт модулей
import sys
sys.path.insert(0, 'modules')

from data_manager import load_data, save_task_entry
from ini_utils import check_files, get_ini_settings
from process_utils import start_refsrv, kill_refsrv
from shortcuts import create_task_shortcuts

# Проверка файлов
found, missing = check_files("/path/to/bin/win")
print(f"Найдены: {found}")
print(f"Отсутствуют: {missing}")

# Получение настроек
settings = get_ini_settings("/path/to/bin/win")
print(settings)

# Запуск refsrv
start_refsrv("/path/to/bin/win")
```

## Планы

1. UI модули - вынести диалоги в отдельный пакет
2. Cloud RK7man - модуль для облачного сервера
3. Task Manager - модуль управления задачами
4. Тестирование - добавить pytest

## Установка зависимостей

```bash
pip install psutil requests packaging
```
