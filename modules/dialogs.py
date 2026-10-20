# ======================= dialogs.py =======================
# Центрированные диалоговые окна и подсказки.
# Перед использованием вызвать init(root, icon_path) — один раз после создания главного окна.

import tkinter as tk

# Максимальная ширина всплывающих окон: если текст в Label не влезает,
# он переносится на новую строку (wraplength), а не растягивает окно.
CENTERED_WINDOW_MAX_WIDTH = 500

_root = None
_icon_path = None

def init(root, icon_path=None):
    """Запоминает главное окно и иконку для всех диалогов."""
    global _root, _icon_path
    _root = root
    _icon_path = icon_path

def _wrap_labels(widget, wraplength):
    if isinstance(widget, tk.Label):
        widget.config(wraplength=wraplength)
    for child in widget.winfo_children():
        _wrap_labels(child, wraplength)

def _center_window(win, max_width=CENTERED_WINDOW_MAX_WIDTH, min_width=280):
    """Центрирует Toplevel-окно относительно root с ограничением максимальной ширины."""
    win.update_idletasks()
    w = win.winfo_reqwidth()
    if w > max_width:
        _wrap_labels(win, max_width - 40)
        win.update_idletasks()
        w = win.winfo_reqwidth()
    w = max(min(w, max_width), min_width)
    h = win.winfo_reqheight()
    x = _root.winfo_x() + (_root.winfo_width() - w) // 2
    y = _root.winfo_y() + (_root.winfo_height() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")
    win.resizable(False, False)

# ======================= Базовые окна =======================

def _create_dialog(title, message):
    """Создаёт модальное скрытое окно с текстом. Возвращает (win, frame)."""
    win = tk.Toplevel(_root)
    win.withdraw()
    win.title(title)

    if _icon_path:
        win.iconbitmap(_icon_path)

    win.transient(_root)
    win.grab_set()

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text=message, justify="left").pack(padx=15, pady=(15, 10))
    return win, frame

def _show_message(title, message):
    """Окно с сообщением и кнопкой OK (не блокирует вызывающий код)."""
    win, frame = _create_dialog(title, message)
    tk.Button(frame, text="OK", command=win.destroy, width=12).pack(pady=(0, 15))

    _center_window(win)

    win.focus_force()
    win.deiconify()

def _ask(title, message, yes_text, no_text):
    """Окно с вопросом и двумя кнопками. Ждёт ответа, возвращает True/False (None — окно закрыто крестиком)."""
    result = [None]
    win, frame = _create_dialog(title, message)

    def answer(value):
        result[0] = value
        win.destroy()

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=(0, 15))
    tk.Button(btn_frame, text=yes_text, command=lambda: answer(True), width=10).pack(side="left", padx=5)
    tk.Button(btn_frame, text=no_text, command=lambda: answer(False), width=10).pack(side="left", padx=5)

    _center_window(win)

    win.focus_force()
    win.deiconify()
    win.wait_window()
    return result[0]

# ======================= Публичные функции =======================

def centered_info(title, message):
    """Центрированное информационное окно."""
    _show_message(title, message)

def centered_warning(title, message):
    """Центрированное окно предупреждения."""
    _show_message(title, message)

def centered_error(title, message):
    """Центрированное окно ошибки."""
    _show_message(title, message)

def centered_askyesno(title, message):
    """Центрированное окно с вопросом Да/Нет. Возвращает True/False."""
    return _ask(title, message, "Да", "Нет")

def centered_askokcancel(title, message):
    """Центрированное окно с вопросом OK/Отмена. Возвращает True/False."""
    return _ask(title, message, "OK", "Отмена")
