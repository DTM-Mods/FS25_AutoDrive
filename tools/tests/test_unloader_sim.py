"""od.56 driving simulation: unloader beside a moving harvester (Active unloading, pipe lock).

Loads the REAL FollowCombineTask, ADSpecialDrivingModule (driveToPoint, driveReverse with the front guard,
limitTrailerSteering) and ADUnloaderClear from scripts/. Mocked: the game API, the harvester's motion (drives forward,
turns at a given rate), a truck (bicycle model, acceleration and steering limits) with an articulated trailer.

Checks, per scenario:
  * gap: the smallest gap between the harvester's outline and the truck or trailer (never touches; keep-out)
  * front: no reversing step while any corner of the truck or trailer is in the area in front of the harvester
  * pipe: it ends up on the pipe side, under the pipe (where the scenario expects that)

usage: python tools/tests/test_unloader_sim.py [-v]
"""
import math
import os
import sys

import lupa.lua51 as L

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.normpath(os.path.join(HERE, "..", ".."))
VERBOSE = "-v" in sys.argv


def read(*p):
    with open(os.path.join(MOD, *p), encoding="utf-8") as f:
        return f.read()


HARNESS = r"""
LOG = {}
Logging = {info = function(f, ...) table.insert(LOG, string.format(f, ...)) end,
           error = function(f, ...) table.insert(LOG, "ERROR " .. string.format(f, ...)) end, warning = function() end}
MathUtil = {vector2Length = function(x, z) return math.sqrt(x * x + z * z) end}
g_server = {}; g_time = 0; g_updateLoopIndex = 0
g_currentMission = {nodeToObject = setmetatable({}, {__index = function() return true end})}
Dischargeable = {DISCHARGE_STATE_OFF = 0, DISCHARGE_STATE_OBJECT = 1, DISCHARGE_STATE_GROUND = 2}
ADDiag = {name = function(v) return v and v.name or "?" end}
AutoDrive = {PERF_FRAMES = 20, MODE_UNLOAD = 1, CHASEPOS_UNKNOWN = 0, CHASEPOS_LEFT = 1, CHASEPOS_RIGHT = -1,
  CHASEPOS_REAR = 3, CHASEPOS_FRONT = 4, DC_VEHICLEINFO = 1, DC_PATHINFO = 2}
AutoDrive.debugPrint = function() end

local function fwd(o) return math.sin(o.h), math.cos(o.h) end
local function left(o) return math.cos(o.h), -math.sin(o.h) end
function toLocal(o, x, z)
  local dx, dz = x - o.x, z - o.z; local fx, fz = fwd(o); local lx, lz = left(o)
  return dx * lx + dz * lz, dx * fx + dz * fz
end
function toWorld(o, a, b)
  local fx, fz = fwd(o); local lx, lz = left(o)
  return o.x + a * lx + b * fx, o.z + a * lz + b * fz
end
function getWorldTranslation(node) local o = node.obj; return o.x, 0, o.z end
function worldToLocal(node, x, y, z) local a, b = toLocal(node.obj, x, z); return a, y, b end
function localToWorld(node, x, y, z) local a, b = toWorld(node.obj, x, z); return a, y, b end
function localDirectionToWorld(node, x, y, z)
  local o = node.obj; local fx, fz = fwd(o); local lx, lz = left(o)
  return x * lx + z * fx, y, x * lz + z * fz
end
AutoDrive.worldToLocal = function(v, x, y, z, node) return worldToLocal(node or v.components[1].node, x, y, z) end
AutoDrive.localToWorld = function(v, x, y, z, node) return localToWorld(node or v.components[1].node, x, y, z) end
AutoDrive.localDirectionToWorld = function(v, x, y, z, node) return localDirectionToWorld(node or v.components[1].node, x, y, z) end
AutoDrive.angleBetween = function(a, b) return math.deg(math.atan2(a.x * b.z - a.z * b.x, a.x * b.x + a.z * b.z)) end
AutoDrive.sign = function(x) if x > 0 then return 1 elseif x < 0 then return -1 end return 0 end
AutoDrive.getDistanceBetween = function(a, b) return MathUtil.vector2Length(a.x - b.x, a.z - b.z) end
AutoDrive.combineIsTurning = function(c) return c.turnFlag == true end
function AutoDrive:getIsCPTurning() return false end
function AutoDrive:getIsCPActive() return false end
function AutoDrive:holdCPCombine() end
AutoDrive.getSetting = function(name) if name == "activeUnloading" then return true end return nil end
AutoDrive.getAllUnits = function(v) return {v, v.trailer}, 2 end
AutoDrive.getObjectFillLevels = function(c) return c.fill, 100, nil, 100 - c.fill end
AutoDrive.getAllFillLevels = function(t) return 50, 100, false, 50 end
AutoDrive.setTrailerCoverOpen = function() end
AutoDrive.getDischargeNode = function(c) return nil end
AutoDrive.getHarvesterHalfSize = function(c) return c.size.width / 2, c.size.length / 2 end
AutoDrive.getPipeSide = function(c) return c.pipeSide end
AutoDrive.getSidewaysHarvester = function() return nil end
AutoDrive.getDriveDirection = function(v, x, y, z)
  local a, b = toLocal(v, x, z); local l = math.sqrt(a * a + b * b)
  if l < 1e-6 then return 0, 1 end
  return a / l, b / l
end
AutoDrive.driveInDirection = function(v, dt, steerLimit, acc, slowAcc, slowAngle, allowed, forwards, lx, lz, speed)
  if forwards == false then
    W.cmd = {kind = "rev", speed = speed}
  else
    W.cmd = {kind = "dir", lx = lx, lz = lz, speed = speed}
  end
end

function ADInheritsFrom(base)
  local c = {}; local mt = {__index = c}
  function c:create() return setmetatable({}, mt) end
  if base then setmetatable(c, {__index = base}) end
  return c
end
AbstractTask = {}
"""

