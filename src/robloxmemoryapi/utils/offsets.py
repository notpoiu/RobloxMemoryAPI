import requests

# Offsets
OffsetsRequest = requests.get("https://imtheo.lol/Offsets/Offsets.json")

# Legacy Offsets
OldOffsetsRequest = requests.get("https://offsets.ntgetwritewatch.workers.dev/offsets.json")
try:
    OldOffsets = OldOffsetsRequest.json()
except:
    OldOffsets = {}

try:
    Offsets = OffsetsRequest.json()["Offsets"]
except:
    Offsets = {}

# Handle non-existant offsets
try:
    Offsets["Camera"]["ViewportSize"] = int(OldOffsets["ViewportSize"], 16)
except:
    Offsets["Camera"]["ViewportSize"] = 0x6AD28F
