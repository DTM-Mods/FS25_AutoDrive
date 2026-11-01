-- Diagnostics: the error and warning messages of AutoDrive tell what happened, with what (target, distances, fuel,
-- damage, mode ...) and what to check. Built on the server: the message is a text with text-key parts that
-- every player's game translates, the values go along as arguments (names and numbers only). The translations of
-- these keys must not contain a percent sign (AutoDrive.localize uses them as a gsub replacement).
-- The full text (English) is also written to the server's log, to read it there later.
ADDiag = {}

ADDiag.DURATION = 12000            -- ms the pop-up stays (longer texts)

ADDiag.MODE_KEYS = {}

local function modeKey(vehicle)
    if next(ADDiag.MODE_KEYS) == nil and AutoDrive.MODE_DRIVETO ~= nil then
        ADDiag.MODE_KEYS = {
            [AutoDrive.MODE_DRIVETO] = "AD_MODE_DRIVETO", [AutoDrive.MODE_DELIVERTO] = "AD_MODE_DELIVERTO",
            [AutoDrive.MODE_PICKUPANDDELIVER] = "AD_MODE_PICKUPANDDELIVER", [AutoDrive.MODE_UNLOAD] = "AD_MODE_UNLOAD",
            [AutoDrive.MODE_LOAD] = "AD_MODE_LOAD", [AutoDrive.MODE_BGA] = "AD_MODE_BGA"}
    end
    local mode = vehicle.ad ~= nil and vehicle.ad.stateModule ~= nil and vehicle.ad.stateModule:getMode() or nil
    return ADDiag.MODE_KEYS[mode]
end

function ADDiag.name(vehicle)
    if vehicle ~= nil and vehicle.ad ~= nil and vehicle.ad.stateModule ~= nil then
        return vehicle.ad.stateModule:getName() or "?"
    end
    return vehicle ~= nil and vehicle.getName ~= nil and vehicle:getName() or "?"
end

function ADDiag.unitName(unit)
    if unit == nil then
        return "?"
    end
    if unit.getFullName ~= nil then
        return unit:getFullName()
    end
    return unit.getName ~= nil and unit:getName() or "?"
end

-- the name of the target on a waypoint, else "#id"
function ADDiag.targetName(wayPointId)
    local marker = wayPointId ~= nil and ADGraphManager:getMapMarkerByWayPointId(wayPointId) or nil
    if marker ~= nil and marker.name ~= nil then
        return marker.name
    end
    return "#" .. tostring(wayPointId)
end

function ADDiag.distanceFromNetwork(vehicle)
    if ADGraphManager.getDistanceFromNetwork ~= nil then
        local ok, distance = pcall(ADGraphManager.getDistanceFromNetwork, ADGraphManager, vehicle)
        if ok and distance ~= nil then
            return math.floor(distance + 0.5)
        end
    end
    return 0
end

function ADDiag.closestWayPoint(vehicle)
    if vehicle.getClosestWayPoint ~= nil then
        local ok, id = pcall(vehicle.getClosestWayPoint, vehicle)
        if ok then
            return id
        end
    end
    return nil
end

-- sends it to the players and writes it to the server log
function ADDiag.send(vehicle, messageType, text, ...)
    local args = {...}
    AutoDriveMessageEvent.sendMessageOrNotification(vehicle, messageType, text, ADDiag.DURATION, ...)
    if Logging ~= nil and AutoDrive.localize ~= nil then
        local ok, full = pcall(function() return string.format(AutoDrive.localize(text), unpack(args)) end)
        Logging.info("[AD] %s", ok and full or text)
    end
end

-------------------------------------------------------------------------------
-- driving
-------------------------------------------------------------------------------

