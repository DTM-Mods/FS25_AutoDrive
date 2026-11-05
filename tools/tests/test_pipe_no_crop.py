"""An unloader driving up to a combine's pipe (not chasing it) never drives through the crop while avoid fruit is on:
the path finder first searches with a bigger step budget, may use fallback 1 and 2 (field border), never fallback 3
(fruit); without a path it says so and the task stands still, says why and plans again. Chasing, and driving to the
network, are as before."""
import os
import run_undo_test as t

s = t.make_runtime(True)
s.execute(t.read(os.path.join(t.MOD, "scripts", "Modules", "PathFinderModule.lua")))
s.execute("""
    AutoDrive.debugPrint = function() end
    AutoDrive.DC_PATHINFO = 1
    AutoDrive.isEditorModeEnabled = function() return false end
    ADScheduler = {removePathfinderVehicle = function() end}
    table.count = table.count or function(t) local n = 0; for _ in pairs(t) do n = n + 1 end; return n end

    -- a path finder in the state startPathPlanningTo / startPathPlanningToPipe leave it in; the search itself is not run:
    -- every update runs out of steps, so the update only goes through the fallbacks
    function newPF(fields)
        local pf = setmetatable({}, {__index = PathFinderModule})
        pf.vehicle = {}
        pf.delayTime = 0
        pf.steps = 0
        pf.grid = {}
        pf.startCell = {x = 0, z = 0, direction = 0}
        pf.targetCell = {x = 5, z = 5}
        pf.determineBlockedCells = function() end
        pf.isFinished = false
        pf.isNewPF = false
        pf.pathFinderTime = 1
        pf.max_pathfinder_steps = PathFinderModule.MAX_PATHFINDER_STEPS_TOTAL
        pf.retryCounter = 0
        pf.restrictToField = true
        pf.avoidFruitSetting = true
        pf.fallBackMode1, pf.fallBackMode2, pf.fallBackMode3 = false, false, false
        pf.pipeStepsRaised, pf.noWayAroundCrop = false, false
        pf.goingToPipe, pf.chasingVehicle, pf.isSecondChasingVehicle = true, false, false
        for k, v in pairs(fields or {}) do pf[k] = v end
        return pf
    end

    -- runs the path finder out of steps until it gives up; returns the fallbacks it went through, in order
    function exhaust(pf)
        local seen = {}
        for i = 1, 20 do
            if pf.isFinished then break end
            pf.steps = pf.max_pathfinder_steps + 1
            local before = {pf.pipeStepsRaised, pf.fallBackMode1, pf.fallBackMode2, pf.fallBackMode3, pf.max_pathfinder_steps}
            pf:update(16)
            if pf.pipeStepsRaised and not before[1] then table.insert(seen, "steps" .. pf.max_pathfinder_steps) end
            if pf.fallBackMode1 and not before[2] then table.insert(seen, "fb1") end
            if pf.fallBackMode2 and not before[3] then table.insert(seen, "fb2") end
            if pf.fallBackMode3 and not before[4] then table.insert(seen, "fb3") end
            if pf.max_pathfinder_steps > before[5] and pf.pipeStepsRaised == before[1] then table.insert(seen, "more" .. pf.max_pathfinder_steps) end
        end
        return table.concat(seen, ",")
    end
""")

total = s.eval("PathFinderModule.MAX_PATHFINDER_STEPS_TOTAL")

