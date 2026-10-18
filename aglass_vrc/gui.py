"""Chinese Tk desktop interface for the existing bridge, with no hardware on import."""
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .gui_support import (BridgeSession, DEFAULTS, ROOT, SETTINGS_PATH, build_arguments,
                          build_key_arguments, load_settings, powershell_command, save_settings)
from .sdk import PROFILES, dll_candidates
from .runtime import running_runtime_sdk
from .runtime_client import runtime_endpoint
from .fluent import BG, WHITE, INK, MUTED, ACCENT, apply_theme

CHOICES = {
    "connection": {"sdk": "SDK DLL（兼容模式）", "runtime": "直连 Runtime 1.1（不加载 DLL）"},
    "profile": {"auto": "自动识别 DLL", "bundled": "Runtime 1.1 · 旧回调接口",
                "vi1-legacy": "DK I / vi-1 · 早期 SDK", "vi1-1.1": "DK I / vi-1 · Client 融合视线", "dkii": "DK II · Client API"},
    "target": {"native": "VRChat 原生眼动", "vrcft-module": "VRCFaceTracking 模块", "vrcft-avatar": "直接发送 Avatar v2 参数"},
    "projection": {"auto": "自动（兼容桌面 / VR）", "steamvr": "SteamVR 投影（必须已启动）", "fov": "桌面 FOV（无需 SteamVR）"},
    "gaze_space": {"viewport": "视口坐标（默认）", "panel": "面板坐标 / 镜片映射"},
    "output": {"center": "融合视线", "per-eye": "左右眼分别输出（仅旧 API）"},
    "client_schema": {"auto": "自动识别", "timestamped": "新版 · 有时间戳", "no-timestamp": "早期 Demo · 无时间戳"},
    "legacy_success_code": {"auto": "跟随 profile / 自动识别", "0": "成功码 0", "1": "成功码 1"},
    "key_medium": {"cdrom": "光驱 CD-ROM（推荐）", "disk": "磁盘（兼容实验）"},
    "key_backend": {"auto": "自动（优先 usbip-win2）", "win2": "usbip-win2 0.9.8.1", "wdm": "cezanne WDM（旧驱动）"},
}


