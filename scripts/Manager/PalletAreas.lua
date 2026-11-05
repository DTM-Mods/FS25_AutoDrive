-- Taller pallet areas: the pallet triggers of selling points (and other unloading stations) are often too low for
-- pallets stacked high on a tall truck or trailer, so the top pallet stays unsold. On the server every pallet trigger
-- of an unloading station is made HEIGHT_FACTOR times as tall, once (also for stations placed later: checked every
-- CHECK_INTERVAL). Changing the scale of a physics shape needs it taken out of and put back into physics.
-- Everything it does goes to the log ("[AD] Pallet areas ...").
-- OFF for now (HEIGHT_FACTOR 1, triggers are not touched at all): setScale stretches from the trigger node's origin, so
-- a trigger box that sits away from its origin was moved as well as stretched, and rope pallets stopped selling at
-- shops (hardware store, farmers market). Needs to stretch the box upwards around its own position before it is on again.
ADPalletAreas = {}

ADPalletAreas.HEIGHT_FACTOR = 1
ADPalletAreas.CHECK_INTERVAL = 10000

ADPalletAreas.done = {}            -- trigger node -> true
ADPalletAreas.timer = 0

function ADPalletAreas:update(dt)
    if self.failed or self.HEIGHT_FACTOR == 1 then
        return
    end
    self.timer = self.timer - dt
    if self.timer > 0 then
        return
    end
    self.timer = self.CHECK_INTERVAL
    if g_currentMission == nil or g_currentMission.storageSystem == nil or g_currentMission.storageSystem.getUnloadingStations == nil then
        return
    end
    local ok, err = pcall(ADPalletAreas.enlargeAll)
    if not ok then
        self.failed = true
        Logging.warning("[AD] Pallet areas: could not make them taller, left as they are: %s", tostring(err))
    end
end

-- is this trigger one that takes pallets?
function ADPalletAreas.isPalletTrigger(trigger)
    if type(trigger) ~= "table" then
        return false
    end
    if PalletUnloadTrigger ~= nil and trigger.isa ~= nil then
        local ok, isPallet = pcall(trigger.isa, trigger, PalletUnloadTrigger)
        if ok and isPallet then
            return true
        end
    end
    return false
end

-- the pallet triggers of a station: in its unload triggers, or below them
function ADPalletAreas.getPalletTriggers(station)
    local found, seen = {}, {}
    local function add(trigger)
        if ADPalletAreas.isPalletTrigger(trigger) and not seen[trigger] then
            seen[trigger] = true
            table.insert(found, trigger)
        end
    end
    for _, list in ipairs({station.unloadTriggers or {}, station.palletTriggers or {}}) do
        for _, trigger in pairs(list) do
            add(trigger)
            if type(trigger) == "table" then
                add(trigger.palletTrigger)
                for _, sub in pairs(trigger.palletTriggers or {}) do
                    add(sub)
                end
            end
        end
    end
    return found
end

function ADPalletAreas.getNode(trigger)
    return trigger.triggerNode or trigger.palletTriggerNode
end

function ADPalletAreas.enlarge(node)
    if node == nil or ADPalletAreas.done[node] or (entityExists ~= nil and not entityExists(node)) then
        return false
    end
    ADPalletAreas.done[node] = true
    local sx, sy, sz = getScale(node)
    removeFromPhysics(node)
    setScale(node, sx, sy * ADPalletAreas.HEIGHT_FACTOR, sz)
    addToPhysics(node)
    return true, sy, sy * ADPalletAreas.HEIGHT_FACTOR
end

local function className(object)
    if ClassUtil ~= nil and ClassUtil.getClassNameByObject ~= nil then
        local ok, name = pcall(ClassUtil.getClassNameByObject, object)
        if ok and name ~= nil then
            return name
        end
    end
    return "?"
end

function ADPalletAreas.reportStations()
    local stations = 0
    for _, station in pairs(g_currentMission.storageSystem:getUnloadingStations()) do
        stations = stations + 1
        if stations <= 8 then
            local classes = {}
            for key, trigger in pairs(station.unloadTriggers or {}) do
                if type(trigger) == "table" then
                    local fields = {}
                    for k, v in pairs(trigger) do
                        if type(v) == "number" and string.find(string.lower(tostring(k)), "node") then
                            table.insert(fields, tostring(k))
                        end
                    end
                    table.insert(classes, className(trigger) .. "(" .. table.concat(fields, ",") .. ")")
                end
            end
            Logging.info("[AD] Pallet areas: no pallet trigger found; %s (%s) has unload triggers: %s",
                tostring(station.getName ~= nil and station:getName() or "?"), className(station), table.concat(classes, " "))
        end
    end
    Logging.info("[AD] Pallet areas: %d unloading stations, PalletUnloadTrigger class %s", stations, tostring(PalletUnloadTrigger ~= nil))
end

function ADPalletAreas.enlargeAll()
    local count = 0
    for _, station in pairs(g_currentMission.storageSystem:getUnloadingStations()) do
        for _, trigger in ipairs(ADPalletAreas.getPalletTriggers(station)) do
            local node = ADPalletAreas.getNode(trigger)
            local changed, before, after = ADPalletAreas.enlarge(node)
            if changed then
                count = count + 1
                local name = station.getName ~= nil and station:getName() or "?"
                Logging.info("[AD] Pallet areas: %s, pallet trigger %s made taller (height scale %.2f -> %.2f)",
                    tostring(name), tostring(getName ~= nil and getName(node) or node), before, after)
            end
        end
    end
    if count > 0 then
        Logging.info("[AD] Pallet areas: %d pallet trigger(s) made %d times as tall", count, ADPalletAreas.HEIGHT_FACTOR)
    elseif not ADPalletAreas.reported and next(ADPalletAreas.done) == nil then
        -- none found at all: say once what the stations have, to find the pallet triggers
        ADPalletAreas.reported = true
        ADPalletAreas.reportStations()
    end
    return count
end
