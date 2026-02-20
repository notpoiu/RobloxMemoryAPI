import requests

BASE_URL = "https://imtheo.lol/Offsets"

# Offsets
OffsetsRequest = requests.get(f"{BASE_URL}/Offsets.json")

try:
    Offsets = OffsetsRequest.json()["Offsets"]
except:
    Offsets = {}

# FFlag offsets (lazily loaded)
_fflag_data = None
_fflag_offsets = None

def get_fflag_offsets() -> dict:
    global _fflag_data, _fflag_offsets
    if _fflag_data is None:
        resp = requests.get(f"{BASE_URL}/FFlags.json")
        resp.raise_for_status()
        _fflag_data = resp.json()
        _fflag_offsets = _fflag_data["FFlagOffsets"]["FFlags"]
    return _fflag_offsets