class Application:
    def __init__(self, root, settings_path=SETTINGS_PATH):
        self.root, self.settings_path = root, settings_path
        self.session = BridgeSession()
        self.key_session = BridgeSession("aglass_vrc.usbkey_runner", "Key 清理仍在等待驱动；后台保持运行，不强制结束。请勿用任务管理器结束 Key。", graceful_only=True)
        self.key_probing = False
        self.key_failed = False
        self.key_retained = False
        self.key_status = tk.StringVar(root, "未启动 · 可先检测驱动")
        self.closing = self.diagnosing = False
        self.error = ""
        self.controls = []
        self.widgets = {}
        self.scan_queue = queue.Queue()
        self.runtime_queue = queue.Queue()
        self.runtime_generation = 0
        self.runtime_selection = None
        self.scanning = False
        self.scroll_canvases = []
        self.last_frame = None
        self.lids = [1., 1.]
        self.lid_output_present = False
        warning = ""
        try:
            values = load_settings(settings_path)
        except (OSError, ValueError) as exc:
            values, warning = DEFAULTS.copy(), f"未加载设置：{exc}"
        self.variables = {}
        for key, value in values.items():
            if isinstance(value, bool):
                variable = tk.BooleanVar(root, value=value)
            else:
                if key in CHOICES and value not in CHOICES[key]:
                    value = DEFAULTS[key]
                    warning = "设置含未知选项，已恢复该选项的默认值。"
                variable = tk.StringVar(root, value=CHOICES.get(key, {}).get(value, value))
            self.variables[key] = variable
        self.previous_target = values["target"] if values["target"] in CHOICES["target"] else "native"
        self.status = tk.StringVar(root, "未运行")
        self.detail = tk.StringVar(root, "选择 Runtime 和输出目标，然后开始。")
        self.packet_count = tk.StringVar(root, "0")
        self.elapsed = tk.StringVar(root, "00:00")
        self.source = tk.StringVar(root, "等待数据")
        self.coordinates = tk.StringVar(root, "尚未收到注视点")
        self.lid_text = tk.StringVar(root, "睁闭眼输出：等待数据")
        self.runtime_hint = tk.StringVar(root, "勾选后自动使用运行中 Runtime 目录里的 SDK。")
        self.dongle_hint = tk.StringVar(root, "在桥接进程内伪造钥匙，不改厂商文件、不需要管理员。")
        self._build()
        self._sync_options()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.tick_id = self.root.after(60, self._tick)
        if warning:
            self.log(warning)
        self.log("就绪。眨眼估算默认开启；可选择 SDK 模式或 Runtime 直连。")
        self.scan_id = self.root.after(150, self.scan_dlls)

    def _build(self):
        self.root.title("aGlass2OSC · 眼动桥接")
        self.root.configure(background=BG)
        self.root.geometry(f"1240x{min(900, self.root.winfo_screenheight() - 90)}")
        self.root.minsize(960, 650)
        self.theme_images = apply_theme(self.root)
        shell = ttk.Frame(self.root, style="Shell.TFrame")
        shell.pack(fill="both", expand=True)
        self.sidebar = ttk.Frame(shell, style="Shell.TFrame", width=196, padding=(12, 24))
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        logo = tk.Canvas(self.sidebar, width=40, height=40, background=BG, highlightthickness=0)
        logo.pack(anchor="w", padx=12)
        logo.create_oval(2, 8, 38, 32, outline=ACCENT, width=3)
        logo.create_oval(13, 13, 27, 27, fill=ACCENT, outline="")
        ttk.Label(self.sidebar, text="aGlass2OSC", style="Shell.TLabel", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        ttk.Label(self.sidebar, text="眼动桥接", style="ShellMuted.TLabel").pack(anchor="w", padx=12, pady=(0, 28))
        self.nav_buttons, self.nav_indicators = [], []
        self.page_titles = ("连接与输出", "眼动设置", "高级设置", "虚拟 USB Key")
        self.page_descriptions = ("选择数据来源，连接你的虚拟世界。", "调整视线映射、平滑与睁闭眼估算。",
                                  "配置接口、网络端口与诊断选项。", "管理驱动与 Key，供现有 Runtime 使用。")
        for index, label in enumerate(self.page_titles):
            row = ttk.Frame(self.sidebar, style="Shell.TFrame")
            row.pack(fill="x", pady=3)
            marker = tk.Frame(row, background=BG, width=3, height=18)
            marker.pack(side="left", padx=(0, 4))
            button = ttk.Button(row, text=label, style="Nav.TButton", command=lambda i=index: self.notebook.select(i))
            button.pack(side="left", fill="x", expand=True)
            self.nav_buttons.append(button)
            self.nav_indicators.append(marker)
            self.root.bind(f"<Control-Key-{index + 1}>", lambda e, i=index: self.notebook.select(i))
        ttk.Label(self.sidebar, text="VRChat\nVRCFaceTracking", style="ShellMuted.TLabel", font=("Segoe UI", 9), justify="left").pack(side="bottom", anchor="w", padx=12, pady=(16, 0))
        ttk.Button(self.sidebar, text="使用说明", command=self.open_readme, style="Nav.TButton").pack(side="bottom", fill="x")
        outer = ttk.Frame(shell, style="Shell.TFrame", padding=(12, 22, 24, 18))
        outer.pack(side="left", fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        header = ttk.Frame(outer, style="Shell.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(1, weight=1)
        self.page_title = ttk.Label(header, text=self.page_titles[0], style="Title.TLabel")
        self.page_title.grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.page_description = ttk.Label(header, text=self.page_descriptions[0], style="ShellMuted.TLabel")
        self.page_description.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        card = ttk.Frame(outer, style="Card.TFrame", padding=(18, 12))
        card.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, textvariable=self.status, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.detail_label = ttk.Label(card, textvariable=self.detail, style="CardMuted.TLabel", wraplength=520)
        self.detail_label.grid(row=1, column=0, sticky="w", pady=(3, 0))
        for column, title, variable in ((1, "OSC 包数", self.packet_count), (2, "运行时间", self.elapsed)):
            frame = ttk.Frame(card, padding=(18, 0))
            frame.grid(row=0, column=column, rowspan=2)
            ttk.Label(frame, textvariable=variable, style="Metric.TLabel").pack()
            ttk.Label(frame, text=title, style="CardMuted.TLabel").pack()

        main = ttk.Frame(outer, style="Shell.TFrame")
        main.grid(row=2, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0)
        main.rowconfigure(0, weight=1)
        self.notebook = ttk.Notebook(main)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        pages = []
        for label in ("连接", "眼动设置", "高级", "虚拟 USB Key"):
            holder, frame = self.scroll_area(self.notebook)
            self.notebook.add(holder, text=label)
            frame.columnconfigure(1, weight=1)
            pages.append(frame)
        self.notebook.bind("<<NotebookTabChanged>>", self._navigate)
        self._navigate()
        connection, tracking, inside, key_page = pages
        self.field(connection, "连接方式", "connection", 0)
        self.field(connection, "设备 / Runtime", "profile", 1)
        runtime_row = ttk.Frame(connection)
        runtime_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=5)
        reuse = self.reuse_check = self.check(runtime_row, "使用运行中 Runtime 的配套 DLL", "use_running_runtime")
        reuse.configure(command=self._sync_options)
        reuse.pack(side="left")
        self.runtime_button = self.button(runtime_row, "检测 Runtime", self.detect_runtime)
        self.runtime_button.pack(side="left", padx=10)
        options = ttk.Frame(connection)
        options.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(options, textvariable=self.runtime_hint, style="Muted.TLabel", wraplength=465).pack(anchor="w")
        self.dongle_check = self.check(options, "使用软件狗（无需 USB Key）", "soft_dongle")
        self.dongle_check.pack(anchor="w", pady=(5, 0))
        ttk.Label(options, textvariable=self.dongle_hint, style="Muted.TLabel", wraplength=465).pack(anchor="w")
        self.field(connection, "SDK DLL（手动）", "dll", 4, combo=True)
        paths = ttk.Frame(connection)
        paths.grid(row=5, column=1, sticky="w", pady=(0, 5))
        self.browse_dll_button = self.button(paths, "浏览 DLL…", self.browse_dll)
        self.browse_dll_button.pack(side="left")
        self.scan_button = self.button(paths, "扫描现有 SDK", self.scan_dlls)
        self.scan_button.pack(side="left", padx=7)
        ttk.Label(connection, text="直连不使用 DLL；SDK 模式可手动选择或检测配套 DLL。", style="Muted.TLabel", wraplength=460).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 14))
        self.field(connection, "输出目标", "target", 7)
        endpoint = ttk.Frame(connection)
        endpoint.grid(row=8, column=1, sticky="ew", pady=5)
        ttk.Label(connection, text="接收地址 / 端口").grid(row=8, column=0, sticky="w", padx=(0, 14))
        self.entry(endpoint, "host", 23).pack(side="left", fill="x", expand=True)
        ttk.Label(endpoint, text=" : ").pack(side="left")
        self.entry(endpoint, "port", 7).pack(side="left")
        self.field(connection, "Avatar 参数前缀", "parameter_prefix", 9)
        self.target_hint = ttk.Label(connection, text="", style="Muted.TLabel", wraplength=480)
        self.target_hint.grid(row=10, column=0, columnspan=2, sticky="w", pady=(3, 12))
        simulate = self.check(connection, "模拟数据（不连接设备）", "simulate")
        simulate.configure(command=self._sync_options)
        simulate.grid(row=11, column=0, columnspan=2, sticky="w", pady=4)
        self.check(connection, "仅预览，不发送 OSC", "dry_run").grid(row=12, column=0, columnspan=2, sticky="w", pady=4)

        for row, (title, key) in enumerate((("坐标映射", "projection"), ("输入空间", "gaze_space"), ("视线输出", "output"))):
            self.field(tracking, title, key, row)
        self.pair(tracking, "近似 FOV  X / Y（度）", "fov_x", "fov_y", 3)
        self.pair(tracking, "中心  X / Y", "center_x", "center_y", 4)
        self.pair(tracking, "幅度  X / Y", "gain_x", "gain_y", 5)
        flip = ttk.Frame(tracking)
        flip.grid(row=6, column=1, sticky="w", pady=5)
        self.check(flip, "翻转 X", "invert_x").pack(side="left")
        self.check(flip, "翻转 Y", "invert_y").pack(side="left", padx=15)
        self.field(tracking, "输出频率（Hz）", "rate", 7)
        self.field(tracking, "平滑时间（ms）", "smoothing_ms", 8)
        self.check(tracking, "开启睁闭眼估算", "blink").grid(row=9, column=0, columnspan=2, sticky="w", pady=(10, 5))
        ttk.Label(tracking, text="根据数据有效性估算眨眼；不是原生眼睑开合测量。", style="Muted.TLabel", wraplength=470).grid(row=10, column=0, columnspan=2, sticky="w")

        for row, (title, key) in enumerate((
            ("Client 数据项版本", "client_schema"), ("旧 API 成功码", "legacy_success_code"),
            ("数据过期（秒）", "stale_seconds"), ("闭眼消抖（ms）", "blink_delay_ms"),
            ("最长闭眼估算（秒）", "blink_max_seconds"), ("旧 Runtime 地址", "runtime_host"),
            ("旧 Runtime 请求端口", "runtime_send_port"), ("旧 Runtime 回复端口", "runtime_recv_port"),
            ("旧 API 握手超时（秒）", "timeout"), ("Client 设备事件端口", "event_port"),
            ("Client 眼动端口", "data_port"), ("SDK 启动上限（秒）", "sdk_start_timeout"),
            ("连接清理上限（秒）", "sdk_stop_timeout"), ("CSV 文件（可选）", "log"),
            ("Runtime TCP 端口（0 自动）", "runtime_port"))):
            self.field(inside, title, key, row)
        self.button(inside, "选择新的 CSV 文件…", self.browse_csv).grid(row=15, column=1, sticky="w")
        ttk.Label(inside, text="SDK 模式隔离厂商 DLL；直连模式仅在桥接后台收发网络数据。", wraplength=470, style="Muted.TLabel").grid(row=16, column=0, columnspan=2, sticky="w", pady=12)
        self.button(inside, "复制命令", self.copy_command).grid(row=17, column=1, sticky="w")
        self._build_key(key_page)

        preview_holder, preview = self.scroll_area(main, width=306, card=True)
        self.preview_holder = preview_holder
        preview_holder.grid(row=0, column=1, sticky="nsew")
        ttk.Label(preview, text="原始注视点", style="Card.TLabel", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(preview, textvariable=self.source, style="CardMuted.TLabel").pack(anchor="w", pady=(3, 10))
        self.canvas = tk.Canvas(preview, width=276, height=202, background="#f7f9fc", highlightthickness=0)
        self.canvas.pack()
        ttk.Label(preview, text="左上 (0, 0)  ·  右下 (1, 1)", style="CardMuted.TLabel").pack(anchor="w", pady=(7, 10))
        ttk.Label(preview, textvariable=self.coordinates, style="Card.TLabel", wraplength=276, justify="left").pack(anchor="w")
        ttk.Separator(preview).pack(fill="x", pady=13)
        ttk.Label(preview, textvariable=self.lid_text, style="Card.TLabel", wraplength=276).pack(anchor="w")
        self.eye_canvas = tk.Canvas(preview, width=276, height=48, background=WHITE, highlightthickness=0)
        self.eye_canvas.pack(pady=6)
        ttk.Label(preview, text="指示桥接输出，非摄像头画面。\nClient 的融合视线无法区分左右眼。", style="CardMuted.TLabel", justify="left", wraplength=276).pack(anchor="w")
        self._draw()

        actions = ttk.Frame(header, style="Shell.TFrame")
        actions.grid(row=0, column=1, sticky="e")
        self.start_button = self.button(actions, "开始桥接", self.start, style="Accent.TButton", padding=(8, 5))
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="停止", command=self.stop, state="disabled", padding=(8, 5))
        self.stop_button.pack(side="left", padx=5)
        self.button(actions, "模拟预览", self.preview, padding=(8, 5)).pack(side="left")
        self.diagnose_button = self.button(actions, "检查 DLL", lambda: self.start(diagnose=True), padding=(8, 5))
        self.diagnose_button.pack(side="left", padx=5)
        self.save_button = self.button(actions, "保存设置", self.save, padding=(8, 5))
        self.save_button.pack(side="left")
        log_head = ttk.Frame(outer, style="Shell.TFrame")
        log_head.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(log_head, text="运行日志", style="ShellMuted.TLabel").pack(side="left")
        ttk.Button(log_head, text="导出日志", command=self.export_log, padding=(6, 2)).pack(side="right")
        ttk.Button(log_head, text="清空", command=self.clear_log, padding=(6, 2)).pack(side="right", padx=6)
        log_frame = ttk.Frame(outer)
        log_frame.grid(row=4, column=0, sticky="ew", pady=(5, 0))
        self.log_view = tk.Text(log_frame, height=5, background=WHITE, foreground="#4c4c4c", insertbackground=INK,
                                font=("Consolas", 9), relief="flat", padx=14, pady=10, state="disabled", wrap="word")
        self.log_view.tag_configure("error", foreground="#c42b1c")
        self.log_view.tag_configure("warning", foreground="#9d5d00")
        self.log_view.tag_configure("key", foreground=ACCENT)
        bar = ttk.Scrollbar(log_frame, command=self.log_view.yview)
        def log_scroll(first, last):
            bar.set(first, last)
            overflow = float(first) > 0 or float(last) < 1
            if overflow and not bar.winfo_manager():
                bar.pack(side="right", fill="y", before=self.log_view)
            elif not overflow and bar.winfo_manager():
                bar.pack_forget()
        self.log_view.configure(yscrollcommand=log_scroll)
        self.log_view.bind("<MouseWheel>", lambda _: "break" if self.log_view.yview() == (0., 1.) else None)
        self.log_view.pack(side="left", fill="x", expand=True)
        self.root.bind("<MouseWheel>", self._wheel, add="+")
        self.root.bind("<Configure>", self._responsive, add="+")

    def _navigate(self, _event=None):
        index = self.notebook.index(self.notebook.select())
        self.page_title.configure(text=self.page_titles[index])
        self.page_description.configure(text=self.page_descriptions[index])
        for i, button in enumerate(self.nav_buttons):
            button.configure(style="Selected.Nav.TButton" if i == index else "Nav.TButton")
            self.nav_indicators[i].configure(background=ACCENT if i == index else BG)

    def _responsive(self, event):
        if event.widget != self.root:
            return
        layout = (event.width < 1180, event.height < 740, event.width)
        if getattr(self, "_last_layout", None) == layout:
            return
        self._last_layout = layout
        compact = event.width < 1180
        self.sidebar.configure(width=184 if compact else 196)
        self.log_view.configure(height=3 if event.height < 740 else 5)
        self.detail_label.configure(wraplength=max(240, event.width - 580))
        if compact:
            self.preview_holder.grid_remove()
            self.notebook.grid_configure(padx=0)
        else:
            self.preview_holder.grid()
            self.notebook.grid_configure(padx=(0, 16))

    def _build_key(self, page):
        ttk.Label(page, text="让现有 Runtime 使用虚拟 USB Key", font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(page, text="先启动 Key，再开始桥接。支持 usbip-win2 与旧 WDM 驱动；自动模式优先新版。", wraplength=470, style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 12))
        first = len(self.controls)
        self.field(page, "Key 应答文件", "key_file", 4)
        self.button(page, "选择 Key JSON / BIN…", lambda: self.browse_key("key_file")).grid(row=5, column=1, sticky="w")
        ttk.Label(page, text="留空优先使用程序旁的 aglass_key.bin；也可指定其他应答文件。", wraplength=470, style="Muted.TLabel").grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 10))
        self.field(page, "介质镜像（可选）", "key_image", 7)
        self.button(page, "选择介质 BIN / ISO…", lambda: self.browse_key("key_image")).grid(row=8, column=1, sticky="w")
        ttk.Label(page, text="留空使用空白只读介质；也可选择 E_usbkey.bin。", wraplength=470, style="Muted.TLabel").grid(row=9, column=0, columnspan=2, sticky="w", pady=(4, 10))
        self.field(page, "设备形态", "key_medium", 10)
        self.field(page, "USB 驱动", "key_backend", 11)
        self.field(page, "usbip.exe（可选）", "key_usbip", 12)
        self.key_controls = self.controls[first:]
        del self.controls[first:]  # Independent of bridge settings and its lock.
        actions = ttk.Frame(page)
        actions.grid(row=2, column=0, columnspan=2, sticky="w", pady=8)
        self.key_probe_button = ttk.Button(actions, text="检测驱动", command=lambda: self.start_key(probe=True))
        self.key_probe_button.pack(side="left")
        self.key_start_button = ttk.Button(actions, text="启动 Key", command=self.start_key)
        self.key_start_button.pack(side="left", padx=8)
        self.key_stop_button = ttk.Button(actions, text="停止 Key", command=self.stop_key, state="disabled")
        self.key_stop_button.pack(side="left")
        ttk.Label(page, textvariable=self.key_status, wraplength=470).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 12))
        ttk.Label(page, text="客户端路径留空使用已安装的 usbip-win2。\n先停止桥接，再停止 Key；关闭窗口会依次清理。请用停止按钮或 Ctrl+C，勿强制结束 Key 后台。\n应答计数表示命令已处理，授权结果以桥接日志为准。", wraplength=470, style="Muted.TLabel").grid(row=13, column=0, columnspan=2, sticky="w", pady=8)

    def browse_key(self, name):
        types = [("Key 应答", "*.json *.bin")] if name == "key_file" else [("介质镜像", "*.bin *.iso")]
        path = filedialog.askopenfilename(parent=self.root, title="选择 Key 应答文件" if name == "key_file" else "选择只读介质镜像", filetypes=types + [("所有文件", "*.*")])
        if path:
            self.variables[name].set(path)

    def _lock_key(self):
        busy = self.key_session.active or self.closing
        for widget, state in self.key_controls:
            widget.configure(state="disabled" if busy else state)
        self.key_start_button.configure(state="disabled" if busy else "normal")
        self.key_probe_button.configure(state="disabled" if busy else "normal")
        can_stop = self.key_session.active and self.key_session.stop_deadline is None and not self.session.active and not self.closing
        self.key_stop_button.configure(state="normal" if can_stop else "disabled")

    def start_key(self, probe=False):
        if self.key_session.active or self.closing:
            return
        try:
            self.key_session.start(build_key_arguments(self.values(), probe))
        except (OSError, ValueError, RuntimeError) as exc:
            self.key_status.set(f"无法启动：{exc}")
            self.log(f"[USB Key] {exc}")
            return
        self.key_probing, self.key_failed = probe, False
        self.key_retained = False
        self.key_status.set("正在检测驱动…" if probe else "正在创建虚拟 Key…")
        self._lock_key()

    def stop_key(self):
        if self.session.active or not self.key_session.active:
            return
        self.key_status.set("正在移除本次虚拟 Key…")
        self.key_session.stop(timeout=30.)
        self._lock_key()

    def _poll_key(self):
        for event in self.key_session.poll():
            if event["type"] == "log":
                self.log("[USB Key] " + event["message"])
            elif event["type"] == "exit":
                if event["code"] and not self.key_failed:
                    self.key_status.set(f"Key 后台退出，退出码 {event['code']}；详情见日志。")
                elif not self.key_probing and not self.key_failed:
                    self.key_status.set("已停止 · 端口尚未确认释放，恢复记录已保留" if self.key_retained else "已停止 · 本次接入已清理")
                self.log("[USB Key] 驱动检测完成。" if self.key_probing and event["code"] == 0
                         else f"[USB Key] 后台结束，退出码 {event['code']}。")
                self._lock_key()
            elif event.get("phase") == "probe":
                dependency = "Python 依赖已就绪" if event["dependency"] else "请安装 requirements-usbkey.txt"
                capacity = event.get("capacity")
                slots = f"{len(event['used'])}/{capacity}" if capacity is not None else f"{len(event['used'])}（实际容量未知）"
                full = " · 端口已满，需要恢复控制器" if capacity is not None and len(event['used']) >= capacity else ""
                if event.get("backend") == "win2":
                    self.key_status.set(f"usbip-win2 {event.get('version', '')} 可用 · {dependency} · 已导入 {len(event['used'])} 个设备")
                else:
                    self.key_status.set(f"VHCI 可用 · {dependency} · 驱动记录槽位 {slots}{full}")
                self.log("[USB Key] " + self.key_status.get())
            elif event.get("phase") == "attached" and self.key_session.stop_deadline is None:
                self.key_status.set(f"已接入 · 端口 {event['port']} · 已处理命令 {event['commands']} 次")
            elif event.get("phase") == "detached":
                self.key_retained = event.get("retained") is not False
            elif event.get("phase") == "detaching":
                self.key_status.set("正在 detach 并确认端口释放…")
            elif event.get("phase") == "cleanup_wait":
                self.key_status.set(event["message"])
                self.log("[USB Key] " + event["message"])
            elif event.get("phase") == "error":
                self.key_failed = True
                self.key_status.set("错误：" + event.get("message", "未知错误"))
                self.log("[USB Key] " + self.key_status.get())

    def scroll_area(self, parent, width=520, card=False):
        holder = ttk.Frame(parent, style="Card.TFrame", padding=6)
        canvas = tk.Canvas(holder, background=WHITE, highlightthickness=0, width=width, height=390)
        bar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set, yscrollincrement=18)
        canvas.pack(side="left", fill="both", expand=True)
        canvas.scroll_enabled = False
        body = ttk.Frame(canvas, padding=(12, 14))
        item = canvas.create_window(0, 0, window=body, anchor="nw")
        def sync_scroll(_event=None):
            height = canvas.winfo_height()
            content_height = body.winfo_reqheight()
            overflow = content_height > height
            canvas.scroll_enabled = overflow
            if overflow and not bar.winfo_manager():
                bar.pack(side="right", fill="y", before=canvas)
            elif not overflow and bar.winfo_manager():
                bar.pack_forget()
            canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(height, content_height)))
            if not overflow:
                canvas.yview_moveto(0)

        def resize(event):
            canvas.itemconfigure(item, width=event.width)
            sync_scroll()

        body.bind("<Configure>", sync_scroll)
        canvas.bind("<Configure>", resize)
        self.scroll_canvases.append(canvas)
        return holder, body

    def _wheel(self, event):
        widget = event.widget
        while widget is not None:
            if widget in self.scroll_canvases:
                if widget.scroll_enabled:
                    widget.yview_scroll(-int(event.delta / 120) * 3, "units")
                return "break"
            widget = getattr(widget, "master", None)

    def entry(self, parent, key, width=24):
        widget = ttk.Entry(parent, textvariable=self.variables[key], width=width)
        self.controls.append((widget, "normal"))
        self.widgets[key] = widget
        return widget

    def field(self, parent, title, key, row, combo=False):
        ttk.Label(parent, text=title).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=5)
        if key in CHOICES or combo:
            widget = ttk.Combobox(parent, textvariable=self.variables[key], values=list(CHOICES.get(key, {}).values()),
                                  state="readonly" if key in CHOICES else "normal", width=29)
            # Run before ttk's class binding, which changes the selected value.
            # The popup list has its own bindings and still scrolls normally.
            widget.bind("<MouseWheel>", lambda event: self._wheel(event) or "break")
            self.controls.append((widget, "readonly" if key in CHOICES else "normal"))
            self.widgets[key] = widget
            if key in ("target", "projection", "profile", "connection"):
                widget.bind("<<ComboboxSelected>>", self._sync_options)
        else:
            widget = self.entry(parent, key)
        widget.grid(row=row, column=1, sticky="ew", pady=5)

    def pair(self, parent, title, a, b, row):
        ttk.Label(parent, text=title).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=5)
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", pady=5)
        self.entry(frame, a, 10).pack(side="left", fill="x", expand=True)
        ttk.Label(frame, text=" / ").pack(side="left")
        self.entry(frame, b, 10).pack(side="left", fill="x", expand=True)

    def button(self, parent, text, command, **kwargs):
        widget = ttk.Button(parent, text=text, command=command, **kwargs)
        self.controls.append((widget, "normal"))
        return widget

    def check(self, parent, title, key):
        widget = ttk.Checkbutton(parent, text=title, variable=self.variables[key])
        self.controls.append((widget, "normal"))
        return widget

    def values(self):
        values = {key: variable.get() for key, variable in self.variables.items()}
        for key, options in CHOICES.items():
            values[key] = next(code for code, label in options.items() if label == values[key])
        return values

    def _sync_options(self, _event=None):
        if self.session.active:
            return
        values = self.values()
        direct = values["connection"] == "runtime"
        reuse = values["use_running_runtime"]
        for widget in (self.widgets["dll"], self.browse_dll_button, self.scan_button):
            widget.configure(state="disabled" if reuse or direct else "normal")
        self.runtime_button.configure(state="normal" if reuse or direct else "disabled")
        self.reuse_check.configure(state="disabled" if direct else "normal")
        self.widgets["profile"].configure(state="disabled" if direct else "readonly")
        self.widgets["runtime_port"].configure(state="normal" if direct else "disabled")
        for key in ("client_schema", "legacy_success_code"):
            self.widgets[key].configure(state="disabled" if direct else "readonly")
        self.diagnose_button.configure(text="检查连接" if direct else "检查 DLL")
        client_profile = values["profile"] in ("dkii", "vi1-1.1")
        self.dongle_check.configure(state="disabled" if values["simulate"] or direct else "normal")
        if direct:
            self.dongle_hint.set("直连不使用此 DLL 选项；需要虚拟钥匙时，请到「虚拟 USB Key」页启动。")
        elif values["simulate"]:
            self.dongle_hint.set("模拟数据不加载 DLL，软件狗选项本次不生效。")
        elif client_profile:
            self.dongle_hint.set("Client 模式的钥匙校验在 aGlassRuntime.exe 里；"
                                 "可到「虚拟 USB Key」页启动系统设备，本选项对它无效。")
        else:
            self.dongle_hint.set("在桥接进程内伪造钥匙，不改厂商文件、不需要管理员；对旧回调 DLL 有效。")
        selection = (direct, reuse, values["profile"])
        if selection != self.runtime_selection:
            self.runtime_selection = selection
            if reuse or direct:
                self.detect_runtime()
            else:
                self.runtime_generation += 1  # Discard a pending result after the user switches back.
                self.runtime_hint.set("勾选后自动使用运行中 Runtime 目录里的 SDK。")
        target = values["target"]
        old_port = "9015" if self.previous_target == "vrcft-module" else "9000"
        if target != self.previous_target and values["port"] == old_port:
            self.variables["port"].set("9015" if target == "vrcft-module" else "9000")
        self.previous_target = target
        self.widgets["parameter_prefix"].configure(state="normal" if target == "vrcft-avatar" else "disabled")
        self.target_hint.configure(text={
            "native": "在 VRChat 中开启 OSC，并使用已设置 Eye Look 的模型。",
            "vrcft-module": "模块 Source=bridge 时接收本机 9015；Source=runtime 直连时无需启动本桥接。",
            "vrcft-avatar": "直发 Float 眼动参数；二进制参数模型请使用 VRCFT 模块。"}[target])
        for key in ("fov_x", "fov_y"):
            self.widgets[key].configure(state="normal" if values["projection"] != "steamvr" else "disabled")
        if values["projection"] == "fov":
            self.variables["gaze_space"].set(CHOICES["gaze_space"]["viewport"])
        self.widgets["gaze_space"].configure(state="readonly" if values["projection"] != "fov" else "disabled")
        if client_profile and not direct:
            self.variables["output"].set(CHOICES["output"]["center"])
        self.widgets["output"].configure(state="disabled" if client_profile and not direct else "readonly")

    def _lock(self, running):
        for widget, state in self.controls:
            widget.configure(state="disabled" if running else state)
        self.stop_button.configure(state="normal" if running else "disabled")
        if not running:
            self._sync_options()
        self._lock_key()

    def start(self, diagnose=False):
        if self.session.active:
            return
        try:
            argv = build_arguments(self.values(), diagnose=diagnose)
            self.session.start(argv)
        except (OSError, ValueError, RuntimeError) as exc:
            self.error = str(exc)
            self.status.set("无法启动")
            self.detail.set(str(exc)[:190])
            self.log(f"错误：{exc}")
            messagebox.showerror("请检查设置", str(exc), parent=self.root)
            return
        self.diagnosing, self.error = diagnose, ""
        self.last_frame, self.lids = None, [1., 1.]
        self.lid_output_present = False
        direct = self.values()["connection"] == "runtime"
        self.status.set(("正在检查连接" if direct else "正在检查 DLL") if diagnose else "正在启动")
        self.detail.set(("只检查 Runtime TCP 连接，不初始化设备、不发送 OSC。" if direct else "检查只加载接口，不初始化设备、不发送 OSC。") if diagnose else "正在连接所选 Runtime…")
        self.packet_count.set("0")
        self.elapsed.set("00:00")
        self.source.set("模拟数据" if self.values()["simulate"] else "真实设备")
        self._lock(True)
        self.log(("开始 Runtime 连接检查。" if self.values()["connection"] == "runtime" else "开始 DLL 检查。") if diagnose else "开始桥接；可随时点击停止。")
        self._draw()

    def preview(self):
        if self.session.active:
            return
        for key in ("simulate", "dry_run"):
            self.variables[key].set(True)
        self.variables["projection"].set(CHOICES["projection"]["fov"])
        self.variables["gaze_space"].set(CHOICES["gaze_space"]["viewport"])
        self._sync_options()
        self.start()

    def stop(self):
        if not self.session.active:
            return
        self.status.set("正在停止")
        self.detail.set("先复位 OSC，再关闭本次连接；请稍候。")
        self.stop_button.configure(state="disabled")
        self.session.stop(float(self.values()["sdk_stop_timeout"]) + 3.)

    def close(self):
        self.closing = True
        self._lock_key()
        if self.session.active:
            self.stop()
        elif self.key_session.active:
            self.stop_key()
        else:
            self._destroy()

    def _destroy(self):
        # Cancel Tcl timers before destroying their registered Python commands.
        for callback in (self.tick_id, self.scan_id):
            self.root.after_cancel(callback)
        self.root.destroy()

    def _tick(self):
        self._poll_key()
        for event in self.session.poll():
            if event["type"] == "log":
                self.log(event["message"])
            elif event["type"] == "exit":
                if event["code"] == 0:
                    self.status.set("检查通过" if self.diagnosing else "已停止")
                    self.detail.set("连接/接口检查完成；设备数据仍需开始桥接确认。" if self.diagnosing else "本次会话已结束，可以调整设置后重新开始。")
                else:
                    self.status.set("已强制停止" if event["forced"] else "运行失败")
                    self.detail.set(self.error[:190] or f"进程退出码 {event['code']}，详情见日志。")
                self.last_frame, self.lids = None, [1., 1.]
                self.lid_output_present = False
                self.source.set("未运行")
                self._draw()
                self.log(f"会话结束，退出码 {event['code']}。")
                self._lock(False)
            else:
                self._status(event)
        try:
            paths, error = self.scan_queue.get_nowait()
            self.scanning = False
            self.widgets["dll"].configure(values=paths)
            self.log(error or f"找到 {len(paths)} 个 DLL。下拉列表可选择，长路径也可用浏览按钮指定。")
        except queue.Empty:
            pass
        while not self.runtime_queue.empty():
            generation, message = self.runtime_queue.get_nowait()
            if generation == self.runtime_generation:
                self.runtime_hint.set(message)
                self.log(message)
        if self.closing and not self.session.active:
            if self.key_session.active:
                self.stop_key()
            else:
                self._destroy()
                return
        self.tick_id = self.root.after(60, self._tick)

    def _status(self, event):
        phase = event.get("phase")
        if phase == "error":
            self.error = event.get("message", "未知错误")
            self.status.set("运行失败")
            self.detail.set(self.error[:190])
        elif phase == "stopping":
            if not self.error:
                self.status.set("正在停止")
                self.detail.set("正在关闭本次连接…")
        elif phase == "running":
            self.last_frame = event
            valid = any(s["valid"] and s["age"] <= event["stale_seconds"] for s in event["samples"].values())
            if self.session.stop_deadline is None:
                self.status.set("模拟预览" if event["simulate"] and event["dry_run"] else "跟踪中" if valid else "等待有效数据")
                mode = "模拟数据" if event["simulate"] else "真实设备"
                destination = "不发送 OSC" if event["dry_run"] else CHOICES["target"][event["target"]]
                self.detail.set(f"{mode}  ·  {destination}")
            self.packet_count.set(str(event["packets"]))
            elapsed = int(event["elapsed"])
            self.elapsed.set(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
            self.source.set("模拟 · 有效性估算眨眼" if event["simulate"] else "Runtime 直连 · 原始坐标" if self.values()["connection"] == "runtime" else "设备回调 · 原始坐标")
            messages = event["messages"]
            self.lid_output_present = any(address == "/tracking/eye/EyesClosedAmount" or address == "/aglass/v1/eyes"
                                          or address.endswith("/EyeLidLeft") for address in messages)
            if "/tracking/eye/EyesClosedAmount" in messages:
                self.lids = [1. - messages["/tracking/eye/EyesClosedAmount"][0]] * 2
            elif "/aglass/v1/eyes" in messages:
                values = messages["/aglass/v1/eyes"]
                self.lids = [values[3], values[6]]
            else:
                for address, values in messages.items():
                    if address.endswith("/EyeLidLeft"):
                        self.lids[0] = values[0] / .75
                    elif address.endswith("/EyeLidRight"):
                        self.lids[1] = values[0] / .75
            self._draw()

    def _draw(self):
        c = self.canvas
        c.delete("all")
        for x in (16, 77, 138, 199, 260):
            c.create_line(x, 16, x, 186, fill="#dce5ec")
        for y in (16, 58, 101, 143, 186):
            c.create_line(16, y, 260, y, fill="#dce5ec")
        c.create_line(130, 101, 146, 101, fill="#8fa3b2", width=2)
        c.create_line(138, 93, 138, 109, fill="#8fa3b2", width=2)
        labels = []
        colors = {"left": ACCENT, "right": "#8764b8", "center": ACCENT}
        names = {"left": "左眼", "right": "右眼", "center": "融合"}
        if self.last_frame:
            for eye, sample in self.last_frame["samples"].items():
                fresh = sample["age"] <= self.last_frame["stale_seconds"]
                valid = sample["valid"] and fresh
                if sample["x"] is not None and sample["y"] is not None:
                    x, y = sample["x"], sample["y"]
                    labels.append(f"{names[eye]}  {x:.3f}, {y:.3f}  ·  {'有效' if valid else '失效'}")
                    px, py = 16 + max(0, min(1, x)) * 244, 16 + max(0, min(1, y)) * 170
                    color = colors[eye] if valid else "#a7b4bf"
                    c.create_oval(px - 7, py - 7, px + 7, py + 7, fill=color if valid else "", outline=color, width=2)
                    c.create_text(px, min(188, py + 20), text=names[eye], fill=color, font=("Microsoft YaHei UI", 9))
                else:
                    labels.append(f"{names[eye]}  ·  无有效注视点")
        if not labels:
            c.create_text(138, 145, text="等待眼动数据", fill=MUTED, font=("Microsoft YaHei UI", 10))
        self.coordinates.set("\n".join(labels) or "尚未收到注视点")
        self.eye_canvas.delete("all")
        active = self.last_frame is not None and self.lid_output_present
        for index, lid in enumerate(self.lids):
            x = 65 + index * 140
            amount = max(0., min(1., lid))
            height = max(1, 12 * amount)
            color = ACCENT if active else "#9cabb5"
            self.eye_canvas.create_oval(x - 28, 21 - height, x + 28, 21 + height, outline=color, width=2)
            if amount > .3:
                self.eye_canvas.create_oval(x - 5, 16, x + 5, 26, fill=color, outline="")
        self.lid_text.set("尚无睁闭眼输出" if not active else
                          "最近输出  ·  左" + ("闭" if self.lids[0] < .5 else "睁") + " / 右" + ("闭" if self.lids[1] < .5 else "睁"))

    def detect_runtime(self):
        if self.session.active:
            return
        self.runtime_generation += 1
        generation = self.runtime_generation
        results = self.runtime_queue
        sdk = PROFILES[self.values()["profile"]][0]
        direct = self.values()["connection"] == "runtime"
        port_text = self.values()["runtime_port"]
        self.runtime_hint.set("正在检测已运行的 Runtime…")
        def detect():
            try:
                if direct:
                    port = int(port_text)
                    if not 0 <= port <= 65535:
                        raise ValueError("TCP 端口须为 0 或 1–65535")
                    host, port = runtime_endpoint(port)
                    message = f"直连端点：{host}:{port}\n不加载厂商 DLL，不创建 SDK 子进程。\n点击“检查连接”验证 TCP；开始时读取真实数据。"
                else:
                    runtime, path = running_runtime_sdk(sdk)
                    message = f"PID {runtime.pid} · {runtime.executable}\n配套 SDK：{path}\n开始桥接时将重新检测。"
            except (OSError, RuntimeError, ValueError) as exc:
                message = f"检测未通过：{exc}"
            results.put((generation, message))
        threading.Thread(target=detect, daemon=True).start()

    def scan_dlls(self):
        if self.variables["use_running_runtime"].get() or self.values()["connection"] == "runtime":
            return
        if self.scanning:
            return
        self.scanning = True
        self.log("正在扫描项目与已解压的 SDK…")
        results = self.scan_queue
        def scan():
            try:
                results.put(([str(p) for p in dll_candidates(ROOT, "auto")], ""))
            except OSError as exc:
                results.put(([], f"扫描失败：{exc}"))
        threading.Thread(target=scan, daemon=True).start()

    def browse_dll(self):
        path = filedialog.askopenfilename(parent=self.root, title="选择与 Runtime 配套的 x64 DLL", filetypes=[("aGlass DLL", "*.dll"), ("所有文件", "*.*")])
        if path:
            self.variables["dll"].set(path)

    def browse_csv(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="选择新的 CSV 日志文件", defaultextension=".csv", initialfile=time.strftime("gaze-%Y%m%d-%H%M%S.csv"), filetypes=[("CSV", "*.csv")])
        if path:
            self.variables["log"].set(path)

    def copy_command(self):
        try:
            command = powershell_command(build_arguments(self.values()))
        except ValueError as exc:
            messagebox.showerror("设置无效", str(exc), parent=self.root)
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(command)
        self.log("已复制 PowerShell 命令。")

    def save(self):
        try:
            build_arguments(self.values())
            save_settings(self.values(), self.settings_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法保存", str(exc), parent=self.root)
            return
        self.log(f"设置已保存到 {self.settings_path.name}。下次打开会恢复设置，但不会自动开始。")

    def log(self, text):
        self.log_view.configure(state="normal")
        tag = "error" if "ERROR" in text or "错误" in text else "warning" if "WARNING" in text else "key" if text.startswith("[USB Key]") else ""
        self.log_view.insert("end", text + "\n", tag)
        lines = int(self.log_view.index("end-1c").split(".")[0])
        if lines > 2000:
            self.log_view.delete("1.0", f"{lines - 2000}.0")
        self.log_view.see("end")
        self.log_view.configure(state="disabled")

    def clear_log(self):
        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", "end")
        self.log_view.configure(state="disabled")

    def export_log(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="导出运行日志", defaultextension=".txt", initialfile=time.strftime("aglass-%Y%m%d-%H%M%S.txt"), filetypes=[("文本日志", "*.txt")])
        if path:
            try:
                Path(path).write_text(self.log_view.get("1.0", "end-1c"), encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("无法导出", str(exc), parent=self.root)

    def open_readme(self):
        if os.name == "nt":
            os.startfile(ROOT / "README.md")


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
