-- Selecting several waypoints in the editor, like files in Windows:
--   Ctrl + Shift + left drag       draws a box, every waypoint in it is added to the selection
--   Ctrl + Shift + left click      on a waypoint adds it to or removes it from the selection
--   Ctrl + left click              the same, while something is selected (with nothing selected it still starts a
--                                  chain of new waypoints from that one)
-- When all keys and buttons are let go, a menu opens at the mouse with what can be done with the selection: move,
-- put on the ground, side road on / off, direction, tidy up, delete, deselect. Each is one undo step. A click outside
-- the menu closes it and clears the selection.
-- Shortcuts that work as well: Alt + left click on a selected waypoint deletes them all, dragging a selected waypoint
-- (Shift + left drag, or right / middle drag) moves them all.
-- Waypoint ids shift when waypoints are added or deleted, so the selection is cleared when the number of waypoints
-- changes.
ADNodeSelection = {}

ADNodeSelection.DRAG_THRESHOLD = 0.005
ADNodeSelection.ON_GROUND = 0.5        -- closer than this to the ground: a moved waypoint follows the ground
ADNodeSelection.COLOR_BOX = {1, 0.65, 0, 0.12}
ADNodeSelection.COLOR_BORDER = {1, 0.65, 0, 0.9}
ADNodeSelection.COLOR_TEXT = {1, 0.65, 0, 1}
-- the menu in the Overdrive look (ADHudStyle, colours as they look on screen)
ADNodeSelection.COLOR_BACKGROUND = ADHudStyle.C.bg
ADNodeSelection.COLOR_BUTTON = ADHudStyle.C.chip
ADNodeSelection.COLOR_HOVER = ADHudStyle.C.hover
ADNodeSelection.COLOR_ACTIVE = ADHudStyle.C.accent
ADNodeSelection.COLOR_DANGER = ADHudStyle.C.danger
ADNodeSelection.COLOR_DANGER_HOVER = ADHudStyle.C.dangerHover
ADNodeSelection.TEXT_SIZE = 0.013
ADNodeSelection.ROW_HEIGHT = 0.026
ADNodeSelection.PADDING = 0.006
ADNodeSelection.GAP = 0.004

ADNodeSelection.ids = {}               -- waypoint id -> true
ADNodeSelection.count = 0
ADNodeSelection.wayPointsCount = nil   -- number of waypoints when the selection was made
ADNodeSelection.box = nil              -- {startX, startY, x, y, active}
ADNodeSelection.menuPending = false    -- open the menu once all keys are let go
ADNodeSelection.menu = nil             -- {x, y (top left), rows, layout}
ADNodeSelection.moving = nil           -- moving with the mouse after "Move": {x, y, z} where the mouse met the ground

function ADNodeSelection:clear()
    self:cancelMove()
    self.ids = {}
    self.count = 0
    self.wayPointsCount = nil
    self.menu = nil
    self.menuPending = false
end

-- clear the selection when waypoints were added or deleted (ids shift)
function ADNodeSelection:checkValid()
    if self.count > 0 and self.wayPointsCount ~= ADGraphManager:getWayPointsCount() then
        self:clear()
    end
end

function ADNodeSelection:isSelected(id)
    return id ~= nil and self.ids[id] == true
end

function ADNodeSelection:getIds()
    local list = {}
    for id in pairs(self.ids) do
        table.insert(list, id)
    end
    table.sort(list)
    return list
end

function ADNodeSelection:add(id)
    if id ~= nil and not self.ids[id] and ADGraphManager:getWayPointById(id) ~= nil then
        self.ids[id] = true
        self.count = self.count + 1
    end
    self.wayPointsCount = ADGraphManager:getWayPointsCount()
end

function ADNodeSelection:toggle(id)
    if self.ids[id] then
        self.ids[id] = nil
        self.count = self.count - 1
    else
        self:add(id)
    end
    self.wayPointsCount = ADGraphManager:getWayPointsCount()
end

local function modifiers()
    return AutoDrive.leftCTRLmodifierKeyPressed, AutoDrive.leftLSHIFTmodifierKeyPressed, AutoDrive.leftALTmodifierKeyPressed, AutoDrive.rightSHIFTmodifierKeyPressed
end

local function anyKey()
    local ctrl, shift, alt, rightShift = modifiers()
    return ctrl or shift or alt or rightShift
end

