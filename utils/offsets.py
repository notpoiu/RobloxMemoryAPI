import json, requests

Offsets = {}
def ParseOffsets(*DataSources):
    for _, Data in enumerate(DataSources, start=1):
        for OffsetName in Data:
            try:
                FormattedOffsetName = OffsetName.replace(" ", "")
                OffsetHexadecimalValue = Data[OffsetName]

                Offsets[FormattedOffsetName] = int(OffsetHexadecimalValue, 16)
            except (ValueError, TypeError):
                pass

OffsetsRequest = requests.get("https://offsets.ntgetwritewatch.workers.dev/offsets.json")

try:
    LoadedOffsetsRequest = requests.get("https://raw.githubusercontent.com/notpoiu/RobloxMemoryAPI/refs/heads/main/data/offsets.json")
    LoadedOffsetsRequest.raise_for_status()

    LoadedOffsets = LoadedOffsetsRequest.json()
except:
    
    try:
        with open("data/offsets.json", "r") as f:
            LoadedOffsets = json.load(f)
            f.close()
    except:
        # TODO: update ts
        LoadedOffsets = {
            "Text": "0xC10",
            "Character": "0x328",
            "PrimaryPart": "0x268"
        }

ParseOffsets(LoadedOffsets, OffsetsRequest.json())

# CFrame Offsets
RotationMatriciesLengthBytes = 3 * 3 * 4

Offsets["CameraCFrame"] = Offsets["CameraPos"] - RotationMatriciesLengthBytes
Offsets["CFrame"] = Offsets["Position"] - RotationMatriciesLengthBytes