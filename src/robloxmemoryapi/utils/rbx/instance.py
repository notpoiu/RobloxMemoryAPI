from ..offsets import *
import time, math
import threading
import inspect
from .datastructures import *
from .bytecode import decryptor, encryptor

# Normal Classes #
class RBXInstance:
    ROTATION_MATRIX_FLOATS = 9

    def __init__(self, address, memory_module):
        self.raw_address = address
        self.memory_module = memory_module
        self.instance_offsets = Offsets["Instance"]
        self.basepart_offsets = Offsets["BasePart"]
        self.camera_offsets = Offsets["Camera"]
        self.gui_offsets = Offsets["GuiObject"]
        self.misc_offsets = Offsets["Misc"]
        self.humanoid_offsets = Offsets["Humanoid"]
        self.model_offsets = Offsets["Model"]

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
        return self.memory_module.get_pointer(
            self.raw_address,
            self.basepart_offsets["Primitive"]
        )
    

    # props #
    @property
    def Parent(self):
        parent_pointer = self.memory_module.get_pointer(
            self.raw_address,
            self.instance_offsets["Parent"]
        )
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
        self.memory_module.write_long(
            self.raw_address + self.instance_offsets["Parent"],
            target
        )

    @property
    def Name(self):
        name_address = self.memory_module.get_pointer(
            self.raw_address,
            self.instance_offsets["Name"]
        )
        return self.memory_module.read_string(name_address)
    
    @Name.setter
    def Name(self, value: str):
        self._ensure_writable()
        name_address = self.memory_module.get_pointer(
            self.raw_address,
            self.instance_offsets["Name"]
        )
        self.memory_module.write_string(name_address, value)
    
    @property
    def ClassName(self):
        class_descriptor_address = self.memory_module.get_pointer(
            self.raw_address,
            self.instance_offsets["ClassDescriptor"]
        )
        class_name_address = self.memory_module.get_pointer(
            class_descriptor_address,
            self.instance_offsets["ClassName"]
        )
        return self.memory_module.read_string(class_name_address)
    
    @property
    def CFrame(self):
        className = self.ClassName

        if "part" in className.lower():
            CFrameRotation = self.memory_module.read_floats(
                self.primitive_address + self.basepart_offsets["Rotation"],
                self.ROTATION_MATRIX_FLOATS
            )
            PositionData = self.memory_module.read_floats(
                self.primitive_address + self.basepart_offsets["Position"],
                3
            )
        elif className == "Camera":
            CFrameRotation = self.memory_module.read_floats(
                self.raw_address + self.camera_offsets["Rotation"],
                self.ROTATION_MATRIX_FLOATS
            )
            PositionData = self.memory_module.read_floats(
                self.raw_address + self.camera_offsets["Position"],
                3
            )
        else:
            return None
        
        RightVectorData = get_flat_matrix_column(CFrameRotation, 0)
        UpVectorData = get_flat_matrix_column(CFrameRotation, 1)
        LookVectorData = get_flat_matrix_column(CFrameRotation, 2, invert_values=True)

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
            value.RightVector.Z, value.UpVector.Z, -value.LookVector.Z
        ]
        position_data = (value.Position.X, value.Position.Y, value.Position.Z)

        className = self.ClassName
        if "part" in className.lower():
            rotation_address = self.primitive_address + self.basepart_offsets["Rotation"]
            position_address = self.primitive_address + self.basepart_offsets["Position"]
        elif className == "Camera":
            rotation_address = self.raw_address + self.camera_offsets["Rotation"]
            position_address = self.raw_address + self.camera_offsets["Position"]
        else:
            raise AttributeError("CFrame cannot be written for this instance type.")

        self.memory_module.write_floats(rotation_address, matrix_data)
        self.memory_module.write_floats(position_address, position_data)

    @property
    def Position(self):
        className = self.ClassName.lower()
        if "part" in className:
            position_vector3 = self.memory_module.read_floats(
                self.primitive_address + self.basepart_offsets["Position"],
                3
            )
            return Vector3(*position_vector3)
        elif className == "camera":
            position_vector3 = self.memory_module.read_floats(
                self.raw_address + self.camera_offsets["Position"],
                3
            )
            return Vector3(*position_vector3)
        else:
            return self._read_udim2(self.raw_address + self.gui_offsets["Position"])

    @Position.setter
    def Position(self, value):
        className = self.ClassName.lower()
        
        self._ensure_writable()
        if "part" in className:
            vec = self._as_vector3(value, "Position")
            self.memory_module.write_floats(
                self.primitive_address + self.basepart_offsets["Position"],
                (vec.X, vec.Y, vec.Z)
            )

        elif className == "camera":
            vec = self._as_vector3(value, "Position")
            self.memory_module.write_floats(
                self.raw_address + self.camera_offsets["Position"],
                (vec.X, vec.Y, vec.Z)
            )

        else:
            udim2_value = self._as_udim2(value, "Position")
            self._write_udim2(self.raw_address + self.gui_offsets["Position"], udim2_value)

    @property
    def Velocity(self):
        className = self.ClassName

        if "part" in className.lower():
            velocity_vector3 = self.memory_module.read_floats(
                self.primitive_address + self.basepart_offsets["AssemblyLinearVelocity"],
                3
            )
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
            self.primitive_address + self.basepart_offsets["AssemblyLinearVelocity"],
            (vec.X, vec.Y, vec.Z)
        )

    @property
    def LayoutOrder(self):
        return self.memory_module.read_int(
            self.raw_address,
            self.gui_offsets["LayoutOrder"]
        )

    @LayoutOrder.setter
    def LayoutOrder(self, value: int):
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + self.gui_offsets["LayoutOrder"],
            value
        )

    @property
    def Enabled(self):
        if self.ClassName != "ScreenGui":
            return None
        
        return self.memory_module.read_bool(
            self.raw_address,
            self.gui_offsets["ScreenGui_Enabled"]
        )

    @Enabled.setter
    def Enabled(self, value: bool):
        if self.ClassName != "ScreenGui":
            raise AttributeError("Enabled is only available on ScreenGui instances.")
        
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + self.gui_offsets["ScreenGui_Enabled"],
            value
        )

    @property
    def Visible(self):
        return self.memory_module.read_bool(
            self.raw_address,
            self.gui_offsets["Visible"]
        )

    @Visible.setter
    def Visible(self, value: bool):
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + self.gui_offsets["Visible"],
            value
        )

    @property
    def Image(self):
        return self.memory_module.read_string(
            self.raw_address,
            self.gui_offsets["Image"]
        )
    
    @Image.setter
    def Image(self, value: str):
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + self.gui_offsets["Image"],
            value
        )

    @property
    def Size(self):
        if "part" in self.ClassName.lower():
            size_vector3 = self.memory_module.read_floats(
                self.primitive_address + self.basepart_offsets["Size"],
                3
            )
            return Vector3(*size_vector3)
        else:
            return self._read_udim2(self.raw_address + self.gui_offsets["Size"])

    @Size.setter
    def Size(self, value):
        self._ensure_writable()
        if "part" in self.ClassName.lower():
            vec = self._as_vector3(value, "Size")
            self.memory_module.write_floats(
                self.primitive_address + self.basepart_offsets["Size"],
                (vec.X, vec.Y, vec.Z)
            )
        else:
            gui_size = self._as_udim2(value, "Size")
            self._write_udim2(self.raw_address + self.gui_offsets["Size"], gui_size)

    # XXXXValue props #
    @property
    def Value(self):
        classname = self.ClassName 
        value_address = self.raw_address + self.misc_offsets["Value"]
        if classname == "StringValue":
            return self.memory_module.read_string(value_address)
        
        elif classname == "IntValue":
            return self.memory_module.read_int(value_address)
        
        elif classname == "NumberValue":
            return self.memory_module.read_double(value_address)
        
        elif classname == "BoolValue":
            return self.memory_module.read_bool(value_address)
        
        elif classname == "ObjectValue":
            object_address = self.memory_module.get_pointer(
                self.raw_address,
                self.misc_offsets["Value"]
            )

            return RBXInstance(object_address, self.memory_module)
        
        return None

    @Value.setter
    def Value(self, new_value):
        self._ensure_writable()
        classname = self.ClassName
        value_address = self.raw_address + self.misc_offsets["Value"]

        if classname == "StringValue":
            self.memory_module.write_string(value_address, str(new_value))
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
    
    @property
    def text_capacity(self) -> int:
        if self.ClassName != "StringValue":
            raise AttributeError("Capacity is only available on StringValue instances.")

        value_address = self.raw_address + self.misc_offsets["Value"]
        return self.memory_module.read_int(value_address + 0x18)

    # text props #
    @property
    def Text(self):
        if "text" in self.ClassName.lower():
            return self.memory_module.read_string(
                self.raw_address,
                self.gui_offsets["Text"]
            )
        
        return None

    @Text.setter
    def Text(self, value: str):
        if "text" not in self.ClassName.lower():
            raise AttributeError("Text is not available on this instance.")
        self.memory_module.write_string(
            self.raw_address + self.gui_offsets["Text"],
            str(value)
        )

    # humanoid props #
    @property
    def WalkSpeed(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            self.humanoid_offsets["Walkspeed"]
        )

    @WalkSpeed.setter
    def WalkSpeed(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("WalkSpeed is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + self.humanoid_offsets["Walkspeed"],
            float(value)
        )

        self.memory_module.write_float(
            self.raw_address + self.humanoid_offsets["WalkspeedCheck"],
            float(value)
        )

    @property
    def JumpPower(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            self.humanoid_offsets["JumpPower"]
        )

    @JumpPower.setter
    def JumpPower(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("JumpPower is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + self.humanoid_offsets["JumpPower"],
            float(value)
        )
        
    @property
    def Health(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            self.humanoid_offsets["Health"]
        )

    @Health.setter
    def Health(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("Health is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + self.humanoid_offsets["Health"],
            float(value)
        )

    @property
    def MaxHealth(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            self.humanoid_offsets["MaxHealth"]
        )

    @MaxHealth.setter
    def MaxHealth(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("MaxHealth is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + self.humanoid_offsets["MaxHealth"],
            float(value)
        )

    # model props #
    @property
    def PrimaryPart(self):
        if self.ClassName != "Model":
            return None
        
        parent_pointer = self.memory_module.get_pointer(
            self.raw_address,
            self.model_offsets["PrimaryPart"]
        )
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
        self.memory_module.write_long(
            self.raw_address + self.model_offsets["PrimaryPart"],
            target
        )
    
    @property
    def Bytecode(self):
        bytecode = self.RawBytecode
        if bytecode is None:
            return None
        
        return decryptor.decode_bytecode(bytecode)
    
    @property
    def RawBytecode(self):
        classname = self.ClassName
        if classname == "LocalScript":
            bytecode_offset = Offsets["LocalScript"]["ByteCode"]
        elif classname == "ModuleScript":
            bytecode_offset = Offsets["ModuleScript"]["ByteCode"]
        else:
            return None

        bytecode_ptr = self.memory_module.get_pointer(self.raw_address, bytecode_offset)
        
        if bytecode_ptr == 0:
            return None

        content_ptr = self.memory_module.get_pointer(bytecode_ptr, Offsets["ByteCode"]["Pointer"])
        size = self.memory_module.read_int(bytecode_ptr + Offsets["ByteCode"]["Size"])

        return self.memory_module.read(content_ptr, size)
    
    @Bytecode.setter
    def Bytecode(self, value: bytes):
        self._ensure_writable()
        
        classname = self.ClassName
        if classname == "LocalScript":
            bytecode_offset = Offsets["LocalScript"]["ByteCode"]
        elif classname == "ModuleScript":
            bytecode_offset = Offsets["ModuleScript"]["ByteCode"]
        else:
            raise AttributeError("Bytecode can only be written for LocalScript or ModuleScript.")

        encoded_data = encryptor.encode_roblox(value)
        new_size = len(encoded_data)
        
        new_content_ptr = self.memory_module.virtual_alloc(new_size)
        self.memory_module.write(new_content_ptr, encoded_data)
        
        bytecode_ptr = self.memory_module.get_pointer(self.raw_address, bytecode_offset)
        
        if bytecode_ptr == 0:
             raise RuntimeError("Cannot set bytecode: Bytecode object not found (script might be empty or not loaded).")

        self.memory_module.write_long(bytecode_ptr + Offsets["ByteCode"]["Pointer"], new_content_ptr)
        self.memory_module.write_int(bytecode_ptr + Offsets["ByteCode"]["Size"], new_size)
    
    # functions #
    def GetChildren(self):
        children = []
        children_pointer = self.memory_module.get_pointer(
            self.raw_address,
            self.instance_offsets["ChildrenStart"]
        )
        
        if children_pointer == 0:
            return children
        
        children_start = self.memory_module.get_pointer(children_pointer)
        children_end = self.memory_module.get_pointer(
            children_pointer,
            self.instance_offsets["ChildrenEnd"]
        )

        for child_address in range(children_start, children_end, 0x10):
            child_pointer = self.memory_module.get_pointer(child_address)
            
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

    def GetAttribute(self, attribute_name: str):
        for name, attribute in self.GetAttributes().items():
            if name == attribute_name:
                return attribute
        return None

    def GetAttributes(self):
        attributes = {}
        attribute_container = self.memory_module.read_long(
            self.raw_address + self.instance_offsets["AttributeContainer"]
        )
        
        if attribute_container == 0:
            return attributes

        attribute_list = self.memory_module.read_long(
            attribute_container + self.instance_offsets["AttributeList"]
        )
        
        if attribute_list == 0:
            return attributes

        i = 0
        while i < 0x400:
            name_ptr = self.memory_module.read_long(attribute_list + i)
            if name_ptr == 0:
                break

            try:
                name = self.memory_module.read_string(name_ptr)
            except OSError:
                break
            
            if not name or name == "invalid_str":
                break

            value_addr = attribute_list + i + self.instance_offsets["AttributeToValue"]
            
            # Read Type Name (Pointer at +0x8 points to TypeDescriptor, Name at TypeDesc + 0x8)
            type_ptr = self.memory_module.read_long(attribute_list + i + 0x8)
            type_name = self._read_type_name(type_ptr)

            attributes[name] = AttributeValue(value_addr, name, type_name, self.memory_module)

            i += self.instance_offsets["AttributeToNext"]
        
        return attributes


    def SetAttribute(self, name: str, value):
        attribute = self.GetAttribute(name)
        if attribute is None:
            raise ValueError(f"Attribute '{name}' not found. Only existing attributes can be modified.")
        
        attribute.value = value

    def _read_type_name(self, type_ptr: int) -> str:
        if type_ptr == 0: return "Unknown"
        try:
            name_ptr = self.memory_module.read_long(type_ptr + 0x8) # Name at +8 of TypeDescriptor
            if name_ptr != 0:
                name = self.memory_module.read_string(name_ptr)
                return name if name else "Unknown"
        except: pass
        return "Unknown"

class AttributeValue:
    def __init__(self, address, name, type_name, memory_module):
        self.address = address
        self.name = name
        self.type_name = type_name
        self.memory_module = memory_module

    @property
    def value(self):
        t = self.type_name.lower()
        if t == "string":
            return self.memory_module.read_string(self.address)
        elif t == "bool":
            return self.memory_module.read_bool(self.address)
        elif t == "double" or t == "float": 
            return self.memory_module.read_double(self.address)
        elif t == "int" or t == "int64":
            return self.memory_module.read_int(self.address)
        elif t == "vector3":
            return Vector3(*self.memory_module.read_floats(self.address, 3))
        elif t == "vector2":
            return Vector2(*self.memory_module.read_floats(self.address, 2))
        elif t == "color3":
            return Vector3(*self.memory_module.read_floats(self.address, 3))
        elif t == "cframe":
            return self.memory_module.read_floats(self.address, 12)
        elif "keycode" in t:
            return self.memory_module.read_int(self.address)
        else:
            return None

    @value.setter
    def value(self, new_value):
        t = self.type_name.lower()
        if t == "string":
            self.memory_module.write_string(self.address, str(new_value))
        elif t == "bool":
            self.memory_module.write_bool(self.address, bool(new_value))
        elif t == "double" or t == "float":
            self.memory_module.write_double(self.address, float(new_value))
        elif t == "int" or t == "int64" or "keycode" in t:
            self.memory_module.write_int(self.address, int(new_value))
        elif t == "vector3":
            if isinstance(new_value, Vector3):
                self.memory_module.write_floats(self.address, (new_value.X, new_value.Y, new_value.Z))
            elif isinstance(new_value, (list, tuple)) and len(new_value) == 3:
                self.memory_module.write_floats(self.address, new_value)
            else:
                raise TypeError("Vector3 value expected")
        elif t == "vector2":
            if isinstance(new_value, Vector2):
                self.memory_module.write_floats(self.address, (new_value.X, new_value.Y))
            elif isinstance(new_value, (list, tuple)) and len(new_value) == 2:
                self.memory_module.write_floats(self.address, new_value)
            else:
                raise TypeError("Vector2 value expected")
        elif t == "color3":
             if isinstance(new_value, Vector3): # Color3 is often treated as Vector3 storage-wise here
                self.memory_module.write_floats(self.address, (new_value.X, new_value.Y, new_value.Z))
             elif isinstance(new_value, (list, tuple)) and len(new_value) == 3:
                self.memory_module.write_floats(self.address, new_value)
             else:
                raise TypeError("Color3 (Vector3/list) value expected")
        else:
            raise TypeError(f"Setting value for type '{t}' is not supported yet.")

    def __repr__(self):
        return f"<AttributeValue name='{self.name}' type='{self.type_name}' value={self.value}>"

    # setters #
    def set_float(self, value):
        if isinstance(value, list):
            self.memory_module.write_floats(self.address, value)
        else:
            self.memory_module.write_float(self.address, value)

    def set_double(self, value):
        if isinstance(value, list):
            self.memory_module.write_doubles(self.address, value)
        else:
            self.memory_module.write_double(self.address, value)
    
    def set_int(self, value):
        if isinstance(value, list):
            self.memory_module.write_ints(self.address, value)
        else:
            self.memory_module.write_int(self.address, value)
        
    def set_long(self, value):
        if isinstance(value, list):
            self.memory_module.write_longs(self.address, value)
        else:
            self.memory_module.write_long(self.address, value)
        
    def set_bool(self, value):
        self.memory_module.write_bool(self.address, value)

    def set_string(self, value):
        self.memory_module.write_string(self.address, value)

    def set_vector2(self, value):
        if isinstance(value, Vector2):
            self.memory_module.write_floats(self.address, (value.X, value.Y))
        else:
            raise TypeError("value must be a Vector2")

    def set_vector3(self, value):
        if isinstance(value, Vector3):
            self.memory_module.write_floats(self.address, (value.X, value.Y, value.Z))
        else:
            raise TypeError("value must be a Vector3")

class PlayerClass(RBXInstance):
    def __init__(self, memory_module, player: RBXInstance):
        super().__init__(player.raw_address, memory_module)
        self.memory_module = memory_module
        self.offset_base = Offsets["Player"]

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
        CharacterAddress = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["ModelInstance"]
        )
        
        if CharacterAddress == 0:
            return None
        
        return RBXInstance(CharacterAddress, self.memory_module)
    
    @property
    def DisplayName(self):
        return self.memory_module.read_string(
            self.raw_address,
            self.offset_base["DisplayName"]
        )

    @DisplayName.setter
    def DisplayName(self, value: str):
        self.memory_module.write_string(
            self.raw_address + self.offset_base["DisplayName"],
            str(value)
        )

    @property
    def UserId(self):
        return self.memory_module.read_long(
            self.raw_address,
            self.offset_base["UserId"]
        )

    @property
    def Team(self):
        TeamAddress = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["Team"]
        )

        if TeamAddress == 0:
            return None
        
        return RBXInstance(TeamAddress, self.memory_module)

class CameraClass(RBXInstance):
    def __init__(self, memory_module, camera: RBXInstance):
        super().__init__(camera.raw_address, memory_module)
        self.offset_base = Offsets["Camera"]
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
        return self.memory_module.read_float(
            self.raw_address,
            self.offset_base["FieldOfView"]
        )

    @FieldOfViewRadians.setter
    def FieldOfViewRadians(self, value: float):
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + self.offset_base["FieldOfView"],
            float(value)
        )
    
    @property
    def ViewportSize(self):
        SizeData = self.memory_module.read_floats(
            self.raw_address + self.offset_base["ViewportSize"],
            2
        )

        return Vector2(*SizeData)

    @ViewportSize.setter
    def ViewportSize(self, value):
        vec = self._as_vector2(value, "ViewportSize")
        self._ensure_writable()

        self.memory_module.write_floats(
            self.raw_address + self.offset_base["ViewportSize"],
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
    @staticmethod
    def _coerce_refresh_interval(value):
        try:
            interval = float(value)
        except (TypeError, ValueError):
            raise TypeError("refresh_interval must be a positive number.")

        if interval <= 0:
            raise ValueError("refresh_interval must be greater than zero.")

        return interval

    def __init__(self, memory_module, auto_refresh: bool = True, refresh_interval: float = 0.5):
        super().__init__()
        self.memory_module = memory_module
        self.offset_base = Offsets["DataModel"]
        self.error = None
        self._refresh_callbacks = []
        self._last_datamodel_address = 0
        self._refresh_lock = threading.Lock()
        self._auto_refresh_thread = None
        self._auto_refresh_stop_event = None
        self._auto_refresh_interval = self._coerce_refresh_interval(refresh_interval)
        self._auto_refresh_enabled = False
        self.refresh_datamodel()

        if auto_refresh:
            self.start_auto_refresh()

    def __del__(self):
        try:
            self.stop_auto_refresh()
        except Exception:
            pass

    def __getattr__(self, name):
        if not self._ensure_instance():
            raise AttributeError("DataModel instance is unavailable.")
        return super().__getattr__(name)

    def start_auto_refresh(self, interval: float | None = None):
        if interval is not None:
            self._auto_refresh_interval = self._coerce_refresh_interval(interval)

        if self._auto_refresh_thread is not None and self._auto_refresh_thread.is_alive():
            self._auto_refresh_enabled = True
            return

        stop_event = threading.Event()
        self._auto_refresh_stop_event = stop_event
        self._auto_refresh_enabled = True
        self._auto_refresh_thread = threading.Thread(
            target=self._auto_refresh_loop,
            args=(stop_event,),
            name="DataModelAutoRefresh",
            daemon=True
        )
        self._auto_refresh_thread.start()

    def stop_auto_refresh(self):
        self._auto_refresh_enabled = False
        stop_event = self._auto_refresh_stop_event
        worker = self._auto_refresh_thread

        if stop_event is not None:
            stop_event.set()

        if worker is not None and worker.is_alive():
            worker.join(timeout=1.0)

        self._auto_refresh_thread = None
        self._auto_refresh_stop_event = None

    def _auto_refresh_loop(self, stop_event: threading.Event):
        while not stop_event.is_set():
            try:
                self.refresh_datamodel()
            except Exception:
                # refresh_datamodel already tracks its own errors.
                pass

            if stop_event.wait(self._auto_refresh_interval):
                break

    def refresh_datamodel(self):
        changed = False
        instance_snapshot = None

        with self._refresh_lock:
            try:
                fake_datamodel_ptr = self.memory_module.get_address(Offsets["FakeDataModel"]["Pointer"], pointer=True)
                datamodel_address_ptr = self.memory_module.get_pointer(fake_datamodel_ptr, Offsets["FakeDataModel"]["RealDataModel"])

                if datamodel_address_ptr == 0:
                    if self.instance is not None:
                        changed = True
                    self.instance = None
                    self.failed = True
                    self._last_datamodel_address = 0
                else:
                    if self.instance is not None and datamodel_address_ptr == self.instance.raw_address:
                        if self.failed:
                            self.failed = False
                    else:
                        datamodel_instance = RBXInstance(datamodel_address_ptr, self.memory_module)

                        if datamodel_instance.ClassName != "DataModel":
                            if self.instance is not None:
                                changed = True
                            self.instance = None
                            self.failed = True
                            self._last_datamodel_address = 0
                        else:
                            if datamodel_instance.raw_address != self._last_datamodel_address:
                                changed = True
                            self.instance = datamodel_instance
                            self.failed = False
                            self.error = None
                            self._last_datamodel_address = datamodel_instance.raw_address
            except (KeyError, OSError) as e:
                self.error = e
                self.failed = True
                if self.instance is not None:
                    changed = True
                self.instance = None
                if self._last_datamodel_address != 0:
                    changed = True
                self._last_datamodel_address = 0
            finally:
                if changed:
                    instance_snapshot = self.instance

        if changed:
            self._dispatch_refresh(instance_snapshot)

    def _ensure_instance(self):
        if not self._auto_refresh_enabled:
            self.refresh_datamodel()
        return self.instance is not None and not self.failed

    def bind_to_refresh(self, callback, invoke_if_ready: bool = False):
        if not callable(callback):
            raise TypeError("callback must be callable.")

        self._refresh_callbacks.append(callback)

        if invoke_if_ready and self.instance is not None and not self.failed:
            try:
                self._invoke_refresh_callback(callback, self.instance)
            except Exception:
                pass

        return callback

    def unbind_from_refresh(self, callback):
        try:
            self._refresh_callbacks.remove(callback)
        except ValueError:
            pass

    def _dispatch_refresh(self, instance):
        for callback in list(self._refresh_callbacks):
            try:
                self._invoke_refresh_callback(callback, instance)
            except Exception:
                continue

    @staticmethod
    def _callback_accepts_instance(callback):
        try:
            signature = inspect.signature(callback)
        except (TypeError, ValueError):
            return True

        for param in signature.parameters.values():
            if param.kind in (
                param.POSITIONAL_ONLY,
                param.POSITIONAL_OR_KEYWORD,
                param.VAR_POSITIONAL,
            ):
                return True

        return False

    def _invoke_refresh_callback(self, callback, instance):
        if self._callback_accepts_instance(callback):
            callback(instance)
        else:
            callback()

    @property
    def ServerIP(self):
        if not self._ensure_instance():
            return "127.0.0.1|42069"

        return self.memory_module.read_string(
            self.instance.raw_address,
            self.offset_base["ServerIP"]
        )

    @property
    def CreatorId(self):
        if not self._ensure_instance():
            return 0

        return self.memory_module.read_long(
            self.instance.raw_address,
            self.offset_base["CreatorId"]
        )

    @property
    def PlaceId(self):
        if not self._ensure_instance():
            return 0

        return self.memory_module.read_long(
            self.instance.raw_address,
            self.offset_base["PlaceId"]
        )

    @property
    def GameId(self):
        if not self._ensure_instance():
            return 0

        return self.memory_module.read_long(
            self.instance.raw_address,
            self.offset_base["GameId"]
        )

    @property
    def JobId(self):
        if not self._ensure_instance():
            return None

        if self.GameId == 0 or self.PlaceId == 0:
            return None

        return self.memory_module.read_string(
            self.instance.raw_address,
            self.offset_base["JobId"]
        )

    @property
    def Players(self):
        if not self._ensure_instance():
            return None

        return PlayersService(self.memory_module, self)

    @property
    def Workspace(self):
        if not self._ensure_instance():
            return None

        return WorkspaceService(self.memory_module, self)

    # class functions #
    def GetService(self, name):
        if not self._ensure_instance():
            return None

        for instance in self.instance.GetChildren():
            if instance.ClassName == name:
                return instance

        return None

    # Stuff
    def IsLoaded(self):
        if not self._ensure_instance():
            return False

        return self.memory_module.read_bool(
            self.instance.raw_address,
            self.offset_base["GameLoaded"]
        )

    def is_lua_app(self):
        if not self._ensure_instance():
            return False

        return self.PlaceId == 0 and self.GameId == 0 and self.Name == "LuaApp"

class PlayersService(ServiceBase):
    def __init__(self, memory_module, game: DataModel):
        super().__init__()
        self.memory_module = memory_module
        self.offset_base = Offsets["Player"]

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
    
        LocalPlayerAddress = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["LocalPlayer"]
        )

        return PlayerClass(self.memory_module, RBXInstance(LocalPlayerAddress, self.memory_module))
    
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
        self.offset_base = Offsets["Workspace"]
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

        CameraAddress = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["CurrentCamera"]
        )

        if CameraAddress == 0:
            return None

        return CameraClass(self.memory_module, RBXInstance(CameraAddress, self.memory_module))
