# ======================= dialogs.py =======================
# Центрированные диалоговые окна и подсказки.
# Перед использованием вызвать init(root, icon_path) — один раз после создания главного окна.

import tkinter as tk

# Максимальная ширина всплывающих окон: если текст в Label не влезает,
# он переносится на новую строку (wraplength), а не растягивает окно.
CENTERED_WINDOW_MAX_WIDTH = 500
# Окно-таблица с флажками шире: в нём пути процессов
CHECKLIST_WINDOW_MAX_WIDTH = 580

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

def _ask_choice(title, message, options, details=None, details_label="Подробнее"):
    """Окно с вопросом и кнопкой на каждый вариант из options. Ждёт ответа,
    возвращает индекс нажатой кнопки (None — окно закрыто крестиком).
    details — необязательный текст, который показывается свёрнутым под сообщением."""
    result = [None]
    win, frame = _create_dialog(title, message)
    if details:
        _add_details(win, frame, details, details_label)

    def answer(index):
        result[0] = index
        win.destroy()

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=(0, 15))
    for i, text in enumerate(options):
        tk.Button(btn_frame, text=text, command=lambda i=i: answer(i),
                  width=max(10, len(text) + 2)).pack(side="left", padx=5)

    _center_window(win)

    win.focus_force()
    win.deiconify()
    win.wait_window()
    return result[0]

def _ask(title, message, yes_text, no_text, details=None, details_label="Подробнее"):
    """Окно с вопросом и двумя кнопками. Возвращает True/False (None — окно закрыто крестиком)."""
    choice = _ask_choice(title, message, [yes_text, no_text], details, details_label)
    return None if choice is None else choice == 0

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

def centered_askchoice(title, message, options, details=None, details_label="Подробнее"):
    """Центрированное окно с кнопкой на каждый вариант из options.
    Возвращает индекс выбранного варианта или None, если окно закрыто крестиком."""
    return _ask_choice(title, message, options, details, details_label)

def centered_askselect(title, message, options, multiple=False):
    """Окно со списком вариантов и кнопками «Выбрать» / «Отмена».
    Обычно выбирается один вариант (двойной клик по строке — выбор) и возвращается его индекс.
    multiple=True — клик отмечает/снимает строку, сразу отмечены все; возвращается список индексов.
    None — пользователь отказался."""
    win, frame = _create_dialog(title, message)
    result = [None]

    listbox = tk.Listbox(frame, activestyle="none", exportselection=False,
                         selectmode="multiple" if multiple else "browse",
                         height=min(len(options), 10), width=max(len(o) for o in options) + 2)
    for option in options:
        listbox.insert("end", option)
    listbox.selection_set(0, "end" if multiple else 0)
    listbox.pack(fill="x", padx=15, pady=(0, 10))

    def choose(event=None):
        selection = listbox.curselection()
        if selection:
            result[0] = list(selection) if multiple else selection[0]
            win.destroy()

    if not multiple:
        listbox.bind("<Double-Button-1>", choose)

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=(0, 15))
    tk.Button(btn_frame, text="Выбрать", command=choose, width=10).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=win.destroy, width=10).pack(side="left", padx=5)

    _center_window(win, max_width=CHECKLIST_WINDOW_MAX_WIDTH)

    win.focus_force()
    win.deiconify()
    win.wait_window()
    return result[0]

