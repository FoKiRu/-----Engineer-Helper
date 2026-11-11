import base64
import ctypes
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from .data_manager import load_data, save_data
from .dialogs import _center_window, centered_askyesno, centered_error, centered_info, centered_warning
from .process_utils import get_process_by_name
from .shortcuts import create_lnk, minimize_lnk
from .sql_database import SqlDatabaseError, create_database, database_exists


class FeatureServerError(Exception):
    pass


_INSTALL_SCRIPT = r"""
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$ErrorActionPreference = 'Stop'

function Format-SqlValue([string]$Value) {
    if ($Value -match '[;"'']' -or $Value -ne $Value.Trim()) {
        return '"' + ($Value -replace '"', '""') + '"'
    }
    return $Value
}

try {
    Import-Module -Name $env:ENGIHELP_FS_MODULE -Force -ErrorAction Stop
    $params = @{
        ver = $env:ENGIHELP_FS_VERSION
        installpath = $env:ENGIHELP_FS_INSTALL_PATH
        server = $env:ENGIHELP_FS_SERVER
    }
    if ($env:ENGIHELP_FS_CACHE_PATH) {
        $params.usecache = $env:ENGIHELP_FS_CACHE_PATH
    }
    if ($env:ENGIHELP_FS_INSTALL_PLUGINS -eq '1') {
        $params.rk7manpath = $env:ENGIHELP_FS_RK7MAN_PATH
    }
    if ($env:ENGIHELP_FS_CS_URL) {
        $params.cs = $env:ENGIHELP_FS_CS_URL
    }
    if ($env:ENGIHELP_FS_FS_URL) {
        $params.fs = $env:ENGIHELP_FS_FS_URL
    }
    if ($env:ENGIHELP_FS_SQL_ENABLED -eq '1') {
        if ($env:ENGIHELP_FS_SQL_WINDOWS_AUTH -eq '1') {
            $sql = 'Provider=SQLOLEDB.1;Persist Security Info=True;Integrated Security=SSPI'
        }
        else {
            $sql = 'Provider=SQLOLEDB.1'
            $sql += ';Password=' + (Format-SqlValue $env:ENGIHELP_FS_SQL_PASSWORD)
            $sql += ';Persist Security Info=True'
            $sql += ';User ID=' + (Format-SqlValue $env:ENGIHELP_FS_SQL_USER)
        }
        $sql += ';Initial Catalog=' + (Format-SqlValue $env:ENGIHELP_FS_SQL_DATABASE)
        $sql += ';Data Source=' + (Format-SqlValue $env:ENGIHELP_FS_SQL_SERVER)
        $params.sql = $sql
    }

    Get-IR @params
    if (-not $?) {
        throw 'Get-IR завершился с ошибкой.'
    }
}
catch {
    Write-Output $_.Exception.Message
    exit 1
}
"""


def _get_ir_module_path():
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, "deploy-stands", "get-ir", "get-ir.psm1")


