-- od.80: common hold/resume operations; chopper-specific turn/unload signals.
ADHarvesterTurn = {}

function ADHarvesterTurn.headerLowered(combine)
    local root = combine.getRootVehicle ~= nil and combine:getRootVehicle() or combine
    local found, lowered = false, true
    for _, unit in pairs(root.getChildVehicles ~= nil and root:getChildVehicles() or {root}) do
        if unit.spec_cutter ~= nil or unit.spec_pickup ~= nil then
            found = true
            if unit.getIsLowered ~= nil and (unit.getAllowsLowering == nil or unit:getAllowsLowering())
                and not unit:getIsLowered(true) then lowered = false end
        end
    end
    if found then return lowered end
    return nil
end

function ADHarvesterTurn.hold(task, dt)
    task.harvesterTurnHold = true
    for _, name in ipairs({"stuckTimer", "angleWrongTimer", "waitForTurnTimer"}) do
        if task[name] ~= nil then task[name]:timer(false) end
    end
    local drive = task.vehicle.ad.specialDrivingModule
    drive:stopVehicle()
    drive:update(dt)
end

function ADHarvesterTurn.resume(task)
    task.harvesterTurnHold = nil
    task.turnSwing, task.turnQuiet, task.combineTurnRate, task.lastCombineFwd = nil, nil, nil, nil
    task.turnStartHeading, task.lineDir, task.laneLined = nil, nil, nil
    task.comingRound, task.wrongSideTime, task.backingOff = nil, nil, nil
    task.turnBackStart, task.turnBackDone = nil, nil
    if task.onHarvesterTurnResume ~= nil then task:onHarvesterTurnResume() end
end

function ADHarvesterTurn.receiving(task)
    local combine = task.combine
    if combine.getDischargeState == nil or combine:getDischargeState() ~= Dischargeable.DISCHARGE_STATE_OBJECT then return false end
    local node = combine.getDischargeNodeByIndex ~= nil and combine.getPipeDischargeNodeIndex ~= nil
        and combine:getDischargeNodeByIndex(combine:getPipeDischargeNodeIndex())
        or (combine.getCurrentDischargeNode ~= nil and combine:getCurrentDischargeNode()) or nil
    if node == nil then return false end
    local target = node.dischargeObject
    if combine.spec_pipe ~= nil and combine.spec_pipe.isAsyncRaycastActive then target = node.lastDischargeObject end
    for _, unit in pairs(task.trailers or AutoDrive.getAllUnits(task.vehicle) or {}) do
        if target == unit then return true end
    end
    return false
end

function ADHarvesterTurn.needsTrailer(combine)
    if AutoDrive.getIsCPWaitingForUnload ~= nil and AutoDrive:getIsCPWaitingForUnload(combine) then return true end
    local root = combine.getRootVehicle ~= nil and combine:getRootVehicle() or combine
    local strategy = root.spec_cpAIFieldWorker ~= nil and root.spec_cpAIFieldWorker.combineDriveStrategy or nil
    if strategy ~= nil and strategy.isChopperWaitingForUnloader ~= nil and strategy:isChopperWaitingForUnloader() then return true end
    -- Buffer full is an engine signal, not a heading/turn guess.
    if AutoDrive.getObjectFillLevels ~= nil then
        local fill, capacity = AutoDrive.getObjectFillLevels(combine)
        return capacity ~= nil and capacity > 0 and fill/capacity >= 0.95
    end
    return false
end

function ADHarvesterTurn.update(task, dt)
    local combine = task.combine
    if combine.ad.isChopper ~= true then return false end
    local turn = task.harvesterTurn
    if turn == nil or turn.combine ~= combine then
        turn = {combine=combine, stable=0, unloadStable=0}
        task.harvesterTurn = turn
    end
    local dx, _, dz = AutoDrive.localDirectionToWorld(combine, 0, 0, 1, combine.ad.ADRootNode)
    local heading = math.atan2(dx, dz)
    local change = turn.heading ~= nil and math.abs(math.atan2(math.sin(heading-turn.heading), math.cos(heading-turn.heading))) or 0
    turn.heading = heading
    local rotating = dt > 0 and math.deg(change)*1000/dt > 2
    local stopped = math.abs(combine.lastSpeedReal or 0) < 0.00014
    local cpTurn = AutoDrive.getIsCPTurning ~= nil and AutoDrive:getIsCPTurning(combine) or false
    local root = combine.getRootVehicle ~= nil and combine:getRootVehicle() or combine
    local aiTurn = root.getAIFieldWorkerIsTurning ~= nil and root:getAIFieldWorkerIsTurning() or false
    local lowered = ADHarvesterTurn.headerLowered(combine)
    if lowered then turn.seenWorking = true end
    local turning = cpTurn or aiTurn or (turn.holding and rotating) or (turn.seenWorking and lowered == false)
    turn.unloadStable = stopped and not rotating and ADHarvesterTurn.needsTrailer(combine)
        and turn.unloadStable+dt or 0
    local unloadPause = turn.unloadStable >= 1000
    if turning and not unloadPause then
        turn.stable = 0
        if not turn.holding then
            turn.holding = true
            if task.onHarvesterTurnStart ~= nil then task:onHarvesterTurnStart() end
        end
        turn.unloadPause = nil
        ADHarvesterTurn.hold(task, dt)
        return true
    end
    if turn.holding then
        turn.stable = turn.stable+dt
        -- A confirmed stationary unload pause may need the trailer before the turn can continue.
        if not unloadPause and turn.stable < 500 then
            ADHarvesterTurn.hold(task, dt)
            return true
        end
        turn.holding = nil
        turn.unloadPause = unloadPause
        ADHarvesterTurn.resume(task)
    end
    task.harvesterTurnHold = nil
    return false
end
