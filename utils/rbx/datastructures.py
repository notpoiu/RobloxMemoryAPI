class UDim:
    def __init__(self, scale=0, offset=0):
        self.Scale = float(scale)
        self.Offset = int(offset)

    def __repr__(self):
        return f"{{{self.Scale}, {self.Offset}}}"

class UDim2:
    def __init__(self, scaleX=0, offsetX=0, scaleY=0, offsetY=0):
        self.X = UDim(scaleX, offsetX)
        self.Y = UDim(scaleY, offsetY)

    def __repr__(self):
        return f"{{{self.X.Scale}, {self.X.Offset}}}, {{{self.Y.Scale}, {self.Y.Offset}}}"

    @classmethod
    def fromScale(cls, scaleX, scaleY):
        return cls(scaleX, 0, scaleY, 0)

    @classmethod
    def fromOffset(cls, offsetX, offsetY):
        return cls(0, offsetX, 0, offsetY)

class Vector2:
    def __init__(self, x=0, y=0):
        self.X = float(x)
        self.Y = float(y)

    def __repr__(self):
        return f"{self.X}, {self.Y}"

    def __eq__(self, other):
        return (
            isinstance(other, Vector2)
            and self.X == other.X
            and self.Y == other.Y
        )


class Vector3:
    def __init__(self, x=0, y=0, z=0):
        self.X = float(x)
        self.Y = float(y)
        self.Z = float(z)

    def __repr__(self):
        return f"{self.X}, {self.Y}, {self.Z}"

    def __eq__(self, other):
        return (
            isinstance(other, Vector3)
            and self.X == other.X
            and self.Y == other.Y
            and self.Z == other.Z
        )
    
    def __add__(self, other):
        if isinstance(other, Vector3):
            return Vector3(self.X + other.X, self.Y + other.Y, self.Z + other.Z)
        raise TypeError("Vector3 can only be added to Vector3")

    def __sub__(self, other):
        if isinstance(other, Vector3):
            return Vector3(self.X - other.X, self.Y - other.Y, self.Z - other.Z)
        raise TypeError("Vector3 can only be subtracted by Vector3")

    def __mul__(self, other):
        if isinstance(other, Vector3):
            return Vector3(self.X * other.X, self.Y * other.Y, self.Z * other.Z)
        if isinstance(other, (int, float)):
            return Vector3(self.X * other, self.Y * other, self.Z * other)
        raise TypeError("Vector3 can only be multiplied by Vector3 or a number")

    def __rmul__(self, other):
        if isinstance(other, (int, float)):
            return Vector3(self.X * other, self.Y * other, self.Z * other)
        return NotImplemented

    def __truediv__(self, other):
        if isinstance(other, Vector3):
            return Vector3(self.X / other.X, self.Y / other.Y, self.Z / other.Z)
        if isinstance(other, (int, float)):
            return Vector3(self.X / other, self.Y / other, self.Z / other)
        raise TypeError("Vector3 can only be divided by Vector3 or a number")

    def __floordiv__(self, other):
        if isinstance(other, Vector3):
            return Vector3(self.X // other.X, self.Y // other.Y, self.Z // other.Z)
        if isinstance(other, (int, float)):
            return Vector3(self.X // other, self.Y // other, self.Z // other)
        raise TypeError("Vector3 can only be floor-divided by Vector3 or a number")

    def __neg__(self):
        return Vector3(-self.X, -self.Y, -self.Z)

    def Dot(self, other):
        return self.X * other.X + self.Y * other.Y + self.Z * other.Z


class CFrame:
    def __init__(self, position=None, right=None, up=None, look=None):
        self.Position = position or Vector3(0, 0, 0)
        self.RightVector = right or Vector3(1, 0, 0)
        self.UpVector = up or Vector3(0, 1, 0)
        self.LookVector = look or Vector3(0, 0, -1)

    def __repr__(self):
        return (
            f"{self.Position}, {self.RightVector}, {self.UpVector}, {self.LookVector}"
        )

    def __eq__(self, value):
        return (
            isinstance(value, CFrame)
            and self.Position == value.Position
            and self.RightVector == value.RightVector
            and self.UpVector == value.UpVector
            and self.LookVector == value.LookVector
        )

    @classmethod
    def new(cls, x=0, y=0, z=0):
        return cls(position=Vector3(x, y, z))

    # Helpers to apply rotation only
    def _rotate_vector(self, v: Vector3) -> Vector3:
        return (
            self.RightVector * v.X + self.UpVector * v.Y + self.LookVector * v.Z
        )

    def __add__(self, other):
        if isinstance(other, Vector3):
            return CFrame(
                self.Position + other,
                self.RightVector,
                self.UpVector,
                self.LookVector,
            )
        raise TypeError("CFrame can only be added to Vector3")

    def __sub__(self, other):
        if isinstance(other, Vector3):
            return CFrame(
                self.Position - other,
                self.RightVector,
                self.UpVector,
                self.LookVector,
            )
        raise TypeError("CFrame can only be subtracted by Vector3")

    def __mul__(self, other):
        if isinstance(other, CFrame):
            r = self._rotate_vector(other.RightVector)
            u = self._rotate_vector(other.UpVector)
            l = self._rotate_vector(other.LookVector)

            p = self.Position + self._rotate_vector(other.Position)
            return CFrame(p, r, u, l)
        if isinstance(other, Vector3):
            return self.Position + self._rotate_vector(other)
        raise TypeError("CFrame can only be multiplied by CFrame or Vector3")