def install_feature_server(options, log_callback=None):
    module_path = _get_ir_module_path()
    if not os.path.isfile(module_path):
        raise FeatureServerError(f"Модуль Get-IR не найден:\n{module_path}")

    env = os.environ.copy()
    env.update({
        "ENGIHELP_FS_MODULE": module_path,
        "ENGIHELP_FS_VERSION": options["version"],
        "ENGIHELP_FS_INSTALL_PATH": options["install_path"],
        "ENGIHELP_FS_CACHE_PATH": options.get("cache_path", ""),
        "ENGIHELP_FS_SERVER": options.get("server", "web"),
        "ENGIHELP_FS_INSTALL_PLUGINS": "1",
        "ENGIHELP_FS_RK7MAN_PATH": options["rk7man_path"],
        "ENGIHELP_FS_CS_URL": options.get("cs_url", ""),
        "ENGIHELP_FS_FS_URL": options.get("fs_url", ""),
        "ENGIHELP_FS_SQL_ENABLED": "1" if options.get("sql_enabled") else "0",
        "ENGIHELP_FS_SQL_SERVER": options.get("sql_server", ""),
        "ENGIHELP_FS_SQL_DATABASE": options.get("sql_database", ""),
        "ENGIHELP_FS_SQL_WINDOWS_AUTH": "1" if options.get("sql_windows_auth") else "0",
        "ENGIHELP_FS_SQL_USER": options.get("sql_username", ""),
        "ENGIHELP_FS_SQL_PASSWORD": options.get("sql_password", ""),
    })

    process = None
    try:
        process = subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-Command", _INSTALL_SCRIPT,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as e:
        raise FeatureServerError("Не найден PowerShell, необходимый для установки Feature Server.") from e
    except OSError as e:
        raise FeatureServerError(f"Не удалось запустить PowerShell:\n{e}") from e
    finally:
        env["ENGIHELP_FS_SQL_PASSWORD"] = ""

    output = []
    for line in process.stdout:
        line = line.rstrip()
        output.append(line)
        if log_callback:
            log_callback(line)
    return_code = process.wait()
    process.stdout.close()
    if return_code != 0:
        details = "\n".join(output[-8:]).strip()
        raise FeatureServerError(details or "PowerShell завершил установку с ошибкой.")

    install_path = options["install_path"]
    required_files = [
        os.path.join(install_path, "IRReportsFSPrj.exe"),
        os.path.join(install_path, "IRReportsFSPrj.ini"),
        os.path.join(
            options["rk7man_path"], "plugins", "SchRepPluginClient", "SchRepPluginClient.ini"
        ),
    ]
    missing = [path for path in required_files if not os.path.isfile(path)]
    if missing:
        raise FeatureServerError("Установка завершилась не полностью. Не найдены файлы:\n" + "\n".join(missing))

    shortcut_path = os.path.join(install_path, "IRReportsFSPrj.lnk")
    if not os.path.isfile(shortcut_path) and log_callback:
        log_callback(f"Предупреждение: ярлык не создан: {shortcut_path}")
    return install_path


def _same_path(left, right):
    return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))


def _start_as_admin(path, arguments=None, show_command=6):
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", path, arguments, os.path.dirname(path), show_command
    )
    if result <= 32:
        raise FeatureServerError(f"Не удалось запустить от администратора:\n{path}\nКод ошибки: {result}")


def _fs_launch_script(fs_shortcut):
    shortcut_path = fs_shortcut.replace("'", "''")
    return f"""
$ErrorActionPreference = 'Stop'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut('{shortcut_path}')
$targetPath = $shortcut.TargetPath
$workingDirectory = $shortcut.WorkingDirectory
if (-not $workingDirectory) {{ $workingDirectory = Split-Path $targetPath }}
Start-Process -FilePath $targetPath -ArgumentList $shortcut.Arguments -WorkingDirectory $workingDirectory -WindowStyle Minimized
Add-Type -Namespace EngiHelp -Name Window -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);'
for ($attempt = 0; $attempt -lt 40; $attempt++) {{
    Start-Sleep -Milliseconds 250
    $minimized = $false
    foreach ($process in @(Get-Process -Name 'IRReportsFSPrj' -ErrorAction SilentlyContinue)) {{
        try {{
            if ($process.Path -ne $targetPath) {{ continue }}
            $handle = $process.MainWindowHandle
            if ($handle -ne 0) {{
                [EngiHelp.Window]::ShowWindow($handle, 6)
                $minimized = $true
            }}
        }} catch {{}}
    }}
    if ($minimized) {{ break }}
}}
"""


def _start_fs_as_admin(fs_shortcut):
    encoded_script = base64.b64encode(_fs_launch_script(fs_shortcut).encode("utf-16le")).decode("ascii")
    powershell_path = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
    )
    _start_as_admin(
        powershell_path,
        f"-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand {encoded_script}",
        0,
    )


def _find_cs_service(saved_path=""):
    if saved_path and os.path.isfile(saved_path):
        return os.path.normpath(saved_path)
    default_dir = r"C:\Program Files (x86)\UCS\CommonServer\default"
    for filename in ("CS_Service.exe.lnk", "CS_Service.lnk", "CS_Service.exe"):
        path = os.path.join(default_dir, filename)
        if os.path.isfile(path):
            return path
    return ""


