import requests

# Offsets
OffsetsRequest = requests.get("https://imtheo.lol/Offsets/Offsets.json")

# Legacy Offsets
OldOffsetsRequest = requests.get("https://offsets.ntgetwritewatch.workers.dev/offsets.json")
OldOffsets = OldOffsetsRequest.json()

Offsets = OffsetsRequest.json()["Offsets"]

# Handle non-existant offsets
Offsets["Camera"]["ViewportSize"] = int(OldOffsets["ViewportSize"], 16)