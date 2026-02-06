# RobloxMemoryAPI

[A Python library](https://pypi.org/project/robloxmemoryapi/) that is _hopefully stealthy_ and abstracts externally reading and writing memory to get datamodel information from the roblox game client.

This was made by [upio](https://github.com/notpoiu), [mstudio45](https://github.com/mstudio45), and [Master Oogway](https://github.com/ActualMasterOogway) and created for the [Dig Macro](https://github.com/mstudio45/digmacro) project (external mode and not the computer vision mode).

## Installation

PyPI:

```bash
pip install robloxmemoryapi
```

Development (editable install from source):

```bash
pip install -e .
```

## Documentation

- [Overview](https://github.com/notpoiu/RobloxMemoryAPI/wiki)
- [API Reference](https://github.com/notpoiu/RobloxMemoryAPI/wiki/API-Reference)
- [Data Types](https://github.com/notpoiu/RobloxMemoryAPI/wiki/Data-Types)

## Usage

An example script can be found in [example.py](https://raw.githubusercontent.com/notpoiu/RobloxMemoryAPI/refs/heads/main/example.py). If running from the repo, use the editable install above so `import robloxmemoryapi` resolves the `src` package.

Import the library and create a client instance:

```python
from robloxmemoryapi import RobloxGameClient

client = RobloxGameClient()
```

To request write access (e.g. to patch values), pass `allow_write=True` when creating the client.

```python
client = RobloxGameClient(allow_write=True)
```

Access the data model:

```python
game = client.DataModel
```

Kill the local player:

```python
# (requires allow_write=True when creating the client)
# allow_write may be detected by roblox. It is disabled by default.
game.Players.LocalPlayer.Character.Humanoid.Health = 0
```

Get the local player's name:

```python
print("Player Name:", game.Players.LocalPlayer.Name)
```

## License

This project is licensed under the MIT License.
