#!/usr/bin/env python3
"""
MedConsult Dev Panel v0.4.0
Unified: service control, SQL query tool, terminal, accounts management.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

# Fix WSL2 Docker API version automatically
os.environ.setdefault("DOCKER_API_VERSION", "1.44")

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

import urllib.request

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
VENV_PYTHON = BASE_DIR / "venv" / "bin" / "python"
GUI_VERSION = "v0.4.0"

# ── Catppuccin Mocha dark palette ─────────────────────────────────────────────
BG     = "#1e1e2e"
BG2    = "#2a2a3e"
BG3    = "#313244"
FG     = "#cdd6f4"
ACCENT = "#89b4fa"
GREEN  = "#a6e3a1"
RED    = "#f38ba8"
YELLOW = "#f9e2af"
BORDER = "#45475a"
MUTED  = "#6c7086"
MONO   = ("Courier New", 10)
UI     = ("Segoe UI", 10)

# ── DB connection config ───────────────────────────────────────────────────────
DB_CFG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "5433")),
    dbname=os.environ.get("DB_NAME", "medconsult"),
    user=os.environ.get("DB_USER", "medconsult_user"),
    password=os.environ.get("DB_PASSWORD", "medconsult_pass"),
)

# ── Quick SQL presets ─────────────────────────────────────────────────────────
QUICK_SQL = [
    ("All Users",       "SELECT id, username, email, role, is_active, is_email_verified\nFROM users ORDER BY id;"),
    ("All Tables",      "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"),
    ("Appointments",    "SELECT id, status, appointment_type, created_at\nFROM appointments ORDER BY created_at DESC LIMIT 50;"),
    ("Payments",        "SELECT id, amount, status, created_at\nFROM payments ORDER BY created_at DESC LIMIT 30;"),
    ("Active Doctors",  "SELECT u.username, d.specialization, d.verification_status\nFROM doctor_profiles d\nJOIN users u ON d.user_id=u.id\nWHERE d.verification_status='verified';"),
    ("Patient Profiles","SELECT u.username, u.email, p.date_of_birth, p.gender\nFROM patient_profiles p\nJOIN users u ON p.user_id=u.id\nORDER BY u.id;"),
    ("Messages",        "SELECT id, conversation_id, message_type, created_at\nFROM messages ORDER BY created_at DESC LIMIT 30;"),
    ("Slots",           "SELECT id, doctor_id, start_datetime, end_datetime,\n       appointment_type, is_booked, is_blocked\nFROM slots ORDER BY start_datetime DESC LIMIT 30;"),
    ("Slot Changes",    "SELECT id, slot_id, change_type, created_at\nFROM slot_change_logs ORDER BY created_at DESC LIMIT 30;"),
    ("Video Rooms",     "SELECT id, room_name, status, created_at\nFROM video_rooms ORDER BY created_at DESC;"),
    ("FAQ Entries",     "SELECT id, question, is_active, \"order\"\nFROM support_faqs ORDER BY \"order\";"),
    ("Contact Msgs",    "SELECT id, email, subject, is_resolved, created_at\nFROM support_contact_messages ORDER BY created_at DESC;"),
    ("Reviews",         "SELECT id, appointment_id, rating, created_at\nFROM reviews ORDER BY created_at DESC LIMIT 20;"),
    ("Notifications",   "SELECT id, user_id, notif_type, title, is_read, created_at\nFROM notifications ORDER BY created_at DESC LIMIT 30;"),
]

# ── Terminal command presets ───────────────────────────────────────────────────
CMD_PRESETS = [
    ("Docker PS",       "docker-compose ps"),
    ("DB Ready?",       "docker exec medconsult_postgres pg_isready -U medconsult_user -d medconsult"),
    ("Redis Ping",      "docker exec medconsult_redis redis-cli ping"),
    ("Check Migrate",   "python manage.py makemigrations --check --dry-run --settings=config.settings.dev"),
    ("Django Check",    "python manage.py check --settings=config.settings.dev"),
    ("Celery Status",   "python manage.py celery_status --settings=config.settings.dev"),
    ("Git Status",      "git status --short"),
    ("Git Log",         "git log --oneline -10"),
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_python() -> str:
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

def get_docker_cmd() -> list[str]:
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    if shutil.which("docker"):
        return ["docker", "compose"]
    raise RuntimeError("docker-compose not found in PATH")

def get_db_connection():
    return psycopg2.connect(**DB_CFG)


# ── Main App ───────────────────────────────────────────────────────────────────

class DevPanel(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"MedConsult Dev Panel {GUI_VERSION}")
        self.geometry("1380x860")
        self.minsize(1100, 680)
        self.configure(bg=BG)

        # ── Process handles ──────────────────────────────────────────────
        self.server_proc:   subprocess.Popen | None = None
        self.worker_proc:   subprocess.Popen | None = None
        self.beat_proc:     subprocess.Popen | None = None
        self.pg_log_proc:   subprocess.Popen | None = None
        self.redis_log_proc: subprocess.Popen | None = None
        self.tunnel_proc:   subprocess.Popen | None = None
        self.tunnel_url:    str = ""
        self.busy = False

        # ── Shared state ─────────────────────────────────────────────────
        self.log_queue:   queue.Queue[str] = queue.Queue()
        self.python_exe   = get_python()
        self.docker_cmd   = get_docker_cmd()
        self.source_mtime = Path(__file__).stat().st_mtime
        self.pending_reload = False

        # ── SQL state ────────────────────────────────────────────────────
        self._db_conn = None

        # ── Terminal history ─────────────────────────────────────────────
        self._cmd_history: list[str] = []
        self._history_idx = 0

        # ── Accounts window ref (kept for compat) ────────────────────────
        self.accounts_window = None
        self.accounts_tree: ttk.Treeview | None = None

        self._build_ui()
        self._configure_ttk()
        self._poll_log_queue()
        self._refresh_status()
        self._watch_source()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.log(f"Python: {self.python_exe}")
        self.log(f"Docker: {' '.join(self.docker_cmd)}")
        if not HAS_PSYCOPG2:
            self.log("WARNING: psycopg2-binary not installed — SQL tab disabled.")

    # ─────────────────────────────────────────────────────────────────────
    # UI Construction
    # ─────────────────────────────────────────────────────────────────────

    def _configure_ttk(self) -> None:
        s = ttk.Style()
        s.theme_use("clam")

        s.configure("Dark.TNotebook", background=BG, borderwidth=0, tabmargins=0)
        s.configure("Dark.TNotebook.Tab", background=BG2, foreground=MUTED,
                    padding=[16, 8], font=(UI[0], 10, "bold"), borderwidth=0)
        s.map("Dark.TNotebook.Tab",
              background=[("selected", BG3), ("active", BORDER)],
              foreground=[("selected", ACCENT), ("active", FG)])

        s.configure("SQL.Treeview", background=BG2, foreground=FG,
                    fieldbackground=BG2, rowheight=30, borderwidth=0, font=MONO)
        s.configure("SQL.Treeview.Heading", background=BORDER, foreground=ACCENT,
                    relief="flat", font=(UI[0], 10, "bold"))
        s.map("SQL.Treeview",
              background=[("selected", ACCENT)], foreground=[("selected", BG)])

        s.configure("Acct.Treeview", background=BG2, foreground=FG,
                    fieldbackground=BG2, rowheight=22, borderwidth=0, font=(UI[0], 10))
        s.configure("Acct.Treeview.Heading", background=BORDER, foreground=ACCENT,
                    relief="flat", font=(UI[0], 10, "bold"))
        s.map("Acct.Treeview",
              background=[("selected", ACCENT)], foreground=[("selected", BG)])

    def _build_ui(self) -> None:
        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)

        # ── Header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg="#10233d", pady=10)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(1, weight=1)

        tk.Label(hdr, text=f"MedConsult Dev Panel {GUI_VERSION}",
                 bg="#10233d", fg="white",
                 font=(UI[0], 14, "bold")).grid(row=0, column=0, padx=16, sticky="w")

        self._reload_lbl = tk.Label(hdr, text="", bg="#10233d", fg=YELLOW,
                                    font=(UI[0], 9))
        self._reload_lbl.grid(row=0, column=1, sticky="w", padx=8)

        tk.Button(hdr, text="Apply Update", bg=ACCENT, fg=BG,
                  font=(UI[0], 9, "bold"), relief="flat", padx=10, pady=3,
                  cursor="hand2", command=self.apply_pending_reload
                  ).grid(row=0, column=2, padx=16)

        # ── Tunnel URL bar ────────────────────────────────────────────────
        self._tunnel_bar = tk.Frame(self, bg="#0d1f0d", pady=8)
        self._tunnel_bar.grid(row=1, column=0, sticky="ew")
        self._tunnel_bar.columnconfigure(1, weight=1)

        tk.Label(self._tunnel_bar, text="🌐  Public URL:",
                 bg="#0d1f0d", fg="#4ade80",
                 font=(UI[0], 10, "bold")).grid(row=0, column=0, padx=(16, 8))

        self._tunnel_url_var = tk.StringVar(value="Not tunneled — click  Start Tunnel  to share with testers")
        self._tunnel_url_lbl = tk.Label(
            self._tunnel_bar, textvariable=self._tunnel_url_var,
            bg="#0d1f0d", fg="#6b7280",
            font=(UI[0], 10), cursor="hand2",
        )
        self._tunnel_url_lbl.grid(row=0, column=1, sticky="w")
        self._tunnel_url_lbl.bind("<Button-1>", self._copy_tunnel_url)

        self._tunnel_copy_hint = tk.Label(
            self._tunnel_bar, text="", bg="#0d1f0d", fg="#4ade80",
            font=(UI[0], 8),
        )
        self._tunnel_copy_hint.grid(row=0, column=2, padx=(4, 16))

        # ── Status strip ─────────────────────────────────────────────────
        strip = tk.Frame(self, bg=BG2, pady=6)
        strip.grid(row=2, column=0, sticky="ew")

        self._dot_vars: dict[str, tk.StringVar] = {}
        for name in ("Docker", "Server", "Worker", "Beat"):
            var = tk.StringVar(value=f"● {name}")
            self._dot_vars[name] = var
            tk.Label(strip, textvariable=var, bg=BG2, fg=MUTED,
                     font=(UI[0], 10, "bold")).pack(side="left", padx=16)

        self._tunnel_dot_var = tk.StringVar(value="● Tunnel")
        self._tunnel_dot_lbl = tk.Label(strip, textvariable=self._tunnel_dot_var,
                                        bg=BG2, fg=MUTED, font=(UI[0], 10, "bold"))
        self._tunnel_dot_lbl.pack(side="left", padx=16)

        self._busy_var = tk.StringVar(value="Idle")
        tk.Label(strip, textvariable=self._busy_var, bg=BG2, fg=MUTED,
                 font=(UI[0], 9)).pack(side="right", padx=16)

        # ── Notebook ──────────────────────────────────────────────────────
        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.grid(row=3, column=0, sticky="nsew", padx=0, pady=0)
        self._nb = nb

        ctrl_tab  = tk.Frame(nb, bg=BG)
        sql_tab   = tk.Frame(nb, bg=BG)
        term_tab  = tk.Frame(nb, bg=BG)
        acct_tab  = tk.Frame(nb, bg=BG)
        test_tab  = tk.Frame(nb, bg=BG)

        nb.add(ctrl_tab,  text="  Control  ")
        nb.add(sql_tab,   text="  SQL  ")
        nb.add(term_tab,  text="  Terminal  ")
        nb.add(acct_tab,  text="  Accounts  ")
        nb.add(test_tab,  text="  Page Health  ")

        self._build_control_tab(ctrl_tab)
        self._build_sql_tab(sql_tab)
        self._build_terminal_tab(term_tab)
        self._build_accounts_tab(acct_tab)
        self._build_tests_tab(test_tab)

    # ─────────────────────────────────────────────────────────────────────
    # Tab 1 — Control
    # ─────────────────────────────────────────────────────────────────────

    def _build_control_tab(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        # ── Service cards ─────────────────────────────────────────────────
        cards_row = tk.Frame(parent, bg=BG, pady=12)
        cards_row.grid(row=0, column=0, sticky="ew", padx=16)

        self._svc_cards: dict[str, dict] = {}
        services = [
            ("Docker", self.start_docker, self.stop_docker, lambda: self._docker_running),
            ("Server", self.start_server, self.stop_server, lambda: self._is_running("server")),
            ("Worker", self.start_celery_worker, self.stop_celery_worker, lambda: self._is_running("worker")),
            ("Beat",   self.start_celery_beat,   self.stop_celery_beat,   lambda: self._is_running("beat")),
        ]
        for i, (name, start_fn, stop_fn, _) in enumerate(services):
            card = tk.Frame(cards_row, bg=BG2, padx=20, pady=14, relief="flat")
            card.grid(row=0, column=i, padx=(0, 10), sticky="ew")
            cards_row.columnconfigure(i, weight=1)

            dot = tk.Label(card, text=f"● {name}", bg=BG2, fg=MUTED,
                           font=(UI[0], 11, "bold"))
            dot.pack(anchor="w")

            sub = tk.Label(card, text="stopped", bg=BG2, fg=MUTED,
                           font=(UI[0], 9))
            sub.pack(anchor="w", pady=(2, 8))

            btn = tk.Button(card, text=f"Start {name}", bg=ACCENT, fg=BG,
                            font=(UI[0], 10, "bold"), relief="flat",
                            padx=10, pady=4, cursor="hand2",
                            command=start_fn)
            btn.pack(fill="x")

            self._svc_cards[name] = {"dot": dot, "sub": sub, "btn": btn,
                                     "start": start_fn, "stop": stop_fn}

        # ── Action buttons ────────────────────────────────────────────────
        actions = tk.Frame(parent, bg=BG, pady=4)
        actions.grid(row=1, column=0, sticky="ew", padx=16)

        btns = [
            ("▶  Start Stack",  self.start_stack,       ACCENT,   BG),
            ("■  Stop All",     self.stop_all,           RED,      BG),
            ("Run Migrations",  self.run_migrations,     BG3,      FG),
            ("Run Checks",      self.run_checks,         BG3,      FG),
            ("DB Logs On/Off",  self.toggle_docker_logs, BG3,      FG),
            ("Refresh Status",  self._refresh_status,    BG3,      FG),
            ("🌐  Start Tunnel", self.toggle_tunnel,     "#14532d", GREEN),
        ]
        self._tunnel_btn: tk.Button | None = None
        for text, cmd, bg, fg in btns:
            b = tk.Button(actions, text=text, bg=bg, fg=fg,
                          font=(UI[0], 10, "bold" if bg not in (BG3, "#14532d") else "normal"),
                          relief="flat", padx=12, pady=5, cursor="hand2", command=cmd)
            b.pack(side="left", padx=(0, 8))
            if text.startswith("🌐"):
                self._tunnel_btn = b

        # ── Live log ──────────────────────────────────────────────────────
        log_frame = tk.Frame(parent, bg=BG)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(8, 12))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)

        log_hdr = tk.Frame(log_frame, bg=BG)
        log_hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(log_hdr, text="Live Output", bg=BG, fg=ACCENT,
                 font=(UI[0], 9, "bold")).pack(side="left")
        for text, cmd in [("Copy", self.copy_logs), ("Save", self.save_logs), ("Clear", self.clear_logs)]:
            tk.Button(log_hdr, text=text, bg=BG2, fg=FG, relief="flat",
                      font=(UI[0], 9), padx=8, pady=2, cursor="hand2", command=cmd
                      ).pack(side="right", padx=(4, 0))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, bg=BG2, fg=FG, insertbackground=FG,
            font=MONO, relief="flat", padx=10, pady=8,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew")
        self.log_text.bind("<Key>", self._block_edit)
        self.log_text.bind("<Control-c>", self._copy_selected_log)
        self.log_text.bind("<Control-C>", self._copy_selected_log)

    # ─────────────────────────────────────────────────────────────────────
    # Tab 2 — SQL
    # ─────────────────────────────────────────────────────────────────────

    def _build_sql_tab(self, parent: tk.Frame) -> None:
        if not HAS_PSYCOPG2:
            tk.Label(parent, text="psycopg2-binary not installed.\nRun: pip install psycopg2-binary",
                     bg=BG, fg=RED, font=(UI[0], 13)).pack(expand=True)
            return

        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # ── Sidebar ───────────────────────────────────────────────────────
        sidebar = tk.Frame(parent, bg=BG2, width=200)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        tk.Label(sidebar, text="Quick Queries", bg=BG2, fg=ACCENT,
                 font=(UI[0], 10, "bold"), pady=10).pack(fill="x", padx=10)

        for label, sql in QUICK_SQL:
            b = tk.Button(sidebar, text=label, bg=BG2, fg=FG, font=UI,
                          relief="flat", anchor="w", padx=12, pady=4,
                          cursor="hand2",
                          command=lambda s=sql: self._sql_load(s))
            b.pack(fill="x", padx=4, pady=1)
            b.bind("<Enter>", lambda e, w=b: w.configure(bg=BORDER))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg=BG2))

        # ── Main area ─────────────────────────────────────────────────────
        main = tk.Frame(parent, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        # Connection bar
        cbar = tk.Frame(main, bg=BG2, pady=5)
        cbar.grid(row=0, column=0, sticky="ew")
        cbar.columnconfigure(1, weight=1)

        self._sql_conn_lbl = tk.Label(cbar, text="● Disconnected", bg=BG2, fg=MUTED,
                                      font=(UI[0], 9), padx=10)
        self._sql_conn_lbl.grid(row=0, column=0)
        tk.Label(cbar,
                 text=f"{DB_CFG['user']}@{DB_CFG['host']}:{DB_CFG['port']}/{DB_CFG['dbname']}",
                 bg=BG2, fg=MUTED, font=(UI[0], 9)).grid(row=0, column=1, sticky="w")
        tk.Button(cbar, text="Connect", bg=BG2, fg=ACCENT, relief="flat",
                  font=(UI[0], 9), cursor="hand2",
                  command=self._sql_connect).grid(row=0, column=2, padx=8)

        # Vertical paned: editor top, results bottom
        vpaned = tk.PanedWindow(main, orient="vertical", bg=BORDER, sashwidth=6,
                                sashrelief="flat")
        vpaned.grid(row=1, column=0, sticky="nsew")
        self._sql_vpaned = vpaned

        # Editor
        ed_frame = tk.Frame(vpaned, bg=BG)
        vpaned.add(ed_frame, minsize=120)
        ed_frame.columnconfigure(0, weight=1)
        ed_frame.rowconfigure(0, weight=1)

        self._sql_editor = scrolledtext.ScrolledText(
            ed_frame, bg=BG2, fg=FG, insertbackground=FG,
            font=("Courier New", 11), relief="flat", padx=12, pady=10,
            undo=True, wrap="none",
        )
        self._sql_editor.grid(row=0, column=0, sticky="nsew")
        self._sql_editor.insert("1.0", "-- Write SQL here, press Ctrl+Enter or Run\nSELECT version();")
        self._sql_editor.bind("<Control-Return>", lambda e: self._sql_run())
        self._sql_editor.bind("<Control-a>", lambda e: (
            self._sql_editor.tag_add("sel", "1.0", "end"), "break")[1])

        # Toolbar
        tb = tk.Frame(ed_frame, bg=BG2, pady=4)
        tb.grid(row=1, column=0, sticky="ew")
        tk.Button(tb, text="▶  Run  (Ctrl+Enter)", bg=ACCENT, fg=BG,
                  font=(UI[0], 10, "bold"), relief="flat", padx=16, pady=4,
                  cursor="hand2", command=self._sql_run).pack(side="left", padx=8)
        tk.Button(tb, text="Clear Editor", bg=BG2, fg=FG, relief="flat",
                  font=UI, padx=10, pady=4, cursor="hand2",
                  command=lambda: self._sql_editor.delete("1.0", "end")).pack(side="left", padx=2)
        tk.Button(tb, text="Clear Results", bg=BG2, fg=FG, relief="flat",
                  font=UI, padx=10, pady=4, cursor="hand2",
                  command=self._sql_clear_results).pack(side="left", padx=2)
        self._sql_status = tk.Label(tb, text="", bg=BG2, fg=GREEN, font=(UI[0], 9))
        self._sql_status.pack(side="right", padx=12)

        # Results
        res_frame = tk.Frame(vpaned, bg=BG)
        vpaned.add(res_frame, minsize=320)
        res_frame.columnconfigure(0, weight=1)
        res_frame.rowconfigure(1, weight=1)

        tk.Label(res_frame, text="Results", bg=BG, fg=ACCENT,
                 font=(UI[0], 9, "bold"), pady=4).grid(row=0, column=0, sticky="w", padx=10)

        tree_wrap = tk.Frame(res_frame, bg=BG)
        tree_wrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        tree_wrap.columnconfigure(0, weight=1)
        tree_wrap.rowconfigure(0, weight=1)

        self._sql_tree = ttk.Treeview(tree_wrap, style="SQL.Treeview", show="headings")
        vsb = ttk.Scrollbar(tree_wrap, orient="vertical",   command=self._sql_tree.yview)
        hsb = ttk.Scrollbar(tree_wrap, orient="horizontal", command=self._sql_tree.xview)
        self._sql_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._sql_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._sql_raw = scrolledtext.ScrolledText(
            res_frame, bg=BG2, fg=FG, font=MONO,
            relief="flat", padx=10, pady=6, height=3, state="disabled",
        )
        self._sql_raw.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))
        # hide raw box until there's content
        self._sql_raw.grid_remove()

        self._sql_connect()
        # push sash down so results get most of the space
        vpaned.after(150, lambda: vpaned.sash_place(0, 0, 190))

    # ─────────────────────────────────────────────────────────────────────
    # Tab 3 — Terminal
    # ─────────────────────────────────────────────────────────────────────

    def _build_terminal_tab(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Preset buttons
        presets = tk.Frame(parent, bg=BG2, pady=8)
        presets.grid(row=0, column=0, sticky="ew", padx=0)
        tk.Label(presets, text="Presets:", bg=BG2, fg=MUTED,
                 font=(UI[0], 9)).pack(side="left", padx=(12, 6))
        for label, cmd in CMD_PRESETS:
            b = tk.Button(presets, text=label, bg=BG3, fg=FG, relief="flat",
                          font=(UI[0], 9), padx=10, pady=3, cursor="hand2",
                          command=lambda c=cmd: self._term_set_cmd(c))
            b.pack(side="left", padx=(0, 4))
            b.bind("<Enter>", lambda e, w=b: w.configure(bg=BORDER))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg=BG3))

        # Output area
        self._term_out = scrolledtext.ScrolledText(
            parent, bg=BG2, fg=FG, insertbackground=FG,
            font=MONO, relief="flat", padx=12, pady=10, state="disabled",
        )
        self._term_out.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        # Input row
        inp_row = tk.Frame(parent, bg=BG3, pady=6)
        inp_row.grid(row=2, column=0, sticky="ew")
        inp_row.columnconfigure(1, weight=1)

        tk.Label(inp_row, text="$", bg=BG3, fg=ACCENT,
                 font=("Courier New", 12, "bold")).grid(row=0, column=0, padx=(12, 6))

        self._term_input = tk.Entry(inp_row, bg=BG3, fg=FG, insertbackground=FG,
                                    font=("Courier New", 11), relief="flat",
                                    disabledbackground=BG3)
        self._term_input.grid(row=0, column=1, sticky="ew", pady=2)
        self._term_input.bind("<Return>",   lambda e: self._term_run())
        self._term_input.bind("<Up>",       self._term_history_up)
        self._term_input.bind("<Down>",     self._term_history_down)
        self._term_input.bind("<Tab>",      lambda e: "break")

        tk.Button(inp_row, text="Run", bg=ACCENT, fg=BG,
                  font=(UI[0], 10, "bold"), relief="flat",
                  padx=14, pady=3, cursor="hand2",
                  command=self._term_run).grid(row=0, column=2, padx=6)
        tk.Button(inp_row, text="Clear", bg=BG3, fg=FG,
                  font=UI, relief="flat", padx=10, pady=3, cursor="hand2",
                  command=self._term_clear).grid(row=0, column=3, padx=(0, 8))

        self._term_write("MedConsult Terminal — type a shell command and press Run or Enter.\n"
                         "↑/↓ for command history. Commands run from project root.\n\n")

    # ─────────────────────────────────────────────────────────────────────
    # Tab 4 — Accounts
    # ─────────────────────────────────────────────────────────────────────

    def _build_accounts_tab(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        # Info banner
        info = tk.Frame(parent, bg=BG2, pady=10)
        info.grid(row=0, column=0, sticky="ew", padx=0)
        tk.Label(info,
                 text="Seeded credentials:  admin@medconsult.com / admin123  ·  "
                      "doctor@test.com / testpass123  ·  patient@test.com / testpass123",
                 bg=BG2, fg=FG, font=(UI[0], 9)).pack(side="left", padx=16)

        # Action buttons
        act = tk.Frame(parent, bg=BG, pady=8)
        act.grid(row=1, column=0, sticky="ew", padx=16)
        for text, cmd in [
            ("Refresh",        self._acct_refresh),
            ("Reset Password", self._acct_reset_password),
            ("Toggle Active",  self._acct_toggle_active),
            ("Copy List",      self._acct_copy),
        ]:
            tk.Button(act, text=text, bg=BG2, fg=FG, relief="flat",
                      font=UI, padx=12, pady=4, cursor="hand2", command=cmd
                      ).pack(side="left", padx=(0, 8))

        # Accounts table
        tree_wrap = tk.Frame(parent, bg=BG)
        tree_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))
        tree_wrap.columnconfigure(0, weight=1)
        tree_wrap.rowconfigure(0, weight=1)

        cols = ("id", "role", "username", "email", "password",
                "active", "verified", "doctor_status", "joined")
        widths = (50, 80, 130, 200, 140, 60, 65, 110, 140)

        self.accounts_tree = ttk.Treeview(tree_wrap, columns=cols,
                                          show="headings", style="Acct.Treeview")
        for col, w in zip(cols, widths):
            self.accounts_tree.heading(col, text=col.replace("_", " ").title())
            self.accounts_tree.column(col, width=w, anchor="w")

        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.accounts_tree.yview)
        hsb = ttk.Scrollbar(tree_wrap, orient="horizontal", command=self.accounts_tree.xview)
        self.accounts_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.accounts_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._acct_refresh()

    # ─────────────────────────────────────────────────────────────────────
    # Logging helpers
    # ─────────────────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{ts}] {msg}\n")

    def _poll_log_queue(self) -> None:
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.insert("end", msg)
            self.log_text.see("end")
        self.after(100, self._poll_log_queue)

    def _block_edit(self, event) -> str | None:
        allowed = {"Left","Right","Up","Down","Home","End","Prior","Next",
                   "Shift_L","Shift_R","Control_L","Control_R"}
        if event.keysym in allowed:
            return None
        if (event.state & 0x4) and event.keysym.lower() == "c":
            return None
        return "break"

    def _copy_selected_log(self, _=None):
        try:
            text = self.log_text.get("sel.first", "sel.last")
        except tk.TclError:
            text = self.log_text.get("1.0", "end-1c")
        self._clipboard(text, "Log text copied.")
        return "break"

    def copy_logs(self):
        self._clipboard(self.log_text.get("1.0", "end-1c"), "Logs copied.")

    def save_logs(self):
        content = self.log_text.get("1.0", "end-1c")
        if not content.strip():
            return
        path = filedialog.asksaveasfilename(
            title="Save Logs", defaultextension=".log",
            initialfile="medconsult-dev.log",
            filetypes=[("Log files","*.log"),("Text","*.txt"),("All","*.*")])
        if path:
            try:
                Path(path).write_text(content)
                self.log(f"Logs saved to {path}")
            except OSError as e:
                self.log(f"Save failed: {e}")

    def clear_logs(self):
        self.log_text.delete("1.0", "end")

    def _clipboard(self, text: str, msg: str) -> None:
        if not text.strip():
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            self.log(msg)
        except tk.TclError as e:
            self.log(f"Clipboard error: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # Status refresh
    # ─────────────────────────────────────────────────────────────────────

    def _refresh_status(self) -> None:
        docker_up, _ = self._docker_ps()
        self._docker_running = docker_up

        states = {
            "Docker": docker_up,
            "Server": self._is_running("server"),
            "Worker": self._is_running("worker"),
            "Beat":   self._is_running("beat"),
        }
        stop_fns = {
            "Docker": self.stop_docker,
            "Server": self.stop_server,
            "Worker": self.stop_celery_worker,
            "Beat":   self.stop_celery_beat,
        }
        for name, running in states.items():
            color = GREEN if running else MUTED
            self._dot_vars[name].set(f"● {name}")
            lbl_widget = self._dot_vars[name]  # StringVar bound to strip label

            card = self._svc_cards[name]
            card["dot"].configure(fg=color)
            card["sub"].configure(text="running" if running else "stopped",
                                  fg=GREEN if running else MUTED)
            if running:
                card["btn"].configure(text=f"Stop {name}", bg=RED,
                                      command=stop_fns[name])
            else:
                card["btn"].configure(text=f"Start {name}", bg=ACCENT,
                                      command=card["start"])

            # Update strip dot color (strip labels use StringVar + configure separately)
            # We stored the Label widget reference differently — patch via after trick
            strip_fg = GREEN if running else MUTED
            # The strip labels are plain tk.Label — update via the parent strip
            for child in self.winfo_children():
                if isinstance(child, tk.Frame) and child.cget("bg") == BG2:
                    for lbl in child.winfo_children():
                        if isinstance(lbl, tk.Label):
                            try:
                                if f"● {name}" in (lbl.cget("textvariable") and
                                                   str(self.getvar(lbl.cget("textvariable"))) or ""):
                                    lbl.configure(fg=strip_fg)
                            except Exception:
                                pass

        if self.pending_reload:
            self._reload_lbl.configure(text="Code changed — click Apply Update")
        else:
            self._reload_lbl.configure(text="")

        if self.accounts_tree:
            try:
                self._acct_refresh()
            except Exception:
                pass

    def _docker_ps(self) -> tuple[bool, str]:
        try:
            r = subprocess.run(
                self.docker_cmd + ["ps", "--services", "--filter", "status=running"],
                cwd=BASE_DIR, capture_output=True, text=True, check=False,
            )
        except Exception as e:
            return False, str(e)
        if r.returncode != 0:
            return False, r.stderr.strip() or "error"
        services = [s.strip() for s in r.stdout.splitlines() if s.strip()]
        return bool(services), ", ".join(services) if services else "stopped"

    def _is_running(self, name: str) -> bool:
        p = {"server": self.server_proc, "worker": self.worker_proc,
             "beat": self.beat_proc}.get(name)
        return p is not None and p.poll() is None

    # ─────────────────────────────────────────────────────────────────────
    # Process management helpers
    # ─────────────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool, label: str = "Idle") -> None:
        self.busy = busy
        self._busy_var.set(label)

    def _run_bg(self, label: str, target) -> None:
        if self.busy:
            self.log("Another action is already running.")
            return
        def runner():
            self._set_busy(True, label)
            try:
                target()
            except Exception as e:
                self.log(f"{label} failed: {e}")
            finally:
                self._set_busy(False)
                self.after(0, self._refresh_status)
        threading.Thread(target=runner, daemon=True).start()

    def _run_cmd(self, cmd: list[str], name: str) -> int:
        self.log(f"$ {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, cwd=BASE_DIR,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        for line in proc.stdout:
            self.log(f"{name}: {line.rstrip()}")
        rc = proc.wait()
        self.log(f"{name} exited {rc}")
        return rc

    def _run_manage(self, args: list[str], name: str) -> int:
        return self._run_cmd(
            [self.python_exe, "manage.py", *args, "--settings=config.settings.dev"], name)

    def _run_snippet(self, code: str) -> tuple[int, str]:
        env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.dev"}
        r = subprocess.run([self.python_exe, "-c", code],
                           cwd=BASE_DIR, capture_output=True, text=True, env=env)
        return r.returncode, (r.stdout.strip() or r.stderr.strip())

    def _stream_proc(self, proc: subprocess.Popen, prefix: str, attr: str) -> None:
        if not proc or not proc.stdout:
            return
        for line in proc.stdout:
            self.log(f"{prefix}: {line.rstrip()}")
        rc = proc.wait()
        self.log(f"{prefix} exited {rc}")
        setattr(self, attr, None)
        self.after(0, self._refresh_status)

    def _kill(self, proc: subprocess.Popen | None, label: str) -> None:
        if not proc:
            return
        self.log(f"Stopping {label}…")
        try:
            if os.name != "nt":
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else:
                proc.terminate()
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # Service actions
    # ─────────────────────────────────────────────────────────────────────

    def start_docker(self):
        self._run_bg("Starting Docker",
                     lambda: self._run_cmd(self.docker_cmd + ["up", "-d"], "docker"))

    def stop_docker(self):
        def target():
            self.stop_docker_logs()
            self._run_cmd(self.docker_cmd + ["down"], "docker")
        self._run_bg("Stopping Docker", target)

    def _launch(self, attr: str, cmd: list[str], label: str) -> None:
        if self._is_running({"server_proc":"server","worker_proc":"worker","beat_proc":"beat"}.get(attr, "")):
            self.log(f"{label} already running.")
            return
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen(cmd, cwd=BASE_DIR,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, env=env,
                                preexec_fn=os.setsid if os.name != "nt" else None)
        setattr(self, attr, proc)
        short = attr.replace("_proc","").replace("_","-")
        threading.Thread(target=self._stream_proc,
                         args=(proc, short, attr), daemon=True).start()
        self.after(200, self._refresh_status)

    def start_server(self):
        if self._is_running("server"):
            self.log("Server already running.")
            return
        self._launch("server_proc",
                     [self.python_exe, "manage.py", "runserver",
                      "--settings=config.settings.dev"],
                     "Server")

    def stop_server(self):
        self._kill(self.server_proc, "server")
        self.server_proc = None
        self._refresh_status()

    def start_celery_worker(self):
        if self._is_running("worker"):
            self.log("Worker already running.")
            return
        self._launch("worker_proc",
                     [self.python_exe, "-m", "celery", "-A", "config", "worker", "-l", "info"],
                     "Worker")

    def stop_celery_worker(self):
        self._kill(self.worker_proc, "worker")
        self.worker_proc = None
        self._refresh_status()

    def start_celery_beat(self):
        if self._is_running("beat"):
            self.log("Beat already running.")
            return
        self._launch("beat_proc",
                     [self.python_exe, "-m", "celery", "-A", "config", "beat", "-l", "info"],
                     "Beat")

    def stop_celery_beat(self):
        self._kill(self.beat_proc, "beat")
        self.beat_proc = None
        self._refresh_status()

    def start_stack(self):
        def target():
            if self._run_cmd(self.docker_cmd + ["up", "-d"], "docker") != 0:
                return
            time.sleep(1)
            self.after(0, self.start_server)
            time.sleep(0.5)
            self.after(0, self.start_celery_worker)
            time.sleep(0.5)
            self.after(0, self.start_celery_beat)
        self._run_bg("Starting Stack", target)

    def stop_all(self):
        def target():
            self.after(0, self.stop_tunnel)
            self.stop_celery_beat()
            time.sleep(0.3)
            self.stop_celery_worker()
            time.sleep(0.3)
            self.stop_server()
            time.sleep(0.3)
            self.stop_docker_logs()
            self._run_cmd(self.docker_cmd + ["down"], "docker")
            self.log("Full stack stopped.")
        self._run_bg("Stopping All", target)

    def toggle_tunnel(self):
        if self.tunnel_proc and self.tunnel_proc.poll() is None:
            self.stop_tunnel()
        else:
            self.start_tunnel()

    def start_tunnel(self):
        if self.tunnel_proc and self.tunnel_proc.poll() is None:
            self.log("Tunnel already running.")
            return
        if not shutil.which("ngrok"):
            self.log("ngrok not found. Install from https://ngrok.com/download and add to PATH.")
            messagebox.showwarning(
                "ngrok not found",
                "ngrok is not installed or not in PATH.\n\n"
                "Install it from https://ngrok.com/download\n"
                "then run: ngrok config add-authtoken YOUR_TOKEN"
            )
            return
        self.log("Starting ngrok tunnel on port 8000…")
        self._update_tunnel_bar("", running=False, starting=True)
        try:
            self.tunnel_proc = subprocess.Popen(
                ["ngrok", "http", "8000", "--log=stdout", "--log-format=json"],
                cwd=BASE_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                preexec_fn=os.setsid if os.name != "nt" else None,
            )
        except Exception as e:
            self.log(f"Failed to start ngrok: {e}")
            return
        threading.Thread(target=self._poll_tunnel_api, daemon=True).start()
        threading.Thread(target=self._stream_proc,
                         args=(self.tunnel_proc, "ngrok", "tunnel_proc"), daemon=True).start()

    def stop_tunnel(self):
        self._kill(self.tunnel_proc, "ngrok")
        self.tunnel_proc = None
        self.tunnel_url = ""
        self._update_tunnel_bar("", running=False)
        self.log("Tunnel stopped.")

    def _poll_tunnel_api(self):
        """Poll ngrok local API until public URL is available."""
        deadline = time.time() + 20
        while time.time() < deadline:
            if not self.tunnel_proc or self.tunnel_proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen("http://localhost:4040/api/tunnels", timeout=2) as r:
                    data = json.loads(r.read())
                tunnels = data.get("tunnels", [])
                https = next((t for t in tunnels if t.get("proto") == "https"), None)
                url = (https or (tunnels[0] if tunnels else None) or {}).get("public_url", "")
                if url:
                    self.tunnel_url = url
                    self.after(0, self._update_tunnel_bar, url, True)
                    self.log(f"Tunnel active: {url}")
                    return
            except Exception:
                pass
            time.sleep(1)
        self.after(0, self._update_tunnel_bar, "", False)
        self.log("ngrok tunnel URL not detected after 20s — check ngrok is authenticated.")

    def _update_tunnel_bar(self, url: str, running: bool, starting: bool = False):
        if running and url:
            self._tunnel_url_var.set(url + "   ← click to copy")
            self._tunnel_url_lbl.configure(fg="#4ade80",
                                           font=(UI[0], 12, "bold"))
            self._tunnel_bar.configure(bg="#052e16")
            for w in self._tunnel_bar.winfo_children():
                try:
                    w.configure(bg="#052e16")
                except Exception:
                    pass
            self._tunnel_dot_var.set("● Tunnel")
            self._tunnel_dot_lbl.configure(fg=GREEN)
            if self._tunnel_btn:
                self._tunnel_btn.configure(text="■  Stop Tunnel", bg="#7f1d1d", fg=RED)
        elif starting:
            self._tunnel_url_var.set("Starting tunnel…")
            self._tunnel_url_lbl.configure(fg=YELLOW, font=(UI[0], 10))
            self._tunnel_dot_var.set("● Tunnel")
            self._tunnel_dot_lbl.configure(fg=YELLOW)
        else:
            self._tunnel_url_var.set("Not tunneled — click  Start Tunnel  to share with testers")
            self._tunnel_url_lbl.configure(fg="#6b7280", font=(UI[0], 10))
            self._tunnel_bar.configure(bg="#0d1f0d")
            for w in self._tunnel_bar.winfo_children():
                try:
                    w.configure(bg="#0d1f0d")
                except Exception:
                    pass
            self._tunnel_dot_var.set("● Tunnel")
            self._tunnel_dot_lbl.configure(fg=MUTED)
            if self._tunnel_btn:
                self._tunnel_btn.configure(text="🌐  Start Tunnel", bg="#14532d", fg=GREEN)

    def _copy_tunnel_url(self, _event=None):
        if self.tunnel_url:
            self.clipboard_clear()
            self.clipboard_append(self.tunnel_url)
            self._tunnel_copy_hint.configure(text="✓ Copied!")
            self.after(2000, lambda: self._tunnel_copy_hint.configure(text=""))
        else:
            self.log("No active tunnel URL to copy.")

    def run_migrations(self):
        def _check_and_migrate():
            # Quick TCP probe — fail fast if PostgreSQL unreachable
            import socket
            host = DB_CFG["host"]
            port = DB_CFG["port"]
            try:
                with socket.create_connection((host, port), timeout=3):
                    pass
            except OSError:
                self.log(
                    f"migrate: ERROR — PostgreSQL not reachable at {host}:{port}.\n"
                    "migrate: Start Docker first (Start Stack or Start Docker), then run migrations."
                )
                return
            self._run_manage(["migrate"], "migrate")
        self._run_bg("Migrations", _check_and_migrate)

    def run_checks(self):
        self._run_bg("Checks", lambda: self._run_manage(["check"], "check"))

    def toggle_docker_logs(self):
        if self._log_running():
            self.stop_docker_logs()
        else:
            self.start_docker_logs()

    def start_docker_logs(self):
        for svc, attr in [("postgres", "pg_log_proc"), ("redis", "redis_log_proc")]:
            proc = getattr(self, attr)
            if proc and proc.poll() is None:
                continue
            p = subprocess.Popen(
                self.docker_cmd + ["logs", "-f", svc],
                cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            setattr(self, attr, p)
            threading.Thread(target=self._stream_proc,
                             args=(p, svc, attr), daemon=True).start()

    def stop_docker_logs(self):
        for proc, attr in [(self.pg_log_proc, "pg_log_proc"),
                           (self.redis_log_proc, "redis_log_proc")]:
            self._kill(proc, attr.replace("_proc",""))
            setattr(self, attr, None)

    def _log_running(self) -> bool:
        return ((self.pg_log_proc and self.pg_log_proc.poll() is None) or
                (self.redis_log_proc and self.redis_log_proc.poll() is None))

    # ─────────────────────────────────────────────────────────────────────
    # SQL tab methods
    # ─────────────────────────────────────────────────────────────────────

    def _sql_connect(self) -> None:
        if not HAS_PSYCOPG2:
            return
        try:
            if self._db_conn and not self._db_conn.closed:
                self._db_conn.close()
            self._db_conn = get_db_connection()
            self._sql_conn_lbl.configure(text="● Connected", fg=GREEN)
        except Exception as e:
            self._db_conn = None
            self._sql_conn_lbl.configure(text="● Disconnected", fg=RED)
            self._sql_show_raw(f"Connection failed:\n{e}", error=True)

    def _sql_load(self, sql: str) -> None:
        self._sql_editor.delete("1.0", "end")
        self._sql_editor.insert("1.0", sql)
        self._sql_editor.focus_set()

    def _sql_run(self) -> None:
        if not HAS_PSYCOPG2:
            return
        sql = self._sql_editor.get("1.0", "end").strip()
        if not sql:
            return
        if not self._db_conn or self._db_conn.closed:
            self._sql_connect()
            if not self._db_conn:
                return
        self._sql_status.configure(text="Running…", fg=FG)
        threading.Thread(target=self._sql_execute, args=(sql,), daemon=True).start()

    def _sql_execute(self, sql: str) -> None:
        try:
            with self._db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                if cur.description:
                    rows = cur.fetchall()
                    cols = [d.name for d in cur.description]
                    self.after(0, self._sql_display_table, cols, rows)
                    self.after(0, self._sql_status.configure,
                               {"text": f"{len(rows)} row(s)", "fg": GREEN})
                else:
                    n = cur.rowcount
                    self._db_conn.commit()
                    self.after(0, self._sql_show_raw, f"OK — {n} row(s) affected.")
                    self.after(0, self._sql_status.configure,
                               {"text": f"{n} row(s) affected", "fg": GREEN})
        except Exception as e:
            try:
                self._db_conn.rollback()
            except Exception:
                pass
            self.after(0, self._sql_show_raw, str(e), True)
            self.after(0, self._sql_status.configure, {"text": "Error", "fg": RED})

    def _sql_display_table(self, cols, rows) -> None:
        self._sql_clear_results()
        self._sql_tree["columns"] = cols
        # auto-size columns from header + first 50 data rows
        sample = rows[:50]
        for col in cols:
            max_len = len(str(col))
            for row in sample:
                val = row.get(col, "")
                max_len = max(max_len, len(str(val) if val is not None else "NULL"))
            col_w = min(max(80, max_len * 9), 400)
            self._sql_tree.heading(col, text=col)
            self._sql_tree.column(col, width=col_w, minwidth=60, stretch=True)
        for row in rows:
            self._sql_tree.insert("", "end",
                values=[str(v) if v is not None else "NULL" for v in row.values()])
        self._sql_raw.grid_remove()

    def _sql_show_raw(self, text: str, error: bool = False) -> None:
        self._sql_raw.configure(state="normal")
        self._sql_raw.delete("1.0", "end")
        self._sql_raw.configure(fg=RED if error else GREEN)
        self._sql_raw.insert("1.0", text)
        self._sql_raw.configure(state="disabled")
        self._sql_raw.grid()  # show the raw box

    def _sql_clear_results(self) -> None:
        self._sql_tree.delete(*self._sql_tree.get_children())
        self._sql_tree["columns"] = []
        self._sql_raw.configure(state="normal")
        self._sql_raw.delete("1.0", "end")
        self._sql_raw.configure(state="disabled")
        self._sql_raw.grid_remove()

    # ─────────────────────────────────────────────────────────────────────
    # Terminal tab methods
    # ─────────────────────────────────────────────────────────────────────

    def _term_write(self, text: str, color: str | None = None) -> None:
        self._term_out.configure(state="normal")
        if color:
            tag = f"c_{color.replace('#','')}"
            self._term_out.tag_configure(tag, foreground=color)
            self._term_out.insert("end", text, tag)
        else:
            self._term_out.insert("end", text)
        self._term_out.see("end")
        self._term_out.configure(state="disabled")

    def _term_set_cmd(self, cmd: str) -> None:
        self._term_input.delete(0, "end")
        self._term_input.insert(0, cmd)
        self._term_input.focus_set()

    def _term_run(self) -> None:
        cmd = self._term_input.get().strip()
        if not cmd:
            return
        self._cmd_history.append(cmd)
        self._history_idx = len(self._cmd_history)
        self._term_input.delete(0, "end")
        self._term_write(f"$ {cmd}\n", ACCENT)
        threading.Thread(target=self._term_exec, args=(cmd,), daemon=True).start()

    def _term_exec(self, cmd: str) -> None:
        env = {**os.environ,
               "DOCKER_API_VERSION": "1.44",
               "DJANGO_SETTINGS_MODULE": "config.settings.dev",
               "PYTHONUNBUFFERED": "1"}
        try:
            proc = subprocess.Popen(
                cmd, shell=True, cwd=BASE_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env,
            )
            for line in proc.stdout:
                self.after(0, self._term_write, line)
            rc = proc.wait()
            color = GREEN if rc == 0 else RED
            self.after(0, self._term_write, f"[exit {rc}]\n\n", color)
        except Exception as e:
            self.after(0, self._term_write, f"Error: {e}\n\n", RED)

    def _term_clear(self) -> None:
        self._term_out.configure(state="normal")
        self._term_out.delete("1.0", "end")
        self._term_out.configure(state="disabled")

    def _term_history_up(self, _) -> str:
        if not self._cmd_history:
            return "break"
        self._history_idx = max(0, self._history_idx - 1)
        self._term_input.delete(0, "end")
        self._term_input.insert(0, self._cmd_history[self._history_idx])
        return "break"

    def _term_history_down(self, _) -> str:
        if self._history_idx >= len(self._cmd_history) - 1:
            self._history_idx = len(self._cmd_history)
            self._term_input.delete(0, "end")
            return "break"
        self._history_idx += 1
        self._term_input.delete(0, "end")
        self._term_input.insert(0, self._cmd_history[self._history_idx])
        return "break"

    # ─────────────────────────────────────────────────────────────────────
    # Accounts tab methods
    # ─────────────────────────────────────────────────────────────────────

    # Known plaintext passwords for seeded dev accounts
    KNOWN_PASSWORDS: dict[str, str] = {
        "admin":       "admin123",
        "testdoctor":  "testpass123",
        "testpatient": "testpass123",
    }

    def _acct_refresh(self) -> None:
        if not self.accounts_tree:
            return
        code = """
