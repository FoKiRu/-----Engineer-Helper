# process_utils.py - Утилиты для управления процессами R-Keeper

import os
import subprocess
import time
import logging

import psutil

# ======================= Поиск процессов =======================

def get_process_by_name(name):
    """Возвращает список (process, exe_dir) для всех процессов с данным именем."""
    import psutil
    results = []
    try:
        result = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and name.lower() in result.stdout.lower():
            for line in result.stdout.strip().split('\n'):
                if name.lower() not in line.lower():
                    continue
                try:
                    parts = line.split(',')
                    pid_str = parts[1].strip('"')
                    pid = int(pid_str)
                    proc = psutil.Process(pid)
                    exe_dir = os.path.normpath(os.path.dirname(proc.exe())).lower()
                    results.append((proc, exe_dir))
                except (ValueError, IndexError, psutil.NoSuchProcess):
                    pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info.get('name', '').lower() != name.lower():
            continue
        try:
            exe_dir = os.path.normpath(os.path.dirname(proc.exe())).lower()
            if not any(p.pid == proc.pid for p, _ in results):
                results.append((proc, exe_dir))
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
    return results

def get_used_ports():
    """Возвращает множество портов, которые уже используются (LISTEN)."""
    import psutil
    used = set()
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr and conn.status == 'LISTEN':
                used.add(conn.laddr.port)
    except (psutil.AccessDenied, OSError):
        pass
    return used

def get_process_listening_ports(pid):
    """Возвращает список портов, которые слушает процесс с данным PID."""
    import psutil
    ports = []
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.pid == pid and conn.laddr and conn.status == 'LISTEN':
                ports.append(conn.laddr.port)
    except (psutil.AccessDenied, OSError):
        pass
    return ports

def get_port_info(ports):
    """Возвращает строку с информацией о процессах на данных портах."""
    import psutil
    if not ports:
        return ""
    info_parts = []
    for port in ports:
        proc_names = set()
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port and conn.status == 'LISTEN' and conn.pid:
                    try:
                        p = psutil.Process(conn.pid)
                        proc_names.add(f"{p.name()} (PID {conn.pid})")
                    except psutil.NoSuchProcess:
                        pass
        except (psutil.AccessDenied, OSError):
            pass
        if proc_names:
            info_parts.append(f"  {port}: {', '.join(proc_names)}")
        else:
            info_parts.append(f"  {port}: (неизвестно)")
    return "\n".join(info_parts)

def get_rk7man_port_info(pid):
    """Возвращает информацию о портах, к которым подключён процесс."""
    import psutil
    connected = []
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.pid == pid and conn.status == 'ESTABLISHED' and conn.raddr:
                port = conn.raddr.port
                proc_info = ""
                try:
                    for c in psutil.net_connections(kind='inet'):
                        if c.laddr.port == port and c.status == 'LISTEN' and c.pid:
                            p = psutil.Process(c.pid)
                            proc_info = f" ({p.name()} PID {c.pid})"
                            break
                except (psutil.AccessDenied, OSError, psutil.NoSuchProcess):
                    pass
                connected.append(f"  {port}: подключён{proc_info}")
    except (psutil.AccessDenied, OSError):
        pass
    return "\n".join(connected) if connected else "  (нет активных подключений)"

def is_process_running(process_name):
    """Проверяет, запущен ли процесс."""
    import psutil
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() == process_name.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

# ======================= Запуск процессов =======================

def start_refsrv(ini_path):
    """Запускает refsrv.exe из текущей директории."""
    import psutil
    exe_path = os.path.join(ini_path, "refsrv.exe")
    if not os.path.isfile(exe_path):
        print(f"Файл refsrv.exe не найден: {exe_path}")
        return False
    ini_path_norm = os.path.normpath(ini_path).lower()
    for proc, exe_dir in get_process_by_name('refsrv.exe'):
        if exe_dir == ini_path_norm:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    time.sleep(0.5)
    try:
        subprocess.Popen(f'start "" "{exe_path}" -desktop', shell=True)
        return True
    except Exception as e:
        print(f"Ошибка запуска refsrv.exe: {e}")
        return False

def start_rk7man(ini_path):
    """Запускает rk7man.bat из текущей директории."""
    import psutil
    ini_path_norm = os.path.normpath(ini_path).lower()
    for proc, exe_dir in get_process_by_name('rk7man.exe'):
        if exe_dir == ini_path_norm:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    time.sleep(0.5)
    bat_path = os.path.join(ini_path, "rk7man.bat")
    if not os.path.isfile(bat_path):
        print(f"Файл не найден: {bat_path}")
        return False
    try:
        subprocess.Popen(f'start "" cmd /c "{bat_path}"', shell=True, cwd=ini_path)
        return True
    except Exception as e:
        print(f"Ошибка запуска rk7man.bat: {e}")
        return False

