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
    if isinstance(widget, (tk.Label, tk.Checkbutton)):
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

    if message:
        tk.Label(frame, text=message, justify="left").pack(padx=15, pady=(15, 10))
    return win, frame

def _show_message(title, message):
    """Окно с сообщением и кнопкой OK (не блокирует вызывающий код)."""
    win, frame = _create_dialog(title, message)
    tk.Button(frame, text="OK", command=win.destroy, width=12).pack(pady=(0, 15))

    _center_window(win)

    win.focus_force()
    win.deiconify()

def _add_details(win, frame, details, details_label):
    """Свёрнутый по умолчанию блок с подробностями: '▸ <details_label>' раскрывает текст."""
    details_frame = tk.Frame(frame)
    details_frame.pack(fill="x", padx=15, pady=(0, 10))
    details_text = tk.Label(details_frame, text=details, justify="left", fg="gray30")
    expanded = [False]

    def toggle():
        expanded[0] = not expanded[0]
        toggle_btn.config(text=f"{'▾' if expanded[0] else '▸'} {details_label}")
        if expanded[0]:
            details_text.pack(anchor="w", padx=(12, 0))
        else:
            details_text.pack_forget()
        _center_window(win)

    toggle_btn = tk.Label(details_frame, text=f"▸ {details_label}", fg="blue", cursor="hand2")
    toggle_btn.pack(anchor="w")
    toggle_btn.bind("<Button-1>", lambda e: toggle())

def _ask(title, message, yes_text, no_text, details=None, details_label="Подробнее"):
    """Окно с вопросом и двумя кнопками. Ждёт ответа, возвращает True/False (None — окно закрыто крестиком).
    details — необязательный текст, который показывается свёрнутым под сообщением."""
    result = [None]
    win, frame = _create_dialog(title, message)
    if details:
        _add_details(win, frame, details, details_label)

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

def centered_askyesno(title, message, details=None, details_label="Подробнее"):
    """Центрированное окно с вопросом Да/Нет. Возвращает True/False.
    details — свёрнутый блок подробностей (раскрывается по клику на details_label)."""
    return _ask(title, message, "Да", "Нет", details, details_label)

def centered_askchecklist(title, entries, question, details=None, details_label="Подробнее"):
    """Окно со списком флажков и кнопками Да/Нет.
    entries — список (text, checkable): checkable=True — флажок (по умолчанию отмечен),
    False — просто строка текста. Если все флажки сняты, кнопка «Да» неактивна.
    Возвращает список bool по каждому элементу entries (для строк без флажка — False)
    или None, если пользователь отказался."""
    win, frame = _create_dialog(title, None)
    result = [None]

    entries_frame = tk.Frame(frame)
    entries_frame.pack(fill="x", padx=15, pady=(15, 5))
    check_vars = []
    for text, checkable in entries:
        if checkable:
            var = tk.BooleanVar(value=True)
            tk.Checkbutton(entries_frame, text=text, variable=var, justify="left", anchor="w",
                           command=lambda: update_yes_state()).pack(anchor="w", pady=2)
        else:
            var = None
            tk.Label(entries_frame, text=text, justify="left", anchor="w").pack(anchor="w", padx=(4, 0), pady=2)
        check_vars.append(var)

    tk.Label(frame, text=question, justify="left").pack(anchor="w", padx=15, pady=(5, 10))
    if details:
        _add_details(win, frame, details, details_label)

    def answer(value):
        if value:
            result[0] = [bool(v and v.get()) for v in check_vars]
        win.destroy()

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=(0, 15))
    yes_btn = tk.Button(btn_frame, text="Да", command=lambda: answer(True), width=10)
    yes_btn.pack(side="left", padx=5)
    tk.Button(btn_frame, text="Нет", command=lambda: answer(False), width=10).pack(side="left", padx=5)

    def update_yes_state():
        any_checked = any(v and v.get() for v in check_vars)
        yes_btn.config(state="normal" if any_checked else "disabled")

    _center_window(win)

    win.focus_force()
    win.deiconify()
    win.wait_window()
    return result[0]

def centered_askokcancel(title, message):
    """Центрированное окно с вопросом OK/Отмена. Возвращает True/False."""
    return _ask(title, message, "OK", "Отмена")
