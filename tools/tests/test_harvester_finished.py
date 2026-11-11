"""Harvester finished its job (od.54): when a harvester's helper (game helper or Courseplay) ends with 'finished job',
its unloaders (same first marker) switch AutoDrive off. Empty: off right away. Grain on board: unload first, then off.
The player stopping the harvester, another 'stopped' reason, or another harvester on the same pins still working:
nothing changes."""
import os
import run_undo_test as t

s = t.make_runtime(True)
s.execute(t.read(os.path.join(t.MOD, "scripts", "Hud", "GenericHudElement.lua")))  # ADInheritsFrom
s.execute(t.read(os.path.join(t.MOD, "scripts", "Utils", "AutoDriveTON.lua")))
s.execute("AbstractMode = AbstractMode or ADInheritsFrom({})")
s.execute(t.read(os.path.join(t.MOD, "scripts", "Modes", "CombineUnloaderMode.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Manager", "HarvestManager.lua")))
s.execute("""
    -- game message classes (GIANTS Class gives isa)
    local function cls() local c = {}; c.new = function() return setmetatable({}, {__index = c}) end
        c.isa = function(self, other) return getmetatable(self).__index == other end; return c end
    AIMessageSuccessFinishedJob = cls()
    AIMessageSuccessStoppedByUser = cls()
    SUBS = {}
    MessageType = {AI_JOB_STOPPED = 77}
    g_messageCenter = {subscribe = function(self, typ, fn, target) SUBS[typ] = {fn = fn, target = target} end}
    function publishStopped(job, msg) local sub = SUBS[MessageType.AI_JOB_STOPPED]; sub.fn(sub.target, job, msg) end

    AutoDrive.MODE_UNLOAD = 4
    CombineUnloaderMode.debugMsg = function() end
    ADTaskModule = {DONT_PROPAGATE = 1}
    LOG = {}
    Logging.info = function(f, ...) table.insert(LOG, string.format(f, ...)) end
    ADDiag = {name = function(v) return v.name or "?" end}
    StopAndDisableADTask = {new = function(self, v, p) return {kind = "stop"} end}
    ExitFieldTask = {new = function(self, v) return {kind = "exitField"} end}
    UnloadAtDestinationTask = {new = function(self, v, id) return {kind = "unload"} end}
    WaitForCallTask = {new = function(self, v) return {kind = "wait"} end}
    DriveToDestinationTask = {new = function(self, v, id) return {kind = "driveToStart"} end}
    ADGraphManager.getWayPointById = function(self, id) return {x = 0, z = 0} end
    ONFIELD = true
    AutoDrive.checkIsOnField = function() return ONFIELD end
    getWorldTranslation = function(node) return 100, 0, 100 end
    MathUtil = MathUtil or {}
    MathUtil.vector2Length = function(x, z) return math.sqrt(x * x + z * z) end
    FILL = {}
    AutoDrive.getAllUnits = function(v) return {v}, 1 end
    AutoDrive.getAllFillLevels = function(trailers) local f = FILL[trailers[1]] or 0; return f, 1000, f > 800, 1000 - f end
    AutoDrive.getSetting = function() return nil end

    MARKER_A, MARKER_B = {id = 1}, {id = 2}
    VEHICLES = {}
    AutoDrive.getAllVehicles = function() return VEHICLES end
    function harvester(name, marker, ai)
        local h = {name = name, ad = {stateModule = {getFirstMarker = function() return marker end}}, ai = ai}
        h.getRootVehicle = function(self) return self end
        h.getIsAIActive = function(self) return self.ai end
        return h
    end
    function unloader(name, marker, fill, state)
        local u = {name = name, components = {{node = 1}}, ad = {}}
        u.getRootVehicle = function(self) return self end
        FILL[u] = fill
        u.tasks = {"current"}
        u.ad.taskModule = {abortAllTasks = function() u.tasks = {} end, addTask = function(self, task) table.insert(u.tasks, task) end,
            getActiveTask = function() return u.tasks[1] end}
        local mode = setmetatable({vehicle = u, state = CombineUnloaderMode[state], harvestFinished = false, trailers = {u},
            getFollowingUnloader = function() return nil end, unregisterFollowingUnloader = function() end}, {__index = CombineUnloaderMode}); CombineUnloaderMode.setStateNames(mode)
        u.ad.modes = {[4] = mode}
        u.active = true
        u.ad.stateModule = {isActive = function() return u.active end, getMode = function() return 4 end,
            getCurrentMode = function() return mode end, getFirstMarker = function() return marker end,
            getSecondMarker = function() return {id = 9} end}
        table.insert(VEHICLES, u)
        return u
    end
    function job(v) return {vehicleParameter = {getVehicle = function() return v end}} end
    function lastKind(u) local tk = u.tasks[#u.tasks]; return type(tk) == "table" and tk.kind or tk end
    function reset() VEHICLES = {}; LOG = {}; ADHarvestManager:load(); ADHarvestManager.jobStoppedSubscribed = false; ADHarvestManager:subscribeJobStopped() end
""")

fails = 0


def check(name, cond):
    global fails
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails += 1


