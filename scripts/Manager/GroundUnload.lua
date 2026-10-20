-- While tipping (vehicle setting whileTipping, default stand still):
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
    if vehicle == nil or vehicle.ad == nil or AutoDrive.getSetting("whileTipping", vehicle) ~= ADGroundUnload.STAND_STILL then
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

-- below this speed (km/h) the vehicle counts as standing and is held hard
ADGroundUnload.HOLD_SPEED = 0.5
-- the hold ended this long ago (ms): the brakes of all units are released
ADGroundUnload.RELEASE_AFTER = 300

ADGroundUnload.held = {}           -- vehicle -> true while held hard

-- the game's own full brake (Wheels:brake, as Courseplay holds its vehicles) on the vehicle and every attached
-- unit: a heavy trailer pushes a truck that only brakes itself, the more so while it tips backwards
function ADGroundUnload.setBrakes(vehicle, pedal)
    for _, unit in ipairs(AutoDrive.getAllImplements(vehicle, true)) do
        if unit.brake ~= nil then
            unit:brake(pedal)
        end
    end
end

-- holding the vehicle while it unloads. AutoDrive's hold gives a touch of throttle (0.0001) with the handbrake
-- flag once it stands; with an automatic gearbox in drive a loaded truck and trailer then creep against the brake.
-- With "stand still", once the vehicle stands: no throttle at all (the gearbox gets no drive request), handbrake,
-- and full brake on the vehicle and all its units, until the load stops running; then the brakes are released
-- (ADGroundUnload:update). Otherwise AutoDrive's own hold, as before.
function ADGroundUnload.hold(vehicle, dt)
    local sdm = vehicle.ad.specialDrivingModule
    if ADGroundUnload.isStandStill(vehicle) then
        -- the tipping needs the motor
        sdm.motorShouldNotBeStopped = true
    end
    sdm:stopVehicle()
    local standing = vehicle.lastSpeedReal ~= nil and vehicle.lastSpeedReal * 3600 <= ADGroundUnload.HOLD_SPEED
    if not ADGroundUnload.isStandStill(vehicle) or not standing or vehicle.updateVehiclePhysics == nil then
        sdm:update(dt)
        return
    end
    -- no throttle (no drive request to the gearbox) and the handbrake, then full brake on every unit
    vehicle:updateVehiclePhysics(0, 0, true, dt)
    ADGroundUnload.setBrakes(vehicle, 1)
    vehicle.ad.hardHoldTime = g_time or 0
    ADGroundUnload.held[vehicle] = true
    vehicle:raiseActive()
end

-- every frame (server): the brakes come off once the vehicle is not held any more (tipping done, unit empty,
-- the trigger full, AutoDrive stopped) - driving on, AutoDrive sets the brake itself again each frame
function ADGroundUnload:update(dt)
    if next(self.held) == nil then
        return
    end
    local now = g_time or 0
    for vehicle, _ in pairs(self.held) do
        if vehicle.isDeleted or vehicle.ad == nil then
            self.held[vehicle] = nil
        elseif now - (vehicle.ad.hardHoldTime or 0) > self.RELEASE_AFTER then
            self.setBrakes(vehicle, 0)
            self.held[vehicle] = nil
        end
    end
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
        ADGroundUnload.hold(vehicle, dt)
    else
        vehicle.ad.drivePathModule:update(dt)
    end
end
