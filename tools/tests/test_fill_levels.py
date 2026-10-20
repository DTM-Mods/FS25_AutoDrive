"""Loading: a truck counts as full although its own empty tank cannot take the product being loaded (the wood chip
tank of the crusher Tatra under a silo pouring alfalfa); tanks with something in them, trailers and dump bodies
that take the product still count."""
import os
import run_undo_test as t

s = t.make_runtime(True)
s.execute(t.read(os.path.join(t.MOD, "scripts", "Utils", "TrailerUtil.lua")))
s.execute("""
    FillType = {UNKNOWN = 0, ALFALFA = 1, WOODCHIPS = 2, DIESEL = 3}
    UNLOAD_LEVEL = 1          -- unload fill level setting: 100 %
    AutoDrive.getSetting = function(name) if name == "unloadFillLevel" then return UNLOAD_LEVEL end end
    AutoDrive.hasAL = function() return false end
    AutoDrive.debugPrint = function() end
    -- a unit: fill units {capacity, level, supported = {fillType = true}}, discharge nodes on the given units
    function unit(units, discharging)
        local u = {fillUnits = units}
        u.getFillUnits = function(self) return self.fillUnits end
        u.getFillUnitFillLevel = function(self, i) return self.fillUnits[i].level end
        u.getFillUnitCapacity = function(self, i) return self.fillUnits[i].capacity end
        u.getFillUnitFreeCapacity = function(self, i) return self.fillUnits[i].capacity - self.fillUnits[i].level end
        u.getFillUnitSupportsFillType = function(self, i, ft) return self.fillUnits[i].supported[ft] == true end
        local nodes = {}
        for _, i in ipairs(discharging) do table.insert(nodes, {fillUnitIndex = i}) end
        u.spec_dischargeable = {dischargeNodes = nodes}
        return u
    end
    SELECTED = {FillType.ALFALFA}
    TATRA = unit({{capacity = 470, level = 300, supported = {[3] = true}}, {capacity = 2000, level = 2000, supported = {}},
        {capacity = 500, level = 0, supported = {[2] = true}}}, {3})
    TRAILER = unit({{capacity = 86850, level = 86850, supported = {[1] = true}}}, {1})
    TATRA.getRootVehicle = function(self) return TATRA end
    TRAILER.getRootVehicle = function(self) return TATRA end
    TATRA.ad = {stateModule = {getSelectedFillTypes = function() return SELECTED end, getFillType = function() return SELECTED[1] end}}
    IMPLEMENTS = {TRAILER}
    AutoDrive.getAllImplements = function(v) return IMPLEMENTS end
""")
# the trailer is full of alfalfa: the truck counts as full (the empty wood chip tank does not count)
s.execute("LEVEL, CAP, FULL, FREE = AutoDrive.getAllFillLevels({TATRA, TRAILER})")
assert s.eval("FULL") is True and s.eval("FREE") == 0 and s.eval("CAP") == 86850, (s.eval("FULL"), s.eval("FREE"), s.eval("CAP"))
# not full yet: not full
s.execute("TRAILER.fillUnits[1].level = 60000; LEVEL, CAP, FULL, FREE = AutoDrive.getAllFillLevels({TATRA, TRAILER})")
assert s.eval("FULL") is False and s.eval("FREE") == 26850
s.execute("TRAILER.fillUnits[1].level = 86850")
# wood chips in the tank: it counts (unloading must still see them)
s.execute("TATRA.fillUnits[3].level = 120; LEVEL, CAP, FULL, FREE = AutoDrive.getAllFillLevels({TATRA, TRAILER})")
assert s.eval("LEVEL") == 86970 and s.eval("CAP") == 87350
s.execute("TATRA.fillUnits[3].level = 0")
# loading wood chips: the tank takes them, it counts
s.execute("SELECTED = {FillType.WOODCHIPS}; LEVEL, CAP, FULL, FREE = AutoDrive.getAllFillLevels({TATRA, TRAILER})")
assert s.eval("CAP") == 87350
s.execute("SELECTED = {FillType.ALFALFA}")
# a truck alone (no trailer): its own tanks count as before
s.execute("IMPLEMENTS = {}; LEVEL, CAP, FULL, FREE = AutoDrive.getAllFillLevels({TATRA})")
assert s.eval("CAP") == 500
s.execute("IMPLEMENTS = {TRAILER}")
# nothing selected: as before
s.execute("SELECTED = {}; TATRA.ad.stateModule.getFillType = function() return FillType.UNKNOWN end; LEVEL, CAP, FULL, FREE = AutoDrive.getAllFillLevels({TATRA, TRAILER})")
assert s.eval("CAP") == 87350
print("OK: loading: the truck's own empty tank that cannot take the product does not keep it from being full")
