import codecs
import os
import tkinter as tk
from collections import deque


class _LogFile:
    def __init__(self, path, tail_lines):
        self.path = path
        self.tail_lines = tail_lines
        self.offset = 0
        self.encoding = None
        self.decoder = None
        self.pending = ""
        self.error = None

    def _new_decoder(self):
        return codecs.getincrementaldecoder(self.encoding or "utf-8")(errors="replace")

    def read(self):
        if self.decoder is None:
            return self.read_tail()
        return self.read_new()

    def read_tail(self):
        with open(self.path, "rb") as file:
            lines = deque(file, maxlen=self.tail_lines)
            self.offset = file.tell()
        data = b"".join(lines)
        if data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
            self.encoding = "utf-16"
            text = data.decode(self.encoding)
            self.encoding = "utf-16-le" if data.startswith(codecs.BOM_UTF16_LE) else "utf-16-be"
        else:
            try:
                text = data.decode("utf-8-sig")
                self.encoding = "utf-8"
            except UnicodeDecodeError:
                text = data.decode("cp1251")
                self.encoding = "cp1251"
        self.decoder = self._new_decoder()
        self.pending = ""
        return text.splitlines()

    def read_new(self):
        with open(self.path, "rb") as file:
            if os.fstat(file.fileno()).st_size < self.offset:
                self.offset = 0
                self.pending = ""
                self.decoder = self._new_decoder()
            file.seek(self.offset)
            data = file.read()
            self.offset = file.tell()
        if not data:
            return []
        self.pending += self.decoder.decode(data)
        lines = self.pending.split("\n")
        self.pending = lines.pop()
        return [line.rstrip("\r") for line in lines]


def open_log_viewer(parent, log_paths, tail_lines=200):
    paths = [os.fspath(path) for path in log_paths]
    names = [os.path.basename(path) for path in paths]
    window = tk.Toplevel(parent)
    window.title("Лог: " + names[0] if len(paths) == 1 else "Логи: " + ", ".join(names))
    parent.update_idletasks()
    width = parent.winfo_width()
    height = parent.winfo_height()
    border = parent.winfo_rootx() - parent.winfo_x()
    x = parent.winfo_x() + width + border * 2
    y = parent.winfo_y()
    window.geometry(f"{width}x{height}{x:+d}{y:+d}")
    window.minsize(400, 200)

    scrollbar = tk.Scrollbar(window, orient="vertical")
    text = tk.Text(
        window,
        wrap="word",
        font=("Consolas", 9),
        state="disabled",
        yscrollcommand=scrollbar.set,
    )
    scrollbar.config(command=text.yview)
    scrollbar.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)

    sources = [_LogFile(path, tail_lines) for path in paths]
    multiple = len(sources) > 1
    after_id = [None]
    closed = [False]
    parent_configure_binding = [None]
    syncing = [False]
    window.update_idletasks()
    positions = {
        "parent": (parent.winfo_x(), parent.winfo_y()),
        "log": (window.winfo_x(), window.winfo_y()),
    }

    def sync_position(source_name):
        if closed[0] or syncing[0]:
            return
        source = parent if source_name == "parent" else window
        target_name = "log" if source_name == "parent" else "parent"
        target = window if source_name == "parent" else parent
        current = (source.winfo_x(), source.winfo_y())
        previous = positions[source_name]
        if current == previous:
            return
        target_position = (
            positions[target_name][0] + current[0] - previous[0],
            positions[target_name][1] + current[1] - previous[1],
        )
        positions[source_name] = current
        positions[target_name] = target_position
        syncing[0] = True
        try:
            target.geometry(f"{target_position[0]:+d}{target_position[1]:+d}")
        finally:
            syncing[0] = False

    def append_lines(source, lines):
        if not lines:
            return
        follow = text.yview()[1] >= 0.999
        prefix = f"[{os.path.basename(source.path)}] " if multiple else ""
        text.config(state="normal")
        text.insert("end", "".join(prefix + line + "\n" for line in lines))
        text.config(state="disabled")
        if follow:
            text.see("end")

    def refresh():
        if closed[0]:
            return
        for source in sources:
            try:
                append_lines(source, source.read())
                source.error = None
            except OSError as exc:
                message = str(exc)
                if source.error != message:
                    append_lines(source, [f"Ошибка чтения: {message}"])
                    source.error = message
        after_id[0] = window.after(500, refresh)

    def on_mousewheel(event):
        steps = -int(event.delta / 120)
        if steps == 0:
            steps = -1 if event.delta > 0 else 1
        text.yview_scroll(steps, "units")
        return "break"

    def on_close():
        closed[0] = True
        if after_id[0] is not None:
            window.after_cancel(after_id[0])
        if parent_configure_binding[0] is not None:
            try:
                parent.unbind("<Configure>", parent_configure_binding[0])
            except tk.TclError:
                pass
        window.destroy()

    def show_initial_end():
        if not closed[0]:
            text.see("end")

    text.bind("<MouseWheel>", on_mousewheel)
    parent_configure_binding[0] = parent.bind(
        "<Configure>", lambda event: sync_position("parent"), add="+"
    )
    window.bind("<Configure>", lambda event: sync_position("log"), add="+")
    window.protocol("WM_DELETE_WINDOW", on_close)
    refresh()
    show_initial_end()
    window.after_idle(show_initial_end)
    return window