-- no path from the vehicle (off the network) to the destination: is it the network route or the way across the land?
function ADDiag.pathFailed(vehicle, destinationId)
    local name, target, distance = ADDiag.name(vehicle), ADDiag.targetName(destinationId), ADDiag.distanceFromNetwork(vehicle)
    local closest = ADDiag.closestWayPoint(vehicle)
    local route = (closest ~= nil and destinationId ~= nil) and ADGraphManager:pathFromTo(closest, destinationId) or nil
    if closest ~= nil and destinationId ~= nil and (route == nil or #route <= 1) and closest ~= destinationId then
        ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
            "$l10n_AD_Driver_of; %s $l10n_AD_cannot_find_path; ($l10n_AD_diag_to; %s, $l10n_AD_diag_nearestWp; %s, %s m $l10n_AD_diag_offNetwork;): $l10n_AD_hint_pfNoRoute;",
            name, target, tostring(closest), tostring(distance))
    else
        ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
            "$l10n_AD_Driver_of; %s $l10n_AD_cannot_find_path; ($l10n_AD_diag_to; %s, %s m $l10n_AD_diag_offNetwork;): $l10n_AD_hint_pfBlocked;",
            name, target, tostring(distance))
    end
end

-- catching up with the combine: new paths again and again without getting lined up (e.g. a long rig circling
-- near the combine); it pauses, the message says why and which settings to check
function ADDiag.catchPaused(vehicle, combine, lastReason, tries, seconds)
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.WARN,
        "$l10n_AD_Driver_of; %s $l10n_AD_diag_catchPaused; %s (%s $l10n_AD_diag_newPaths;, $l10n_" .. lastReason .. ";): $l10n_AD_hint_catchPaused; '$l10n_gui_ad_restrictToField;', '$l10n_gui_ad_followOnlyOnField;'",
        ADDiag.name(vehicle), ADDiag.name(combine), tostring(tries))
end

-- on the network, but no route from where it stands to the target
function ADDiag.cannotReach(vehicle, wayPointId)
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
        "$l10n_AD_Driver_of; %s $l10n_AD_cannot_reach; %s ($l10n_AD_diag_startWp; %s, %s m $l10n_AD_diag_offNetwork;): $l10n_AD_hint_noRoute;",
        ADDiag.name(vehicle), ADDiag.targetName(wayPointId), tostring(ADDiag.closestWayPoint(vehicle) or "?"), tostring(ADDiag.distanceFromNetwork(vehicle)))
end

-- no nearer to the next waypoint for 8 s
function ADDiag.stuck(vehicle, drivePathModule)
    local wp = drivePathModule ~= nil and drivePathModule:getCurrentWayPoint() or nil
    local distance = 0
    if wp ~= nil then
        local x, _, z = getWorldTranslation(vehicle.components[1].node)
        distance = math.floor(MathUtil.vector2Length(x - wp.x, z - wp.z) + 0.5)
    end
    local speed = math.floor((vehicle.lastSpeedReal or 0) * 3600 + 0.5)
    local text = "$l10n_AD_Driver_of; %s $l10n_AD_got_stuck; ($l10n_AD_diag_nextWp; %s, %s m, %s km/h"
    local args = {ADDiag.name(vehicle), tostring(wp ~= nil and wp.id or "?"), tostring(distance), tostring(speed)}
    local collision = vehicle.ad.collisionDetectionModule
    if collision ~= nil and collision.trafficVehicle ~= nil then
        text = text .. ", $l10n_AD_diag_blockedBy; %s"
        table.insert(args, ADDiag.name(collision.trafficVehicle))
    elseif collision ~= nil and collision.detectedObstable then
        text = text .. ", $l10n_AD_wait_blocked;"
    end
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR, text .. "): $l10n_AD_hint_stuck;", unpack(args))
end

-- leaving the field: no route on the network to the unload target
function ADDiag.exitFieldNoRoute(vehicle, fromText, toWayPointId)
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
        "$l10n_AD_Driver_of; %s $l10n_AD_cannot_find_path; ($l10n_AD_diag_from; %s $l10n_AD_diag_to; %s): $l10n_AD_hint_exitField;",
        ADDiag.name(vehicle), fromText or "?", ADDiag.targetName(toWayPointId))
end

-- a mode was started without its target(s)
function ADDiag.noTarget(vehicle)
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR, "$l10n_AD_Driver_of; %s $l10n_AD_diag_noTarget;", ADDiag.name(vehicle))
end

-------------------------------------------------------------------------------
-- refuel, repair, park
-------------------------------------------------------------------------------

