"""Application lifecycle and queue presentation; Tk stays on the main thread."""
import queue
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk

from .connection import ApprovalConnection
from .popup import ApprovalPopup


class ApprovalApp:
    def __init__(self, config):
        self.connection = ApprovalConnection(config)
        self.pending = []
        self.popup = None
        self.root = tk.Tk()
        self.root.title("MCP Guardian — Approval service")
        self.root.geometry("580x195")
        self.root.minsize(480, 180)
        self.root.configure(bg="#101827")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#101827")
        style.configure("TLabel", background="#101827", foreground="#e5edf7", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="MCP GUARDIAN", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="Connecting to approval gateway…")
        ttk.Label(frame, textvariable=self.status, wraplength=530).pack(anchor="w", pady=10)
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Button(row, text="Hide status", command=self.root.withdraw).pack(side="left")
        ttk.Button(row, text="Quit and block pending", command=self.close).pack(side="right")
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)
        self.connection.start()
        if os.environ.get("GUARDIAN_LAUNCH_ID"):
            def follow_parent():
                sys.stdin.buffer.read()
                self.connection.events.put(("shutdown", None))
            threading.Thread(target=follow_parent, daemon=True).start()
        self.root.after(100, self.tick)

    def dismiss(self):
        if self.popup:
            self.popup.close()
        self.popup = None

    def handle_event(self, kind, value):
        if kind == "shutdown":
            self.close()
            return
        if kind == "snapshot":
            self.pending = value
            self.status.set(f"Connected · {len(value)} request(s) awaiting approval · runs while hidden")
            if self.popup and self.popup.pending["id"] not in {p["id"] for p in value}:
                self.dismiss()
            if self.popup is None and value:
                self.popup = ApprovalPopup(self.root, value[0], self.connection.decide)
        elif kind == "offline":
            self.pending = []
            self.status.set("Disconnected · requests fail closed · reconnecting…")
            self.dismiss()
            self.root.deiconify()
        elif kind in {"decided", "decision_failed"}:
            if self.popup and self.popup.pending["id"] == value:
                self.dismiss()

    def tick(self):
        while True:
            try:
                event = self.connection.events.get_nowait()
            except queue.Empty:
                break
            self.handle_event(*event)
        if self.popup:
            self.popup.update_timer(len(self.pending))
        self.root.after(100, self.tick)

    def close(self):
        self.connection.close()
        self.root.after(250, self.root.destroy)

    def run(self):
        self.root.mainloop()

