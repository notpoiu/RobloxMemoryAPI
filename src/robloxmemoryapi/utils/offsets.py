import requests
import platform

from .._version import USER_AGENT
from .macos import roblox_architecture

IMTHEO_BASE_URL = "https://offsets.imtheo.lol"
MAC_ARM_OFFSETS_URL = "https://offsets.upio.dev/rbxl-macarm-latest.json"
MAC_INTEL_OFFSETS_URL = "https://offsets.upio.dev/rbxl-macintel-latest.json"
REQUEST_HEADERS = {"User-Agent": USER_AGENT}

_macos_roblox_architecture = roblox_architecture


def _offsets_url() -> str:
    if platform.system() != "Darwin":
        return f"{IMTHEO_BASE_URL}/Offsets.json"

    if roblox_architecture() == "arm64":
        return MAC_ARM_OFFSETS_URL

    return MAC_INTEL_OFFSETS_URL

# Offsets
OffsetsRequest = requests.get(_offsets_url(), headers=REQUEST_HEADERS)

try:
    Offsets = OffsetsRequest.json()["Offsets"]
except Exception:
    Offsets = {}

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
