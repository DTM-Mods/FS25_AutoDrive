"""Ticker at the bottom: why each vehicle waits (server), the line of vehicle status and messages (client), the copy
of every AutoDrive message, the scrolling, and the reason sent along with the vehicle's state."""
import os
import run_undo_test as t

s = t.make_runtime(True)
s.execute("""
    ADInheritsFrom = function(base)
        local c = {}
        local mt = {__index = c}
        function c:create() return setmetatable({}, mt) end
        return c
    end
    LoadAtDestinationTask = ADInheritsFrom()
    UnloadAtDestinationTask = ADInheritsFrom()
    -- the messages manager before the ticker hooks it
    SHOWN = {}
    ADMessagesManager = {messageTypes = {INFO = 1, WARN = 2, ERROR = 3}}
    function ADMessagesManager:addMessage(vehicle, t, text, d) table.insert(SHOWN, text) end
    function ADMessagesManager:addNotification(vehicle, t, text, d)
        if vehicle == AutoDrive.getControlledVehicle() then return self:addMessage(vehicle, t, text, d) end
        table.insert(SHOWN, text)
    end
    CONTROLLED = nil
    AutoDrive.getControlledVehicle = function() return CONTROLLED end
    SETTINGS = {showTicker = true}
    AutoDrive.getSetting = function(name) return SETTINGS[name] end
    g_time = 100000
    g_localPlayer = {getFarmId = function() return 1 end}
""")
s.execute(t.read(os.path.join(t.MOD, "scripts", "Gui", "Ticker.lua")))
s.execute("""
    T = ADTicker
    TEXTS = TEXTS or {}
    g_i18n.getText = function(self, key) local x = TEXTS[key]; if x == nil then error("missing l10n " .. key) end return x end
    AutoDrive.localize = function(text) return (text:gsub("%$l10n_([%w_]+);", function(k) return g_i18n:getText(k) end)) end
    VEHICLES = {}
    function vehicle(name, farm)
        local v = {lastSpeedReal = 0, getOwnerFarmId = function() return farm or 1 end,
            ad = {stateModule = {active = true, name = name, info = "Drive to unload point", reason = ""}}}
        local st = v.ad.stateModule
        st.isActive = function(self) return self.active end
        st.getName = function(self) return self.name end
        st.getCurrentLocalizedTaskInfo = function(self) return self.info end
        st.setWaitReason = function(self, r) self.reason = r end
        st.getWaitReasonLocalized = function(self) return AutoDrive.localize(self.reason) end
        v.ad.drivePathModule = {isTargetReached = function() return v.atTarget == true end}
        v.ad.collisionDetectionModule = {}
        v.ad.trailerModule = {}
        v.ad.taskModule = {}
        table.insert(VEHICLES, v)
        return v
    end
    AutoDrive.getAllVehicles = function() return VEHICLES end
    FILL = 0
    AutoDrive.getAllFillLevels = function() return FILL, 87350, false, 87350 - FILL end
    function reason(v) return T.getWaitReason(v) end
""")

