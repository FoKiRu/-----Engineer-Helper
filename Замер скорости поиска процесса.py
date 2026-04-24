import subprocess
import os
import time

def measure_refsrv_search_tasklist(selected_path: str) -> None:
    """Поиск через tasklist - самый быстрый способ"""
    
    sel_norm = os.path.normpath(selected_path).lower()
    start_time = time.perf_counter()
    
    try:
        # ✅ Получаем список процессов через tasklist
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq refsrv.exe', '/FO', 'CSV'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0 or 'refsrv.exe' not in result.stdout:
            elapsed = time.perf_counter() - start_time
            print(f"❌ НЕ НАЙДЕН")
            print(f"⏱️ Время поиска: {elapsed*1000:.2f} мс")
            return
        
        # Парсим PID из tasklist
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            # Формат: "refsrv.exe","PID"
            pid_str = lines[1].split(',')[1].strip('"')
            pid = int(pid_str)
            
            # Теперь получаем полный путь
            try:
                proc = psutil.Process(pid)
                exe_path = proc.exe()
                exe_dir_norm = os.path.normpath(os.path.dirname(exe_path)).lower()
                
                if exe_dir_norm == sel_norm:
                    elapsed = time.perf_counter() - start_time
                    print(f"✅ НАЙДЕН: PID={pid}")
                    print(f"⏱️ Время поиска: {elapsed*1000:.2f} мс")
                    print(f"📊 Путь: {exe_path}")
                    return
            except Exception as e:
                print(f"⚠️ Ошибка при получении пути: {e}")
        
        elapsed = time.perf_counter() - start_time
        print(f"❌ НЕ НАЙДЕН")
        print(f"⏱️ Время поиска: {elapsed*1000:.2f} мс")
        
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"⚠️ ОШИБКА: {e}")
        print(f"⏱️ Время выполнения: {elapsed*1000:.2f} мс")


if __name__ == "__main__":
    import psutil
    measure_refsrv_search_tasklist("C:/Users/WiKi/Desktop/RK7/INST7.25.09.2001 - 187195/bin/win")