-- "Diesel 12 %, DEF 40 %": the fuels it needs and how full their tanks are
function ADDiag.fuelText(vehicle, ignoreFillLevel)
    local parts = {}
    local spec = vehicle.spec_motorized
    local needed = AutoDrive.getRequiredRefuels ~= nil and AutoDrive.getRequiredRefuels(vehicle, ignoreFillLevel) or {}
    for _, fillType in ipairs(needed) do
        local title = g_fillTypeManager ~= nil and g_fillTypeManager:getFillTypeTitleByIndex(fillType) or tostring(fillType)
        local percent = nil
        if spec ~= nil and spec.consumersByFillTypeName ~= nil then
            for _, consumer in pairs(spec.consumersByFillTypeName) do
                if consumer.fillType == fillType and vehicle.getFillUnitFillLevelPercentage ~= nil then
                    percent = math.floor(vehicle:getFillUnitFillLevelPercentage(consumer.fillUnitIndex) * 100 + 0.5)
                end
            end
        end
        table.insert(parts, percent ~= nil and string.format("%s %d %%", title, percent) or title)
    end
    return table.concat(parts, ", "), #needed
end

function ADDiag.noRefuelStation(vehicle, ignoreFillLevel)
    local fuels, count = ADDiag.fuelText(vehicle, ignoreFillLevel)
    if count == 0 then
        ADDiag.send(vehicle, ADMessagesManager.messageTypes.WARN, "$l10n_AD_Driver_of; %s $l10n_AD_diag_tankNotLow; (%s)", ADDiag.name(vehicle), "90 %")
        return
    end
    local stations = 0
    if ADTriggerManager ~= nil and ADTriggerManager.getRefuelTriggers ~= nil then
        local ok, triggers = pcall(ADTriggerManager.getRefuelTriggers, vehicle, ignoreFillLevel)
        stations = ok and triggers ~= nil and #triggers or 0
    end
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
        "$l10n_AD_Driver_of; %s $l10n_AD_No_Refuel_Station; (%s, %s $l10n_AD_diag_stations;): $l10n_AD_hint_refuel;",
        ADDiag.name(vehicle), fuels, tostring(stations))
end

-- the chosen refuel target can not be used: gone, or no refuel point with fuel for the vehicle / no access there
function ADDiag.refuelChoiceUnusable(vehicle, name, gone)
    local reason = gone and "$l10n_AD_diag_refuelChoiceGone;" or "$l10n_AD_diag_refuelChoiceUnusable;"
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.WARN, "$l10n_AD_Driver_of; %s: " .. reason .. " '%s' (%s) - $l10n_AD_diag_refuelUsingNearest;",
        ADDiag.name(vehicle), tostring(name), (ADDiag.fuelText(vehicle, true)))
end

-- "Tatra 72 %, ASW 271 65 %": the damaged units
function ADDiag.damageText(vehicle)
    local parts = {}
    for _, unit in ipairs(AutoDrive.getAllImplements(vehicle, true)) do
        if unit.spec_wearable ~= nil and unit.spec_wearable.damage ~= nil and unit.spec_wearable.damage > 0.05 then
            table.insert(parts, string.format("%s %d %%", ADDiag.unitName(unit), math.floor(unit.spec_wearable.damage * 100 + 0.5)))
        end
    end
    return #parts > 0 and table.concat(parts, ", ") or "-"
end

function ADDiag.noRepairStation(vehicle)
    local workshops = 0
    if ADTriggerManager ~= nil and ADTriggerManager.getRepairTriggers ~= nil then
        local ok, triggers = pcall(ADTriggerManager.getRepairTriggers)
        workshops = ok and triggers ~= nil and #triggers or 0
    end
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
        "$l10n_AD_Driver_of; %s $l10n_AD_diag_noWorkshop; (%s, %s $l10n_AD_diag_workshops;): $l10n_AD_hint_repair;",
        ADDiag.name(vehicle), ADDiag.damageText(vehicle), tostring(workshops))
end

function ADDiag.noParkDestination(vehicle)
    local tool = AutoDrive.getSelectedWorkTool ~= nil and AutoDrive.getSelectedWorkTool(vehicle) or nil
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
        "$l10n_AD_Driver_of; %s $l10n_AD_parkVehicle_noPosSet; ($l10n_AD_diag_forTool; %s): $l10n_AD_hint_park;",
        ADDiag.name(vehicle), ADDiag.unitName(tool or vehicle))
