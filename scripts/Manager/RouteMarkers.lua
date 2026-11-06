-- Route problems where they are: while the editor is on, the route check runs by itself a moment after the network
-- changed, and every problem it finds (dead end, loose waypoint, trap, target that can not be reached or left) is
-- marked in the world with a tall beacon in its colour and its text above it, counted under the HUD with the
-- distance to the nearest one (an arrow points to it when it is out of sight), and shown on the big map.
-- User setting showRouteProblems.
ADRouteMarkers = {}

ADRouteMarkers.QUIET_TIME = 1500       -- ms without changes to the network before it is checked again
ADRouteMarkers.MAX_BEACONS = 100       -- the nearest ones get a beacon
ADRouteMarkers.MAX_LABELS = 15         -- the nearest ones get their text
ADRouteMarkers.LABEL_DISTANCE = 300
ADRouteMarkers.BEACON_HEIGHT = 25
ADRouteMarkers.TEXT_SIZE = 0.013
ADRouteMarkers.MAP_SQUARE_PIXELS = 10
ADRouteMarkers.WARNING = {1, 0.55, 0}
ADRouteMarkers.ERROR = {1, 0.1, 0.1}
ADRouteMarkers.SUMMARY_ERROR = {1, 0.4, 0.4}   -- lighter red, readable on the dark box
ADRouteMarkers.SUMMARY_TEXT_SIZE = 0.012
ADRouteMarkers.COLORS = {
    [ADRouteCheck.LOOSE] = ADRouteMarkers.WARNING,
    [ADRouteCheck.DEAD_END] = ADRouteMarkers.WARNING,
    [ADRouteCheck.TRAP] = ADRouteMarkers.ERROR,
    [ADRouteCheck.UNREACHABLE] = ADRouteMarkers.ERROR,
    [ADRouteCheck.NO_WAY_BACK] = ADRouteMarkers.ERROR
}

ADRouteMarkers.changes = 0             -- changes of the network, counted by ADGraphManager:markChanges
ADRouteMarkers.lastChangeTime = 0
ADRouteMarkers.checkedChanges = nil    -- the count the problems belong to
ADRouteMarkers.problems = {}

-- every change of the network goes through markChanges (also while a waypoint is dragged)
ADGraphManager.markChanges = Utils.appendedFunction(ADGraphManager.markChanges, function()
    ADRouteMarkers.changes = ADRouteMarkers.changes + 1
    ADRouteMarkers.lastChangeTime = g_time or 0
end)

function ADRouteMarkers.isActive()
    return g_dedicatedServer == nil and AutoDrive.getSetting("showRouteProblems")
        and (AutoDrive.isEditorModeEnabled() or AutoDrive.isEditorShowEnabled())
end

local function getViewPosition(vehicle)
    local camera = getCamera ~= nil and getCamera() or nil
    if camera ~= nil and camera ~= 0 then
        return getWorldTranslation(camera)
    end
    return ADRouteCheck.getVehiclePosition(vehicle)
end

-- checks the network again once it has not changed for QUIET_TIME (not while a waypoint is dragged)
function ADRouteMarkers:update(vehicle)
    if self.checkedChanges == self.changes or g_time - self.lastChangeTime < self.QUIET_TIME then
        return
    end
    if vehicle ~= nil and vehicle.ad ~= nil and (vehicle.ad.nodeToMoveId ~= nil or vehicle.ad.keyDragNodeId ~= nil) then
        return
    end
    self.checkedChanges = self.changes
    self.problems = ADRouteCheck.analyse(ADGraphManager:getWayPoints(), ADGraphManager:getMapMarkers(), ADRouteCheck.isNearField)
end

-- the problems with their distance from x, z, nearest first
function ADRouteMarkers:getSorted(x, z)
    local sorted = {}
    for _, problem in ipairs(self.problems) do
        problem.viewDistance = MathUtil.vector2Length(problem.x - x, problem.z - z)
        table.insert(sorted, problem)
    end
    table.sort(sorted, function(a, b) return a.viewDistance < b.viewDistance end)
    return sorted
end

local function renderShadowed(x, y, size, text, r, g, b)
    setTextColor(0, 0, 0, 0.9)
    renderText(x + 0.001, y - 0.0015, size, text)
    setTextColor(r, g, b, 1)
    renderText(x, y, size, text)
end

