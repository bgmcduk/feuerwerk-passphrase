#!/usr/bin/env python3
"""
Feuerwerk Passphrase
====================
A memorable-password generator with a built-in, encrypted notes system.

It makes passwords a person can actually recall: two or three real words joined by
symbols, with optional digits. A four-word list of common words has vastly more
entropy than a string of random characters, and it can be written on a sticky note
and still be safe, because what is saved is a *wordlist-seeded* passphrase, not
the words themselves.

The notes system records what each password is for, so that "the one for the
bank" can be answered months later.

SECURITY
--------
The master password never leaves this machine and is never stored. It is used
only to derive a key with PBKDF2-HMAC-SHA256, which encrypts the whole vault
with Fernet (AES-128-CBC with HMAC-SHA256) from the `cryptography` library.

The vault lives at  ~/.config/feuerwerk-passphrase/vault.enc
The master verifier   at  ~/.config/feuerwerk-passphrase/master.salt
The wordlist          at  ~/.config/feuerwerk-passphrase/words.txt

If the master password is forgotten the vault cannot be recovered. That is the
point of encrypting it, and it is the one thing the user must accept.

Author : SAL-9000 for Beatrix Groves-McDaniel
Licence : MIT
"""

import base64
import csv
import io
import json
import os
import random
import re
import secrets
import string
import subprocess
import sys
from datetime import datetime
from pathlib import Path

APP_NAME = "Feuerwerk Passphrase"
CONFIG_DIR = Path.home() / ".config" / "feuerwerk-passphrase"
VAULT_FILE = CONFIG_DIR / "vault.enc"
MASTER_FILE = CONFIG_DIR / "master.salt"
WORDS_FILE = CONFIG_DIR / "words.txt"
PBKDF2_ROUNDS = 480_000

# The house livery: Feuerwerk gold on black.
GOLD = "#f5c211"
GOLD_DIM = "#aa7733"
GOLD_PALE = "#ffffaa"
BLACK = "#000000"
PANEL = "#1a1a1a"
URGENT = "#aa4400"

SYMBOLS = ["_", "-", "+", "&", "=", ".", "@", "#"]
# Ambiguous glyphs are deliberately excluded: O/0, l/1/I, O/0, etc.
AMBIGUOUS = set("Il1O0oB8S5Z2")

DEFAULT_WORDS = 3
DEFAULT_DIGITS = 0


# --------------------------------------------------------------------- crypto
def _fernet(master_password: str, salt: bytes):
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ROUNDS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8")))
    return Fernet(key)


def vault_exists() -> bool:
    return VAULT_FILE.exists() and MASTER_FILE.exists()


