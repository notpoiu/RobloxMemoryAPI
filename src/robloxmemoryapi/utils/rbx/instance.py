from ..offsets import *
import time, math
from .datastructures import *

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
    def _ensure_writable(self):
        if not hasattr(self.memory_module, "write"):
            raise RuntimeError("Write operations require a memory module with write support (allow_write=True).")

    @staticmethod
    def _as_vector3(value, context="value"):
        if isinstance(value, Vector3):
            return value
        
        if isinstance(value, (tuple, list)) and len(value) == 3:
            return Vector3(*value)
        
        raise TypeError(f"{context} must be a Vector3 or an iterable of three numbers.")

    @staticmethod
    def _as_vector2(value, context="value"):
        if isinstance(value, Vector2):
            return value
        
        if isinstance(value, (tuple, list)) and len(value) == 2:
            return Vector2(*value)
        
        raise TypeError(f"{context} must be a Vector2 or an iterable of two numbers.")

    @staticmethod
    def _as_udim2(value, context="value"):
        if isinstance(value, UDim2):
            return value
        if isinstance(value, (tuple, list)):
            if len(value) == 4:
                return UDim2(value[0], value[1], value[2], value[3])
            if len(value) == 2:
                x, y = value
                if isinstance(x, UDim) and isinstance(y, UDim):
                    return UDim2(x.Scale, x.Offset, y.Scale, y.Offset)
                if isinstance(x, (tuple, list)) and isinstance(y, (tuple, list)) and len(x) == 2 and len(y) == 2:
                    return UDim2(x[0], x[1], y[0], y[1])
        raise TypeError(f"{context} must be a UDim2 or a compatible iterable.")

    # memory helpers #
    def _write_rbx_string(self, address: int, value: str):
        self._ensure_writable()

        if not isinstance(value, str):
            raise TypeError("value must be a string.")
        
        if address == 0:
            raise ValueError("String address is null; cannot write.")
        
        encoded = value.encode('utf-8')
        if len(encoded) > 15:
            raise ValueError("String too long (max 15 UTF-8 bytes supported for inline Roblox strings).")
        
        current_length = self.memory_module.read_int(address + 0x10)
        if current_length > 15:
            raise ValueError("Existing string is heap allocated; inline overwrite is not supported.")
        
        padded = encoded + b'\x00'
        if len(padded) < 16:
            padded += b'\x00' * (16 - len(padded))
        
        self.memory_module.write(address, padded[:16])
        self.memory_module.write_int(address + 0x10, len(encoded))


    def _read_udim2(self, address: int) -> UDim2:
        if not isinstance(address, int):
            raise TypeError("address must be an int.")

        scale_x = self.memory_module.read_float(address)
        offset_x = self.memory_module.read_int(address + 0x4)
        scale_y = self.memory_module.read_float(address + 0x8)
        offset_y = self.memory_module.read_int(address + 0xC)

        return UDim2(scale_x, offset_x, scale_y, offset_y)
        

    def _write_udim2(self, address: int, value: UDim2):
        value = self._as_udim2(value, "UDim2")

        if not isinstance(value, UDim2):
            raise TypeError("value must be a UDim2.")

        self._ensure_writable()

        self.memory_module.write_float(address, value.X.Scale)
        self.memory_module.write_int(address + 0x4, value.X.Offset)
        
        self.memory_module.write_float(address + 0x8, value.Y.Scale)
        self.memory_module.write_int(address + 0xC, value.Y.Offset)


    # useful pointer stuff #
    @property
    def primitive_address(self):
        part_primitive_pointer = self.raw_address + Offsets["Primitive"]
        part_primitive = int.from_bytes(self.memory_module.read(part_primitive_pointer, 8), 'little')
        return part_primitive
    

    # props #
    @property
    def Parent(self):
        parent_pointer = int.from_bytes(self.memory_module.read(self.raw_address + Offsets["Parent"], 8), 'little')
        if parent_pointer == 0:
            return None
        
        return RBXInstance(parent_pointer, self.memory_module)
    
    @Parent.setter
    def Parent(self, value):
        if value is None:
            target = 0
        elif isinstance(value, RBXInstance):
            target = value.raw_address
        elif isinstance(value, int):
            target = value
        else:
            raise TypeError("Parent must be set to an RBXInstance, int address, or None.")
        self._ensure_writable()
        self.memory_module.write_long(self.raw_address + Offsets["Parent"], target)

    @property
    def Name(self):
        name_address_pointer = self.raw_address + Offsets["Name"]
        name_address = int.from_bytes(self.memory_module.read(name_address_pointer, 8), 'little')
        return self.memory_module.read_string(name_address)
    
    @Name.setter
    def Name(self, value: str):
        self._ensure_writable()
        name_address_pointer = self.raw_address + Offsets["Name"]
        name_address = int.from_bytes(self.memory_module.read(name_address_pointer, 8), 'little')
        self._write_rbx_string(name_address, value)
    
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

        CFrameDataMatriciesLength = 12 # 3x4 matrix

        if "part" in className.lower():
            CFrameData = self.memory_module.read_floats(self.primitive_address + Offsets["CFrame"], CFrameDataMatriciesLength)
        elif className == "Camera":
            CFrameData = self.memory_module.read_floats(self.raw_address + Offsets["CameraCFrame"], CFrameDataMatriciesLength)
        else:
            return None
        
        RightVectorData = get_flat_matrix_column(CFrameData, 0)
        UpVectorData = get_flat_matrix_column(CFrameData, 1)
        LookVectorData = get_flat_matrix_column(CFrameData, 2, invert_values=True)
        PositionData = CFrameData[9:12]

        return CFrame(
            Vector3(*PositionData),
            Vector3(*RightVectorData),
            Vector3(*UpVectorData),
            Vector3(*LookVectorData)
        )

    @CFrame.setter
    def CFrame(self, value: "CFrame"):
        if not isinstance(value, CFrame):
            raise TypeError("CFrame setter expects a CFrame value.")
        self._ensure_writable()

        matrix_data = [
            value.RightVector.X, value.UpVector.X, -value.LookVector.X,
            value.RightVector.Y, value.UpVector.Y, -value.LookVector.Y,
            value.RightVector.Z, value.UpVector.Z, -value.LookVector.Z,
            value.Position.X, value.Position.Y, value.Position.Z
        ]

        className = self.ClassName
        if "part" in className.lower():
            base_address = self.primitive_address + Offsets["CFrame"]
        elif className == "Camera":
            base_address = self.raw_address + Offsets["CameraCFrame"]
        else:
            raise AttributeError("CFrame cannot be written for this instance type.")

        self.memory_module.write_floats(base_address, matrix_data)

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
            return self._read_udim2(self.raw_address + Offsets["FramePositionX"])

    @Position.setter
    def Position(self, value):
        className = self.ClassName
        
        self._ensure_writable()
        if "part" in className.lower():
            vec = self._as_vector3(value, "Position")
            self.memory_module.write_floats(
                self.primitive_address + Offsets["Position"],
                (vec.X, vec.Y, vec.Z)
            )

        elif className == "Camera":
            vec = self._as_vector3(value, "Position")
            self.memory_module.write_floats(
                self.raw_address + Offsets["CameraPos"],
                (vec.X, vec.Y, vec.Z)
            )

        else:
            udim2_value = self._as_udim2(value, "Position")
            self._write_udim2(self.raw_address + Offsets["FramePositionX"], udim2_value)

    @property
    def Velocity(self):
        className = self.ClassName

        if "part" in className.lower():
            velocity_vector3 = self.memory_module.read_floats(self.primitive_address + Offsets["Velocity"], 3)
            return Vector3(*velocity_vector3)
        
        return None

    @Velocity.setter
    def Velocity(self, value):
        className = self.ClassName
        if "part" not in className.lower():
            raise AttributeError("Velocity can only be written for BasePart-derived instances.")
        
        vec = self._as_vector3(value, "Velocity")
        
        self._ensure_writable()
        self.memory_module.write_floats(
            self.primitive_address + Offsets["Velocity"],
            (vec.X, vec.Y, vec.Z)
        )

    @property
    def Size(self):
        if "part" in self.ClassName.lower():
            size_vector3 = self.memory_module.read_floats(self.primitive_address + Offsets["PartSize"], 3)
            return Vector3(*size_vector3)
        else:
            return self._read_udim2(self.raw_address + Offsets["FrameSizeX"])

    @Size.setter
    def Size(self, value):
        self._ensure_writable()
        if "part" in self.ClassName.lower():
            vec = self._as_vector3(value, "Size")
            self.memory_module.write_floats(
                self.primitive_address + Offsets["PartSize"],
                (vec.X, vec.Y, vec.Z)
            )
        else:
            gui_size = self._as_udim2(value, "Size")
            self._write_udim2(self.raw_address + Offsets["FrameSizeX"], gui_size)

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

    @Value.setter
    def Value(self, new_value):
        self._ensure_writable()
        classname = self.ClassName
        value_address = self.raw_address + Offsets["Value"]

        if classname == "StringValue":
            self._write_rbx_string(value_address, str(new_value))
        elif classname == "IntValue":
            self.memory_module.write_int(value_address, int(new_value))
        elif classname == "NumberValue":
            self.memory_module.write_double(value_address, float(new_value))
        elif classname == "BoolValue":
            self.memory_module.write_bool(value_address, bool(new_value))
        elif classname == "ObjectValue":
            if new_value is None:
                target = 0
            elif isinstance(new_value, RBXInstance):
                target = new_value.raw_address
            elif isinstance(new_value, int):
                target = new_value
            else:
                raise TypeError("ObjectValue.Value must be set to an RBXInstance, int address, or None.")
            self.memory_module.write_long(value_address, target)
        else:
            raise AttributeError(f"Writing Value is not supported for class {classname}.")
    
    # text props #
    @property
    def Text(self):
        if "text" in self.ClassName.lower():
            return self.memory_module.read_string(self.raw_address + Offsets["Text"])
        
        return None

    @Text.setter
    def Text(self, value: str):
        if "text" not in self.ClassName.lower():
            raise AttributeError("Text is not available on this instance.")
        self._write_rbx_string(self.raw_address + Offsets["Text"], str(value))

    # humanoid props #
    @property
    def WalkSpeed(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(self.raw_address + Offsets["WalkSpeed"])

    @WalkSpeed.setter
    def WalkSpeed(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("WalkSpeed is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(self.raw_address + Offsets["WalkSpeed"], float(value))

    @property
    def JumpPower(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(self.raw_address + Offsets["JumpPower"])

    @JumpPower.setter
    def JumpPower(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("JumpPower is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(self.raw_address + Offsets["JumpPower"], float(value))
        
    @property
    def Health(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(self.raw_address + Offsets["Health"])

    @Health.setter
    def Health(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("Health is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(self.raw_address + Offsets["Health"], float(value))

    @property
    def MaxHealth(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(self.raw_address + Offsets["MaxHealth"])

    @MaxHealth.setter
    def MaxHealth(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("MaxHealth is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(self.raw_address + Offsets["MaxHealth"], float(value))

    # model props #
    @property
    def PrimaryPart(self):
        if self.ClassName != "Model":
            return None
        
        parent_pointer = int.from_bytes(self.memory_module.read(self.raw_address + Offsets["PrimaryPart"], 8), 'little')
        if parent_pointer == 0:
            return None

        return RBXInstance(parent_pointer, self.memory_module)

    @PrimaryPart.setter
    def PrimaryPart(self, value):
        if self.ClassName != "Model":
            raise AttributeError("PrimaryPart is only available on Model instances.")
        self._ensure_writable()

        if value is None:
            target = 0
        elif isinstance(value, RBXInstance):
            target = value.raw_address
        elif isinstance(value, int):
            target = value
        else:
            raise TypeError("PrimaryPart must be set to an RBXInstance, int address, or None.")
        self.memory_module.write_long(self.raw_address + Offsets["PrimaryPart"], target)
    
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
        if addr == 0:
            return None
        
        return RBXInstance(addr, self.memory_module)
    
    @property
    def DisplayName(self):
        return self.memory_module.read_string(self.raw_address + Offsets["DisplayName"])

    @DisplayName.setter
    def DisplayName(self, value: str):
        self._write_rbx_string(self.raw_address + Offsets["DisplayName"], str(value))

    @property
    def UserId(self):
        return self.memory_module.read_long(self.raw_address + Offsets["UserId"])

    @property
    def Team(self):
        addr = int.from_bytes(self.memory_module.read(self.instance.raw_address + Offsets["Team"], 8), 'little')
        if addr == 0:
            return None
        
        return RBXInstance(addr, self.memory_module)

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

    @FieldOfView.setter
    def FieldOfView(self, value: float):
        self.FieldOfViewRadians = float(value) * (math.pi / 180)
    
    @property
    def FieldOfViewRadians(self):
        return self.memory_module.read_float(self.raw_address + Offsets["FOV"])

    @FieldOfViewRadians.setter
    def FieldOfViewRadians(self, value: float):
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + Offsets["FOV"], float(value))
    
    @property
    def ViewportSize(self):
        SizeData = self.memory_module.read_floats(self.raw_address + Offsets["ViewportSize"], 2)
        return Vector2(*SizeData)

    @ViewportSize.setter
    def ViewportSize(self, value):
        vec = self._as_vector2(value, "ViewportSize")
        self._ensure_writable()
        self.memory_module.write_floats(
            self.raw_address + Offsets["ViewportSize"],
            (vec.X, vec.Y)
        )

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
            if Offsets.get("DataModelPointer") is not None:
                datamodel_addr = Offsets["DataModelPointer"]
            else:
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
        if addr == 0:
            return None
        
        return CameraClass(self.memory_module, RBXInstance(addr, self.memory_module))