def _resolve_cs_service(saved_path, parent, initial_dir):
    cs_path = _find_cs_service(saved_path)
    if cs_path:
        return cs_path
    default_dir = r"C:\Program Files (x86)\UCS\CommonServer\default"
    selected = filedialog.askopenfilename(
        parent=parent,
        title="Выберите CS_Service.exe или его ярлык",
        initialdir=default_dir if os.path.isdir(default_dir) else initial_dir,
        filetypes=[("Common Server", "CS_Service.exe CS_Service*.lnk"), ("Все файлы", "*.*")],
    )
    return os.path.normpath(selected) if selected else ""


def _create_cs_shortcut(task_folder, cs_path):
    shortcut_path = os.path.join(task_folder, "CS.lnk")
    if os.path.isfile(shortcut_path):
        return shortcut_path
    if cs_path.lower().endswith(".lnk"):
        shutil.copy2(cs_path, shortcut_path)
    else:
        create_lnk(shortcut_path, cs_path, "")
    if not os.path.isfile(shortcut_path):
        raise FeatureServerError(f"Не удалось создать ярлык Common Server:\n{shortcut_path}")
    return shortcut_path


def launch_feature_services(task_id, task_info, parent):
    task_folder = os.path.dirname(os.path.normpath(task_info.get("base_path", "")))
    fs_shortcut = os.path.join(task_folder, "FS.lnk")
    cs_shortcut = os.path.join(task_folder, "CS.lnk")
    if not os.path.isfile(fs_shortcut):
        centered_error("Запуск FS и CS", f"Ярлык Feature Server не найден:\n{fs_shortcut}")
        return False

    cs_path = task_info.get("cs_service_path", "")
    try:
        if not os.path.isfile(cs_shortcut):
            cs_path = _resolve_cs_service(cs_path, parent, task_folder)
            if not cs_path:
                return False
            _create_cs_shortcut(task_folder, cs_path)
        if not minimize_lnk(fs_shortcut):
            raise FeatureServerError(f"Не удалось настроить свёрнутый запуск FS:\n{fs_shortcut}")
        _start_fs_as_admin(fs_shortcut)
        _start_as_admin(cs_shortcut)
    except (FeatureServerError, OSError) as e:
        centered_error("Запуск FS и CS", str(e))
        return False

    data = load_data()
    current_task = data.get("tasks", {}).get(task_id)
    if current_task is not None and cs_path:
        current_task["cs_service_path"] = cs_path
        save_data(data)
    return True


def prepare_schrep_plugin(ini_path, launch_with_services):
    plugin_dir = os.path.join(ini_path, "plugins", "SchRepPluginClient")
    active_path = os.path.join(plugin_dir, "SchRepPluginClient.ini")
    disabled_path = os.path.join(plugin_dir, "#SchRepPluginClient.ini")

    if launch_with_services:
        if not os.path.exists(active_path) and os.path.isfile(disabled_path):
            os.rename(disabled_path, active_path)
        return None

    if os.path.isfile(active_path):
        if os.path.exists(disabled_path):
            raise FeatureServerError(
                "Найдены одновременно SchRepPluginClient.ini и #SchRepPluginClient.ini.\n"
                "Оставьте только один файл перед запуском RK7man."
            )
        os.rename(active_path, disabled_path)
        return disabled_path, active_path
    return None


def restore_schrep_plugin(disabled_path, active_path):
    if os.path.isfile(disabled_path) and not os.path.exists(active_path):
        os.rename(disabled_path, active_path)


def _schrep_ini_path(ini_path):
    plugin_dir = os.path.join(ini_path, "plugins", "SchRepPluginClient")
    for filename in ("SchRepPluginClient.ini", "#SchRepPluginClient.ini"):
        path = os.path.join(plugin_dir, filename)
        if os.path.isfile(path):
            return path
    return ""


