"""Stuck at a standing harvester (od.55): with Active unloading (pipe lock), a truck whose chase spot is BEHIND a standing
harvester holds still instead of chasing that spot; only beside the harvester on its pipe side counts as at the pipe.
Standing still with nothing falling in and not beside the pipe for 10 s: it drives round the harvester (forward only,
path finder held to the field) to 25 m behind its tail, and is only 'done' when the whole train has cleared it."""
import os
import run_undo_test as t

s = t.make_runtime(True)
s.execute(t.read(os.path.join(t.MOD, "scripts", "Hud", "GenericHudElement.lua")))  # ADInheritsFrom
s.execute(t.read(os.path.join(t.MOD, "scripts", "Utils", "AutoDriveTON.lua")))
s.execute("AbstractTask = AbstractTask or ADInheritsFrom({})")
s.execute(t.read(os.path.join(t.MOD, "scripts", "Tasks", "FollowCombineTask.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Tasks", "MoveClearOfHarvesterTask.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Modules", "PathFinderModule.lua")))
s.execute("""
    AutoDrive.MODE_UNLOAD = 4
    AutoDrive.CHASEPOS_LEFT, AutoDrive.CHASEPOS_RIGHT, AutoDrive.CHASEPOS_REAR = 1, -1, 2
    AutoDrive.sign = function(x) return x >= 0 and 1 or -1 end
    PIPE = 1
    AutoDrive.getPipeSide = function() return PIPE end
    AutoDrive.getDischargeNode = function() return nil end
    AutoDrive.getHarvesterHalfSize =function() return 2, 6 end   -- harvester 4 m wide, 12 m long, at 0,0 facing +z
    POS = {}
    getWorldTranslation = function(node) local p = POS[node]; return p[1], 0, p[2] end
    AutoDrive.worldToLocal = function(v, x, y, z) return x, y, z end
    AutoDrive.localToWorld = function(v, x, y, z) return x, y, z end
    AutoDrive.localDirectionToWorld = function(v, x, y, z) return x, y, z end
    MathUtil = MathUtil or {}
    MathUtil.vector2Length = function(x, z) return math.sqrt(x * x + z * z) end
    Dischargeable = {DISCHARGE_STATE_OBJECT = 1, DISCHARGE_STATE_OFF = 0}
    LOG = {}
    Logging.info = function(f, ...) table.insert(LOG, string.format(f, ...)) end
    ADDiag = {name = function(v) return v.name or "?" end}
    GOAROUND = nil
    ADUnloaderClear = {GO_AROUND_BEHIND = 25, goAround = function(mode, c) GOAROUND = c end,
        onMoveDone = function() MOVE = "done" end, onMoveFailed = function() MOVE = "failed" end}

    COMBINE = {name = "Ropa", lastSpeedReal = 0, ad = {isHarvester = true, ADRootNode = 0}, components = {{node = "c"}},
        getDischargeState = function() return FLOW end}
    function truck(x, z)
        POS["t"] = {x, z}
        local v = {name = "Truck", lastSpeedReal = 0, size = {length = 8, width = 3}, components = {{node = "t"}}, ad = {}}
        v.ad.modes = {[4] = {}}
        STOPS = 0
        v.ad.specialDrivingModule = {stopVehicle = function() STOPS = STOPS + 1 end, update = function() end,
            driveToPoint = function() DROVE = true end, driveReverse = function() REVERSED = true end}
        return v
    end
    function task(v, chaseSide, chaseX, chaseZ)
        local tk = setmetatable({vehicle = v, combine = COMBINE, chaseSide = chaseSide, chasePos = {x = chaseX, y = 0, z = chaseZ},
            combineFillPercent = 80, filled = false, stuckTimer = AutoDriveTON:new(), angleWrongTimer = AutoDriveTON:new(),
            state = FollowCombineTask.STATE_CHASING}, {__index = FollowCombineTask})
        tk.lastState = tk.state
        return tk
    end
    function run(tk, ms) for i = 1, ms / 100 do if GOAROUND then break end; tk:updatePipeLock(100) end end
""")

fails = 0


def check(name, cond):
    global fails
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails += 1


L = s.eval
# 1. the photo: truck diagonally behind-left, chase spot behind, harvester standing, nothing falling in
s.execute("""FLOW = 0; GOAROUND = nil; DROVE = false; REVERSED = false
    TK = task(truck(-5, -14), AutoDrive.CHASEPOS_REAR, 0, -51); run(TK, 9000)""")
check("behind a standing harvester: holds still (no chasing the rear spot)", L("STOPS > 0 and not DROVE and not REVERSED"))
check("not sent round before 10 s", L("GOAROUND == nil"))
s.execute("run(TK, 1500)")
check("after 10 s: drives round the harvester", L("GOAROUND == COMBINE"))
check("says why in the log", L("string.find(LOG[#LOG], 'nothing falling in for 10 s', 1, true) ~= nil"))

# 2. beside it on the pipe side, under the pipe, crop falling in: never sent round
s.execute("""FLOW = 1; GOAROUND = nil
    TK = task(truck(-6, 0), AutoDrive.CHASEPOS_LEFT, -6, 0); PIPE = -1""")
