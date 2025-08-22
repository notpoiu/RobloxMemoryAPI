# RobloxMemoryAPI

A Python library that is _hopefully stealthy_ and abstracts externally reading memory to get datamodel information from the roblox game client.

This was made by [upio](https://github.com/notpoiu), [mstudio45](https://github.com/mstudio45), and [Master Oogway](https://github.com/ActualMasterOogway) and created for the [Dig Macro](https://github.com/mstudio45/digmacro) project (external mode and not the computer vision mode).

## Installation

Clone the repository and install the required dependencies:

```bash
git clone https://github.com/notpoiu/RobloxMemoryAPI.git
cd RobloxMemoryAPI
pip install -r requirements.txt
```

## Usage

Import the library and create a client instance:

```python
from robloxmemoryapi import RobloxGameClient

client = RobloxGameClient()
```

Access the data model:

```python
game = client.DataModel
```

Get the local player's name:

```python
print("Player Name:", game.Players.LocalPlayer.Name)
```

## License

This project is licensed under the MIT License.
