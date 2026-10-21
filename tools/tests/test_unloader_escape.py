"""Drive clear when blocked: an unloader standing in front of a helper-driven harvester, or stuck against a vehicle,
switches off its collisions with vehicles, drives to the nearest field edge and switches them on again once clear."""
import os
import run_undo_test as t

s = t.make_runtime(True)
s.execute("""
    Class = function(c, super) local mt = {__index = c}; setmetatable(c, {__index = super}); return mt end
    Event = {new = function(mt) return setmetatable({}, mt) end}
    InitEventClass = function() end
""")
s.execute(t.read(os.path.join(t.MOD, "scripts", "Hud", "GenericHudElement.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Utils", "UtilFuncs.lua")))
s.execute(t.read(os.path.join(t.MOD, "scripts", "Utils", "CollisionDetectionUtils.lua")))
for f in [("Tasks", "AbstractTask.lua"), ("Manager", "UnloaderEscape.lua"), ("Tasks", "EscapeToFieldEdgeTask.lua"), ("Events", "UnloaderEscapeEvent.lua")]:
    s.execute(t.read(os.path.join(t.MOD, "scripts", *f)))
s.execute("""
    E = ADUnloaderEscape
    CollisionFlag = {DEFAULT = 1, VEHICLE = 2, TERRAIN = 4}
    -- a field: x 0..100, z 0..200
    AutoDrive.checkIsOnField = function(x, y, z) return x >= 0 and x <= 100 and z >= 0 and z <= 200 end
    g_currentMission = g_currentMission or {}
    g_currentMission.terrainRootNode = 1
    getTerrainHeightAtWorldPos = function() return 0 end
    g_time = 0
    POS = {}
    getWorldTranslation = function(node) local p = POS[node]; return p[1], 0, p[2] end
    -- vehicles: one component each; the unloader's component has a compound child shape (node + 100)
    MASKS = {}
    CHILDREN = {}
    getNumOfChildren = function(node) return #(CHILDREN[node] or {}) end
    getChildAt = function(node, i) return CHILDREN[node][i + 1] end
    getIsCompoundChild = function(node) return node > 100 end
    getCollisionFilterMask = function(node) return MASKS[node] end
    setCollisionFilterMask = function(node, mask) MASKS[node] = mask end
    entityExists = function() return true end
    VEHICLES = {}
    function vehicle(node, x, z, dirX, dirZ, width, length)
        local v = {components = {{node = node}}, rootNode = node, size = {width = width, length = length, lengthOffset = 0}, dirX = dirX, dirZ = dirZ,
            lastSpeedReal = 0, ad = {}}
        v.getRootVehicle = function(self) return self end
        POS[node] = {x, z}
        MASKS[node] = 1 + 2 + 4
        table.insert(VEHICLES, v)
        return v
    end
    AutoDrive.getAllVehicles = function() return VEHICLES end
    AutoDrive.getAllImplements = function(v, include) return {v} end
    AutoDrive.checkIsConnected = function(self, a, b) return a == b end
    AutoDrive.getVehicleDimensions = function(v) return v.size.width, v.size.length end
    AutoDrive.localDirectionToWorld = function(v, x, y, z) return v.dirX, 0, v.dirZ end
    AutoDrive.localToWorld = function(v, x, y, z) local p = POS[v.components[1].node]; return p[1] + v.dirX * z, 0, p[2] + v.dirZ * z end
    AutoDrive.combineIsTurning = function() return false end
    SETTING = true
    AutoDrive.getSetting = function(name) if name == "unloaderEscape" then return SETTING end end
    BROADCAST = {}
    g_server = {broadcastEvent = function(self, ev) table.insert(BROADCAST, ev) end}
    MESSAGES = {}
    ADMessagesManager = {messageTypes = {INFO = 1}}
    AutoDriveMessageEvent = {sendMessageOrNotification = function(v, typ, text, duration, ...) table.insert(MESSAGES, string.format(text, ...)) end}
    ADDiag = {unitName = function(v) return v.unitName or "?" end}

    HARVESTER = vehicle(10, 50, 50, 0, 1, 4, 10)
    HARVESTER.unitName = "Combine"
    HARVESTER.getIsAIActive = function() return HARVESTER_AI end
    HARVESTER_AI = true
    UNLOADER = vehicle(20, 50, 64, 0, 1, 3, 12)      -- right in front of the harvester
    CHILDREN[20] = {121}
    MASKS[121] = 2 + 1
    ADHarvestManager = {harvesters = {HARVESTER}}
    -- the unloader's modules
    DRIVEN = 0
    UNLOADER.ad.specialDrivingModule = {releaseVehicle = function() end, stopVehicle = function() STOPPED = true end, update = function() end,
        driveToPoint = function(self, dt, point) DRIVEN = DRIVEN + 1; LAST_POINT = point end}
    TASKS = {}
    UNLOADER.ad.taskModule = {abortAllTasks = function() TASKS = {} end, addTask = function(self, task) table.insert(TASKS, task) end,
        setCurrentTaskFinished = function() TASK_FINISHED = true end}
    UNLOADER.ad.stateModule = {getName = function() return "Truck 1" end}
    MODE = {vehicle = UNLOADER, combine = HARVESTER, state = "chase", STATE_ESCAPE = "escape", trailers = {}, failedPathFinder = 0}
    AutoDrive.getAllFillLevels = function() return 0 end
""")

