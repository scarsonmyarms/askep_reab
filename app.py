"""
Графічна програма для кодування діагнозів реабілітаційного випадку.

Запуск:
    python app.py                      — відкриє вікно вибору файлу довідника
    python app.py довідник.xlsx        — одразу завантажить довідник

Потрібно: Python 3.10+, openpyxl (pip install openpyxl). tkinter входить до стандартного Python
для Windows/macOS; у Linux: sudo apt install python3-tk.
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from coding_rules import (FAIL, INFO, OK, PERIOD_LONG, PERIOD_POST, WARN, Directory, validate)

N_SLOTS = 8
COLORS = {OK: "#1e7b34", WARN: "#9a6700", FAIL: "#b3261e", INFO: "#1f5fa8"}


class SearchCombobox(ttk.Combobox):
    """Випадаючий список з пошуком: введений текст фільтрує варіанти (за будь-якою частиною назви/коду)."""

    def __init__(self, master, on_change, **kw):
        super().__init__(master, **kw)
        self._all: list[str] = []
        self._on_change = on_change
        self.bind("<KeyRelease>", self._filter)
        self.bind("<<ComboboxSelected>>", lambda e: self._on_change())
        self.bind("<Return>", lambda e: self._on_change())
        self.bind("<FocusOut>", lambda e: self._on_change())

    def set_values(self, values: list[str]):
        self._all = values
        self["values"] = values

    def _filter(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        q = self.get().strip().lower()
        self["values"] = [v for v in self._all if q in v.lower()] if q else self._all


class App(tk.Tk):
    def __init__(self, path: str | None = None):
        super().__init__()
        self.title("Кодування діагнозів реабілітаційного випадку")
        self.geometry("1150x860")
        self.directory: Directory | None = None
        self._busy = False
        self._build()
        if path:
            self.load(path)

    # ------------------------------------------------------------------ UI
    def _build(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Відкрити довідник…", command=self.open_file).pack(side="left")
        self.file_lbl = ttk.Label(top, text="Довідник не завантажено", foreground="#666")
        self.file_lbl.pack(side="left", padx=10)

        opts = ttk.Frame(self, padding=(8, 0))
        opts.pack(fill="x")
        ttk.Label(opts, text="Реабілітаційний період:").pack(side="left")
        self.period = tk.StringVar(value=PERIOD_POST)
        for p in (PERIOD_POST, PERIOD_LONG):
            ttk.Radiobutton(opts, text=p, value=p, variable=self.period, command=self.refresh).pack(side="left", padx=4)
        self.st_required = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Коди S/T у формулах наслідків (T90–T95) обов'язкові",
                        variable=self.st_required, command=self.refresh).pack(side="left", padx=20)

        form = ttk.Frame(self, padding=8)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Основний діагноз:", font=("", 10, "bold")).grid(row=0, column=0, sticky="w", pady=3)
        self.main_cb = SearchCombobox(form, self.refresh, width=110)
        self.main_cb.grid(row=0, column=1, sticky="ew", pady=3)
        self.main_cnt = ttk.Label(form, width=14, foreground="#666")
        self.main_cnt.grid(row=0, column=2, sticky="w", padx=4)

        self.slot_cbs: list[SearchCombobox] = []
        self.slot_cnts: list[ttk.Label] = []
        for i in range(N_SLOTS):
            lbl = f"Супутній {i + 1}:" + (" (з формулою)" if i == 0 else "")
            ttk.Label(form, text=lbl).grid(row=i + 1, column=0, sticky="w", pady=2)
            cb = SearchCombobox(form, self.refresh, width=110)
            cb.grid(row=i + 1, column=1, sticky="ew", pady=2)
            cnt = ttk.Label(form, width=14, foreground="#666")
            cnt.grid(row=i + 1, column=2, sticky="w", padx=4)
            ttk.Button(form, text="✕", width=3, command=lambda c=cb: (c.set(""), self.refresh())).grid(row=i + 1, column=3)
            self.slot_cbs.append(cb)
            self.slot_cnts.append(cnt)
        ttk.Label(form, foreground="#666", wraplength=1050, justify="left",
                  text="Поле 1 — за формулою основного; поля 2–8 — за формулами основного та супутнього 1. "
                       "Можна ввести діагноз поза списком (коморбідний стан) — він не враховується у формулах.") \
            .grid(row=N_SLOTS + 1, column=0, columnspan=4, sticky="w", pady=(4, 0))

        btns = ttk.Frame(self, padding=(8, 0))
        btns.pack(fill="x")
        ttk.Button(btns, text="Перевірити", command=self.refresh).pack(side="left")
        ttk.Button(btns, text="Копіювати звіт", command=self.copy_report).pack(side="left", padx=6)
        ttk.Button(btns, text="Очистити все", command=self.clear_all).pack(side="left")

        self.summary = tk.Label(self, text="", font=("", 12, "bold"), anchor="w", padx=10, pady=6)
        self.summary.pack(fill="x", padx=8, pady=(8, 0))

        box = ttk.Frame(self, padding=8)
        box.pack(fill="both", expand=True)
        self.out = tk.Text(box, wrap="word", font=("Consolas", 10), state="disabled")
        sb = ttk.Scrollbar(box, command=self.out.yview)
        self.out.configure(yscrollcommand=sb.set)
        self.out.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for lvl, col in COLORS.items():
            self.out.tag_configure(lvl, foreground=col)
        self.out.tag_configure("h", font=("Consolas", 10, "bold"))

    # ------------------------------------------------------------------ дії
    def open_file(self):
        p = filedialog.askopenfilename(title="Оберіть файл довідника (Додаток)",
                                       filetypes=[("Excel", "*.xlsx *.xlsm"), ("Усі файли", "*.*")])
        if p:
            self.load(p)

    def load(self, path: str):
        try:
            self.directory = Directory(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Помилка", f"Не вдалося прочитати довідник:\n{e}")
            return
        self.file_lbl.config(text=f"{path}  —  {len(self.directory.items)} діагнозів", foreground="#000")
        self.refresh()

    def clear_all(self):
        self.main_cb.set("")
        for cb in self.slot_cbs:
            cb.set("")
        self.refresh()

    def copy_report(self):
        self.clipboard_clear()
        self.clipboard_append(self.out.get("1.0", "end").strip())

    def refresh(self):
        if self._busy or self.directory is None:
            return
        self._busy = True
        try:
            d = self.directory
            mains = d.main_candidates(self.period.get())
            self.main_cb.set_values([x.name for x in mains])
            self.main_cnt.config(text=f"{len(mains)} у списку")

            main = d.find(self.main_cb.get())
            selected = [d.find(cb.get()) if cb.get().strip() else None for cb in self.slot_cbs]
            for i, cb in enumerate(self.slot_cbs):
                cand = d.companion_candidates(main, i, selected)
                cb.set_values([x.name for x in cand])
                self.slot_cnts[i].config(text=f"{len(cand)} у списку" if main else "")

            texts = [cb.get() for cb in self.slot_cbs]
            self._render(validate(d, self.period.get(), self.main_cb.get(), texts, self.st_required.get()))
        finally:
            self._busy = False

    def _render(self, rep):
        self.out.config(state="normal")
        self.out.delete("1.0", "end")

        def head(t):
            self.out.insert("end", t + "\n", "h")

        def line(l, indent="  "):
            self.out.insert("end", f"{indent}{l.level} ", l.level)
            self.out.insert("end", l.text + "\n")

        head("ОСНОВНИЙ ДІАГНОЗ")
        for l in rep.main:
            line(l)
        if rep.main_groups:
            head("\nФОРМУЛА ОСНОВНОГО (закривається супутніми)")
            for l in rep.main_groups:
                line(l)
        if rep.companions:
            head("\nСУПУТНІ")
            for i, (name, ls) in enumerate(rep.companions, 1):
                self.out.insert("end", f"  {i}. {name}\n")
                for l in ls:
                    line(l, "      ")
        head("\nНЕСУМІСНІ ПОЄДНАННЯ")
        if rep.exclusions:
            for l in rep.exclusions:
                line(l)
        else:
            self.out.insert("end", f"  {OK} ", OK)
            self.out.insert("end", "Не виявлено\n")
        self.out.config(state="disabled")
        bg = {OK: "#c6efce", WARN: "#ffeb9c", FAIL: "#ffc7ce", INFO: "#ddebf7"}[rep.summary.level]
        self.summary.config(text=f"{rep.summary.level}  {rep.summary.text}", bg=bg)


if __name__ == "__main__":
    App(sys.argv[1] if len(sys.argv) > 1 else None).mainloop()