end

-------------------------------------------------------------------------------
-- handing over between AutoDrive, Courseplay and the game's helper
-------------------------------------------------------------------------------

function ADDiag.wrongModeForHelper(vehicle)
    local key = modeKey(vehicle)
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
        "$l10n_AD_Driver_of; %s: $l10n_AD_Wrong_Mode_takeover_from_CP; ($l10n_AD_diag_mode; " .. (key ~= nil and ("$l10n_" .. key .. ";") or "?") .. "): $l10n_AD_hint_helperMode;",
        ADDiag.name(vehicle))
end

function ADDiag.aiJobActive(vehicle)
    local who = (AutoDrive.getIsCPActive ~= nil and AutoDrive:getIsCPActive(vehicle)) and "$l10n_AD_diag_byCourseplay;" or "$l10n_AD_diag_byHelper;"
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
        "$l10n_AD_Driver_of; %s: $l10n_AD_AIJob_active; (" .. who .. "): $l10n_AD_hint_aiActive;", ADDiag.name(vehicle))
end

function ADDiag.cannotStartAIJob(vehicle, errorMessage, onField)
    if not onField then
        ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
            "$l10n_AD_Driver_of; %s: $l10n_AD_Unable_to_start_AIJob; ($l10n_AD_diag_notOnField;): $l10n_AD_hint_aiJob;", ADDiag.name(vehicle))
    else
        ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR,
            "$l10n_AD_Driver_of; %s: $l10n_AD_Unable_to_start_AIJob; (%s): $l10n_AD_hint_aiJob;", ADDiag.name(vehicle), tostring(errorMessage or "?"))
    end
end

-------------------------------------------------------------------------------
-- recording, bunker silo (shovel), others
-------------------------------------------------------------------------------

function ADDiag.recordingTwoRoads(vehicle, reversing)
    if reversing then
        ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR, "$l10n_AD_diag_recordReverse;")
    else
        ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR, "$l10n_AD_diag_recordOffsets; (%s m / %s m)",
            tostring(AutoDrive.getSetting("RecordDriveDirectionOffset")), tostring(AutoDrive.getSetting("RecordOppositeDriveDirectionOffset")))
    end
end

function ADDiag.noShovel(vehicle)
    local names = {}
    for _, unit in ipairs(AutoDrive.getAllImplements(vehicle, false)) do
        table.insert(names, ADDiag.unitName(unit))
    end
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR, "$l10n_AD_Driver_of; %s $l10n_AD_No_Shovel; ($l10n_AD_diag_attached; %s): $l10n_AD_hint_shovel;",
        ADDiag.name(vehicle), #names > 0 and table.concat(names, ", ") or "-")
end

function ADDiag.noBunker(vehicle)
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR, "$l10n_AD_Driver_of; %s $l10n_AD_No_Bunker;: $l10n_AD_hint_bunker;", ADDiag.name(vehicle))
end

function ADDiag.bunkerEmpty(vehicle, fillTypeIndex)
    local title = (fillTypeIndex ~= nil and g_fillTypeManager ~= nil) and g_fillTypeManager:getFillTypeTitleByIndex(fillTypeIndex) or "?"
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR, "$l10n_AD_Driver_of; %s $l10n_AD_diag_bunkerEmpty; (%s): $l10n_AD_hint_bunkerEmpty;",
        ADDiag.name(vehicle), tostring(title))
end

function ADDiag.noTrailerForShovel(vehicle)
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.ERROR, "$l10n_AD_Driver_of; %s $l10n_AD_No_Trailer;: $l10n_AD_hint_bgaTrailer;", ADDiag.name(vehicle))
end

-- once a session: Universal Autoload too old / new for picking pallets
function ADDiag.ualNotSupported(vehicle)
    if ADDiag.ualWarned then
        return
    end
    ADDiag.ualWarned = true
    ADDiag.send(vehicle, ADMessagesManager.messageTypes.WARN, "$l10n_AD_diag_ualUnsupported;")
end
