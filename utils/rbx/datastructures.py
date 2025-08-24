class UDim2:
    def __init__(self, scaleX, offsetX, scaleY, offsetY):
        self.X = {
            ["Offset"]: offsetX,
            ["Scale"]: scaleX
        }

        self.Y = {
            ["Offset"]: offsetY,
            ["Scale"]: scaleY
        }

        self.Width = self.X
        self.Height = self.Y
    
    def __str__(self):
        return f"{{{self.X.Scale}, {self.X.Offset}}}, {{{self.Y.Scale}, {self.Y.Offset}}}"

    def fromScale(scaleX, scaleY):
        return UDim2(scaleX, 0, scaleY, 0)
    
    def fromOffset(offsetX, offsetY):
        return UDim2(0, offsetX, 0, offsetY)

class Vector3:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
    
    def __str__(self):
        return f"{self.x}, {self.y}, {self.z}"
    
    def __eq__(self, vector):
        if isinstance(vector, Vector3):
            return vector.x == self.x and vector.y == self.y and vector.z == self.y
