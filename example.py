from robloxmemoryapi import RobloxGameClient, RobloxRandom
from robloxmemoryapi.utils.rbx.datastructures import UDim2
import platform

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

LocalPlayer = game.Players.LocalPlayer

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
print("Player HRP Parent:", LocalPlayer.Character.PrimaryPart.GetFullName())
print("Health:", LocalPlayer.Character.Humanoid.Health, LocalPlayer.Character.Humanoid.MaxHealth)
print("Player Count:", len(game.Players.GetPlayers()))
print("==============================")
print("CurrentCamera CFrame:", game.Workspace.CurrentCamera.CFrame)
print("CurrentCamera FOV:", game.Workspace.CurrentCamera.FieldOfView)
print("CurrentCamera ViewportSize:", game.Workspace.CurrentCamera.ViewportSize)

# Write to the client's memory (kills player)
#LocalPlayer.Character.Humanoid.Health = 0

client.close()