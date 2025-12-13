from robloxmemoryapi import RobloxGameClient, RobloxRandom
from robloxmemoryapi.utils.rbx.datastructures import UDim2
import platform
import hashlib

## Random Class ##
Test = RobloxRandom(5)
print("Roblox Random Demo")
print("math.random() with seed '5' result:", Test.NextNumber())

## Memory Reading ###
if platform.system() != "Windows":
    print("Sorry! The memory reading module only works in windows, trying to access it will cause client.failed = True")
    exit()

# Create a client instance
# allow_write is by default False, but can be enabled by passing True
client = RobloxGameClient(allow_write=True)
# client = RobloxGameClient(pid=2398) # PID is also possible

if client.failed:
    print("Failed to get data model")
    exit()

# Get the client's data model
game = client.DataModel

print("")

# Refresh hooks let you react when Roblox swaps between home screen and game.
def on_refresh(datamodel):
    if game.is_lua_app():
        print("[Refresh] You are now in the Roblox Home Screen.")
    else:
        print(f"[Refresh] You are now in-game (PlaceId: {game.PlaceId})")

# Register callback (optional invoke to run immediately with the current model).
game.bind_to_refresh(on_refresh, invoke_if_ready=True)

LocalPlayer = game.Players.LocalPlayer

print("")

# Print some info about the game
print("RobloxMemoryAPI Demo:")
print("An External Roblox Memory Reader")
print("==============================")
print("PlaceID:", game.PlaceId)
print("GameID:", game.GameId)
print("JobId:", game.JobId)
print("Loaded:", game.IsLoaded())
print("==============================")
print("Player Name:", LocalPlayer.Name, f"({LocalPlayer.DisplayName} | userid: {LocalPlayer.UserId})")

# LuaApp = Roblox Home Screen
if not game.is_lua_app():
    print("Player HRP Parent:", LocalPlayer.Character.PrimaryPart.GetFullName())
    print("Health:", LocalPlayer.Character.Humanoid.Health, LocalPlayer.Character.Humanoid.MaxHealth)
    print("Player Count:", len(game.Players.GetPlayers()))
    print("==============================")
    print("CurrentCamera CFrame:", game.Workspace.CurrentCamera.CFrame)
    print("CurrentCamera FOV:", game.Workspace.CurrentCamera.FieldOfView)
    print("CurrentCamera ViewportSize:", game.Workspace.CurrentCamera.ViewportSize)

    # Bytecode operations (READING)
    PlayerModule = LocalPlayer.PlayerScripts.PlayerModule
    if PlayerModule is not None and PlayerModule.Bytecode is not None:
        print("PlayerModule Script Hash:", hashlib.sha384(PlayerModule.RawBytecode).hexdigest())

    # Bytecode write operations (WRITING)
    if os.path.exists("misc/BytecodeToWrite.luac"):
        with open("misc/BytecodeToWrite.luac", "rb") as f:
            BytecodeToWrite = f.read()
        
        PlayerModule.Bytecode = BytecodeToWrite
        print("Set bytecode of PlayerModule to BytecodeToWrite.luac")
    else:
        print("misc/BytecodeToWrite.luac not found")
else:
    print("Roblox is not in a game. No preview data available.")

# Write to the client's memory (kills player)
#LocalPlayer.Character.Humanoid.Health = 0

print("")

input("Press Enter to close.\n\n")
client.close()
