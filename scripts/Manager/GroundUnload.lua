-- While tipping (vehicle setting groundUnload):
-- Bunker silo / heap areas: AutoDrive drives slowly through the area while tipping, to spread the load (upstream).
-- "Stand still": the vehicle stops at the first place it can tip and stays there. When nothing comes out any more
-- for a while (the heap is as high as it gets), it moves on slowly until the load runs again, and stops again.
-- Reversing into a silo is left as it is.
-- Everywhere else (a silo pit, a truck with a trailer): with "stand still" the vehicle does not drive on while one
-- of its units is open and the load goes down, also when AutoDrive lost track of which unit tips.
ADGroundUnload = {}

ADGroundUnload.DRIVE_THROUGH = 1
ADGroundUnload.STAND_STILL = 2
-- the load ran and then nothing was tipped for this long (ms): the heap is full, move on to the next free place
ADGroundUnload.STALL_TIME = 6000
-- before the load first runs (the tipper body still rises), wait this long (ms) before moving on
ADGroundUnload.FIRST_FLOW_TIME = 30000
-- less than this (litres) is "nothing tipped"
ADGroundUnload.MIN_FLOW = 1

function ADGroundUnload.isStandStill(vehicle)
    if vehicle == nil or vehicle.ad == nil or AutoDrive.getSetting("groundUnload", vehicle) ~= ADGroundUnload.STAND_STILL then
        return false
    end
    local drivePathModule = vehicle.ad.drivePathModule
    return not (drivePathModule ~= nil and drivePathModule:getIsReversing())
end

-- while tipping on the ground: true = stand still, false = drive on (spread, or move on from a full heap)
function ADGroundUnload.shouldStop(vehicle, fillLevel, dt)
    if not ADGroundUnload.isStandStill(vehicle) then
        return false
    end
    local state = vehicle.ad.groundUnloadState
    if state == nil or fillLevel > state.fillLevel + ADGroundUnload.MIN_FLOW then
        -- a new load
        state = {fillLevel = fillLevel, stalled = 0, flowing = false}
        vehicle.ad.groundUnloadState = state
    end
    if fillLevel < state.fillLevel - ADGroundUnload.MIN_FLOW then
        -- the load runs: stay here
        state.fillLevel = fillLevel
        state.stalled = 0
        state.flowing = true
        return true
    end
    state.stalled = state.stalled + (dt or 0)
    if state.flowing then
        return state.stalled < ADGroundUnload.STALL_TIME
    end
    return state.stalled < ADGroundUnload.FIRST_FLOW_TIME
end

-- the load went down within this time (ms): it still runs
ADGroundUnload.FLOW_HOLD = 1500

-- a unit of the vehicle is open (discharging) and the load went down a moment ago; only with "stand still"
function ADGroundUnload.isStillTipping(task, dt)
    local vehicle = task.vehicle
    if not ADGroundUnload.isStandStill(vehicle) or task.trailers == nil or #task.trailers == 0 then
        return false
    end
    local open = false
    for _, unit in ipairs(task.trailers) do
        if unit.getDischargeState ~= nil and unit:getDischargeState() ~= Dischargeable.DISCHARGE_STATE_OFF then
            open = true
        end
    end
    local fillLevel = AutoDrive.getAllFillLevels(task.trailers)
    local watch = task.tipWatch
    if watch == nil or fillLevel > watch.fillLevel + ADGroundUnload.MIN_FLOW then
        watch = {fillLevel = fillLevel, sinceFlow = math.huge}
        task.tipWatch = watch
    end
    if fillLevel < watch.fillLevel - ADGroundUnload.MIN_FLOW then
        watch.fillLevel = fillLevel
        watch.sinceFlow = 0
    else
        watch.sinceFlow = watch.sinceFlow + (dt or 0)
    end
    return open and watch.sinceFlow < ADGroundUnload.FLOW_HOLD
end

function ADGroundUnload.reset(vehicle)
    if vehicle ~= nil and vehicle.ad ~= nil then
        vehicle.ad.groundUnloadState = nil
    end
end

-- the unload task: stand still or keep following the route
function ADGroundUnload.drive(task, dt)
    local vehicle = task.vehicle
    local now = g_time or 0
    if vehicle.ad.groundUnloadLogged == nil or now - vehicle.ad.groundUnloadLogged > 60000 then
        -- at most once a minute, so the server log tells which way the vehicle tips on the ground
        vehicle.ad.groundUnloadLogged = now
        local name = vehicle.ad.stateModule ~= nil and vehicle.ad.stateModule:getName() or "?"
        Logging.info("[AD] %s: tipping on the ground (bunker silo / heap), setting %s", tostring(name),
            ADGroundUnload.isStandStill(vehicle) and "stand still" or "drive through")
    end
    if ADGroundUnload.shouldStop(vehicle, AutoDrive.getAllFillLevels(task.trailers), dt) then
        vehicle.ad.specialDrivingModule.motorShouldNotBeStopped = true
        vehicle.ad.specialDrivingModule:stopVehicle()
        vehicle.ad.specialDrivingModule:update(dt)
    else
        vehicle.ad.drivePathModule:update(dt)
    end
end
