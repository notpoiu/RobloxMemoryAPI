from ..offsets import *
import time, math
from utils.rbx.datastructures import *

# Normal Classes #
class RBXInstance:
    def __init__(self, address, memory_module):
        self.raw_address = address
        self.memory_module = memory_module

    def __eq__(self, value):
        return value.raw_address == self.raw_address
    
    def __getattr__(self, key):
        return self.FindFirstChild(key)

    # utilities #
    @property
    def primitive_address(self):
        part_primitive_pointer = self.raw_address + Offsets["Primitive"]
        part_primitive = int.from_bytes(self.memory_module.read(part_primitive_pointer, 8), 'little')
        return part_primitive

    # props #
    @property
    def Parent(self):
        parent_pointer = int.from_bytes(self.memory_module.read(self.raw_address + Offsets["Parent"], 8), 'little')
        instance = RBXInstance(parent_pointer, self.memory_module)

        try:
            thing = instance.ClassName
        except Exception as e:
            return None

        return instance
    
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
    
    @property
    def CFrame(self):
        className = self.ClassName

        RotationMatriciesLength = 3 * 3

        if "part" in className.lower():
            # extra 3 for position matrix
            CFrameData = self.memory_module.read_floats(self.primitive_address + Offsets["CFrame"], RotationMatriciesLength + 3)
        elif className == "Camera":
            # * 4 because 1 float is 4 bytes
            CameraCFrameOffset = Offsets["CameraPos"] - RotationMatriciesLength * 4
            CFrameData = self.memory_module.read_floats(self.raw_address + CameraCFrameOffset, RotationMatriciesLength + 3)
        else:
            return None
        
        RightVectorData = CFrameData[0:3]
        UpVectorData = CFrameData[3:6]
        LookVectorData = CFrameData[6:9]
        PositionData = CFrameData[9:12]

        return CFrame(
            Vector3(*PositionData),
            Vector3(*RightVectorData),
            Vector3(*UpVectorData),
            Vector3(*LookVectorData)
        )


    @property
    def Position(self):
        className = self.ClassName
        if "part" in className.lower():
            position_vector3 = self.memory_module.read_floats(self.primitive_address + Offsets["Position"], 3)
            return Vector3(*position_vector3)
        elif className == "Camera":
            position_vector3 = self.memory_module.read_floats(self.raw_address + Offsets["CameraPos"], 3)
            return Vector3(*position_vector3)
        else:
            try:
                x = self.memory_module.read_float(self.raw_address + Offsets["FramePositionX"])
                x_offset = self.memory_module.read_int(self.raw_address + Offsets["FramePositionOffsetX "])

                y = self.memory_module.read_float(self.raw_address + Offsets["FramePositionY"])
                y_offset = self.memory_module.read_int(self.raw_address + Offsets["FramePositionOffsetY"])

                return UDim2(x, x_offset, y, y_offset)
            except (KeyError, OSError) as e:
                print(f"Error reading position: {e}")
                return (0.0, 0, 0.0, 0)

    @property
    def Size(self):
        if "part" in self.ClassName.lower():
            size_vector3 = self.memory_module.read_floats(self.primitive_address + Offsets["PartSize"], 3)
            return Vector3(*size_vector3)
        else:
            try:
                x = self.memory_module.read_float(self.raw_address + Offsets["FrameSizeX"])
                y = self.memory_module.read_float(self.raw_address + Offsets["FrameSizeY"])
                return (x, y)
            except (KeyError, OSError) as e:
                print(f"Error reading position: {e}")
                return (0.0, 0.0)

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
        
        elif classname == "BoolValue":
            return self.memory_module.read_bool(self.raw_address + Offsets["Value"])
        
        elif classname == "ObjectValue":
            object_pointer = self.raw_address + Offsets["Value"]
            object_address = int.from_bytes(self.memory_module.read(object_pointer, 8), 'little')

            return RBXInstance(object_address, self.memory_module)
        
        return None
    
    # text props #
    @property
    def Text(self):
        if "text" in self.ClassName.lower():
            return self.memory_module.read_string(self.raw_address + Offsets["Text"])
        
        return None

    # humanoid props #
    @property
    def WalkSpeed(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(self.raw_address + Offsets["WalkSpeed"])

    @property
    def JumpPower(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(self.raw_address + Offsets["JumpPower"])
        
    @property
    def Health(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(self.raw_address + Offsets["Health"])

    @property
    def MaxHealth(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(self.raw_address + Offsets["MaxHealth"])

    # model props #
    @property
    def PrimaryPart(self):
        if self.ClassName != "Model":
            return None
        
        parent_pointer = int.from_bytes(self.memory_module.read(self.raw_address + Offsets["PrimaryPart"], 8), 'little')
        instance = RBXInstance(parent_pointer, self.memory_module)

        try:
            thing = instance.ClassName
        except Exception as e:
            return None

        return instance
    
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

    def GetFullName(self):
        if self.ClassName == "DataModel":
            return self.Name

        ObjectPointer = self
        ObjectPath = self.Name

        while True:
            if ObjectPointer.Parent.ClassName == "DataModel":
                break
            
            ObjectPointer = ObjectPointer.Parent
            ObjectPath = f"{ObjectPointer.Name}." + ObjectPath
        
        return ObjectPath

    def GetDescendants(self):
        descendants = []
        for child in self.GetChildren():
            descendants.append(child)
            descendants.extend(child.GetDescendants())
        return descendants

    def FindFirstChildOfClass(self, classname):
        for child in self.GetChildren():
            if child.ClassName == classname:
                return child
        return None

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
    
    @property
    def DisplayName(self):
        return self.memory_module.read_string(self.raw_address + Offsets["DisplayName"])

    @property
    def UserId(self):
        return self.memory_module.read_long(self.raw_address + Offsets["UserId"])

class CameraClass(RBXInstance):
    def __init__(self, memory_module, camera: RBXInstance):
        super().__init__(camera.raw_address, memory_module)
        self.memory_module = memory_module

        try:
            if camera.ClassName != "Camera":
                self.failed = True
            else:
                self.instance = camera
        except (KeyError, OSError):
            self.failed = True

    # props #
    @property
    def FieldOfView(self):
        return self.FieldOfViewRadians * (180/math.pi)
    
    @property
    def FieldOfViewRadians(self):
        return self.memory_module.read_float(self.raw_address + Offsets["FOV"])
    
    @property
    def ViewportSize(self):
        SizeData = self.memory_module.read_floats(self.raw_address + Offsets["ViewportSize"], 2)
        return Vector2(*SizeData)

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
        
        return self.instance.FindFirstChild(name)

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

    @property
    def Workspace(self):
        return WorkspaceService(self.memory_module, self)

    # class functions #
    def GetService(self, name):
        if self.failed: return

        for instance in self.instance.GetChildren():
            if instance.ClassName == name:
                return instance

        return None

    # Stuff
    def IsLoaded(self):
        return self.memory_module.read_bool(self.raw_address + Offsets["GameLoaded"])

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

class WorkspaceService(ServiceBase):
    def __init__(self, memory_module, game: DataModel):
        super().__init__()
        self.memory_module = memory_module

        try:
            workspace_instance: RBXInstance = game.GetService("Workspace")
            if workspace_instance.ClassName != "Workspace":
                self.failed = True
            else:
                self.instance = workspace_instance
        except (KeyError, OSError):
            self.failed = True

    # props #
    @property
    def CurrentCamera(self) -> CameraClass | None:
        if self.failed: return

        addr = int.from_bytes(self.memory_module.read(self.instance.raw_address + Offsets["Camera"], 8), 'little')
        return CameraClass(self.memory_module, RBXInstance(addr, self.memory_module))

    def GetPlayers(self):
        players = []

        for instance in self.instance.GetChildren():
            if instance.ClassName == "Player":
                players.append(PlayerClass(self.memory_module, instance))
        
        return players
