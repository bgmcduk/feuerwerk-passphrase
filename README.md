# Feuerwerk Passphrase

A memorable-passphrase generator with an encrypted notes vault, in black and gold.

**Feuerwerk** is a firework. A passphrase is a small firework you can light from memory.

---

## What it is

Two things, in one application:

- **A passphrase generator.** Words from a curated 2,908-word list, joined by a symbol, with
  optional digits and a capitalised word for readability. It tells you honestly how strong
  the result is.
- **An encrypted vault.** Notes, system names and passwords, encrypted with a master password
  you choose.

**The master password is never stored anywhere.** It is not kept by the application, not
written to disk, and not sent to any server. Lose it and the vault cannot be recovered by
anyone, including the author. Write it down somewhere safe.

The vault format is deliberately boring and portable:

```
master.salt   16 random bytes
vault.enc     a Fernet token (AES-128-CBC, HMAC-SHA256)
```

The Fernet key is `PBKDF2-HMAC-SHA256(master_password, salt, 480000 rounds)`, base64url-encoded.
The master password is never stored.

---

## Install

| Platform | What to download | How |
|---|---|---|
| **Linux** | `feuerwerk-passphrase_1.0.0-12_all.deb` | `sudo apt install ./feuerwerk-passphrase_1.0.0-12_all.deb` |
| **Linux (portable)** | `org.bgmcd.FeuerwerkPassphrase.flatpak` | `flatpak install ./org.bgmcd.FeuerwerkPassphrase.flatpak` |
| **Windows** | `FeuerwerkPassphrase.exe` | Run it. Nothing to install. |
| **macOS (Intel)** | `FeuerwerkPassphrase-1.0.dmg` | Open the disk image and drag the app to Applications |
| **macOS (from source)** | `install.command` | Double-click it. It builds the app for your machine. |
| **Anywhere** | the web version | <https://feuerpass.beagmcd.net> |

### A note on macOS

The `.dmg` is built natively on an Intel Mac. If macOS refuses to open it the first time,
right-click the app, choose **Open**, then **Open** again. Or:

```sh
xattr -dr com.apple.quarantine "Feuerwerk Passphrase-1.0.dmg"
```

**Building from source on macOS** needs a Python with `tkinter` — the one that comes with the
Command Line Tools (`xcode-select --install`) has it. Then double-click `install.command`,
which makes a private virtual environment, installs what it needs, builds the app and puts it
in Applications.

---

## The vault travels between machines

The vault lives at:

- Linux and macOS: `~/.config/feuerwerk-passphrase/`
- Windows: `%APPDATA%\FeuerwerkPassphrase\`

**Export** writes two files, `master.salt` (16 raw bytes) and `vault.enc` (the token).
**Import** reads them back. A vault created on one machine opens on any other — the format
is identical on all of them.

If you use the web version, the vault lives in the browser's own storage and the encryption
happens **in the browser**. Nothing is sent to the server. Exporting from there and
importing into a desktop app works, and the other way round.

---

## The wordlist

2,908 words, filtered so that every one of them is spellable from memory: lower case only,
no proper nouns, no abbreviations, no ambiguous characters (`I`, `l`, `1`, `O`, `0`, `B`,
`8`, `S`, `5`, `Z`, `2`), and between three and nine letters. Accented words are welcome —
*attaché*, *café*, *château* — as long as a keyboard can produce them.

---

## Building from source

### Linux (Debian/Ubuntu)

```sh
dpkg-buildpackage -us -uc -b
```

### Linux (Flatpak)

The Flatpak bundles Python and the GTK application, so it runs on any distribution.

### Windows

```sh
pip install pyinstaller
pyinstaller --onefile --windowed --name FeuerwerkPassphrase ^
    --add-data "words.txt;." feuerwerk-passphrase.py
```

### macOS

```sh
bash build-dmg.sh
```

This needs `pyinstaller` and `cryptography`, and it must run **on a Mac** — a disk image
cannot be built anywhere else.

---

## The applications

The house livery is black and gold, and it is used consistently across every platform:
the GTK application on Linux, the Tkinter application on Windows and macOS, and the web
version.

---

## Licence

MIT. See `LICENSE`.

---

*Written by SAL-9000 for Beatrix Groves-McDaniel.*
