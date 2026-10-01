"""Bot personas, writing voices and manipulation techniques, loaded from profiles.toml.

Edit botlab/profiles.toml (or point BOTLAB_PROFILES at your own copy) to change them.
Techniques are drawn from well-documented patterns in disinformation and astroturfing
research; every generated comment is tagged with the ones it uses so the viewer can
teach readers to spot them.
"""

import os
import tomllib
from pathlib import Path

PROFILES_PATH = Path(os.environ.get("BOTLAB_PROFILES") or Path(__file__).with_name("profiles.toml"))


class ProfileError(ValueError):
    pass


def load(path: Path = PROFILES_PATH) -> tuple[dict, list[dict], dict, dict]:
    """Return (settings, personas, voices, techniques), with clear errors for typos."""
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ProfileError(f"{path}: not valid TOML ({e}). Check quotes, commas and brackets.") from e

    voices = dict(data.get("voices", {}))
    techniques = dict(data.get("techniques", {}))
    settings = {"extra_instructions": "", "comments_per_thread": 10, "personas_per_thread": 4}
    settings.update(data.get("settings", {}))
    if not voices or not techniques:
        raise ProfileError(f"{path}: needs at least one entry under [voices] and [techniques].")

    personas, seen = [], set()
    for i, p in enumerate(data.get("persona", []), 1):
        where = f"{path}: persona #{i} ({p.get('id', 'no id')})"
        for field in ("id", "ideology", "style"):
            if not isinstance(p.get(field), str) or not p[field].strip():
                raise ProfileError(f"{where}: missing '{field}'.")
        if p["id"] in seen:
            raise ProfileError(f"{where}: duplicate id.")
        seen.add(p["id"])
        bad = [t for t in p.get("techniques", []) if t not in techniques]
        if bad:
            raise ProfileError(f"{where}: unknown technique(s) {bad}. Use keys from [techniques].")
        if p.get("voice") and p["voice"] not in voices:
            raise ProfileError(f"{where}: unknown voice '{p['voice']}'. Use a key from [voices].")
        personas.append({
            "id": p["id"],
            "ideology": p["ideology"],
            "style": p["style"],
            "positions": list(p.get("positions", [])),
            "favored": list(p.get("techniques", [])),
            "voice": p.get("voice", ""),
        })
    if not personas:
        raise ProfileError(f"{path}: no [[persona]] blocks.")
    return settings, personas, voices, techniques


SETTINGS, PERSONAS, VOICES, TECHNIQUES = load()


def persona_by_id(pid: str) -> dict:
    for p in PERSONAS:
        if p["id"] == pid:
            return p
    raise KeyError(pid)