local function text(key)
    return g_i18n:getText(key)
end

-- waypoints whose drawn position is inside the box (screen coordinates)
function ADNodeSelection:getWayPointsInBox(vehicle, x1, y1, x2, y2)
    local minX, maxX = math.min(x1, x2), math.max(x1, x2)
    local minY, maxY = math.min(y1, y2), math.max(y1, y2)
    local found = {}
    local offset = AutoDrive.drawHeight + AutoDrive.getSetting("lineHeight")
    for _, point in pairs(vehicle:getWayPointsInRange(0, AutoDrive.drawDistance)) do
        local x, y, z = project(point.x, point.y + offset, point.z)
        if x ~= nil and z ~= nil and z > 0 and z < 1 and x >= minX and x <= maxX and y >= minY and y <= maxY then
            table.insert(found, point.id)
        end
    end
    return found
end

-- the connected pairs of selected waypoints {a, b}, a < b
function ADNodeSelection:getPairs()
    local found = {}
    for _, a in ipairs(self:getIds()) do
        local wp = ADGraphManager:getWayPointById(a)
        if wp ~= nil then
            local seen = {}
            for _, list in ipairs({wp.out or {}, wp.incoming or {}}) do
                for _, b in pairs(list) do
                    if b > a and self.ids[b] and not seen[b] then
                        seen[b] = true
                        table.insert(found, {a, b})
                    end
                end
            end
        end
    end
    -- a reverse connection into a is only in the out list of the other waypoint
    for _, b in ipairs(self:getIds()) do
        local wp = ADGraphManager:getWayPointById(b)
        if wp ~= nil then
            for _, a in pairs(wp.out or {}) do
                if a < b and self.ids[a] then
                    local known = false
                    for _, pair in ipairs(found) do
                        if pair[1] == a and pair[2] == b then
                            known = true
                            break
                        end
                    end
                    if not known then
                        table.insert(found, {a, b})
                    end
                end
            end
        end
    end
    return found
end

-- the selected waypoints in order when they are one unbranched line, else nil. Turned so that most of its
-- connections already go along it.
function ADNodeSelection:getChain()
    if self.count < 2 then
        return nil
    end
    local pairList = self:getPairs()
    if #pairList ~= self.count - 1 then
        return nil
    end
    local neighbours = {}
    for _, pair in ipairs(pairList) do
        for i = 1, 2 do
            local id, other = pair[i], pair[3 - i]
            neighbours[id] = neighbours[id] or {}
            table.insert(neighbours[id], other)
        end
    end
    local start
    for id in pairs(self.ids) do
        local n = neighbours[id] ~= nil and #neighbours[id] or 0
        if n == 0 or n > 2 then
            return nil
        elseif n == 1 and (start == nil or id < start) then
            start = id
        end
    end
    if start == nil then
        return nil
    end
    local chain, previous = {start}, nil
    local current = start
    while #chain < self.count do
        local nextId
        for _, other in ipairs(neighbours[current]) do
            if other ~= previous then
                nextId = other
            end
        end
        if nextId == nil then
            return nil
        end
        table.insert(chain, nextId)
        previous, current = current, nextId
    end
    -- along the way it is mostly driven already
    local along, against = 0, 0
    for i = 1, #chain - 1 do
        local direction = ADWaypointPanel.getDirection(ADGraphManager:getWayPointById(chain[i]), ADGraphManager:getWayPointById(chain[i + 1]))
        if direction == ADWaypointPanel.OUT or direction == ADWaypointPanel.REVERSE then
            along = along + 1
        elseif direction == ADWaypointPanel.IN or direction == ADWaypointPanel.REVERSE_IN then
            against = against + 1
        end
    end
    if against > along then
        local reversed = {}
        for i = #chain, 1, -1 do
            table.insert(reversed, chain[i])
        end
        chain = reversed
    end
    return chain
end

---------------------------------------------------------------------------------------------------------------------
-- actions

function ADNodeSelection:deleteAll(vehicle)
    local ids = self:getIds()
    table.sort(ids, function(a, b) return a > b end)
    self:clear()
    if vehicle ~= nil then
        vehicle.ad.selectedNodeId = nil
    end
    AutoDriveDeleteWayPointsEvent.sendEvent(ids)
end

function ADNodeSelection:setSideRoad(on)
    ADWaypointPanel.setSideRoadOnIds(self:getIds(), on)
end