def create_vault(master_password: str) -> None:
    """Create a new, empty vault, encrypted under the master password."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    salt = os.urandom(16)
    MASTER_FILE.write_bytes(salt)
    os.chmod(MASTER_FILE, 0o600)

    data = {"notes": [], "created": datetime.now().isoformat(timespec="seconds")}
    payload = json.dumps(data).encode("utf-8")
    token = _fernet(master_password, salt).encrypt(payload)
    VAULT_FILE.write_bytes(token)
    os.chmod(VAULT_FILE, 0o600)


def load_vault(master_password: str):
    """Decrypt the vault. Raises ValueError if the master password is wrong."""
    from cryptography.fernet import InvalidToken

    salt = MASTER_FILE.read_bytes()
    token = VAULT_FILE.read_bytes()
    try:
        payload = _fernet(master_password, salt).decrypt(token)
    except InvalidToken:
        raise ValueError("wrong master password")
    return json.loads(payload.decode("utf-8"))


def save_vault(master_password: str, data) -> None:
    salt = MASTER_FILE.read_bytes()
    payload = json.dumps(data).encode("utf-8")
    token = _fernet(master_password, salt).encrypt(payload)
    VAULT_FILE.write_bytes(token)
    os.chmod(VAULT_FILE, 0o600)


# ------------------------------------------------------------------ wordlist
def load_words() -> list:
    """The wordlist, filtered to words a person can spell and remember."""
    if not WORDS_FILE.exists():
        return []
    words = []
    for raw in WORDS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        w = raw.strip().lower()
        if not w or not w.isalpha() or not (3 <= len(w) <= 9):
            continue
        if any(c in AMBIGUOUS for c in w):
            continue
        words.append(w)
    return sorted(set(words))


def ensure_words() -> list:
    """Install the wordlist on first run.

    The curated list is shipped inside the package (data/words.txt), so the tool
    works on any machine without needing a system dictionary. If that is missing
    for some reason, fall back to the system dictionary and filter it.
    """
    words = load_words()
    if words:
        return words

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # The curated list is shipped in two places, and the installed binary lives
    # at /usr/bin, so look in the share directory first, then beside the script.
    candidates = [
        Path("/usr/share/feuerwerk-passphrase/data/words.txt"),
        # Inside a Flatpak the sandbox prefix is /app.
        Path("/app/share/feuerwerk-passphrase/data/words.txt"),
        Path(__file__).resolve().parent / "data" / "words.txt",
    ]
    for shipped in candidates:
        if shipped.exists():
            WORDS_FILE.write_text(
                shipped.read_text(encoding="utf-8", errors="replace"),
                encoding="utf-8")
            os.chmod(WORDS_FILE, 0o600)
            return load_words()

    system = Path("/usr/share/dict/words")
    if system.exists():
        WORDS_FILE.write_text(system.read_text(encoding="utf-8", errors="replace"),
                             encoding="utf-8")
        os.chmod(WORDS_FILE, 0o600)
        return load_words()
    return []


# ----------------------------------------------------------------- generator
def generate(words: list, n_words: int = DEFAULT_WORDS,
             n_digits: int = DEFAULT_DIGITS,
             symbol: str = None, rng=None) -> str:
    """Build a passphrase: words joined by symbols, optionally with digits."""
    rng = rng or random.SystemRandom()
    if not words:
        raise ValueError("no wordlist available")

    chosen = [rng.choice(words) for _ in range(n_words)]
    if symbol is None:
        symbol = rng.choice(SYMBOLS)

    # Capitalise one word, for a little more entropy and easy reading aloud.
    i = rng.randrange(len(chosen))
    chosen[i] = chosen[i].capitalize()

    parts = [chosen[0]]
    for w in chosen[1:]:
        parts.append(symbol)
        parts.append(w)

    phrase = "".join(parts)

    if n_digits:
        digits = "".join(str(rng.randrange(10)) for _ in range(n_digits))
        # Put the digits at the end, so the word part stays readable.
        phrase += symbol + digits

    return phrase


def strength_of(phrase: str, words: list) -> str:
    """A rough, honest strength read: words are strong, length still helps."""
    parts = [p for p in re.split(r"[_+\-&=.@#]", phrase) if p]
    wordy = sum(1 for p in parts if p.lower() in words)
    if wordy >= 4:
        return "Very strong"
    if wordy == 3 and len(phrase) >= 18:
        return "Very strong"
    if wordy == 3:
        return "Strong"
    if wordy == 2 and len(phrase) >= 14:
        return "Good"
    if wordy == 2:
        return "Reasonable"
    return "Weak"


# --------------------------------------------------------------------- GUI
def build_gui():
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk, GdkPixbuf, Pango
    from gi.repository import GLib

    class CssProvider:
        @staticmethod
        def install():
            css = b"""
            window, .fp-window { background-color: #1a1a1a; color: #ffffaa; }
            label { color: #ffffaa; }
            .title { color: #f5c211; font-weight: bold; font-size: 15px; }
            .subtitle { color: #aa7733; }
            .pass {
                color: #f5c211;
                font-family: monospace;
                font-size: 16px;
                font-weight: bold;
                padding: 6px;
            }
            .weak { color: #aa4400; font-weight: bold; }
            .ok { color: #88aa44; }
            .mid { color: #aa7733; }
            .good { color: #88aa44; }
            .strong { color: #f5c211; font-weight: bold; }
            .dim { color: #777777; }
            button {
                color: #f5c211;
                background-image: none;
                background-color: #242424;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
            }
            button:hover { background-color: #2f2f2f; border-color: #f5c211; }
            entry {
                background-color: #242424;
                color: #ffffaa;
                caret-color: #f5c211;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
            }
            entry:focus { border-color: #f5c211; }
            entry:selected, entry:selected:focus {
                background-color: #2f2f2f;
                color: #ffffaa;
            }
            frame { border-color: #555555; }
            treeview { background-color: #242424; color: #ffffaa; }
            treeview:hover { background-color: #2f2f2f; }
            treeview:selected { background-color: #f5c211; color: #000000; }
            scrolledwindow { background-color: #242424; }
            spinbutton {
                background-color: #242424;
                color: #ffffaa;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px;
            }
            combobox button { color: #f5c211; }
            """
            prov = Gtk.CssProvider()
            prov.load_from_data(css)
            #
            # GTK3 has moved this API around between versions, and Zorin's
            # GTK3 has no add_provider_for_display at all. Try the newest
            # first, then the older one, and finally fall back to applying
            # the style to the window's own context, which always works.
            #
            # Note also that Gdk.Screen.get_default() returns None when there
            # is no display, and the older call then raises a TypeError.
            applied = False
            display = Gdk.Display.get_default()
            if display is not None and hasattr(
                    Gtk.StyleContext, "add_provider_for_display"):
                Gtk.StyleContext.add_provider_for_display(
                    display, prov,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                applied = True
            if not applied:
                screen = Gdk.Screen.get_default()
                if screen is not None:
                    Gtk.StyleContext.add_provider_for_screen(
                        screen, prov,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                    applied = True
            if not applied:
                win = Gtk.Window()
                win.get_style_context().add_provider(
                    prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                win.destroy()

    CssProvider.install()

    from cryptography.fernet import InvalidToken

    state = {
        "master": None,
        "vault": None,
        "words": [],
        "last_generated": "",
    }

    def err(parent, msg):
        dlg = Gtk.MessageDialog(
            transient_for=parent, modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=msg)
        dlg.run()
        dlg.destroy()

    def info(parent, msg):
        dlg = Gtk.MessageDialog(
            transient_for=parent, modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK, text=msg)
        dlg.run()
        dlg.destroy()

    def ask_master(parent, confirm=True):
        """Prompt for the master password. Returns the string, or None."""
        dlg = Gtk.Dialog(title="Master password", transient_for=parent, modal=True)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL,
                        "OK", Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)
        box = dlg.get_content_area()
        box.set_spacing(8)
        box.set_border_width(12)
        lbl = Gtk.Label(label="Master password")
        lbl.set_xalign(0)
        box.pack_start(lbl, False, False, 0)
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_placeholder_text("your master password")
        box.pack_start(entry, False, False, 0)
        dlg.show_all()
        while True:
            resp = dlg.run()
            if resp != Gtk.ResponseType.OK:
                dlg.destroy()
                return None
            pw = entry.get_text()
            if pw:
                break
            err(dlg, "The master password cannot be empty.")
        dlg.destroy()
        return pw

    # ------------------------------------------------------------- setup view
    def show_setup(win, stack):
        """First run: create the master password and the vault."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.set_border_width(24)

        title = Gtk.Label(label=APP_NAME)
        title.get_style_context().add_class("title")
        title.set_xalign(0)
        page.pack_start(title, False, False, 0)

        sub = Gtk.Label(
            label="Welcome. You are about to create the master password.\n\n"
                  "This is the one password you must never forget and never "
                  "write down anywhere else. It protects every password and "
                  "every note you store here.\n\n"
                  "If you lose it, the vault cannot be recovered by anyone, "
                  "including me.\n\n"
                  "Choose something long and comfortable. A short phrase of "
                  "your own works well.")
        sub.get_style_context().add_class("subtitle")
        sub.set_xalign(0)
        sub.set_line_wrap(True)
        page.pack_start(sub, False, False, 0)

        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_placeholder_text("master password")
        page.pack_start(entry, False, False, 0)

        entry2 = Gtk.Entry()
        entry2.set_visibility(False)
        entry2.set_placeholder_text("and again, to be sure")
        page.pack_start(entry2, False, False, 0)

        strength = Gtk.Label(label="")
        strength.get_style_context().add_class("ok")
        strength.set_xalign(0)
        page.pack_start(strength, False, False, 0)

        def on_changed(_e):
            pw = entry.get_text()
            if not pw:
                strength.set_text("")
                return
            if len(pw) < 8:
                strength.set_text("too short — eight characters or more")
                strength.get_style_context().remove_class("ok")
                strength.get_style_context().add_class("weak")
            elif len(pw) < 14:
                strength.set_text("workable, but longer is better")
                strength.get_style_context().remove_class("ok")
                strength.get_style_context().add_class("mid")
            else:
                strength.set_text("good master password")
                strength.get_style_context().remove_class("mid")
                strength.get_style_context().remove_class("weak")
                strength.get_style_context().add_class("ok")

        entry.connect("changed", on_changed)

        def on_create(_b):
            pw = entry.get_text()
            if not pw:
                err(win, "Please choose a master password.")
                return
            if pw != entry2.get_text():
                err(win, "The two entries do not match.")
                return
            if len(pw) < 8:
                err(win, "The master password must be at least eight characters.")
                return
            try:
                create_vault(pw)
            except Exception as exc:      # noqa: BLE001
                err(win, f"Could not create the vault:\n{exc}")
                return
            state["master"] = pw
            # The vault contents must be loaded into the state, or the notes
            # code finds state["vault"] is None and cannot subscript it.
            try:
                state["vault"] = load_vault(pw)
            except Exception as exc:      # noqa: BLE001
                err(win, f"Could not open the new vault:\n{exc}")
                return
            state["words"] = ensure_words()
            if not state["words"]:
                err(win, "No wordlist could be found. The generator will "
                         "not work until one is installed.")
            show_main(win, stack)

        btn = Gtk.Button(label="Create the vault")
        btn.get_style_context().add_class("strong")
        btn.connect("clicked", on_create)
        page.pack_start(btn, False, False, 0)

        page.show_all()
        stack.add_named(page, "setup")
        stack.set_visible_child_name("setup")
        return page

    # -------------------------------------------------------------- main view
    def show_main(win, stack):
        # After a Lock, unlocking comes back here. Reuse the existing page
        # rather than adding a second one under the same name.
        existing = state.get("main_page")
        if existing is not None:
            stack.set_visible_child_name("main")
            refresh_main()
            return existing
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(16)

        # ---- generator ----
        gen_frame = Gtk.Frame(label="Generate a passphrase")
        gen_frame.set_border_width(10)
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        out_entry = Gtk.Entry()
        out_entry.set_editable(False)
        out_entry.get_style_context().add_class("pass")
        out_entry.set_placeholder_text("a passphrase will appear here")
        v.pack_start(out_entry, False, False, 0)

        ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        n_words = Gtk.SpinButton.new_with_range(2, 6, 1)
        n_words.set_value(DEFAULT_WORDS)
        ctrl.pack_start(Gtk.Label(label="Words:"), False, False, 0)
        ctrl.pack_start(n_words, False, False, 0)

        n_digits = Gtk.SpinButton.new_with_range(0, 4, 1)
        n_digits.set_value(DEFAULT_DIGITS)
        ctrl.pack_start(Gtk.Label(label="Digits:"), False, False, 0)
        ctrl.pack_start(n_digits, False, False, 0)

        sym_combo = Gtk.ComboBoxText()
        for s in SYMBOLS:
            sym_combo.append_text(s)
        sym_combo.set_active(0)
        ctrl.pack_start(Gtk.Label(label="Joiner:"), False, False, 0)
        ctrl.pack_start(sym_combo, False, False, 0)

        gen_btn = Gtk.Button(label="Generate")
        gen_btn.get_style_context().add_class("strong")
        ctrl.pack_end(gen_btn, False, False, 0)

        copy_btn = Gtk.Button(label="Copy")
        ctrl.pack_end(copy_btn, False, False, 0)

        v.pack_start(ctrl, False, False, 0)

        strength_lbl = Gtk.Label(label="")
        strength_lbl.set_xalign(0)
        v.pack_start(strength_lbl, False, False, 0)

        gen_frame.add(v)
        page.pack_start(gen_frame, False, False, 0)

        # ---- notes ----
        notes_frame = Gtk.Frame(label="What is each password for?")
        notes_frame.set_border_width(10)
        nv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        tree = Gtk.TreeView()
        tree.set_model(Gtk.ListStore(str, str, str))
        tree.set_headers_visible(True)
        for col_index, col_title in enumerate(("System", "Note", "Passphrase")):
            # The "text" attribute takes the column INDEX, not the title.
            col = Gtk.TreeViewColumn(col_title, Gtk.CellRendererText(),
                                     text=col_index)
            col.set_resizable(True)
            # Sizing is a per-column property; TreeView has no set_column_sizing.
            col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
            tree.append_column(col)
        scroller = Gtk.ScrolledWindow()
        scroller.set_shadow_type(Gtk.ShadowType.IN)
        scroller.set_size_request(-1, 220)
        scroller.add(tree)
        nv.pack_start(scroller, True, True, 0)

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        sys_entry = Gtk.Entry()
        sys_entry.set_placeholder_text("system, e.g. the bank")
        note_entry = Gtk.Entry()
        note_entry.set_placeholder_text("note, e.g. the password for online banking")
        save_btn = Gtk.Button(label="Save")
        save_btn.get_style_context().add_class("strong")
        del_btn = Gtk.Button(label="Delete")
        entry_row.pack_start(sys_entry, False, False, 0)
        entry_row.pack_start(note_entry, True, True, 0)
        entry_row.pack_start(save_btn, False, False, 0)
        entry_row.pack_start(del_btn, False, False, 0)
        nv.pack_start(entry_row, False, False, 0)

        notes_frame.add(nv)
        page.pack_start(notes_frame, True, True, 0)

        # ---- footer ----
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lock_lbl = Gtk.Label(label="vault locked")
        lock_lbl.get_style_context().add_class("dim")
        footer.pack_start(lock_lbl, False, False, 0)

        lock_btn = Gtk.Button(label="Lock")
        lock_btn.set_tooltip_text(
            "Close the vault and ask for the master password again")
        exit_btn = Gtk.Button(label="Exit")
        exit_btn.set_tooltip_text("Close the application")
        footer.pack_end(lock_btn, False, False, 0)
        footer.pack_end(exit_btn, False, False, 0)
        page.pack_start(footer, False, False, 0)

        # ---- behaviour ----
        def refresh_tree():
            store = Gtk.ListStore(str, str, str)
            if state["vault"]:
                for item in state["vault"]["notes"]:
                    store.append([item.get("system", ""), item.get("note", ""),
                                  item.get("password", "")])
            tree.set_model(store)

        def do_generate(_b=None):
            words = state["words"]
            if not words:
                err(win, "No wordlist available.")
                return
            sym = sym_combo.get_active_text()
            phrase = generate(words,
                              n_words=int(n_words.get_value()),
                              n_digits=int(n_digits.get_value()),
                              symbol=sym)
            out_entry.set_text(phrase)
            state["last_generated"] = phrase
            s = strength_of(phrase, words)
            strength_lbl.set_text(f"strength: {s}")
            for cls in ("weak", "mid", "good", "strong"):
                strength_lbl.get_style_context().remove_class(cls)
            strength_lbl.get_style_context().add_class(
                {"Weak": "weak", "Reasonable": "mid", "Good": "good",
                 "Strong": "strong", "Very strong": "strong"}.get(s, "good"))

        def do_copy(_b=None):
            phrase = out_entry.get_text()
            if not phrase:
                return
            clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clip.set_text(phrase, -1)
            clip.store()
            strength_lbl.set_text("copied to the clipboard")

        def do_save(_b=None):
            system = sys_entry.get_text().strip()
            note = note_entry.get_text().strip()
            pw = out_entry.get_text().strip()
            if not system or not pw:
                err(win, "Give the system a name, and generate or paste a "
                         "passphrase first.")
                return
            try:
                state["vault"]["notes"].append(
                    {"system": system, "note": note, "password": pw,
                     "created": datetime.now().isoformat(timespec="seconds")})
                save_vault(state["master"], state["vault"])
            except Exception as exc:          # noqa: BLE001
                err(win, f"Could not save:\n{exc}")
                return
            sys_entry.set_text("")
            note_entry.set_text("")
            refresh_tree()

        def do_delete(_b=None):
            model, path = tree.get_selection().get_selected()
            if path is None:
                err(win, "Choose a row to delete.")
                return
            row = model[path]
            dlg = Gtk.MessageDialog(
                transient_for=win, modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text=f"Delete the note for '{row[0]}'?")
            resp = dlg.run()
            dlg.destroy()
            if resp != Gtk.ResponseType.OK:
                return
            try:
                state["vault"]["notes"] = [
                    n for n in state["vault"]["notes"]
                    if not (n.get("system") == row[0]
                            and n.get("note") == row[1]
                            and n.get("password") == row[2])]
                save_vault(state["master"], state["vault"])
            except Exception as exc:          # noqa: BLE001
                err(win, f"Could not delete:\n{exc}")
                return
            refresh_tree()

        def do_lock(_b=None):
            """Close the vault and go back to asking for the master password."""
            state["master"] = None
            state["vault"] = None
            state["last_generated"] = ""
            out_entry.set_text("")
            refresh_tree()
            try:
                show_unlock(win, stack)
            except Exception as exc:          # noqa: BLE001
                err(win, f"Could not lock the vault:\n{exc}")
                return
            entry_ref = state.get("unlock_entry")
            if entry_ref is not None:
                entry_ref.set_text("")

        def do_exit(_b=None):
            """Close the application."""
            win.destroy()

        gen_btn.connect("clicked", do_generate)
        copy_btn.connect("clicked", do_copy)
        save_btn.connect("clicked", do_save)
        del_btn.connect("clicked", do_delete)
        lock_btn.connect("clicked", do_lock)
        exit_btn.connect("clicked", do_exit)

        def on_destroy(_w):
            state["master"] = None
            state["vault"] = None
            Gtk.main_quit()

        win.connect("destroy", on_destroy)

        # The page is built after win.show_all(), so its children have never
        # been shown. Show them, then add it, then switch the stack to it.
        state["main_page"] = page
        state["main_refresh"] = lambda: (do_generate(), refresh_tree())
        page.show_all()
        stack.add_named(page, "main")
        stack.set_visible_child_name("main")
        do_generate()
        refresh_tree()
        return page

    # ------------------------------------------------------------- unlock view
    def show_unlock(win, stack):
        # Building the page twice would add a second page under the same
        # name, so reuse the one already there.
        existing = state.get("unlock_page")
        if existing is not None:
            stack.set_visible_child_name("unlock")
            return existing
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.set_border_width(24)

        title = Gtk.Label(label=APP_NAME)
        title.get_style_context().add_class("title")
        title.set_xalign(0)
        page.pack_start(title, False, False, 0)

        sub = Gtk.Label(label="Enter the master password to open the vault.")
        sub.get_style_context().add_class("subtitle")
        sub.set_xalign(0)
        page.pack_start(sub, False, False, 0)

        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_placeholder_text("master password")
        page.pack_start(entry, False, False, 0)

        def on_unlock(_b=None):
            pw = entry.get_text()
            if not pw:
                return
            try:
                state["vault"] = load_vault(pw)
            except ValueError:
                err(win, "That is not the master password.")
                entry.set_text("")
                return
            except Exception as exc:          # noqa: BLE001
                err(win, f"Could not open the vault:\n{exc}")
                return
            state["master"] = pw
            state["words"] = ensure_words()
            show_main(win, stack)

        btn = Gtk.Button(label="Unlock")
        btn.get_style_context().add_class("strong")
        btn.connect("clicked", on_unlock)
        entry.connect("activate", on_unlock)
        page.pack_start(btn, False, False, 0)

        state["unlock_page"] = page
        state["unlock_entry"] = entry
        page.show_all()
        stack.add_named(page, "unlock")
        stack.set_visible_child_name("unlock")
        return page

    def refresh_main():
        """Re-populate the main view after it has been rebuilt."""
        fn = state.get("main_refresh")
        if fn is not None:
            fn()

    # ----------------------------------------------------------------- window
    win = Gtk.Window(title=APP_NAME)
    win.set_default_size(860, 760)
    win.set_size_request(700, 560)
    win.get_style_context().add_class("fp-window")
    win.set_border_width(0)
    win.connect("delete-event", lambda w, e: (w.destroy(), True)[1])

    stack = Gtk.Stack()
    win.add(stack)

    if vault_exists():
        show_unlock(win, stack)
    else:
        show_setup(win, stack)

    win.show_all()
    # Raise and focus the window on startup. On a busy desktop another window
    # (a browser, a chat client) can be stacked over ours, and it will then
    # swallow every click on the lower half of our window -- including our own
    # buttons. present() asks the window manager to bring us to the front and
    # take focus, which is what a user expects when they open an application.
    win.present()

    # Raise the window whenever it is focused, rather than keeping it
    # permanently above every other window. A permanently-above window has to
    # be minimised to reach anything beneath it, which is worse than the
    # problem it solves. Raising on focus gives the same protection -- the
    # window is at the front whenever you are actually using it -- without
    # getting in the way the rest of the time.
    def raise_on_focus(_w, _event):
        win.present()
        return False

    win.connect("focus-in-event", raise_on_focus)
    Gtk.main()


def main():
    if "--version" in sys.argv:
        print(f"{APP_NAME} 1.0")
        return 0
    try:
        build_gui()
    except ImportError as exc:
        print(f"{APP_NAME} needs PyGObject and GTK3: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