WORLD = r"""
FollowCombineTask.debugMsg = function() end
CatchCombinePipeTask.debugMsg = function() end
CatchCombinePipeTask.isActiveMoving = CatchCombinePipeTask.isActiveMoving or function() return true end

local function fwd(o) return math.sin(o.h), math.cos(o.h) end

local function newObj(name, x, z, h, w, l)
  local o = {name = name, x = x, z = z, h = h, size = {width = w, length = l}, lastSpeedReal = 0, ad = {}}
  o.components = {{node = {obj = o}}}
  o.ad.ADRootNode = o.components[1].node
  return o
end

W = {}

local function placeTrailerFromHitch()
  local t, tr = W.truck, W.trailer
  local fx, fz = fwd(t)
  local hx, hz = t.x - fx * (t.size.length / 2 - 1), t.z - fz * (t.size.length / 2 - 1)
  local gx, gz = fwd(tr)
  tr.x, tr.z = hx - gx * tr.size.length / 2, hz - gz * tr.size.length / 2
end

function setupWorld(sc)
  local comb = newObj("harvester", 0, 0, 0, sc.combW or 3.8, sc.combL or 11)
  comb.ad.isHarvester = true; comb.ad.isChopper = false
  comb.ad.noMovementTimer = {elapsedTime = 0}; comb.ad.driveForwardTimer = {elapsedTime = 100000}
  comb.fill = 50; comb.turnFlag = false; comb.movingDirection = 1
  comb.pipeSide = sc.pipeSide or 1
  comb.getRootVehicle = function(self) return self end
  comb.getDischargeState = function() return Dischargeable.DISCHARGE_STATE_OBJECT end
  comb.ad.sensors = {frontSensorFruit = {pollInfo = function() return true end}}
  comb.fx, comb.fz = 0, comb.size.length / 2

  local side = comb.pipeSide
  local truck = newObj("truck", 0, 0, 0, 2.6, 7)
  local trailer = newObj("trailer", 0, 0, 0, 2.6, 12)
  truck.trailer = trailer
  truck.getAttachedImplements = function() return {{object = trailer}} end
  local sideOffset = sc.sideOffset or 7.8
  truck.x, truck.z = toWorld(comb, sc.startX, sc.startZ)
  truck.h = comb.h + math.rad(sc.startH or 0)
  trailer.h = truck.h
  local mode = {
    tractorTrainLength = 20,
    getPipeChasePosition = function(self)
      local x, z = toWorld(comb, side * sideOffset, sc.chaseZ or 4); return {x = x, y = 0, z = z}, side
    end,
    getAngleToCombineHeading = function()
      local a = math.abs(math.deg(truck.h - comb.h)) % 360; if a > 180 then a = 360 - a end; return a
    end,
    getAngleToCombine = function()
      local lx, lz = toLocal(truck, comb.x, comb.z); return math.abs(math.deg(math.atan2(lx, lz)))
    end,
    isUnloaderOnCorrectSide = function() return true end,
    getUnloaderOnSide = function(self)
      local dx, dz = toLocal(comb, truck.x, truck.z)
      local lr = AutoDrive.CHASEPOS_UNKNOWN
      if math.abs(dx) > comb.size.width / 2 then lr = AutoDrive.sign(dx) end
      return lr, AutoDrive.CHASEPOS_REAR
    end,
  }
  mode.combine = comb
  truck.ad.modes = {[1] = mode}
  truck.ad.stateModule = {getFieldSpeedLimit = function() return sc.fieldLimit or 40 end, getMode = function() return 1 end}
  truck.ad.trailerModule = {canBeHandledInReverse = function() return false end, handleTrailerReversing = function() end}
  truck.ad.taskModule = {setCurrentTaskFinished = function() W.finished = true end}
  truck.ad.collisionDetectionModule = {hasDetectedObstable = function() return false end,
    checkReverseCollision = function() return false end}
  truck.ad.sensors = {frontSensor = {pollInfo = function() return false end}}
  -- REAL driving module (driveToPoint, driveReverse incl. the front guard), stop/hold outputs captured
  local sdm = setmetatable({vehicle = truck, stoppedTimer = AutoDriveTON:new()}, {__index = ADSpecialDrivingModule})
  sdm.stopVehicle = function(self) W.cmd = {kind = "stop"}; self.isBlocked = false end
  sdm.stopAndHoldVehicle = function(self) W.cmd = {kind = "stop"} end
  sdm.update = function() end
  sdm.releaseVehicle = function(self) self.isBlocked = false; self.stoppedTimer:timer(false) end
  sdm.shouldStopMotor = function() return false end
  truck.ad.specialDrivingModule = sdm
  truck.speed = (sc.startSpeed or sc.combSpeed(0)) / 3.6
  truck.steer = 0
  W.comb, W.truck, W.trailer, W.mode = comb, truck, trailer, mode
  W.cmd = {kind = "stop"}
  placeTrailerFromHitch()
end

local WHEELBASE, MAX_STEER, STEER_RATE, ACC, BRAKE = 4.6, math.rad(35), math.rad(40), 1.5, 3.5
local function stepTruck(dt)
  local t, tr, cmd = W.truck, W.trailer, W.cmd
  local s = dt / 1000
  local target, wantSteer = 0, t.steer
  if cmd.kind == "dir" then
    target = math.max(0, cmd.speed or 0) / 3.6
    wantSteer = math.max(-MAX_STEER, math.min(MAX_STEER, math.atan2(cmd.lx, cmd.lz) * 1.2))
  elseif cmd.kind == "rev" then
    target = -(cmd.speed or 3) / 3.6
    wantSteer = 0
  end
  local dv = target - t.speed
  local lim = (dv * t.speed > 0) and ACC or BRAKE
  t.speed = t.speed + math.max(-lim * s, math.min(lim * s, dv))
  local ds = math.max(-STEER_RATE * s, math.min(STEER_RATE * s, wantSteer - t.steer))
  t.steer = t.steer + ds
  local v = t.speed
  t.h = t.h + v / WHEELBASE * math.tan(t.steer) * s
  local fx, fz = fwd(t)
  t.x, t.z = t.x + fx * v * s, t.z + fz * v * s
  t.lastSpeedReal = math.abs(v) / 1000
  t.lastSignedSpeed = v / 1000
  tr.h = tr.h + v / tr.size.length * math.sin(t.h - tr.h) * s
  placeTrailerFromHitch()
end

local function stepCombine(sc, tms, dt)
  local c = W.comb
  local speed = sc.combSpeed(tms) / 3.6
  c.h = c.h + math.rad(sc.combRate(tms)) * dt / 1000
  local fx, fz = fwd(c)
  c.fx, c.fz = c.fx + fx * speed * dt / 1000, c.fz + fz * speed * dt / 1000
  c.x, c.z = c.fx - fx * c.size.length / 2, c.fz - fz * c.size.length / 2
  c.lastSpeedReal = speed / 1000
  c.turnFlag = sc.turnFlag(tms)
end

function boxGap(a, b)
  local best = math.huge
  for _, pair in ipairs({{a, b}, {b, a}}) do
    local p, q = pair[1], pair[2]
    for _, sx in ipairs({-1, -0.5, 0, 0.5, 1}) do for _, sz in ipairs({-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1}) do
      if math.abs(sx) == 1 or math.abs(sz) == 1 then
        local wx, wz = toWorld(p, sx * p.size.width / 2, sz * p.size.length / 2)
        local lx, lz = toLocal(q, wx, wz)
        local gx, gz = math.abs(lx) - q.size.width / 2, math.abs(lz) - q.size.length / 2
        local g = (gx < 0 and gz < 0) and math.max(gx, gz) or math.sqrt(math.max(gx, 0) ^ 2 + math.max(gz, 0) ^ 2)
        if g < best then best = g end
      end
    end end
  end
  return best
end

local function anyCornerInFront()
  for _, u in ipairs({W.truck, W.trailer}) do
    for _, c in ipairs({{-1, -1}, {1, -1}, {-1, 1}, {1, 1}}) do
      local x, z = toWorld(u, c[1] * u.size.width / 2, c[2] * u.size.length / 2)
      if ADUnloaderClear.isInFront(W.comb, x, z) then return true end
    end
  end
  return false
end

function runScenario(sc)
  LOG = {}; W = {}; W.finished = false
  setupWorld(sc)
  local task = FollowCombineTask:new(W.truck, W.comb)
  task:setUp()
  local dt = 50
  local r = {rev = 0, minGap = math.huge, arrived = nil, revInFront = 0, inFront = 0, sideAtEnd = 0, lastPipe = 0,
             holds = 0, wrongBesideTime = 0, log = LOG, track = {}}
  for tms = 0, sc.duration, dt do
    g_time = tms; g_updateLoopIndex = g_updateLoopIndex + 1
    stepCombine(sc, tms, dt)
    if not W.finished then task:update(dt) end
    local before = anyCornerInFront()
    if W.cmd.kind == "rev" then
      r.rev = r.rev + 1
    end
    stepTruck(dt)
    if W.cmd.kind == "rev" and anyCornerInFront() and not before then r.revInFront = r.revInFront + 1 end
    if W.truck.ad.specialDrivingModule.frontHold then r.holds = r.holds + 1 end
    if anyCornerInFront() then r.inFront = r.inFront + 1 end
    local g = math.min(boxGap(W.comb, W.truck), boxGap(W.comb, W.trailer))
    if g < r.minGap then r.minGap = g; r.minGapAt = tms end
    local cp = W.mode:getPipeChasePosition()
    local pd = MathUtil.vector2Length(W.truck.x - cp.x, W.truck.z - cp.z)
    r.lastPipe = pd
    if not r.arrived and pd < 2 then r.arrived = tms end
    local tx, tz = toLocal(W.comb, W.truck.x, W.truck.z)
    r.sideAtEnd = tx
    if tms % 1000 == 0 then table.insert(r.track, string.format("%5.1fs x=%6.1f z=%6.1f gap=%5.2f %s", tms / 1000, tx, tz, g, W.cmd.kind)) end
  end
  r.finished = W.finished
  return r
end
"""