function ADNodeSelection:isSideRoad()
    local on, off = 0, 0
    for id in pairs(self.ids) do
        if ADGraphManager:getIsPointSubPrio(id) then
            on = on + 1
        else
            off = off + 1
        end
    end
    if off == 0 then
        return true
    elseif on == 0 then
        return false
    end
    return nil
end

function ADNodeSelection:setDirection(mode)
    if mode == "oneWay" then
        local chain = self:getChain()
        if chain ~= nil then
            ADWaypointPanel.setRoadDirection(chain, "oneWay")
        end
    else
        ADWaypointPanel.setPairsDirection(self:getPairs(), mode)
    end
end

function ADNodeSelection:tidy(tool)
    local chain = self:getChain()
    if chain ~= nil then
        ADWaypointPanel.tidyRoad(chain, tool)
    end
end

function ADNodeSelection:putOnGround()
    local moves = {}
    for _, id in ipairs(self:getIds()) do
        local wp = ADGraphManager:getWayPointById(id)
        if wp ~= nil then
            local y = ADTidyTools.groundHeight(wp.x, wp.y, wp.z)
            if y ~= nil and math.abs(y - wp.y) > 0.01 then
                table.insert(moves, {id = id, x = wp.x, y = y, z = wp.z, flags = wp.flags})
            end
        end
    end
    if #moves > 0 then
        ADGraphManager:moveWayPoints(moves)
    end
end

-- every selected waypoint (but skipId) moved by dx, dz from where it was before the move; on the ground they follow it
function ADNodeSelection:applyOffset(dx, dy, dz, skipId)
    for id in pairs(self.ids) do
        local point = ADGraphManager:getWayPointById(id)
        if id ~= skipId and point ~= nil then
            if point.undoOrigin == nil then
                point.undoOrigin = {x = point.x, y = point.y, z = point.z}
            end
            local origin = point.undoOrigin
            point.x, point.z = origin.x + dx, origin.z + dz
            local ground = AutoDrive:getTerrainHeightAtWorldPos(origin.x, origin.z)
            if ground ~= nil and math.abs(origin.y - ground) < self.ON_GROUND then
                point.y = AutoDrive:getTerrainHeightAtWorldPos(point.x, point.z) + (origin.y - ground)
            else
                point.y = origin.y + dy
            end
        end
    end
    ADGraphManager:markChanges()
end

-- the selected waypoints where they are now, as one move (one undo step)
function ADNodeSelection:sendMoves()
    local moves = {}
    for _, id in ipairs(self:getIds()) do
        local point = ADGraphManager:getWayPointById(id)
        if point ~= nil then
            table.insert(moves, {id = id, x = point.x, y = point.y, z = point.z, flags = point.flags})
        end
    end
    ADGraphManager:moveWayPoints(moves)
end

-- "Move": the selection follows the mouse until a click puts it down
function ADNodeSelection:startMove()
    local x, y, z = AutoDrive.getGroundUnderMouse(g_lastMousePosX, g_lastMousePosY)
    if x ~= nil then
        self.moving = {x = x, y = y, z = z}
        self.menu = nil
    end
end

function ADNodeSelection:updateMove()
    local x, _, z = AutoDrive.getGroundUnderMouse(g_lastMousePosX, g_lastMousePosY)
    if x ~= nil then
        self:applyOffset(x - self.moving.x, 0, z - self.moving.z)
    end
end

function ADNodeSelection:finishMoving()
    self.moving = nil
    self:sendMoves()
    self.menuPending = true
end

-- back to where they were (leaving the editor while moving)
function ADNodeSelection:cancelMove()
    if self.moving == nil then
        return
    end
    self.moving = nil
    for id in pairs(self.ids) do
        local point = ADGraphManager:getWayPointById(id)
        if point ~= nil and point.undoOrigin ~= nil then
            point.x, point.y, point.z = point.undoOrigin.x, point.undoOrigin.y, point.undoOrigin.z
            point.undoOrigin = nil
        end
    end
    ADGraphManager:markChanges()
end

---------------------------------------------------------------------------------------------------------------------
-- the menu

local function button(label, action, active, color, hoverColor)
    return {label = label, action = action, active = active, color = color, hoverColor = hoverColor}
end

