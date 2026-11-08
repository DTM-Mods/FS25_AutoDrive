"""Catching up with the combine: the HUD says why the unloader waits before planning (again) - starting, no path,
combine moved on, not lined up, spot behind the combine off its field, combine almost full - instead of
'Unload area blocked' for all of them, and, while it waits behind the combine, the tries used before it gives up."""
import os
import re
import run_undo_test as t

s = t.make_runtime(True)
s.execute(t.read(os.path.join(t.MOD, "scripts", "Hud", "GenericHudElement.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Utils", "AutoDriveTON.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Tasks", "AbstractTask.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Tasks", "CatchCombinePipeTask.lua")))
# the unloader mode's constants the tasks read (PATH_TIMEOUT, states); the whole mode needs much more of the game
mode_src = t.read(os.path.join(t.MOD, "scripts", "Modes", "CombineUnloaderMode.lua"))
s.execute("CombineUnloaderMode = CombineUnloaderMode or {}\n" + "\n".join(re.findall(r"^CombineUnloaderMode\.[A-Z_]+ = [^\r\n]+", mode_src, re.M)))
s.execute("""
    AutoDrive.debugPrint = function() end
    AutoDrive.MODE_UNLOAD = 4
    AutoDrive.CHASEPOS_REAR = 3
    AutoDrive.CHASEPOS_LEFT = 1
    POS = {[1] = {0, 0}, [2] = {0, 50}}
    getWorldTranslation = function(node) local p = POS[node]; return p[1], 0, p[2] end
    g_currentMission = g_currentMission or {}
    g_currentMission.nodeToObject = {[2] = true}
    FIELD = {chase = 7, combine = 7}
    g_farmlandManager = {getFarmlandIdAtWorldPosition = function(self, x, z) return z < 0 and FIELD.chase or FIELD.combine end}
    COMBINE_FILL = 0.5
    AutoDrive.getObjectFillLevels = function(v) return COMBINE_FILL * 1000, 1000, nil, (1 - COMBINE_FILL) * 1000 end
    AutoDrive.getDistanceBetween = function() return 50 end
    CHASE_SIDE = AutoDrive.CHASEPOS_LEFT
    ANGLE = 10
    PATH = {{x = 0, z = 0}}
    TARGET_REACHED = false
    COMBINE = {components = {{node = 2}}, ad = {isChopper = false}}
    COMBINE.getRootVehicle = function(self) return self end
    UNLOADER = {components = {{node = 1}}, lastSpeedReal = 1, ad = {
        modes = {[4] = {
            getPipeChasePosition = function() return {x = 0, z = CHASE_SIDE == AutoDrive.CHASEPOS_REAR and -10 or 10}, CHASE_SIDE end,
            getAngleToCombineHeading = function() return ANGLE end,
            getAngleToCombine = function() return ANGLE end,
            isUnloaderOnCorrectSide = function() return true end,
            notifyAboutFailedPathfinder = function() end,
            setToWaitForCall = function() end}},
        pathFinderModule = {reset = function() end, startPathPlanningToPipe = function() end, hasFinished = function() return true end,
            getPath = function() return PATH end, update = function() end, addDelayTimer = function() end,
            getCurrentState = function() return 1, 2, 3, 4 end,
            isNoWayAroundCrop = function() return false end},
        specialDrivingModule = {stopVehicle = function() end, update = function() end},
        drivePathModule = {setWayPoints = function() end, isTargetReached = function() return TARGET_REACHED end, update = function() end},
        taskModule = {setCurrentTaskFinished = function() end}}}
    LOG, PAUSED = {}, {}
    Logging.info = function(f, ...) table.insert(LOG, string.format(f, ...)) end
    ADDiag = {name = function(v) return v == COMBINE and "Combine" or "Truck" end,
              catchPaused = function(v, c, reason, tries, seconds) table.insert(PAUSED, {reason = reason, tries = tries, seconds = seconds}) end}
    STOPPED = 0
    UNLOADER.ad.specialDrivingModule.stopVehicle = function() STOPPED = STOPPED + 1 end
    TASK = CatchCombinePipeTask:new(UNLOADER, COMBINE)
""")


def info():
    return s.eval("TASK:getI18nInfo()")


def state():
    return s.eval("TASK:getStateName()")


