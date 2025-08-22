import requests
import time
import json

OffsetsRequest = requests.get("https://offsets.ntgetwritewatch.workers.dev/offsets.json")
Offsets = OffsetsRequest.json()

for key in Offsets:
    try:
        Offsets[key] = int(Offsets[key], 16)
    except (ValueError, TypeError):
        pass

with open("data/offsets.json", "r") as f:
    LoadedOffsets = json.load(f)
    f.close()

for key in LoadedOffsets:
    Offsets[key] = int(LoadedOffsets[key], 16)

class RBXInstance:
    def __init__(self, address, memory_module):
        self.raw_address = address
        self.memory_module = memory_module

    # props #
    @property
    def parent_address(self):
        return self.raw_address + Offsets["Parent"]

    @property
    def Parent(self):
        parent_pointer = int.from_bytes(self.memory_module.read(self.raw_address + Offsets["Parent"], 8), 'little')
        return RBXInstance(parent_pointer, self.memory_module)
    
    @property
    def Name(self):
        name_address_pointer = self.raw_address + Offsets["Name"]
        name_address = int.from_bytes(self.memory_module.read(name_address_pointer, 8), 'little')
        return self.memory_module.read_string(name_address)
    
    @property
    def ClassName(self):
        class_descriptor_address = int.from_bytes(
            self.memory_module.read(self.raw_address + Offsets["ClassDescriptor"], 8),
            'little'
        )
        class_name_address = int.from_bytes(
            self.memory_module.read(class_descriptor_address + Offsets["ClassDescriptorToClassName"], 8),
            'little'
        )
        return self.memory_module.read_string(class_name_address)

    # frame properties #
    @property
    def Position(self):
        try:
            x = self.memory_module.read_float(self.raw_address + Offsets["FramePositionX"])
            x_offset = self.memory_module.read_int(self.raw_address + Offsets["FramePositionOffsetX "])

            y = self.memory_module.read_float(self.raw_address + Offsets["FramePositionY"])
            y_offset = self.memory_module.read_int(self.raw_address + Offsets["FramePositionOffsetY"])

            return (x, x_offset, y, y_offset)
        except (KeyError, OSError) as e:
            print(f"Error reading position: {e}")
            return (0.0, 0, 0.0, 0)

    @property
    def Size(self):
        try:
            x = self.memory_module.read_float(self.raw_address + Offsets["FrameSizeX"])
            y = self.memory_module.read_float(self.raw_address + Offsets["FrameSizeY"])
            return (x, y)
        except (KeyError, OSError) as e:
            print(f"Error reading position: {e}")
            return (0.0, 0.0)

    """@property
    def ScreenPosition(self):
        udim2_x_scale, udim2_y_scale, udim2_x_offset, udim2_y_offset = self.Position
        
        real_x = (udim2_x_scale * SCREEN_WIDTH) + udim2_x_offset
        real_y = (udim2_y_scale * SCREEN_HEIGHT) + udim2_y_offset

        return (real_x, real_y)"""

    # XXXXValue props #
    @property
    def Value(self):
        classname = self.ClassName 
        if classname == "StringValue":
            return self.memory_module.read_string(self.raw_address + Offsets["Value"])
        
        elif classname == "IntValue":
            return self.memory_module.read_int(self.raw_address + Offsets["Value"])
        
        elif classname == "NumberValue":
            return self.memory_module.read_double(self.raw_address + Offsets["Value"])
        
        return None
    
    # text props #
    @property
    def Text(self):
        classname = self.ClassName 
        if classname == "TextLabel":
            return self.memory_module.read_string(self.raw_address + Offsets["Text"])
        
        return None
    
    # functions #
    def GetChildren(self):
        children = []
        children_pointer = int.from_bytes(self.memory_module.read(self.raw_address + Offsets["Children"], 8), 'little')
        
        if children_pointer == 0:
            return children
        
        children_start = int.from_bytes(self.memory_module.read(children_pointer, 8), 'little')
        children_end = int.from_bytes(self.memory_module.read(children_pointer + Offsets["ChildrenEnd"], 8), 'little')

        for child_address in range(children_start, children_end, 0x10):
            child_pointer_bytes = self.memory_module.read(child_address, 8)
            child_pointer = int.from_bytes(child_pointer_bytes, 'little')
            
            if child_pointer != 0:
                children.append(RBXInstance(child_pointer, self.memory_module))
        
        return children

    def FindFirstChild(self, name, recursive=False):
        try:
            children = self.GetChildren()
            for child in children:
                if child.Name == name:
                    return child
            
            if recursive:
                for child in children:
                    found_descendant = child.FindFirstChild(name, recursive=True)
                    if found_descendant:
                        return found_descendant
        except: pass

        return None
    
    def WaitForChild(self, name, memoryhandler, timeout=5):
        start = time.time()
        child = None

        while time.time() - start < timeout:
            child = self.FindFirstChild(name)
            if child is not None: break
            if not (memoryhandler.game and not memoryhandler.game.failed): break
            time.sleep(0.1)

        return child
    