# --- collisions with vehicles off for every shape of the unloader, on again exactly as before
s.execute("E.setGhost(UNLOADER, true)")
assert s.eval("MASKS[20]") == 5 and s.eval("MASKS[121]") == 1 and s.eval("E.isGhosted(UNLOADER)")
assert s.eval("#BROADCAST") == 1 and s.eval("BROADCAST[1].ghost") is True    # the clients do the same
s.execute("E.setGhost(UNLOADER, false)")
assert s.eval("MASKS[20]") == 7 and s.eval("MASKS[121]") == 3 and not s.eval("E.isGhosted(UNLOADER)")

# --- the nearest field edge: from x 90 the east edge (x 100), a few metres past it
s.execute("EX, EZ = E.findFieldEdge(90, 100)")
assert 100 < s.eval("EX") <= 112 and abs(s.eval("EZ") - 100) < 0.01, (s.eval("EX"), s.eval("EZ"))
s.execute("EX, EZ = E.findFieldEdge(50, 196)")      # north edge is nearest there
assert abs(s.eval("EX") - 50) < 0.01 and s.eval("EZ") > 200
assert s.eval("E.findFieldEdge(150, 100)") is None   # not on a field

# --- in front of the harvester, not beside it
assert s.eval("E.isInFrontOfHarvester(UNLOADER, HARVESTER)")
s.execute("POS[20] = {58, 50}")
assert not s.eval("E.isInFrontOfHarvester(UNLOADER, HARVESTER)")
s.execute("POS[20] = {50, 64}")

# --- blocking the harvester: after 6 s of both standing, the escape starts (once, then a pause)
for _ in range(59):
    assert not s.eval("E.monitor(MODE, 100, false)")
assert s.eval("E.monitor(MODE, 100, false)")
assert s.eval("MODE.state") == "escape" and s.eval("#TASKS") == 1 and s.eval("MESSAGES[1]").endswith("$l10n_AD_escape_harvester; (Combine)"), s.eval("MESSAGES[1]")
assert s.eval("E.monitor(MODE, 100, false)")         # while escaping the escape owns the vehicle
s.execute("MODE.state = 'chase'; MODE.escapeHarvesterTime = 0")
for _ in range(80):
    assert not s.eval("E.monitor(MODE, 100, false)")   # cooldown
s.execute("g_time = g_time + E.COOLDOWN + 1")
# the harvester driven by a person, or the unloader being filled: no escape
s.execute("HARVESTER_AI = false")
for _ in range(80):
    assert not s.eval("E.monitor(MODE, 100, false)")
s.execute("HARVESTER_AI = true; MODE.trailers = {UNLOADER}; FILLS = 0; AutoDrive.getAllFillLevels = function() FILLS = FILLS + 10; return FILLS end")
for _ in range(80):
    assert not s.eval("E.monitor(MODE, 100, false)")
s.execute("AutoDrive.getAllFillLevels = function() return 0 end")

# --- stuck: only against a vehicle (else AutoDrive reverses as before)
s.execute("POS[20] = {20, 20}; MODE.escapeHarvesterTime = 0")
assert not s.eval("E.monitor(MODE, 100, true)")
s.execute("OTHER = vehicle(30, 20, 27.5, 0, 1, 3, 3)")     # right behind the unloader's front
assert s.eval("E.monitor(MODE, 100, true)") and s.eval("MESSAGES[#MESSAGES]").endswith("$l10n_AD_escape_stuck;")
# the setting off: nothing
s.execute("MODE.state = 'chase'; g_time = g_time + E.COOLDOWN + 1; SETTING = false")
assert not s.eval("E.monitor(MODE, 100, true)")
s.execute("SETTING = true")

# --- the task: collisions off, to the edge, wait while another vehicle is near, then collisions on and done
s.execute("""
    POS[20] = {90, 100}; POS[30] = {91, 104}       -- OTHER still overlaps
    UNLOADER.dirX, UNLOADER.dirZ = 1, 0
    TASK = EscapeToFieldEdgeTask:new(UNLOADER)
    TASK:setUp()
""")
assert s.eval("E.isGhosted(UNLOADER)") and s.eval("UNLOADER.ad.escapeActive")
assert s.eval("TASK.target.x") > 100
s.execute("TASK:update(100)")
assert s.eval("DRIVEN") == 1 and s.eval("LAST_POINT.x") > 100
s.execute("POS[20] = {TASK.target.x, TASK.target.z}; POS[30] = {TASK.target.x + 1, TASK.target.z}; TASK:update(100); TASK:update(100)")
assert s.eval("TASK.state") == 2 and s.eval("E.isGhosted(UNLOADER)") and not s.eval("TASK_FINISHED")   # not clear yet
s.execute("POS[30] = {0, 0}; TASK:update(100)")
assert not s.eval("E.isGhosted(UNLOADER)") and s.eval("TASK_FINISHED") and not s.eval("UNLOADER.ad.escapeActive")

# --- the watcher: AutoDrive stopped during an escape, collisions come back once nothing is near
s.execute("""
    E.setGhost(UNLOADER, true); UNLOADER.ad.escapeActive = false
    POS[30] = {POS[20][1] + 1, POS[20][2]}
    E:update(600)
""")
assert s.eval("E.isGhosted(UNLOADER)")
s.execute("POS[30] = {0, 0}; E:update(600)")
assert not s.eval("E.isGhosted(UNLOADER)")
print("OK: drive clear when blocked (collisions off/on, field edge, blocking a harvester, stuck against a vehicle, cooldown, task, watcher)")
