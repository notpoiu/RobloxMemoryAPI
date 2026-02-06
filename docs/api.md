# API Reference

## robloxmemoryapi.RobloxGameClient

Attach to the Roblox process and create a DataModel wrapper.

Constructor:
- `RobloxGameClient(pid=None, process_name="RobloxPlayerBeta.exe", allow_write=False)`

Parameters:
- `pid`: Optional process ID to attach to.
- `process_name`: Executable name to search for when `pid` is not provided.
- `allow_write`: Request write permissions for memory operations.

Attributes:
- `pid`: The attached process ID.
- `failed`: `True` when attach failed or on non-Windows platforms.
- `memory_module`: Internal memory accessor (useful if you need lower-level control).

Properties:
- `DataModel`: Returns a `DataModel` instance. Raises if not on Windows or if attach failed.

Methods:
- `close()`: Close the process handle.

## robloxmemoryapi.RobloxRandom

Deterministic RNG compatible with Roblox behavior.

Methods:
- `NextNumber(minimum=0.0, maximum=1.0) -> float`
- `NextInteger(a, b=None) -> int`

## robloxmemoryapi.utils.rbx.instance.RBXInstance

Represents a Roblox Instance at a memory address. Attribute access attempts to find child instances by name.

Traversal and utilities:
- `GetChildren() -> list[RBXInstance]`
- `GetDescendants() -> list[RBXInstance]`
- `GetFullName() -> str`
- `FindFirstChild(name, recursive=False) -> RBXInstance | None`
- `FindFirstChildOfClass(classname) -> RBXInstance | None`
- `WaitForChild(name, timeout=5) -> RBXInstance | None`

Attributes:
- `GetAttributes() -> dict[str, AttributeValue]`
- `GetAttribute(name) -> AttributeValue | None`
- `SetAttribute(name, value) -> None`

Common properties (availability depends on instance class):
- `Name`, `ClassName`, `Parent`
- `CFrame` (BasePart and Camera)
- `Position` (BasePart, Camera, and GUI objects)
- `Size` (BasePart or GUI objects)
- `AssemblyLinearVelocity`, `AssemblyAngularVelocity`, `Velocity`
- `Transparency`, `Color`, `Anchored`, `CanCollide`, `CanTouch`

GUI-related properties:
- `LayoutOrder`, `Visible`, `Image`, `Text`, `RichText`
- `BackgroundColor3`, `BorderColor3`, `TextColor3`, `Rotation`
- `text_capacity` (read-only string capacity helper)

Value object helpers:
- `Value` (StringValue, IntValue, NumberValue, BoolValue, ObjectValue)
- `GetValue()` and `SetValue()` for `StatsItem`

ProximityPrompt and ClickDetector:
- `Enabled`, `MaxActivationDistance`, `HoldDuration`
- `ObjectText`, `ActionText`, `RequiresLineOfSight`, `CursorIcon`

Humanoid-related:
- `WalkSpeed`, `JumpPower`, `JumpHeight`, `HipHeight`, `MaxSlopeAngle`
- `RigType`, `FloorMaterial`, `Jump`, `MoveDirection`, `AutoRotate`
- `Health`, `MaxHealth`, `HumanoidState`

Other:
- `Adornee` (GUI adornment targets)
- `AnimationId` (Animation instances)
- `PrimaryPart` (Model instances)
- `Bytecode` and `RawBytecode` (LocalScript and ModuleScript)

## robloxmemoryapi.utils.rbx.instance.AttributeValue

Represents a typed Attribute entry.

Properties:
- `value`: Read or write the underlying attribute value.
- `name`: Attribute name.
- `type_name`: Attribute type name.

## robloxmemoryapi.utils.rbx.instance.DataModel

Wraps the Roblox DataModel and supports auto refresh.

Constructor:
- `DataModel(memory_module, auto_refresh=True, refresh_interval=0.5)`

Methods:
- `refresh_datamodel()`
- `start_auto_refresh(interval=None)`
- `stop_auto_refresh()`
- `bind_to_refresh(callback, invoke_if_ready=False)`
- `unbind_from_refresh(callback)`
- `GetRawService(name)`
- `GetService(name)`
- `IsLoaded() -> bool`
- `is_lua_app() -> bool`

Properties:
- `ServerIP`, `CreatorId`, `PlaceId`, `GameId`, `JobId`, `PlaceVersion`
- `Players`, `Workspace`, `Lighting`, `MouseService`

## Services

### PlayersService

Properties:
- `LocalPlayer -> PlayerClass | None`

Methods:
- `GetPlayers() -> list[PlayerClass]`

### WorkspaceService

Properties:
- `CurrentCamera -> CameraClass | None`
- `Gravity`
- `DistributedGameTime`

### LightingService

Properties:
- `ClockTime`, `Brightness`, `FogStart`, `FogEnd`, `FogColor`
- `Ambient`, `OutdoorAmbient`, `ColorShift_Top`, `ColorShift_Bottom`
- `ExposureCompensation`, `GeographicLatitude`

### MouseService

Properties:
- `InputObject -> InputObject | None`
- `MousePosition`

## PlayerClass

Player-specific wrapper.

Properties:
- `Character -> RBXInstance | None`
- `DisplayName`, `UserId`, `Team`, `Country`
- `MinZoomDistance`, `MaxZoomDistance`, `CameraMode`

## CameraClass

Camera-specific wrapper.

Properties:
- `FieldOfView`, `FieldOfViewRadians`, `ViewportSize`
- `CameraType`, `CameraSubject`

## InputObject

Properties:
- `MousePosition`
