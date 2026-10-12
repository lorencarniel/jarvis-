import tkinter as tk
import threading
import json
import urllib.request
import time
import os
import sys

API = "http://localhost:8080/api"

class JarvisWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("JARVIS")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.92)
        self.root.configure(bg='#0a0a1a')

        self.width = 320
        self.height = 52
        self.expanded_height = 220
        self.expanded = False

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - self.width - 20
        y = screen_h - self.height - 60
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

        self._drag_x = 0
        self._drag_y = 0

        self._build_ui()
        self._bind_drag()
        self._update_clock()

    def _build_ui(self):
        self.main_frame = tk.Frame(self.root, bg='#0a0a1a', highlightbackground='#ff9500',
                                    highlightthickness=1, highlightcolor='#ff9500')
        self.main_frame.pack(fill='both', expand=True)

        # Header bar (always visible)
        self.header = tk.Frame(self.main_frame, bg='#111122', height=52)
        self.header.pack(fill='x')
        self.header.pack_propagate(False)

        self.dot = tk.Canvas(self.header, width=10, height=10, bg='#111122', highlightthickness=0)
        self.dot.pack(side='left', padx=(10, 4), pady=0)
        self.dot.create_oval(2, 2, 10, 10, fill='#00ff88', outline='')

        self.title_label = tk.Label(self.header, text="JARVIS", fg='#ff9500', bg='#111122',
                                     font=('Consolas', 10, 'bold'))
        self.title_label.pack(side='left', padx=(0, 5))

        self.clock_label = tk.Label(self.header, text="--:--", fg='#666688', bg='#111122',
                                     font=('Consolas', 9))
        self.clock_label.pack(side='left', padx=(0, 5))

        self.close_btn = tk.Button(self.header, text="✕", fg='#666688', bg='#111122',
                                    activebackground='#331111', activeforeground='#ff4444',
                                    bd=0, font=('Consolas', 10), command=self._close, cursor='hand2')
        self.close_btn.pack(side='right', padx=(0, 6))

        self.toggle_btn = tk.Button(self.header, text="▲", fg='#ff9500', bg='#111122',
                                     activebackground='#1a1a2e', activeforeground='#ffaa33',
                                     bd=0, font=('Consolas', 10), command=self._toggle_expand, cursor='hand2')
        self.toggle_btn.pack(side='right', padx=(0, 2))

        # Expandable body
        self.body = tk.Frame(self.main_frame, bg='#0a0a1a')

        # Input row
        self.input_frame = tk.Frame(self.body, bg='#0a0a1a')
        self.input_frame.pack(fill='x', padx=8, pady=(8, 4))

        self.entry = tk.Entry(self.input_frame, bg='#1a1a2e', fg='#eeeeee', insertbackground='#ff9500',
                               font=('Consolas', 10), bd=0, highlightbackground='#ff950044',
                               highlightthickness=1, highlightcolor='#ff9500')
        self.entry.pack(side='left', fill='x', expand=True, ipady=5, padx=(0, 5))
        self.entry.bind('<Return>', lambda e: self._send())

        self.send_btn = tk.Button(self.input_frame, text="➤", fg='#ff9500', bg='#1a1a2e',
                                   activebackground='#2a2a3e', activeforeground='#ffaa33',
                                   bd=0, font=('Consolas', 12), command=self._send, cursor='hand2',
                                   width=3)
        self.send_btn.pack(side='right')

        # Response area
        self.response_frame = tk.Frame(self.body, bg='#0a0a1a')
        self.response_frame.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        self.response_text = tk.Text(self.response_frame, bg='#0d0d1f', fg='#ccccdd',
                                      font=('Consolas', 9), bd=0, wrap='word', height=6,
                                      highlightthickness=0, state='disabled', cursor='arrow')
        self.response_text.pack(fill='both', expand=True)

        scrollbar = tk.Scrollbar(self.response_frame, command=self.response_text.yview, width=8)
        self.response_text.configure(yscrollcommand=scrollbar.set)

        # Quick buttons
        self.quick_frame = tk.Frame(self.body, bg='#0a0a1a')
        self.quick_frame.pack(fill='x', padx=8, pady=(0, 8))

        quick_cmds = [
            ("Clima", "como esta el clima"),
            ("Emails", "leeme mis emails"),
            ("Tareas", "mis tareas pendientes"),
            ("Noticias", "que noticias hay hoy"),
        ]
        for label, cmd in quick_cmds:
            btn = tk.Button(self.quick_frame, text=label, fg='#ff9500', bg='#1a1a2e',
                           activebackground='#2a2a3e', activeforeground='#ffaa33',
                           bd=0, font=('Consolas', 8), cursor='hand2', padx=6, pady=2,
                           command=lambda c=cmd: self._send_quick(c))
            btn.pack(side='left', padx=2)

    def _bind_drag(self):
        for w in [self.header, self.title_label, self.clock_label, self.dot]:
            w.bind('<Button-1>', self._start_drag)
            w.bind('<B1-Motion>', self._on_drag)

    def _start_drag(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _on_drag(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _toggle_expand(self):
        if self.expanded:
            self.body.pack_forget()
            self.root.geometry(f"{self.width}x{self.height}")
            self.toggle_btn.config(text="▲")
            self.expanded = False
        else:
            self.body.pack(fill='both', expand=True)
            self.root.geometry(f"{self.width}x{self.expanded_height}")
            self.toggle_btn.config(text="▼")
            self.expanded = True
            self.entry.focus_set()

    def _send(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, 'end')
        self._set_response("Procesando...")
        threading.Thread(target=self._call_api, args=(text,), daemon=True).start()

    def _send_quick(self, cmd):
        self._set_response("Procesando...")
        if not self.expanded:
            self._toggle_expand()
        threading.Thread(target=self._call_api, args=(cmd,), daemon=True).start()

    def _call_api(self, message):
        try:
            payload = json.dumps({"message": message}).encode("utf-8")
            req = urllib.request.Request(
                f"{API}/chat",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            response = data.get("text", "Sin respuesta")
        except Exception as e:
            response = f"Error: {e}"
        self.root.after(0, lambda: self._set_response(response))

    def _set_response(self, text):
        self.response_text.config(state='normal')
        self.response_text.delete('1.0', 'end')
        self.response_text.insert('1.0', text)
        self.response_text.config(state='disabled')

    def _update_clock(self):
        t = time.strftime("%H:%M")
        self.clock_label.config(text=t)
        self.root.after(10000, self._update_clock)

    def _close(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = JarvisWidget()
    app.run()
