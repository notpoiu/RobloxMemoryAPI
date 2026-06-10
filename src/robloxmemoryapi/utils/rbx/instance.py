from ..offsets import *
import time, math
import threading
import inspect
import struct
from .datastructures import *
from .bytecode import decryptor, encryptor

instance_offsets = Offsets["Instance"]
basepart_offsets = Offsets["BasePart"]
primitive_offsets = Offsets["Primitive"]
camera_offsets = Offsets["Camera"]
gui_offsets = Offsets["GuiObject"]
gui_2d_offsets = Offsets["GuiBase2D"]
misc_offsets = Offsets["Misc"]
humanoid_offsets = Offsets["Humanoid"]
model_offsets = Offsets["Model"]
proximityprompt_offsets = Offsets["ProximityPrompt"]
clickdetector_offsets = Offsets["ClickDetector"]
statsitem_offsets = Offsets["StatsItem"]
inputobject_offsets = Offsets["MouseService"]  # InputObject uses MouseService offsets
animator_offsets = Offsets["Animator"]
animationtrack_offsets = Offsets["AnimationTrack"]
tool_offsets = Offsets["Tool"]
world_offsets = Offsets["World"]
sound_offsets = Offsets["Sound"]
spawnlocation_offsets = Offsets["SpawnLocation"]
clothing_offsets = Offsets["Clothing"]
charactermesh_offsets = Offsets["CharacterMesh"]
attachment_offsets = Offsets["Attachment"]
air_properties_offsets = Offsets["AirProperties"]
seat_offsets = Offsets["Seat"]
meshpart_offsets = Offsets["MeshPart"]
textures_offsets = Offsets["Textures"]
beam_offsets = Offsets["Beam"]
particleemitter_offsets = Offsets["ParticleEmitter"]
vehicleseat_offsets = Offsets["VehicleSeat"]
weld_offsets = Offsets["Weld"]
weldconstraint_offsets = Offsets["WeldConstraint"]
surfaceappearance_offsets = Offsets["SurfaceAppearance"]
script_offsets = Offsets["Script"]
atmosphere_offsets = Offsets.get("Atmosphere", {})
bloom_effect_offsets = Offsets.get("BloomEffect", {})
depth_of_field_effect_offsets = Offsets.get("DepthOfFieldEffect", {})
sun_rays_effect_offsets = Offsets.get("SunRaysEffect", {})
specialmesh_offsets = Offsets.get("SpecialMesh", {})
terrain_offsets = Offsets.get("Terrain", {})
material_colors_offsets = Offsets.get("MaterialColors", {})
dragdetector_offsets = Offsets.get("DragDetector", {})
sky_offsets = Offsets.get("Sky", {})
team_offsets = Offsets.get("Team", {})
unionoperation_offsets = Offsets.get("UnionOperation", {})
meshcontentprovider_offsets = Offsets.get("MeshContentProvider", {})
meshdata_offsets = Offsets.get("MeshData", {})
playerconfigurer_offsets = Offsets.get("PlayerConfigurer", {})
playermouse_offsets = Offsets.get("PlayerMouse", {})
renderjob_offsets = Offsets.get("RenderJob", {})
renderview_offsets = Offsets.get("RenderView", {})
runservice_offsets = Offsets.get("RunService", {})
scriptcontext_offsets = Offsets.get("ScriptContext", {})
visualengine_offsets = Offsets.get("VisualEngine", {})
taskscheduler_offsets = Offsets.get("TaskScheduler", {})

ROTATION_MATRIX_FLOATS = 9

_ENABLED_OFFSETS_BY_CLASS = {
    "ColorCorrectionEffect": Offsets["ColorCorrectionEffect"],
    "BlurEffect": Offsets["BlurEffect"],
    "ColorGradingEffect": Offsets["ColorGradingEffect"],
    "BloomEffect": bloom_effect_offsets,
    "DepthOfFieldEffect": depth_of_field_effect_offsets,
    "SunRaysEffect": sun_rays_effect_offsets,
    "ScreenGui": {"Enabled": gui_offsets["ScreenGui_Enabled"]},
    "ProximityPrompt": proximityprompt_offsets,
    "Tool": tool_offsets,
    "SpawnLocation": spawnlocation_offsets,
}

_ATMOSPHERE_COLOR_OFFSETS_BY_CLASS = {
    "Atmosphere": atmosphere_offsets,
}

_EFFECT_INTENSITY_OFFSETS_BY_CLASS = {
    "BloomEffect": bloom_effect_offsets,
    "SunRaysEffect": sun_rays_effect_offsets,
}

_SURFACE_APPEARANCE_CONTENT_OFFSETS_BY_PROPERTY = {
    "ColorMap": surfaceappearance_offsets.get("ColorMap"),
    "EmissiveMaskContent": surfaceappearance_offsets.get("EmissiveMaskContent"),
    "MetalnessMap": surfaceappearance_offsets.get("MetalnessMap"),
    "NormalMap": surfaceappearance_offsets.get("NormalMap"),
    "RoughnessMap": surfaceappearance_offsets.get("RoughnessMap"),
}

