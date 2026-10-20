# ======================= shortcuts.py =======================
# Создание ярлыков для задач R-Keeper
# Этот модуль можно использовать независимо от основного приложения

import os
import subprocess

def create_task_shortcuts(task_folder, bin_win_path):
    """Создаёт ярлыки и ярлык папки win в папке задачи."""
    try:
        # 1. Ярлык папки win
        win_folder = bin_win_path
        if os.path.isdir(win_folder):
            create_folder_lnk(os.path.join(task_folder, "..win.lnk"), win_folder)

        # 2. refsrv.exe с ключом /desktop
        refsrv_src = os.path.join(bin_win_path, "refsrv.exe")
        if os.path.isfile(refsrv_src):
            create_lnk(os.path.join(task_folder, "refsrv.lnk"), refsrv_src, "/desktop")

        # 3. MIDSERV.exe с ключом /desktop
        midsrv_src = os.path.join(bin_win_path, "MIDSERV.exe")
        if os.path.isfile(midsrv_src):
            create_lnk(os.path.join(task_folder, "MIDSERV.lnk"), midsrv_src, "/desktop")

        # 4. rk7man.bat без ключа
        rk7man_src = os.path.join(bin_win_path, "rk7man.bat")
        if os.path.isfile(rk7man_src):
            create_lnk(os.path.join(task_folder, "rk7man.lnk"), rk7man_src, "")

        # 5. wincash.bat без ключа
        wincash_src = os.path.join(bin_win_path, "wincash.bat")
        if os.path.isfile(wincash_src):
            create_lnk(os.path.join(task_folder, "wincash.lnk"), wincash_src, "")

        print(f"[OK] Ярлыки созданы в {task_folder}")
    except Exception as e:
        print(f"[WARN] Не удалось создать ярлыки: {e}")

def create_folder_lnk(lnk_path, target_folder):
    """Создаёт ярлык папки (.lnk) через PowerShell."""
    if os.path.exists(lnk_path):
        return
    try:
        bin_folder = os.path.dirname(target_folder).replace("/", "\\")
        target_folder_escaped = target_folder.replace("/", "\\")
        if not target_folder_escaped.endswith("\\"):
            target_folder_escaped += "\\"
        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{lnk_path}")
$Shortcut.TargetPath = "{target_folder_escaped}"
$Shortcut.WorkingDirectory = "{bin_folder}"
$Shortcut.Description = "..win"
$Shortcut.Save()
'''
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        if result.returncode != 0:
            print(f"[WARN] PowerShell error: {result.stderr}")
    except Exception as e:
        print(f"[WARN] create_folder_lnk failed: {e}")

def create_lnk(lnk_path, target, arguments):
    """Создаёт .lnk файл через PowerShell."""
    if os.path.exists(lnk_path):
        return
    try:
        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{lnk_path}")
$Shortcut.TargetPath = "{target}"
$Shortcut.Arguments = "{arguments}"
$Shortcut.WorkingDirectory = "{os.path.dirname(target)}"
$Shortcut.Save()
'''
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        if result.returncode != 0:
            print(f"[WARN] PowerShell error: {result.stderr}")
    except Exception as e:
        print(f"[WARN] create_lnk failed: {e}")
