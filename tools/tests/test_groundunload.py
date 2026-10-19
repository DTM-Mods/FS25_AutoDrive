"""Tipping on the ground (bunker silo / heap): "stand still" stops while the load runs, moves on when nothing comes
out any more (heap full) and stops again when it runs; "drive through" and reversing stay as upstream."""
import os
import run_undo_test as t

s = t.make_runtime(True)
s.execute(t.read(os.path.join(t.MOD, "scripts", "Manager", "GroundUnload.lua")))
s.execute("""
    Logging = {info = function(...) LOGGED = string.format(select(1, ...), select(2, ...)) end}
    G = ADGroundUnload
    SETTING = G.STAND_STILL
    AutoDrive.getSetting = function(name, vehicle) if name == "groundUnload" then return SETTING end end
    REVERSING = false
    FILL = 10000
    AutoDrive.getAllFillLevels = function() return FILL end
    ACTIONS = {}
    V = {ad = {drivePathModule = {getIsReversing = function() return REVERSING end, update = function() table.insert(ACTIONS, "drive") end},
        specialDrivingModule = {stopVehicle = function() table.insert(ACTIONS, "stop") end, update = function() end}}}
    TASK = {vehicle = V, trailers = {}}
    function tick(litres, dt) FILL = FILL - litres; ACTIONS = {}; G.drive(TASK, dt or 100); return ACTIONS[1] end
""")
# the tipper body rises first: nothing comes out for a while, it still stands (up to 30 s)
for _ in range(299):
    assert s.eval("tick(0)") == "stop"
# the load runs: stand still
for _ in range(20):
    assert s.eval("tick(50)") == "stop"
# nothing comes out for 6 s after it ran (the heap is full): move on
for i in range(59):
    assert s.eval("tick(0)") == "stop", i
assert s.eval("tick(0)") == "drive"
assert s.eval("tick(0)") == "drive"
# it runs again at the next place: stand still again
assert s.eval("tick(80)") == "stop"
# a load that never runs (nothing to tip): moves on after 30 s
s.execute("FILL = 30000; V.ad.groundUnloadState = nil")
for _ in range(299):
    assert s.eval("tick(0)") == "stop"
assert s.eval("tick(0)") == "drive"
# a new load (fuller than before) starts fresh
s.execute("FILL = 40000; tick(0)")
assert s.eval("V.ad.groundUnloadState.stalled") <= 100
# reversing into a silo and "drive through" stay as upstream
s.execute("REVERSING = true")
assert s.eval("tick(50)") == "drive" and not s.eval("G.isStandStill(V)")
s.execute("REVERSING = false; SETTING = G.DRIVE_THROUGH")
assert s.eval("tick(50)") == "drive" and not s.eval("G.isStandStill(V)")
assert "tipping on the ground (bunker silo / heap), setting stand still" in s.eval("LOGGED")
print("OK: tipping on the ground (waits for the tipper body): stand still while it runs, move on when the heap is full, drive through / reversing unchanged")