class MaterialColors:
    _internal_attrs = {"memory_module", "base_address", "_offsets"}

    def __init__(self, memory_module, base_address: int, offsets: dict):
        object.__setattr__(self, "memory_module", memory_module)
        object.__setattr__(self, "base_address", base_address)
        object.__setattr__(self, "_offsets", offsets)

    def __repr__(self):
        materials = ", ".join(self.keys())
        return f"MaterialColors({materials})"

    def __contains__(self, material):
        try:
            self._resolve_material(material)
            return True
        except KeyError:
            return False

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self._offsets)

    def __getitem__(self, material):
        return self.get(material)

    def __setitem__(self, material, color):
        self.set(material, color)

    def __getattr__(self, material):
        try:
            return self.get(material)
        except KeyError:
            raise AttributeError(material) from None

    def __setattr__(self, material, color):
        if material in self._internal_attrs:
            object.__setattr__(self, material, color)
            return
        self.set(material, color)

    def keys(self):
        return tuple(sorted(self._offsets, key=self._offsets.get))

    def items(self):
        return tuple((name, self.get(name)) for name in self.keys())

    def to_dict(self):
        return {name: self.get(name) for name in self.keys()}

    def get(self, material):
        offset = self._offset_for(material)
        raw = self.memory_module.read(self.base_address + offset, 3)
        if len(raw) != 3:
            return Color3()
        return Color3(raw[0] / 255.0, raw[1] / 255.0, raw[2] / 255.0)

    def set(self, material, color):
        if not hasattr(self.memory_module, "write"):
            raise RuntimeError("Write operations require a memory module with write support (allow_write=True).")

        offset = self._offset_for(material)
        color = RBXInstance._as_color3(color, "MaterialColors value")
        self.memory_module.write(
            self.base_address + offset,
            bytes((
                self._color_channel_to_byte(color.R),
                self._color_channel_to_byte(color.G),
                self._color_channel_to_byte(color.B),
            ))
        )

    def _offset_for(self, material):
        return self._offsets[self._resolve_material(material)]

    def _resolve_material(self, material):
        if not isinstance(material, str):
            material = getattr(material, "Name", material)

        if not isinstance(material, str):
            raise KeyError(material)

        normalized = material.replace("_", "").replace(" ", "").lower()
        for name in self._offsets:
            if name.replace("_", "").replace(" ", "").lower() == normalized:
                return name

        raise KeyError(material)

    @staticmethod
    def _color_channel_to_byte(value):
        return max(0, min(255, int(round(float(value) * 255))))

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
    def _as_color3(value, context="value"):
        if isinstance(value, Color3):
            return value
        
        if isinstance(value, (tuple, list)) and len(value) == 3:
            return Color3(*value)
        
        raise TypeError(f"{context} must be a Color3 or an iterable of three numbers.")

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

    @staticmethod
    def _format_class_list(class_names):
        names = tuple(class_names)
        if len(names) == 1:
            return names[0]
        return ", ".join(names[:-1]) + f", or {names[-1]}"

    @staticmethod
    def _color3_tuple(value):
        return (value.R, value.G, value.B)

    def _class_offsets(self, offsets_by_class, property_name, write=False):
        offsets = offsets_by_class.get(self.ClassName)
        if offsets is None:
            if write:
                raise AttributeError(
                    f"{property_name} is only available on {self._format_class_list(offsets_by_class)} instances."
                )
            return None
        return offsets

    def _read_class_float(self, property_name, offsets_by_class):
        offsets = self._class_offsets(offsets_by_class, property_name)
        if offsets is None:
            return None
        return self.memory_module.read_float(self.raw_address, offsets[property_name])

    def _write_class_float(self, property_name, offsets_by_class, value):
        offsets = self._class_offsets(offsets_by_class, property_name, write=True)
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + offsets[property_name], float(value))

    def _read_class_bool(self, property_name, offsets_by_class):
        offsets = self._class_offsets(offsets_by_class, property_name)
        if offsets is None:
            return None
        return self.memory_module.read_bool(self.raw_address, offsets[property_name])

    def _write_class_bool(self, property_name, offsets_by_class, value):
        offsets = self._class_offsets(offsets_by_class, property_name, write=True)
        self._ensure_writable()
        self.memory_module.write_bool(self.raw_address + offsets[property_name], bool(value))

    def _read_class_color3(self, property_name, offsets_by_class):
        offsets = self._class_offsets(offsets_by_class, property_name)
        if offsets is None:
            return None
        return Color3(*self.memory_module.read_floats(self.raw_address + offsets[property_name], 3))

    def _write_class_color3(self, property_name, offsets_by_class, value):
        offsets = self._class_offsets(offsets_by_class, property_name, write=True)
        self._ensure_writable()
        color = self._as_color3(value, property_name)
        self.memory_module.write_floats(
            self.raw_address + offsets[property_name],
            self._color3_tuple(color)
        )

    def _read_class_string(self, property_name, offsets_by_class):
        offsets = self._class_offsets(offsets_by_class, property_name)
        if offsets is None:
            return None
        return self.memory_module.read_string(self.raw_address, offsets[property_name])

    def _write_class_string(self, property_name, offsets_by_class, value):
        offsets = self._class_offsets(offsets_by_class, property_name, write=True)
        self._ensure_writable()
        self.memory_module.write_string(self.raw_address + offsets[property_name], str(value))

    def _read_class_int(self, property_name, offsets_by_class):
        offsets = self._class_offsets(offsets_by_class, property_name)
        if offsets is None:
            return None
        return self.memory_module.read_int(self.raw_address, offsets[property_name])

    def _write_class_int(self, property_name, offsets_by_class, value):
        offsets = self._class_offsets(offsets_by_class, property_name, write=True)
        self._ensure_writable()
        self.memory_module.write_int(self.raw_address + offsets[property_name], int(value))


    # useful pointer stuff #
    @property
    def primitive_address(self):
        return self.memory_module.get_pointer(
            self.raw_address,
            basepart_offsets["Primitive"]
        )

    # props #
    @property
    def Parent(self):
        parent_pointer = self.memory_module.get_pointer(
            self.raw_address,
            instance_offsets["Parent"]
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

        current_parent = self.Parent
        if current_parent is not None:
            current_parent.Children.remove(self)
        
        self.memory_module.write_long(
            self.raw_address + instance_offsets["Parent"],
            target
        )

    @property
    def Name(self):
        name_address = self.memory_module.get_pointer(
            self.raw_address,
            instance_offsets["Name"]
        )
        return self.memory_module.read_string(name_address)
    
    @Name.setter
    def Name(self, value: str):
        self._ensure_writable()
        name_address = self.memory_module.get_pointer(
            self.raw_address,
            instance_offsets["Name"]
        )
        self.memory_module.write_string(name_address, value)
    
    @property
    def ClassName(self):
        class_descriptor_address = self.memory_module.get_pointer(
            self.raw_address,
            instance_offsets["ClassDescriptor"]
        )
        class_name_address = self.memory_module.get_pointer(
            class_descriptor_address,
            instance_offsets["ClassName"]
        )
        return self.memory_module.read_string(class_name_address)

    @property
    def CFrame(self):
        className = self.ClassName

        if "part" in className.lower():
            CFrameRotation = self.memory_module.read_floats(
                self.primitive_address + primitive_offsets["Rotation"],
                ROTATION_MATRIX_FLOATS
            )
            PositionData = self.memory_module.read_floats(
                self.primitive_address + primitive_offsets["Position"],
                3
            )
        elif className == "Camera":
            CFrameRotation = self.memory_module.read_floats(
                self.raw_address + camera_offsets["Rotation"],
                ROTATION_MATRIX_FLOATS
            )
            PositionData = self.memory_module.read_floats(
                self.raw_address + camera_offsets["Position"],
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
            rotation_address = self.primitive_address + primitive_offsets["Rotation"]
            position_address = self.primitive_address + primitive_offsets["Position"]
        elif className == "Camera":
            rotation_address = self.raw_address + camera_offsets["Rotation"]
            position_address = self.raw_address + camera_offsets["Position"]
        else:
            raise AttributeError("CFrame cannot be written for this instance type.")

        self.memory_module.write_floats(rotation_address, matrix_data)
        self.memory_module.write_floats(position_address, position_data)

    @property
    def ImagePlaneDepth(self):
        className = self.ClassName

        if className != "Camera":
            raise AttributeError("ImagePlaneDepth cannot be accessed on this instance type")

        return self.memory_module.read_float(self.raw_address + camera_offsets["ImagePlaneDepth"])

    @ImagePlaneDepth.setter
    def ImagePlaneDepth(self, value: float):
        if self.ClassName != "Camera":
            raise AttributeError("ImagePlaneDepth cannot be written on this instance type")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + camera_offsets["ImagePlaneDepth"],
            float(value)
        )

    @property
    def Position(self):
        className = self.ClassName.lower()
        if "part" in className:
            position_vector3 = self.memory_module.read_floats(
                self.primitive_address + primitive_offsets["Position"],
                3
            )
            return Vector3(*position_vector3)
        elif className == "camera":
            position_vector3 = self.memory_module.read_floats(
                self.raw_address + camera_offsets["Position"],
                3
            )
            return Vector3(*position_vector3)
        elif className == "attachment":
            position_vector3 = self.memory_module.read_floats(
                self.raw_address + attachment_offsets["Position"],
                3
            )
            return Vector3(*position_vector3)
        else:
            return self._read_udim2(self.raw_address + gui_offsets["Position"])

    @Position.setter
    def Position(self, value):
        className = self.ClassName.lower()
        
        self._ensure_writable()
        if "part" in className:
            vec = self._as_vector3(value, "Position")
            self.memory_module.write_floats(
                self.primitive_address + primitive_offsets["Position"],
                (vec.X, vec.Y, vec.Z)
            )

        elif className == "camera":
            vec = self._as_vector3(value, "Position")
            self.memory_module.write_floats(
                self.raw_address + camera_offsets["Position"],
                (vec.X, vec.Y, vec.Z)
            )

        elif className == "attachment":
            vec = self._as_vector3(value, "Position")
            self.memory_module.write_floats(
                self.raw_address + attachment_offsets["Position"],
                (vec.X, vec.Y, vec.Z)
            )

        else:
            udim2_value = self._as_udim2(value, "Position")
            self._write_udim2(self.raw_address + gui_offsets["Position"], udim2_value)

    @property
    def AssemblyLinearVelocity(self):
        className = self.ClassName

        if "part" in className.lower():
            velocity_vector3 = self.memory_module.read_floats(
                self.primitive_address + primitive_offsets["AssemblyLinearVelocity"],
                3
            )
            return Vector3(*velocity_vector3)
        
        return None

    @AssemblyLinearVelocity.setter
    def AssemblyLinearVelocity(self, value):
        className = self.ClassName
        if "part" not in className.lower():
            raise AttributeError("AssemblyLinearVelocity can only be written for BasePart-derived instances.")
        
        vec = self._as_vector3(value, "AssemblyLinearVelocity")
        
        self._ensure_writable()
        self.memory_module.write_floats(
            self.primitive_address + primitive_offsets["AssemblyLinearVelocity"],
            (vec.X, vec.Y, vec.Z)
        )

    @property
    def AssemblyAngularVelocity(self):
        className = self.ClassName

        if "part" in className.lower():
            velocity_vector3 = self.memory_module.read_floats(
                self.primitive_address + primitive_offsets["AssemblyAngularVelocity"],
                3
            )
            return Vector3(*velocity_vector3)
        
        return None

    @AssemblyAngularVelocity.setter
    def AssemblyAngularVelocity(self, value):
        className = self.ClassName
        if "part" not in className.lower():
            raise AttributeError("AssemblyAngularVelocity can only be written for BasePart-derived instances.")
        
        vec = self._as_vector3(value, "AssemblyAngularVelocity")
        
        self._ensure_writable()
        self.memory_module.write_floats(
            self.primitive_address + primitive_offsets["AssemblyAngularVelocity"],
            (vec.X, vec.Y, vec.Z)
        )

    @property
    def Velocity(self):
        return self.AssemblyLinearVelocity

    @Velocity.setter
    def Velocity(self, value):
        self.AssemblyLinearVelocity = value

    @property
    def LayoutOrder(self):
        return self.memory_module.read_int(
            self.raw_address,
            gui_offsets["LayoutOrder"]
        )

    @LayoutOrder.setter
    def LayoutOrder(self, value: int):
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + gui_offsets["LayoutOrder"],
            value
        )

    @property
    def Enabled(self):
        return self._read_class_bool("Enabled", _ENABLED_OFFSETS_BY_CLASS)

    @Enabled.setter
    def Enabled(self, value: bool):
        self._write_class_bool("Enabled", _ENABLED_OFFSETS_BY_CLASS, value)
    
    @property
    def Visible(self):
        return self.memory_module.read_bool(
            self.raw_address,
            gui_offsets["Visible"]
        )

    @Visible.setter
    def Visible(self, value: bool):
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + gui_offsets["Visible"],
            value
        )

    @property
    def Image(self):
        return self.memory_module.read_string(
            self.raw_address,
            gui_offsets["Image"]
        )
    
    @Image.setter
    def Image(self, value: str):
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + gui_offsets["Image"],
            value
        )

    @property
    def Size(self):
        className = self.ClassName
        if className == "BloomEffect":
            return self.memory_module.read_float(
                self.raw_address,
                bloom_effect_offsets["Size"]
            )
        if "part" in className.lower():
            size_vector3 = self.memory_module.read_floats(
                self.primitive_address + primitive_offsets["Size"],
                3
            )
            return Vector3(*size_vector3)
        else:
            return self._read_udim2(self.raw_address + gui_offsets["Size"])

    @Size.setter
    def Size(self, value):
        self._ensure_writable()
        className = self.ClassName
        if className == "BloomEffect":
            self.memory_module.write_float(
                self.raw_address + bloom_effect_offsets["Size"],
                float(value)
            )
        elif "part" in className.lower():
            vec = self._as_vector3(value, "Size")
            self.memory_module.write_floats(
                self.primitive_address + primitive_offsets["Size"],
                (vec.X, vec.Y, vec.Z)
            )
        else:
            gui_size = self._as_udim2(value, "Size")
            self._write_udim2(self.raw_address + gui_offsets["Size"], gui_size)

    @property
    def AbsoluteSize(self):
        SizeData = self.memory_module.read_floats(
            self.raw_address + gui_2d_offsets["AbsoluteSize"],
            2
        )

        return Vector2(*SizeData)
    
    @AbsoluteSize.setter
    def AbsoluteSize(self, value):
        self._ensure_writable()
        vec = self._as_vector2(value, "AbsoluteSize")
        self.memory_module.write_floats(
            self.raw_address + gui_2d_offsets["AbsoluteSize"],
            (vec.X, vec.Y)
        )
    
    @property
    def AbsolutePosition(self):
        PositionData = self.memory_module.read_floats(
            self.raw_address + gui_2d_offsets["AbsolutePosition"],
            2
        )

        return Vector2(*PositionData)
    
    @AbsolutePosition.setter
    def AbsolutePosition(self, value):
        self._ensure_writable()
        vec = self._as_vector2(value, "AbsolutePosition")
        self.memory_module.write_floats(
            self.raw_address + gui_2d_offsets["AbsolutePosition"],
            (vec.X, vec.Y)
        )

    @property
    def AbsoluteRotation(self):
        return self.memory_module.read_float(
            self.raw_address + gui_2d_offsets["AbsoluteRotation"]
        )

    @property
    def Transparency(self):
        if "part" not in self.ClassName.lower():
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            basepart_offsets["Transparency"]
        )

    @Transparency.setter
    def Transparency(self, value: float):
        if "part" not in self.ClassName.lower():
            raise AttributeError("Transparency is only available on BasePart-derived instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + basepart_offsets["Transparency"],
            float(value)
        )

    @property
    def Color(self):
        className = self.ClassName
        if className == "Atmosphere":
            return self._read_class_color3("Color", _ATMOSPHERE_COLOR_OFFSETS_BY_CLASS)
        if className == "SurfaceAppearance":
            return Color3(*self.memory_module.read_floats(
                self.raw_address + surfaceappearance_offsets["Color"],
                3
            ))
        if "part" not in className.lower():
            return None
        
        # Color is stored as 3 bytes (R, G, B) rather than floats
        color_bytes = self.memory_module.read(self.raw_address + basepart_offsets["Color3"], 3)
        if len(color_bytes) == 3:
            return Color3(color_bytes[0] / 255.0, color_bytes[1] / 255.0, color_bytes[2] / 255.0)
        return Color3(0, 0, 0)

    @Color.setter
    def Color(self, value):
        className = self.ClassName
        if className == "Atmosphere":
            self._write_class_color3("Color", _ATMOSPHERE_COLOR_OFFSETS_BY_CLASS, value)
            return
        if className == "SurfaceAppearance":
            self._ensure_writable()
            color = self._as_color3(value, "Color")
            self.memory_module.write_floats(
                self.raw_address + surfaceappearance_offsets["Color"],
                self._color3_tuple(color)
            )
            return
        if "part" not in className.lower():
            raise AttributeError("Color is only available on BasePart-derived, Atmosphere, or SurfaceAppearance instances.")
        self._ensure_writable()

        vec = self._as_color3(value, "Color3")
        r, g, b = int(vec.R * 255), int(vec.G * 255), int(vec.B * 255)
        # Write 3 bytes directly
        self.memory_module.write(
            self.raw_address + basepart_offsets["Color3"],
            bytes([r & 0xFF, g & 0xFF, b & 0xFF])
        )

    @property
    def Reflectance(self):
        if "part" not in self.ClassName.lower():
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            basepart_offsets["Reflectance"]
        )

    @Reflectance.setter
    def Reflectance(self, value: float):
        if "part" not in self.ClassName.lower():
            raise AttributeError("Reflectance is only available on BasePart-derived instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + basepart_offsets["Reflectance"],
            float(value)
        )

    @property
    def Locked(self):
        if "part" not in self.ClassName.lower():
            return None
        
        return self.memory_module.read_bool(
            self.raw_address,
            basepart_offsets["Locked"]
        )

    @Locked.setter
    def Locked(self, value: bool):
        if "part" not in self.ClassName.lower():
            raise AttributeError("Locked is only available on BasePart-derived instances.")
        self._ensure_writable()

        self.memory_module.write_bool(
            self.raw_address + basepart_offsets["Locked"],
            bool(value)
        )

    @property
    def Massless(self):
        if "part" not in self.ClassName.lower():
            return None
        
        return self.memory_module.read_bool(
            self.raw_address,
            basepart_offsets["Massless"]
        )

    @Massless.setter
    def Massless(self, value: bool):
        if "part" not in self.ClassName.lower():
            raise AttributeError("Massless is only available on BasePart-derived instances.")
        self._ensure_writable()

        self.memory_module.write_bool(
            self.raw_address + basepart_offsets["Massless"],
            bool(value)
        )

    @property
    def CastShadow(self):
        if "part" not in self.ClassName.lower():
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            basepart_offsets["CastShadow"]
        )

    @CastShadow.setter
    def CastShadow(self, value: bool):
        if "part" not in self.ClassName.lower():
            raise AttributeError("CastShadow is only available on BasePart-derived instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + basepart_offsets["CastShadow"],
            bool(value)
        )

    @property
    def Shape(self):
        if "part" not in self.ClassName.lower():
            return None
        return self.memory_module.read_int(
            self.raw_address,
            basepart_offsets["Shape"]
        )

    @Shape.setter
    def Shape(self, value: int):
        if "part" not in self.ClassName.lower():
            raise AttributeError("Shape is only available on BasePart-derived instances.")
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + basepart_offsets["Shape"],
            int(value)
        )

    def _read_primitive_flags(self):
        data = self.memory_module.read(
            self.primitive_address + primitive_offsets["Flags"], 
            1
        )
        return int.from_bytes(data, 'little') if data else 0

    def _write_primitive_flags(self, flags: int):
        self._ensure_writable()
        self.memory_module.write(
            self.primitive_address + primitive_offsets["Flags"],
            (flags & 0xFF).to_bytes(1, 'little')
        )

    @property
    def Anchored(self):
        if "part" not in self.ClassName.lower():
            return None
        
        flags = self._read_primitive_flags()
        return bool(flags & Offsets["PrimitiveFlags"]["Anchored"])

    @Anchored.setter
    def Anchored(self, value: bool):
        if "part" not in self.ClassName.lower():
            raise AttributeError("Anchored is only available on BasePart-derived instances.")
        
        flags = self._read_primitive_flags()
        if value:
            flags |= Offsets["PrimitiveFlags"]["Anchored"]
        else:
            flags &= ~Offsets["PrimitiveFlags"]["Anchored"]
        self._write_primitive_flags(flags)

    @property
    def CanCollide(self):
        if "part" not in self.ClassName.lower():
            return None
        
        flags = self._read_primitive_flags()
        return bool(flags & Offsets["PrimitiveFlags"]["CanCollide"])

    @CanCollide.setter
    def CanCollide(self, value: bool):
        if "part" not in self.ClassName.lower():
            raise AttributeError("CanCollide is only available on BasePart-derived instances.")
        
        flags = self._read_primitive_flags()
        if value:
            flags |= Offsets["PrimitiveFlags"]["CanCollide"]
        else:
            flags &= ~Offsets["PrimitiveFlags"]["CanCollide"]
        self._write_primitive_flags(flags)

    @property
    def CanTouch(self):
        if "part" not in self.ClassName.lower():
            return None
        
        flags = self._read_primitive_flags()
        return bool(flags & Offsets["PrimitiveFlags"]["CanTouch"])

    @CanTouch.setter
    def CanTouch(self, value: bool):
        if "part" not in self.ClassName.lower():
            raise AttributeError("CanTouch is only available on BasePart-derived instances.")
        
        flags = self._read_primitive_flags()
        if value:
            flags |= Offsets["PrimitiveFlags"]["CanTouch"]
        else:
            flags &= ~Offsets["PrimitiveFlags"]["CanTouch"]
        self._write_primitive_flags(flags)

    @property
    def CanQuery(self):
        if "part" not in self.ClassName.lower():
            return None
        
        flags = self._read_primitive_flags()
        return bool(flags & Offsets["PrimitiveFlags"]["CanQuery"])

    @CanQuery.setter
    def CanQuery(self, value: bool):
        if "part" not in self.ClassName.lower():
            raise AttributeError("CanQuery is only available on BasePart-derived instances.")
        
        flags = self._read_primitive_flags()
        if value:
            flags |= Offsets["PrimitiveFlags"]["CanQuery"]
        else:
            flags &= ~Offsets["PrimitiveFlags"]["CanQuery"]
        self._write_primitive_flags(flags)

    # Animator props #
    def GetPlayingAnimationTracks(self):
        if self.ClassName != "Animator":
            raise AttributeError("GetPlayingAnimationTracks is only available on Animator instances.")

        head = self.memory_module.get_pointer(
            self.raw_address,
            animator_offsets["ActiveAnimations"]
        )
        if head == 0:
            return []

        node = self.memory_module.get_pointer(head)
        result = []

        while node != 0 and node != head:
            track_address = self.memory_module.get_pointer(node, 0x10)
            animation_track = AnimationTrack(track_address, self.memory_module, animationtrack_offsets)
            
            try:
                if animation_track.Animation.AnimationId is None:
                    raise Exception("AnimationId is None")
                
                result.append(animation_track)
            except Exception:
                pass
            node = self.memory_module.get_pointer(node)

        return result

    # ProximityPrompt props #
    @property
    def MaxActivationDistance(self):
        className = self.ClassName
        if className == "ProximityPrompt":
            return self.memory_module.read_float(
                self.raw_address,
                proximityprompt_offsets["MaxActivationDistance"]
            )
        elif className == "ClickDetector":
            return self.memory_module.read_float(
                self.raw_address,
                clickdetector_offsets["MaxActivationDistance"]
            )
        elif className == "DragDetector":
            return self.memory_module.read_float(
                self.raw_address,
                dragdetector_offsets["MaxActivationDistance"]
            )
        return None

    @MaxActivationDistance.setter
    def MaxActivationDistance(self, value: float):
        className = self.ClassName
        self._ensure_writable()
        if className == "ProximityPrompt":
            self.memory_module.write_float(
                self.raw_address + proximityprompt_offsets["MaxActivationDistance"],
                float(value)
            )
        elif className == "ClickDetector":
            self.memory_module.write_float(
                self.raw_address + clickdetector_offsets["MaxActivationDistance"],
                float(value)
            )
        elif className == "DragDetector":
            self.memory_module.write_float(
                self.raw_address + dragdetector_offsets["MaxActivationDistance"],
                float(value)
            )
        else:
            raise AttributeError("MaxActivationDistance is only available on ProximityPrompt, ClickDetector, or DragDetector.")

    @property
    def HoldDuration(self):
        if self.ClassName != "ProximityPrompt":
            return None
        return self.memory_module.read_float(
            self.raw_address,
            proximityprompt_offsets["HoldDuration"]
        )

    @HoldDuration.setter
    def HoldDuration(self, value: float):
        if self.ClassName != "ProximityPrompt":
            raise AttributeError("HoldDuration is only available on ProximityPrompt.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + proximityprompt_offsets["HoldDuration"],
            float(value)
        )

    @property
    def ObjectText(self):
        if self.ClassName != "ProximityPrompt":
            return None
        return self.memory_module.read_string(
            self.raw_address,
            proximityprompt_offsets["ObjectText"]
        )

    @ObjectText.setter
    def ObjectText(self, value: str):
        if self.ClassName != "ProximityPrompt":
            raise AttributeError("ObjectText is only available on ProximityPrompt.")
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + proximityprompt_offsets["ObjectText"],
            str(value)
        )

    @property
    def ActionText(self):
        if self.ClassName != "ProximityPrompt":
            return None
        return self.memory_module.read_string(
            self.raw_address,
            proximityprompt_offsets["ActionText"]
        )

    @ActionText.setter
    def ActionText(self, value: str):
        if self.ClassName != "ProximityPrompt":
            raise AttributeError("ActionText is only available on ProximityPrompt.")
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + proximityprompt_offsets["ActionText"],
            str(value)
        )

    @property
    def RequiresLineOfSight(self):
        if self.ClassName != "ProximityPrompt":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            proximityprompt_offsets["RequiresLineOfSight"]
        )

    @RequiresLineOfSight.setter
    def RequiresLineOfSight(self, value: bool):
        if self.ClassName != "ProximityPrompt":
            raise AttributeError("RequiresLineOfSight is only available on ProximityPrompt.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + proximityprompt_offsets["RequiresLineOfSight"],
            bool(value)
        )

    # ClickDetector props #
    @property
    def CursorIcon(self):
        cn = self.ClassName
        if cn == "ClickDetector":
            return self.memory_module.read_string(
                self.raw_address,
                clickdetector_offsets["CursorIcon"]
            )
        if cn == "DragDetector":
            return self.memory_module.read_string(
                self.raw_address,
                dragdetector_offsets["CursorIcon"]
            )
        return None

    @CursorIcon.setter
    def CursorIcon(self, value: str):
        cn = self.ClassName
        self._ensure_writable()
        if cn == "ClickDetector":
            self.memory_module.write_string(
                self.raw_address + clickdetector_offsets["CursorIcon"],
                str(value)
            )
        elif cn == "DragDetector":
            self.memory_module.write_string(
                self.raw_address + dragdetector_offsets["CursorIcon"],
                str(value)
            )
        else:
            raise AttributeError("CursorIcon is only available on ClickDetector or DragDetector.")

    # DragDetector props #
    @property
    def ActivatedCursorIcon(self):
        if self.ClassName != "DragDetector":
            return None
        return self.memory_module.read_string(
            self.raw_address,
            dragdetector_offsets["ActivatedCursorIcon"]
        )

    @ActivatedCursorIcon.setter
    def ActivatedCursorIcon(self, value: str):
        if self.ClassName != "DragDetector":
            raise AttributeError("ActivatedCursorIcon is only available on DragDetector instances.")
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + dragdetector_offsets["ActivatedCursorIcon"],
            str(value)
        )

    @property
    def ReferenceInstance(self):
        if self.ClassName != "DragDetector":
            return None
        ptr = self.memory_module.get_pointer(
            self.raw_address,
            dragdetector_offsets["ReferenceInstance"]
        )
        return RBXInstance(ptr, self.memory_module) if ptr != 0 else None

    @ReferenceInstance.setter
    def ReferenceInstance(self, value):
        if self.ClassName != "DragDetector":
            raise AttributeError("ReferenceInstance is only available on DragDetector instances.")
        self._ensure_writable()
        if value is None:
            target = 0
        elif isinstance(value, RBXInstance):
            target = value.raw_address
        elif isinstance(value, int):
            target = value
        else:
            raise TypeError("ReferenceInstance must be set to an RBXInstance, int address, or None.")
        self.memory_module.write_long(
            self.raw_address + dragdetector_offsets["ReferenceInstance"],
            target
        )

    @property
    def MaxDragAngle(self):
        return self._read_class_float("MaxDragAngle", {"DragDetector": dragdetector_offsets})

    @MaxDragAngle.setter
    def MaxDragAngle(self, value: float):
        self._write_class_float("MaxDragAngle", {"DragDetector": dragdetector_offsets}, value)

    @property
    def MinDragAngle(self):
        return self._read_class_float("MinDragAngle", {"DragDetector": dragdetector_offsets})

    @MinDragAngle.setter
    def MinDragAngle(self, value: float):
        self._write_class_float("MinDragAngle", {"DragDetector": dragdetector_offsets}, value)

    @property
    def MaxDragTranslation(self):
        if self.ClassName != "DragDetector":
            return None
        data = self.memory_module.read_floats(
            self.raw_address + dragdetector_offsets["MaxDragTranslation"],
            3
        )
        return Vector3(*data)

    @MaxDragTranslation.setter
    def MaxDragTranslation(self, value):
        if self.ClassName != "DragDetector":
            raise AttributeError("MaxDragTranslation is only available on DragDetector instances.")
        self._ensure_writable()
        vec = self._as_vector3(value, "MaxDragTranslation")
        self.memory_module.write_floats(
            self.raw_address + dragdetector_offsets["MaxDragTranslation"],
            (vec.X, vec.Y, vec.Z)
        )

    @property
    def MinDragTranslation(self):
        if self.ClassName != "DragDetector":
            return None
        data = self.memory_module.read_floats(
            self.raw_address + dragdetector_offsets["MinDragTranslation"],
            3
        )
        return Vector3(*data)

    @MinDragTranslation.setter
    def MinDragTranslation(self, value):
        if self.ClassName != "DragDetector":
            raise AttributeError("MinDragTranslation is only available on DragDetector instances.")
        self._ensure_writable()
        vec = self._as_vector3(value, "MinDragTranslation")
        self.memory_module.write_floats(
            self.raw_address + dragdetector_offsets["MinDragTranslation"],
            (vec.X, vec.Y, vec.Z)
        )

    @property
    def MaxForce(self):
        return self._read_class_float("MaxForce", {"DragDetector": dragdetector_offsets})

    @MaxForce.setter
    def MaxForce(self, value: float):
        self._write_class_float("MaxForce", {"DragDetector": dragdetector_offsets}, value)

    @property
    def MaxTorque(self):
        return self._read_class_float("MaxTorque", {"DragDetector": dragdetector_offsets})

    @MaxTorque.setter
    def MaxTorque(self, value: float):
        self._write_class_float("MaxTorque", {"DragDetector": dragdetector_offsets}, value)

    @property
    def Responsiveness(self):
        return self._read_class_float("Responsiveness", {"DragDetector": dragdetector_offsets})

    @Responsiveness.setter
    def Responsiveness(self, value: float):
        self._write_class_float("Responsiveness", {"DragDetector": dragdetector_offsets}, value)

    # XXXXValue props #
    def GetValue(self):
        classname = self.ClassName 
        if classname == "StatsItem":
            value_address = self.raw_address + statsitem_offsets["Value"]
            
            return self.memory_module.read_float(value_address)

        return None

    def SetValue(self, value):
        classname = self.ClassName 
        if classname == "StatsItem":
            value_address = self.raw_address + statsitem_offsets["Value"]
            
            self.memory_module.write_float(value_address, float(value))

    @property
    def Value(self):
        classname = self.ClassName 
        value_address = self.raw_address + misc_offsets["Value"]
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
                misc_offsets["Value"]
            )

            if object_address == 0:
                return None

            return RBXInstance(object_address, self.memory_module)

        return None

    @Value.setter
    def Value(self, new_value):
        self._ensure_writable()
        classname = self.ClassName
        value_address = self.raw_address + misc_offsets["Value"]

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

        value_address = self.raw_address + misc_offsets["Value"]
        return self.memory_module.read_int(value_address + 0x18)

    # text props #
    @property
    def Text(self):
        if "text" in self.ClassName.lower():
            return self.memory_module.read_string(
                self.raw_address,
                gui_offsets["Text"]
            )
        
        return None

    @Text.setter
    def Text(self, value: str):
        if "text" not in self.ClassName.lower():
            raise AttributeError("Text is not available on this instance.")
        self.memory_module.write_string(
            self.raw_address + gui_offsets["Text"],
            str(value)
        )

    @property
    def RichText(self):
        return self.memory_module.read_bool(
            self.raw_address,
            gui_offsets["RichText"]
        )

    @RichText.setter
    def RichText(self, value: bool):
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + gui_offsets["RichText"],
            bool(value)
        )

    @property
    def BackgroundColor3(self):
        color_data = self.memory_module.read_floats(
            self.raw_address + gui_offsets["BackgroundColor3"],
            3
        )
        return Color3(*color_data)

    @BackgroundColor3.setter
    def BackgroundColor3(self, value):
        self._ensure_writable()
        vec = self._as_color3(value, "BackgroundColor3")
        self.memory_module.write_floats(
            self.raw_address + gui_offsets["BackgroundColor3"],
            (vec.R, vec.G, vec.B)
        )

    @property
    def BorderColor3(self):
        color_data = self.memory_module.read_floats(
            self.raw_address + gui_offsets["BorderColor3"],
            3
        )
        return Color3(*color_data)

    @BorderColor3.setter
    def BorderColor3(self, value):
        self._ensure_writable()
        vec = self._as_color3(value, "BorderColor3")
        self.memory_module.write_floats(
            self.raw_address + gui_offsets["BorderColor3"],
            (vec.R, vec.G, vec.B)
        )

    @property
    def TextColor3(self):
        color_data = self.memory_module.read_floats(
            self.raw_address + gui_offsets["TextColor3"],
            3
        )
        return Color3(*color_data)

    @TextColor3.setter
    def TextColor3(self, value):
        self._ensure_writable()
        vec = self._as_color3(value, "TextColor3")
        self.memory_module.write_floats(
            self.raw_address + gui_offsets["TextColor3"],
            (vec.R, vec.G, vec.B)
        )

    @property
    def Rotation(self):
        className = self.ClassName.lower()
        if className == "particleemitter":
            data = self.memory_module.read_floats(
                self.raw_address + particleemitter_offsets["Rotation"],
                2
            )
            return NumberRange(*data)
        if "part" in className:
            # BasePart rotation handled via CFrame
            return None
        else:
            return self.memory_module.read_float(
                self.raw_address,
                gui_offsets["Rotation"]
            )

    @Rotation.setter
    def Rotation(self, value: float):
        className = self.ClassName.lower()
        if className == "particleemitter":
            self._ensure_writable()
            if isinstance(value, NumberRange):
                vals = (value.Min, value.Max)
            elif isinstance(value, (tuple, list)) and len(value) == 2:
                vals = (float(value[0]), float(value[1]))
            else:
                v = float(value)
                vals = (v, v)
            self.memory_module.write_floats(
                self.raw_address + particleemitter_offsets["Rotation"],
                vals
            )
            return
        if "part" in className:
            raise AttributeError("Use CFrame to set rotation on BasePart instances.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + gui_offsets["Rotation"],
            float(value)
        )

    @property
    def BackgroundTransparency(self):
        return self.memory_module.read_float(
            self.raw_address + gui_offsets["BackgroundTransparency"]
        )

    @BackgroundTransparency.setter
    def BackgroundTransparency(self, value: float):
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + gui_offsets["BackgroundTransparency"],
            float(value)
        )

    @property
    def ZIndex(self):
        return self.memory_module.read_int(
            self.raw_address + gui_offsets["ZIndex"]
        )

    @ZIndex.setter
    def ZIndex(self, value: int):
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + gui_offsets["ZIndex"],
            int(value)
        )

    # tool props #
    @property
    def CanBeDropped(self):
        if self.ClassName != "Tool":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            tool_offsets["CanBeDropped"]
        )

    @CanBeDropped.setter
    def CanBeDropped(self, value: bool):
        if self.ClassName != "Tool":
            raise AttributeError("CanBeDropped is only available on Tool instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + tool_offsets["CanBeDropped"],
            bool(value)
        )

    @property
    def Grip(self):
        if self.ClassName != "Tool":
            return None
        grip_data = self.memory_module.read_floats(
            self.raw_address + tool_offsets["Grip"],
            12  # CFrame: 9 rotation + 3 position
        )
        return grip_data

    @property
    def ManualActivationOnly(self):
        if self.ClassName != "Tool":
            return None
        return self.memory_module.read_bool(
            self.raw_address + tool_offsets["ManualActivationOnly"]
        )

    @ManualActivationOnly.setter
    def ManualActivationOnly(self, value: bool):
        if self.ClassName != "Tool":
            raise AttributeError("ManualActivationOnly is only available on Tool instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + tool_offsets["ManualActivationOnly"],
            bool(value)
        )

    @property
    def RequiresHandle(self):
        if self.ClassName != "Tool":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            tool_offsets["RequiresHandle"]
        )

    @RequiresHandle.setter
    def RequiresHandle(self, value: bool):
        if self.ClassName != "Tool":
            raise AttributeError("RequiresHandle is only available on Tool instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + tool_offsets["RequiresHandle"],
            bool(value)
        )

    @property
    def TextureId(self):
        className = self.ClassName
        if className == "Tool":
            return self.memory_module.read_string(
                self.raw_address,
                tool_offsets["TextureId"]
            )
        elif className == "MeshPart":
            return self.memory_module.read_string(
                self.raw_address,
                meshpart_offsets["Texture"]
            )
        elif className == "Decal":
            return self.memory_module.read_string(
                self.raw_address,
                textures_offsets["Decal_Texture"]
            )
        elif className == "Texture":
            return self.memory_module.read_string(
                self.raw_address,
                textures_offsets["Texture_Texture"]
            )
        return None

    @TextureId.setter
    def TextureId(self, value: str):
        className = self.ClassName
        self._ensure_writable()
        if className == "Tool":
            self.memory_module.write_string(
                self.raw_address + tool_offsets["TextureId"],
                str(value)
            )
        elif className == "MeshPart":
            self.memory_module.write_string(
                self.raw_address + meshpart_offsets["Texture"],
                str(value)
            )
        elif className == "Decal":
            self.memory_module.write_string(
                self.raw_address + textures_offsets["Decal_Texture"],
                str(value)
            )
        elif className == "Texture":
            self.memory_module.write_string(
                self.raw_address + textures_offsets["Texture_Texture"],
                str(value)
            )
        else:
            raise AttributeError("TextureId is only available on Tool, MeshPart, Decal, or Texture instances.")

    @property
    def Texture(self):
        cn = self.ClassName
        if cn == "Beam":
            return self.memory_module.read_string(self.raw_address, beam_offsets["Texture"])
        if cn == "ParticleEmitter":
            return self.memory_module.read_string(self.raw_address, particleemitter_offsets["Texture"])
        return None

    @Texture.setter
    def Texture(self, value: str):
        cn = self.ClassName
        self._ensure_writable()
        if cn == "Beam":
            self.memory_module.write_string(self.raw_address + beam_offsets["Texture"], str(value))
        elif cn == "ParticleEmitter":
            self.memory_module.write_string(self.raw_address + particleemitter_offsets["Texture"], str(value))
        else:
            raise AttributeError("Texture is only available on Beam or ParticleEmitter instances.")

    @property
    def MeshId(self):
        className = self.ClassName
        if className == "SpecialMesh":
            return self.memory_module.read_string(
                self.raw_address,
                specialmesh_offsets["MeshId"]
            )
        if className != "MeshPart":
            return None
        return self.memory_module.read_string(
            self.raw_address,
            meshpart_offsets["MeshId"]
        )

    @MeshId.setter
    def MeshId(self, value: str):
        className = self.ClassName
        if className == "SpecialMesh":
            self._ensure_writable()
            self.memory_module.write_string(
                self.raw_address + specialmesh_offsets["MeshId"],
                str(value)
            )
            return
        if className != "MeshPart":
            raise AttributeError("MeshId is only available on MeshPart or SpecialMesh instances.")
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + meshpart_offsets["MeshId"],
            str(value)
        )

    @property
    def Scale(self):
        if self.ClassName != "SpecialMesh":
            return None
        data = self.memory_module.read_floats(
            self.raw_address + specialmesh_offsets["Scale"],
            3
        )
        return Vector3(*data)

    @Scale.setter
    def Scale(self, value):
        if self.ClassName != "SpecialMesh":
            raise AttributeError("Scale is only available on SpecialMesh instances.")
        self._ensure_writable()
        scale = self._as_vector3(value, "Scale")
        self.memory_module.write_floats(
            self.raw_address + specialmesh_offsets["Scale"],
            (scale.X, scale.Y, scale.Z)
        )

    @property
    def Tooltip(self):
        if self.ClassName != "Tool":
            return None
        return self.memory_module.read_string(
            self.raw_address,
            tool_offsets["Tooltip"]
        )

    @Tooltip.setter
    def Tooltip(self, value: str):
        if self.ClassName != "Tool":
            raise AttributeError("Tooltip is only available on Tool instances.")
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + tool_offsets["Tooltip"],
            str(value)
        )

    # atmosphere / post-processing props #
    @property
    def Decay(self):
        return self._read_class_color3("Decay", {"Atmosphere": atmosphere_offsets})

    @Decay.setter
    def Decay(self, value):
        self._write_class_color3("Decay", {"Atmosphere": atmosphere_offsets}, value)

    @property
    def Density(self):
        return self._read_class_float("Density", {"Atmosphere": atmosphere_offsets})

    @Density.setter
    def Density(self, value: float):
        self._write_class_float("Density", {"Atmosphere": atmosphere_offsets}, value)

    @property
    def Glare(self):
        return self._read_class_float("Glare", {"Atmosphere": atmosphere_offsets})

    @Glare.setter
    def Glare(self, value: float):
        self._write_class_float("Glare", {"Atmosphere": atmosphere_offsets}, value)

    @property
    def Haze(self):
        return self._read_class_float("Haze", {"Atmosphere": atmosphere_offsets})

    @Haze.setter
    def Haze(self, value: float):
        self._write_class_float("Haze", {"Atmosphere": atmosphere_offsets}, value)

    @property
    def Offset(self):
        return self._read_class_float("Offset", {"Atmosphere": atmosphere_offsets})

    @Offset.setter
    def Offset(self, value: float):
        self._write_class_float("Offset", {"Atmosphere": atmosphere_offsets}, value)

    @property
    def Intensity(self):
        return self._read_class_float("Intensity", _EFFECT_INTENSITY_OFFSETS_BY_CLASS)

    @Intensity.setter
    def Intensity(self, value: float):
        self._write_class_float("Intensity", _EFFECT_INTENSITY_OFFSETS_BY_CLASS, value)

    @property
    def Threshold(self):
        return self._read_class_float("Threshold", {"BloomEffect": bloom_effect_offsets})

    @Threshold.setter
    def Threshold(self, value: float):
        self._write_class_float("Threshold", {"BloomEffect": bloom_effect_offsets}, value)

    @property
    def FarIntensity(self):
        return self._read_class_float("FarIntensity", {"DepthOfFieldEffect": depth_of_field_effect_offsets})

    @FarIntensity.setter
    def FarIntensity(self, value: float):
        self._write_class_float("FarIntensity", {"DepthOfFieldEffect": depth_of_field_effect_offsets}, value)

    @property
    def FocusDistance(self):
        return self._read_class_float("FocusDistance", {"DepthOfFieldEffect": depth_of_field_effect_offsets})

    @FocusDistance.setter
    def FocusDistance(self, value: float):
        self._write_class_float("FocusDistance", {"DepthOfFieldEffect": depth_of_field_effect_offsets}, value)

    @property
    def InFocusRadius(self):
        return self._read_class_float("InFocusRadius", {"DepthOfFieldEffect": depth_of_field_effect_offsets})

    @InFocusRadius.setter
    def InFocusRadius(self, value: float):
        self._write_class_float("InFocusRadius", {"DepthOfFieldEffect": depth_of_field_effect_offsets}, value)

    @property
    def NearIntensity(self):
        return self._read_class_float("NearIntensity", {"DepthOfFieldEffect": depth_of_field_effect_offsets})

    @NearIntensity.setter
    def NearIntensity(self, value: float):
        self._write_class_float("NearIntensity", {"DepthOfFieldEffect": depth_of_field_effect_offsets}, value)

    @property
    def Spread(self):
        return self._read_class_float("Spread", {"SunRaysEffect": sun_rays_effect_offsets})

    @Spread.setter
    def Spread(self, value: float):
        self._write_class_float("Spread", {"SunRaysEffect": sun_rays_effect_offsets}, value)

    # colorcorrection props #
    @property
    def Brightness(self):
        cn = self.ClassName
        if cn == "ColorCorrectionEffect":
            return self.memory_module.read_float(
                self.raw_address,
                Offsets["ColorCorrectionEffect"]["Brightness"]
            )
        elif cn == "Beam":
            return self.memory_module.read_float(self.raw_address, beam_offsets["Brightness"])
        elif cn == "ParticleEmitter":
            return self.memory_module.read_float(self.raw_address, particleemitter_offsets["Brightness"])
        return None

    @Brightness.setter
    def Brightness(self, value: float):
        cn = self.ClassName
        self._ensure_writable()
        if cn == "ColorCorrectionEffect":
            self.memory_module.write_float(
                self.raw_address + Offsets["ColorCorrectionEffect"]["Brightness"],
                float(value)
            )
        elif cn == "Beam":
            self.memory_module.write_float(self.raw_address + beam_offsets["Brightness"], float(value))
        elif cn == "ParticleEmitter":
            self.memory_module.write_float(self.raw_address + particleemitter_offsets["Brightness"], float(value))
        else:
            raise AttributeError("Brightness is only available on ColorCorrectionEffect, Beam, or ParticleEmitter instances.")

    @property
    def Contrast(self):
        if self.ClassName != "ColorCorrectionEffect":
            return None
        return self.memory_module.read_float(
            self.raw_address,
            Offsets["ColorCorrectionEffect"]["Contrast"]
        )

    @Contrast.setter
    def Contrast(self, value: float):
        if self.ClassName != "ColorCorrectionEffect":
            raise AttributeError("Contrast is only available on ColorCorrectionEffect instances.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + Offsets["ColorCorrectionEffect"]["Contrast"],
            float(value)
        )

    @property
    def TintColor(self):
        if self.ClassName != "ColorCorrectionEffect":
            return None
        color_data = self.memory_module.read_floats(
            self.raw_address + Offsets["ColorCorrectionEffect"]["TintColor"],
            3
        )
        return Color3(*color_data)

    @TintColor.setter
    def TintColor(self, value):
        if self.ClassName != "ColorCorrectionEffect":
            raise AttributeError("TintColor is only available on ColorCorrectionEffect instances.")
        self._ensure_writable()
        vec = self._as_color3(value, "TintColor")
        self.memory_module.write_floats(
            self.raw_address + Offsets["ColorCorrectionEffect"]["TintColor"],
            self._color3_tuple(vec)
        )

    # blureffect props #
    @property
    def BlurSize(self):
        if self.ClassName != "BlurEffect":
            return None
        return self.memory_module.read_float(
            self.raw_address + Offsets["BlurEffect"]["Size"]
        )

    @BlurSize.setter
    def BlurSize(self, value: float):
        if self.ClassName != "BlurEffect":
            raise AttributeError("BlurSize is only available on BlurEffect instances.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + Offsets["BlurEffect"]["Size"],
            float(value)
        )

    # colorgradingeffect props #
    @property
    def TonemapperPreset(self):
        if self.ClassName != "ColorGradingEffect":
            return None
        return self.memory_module.read_int(
            self.raw_address + Offsets["ColorGradingEffect"]["TonemapperPreset"]
        )

    @TonemapperPreset.setter
    def TonemapperPreset(self, value: int):
        if self.ClassName != "ColorGradingEffect":
            raise AttributeError("TonemapperPreset is only available on ColorGradingEffect instances.")
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + Offsets["ColorGradingEffect"]["TonemapperPreset"],
            int(value)
        )

    # seat props #
    @property
    def Occupant(self):
        if self.ClassName != "Seat":
            return None
        ptr = self.memory_module.get_pointer(
            self.raw_address,
            seat_offsets["Occupant"]
        )
        if ptr == 0:
            return None
        return RBXInstance(ptr, self.memory_module)

    # charactermesh props #
    @property
    def BaseTextureId(self):
        if self.ClassName != "CharacterMesh":
            return None
        offset = charactermesh_offsets.get("BaseTextureId", 0)
        if offset == 0: return None
        return self.memory_module.read_string(
            self.raw_address + offset
        )

    @BaseTextureId.setter
    def BaseTextureId(self, value: int):
        if self.ClassName != "CharacterMesh":
            raise AttributeError("BaseTextureId is only available on CharacterMesh instances.")
        self._ensure_writable()
        offset = charactermesh_offsets.get("BaseTextureId", 0)
        if offset == 0: return
        self.memory_module.write_string(
            self.raw_address + offset,
            str(value)
        )

    @property
    def OverlayTextureId(self):
        if self.ClassName != "CharacterMesh":
            return None
        offset = charactermesh_offsets.get("OverlayTextureId", 0)
        if offset == 0: return None
        return self.memory_module.read_string(
            self.raw_address + offset
        )

    @OverlayTextureId.setter
    def OverlayTextureId(self, value: int):
        if self.ClassName != "CharacterMesh":
            raise AttributeError("OverlayTextureId is only available on CharacterMesh instances.")
        self._ensure_writable()
        offset = charactermesh_offsets.get("OverlayTextureId", 0)
        if offset == 0: return
        self.memory_module.write_string(
            self.raw_address + offset,
            str(value)
        )

    @property
    def BodyPart(self):
        if self.ClassName != "CharacterMesh":
            return None
        return self.memory_module.read_int(
            self.raw_address,
            charactermesh_offsets["BodyPart"]
        )

    @property
    def CharacterMeshId(self):
        if self.ClassName != "CharacterMesh":
            return None
        offset = charactermesh_offsets.get("MeshId", 0)
        if offset == 0: return None
        return self.memory_module.read_string(
            self.raw_address + offset
        )

    # clothing props (Shirt/Pants) #
    @property
    def ClothingColor3(self):
        cn = self.ClassName
        if cn != "Shirt" and cn != "Pants":
            return None
        color_data = self.memory_module.read_floats(
            self.raw_address + clothing_offsets["Color3"],
            3
        )
        return Color3(*color_data)

    @ClothingColor3.setter
    def ClothingColor3(self, value):
        cn = self.ClassName
        if cn != "Shirt" and cn != "Pants":
            raise AttributeError("ClothingColor3 is only available on Shirt or Pants instances.")
        self._ensure_writable()
        vec = self._as_color3(value, "ClothingColor3")
        self.memory_module.write_floats(
            self.raw_address + clothing_offsets["Color3"],
            self._color3_tuple(vec)
        )

    @property
    def Template(self):
        cn = self.ClassName
        if cn != "Shirt" and cn != "Pants":
            return None
        return self.memory_module.read_string(
            self.raw_address,
            clothing_offsets["Template"]
        )

    @Template.setter
    def Template(self, value: str):
        cn = self.ClassName
        if cn != "Shirt" and cn != "Pants":
            raise AttributeError("Template is only available on Shirt or Pants instances.")
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + clothing_offsets["Template"],
            str(value)
        )

    # sound props #
    @property
    def SoundId(self):
        if self.ClassName != "Sound":
            return None
        return self.memory_module.read_string(
            self.raw_address,
            sound_offsets["SoundId"]
        )

    @SoundId.setter
    def SoundId(self, value: str):
        if self.ClassName != "Sound":
            raise AttributeError("SoundId is only available on Sound instances.")
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + sound_offsets["SoundId"],
            str(value)
        )

    @property
    def Volume(self):
        if self.ClassName != "Sound":
            return None
        return self.memory_module.read_float(
            self.raw_address,
            sound_offsets["Volume"]
        )

    @Volume.setter
    def Volume(self, value: float):
        if self.ClassName != "Sound":
            raise AttributeError("Volume is only available on Sound instances.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + sound_offsets["Volume"],
            float(value)
        )

    @property
    def PlaybackSpeed(self):
        if self.ClassName != "Sound":
            return None
        return self.memory_module.read_float(
            self.raw_address,
            sound_offsets["PlaybackSpeed"]
        )

    @PlaybackSpeed.setter
    def PlaybackSpeed(self, value: float):
        if self.ClassName != "Sound":
            raise AttributeError("PlaybackSpeed is only available on Sound instances.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + sound_offsets["PlaybackSpeed"],
            float(value)
        )

    @property
    def Looped(self):
        if self.ClassName != "Sound":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            sound_offsets["Looped"]
        )

    @Looped.setter
    def Looped(self, value: bool):
        if self.ClassName != "Sound":
            raise AttributeError("Looped is only available on Sound instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + sound_offsets["Looped"],
            bool(value)
        )

    @property
    def Playing(self):
        if self.ClassName != "Sound":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            sound_offsets["Playing"]
        )

    @Playing.setter
    def Playing(self, value: bool):
        if self.ClassName != "Sound":
            raise AttributeError("Playing is only available on Sound instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + sound_offsets["Playing"],
            bool(value)
        )

    @property
    def RollOffMaxDistance(self):
        if self.ClassName != "Sound":
            return None
        return self.memory_module.read_float(
            self.raw_address,
            sound_offsets["RollOffMaxDistance"]
        )

    @RollOffMaxDistance.setter
    def RollOffMaxDistance(self, value: float):
        if self.ClassName != "Sound":
            raise AttributeError("RollOffMaxDistance is only available on Sound instances.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + sound_offsets["RollOffMaxDistance"],
            float(value)
        )

    @property
    def RollOffMinDistance(self):
        if self.ClassName != "Sound":
            return None
        return self.memory_module.read_float(
            self.raw_address,
            sound_offsets["RollOffMinDistance"]
        )

    @RollOffMinDistance.setter
    def RollOffMinDistance(self, value: float):
        if self.ClassName != "Sound":
            raise AttributeError("RollOffMinDistance is only available on Sound instances.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + sound_offsets["RollOffMinDistance"],
            float(value)
        )

    @property
    def SoundGroup(self):
        if self.ClassName != "Sound":
            return None
        ptr = self.memory_module.get_pointer(
            self.raw_address,
            sound_offsets["SoundGroup"]
        )
        if ptr == 0:
            return None
        return RBXInstance(ptr, self.memory_module)

    # spawnlocation props #
    @property
    def AllowTeamChangeOnTouch(self):
        if self.ClassName != "SpawnLocation":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            spawnlocation_offsets["AllowTeamChangeOnTouch"]
        )

    @AllowTeamChangeOnTouch.setter
    def AllowTeamChangeOnTouch(self, value: bool):
        if self.ClassName != "SpawnLocation":
            raise AttributeError("AllowTeamChangeOnTouch is only available on SpawnLocation instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + spawnlocation_offsets["AllowTeamChangeOnTouch"],
            bool(value)
        )

    @property
    def Neutral(self):
        if self.ClassName != "SpawnLocation":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            spawnlocation_offsets["Neutral"]
        )

    @Neutral.setter
    def Neutral(self, value: bool):
        if self.ClassName != "SpawnLocation":
            raise AttributeError("Neutral is only available on SpawnLocation instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + spawnlocation_offsets["Neutral"],
            bool(value)
        )

    @property
    def ForcefieldDuration(self):
        if self.ClassName != "SpawnLocation":
            return None
        return self.memory_module.read_int(
            self.raw_address,
            spawnlocation_offsets["ForcefieldDuration"]
        )

    @ForcefieldDuration.setter
    def ForcefieldDuration(self, value: int):
        if self.ClassName != "SpawnLocation":
            raise AttributeError("ForcefieldDuration is only available on SpawnLocation instances.")
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + spawnlocation_offsets["ForcefieldDuration"],
            int(value)
        )

    @property
    def TeamColor(self):
        if self.ClassName != "SpawnLocation":
            return None
        return self.memory_module.read_int(
            self.raw_address,
            spawnlocation_offsets["TeamColor"]
        )

    @TeamColor.setter
    def TeamColor(self, value: int):
        if self.ClassName != "SpawnLocation":
            raise AttributeError("TeamColor is only available on SpawnLocation instances.")
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + spawnlocation_offsets["TeamColor"],
            int(value)
        )

    # humanoid props #
    @property
    def WalkSpeed(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            humanoid_offsets["Walkspeed"]
        )

    @WalkSpeed.setter
    def WalkSpeed(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("WalkSpeed is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + humanoid_offsets["Walkspeed"],
            float(value)
        )

        self.memory_module.write_float(
            self.raw_address + humanoid_offsets["WalkspeedCheck"],
            float(value)
        )

    @property
    def JumpPower(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            humanoid_offsets["JumpPower"]
        )

    @JumpPower.setter
    def JumpPower(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("JumpPower is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + humanoid_offsets["JumpPower"],
            float(value)
        )
        
    @property
    def Health(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            humanoid_offsets["Health"]
        )

    @Health.setter
    def Health(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("Health is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + humanoid_offsets["Health"],
            float(value)
        )

    @property
    def MaxHealth(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            humanoid_offsets["MaxHealth"]
        )

    @MaxHealth.setter
    def MaxHealth(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("MaxHealth is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + humanoid_offsets["MaxHealth"],
            float(value)
        )

    @property
    def JumpHeight(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            humanoid_offsets["JumpHeight"]
        )

    @JumpHeight.setter
    def JumpHeight(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("JumpHeight is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + humanoid_offsets["JumpHeight"],
            float(value)
        )

    @property
    def HipHeight(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            humanoid_offsets["HipHeight"]
        )

    @HipHeight.setter
    def HipHeight(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("HipHeight is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + humanoid_offsets["HipHeight"],
            float(value)
        )

    @property
    def MaxSlopeAngle(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_float(
            self.raw_address,
            humanoid_offsets["MaxSlopeAngle"]
        )

    @MaxSlopeAngle.setter
    def MaxSlopeAngle(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("MaxSlopeAngle is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_float(
            self.raw_address + humanoid_offsets["MaxSlopeAngle"],
            float(value)
        )

    @property
    def RigType(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_int(
            self.raw_address,
            humanoid_offsets["RigType"]
        )

    @property
    def FloorMaterial(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_int(
            self.raw_address,
            humanoid_offsets["FloorMaterial"]
        )

    @property
    def Jump(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_bool(
            self.raw_address,
            humanoid_offsets["Jump"]
        )

    @Jump.setter
    def Jump(self, value: bool):
        if self.ClassName != "Humanoid":
            raise AttributeError("Jump is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_bool(
            self.raw_address + humanoid_offsets["Jump"],
            bool(value)
        )

    @property
    def MoveDirection(self):
        if self.ClassName != "Humanoid":
            return None
        
        move_dir = self.memory_module.read_floats(
            self.raw_address + humanoid_offsets["MoveDirection"],
            3
        )
        return Vector3(*move_dir)

    @property
    def AutoRotate(self):
        if self.ClassName != "Humanoid":
            return None
        
        return self.memory_module.read_bool(
            self.raw_address,
            humanoid_offsets["AutoRotate"]
        )

    @AutoRotate.setter
    def AutoRotate(self, value: bool):
        if self.ClassName != "Humanoid":
            raise AttributeError("AutoRotate is only available on Humanoid instances.")
        self._ensure_writable()

        self.memory_module.write_bool(
            self.raw_address + humanoid_offsets["AutoRotate"],
            bool(value)
        )

    @property
    def AutoJumpEnabled(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            humanoid_offsets["AutoJumpEnabled"]
        )

    @AutoJumpEnabled.setter
    def AutoJumpEnabled(self, value: bool):
        if self.ClassName != "Humanoid":
            raise AttributeError("AutoJumpEnabled is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + humanoid_offsets["AutoJumpEnabled"],
            bool(value)
        )

    @property
    def BreakJointsOnDeath(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            humanoid_offsets["BreakJointsOnDeath"]
        )

    @BreakJointsOnDeath.setter
    def BreakJointsOnDeath(self, value: bool):
        if self.ClassName != "Humanoid":
            raise AttributeError("BreakJointsOnDeath is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + humanoid_offsets["BreakJointsOnDeath"],
            bool(value)
        )

    @property
    def CameraOffset(self):
        if self.ClassName != "Humanoid":
            return None
        data = self.memory_module.read_floats(
            self.raw_address + humanoid_offsets["CameraOffset"],
            3
        )
        return Vector3(*data)

    @CameraOffset.setter
    def CameraOffset(self, value):
        if self.ClassName != "Humanoid":
            raise AttributeError("CameraOffset is only available on Humanoid instances.")
        self._ensure_writable()
        vec = self._as_vector3(value, "CameraOffset")
        self.memory_module.write_floats(
            self.raw_address + humanoid_offsets["CameraOffset"],
            (vec.X, vec.Y, vec.Z)
        )

    @property
    def DisplayName(self):
        """Humanoid display name label. Use PlayerClass.DisplayName for the player display name."""
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_string(
            self.raw_address,
            humanoid_offsets["DisplayName"]
        )

    @property
    def EvaluateStateMachine(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            humanoid_offsets["EvaluateStateMachine"]
        )

    @EvaluateStateMachine.setter
    def EvaluateStateMachine(self, value: bool):
        if self.ClassName != "Humanoid":
            raise AttributeError("EvaluateStateMachine is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + humanoid_offsets["EvaluateStateMachine"],
            bool(value)
        )

    @property
    def HealthDisplayDistance(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_float(
            self.raw_address,
            humanoid_offsets["HealthDisplayDistance"]
        )

    @HealthDisplayDistance.setter
    def HealthDisplayDistance(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("HealthDisplayDistance is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + humanoid_offsets["HealthDisplayDistance"],
            float(value)
        )

    @property
    def HealthDisplayType(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_int(
            self.raw_address,
            humanoid_offsets["HealthDisplayType"]
        )

    @HealthDisplayType.setter
    def HealthDisplayType(self, value: int):
        if self.ClassName != "Humanoid":
            raise AttributeError("HealthDisplayType is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + humanoid_offsets["HealthDisplayType"],
            int(value)
        )

    @property
    def HumanoidRootPart(self):
        if self.ClassName != "Humanoid":
            return None
        ptr = self.memory_module.get_pointer(
            self.raw_address,
            humanoid_offsets["HumanoidRootPart"]
        )
        if ptr == 0:
            return None
        return RBXInstance(ptr, self.memory_module)

    @property
    def NameDisplayDistance(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_float(
            self.raw_address,
            humanoid_offsets["NameDisplayDistance"]
        )

    @NameDisplayDistance.setter
    def NameDisplayDistance(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("NameDisplayDistance is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + humanoid_offsets["NameDisplayDistance"],
            float(value)
        )

    @property
    def NameOcclusion(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_int(
            self.raw_address,
            humanoid_offsets["NameOcclusion"]
        )

    @NameOcclusion.setter
    def NameOcclusion(self, value: int):
        if self.ClassName != "Humanoid":
            raise AttributeError("NameOcclusion is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + humanoid_offsets["NameOcclusion"],
            int(value)
        )

    @property
    def PlatformStand(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            humanoid_offsets["PlatformStand"]
        )

    @PlatformStand.setter
    def PlatformStand(self, value: bool):
        if self.ClassName != "Humanoid":
            raise AttributeError("PlatformStand is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + humanoid_offsets["PlatformStand"],
            bool(value)
        )

    @property
    def RequiresNeck(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            humanoid_offsets["RequiresNeck"]
        )

    @RequiresNeck.setter
    def RequiresNeck(self, value: bool):
        if self.ClassName != "Humanoid":
            raise AttributeError("RequiresNeck is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + humanoid_offsets["RequiresNeck"],
            bool(value)
        )

    @property
    def SeatPart(self):
        if self.ClassName != "Humanoid":
            return None
        ptr = self.memory_module.get_pointer(
            self.raw_address,
            humanoid_offsets["SeatPart"]
        )
        if ptr == 0:
            return None
        return RBXInstance(ptr, self.memory_module)

    @property
    def Sit(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            humanoid_offsets["Sit"]
        )

    @Sit.setter
    def Sit(self, value: bool):
        if self.ClassName != "Humanoid":
            raise AttributeError("Sit is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + humanoid_offsets["Sit"],
            bool(value)
        )

    @property
    def TargetPoint(self):
        if self.ClassName != "Humanoid":
            return None
        data = self.memory_module.read_floats(
            self.raw_address + humanoid_offsets["TargetPoint"],
            3
        )
        return Vector3(*data)

    @TargetPoint.setter
    def TargetPoint(self, value):
        if self.ClassName != "Humanoid":
            raise AttributeError("TargetPoint is only available on Humanoid instances.")
        self._ensure_writable()
        vec = self._as_vector3(value, "TargetPoint")
        self.memory_module.write_floats(
            self.raw_address + humanoid_offsets["TargetPoint"],
            (vec.X, vec.Y, vec.Z)
        )

    @property
    def HumanoidState(self):
        if self.ClassName != "Humanoid":
            return None
        
        state_container = self.memory_module.get_pointer(
            self.raw_address,
            humanoid_offsets["HumanoidState"]
        )
        if state_container == 0:
            return None
        
        return self.memory_module.read_int(
            state_container,
            humanoid_offsets["HumanoidStateID"]
        )

    @HumanoidState.setter
    def HumanoidState(self, value: int):
        if self.ClassName != "Humanoid":
            raise AttributeError("HumanoidState is only available on Humanoid instances.")
        self._ensure_writable()
        
        state_container = self.memory_module.get_pointer(
            self.raw_address,
            humanoid_offsets["HumanoidState"]
        )
        if state_container == 0:
            return
        
        self.memory_module.write_int(
            state_container + humanoid_offsets["HumanoidStateID"],
            int(value)
        )

    def MoveTo(self, target, wait=True):
        if self.ClassName != "Humanoid":
            raise AttributeError("MoveTo is only available on Humanoid instances.")
        
        self._ensure_writable()

        if isinstance(target, RBXInstance):
            self.memory_module.write_long(
                self.raw_address + humanoid_offsets["MoveToPart"],
                target.raw_address
            )
            position = target.Position
        else:
            position = self._as_vector3(target, "MoveTo target")

        character = self.Parent
        if character is None:
            raise RuntimeError("Humanoid has no parent Character model.")

        hrp = character.PrimaryPart
        if hrp is None:
            raise RuntimeError("Could not find PrimaryPart in Character.")

        def execute_move():
            while True:
                try:
                    if self.memory_module.is_invalid_handle or self.memory_module.is_closed:
                        break

                    if hrp.Parent is None or self.Health <= 0:
                        break

                    current = hrp.Position
                    if abs(current.X - position.X) <= 1.0 and abs(current.Z - position.Z) <= 1.0:
                        break

                    self.memory_module.write_floats(
                        self.raw_address + humanoid_offsets["MoveToPoint"],
                        (position.X, position.Y, position.Z)
                    )
                    self.memory_module.write_bool(
                        self.raw_address + humanoid_offsets["IsWalking"],
                        True
                    )
                except Exception:
                    break

        if wait:
            execute_move()
        else:
            threading.Thread(target=execute_move, daemon=True).start()

    @property
    def AutomaticScalingEnabled(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            humanoid_offsets["AutomaticScalingEnabled"]
        )

    @AutomaticScalingEnabled.setter
    def AutomaticScalingEnabled(self, value: bool):
        if self.ClassName != "Humanoid":
            raise AttributeError("AutomaticScalingEnabled is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + humanoid_offsets["AutomaticScalingEnabled"],
            bool(value)
        )

    @property
    def UseJumpPower(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            humanoid_offsets["UseJumpPower"]
        )

    @UseJumpPower.setter
    def UseJumpPower(self, value: bool):
        if self.ClassName != "Humanoid":
            raise AttributeError("UseJumpPower is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_bool(
            self.raw_address + humanoid_offsets["UseJumpPower"],
            bool(value)
        )

    @property
    def WalkTimer(self):
        if self.ClassName != "Humanoid":
            return None
        return self.memory_module.read_double(
            self.raw_address + humanoid_offsets["WalkTimer"]
        )

    @WalkTimer.setter
    def WalkTimer(self, value: float):
        if self.ClassName != "Humanoid":
            raise AttributeError("WalkTimer is only available on Humanoid instances.")
        self._ensure_writable()
        self.memory_module.write_double(
            self.raw_address + humanoid_offsets["WalkTimer"],
            float(value)
        )

    # adornee / animation props #
    @property
    def Adornee(self):
        adornee_ptr = self.memory_module.get_pointer(
            self.raw_address,
            misc_offsets["Adornee"]
        )
        if adornee_ptr == 0:
            return None
        return RBXInstance(adornee_ptr, self.memory_module)

    @Adornee.setter
    def Adornee(self, value):
        self._ensure_writable()
        if value is None:
            target = 0
        elif isinstance(value, RBXInstance):
            target = value.raw_address
        elif isinstance(value, int):
            target = value
        else:
            raise TypeError("Adornee must be set to an RBXInstance, int address, or None.")
        self.memory_module.write_long(
            self.raw_address + misc_offsets["Adornee"],
            target
        )

    @property
    def AnimationId(self):
        if self.ClassName != "Animation":
            return None
        return self.memory_module.read_string(
            self.raw_address,
            misc_offsets["AnimationId"]
        )

    @AnimationId.setter
    def AnimationId(self, value: str):
        if self.ClassName != "Animation":
            raise AttributeError("AnimationId is only available on Animation instances.")
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + misc_offsets["AnimationId"],
            str(value)
        )

    # model props #
    @property
    def PrimaryPart(self):
        if self.ClassName != "Model":
            return None
        
        parent_pointer = self.memory_module.get_pointer(
            self.raw_address,
            model_offsets["PrimaryPart"]
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
            self.raw_address + model_offsets["PrimaryPart"],
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
        elif classname == "Script":
            bytecode_offset = script_offsets["ByteCode"]
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
        elif classname == "Script":
            bytecode_offset = script_offsets["ByteCode"]
        else:
            raise AttributeError("Bytecode can only be written for LocalScript, ModuleScript, or Script.")

        encoded_data = encryptor.encode_roblox(value)
        new_size = len(encoded_data)
        
        new_content_ptr = self.memory_module.virtual_alloc(new_size)
        self.memory_module.write(new_content_ptr, encoded_data)
        
        bytecode_ptr = self.memory_module.get_pointer(self.raw_address, bytecode_offset)
        
        if bytecode_ptr == 0:
             raise RuntimeError("Cannot set bytecode: Bytecode object not found (script might be empty or not loaded).")

        self.memory_module.write_long(bytecode_ptr + Offsets["ByteCode"]["Pointer"], new_content_ptr)
        self.memory_module.write_int(bytecode_ptr + Offsets["ByteCode"]["Size"], new_size)

    # script identification #
    @property
    def GUID(self):
        classname = self.ClassName
        if classname == "LocalScript":
            guid_offset = Offsets["LocalScript"]["GUID"]
        elif classname == "ModuleScript":
            guid_offset = Offsets["ModuleScript"]["GUID"]
        elif classname == "Script":
            guid_offset = script_offsets["GUID"]
        else:
            return None
        return self.memory_module.read_string(
            self.raw_address,
            guid_offset
        )

    @property
    def Hash(self):
        classname = self.ClassName
        if classname == "LocalScript":
            hash_offset = Offsets["LocalScript"]["Hash"]
        elif classname == "ModuleScript":
            hash_offset = Offsets["ModuleScript"]["Hash"]
        elif classname == "Script":
            hash_offset = script_offsets["Hash"]
        else:
            return None
        return self.memory_module.read_string(
            self.raw_address,
            hash_offset
        )
    
    # functions #
    def GetChildren(self):
        children = []
        children_pointer = self.memory_module.get_pointer(
            self.raw_address,
            instance_offsets["ChildrenStart"]
        )
        
        if children_pointer == 0:
            return children
        
        children_start = self.memory_module.get_pointer(children_pointer)
        children_end = self.memory_module.get_pointer(
            children_pointer,
            instance_offsets["ChildrenEnd"]
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
    
    def WaitForChild(self, name, timeout=5):
        start = time.time()
        child = None

        while time.time() - start < timeout:
            child = self.FindFirstChild(name)
            if child is not None: break
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
            self.raw_address + instance_offsets["AttributeContainer"]
        )
        
        if attribute_container == 0:
            return attributes

        attribute_list = self.memory_module.read_long(
            attribute_container + instance_offsets["AttributeList"]
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

            value_addr = attribute_list + i + instance_offsets["AttributeToValue"]
            
            # Read Type Name (Pointer at +0x8 points to TypeDescriptor, Name at TypeDesc + 0x8)
            type_ptr = self.memory_module.read_long(attribute_list + i + 0x8)
            type_name = self._read_type_name(type_ptr)

            attributes[name] = AttributeValue(value_addr, name, type_name, self.memory_module)

            i += instance_offsets["AttributeToNext"]
        
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

    # modulescript props #
    @property
    def IsCoreScript(self):
        if self.ClassName != "ModuleScript":
            return None
        return self.memory_module.read_bool(
            self.raw_address,
            Offsets["ModuleScript"]["IsCoreScript"]
        )

    # beam props #
    @property
    def Attachment0(self):
        cn = self.ClassName
        if cn == "Beam":
            ptr = self.memory_module.get_pointer(self.raw_address, beam_offsets["Attachment0"])
            return RBXInstance(ptr, self.memory_module) if ptr != 0 else None
        return None

    @property
    def Attachment1(self):
        cn = self.ClassName
        if cn == "Beam":
            ptr = self.memory_module.get_pointer(self.raw_address, beam_offsets["Attachment1"])
            return RBXInstance(ptr, self.memory_module) if ptr != 0 else None
        return None

    @property
    def CurveSize0(self):
        if self.ClassName != "Beam":
            return None
        return self.memory_module.read_float(self.raw_address, beam_offsets["CurveSize0"])

    @CurveSize0.setter
    def CurveSize0(self, value: float):
        if self.ClassName != "Beam":
            raise AttributeError("CurveSize0 is only available on Beam instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + beam_offsets["CurveSize0"], float(value))

    @property
    def CurveSize1(self):
        if self.ClassName != "Beam":
            return None
        return self.memory_module.read_float(self.raw_address, beam_offsets["CurveSize1"])

    @CurveSize1.setter
    def CurveSize1(self, value: float):
        if self.ClassName != "Beam":
            raise AttributeError("CurveSize1 is only available on Beam instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + beam_offsets["CurveSize1"], float(value))

    @property
    def LightEmission(self):
        cn = self.ClassName
        if cn == "Beam":
            return self.memory_module.read_float(self.raw_address, beam_offsets["LightEmission"])
        elif cn == "ParticleEmitter":
            return self.memory_module.read_float(self.raw_address, particleemitter_offsets["LightEmission"])
        return None

    @LightEmission.setter
    def LightEmission(self, value: float):
        cn = self.ClassName
        self._ensure_writable()
        if cn == "Beam":
            self.memory_module.write_float(self.raw_address + beam_offsets["LightEmission"], float(value))
        elif cn == "ParticleEmitter":
            self.memory_module.write_float(self.raw_address + particleemitter_offsets["LightEmission"], float(value))
        else:
            raise AttributeError("LightEmission is only available on Beam or ParticleEmitter instances.")

    @property
    def LightInfluence(self):
        cn = self.ClassName
        if cn == "Beam":
            return self.memory_module.read_float(self.raw_address, beam_offsets["LightInfluence"])
        elif cn == "ParticleEmitter":
            return self.memory_module.read_float(self.raw_address, particleemitter_offsets["LightInfluence"])
        return None

    @LightInfluence.setter
    def LightInfluence(self, value: float):
        cn = self.ClassName
        self._ensure_writable()
        if cn == "Beam":
            self.memory_module.write_float(self.raw_address + beam_offsets["LightInfluence"], float(value))
        elif cn == "ParticleEmitter":
            self.memory_module.write_float(self.raw_address + particleemitter_offsets["LightInfluence"], float(value))
        else:
            raise AttributeError("LightInfluence is only available on Beam or ParticleEmitter instances.")

    @property
    def TextureLength(self):
        if self.ClassName != "Beam":
            return None
        return self.memory_module.read_float(self.raw_address, beam_offsets["TextureLength"])

    @TextureLength.setter
    def TextureLength(self, value: float):
        if self.ClassName != "Beam":
            raise AttributeError("TextureLength is only available on Beam instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + beam_offsets["TextureLength"], float(value))

    @property
    def TextureSpeed(self):
        if self.ClassName != "Beam":
            return None
        return self.memory_module.read_float(self.raw_address, beam_offsets["TextureSpeed"])

    @TextureSpeed.setter
    def TextureSpeed(self, value: float):
        if self.ClassName != "Beam":
            raise AttributeError("TextureSpeed is only available on Beam instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + beam_offsets["TextureSpeed"], float(value))

    @property
    def Width0(self):
        if self.ClassName != "Beam":
            return None
        return self.memory_module.read_float(self.raw_address, beam_offsets["Width0"])

    @Width0.setter
    def Width0(self, value: float):
        if self.ClassName != "Beam":
            raise AttributeError("Width0 is only available on Beam instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + beam_offsets["Width0"], float(value))

    @property
    def Width1(self):
        if self.ClassName != "Beam":
            return None
        return self.memory_module.read_float(self.raw_address, beam_offsets["Width1"])

    @Width1.setter
    def Width1(self, value: float):
        if self.ClassName != "Beam":
            raise AttributeError("Width1 is only available on Beam instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + beam_offsets["Width1"], float(value))

    @property
    def ZOffset(self):
        cn = self.ClassName
        if cn == "Beam":
            return self.memory_module.read_float(self.raw_address, beam_offsets["ZOffset"])
        elif cn == "ParticleEmitter":
            return self.memory_module.read_float(self.raw_address, particleemitter_offsets["ZOffset"])
        return None

    @ZOffset.setter
    def ZOffset(self, value: float):
        cn = self.ClassName
        self._ensure_writable()
        if cn == "Beam":
            self.memory_module.write_float(self.raw_address + beam_offsets["ZOffset"], float(value))
        elif cn == "ParticleEmitter":
            self.memory_module.write_float(self.raw_address + particleemitter_offsets["ZOffset"], float(value))
        else:
            raise AttributeError("ZOffset is only available on Beam or ParticleEmitter instances.")

    # particleemitter props #
    @property
    def Acceleration(self):
        if self.ClassName != "ParticleEmitter":
            return None
        data = self.memory_module.read_floats(
            self.raw_address + particleemitter_offsets["Acceleration"], 3
        )
        return Vector3(*data)

    @Acceleration.setter
    def Acceleration(self, value):
        if self.ClassName != "ParticleEmitter":
            raise AttributeError("Acceleration is only available on ParticleEmitter instances.")
        self._ensure_writable()
        vec = self._as_vector3(value, "Acceleration")
        self.memory_module.write_floats(
            self.raw_address + particleemitter_offsets["Acceleration"],
            (vec.X, vec.Y, vec.Z)
        )

    @property
    def Drag(self):
        if self.ClassName != "ParticleEmitter":
            return None
        return self.memory_module.read_float(self.raw_address, particleemitter_offsets["Drag"])

    @Drag.setter
    def Drag(self, value: float):
        if self.ClassName != "ParticleEmitter":
            raise AttributeError("Drag is only available on ParticleEmitter instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + particleemitter_offsets["Drag"], float(value))

    @property
    def Lifetime(self):
        if self.ClassName != "ParticleEmitter":
            return None
        data = self.memory_module.read_floats(
            self.raw_address + particleemitter_offsets["Lifetime"], 2
        )
        return NumberRange(*data)

    @Lifetime.setter
    def Lifetime(self, value):
        if self.ClassName != "ParticleEmitter":
            raise AttributeError("Lifetime is only available on ParticleEmitter instances.")
        self._ensure_writable()
        if isinstance(value, NumberRange):
            vals = (value.Min, value.Max)
        elif isinstance(value, (tuple, list)) and len(value) == 2:
            vals = (float(value[0]), float(value[1]))
        else:
            v = float(value)
            vals = (v, v)
        self.memory_module.write_floats(
            self.raw_address + particleemitter_offsets["Lifetime"], vals
        )

    @property
    def Rate(self):
        if self.ClassName != "ParticleEmitter":
            return None
        return self.memory_module.read_float(self.raw_address, particleemitter_offsets["Rate"])

    @Rate.setter
    def Rate(self, value: float):
        if self.ClassName != "ParticleEmitter":
            raise AttributeError("Rate is only available on ParticleEmitter instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + particleemitter_offsets["Rate"], float(value))

    @property
    def RotSpeed(self):
        if self.ClassName != "ParticleEmitter":
            return None
        data = self.memory_module.read_floats(
            self.raw_address + particleemitter_offsets["RotSpeed"], 2
        )
        return NumberRange(*data)

    @RotSpeed.setter
    def RotSpeed(self, value):
        if self.ClassName != "ParticleEmitter":
            raise AttributeError("RotSpeed is only available on ParticleEmitter instances.")
        self._ensure_writable()
        if isinstance(value, NumberRange):
            vals = (value.Min, value.Max)
        elif isinstance(value, (tuple, list)) and len(value) == 2:
            vals = (float(value[0]), float(value[1]))
        else:
            v = float(value)
            vals = (v, v)
        self.memory_module.write_floats(
            self.raw_address + particleemitter_offsets["RotSpeed"], vals
        )

    @property
    def ParticleSpeed(self):
        """Speed property for ParticleEmitter (named ParticleSpeed to avoid conflict with AnimationTrack.Speed)."""
        if self.ClassName != "ParticleEmitter":
            return None
        data = self.memory_module.read_floats(
            self.raw_address + particleemitter_offsets["Speed"], 2
        )
        return NumberRange(*data)

    @ParticleSpeed.setter
    def ParticleSpeed(self, value):
        if self.ClassName != "ParticleEmitter":
            raise AttributeError("ParticleSpeed is only available on ParticleEmitter instances.")
        self._ensure_writable()
        if isinstance(value, NumberRange):
            vals = (value.Min, value.Max)
        elif isinstance(value, (tuple, list)) and len(value) == 2:
            vals = (float(value[0]), float(value[1]))
        else:
            v = float(value)
            vals = (v, v)
        self.memory_module.write_floats(
            self.raw_address + particleemitter_offsets["Speed"], vals
        )

    @property
    def SpreadAngle(self):
        if self.ClassName != "ParticleEmitter":
            return None
        data = self.memory_module.read_floats(
            self.raw_address + particleemitter_offsets["SpreadAngle"], 2
        )
        return Vector2(*data)

    @SpreadAngle.setter
    def SpreadAngle(self, value):
        if self.ClassName != "ParticleEmitter":
            raise AttributeError("SpreadAngle is only available on ParticleEmitter instances.")
        self._ensure_writable()
        angle = self._as_vector2(value, "SpreadAngle")
        self.memory_module.write_floats(
            self.raw_address + particleemitter_offsets["SpreadAngle"],
            (angle.X, angle.Y)
        )

    @property
    def TimeScale(self):
        if self.ClassName != "ParticleEmitter":
            return None
        return self.memory_module.read_float(self.raw_address, particleemitter_offsets["TimeScale"])

    @TimeScale.setter
    def TimeScale(self, value: float):
        if self.ClassName != "ParticleEmitter":
            raise AttributeError("TimeScale is only available on ParticleEmitter instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + particleemitter_offsets["TimeScale"], float(value))

    @property
    def VelocityInheritance(self):
        if self.ClassName != "ParticleEmitter":
            return None
        return self.memory_module.read_float(self.raw_address, particleemitter_offsets["VelocityInheritance"])

    @VelocityInheritance.setter
    def VelocityInheritance(self, value: float):
        if self.ClassName != "ParticleEmitter":
            raise AttributeError("VelocityInheritance is only available on ParticleEmitter instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + particleemitter_offsets["VelocityInheritance"], float(value))

    # vehicleseat props #
    @property
    def MaxSpeed(self):
        if self.ClassName != "VehicleSeat":
            return None
        return self.memory_module.read_float(self.raw_address, vehicleseat_offsets["MaxSpeed"])

    @MaxSpeed.setter
    def MaxSpeed(self, value: float):
        if self.ClassName != "VehicleSeat":
            raise AttributeError("MaxSpeed is only available on VehicleSeat instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + vehicleseat_offsets["MaxSpeed"], float(value))

    @property
    def SteerFloat(self):
        if self.ClassName != "VehicleSeat":
            return None
        return self.memory_module.read_float(self.raw_address, vehicleseat_offsets["SteerFloat"])

    @SteerFloat.setter
    def SteerFloat(self, value: float):
        if self.ClassName != "VehicleSeat":
            raise AttributeError("SteerFloat is only available on VehicleSeat instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + vehicleseat_offsets["SteerFloat"], float(value))

    @property
    def ThrottleFloat(self):
        if self.ClassName != "VehicleSeat":
            return None
        return self.memory_module.read_float(self.raw_address, vehicleseat_offsets["ThrottleFloat"])

    @ThrottleFloat.setter
    def ThrottleFloat(self, value: float):
        if self.ClassName != "VehicleSeat":
            raise AttributeError("ThrottleFloat is only available on VehicleSeat instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + vehicleseat_offsets["ThrottleFloat"], float(value))

    @property
    def Torque(self):
        if self.ClassName != "VehicleSeat":
            return None
        return self.memory_module.read_float(self.raw_address, vehicleseat_offsets["Torque"])

    @Torque.setter
    def Torque(self, value: float):
        if self.ClassName != "VehicleSeat":
            raise AttributeError("Torque is only available on VehicleSeat instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + vehicleseat_offsets["Torque"], float(value))

    @property
    def TurnSpeed(self):
        if self.ClassName != "VehicleSeat":
            return None
        return self.memory_module.read_float(self.raw_address, vehicleseat_offsets["TurnSpeed"])

    @TurnSpeed.setter
    def TurnSpeed(self, value: float):
        if self.ClassName != "VehicleSeat":
            raise AttributeError("TurnSpeed is only available on VehicleSeat instances.")
        self._ensure_writable()
        self.memory_module.write_float(self.raw_address + vehicleseat_offsets["TurnSpeed"], float(value))

    # weld / weldconstraint props #
    @property
    def Part0(self):
        cn = self.ClassName
        if cn == "Weld":
            ptr = self.memory_module.get_pointer(self.raw_address, weld_offsets["Part0"])
        elif cn == "WeldConstraint":
            ptr = self.memory_module.get_pointer(self.raw_address, weldconstraint_offsets["Part0"])
        else:
            return None
        return RBXInstance(ptr, self.memory_module) if ptr != 0 else None

    @Part0.setter
    def Part0(self, value):
        cn = self.ClassName
        if cn != "Weld" and cn != "WeldConstraint":
            raise AttributeError("Part0 is only available on Weld or WeldConstraint instances.")
        self._ensure_writable()
        if value is None:
            target = 0
        elif isinstance(value, RBXInstance):
            target = value.raw_address
        elif isinstance(value, int):
            target = value
        else:
            raise TypeError("Part0 must be set to an RBXInstance, int address, or None.")
        offset = weld_offsets["Part0"] if cn == "Weld" else weldconstraint_offsets["Part0"]
        self.memory_module.write_long(self.raw_address + offset, target)

    @property
    def Part1(self):
        cn = self.ClassName
        if cn == "Weld":
            ptr = self.memory_module.get_pointer(self.raw_address, weld_offsets["Part1"])
        elif cn == "WeldConstraint":
            ptr = self.memory_module.get_pointer(self.raw_address, weldconstraint_offsets["Part1"])
        else:
            return None
        return RBXInstance(ptr, self.memory_module) if ptr != 0 else None

    @Part1.setter
    def Part1(self, value):
        cn = self.ClassName
        if cn != "Weld" and cn != "WeldConstraint":
            raise AttributeError("Part1 is only available on Weld or WeldConstraint instances.")
        self._ensure_writable()
        if value is None:
            target = 0
        elif isinstance(value, RBXInstance):
            target = value.raw_address
        elif isinstance(value, int):
            target = value
        else:
            raise TypeError("Part1 must be set to an RBXInstance, int address, or None.")
        offset = weld_offsets["Part1"] if cn == "Weld" else weldconstraint_offsets["Part1"]
        self.memory_module.write_long(self.raw_address + offset, target)

    # surfaceappearance props #
    @property
    def AlphaMode(self):
        if self.ClassName != "SurfaceAppearance":
            return None
        return self.memory_module.read_int(
            self.raw_address, surfaceappearance_offsets["AlphaMode"]
        )

    @AlphaMode.setter
    def AlphaMode(self, value: int):
        if self.ClassName != "SurfaceAppearance":
            raise AttributeError("AlphaMode is only available on SurfaceAppearance instances.")
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + surfaceappearance_offsets["AlphaMode"], int(value)
        )

    @property
    def EmissiveStrength(self):
        if self.ClassName != "SurfaceAppearance":
            return None
        return self.memory_module.read_float(
            self.raw_address, surfaceappearance_offsets["EmissiveStrength"]
        )

    @EmissiveStrength.setter
    def EmissiveStrength(self, value: float):
        if self.ClassName != "SurfaceAppearance":
            raise AttributeError("EmissiveStrength is only available on SurfaceAppearance instances.")
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + surfaceappearance_offsets["EmissiveStrength"], float(value)
        )

    @property
    def EmissiveTint(self):
        if self.ClassName != "SurfaceAppearance":
            return None
        return Color3(*self.memory_module.read_floats(
            self.raw_address + surfaceappearance_offsets["EmissiveTint"],
            3
        ))

    @EmissiveTint.setter
    def EmissiveTint(self, value):
        if self.ClassName != "SurfaceAppearance":
            raise AttributeError("EmissiveTint is only available on SurfaceAppearance instances.")
        self._ensure_writable()
        color = self._as_color3(value, "EmissiveTint")
        self.memory_module.write_floats(
            self.raw_address + surfaceappearance_offsets["EmissiveTint"],
            self._color3_tuple(color)
        )

    def _surface_appearance_content(self, property_name):
        if self.ClassName != "SurfaceAppearance":
            return None
        return self.memory_module.read_string(
            self.raw_address,
            _SURFACE_APPEARANCE_CONTENT_OFFSETS_BY_PROPERTY[property_name]
        )

    def _set_surface_appearance_content(self, property_name, value):
        if self.ClassName != "SurfaceAppearance":
            raise AttributeError(f"{property_name} is only available on SurfaceAppearance instances.")
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + _SURFACE_APPEARANCE_CONTENT_OFFSETS_BY_PROPERTY[property_name],
            str(value)
        )

    @property
    def ColorMap(self):
        return self._surface_appearance_content("ColorMap")

    @ColorMap.setter
    def ColorMap(self, value: str):
        self._set_surface_appearance_content("ColorMap", value)

    @property
    def EmissiveMaskContent(self):
        return self._surface_appearance_content("EmissiveMaskContent")

    @EmissiveMaskContent.setter
    def EmissiveMaskContent(self, value: str):
        self._set_surface_appearance_content("EmissiveMaskContent", value)

    @property
    def MetalnessMap(self):
        return self._surface_appearance_content("MetalnessMap")

    @MetalnessMap.setter
    def MetalnessMap(self, value: str):
        self._set_surface_appearance_content("MetalnessMap", value)

    @property
    def NormalMap(self):
        return self._surface_appearance_content("NormalMap")

    @NormalMap.setter
    def NormalMap(self, value: str):
        self._set_surface_appearance_content("NormalMap", value)

    @property
    def RoughnessMap(self):
        return self._surface_appearance_content("RoughnessMap")

    @RoughnessMap.setter
    def RoughnessMap(self, value: str):
        self._set_surface_appearance_content("RoughnessMap", value)

    # terrain props #
    @property
    def GrassLength(self):
        return self._read_class_float("GrassLength", {"Terrain": terrain_offsets})

    @GrassLength.setter
    def GrassLength(self, value: float):
        self._write_class_float("GrassLength", {"Terrain": terrain_offsets}, value)

    @property
    def WaterColor(self):
        return self._read_class_color3("WaterColor", {"Terrain": terrain_offsets})

    @WaterColor.setter
    def WaterColor(self, value):
        self._write_class_color3("WaterColor", {"Terrain": terrain_offsets}, value)

    @property
    def WaterReflectance(self):
        return self._read_class_float("WaterReflectance", {"Terrain": terrain_offsets})

    @WaterReflectance.setter
    def WaterReflectance(self, value: float):
        self._write_class_float("WaterReflectance", {"Terrain": terrain_offsets}, value)

    @property
    def WaterTransparency(self):
        return self._read_class_float("WaterTransparency", {"Terrain": terrain_offsets})

    @WaterTransparency.setter
    def WaterTransparency(self, value: float):
        self._write_class_float("WaterTransparency", {"Terrain": terrain_offsets}, value)

    @property
    def WaterWaveSize(self):
        return self._read_class_float("WaterWaveSize", {"Terrain": terrain_offsets})

    @WaterWaveSize.setter
    def WaterWaveSize(self, value: float):
        self._write_class_float("WaterWaveSize", {"Terrain": terrain_offsets}, value)

    @property
    def WaterWaveSpeed(self):
        return self._read_class_float("WaterWaveSpeed", {"Terrain": terrain_offsets})

    @WaterWaveSpeed.setter
    def WaterWaveSpeed(self, value: float):
        self._write_class_float("WaterWaveSpeed", {"Terrain": terrain_offsets}, value)

    @property
    def MaterialColors(self):
        if self.ClassName != "Terrain":
            return None
        return MaterialColors(
            self.memory_module,
            self.raw_address + terrain_offsets["MaterialColors"],
            material_colors_offsets
        )

    def GetMaterialColor(self, material):
        colors = self.MaterialColors
        if colors is None:
            raise AttributeError("GetMaterialColor is only available on Terrain instances.")
        return colors[material]

    def SetMaterialColor(self, material, color):
        colors = self.MaterialColors
        if colors is None:
            raise AttributeError("SetMaterialColor is only available on Terrain instances.")
        colors[material] = color

    # sky props #
    def _read_skybox_content(self, property_name):
        if self.ClassName != "Sky":
            return None
        return self.memory_module.read_string(self.raw_address, sky_offsets[property_name])

    def _write_skybox_content(self, property_name, value):
        if self.ClassName != "Sky":
            raise AttributeError(f"{property_name} is only available on Sky instances.")
        self._ensure_writable()
        self.memory_module.write_string(self.raw_address + sky_offsets[property_name], str(value))

    @property
    def SkyboxBk(self):
        return self._read_skybox_content("SkyboxBk")

    @SkyboxBk.setter
    def SkyboxBk(self, value: str):
        self._write_skybox_content("SkyboxBk", value)

    @property
    def SkyboxDn(self):
        return self._read_skybox_content("SkyboxDn")

    @SkyboxDn.setter
    def SkyboxDn(self, value: str):
        self._write_skybox_content("SkyboxDn", value)

    @property
    def SkyboxFt(self):
        return self._read_skybox_content("SkyboxFt")

    @SkyboxFt.setter
    def SkyboxFt(self, value: str):
        self._write_skybox_content("SkyboxFt", value)

    @property
    def SkyboxLf(self):
        return self._read_skybox_content("SkyboxLf")

    @SkyboxLf.setter
    def SkyboxLf(self, value: str):
        self._write_skybox_content("SkyboxLf", value)

    @property
    def SkyboxRt(self):
        return self._read_skybox_content("SkyboxRt")

    @SkyboxRt.setter
    def SkyboxRt(self, value: str):
        self._write_skybox_content("SkyboxRt", value)

    @property
    def SkyboxUp(self):
        return self._read_skybox_content("SkyboxUp")

    @SkyboxUp.setter
    def SkyboxUp(self, value: str):
        self._write_skybox_content("SkyboxUp", value)

    @property
    def SunTextureId(self):
        return self._read_skybox_content("SunTextureId")

    @SunTextureId.setter
    def SunTextureId(self, value: str):
        self._write_skybox_content("SunTextureId", value)

    @property
    def MoonTextureId(self):
        return self._read_skybox_content("MoonTextureId")

    @MoonTextureId.setter
    def MoonTextureId(self, value: str):
        self._write_skybox_content("MoonTextureId", value)

    @property
    def SkyboxOrientation(self):
        return self._read_class_int("SkyboxOrientation", {"Sky": sky_offsets})

    @SkyboxOrientation.setter
    def SkyboxOrientation(self, value: int):
        self._write_class_int("SkyboxOrientation", {"Sky": sky_offsets}, value)

    @property
    def StarCount(self):
        return self._read_class_int("StarCount", {"Sky": sky_offsets})

    @StarCount.setter
    def StarCount(self, value: int):
        self._write_class_int("StarCount", {"Sky": sky_offsets}, value)

    @property
    def SunAngularSize(self):
        return self._read_class_float("SunAngularSize", {"Sky": sky_offsets})

    @SunAngularSize.setter
    def SunAngularSize(self, value: float):
        self._write_class_float("SunAngularSize", {"Sky": sky_offsets}, value)

    @property
    def MoonAngularSize(self):
        return self._read_class_float("MoonAngularSize", {"Sky": sky_offsets})

    @MoonAngularSize.setter
    def MoonAngularSize(self, value: float):
        self._write_class_float("MoonAngularSize", {"Sky": sky_offsets}, value)

    # team / union props #
    @property
    def BrickColor(self):
        if self.ClassName == "Team":
            return self.memory_module.read_int(self.raw_address, team_offsets["BrickColor"])
        return None

    @BrickColor.setter
    def BrickColor(self, value: int):
        if self.ClassName != "Team":
            raise AttributeError("BrickColor is only available on Team instances.")
        self._ensure_writable()
        self.memory_module.write_int(self.raw_address + team_offsets["BrickColor"], int(value))

    @property
    def AssetId(self):
        if self.ClassName != "UnionOperation":
            return None
        return self.memory_module.read_string(self.raw_address, unionoperation_offsets["AssetId"])

    @AssetId.setter
    def AssetId(self, value: str):
        if self.ClassName != "UnionOperation":
            raise AttributeError("AssetId is only available on UnionOperation instances.")
        self._ensure_writable()
        self.memory_module.write_string(self.raw_address + unionoperation_offsets["AssetId"], str(value))

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
            return Color3(*self.memory_module.read_floats(self.address, 3))
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
             if isinstance(new_value, Color3):
                self.memory_module.write_floats(self.address, (new_value.R, new_value.G, new_value.B))
             elif isinstance(new_value, Vector3): # Color3 is often treated as Vector3 storage-wise here
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

    @property
    def Mouse(self):
        mouse_address = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["Mouse"]
        )
        if mouse_address == 0:
            return None
        return PlayerMouse(mouse_address, self.memory_module)

    @property
    def LocaleId(self):
        return self.memory_module.read_string(
            self.raw_address,
            self.offset_base["LocaleId"]
        )

    @property
    def Country(self):
        """Deprecated: Use LocaleId instead. Renamed in V2.1.4."""
        return self.LocaleId

    @property
    def TeamColor(self):
        return self.memory_module.read_int(
            self.raw_address,
            self.offset_base["TeamColor"]
        )

    @TeamColor.setter
    def TeamColor(self, value: int):
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + self.offset_base["TeamColor"],
            int(value)
        )

    @property
    def AccountAge(self):
        return self.memory_module.read_int(
            self.raw_address,
            self.offset_base["AccountAge"]
        )

    @property
    def MinZoomDistance(self):
        return self.memory_module.read_float(
            self.raw_address,
            self.offset_base["MinZoomDistance"]
        )

    @MinZoomDistance.setter
    def MinZoomDistance(self, value: float):
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + self.offset_base["MinZoomDistance"],
            float(value)
        )

    @property
    def MaxZoomDistance(self):
        return self.memory_module.read_float(
            self.raw_address,
            self.offset_base["MaxZoomDistance"]
        )

    @MaxZoomDistance.setter
    def MaxZoomDistance(self, value: float):
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + self.offset_base["MaxZoomDistance"],
            float(value)
        )

    @property
    def CameraMode(self):
        return self.memory_module.read_int(
            self.raw_address,
            self.offset_base["CameraMode"]
        )

    @CameraMode.setter
    def CameraMode(self, value: int):
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + self.offset_base["CameraMode"],
            int(value)
        )

    @property
    def HealthDisplayDistance(self):
        return self.memory_module.read_float(
            self.raw_address,
            self.offset_base["HealthDisplayDistance"]
        )

    @HealthDisplayDistance.setter
    def HealthDisplayDistance(self, value: float):
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + self.offset_base["HealthDisplayDistance"],
            float(value)
        )

    @property
    def NameDisplayDistance(self):
        return self.memory_module.read_float(
            self.raw_address,
            self.offset_base["NameDisplayDistance"]
        )

    @NameDisplayDistance.setter
    def NameDisplayDistance(self, value: float):
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + self.offset_base["NameDisplayDistance"],
            float(value)
        )

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

    @property
    def Viewport(self):
        raw = self.memory_module.read(
            self.raw_address + self.offset_base["Viewport"],
            4
        )
        if len(raw) != 4:
            return Vector2()
        return Vector2(
            int.from_bytes(raw[0:2], "little", signed=True),
            int.from_bytes(raw[2:4], "little", signed=True)
        )

    @Viewport.setter
    def Viewport(self, value):
        vec = self._as_vector2(value, "Viewport")
        self._ensure_writable()
        self.memory_module.write(
            self.raw_address + self.offset_base["Viewport"],
            int(vec.X).to_bytes(2, "little", signed=True) + int(vec.Y).to_bytes(2, "little", signed=True)
        )

    @property
    def ImagePlaneDepth(self):
        return self.memory_module.read_float(
            self.raw_address,
            self.offset_base["ImagePlaneDepth"]
        )

    @ImagePlaneDepth.setter
    def ImagePlaneDepth(self, value: float):
        self._ensure_writable()
        self.memory_module.write_float(
            self.raw_address + self.offset_base["ImagePlaneDepth"],
            float(value)
        )

    @property
    def CameraType(self):
        return self.memory_module.read_int(
            self.raw_address,
            self.offset_base["CameraType"]
        )

    @CameraType.setter
    def CameraType(self, value: int):
        self._ensure_writable()
        self.memory_module.write_int(
            self.raw_address + self.offset_base["CameraType"],
            int(value)
        )

    @property
    def CameraSubject(self):
        subject_address = self.memory_module.get_pointer(
            self.raw_address,
            self.offset_base["CameraSubject"]
        )

        if subject_address == 0:
            return None
        
        return RBXInstance(subject_address, self.memory_module)

    @CameraSubject.setter
    def CameraSubject(self, value):
        self._ensure_writable()
        if value is None:
            target = 0
        elif isinstance(value, RBXInstance):
            target = value.raw_address
        elif isinstance(value, int):
            target = value
        else:
            raise TypeError("CameraSubject must be set to an RBXInstance, int address, or None.")
        self.memory_module.write_long(
            self.raw_address + self.offset_base["CameraSubject"],
            target
        )

class PlayerMouse:
    def __init__(self, raw_address: int, memory_module):
        self.raw_address = raw_address
        self.memory_module = memory_module
        self.offset_base = playermouse_offsets

    def __repr__(self):
        return f"PlayerMouse(0x{self.raw_address:X})"

    def _ensure_writable(self):
        if not hasattr(self.memory_module, "write"):
            raise RuntimeError("Write operations require a memory module with write support (allow_write=True).")

    @property
    def Icon(self):
        return self.memory_module.read_string(
            self.raw_address,
            self.offset_base["Icon"]
        )

    @Icon.setter
    def Icon(self, value: str):
        self._ensure_writable()
        self.memory_module.write_string(
            self.raw_address + self.offset_base["Icon"],
            str(value)
        )

    @property
    def Workspace(self):
        ptr = self.memory_module.get_pointer(
            self.raw_address,
            self.offset_base["Workspace"]
        )
        return RBXInstance(ptr, self.memory_module) if ptr != 0 else None

# Service #
class ServiceBase:
    def __init__(self):
        self.instance = None
        self.failed = False

    def _ensure_writable(self):
        if not hasattr(self.memory_module, "write"):
            raise RuntimeError("Write operations require a memory module with write support (allow_write=True).")

    # expose instance functions #
    def __getattr__(self, name):
        # instance #
        if self.instance is not None:
            return getattr(self.instance, name)

        raise AttributeError(name)

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
    def PlaceVersion(self):
        if not self._ensure_instance():
            return 0

        return self.memory_module.read_int(
            self.instance.raw_address,
            self.offset_base["PlaceVersion"]
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

    @property
    def Lighting(self):
        if not self._ensure_instance():
            return None

        return LightingService(self.memory_module, self)

    @property
    def MouseService(self):
        if not self._ensure_instance():
            return None

        return MouseService(self.memory_module, self)

    @property
    def UserInputService(self):
        if not self._ensure_instance():
            return None

        return UserInputService(self.memory_module, self)

    @property
    def RunService(self):
        if not self._ensure_instance():
            return None

        return RunService(self.memory_module, self)

    @property
    def ScriptContext(self):
        if not self._ensure_instance():
            return None

        return ScriptContext(self.memory_module, self)

    @property
    def MeshContentProvider(self):
        if not self._ensure_instance():
            return None

        return MeshContentProviderService(self.memory_module, self)

    @property
    def VisualEngine(self):
        return VisualEngine(self.memory_module)

    @property
    def TaskScheduler(self):
        return TaskScheduler(self.memory_module)

    @property
    def PlayerConfigurer(self):
        return PlayerConfigurer(self.memory_module)

    @property
    def RenderView(self):
        if not self._ensure_instance():
            return None

        offsets = self.offset_base
        try:
            ptr = self.memory_module.get_pointer(self.instance.raw_address, offsets["ToRenderView1"])
            ptr = self.memory_module.get_pointer(ptr, offsets["ToRenderView2"]) if ptr != 0 else 0
            ptr = self.memory_module.get_pointer(ptr, offsets["ToRenderView3"]) if ptr != 0 else 0
        except (KeyError, OSError):
            ptr = 0

        return RenderView(ptr, self.memory_module) if ptr != 0 else None

    @property
    def PrimitiveCount(self):
        if not self._ensure_instance():
            return 0

        return self.memory_module.read_int(
            self.instance.raw_address,
            self.offset_base["PrimitiveCount"]
        )

    # class functions #
    def GetRawService(self, name):
        if not self._ensure_instance():
            return None

        for instance in self.instance.GetChildren():
            if instance.ClassName == name:
                return instance

    def GetService(self, name):
        if not self._ensure_instance():
            return None

        if name == "ScriptContext":
            return self.ScriptContext

        if name == "VisualEngine":
            return self.VisualEngine

        if name == "TaskScheduler":
            return self.TaskScheduler

        if name == "PlayerConfigurer":
            return self.PlayerConfigurer

        for instance in self.instance.GetChildren():
            className = instance.ClassName
            if className != name:
                continue

            if className == "Players":
                return self.Players

            if className == "Workspace":
                return self.Workspace

            if className == "Lighting":
                return self.Lighting

            if className == "MouseService":
                return self.MouseService

            if className == "UserInputService":
                return self.UserInputService

            if className == "RunService":
                return self.RunService

            if className == "ScriptContext":
                return self.ScriptContext

            if className == "MeshContentProvider":
                return self.MeshContentProvider

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

class RunService(ServiceBase):
    def __init__(self, memory_module, game: DataModel):
        super().__init__()
        self.memory_module = memory_module
        self.offset_base = runservice_offsets
        try:
            run_service_instance: RBXInstance = game.GetRawService("RunService")
            if run_service_instance is None or run_service_instance.ClassName != "RunService":
                self.failed = True
            else:
                self.instance = run_service_instance
        except (KeyError, OSError):
            self.failed = True

    @property
    def HeartbeatFPS(self):
        if self.failed:
            return 0.0
        return self.memory_module.read_float(
            self.instance.raw_address,
            self.offset_base["HeartbeatFPS"]
        )

    @HeartbeatFPS.setter
    def HeartbeatFPS(self, value: float):
        if self.failed:
            return
        self._ensure_writable()
        self.memory_module.write_float(
            self.instance.raw_address + self.offset_base["HeartbeatFPS"],
            float(value)
        )

    @property
    def HeartbeatTask(self):
        if self.failed:
            return 0
        return self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["HeartbeatTask"]
        )

class ScriptContext(ServiceBase):
    def __init__(self, memory_module, game: DataModel):
        super().__init__()
        self.memory_module = memory_module
        self.offset_base = scriptcontext_offsets
        self.instance = None
        try:
            ptr = self.memory_module.get_pointer(
                game.instance.raw_address,
                game.offset_base["ScriptContext"]
            )
            if ptr == 0:
                raw_instance = game.GetRawService("ScriptContext")
                ptr = raw_instance.raw_address if raw_instance is not None else 0

            if ptr == 0:
                self.failed = True
            else:
                self.instance = RBXInstance(ptr, self.memory_module)
        except (KeyError, OSError):
            self.failed = True

    @property
    def RequireBypass(self):
        offset = self.offset_base.get("RequireBypass")
        if self.failed or offset in (None, 0):
            return None
        return self.memory_module.read_bool(self.instance.raw_address, offset)

    @RequireBypass.setter
    def RequireBypass(self, value: bool):
        offset = self.offset_base.get("RequireBypass")
        if self.failed or offset in (None, 0):
            raise AttributeError("RequireBypass is not available in the loaded offsets.")
        self._ensure_writable()
        self.memory_module.write_bool(self.instance.raw_address + offset, bool(value))

class MeshData:
    def __init__(self, raw_address: int, memory_module):
        self.raw_address = raw_address
        self.memory_module = memory_module
        self.offset_base = meshdata_offsets

    def __repr__(self):
        return f"MeshData(0x{self.raw_address:X})"

    @property
    def VertexStart(self):
        return self.memory_module.get_pointer(self.raw_address, self.offset_base["VertexStart"])

    @property
    def VertexEnd(self):
        return self.memory_module.get_pointer(self.raw_address, self.offset_base["VertexEnd"])

    @property
    def FaceStart(self):
        return self.memory_module.get_pointer(self.raw_address, self.offset_base["FaceStart"])

    @property
    def FaceEnd(self):
        return self.memory_module.get_pointer(self.raw_address, self.offset_base["FaceEnd"])

class Head:
    def __init__(self, raw_address: int, memory_module):
        self.raw_address = raw_address
        self.memory_module = memory_module
        self.offset_base = meshcontentprovider_offsets
        self.Node = raw_address
        if self.Node:
            self.NextNode()

    def NextNode(self):
        if not self.Node:
            return None

        Node = self.memory_module.get_pointer(self.Node)
        if Node and Node != self.raw_address:
            self.Node = Node
            return self.Node

        self.Node = None
        return None

    @property
    def ToMeshData(self):
        if not self.Node:
            return 0
        return self.memory_module.get_pointer(self.Node, self.offset_base["ToMeshData"])

    @property
    def MeshData(self):
        to_mesh_data = self.ToMeshData
        if not to_mesh_data:
            return None

        ptr = self.memory_module.get_pointer(to_mesh_data, self.offset_base["MeshData"])
        return MeshData(ptr, self.memory_module) if ptr != 0 else None

    def GetMeshesIds(self):
        ids = {}
        while self.Node:
            raw_id = self.AssetID
            clean_id = raw_id[raw_id.rfind("=") + 1:] if raw_id and "=" in raw_id else raw_id
            ids[raw_id] = clean_id
            self.NextNode()
        return ids

    def GetMeshData(self, id: str | tuple = None, max_nodes: int = 100_000) -> dict[str, dict[str]]:
        """
        Extract meshes.
        Args:
            id (str): If an ID is provided, the search returns when the corresponding mesh is found.
            id (tuple): If a tuple of IDs is provided, the search returns once all corresponding meshes are found.
            max_nodes: The maximum number of nodes to search through.

        Returns:
            dict: A dictionary mapping mesh IDs to their extracted data.
            Each mesh data dictionary contains:
                id (str)
                rawId (str)
                vertices (list)
                faces (list)
                vertexCount (int)
                faceCount (int)
        """
        if isinstance(id, str):
            id = (id, )

        VERTEX_SIZE = 40
        FACE_SIZE = 12

        meshes = {}
        visited = 0
        while self.Node and visited < max_nodes:
            visited += 1
            raw_id = self.AssetID
            clean_id = raw_id[raw_id.rfind("=") + 1:] if raw_id and "=" in raw_id else raw_id

            mesh = self.MeshData

            if id:
                flag = clean_id in id
            else:
                flag = True

            if mesh and flag:
                vertex_start = mesh.VertexStart
                vertex_end = mesh.VertexEnd
                face_start = mesh.FaceStart
                face_end = mesh.FaceEnd

                if (
                    vertex_start
                    and vertex_end
                    and face_start
                    and face_end
                    and vertex_end > vertex_start
                    and face_end > face_start
                ):
                    vertex_count = (vertex_end - vertex_start) // VERTEX_SIZE
                    face_count = (face_end - face_start) // FACE_SIZE

                    if 0 < vertex_count < 5_000_000 and 0 < face_count < 5_000_000:
                        vertices = []
                        for i in range(vertex_count):
                            data = bytes(self.memory_module.read(vertex_start + i * VERTEX_SIZE, VERTEX_SIZE))
                            pos = struct.unpack_from("<3f", data, 0x00)
                            normal = struct.unpack_from("<3f", data, 0x0C)
                            uv = struct.unpack_from("<2f", data, 0x18)
                            vertices.append({
                                "position": [pos[0], pos[1], pos[2]],
                                "normal": [normal[0], normal[1], normal[2]],
                                "uv": [uv[0], 1.0 - uv[1]]
                            })

                        faces = []
                        for i in range(face_count):
                            data = bytes(self.memory_module.read(face_start + i * FACE_SIZE, FACE_SIZE))
                            i1, i2, i3 = struct.unpack_from("<3I", data, 0x00)
                            if i1 < len(vertices) and i2 < len(vertices) and i3 < len(vertices):
                                faces.append([int(i1), int(i2), int(i3)])

                        meshes[clean_id] = {
                            "id": clean_id,
                            "rawId": raw_id,
                            "vertices": vertices or [],
                            "faces": faces or [],
                            "vertexCount": vertex_count,
                            "faceCount": face_count,
                        }

            if id and set(id).issubset(meshes):
                return meshes

            self.NextNode()
        return meshes

    @property
    def AssetID(self):
        if not self.Node:
            return ""
        return self.memory_module.read_string(self.Node, self.offset_base["AssetID"])

class MeshContentProviderService(ServiceBase):
    def __init__(self, memory_module, game: DataModel):
        super().__init__()
        self.memory_module = memory_module
        self.offset_base = meshcontentprovider_offsets
        try:
            provider_instance: RBXInstance = game.GetRawService("MeshContentProvider")
            if provider_instance is None or provider_instance.ClassName != "MeshContentProvider":
                self.failed = True
            else:
                self.instance = provider_instance
        except (KeyError, OSError):
            self.failed = True

    def _ptr(self, address, offset_name=0):
        if self.failed or not address:
            return 0
        offset = self.offset_base[offset_name] if isinstance(offset_name, str) else offset_name
        return self.memory_module.get_pointer(address, offset)

    @property
    def Cache(self):
        if self.failed:
            return 0
        return self._ptr(self.instance.raw_address, self.offset_base.get("Cache", 0xF0))

    @property
    def LRUCache(self):
        cache = self.Cache
        return self._ptr(cache, "LRUCache") if cache else 0

    @property
    def AssetID(self):
        if self.failed:
            return 0
        return self.memory_module.read_long(self.instance.raw_address, self.offset_base["AssetID"])

    @property
    def Head(self):
        lru_cache = self.LRUCache
        ptr = self._ptr(lru_cache, 0x08) if lru_cache else 0
        return Head(ptr, self.memory_module) if ptr != 0 else None

class PlayerConfigurer:
    def __init__(self, memory_module, raw_address: int | None = None):
        self.memory_module = memory_module
        self.offset_base = playerconfigurer_offsets
        try:
            if raw_address is None:
                raw_address = self.memory_module.get_address(self.offset_base["Pointer"], pointer=True)
        except (KeyError, OSError):
            raw_address = 0
        self.raw_address = raw_address or 0
        self.failed = self.raw_address == 0

    def __repr__(self):
        return f"PlayerConfigurer(0x{self.raw_address:X})"

class RenderView:
    def __init__(self, raw_address: int, memory_module):
        self.raw_address = raw_address
        self.memory_module = memory_module
        self.offset_base = renderview_offsets

    def __repr__(self):
        return f"RenderView(0x{self.raw_address:X})"

    @property
    def DeviceD3D11(self):
        return self.memory_module.get_pointer(self.raw_address, self.offset_base["DeviceD3D11"])

    @property
    def LightingValid(self):
        return self.memory_module.read_bool(self.raw_address, self.offset_base["LightingValid"])

    @property
    def SkyValid(self):
        return self.memory_module.read_bool(self.raw_address, self.offset_base["SkyValid"])

    @property
    def VisualEngine(self):
        ptr = self.memory_module.get_pointer(self.raw_address, self.offset_base["VisualEngine"])
        return VisualEngine(self.memory_module, ptr) if ptr != 0 else None

class RenderJob:
    def __init__(self, raw_address: int, memory_module):
        self.raw_address = raw_address
        self.memory_module = memory_module
        self.offset_base = renderjob_offsets

    def __repr__(self):
        return f"RenderJob(0x{self.raw_address:X})"

    @property
    def RenderView(self):
        ptr = self.memory_module.get_pointer(self.raw_address, self.offset_base["RenderView"])
        return RenderView(ptr, self.memory_module) if ptr != 0 else None

    @property
    def FakeDataModel(self):
        return self.memory_module.get_pointer(self.raw_address, self.offset_base["FakeDataModel"])

    @property
    def RealDataModel(self):
        ptr = self.memory_module.get_pointer(self.raw_address, self.offset_base["RealDataModel"])
        return RBXInstance(ptr, self.memory_module) if ptr != 0 else None

class VisualEngine:
    def __init__(self, memory_module, raw_address: int | None = None):
        self.memory_module = memory_module
        self.offset_base = visualengine_offsets
        try:
            if raw_address is None:
                raw_address = self.memory_module.get_address(self.offset_base["Pointer"], pointer=True)
        except (KeyError, OSError):
            raw_address = 0
        self.raw_address = raw_address or 0
        self.failed = self.raw_address == 0

    def __repr__(self):
        return f"VisualEngine(0x{self.raw_address:X})"

    def _ensure_writable(self):
        if not hasattr(self.memory_module, "write"):
            raise RuntimeError("Write operations require a memory module with write support (allow_write=True).")

    @property
    def Dimensions(self):
        if self.failed:
            return None
        data = self.memory_module.read_floats(
            self.raw_address + self.offset_base["Dimensions"],
            2
        )
        return Vector2(*data)

    @Dimensions.setter
    def Dimensions(self, value):
        if self.failed:
            return
        self._ensure_writable()
        size = RBXInstance._as_vector2(value, "Dimensions")
        self.memory_module.write_floats(
            self.raw_address + self.offset_base["Dimensions"],
            (size.X, size.Y)
        )

    @property
    def ViewMatrix(self):
        if self.failed:
            return []
        return self.memory_module.read_floats(
            self.raw_address + self.offset_base["ViewMatrix"],
            16
        )

    @property
    def RenderView(self):
        if self.failed:
            return None
        ptr = self.memory_module.get_pointer(
            self.raw_address,
            self.offset_base["RenderView"]
        )
        return RenderView(ptr, self.memory_module) if ptr != 0 else None

    @property
    def FakeDataModel(self):
        if self.failed:
            return 0
        return self.memory_module.get_pointer(
            self.raw_address,
            self.offset_base["FakeDataModel"]
        )

class TaskSchedulerJob:
    def __init__(self, raw_address: int, memory_module):
        self.raw_address = raw_address
        self.memory_module = memory_module

    def __repr__(self):
        return f"TaskSchedulerJob(name={self.Name!r}, address=0x{self.raw_address:X})"

    @property
    def Name(self):
        return self.memory_module.read_string(
            self.raw_address,
            taskscheduler_offsets["JobName"]
        )

class TaskScheduler:
    def __init__(self, memory_module, raw_address: int | None = None):
        self.memory_module = memory_module
        self.offset_base = taskscheduler_offsets
        try:
            if raw_address is None:
                raw_address = self.memory_module.get_address(self.offset_base["Pointer"], pointer=True)
        except (KeyError, OSError):
            raw_address = 0
        self.raw_address = raw_address or 0
        self.failed = self.raw_address == 0

    def __repr__(self):
        return f"TaskScheduler(0x{self.raw_address:X})"

    def _ensure_writable(self):
        if not hasattr(self.memory_module, "write"):
            raise RuntimeError("Write operations require a memory module with write support (allow_write=True).")

    @property
    def JobStart(self):
        if self.failed:
            return 0
        return self.memory_module.get_pointer(self.raw_address, self.offset_base["JobStart"])

    @property
    def JobEnd(self):
        if self.failed:
            return 0
        return self.memory_module.get_pointer(self.raw_address, self.offset_base["JobEnd"])

    @property
    def FrameDelay(self):
        if self.failed:
            return 0.0
        return self.memory_module.read_double(
            self.raw_address,
            self.offset_base["MaxFPS"]
        )

    @FrameDelay.setter
    def FrameDelay(self, value: float):
        if self.failed:
            return
        self._ensure_writable()
        self.memory_module.write_double(
            self.raw_address + self.offset_base["MaxFPS"],
            float(value)
        )

    @property
    def MaxFPS(self):
        delay = self.FrameDelay
        if delay <= 0:
            return 0.0
        return 1.0 / delay

    @MaxFPS.setter
    def MaxFPS(self, value: float):
        fps = float(value)
        self.FrameDelay = 1.0 / fps if fps > 0 else 1.0 / 10000.0

    def GetJobs(self):
        if self.failed:
            return []

        start = self.JobStart
        end = self.JobEnd
        if start == 0 or end == 0 or end < start:
            return []

        jobs = []
        for node in range(start, end, 8):
            try:
                job_ptr = self.memory_module.get_pointer(node)
            except OSError:
                break
            if job_ptr != 0:
                jobs.append(TaskSchedulerJob(job_ptr, self.memory_module))
        return jobs

    def FindJob(self, name: str):
        for job in self.GetJobs():
            try:
                if job.Name == name:
                    return job
            except (OSError, ValueError):
                continue
        return None

    @property
    def RenderJob(self):
        job = self.FindJob("RenderJob")
        return RenderJob(job.raw_address, self.memory_module) if job is not None else None

class PlayersService(ServiceBase):
    def __init__(self, memory_module, game: DataModel):
        super().__init__()
        self.memory_module = memory_module
        self.offset_base = Offsets["Player"]

        try:
            players_instance: RBXInstance = game.GetRawService("Players")
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
            workspace_instance: RBXInstance = game.GetRawService("Workspace")
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
    
    @property
    def Gravity(self):
        World = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["World"]
        )

        return self.memory_module.read_float(
            World,
            world_offsets["Gravity"]
        )

    @Gravity.setter
    def Gravity(self, value: float):
        self._ensure_writable()

        World = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["World"]
        )

        self.memory_module.write_float(
            World + world_offsets["Gravity"],
            float(value)
        )

    @property
    def DistributedGameTime(self):
        if self.failed: 
            return 0.0

        return self.memory_module.read_double(
            self.instance.raw_address,
            self.offset_base["DistributedGameTime"]
        )

    @property
    def WorldStepsPerSec(self):
        if self.failed:
            return 0.0

        World = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["World"]
        )

        return self.memory_module.read_float(
            World,
            world_offsets["worldStepsPerSec"]
        )

    @WorldStepsPerSec.setter
    def WorldStepsPerSec(self, value: float):
        self._ensure_writable()

        World = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["World"]
        )

        self.memory_module.write_float(
            World + world_offsets["worldStepsPerSec"],
            float(value)
        )

    @property
    def FallenPartsDestroyHeight(self):
        if self.failed:
            return 0.0

        World = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["World"]
        )

        return self.memory_module.read_float(
            World,
            world_offsets["FallenPartsDestroyHeight"]
        )

    @FallenPartsDestroyHeight.setter
    def FallenPartsDestroyHeight(self, value: float):
        self._ensure_writable()

        World = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["World"]
        )

        self.memory_module.write_float(
            World + world_offsets["FallenPartsDestroyHeight"],
            float(value)
        )

    def _get_air_properties(self):
        """Returns the AirProperties pointer from World."""
        World = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["World"]
        )
        return self.memory_module.get_pointer(
            World,
            world_offsets["AirProperties"]
        )

    @property
    def AirDensity(self):
        if self.failed:
            return 0.0

        air = self._get_air_properties()
        return self.memory_module.read_float(
            air,
            air_properties_offsets["AirDensity"]
        )

    @AirDensity.setter
    def AirDensity(self, value: float):
        self._ensure_writable()
        air = self._get_air_properties()
        self.memory_module.write_float(
            air + air_properties_offsets["AirDensity"],
            float(value)
        )

    @property
    def GlobalWind(self):
        if self.failed:
            return None

        air = self._get_air_properties()
        data = self.memory_module.read_floats(
            air + air_properties_offsets["GlobalWind"],
            3
        )
        return Vector3(*data)

    @GlobalWind.setter
    def GlobalWind(self, value):
        self._ensure_writable()
        if isinstance(value, Vector3):
            v = value
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            v = Vector3(*value)
        else:
            raise TypeError("GlobalWind must be a Vector3 or iterable of 3 numbers.")
        air = self._get_air_properties()
        self.memory_module.write_floats(
            air + air_properties_offsets["GlobalWind"],
            (v.X, v.Y, v.Z)
        )

class LightingService(ServiceBase):
    def __init__(self, memory_module, game: DataModel):
        super().__init__()
        self.memory_module = memory_module
        self.offset_base = Offsets["Lighting"]
        try:
            lighting_instance: RBXInstance = game.GetRawService("Lighting")
            if lighting_instance.ClassName != "Lighting":
                self.failed = True
            else:
                self.instance = lighting_instance
        except (KeyError, OSError):
            self.failed = True

   # props #
    @property
    def ClockTime(self):
        if self.failed: return 0.0
        
        # clocktime is in milliseconds
        return self.memory_module.read_int64(
            self.instance.raw_address,
            self.offset_base["ClockTime"]
        ) / 3600000000

    @property
    def Brightness(self):
        if self.failed: return 0.0
        return self.memory_module.read_float(
            self.instance.raw_address,
            self.offset_base["Brightness"]
        )

    @Brightness.setter
    def Brightness(self, value: float):
        if self.failed: return
        self._ensure_writable()
        self.memory_module.write_float(
            self.instance.raw_address + self.offset_base["Brightness"],
            float(value)
        )

    @property
    def FogStart(self):
        if self.failed: return 0.0
        return self.memory_module.read_float(
            self.instance.raw_address,
            self.offset_base["FogStart"]
        )

    @FogStart.setter
    def FogStart(self, value: float):
        if self.failed: return
        self._ensure_writable()
        self.memory_module.write_float(
            self.instance.raw_address + self.offset_base["FogStart"],
            float(value)
        )

    @property
    def FogEnd(self):
        if self.failed: return 0.0
        return self.memory_module.read_float(
            self.instance.raw_address,
            self.offset_base["FogEnd"]
        )

    @FogEnd.setter
    def FogEnd(self, value: float):
        if self.failed: return
        self._ensure_writable()
        self.memory_module.write_float(
            self.instance.raw_address + self.offset_base["FogEnd"],
            float(value)
        )

    @property
    def FogColor(self):
        if self.failed: return None
        color_data = self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["FogColor"],
            3
        )
        return Color3(*color_data)

    @FogColor.setter
    def FogColor(self, value):
        if self.failed: return
        self._ensure_writable()
        if isinstance(value, Color3):
            self.memory_module.write_floats(
                self.instance.raw_address + self.offset_base["FogColor"],
                (value.R, value.G, value.B)
            )
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            self.memory_module.write_floats(
                self.instance.raw_address + self.offset_base["FogColor"],
                value
            )

    @property
    def Ambient(self):
        if self.failed: return None
        color_data = self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["Ambient"],
            3
        )
        return Color3(*color_data)

    @Ambient.setter
    def Ambient(self, value):
        if self.failed: return
        self._ensure_writable()
        if isinstance(value, Color3):
            self.memory_module.write_floats(
                self.instance.raw_address + self.offset_base["Ambient"],
                (value.R, value.G, value.B)
            )
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            self.memory_module.write_floats(
                self.instance.raw_address + self.offset_base["Ambient"],
                value
            )

    @property
    def OutdoorAmbient(self):
        if self.failed: return None
        color_data = self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["OutdoorAmbient"],
            3
        )
        return Color3(*color_data)

    @OutdoorAmbient.setter
    def OutdoorAmbient(self, value):
        if self.failed: return
        self._ensure_writable()
        if isinstance(value, Color3):
            self.memory_module.write_floats(
                self.instance.raw_address + self.offset_base["OutdoorAmbient"],
                (value.R, value.G, value.B)
            )
        elif isinstance(value, (tuple, list)) and len(value) == 3:
            self.memory_module.write_floats(
                self.instance.raw_address + self.offset_base["OutdoorAmbient"],
                value
            )

    @property
    def ColorShift_Top(self):
        if self.failed: return None
        color_data = self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["ColorShift_Top"],
            3
        )
        return Color3(*color_data)

    @ColorShift_Top.setter
    def ColorShift_Top(self, value):
        if self.failed: return
        self._ensure_writable()
        color = RBXInstance._as_color3(value, "ColorShift_Top")
        self.memory_module.write_floats(
            self.instance.raw_address + self.offset_base["ColorShift_Top"],
            (color.R, color.G, color.B)
        )

    @property
    def ColorShift_Bottom(self):
        if self.failed: return None
        color_data = self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["ColorShift_Bottom"],
            3
        )
        return Color3(*color_data)

    @ColorShift_Bottom.setter
    def ColorShift_Bottom(self, value):
        if self.failed: return
        self._ensure_writable()
        color = RBXInstance._as_color3(value, "ColorShift_Bottom")
        self.memory_module.write_floats(
            self.instance.raw_address + self.offset_base["ColorShift_Bottom"],
            (color.R, color.G, color.B)
        )

    @property
    def GradientTop(self):
        if self.failed: return None
        return Color3(*self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["GradientTop"],
            3
        ))

    @GradientTop.setter
    def GradientTop(self, value):
        if self.failed: return
        self._ensure_writable()
        color = RBXInstance._as_color3(value, "GradientTop")
        self.memory_module.write_floats(
            self.instance.raw_address + self.offset_base["GradientTop"],
            (color.R, color.G, color.B)
        )

    @property
    def GradientBottom(self):
        if self.failed: return None
        return Color3(*self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["GradientBottom"],
            3
        ))

    @GradientBottom.setter
    def GradientBottom(self, value):
        if self.failed: return
        self._ensure_writable()
        color = RBXInstance._as_color3(value, "GradientBottom")
        self.memory_module.write_floats(
            self.instance.raw_address + self.offset_base["GradientBottom"],
            (color.R, color.G, color.B)
        )

    @property
    def LightColor(self):
        if self.failed: return None
        return Color3(*self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["LightColor"],
            3
        ))

    @property
    def LightDirection(self):
        if self.failed: return None
        return Vector3(*self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["LightDirection"],
            3
        ))

    @property
    def ExposureCompensation(self):
        if self.failed: return 0.0
        return self.memory_module.read_float(
            self.instance.raw_address,
            self.offset_base["ExposureCompensation"]
        )

    @ExposureCompensation.setter
    def ExposureCompensation(self, value: float):
        if self.failed: return
        self._ensure_writable()
        self.memory_module.write_float(
            self.instance.raw_address + self.offset_base["ExposureCompensation"],
            float(value)
        )

    @property
    def GeographicLatitude(self):
        if self.failed: return 0.0
        return self.memory_module.read_float(
            self.instance.raw_address,
            self.offset_base["GeographicLatitude"]
        )

    @GeographicLatitude.setter
    def GeographicLatitude(self, value: float):
        if self.failed: return
        self._ensure_writable()
        self.memory_module.write_float(
            self.instance.raw_address + self.offset_base["GeographicLatitude"],
            float(value)
        )

    @property
    def Sky(self):
        if self.failed: return None
        sky_ptr = self.memory_module.get_pointer(
            self.instance.raw_address,
            self.offset_base["Sky"]
        )
        if sky_ptr == 0:
            return None
        return RBXInstance(sky_ptr, self.memory_module)

    @property
    def Source(self):
        if self.failed: return None
        return self.memory_module.read_int(
            self.instance.raw_address,
            self.offset_base["Source"]
        )

    @property
    def SunPosition(self):
        if self.failed: return None
        pos_data = self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["SunPosition"],
            3
        )
        return Vector3(*pos_data)

    @property
    def MoonPosition(self):
        if self.failed: return None
        pos_data = self.memory_module.read_floats(
            self.instance.raw_address + self.offset_base["MoonPosition"],
            3
        )
        return Vector3(*pos_data)

    @property
    def EnvironmentDiffuseScale(self):
        if self.failed: return 0.0
        return self.memory_module.read_float(
            self.instance.raw_address,
            self.offset_base["EnvironmentDiffuseScale"]
        )

    @EnvironmentDiffuseScale.setter
    def EnvironmentDiffuseScale(self, value: float):
        if self.failed: return
        self._ensure_writable()
        self.memory_module.write_float(
            self.instance.raw_address + self.offset_base["EnvironmentDiffuseScale"],
            float(value)
        )

    @property
    def EnvironmentSpecularScale(self):
        if self.failed: return 0.0
        return self.memory_module.read_float(
            self.instance.raw_address,
            self.offset_base["EnvironmentSpecularScale"]
        )

    @EnvironmentSpecularScale.setter
    def EnvironmentSpecularScale(self, value: float):
        if self.failed: return
        self._ensure_writable()
        self.memory_module.write_float(
            self.instance.raw_address + self.offset_base["EnvironmentSpecularScale"],
            float(value)
        )

    @property
    def GlobalShadows(self):
        if self.failed: return None
        return self.memory_module.read_bool(
            self.instance.raw_address,
            self.offset_base["GlobalShadows"]
        )

    @GlobalShadows.setter
    def GlobalShadows(self, value: bool):
        if self.failed: return
        self._ensure_writable()
        self.memory_module.write_bool(
            self.instance.raw_address + self.offset_base["GlobalShadows"],
            bool(value)
        )

class InputObject(RBXInstance):
    def __init__(self, raw_address: int, memory_module):
        super().__init__(raw_address, memory_module)

    @property
    def MousePosition(self):
        pos_data = self.memory_module.read_floats(
            self.raw_address + inputobject_offsets["MousePosition"],
            2
        )
        return Vector2(*pos_data)

    @MousePosition.setter
    def MousePosition(self, value):
        self._ensure_writable()
        if isinstance(value, Vector2):
            pos = (value.X, value.Y)
        elif isinstance(value, (tuple, list)) and len(value) == 2:
            pos = (float(value[0]), float(value[1]))
        else:
            raise TypeError("MousePosition must be a Vector2 or tuple/list of 2 numbers")
        self.memory_module.write_floats(
            self.raw_address + inputobject_offsets["MousePosition"],
            pos
        )
    

class MouseService(ServiceBase):
    def __init__(self, memory_module, game: DataModel):
        super().__init__()
        self.memory_module = memory_module
        self.offset_base = Offsets["MouseService"]
        try:
            mouse_instance: RBXInstance = game.GetRawService("MouseService")
            if mouse_instance is None or mouse_instance.ClassName != "MouseService":
                self.failed = True
            else:
                self.instance = mouse_instance
        except (KeyError, OSError):
            self.failed = True

    @property
    def InputObject(self):
        if self.failed:
            return None
        try:
            input_ptr = self.memory_module.get_pointer(
                self.instance.raw_address,
                self.offset_base["InputObject"]
            )
            if input_ptr == 0:
                return None
            return InputObject(input_ptr, self.memory_module)
        except (KeyError, OSError):
            return None

    @property
    def MousePosition(self):
        input_obj = self.InputObject
        if input_obj is None:
            return None
        return input_obj.MousePosition

    @MousePosition.setter
    def MousePosition(self, value):
        input_obj = self.InputObject
        if input_obj is None:
            return
        input_obj.MousePosition = value

    @property
    def InputObject2(self):
        if self.failed:
            return None
        try:
            input_ptr = self.memory_module.get_pointer(
                self.instance.raw_address,
                self.offset_base["InputObject2"]
            )
            if input_ptr == 0:
                return None
            return InputObject(input_ptr, self.memory_module)
        except (KeyError, OSError):
            return None

class UserInputService(ServiceBase):
    def __init__(self, memory_module, game: DataModel):
        super().__init__()
        self.memory_module = memory_module
        self.offset_base = Offsets["UserInputService"]
        try:
            uis_instance: RBXInstance = game.GetRawService("UserInputService")
            if uis_instance is None or uis_instance.ClassName != "UserInputService":
                self.failed = True
            else:
                self.instance = uis_instance
        except (KeyError, OSError):
            self.failed = True

    @property
    def WindowInputState(self):
        if self.failed:
            return None
        try:
            ptr = self.memory_module.get_pointer(
                self.instance.raw_address,
                self.offset_base["WindowInputState"]
            )
            if ptr == 0:
                return None
            return WindowInputState(ptr, self.memory_module)
        except (KeyError, OSError):
            return None

class WindowInputState(RBXInstance):
    def __init__(self, raw_address: int, memory_module):
        super().__init__(raw_address, memory_module)
        self._wis_offsets = Offsets["WindowInputState"]

    @property
    def CapsLock(self):
        return self.memory_module.read_bool(
            self.raw_address,
            self._wis_offsets["CapsLock"]
        )

    @property
    def CurrentTextBox(self):
        ptr = self.memory_module.get_pointer(
            self.raw_address,
            self._wis_offsets["CurrentTextBox"]
        )
        if ptr == 0:
            return None
        return RBXInstance(ptr, self.memory_module)