# --- why it waits (server)
s.execute("TRUCK = vehicle('Truck 1')")
s.execute("TRUCK.lastSpeedReal = 20 / 3600")
assert s.eval("reason(TRUCK)") == ""                                  # driving
s.execute("TRUCK.lastSpeedReal = 0")
assert s.eval("reason(TRUCK)") == ""                                  # just stopped (< 1.5 s)
s.execute("g_time = g_time + 2000")
assert s.eval("reason(TRUCK)") == ""                                  # stands, nothing to say yet
s.execute("TRUCK.ad.drivePathModule.isPaused = true")
assert s.eval("reason(TRUCK)") == "$l10n_AD_wait_queue;"
s.execute("TRUCK.ad.drivePathModule.isPaused = false; TRUCK.ad.actionWaitUntil = g_time + 19500")
assert s.eval("reason(TRUCK)") == "$l10n_AD_wait_waypoint; (20 s)"
s.execute("TRUCK.ad.actionWaitUntil = nil; OTHER = vehicle('8RX 410'); TRUCK.ad.collisionDetectionModule.trafficVehicle = OTHER")
assert s.eval("reason(TRUCK)") == "$l10n_AD_wait_traffic; (8RX 410)"
s.execute("TRUCK.ad.collisionDetectionModule.trafficVehicle = nil; TRUCK.ad.collisionDetectionModule.detectedObstable = true")
assert s.eval("reason(TRUCK)") == "$l10n_AD_wait_blocked;"
s.execute("TRUCK.ad.collisionDetectionModule.detectedObstable = false")
# loading: filling, then at the load point and not full (the free litres)
s.execute("TRUCK.ad.taskModule.activeTask = LoadAtDestinationTask:create(); TRUCK.ad.taskModule.activeTask.trailers = {{}}; FILL = 40000; TRUCK.ad.trailerModule.isLoading = true")
assert s.eval("reason(TRUCK)") == "$l10n_AD_wait_loading; (40000 l / 87400 l)", s.eval("reason(TRUCK)")
s.execute("TRUCK.ad.trailerModule.isLoading = false; TRUCK.atTarget = true; FILL = 86850")
assert s.eval("reason(TRUCK)") == "$l10n_AD_wait_notFull; (500 l free)", s.eval("reason(TRUCK)")
# unloading: tipping while it runs, then nothing comes out
s.execute("""
    TRUCK.atTarget = false
    TRUCK.ad.taskModule.activeTask = UnloadAtDestinationTask:create(); TRUCK.ad.taskModule.activeTask.trailers = {{}}
    TRUCK.ad.trailerModule.isUnloading = true
    FILL = 30000; reason(TRUCK); g_time = g_time + 1000; FILL = 29000
""")
assert s.eval("reason(TRUCK)") == "$l10n_AD_wait_tipping; (29000 l)", s.eval("reason(TRUCK)")
s.execute("g_time = g_time + 12000")
assert s.eval("reason(TRUCK)").startswith("$l10n_AD_wait_noFlow; (")
s.execute("TRUCK.ad.trailerModule.isUnloading = false; TRUCK.atTarget = true")
assert s.eval("reason(TRUCK)") == "$l10n_AD_wait_unloadPoint; (29000 l)"
s.execute("TRUCK.atTarget = false; TRUCK.ad.taskModule.activeTask = nil")
assert s.eval("reason(TRUCK)").startswith("$l10n_AD_wait_standing; (")
s.execute("TRUCK.ad.stateModule.active = false")
assert s.eval("reason(TRUCK)") == ""                                  # switched off
s.execute("TRUCK.ad.stateModule.active = true")
# the server sets it for every vehicle once a second
s.execute("T.reasonTimer = 0; T:updateServer(1000)")
assert s.eval("TRUCK.ad.stateModule.reason").startswith("$l10n_AD_wait_standing;")

# --- messages: a copy of each, once, only own farm's notifications
s.execute("""
    ADMessagesManager:addMessage(nil, 2, "Truck 1: no parking destination", 3000)
    ADMessagesManager:addMessage(nil, 2, "Truck 1: no parking destination", 3000)
    CONTROLLED = TRUCK
    ADMessagesManager:addNotification(TRUCK, 1, "Driver of Truck 1 has reached Silo", 3000)
    STRANGER = vehicle('Neighbour', 2); STRANGER.ad.stateModule.active = false
    ADMessagesManager:addNotification(STRANGER, 1, "Driver of Neighbour has reached Mill", 3000)
""")
assert s.eval("#T.messages") == 2 and s.eval("#SHOWN") == 4               # the pop-ups still all show
assert s.eval("T.messages[1].text") == "Driver of Truck 1 has reached Silo"

# --- the line: active own vehicles with status and reason, then the messages; old messages drop out
s.execute("""
    TEXTS.AD_wait_standing = "standing still"
    TEXTS.AD_ticker_waiting = "waiting"; TEXTS.AD_ticker_helpers = "Helpers"
    -- other drivers on the server: a Courseplay tractor, a game helper, and an implement of an active vehicle (not counted)
    CP = {getIsCpActive = function() return true end, getIsAIActive = function() return true end}
    HELPER = {getIsAIActive = function() return true end}
    IMPLEMENT = {getIsAIActive = function() return true end, getRootVehicle = function() return HELPER end}
    PARKED = {getIsAIActive = function() return false end}
    table.insert(VEHICLES, CP); table.insert(VEHICLES, HELPER); table.insert(VEHICLES, IMPLEMENT); table.insert(VEHICLES, PARKED)
    TRUCK.ad.stateModule.reason = "$l10n_AD_wait_standing; (20 s)"
    OTHER.ad.stateModule.info = "Drive to loading point"
    SEGMENTS = T.buildSegments()
    function line(segs) local x = {} for _, sgm in ipairs(segs) do table.insert(x, sgm.text) end return table.concat(x) end
""")
text = s.eval("line(SEGMENTS)")
assert text.startswith("AutoDrive 2 (1 waiting)     |     Courseplay 1     |     Helpers 1     |     8RX 410: Drive to loading point     |     Truck 1: Drive to unload point  - standing still (20 s)"), text
assert "Driver of Truck 1 has reached Silo" in text and "no parking destination" in text and "Neighbour" not in text
assert s.eval("SEGMENTS[#SEGMENTS].color == T.COLOR_WARN")
# --- errors in red: Courseplay info texts (errors red, look-after yellow, the rest white) and AutoDrive vehicles
# stopped because of an error (red, as long as they stand)
s.execute("""
    CP.getName = function() return "8RX 310" end
    CP.getOwnerFarmId = function() return 1 end
    CP_TEXTS = {[1] = {name = "ERROR_NO_PATH_FOUND", text = "no path found", id = 2},
        [2] = {name = "FUEL_IS_LOW", text = "should refuel", id = 16384}, [3] = {name = "DRIVING_TO_COMBINE", text = "driving to combine", id = 1048576}}
    CP.getCpActiveInfoTexts = function() return CP_TEXTS end
    BROKEN = vehicle('Tatra'); BROKEN.ad.stateModule.active = false
    ADFleetGui = {getLastProblem = function(v) if v == BROKEN then return {text = "cannot reach the target", messageType = 3} end end}
    SEGS = T.buildSegments()
    function find(txt) for _, sgm in ipairs(SEGS) do if sgm.text == txt then return sgm end end end
""")
assert s.eval("find('no path found').color == T.COLOR_ERROR")
assert s.eval("find('should refuel').color == T.COLOR_WARN")
assert s.eval("find('driving to combine').color == T.COLOR_TEXT")
assert s.eval("find('8RX 310 (Courseplay): ') ~= nil")
assert s.eval("find('cannot reach the target').color == T.COLOR_ERROR") and s.eval("find('Tatra: ') ~= nil")
# a Courseplay vehicle of another farm: not shown
s.execute("CP.getOwnerFarmId = function() return 2 end; SEGS = T.buildSegments()")
assert s.eval("find('no path found')") is None
# started again: no longer listed as stopped
s.execute("BROKEN.ad.stateModule.active = true; SEGS = T.buildSegments()")
assert s.eval("find('cannot reach the target')") is None
s.execute("BROKEN.ad.stateModule.active = false; ADFleetGui = nil")