def read_schrep_guid(ini_path):
    path = _schrep_ini_path(ini_path)
    if not path:
        return ""
    with open(path, "rb") as ini_file:
        content = ini_file.read()
    section = re.search(
        rb"(?ims)^[ \t]*\[CS_CONNECTION\][^\r\n]*\r?\n(.*?)(?=^[ \t]*\[|\Z)",
        content,
    )
    if not section:
        return ""
    guid = re.search(
        rb"(?im)^[ \t]*fs_guid[ \t]*=[ \t]*(\{[^}\r\n]+\})",
        section.group(1),
    )
    return guid.group(1).decode("ascii") if guid else ""


def set_schrep_guid(ini_path, guid):
    path = _schrep_ini_path(ini_path)
    if not path:
        raise FeatureServerError("Файл SchRepPluginClient.ini не найден.")
    with open(path, "rb") as ini_file:
        content = ini_file.read()
    section = re.search(
        rb"(?ims)^[ \t]*\[CS_CONNECTION\][^\r\n]*\r?\n(.*?)(?=^[ \t]*\[|\Z)",
        content,
    )
    if not section:
        raise FeatureServerError("В SchRepPluginClient.ini не найдена секция [CS_CONNECTION].")
    replacement = guid.encode("ascii")
    new_section, count = re.subn(
        rb"(?im)^([ \t]*fs_guid[ \t]*=[ \t]*)\{[^}\r\n]*\}",
        lambda match: match.group(1) + replacement,
        section.group(1),
        count=1,
    )
    if count != 1:
        raise FeatureServerError("В секции [CS_CONNECTION] не найден параметр fs_guid.")
    content = content[:section.start(1)] + new_section + content[section.end(1):]
    with open(path, "wb") as ini_file:
        ini_file.write(content)