import json, os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from apps.accounts.models import User
rows = []
for u in User.objects.select_related('doctor_profile').order_by('id'):
    dp = getattr(u, 'doctor_profile', None)
    rows.append({
        'id': u.id, 'role': u.role, 'username': u.username, 'email': u.email,
        'password_hash': u.password or '',
        'active': 'yes' if u.is_active else 'no',
        'verified': 'yes' if getattr(u,'is_email_verified',False) else 'no',
        'doctor_status': dp.verification_status if dp else '',
        'joined': u.date_joined.strftime('%Y-%m-%d %H:%M'),
    })
print(json.dumps(rows))
"""
        rc, out = self._run_snippet(code)
        if rc != 0:
            return
        try:
            rows = json.loads(out) if out else []
        except json.JSONDecodeError:
            return
        self.accounts_tree.delete(*self.accounts_tree.get_children())
        for r in rows:
            uname = r["username"]
            if uname in self.KNOWN_PASSWORDS:
                pw_display = self.KNOWN_PASSWORDS[uname]
            elif r["password_hash"].startswith("!"):
                pw_display = "(unusable)"
            elif r["password_hash"]:
                # Show algo + first 8 chars of hash so it's identifiable
                parts = r["password_hash"].split("$")
                algo = parts[0] if parts else "?"
                pw_display = f"[{algo}] (custom)"
            else:
                pw_display = "(none)"
            self.accounts_tree.insert("", "end", values=(
                r["id"], r["role"], uname, r["email"], pw_display,
                r["active"], r["verified"], r["doctor_status"], r["joined"],
            ))

    def _acct_reset_password(self) -> None:
        sel = self.accounts_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select a user first.")
            return
        vals = self.accounts_tree.item(sel[0], "values")
        uid, uname = int(vals[0]), vals[2]
        pw = simpledialog.askstring("Reset Password",
                                    f"New password for {uname}:", show="*")
        if not pw:
            return
        code = f"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from apps.accounts.models import User
u = User.objects.get(id={uid})
u.set_password({pw!r})
u.save(update_fields=['password'])
print('ok')
"""
        rc, out = self._run_snippet(code)
        if rc == 0:
            self.KNOWN_PASSWORDS[uname] = pw
            messagebox.showinfo("Done", f"Password updated for {uname}.")
            self._acct_refresh()
        else:
            messagebox.showerror("Failed", out or "Unknown error")

    def _acct_toggle_active(self) -> None:
        sel = self.accounts_tree.selection()
        if not sel:
            messagebox.showwarning("No selection", "Select a user first.")
            return
        vals = self.accounts_tree.item(sel[0], "values")
        uid, uname, currently = int(vals[0]), vals[2], vals[5]
        new_val = "False" if currently == "yes" else "True"
        code = f"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from apps.accounts.models import User
