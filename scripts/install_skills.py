#!/usr/bin/env python3
"""Install selected skills from GitHub main without altering a Git checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile

REPOSITORY = "Frenz242/codex-skills"
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def lexists(path):
    return os.path.lexists(path)


def is_link(path):
    return path.is_symlink() or bool(
        getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def fingerprint(path, *, include_modes=True):
    """Hash names, bytes and POSIX execute bits; reject embedded links.

    include_modes=False is only for verifying pre-v2 installation state.
    Windows does not expose POSIX execute permissions, so its hash is unchanged.
    """
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if is_link(item):
            raise ValueError(f"Unexpected link inside skill content: {item}")
        if item.is_file():
            digest.update(item.relative_to(path).as_posix().encode() + b"\0")
            digest.update(hashlib.sha256(item.read_bytes()).digest())
            if include_modes and os.name != "nt":
                digest.update(bytes([item.stat().st_mode & 0o111]))
    return digest.hexdigest()


def catalog(root):
    return sorted(p.name for p in root.iterdir()
                  if NAME.fullmatch(p.name) and p.is_dir() and (p / "SKILL.md").is_file())


def effective_hash(root, name, *, include_modes=True):
    # These skills call a sibling recorder. Keep its version with the skill.
    parts = [fingerprint(root / name, include_modes=include_modes)]
    if name != "improve-skills" and (root / "improve-skills" / "SKILL.md").is_file():
        parts.append(fingerprint(root / "improve-skills", include_modes=include_modes))
    return hashlib.sha256("".join(parts).encode()).hexdigest()


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "codex-skills-installer"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch_main(destination):
    commit = json.loads(download(f"https://api.github.com/repos/{REPOSITORY}/commits/main"))["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("GitHub returned an invalid main commit")
    archive = destination / "source.zip"
    archive.write_bytes(download(f"https://codeload.github.com/{REPOSITORY}/zip/{commit}"))
    with zipfile.ZipFile(archive) as bundle:
        # Do not trust zip paths, device names, or symlink metadata.
        seen = set()
        for member in bundle.infolist():
            parts = PurePosixPath(member.filename).parts
            if (not parts or parts[0] != f"codex-skills-{commit}"
                    or any(p in (".", "..") or ":" in p or "\\" in p
                           or p.endswith((".", " "))
                           or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", p)
                           for p in parts)
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError(f"Unsafe archive member: {member.filename}")
            key = member.filename.casefold()
            if key in seen:
                raise ValueError("Duplicate archive path")
            seen.add(key)
        bundle.extractall(destination)
        if os.name != "nt":
            for member in bundle.infolist():
                if not member.is_dir():
                    (destination / member.filename).chmod(0o755 if member.external_attr >> 16 & 0o111 else 0o644)
    return destination / f"codex-skills-{commit}", commit


def locations():
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser().absolute()
    evidence = []
    executable = shutil.which("codex")
    if executable:
        evidence.append(f"CLI: {executable}")
    if codex_home.is_dir():
        evidence.append(f"Codex home: {codex_home}")
    for app in (home / "Applications/Codex.app", Path("/Applications/Codex.app"),
                Path(os.environ.get("LOCALAPPDATA", home)) / "Programs/Codex"):
        if app.is_dir():
            evidence.append(f"Desktop: {app}")
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        for app in (Path(os.environ["LOCALAPPDATA"]) / "Packages").glob("*Codex*"):
            evidence.append(f"Desktop package data: {app}")
    return home / ".agents/skills", home / ".agents/codex-skills-installer", codex_home, evidence


def link_directory(source, destination):
    if os.name == "nt":
        # Literal paths passed via environment, never interpolated into shell code.
        env = dict(os.environ, SKILL_LINK_SOURCE=str(source), SKILL_LINK_DEST=str(destination))
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                        "$ErrorActionPreference='Stop'; New-Item -ItemType Junction "
                        "-Path $env:SKILL_LINK_DEST -Target $env:SKILL_LINK_SOURCE | Out-Null"],
                       env=env, check=True, capture_output=True, text=True)
    else:
        destination.symlink_to(source, target_is_directory=True)


def unlink_directory(path):
    if not is_link(path):
        raise ValueError(f"Refusing to remove a real directory: {path}")
    if os.name == "nt" and not path.is_symlink():
        path.rmdir()  # Remove only the junction, never its target.
    else:
        path.unlink()


def save_state(path, state):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def status(name, source, destination, state):
    entry = state.get(name)
    if not lexists(destination):
        return "not installed"
    if entry and is_link(destination) and str(destination.resolve()) == entry["target"]:
        if not destination.is_dir():
            return "conflict: broken managed link"
        version = entry.get("fingerprint_version", 1)
        if version not in (1, 2):
            return "conflict: unsupported fingerprint version"
        try:
            current = effective_hash(destination.resolve().parent, name, include_modes=version == 2)
        except (OSError, ValueError):
            return "conflict: modified managed files"
        if current != entry["hash"]:
            return "conflict: modified managed files"
        if version == 1 and os.name != "nt":
            # Old state cannot prove the original permissions. Refresh selected
            # installations from upstream with a backup, never bless local modes.
            return "update available"
        return "current" if current == effective_hash(source, name) else "update available"
    if destination.is_dir():
        try:
            same = fingerprint(destination) == fingerprint(source / name)
            return "unmanaged: " + ("current" if same else "update available")
        except (OSError, ValueError):
            pass
    return "conflict: unmanaged or broken path"


def install(name, source, destination, store, state, state_path, adopt=False):
    previous = status(name, source, destination, state)
    if previous == "current":
        return
    if previous.startswith("conflict:") or (previous.startswith("unmanaged:") and not adopt):
        raise ValueError(f"{name}: {previous}; preserved (use --adopt for intact unmanaged installs)")
    if lexists(destination) and not is_link(destination):
        if any((p / ".git").exists() for p in (destination, *destination.parents)):
            raise ValueError(f"{name}: destination belongs to a Git checkout; use a separate --dest")
    # Each selected skill gets an independent bundle; sibling resources stay coherent
    # without activating other skills or silently updating unselected installations.
    bundle = store / "versions" / uuid.uuid4().hex
    bundle.mkdir(parents=True)
    for skill in catalog(source):
        fingerprint(source / skill)
        shutil.copytree(source / skill, bundle / skill)
    target = bundle / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    replacement = destination.parent / (".install-" + uuid.uuid4().hex)
    link_directory(target, replacement)
    backup = None
    old_state = dict(state)
    try:
        if lexists(destination):
            # Same-volume backup outside Codex's skill search directory. Never delete it.
            backup = destination.parent.parent / ".codex-skills-backups" / uuid.uuid4().hex / name
            backup.parent.mkdir(parents=True)
            os.rename(destination, backup)
        os.rename(replacement, destination)
        state[name] = {"target": str(target.resolve()), "hash": effective_hash(bundle, name),
                       "fingerprint_version": 2}
        save_state(state_path, state)
    except BaseException:
        if lexists(destination) and is_link(destination) and destination.resolve() == target.resolve():
            unlink_directory(destination)
        if backup:
            os.rename(backup, destination)
        state.clear()
        state.update(old_state)
        raise
    finally:
        if lexists(replacement):
            unlink_directory(replacement)
    if backup:
        print(f"  Previous installation preserved: {backup}")


def select_skills(names, states):
    while True:
        choice = input("Skills (numbers/names separated by commas, a=all, u=updates, q=quit): ").strip()
        if choice.lower() in ("", "q"):
            return []
        if choice.lower() == "a":
            return names
        if choice.lower() == "u":
            return [n for n in names if states[n] == "update available"]
        chosen = []
        for token in re.split(r"[,\s]+", choice):
            name = names[int(token) - 1] if token.isdigit() and 1 <= int(token) <= len(names) else token
            if name not in names:
                print(f"Unknown selection: {token}")
                break
            if name not in chosen:
                chosen.append(name)
        else:
            return chosen


def main(argv=None):
    default_dest, default_store, codex_home, evidence = locations()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=default_dest, help="override user skill directory")
    parser.add_argument("--store", type=Path, default=default_store, help="managed versions and state")
    parser.add_argument("--source", type=Path, help="explicit local source (offline testing; does not fetch main)")
    parser.add_argument("--skills", nargs="+", help="noninteractive skill names")
    parser.add_argument("--list", action="store_true", help="fetch/check only; do not install")
    parser.add_argument("--adopt", action="store_true", help="back up intact unmanaged installations before replacing")
    args = parser.parse_args(argv)
    destination, store = args.dest.expanduser().absolute(), args.store.expanduser().absolute()
    if destination.resolve() == store.resolve() or destination.resolve() in store.resolve().parents:
        parser.error("--store must be outside the skill discovery directory")
    print(f"Platform: {platform.system()} ({platform.release()})")
    print("\n".join(evidence) if evidence else "Codex not detected; preparing skills for this user is supported.")
    print(f"Skills: {destination}\nManaged content: {store}")
    legacy = codex_home / "skills"
    if legacy.is_dir() and legacy.resolve() != destination.resolve():
        print(f"Legacy/custom skill directory detected: {legacy} (use --dest to target it explicitly)")
    with tempfile.TemporaryDirectory(prefix="codex-skills-download-") as temporary:
        if args.source:
            source, revision = args.source.expanduser().resolve(), "explicit local source; main not checked"
        else:
            source, revision = fetch_main(Path(temporary))
        print(f"Source: {revision}")
        names = catalog(source)
        if not names:
            raise ValueError("Source contains no top-level skills")
        # Include destination identity so separate custom destinations do not share state.
        key = hashlib.sha256(str(destination.resolve()).encode()).hexdigest()[:16]
        state_path = store / f"state-{key}.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        states = {n: status(n, source, destination / n, state) for n in names}
        for index, name in enumerate(names, 1):
            print(f"{index:2}. {name:28} {states[name]}")
        if args.list:
            return 0
        selected = args.skills if args.skills is not None else select_skills(names, states)
        if any(n not in names for n in selected):
            raise ValueError("Unknown skill name; use --list to see available skills")
        if not selected:
            return 0
        if "improve-skills" in names and "improve-skills" not in selected:
            print("Including improve-skills: shared observation helper required by these skills.")
            selected = ["improve-skills", *selected]
        store.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects independent installer processes sharing this store.
        lock = store / "install.lock"
        handle = lock.open("x")
        try:
            with handle:
                # Refresh after acquiring the lock; a previous process may have finished.
                state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
                for name in dict.fromkeys(selected):
                    adopt = args.adopt
                    if states[name].startswith("unmanaged:") and not args.skills and not adopt:
                        adopt = input(f"Back up and replace unmanaged {name}? [y/N]: ").strip().lower() == "y"
                    install(name, source, destination / name, store, state, state_path, adopt)
                    print(f"Ready: {name}")
        finally:
            lock.unlink()
    print("Done. Restart Codex if the selected skills do not appear.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError, EOFError) as error:
        print(f"Installer stopped: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr.strip(), file=sys.stderr)
        sys.exit(1)