function ADNodeSelection:getMenuRows(vehicle)
    local rows = {}
    local chain = self:getChain()
    local hasPairs = #self:getPairs() > 0
    table.insert(rows, {label = tostring(self.count) .. " " .. text("AD_nodeSelection_count"), title = true})
    table.insert(rows, {buttons = {
        button(text("AD_nodeSelection_move"), function() self:startMove() end),
        button(text("AD_nodeSelection_ground"), function() self:putOnGround() end)}})
    local sideRoad = self:isSideRoad()
    table.insert(rows, {label = text("AD_wpPanel_sideRoad"), buttons = {
        button(text("AD_wpPanel_on"), function() self:setSideRoad(true) end, sideRoad == true),
        button(text("AD_wpPanel_off"), function() self:setSideRoad(false) end, sideRoad == false)}})
    if hasPairs then
        local buttons = {}
        if chain ~= nil then
            table.insert(buttons, button(text("AD_wpPanel_oneWay"), function() self:setDirection("oneWay") end))
        end
        table.insert(buttons, button(text("AD_wpPanel_twoWay"), function() self:setDirection("twoWay") end))
        table.insert(buttons, button(text("AD_wpPanel_flip"), function() self:setDirection("flip") end))
        table.insert(rows, {label = text("AD_wpPanel_direction"), buttons = buttons})
    end
    if chain ~= nil and #chain >= 3 then
        table.insert(rows, {label = text("AD_wpPanel_tidy"), buttons = {
            button(text("AD_wpPanel_even"), function() self:tidy(ADTidyTools.EVEN) end),
            button(text("AD_wpPanel_straight"), function() self:tidy(ADTidyTools.STRAIGHTEN) end),
            button(text("AD_wpPanel_smooth"), function() self:tidy(ADTidyTools.SMOOTH) end)}})
    end
    table.insert(rows, {buttons = {
        button(text("AD_nodeSelection_delete"), function() self:deleteAll(vehicle) end, false, self.COLOR_DANGER, self.COLOR_DANGER_HOVER),
        button(text("AD_nodeSelection_deselect"), function() self:clear() end)}})
    return rows
end

-- where everything of the menu goes; the menu opens to the lower right of x, y and stays on the screen
function ADNodeSelection:layoutMenu(x, y, rows)
    local size, pad, gap, rowHeight = self.TEXT_SIZE, self.PADDING, self.GAP, self.ROW_HEIGHT
    local labelWidth = 0
    for _, row in ipairs(rows) do
        if row.label ~= nil and row.buttons ~= nil then
            labelWidth = math.max(labelWidth, getTextWidth(size, row.label) + gap * 2)
        end
    end
    local width = 0
    for _, row in ipairs(rows) do
        local w = 0
        if row.buttons ~= nil then
            w = labelWidth
            for _, b in ipairs(row.buttons) do
                b.width = getTextWidth(size, b.label) + pad * 2
                w = w + b.width + gap
            end
        else
            w = getTextWidth(size, row.label)
        end
        width = math.max(width, w)
    end
    width = width + pad * 2
    local height = #rows * rowHeight + pad * 2
    x = math.max(0, math.min(x, 1 - width))
    y = math.min(1, math.max(y, height))
    local layout = {x = x, y = y - height, width = width, height = height, buttons = {}}
    for i, row in ipairs(rows) do
        local rowY = y - pad - i * rowHeight
        row.textY = rowY + (rowHeight - size) / 2 + size * 0.15
        if row.buttons ~= nil then
            local bx = x + pad + labelWidth
            for _, b in ipairs(row.buttons) do
                b.rect = {x = bx, y = rowY + gap / 2, width = b.width, height = rowHeight - gap}
                table.insert(layout.buttons, b)
                bx = bx + b.width + gap
            end
        end
    end
    return layout
end

function ADNodeSelection:openMenu(vehicle, x, y)
    local rows = self:getMenuRows(vehicle)
    self.menu = {vehicle = vehicle, x = x, y = y, rows = rows, layout = self:layoutMenu(x, y, rows)}
end

-- after an action the menu shows what changed (side road, direction)
function ADNodeSelection:refreshMenu()
    if self.menu ~= nil then
        self:openMenu(self.menu.vehicle, self.menu.x, self.menu.y)
    end
end

local function inside(rect, x, y)
    return rect ~= nil and x ~= nil and x >= rect.x and x <= rect.x + rect.width and y >= rect.y and y <= rect.y + rect.height
end