def build():
    lua = L.LuaRuntime(unpack_returned_tuples=True)
    lua.execute(HARNESS)
    for p in (("scripts", "Utils", "AutoDriveTON.lua"), ("scripts", "Tasks", "CatchCombinePipeTask.lua"),
              ("scripts", "Tasks", "FollowCombineTask.lua"), ("scripts", "Modules", "SpecialDrivingModule.lua"),
              ("scripts", "Manager", "UnloaderClear.lua")):
        lua.execute(read(*p))
    lua.execute(WORLD)
    return lua


lua = build()
run = lua.globals().runScenario

fails = 0


def check(name, cond, detail=""):
    global fails
    print(("ok   " if cond else "FAIL ") + name + ("  (" + detail + ")" if detail else ""))
    if not cond:
        fails += 1


def scenario(**kw):
    sc = {"duration": 60000, "startX": 7.8, "startZ": -30, "startH": 0, "pipeSide": 1}
    sc.update(kw)
    speed = sc.pop("speed", 8)
    rate = sc.pop("rate", None) or (lambda t: 0)
    turn = sc.pop("turn", None) or (lambda t: False)
    sc["combSpeed"] = sc.get("combSpeed") or (lambda t: speed)
    sc["combRate"] = rate
    sc["turnFlag"] = turn
    return lua.table_from(sc)


