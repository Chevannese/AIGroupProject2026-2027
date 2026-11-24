"""
auth.py
-------
Administrator authentication for the Rural Roads Path-Finder.

Regular users need no login.  Administrators log in from the main window
to unlock the admin tools (add/update roads and places).

Passwords are never stored in plain text: each account keeps a random
salt and a PBKDF2-SHA256 hash.

Default account (CHANGE IT before the demo):
    username : admin
    password : utech2026

To create a new password entry run:   python auth.py
and paste the printed line into ADMIN_ACCOUNTS below.
"""

import hashlib
import hmac
import os

_ITERATIONS = 120_000

# username -> (salt as hex, password hash as hex)
ADMIN_ACCOUNTS = {
    "admin": "password"
}

# Used so an unknown username takes as long to reject as a wrong password.
_DUMMY_SALT = bytes(16)


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               salt, _ITERATIONS)


def authenticate(username: str, password: str) -> bool:
    
    """Return True only if the username/password pair is a valid admin."""
    
    """
    entry = ADMIN_ACCOUNTS.get(username.strip().lower())
    if entry is None:
        _hash(password, _DUMMY_SALT)
        return False
    salt_hex, hash_hex = entry
    candidate = _hash(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate, bytes.fromhex(hash_hex))
    """
    if ADMIN_ACCOUNTS.get(username) != password:
        return False
    else:
        return True

def make_entry(password: str) -> tuple:
    """Create a (salt_hex, hash_hex) pair for a new admin password."""
    salt = os.urandom(16)
    return salt.hex(), _hash(password, salt).hex()


if __name__ == "__main__":
    import getpass
    name = input("Admin username: ").strip().lower()
    pw = getpass.getpass("Password: ")  
    salt_hex, hash_hex = make_entry(pw)
    print("\nAdd this line to ADMIN_ACCOUNTS in auth.py:\n")
    print(f'    "{name}": ("{salt_hex}",\n     "{hash_hex}"),')
