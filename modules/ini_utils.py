# ini_utils.py - Утилиты для работы с INI-файлами R-Keeper

import os
import re
import shutil
from collections import Counter

FILES = ["RKEEPER.INI", "wincash.ini", "rk7srv.INI", "rk7man.ini"]

def get_usedbsync_values(ini_path):
    """Читает UseDBSync из всех INI-файлов."""
    values = {}
    for filename in FILES:
        path = os.path.join(ini_path, filename)
        if not os.path.isfile(path):
            continue
        try:
            try:
                with open(path, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                with open(path, 'r', encoding='cp1251') as file:
                    lines = file.readlines()
            found = False
            for line in lines:
                match = re.match(r'^\s*UseDBSync\s*=\s*(\d+)', line, re.IGNORECASE)
                if match:
                    values[filename] = match.group(1)
                    found = True
                    break
            if not found and filename != "rk7srv.INI":
                values[filename] = "1"
        except Exception:
            continue
    return values

def detect_consensus_value(ini_path):
    """Определяет консенсус UseDBSync и синхронизирует все файлы."""
    values = get_usedbsync_values(ini_path)
    if not values:
        return "0"
    counts = Counter(values.values())
    consensus = counts.most_common(1)[0][0]
    for filename, value in values.items():
        if value != consensus:
            full_path = os.path.join(ini_path, filename)
            update_ini_file(full_path, consensus, "UseDBSync")
    return consensus

def get_usedbsync_values_for_path(path):
    """Читает UseDBSync из всех INI-файлов для указанного пути."""
    values = {}
    for filename in FILES:
        file_path = os.path.join(path, filename)
        if os.path.isfile(file_path):
            try:
                value = _read_ini_key(file_path, "UseDBSync", "DBSYNC")
                values[filename] = value if value else "0"
            except Exception:
                values[filename] = "0"
    return values

def get_usesql_value(ini_path):
    """Читает UseSQL из rk7srv.INI."""
    ini_file = os.path.join(ini_path, "rk7srv.INI")
    if not os.path.isfile(ini_file):
        return "0"
    try:
        try:
            with open(ini_file, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            with open(ini_file, 'r', encoding='cp1251') as file:
                lines = file.readlines()
        for line in lines:
            match = re.match(r'^\s*USESQL\s*=\s*(\d+)', line, re.IGNORECASE)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "0"

def get_usesql_value_for_path(ini_path_val):
    """Читает USESQL из rk7srv.INI для указанного пути."""
    return get_usesql_value(ini_path_val)

def get_port_value(ini_path):
    """Читает PORT из секции [TCPSOC] файла rk7srv.INI."""
    rk7srv_path = os.path.join(ini_path, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return ""
    try:
        try:
            with open(rk7srv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(rk7srv_path, 'r', encoding='cp1251') as f:
                lines = f.readlines()
        in_tcpsoc = False
        for line in lines:
            stripped = line.strip()
            if re.match(r'^\[TCPSOC\]', stripped, re.IGNORECASE):
                in_tcpsoc = True
                continue
            if in_tcpsoc:
                if stripped.startswith('['):
                    break
                m = re.match(r'^\s*PORT\s*=\s*(\d+)', stripped, re.IGNORECASE)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return ""

def get_port_value_for_path(ini_path_val):
    """Читает PORT из секции [TCPSOC] файла rk7srv.INI для указанного пути."""
    return get_port_value(ini_path_val)

def set_port_rk7srv(ini_path_val, port):
    """Устанавливает PORT=port в секции [TCPSOC] файла rk7srv.INI."""
    rk7srv_path = os.path.join(ini_path_val, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return False
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
        in_tcpsoc = False
        port_updated = False
        tcpsoc_found = False
        for line in lines:
            stripped = line.strip()
            if re.match(r'^\[TCPSOC\]', stripped, re.IGNORECASE):
                in_tcpsoc = True
                tcpsoc_found = True
                new_lines.append(line)
                continue
            if in_tcpsoc:
                if stripped.startswith('['):
                    if not port_updated:
                        new_lines.append(f"PORT={port}\n")
                        port_updated = True
                    in_tcpsoc = False
                elif re.match(r'^\s*PORT\s*=', stripped, re.IGNORECASE):
                    new_lines.append(f"PORT={port}\n")
                    port_updated = True
                    continue
            new_lines.append(line)
        if not tcpsoc_found:
            new_lines.append(f"\n[TCPSOC]\nPORT={port}\n")
        elif not port_updated:
            new_lines.append(f"PORT={port}\n")
        shutil.copy2(rk7srv_path, rk7srv_path + ".bak")
        with open(rk7srv_path, 'w', encoding=enc) as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"[ERR] set_port_rk7srv: {e}")
        return False

def set_port_rk7man(ini_path_val, server_name, port):
    """Устанавливает {server_name}=127.0.0.1:{port} в секции [TCPDNS] файла rk7man.ini."""
    rk7man_path = os.path.join(ini_path_val, "rk7man.ini")
    if not os.path.isfile(rk7man_path):
        return False
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
        in_tcpdns = False
        entry_updated = False
        tcpdns_found = False
        for line in lines:
            stripped = line.strip()
            if re.match(r'^\[TCPDNS\]', stripped, re.IGNORECASE):
                in_tcpdns = True
                tcpdns_found = True
                new_lines.append(line)
                continue
            if in_tcpdns:
                if stripped.startswith('['):
                    if not entry_updated:
                        new_lines.append(f"{server_name}=127.0.0.1:{port}\n")
                        entry_updated = True
                    in_tcpdns = False
                elif re.match(rf'^\s*{re.escape(server_name)}\s*=', stripped, re.IGNORECASE):
                    new_lines.append(f"{server_name}=127.0.0.1:{port}\n")
                    entry_updated = True
                    continue
            new_lines.append(line)
        if not tcpdns_found:
            new_lines.append(f"\n[TCPDNS]\n{server_name}=127.0.0.1:{port}\n")
        elif not entry_updated:
            new_lines.append(f"{server_name}=127.0.0.1:{port}\n")
        shutil.copy2(rk7man_path, rk7man_path + ".bak")
        with open(rk7man_path, 'w', encoding=enc) as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"[ERR] set_port_rk7man: {e}")
        return False

def apply_port(ini_path_val, port):
    """Применяет порт в rk7srv.INI [TCPSOC] и rk7man.ini [TCPDNS]."""
    if not port:
        return
    server_name = get_refserver_name(ini_path_val)
    ok1 = set_port_rk7srv(ini_path_val, port)
    if server_name:
        ok2 = set_port_rk7man(ini_path_val, server_name, port)
    else:
        ok2 = False
        print("[WARN] apply_port: имя сервера из [REFSERVER] не найдено, rk7man.ini не обновлён")
    print(f"[PORT] rk7srv={ok1}, rk7man={ok2}, server='{server_name}', port={port}")

def get_refserver_name(ini_path):
    """Читает имя сервера из [REFSERVER] Server = ... в rk7srv.INI."""
    rk7srv_path = os.path.join(ini_path, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return ""
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
                    return m.group(1).strip()
    except Exception:
        pass
    return ""

def get_refserver_name_for_path(ini_path_val):
    """Читает имя сервера из [REFSERVER] Server = ... в rk7srv.INI для указанного пути."""
    return get_refserver_name(ini_path_val)

def get_station_server_for_path(ini_path_val):
    """Читает Station и Server из wincash.ini."""
    wincash_path = os.path.join(ini_path_val, "wincash.ini")
    station, server = "", ""
    if os.path.isfile(wincash_path):
        try:
            with open(wincash_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(wincash_path, 'r', encoding='cp1251') as f:
                content = f.read()
        for line in content.splitlines():
            l = line.strip()
            if l.lower().startswith("station="):
                station = l.split("=", 1)[-1].strip()
            elif l.lower().startswith("server ="):
                server = l.split("=", 1)[-1].strip()
    return station, server

def _read_ini_key(filepath, key, section):
    """Читает значение ключа key из секции section файла filepath."""
    try:
        with open(filepath, 'r', encoding='cp1251') as f:
            in_section = section is None
            for line in f:
                line = line.strip()
                if section and re.match(rf'^\[{section}\]\s*$', line, re.IGNORECASE):
                    in_section = True
                    continue
                if section and re.match(r'^\[.*\]\s*$', line):
                    in_section = False
                if in_section and re.match(rf'^\s*{key}\s*=\s*(.*)$', line, re.IGNORECASE):
                    return line.split('=', 1)[1].strip()
    except Exception:
        pass
    return None

def update_ini_file(filepath, value, key):
    """Универсальное обновление ключа в INI файле."""
    try:
        if os.path.exists(filepath):
            shutil.copy2(filepath, filepath + ".bak")
        lines = []
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='cp1251') as file:
                    lines = file.readlines()
        updated = False
        new_lines = []
        key_found = False
        dbsync_section_exists = False
        for line in lines:
            if re.match(r'^\s*\[DBSYNC\]\s*$', line, re.IGNORECASE):
                dbsync_section_exists = True
                break
        for line in lines:
            if re.match(fr'^\s*{key}\s*=.*', line, re.IGNORECASE):
                new_lines.append(f"{key}={value}\n")
                key_found = True
                updated = True
            else:
                new_lines.append(line)
        if not key_found:
            if not dbsync_section_exists:
                if new_lines and not new_lines[-1].endswith('\n'):
                    new_lines.append('\n')
                new_lines.append("\n[DBSYNC]\n")
            inserted = False
            final_lines = []
            for line in new_lines:
                final_lines.append(line)
                if re.match(r'^\s*\[DBSYNC\]\s*$', line, re.IGNORECASE):
                    final_lines.append(f"{key}={value}\n")
                    inserted = True
            if inserted:
                new_lines = final_lines
            else:
                new_lines.append(f"{key}={value}\n")
            updated = True
        with open(filepath, 'w', encoding='cp1251') as file:
            file.writelines(new_lines)
        return updated
    except Exception as e:
        print(f"[ERROR] {filepath}: {e}")
        return False

def update_rkeeper_ini_basepath(ini_path, midbase_folder_name):
    """Обновляет параметр BasePath в секции [Config] файла RKEEPER.INI."""
    rkeeper_path = os.path.join(ini_path, "RKEEPER.INI")
    if not os.path.isfile(rkeeper_path):
        print(f"[WARN] RKEEPER.INI не найден: {rkeeper_path}")
        return False
    try:
        try:
            with open(rkeeper_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(rkeeper_path, 'r', encoding='cp1251') as f:
                lines = f.readlines()
        new_lines = []
        updated = False
        for line in lines:
            if re.match(r'^\s*BasePath\s*=', line, re.IGNORECASE):
                new_lines.append(f"BasePath = ..\\..\\{midbase_folder_name}\n")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            final_lines = []
            in_config = False
            inserted = False
            for line in new_lines:
                final_lines.append(line)
                if re.match(r'^\s*\[Config\]\s*$', line, re.IGNORECASE):
                    in_config = True
                elif in_config and re.match(r'^\s*\[', line) and not inserted:
                    final_lines.insert(-1, f"BasePath = ..\\..\\{midbase_folder_name}\n")
                    inserted = True
                    in_config = False
            if not inserted:
                final_lines.append(f"BasePath = ..\\..\\{midbase_folder_name}\n")
            new_lines = final_lines
        with open(rkeeper_path, 'w', encoding='cp1251') as f:
            f.writelines(new_lines)
        print(f"[OK] RKEEPER.INI обновлён: BasePath = ..\\..\\{midbase_folder_name}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка обновления RKEEPER.INI: {e}")
        return False

def update_rk7srv_ini(ini_path, base_dir):
    """Обновляет UDBFILE и WorkModules в rk7srv.INI."""
    try:
        with open(ini_path, 'r', encoding='cp1251') as file:
            lines = file.readlines()
        new_lines = []
        for line in lines:
            if re.match(r'^\s*UDBFILE\s*=', line, re.IGNORECASE):
                new_lines.append(f"UDBFILE            = ..\\..\\{base_dir}\\rk7.udb\n")
            elif re.match(r'^\s*WorkModules\s*=', line, re.IGNORECASE):
                new_lines.append(f"WorkModules        = ..\\..\\{base_dir}\\workmods\n")
            else:
                new_lines.append(line)
        with open(ini_path, 'w', encoding='cp1251') as file:
            file.writelines(new_lines)
        print("rk7srv.INI обновлён!")
        return True
    except Exception as e:
        print(f"Ошибка при обновлении rk7srv.INI: {e}")
        return False

def get_rk7srv_udb_workmodules(ini_path_val):
    """Читает UDBFILE и WorkModules из rk7srv.INI."""
    rk7srv_path = os.path.join(ini_path_val, "rk7srv.INI")
    if not os.path.isfile(rk7srv_path):
        return None
    try:
        with open(rk7srv_path, 'r', encoding='cp1251') as f:
            content = f.read()
        result = {}
        for line in content.splitlines():
            m = re.match(r'^\s*(UDBFILE|WorkModules)\s*=\s*(.*)$', line, re.IGNORECASE)
            if m:
                result[m.group(1)] = m.group(2).strip()
        return result if result else None
    except Exception as e:
        print(f"Ошибка чтения rk7srv.INI: {e}")
        return None

def get_ini_settings(ini_path):
    """Сбор параметров UseDBSync, UseSQL, Station, Server, Port, UDBFILE, WorkModules, REFSERVER."""
    station, server = get_station_server_for_path(ini_path)
    refserver = get_refserver_name(ini_path)
    settings = {
        "UseDBSync": get_usedbsync_values_for_path(ini_path),
        "UseSQL": get_usesql_value_for_path(ini_path),
        "Station": station,
        "Server": server,
        "Port": get_port_value_for_path(ini_path),
        "REFSERVER": refserver,
    }
    rk7srv = get_rk7srv_udb_workmodules(ini_path)
    if rk7srv:
        settings["UDBFILE"] = rk7srv.get("UDBFILE")
        settings["WorkModules"] = rk7srv.get("WorkModules")
    return settings

def check_files(ini_path):
    """Проверяет наличие INI-файлов в указанном пути."""
    found, missing = [], []
    for filename in FILES:
        full_path = os.path.join(ini_path, filename)
        if os.path.isfile(full_path):
            found.append(filename)
        else:
            missing.append(filename)
    return found, missing