def show(r):
    if VERBOSE:
        for line in r.track.values():
            print("     ", line)
        for line in r.log.values():
            print("      log:", line)


def res(r):
    return "min gap %.2f m at %.1f s, reversed %d steps, reversed-in-front %d, front-holds %d, end x %.1f, pipe %.1f m" % (
        r.minGap, (r.minGapAt or 0) / 1000, r.rev, r.revInFront, r.holds, r.sideAtEnd, r.lastPipe)


# 1. straight, starts behind on the pipe side
r = run(scenario(startX=7.8, startZ=-30)); show(r)
check("1 behind on pipe side: reaches the pipe", r.arrived is not None and r.lastPipe < 2, res(r))
check("1 never closer than 0.5 m", r.minGap >= 0.5, res(r))

# 2. starts behind, on the WRONG side (lazy-arc case)
r = run(scenario(startX=-7.8, startZ=-30)); show(r)
check("2 behind on wrong side: ends under the pipe on the pipe side", r.lastPipe < 2 and r.sideAtEnd > 0, res(r))
check("2 never touches (gap >= 0.5 m)", r.minGap >= 0.5, res(r))
check("2 logs lining up on the pipe side", any("lining up on its pipe side" in l for l in r.log.values()), "")

# 3. starts BESIDE on the wrong side (right), at the harvester's speed
r = run(scenario(startX=-6.5, startZ=0, startSpeed=8, duration=90000)); show(r)
check("3 beside on the wrong side: never touches", r.minGap >= 0.5, res(r))
check("3 ... stops and lets it pass, then comes up the pipe side", r.lastPipe < 2 and r.sideAtEnd > 0, res(r))
check("3 logs stopping to let it pass", any("stopping to let it pass" in l for l in r.log.values()), "")