s.execute("g_time = g_time + T.MESSAGE_LIFETIME + 1")
assert "reached Silo" not in s.eval("line(T.buildSegments())")

# --- drawing: a bar at the bottom, the text scrolls left and wraps around; hidden in menus or switched off
s.execute("""
    g_screenWidth, g_screenHeight = 1920, 1080
    OVERLAYS, DRAWN = 0, {}
    createImageOverlay = function() return 1 end
    setOverlayColor = function() end
    renderOverlay = function(id, x, y, w, h) OVERLAYS = OVERLAYS + 1; BAR = {x, y, w, h} end
    renderText = function(x, y, size, txt) table.insert(DRAWN, {x, txt}) end
    getTextWidth = function(size, txt) return #txt * 0.004 end
    setTextAlignment = function() end; setTextBold = function() end; setTextColor = function() end
    RenderText = {ALIGN_LEFT = 0}
    g_gui = {getIsGuiVisible = function() return MENU end}
    MENU = false
    T.rebuildTimer = T.REBUILD_INTERVAL; T:update(16)
    T:safeDraw()
""")
assert s.eval("OVERLAYS") == 1 and s.eval("BAR[2]") == 0 and s.eval("BAR[3]") == 1   # full width, at the very bottom
first = s.eval("DRAWN[1][1]")
s.execute("DRAWN = {}; T:update(1000); T:safeDraw()")
assert s.eval("DRAWN[1][1]") < first                                           # moved left
s.execute("T.offset = T.totalWidth * 3 + 0.01; DRAWN = {}; T:safeDraw()")
assert 0 <= s.eval("T.offset") < s.eval("T.totalWidth")                         # wraps around
assert not s.eval("T.failed")
s.execute("MENU = true; OVERLAYS = 0; T:safeDraw(); MENU = false; SETTINGS.showTicker = false; T:safeDraw(); SETTINGS.showTicker = true")
assert s.eval("OVERLAYS") == 0

# --- the reason goes along with the vehicle's state: written last, read back and translated
state = t.read(os.path.join(t.MOD, "scripts", "Modules", "StateModule.lua")).replace(chr(13), "")
write = state[state.index("function ADStateModule:doWriteStream"):state.index("function ADStateModule:doReadStream")]
read = state[state.index("function ADStateModule:doReadStream"):state.index("function ADStateModule:writeStream")]
assert "streamWriteString(streamId, self.waitReason or " in write.split("streamWriteUInt8(streamId, self.actualFarmId)")[1]
assert "self.waitReason = streamReadString(streamId)" in read.split("self.actualFarmId = streamReadUInt8(streamId)")[1]
assert "self.waitReasonLocalized = AutoDrive.localize(self.waitReason)" in read
print("OK: ticker (errors red: Courseplay info texts and AutoDrive vehicles stopped by an error; driver counts AutoDrive / waiting / Courseplay / helpers; why it waits: queue, waypoint, traffic, blocked, loading, not full, tipping, nothing comes out, unload point, standing; messages copied once; line; scrolling; synced reason)")
