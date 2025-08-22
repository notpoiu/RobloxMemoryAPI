# RobloxMemoryAPI

A Python library for interacting with the roblox game client.

Made by [upio](https://github.com/notpoiu), [mstudio45](https://github.com/mstudio45), and [master oogway](https://github.com/ActualMasterOogway) and used in the [Dig Macro external mode](https://github.com/mstudio45/digmacro).

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
