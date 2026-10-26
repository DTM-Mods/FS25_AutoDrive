-- Strapped load: pallets and bales held by the game's tension belts (not APalletAutoLoader; on Universal Autoload
-- vehicles only what Autoload does not track itself, e.g. put on by forklift and strapped with L). AutoDrive used to see nothing on such a trailer: the run
-- ended on arrival at the selling point and nothing was sold while the belts stayed shut.
--
--   * counted as load (AutoDrive.getObjectFillLevels, for units without a tippable load of their own): the amount
--     of the strapped pallets / bales, and as "full": strapping the load means it is ready to go
--   * best price and the unload products dialog see the products
--   * at the unload target only the pallets / bales of the products unloaded there (vehicle list, target list, best
--     price stop) are released from the belts, one by one (TensionBelts:freeTensionBeltObject: joint off, sellable
--     again); the belts stay closed and everything else stays locked, and locked objects cannot be sold
--     (lockTensionBeltObject sets setCanBeSold(false)). So it does not matter where on the trailer a product sits.
--     The stop is done when everything released is sold or nothing has been sold for SETTLE_TIME; what was released
--     and not taken is locked again (refreshTensionBelts) before driving on.
--   * without freeTensionBeltObject (another game version) the belts of a whole trailer are opened instead
ADStrappedLoad = {}

ADStrappedLoad.SETTLE_TIME = 5000      -- ms without a sale before the stop is done
ADStrappedLoad.MAX_TIME = 60000        -- ms at most at one stop

-- a pallet or a bale (the same test as Universal Autoload); vehicles, logs etc. strapped on a trailer are no load
function ADStrappedLoad.isSellable(object)
    if type(object) ~= "table" or object.isDeleted then
        return false
    end
    if object.isRoundbale ~= nil then
        return true
    end
    local specs = object.specializationsByName
    return specs ~= nil and specs.pallet ~= nil and specs.fillUnit ~= nil
end