# 4. a chase spot too close to the harvester (short pipe / bad sizes): keep-out floor holds
r = run(scenario(startX=3.6, startZ=-30, sideOffset=3.0)); show(r)
check("4 chase spot inside touching distance: still never touches", r.minGap >= 0.3, res(r))

# 5. harvester veers toward the truck's side (turn flag, 6 deg/s for 6 s): prediction pulls inward, keep-out holds
r = run(scenario(startX=7.8, startZ=4, startSpeed=8, rate=lambda t: 6 if 20000 < t < 26000 else 0,
                 turn=lambda t: 20000 < t < 26000)); show(r)
check("5 veer toward the truck: never touches", r.minGap >= 0.3, res(r))

# 6. truck drifting in (starts 0.6 m from the harvester's side): steers away
r = run(scenario(startX=4.3, startZ=4, startSpeed=8, sideOffset=4.5)); show(r)
check("6 starts too close beside it: moves out, never touches", r.minGap >= 0.2, res(r))
check("6 ... and ends at least the keep-out lane out", abs(r.sideAtEnd) >= 4.2 - 0.3, res(r))

# 7. end of row, U-turn TOWARD the truck (inside of the turn), tight: backs off, but never reverses in front of it
# a Courseplay headland U-turn: 5 km/h, radius 8 m (10 deg/s for 18 s)
uturn = lambda t: 10 if 15000 < t < 33000 else 0
r = run(scenario(startX=7.8, startZ=4, startSpeed=8, speed=5, rate=uturn, turn=lambda t: 15000 < t < 34000,
                 duration=60000)); show(r)
check("7 U-turn toward it: no reversing step with any corner in front of the harvester", r.revInFront == 0, res(r))

# 8. end of row, U-turn AWAY from the truck (outside of the turn)
r = run(scenario(startX=7.8, startZ=4, startSpeed=8, speed=5, rate=lambda t: -10 if 15000 < t < 33000 else 0,
                 turn=lambda t: 15000 < t < 34000, duration=60000)); show(r)
check("8 U-turn away: no reversing in front of it", r.revInFront == 0, res(r))
check("8 never touches", r.minGap > 0, res(r))

# 13. the photo: STANDING harvester ("needs to be unloaded"), truck comes up from behind at an angle on the pipe side
for sx, sz, sh in ((3, -25, 20), (0, -22, 0), (10, -20, -25), (-4, -25, 30)):
    r = run(scenario(startX=sx, startZ=sz, startH=sh, startSpeed=10, speed=0, duration=40000)); show(r)
    check("13 standing, from (%g, %g) at %g deg: never touches" % (sx, sz, sh), r.minGap >= 0.5, res(r))
    check("13 ... ends at the pipe (the 3 m at-the-pipe rule)", r.lastPipe < 3, res(r))

