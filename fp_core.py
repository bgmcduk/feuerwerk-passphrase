"""
Feuerwerk Passphrase — shared core.

This module holds everything that is not a user interface: the vault format,
the encryption, the wordlist handling and the passphrase generator. The Linux
(GTK3) and Windows (Tkinter) applications both import it, so **a vault written
by one opens in the other** and the two applications can be used interchangeably.

The vault format is deliberately boring and portable:

    master.salt   16 random bytes
    vault.enc     a Fernet token (AES-128-CBC, HMAC-SHA256)

The Fernet key is PBKDF2-HMAC-SHA256(master_password, salt, 480000 rounds),
base64url-encoded as the Fernet key. The master password is never stored.
"""

import base64
import json
import os
import random
import re
import secrets
import string
from datetime import datetime
from pathlib import Path

APP_NAME = "Feuerwerk Passphrase"
PBKDF2_ROUNDS = 480_000

# The house livery: Feuerwerk gold on black.
GOLD = "#f5c211"
GOLD_DIM = "#aa7733"
GOLD_PALE = "#ffffaa"
BLACK = "#000000"
PANEL = "#1a1a1a"
URGENT = "#aa4400"

SYMBOLS = ["_", "-", "+", "&", "=", ".", "@", "#"]

DEFAULT_WORDS = 3
DEFAULT_DIGITS = 0


def config_dir() -> Path:
    """Where the vault lives, on whichever platform we are running."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "FeuerwerkPassphrase"
    return Path.home() / ".config" / "feuerwerk-passphrase"


CONFIG_DIR = config_dir()
VAULT_FILE = CONFIG_DIR / "vault.enc"
MASTER_FILE = CONFIG_DIR / "master.salt"
WORDS_FILE = CONFIG_DIR / "words.txt"


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
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass                       # Windows has no POSIX mode to set
    salt = os.urandom(16)
    MASTER_FILE.write_bytes(salt)
    try:
        os.chmod(MASTER_FILE, 0o600)
    except OSError:
        pass

    data = {"notes": [], "created": datetime.now().isoformat(timespec="seconds")}
    payload = json.dumps(data).encode("utf-8")
    token = _fernet(master_password, salt).encrypt(payload)
    VAULT_FILE.write_bytes(token)
    try:
        os.chmod(VAULT_FILE, 0o600)
    except OSError:
        pass


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
    try:
        os.chmod(VAULT_FILE, 0o600)
    except OSError:
        pass


# ------------------------------------------------------------------ wordlist
def load_words() -> list:
    """The wordlist, filtered to words a person can spell and remember."""
    if not WORDS_FILE.exists():
        return []
    out = []
    seen = set()
    try:
        text = WORDS_FILE.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for line in text.splitlines():
        w = line.strip()
        if not w or w in seen:
            continue
        if not w.isalpha():
            continue
        if not w.islower():          # proper nouns and abbreviations are excluded
            continue
        if len(w) < 3 or len(w) > 9:
            continue
        # Accented words are allowed (attaché, café, château), but the
        # ambiguous Latin letters are still excluded.
        if any(c in w for c in "Il1O0oB8S5Z2"):
            continue
        # Keep only letters that a keyboard can produce without a special
        # layout, plus the common accented forms.
        if not all(ch.isalpha() for ch in w):
            continue
        seen.add(w)
        out.append(w)
    return out


def install_words(source: str) -> int:
    """Copy the curated wordlist into the config directory."""
    try:
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    WORDS_FILE.write_text(text, encoding="utf-8")
    try:
        os.chmod(WORDS_FILE, 0o600)
    except OSError:
        pass
    return len(load_words())


def ensure_words() -> list:
    """Make sure a wordlist is available, installing the bundled one if not."""
    words = load_words()
    if words:
        return words
    here = Path(__file__).resolve().parent
    for candidate in (here / "words.txt",
                      here.parent / "data" / "words.txt",
                      Path("/usr/share/feuerwerk-passphrase/data/words.txt")):
        if candidate.exists():
            n = install_words(str(candidate))
            if n:
                return load_words()
    return []


# ------------------------------------------------------------------ generator
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
        # The digits go at the end, so the word part stays readable.
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


def entropy_bits(n_words: int, n_words_total: int) -> float:
    """The entropy of an n-word passphrase drawn from a list of that size."""
    import math
    return math.log2(max(n_words_total, 2) ** max(n_words, 1))
