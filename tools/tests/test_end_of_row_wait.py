"""End of row (od.58): a harvester's header up or off = end of the row. The runner stands where it is (stopVehicle, no
driving) until every header is lowered and on again, then chases again. Only after the header was seen working, not while
the harvester calls for an unload, at most MAX_TURN_TIME, not for forage harvesters or harvesters without a header."""
import os
import run_undo_test as t

s = t.make_runtime(True)
s.execute(t.read(os.path.join(t.MOD, "scripts", "Hud", "GenericHudElement.lua")))  # ADInheritsFrom
s.execute(t.read(os.path.join(t.MOD, "scripts", "Utils", "AutoDriveTON.lua")))
s.execute("AbstractTask = AbstractTask or ADInheritsFrom({})")
s.execute(t.read(os.path.join(t.MOD, "scripts", "Tasks", "FollowCombineTask.lua")))
s.execute("""
    LOG = {}
    Logging.info = function(f, ...) table.insert(LOG, string.format(f, ...)) end
    ADDiag = {name = function(v) return v.name or "?" end}
    CALLING = false
    AutoDrive.getIsCPWaitingForUnload = function() return CALLING end
    HEADER = {spec_cutter = {}, low = true, on = true}
    function HEADER:getIsLowered() return self.low end
    function HEADER:getIsTurnedOn() return self.on end
    ROOT = {name = "Combine", spec_combine = {}}
    function ROOT:getChildVehicles() return {self, HEADER} end
    function make(isChopper)
        STOPS = 0
        local v = {name = "Truck", ad = {specialDrivingModule = {stopVehicle = function() STOPS = STOPS + 1 end, update = function() end}}}
        return setmetatable({vehicle = v, combine = {name = "Combine", ad = {isHarvester = true, isChopper = isChopper}},
            combineRootVehicle = ROOT, combineFillPercent = 50, state = FollowCombineTask.STATE_CHASING}, {__index = FollowCombineTask})
    end
""")
def E(code):
    try:
        return s.eval(code)
    except Exception as e:
        if "Syntax" not in type(e).__name__:
            raise
        return s.execute(code)

def check(cond, msg):
    if not cond:
        raise AssertionError(msg)

# header up before it was ever seen working: no wait
E("HEADER.low = false; TK = make(false)")
check(not E("TK:updateEndOfRowWait(100)"), "waited before the header was seen working")
# harvesting, then header up -> stands, does not drive
E("HEADER.low = true")
check(not E("TK:updateEndOfRowWait(100)"), "waited while harvesting")
E("HEADER.low = false")
check(E("TK:updateEndOfRowWait(100)") and E("STOPS") == 1, "did not stop when the header went up")
E("TK.state = FollowCombineTask.STATE_WAIT_FOR_TURN")
for _ in range(20):
    check(E("TK:updateEndOfRowWait(100)"), "stopped waiting while the header was up")
# down but still off: keeps waiting
E("HEADER.low = true; HEADER.on = false")
check(E("TK:updateEndOfRowWait(100)"), "chased again with the header down but off")
# down and on: chases again, state back to chasing
E("HEADER.on = true")
check(not E("TK:updateEndOfRowWait(100)"), "kept waiting with the header down and on")
check(E("TK.state == FollowCombineTask.STATE_CHASING"), "state not back to chasing")
# calling for an unload: no wait
E("HEADER.low = false; CALLING = true")
check(not E("TK:updateEndOfRowWait(100)"), "waited while the harvester calls for an unload")
E("CALLING = false; TK.combineFillPercent = 99")
check(not E("TK:updateEndOfRowWait(100)"), "waited with a full harvester")
# time limit
E("TK.combineFillPercent = 50")
check(E("TK:updateEndOfRowWait(100)"), "no wait after a full harvester got lower")
check(not E("TK:updateEndOfRowWait(FollowCombineTask.MAX_TURN_TIME)"), "waited past MAX_TURN_TIME")
check(not E("TK:updateEndOfRowWait(100)"), "waited again without harvesting in between")
# forage harvester, harvester without a header: off
E("HEADER.low = true; TK = make(true); TK:updateEndOfRowWait(100); HEADER.low = false")
check(not E("TK:updateEndOfRowWait(100)"), "forage harvester waited")
E("ROOT.getChildVehicles = function(self) return {self} end; TK = make(false); TK:updateEndOfRowWait(100)")
check(not E("TK:updateEndOfRowWait(100)"), "waited without a header")
check(any("header up, standing here" in str(l) for l in E("LOG").values()), "start not logged")
print("OK: end of row (header up or off -> stand still, header down and on -> chase again; not before it harvested, "
      "not while calling for an unload or full, 60 s max, not forage harvesters or without a header; logged)")