# Service #
class ServiceBase:
    def __init__(self):
        self.instance = None
        self.failed = False

    # expose instance functions #
    def __getattr__(self, name):
        # instance #
        if self.instance is not None:
            return getattr(self.instance, name)
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

class DataModel(ServiceBase):
    def __init__(self, memory_module):
        super().__init__()
        self.memory_module = memory_module

        self.error = None
        try:
            fake_dm_pointer_offset = Offsets["FakeDataModelPointer"]
            fake_dm_pointer_addr = memory_module.base + fake_dm_pointer_offset
            fake_dm_pointer_val = int.from_bytes(memory_module.read(fake_dm_pointer_addr, 8), 'little')

            dm_to_datamodel_offset = Offsets["FakeDataModelToDataModel"]
            datamodel_addr_ptr = fake_dm_pointer_val + dm_to_datamodel_offset
            datamodel_addr = int.from_bytes(memory_module.read(datamodel_addr_ptr, 8), 'little')

            datamodel_instance = RBXInstance(datamodel_addr, memory_module)
            if datamodel_instance.Name != "Ugc":
                self.failed = True
            else:
                self.instance = datamodel_instance
        except (KeyError, OSError) as e:
            self.error = e
            self.failed = True

    @property
    def PlaceId(self):
        return self.memory_module.read_long(self.raw_address + Offsets["PlaceId"])

    @property
    def GameId(self):
        return self.memory_module.read_long(self.raw_address + Offsets["GameId"])

    @property
    def JobId(self):
        return self.memory_module.read_string(self.raw_address + Offsets["JobId"])

    @property
    def Players(self):
        return PlayersService(self.memory_module, self)

    # class functions #
    def GetService(self, name):
        if self.failed: return

        for instance in self.instance.GetChildren():
            if instance.ClassName == name:
                return instance

        return None

class PlayerClass(RBXInstance):
    def __init__(self, memory_module, player: RBXInstance):
        super().__init__(player.raw_address, memory_module)
        self.memory_module = memory_module

        try:
            if player.ClassName != "Player":
                self.failed = True
            else:
                self.instance = player
        except (KeyError, OSError):
            self.failed = True

    # props #
    @property
    def Character(self) -> RBXInstance | None:
        addr = int.from_bytes(self.memory_module.read(self.instance.raw_address + Offsets["Character"], 8), 'little')
        return RBXInstance(addr, self.memory_module)

class PlayersService(ServiceBase):
    def __init__(self, memory_module, game: DataModel):
        super().__init__()
        self.memory_module = memory_module

        try:
            players_instance: RBXInstance = game.GetService("Players")
            if players_instance.ClassName != "Players":
                self.failed = True
            else:
                self.instance = players_instance
        except (KeyError, OSError):
            self.failed = True

    # props #
    @property
    def LocalPlayer(self) -> RBXInstance | None:
        if self.failed: return

        addr = int.from_bytes(self.memory_module.read(self.instance.raw_address + Offsets["LocalPlayer"], 8), 'little')
        return PlayerClass(self.memory_module, RBXInstance(addr, self.memory_module))

    def GetPlayers(self):
        players = []

        for instance in self.instance.GetChildren():
            if instance.ClassName == "Player":
                players.append(PlayerClass(self.memory_module, instance))
        
        return players