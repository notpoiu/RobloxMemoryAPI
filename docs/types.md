# Data Types

These classes live in `robloxmemoryapi.utils.rbx.datastructures` and are used throughout the API.

## Vector2

Represents a 2D vector.

```python
from robloxmemoryapi.utils.rbx.datastructures import Vector2

v = Vector2(10, 20)
print(v.X, v.Y)
```

## Vector3

Represents a 3D vector and supports basic vector math.

```python
from robloxmemoryapi.utils.rbx.datastructures import Vector3

a = Vector3(1, 2, 3)
b = Vector3(4, 5, 6)
print(a + b)
print(a.Dot(b))
```

## Color3

RGB color in 0..1 space with basic math and conversion helpers.

```python
from robloxmemoryapi.utils.rbx.datastructures import Color3

c = Color3(1.0, 0.5, 0.25)
print(c.ToRGB())
```

## UDim And UDim2

UDim is a (scale, offset) pair. UDim2 contains X and Y UDim values.

```python
from robloxmemoryapi.utils.rbx.datastructures import UDim, UDim2

u = UDim(0.5, 10)
ui = UDim2.fromScale(0.5, 0.5)
```

## CFrame

Represents a coordinate frame with a position and orthonormal basis.

```python
from robloxmemoryapi.utils.rbx.datastructures import CFrame, Vector3

cf = CFrame.new(0, 5, 0)
cf2 = cf + Vector3(0, 10, 0)
```