# 9. pipe on the RIGHT side (mirror of 2)
r = run(scenario(pipeSide=-1, startX=7.8, startZ=-30)); show(r)
check("9 pipe on the right, starts behind-left: ends under the pipe on the right", r.lastPipe < 2 and r.sideAtEnd < 0, res(r))
check("9 never touches", r.minGap >= 0.5, res(r))

# 10. long straight chase at 12 km/h with a slow lane change: stays under the pipe, never touches
r = run(scenario(startX=7.8, startZ=4, startSpeed=12, speed=12, rate=lambda t: 3 if 20000 < t < 24000 else (-3 if 24000 < t < 28000 else 0),
                 duration=60000)); show(r)
check("10 lane change: under the pipe at the end", r.lastPipe < 2, res(r))
check("10 never touches", r.minGap >= 0.5, res(r))

# 11. front guard directly: truck standing in front of a standing harvester, something asks it to reverse
lua.execute("""
  setupWorld({startX = 0, startZ = 20, startH = 0, pipeSide = 1, combSpeed = function() return 0 end})
  W.truck.speed = 0
  local sdm = W.truck.ad.specialDrivingModule
  LOG = {}
  sdm:driveReverse(50, 10, 1, false)
  G1 = W.cmd.kind
  W.truck.x, W.truck.z = toWorld(W.comb, 0, -40)   -- behind it: reversing is fine there
  W.trailer.x, W.trailer.z = toWorld(W.comb, 0, -50)
  sdm:driveReverse(50, 10, 1, false)
  G2 = W.cmd.kind
  G3 = #LOG
""")
g = lua.globals()
check("11 in front of the harvester: driveReverse stops and holds", g.G1 == "stop", str(g.G1))
check("11 behind it: driveReverse reverses", g.G2 == "rev", str(g.G2))
check("11 logs the hold and the release", g.G3 == 2, str(g.G3))

# 12. not in unload-combine mode: the guard is off
lua.execute("""
  setupWorld({startX = 0, startZ = 20, startH = 0, pipeSide = 1, combSpeed = function() return 0 end})
  W.truck.ad.stateModule.getMode = function() return 5 end
  W.truck.ad.specialDrivingModule:driveReverse(50, 10, 1, false)
  G4 = W.cmd.kind
""")
check("12 other modes: reverse as before", g.G4 == "rev", str(g.G4))

# 14. SWEEP: both pipe sides x U-turn toward / away x radius 8..20 m x start beside / behind / behind on the wrong side.
# Counts: contact (gap < 0), reversing into the front, back at the pipe 90 s after the turn (a semi has to turn round).
sweep = {"runs": 0, "contact": [], "revFront": [], "lost": []}
for pipe in (1, -1):
    for turn_dir in (1, -1):
        for deg in (4, 5, 6, 8, 10):
            dur = 180 / deg * 1000
            for name, sx, sz, sp in (("beside", 7.8, 4, 8), ("behind", 7.8, -30, 8), ("behind-wrong", -7.8, -30, 8)):
                r = run(scenario(pipeSide=pipe, startX=sx * pipe, startZ=sz, startSpeed=sp, speed=5,
                                 rate=lambda t, d=deg * turn_dir, u=dur: d if 15000 < t < 15000 + u else 0,
                                 turn=lambda t, u=dur: 15000 < t < 16000 + u, duration=15000 + dur + 90000))
                sweep["runs"] += 1
                tag = "pipe %s, turn %s, %d deg/s (r %.0f m), %s" % ("L" if pipe > 0 else "R",
                    "toward" if turn_dir * pipe > 0 else "away", deg, (5 / 3.6) / math.radians(deg), name)
                if r.minGap < 0:
                    sweep["contact"].append("%s: gap %.2f at %.1f s" % (tag, r.minGap, (r.minGapAt or 0) / 1000))
                if r.revInFront > 0:
                    sweep["revFront"].append(tag)
                if r.lastPipe > 3:
                    sweep["lost"].append("%s: %.0f m from the pipe at the end" % (tag, r.lastPipe))
print("     sweep: %d runs" % sweep["runs"])
for k in ("contact", "revFront", "lost"):
    for line in sweep[k]:
        print("       %s: %s" % (k, line))
check("14 sweep: no contact in any run", not sweep["contact"], "%d of %d" % (len(sweep["contact"]), sweep["runs"]))
check("14 sweep: never reverses into the front", not sweep["revFront"], "%d" % len(sweep["revFront"]))
check("14 sweep: back under the pipe 90 s after every turn", not sweep["lost"], "%d" % len(sweep["lost"]))

print("ALL OK" if fails == 0 else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