def feature_server_dialog(root, task_id, ini_path, base_path, icon_path=None):
    if not task_id:
        centered_warning("Установка Feature Server", "Сначала выберите задачу.")
        return
    if not ini_path or not os.path.isdir(ini_path):
        centered_warning("Установка Feature Server", "Папка bin\\win текущей версии RK не найдена.")
        return

    data = load_data()
    saved = data["settings"].get("feature_server", {})
    sql_saved = data["settings"].get("sql_database", {})
    task_folder = os.path.dirname(os.path.normpath(base_path)) if base_path else ""

    win = tk.Toplevel(root)
    win.withdraw()
    win.title("Установка Feature Server")
    if icon_path:
        win.iconbitmap(icon_path)
    win.transient(root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text=f"Задача: {task_id}", font=("TkDefaultFont", 9, "bold")).pack(
        anchor="w", padx=12, pady=(12, 6)
    )

    distribution = tk.LabelFrame(frame, text="Дистрибутив и установка")
    distribution.pack(fill="x", padx=12, pady=(0, 8))
    distribution.grid_columnconfigure(1, weight=1)

    version_var = tk.StringVar(value=saved.get("version", "latest"))
    install_path_var = tk.StringVar(value=os.path.join(task_folder, "featureserver") if task_folder else "")
    cache_path_var = tk.StringVar(value=saved.get("cache_path", ""))
    server_var = tk.StringVar(value=saved.get("server", "web"))
    task_info = data.get("tasks", {}).get(task_id, {})
    launch_services_var = tk.BooleanVar(value=task_info.get("run_fs_cs_with_rk7man", False))

    tk.Label(distribution, text="Версия IR:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
    tk.Entry(distribution, textvariable=version_var, width=18).grid(row=0, column=1, sticky="w", pady=3)
    tk.Label(distribution, text="latest — последняя доступная", fg="gray40").grid(
        row=0, column=2, sticky="w", padx=6
    )

    tk.Label(distribution, text="Папка FS:").grid(row=1, column=0, sticky="w", padx=6, pady=3)
    tk.Entry(distribution, textvariable=install_path_var, width=48).grid(
        row=1, column=1, columnspan=2, sticky="ew", pady=3
    )

    def browse_install_path():
        initial = install_path_var.get().strip()
        if not os.path.isdir(initial):
            initial = task_folder if os.path.isdir(task_folder) else ini_path
        selected = filedialog.askdirectory(parent=win, initialdir=initial)
        if selected:
            install_path_var.set(os.path.normpath(selected))

    tk.Button(distribution, text="Обзор", command=browse_install_path).grid(row=1, column=3, padx=6)

    tk.Label(distribution, text="Кэш:").grid(row=2, column=0, sticky="w", padx=6, pady=3)
    tk.Entry(distribution, textvariable=cache_path_var, width=48).grid(
        row=2, column=1, columnspan=2, sticky="ew", pady=3
    )

    def browse_cache_path():
        initial = cache_path_var.get().strip()
        selected = filedialog.askdirectory(
            parent=win, initialdir=initial if os.path.isdir(initial) else task_folder
        )
        if selected:
            cache_path_var.set(os.path.normpath(selected))

    tk.Button(distribution, text="Обзор", command=browse_cache_path).grid(row=2, column=3, padx=6)

    tk.Label(distribution, text="Сервер:").grid(row=3, column=0, sticky="w", padx=6, pady=3)
    ttk.Combobox(
        distribution, textvariable=server_var, values=("web", "new"), state="readonly", width=15
    ).grid(row=3, column=1, sticky="w", pady=3)
    def on_launch_services_toggle():
        current_data = load_data()
        current_task = current_data.get("tasks", {}).get(task_id)
        if current_task is not None:
            current_task["run_fs_cs_with_rk7man"] = launch_services_var.get()
            save_data(current_data)

    tk.Checkbutton(
        distribution,
        text="Запускать FS, CS вместе с RK7man",
        variable=launch_services_var,
        command=on_launch_services_toggle,
    ).grid(row=4, column=0, columnspan=4, sticky="w", padx=6, pady=(2, 5))

    sql_frame = tk.LabelFrame(frame, text="База данных")
    sql_frame.pack(fill="x", padx=12, pady=(0, 8))
    sql_frame.grid_columnconfigure(1, weight=1)

    sql_enabled_var = tk.BooleanVar(value=saved.get("sql_enabled", True))
    sql_server_var = tk.StringVar(value=saved.get("sql_server", sql_saved.get("server", "localhost")))
    sql_database_var = tk.StringVar(value=f"RK7_{task_id}")
    windows_auth_var = tk.BooleanVar(value=saved.get(
        "sql_windows_auth", sql_saved.get("windows_auth", True)
    ))
    username_var = tk.StringVar(value=saved.get("sql_username", sql_saved.get("username", "")))
    password_var = tk.StringVar()

    sql_check = tk.Checkbutton(sql_frame, text="Настроить подключение Feature Server к SQL", variable=sql_enabled_var)
    sql_check.grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(3, 2))
    tk.Label(sql_frame, text="SQL Server:").grid(row=1, column=0, sticky="w", padx=6, pady=2)
    sql_server_entry = tk.Entry(sql_frame, textvariable=sql_server_var, width=38)
    sql_server_entry.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=2)
    tk.Label(sql_frame, text="Имя базы:").grid(row=2, column=0, sticky="w", padx=6, pady=2)
    sql_database_entry = tk.Entry(sql_frame, textvariable=sql_database_var, width=38)
    sql_database_entry.grid(row=2, column=1, sticky="ew", padx=(0, 6), pady=2)
    create_db_btn = tk.Button(
        sql_frame, text="Создать БД", state="disabled", width=12,
        command=lambda: on_create_database()
    )
    create_db_btn.grid(row=2, column=2, padx=(0, 6))
    auth_check = tk.Checkbutton(sql_frame, text="Проверка подлинности Windows", variable=windows_auth_var)
    auth_check.grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    tk.Label(sql_frame, text="Пользователь:").grid(row=4, column=0, sticky="w", padx=6, pady=2)
    username_entry = tk.Entry(sql_frame, textvariable=username_var, width=38)
    username_entry.grid(row=4, column=1, sticky="ew", padx=(0, 6), pady=2)
    tk.Label(sql_frame, text="Пароль:").grid(row=5, column=0, sticky="w", padx=6, pady=2)
    password_entry = tk.Entry(sql_frame, textvariable=password_var, show="*", width=38)
    password_entry.grid(row=5, column=1, sticky="ew", padx=(0, 6), pady=2)
    tk.Label(
        sql_frame,
        text="При установке удаляются старые служебные записи IR из DBInformation.",
        fg="gray40", font=("TkDefaultFont", 8)
    ).grid(row=6, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 5))

    def update_sql_state():
        sql_active = sql_enabled_var.get() and not state["busy"]
        sql_state = "normal" if sql_active else "disabled"
        for widget in (sql_server_entry, sql_database_entry, auth_check):
            widget.config(state=sql_state)
        auth_state = "normal" if sql_active and not windows_auth_var.get() else "disabled"
        username_entry.config(state=auth_state)
        password_entry.config(state=auth_state)
        create_state = "normal" if sql_active and state["database_missing"] else "disabled"
        create_db_btn.config(state=create_state)

    sql_check.config(command=update_sql_state)
    auth_check.config(command=update_sql_state)

    advanced_frame = tk.LabelFrame(frame, text="Адреса сервисов")
    cs_url_var = tk.StringVar(value=saved.get("cs_url", "http://127.0.0.1:7007/soap/UCSCommonWS"))
    fs_url_var = tk.StringVar(value=saved.get("fs_url", "http://127.0.0.1:8888/soap/IStructuresInfo"))
    advanced_frame.grid_columnconfigure(1, weight=1)
    tk.Label(advanced_frame, text="UCSCommonWS:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
    tk.Entry(advanced_frame, textvariable=cs_url_var, width=48).grid(row=0, column=1, sticky="ew", padx=(0, 6))
    tk.Label(advanced_frame, text="IStructuresInfo:").grid(row=1, column=0, sticky="w", padx=6, pady=3)
    tk.Entry(advanced_frame, textvariable=fs_url_var, width=48).grid(row=1, column=1, sticky="ew", padx=(0, 6))

    advanced_visible = [False]

    def toggle_advanced():
        advanced_visible[0] = not advanced_visible[0]
        if advanced_visible[0]:
            advanced_frame.pack(fill="x", padx=12, pady=(0, 8), before=status_frame)
            advanced_btn.config(text="▾ Дополнительные настройки")
        else:
            advanced_frame.pack_forget()
            advanced_btn.config(text="▸ Дополнительные настройки")
        _center_window(win, max_width=680, min_width=560)

    advanced_btn = tk.Button(frame, text="▸ Дополнительные настройки", relief="flat", command=toggle_advanced)
    advanced_btn.pack(anchor="w", padx=12)

    status_frame = tk.Frame(frame)
    status_frame.pack(fill="x", padx=12, pady=(4, 0))
    progress = ttk.Progressbar(status_frame, mode="indeterminate", length=130)
    progress.pack(side="left", fill="x", expand=True)
    status_var = tk.StringVar(value="Готово к установке")
    tk.Label(status_frame, textvariable=status_var, fg="gray40").pack(side="left", padx=(8, 0))

    log_text = tk.Text(frame, height=7, wrap="word", state="disabled", font=("TkDefaultFont", 8))
    log_text.pack(fill="both", expand=True, padx=12, pady=(5, 8))

    def append_log(line):
        def update():
            if not win.winfo_exists():
                return
            log_text.config(state="normal")
            log_text.insert("end", line + "\n")
            log_text.see("end")
            log_text.config(state="disabled")
        root.after(0, update)

    state = {
        "busy": False,
        "database_missing": False,
        "cs_path": task_info.get("cs_service_path", ""),
    }

    def set_busy(busy, status="Установка..."):
        state["busy"] = busy
        install_btn.config(state="disabled" if busy else "normal")
        cancel_btn.config(state="disabled" if busy else "normal")
        update_sql_state()
        if busy:
            progress.start(12)
            status_var.set(status)
        else:
            progress.stop()

    def on_close():
        if not state["busy"]:
            win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)

    def on_create_database():
        server = sql_server_var.get().strip()
        database = sql_database_var.get().strip()
        windows_auth = windows_auth_var.get()
        username = username_var.get().strip()
        password = password_var.get()

        if not server or not database:
            centered_warning("Установка Feature Server", "Укажите адрес SQL Server и имя базы данных.")
            return
        if not windows_auth and (not username or not password):
            centered_warning("Установка Feature Server", "Укажите пользователя и пароль SQL Server.")
            return

        set_busy(True, "Создание базы данных...")

        def job():
            try:
                created_name = create_database(server, database, windows_auth, username, password)
            except SqlDatabaseError as e:
                def show_error(error_message=str(e)):
                    if not win.winfo_exists():
                        return
                    set_busy(False)
                    status_var.set("Ошибка создания базы данных")
                    centered_error("Установка Feature Server", error_message)
                root.after(0, show_error)
                return

            def show_success():
                if not win.winfo_exists():
                    return
                state["database_missing"] = False
                set_busy(False)
                status_var.set("База данных создана")
                centered_info(
                    "Установка Feature Server",
                    f"База данных {created_name} успешно создана.\nТеперь можно продолжить установку."
                )
            root.after(0, show_success)

        threading.Thread(target=job, daemon=True).start()

    def on_install(database_checked=False):
        version = version_var.get().strip().lower()
        install_path = os.path.normpath(os.path.abspath(install_path_var.get().strip()))
        cache_path = cache_path_var.get().strip()
        sql_enabled = sql_enabled_var.get()
        windows_auth = windows_auth_var.get()

        if not re.fullmatch(r"(?:\d+\.\d+\.\d+\.\d+|latest)", version):
            centered_warning("Установка Feature Server", "Версия должна иметь вид X.Y.Z.W или latest.")
            return
        if not install_path_var.get().strip() or os.path.splitdrive(install_path)[1] in ("", "\\", "/"):
            centered_warning("Установка Feature Server", "Укажите отдельную папку для установки Feature Server.")
            return
        if _same_path(install_path, ini_path):
            centered_warning("Установка Feature Server", "Feature Server нельзя устанавливать в папку bin\\win.")
            return
        if not os.path.isfile(os.path.join(ini_path, "rk7man.exe")):
            centered_warning("Установка Feature Server", "В текущей папке bin\\win не найден rk7man.exe.")
            return
        if sql_enabled and (not sql_server_var.get().strip() or not sql_database_var.get().strip()):
            centered_warning("Установка Feature Server", "Укажите адрес SQL Server и имя базы данных.")
            return
        if sql_enabled and not windows_auth and (not username_var.get().strip() or not password_var.get()):
            centered_warning("Установка Feature Server", "Укажите пользователя и пароль SQL Server.")
            return
        state["cs_path"] = _resolve_cs_service(state["cs_path"], win, task_folder)
        if not state["cs_path"]:
            return

        if sql_enabled and not database_checked:
            server = sql_server_var.get().strip()
            database = sql_database_var.get().strip()
            username = username_var.get().strip()
            password = password_var.get()
            state["database_missing"] = False
            set_busy(True, "Проверка базы данных...")

            def check_job():
                try:
                    exists = database_exists(server, database, windows_auth, username, password)
                except SqlDatabaseError as e:
                    def show_error(error_message=str(e)):
                        if not win.winfo_exists():
                            return
                        set_busy(False)
                        status_var.set("Ошибка проверки базы данных")
                        centered_error("Установка Feature Server", error_message)
                    root.after(0, show_error)
                    return

                def show_result():
                    if not win.winfo_exists():
                        return
                    set_busy(False)
                    if exists:
                        on_install(database_checked=True)
                        return
                    state["database_missing"] = True
                    update_sql_state()
                    status_var.set("База данных не найдена")
                    append_log(f"База данных не найдена: {database}")
                    centered_warning(
                        "Установка Feature Server",
                        f"Базы данных «{database}» нет в списке баз на SQL Server.\n"
                        "Нажмите «Создать БД», чтобы создать её, или укажите другое имя."
                    )
                root.after(0, show_result)

            threading.Thread(target=check_job, daemon=True).start()
            return

        for process, process_dir in get_process_by_name("IRReportsFSPrj.exe"):
            if _same_path(process_dir, install_path):
                centered_warning(
                    "Установка Feature Server",
                    "Feature Server запущен из выбранной папки. Закройте его и повторите установку."
                )
                return
        for process, process_dir in get_process_by_name("rk7man.exe"):
            if _same_path(process_dir, ini_path):
                centered_warning(
                    "Установка Feature Server",
                    "RK7man текущей версии запущен. Закройте его перед обновлением плагинов."
                )
                return

        if os.path.isdir(install_path) and os.listdir(install_path):
            if not centered_askyesno(
                "Повторная установка Feature Server",
                "Выбранная папка не пуста. Существующие файлы будут перезаписаны, "
                "IRReportsFSPrj.ini будет создан заново с сохранением GUID. Продолжить?"
            ):
                return

        options = {
            "version": version,
            "install_path": install_path,
            "cache_path": cache_path,
            "server": server_var.get(),
            "rk7man_path": ini_path,
            "cs_path": state["cs_path"],
            "cs_url": cs_url_var.get().strip(),
            "fs_url": fs_url_var.get().strip(),
            "sql_enabled": sql_enabled,
            "sql_server": sql_server_var.get().strip(),
            "sql_database": sql_database_var.get().strip(),
            "sql_windows_auth": windows_auth,
            "sql_username": username_var.get().strip(),
            "sql_password": password_var.get(),
        }

        set_busy(True)
        log_text.config(state="normal")
        log_text.delete("1.0", "end")
        log_text.config(state="disabled")

        def job():
            try:
                install_feature_server(options, append_log)
                schrep_guid = read_schrep_guid(ini_path)
                if not schrep_guid:
                    raise FeatureServerError(
                        "В SchRepPluginClient.ini не найден fs_guid в секции [CS_CONNECTION]."
                    )
                fs_shortcut = os.path.join(task_folder, "FS.lnk")
                create_lnk(
                    fs_shortcut,
                    os.path.join(install_path, "IRReportsFSPrj.exe"),
                    "/desktop"
                )
                if not minimize_lnk(fs_shortcut):
                    raise FeatureServerError(f"Не удалось настроить свёрнутый запуск FS:\n{fs_shortcut}")
                _create_cs_shortcut(task_folder, options["cs_path"])
            except Exception as e:
                def show_error(error_message=str(e)):
                    if not win.winfo_exists():
                        return
                    password_var.set("")
                    set_busy(False)
                    status_var.set("Ошибка установки")
                    append_log(error_message)
                    centered_error("Установка Feature Server", error_message)
                root.after(0, show_error)
                return
            finally:
                options["sql_password"] = ""

            def show_success():
                if not win.winfo_exists():
                    return
                password_var.set("")
                current_data = load_data()
                current_data["settings"]["feature_server"] = {
                    "version": version,
                    "cache_path": cache_path,
                    "server": server_var.get(),
                    "cs_url": cs_url_var.get().strip(),
                    "fs_url": fs_url_var.get().strip(),
                    "sql_enabled": sql_enabled,
                    "sql_server": sql_server_var.get().strip(),
                    "sql_windows_auth": windows_auth,
                    "sql_username": "" if windows_auth else username_var.get().strip(),
                }
                current_task = current_data.get("tasks", {}).get(task_id)
                if current_task is not None:
                    current_task["run_fs_cs_with_rk7man"] = launch_services_var.get()
                    current_task["schrep_fs_guid"] = schrep_guid
                    current_task["cs_service_path"] = options["cs_path"]
                save_data(current_data)
                set_busy(False)
                status_var.set("Установка завершена")
                append_log("Feature Server успешно установлен.")
                centered_info("Установка Feature Server", f"Feature Server установлен:\n{install_path}")
            root.after(0, show_success)

        threading.Thread(target=job, daemon=True).start()

    buttons = tk.Frame(frame)
    buttons.pack(pady=(0, 12))
    install_btn = tk.Button(buttons, text="Установить", command=on_install, width=12)
    install_btn.pack(side="left", padx=5)
    cancel_btn = tk.Button(buttons, text="Закрыть", command=on_close, width=12)
    cancel_btn.pack(side="left", padx=5)

    update_sql_state()
    _center_window(win, max_width=680, min_width=560)
    win.focus_force()
    win.deiconify()
