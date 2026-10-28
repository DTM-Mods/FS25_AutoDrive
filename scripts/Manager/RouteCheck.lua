-- Route check: finds problems in the route network that the single waypoint checks of the
-- road network debug markers can not see, e.g. targets that can not be reached.
-- The check only reads the network, it runs on every machine and changes nothing.

ADRouteCheck = {}

ADRouteCheck.LOOSE = 1 -- waypoint without any connection
ADRouteCheck.DEAD_END = 2 -- waypoint without outgoing connection (and without target)
ADRouteCheck.TRAP = 3 -- part of the network that can be entered but not left
ADRouteCheck.UNREACHABLE = 4 -- target that can not be reached from the main network
ADRouteCheck.NO_WAY_BACK = 5 -- target from which the main network can not be reached

ADRouteCheck.KIND_TEXTS = {
    [ADRouteCheck.LOOSE] = "AD_routeCheck_loose",
    [ADRouteCheck.DEAD_END] = "AD_routeCheck_deadEnd",
    [ADRouteCheck.TRAP] = "AD_routeCheck_trap",
    [ADRouteCheck.UNREACHABLE] = "AD_routeCheck_unreachable",
    [ADRouteCheck.NO_WAY_BACK] = "AD_routeCheck_noWayBack"
}

-- at most this many problems are listed, the nearest first
ADRouteCheck.MAX_PROBLEMS = 500
-- points highlighted for one problem, e.g. a trap
ADRouteCheck.MAX_PROBLEM_POINTS = 60

-- strongly connected components of the network (iterative Tarjan, the network can have 50k waypoints)
-- returns component per waypoint id and the number of components
function ADRouteCheck.findComponents(wayPoints)
    local index, low, onStack, component, edgePosition = {}, {}, {}, {}, {}
    local stack, stackSize = {}, 0
    local callStack = {}
    local counter, componentCount = 0, 0

    for root = 1, #wayPoints do
        if index[root] == nil then
            counter = counter + 1
            index[root], low[root] = counter, counter
            stackSize = stackSize + 1
            stack[stackSize] = root
            onStack[root] = true
            edgePosition[root] = 1
            local depth = 1
            callStack[1] = root

            while depth > 0 do
                local v = callStack[depth]
                local out = wayPoints[v].out
                local position = edgePosition[v]
                if position <= #out then
                    edgePosition[v] = position + 1
                    local w = out[position]
                    if wayPoints[w] ~= nil then
                        if index[w] == nil then
                            counter = counter + 1
                            index[w], low[w] = counter, counter
                            stackSize = stackSize + 1
                            stack[stackSize] = w
                            onStack[w] = true
                            edgePosition[w] = 1
                            depth = depth + 1
                            callStack[depth] = w
                        elseif onStack[w] and index[w] < low[v] then
                            low[v] = index[w]
                        end
                    end
                else
                    if low[v] == index[v] then
                        componentCount = componentCount + 1
                        local w
                        repeat
                            w = stack[stackSize]
                            stack[stackSize] = nil
                            stackSize = stackSize - 1
                            onStack[w] = nil
                            component[w] = componentCount
                        until w == v
                    end
                    callStack[depth] = nil
                    depth = depth - 1
                    if depth > 0 then
                        local u = callStack[depth]
                        if low[v] < low[u] then
                            low[u] = low[v]
                        end
                    end
                end
            end
        end
    end
    return component, componentCount
end

