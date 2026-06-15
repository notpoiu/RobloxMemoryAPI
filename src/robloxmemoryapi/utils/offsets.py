import requests
import platform

from .._version import USER_AGENT
from .macos import roblox_architecture

IMTHEO_BASE_URL = "https://offsets.imtheo.lol"
MACOS_OFFSETS_BASE = "https://offsets.upio.dev/rbxl/macOS"
REQUEST_HEADERS = {"User-Agent": USER_AGENT}

_macos_roblox_architecture = roblox_architecture


def _fetch_macos_offsets() -> dict:
    arch = roblox_architecture()
    version = requests.get(
        f"{MACOS_OFFSETS_BASE}/latest.txt",
        headers=REQUEST_HEADERS,
    ).text.strip()
    response = requests.get(
        f"{MACOS_OFFSETS_BASE}/{arch}/{version}/offsets.json",
        headers=REQUEST_HEADERS,
    )
    return response.json()["Offsets"]


def _load_offsets() -> dict:
    if platform.system() == "Darwin":
        try:
            return _fetch_macos_offsets()
        except Exception:
            return {}

    try:
        response = requests.get(
            f"{IMTHEO_BASE_URL}/Offsets.json",
            headers=REQUEST_HEADERS,
        )
        return response.json()["Offsets"]
    except Exception:
        return {}


Offsets = _load_offsets()

# FFlag offsets (lazily loaded)
_fflag_data = None
_fflag_offsets = None

def get_fflag_offsets() -> dict:
    global _fflag_data, _fflag_offsets
    if _fflag_data is None:
        resp = requests.get(f"{IMTHEO_BASE_URL}/FFlags.json", headers=REQUEST_HEADERS)
        resp.raise_for_status()
        _fflag_data = resp.json()
        _fflag_offsets = _fflag_data["FFlagOffsets"]["FFlags"]
    return _fflag_offsets
