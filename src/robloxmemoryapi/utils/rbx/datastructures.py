import math

def get_flat_matrix_column(matrix, column, invert_values=False):
    stride = 3

    if invert_values:
        return [matrix[column + i * stride] * -1 for i in range(3)]
    
    return [matrix[column + i * stride] for i in range(3)]

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

class Color3:
    def __init__(self, r=0, g=0, b=0):
        self.R = float(r)
        self.G = float(g)
        self.B = float(b)

    def __repr__(self):
        return f"{self.R}, {self.G}, {self.B}"
    
    def __eq__(self, other):
        return (
            isinstance(other, Color3)
            and self.R == other.R
            and self.G == other.G
            and self.B == other.B
        )
    
    def __add__(self, other):
        if isinstance(other, Color3):
            return Color3(self.R + other.R, self.G + other.G, self.B + other.B)
        raise TypeError("Color3 can only be added to Color3")
    
    def __sub__(self, other):
        if isinstance(other, Color3):
            return Color3(self.R - other.R, self.G - other.G, self.B - other.B)
        raise TypeError("Color3 can only be subtracted by Color3")
    
    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return Color3(self.R * other, self.G * other, self.B * other)
        if isinstance(other, Color3):
            return Color3(self.R * other.R, self.G * other.G, self.B * other.B)
        raise TypeError("Color3 can only be multiplied by Color3 or a number")
    
    __rmul__ = __mul__
    
    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return Color3(self.R / other, self.G / other, self.B / other)
        if isinstance(other, Color3):
            return Color3(self.R / other.R, self.G / other.G, self.B / other.B)
        raise TypeError("Color3 can only be divided by Color3 or a number")
    
    def __neg__(self):
        return Color3(-self.R, -self.G, -self.B)
    
    def ToHex(self):
        return f"#{int(self.R * 255):02x}{int(self.G * 255):02x}{int(self.B * 255):02x}"
    
    def ToTuple(self):
        return (self.R, self.G, self.B)
    
    def ToVector3(self):
        return Vector3(self.R, self.G, self.B)

    def ToRGB(self):
        return (int(self.R * 255), int(self.G * 255), int(self.B * 255))
    
    def ToHSV(self):
        maxc = max(self.R, self.G, self.B)
        minc = min(self.R, self.G, self.B)
        
        if maxc == minc:
            return (0, 0, maxc)
        
        h = 0
        if maxc == self.R:
            h = (self.G - self.B) / (maxc - minc)
        elif maxc == self.G:
            h = 2 + (self.B - self.R) / (maxc - minc)
        else:
            h = 4 + (self.R - self.G) / (maxc - minc)
        
        return (h / 6, maxc, minc)
    
    def ToCMYK(self):
        if self.R == 0 and self.G == 0 and self.B == 0:
            return (0, 0, 0, 1)
        
        c = 1 - self.R
        m = 1 - self.G
        y = 1 - self.B
        k = min(c, m, y)
        
        return (c, m, y, k)
    
    def ToCMY(self):
        return (1 - self.R, 1 - self.G, 1 - self.B)
        

class Vector3:
    def __init__(self, x=0, y=0, z=0):
        self.X = float(x)
        self.Y = float(y)
        self.Z = float(z)

    def __repr__(self):
        return f"{self.X}, {self.Y}, {self.Z}"

    def __eq__(self, other):
        eps = 1e-9

        return (
            isinstance(other, Vector3)
            and abs(self.X - other.X) < eps
            and abs(self.Y - other.Y) < eps
            and abs(self.Z - other.Z) < eps
        )
    
    # --- Arithmetic ---
    def __add__(self, other):
        if isinstance(other, Vector3):
            return Vector3(self.X + other.X, self.Y + other.Y, self.Z + other.Z)
        raise TypeError("Vector3 can only be added to Vector3")

    def __sub__(self, other):
        if isinstance(other, Vector3):
            return Vector3(self.X - other.X, self.Y - other.Y, self.Z - other.Z)
        raise TypeError("Vector3 can only be subtracted by Vector3")

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return Vector3(self.X * other, self.Y * other, self.Z * other)
        if isinstance(other, Vector3):
            return Vector3(self.X * other.X, self.Y * other.Y, self.Z * other.Z)
        raise TypeError("Vector3 can only be multiplied by Vector3 or a number")

    __rmul__ = __mul__

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return Vector3(self.X / other, self.Y / other, self.Z / other)
        if isinstance(other, Vector3):
            return Vector3(self.X / other.X, self.Y / other.Y, self.Z / other.Z)
        raise TypeError("Vector3 can only be divided by Vector3 or a number")

    def __neg__(self):
        return Vector3(-self.X, -self.Y, -self.Z)

    # --- Vector math ---
    def Dot(self, other):
        return self.X * other.X + self.Y * other.Y + self.Z * other.Z

    def Cross(self, other):
        return Vector3(
            self.Y * other.Z - self.Z * other.Y,
            self.Z * other.X - self.X * other.Z,
            self.X * other.Y - self.Y * other.X,
        )

    def Magnitude(self):
        return math.sqrt(self.X**2 + self.Y**2 + self.Z**2)

    def Unit(self):
        m = self.Magnitude()
        return Vector3(self.X / m, self.Y / m, self.Z / m) if m != 0 else Vector3()

    def Lerp(self, other, alpha: float):
        return self + (other - self) * alpha