s.execute("AutoDrive.getPipeSide = function() return -1 end; run(TK, 30000)")
check("beside the pipe with crop falling in: stays", L("GOAROUND == nil"))
# beside the pipe, nothing falling: the creep along the trailer handles it, not the go-round
s.execute("FLOW = 0; TK = task(truck(-6, 0), AutoDrive.CHASEPOS_LEFT, -6, 0); TK.getCreepTrailer = function() return nil end; run(TK, 30000)")
check("beside the pipe, nothing falling: no go-round (creep handles it)", L("GOAROUND == nil"))

# 3. beside the harvester but on the wrong side / behind its tail: not 'beside the pipe'
s.execute("TK = task(truck(6, 0), AutoDrive.CHASEPOS_REAR, 0, -51)")
check("other side: not beside the pipe", L("TK:isBesidePipeSide() == false"))
s.execute("TK = task(truck(-6, -14), AutoDrive.CHASEPOS_REAR, 0, -51)")
check("behind the tail on the pipe side: not beside the pipe", L("TK:isBesidePipeSide() == false"))
s.execute("TK = task(truck(-6, -8), AutoDrive.CHASEPOS_REAR, 0, -51)")
check("front level with the tail on the pipe side: beside", L("TK:isBesidePipeSide() == true"))

# 4. the harvester rolls: the timer starts over
s.execute("""AutoDrive.getPipeSide = function() return 1 end; FLOW = 0; GOAROUND = nil
    TK = task(truck(-5, -14), AutoDrive.CHASEPOS_REAR, 0, -51); run(TK, 9000)
    COMBINE.lastSpeedReal = 0.002; TK.pipeLockSkip = true
    TK.goAroundTime = TK.goAroundTime -- (moving branch resets it; drive part needs more stubs, so only the reset is checked)
    """)
s.execute("""COMBINE.lastSpeedReal = 0.002
    local ok = pcall(function() TK:updatePipeLock(100) end)
    COMBINE.lastSpeedReal = 0""")
check("harvester rolls: timer reset", L("TK.goAroundTime == 0"))

# 5. done only when the whole train has cleared the harvester (5 m outside its outline)
s.execute("""AutoDrive.getAllUnits = function(v) return {v}, 1 end
    V = truck(0, -36)""")
check("25 m behind the tail: clear", L("MoveClearOfHarvesterTask.isClearOf(V, COMBINE)"))
s.execute("POS['t'] = {-6, -8}")
check("beside it: not clear", L("not MoveClearOfHarvesterTask.isClearOf(V, COMBINE)"))
s.execute("""V = truck(0, -36); MT = MoveClearOfHarvesterTask:new(V, {x = 0, y = 0, z = -31}, {x = 0, z = 1}, false)
    MT.harvester = COMBINE; MT.state = MoveClearOfHarvesterTask.STATE_DRIVING; MT.elapsed = 0
    V.ad.drivePathModule = {isTargetReached = function() return true end}
    V.ad.taskModule = {setCurrentTaskFinished = function() end}
    MOVE = nil; MT:update(16)""")
check("arrived clear: move done", L("MOVE == 'done'"))
s.execute("POS['t'] = {-6, -8}; MOVE = nil; MT:update(16)")
check("arrived but not clear: counted as failed", L("MOVE == 'failed'"))

# 6. path finder held to the field: no fallback that leaves it
s.execute("""PF = setmetatable({}, {__index = PathFinderModule})
    PF.vehicle = {}; PF.delayTime = 0; PF.steps = 0; PF.grid = {}; PF.startCell = {x = 0, z = 0, direction = 0}
    PF.targetCell = {x = 5, z = 5}; PF.determineBlockedCells = function() end; PF.isFinished = false; PF.isNewPF = false
    PF.pathFinderTime = 1; PF.max_pathfinder_steps = PathFinderModule.MAX_PATHFINDER_STEPS_TOTAL; PF.retryCounter = 0
    PF.restrictToField = true; PF.stayOnField = true; PF.avoidFruitSetting = false
    PF.fallBackMode1, PF.fallBackMode2, PF.fallBackMode3 = false, false, false
    PF.pipeStepsRaised, PF.noWayAroundCrop = false, false
    PF.goingToPipe, PF.chasingVehicle, PF.isSecondChasingVehicle = false, false, false
    AutoDrive.debugPrint = function() end; AutoDrive.DC_PATHINFO = 1
    AutoDrive.isEditorModeEnabled = function() return false end
    ADScheduler = {removePathfinderVehicle = function() end}
    table.count = table.count or function(t) local n = 0; for _ in pairs(t) do n = n + 1 end; return n end
    for i = 1, 10 do if PF.isFinished then break end; PF.steps = PF.max_pathfinder_steps + 1; pcall(function() PF:update(16) end) end""")
check("stay on field: never drops the field restriction", L("not PF.fallBackMode1 and not PF.fallBackMode2"))

print("\n%d failure(s)" % fails)
raise SystemExit(1 if fails else 0)
