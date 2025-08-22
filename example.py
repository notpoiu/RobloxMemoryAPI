from robloxmemoryapi import RobloxGameClient

# Create a client instance
client = RobloxGameClient()
# client = RobloxGameClient(pid=2398) # PID is also possible

# Get the client's data model
game = client.DataModel

if game.failed:
    print("Failed to get data model")
    exit()

# Print some info about the game
print("RobloxMemoryAPI Demo:")
print("A External Roblox Memory Reader")
print("==============================")
print("PlaceID:", game.PlaceId)
print("GameID:", game.GameId)
print("JobId:", game.JobId)
print("==============================")
print("Player Name:", game.Players.LocalPlayer.Name)
print("Player Character Parent:", game.Players.LocalPlayer.Character.Parent.Name)
print("Player Count:", len(game.Players.GetPlayers()))
print("==============================")