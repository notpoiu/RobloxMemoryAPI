from robloxmemoryapi import RobloxGameClient

# Create a client instance
client = RobloxGameClient()
# client = RobloxGameClient(pid=2398) # PID is also possible

# Get the client's data model
game = client.DataModel

if game.failed:
    print("Failed to get data model")
    exit()

LocalPlayer = game.Players.LocalPlayer

# Print some info about the game
print("RobloxMemoryAPI Demo:")
print("A External Roblox Memory Reader")
print("==============================")
print("PlaceID:", game.PlaceId)
print("GameID:", game.GameId)
print("JobId:", game.JobId)
print("Loaded:", game.IsLoaded())
print("==============================")
print("Player Name:", LocalPlayer.Name)
print("Player Character Parent:", LocalPlayer.Character.HumanoidRootPart.GetFullName())
print("Player Count:", len(game.Players.GetPlayers()))
print("==============================")
print(f"CurrentCamera Position: {game.Workspace.CurrentCamera.Position}")
print(f"CurrentCamera CFrame: {game.Workspace.CurrentCamera.CFrame}")