-- Where a vehicle refuels: the player picks one of the refuel targets for the vehicle's fuels, or Nearest.
-- Stored per vehicle as the target's name (vehicle.ad.refuelDestination, "" = Nearest), since ids change when the
-- network is edited. Saved in the savegame, sent to joining clients with the vehicle, changed with
-- AutoDriveRefuelDestinationEvent. It replaces ADTriggerManager.getClosestRefuelDestination, so every way to a refuel
-- point uses it: the refuel button, auto refuel during AutoDrive's modes and onCpFuelEmpty (Courseplay hand-over).
-- If the chosen target can not be used (gone, no refuel point with fuel for this vehicle, no access) the vehicle goes
-- to the nearest one and the log says why.
-- Nearest: measured along the route network (one search from the vehicle's closest waypoint), straight-line if the
-- network gives nothing; a refuel point of the vehicle's own farm wins if it is at most OWN_FARM_FACTOR as far.
ADRefuelChoice = {}

ADRefuelChoice.NEAREST = ""
ADRefuelChoice.OWN_FARM_FACTOR = 1.5
ADRefuelChoice.LOG_INTERVAL = 60000     -- ms; the fallback is said once per vehicle and target in this time

function ADRefuelChoice.get(vehicle)
    if vehicle == nil or vehicle.ad == nil or vehicle.ad.refuelDestination == nil then
        return ADRefuelChoice.NEAREST
    end
    return vehicle.ad.refuelDestination
end

-- sets it here only (the event sets it everywhere)
function ADRefuelChoice.set(vehicle, name)
    if vehicle ~= nil and vehicle.ad ~= nil then
        vehicle.ad.refuelDestination = name or ADRefuelChoice.NEAREST
    end
end

local function getMarkerWayPoint(mapMarkerID)
    local marker = ADGraphManager:getMapMarkerById(mapMarkerID)
    if marker == nil then
        return nil, nil
    end
    return marker, ADGraphManager:getWayPointById(marker.id)
end

-- names of the refuel targets for the vehicle's fuels (fill level ignored), sorted
function ADRefuelChoice.getChoices(vehicle)
    local names, seen = {}, {}
    local ok, destinations = pcall(ADTriggerManager.getRefuelDestinations, vehicle, true)
    for _, item in pairs(ok and destinations or {}) do
        local marker = ADGraphManager:getMapMarkerById(item.mapMarkerID)
        if marker ~= nil and marker.name ~= nil and not seen[marker.name] then
            seen[marker.name] = true
            table.insert(names, marker.name)
        end
    end
    table.sort(names, function(a, b) return a:lower() < b:lower() end)
    return names
end

-- the farm owning a refuel trigger (its loading station or placeable), nil if not known
function ADRefuelChoice.getTriggerFarm(trigger)
    if trigger == nil then
        return nil
    end
    local source = trigger.source
    local candidates = {trigger, source, source ~= nil and source.owningPlaceable or nil, trigger.owningPlaceable}
    for i = 1, 4 do
        local object = candidates[i]
        if type(object) == "table" then
            if type(object.getOwnerFarmId) == "function" then
                local ok, farmId = pcall(object.getOwnerFarmId, object)
                if ok and farmId ~= nil then
                    return farmId
                end
            end
            if object.ownerFarmId ~= nil then
                return object.ownerFarmId
            end
        end
    end
    return nil
end

local function heapPush(heap, distance, id)
    table.insert(heap, {distance, id})
    local i = #heap
    while i > 1 do
        local parent = math.floor(i / 2)
        if heap[parent][1] <= heap[i][1] then
            break
        end
        heap[parent], heap[i] = heap[i], heap[parent]
        i = parent
    end
end

local function heapPop(heap)
    local top = heap[1]
    local last = table.remove(heap)
    if #heap > 0 then
        heap[1] = last
        local i, n = 1, #heap
        while true do
            local smallest, left, right = i, 2 * i, 2 * i + 1
            if left <= n and heap[left][1] < heap[smallest][1] then
                smallest = left
            end
            if right <= n and heap[right][1] < heap[smallest][1] then
                smallest = right
            end
            if smallest == i then
                break
            end
            heap[smallest], heap[i] = heap[i], heap[smallest]
            i = smallest
        end
    end
    return top[1], top[2]
end

-- route length from startId to each waypoint in targets (set of ids) along the network; stops once all are found
function ADRefuelChoice.getRouteDistances(startId, targets, wayPoints)
    local remaining = 0
    for _ in pairs(targets) do
        remaining = remaining + 1
    end
    local found, done, best = {}, {}, {[startId] = 0}
    local heap = {}
    heapPush(heap, 0, startId)
    while #heap > 0 and remaining > 0 do
        local distance, id = heapPop(heap)
        if not done[id] then
            done[id] = true
            if targets[id] then
                found[id] = distance
                remaining = remaining - 1
            end
            local wp = wayPoints[id]
            if wp ~= nil and wp.out ~= nil then
                for _, outId in ipairs(wp.out) do
                    local nextWp = wayPoints[outId]
                    if nextWp ~= nil and not done[outId] then
                        local newDistance = distance + MathUtil.vector2Length(nextWp.x - wp.x, nextWp.z - wp.z)
                        if best[outId] == nil or newDistance < best[outId] then
                            best[outId] = newDistance
                            heapPush(heap, newDistance, outId)
                        end
                    end
                end
            end
        end
    end
    return found
end

local function getStartWayPoint(vehicle)
    if vehicle.getClosestWayPoint ~= nil then
        local ok, id = pcall(vehicle.getClosestWayPoint, vehicle)
        if ok and id ~= nil and id > 0 then
            return id
        end
    end
    return nil
end

-- the nearest of the refuel destinations (as ADTriggerManager.getRefuelDestinations gives them), its map marker id
function ADRefuelChoice.getNearest(vehicle, destinations)
    if destinations == nil or #destinations == 0 then
        return nil
    end
    local wayPointOf = {}
    local targets = {}
    for i, item in ipairs(destinations) do
        local _, wp = getMarkerWayPoint(item.mapMarkerID)
        if wp ~= nil then
            wayPointOf[i] = wp
            targets[wp.id] = true
        end
    end

    -- by route if the network reaches at least one of them, else straight-line from the vehicle
    local routes = nil
    local startId = getStartWayPoint(vehicle)
    if startId ~= nil then
        local found = ADRefuelChoice.getRouteDistances(startId, targets, ADGraphManager:getWayPoints())
        if next(found) ~= nil then
            routes = found
        end
    end
    local x, _, z = getWorldTranslation(vehicle.components[1].node)
    local farmId = vehicle.getOwnerFarmId ~= nil and vehicle:getOwnerFarmId() or nil

    local nearest, nearestDistance, own, ownDistance = nil, math.huge, nil, math.huge
    for i, item in ipairs(destinations) do
        local wp = wayPointOf[i]
        if wp ~= nil then
            local distance
            if routes ~= nil then
                distance = routes[wp.id]
            else
                distance = MathUtil.vector2Length(wp.x - x, wp.z - z)
            end
            if distance ~= nil then
                if distance < nearestDistance then
                    nearest, nearestDistance = item, distance
                end
                local triggerFarm = ADRefuelChoice.getTriggerFarm(item.refuelTrigger)
                if farmId ~= nil and farmId ~= 0 and triggerFarm == farmId and distance < ownDistance then
                    own, ownDistance = item, distance
                end
            end
        end
    end
    local chosen = nearest
    if own ~= nil and ownDistance <= nearestDistance * ADRefuelChoice.OWN_FARM_FACTOR then
        chosen = own
    end
    if chosen == nil then
        return nil
    end
    -- of the targets at that refuel point, the one closest to it (as before)
    local result, closest = chosen.mapMarkerID, math.huge
    for i, item in ipairs(destinations) do
        if item.refuelTrigger == chosen.refuelTrigger and wayPointOf[i] ~= nil and item.distance < closest then
            result, closest = item.mapMarkerID, item.distance
        end
    end
    return result
end

local function isTarget(name)
    for _, marker in pairs(ADGraphManager:getMapMarkers()) do
        if marker.name == name then
            return true
        end
    end
    return false
end

function ADRefuelChoice.logFallback(vehicle, name)
    local now = g_time or 0
    local last = vehicle.ad.refuelFallbackLog
    if last ~= nil and last.name == name and now - last.time < ADRefuelChoice.LOG_INTERVAL then
        return
    end
    vehicle.ad.refuelFallbackLog = {name = name, time = now}
    ADDiag.refuelChoiceUnusable(vehicle, name, not isTarget(name))
end

-- the map marker id to refuel at: the chosen target, else the nearest; nil if there is none
function ADRefuelChoice.getDestination(vehicle, ignoreFillLevel)
    local destinations = ADTriggerManager.getRefuelDestinations(vehicle, ignoreFillLevel)
    local name = ADRefuelChoice.get(vehicle)
    if name ~= ADRefuelChoice.NEAREST then
        local chosen, closest = nil, math.huge
        for _, item in ipairs(destinations) do
            local marker, wp = getMarkerWayPoint(item.mapMarkerID)
            if marker ~= nil and wp ~= nil and marker.name == name and item.distance < closest then
                chosen, closest = item.mapMarkerID, item.distance
            end
        end
        if chosen ~= nil then
            return chosen
        end
        if #AutoDrive.getRequiredRefuels(vehicle, ignoreFillLevel) > 0 then
            ADRefuelChoice.logFallback(vehicle, name)
        end
    end
    return ADRefuelChoice.getNearest(vehicle, destinations)
end

-- every caller (and other mods) get the choice
ADTriggerManager.getClosestRefuelDestination = ADRefuelChoice.getDestination

-- savegame: vehicles.vehicle(?).AutoDrive#refuelDestination
function ADRefuelChoice.registerSavegameKeys(schemaSavegame)
    schemaSavegame:register(XMLValueType.STRING, "vehicles.vehicle(?).AutoDrive#refuelDestination", "AutoDrive: target name to refuel at, empty = nearest")
end

function ADRefuelChoice.loadFromXML(vehicle, xmlFile, key)
    ADRefuelChoice.set(vehicle, xmlFile:getValue(key .. "#refuelDestination"))
end

function ADRefuelChoice.saveToXML(vehicle, xmlFile, key)
    local name = ADRefuelChoice.get(vehicle)
    if name ~= ADRefuelChoice.NEAREST then
        xmlFile:setValue(key .. "#refuelDestination", name)
    end
end

-- for other mods (e.g. CourseCorrect): the target name, "" = Nearest; set it from any side, it is synced
function AutoDrive.getRefuelDestination(vehicle)
    return ADRefuelChoice.get(vehicle)
end

function AutoDrive.setRefuelDestination(vehicle, name)
    AutoDriveRefuelDestinationEvent.sendEvent(vehicle, name or ADRefuelChoice.NEAREST)
end

function AutoDrive.getRefuelDestinationChoices(vehicle)
    return ADRefuelChoice.getChoices(vehicle)
end