function ADNodeSelection:getMenuButtonAt(x, y)
    if self.menu == nil then
        return nil
    end
    for _, b in ipairs(self.menu.layout.buttons) do
        if inside(b.rect, x, y) then
            return b
        end
    end
    return nil
end

---------------------------------------------------------------------------------------------------------------------
-- mouse

-- called by the editor's mouse handling once the hovered waypoint is known; returns true when the event was used
-- here and must not do anything else
function ADNodeSelection:mouseEvent(vehicle, posX, posY, isDown, isUp, button)
    if self.failed then
        return false
    end
    self:checkValid()
    local ctrl, shift, alt, rightShift = modifiers()
    local hovered = vehicle.ad.hoveredNodeId

    -- "Move" chosen: the selection follows the mouse, a left click puts it down
    if self.moving ~= nil then
        self:updateMove()
        if button == 1 and isUp then
            self:finishMoving()
        end
        return true
    end

    -- the menu: clicks on it are its own, a click without keys anywhere else closes it and clears the selection.
    -- With keys held a click goes through it (adding a waypoint below the menu to the selection).
    if self.menu ~= nil then
        if inside(self.menu.layout, posX, posY) and not anyKey() then
            if button == 1 and isUp then
                local b = self:getMenuButtonAt(posX, posY)
                if b ~= nil then
                    AutoDrive.playSample(AutoDrive.mouseClickSample, 0.45)
                    b.action()
                    if self.menu ~= nil then
                        self:refreshMenu()
                    end
                end
            end
            return true
        end
        if button == 1 and isUp and not anyKey() then
            self:clear()
            return true
        end
        if button ~= 0 then
            -- with keys: adding to the selection, the shortcuts; the menu comes back when they are let go
            self.menu = nil
            self.menuPending = true
        end
    end

    -- the box: started with Ctrl + Shift + left press, drawn while the mouse moves, used on release
    local box = self.box
    if box ~= nil then
        box.x, box.y = posX, posY
        if not box.active and MathUtil.vector2Length(posX - box.startX, posY - box.startY) > self.DRAG_THRESHOLD then
            box.active = true
        end
        if button == 1 and isUp then
            self.box = nil
            if box.active then
                for _, id in ipairs(self:getWayPointsInBox(vehicle, box.startX, box.startY, posX, posY)) do
                    self:add(id)
                end
                self.menuPending = self.count > 0
                AutoDrive.playSample(AutoDrive.selectedWayPointSample, 0.75)
                return true
            end
        elseif box.active then
            return true
        end
    end
    if button == 1 and isDown and ctrl and shift and not alt and not rightShift and vehicle.ad.nodeToMoveId == nil then
        self.box = {startX = posX, startY = posY, x = posX, y = posY, active = false}
        return false
    end

    if button ~= 1 or not isUp then
        return false
    end

    -- Ctrl + Shift + click on a waypoint, or Ctrl + click while something is selected: add or remove it
    if hovered ~= nil and ctrl and not alt and not rightShift and (shift or self.count > 0) then
        self:toggle(hovered)
        self.menuPending = self.count > 0
        vehicle.ad.selectedNodeId = nil
        vehicle.ad.newcreated = nil
        AutoDrive.playSample(AutoDrive.selectedWayPointSample, 0.75)
        return true
    end

    if self.count == 0 then
        return false
    end

    -- Alt + click on a selected waypoint: delete them all
    if alt and not ctrl and not shift and not rightShift and self:isSelected(hovered) then
        self:deleteAll(vehicle)
        return true
    end

    -- a click without keys clears the selection (on a waypoint it then selects that one as before)
    if not anyKey() then
        self:clear()
    end
    return false
end

-- while a selected waypoint is dragged: the other selected ones follow it
function ADNodeSelection:updateGroupMove(vehicle)
    local movedId = vehicle.ad.nodeToMoveId
    if movedId == nil or self.count < 2 or not self:isSelected(movedId) then
        return
    end
    local moved = ADGraphManager:getWayPointById(movedId)
    if moved == nil or moved.undoOrigin == nil then
        return
    end
    self.menu = nil
    self:applyOffset(moved.x - moved.undoOrigin.x, moved.y - moved.undoOrigin.y, moved.z - moved.undoOrigin.z, movedId)
end