# just started: planning, no tries counted yet
assert info() == "$l10n_AD_task_catch_up_with_combine; - $l10n_AD_task_catch_planning;", info()
# planning finished without a path: no path (a finished path finding starts the count of tries again)
s.execute("TASK:update(5000)")
assert state() == "STATE_PATHPLANNING", state()
s.execute("PATH = {}; TASK:update(16)")
assert info().endswith("$l10n_AD_task_catch_no_path; (1/8)"), info()
assert "Truck, catching up with Combine: No way to the combine found, trying again (new path 1 of 8)" in s.eval("LOG[#LOG]"), s.eval("LOG[#LOG]")
# (the wait before planning again is over after a second: update(5000) gets past it)
# a path this time, driving; the combine moves on more than 85 m: planning again
s.execute("PATH = {{x = 0, z = 0}}; TASK:update(5000); TASK:update(16)")
assert state() == "STATE_DRIVING", state()
s.execute("POS[2] = {0, 140}; TASK:update(16)")
assert info().endswith("$l10n_AD_task_catch_combine_moved; (2/8)"), info()
# at the end of the path, but at an angle to the combine: not lined up
s.execute("POS[2] = {0, 50}; TASK:update(5000); TASK:update(16)")
assert state() == "STATE_DRIVING", state()
s.execute("ANGLE = 60; TARGET_REACHED = true; TASK:update(16)")
assert info().endswith("$l10n_AD_task_catch_not_lined_up; (3/8)"), info()
# it would have to chase behind the combine, and that spot is not on the combine's field
s.execute("CHASE_SIDE = AutoDrive.CHASEPOS_REAR; FIELD.chase = 8; TASK:update(5000)")
assert state() == "STATE_DELAY_PATHPLANNING", state()
assert info().endswith("$l10n_AD_task_catch_chase_off_field; (1/20)"), info()
# behind the combine on its field, but the combine is almost full
s.execute("FIELD.chase = 7; COMBINE_FILL = 0.88; TASK:update(5000)")
assert info().endswith("$l10n_AD_task_catch_combine_almost_full; (2/20)"), info()

# driving circles: not lined up again and again; the 8th new path in a row makes it stand still for 30 s, it says why
# once, then tries again; the count is kept on the vehicle (the task is made anew) and starts again when lined up
s.execute("""
    FIELD.chase = 7; COMBINE_FILL = 0.5; CHASE_SIDE = AutoDrive.CHASEPOS_LEFT
    TASK = CatchCombinePipeTask:new(UNLOADER, COMBINE)
    for i = 1, 5 do TARGET_REACHED = false; TASK:update(5000); TASK:update(16); TARGET_REACHED = true; TASK:update(16) end
""")
assert s.eval("UNLOADER.ad.catchReplans") == 0 and s.eval("#PAUSED") == 1
assert s.eval("PAUSED[1].reason") == "AD_task_catch_not_lined_up" and s.eval("PAUSED[1].tries") == 8 and s.eval("PAUSED[1].seconds") == 30
assert info().endswith("$l10n_AD_task_catch_paused; (30 s)"), info()
s.execute("STOPPED = 0; TASK:update(20000)")
assert state() == "STATE_DELAY_PATHPLANNING" and s.eval("STOPPED") == 1 and info().endswith("(10 s)"), info()
s.execute("TASK:update(10000); TASK:update(5000)")
assert state() == "STATE_PATHPLANNING", state()
# lined up: the count starts again
s.execute("UNLOADER.ad.catchReplans = 5; ANGLE = 10; TASK:update(16); TARGET_REACHED = true; TASK:update(16)")
assert state() == "STATE_FINISHED" and s.eval("UNLOADER.ad.catchReplans") == 0, state()
# the message: names, count, last reason, what to check (both settings by their translated names)
diag = t.read(os.path.join(t.MOD, "scripts", "Manager", "Diagnostics.lua"))
body = diag[diag.index("function ADDiag.catchPaused"):]
body = body[:body.index("\nend\n")]
for part in ("$l10n_AD_diag_catchPaused;", "$l10n_AD_diag_newPaths;", "$l10n_AD_hint_catchPaused;", "$l10n_gui_ad_restrictToField;", "$l10n_gui_ad_followOnlyOnField;"):
    assert part in body, part
for f in os.listdir(os.path.join(t.MOD, "translations")):
    text = t.read(os.path.join(t.MOD, "translations", f))
    for key in ("AD_task_catch_paused", "AD_diag_catchPaused", "AD_diag_newPaths", "AD_hint_catchPaused"):
        assert 'name="%s"' % key in text, (f, key)

# every reason has a text in the English translation, and the old catch-all is gone
en = t.read(os.path.join(t.MOD, "translations", "translation_en.xml"))
keys = set(re.findall(r'<text name="([^"]+)"', en))
reasons = re.findall(r'CatchCombinePipeTask\.DELAY_\w+ = "(\w+)"', t.read(os.path.join(t.MOD, "scripts", "Tasks", "CatchCombinePipeTask.lua")))
assert len(reasons) == 8 and all(r in keys for r in reasons), reasons
assert "AD_task_unload_area_in_fruit" not in keys
print("OK: catching up with the combine says why it waits (starting, no path, combine moved, not lined up, "
      "spot behind off the field, combine almost full, paused) and, waiting behind the combine, how many of the 20 tries are used; "
      "new paths in a row are counted and logged, the 8th pauses it 30 s with one message saying why and what to check")