L = s.eval
# 1. finished job: empty unloader off at once, full one leaves the field to unload
s.execute("""reset()
    H = harvester("Combine", MARKER_A, false); table.insert(ADHarvestManager.harvesters, H)
    EMPTY = unloader("Empty", MARKER_A, 0, "STATE_WAIT_TO_BE_CALLED")
    FULL = unloader("Full", MARKER_A, 500, "STATE_ACTIVE_UNLOAD_COMBINE")
    OTHER = unloader("OtherField", MARKER_B, 0, "STATE_WAIT_TO_BE_CALLED")
    publishStopped(job(H), AIMessageSuccessFinishedJob.new())""")
check("empty unloader gets the stop task", L("lastKind(EMPTY) == 'stop' and #EMPTY.tasks == 1"))
check("full unloader leaves the field to unload", L("lastKind(FULL) == 'exitField' and FULL.ad.modes[4].harvestFinished"))
check("unloader on other pins untouched", L("lastKind(OTHER) == 'current' and not OTHER.ad.modes[4].harvestFinished"))
# full one: exit field -> unload -> then off instead of driving back
s.execute("M = FULL.ad.modes[4]; T1 = M:getNextTask(); T2 = M:getNextTask()")
check("after the field exit it unloads", L("T1.kind == 'unload'"))
check("after unloading it switches off", L("T2.kind == 'stop'"))
# helper-off fire from the harvest manager afterwards does not undo it
s.execute("FULL.tasks = {'unloading'}; M.state = CombineUnloaderMode.STATE_DRIVE_TO_UNLOAD; M:onHarvesterLeft()")
check("later 'harvester left' leaves it alone", L("FULL.tasks[1] == 'unloading' and #FULL.tasks == 1"))
# start again later: flag cleared
s.execute("""ADHarvestManager.unregisterAsUnloader = function() end
    FULL.ad.trailerModule = {reset = function() end}
    AutoDrive.getTractorTrainLength = function() return 10 end
    AutoDrive.getAllDischargeableUnits = function() end
    Queue = {new = function() return {} end}
    M:reset()""")
check("restarting clears the finished flag", L("M.harvestFinished == false"))

# 2. already driving to unload: keeps its task, off afterwards
s.execute("""reset()
    H = harvester("Combine", MARKER_A, false); table.insert(ADHarvestManager.harvesters, H)
    ON_ROAD = unloader("OnRoad", MARKER_A, 900, "STATE_DRIVE_TO_UNLOAD")
    publishStopped(job(H), AIMessageSuccessFinishedJob.new())
    T = ON_ROAD.ad.modes[4]:getNextTask()""")
check("unloader already driving to unload keeps its task", L("ON_ROAD.tasks[1] == 'current' and #ON_ROAD.tasks == 1"))
check("...and switches off after it", L("T.kind == 'stop'"))

# 3. player stopped it: nothing happens
s.execute("""reset()
    H = harvester("Combine", MARKER_A, false); table.insert(ADHarvestManager.harvesters, H)
    U = unloader("U", MARKER_A, 0, "STATE_WAIT_TO_BE_CALLED")
    publishStopped(job(H), AIMessageSuccessStoppedByUser.new())""")
check("player stop: unloader keeps working", L("lastKind(U) == 'current' and not U.ad.modes[4].harvestFinished"))

# 4. second harvester on the same pins still working: unloaders stay
s.execute("""reset()
    H = harvester("Combine1", MARKER_A, false); H2 = harvester("Combine2", MARKER_A, true)
    table.insert(ADHarvestManager.harvesters, H); table.insert(ADHarvestManager.harvesters, H2)
    U = unloader("U", MARKER_A, 0, "STATE_WAIT_TO_BE_CALLED")
    publishStopped(job(H), AIMessageSuccessFinishedJob.new())""")
check("another harvester still working: unloader stays", L("lastKind(U) == 'current'"))

# 5. a vehicle AutoDrive does not know as harvester (e.g. a sprayer) finishing: nothing
s.execute("""reset()
    SPRAYER = harvester("Sprayer", MARKER_A, false)
    U = unloader("U", MARKER_A, 0, "STATE_WAIT_TO_BE_CALLED")
    publishStopped(job(SPRAYER), AIMessageSuccessFinishedJob.new())""")
check("non-harvester job finishing: unloader stays", L("lastKind(U) == 'current'"))

# 6. trailed forage harvester: the job runs on the tractor (root), harvester is the implement
s.execute("""reset()
    TRACTOR = {name = "Tractor"}; TRACTOR.getRootVehicle = function(self) return self end
    FH = harvester("Forage", MARKER_A, false); FH.getRootVehicle = function() return TRACTOR end
    FH.isTrailedHarvester = true; FH.trailingVehicle = TRACTOR
    table.insert(ADHarvestManager.harvesters, FH)
    U = unloader("U", MARKER_A, 0, "STATE_FOLLOW_COMBINE")
    publishStopped(job(TRACTOR), AIMessageSuccessFinishedJob.new())""")
check("pulled forage harvester: unloader switches off", L("lastKind(U) == 'stop'"))

print("\n".join(s.eval("LOG")[i] for i in range(1, len(s.eval("LOG")) + 1)))
print("%d failed" % fails if fails else "all ok")
raise SystemExit(1 if fails else 0)