-- the end of a drag: all selected waypoints moved in one step, or only the dragged one as before
function ADNodeSelection:finishMove(movedId)
    if self.count < 2 or not self:isSelected(movedId) then
        ADGraphManager:changeWayPointPosition(movedId)
        return
    end
    self:sendMoves()
    self.menuPending = true
end

---------------------------------------------------------------------------------------------------------------------
-- drawing (every frame while the HUD is shown)

local function drawFrame(x, y, width, height, thickness, r, g, b, a)
    drawFilledRect(x, y, width, thickness, r, g, b, a)
    drawFilledRect(x, y + height - thickness, width, thickness, r, g, b, a)
    drawFilledRect(x, y, thickness, height, r, g, b, a)
    drawFilledRect(x + width - thickness, y, thickness, height, r, g, b, a)
end

function ADNodeSelection:drawMenu()
    local menu = self.menu
    local l = menu.layout
    ADHudStyle.panel(l.x, l.y, l.width, l.height, 1, self.COLOR_BACKGROUND)
    local chipRadius = ADHudStyle.px(ADHudStyle.CHIP_RADIUS)
    local hoveredButton = self:getMenuButtonAt(g_lastMousePosX, g_lastMousePosY)
    setTextAlignment(RenderText.ALIGN_LEFT)
    for _, row in ipairs(menu.rows) do
        if row.label ~= nil then
            setTextBold(row.title == true)
            if row.title then
                setTextColor(unpack(self.COLOR_TEXT))
            else
                ADHudStyle.setTextColor(ADHudStyle.C.muted)
            end
            renderText(l.x + self.PADDING, row.textY, self.TEXT_SIZE, row.label)
        end
        for _, b in ipairs(row.buttons or {}) do
            local color = b.color or self.COLOR_BUTTON
            if b == hoveredButton then
                color = b.hoverColor or self.COLOR_HOVER
            elseif b.active then
                color = self.COLOR_ACTIVE
            end
            ADHudStyle.roundRect(b.rect.x, b.rect.y, b.rect.width, b.rect.height, chipRadius, color)
            ADHudStyle.setTextColor(ADHudStyle.C.text)
            setTextBold(false)
            renderText(b.rect.x + self.PADDING, row.textY, self.TEXT_SIZE, b.label)
        end
    end
    setTextBold(false)
    setTextColor(1, 1, 1, 1)
end

function ADNodeSelection:draw(vehicle)
    if not AutoDrive.isInExtendedEditorMode() then
        -- the selection is only kept while editing
        self.box = nil
        if self.count > 0 then
            self:clear()
        end
        return
    end
    self:checkValid()

    -- all keys and buttons let go after selecting: the menu opens at the mouse
    if self.menuPending and self.box == nil and self.moving == nil and not anyKey() and g_lastMousePosX ~= nil
        and (vehicle == nil or vehicle.ad == nil or vehicle.ad.nodeToMoveId == nil) then
        self.menuPending = false
        if self.count > 0 then
            self:openMenu(vehicle, g_lastMousePosX + 0.01, g_lastMousePosY - 0.01)
        end
    end

    local box = self.box
    if box ~= nil and box.active then
        local x, y = math.min(box.startX, box.x), math.min(box.startY, box.y)
        local width, height = math.abs(box.x - box.startX), math.abs(box.y - box.startY)
        drawFilledRect(x, y, width, height, unpack(self.COLOR_BOX))
        drawFrame(x, y, width, height, 0.0015, unpack(self.COLOR_BORDER))
    end
    if self.menu ~= nil then
        self:drawMenu()
    elseif self.count > 0 and g_lastMousePosX ~= nil then
        local label = tostring(self.count) .. " " .. text("AD_nodeSelection_count")
        if self.moving ~= nil then
            label = text("AD_nodeSelection_place")
        end
        setTextAlignment(RenderText.ALIGN_LEFT)
        setTextColor(unpack(self.COLOR_TEXT))
        renderText(g_lastMousePosX + 0.012, g_lastMousePosY - 0.022, self.TEXT_SIZE, label)
        setTextColor(1, 1, 1, 1)
    end
end

function ADNodeSelection.safeDraw(vehicle)
    if ADNodeSelection.failed then
        return
    end
    local ok, err = pcall(ADNodeSelection.draw, ADNodeSelection, vehicle)
    if not ok then
        ADNodeSelection.failed = true
        ADNodeSelection.menu = nil
        Logging.error("[AD] waypoint selection switched off after an error: %s", tostring(err))
    end
end
