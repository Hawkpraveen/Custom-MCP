"""Presentation of one immutable request. No transport or approval policy."""
import json
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


class ApprovalPopup:
    def __init__(self, root, pending, on_decision):
        self.pending = pending
        self.on_decision = on_decision
        self.busy = False
        self.window = tk.Toplevel(root)
        self.window.title("MCP Authorization Required")
        self.window.geometry("760x640")
        self.window.minsize(620, 480)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", lambda: self.decide(False))
        self.window.bind("<Escape>", lambda _: self.decide(False))
        outer = ttk.Frame(self.window, padding=22)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="MCP Authorization Required", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(outer, text="The request is paused. Review it before allowing execution.").pack(anchor="w", pady=(6, 15))
        message = pending["message"]
        rows = [("Server", pending["server"]), ("Client", pending["source"]),
                ("Method", message["method"]), ("Tool", message.get("params", {}).get("name", "—")),
                ("Request", pending["id"])]
        for label, value in rows:
            ttk.Label(outer, text=f"{label}: {value}", wraplength=690).pack(anchor="w", pady=2)
        ttk.Label(outer, text="Exact request JSON (untrusted content)", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(15, 6))
        text = ScrolledText(outer, height=12, wrap="none", font=("Consolas", 10), bg="#182335", fg="#edf3fc")
        text.pack(fill="both", expand=True)
        text.insert("1.0", json.dumps(message, indent=2, ensure_ascii=True))
        text.configure(state="disabled")
        self.timer = tk.StringVar()
        ttk.Label(outer, textvariable=self.timer, wraplength=690).pack(anchor="w", pady=10)
        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        self.block_button = ttk.Button(buttons, text="Block request", command=lambda: self.decide(False))
        self.block_button.pack(side="left")
        self.allow_button = ttk.Button(buttons, text="Allow this request once", command=lambda: self.decide(True))
        self.allow_button.pack(side="right")
        self.window.lift()
        self.block_button.focus_set()

    def update_timer(self, count):
        remaining = max(0, int(self.pending["deadline"] - time.time()))
        self.timer.set(f"{remaining}s remaining · {count} pending · closing this popup blocks the request")
        if remaining == 0:
            self.allow_button.state(["disabled"])

    def decide(self, allow):
        if self.busy:
            return
        self.busy = True
        self.allow_button.state(["disabled"])
        self.block_button.state(["disabled"])
        self.on_decision(self.pending, allow)

    def close(self):
        self.window.destroy()