-- all waypoints reachable from the start ids, following the given adjacency (id -> list of ids)
function ADRouteCheck.reachable(startIds, adjacency)
    local seen = {}
    local queue, head = {}, 1
    for _, id in ipairs(startIds) do
        if not seen[id] then
            seen[id] = true
            table.insert(queue, id)
        end
    end
    while head <= #queue do
        local id = queue[head]
        head = head + 1
        local next = adjacency[id]
        if next ~= nil then
            for _, w in ipairs(next) do
                if not seen[w] then
                    seen[w] = true
                    queue[#queue + 1] = w
                end
            end
        end
    end
    return seen
end

-- runs all checks, returns the list of problems:
-- {kind, wayPointId, x, y, z, count, name, distance, points = {{x, y, z}, ...}}
function ADRouteCheck.analyse(wayPoints, mapMarkers)
    local problems = {}
    local function point(id)
        local wp = wayPoints[id]
        return {x = wp.x, y = wp.y, z = wp.z}
    end
    local function addProblem(kind, id, extra)
        local wp = wayPoints[id]
        local problem = {kind = kind, wayPointId = id, x = wp.x, y = wp.y, z = wp.z, points = {point(id)}}
        if extra ~= nil then
            for k, v in pairs(extra) do
                problem[k] = v
            end
        end
        table.insert(problems, problem)
        return problem
    end

    -- incoming connections, built from the outgoing ones (they include reverse connections)
    local incoming = {}
    for id, wp in ipairs(wayPoints) do
        for _, outId in ipairs(wp.out) do
            if wayPoints[outId] ~= nil then
                if incoming[outId] == nil then
                    incoming[outId] = {}
                end
                table.insert(incoming[outId], id)
            end
        end
    end

    local markersOnWayPoint = {}
    for _, marker in pairs(mapMarkers) do
        if marker.isADDebug ~= true and marker.id ~= nil and wayPoints[marker.id] ~= nil then
            if markersOnWayPoint[marker.id] == nil then
                markersOnWayPoint[marker.id] = {}
            end
            table.insert(markersOnWayPoint[marker.id], marker)
        end
    end

    -- single waypoints
    for id, wp in ipairs(wayPoints) do
        local hasOut = false
        for _, outId in ipairs(wp.out) do
            if wayPoints[outId] ~= nil and outId ~= id then
                hasOut = true
                break
            end
        end
        if not hasOut then
            if incoming[id] == nil then
                addProblem(ADRouteCheck.LOOSE, id)
            elseif markersOnWayPoint[id] == nil then
                addProblem(ADRouteCheck.DEAD_END, id)
            end
        end
    end

    -- reachability: the main network is the part with the most targets
    local component, componentCount = ADRouteCheck.findComponents(wayPoints)
    local size, targetCount = {}, {}
    for c = 1, componentCount do
        size[c], targetCount[c] = 0, 0
    end
    for id = 1, #wayPoints do
        local c = component[id]
        size[c] = size[c] + 1
        if markersOnWayPoint[id] ~= nil then
            targetCount[c] = targetCount[c] + #markersOnWayPoint[id]
        end
    end
    local main
    for c = 1, componentCount do
        if main == nil or targetCount[c] > targetCount[main] or (targetCount[c] == targetCount[main] and size[c] > size[main]) then
            main = c
        end
    end

    if main ~= nil then
        local mainIds = {}
        local out = {}
        for id, wp in ipairs(wayPoints) do
            out[id] = wp.out
            if component[id] == main then
                table.insert(mainIds, id)
            end
        end
        local fromMain = ADRouteCheck.reachable(mainIds, out)
        local toMain = ADRouteCheck.reachable(mainIds, incoming)

        for id, markers in pairs(markersOnWayPoint) do
            if component[id] ~= main then
                for _, marker in ipairs(markers) do
                    if not fromMain[id] then
                        addProblem(ADRouteCheck.UNREACHABLE, id, {name = marker.name, noWayBack = not toMain[id]})
                    elseif not toMain[id] then
                        addProblem(ADRouteCheck.NO_WAY_BACK, id, {name = marker.name})
                    end
                end
            end
        end

        -- traps: parts that can be entered from the main network, but have no way out
        local leaves, entry = {}, {}
        for id, wp in ipairs(wayPoints) do
            local c = component[id]
            for _, outId in ipairs(wp.out) do
                local target = component[outId]
                if target ~= nil and target ~= c then
                    leaves[c] = true
                    if fromMain[id] and entry[target] == nil then
                        entry[target] = outId
                    end
                end
            end
        end
        local members = {}
        for id = 1, #wayPoints do
            local c = component[id]
            if c ~= main and not leaves[c] and entry[c] ~= nil and size[c] > 1 then
                if members[c] == nil then
                    members[c] = {}
                end
                table.insert(members[c], id)
            end
        end
        for c, ids in pairs(members) do
            local problem = addProblem(ADRouteCheck.TRAP, entry[c], {count = #ids})
            local step = math.max(1, math.floor(#ids / ADRouteCheck.MAX_PROBLEM_POINTS))
            for i = 1, #ids, step do
                if ids[i] ~= entry[c] and #problem.points < ADRouteCheck.MAX_PROBLEM_POINTS then
                    table.insert(problem.points, point(ids[i]))
                end
            end
        end
    end

    return problems
end

-- counts per kind
function ADRouteCheck.countKinds(problems)
    local counts = {}
    for kind = 1, #ADRouteCheck.KIND_TEXTS do
        counts[kind] = 0
    end
    for _, problem in ipairs(problems) do
        counts[problem.kind] = counts[problem.kind] + 1
    end
    return counts
end

-- sorts by distance from x, z and keeps the nearest MAX_PROBLEMS
function ADRouteCheck.sortByDistance(problems, x, z)
    for _, problem in ipairs(problems) do
        problem.distance = MathUtil.vector2Length(problem.x - x, problem.z - z)
    end
    table.sort(problems, function(a, b)
        if a.distance ~= b.distance then
            return a.distance < b.distance
        end
        return a.wayPointId < b.wayPointId
    end)
    while #problems > ADRouteCheck.MAX_PROBLEMS do
        table.remove(problems)
    end
    return problems
end

function ADRouteCheck.getProblemText(problem)
    local text = g_i18n:getText(ADRouteCheck.KIND_TEXTS[problem.kind])
    if problem.kind == ADRouteCheck.TRAP then
        return string.format(text, problem.count)
    elseif problem.kind == ADRouteCheck.UNREACHABLE then
        if problem.noWayBack then
            return string.format(g_i18n:getText("AD_routeCheck_isolated"), problem.name)
        end
        return string.format(text, problem.name)
    elseif problem.kind == ADRouteCheck.NO_WAY_BACK then
        return string.format(text, problem.name)
    end
    return text
end

-------------------------------------------------------------------------------
-- in game: list of problems, the chosen one is shown with a beacon and a pointer
-------------------------------------------------------------------------------

ADRouteCheck.SHOW_DURATION = 120000
ADRouteCheck.SHOW_COLOR = {1, 0.15, 0.15}
ADRouteCheck.KIND_ICONS = {
    [ADRouteCheck.LOOSE] = "ad_gui.warn_icon",
    [ADRouteCheck.DEAD_END] = "ad_gui.warn_icon",
    [ADRouteCheck.TRAP] = "ad_gui.error_icon",
    [ADRouteCheck.UNREACHABLE] = "ad_gui.error_icon",
    [ADRouteCheck.NO_WAY_BACK] = "ad_gui.error_icon"
}

function ADRouteCheck.getVehiclePosition(vehicle)
    if vehicle ~= nil and vehicle.components ~= nil then
        return getWorldTranslation(vehicle.components[1].node)
    end
    return nil
end

function ADRouteCheck:run(vehicle)
    local x, _, z = ADRouteCheck.getVehiclePosition(vehicle)
    local problems = ADRouteCheck.analyse(ADGraphManager:getWayPoints(), ADGraphManager:getMapMarkers())
    self.counts = ADRouteCheck.countKinds(problems)
    self.total = #problems
    self.problems = ADRouteCheck.sortByDistance(problems, x or 0, z or 0)
    return self.problems
end

-- key: checks the network and opens the list
function ADRouteCheck:open(vehicle)
    if g_dedicatedServer ~= nil or vehicle == nil then
        return
    end
    local count = ADGraphManager:getWayPointsCount()
    if count == 0 then
        return
    end
    self:run(vehicle)
    if self.total == 0 then
        self.shown = nil
        ADMessagesManager:addMessage(nil, ADMessagesManager.messageTypes.INFO, string.format(g_i18n:getText("AD_routeCheck_none"), count), 5000)
        return
    end
    AutoDrive.onOpenRouteCheck()
end

function ADRouteCheck:getTitle()
    return string.format(g_i18n:getText("AD_routeCheck_title"), self.total or 0)
end

function ADRouteCheck:getRowText(problem)
    return string.format("%s  (%d m)", ADRouteCheck.getProblemText(problem), math.floor(problem.distance + 0.5))
end

function ADRouteCheck:show(problem, vehicle)
    self.shown = {problem = problem, endTime = g_time + ADRouteCheck.SHOW_DURATION}
    local x, _, z = ADRouteCheck.getVehiclePosition(vehicle)
    local distance = problem.distance
    if x ~= nil then
        distance = MathUtil.vector2Length(problem.x - x, problem.z - z)
    end
    local text = string.format(g_i18n:getText("AD_routeCheck_shown"), ADRouteCheck.getProblemText(problem), math.floor(distance + 0.5))
    ADMessagesManager:addMessage(nil, ADMessagesManager.messageTypes.INFO, text, 6000)
end

-- called while drawing the vehicle the player is in
function ADRouteCheck:draw(vehicle)
    local shown = self.shown
    if shown == nil then
        return
    end
    if g_time > shown.endTime then
        self.shown = nil
        return
    end
    local r, g, b = unpack(ADRouteCheck.SHOW_COLOR)
    local pulse = 0.5 + 0.5 * math.sin(g_time / 150)
    for _, point in ipairs(shown.problem.points) do
        ADDrawingManager:addSphereTask(point.x, point.y, point.z, 3 + 3 * pulse, r, g, b, 0.5)
        ADDrawingManager:addLineTask(point.x, point.y, point.z, point.x, point.y + 2 * ADUndoManager.HIGHLIGHT_BEACON_HEIGHT, point.z, 2, r, g, b)
    end

    local vehicleX, vehicleY, vehicleZ = ADRouteCheck.getVehiclePosition(vehicle)
    if vehicleX == nil then
        return
    end
    local problem = shown.problem
    local distance = MathUtil.vector2Length(problem.x - vehicleX, problem.z - vehicleZ)
    if distance > AutoDrive.drawDistance then
        -- out of sight: point from the vehicle towards it
        local dirX, dirZ = (problem.x - vehicleX) / distance, (problem.z - vehicleZ) / distance
        local length = ADUndoManager.POINTER_LENGTH
        local startY = vehicleY + 3
        local endX, endZ = vehicleX + dirX * length, vehicleZ + dirZ * length
        ADDrawingManager:addLineTask(vehicleX, startY, vehicleZ, endX, startY, endZ, 2, r, g, b)
        ADDrawingManager:addArrowTask(vehicleX, startY, vehicleZ, endX, startY, endZ, 2, ADDrawingManager.arrows.position.start, r, g, b)
    end
end

function ADRouteCheck:hide()
    self.shown = nil
end

-------------------------------------------------------------------------------
-- fixes: delete a loose waypoint, connect a dead end to the waypoint ahead where the road goes on.
-- One undo step each (AutoDriveRouteFixEvent)
-------------------------------------------------------------------------------

ADRouteCheck.FIX_DELETE = 1
ADRouteCheck.FIX_CONNECT = 3
-- a dead end is connected to a waypoint at most this far away, ahead: at most CONNECT_ANGLE degrees off the
-- direction the road arrives in (or right on top of the dead end), not one of the last BEHIND_STEPS waypoints
-- before it (the road curving round)
ADRouteCheck.CONNECT_RANGE = 30
ADRouteCheck.CONNECT_ANGLE = 60
ADRouteCheck.ON_TOP = 0.5
ADRouteCheck.BEHIND_STEPS = 3
-- how long the waypoints of a fix flash in the editor (the list may still be open)
ADRouteCheck.FIX_HIGHLIGHT_DURATION = 20000

local function isAt(wp, point)
    return wp ~= nil and point ~= nil and math.abs(wp.x - point.x) < 0.01 and math.abs(wp.z - point.z) < 0.01
end

-- the waypoint a dead end is best continued to, and how far away: the nearest one that leads on somewhere, lies
-- ahead and is not part of the road behind the dead end. (Taking just the nearest one connected the dead end back
-- onto its own road: a U-turn drawn on top of the road, it looked as if nothing had happened.)
function ADRouteCheck.findContinuation(wp, wayPoints)
    -- connections into each waypoint, also reverse ones (only in the out list of the other waypoint)
    local into = {}
    for id, candidate in ipairs(wayPoints) do
        for _, outId in ipairs(candidate.out) do
            if into[outId] == nil then
                into[outId] = {}
            end
            table.insert(into[outId], id)
        end
    end
    -- the direction the road arrives in
    local headingX, headingZ = 0, 0
    for _, fromId in ipairs(into[wp.id] or {}) do
        local from = wayPoints[fromId]
        local length = MathUtil.vector2Length(wp.x - from.x, wp.z - from.z)
        if length > 0.01 then
            headingX, headingZ = headingX + (wp.x - from.x) / length, headingZ + (wp.z - from.z) / length
        end
    end
    local headingLength = MathUtil.vector2Length(headingX, headingZ)
    if headingLength < 0.01 then
        return nil
    end
    headingX, headingZ = headingX / headingLength, headingZ / headingLength
    -- the road behind: waypoints that lead to the dead end within BEHIND_STEPS
    local behind = {[wp.id] = true}
    local front = {wp.id}
    for _ = 1, ADRouteCheck.BEHIND_STEPS do
        local nextFront = {}
        for _, id in ipairs(front) do
            for _, fromId in ipairs(into[id] or {}) do
                if not behind[fromId] then
                    behind[fromId] = true
                    table.insert(nextFront, fromId)
                end
            end
        end
        if #nextFront == 0 then
            break
        end
        front = nextFront
    end
    local minCos = math.cos(math.rad(ADRouteCheck.CONNECT_ANGLE))
    local best, bestDistance = nil, ADRouteCheck.CONNECT_RANGE
    for id, candidate in ipairs(wayPoints) do
        if not behind[id] and #candidate.out > 0 then
            local dx, dz = candidate.x - wp.x, candidate.z - wp.z
            local distance = MathUtil.vector2Length(dx, dz)
            if distance < bestDistance and (distance < ADRouteCheck.ON_TOP or (dx * headingX + dz * headingZ) / distance >= minCos) then
                best, bestDistance = candidate, distance
            end
        end
    end
    return best, bestDistance
end

-- the fix for a problem as {type, a, b}, or nil and the text key of the reason
function ADRouteCheck.getFix(problem, wayPoints, mapMarkers)
    local wp = wayPoints[problem.wayPointId]
    if not isAt(wp, problem) then
        return nil, "AD_routeCheck_fixOutdated"
    end
    if problem.kind == ADRouteCheck.LOOSE then
        return {type = ADRouteCheck.FIX_DELETE, a = wp.id}
    elseif problem.kind == ADRouteCheck.DEAD_END then
        local continuation, distance = ADRouteCheck.findContinuation(wp, wayPoints)
        if continuation == nil then
            return nil, "AD_routeCheck_fixNoNeighbour"
        end
        return {type = ADRouteCheck.FIX_CONNECT, a = wp.id, b = continuation.id, distance = distance}
    end
    return nil, "AD_routeCheck_fixNotPossible"
end

-- applies a fix with the network functions that do not send events (the server inside one undo step,
-- the clients when the server tells them)
function ADRouteCheck.applyFix(fixType, a, b)
    local gm = ADGraphManager
    if fixType == ADRouteCheck.FIX_DELETE then
        gm:removeWayPoint(a, false)
    elseif fixType == ADRouteCheck.FIX_CONNECT then
        local from, to = gm:getWayPointById(a), gm:getWayPointById(b)
        if from ~= nil and to ~= nil then
            gm:setConnectionBetween(from, to, 1, false)
        end
    end
end

-- list button: fix the problem (the list is checked again shortly after)
function ADRouteCheck:fix(problem)
    local fix, reason = ADRouteCheck.getFix(problem, ADGraphManager:getWayPoints(), ADGraphManager:getMapMarkers())
    if fix == nil then
        ADMessagesManager:addMessage(nil, ADMessagesManager.messageTypes.WARN, g_i18n:getText(reason), 5000)
        return false
    end
    local wp = ADGraphManager:getWayPointById(fix.a)
    local points = {{x = wp.x, y = wp.y, z = wp.z, kind = ADUndoManager.HIGHLIGHT_CHANGED}}
    if fix.type == ADRouteCheck.FIX_DELETE then
        points[1].kind = ADUndoManager.HIGHLIGHT_REMOVED
        Logging.info("[AD] Route check fix: loose waypoint %d deleted", fix.a)
    else
        local target = ADGraphManager:getWayPointById(fix.b)
        table.insert(points, {x = target.x, y = target.y, z = target.z, kind = ADUndoManager.HIGHLIGHT_ADDED})
        Logging.info("[AD] Route check fix: dead end %d connected to waypoint %d, %.1f m ahead", fix.a, fix.b, fix.distance or 0)
    end
    AutoDriveRouteFixEvent.sendEvent(fix.type, fix.a, fix.b)
    -- show what changed: the waypoints flash in the editor
    ADUndoManager:setHighlights(points)
    if ADUndoManager.highlights ~= nil then
        ADUndoManager.highlights.endTime = g_time + ADRouteCheck.FIX_HIGHLIGHT_DURATION
    end
    ADMessagesManager:addMessage(nil, ADMessagesManager.messageTypes.INFO, string.format(g_i18n:getText("AD_routeCheck_fixed"), ADRouteCheck.getProblemText(problem)), 4000)
    return true
end
