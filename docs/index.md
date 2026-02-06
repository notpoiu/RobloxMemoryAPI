# RobloxMemoryAPI

RobloxMemoryAPI is a Python library for externally reading and (optionally) writing Roblox client memory to access the DataModel and its instances.

## Requirements

- Windows only. The memory module relies on Windows APIs.
- Roblox client running. By default it targets `RobloxPlayerBeta.exe`.
- Python 3.9+.
- Internet access on import to fetch current offsets.

## Install

```bash
pip install robloxmemoryapi
```

Editable install from source:

```bash
pip install -e .
```

## Quickstart

```python
from robloxmemoryapi import RobloxGameClient

client = RobloxGameClient()
if client.failed:
    raise RuntimeError("Failed to attach to Roblox.")

game = client.DataModel
print("PlaceId:", game.PlaceId)
print("JobId:", game.JobId)
print("Loaded:", game.IsLoaded())

client.close()
```

## Writing To Memory

Writing requires passing `allow_write=True` when creating the client. This requests additional process rights and can fail or be blocked depending on your environment.

```python
from robloxmemoryapi import RobloxGameClient

client = RobloxGameClient(allow_write=True)
if client.failed:
    raise RuntimeError("Failed to attach to Roblox.")

game = client.DataModel
# Example: change workspace gravity
if game.Workspace is not None:
    game.Workspace.Gravity = 80.0

client.close()
```

## Navigating Instances

Instances support attribute-style access to find children by name, and utility methods for traversal.

```python
workspace = game.Workspace
part = workspace.FindFirstChild("Part", recursive=True)
if part:
    print(part.ClassName, part.Name)
```

## Auto Refresh

The DataModel can change when the client switches between the home screen and a game. Auto refresh keeps the reference updated and notifies you.

```python
from robloxmemoryapi import RobloxGameClient

client = RobloxGameClient()
game = client.DataModel

def on_refresh(instance):
    if game.is_lua_app():
        print("LuaApp / home screen")
    else:
        print("In-game", game.PlaceId)

game.bind_to_refresh(on_refresh, invoke_if_ready=True)
```

## Notes And Limitations

- Offsets are fetched at import time from remote sources. If those sources are unavailable or Roblox updates, values can be wrong and reads may fail.
- Many properties are class-specific. If a property is not supported by the underlying instance, the library returns `None` or raises an `AttributeError`.
- Use `client.close()` when finished to release the process handle.
