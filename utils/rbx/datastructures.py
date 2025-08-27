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
        # Leverage UDim.__repr__ to format each component
        return f"{{{self.X}, {self.Y}}}"

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


import math


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

    # Vector utilities
    def Cross(self, other):
        return Vector3(
            self.Y * other.Z - self.Z * other.Y,
            self.Z * other.X - self.X * other.Z,
            self.X * other.Y - self.Y * other.X,
        )

    def Magnitude(self):
        return math.sqrt(self.X * self.X + self.Y * self.Y + self.Z * self.Z)

    def Unit(self):
        m = self.Magnitude()
        if m == 0:
            return Vector3(0, 0, 0)
        return Vector3(self.X / m, self.Y / m, self.Z / m)


class CFrame:
    def __init__(self, position=None, right=None, up=None, look=None):
        self.Position = position or Vector3(0, 0, 0)

        # If any axis is provided, compute a clean orthonormal basis.
        if right is None and up is None and look is None:
            self.RightVector = Vector3(1, 0, 0)
            self.UpVector = Vector3(0, 1, 0)
            self.LookVector = Vector3(0, 0, -1)
        else:
            r, u, l = self._orthonormal_basis(right, up, look)
            self.RightVector, self.UpVector, self.LookVector = r, u, l

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

    @staticmethod
    def _orthonormal_basis(right=None, up=None, look=None):
        """
        Build a right-handed orthonormal basis (r, u, l) from any combination
        of provided axes. If only one is provided, pick a stable orthogonal
        fallback for the next, then derive the third via cross products so that
        r × u = l.
        """
        def unit(v: Vector3 | None):
            return v.Unit() if isinstance(v, Vector3) else None

        def nearly_parallel(a: Vector3, b: Vector3) -> bool:
            ma, mb = a.Magnitude(), b.Magnitude()
            if ma == 0 or mb == 0:
                return True
            return abs(a.Dot(b) / (ma * mb)) > 0.9999

        def orthogonal_to(v: Vector3) -> Vector3:
            # Choose a fallback not parallel to v and remove projection.
            fallback = Vector3(0, 1, 0)
            if nearly_parallel(v, fallback):
                fallback = Vector3(1, 0, 0)
            return (fallback - v * fallback.Dot(v)).Unit()

        r = unit(right)
        u = unit(up)
        l = unit(look)

        if r is not None and u is not None:
            u = (u - r * u.Dot(r)).Unit()
            l = r.Cross(u).Unit()
            return r, u, l
        if r is not None and l is not None:
            l = (l - r * l.Dot(r)).Unit()
            u = l.Cross(r).Unit()
            l = r.Cross(u).Unit()
            return r, u, l
        if u is not None and l is not None:
            u = u.Unit()
            l = (l - u * l.Dot(u)).Unit()
            r = u.Cross(l).Unit()
            u = l.Cross(r).Unit()
            return r, u, l
        if r is not None:
            u = orthogonal_to(r)
            l = r.Cross(u).Unit()
            return r, u, l
        if u is not None:
            r = orthogonal_to(u)
            l = r.Cross(u).Unit()
            return r, u, l
        if l is not None:
            u = orthogonal_to(l)
            r = u.Cross(l).Unit()
            u = l.Cross(r).Unit()
            return r, u, l

        # Fallback to defaults (shouldn't reach here because caller checks)
        return Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, -1)

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
            p = self.Position + other.Position
            return CFrame(p, r, u, l)
        if isinstance(other, Vector3):
            return self.Position + self._rotate_vector(other)
        raise TypeError("CFrame can only be multiplied by CFrame or Vector3")
