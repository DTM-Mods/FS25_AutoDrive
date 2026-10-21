-- Ticker: a bar along the bottom edge of the screen with scrolling text, like a news ticker. It carries
--   - what each AutoDrive vehicle of the player's farm is doing (the task line of the HUD), and why it waits
--     when it stands (worked out on the server, sent along with the vehicle's state: ADStateModule.waitReason)
--   - the AutoDrive messages of the last minutes (the pop-ups at the top stay as they are)
-- User setting showTicker.
ADTicker = {}

ADTicker.HEIGHT = 0.026            -- of the screen height
ADTicker.TEXT_SIZE = 0.0145
ADTicker.SPEED_PIXELS = 90         -- scroll speed, pixels a second
ADTicker.REBUILD_INTERVAL = 1000   -- ms between rebuilding the text
ADTicker.MESSAGE_LIFETIME = 180000 -- ms a message stays in the ticker
ADTicker.MAX_MESSAGES = 12
ADTicker.SEPARATOR = "     |     "
-- server: how often the reasons are worked out (ms), how long a vehicle stands before it counts (ms)
ADTicker.REASON_INTERVAL = 1000
ADTicker.STANDING_TIME = 1500
ADTicker.STANDING_SPEED = 1        -- km/h

ADTicker.COLOR_BACKGROUND = {0, 0, 0, 0.65}
ADTicker.COLOR_TEXT = {1, 1, 1, 1}
ADTicker.COLOR_NAME = {0.55, 0.85, 0.35, 1}
ADTicker.COLOR_REASON = {1, 0.7, 0.2, 1}
ADTicker.COLOR_WARN = {1, 0.85, 0.2, 1}
ADTicker.COLOR_ERROR = {1, 0.35, 0.3, 1}

ADTicker.messages = {}             -- {text, type, time}
ADTicker.segments = {}             -- {text, color, width}
ADTicker.offset = 0
ADTicker.rebuildTimer = 0
ADTicker.reasonTimer = 0

-------------------------------------------------------------------------------
-- messages (client): a copy of every message AutoDrive shows
-------------------------------------------------------------------------------

function ADTicker.addMessage(messageType, text)
    if text == nil or text == "" then
        return
    end
    local now = g_time or 0
    for _, message in ipairs(ADTicker.messages) do
        if message.text == text then
            message.time = now
            return
        end
    end
    table.insert(ADTicker.messages, 1, {text = text, type = messageType, time = now})
    while #ADTicker.messages > ADTicker.MAX_MESSAGES do
        table.remove(ADTicker.messages)
    end
    ADTicker.rebuildTimer = ADTicker.REBUILD_INTERVAL
end

function ADTicker.installMessageHooks()
    if ADMessagesManager == nil or ADMessagesManager.adTickerHooked then
        return
    end
    ADMessagesManager.adTickerHooked = true
    local addMessage = ADMessagesManager.addMessage
    ADMessagesManager.addMessage = function(self, vehicle, messageType, text, duration, ...)
        ADTicker.addMessage(messageType, text)
        return addMessage(self, vehicle, messageType, text, duration, ...)
    end
    local addNotification = ADMessagesManager.addNotification
    ADMessagesManager.addNotification = function(self, vehicle, messageType, text, duration, ...)
        -- the controlled vehicle's notifications go through addMessage; others only for the player's farm
        if vehicle ~= AutoDrive.getControlledVehicle() and ADTicker.isOwnVehicle(vehicle) then
            ADTicker.addMessage(messageType, text)
        end
        return addNotification(self, vehicle, messageType, text, duration, ...)
    end
end

-------------------------------------------------------------------------------
-- why a vehicle waits (server), sent along with the vehicle's state
-------------------------------------------------------------------------------

local function isTask(task, class)
    if task == nil or class == nil then
        return false
    end
    local mt = getmetatable(task)
    return mt ~= nil and mt.__index == class
end

local function litres(value)
    return string.format("%d l", math.floor((value or 0) / 100 + 0.5) * 100)
end

local function reasonText(key, detail)
    if detail ~= nil and detail ~= "" then
        return string.format("$l10n_%s; (%s)", key, detail)
    end
    return string.format("$l10n_%s;", key)
end

-- the fill level went down a moment ago: the load runs
local function isFlowing(vehicle, fillLevel)
    local ad = vehicle.ad
    local now = g_time or 0
    if ad.tickerFlow == nil or fillLevel > ad.tickerFlow.fillLevel + 1 then
        ad.tickerFlow = {fillLevel = fillLevel, lastFlow = -math.huge}
    elseif fillLevel < ad.tickerFlow.fillLevel - 1 then
        ad.tickerFlow.fillLevel = fillLevel
        ad.tickerFlow.lastFlow = now
    end
    return now - ad.tickerFlow.lastFlow < 2500
end

-- why the vehicle stands: a text key and a detail in brackets, or "" when it drives or the task line says it already
function ADTicker.getWaitReason(vehicle)
    local ad = vehicle.ad
    if ad == nil or ad.stateModule == nil or not ad.stateModule:isActive() then
        return ""
    end
    local now = g_time or 0
    local speed = (vehicle.lastSpeedReal or 0) * 3600
    if speed > ADTicker.STANDING_SPEED then
        ad.tickerStandingSince = nil
        return ""
    end
    ad.tickerStandingSince = ad.tickerStandingSince or now
    local standing = now - ad.tickerStandingSince
    if standing < ADTicker.STANDING_TIME then
        return ""
    end

    local drivePath = ad.drivePathModule
    if drivePath ~= nil and drivePath.isPaused then
        return reasonText("AD_wait_queue")
    end
    if ad.actionWaitUntil ~= nil and now <= ad.actionWaitUntil then
        return reasonText("AD_wait_waypoint", string.format("%d s", math.ceil((ad.actionWaitUntil - now) / 1000)))
    end
    local collision = ad.collisionDetectionModule
    if collision ~= nil and collision.trafficVehicle ~= nil and collision.trafficVehicle.ad ~= nil and collision.trafficVehicle.ad.stateModule ~= nil then
        return reasonText("AD_wait_traffic", collision.trafficVehicle.ad.stateModule:getName())
    end
    if collision ~= nil and collision.detectedObstable then
        return reasonText("AD_wait_blocked")
    end

    local task = ad.taskModule ~= nil and ad.taskModule.activeTask or nil
    local trailerModule = ad.trailerModule
    local trailers = task ~= nil and task.trailers or nil
    if trailers ~= nil and #trailers > 0 and AutoDrive.getAllFillLevels ~= nil then
        local fillLevel, fillCapacity, _, fillFree = AutoDrive.getAllFillLevels(trailers)
        if isTask(task, LoadAtDestinationTask) then
            if trailerModule ~= nil and trailerModule.isLoading then
                return reasonText("AD_wait_loading", litres(fillLevel) .. " / " .. litres(fillCapacity))
            end
            if drivePath ~= nil and drivePath:isTargetReached() then
                return reasonText("AD_wait_notFull", litres(fillFree) .. " " .. g_i18n:getText("AD_wait_free"))
            end
        elseif isTask(task, UnloadAtDestinationTask) then
            local flowing = isFlowing(vehicle, fillLevel)
            if trailerModule ~= nil and trailerModule.isUnloading then
                if flowing then
                    return reasonText("AD_wait_tipping", litres(fillLevel))
                end
                local since = now - math.max(ad.tickerFlow.lastFlow, ad.tickerStandingSince)
                return reasonText("AD_wait_noFlow", string.format("%d s", math.floor(since / 1000)))
            end
            if drivePath ~= nil and drivePath:isTargetReached() then
                return reasonText("AD_wait_unloadPoint", litres(fillLevel))
            end
        end
    end
    if standing >= 10000 then
        return reasonText("AD_wait_standing", string.format("%d s", math.floor(standing / 10000) * 10))
    end
    return ""
end

function ADTicker:updateServer(dt)
    self.reasonTimer = self.reasonTimer + dt
    if self.reasonTimer < self.REASON_INTERVAL then
        return
    end
    self.reasonTimer = 0
    for _, vehicle in pairs(AutoDrive.getAllVehicles() or {}) do
        if vehicle.ad ~= nil and vehicle.ad.stateModule ~= nil and vehicle.ad.stateModule.setWaitReason ~= nil then
            local ok, reason = pcall(ADTicker.getWaitReason, vehicle)
            vehicle.ad.stateModule:setWaitReason(ok and reason or "")
        end
    end
end

-------------------------------------------------------------------------------
-- the bar (client)
-------------------------------------------------------------------------------

function ADTicker.isOwnVehicle(vehicle)
    if vehicle == nil then
        return false
    end
    if g_localPlayer == nil or g_localPlayer.getFarmId == nil or vehicle.getOwnerFarmId == nil then
        return true
    end
    return vehicle:getOwnerFarmId() == g_localPlayer:getFarmId()
end

-- the AutoDrive vehicles of the player's farm that are switched on
function ADTicker.getActiveVehicles()
    local vehicles = {}
    for _, vehicle in pairs(AutoDrive.getAllVehicles() or {}) do
        if vehicle.ad ~= nil and vehicle.ad.stateModule ~= nil and vehicle.ad.stateModule:isActive() and ADTicker.isOwnVehicle(vehicle) then
            table.insert(vehicles, vehicle)
        end
    end
    table.sort(vehicles, function(a, b) return (a.ad.stateModule:getName() or "") < (b.ad.stateModule:getName() or "") end)
    return vehicles
end

-- the pieces of the line: {text, color}
function ADTicker.buildSegments()
    local segments = {}
    local function add(text, color)
        table.insert(segments, {text = text, color = color})
    end
    for _, vehicle in ipairs(ADTicker.getActiveVehicles()) do
        local state = vehicle.ad.stateModule
        if #segments > 0 then
            add(ADTicker.SEPARATOR, ADTicker.COLOR_TEXT)
        end
        add((state:getName() or "?") .. ": ", ADTicker.COLOR_NAME)
        add(state:getCurrentLocalizedTaskInfo() or "", ADTicker.COLOR_TEXT)
        local reason = state.getWaitReasonLocalized ~= nil and state:getWaitReasonLocalized() or ""
        if reason ~= "" then
            add("  - " .. reason, ADTicker.COLOR_REASON)
        end
    end
    local now = g_time or 0
    for _, message in ipairs(ADTicker.messages) do
        if now - message.time <= ADTicker.MESSAGE_LIFETIME then
            if #segments > 0 then
                add(ADTicker.SEPARATOR, ADTicker.COLOR_TEXT)
            end
            local color = ADTicker.COLOR_TEXT
            if ADMessagesManager ~= nil and message.type == ADMessagesManager.messageTypes.ERROR then
                color = ADTicker.COLOR_ERROR
            elseif ADMessagesManager ~= nil and message.type == ADMessagesManager.messageTypes.WARN then
                color = ADTicker.COLOR_WARN
            end
            add(message.text, color)
        end
    end
    return segments
end

function ADTicker.isShown()
    if not AutoDrive.getSetting("showTicker") or g_dedicatedServer ~= nil then
        return false
    end
    if g_gui ~= nil and g_gui:getIsGuiVisible() then
        return false
    end
    local hud = g_currentMission ~= nil and g_currentMission.hud or nil
    if hud ~= nil and hud.getIsVisible ~= nil and not hud:getIsVisible() then
        return false
    end
    return true
end

function ADTicker:update(dt)
    if g_server ~= nil then
        self:updateServer(dt)
    end
    if not ADTicker.isShown() then
        return
    end
    self.rebuildTimer = self.rebuildTimer + dt
    if self.rebuildTimer >= self.REBUILD_INTERVAL then
        self.rebuildTimer = 0
        self.segments = ADTicker.buildSegments()
        self.totalWidth = nil
    end
    self.offset = self.offset + dt / 1000 * self.SPEED_PIXELS / (g_screenWidth or 1920)
end

function ADTicker:draw()
    if #self.segments == 0 or not ADTicker.isShown() then
        return
    end
    if self.overlay == nil then
        self.overlay = createImageOverlay("dataS/menu/base/graph_pixel.dds")
    end
    setOverlayColor(self.overlay, unpack(self.COLOR_BACKGROUND))
    renderOverlay(self.overlay, 0, 0, 1, self.HEIGHT)

    local size = self.TEXT_SIZE
    if self.totalWidth == nil then
        local total = 0
        for _, segment in ipairs(self.segments) do
            segment.width = getTextWidth(size, segment.text)
            total = total + segment.width
        end
        -- a gap before the line starts again
        self.totalWidth = total + getTextWidth(size, self.SEPARATOR)
    end
    local loop = math.max(self.totalWidth, 0.001)
    self.offset = self.offset % loop
    local y = (self.HEIGHT - size) / 2 + size * 0.2
    setTextAlignment(RenderText.ALIGN_LEFT)
    setTextBold(false)
    -- as many copies of the line as fit, so it scrolls in without a gap
    local x = -self.offset
    while x < 1 do
        for _, segment in ipairs(self.segments) do
            if x + segment.width > 0 and x < 1 then
                setTextColor(unpack(segment.color))
                renderText(x, y, size, segment.text)
            end
            x = x + segment.width
        end
        x = x + getTextWidth(size, self.SEPARATOR)
    end
    setTextColor(1, 1, 1, 1)
end

function ADTicker:safeDraw()
    if self.failed then
        return
    end
    local ok, err = pcall(self.draw, self)
    if not ok then
        self.failed = true
        Logging.error("[AD] ticker switched off after an error: %s", tostring(err))
    end
end

ADTicker.installMessageHooks()
