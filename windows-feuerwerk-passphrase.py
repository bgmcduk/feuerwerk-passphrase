"""
Feuerwerk Passphrase — Windows version.

A memorable-passphrase generator with an encrypted notes vault, in the house
Black and Gold livery. Built with Tkinter, which ships with Python on
Windows, so the only thing to install besides Python is `cryptography`.

The vault format is identical to the Linux application, so a vault created on
one machine opens on the other.

    pip install cryptography
    python feuerwerk-passphrase.py

To build a standalone .exe:

    pip install pyinstaller
    pyinstaller --onefile --windowed --name FeuerwerkPassphrase ^
        --add-data "words.txt;." feuerwerk-passphrase.py
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fp_core as core

APP_NAME = core.APP_NAME


class App:
    def __init__(self):
        self.master_password = None
        self.vault = None
        self.words = []

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("780x640")
        self.root.configure(bg=core.BLACK)
        self.root.resizable(False, False)

        self._style()
        self.frame = tk.Frame(self.root, bg=core.BLACK, padx=24, pady=20)
        self.frame.pack(fill="both", expand=True)

        if core.vault_exists():
            self.show_unlock()
        else:
            self.show_setup()
        self.root.mainloop()

    # ------------------------------------------------------------ appearance
    def _style(self):
        s = ttk.Style(self.root)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=core.BLACK, foreground=core.GOLD_PALE,
                    fieldbackground=core.PANEL, bordercolor=core.PANEL)
        s.configure("TFrame", background=core.BLACK)
        s.configure("TLabel", background=core.BLACK, foreground=core.GOLD_PALE)
        s.configure("Title.TLabel", foreground=core.GOLD, font=("Segoe UI", 13, "bold"))
        s.configure("Sub.TLabel", foreground=core.GOLD_DIM,
                    font=("Segoe UI", 9), wraplength=700)
        s.configure("Gold.TButton", background=core.GOLD, foreground=core.BLACK,
                    font=("Segoe UI", 10, "bold"), borderwidth=0, padding=(12, 7))
        s.map("Gold.TButton",
              background=[("active", core.GOLD_PALE)],
              foreground=[("active", core.BLACK)])
        s.configure("Plain.TButton", background=core.PANEL, foreground=core.GOLD_PALE,
                    borderwidth=1, padding=(10, 5))
        s.map("Plain.TButton", background=[("active", "#2a2a2a")])
        s.configure("TEntry", fieldbackground=core.PANEL, foreground=core.GOLD_PALE,
                    insertcolor=core.GOLD, bordercolor=core.GOLD_DIM)
        s.configure("TCombobox", fieldbackground=core.PANEL,
                    background=core.PANEL, foreground=core.GOLD_PALE,
                    arrowcolor=core.GOLD, bordercolor=core.GOLD_DIM,
                    selectbackground=core.PANEL, selectforeground=core.GOLD_PALE,
                    borderwidth=1, padding=3)
        try:
            s.configure("ComboboxPopover.TCombobox", fieldbackground=core.PANEL)
        except tk.TclError:
            pass
        s.map("TCombobox",
              fieldbackground=[("readonly", core.PANEL)],
              foreground=[("readonly", core.GOLD_PALE)],
              background=[("readonly", core.PANEL)],
              selectbackground=[("readonly", core.PANEL)],
              arrowcolor=[("active", core.GOLD)])
        # The dropdown list is a separate widget from the entry.
        s.configure("TCombobox.Listbox", background=core.PANEL,
                    foreground=core.GOLD_PALE, selectbackground=core.GOLD,
                    selectforeground=core.BLACK)
        s.configure("TSpinbox", fieldbackground=core.PANEL, background=core.PANEL,
                    foreground=core.GOLD_PALE, arrowcolor=core.GOLD,
                    bordercolor=core.GOLD_DIM, borderwidth=1, padding=2)
        s.map("TSpinbox",
              fieldbackground=[("readonly", core.PANEL)],
              background=[("readonly", core.PANEL)],
              foreground=[("readonly", core.GOLD_PALE)],
              arrowcolor=[("active", core.GOLD)])
        s.configure("Treeview", background=core.PANEL, fieldbackground=core.PANEL,
                    foreground=core.GOLD_PALE, borderwidth=0,
                    rowheight=22, font=("Segoe UI", 9))
        s.configure("Treeview.Heading", background="#111111", foreground=core.GOLD,
                    font=("Segoe UI", 9, "bold"), relief="flat", borderwidth=0,
                    padding=(4, 4))
        s.map("Treeview.Heading", background=[("active", "#111111")],
              foreground=[("active", core.GOLD)])
        s.map("Treeview", background=[("selected", core.GOLD)],
              foreground=[("selected", core.BLACK)])

    def clear(self):
        for child in self.frame.winfo_children():
            child.destroy()

    def title(self, text, sub=None):
        t = ttk.Label(self.frame, text=text, style="Title.TLabel")
        t.pack(anchor="w", pady=(0, 8))
        if sub:
            s = ttk.Label(self.frame, text=sub, style="Sub.TLabel")
            s.pack(anchor="w", pady=(0, 14))

    # ------------------------------------------------------------------ setup
    def show_setup(self):
        self.clear()
        self.title(APP_NAME,
                   "You are about to create the master password.\n\n"
                   "This is the one password you must never forget and never write "
                   "down anywhere else. It protects every password and every note "
                   "you store here.\n\n"
                   "If you lose it, the vault cannot be recovered by anyone, "
                   "including the person who wrote this.\n\n"
                   "Choose something long and comfortable. A short phrase of your "
                   "own works well.")

        self.pw = tk.StringVar()
        self.pw2 = tk.StringVar()
        self.strength = tk.StringVar()

        self.e1 = ttk.Entry(self.frame, textvariable=self.pw, show="*")
        self.e1.pack(fill="x", ipady=5, pady=(0, 8))
        self.e2 = ttk.Entry(self.frame, textvariable=self.pw2, show="*")
        self.e2.pack(fill="x", ipady=5, pady=(0, 8))

        self.lbl = ttk.Label(self.frame, textvariable=self.strength,
                             foreground=core.GOLD)
        self.lbl.pack(anchor="w", pady=(0, 14))

        self.pw.trace_add("write", lambda *_: self.on_changed())
        self.e2.bind("<Return>", lambda _e: self.do_create())
        self.e1.focus_set()

        b = ttk.Button(self.frame, text="Create the vault", style="Gold.TButton",
                       command=self.do_create)
        b.pack(fill="x")

    def on_changed(self):
        pw = self.pw.get()
        if not pw:
            self.strength.set("")
            return
        if len(pw) < 8:
            self.strength.set("too short - eight characters or more")
            self.lbl.configure(foreground=core.URGENT)
        elif len(pw) < 14:
            self.strength.set("workable, but longer is better")
            self.lbl.configure(foreground=core.GOLD_DIM)
        else:
            self.strength.set("good master password")
            self.lbl.configure(foreground=core.GOLD)

    def do_create(self):
        pw = self.pw.get()
        if not pw:
            messagebox.showerror(APP_NAME, "Please choose a master password.")
            return
        if pw != self.pw2.get():
            messagebox.showerror(APP_NAME, "The two entries do not match.")
            return
        if len(pw) < 8:
            messagebox.showerror(APP_NAME,
                                 "The master password must be at least eight characters.")
            return
        try:
            core.create_vault(pw)
            self.master_password = pw
            self.vault = core.load_vault(pw)
            self.words = core.ensure_words()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not create the vault:\n{exc}")
            return
        self.show_main()

    # ----------------------------------------------------------------- unlock
    def show_unlock(self):
        self.clear()
        self.title(APP_NAME, "Enter the master password to open the vault.")
        self.pw = tk.StringVar()
        e = ttk.Entry(self.frame, textvariable=self.pw, show="*")
        e.pack(fill="x", ipady=5, pady=(0, 14))
        e.focus_set()
        e.bind("<Return>", lambda _e: self.do_unlock())
        ttk.Button(self.frame, text="Unlock", style="Gold.TButton",
                   command=self.do_unlock).pack(fill="x")

    def do_unlock(self):
        pw = self.pw.get()
        if not pw:
            return
        try:
            self.vault = core.load_vault(pw)
        except ValueError:
            messagebox.showerror(APP_NAME, "That is not the master password.")
            self.pw.set("")
            return
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open the vault:\n{exc}")
            return
        self.master_password = pw
        self.words = core.ensure_words()
        self.show_main()

    # ------------------------------------------------------------------- main
    def show_main(self):
        self.clear()
        self.title(APP_NAME)

        gen = ttk.LabelFrame(self.frame, text="Generate a passphrase")
        gen.configure(style="TFrame")
        gen.pack(fill="x", pady=(0, 12))
        inner = ttk.Frame(gen)
        inner.pack(fill="x", padx=10, pady=10)

        self.out = tk.StringVar()
        e = ttk.Entry(inner, textvariable=self.out, state="readonly")
        e.grid(row=0, column=0, columnspan=6, sticky="ew", ipady=5, pady=(0, 10))
        inner.columnconfigure(0, weight=1)

        self.n_words = tk.IntVar(value=core.DEFAULT_WORDS)
        self.n_digits = tk.IntVar(value=core.DEFAULT_DIGITS)
        self.symbol = tk.StringVar(value=core.SYMBOLS[0])

        ttk.Label(inner, text="Words:").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(inner, from_=2, to=6, width=4,
                    textvariable=self.n_words).grid(row=1, column=1, padx=4)
        ttk.Label(inner, text="Digits:").grid(row=1, column=2, sticky="w", padx=(12, 0))
        ttk.Spinbox(inner, from_=0, to=6, width=4,
                    textvariable=self.n_digits).grid(row=1, column=3, padx=4)
        ttk.Label(inner, text="Joiner:").grid(row=1, column=4, sticky="w", padx=(12, 0))
        cb = ttk.Combobox(inner, values=core.SYMBOLS, state="readonly", width=4,
                          textvariable=self.symbol)
        cb.grid(row=1, column=5, padx=4)
        ttk.Button(inner, text="Generate", style="Plain.TButton",
                   command=self.do_generate).grid(row=1, column=6, padx=(16, 0))
        ttk.Button(inner, text="Copy", style="Plain.TButton",
                   command=self.do_copy).grid(row=1, column=7, padx=(6, 0))

        self.strength = tk.StringVar()
        self.strength_lbl = ttk.Label(inner, textvariable=self.strength,
                                       foreground=core.GOLD)
        self.strength_lbl.grid(row=2, column=0, columnspan=8, sticky="w", pady=(10, 0))

        notes = ttk.LabelFrame(self.frame, text="What is each password for?")
        notes.pack(fill="both", expand=True, pady=(0, 12))

        cols = ("system", "note", "passphrase")
        self.tree = ttk.Treeview(notes, columns=cols, show="headings", height=9)
        for c, title, w in (("system", "System", 140), ("note", "Note", 230),
                            ("passphrase", "Passphrase", 330)):
            self.tree.heading(c, text=title)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        row = ttk.Frame(self.frame)
        row.pack(fill="x")
        self.sys_entry = ttk.Entry(row)
        self.sys_entry.pack(side="left", padx=(0, 8), ipady=4)
        self.note_entry = ttk.Entry(row)
        self.note_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=4)
        ttk.Button(row, text="Save", style="Plain.TButton",
                   command=self.do_save).pack(side="left", padx=4)
        ttk.Button(row, text="Delete", style="Plain.TButton",
                   command=self.do_delete).pack(side="left", padx=4)

        foot = ttk.Frame(self.frame)
        foot.pack(fill="x", pady=(12, 0))
        ttk.Label(foot, text="vault locked", foreground=core.GOLD_DIM).pack(side="left")
        ttk.Button(foot, text="Lock", style="Plain.TButton",
                   command=self.do_lock).pack(side="right", padx=4)
        ttk.Button(foot, text="Exit", style="Plain.TButton",
                   command=self.do_exit).pack(side="right", padx=4)

        self.refresh_tree()
        self.do_generate()

    # ------------------------------------------------------------- behaviour
    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for item in (self.vault or {}).get("notes", []):
            self.tree.insert("", "end", values=(item.get("system", ""),
                                                item.get("note", ""),
                                                item.get("password", "")))

    def do_generate(self):
        if not self.words:
            messagebox.showerror(APP_NAME, "No wordlist available.")
            return
        phrase = core.generate(self.words,
                               n_words=int(self.n_words.get()),
                               n_digits=int(self.n_digits.get()),
                               symbol=self.symbol.get())
        self.out.set(phrase)
        s = core.strength_of(phrase, self.words)
        self.strength.set(f"strength: {s}")
        colour = {core.GOLD: "strong", core.GOLD_DIM: "mid"}.get(core.GOLD)
        self.strength_lbl.configure(
            foreground=core.GOLD if s in ("Strong", "Very strong") else core.GOLD_DIM)

    def do_copy(self):
        phrase = self.out.get()
        if not phrase:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(phrase)
        self.root.update()
        self.strength.set("copied to the clipboard")

    def do_save(self):
        system = self.sys_entry.get().strip()
        note = self.note_entry.get().strip()
        pw = self.out.get().strip()
        if not system or not pw:
            messagebox.showerror(
                APP_NAME,
                "Give the system a name, and generate or paste a passphrase first.")
            return
        try:
            self.vault["notes"].append({
                "system": system, "note": note, "password": pw,
                "created": __import__("datetime").datetime.now().isoformat(
                    timespec="seconds")})
            core.save_vault(self.master_password, self.vault)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not save:\n{exc}")
            return
        self.sys_entry.delete(0, "end")
        self.note_entry.delete(0, "end")
        self.refresh_tree()

    def do_delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror(APP_NAME, "Choose a row to delete.")
            return
        row = self.tree.item(sel[0], "values")
        if not messagebox.askyesno(APP_NAME, f"Delete the note for '{row[0]}'?"):
            return
        try:
            self.vault["notes"] = [
                n for n in self.vault["notes"]
                if not (n.get("system") == row[0] and n.get("note") == row[1]
                        and n.get("password") == row[2])]
            core.save_vault(self.master_password, self.vault)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not delete:\n{exc}")
            return
        self.refresh_tree()

    def do_lock(self):
        self.master_password = None
        self.vault = None
        self.show_unlock()

    def do_exit(self):
        self.root.destroy()


def hide_console():
    """Hide the console window, if we have one.

    The executable is built with PyInstaller's console bootloader and hides its
    own console here. That is deliberate: the windowed bootloader cannot
    initialise the standard streams under Wine, and it fails before the
    application gets a chance to run. A console bootloader always works, and
    hiding the console gives the same result as --windowed.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetConsoleWindow()
        if handle:
            kernel32.ShowWindow(handle, 0)   # SW_HIDE
    except Exception:
        pass


def main():
    try:
        import cryptography  # noqa: F401
    except ImportError:
        print("Feuerwerk Passphrase needs the 'cryptography' package:\n"
              "    pip install cryptography")
        return 1
    hide_console()
    App()
    return 0


if __name__ == "__main__":
    sys.exit(main())
