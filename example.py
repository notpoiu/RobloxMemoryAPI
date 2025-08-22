from robloxmemoryapi import RobloxGameClient

client = RobloxGameClient()
game = client.DataModel

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