class CFrame:
    def __init__(self, position=None, right=None, up=None, look=None):
        self.Position = position or Vector3(0, 0, 0)

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

    @classmethod
    def new(cls, x=0, y=0, z=0):
        return cls(position=Vector3(x, y, z))

    # --- Rotation helpers ---
    def _rotate_vector(self, v: Vector3) -> Vector3:
        return (
            self.RightVector * v.X +
            self.UpVector * v.Y +
            self.LookVector * v.Z
        )

    def _inverse_rotate_vector(self, v: Vector3) -> Vector3:
        # Multiply by transpose of rotation matrix
        return Vector3(
            v.Dot(self.RightVector),
            v.Dot(self.UpVector),
            v.Dot(self.LookVector)
        )

    @staticmethod
    def _orthonormal_basis(right=None, up=None, look=None):
        def unit(v: Vector3 | None):
            return v.Unit() if isinstance(v, Vector3) else None

        def nearly_parallel(a: Vector3, b: Vector3) -> bool:
            ma, mb = a.Magnitude(), b.Magnitude()
            if ma == 0 or mb == 0:
                return True
            return abs(a.Dot(b) / (ma * mb)) > 0.9999

        def orthogonal_to(v: Vector3) -> Vector3:
            fallback = Vector3(0, 1, 0)
            if nearly_parallel(v, fallback):
                fallback = Vector3(1, 0, 0)
            return (fallback - v * fallback.Dot(v)).Unit()

        r = unit(right)
        u = unit(up)
        l = unit(look)

        if r is not None and u is not None:
            u = (u - r * u.Dot(r)).Unit()
            l = -r.Cross(u).Unit()
            return r, u, l
        
        if r is not None and l is not None:
            l = (l - r * l.Dot(r)).Unit()
            u = l.Cross(r).Unit()
            return r, u, l
        
        if u is not None and l is not None:
            l = (l - u * l.Dot(l)).Unit()
            r = l.Cross(u).Unit()
            return r, u, l
        
        if r is not None:
            u = orthogonal_to(r)
            l = -r.Cross(u).Unit()
            return r, u, l
        
        if u is not None:
            r = orthogonal_to(u)
            l = -r.Cross(u).Unit()
            return r, u, l
        
        if l is not None:
            u = orthogonal_to(l)
            r = l.Cross(u).Unit()
            return r, u, l

        return Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, -1)

    # --- Operators ---
    def __mul__(self, other):
        if isinstance(other, CFrame):
            rotated_pos = self._rotate_vector(other.Position)
            new_pos = self.Position + rotated_pos

            r = self._rotate_vector(other.RightVector)
            u = self._rotate_vector(other.UpVector)
            l = self._rotate_vector(other.LookVector)

            return CFrame(new_pos, r, u, l)

        if isinstance(other, Vector3):
            return self.Position + self._rotate_vector(other)

        raise TypeError("CFrame can only be multiplied by CFrame or Vector3")

    def __add__(self, other):
        if isinstance(other, Vector3):
            return CFrame(self.Position + other,
                          self.RightVector, self.UpVector, self.LookVector)
        raise TypeError("CFrame can only be added to Vector3")

    def __sub__(self, other):
        if isinstance(other, Vector3):
            return CFrame(self.Position - other,
                          self.RightVector, self.UpVector, self.LookVector)
        raise TypeError("CFrame can only be subtracted by Vector3")

    # --- API Methods ---
    def Inverse(self):
        # Rotation inverse is transpose
        r = Vector3(self.RightVector.X, self.UpVector.X, self.LookVector.X)
        u = Vector3(self.RightVector.Y, self.UpVector.Y, self.LookVector.Y)
        l = Vector3(self.RightVector.Z, self.UpVector.Z, self.LookVector.Z)

        inv_pos = Vector3(
            -self.Position.Dot(r),
            -self.Position.Dot(u),
            -self.Position.Dot(l),
        )

        return CFrame(inv_pos, r, u, l)

    def ToWorldSpace(self, cf):
        return self * cf

    def ToObjectSpace(self, cf):
        return self.Inverse() * cf

    def GetComponents(self):
        return tuple([
            self.RightVector.X, self.UpVector.X, self.LookVector.X,
            self.RightVector.Y, self.UpVector.Y, self.LookVector.Y,
            self.RightVector.Z, self.UpVector.Z, self.LookVector.Z,
            self.Position.X, self.Position.Y, self.Position.Z
        ])