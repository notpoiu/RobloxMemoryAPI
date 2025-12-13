local fs = require("@lune/fs")
local luau = require("@lune/luau")

fs.writeFile("BytecodeToWrite.luac", luau.compile([[
print("Hello World! :D")

local function sum(...)
    local s = 0
    for i, v in {...} do
        s += v
    end
    return s
end
return sum(1, 2, 3, 4)]], {
    optimizationLevel = 2
}))
