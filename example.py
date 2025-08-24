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

# 1.0511624813079834, 2.9980251789093018, -1.8010846376419067
print("Player Position:", LocalPlayer.Character.HumanoidRootPart.Position)
print("Player HRP Size:", LocalPlayer.Character.HumanoidRootPart.Size)