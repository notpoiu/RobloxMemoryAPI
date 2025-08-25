class UDim:
    def __init__(self, scale=0, offset=0):
        self.Scale = float(scale)
        self.Offset = int(offset)

    def __repr__(self):
        return f"UDim(Scale={self.Scale}, Offset={self.Offset})"


class UDim2:
    def __init__(self, scaleX=0, offsetX=0, scaleY=0, offsetY=0):
        self.X = UDim(scaleX, offsetX)
        self.Y = UDim(scaleY, offsetY)

    def __repr__(self):
        return f"UDim2({self.X.Scale}, {self.X.Offset}, {self.Y.Scale}, {self.Y.Offset})"

    @classmethod
    def fromScale(cls, scaleX, scaleY):
        return cls(scaleX, 0, scaleY, 0)

    @classmethod
    def fromOffset(cls, offsetX, offsetY):
        return cls(0, offsetX, 0, offsetY)


class Vector3:
    def __init__(self, x=0, y=0, z=0):
        self.X = float(x)
        self.Y = float(y)
        self.Z = float(z)

    def __repr__(self):
        return f"Vector3({self.X}, {self.Y}, {self.Z})"

    def __eq__(self, other):
        return (
            isinstance(other, Vector3)
            and self.X == other.X
            and self.Y == other.Y
            and self.Z == other.Z
        )


class CFrame:
    def __init__(self, position=None, right=None, up=None, look=None):
        self.Position = position or Vector3(0, 0, 0)
        self.RightVector = right or Vector3(1, 0, 0)
        self.UpVector = up or Vector3(0, 1, 0)
        self.LookVector = look or Vector3(0, 0, -1)

    def __repr__(self):
        return (
            f"CFrame(Position={self.Position}, "
            f"Right={self.RightVector}, Up={self.UpVector}, Look={self.LookVector})"
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