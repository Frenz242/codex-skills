"""Keep the review publisher key in Windows Credential Manager; never print it.

store SITE_ID reads {"publisher_key": "..."} from hidden stdin.
run CONFIG REPO_ROOT MANIFEST ASSETS injects the saved key into the fixed Node
publisher process; native Site metadata still arrives through stdin.
Other platforms use their own secure environment injection with the Node CLI.
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

class Credential(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]

def target(site_id):
    if not isinstance(site_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", site_id):
        raise ValueError("Invalid Site identity")
    return "codex-review-site/" + site_id

def vault_read(name):
    pointer = ctypes.POINTER(Credential)()
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(Credential))]
    api.CredReadW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    if not api.CredReadW(name, 1, 0, ctypes.byref(pointer)):
        if ctypes.get_last_error() == 1168:
            return None
        raise RuntimeError("Credential Manager read failed")
    try:
        c = pointer.contents
        return ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize).decode("utf-16-le")
    finally:
        api.CredFree(pointer)

def vault_store(name, secret):
    if not isinstance(secret, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", secret):
        raise ValueError("Invalid publisher secret")
    previous = vault_read(name)
    if previous is not None:
        if previous != secret:
            raise RuntimeError("Existing publisher key differs; no credential was replaced")
        return
    blob = secret.encode("utf-16-le")
    buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    value = Credential()
    value.Type, value.TargetName, value.Persist = 1, name, 2
    value.CredentialBlobSize, value.CredentialBlob = len(blob), buffer
    value.UserName = "review-publisher"
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    if not api.CredWriteW(ctypes.byref(value), 0):
        raise RuntimeError("Credential Manager write failed")
    if vault_read(name) != secret:
        raise RuntimeError("Credential Manager verification failed")

def private_input():
    if sys.stdin.isatty():
        import msvcrt
        print("Ready for secure review input (hidden).", flush=True)
        chars = []
        while True:
            char = msvcrt.getwch()
            if char == "\x03":
                raise RuntimeError("Input cancelled")
            if char in "\r\n":
                break
            chars.append(char)
            if len(chars) > 131072:
                raise ValueError("Input too large")
        text = "".join(chars)
    else:
        text = sys.stdin.readline(131073)
        if len(text) > 131072:
            raise ValueError("Input too large")
    return json.loads(text)

def main():
    if sys.platform != "win32":
        raise RuntimeError("Use secure environment injection with the Node CLI on this platform")
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "store":
        vault_store(target(args[1]), private_input()["publisher_key"])
        print(json.dumps({"ok": True, "stored": "Windows Credential Manager"}))
        return 0
    if len(args) == 5 and args[0] == "run":
        config = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        if config.get("enabled") is False and config.get("schema_version") == 1:
            print(json.dumps({"status": "disabled", "site_mutations": 0}))
            return 0
        secret = vault_read(target(config["site"]["project_id"]))
        if not secret:
            raise RuntimeError("Publisher key is not in Windows Credential Manager")
        variable = config["auth"]["publisher_key_env"]
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,100}", variable):
            raise ValueError("Invalid publisher environment variable name")
        payload = private_input()
        if "publisher_key" in payload:
            raise ValueError("Vault run does not accept an overriding publisher key")
        env = os.environ.copy()
        env[variable] = secret
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node is unavailable")
        command = [node, "--use-system-ca", str(Path(__file__).with_name("review-publish-cli.mjs")), *args[1:]]
        return subprocess.run(command, input=json.dumps(payload)+"\n", text=True, env=env, timeout=600, check=False).returncode
    raise ValueError("Usage: review-publisher-vault.py store SITE_ID | run CONFIG REPO_ROOT MANIFEST ASSETS")

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt):
        # Neither exception text nor credential material is safe for diagnostic output.
        print(json.dumps({"ok": False, "error": "Secure publisher operation failed; verify setup and inputs locally"}), file=sys.stderr)
        sys.exit(1)