u = User.objects.get(id={uid})
u.is_active = {new_val}
u.save(update_fields=['is_active'])
print('ok')
"""
        rc, out = self._run_snippet(code)
        if rc == 0:
            self._acct_refresh()
        else:
            messagebox.showerror("Failed", out)

    def _acct_copy(self) -> None:
        lines = [
            "Seeded: admin@medconsult.com/admin123, doctor@test.com/testpass123, patient@test.com/testpass123", "",
        ]
        for iid in self.accounts_tree.get_children():
            lines.append(" | ".join(str(v) for v in self.accounts_tree.item(iid, "values")))
        self._clipboard("\n".join(lines), "Accounts copied.")

    # ─────────────────────────────────────────────────────────────────────
    # Tab 5 — Page Health
    # ─────────────────────────────────────────────────────────────────────

    _HEALTH_SCRIPT = '''
import os, json, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django
django.setup()

from apps.accounts import middleware as _mw
_mw.EnforceTwoFactorMiddleware.__call__ = lambda self, req: self.get_response(req)

from django.test import Client
from apps.accounts.models import User

PAGES = {
    "admin": [
        ("Dashboard",       "/app/"),
        ("Admin Panel",     "/internal/"),
        ("Users",           "/internal/users/"),
        ("Doctors",         "/internal/doctors/"),
        ("Appointments",    "/internal/appointments/"),
        ("Financial",       "/internal/financial/"),
        ("Audit Logs",      "/internal/audit/"),
        ("Verifications",   "/internal/verify/"),
        ("Knowledge Graph", "/internal/knowledge-graph/"),
        ("Settings",        "/auth/settings/"),
        ("Profile",         "/auth/profile/"),
        ("Notifications",   "/auth/notifications/"),
        ("FAQ",             "/support/faq/"),
        ("Contact",         "/support/contact/"),
        ("Messages",        "/messages/"),
    ],
    "doctor": [
        ("Dashboard",       "/app/"),
        ("Schedule",        "/doctor/schedule/"),
        ("Availability",    "/doctor/availability/"),
        ("Time Off",        "/doctor/availability/time-off/"),
        ("Analytics",       "/doctor/analytics/"),
        ("Messages",        "/messages/"),
        ("Settings",        "/auth/settings/"),
        ("Profile",         "/auth/profile/"),
        ("FAQ",             "/support/faq/"),
        ("Notifications",   "/auth/notifications/"),
    ],
    "patient": [
        ("Dashboard",       "/app/"),
        ("Find Doctors",    "/patient/doctors/"),
        ("Appointments",    "/patient/appointments/"),
        ("Health Records",  "/patient/health-records/"),
        ("Messages",        "/messages/"),
        ("Settings",        "/auth/settings/"),
        ("Profile",         "/auth/profile/"),
        ("FAQ",             "/support/faq/"),
        ("Contact",         "/support/contact/"),
        ("Notifications",   "/auth/notifications/"),
    ],
}

USER_MAP = {"admin": "admin", "doctor": "testdoctor", "patient": "testpatient"}

results = []
for role, pages in PAGES.items():
    uname = USER_MAP[role]
    try:
        user = User.objects.get(username=uname)
    except User.DoesNotExist:
        for name, url in pages:
            results.append({"role": role, "name": name, "url": url,
                             "status": "SKIP", "note": f"user {uname!r} not found"})
        continue

    c = Client()
    c.force_login(user)

    for name, url in pages:
        try:
            resp = c.get(url, follow=True)
            status = resp.status_code
            chain = [r[0] for r in resp.redirect_chain]
            note = ""
            if any("login" in u or "two_factor" in u or "/account/" in u for u in chain):
                note = "auth redirect"
            results.append({"role": role, "name": name, "url": url,
                             "status": status, "note": note})
        except Exception as e:
            results.append({"role": role, "name": name, "url": url,
                             "status": "ERR", "note": str(e)[:120]})

print(json.dumps(results))
'''

    def _build_tests_tab(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Toolbar
        bar = tk.Frame(parent, bg=BG2, pady=8)
        bar.grid(row=0, column=0, sticky="ew")

        self._health_run_btn = tk.Button(
            bar, text="▶  Run All Tests", bg=ACCENT, fg=BG,
            font=(UI[0], 10, "bold"), relief="flat", padx=16, pady=5,
            cursor="hand2", command=self._run_page_health,
        )
        self._health_run_btn.pack(side="left", padx=(12, 8))

        tk.Button(bar, text="Clear", bg=BG3, fg=FG,
                  font=UI, relief="flat", padx=12, pady=5, cursor="hand2",
                  command=self._health_clear).pack(side="left", padx=(0, 8))

        self._health_status = tk.Label(bar, text="Press 'Run All Tests' to scan every page for 500 errors.",
                                       bg=BG2, fg=MUTED, font=(UI[0], 9))
        self._health_status.pack(side="left", padx=12)

        self._health_summary = tk.Label(bar, text="", bg=BG2, fg=FG, font=(UI[0], 9, "bold"))
        self._health_summary.pack(side="right", padx=16)

        # Results tree
        tree_wrap = tk.Frame(parent, bg=BG)
        tree_wrap.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        tree_wrap.columnconfigure(0, weight=1)
        tree_wrap.rowconfigure(0, weight=1)

        cols = ("role", "page", "url", "status", "note")
        widths = (80, 160, 300, 70, 360)
        self._health_tree = ttk.Treeview(tree_wrap, columns=cols,
                                          show="headings", style="SQL.Treeview")
        for col, w in zip(cols, widths):
            self._health_tree.heading(col, text=col.title())
            self._health_tree.column(col, width=w, minwidth=40, anchor="w")

        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self._health_tree.yview)
        hsb = ttk.Scrollbar(tree_wrap, orient="horizontal", command=self._health_tree.xview)
        self._health_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._health_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._health_tree.tag_configure("ok",    foreground=GREEN)
        self._health_tree.tag_configure("warn",  foreground=YELLOW)
        self._health_tree.tag_configure("error", foreground=RED)
        self._health_tree.tag_configure("skip",  foreground=MUTED)

    def _health_clear(self) -> None:
        self._health_tree.delete(*self._health_tree.get_children())
        self._health_status.configure(text="Press 'Run All Tests' to scan every page for 500 errors.")
        self._health_summary.configure(text="")

    def _run_page_health(self) -> None:
        self._health_tree.delete(*self._health_tree.get_children())
        self._health_status.configure(text="Running…", fg=YELLOW)
        self._health_summary.configure(text="")
        self._health_run_btn.configure(state="disabled")

        def worker():
            env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.dev"}
            r = subprocess.run(
                [self.python_exe, "-c", self._HEALTH_SCRIPT],
                cwd=BASE_DIR, capture_output=True, text=True, env=env,
            )
            if r.returncode != 0:
                err = (r.stderr or r.stdout or "unknown error").strip()
                self.after(0, self._health_status.configure,
                           {"text": f"Script failed: {err[:120]}", "fg": RED})
                self.after(0, self._health_run_btn.configure, {"state": "normal"})
                return
            try:
                results = json.loads(r.stdout.strip())
            except Exception as e:
                self.after(0, self._health_status.configure,
                           {"text": f"Parse error: {e}", "fg": RED})
                self.after(0, self._health_run_btn.configure, {"state": "normal"})
                return
            self.after(0, self._health_display, results)

        threading.Thread(target=worker, daemon=True).start()

    def _health_display(self, results: list) -> None:
        self._health_tree.delete(*self._health_tree.get_children())
        ok = warn = errors = 0
        for r in results:
            status = str(r.get("status", "?"))
            note = r.get("note", "")
            if status == "200":
                tag = "ok"; ok += 1
            elif status in ("404", "403"):
                tag = "warn"; warn += 1
            elif status == "SKIP":
                tag = "skip"
            elif status == "ERR" or status.startswith("5"):
                tag = "error"; errors += 1
            elif note == "auth redirect":
                tag = "warn"; warn += 1
            else:
                tag = "ok" if status == "200" else "warn"
                if status not in ("200",):
                    warn += 1
                else:
                    ok += 1
            self._health_tree.insert("", "end",
                values=(r["role"], r["name"], r["url"], status, note),
                tags=(tag,))

        total = len(results)
        if errors:
            self._health_status.configure(text=f"Done — {errors} error(s) found!", fg=RED)
            self._health_summary.configure(
                text=f"✓ {ok} OK  ⚠ {warn} warn  ✗ {errors} error", fg=RED)
        else:
            self._health_status.configure(text=f"All {total} pages checked — no 500 errors.", fg=GREEN)
            self._health_summary.configure(
                text=f"✓ {ok} OK  ⚠ {warn} warn  ✗ 0 errors", fg=GREEN)
        self._health_run_btn.configure(state="normal")

    # ─────────────────────────────────────────────────────────────────────
    # Source file hot-reload watcher
    # ─────────────────────────────────────────────────────────────────────

    def _watch_source(self) -> None:
        try:
            mtime = Path(__file__).stat().st_mtime
        except OSError:
            self.after(2000, self._watch_source)
            return
        if mtime != self.source_mtime:
            self.source_mtime = mtime
            self.log("dev_gui.py changed.")
            if self._has_procs():
                self.pending_reload = True
                self._reload_lbl.configure(text="Code changed — click Apply Update")
            else:
                self._do_reload()
        elif self.pending_reload and not self._has_procs():
            self._do_reload()
        self.after(2000, self._watch_source)

    def _has_procs(self) -> bool:
        tunnel_running = self.tunnel_proc and self.tunnel_proc.poll() is None
        return any([self._is_running("server"), self._is_running("worker"),
                    self._is_running("beat"), self._log_running(), tunnel_running])

    def _do_reload(self) -> None:
        self.pending_reload = False
        self.log("Reloading…")
        self.update_idletasks()
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])

    def apply_pending_reload(self) -> None:
        if self._has_procs():
            self.pending_reload = True
            return
        self._do_reload()

    # ─────────────────────────────────────────────────────────────────────
    # Close
    # ─────────────────────────────────────────────────────────────────────

    def on_close(self) -> None:
        if self._has_procs():
            if not messagebox.askyesno("Stop processes?",
                                       "Managed processes are still running. Stop and quit?"):
                return
            self.stop_docker_logs()
            self.stop_celery_beat()
            self.stop_celery_worker()
            self.stop_server()
        if self.tunnel_proc and self.tunnel_proc.poll() is None:
            self._kill(self.tunnel_proc, "ngrok")
            self.tunnel_proc = None
        if self._db_conn and not self._db_conn.closed:
            self._db_conn.close()
        self.destroy()


# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = DevPanel()
    app.mainloop()