-- may AutoDrive handle the strapped objects of this unit? Not on APalletAutoLoader trailers (own unloading). On a
-- Universal Autoload vehicle only the objects Autoload does not track itself (put on by forklift and strapped with
-- the game's belts), see isTrackedByAutoload.
function ADStrappedLoad.handlesUnit(unit)
    return unit ~= nil and unit.spec_tensionBelts ~= nil and unit.spec_tensionBelts.objectsToJoint ~= nil
        and unit.spec_aPalletAutoLoader == nil
end

-- with AutoDrive's Autoload unload position "off" Autoload never sets pallets down, so AutoDrive also releases the
-- ones Autoload tracks (put on by forklift, Autoload adds them to its list); with center / left / behind / right
-- Autoload's own unloading handles them
function ADStrappedLoad.releasesTracked(vehicle)
    return AutoDrive.getSetting ~= nil and AutoDrive.getSetting("ALUnload", vehicle) == 0
end

function ADStrappedLoad.isTrackedByAutoload(unit, object)
    local ual = unit.spec_universalAutoload
    return ual ~= nil and ual.loadedObjects ~= nil and ual.loadedObjects[object] ~= nil
end

-- the sellable objects held by the trailer's belts (only while they are fastened)
function ADStrappedLoad.getObjects(unit)
    local objects = {}
    if not ADStrappedLoad.handlesUnit(unit) then
        return objects
    end
    local seen = {}
    for _, data in pairs(unit.spec_tensionBelts.objectsToJoint) do
        local object = type(data) == "table" and data.object or nil
        if object ~= nil and not seen[object] and ADStrappedLoad.isSellable(object) and not ADStrappedLoad.isTrackedByAutoload(unit, object) then
            seen[object] = true
            table.insert(objects, object)
        end
    end
    return objects
end

-- fill type -> litres of the strapped load of one unit
function ADStrappedLoad.getLoad(unit)
    local load = {}
    for _, object in ipairs(ADStrappedLoad.getObjects(unit)) do
        local fillType, litres = ADUnloadFilter.getObjectProduct(object)
        if fillType ~= nil and fillType ~= FillType.UNKNOWN then
            load[fillType] = (load[fillType] or 0) + (litres or 0)
        end
    end
    return load
end

function ADStrappedLoad.getLitres(unit)
    local total = 0
    for _, litres in pairs(ADStrappedLoad.getLoad(unit)) do
        total = total + litres
    end
    return total
end

local function isGone(object)
    if object.isDeleted then
        return true
    end
    local node = object.rootNode or object.nodeId
    return node ~= nil and entityExists ~= nil and not entityExists(node)
end

-- UnloadAtDestinationTask at the target (server): releases what is sold here and waits while the selling point
-- takes it. Returns true while it holds the vehicle.
function ADStrappedLoad.updateStop(task, dt)
    local vehicle = task.vehicle
    local stop = task.strappedStop
    if stop == nil then
        stop = {units = {}, objects = {}, opened = {}, done = false, started = g_time, lastChange = g_time}
        task.strappedStop = stop
        for _, unit in ipairs(AutoDrive.getAllUnits(vehicle) or {}) do
            ADStrappedLoad.releaseForStop(vehicle, unit, stop)
        end
        ADStrappedLoad.describe(vehicle, "at the unload target")
        stop.left = #stop.objects
        stop.done = #stop.objects == 0
        if not stop.done then
            Logging.info("[AD] %s: released %d pallets / bales to sell here (%d trailer(s) opened completely)",
                tostring(vehicle.ad.stateModule:getName()), #stop.objects, #stop.opened)
        end
    end
    if stop.done then
        return false
    end

    local left = 0
    for _, object in ipairs(stop.objects) do
        if not isGone(object) then
            left = left + 1
        end
    end
    if left ~= stop.left then
        stop.left = left
        stop.lastChange = g_time
    end
    if left == 0 or g_time - stop.lastChange >= ADStrappedLoad.SETTLE_TIME or g_time - stop.started >= ADStrappedLoad.MAX_TIME then
        ADStrappedLoad.relock(stop)
        Logging.info("[AD] %s: %d of %d pallets / bales sold here", tostring(vehicle.ad.stateModule:getName()), #stop.objects - left, #stop.objects)
        stop.done = true
        return false
    end
    vehicle.ad.specialDrivingModule.motorShouldNotBeStopped = true
    ADGroundUnload.hold(vehicle, dt)
    return true
end

-- one unit: release the objects of the products sold here (or, without freeTensionBeltObject, open all its belts
-- when one of its products is sold here)
function ADStrappedLoad.releaseForStop(vehicle, unit, stop)
    if not ADStrappedLoad.handlesUnit(unit) then
        return
    end
    local belts = unit.spec_tensionBelts
    -- collect first, freeing changes objectsToJoint
    local toRelease, seen = {}, {}
    for objectId, data in pairs(belts.objectsToJoint) do
        local object = type(data) == "table" and data.object or nil
        if object ~= nil and ADStrappedLoad.isSellable(object)
            and (not ADStrappedLoad.isTrackedByAutoload(unit, object) or ADStrappedLoad.releasesTracked(vehicle)) then
            local fillType = ADUnloadFilter.getObjectProduct(object)
            if fillType ~= nil and ADUnloadFilter.allowsProduct(vehicle, fillType) then
                table.insert(toRelease, {objectId = objectId, object = object})
            end
        end
    end
    if #toRelease == 0 then
        return
    end
    if unit.freeTensionBeltObject ~= nil then
        for _, entry in ipairs(toRelease) do
            unit:freeTensionBeltObject(entry.objectId, belts.objectsToJoint, true, entry.object)
            if not seen[entry.object] then
                seen[entry.object] = true
                table.insert(stop.objects, entry.object)
            end
        end
        table.insert(stop.units, unit)
    elseif unit.setAllTensionBeltsActive ~= nil then
        for _, object in ipairs(ADStrappedLoad.getObjects(unit)) do
            table.insert(stop.objects, object)
        end
        unit:setAllTensionBeltsActive(false, false)
        table.insert(stop.opened, unit)
    end
end

-- before driving on: lock again what was released and not taken
function ADStrappedLoad.relock(stop)
    for _, unit in ipairs(stop.units) do
        if not unit.isDeleted and unit.refreshTensionBelts ~= nil then
            unit:refreshTensionBelts()
        end
    end
    for _, unit in ipairs(stop.opened) do
        if not unit.isDeleted and unit.setAllTensionBeltsActive ~= nil then
            unit:setAllTensionBeltsActive(true, false)
        end
    end
end

-- the stop is over when the strapped part is done and nothing else (tippable load) is left
function ADStrappedLoad.stopFinished(task)
    local stop = task.strappedStop
    if stop == nil or not stop.done then
        return false
    end
    -- the fill level without the strapped part
    ADStrappedLoad.skip = true
    local ok, fillLevel = pcall(AutoDrive.getAllFillLevels, task.trailers or AutoDrive.getAllUnits(task.vehicle) or {})
    ADStrappedLoad.skip = false
    return ok and (fillLevel or 0) < 0.1
end

-- AutoDrive.getObjectFillLevels: a unit without a tippable load of its own counts its strapped load (as full).
-- Returns nil when there is nothing strapped to count.
function ADStrappedLoad.getFillLevels(object, fillCapacity)
    if ADStrappedLoad.skip or (fillCapacity or 0) > 0 then
        return nil
    end
    local litres = ADStrappedLoad.getLitres(object)
    if litres <= 0 then
        return nil
    end
    return litres, litres, true, 0
end

-- AutoDrive:getALObjectFillLevels (a vehicle with Universal Autoload counts only Autoload's load): add the strapped
-- objects Autoload does not track; with any of them on board the vehicle counts as loaded
function ADStrappedLoad.addToAutoloadLevels(object, fillLevel, fillCapacity, filledToUnload, fillFreeCapacity)
    if ADStrappedLoad.skip then
        return fillLevel, fillCapacity, filledToUnload, fillFreeCapacity
    end
    local litres = ADStrappedLoad.getLitres(object)
    if litres <= 0 then
        return fillLevel, fillCapacity, filledToUnload, fillFreeCapacity
    end
    return fillLevel + litres, fillCapacity + litres, true, fillFreeCapacity
end

-------------------------------------------------------------------------------
-- diagnostics: what is on the vehicle, as AutoDrive sees it (server log, once per stop)
-------------------------------------------------------------------------------

local function count(t)
    local n = 0
    for _ in pairs(t or {}) do
        n = n + 1
    end
    return n
end

local function objectName(object)
    local ok, name = pcall(function() return object.getName ~= nil and object:getName() or nil end)
    return tostring(ok and name or object.typeName or object.configFileName or object.i3dFilename or "?")
end

function ADStrappedLoad.describeObject(unit, object, inBelts)
    local fillType, litres = ADUnloadFilter.getObjectProduct(object)
    local specs = {}
    for name, _ in pairs(object.specializationsByName or {}) do
        if name == "pallet" or name == "fillUnit" or name == "tensionBeltObject" or name == "mountable" then
            table.insert(specs, name)
        end
    end
    table.sort(specs)
    local mount = object.getDynamicMountType ~= nil and object:getDynamicMountType() or object.dynamicMountType
    return string.format("%s [type %s, specs %s, bale %s] product %s %.0f l, in belts %s, Autoload tracks %s, counted %s, mount %s, canBeSold %s",
        objectName(object), tostring(object.typeName), table.concat(specs, "+"), tostring(object.isRoundbale ~= nil),
        tostring(fillType ~= nil and g_fillTypeManager ~= nil and g_fillTypeManager:getFillTypeNameByIndex(fillType) or fillType),
        litres or 0, tostring(inBelts), tostring(ADStrappedLoad.isTrackedByAutoload(unit, object)),
        tostring(ADStrappedLoad.isSellable(object)), tostring(mount), tostring(object.canBeSold))
end

function ADStrappedLoad.describe(vehicle, why)
    local ok, err = pcall(function()
        local name = tostring(vehicle.ad.stateModule:getName())
        local units = AutoDrive.getAllUnits(vehicle) or {}
        Logging.info("[AD] Strapped check %s (%s): %d unit(s), fill level %s, best price stop products %s",
            name, why, #units, tostring(AutoDrive.getAllFillLevels(units)),
            vehicle.ad.bestPriceActive == true and tostring(count(vehicle.ad.bestPriceProducts)) or "off")
        for index, unit in ipairs(units) do
            local belts = unit.spec_tensionBelts
            local ual = unit.spec_universalAutoload
            Logging.info("[AD]   unit %d %s: belts %s (fastened %s, held %d, in range %d), hasAL %s, Autoload %s (available %s, disabled %s, tracks %d, count %s, out of physics %s), APAL %s",
                index, objectName(unit), tostring(belts ~= nil), tostring(belts ~= nil and belts.areAllBeltsFastened),
                belts ~= nil and count(belts.objectsToJoint) or 0, belts ~= nil and count(belts.objectsInTensionBeltRange) or 0,
                tostring(AutoDrive:hasAL(unit)), tostring(ual ~= nil), tostring(ual ~= nil and ual.isAutoloadAvailable),
                tostring(ual ~= nil and ual.autoloadDisabled), ual ~= nil and count(ual.loadedObjects) or 0,
                tostring(ual ~= nil and ual.totalUnloadCount), tostring(ual ~= nil and ual.palletsRemovedFromPhysics),
                tostring(unit.spec_aPalletAutoLoader ~= nil))
            local listed = {}
            for _, data in pairs(belts ~= nil and belts.objectsToJoint or {}) do
                local object = type(data) == "table" and data.object or nil
                if object ~= nil and not listed[object] then
                    listed[object] = true
                    Logging.info("[AD]     %s", ADStrappedLoad.describeObject(unit, object, true))
                end
            end
            for object, _ in pairs(ual ~= nil and ual.loadedObjects or {}) do
                if type(object) == "table" and not listed[object] then
                    listed[object] = true
                    Logging.info("[AD]     %s", ADStrappedLoad.describeObject(unit, object, false))
                end
            end
        end
    end)
    if not ok then
        Logging.info("[AD] Strapped check failed: %s", tostring(err))
    end
end