# to the pipe, avoid fruit on: bigger search, field border fallbacks, never through the fruit; then no path, flagged
s.execute("PF = newPF()")
assert s.eval("exhaust(PF)") == "steps%d,fb1,fb2" % (total * 3), s.eval("exhaust(PF)")
assert s.eval("PF.isFinished") and s.eval("#PF.wayPoints") == 0 and s.eval("PF.fallBackMode3") is False
assert s.eval("PF:isNoWayAroundCrop()") is True
# close to the combine it starts with only 100 steps: the bigger search applies there too; pathFinderTime x3 or the
# new path finder (fallback 2 skipped there) as well
s.execute("PF = newPF({max_pathfinder_steps = PathFinderModule.MAX_PATHFINDER_STEPS_COMBINE_TURN, pathFinderTime = 3})")
assert s.eval("exhaust(PF)") == "steps%d,fb1,fb2" % (total * 3)
s.execute("PF = newPF({isNewPF = true})")
assert s.eval("exhaust(PF)") == "steps%d,fb1" % (total * 3) and s.eval("PF:isNoWayAroundCrop()") is True
# without restrict to field: only the bigger search
s.execute("PF = newPF({restrictToField = false})")
assert s.eval("exhaust(PF)") == "steps%d" % (total * 3) and s.eval("PF:isNoWayAroundCrop()") is True
# avoid fruit off: bigger search and field border fallbacks, no fruit fallback needed, not flagged as crop
s.execute("PF = newPF({avoidFruitSetting = false})")
assert s.eval("exhaust(PF)") == "steps%d,fb1,fb2" % (total * 3) and s.eval("PF:isNoWayAroundCrop()") is False
# chasing the combine: no fallbacks at all, as before
s.execute("PF = newPF({chasingVehicle = true})")
assert s.eval("exhaust(PF)") == "" and s.eval("PF:isNoWayAroundCrop()") is False
# not to a pipe (e.g. to the network): unchanged, fallback 3 still used
s.execute("PF = newPF({goingToPipe = false, max_pathfinder_steps = 200})")
assert s.eval("exhaust(PF)") == "fb1,fb2,fb3,more300,fb1,fb2,fb3,more400,fb1,fb2,fb3", s.eval("exhaust(PF)")
# the HUD count of the path finder's states: the bigger search counts as one
s.execute("PF = newPF(); exhaust(PF)")
assert tuple(s.eval("{PF:getCurrentState()}").values())[:2] == (4, 4), tuple(s.eval("{PF:getCurrentState()}").values())

# a new start clears the flag
src = t.read(os.path.join(t.MOD, "scripts", "Modules", "PathFinderModule.lua"))
start = src[src.index("function PathFinderModule:startPathPlanningTo(targetPoint"):]
start = start[:start.index("\nend\n")]
assert "self.noWayAroundCrop = false" in start and "self.pipeStepsRaised = false" in start

# the catching task: no path because of the crop -> stands still 5 s with the reason, not counted as a new path, logged
# once; then plans again; a path found allows the log again
s.execute(t.read(os.path.join(t.MOD, "scripts", "Hud", "GenericHudElement.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Utils", "AutoDriveTON.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Tasks", "AbstractTask.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Tasks", "CatchCombinePipeTask.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Tasks", "EmptyHarvesterTask.lua")))
s.execute("""
    AutoDrive.MODE_UNLOAD = 4
    AutoDrive.CHASEPOS_LEFT = 1
    AutoDrive.CHASEPOS_REAR = 3
    getWorldTranslation = function(node) return 0, 0, node == 2 and 50 or 0 end
    g_currentMission = g_currentMission or {}
    g_currentMission.nodeToObject = {[2] = true}
    g_farmlandManager = {getFarmlandIdAtWorldPosition = function() return 7 end}
    AutoDrive.getObjectFillLevels = function() return 500, 1000, nil, 500 end
    AutoDrive.getDistanceBetween = function() return 100 end
    AutoDrive.getAllUnits = function() return {}, 0 end
    AutoDrive.getTractorTrainLength = function() return 10 end
    AutoDrive.setTrailerCoverOpen = function() end
    PATH, CROP, PLANS, STOPPED, FAILED = {}, true, 0, 0, 0
    COMBINE = {components = {{node = 2}}, ad = {isChopper = false}}
    PFM = {reset = function() end, startPathPlanningToPipe = function() PLANS = PLANS + 1 end, hasFinished = function() return true end,
        getPath = function() return PATH end, update = function() end, addDelayTimer = function(self, d) self.delayTime = d end,
        getCurrentState = function() return 1, 2, 3, 4 end, isNoWayAroundCrop = function() return CROP end,
        isTargetBlocked = function() return false end, delayTime = 0}
    UNLOADER = {components = {{node = 1}}, lastSpeedReal = 1, ad = {
        modes = {[4] = {
            getPipeChasePosition = function() return {x = 0, z = 10}, AutoDrive.CHASEPOS_LEFT end,
            notifyAboutFailedPathfinder = function() FAILED = FAILED + 1 end,
            setToWaitForCall = function() end}},
        pathFinderModule = PFM,
        specialDrivingModule = {stopVehicle = function() STOPPED = STOPPED + 1 end, update = function() end},
        drivePathModule = {setWayPoints = function() end, isTargetReached = function() return false end, update = function() end},
        taskModule = {setCurrentTaskFinished = function() end}}}
    LOG = {}
    Logging.info = function(f, ...) table.insert(LOG, string.format(f, ...)) end
    ADDiag = {name = function(v) return v == COMBINE and "Combine" or "Truck" end, catchPaused = function() error("no pause") end}
    TASK = CatchCombinePipeTask:new(UNLOADER, COMBINE)
""")