function ADRouteMarkers:draw(vehicle)
    if not ADRouteMarkers.isActive() then
        return
    end
    self:update(vehicle)
    if #self.problems == 0 then
        return
    end
    local x, _, z = getViewPosition(vehicle)
    if x == nil then
        return
    end
    local sorted = self:getSorted(x, z)
    local pulse = 0.5 + 0.5 * math.sin(g_time / 200)
    setTextAlignment(RenderText.ALIGN_CENTER)
    setTextBold(true)
    for i, problem in ipairs(sorted) do
        if i > self.MAX_BEACONS then
            break
        end
        local r, g, b = unpack(self.COLORS[problem.kind] or self.ERROR)
        for _, point in ipairs(problem.points) do
            ADDrawingManager:addSphereTask(point.x, point.y, point.z, 2 + 2 * pulse, r, g, b, 0.6)
        end
        local top = problem.y + self.BEACON_HEIGHT
        ADDrawingManager:addLineTask(problem.x, problem.y, problem.z, problem.x, top, problem.z, 3, r, g, b)
        if i <= self.MAX_LABELS and problem.viewDistance <= self.LABEL_DISTANCE then
            local sx, sy, sz = project(problem.x, top + 1, problem.z)
            if sx ~= nil and sz ~= nil and sz > 0 and sz < 1 and sx > 0 and sx < 1 and sy > 0 and sy < 1 then
                renderShadowed(sx, sy, self.TEXT_SIZE, ADRouteCheck.getProblemText(problem), r, g, b)
            end
        end
    end

    local nearest = sorted[1]
    setTextAlignment(RenderText.ALIGN_LEFT)
    setTextBold(false)
    setTextColor(1, 1, 1, 1)

    -- the nearest one out of sight: an arrow from the vehicle towards it
    local vehicleX, vehicleY, vehicleZ = ADRouteCheck.getVehiclePosition(vehicle)
    if vehicleX ~= nil then
        local distance = MathUtil.vector2Length(nearest.x - vehicleX, nearest.z - vehicleZ)
        if distance > AutoDrive.drawDistance then
            local r, g, b = unpack(self.COLORS[nearest.kind] or self.ERROR)
            local dirX, dirZ = (nearest.x - vehicleX) / distance, (nearest.z - vehicleZ) / distance
            local startY = vehicleY + 3
            local endX, endZ = vehicleX + dirX * ADUndoManager.POINTER_LENGTH, vehicleZ + dirZ * ADUndoManager.POINTER_LENGTH
            ADDrawingManager:addLineTask(vehicleX, startY, vehicleZ, endX, startY, endZ, 2, r, g, b)
            ADDrawingManager:addArrowTask(vehicleX, startY, vehicleZ, endX, startY, endZ, 2, ADDrawingManager.arrows.position.start, r, g, b)
        end
    end
end

-- under the HUD: how many, how far the nearest one is, on a dark box. Drawn before the HUD, so the HUD's lists
-- (the target list opened downwards) cover it.
function ADRouteMarkers:drawSummary(vehicle)
    local hud = AutoDrive.Hud
    if not ADRouteMarkers.isActive() or hud == nil or hud.posX == nil then
        return
    end
    self:update(vehicle)
    if #self.problems == 0 then
        return
    end
    local x, _, z = getViewPosition(vehicle)
    if x == nil then
        return
    end
    local nearest = self:getSorted(x, z)[1]
    local text = string.format(g_i18n:getText("AD_routeMarkers_summary"), #self.problems, math.floor(nearest.viewDistance + 0.5))
    local size = self.SUMMARY_TEXT_SIZE
    local posX, posY = hud.posX, hud.posY - 0.022
    -- on a rounded dark box (ADHudStyle) as wide as the text
    local padX, padY = 0.005, 0.004
    setTextBold(true)
    ADHudStyle.roundRect(posX - padX, posY - padY, getTextWidth(size, text) + 2 * padX, size + 1.5 * padY, ADHudStyle.px(ADHudStyle.CHIP_RADIUS), ADHudStyle.C.bg)
    local color = self.COLORS[nearest.kind] == self.WARNING and self.WARNING or self.SUMMARY_ERROR
    local r, g, b = unpack(color)
    setTextAlignment(RenderText.ALIGN_LEFT)
    setTextBold(true)
    setTextColor(r, g, b, 1)
    renderText(posX, posY, size, text)
    setTextBold(false)
    setTextColor(1, 1, 1, 1)
end

function ADRouteMarkers.safeDrawSummary(vehicle)
    if ADRouteMarkers.failed then
        return
    end
    local ok, err = pcall(ADRouteMarkers.drawSummary, ADRouteMarkers, vehicle)
    if not ok then
        ADRouteMarkers.failed = true
        Logging.warning("[AD] route problems can not be shown: %s", tostring(err))
    end
end

function ADRouteMarkers.safeDraw(vehicle)
    if ADRouteMarkers.failed then
        return
    end
    local ok, err = pcall(ADRouteMarkers.draw, ADRouteMarkers, vehicle)
    if not ok then
        ADRouteMarkers.failed = true
        Logging.warning("[AD] route problems can not be shown: %s", tostring(err))
    end
end

-- big map of the menu: a square in the problem's colour
function ADRouteMarkers:drawOnMap(map)
    if map == nil or not ADRouteMarkers.isActive() or #self.problems == 0 then
        return
    end
    if self.overlay == nil then
        self.overlay = createImageOverlay("dataS/menu/base/graph_pixel.dds")
    end
    local square = self.MAP_SQUARE_PIXELS
    for _, problem in ipairs(self.problems) do
        local sx, sy = ADRoutePreview.mapPosition(map, problem.x, problem.z, false)
        if sx ~= nil then
            local r, g, b = unpack(self.COLORS[problem.kind] or self.ERROR)
            ADFleetMap.drawSquare(self.overlay, sx, sy, square + 4, 0, 0, 0, 0.9)
            ADFleetMap.drawSquare(self.overlay, sx, sy, square, r, g, b, 1)
        end
    end
end

function ADRouteMarkers.safeDrawOnMap(map)
    if ADRouteMarkers.mapFailed then
        return
    end
    local ok, err = pcall(ADRouteMarkers.drawOnMap, ADRouteMarkers, map)
    if not ok then
        ADRouteMarkers.mapFailed = true
        Logging.warning("[AD] route problems can not be shown on the map: %s", tostring(err))
    end
end

-- (the map element gets the extended draw function again in RoutePreview.lua)
if InGameMenuMapFrame ~= nil and InGameMenuMapFrame.onDrawPostIngameMap ~= nil then
    InGameMenuMapFrame.onDrawPostIngameMap = Utils.appendedFunction(InGameMenuMapFrame.onDrawPostIngameMap, function(frame, element, ingameMap)
        ADRouteMarkers.safeDrawOnMap(frame.ingameMapBase or ingameMap)
    end)
end
