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


class _LogViewer:
    def __init__(self, parent, tail_lines, before=None):
        self.parent = parent
        self.tail_lines = tail_lines
        self.before = before
        self.panel = None
        self.title_label = None
        self.text = None
        self.paths = []
        self.sources = []
        self.multiple = False
        self.after_id = None
        self.panel_width = 0

    def open(self, log_paths):
        paths = [os.fspath(path) for path in log_paths]
        if self.panel is not None and self.panel.winfo_ismapped() and paths == self.paths:
            self.close()
            return self.panel
        if self.panel is None:
            self._create_panel()
        if not self.panel.winfo_ismapped():
            self._show_panel()
        if paths != self.paths:
            self._set_logs(paths)
        elif self.after_id is None:
            self._refresh()
        self.text.focus_set()
        return self.panel

    def _create_panel(self):
        self.panel = tk.Frame(self.parent)
        self.panel.pack_propagate(False)

        header = tk.Frame(self.panel)
        header.pack(side="top", fill="x")
        self.title_label = tk.Label(header, anchor="w")
        self.title_label.pack(side="left", fill="x", expand=True, padx=(6, 3), pady=3)
        tk.Button(header, text="✕", command=self.close, width=2).pack(side="right", padx=(0, 3), pady=2)

        body = tk.Frame(self.panel)
        body.pack(side="top", fill="both", expand=True)
        scrollbar = tk.Scrollbar(body, orient="vertical")
        self.text = tk.Text(
            body,
            wrap="word",
            font=("Consolas", 9),
            state="disabled",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.text.yview)
        scrollbar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<MouseWheel>", self._on_mousewheel)
        self.panel.bind("<Map>", self._show_initial_end)

    def _show_panel(self):
        self.parent.update_idletasks()
        width = self.parent.winfo_width()
        height = self.parent.winfo_height()
        self.panel_width = width
        self.panel.config(width=self.panel_width)
        options = {"side": "right", "fill": "y"}
        if self.before is not None:
            options["before"] = self.before
        self.panel.pack(**options)
        self.parent.geometry(f"{width + self.panel_width}x{height}")

    def _set_logs(self, paths):
        if self.after_id is not None:
            self.panel.after_cancel(self.after_id)
            self.after_id = None
        self.paths = paths
        names = [os.path.basename(path) for path in paths]
        title = "Лог: " + names[0] if len(paths) == 1 else "Логи: " + ", ".join(names)
        self.title_label.config(text=title)
        self.sources = [_LogFile(path, self.tail_lines) for path in paths]
        self.multiple = len(self.sources) > 1
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")
        self._refresh()
        self._show_initial_end()
        self.panel.after_idle(self._show_initial_end)

    def _append_lines(self, source, lines):
        if not lines:
            return
        follow = self.text.yview()[1] >= 0.999
        prefix = f"[{os.path.basename(source.path)}] " if self.multiple else ""
        self.text.config(state="normal")
        self.text.insert("end", "".join(prefix + line + "\n" for line in lines))
        self.text.config(state="disabled")
        if follow:
            self.text.see("end")

    def _refresh(self):
        if self.panel is None:
            self.after_id = None
            return
        for source in self.sources:
            try:
                self._append_lines(source, source.read())
                source.error = None
            except OSError as exc:
                message = str(exc)
                if source.error != message:
                    self._append_lines(source, [f"Ошибка чтения: {message}"])
                    source.error = message
        self.after_id = self.panel.after(500, self._refresh)

    def _on_mousewheel(self, event):
        steps = -int(event.delta / 120)
        if steps == 0:
            steps = -1 if event.delta > 0 else 1
        self.text.yview_scroll(steps, "units")
        return "break"

    def close(self):
        if self.after_id is not None:
            self.panel.after_cancel(self.after_id)
            self.after_id = None
        if self.panel is not None and self.panel.winfo_ismapped():
            width = self.parent.winfo_width()
            height = self.parent.winfo_height()
            self.panel.pack_forget()
            self.parent.geometry(f"{max(1, width - self.panel_width)}x{height}")

    def _show_initial_end(self, event=None):
        if self.panel is not None and self.panel.winfo_ismapped():
            self.text.update_idletasks()
            self.text.yview_moveto(1.0)


def open_log_viewer(parent, log_paths, tail_lines=200, before=None):
    viewer = getattr(parent, "_log_viewer_instance", None)
    if viewer is None:
        viewer = _LogViewer(parent, tail_lines, before)
        parent._log_viewer_instance = viewer
    return viewer.open(log_paths)