def info():
    return s.eval("TASK:getI18nInfo()")


s.execute("TASK:update(5000); TASK:update(16)")          # plans, finds nothing: crop
assert s.eval("TASK:getStateName()") == "STATE_DELAY_PATHPLANNING"
assert info() == "$l10n_AD_task_catch_up_with_combine; - $l10n_AD_task_catch_no_way_around_crop; (5 s)", info()
assert s.eval("UNLOADER.ad.catchReplans") is None and s.eval("#LOG") == 1
assert s.eval("LOG[1]") == "[AD] Truck, catching up with Combine: No way around the crop to the combine, waiting (avoid fruit is on, not driving through the crop)", s.eval("LOG[1]")
s.execute("STOPPED = 0; TASK:update(3000)")
assert s.eval("STOPPED") == 1 and info().endswith("(2 s)") and s.eval("PLANS") == 1, info()
s.execute("TASK:update(3000); TASK:update(1500)")        # wait over, a second's check, plans again
assert s.eval("TASK:getStateName()") == "STATE_PATHPLANNING" and s.eval("PLANS") == 2
s.execute("TASK:update(16)")                             # still nothing: waits again, not logged again
assert info().endswith("$l10n_AD_task_catch_no_way_around_crop; (5 s)") and s.eval("#LOG") == 1
s.execute("TASK:update(6000); TASK:update(1500); PATH = {{x = 0, z = 0}}; CROP = false; TASK:update(16)")
assert s.eval("TASK:getStateName()") == "STATE_DRIVING" and s.eval("UNLOADER.ad.noWayAroundCropLogged") is None

# the task at a standing combine: no path because of the crop -> stands still for the path finder's 10 s delay with
# the reason, logged once, then plans again
s.execute("PATH, CROP, LOG, PLANS = {}, true, {}, 0; TASK = EmptyHarvesterTask:new(UNLOADER, COMBINE); TASK:setUp(); TASK:update(16)")
assert s.eval("PLANS") == 2 and s.eval("PFM.delayTime") == 10000
assert info() == "$l10n_AD_task_unloading_combine; - $l10n_AD_task_catch_no_way_around_crop; (10 s)", info()
assert s.eval("LOG[1]") == "[AD] Truck, unloading Combine: No way around the crop to the combine, waiting (avoid fruit is on, not driving through the crop)"
s.execute("PFM.delayTime = 0")
assert info().startswith("$l10n_AD_task_unloading_combine; - $l10n_AD_task_pathfinding;"), info()
s.execute("TASK:update(16)")
assert s.eval("#LOG") == 1

# the unloader does not count it as stuck (that would make it reverse out)
mode = t.read(os.path.join(t.MOD, "scripts", "Modes", "CombineUnloaderMode.lua"))
body = mode[mode.index("function CombineUnloaderMode:notifyAboutFailedPathfinder"):]
body = body[:body.index("\nend\n")]
assert "not self.vehicle.ad.pathFinderModule.noWayAroundCrop" in body

for f in os.listdir(os.path.join(t.MOD, "translations")):
    assert 'name="AD_task_catch_no_way_around_crop"' in t.read(os.path.join(t.MOD, "translations", f)), f
print("OK: to a combine's pipe with avoid fruit on: bigger search (%d steps), field border fallbacks, never through the crop; "
      "no path -> waits with 'no way around the crop' and plans again (catching: 5 s, at a standing combine: 10 s), "
      "logged once, not counted as stuck; chasing and network paths unchanged" % (total * 3))