def start_midserv(ini_path):
    """Запускает midserv.exe из текущей директории."""
    import psutil
    exe_path = os.path.join(ini_path, "midserv.exe")
    if not os.path.isfile(exe_path):
        print(f"Файл midserv.exe не найден: {exe_path}")
        return False
    ini_path_norm = os.path.normpath(ini_path).lower()
    for proc, exe_dir in get_process_by_name('midserv.exe'):
        if exe_dir == ini_path_norm:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    time.sleep(0.5)
    try:
        subprocess.Popen(f'start "" "{exe_path}" -desktop', shell=True)
        return True
    except Exception as e:
        print(f"Ошибка запуска midserv.exe: {e}")
        return False

def start_wincash(ini_path):
    """Запускает wincash.bat из текущей директории."""
    import psutil
    ini_path_norm = os.path.normpath(ini_path).lower()
    for proc, exe_dir in get_process_by_name('doscash.exe'):
        if exe_dir == ini_path_norm:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    time.sleep(0.5)
    bat_path = os.path.join(ini_path, "wincash.bat")
    if not os.path.isfile(bat_path):
        print(f"Файл не найден: {bat_path}")
        return False
    try:
        subprocess.Popen([bat_path], shell=True, cwd=ini_path)
        return True
    except Exception as e:
        print(f"Ошибка запуска wincash.bat: {e}")
        return False

# ======================= Закрытие процессов =======================

def kill_refsrv(ini_path):
    """Закрывает refsrv.exe."""
    import psutil
    ini_path_norm = os.path.normpath(ini_path).lower()
    procs = get_process_by_name('refsrv.exe')
    same_dir = [(p, d) for p, d in procs if d == ini_path_norm]
    if same_dir:
        same_dir[0][0].kill()
        return True
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == "refsrv.exe":
                proc.kill()
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def kill_rk7man(ini_path):
    """Закрывает rk7man.exe."""
    import psutil
    ini_path_norm = os.path.normpath(ini_path).lower()
    procs = get_process_by_name('rk7man.exe')
    same_dir = [(p, d) for p, d in procs if d == ini_path_norm]
    if same_dir:
        same_dir[0][0].kill()
        return True
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == "rk7man.exe":
                proc.kill()
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def kill_midserv():
    """Закрывает midserv.exe."""
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == "midserv.exe":
                proc.terminate()
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def kill_doscash():
    """Закрывает doscash.exe."""
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == "doscash.exe":
                proc.terminate()
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def kill_processes_for_version_change():
    """Завершает процессы refsrv.exe и rk7man.exe."""
    import psutil
    killed = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if name and name.lower() in ('refsrv.exe', 'rk7man.exe'):
                proc.terminate()
                killed.append(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if killed:
        time.sleep(2)
    return killed

# ======================= Комбинированные операции =======================

def run_refsrv_and_rk7man(ini_path):
    """Запускает refsrv и rk7man с проверкой портов."""
    from modules.ini_utils import get_port_value, set_port_rk7srv, set_port_rk7man, get_refserver_name
    ini_path_norm = os.path.normpath(ini_path).lower()
    current_port = get_port_value(ini_path)
    if current_port:
        used_ports = get_used_ports()
        if int(current_port) in used_ports:
            conflict = False
            for proc, exe_dir in get_process_by_name('refsrv.exe'):
                if exe_dir != ini_path_norm:
                    ports = get_process_listening_ports(proc.pid)
                    if int(current_port) in ports:
                        conflict = True
                        break
            if conflict:
                new_port = int(current_port) + 1
                while new_port in used_ports and new_port < int(current_port) + 100:
                    new_port += 1
                if new_port < int(current_port) + 100:
                    server_name = get_refserver_name(ini_path)
                    if set_port_rk7srv(ini_path, str(new_port)):
                        set_port_rk7man(ini_path, server_name, str(new_port))
                        print(f"[PORT] Смена порта: {current_port} -> {new_port}")
    start_refsrv(ini_path)
    time.sleep(1.5)
    start_rk7man(ini_path)

def run_midserv_and_wincash(ini_path, after_callback):
    """Запускает midserv и wincash с задержкой."""
    start_midserv(ini_path)
    after_callback(1500, lambda: start_wincash(ini_path))

# ======================= Запуск refsrv в режиме -desktop =======================

def launch_refsrv(exe_path: str) -> None:
    """Запускает refsrv.exe с параметром -desktop."""
    try:
        subprocess.Popen(
            f'start "" "{exe_path}" -desktop',
            shell=True
        )
        logging.info("refsrv.exe запущен: %s", exe_path)
    except Exception as e:
        logging.error("Не удалось запустить refsrv.exe: %s", e)

def wait_and_launch_refsrv(proc: psutil.Process, exe_path: str) -> None:
    """Ждёт завершения процесса и запускает его снова."""
    try:
        proc.wait(timeout=5)
    except (psutil.TimeoutExpired, psutil.AccessDenied, psutil.NoSuchProcess):
        time.sleep(2)
    except Exception as e:
        logging.error("Ошибка при ожидании процесса: %s", e)
        time.sleep(2)

    launch_refsrv(exe_path)
