"""Taller pallet areas: switched off (HEIGHT_FACTOR 1: no trigger is touched, nothing logged). With a factor set, on the
server every pallet trigger of an unloading station is made that many times as tall, once, also for stations placed
later; other triggers are left alone; failures leave everything as it is; it is logged."""
import os
from lupa.lua55 import LuaRuntime

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read(*parts):
    return open(os.path.join(MOD, *parts), encoding="utf-8").read().replace("\r\n", "\n")


s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    LOG, WARN = {}, {}
    Logging = {info = function(f, ...) table.insert(LOG, string.format(f, ...)) end,
               warning = function(f, ...) table.insert(WARN, string.format(f, ...)) end}
    SCALE, PHYS = {}, {}
    function getScale(node) local s = SCALE[node] or {1, 1, 1}; return s[1], s[2], s[3] end
    function setScale(node, x, y, z) SCALE[node] = {x, y, z} end
    function removeFromPhysics(node) table.insert(PHYS, "out " .. node) end
    function addToPhysics(node) table.insert(PHYS, "in " .. node) end
    function entityExists(node) return node > 0 end
    function getName(node) return "trigger" .. node end
    PalletUnloadTrigger = {}
    local function trigger(class, node)
        local t = {triggerNode = node}
        function t:isa(c) return c == class end
        return t
    end
    function palletTrigger(node) return trigger(PalletUnloadTrigger, node) end
    function bulkTrigger(node) return trigger({}, node) end
    STATIONS = {
        {getName = function() return "Edeka" end, unloadTriggers = {bulkTrigger(1), palletTrigger(2)}},
        {getName = function() return "Factory" end, unloadTriggers = {{palletTrigger = palletTrigger(3)}}},
    }
    g_currentMission = {storageSystem = {getUnloadingStations = function() return STATIONS end}}
""")
s.execute(read("scripts", "Manager", "PalletAreas.lua"))

# off: factor 1 leaves every trigger as it is, not even taken out of physics, and says nothing
assert s.eval("ADPalletAreas.HEIGHT_FACTOR") == 1
s.execute("ADPalletAreas:update(16); ADPalletAreas:update(20000)")
assert s.eval("next(SCALE)") is None and s.eval("#PHYS") == 0 and s.eval("#LOG") == 0 and s.eval("next(ADPalletAreas.done)") is None

# the scaling itself, with a factor of 3
s.execute("ADPalletAreas.HEIGHT_FACTOR = 3; ADPalletAreas.timer = 0")

# first check: the two pallet triggers 3x as tall, taken out of and back into physics; the bulk trigger untouched
s.execute("ADPalletAreas:update(16)")
assert s.eval("SCALE[2][2]") == 3 and s.eval("SCALE[3][2]") == 3 and s.eval("SCALE[2][1]") == 1
assert s.eval("SCALE[1]") is None
assert list(s.eval("PHYS").values()) == ["out 2", "in 2", "out 3", "in 3"] or list(s.eval("PHYS").values()) == ["out 3", "in 3", "out 2", "in 2"]
assert any("Edeka, pallet trigger trigger2 made taller (height scale 1.00 -> 3.00)" in l for l in s.eval("LOG").values())
assert "2 pallet trigger(s) made 3 times as tall" in s.eval("LOG[#LOG]")
# not again within 10 s, and never twice for the same trigger
n = s.eval("#LOG")
s.execute("ADPalletAreas:update(5000)")
assert s.eval("#LOG") == n
s.execute("ADPalletAreas:update(5000)")
assert s.eval("SCALE[2][2]") == 3 and s.eval("#LOG") == n
# a station placed later is picked up at the next check
s.execute("table.insert(STATIONS, {getName = function() return 'New' end, unloadTriggers = {palletTrigger(4)}}); ADPalletAreas:update(10000)")
assert s.eval("SCALE[4][2]") == 3 and s.eval("SCALE[2][2]") == 3
# an error leaves everything as it is and stops trying
s.execute("table.insert(STATIONS, {unloadTriggers = {palletTrigger(5)}}); setScale = function() error('engine says no') end; ADPalletAreas:update(10000)")
assert s.eval("ADPalletAreas.failed") is True and "left as they are" in s.eval("WARN[1]")
s.execute("ADPalletAreas:update(10000)")
assert s.eval("#WARN") == 1

# no pallet triggers at all: what the stations have is reported once
s.execute("""
    ADPalletAreas.failed = nil; ADPalletAreas.done = {}; ADPalletAreas.timer = 0; LOG = {}
    STATIONS = {{getName = function() return 'Shop' end, unloadTriggers = {bulkTrigger(9)}}}
    ADPalletAreas:update(16)
""")
assert any("no pallet trigger found; Shop" in l for l in s.eval("LOG").values())

# wiring: server update, sourced
ad = read("scripts", "AutoDrive.lua")
server = ad[ad.index("if g_server ~= nil then\n\t\tADHarvestManager:update(dt)"):]
server = server[:server.index("\tend\n")]
assert "ADPalletAreas:update(dt)" in server
assert read("register.lua").count("scripts/Manager/PalletAreas.lua") == 1

print("OK: taller pallet areas off (factor 1: triggers untouched, nothing logged); with a factor (only pallet triggers, 3x height, out of and back into physics, once each, stations "
      "placed later, every 10 s, failure leaves them as they are, report when none found, server update, logged)")