def centered_askchecklist(title, entries, question, details=None, details_label="Подробнее"):
    """Окно со списком флажков и кнопками Да/Нет.
    entries — список (text, checkable): checkable=True — флажок (по умолчанию отмечен),
    False — просто строка текста. Если все флажки сняты, кнопка «Да» неактивна.
    Возвращает список bool по каждому элементу entries (для строк без флажка — False)
    или None, если пользователь отказался."""
    win, frame = _create_dialog(title, None)
    result = [None]

    # Таблица: первый столбец — флажок, второй — описание (первая строка жирным).
    # Линии сетки — фон контейнера, видимый в промежутках между ячейками.
    table = tk.Frame(frame, background="gray70", padx=1, pady=1)
    table.pack(fill="x", padx=15, pady=(15, 5))
    table.grid_columnconfigure(1, weight=1)
    cell_bg = frame.cget("background")
    header_bg = "gray88"
    bold_font = ("TkDefaultFont", 9, "bold")

    for col, text in enumerate(("Закрыть", "Процесс")):
        tk.Label(table, text=text, font=bold_font, background=header_bg, padx=8, pady=3,
                 anchor="center" if col == 0 else "w").grid(row=0, column=col, sticky="nsew",
                                                           padx=(0, 1 if col == 0 else 0), pady=(0, 1))

    check_vars = []
    for row, (text, checkable) in enumerate(entries, start=1):
        pady = (0, 1) if row < len(entries) else 0
        check_cell = tk.Frame(table, background=cell_bg, width=60)
        check_cell.grid(row=row, column=0, sticky="nsew", padx=(0, 1), pady=pady)
        info_cell = tk.Frame(table, background=cell_bg, padx=8, pady=4)
        info_cell.grid(row=row, column=1, sticky="nsew", pady=pady)

        first_line, _, rest = text.partition("\n")
        labels = [tk.Label(info_cell, text=first_line, font=bold_font, justify="left", anchor="w",
                           background=cell_bg, wraplength=420)]
        if rest:
            labels.append(tk.Label(info_cell, text=rest, justify="left", anchor="w",
                                   background=cell_bg, wraplength=420))
        for label in labels:
            label.pack(anchor="w", fill="x")

        if checkable:
            var = tk.BooleanVar(value=True)
            tk.Checkbutton(check_cell, variable=var, background=cell_bg, activebackground=cell_bg,
                           command=lambda: update_yes_state()).place(relx=0.5, rely=0.5, anchor="center")

            def toggle(event, var=var):
                var.set(not var.get())
                update_yes_state()
            for widget in [info_cell] + labels:
                widget.bind("<Button-1>", toggle)
                widget.config(cursor="hand2")
        else:
            var = None
            for label in labels:
                label.config(foreground="gray40")
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

    _center_window(win, max_width=CHECKLIST_WINDOW_MAX_WIDTH)

    win.focus_force()
    win.deiconify()
    win.wait_window()
    return result[0]

def centered_asklogin(title, message, login=""):
    """Окно ввода логина и пароля. Возвращает (логин, пароль) или None, если отказались."""
    win, frame = _create_dialog(title, message)
    result = [None]

    fields = tk.Frame(frame)
    fields.pack(padx=15, pady=(0, 10), fill="x")
    tk.Label(fields, text="Логин:").grid(row=0, column=0, sticky="w", pady=2)
    login_entry = tk.Entry(fields, width=32)
    login_entry.insert(0, login)
    login_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=2)
    tk.Label(fields, text="Пароль:").grid(row=1, column=0, sticky="w", pady=2)
    password_entry = tk.Entry(fields, width=32, show="•")
    password_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=2)
    fields.grid_columnconfigure(1, weight=1)

    def ok(event=None):
        if login_entry.get().strip() and password_entry.get():
            result[0] = (login_entry.get().strip(), password_entry.get())
            win.destroy()

    win.bind("<Return>", ok)
    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=(0, 15))
    tk.Button(btn_frame, text="OK", command=ok, width=10).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Отмена", command=win.destroy, width=10).pack(side="left", padx=5)

    _center_window(win)

    win.focus_force()
    win.deiconify()
    (password_entry if login else login_entry).focus_set()
    win.wait_window()
    return result[0]

def centered_askokcancel(title, message):
    """Центрированное окно с вопросом OK/Отмена. Возвращает True/False."""
    return _ask(title, message, "OK", "Отмена")

def add_tooltip(widget, text, delay=500, wraplength=300):
    """Всплывающая подсказка: появляется под курсором через delay мс после наведения на widget."""
    state = {"job": None, "win": None}

    def show():
        state["job"] = None
        win = tk.Toplevel(widget)
        win.wm_overrideredirect(True)
        win.attributes("-topmost", True)
        tk.Label(win, text=text, justify="left", background="#ffffe1", relief="solid",
                 borderwidth=1, padx=6, pady=3, wraplength=wraplength).pack()
        win.update_idletasks()
        # Под курсором, но не за правым и нижним краем экрана
        x = min(widget.winfo_pointerx() + 12, widget.winfo_screenwidth() - win.winfo_reqwidth())
        y = widget.winfo_pointery() + 18
        if y + win.winfo_reqheight() > widget.winfo_screenheight():
            y = widget.winfo_pointery() - win.winfo_reqheight() - 6
        win.geometry(f"+{x}+{y}")
        state["win"] = win

    def enter(event):
        hide()
        state["job"] = widget.after(delay, show)

    def hide(event=None):
        if state["job"]:
            widget.after_cancel(state["job"])
            state["job"] = None
        if state["win"]:
            state["win"].destroy()
            state["win"] = None

    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", hide, add="+")
    widget.bind("<ButtonPress>", hide, add="+")
