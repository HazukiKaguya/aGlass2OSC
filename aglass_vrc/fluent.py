"""Fluent-inspired Tk theme. No extra runtime packages or window hooks."""
import tkinter as tk
from tkinter import ttk, font

BG, WHITE, INK, MUTED, ACCENT = "#f3f3f3", "#ffffff", "#1b1b1b", "#616161", "#0067c0"


def apply_theme(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    font.nametofont("TkDefaultFont", root=root).configure(family="Microsoft YaHei UI", size=10)
    font.nametofont("TkTextFont", root=root).configure(family="Microsoft YaHei UI", size=10)
    style.configure(".", font=("Microsoft YaHei UI", 10))
    root.option_add("*TCombobox*Listbox.background", WHITE)
    root.option_add("*TCombobox*Listbox.foreground", INK)
    root.option_add("*TCombobox*Listbox.selectBackground", "#e5f1fb")
    root.option_add("*TCombobox*Listbox.selectForeground", INK)
    images = []

    def tile(fill, edge, radius=5, size=64):
        # ttk tiles (rather than stretches) the image inside its border.
        # An 18px card with border=8 had a 2x2px center, causing tens of
        # thousands of native image blits on every repaint on Windows.
        image = tk.PhotoImage(master=root, width=size, height=size)
        rows = []
        transparent = []
        for y in range(size):
            row = []
            for x in range(size):
                dx = max(radius - x, x - (size - radius - 1), 0)
                dy = max(radius - y, y - (size - radius - 1), 0)
                if dx * dx + dy * dy <= radius * radius:
                    boundary = x in (0, size - 1) or y in (0, size - 1) or dx * dx + dy * dy > (radius - 1) ** 2
                    row.append(edge if boundary else fill)
                else:
                    row.append(fill)
                    transparent.append((x, y))
            rows.append(tuple(row))
        # Batch the pixels into one Tcl call; preserve just the round corners.
        image.put(tuple(rows))
        for x, y in transparent:
            image.transparency_set(x, y, True)
        images.append(image)
        return image

    for name, fill, hover, pressed, edge, foreground in (
        ("TButton", WHITE, "#f9f9f9", "#eeeeee", "#d5d5d5", INK),
        ("Accent.TButton", ACCENT, "#1975c5", "#3185ce", ACCENT, WHITE),
        ("Nav.TButton", BG, "#eaeaea", "#e4e4e4", BG, INK),
        ("Selected.Nav.TButton", "#e6e6e6", "#e2e2e2", "#dddddd", "#e6e6e6", INK),
    ):
        element = "Fluent." + name
        style.element_create(element, "image", tile(fill, edge),
                             ("disabled", tile("#f5f5f5", "#e5e5e5")),
                             ("pressed", tile(pressed, edge)), ("active", tile(hover, edge)),
                             ("focus", tile(fill, ACCENT)), border=5, sticky="nsew", width=0, height=0)
        style.layout(name, [(element, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]})])
        style.configure(name, foreground=foreground, background=fill, borderwidth=0, relief="flat",
                        padding=(12, 5), width=0, anchor="center", font=("Microsoft YaHei UI", 10))
        style.map(name, foreground=[("disabled", "#9b9b9b")],
                  background=[("disabled", "#f5f5f5"), ("pressed", pressed), ("active", hover)])
    style.configure("Nav.TButton", anchor="w", padding=(15, 11))
    style.configure("Selected.Nav.TButton", anchor="w", padding=(15, 11))
    style.configure("TFrame", background=WHITE)
    style.configure("Shell.TFrame", background=BG)
    style.configure("Card.TFrame", background=WHITE)
    style.element_create("Fluent.Card", "image", tile(WHITE, "#e5e5e5", radius=7, size=128),
                         border=8, sticky="nsew", width=0, height=0)
    style.layout("Card.TFrame", [("Fluent.Card", {"sticky": "nsew"})])
    style.configure("TLabel", background=WHITE, foreground=INK, font=("Microsoft YaHei UI", 10))
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Shell.TLabel", background=BG, foreground=INK)
    style.configure("ShellMuted.TLabel", background=BG, foreground=MUTED)
    style.configure("Card.TLabel", background=WHITE, foreground=INK)
    style.configure("CardMuted.TLabel", background=WHITE, foreground=MUTED)
    style.configure("Title.TLabel", background=BG, font=("Microsoft YaHei UI", 22, "bold"))
    style.configure("Status.TLabel", font=("Microsoft YaHei UI", 16, "bold"), foreground=ACCENT, background=WHITE)
    style.configure("Metric.TLabel", font=("Segoe UI Variable Display", 20), background=WHITE)
    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=0,
                    bordercolor=BG, lightcolor=BG, darkcolor=BG)
    style.layout("TNotebook.Tab", [])
    style.configure("TCheckbutton", background=WHITE, foreground=INK, padding=(0, 5))
    style.map("TCheckbutton", background=[("active", WHITE)], foreground=[("disabled", "#999999")])
    style.configure("TEntry", padding=(8, 7), borderwidth=1, relief="flat", fieldbackground=WHITE,
                    bordercolor="#d1d1d1", lightcolor=WHITE, darkcolor=WHITE, foreground=INK)
    style.map("TEntry", bordercolor=[("focus", ACCENT)], fieldbackground=[("disabled", "#f7f7f7")],
              foreground=[("disabled", "#999999")])
    style.configure("TCombobox", padding=(8, 7), arrowsize=14, borderwidth=1, bordercolor="#d1d1d1",
                    lightcolor=WHITE, darkcolor=WHITE, background=WHITE, fieldbackground=WHITE, foreground=INK)
    style.map("TCombobox", fieldbackground=[("disabled", "#f7f7f7"), ("readonly", WHITE)],
              background=[("active", "#f9f9f9")], foreground=[("disabled", "#999999"), ("readonly", INK)],
              bordercolor=[("focus", ACCENT)], selectbackground=[("readonly", WHITE)], selectforeground=[("readonly", INK)])
    style.configure("Vertical.TScrollbar", gripcount=0, background="#c5c5c5", troughcolor=WHITE,
                    borderwidth=0, arrowsize=10, width=10, arrowcolor=MUTED)
    style.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    style.configure("TSeparator", background="#ebebeb")
    return images  # Keep PhotoImages alive as long as the Tk interpreter.
