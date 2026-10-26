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
    AutoDrive.getSetting = function(name, vehicle) if name == "whileTipping" then return SETTING end end
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

# --- a silo pit, truck + trailer: with "stand still" no rolling on while a unit is open and the load goes down
s.execute("""
    SETTING = G.STAND_STILL; REVERSING = false
    Dischargeable = {DISCHARGE_STATE_OFF = 0, DISCHARGE_STATE_OBJECT = 1}
    TRUCK_STATE, TRAILER_STATE = 0, 0
    PIT = {vehicle = V, trailers = {{getDischargeState = function() return TRUCK_STATE end}, {getDischargeState = function() return TRAILER_STATE end}}}
    FILL = 50000
    function pit(litres, dt) FILL = FILL - litres; return G.isStillTipping(PIT, dt or 100) end
""")
assert not s.eval("pit(0)")                       # closed, nothing runs: drive on (to the pit)
s.execute("TRAILER_STATE = 1")                    # the trailer opens (AutoDrive may follow the truck only)
assert s.eval("pit(40)") and s.eval("pit(40)")    # grain runs: hold
for _ in range(14):
    assert s.eval("pit(0)")                        # a short gap in the flow: still hold
assert not s.eval("pit(0)")                       # nothing for 1.5 s: drive on (bring the next unit over the pit)
assert s.eval("pit(30)")                          # runs again: hold
s.execute("TRAILER_STATE = 0")
assert not s.eval("pit(30)")                      # closed: not tipping
s.execute("TRAILER_STATE = 1; SETTING = G.DRIVE_THROUGH")
assert not s.eval("pit(30)")                      # "drive through": as before

# --- holding while it tips: standing with "stand still" = no throttle, full brake and handbrake (not AutoDrive's
# 0.0001 throttle, which let a loaded truck in drive creep); while still rolling, or with "drive through", as before
s.execute("""
    PHYSICS = nil; SDM_UPDATES = 0
    H = {lastSpeedReal = 0, raiseActive = function() end,
        updateVehiclePhysics = function(self, forward, side, handbrake, dt) PHYSICS = {forward, side, handbrake} end,
        ad = {drivePathModule = {getIsReversing = function() return false end},
            specialDrivingModule = {stopVehicle = function() end, update = function() SDM_UPDATES = SDM_UPDATES + 1 end}}}
    SETTING = G.STAND_STILL
    BRAKES = {}
    TRAILER = {brake = function(self, pedal) BRAKES.trailer = pedal end}
    H.brake = function(self, pedal) BRAKES.truck = pedal end
    AutoDrive.getAllImplements = function(v, include) return {TRAILER, v} end
    g_time = 1000
    G.hold(H, 16)
""")
# full brake on the truck and the trailer while held
assert s.eval("BRAKES.truck") == 1 and s.eval("BRAKES.trailer") == 1 and s.eval("G.held[H]")
# still held a moment later: the brakes stay on
s.execute("g_time = 1200; G:update(16)")
assert s.eval("BRAKES.truck") == 1 and s.eval("G.held[H]")
# the hold ended (tipping done / empty / trigger full): all brakes released
s.execute("g_time = 1400; G:update(16)")
assert s.eval("BRAKES.truck") == 0 and s.eval("BRAKES.trailer") == 0 and s.eval("G.held[H]") is None
s.execute("G.hold(H, 16)")
assert list(s.eval("PHYSICS").values()) == [0, 0, True] and s.eval("SDM_UPDATES") == 0
assert s.eval("H.ad.specialDrivingModule.motorShouldNotBeStopped") is True
s.execute("PHYSICS = nil; H.lastSpeedReal = 3 / 3600; G.hold(H, 16)")      # still rolling at 3 km/h: brake down as before
assert s.eval("PHYSICS") is None and s.eval("SDM_UPDATES") == 1
s.execute("PHYSICS = nil; H.lastSpeedReal = 0; SETTING = G.DRIVE_THROUGH; H.ad.specialDrivingModule.motorShouldNotBeStopped = nil; G.hold(H, 16)")
assert s.eval("PHYSICS") is None and s.eval("SDM_UPDATES") == 2 and s.eval("H.ad.specialDrivingModule.motorShouldNotBeStopped") is None

# --- AutoDrive's "stuck in silo bunker" rescue waits only while stand still really waits: a loading wagon that
# "started" tipping next to its target with nothing coming out stood there for good when the rescue was always off
s.execute("""
    SETTING = G.STAND_STILL; REVERSING = false
    W = {ad = {drivePathModule = {getIsReversing = function() return false end, update = function() end},
        specialDrivingModule = {stopVehicle = function() end, update = function() end}}}
    WFILL = 20000
    function wait(litres, dt) WFILL = WFILL - litres; G.shouldStop(W, WFILL, dt or 100); return G.isHoldingForFlow(W) end
""")
assert s.eval("G.isHoldingForFlow(W)")            # just started: the body rises, no rescue
for _ in range(299):
    assert s.eval("wait(0)")                       # waiting for the load to run (30 s)
assert not s.eval("wait(0)")                      # nothing came out in 30 s: the rescue may end it
s.execute("W.ad.groundUnloadState = nil")
assert s.eval("wait(0)") and s.eval("wait(40)")   # runs: hold, no rescue
for _ in range(59):
    assert s.eval("wait(0)")
assert not s.eval("wait(0)")                      # ran, then nothing for 6 s: the rescue may end it
s.execute("SETTING = G.DRIVE_THROUGH")
assert not s.eval("G.isHoldingForFlow(W)")        # drive through: the rescue as always
s.execute("SETTING = G.STAND_STILL")

# --- the setting: stand still is the default, saved under the new name (old "groundUnload" values are not read)
settings = t.read(os.path.join(t.MOD, "scripts", "Settings.lua"))
block = settings.replace(chr(13) + chr(10), chr(10))
block = block[block.index("AutoDrive.settings.whileTipping = {"):]
block = block[:block.index(chr(10) + "}") + 2]
assert "default = 2," in block and "values = {1, 2}," in block and "isVehicleSpecific = true" in block
assert "AutoDrive.settings.groundUnload" not in settings
assert 'name="whileTipping"' in t.read(os.path.join(t.MOD, "gui", "overdriveSettingsPage.xml"))
assert s.eval("G.STAND_STILL") == 2

print("OK: while tipping (default stand still; bunker rescue works once nothing comes out; hard hold: no throttle, handbrake, full brake on truck and trailer, released after; silo pit / truck + trailer hold while the load runs; ground: waits for the tipper body): stand still while it runs, move on when the heap is full, drive through / reversing unchanged")
