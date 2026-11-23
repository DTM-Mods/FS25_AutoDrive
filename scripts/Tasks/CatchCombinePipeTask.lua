CatchCombinePipeTask = ADInheritsFrom(AbstractTask)
CatchCombinePipeTask.debug = false

CatchCombinePipeTask.TARGET_DISTANCE = 15

CatchCombinePipeTask.STATE_PATHPLANNING = {}
CatchCombinePipeTask.STATE_DRIVING = {}
CatchCombinePipeTask.STATE_REVERSING = {}
CatchCombinePipeTask.STATE_DELAY_PATHPLANNING = {}
CatchCombinePipeTask.STATE_WAIT_BEFORE_FINISH = {}
CatchCombinePipeTask.STATE_FINISHED = {}

CatchCombinePipeTask.MAX_REVERSE_DISTANCE = 18
CatchCombinePipeTask.MIN_COMBINE_DISTANCE = 25
CatchCombinePipeTask.MAX_REVERSE_TIME = 5000
CatchCombinePipeTask.MAX_STUCK_TIME = 60000
CatchCombinePipeTask.MAX_COUNT_NEW_PATHFINDING = 20
-- Overdrive: new paths in a row without getting lined up with the combine. The count above starts again with every
-- path found, so on its own it never stops an unloader that drives circles near the combine: after MAX_REPLANS it
-- stands still for REPLAN_PAUSE and says why (once), then tries again. Kept on the vehicle, as the task is made anew.
CatchCombinePipeTask.MAX_REPLANS = 8
CatchCombinePipeTask.REPLAN_PAUSE = 30000
-- Overdrive: no way around the crop to the combine (avoid fruit on, the path finder does not drive through it): stand
-- still this long, then plan again - the combine may move or the harvested area grow
CatchCombinePipeTask.CROP_WAIT = 5000

-- Why the task waits before planning (again), shown in the HUD instead of one text for all of them
CatchCombinePipeTask.DELAY_STARTING = "AD_task_catch_planning"
CatchCombinePipeTask.DELAY_NO_PATH = "AD_task_catch_no_path"
CatchCombinePipeTask.DELAY_COMBINE_MOVED = "AD_task_catch_combine_moved"
CatchCombinePipeTask.DELAY_NOT_LINED_UP = "AD_task_catch_not_lined_up"
CatchCombinePipeTask.DELAY_CHASE_OFF_FIELD = "AD_task_catch_chase_off_field"
CatchCombinePipeTask.DELAY_COMBINE_ALMOST_FULL = "AD_task_catch_combine_almost_full"
CatchCombinePipeTask.DELAY_PAUSED = "AD_task_catch_paused"
CatchCombinePipeTask.DELAY_NO_WAY_AROUND_CROP = "AD_task_catch_no_way_around_crop"

-- PropaineX edit (3.7.1.4): an Active unloading harvester (not a forage harvester) that is driving
function CatchCombinePipeTask.isActiveMoving(combine)
    return combine ~= nil and combine.ad ~= nil and combine.ad.isHarvester and not combine.ad.isChopper
        and combine.lastSpeedReal ~= nil and combine.lastSpeedReal > 0.0004
        and AutoDrive.getSetting("activeUnloading", combine:getRootVehicle()) == true
end

-- PropaineX edit (3.7.1.4): the unloader is ahead of the combine (chasing from there would aim at the header)
function CatchCombinePipeTask.isInFront(vehicle)
    local mode = vehicle.ad.modes[AutoDrive.MODE_UNLOAD]
    local _, frontBack = mode:getUnloaderOnSide()
    return frontBack == AutoDrive.CHASEPOS_FRONT
end

-- PropaineX edit (3.7.1.4): skip the catch-up route and chase straight away: combine moving (Active unloading),
-- unloader on the combine's field (farmland) and beside or behind it. A route was planned, driven and thrown away every
-- ~20 s ("combine moved on", 85 m), standing ~7 s each time, 8 in a row -> 30 s wait.
function CatchCombinePipeTask:shouldChaseDirectly()
    if not CatchCombinePipeTask.isActiveMoving(self.combine) or CatchCombinePipeTask.isInFront(self.vehicle) then
        return false
    end
    local vx, _, vz = getWorldTranslation(self.vehicle.components[1].node)
    local cx, _, cz = getWorldTranslation(self.combine.components[1].node)
    return g_farmlandManager:getFarmlandIdAtWorldPosition(vx, vz) == g_farmlandManager:getFarmlandIdAtWorldPosition(cx, cz)
end

function CatchCombinePipeTask:new(vehicle, combine)
    local o = CatchCombinePipeTask:create()
    o.vehicle = vehicle
    o.combine = combine
    o.state = CatchCombinePipeTask.STATE_DELAY_PATHPLANNING
    o.delayReason = CatchCombinePipeTask.DELAY_STARTING
    o.wayPoints = nil
    o.stuckTimer = AutoDriveTON:new()
    o.reverseTimer = AutoDriveTON:new()
    o.waitTimer = AutoDriveTON:new()
    o.waitForCheckTimer = AutoDriveTON:new()
    o.waitForCheckTimer.elapsedTime = 4000
    o.taskType = "CatchCombinePipeTask"
    o.newPathFindingCounter = 0
    o.pauseTimer = 0
    o.trailers = nil
    CatchCombinePipeTask.setStateNames(o)
    return o
end

function CatchCombinePipeTask:setUp()
    CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:setUp()")
    local angleToCombineHeading = self.vehicle.ad.modes[AutoDrive.MODE_UNLOAD]:getAngleToCombineHeading()
    local angleToCombine = self.vehicle.ad.modes[AutoDrive.MODE_UNLOAD]:getAngleToCombine()

    -- od.80: preserve valid close approaches; only a requested recovery bypasses this handover.
    if not self.chopperRecovery and not (AutoDrive.getIsCPTurning ~= nil and AutoDrive:getIsCPTurning(self.combine))
        and angleToCombineHeading < 35 and angleToCombine < 90 and AutoDrive.getDistanceBetween(self.vehicle, self.combine) < 60
        and not self.combine.ad.isFixedPipeChopper then
        self:finished()
    end
    self.trailers, _ = AutoDrive.getAllUnits(self.vehicle)
    AutoDrive.setTrailerCoverOpen(self.vehicle, self.trailers, true)
end

function CatchCombinePipeTask:update(dt)
    if self.combine ~= nil and g_currentMission.nodeToObject[self.combine.components[1].node] == nil then
        self:finished()
        return
    end
    --[=[ od.79: unconditional rear manoeuvre, preserved for rollback.
    -- od.79: a stopped forage harvester needs this trailer before it can move.
    -- Retain the task/assignment and search different rear approaches, not clear/re-call.
    if self:isStationaryChopper() then
        self:updateStationaryApproach(dt)
        return
    elseif self.rendezvous ~= nil then
        self.vehicle.ad.pathFinderModule:abort()
        self.rendezvous = nil
        self.rendezvousPreferredSide = nil
        self.state = CatchCombinePipeTask.STATE_DELAY_PATHPLANNING
        self.pauseTimer = 0
        self.waitForCheckTimer.elapsedTime = 4000
    end
    --]=]
    if ADHarvesterTurn.update(self, dt) then return end
    if self.chopperRecovery then
        self:updateStationaryApproach(dt)
        return
    end
    if self.lastState ~= self.state then
        CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update %s -> %s", tostring(self:getStateName(self.lastState)), tostring(self:getStateName()))
        self.lastState = self.state
        self:resetAllTimers()
    end

    -- od.77: get out of the way before ANY driving or direct-chase handover. Planning and
    -- deliberate waits must not leave a truck parked in front of the harvester either.
    if ADUnloaderClear ~= nil and ADUnloaderClear.clearApproach(self, dt,
        self.state == CatchCombinePipeTask.STATE_DRIVING) then
        return
    end

    -- PropaineX edit (3.7.1.4): chase straight away (see shouldChaseDirectly); finishing hands over to FollowCombineTask
    if (self.state == CatchCombinePipeTask.STATE_DELAY_PATHPLANNING or self.state == CatchCombinePipeTask.STATE_PATHPLANNING
        or self.state == CatchCombinePipeTask.STATE_DRIVING) and self:shouldChaseDirectly() then
        if self.state == CatchCombinePipeTask.STATE_PATHPLANNING then
            self.vehicle.ad.pathFinderModule:abort()
        end
        self.pauseTimer = 0
        self.vehicle.ad.catchReplans = 0
        CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - combine moving, chase directly")
        self.state = CatchCombinePipeTask.STATE_FINISHED
        self:finished()
        return
    end

    local checkForStuck = (self.vehicle.lastSpeedReal <= 0.0002) and (
        self.state == CatchCombinePipeTask.STATE_DRIVING
    )

    self.stuckTimer:timer(checkForStuck, self.MAX_STUCK_TIME, dt)
    if self.stuckTimer:done()
        -- or AutoDrive.getDistanceBetween(self.vehicle, self.combine) < self.MIN_COMBINE_DISTANCE 
        then
        -- got stuck or to close to combine -> reverse
        CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - STATE_DRIVING stuck")
        self.stuckTimer:timer(false)
        local x, y, z = getWorldTranslation(self.vehicle.components[1].node)
        self.reverseStartLocation = {x = x, y = y, z = z}
        self.state = CatchCombinePipeTask.STATE_REVERSING
        return
    end

    -- PropaineX edit (3.6.0.4): no path within PATH_TIMEOUT -> hand the job off or move aside and plan again
    -- (CombineUnloaderMode:onPathTimeout). The clock runs while the path finder searches and during the waits after a
    -- failed search; not during the path finder's start delay or the deliberate waits (almost full, not lined up, ...).
    -- (3.7.1.4: not during the 30 s wait after too many new paths, DELAY_PAUSED; it fired 11 s into it and moved it aside)
    local failedWait = self.state == CatchCombinePipeTask.STATE_DELAY_PATHPLANNING and (self.delayReason == CatchCombinePipeTask.DELAY_NO_PATH
        or self.delayReason == CatchCombinePipeTask.DELAY_NO_WAY_AROUND_CROP)
    if (self.state == CatchCombinePipeTask.STATE_PATHPLANNING and (self.vehicle.ad.pathFinderModule.delayTime or 0) <= 0) or failedWait then
        self.pathWait = (self.pathWait or 0) + dt
        if self.pathWait > CombineUnloaderMode.PATH_TIMEOUT then
            self.pathWait = 0
            self.vehicle.ad.pathFinderModule:abort()
            if self.combine.ad.isChopper then
                self:requestChopperRecovery("normal approach timed out")
                return
            end
            self.vehicle.ad.modes[AutoDrive.MODE_UNLOAD]:onPathTimeout()
            return
        end
    elseif self.state == CatchCombinePipeTask.STATE_DRIVING then
        self.pathWait = 0
    end

    if self.state == CatchCombinePipeTask.STATE_PATHPLANNING then
        if self.vehicle.ad.pathFinderModule:hasFinished() then
            CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - STATE_PATHPLANNING finished")
            self.newPathFindingCounter = 0
            self.wayPoints = self.vehicle.ad.pathFinderModule:getPath()
            if self.wayPoints == nil or #self.wayPoints < 1 then
                --restart
                self.vehicle.ad.modes[AutoDrive.MODE_UNLOAD]:notifyAboutFailedPathfinder()
                --AutoDriveMessageEvent.sendMessageOrNotification(self.vehicle, ADMessagesManager.messageTypes.WARN, "$l10n_AD_Driver_of; %s $l10n_AD_cannot_find_path; %s", 5000, self.vehicle.ad.stateModule:getName(), self.combine.ad.stateModule:getName())
                CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - STATE_PATHPLANNING restarting path finder - with delay")
                if self.vehicle.ad.pathFinderModule:isNoWayAroundCrop() then
                    self:waitForCrop()
                else
                    self:replan(CatchCombinePipeTask.DELAY_NO_PATH)
                end
                return
            else
                if self.combine.ad.isChopper then
                    local x, _, z = getWorldTranslation(self.vehicle.components[1].node)
                    if not ADUnloaderClear.rendezvousPathSafe(self.vehicle.ad.pathFinderModule.rendezvousZones,
                        self.wayPoints, {x=x,z=z}) then
                        self:requestChopperRecovery("normal approach crosses field or header")
                        return
                    end
                end
                self.vehicle.ad.noWayAroundCropLogged = nil
                self.vehicle.ad.drivePathModule:setWayPoints(self.wayPoints)
                self.state = CatchCombinePipeTask.STATE_DRIVING
                return
            end
        else
            self.vehicle.ad.pathFinderModule:update(dt)
            self.vehicle.ad.specialDrivingModule:stopVehicle()
            self.vehicle.ad.specialDrivingModule:update(dt)
            return
        end
    elseif self.state == CatchCombinePipeTask.STATE_DELAY_PATHPLANNING then
        CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - STATE_DELAY_PATHPLANNING")
        if self.pauseTimer > 0 then
            -- too many new paths in a row: stand still for a while
            self.pauseTimer = self.pauseTimer - dt
            self.vehicle.ad.specialDrivingModule:stopVehicle()
            self.vehicle.ad.specialDrivingModule:update(dt)
            return
        end
        if self.waitForCheckTimer:timer(true, 1000, dt) then
            if self.newPathFindingCounter > self.MAX_COUNT_NEW_PATHFINDING then
                -- prevent deadlock
                self.state = CatchCombinePipeTask.STATE_FINISHED
                return
            end
            if self:startNewPathFinding() then
                self.vehicle.ad.pathFinderModule:addDelayTimer(6000)
                self.state = CatchCombinePipeTask.STATE_PATHPLANNING
                return
            end
        end        
        self.vehicle.ad.specialDrivingModule:stopVehicle()
        self.vehicle.ad.specialDrivingModule:update(dt)
        return
    elseif self.state == CatchCombinePipeTask.STATE_DRIVING then
        -- check if this is still a clever path to follow
        -- do this by distance of the combine to the last location pathfinder started at
        local x, y, z = getWorldTranslation(self.combine.components[1].node)
        local combineTravelDistance = MathUtil.vector2Length(x - self.combinesStartLocation.x, z - self.combinesStartLocation.z)

        if combineTravelDistance > 85 then
            CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - combine travelled - recalculate path")
            self.waitForCheckTimer.elapsedTime = 4000
            self:replan(CatchCombinePipeTask.DELAY_COMBINE_MOVED)
            return
        else
            if self.vehicle.ad.drivePathModule:isTargetReached() then
                -- check if we have actually reached the target or not
                -- accept current location if we are in a good position to start chasing: distance and angle are important here
                CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - STATE_DRIVING TargetReached")
                local angleToCombine = self.vehicle.ad.modes[AutoDrive.MODE_UNLOAD]:getAngleToCombineHeading()
                local isCorrectSide = self.vehicle.ad.modes[AutoDrive.MODE_UNLOAD]:isUnloaderOnCorrectSide()

                if angleToCombine < 35 and AutoDrive.getDistanceBetween(self.vehicle, self.combine) < 80 and isCorrectSide then
                    CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - STATE_DRIVING -> STATE_FINISHED")
                    self.vehicle.ad.catchReplans = 0
                    self.state = CatchCombinePipeTask.STATE_FINISHED
                    return
                else
                    CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - angle or distance to combine too high - recalculate path now")
                    self:replan(CatchCombinePipeTask.DELAY_NOT_LINED_UP)
                    return
                end
            else
                self.vehicle.ad.drivePathModule:update(dt)
            end
        end
    elseif self.state == CatchCombinePipeTask.STATE_REVERSING then
        local x, y, z = getWorldTranslation(self.vehicle.components[1].node)
        local distanceToReverseStart = MathUtil.vector2Length(x - self.reverseStartLocation.x, z - self.reverseStartLocation.z)
        self.reverseTimer:timer(true, self.MAX_REVERSE_TIME, dt)
        if distanceToReverseStart > self.MAX_REVERSE_DISTANCE or self.reverseTimer:done() then
            self.state = CatchCombinePipeTask.STATE_WAIT_BEFORE_FINISH
            return
        else
            self.vehicle.ad.specialDrivingModule:driveReverse(dt, 15, 1, self.vehicle.ad.trailerModule:canBeHandledInReverse())
        end
    elseif self.state == CatchCombinePipeTask.STATE_WAIT_BEFORE_FINISH then
        CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - STATE_WAIT_BEFORE_FINISH")
        self.waitTimer:timer(true, self.MAX_REVERSE_TIME, dt)
        if self.waitTimer:done() then
            self.state = CatchCombinePipeTask.STATE_FINISHED
            return
        else
            self.vehicle.ad.specialDrivingModule:stopVehicle()
            self.vehicle.ad.specialDrivingModule:update(dt)
            return
        end
    elseif self.state == CatchCombinePipeTask.STATE_FINISHED then
        CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:update - STATE_FINISHED")
        self:finished()
        return
    end
end

-- Overdrive: plan again (no path, combine moved on, not lined up); counted on the vehicle and logged, and after
-- MAX_REPLANS in a row it pauses and tells the players why
function CatchCombinePipeTask:replan(reason)
    if self.combine.ad.isChopper then
        self:requestChopperRecovery(reason)
        return
    end
    self.delayReason = reason
    self.state = CatchCombinePipeTask.STATE_DELAY_PATHPLANNING
    local count = (self.vehicle.ad.catchReplans or 0) + 1
    self.vehicle.ad.catchReplans = count
    local reasonText = g_i18n ~= nil and g_i18n:getText(reason) or reason
    Logging.info("[AD] %s, catching up with %s: %s (new path %d of %d)", ADDiag.name(self.vehicle), ADDiag.name(self.combine), reasonText, count, self.MAX_REPLANS)
    if count >= self.MAX_REPLANS then
        self.vehicle.ad.catchReplans = 0
        self.pauseTimer = self.REPLAN_PAUSE
        self.delayReason = CatchCombinePipeTask.DELAY_PAUSED
        ADDiag.catchPaused(self.vehicle, self.combine, reason, count, self.REPLAN_PAUSE / 1000)
    end
end

-- Overdrive: no way around the crop (avoid fruit on): stand still for CROP_WAIT, then plan again. Not counted as a new
-- path (it stands still, there is nothing to cap); logged once until a path is found.
function CatchCombinePipeTask:waitForCrop()
    if self.combine.ad.isChopper then
        self:requestChopperRecovery("normal approach blocked by crop")
        return
    end
    self.state = CatchCombinePipeTask.STATE_DELAY_PATHPLANNING
    self.delayReason = CatchCombinePipeTask.DELAY_NO_WAY_AROUND_CROP
    self.pauseTimer = self.CROP_WAIT
    CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:waitForCrop - no way around the crop, waiting %d ms", self.CROP_WAIT)
    if not self.vehicle.ad.noWayAroundCropLogged then
        self.vehicle.ad.noWayAroundCropLogged = true
        local reasonText = g_i18n ~= nil and g_i18n:getText(self.delayReason) or self.delayReason
    end
end

function CatchCombinePipeTask:abort()
    if self.state == CatchCombinePipeTask.STATE_PATHPLANNING or self.rendezvous ~= nil then
        self.vehicle.ad.pathFinderModule:abort()
    end
end

function CatchCombinePipeTask:requestChopperRecovery(reason)
    self.vehicle.ad.pathFinderModule:abort()
    self.chopperRecovery = true
    self.rendezvous = nil
    self.recoveryDelay = 0
    self:diagStationary("field-contained recovery: " .. reason)
end

function CatchCombinePipeTask:onHarvesterTurnStart()
    self.vehicle.ad.pathFinderModule:abort()
    self.rendezvous = nil
    self.state = CatchCombinePipeTask.STATE_DELAY_PATHPLANNING
end

function CatchCombinePipeTask:onHarvesterTurnResume()
    self:requestChopperRecovery("turn ended; discard previous row route")
end

function CatchCombinePipeTask:isStationaryChopper()
    return self.combine ~= nil and self.combine.ad ~= nil and self.combine.ad.isChopper == true
        and (self.combine.lastSpeedReal or 0) <= 0.0004
end

function CatchCombinePipeTask:startStationaryLeg(r)
    local pf = self.vehicle.ad.pathFinderModule
    pf:reset()
    local dx, _, dz = AutoDrive.localDirectionToWorld(self.combine, 0, 0, 1, self.combine.ad.ADRootNode)
    pf:startPathPlanningTo(r.leg == 1 and r.rear or r.target, {x=dx, z=dz})
    r.zones = ADUnloaderClear.makeRendezvousZones(self.vehicle, self.combine)
    ADUnloaderClear.setRendezvousField(r.zones, self.vehicle, self.combine, self.workingField)
    pf.rendezvousZones = r.zones
    pf.restrictToField, pf.stayOnField = true, true
    -- Keep the user's crop/field settings. No fruit fallback for a loading approach.
    pf.goingToPipe = true
    pf.chasingVehicle = false
    pf.isSecondChasingVehicle = false
    r.planning = true
    r.elapsed, r.still = 0, 0
    pf.max_pathfinder_steps = math.max(pf.max_pathfinder_steps or 0, 400)*(r.searchScale or 1)
    self.state = CatchCombinePipeTask.STATE_PATHPLANNING
end

function CatchCombinePipeTask:retryStationaryApproach(reason)
    self.vehicle.ad.pathFinderModule:abort()
    self.rendezvousAttempt = (self.rendezvousAttempt or 0)+1
    self.rendezvous = nil
    self.recoveryDelay = 1000
    self.state = CatchCombinePipeTask.STATE_DELAY_PATHPLANNING
    self.delayReason = CatchCombinePipeTask.DELAY_NO_PATH
    self:diagStationary("trying another rear approach: " .. reason)
end

function CatchCombinePipeTask:diagStationary(reason)
    Logging.info("[AD] %s, rendezvous with %s: %s", ADDiag.name(self.vehicle), ADDiag.name(self.combine), reason)
end

function CatchCombinePipeTask:updateStationaryApproach(dt)
    local drive, pf = self.vehicle.ad.drivePathModule, self.vehicle.ad.pathFinderModule
    local sdm = self.vehicle.ad.specialDrivingModule
    local mode = self.vehicle.ad.modes[AutoDrive.MODE_UNLOAD]
    local r = self.rendezvous
    if self.workingField == nil then
        self.fieldLookupDelay = (self.fieldLookupDelay or 0)-dt
        if self.fieldLookupDelay <= 0 then
            self.workingField = ADUnloaderClear.captureWorkingField(self.combine)
            self.fieldLookupDelay = 1000
        end
    end
    if self.workingField == nil then
        sdm:stopVehicle(); sdm:update(dt)
        if not self.fieldUnknownLogged then
            self.fieldUnknownLogged = true
            self:diagStationary("cannot identify working field boundary; no off-field fallback")
        end
        return
    end
    -- Finish early only when THIS train is actually receiving from the assigned harvester.
    --[=[ od.79: synchronous dischargeObject only, preserved for rollback.
    local node = self.combine.getCurrentDischargeNode ~= nil and self.combine:getCurrentDischargeNode() or nil
    if node ~= nil and self.combine.getDischargeState ~= nil
        and self.combine:getDischargeState() == Dischargeable.DISCHARGE_STATE_OBJECT then
        for _, unit in pairs(self.trailers or {}) do
            if node.dischargeObject == unit then
                pf:abort()
                self.rendezvous = nil
                self:finished()
                return
            end
        end
    end
    --]=]
    if ADHarvesterTurn.receiving(self) then
        pf:abort()
        self.rendezvous = nil
        self:finished()
        return
    end
    if r == nil then
        sdm:stopVehicle(); sdm:update(dt)
        if (self.recoveryDelay or 0) > 0 then
            self.recoveryDelay = self.recoveryDelay-dt
            return
        end
        local attempt = self.rendezvousAttempt or 0
        local target, side = mode:getPipeChasePosition(true)
        local setting = AutoDrive.getSetting("chaseSide", self.combine)
        local autoSide = self.combine.ad.isAutoAimingChopper and setting == AutoDrive.CHASEPOS_AUTO
        if autoSide then
            self.rendezvousPreferredSide = self.rendezvousPreferredSide
                or (side == AutoDrive.CHASEPOS_RIGHT and side or AutoDrive.CHASEPOS_LEFT)
            side = self.rendezvousPreferredSide
            if attempt % 2 == 1 then side = side == AutoDrive.CHASEPOS_LEFT and AutoDrive.CHASEPOS_RIGHT or AutoDrive.CHASEPOS_LEFT end
            local offset = math.abs(mode:getSideChaseOffsetX())
            target = AutoDrive.createWayPointRelativeToVehicle(self.combine,
                side*(offset+mode:getPipeSlopeCorrection()), mode:getSideChaseOffsetZ(AutoDrive.dynamicChaseDistance)-2)
        end
        local tx, _, tz = AutoDrive.worldToLocal(self.combine, target.x, target.y, target.z, self.combine.ad.ADRootNode)
        local halfW, halfL = AutoDrive.getHarvesterHalfSize(self.combine)
        if self.combine.ad.isAutoAimingChopper and side ~= AutoDrive.CHASEPOS_REAR then
            local width = self.vehicle.size.width or 3
            for _, unit in pairs(self.trailers or {}) do
                width = math.max(width, unit.size ~= nil and unit.size.width or 0)
            end
            tx = (tx >= 0 and 1 or -1)*math.max(math.abs(tx), halfW+width/2+0.5,
                AutoDrive.getFrontToolWidth(self.combine)/2+width/2+0.5)
            target.x, target.y, target.z = AutoDrive.localToWorld(self.combine, tx, 0, tz, self.combine.ad.ADRootNode)
        end
        local train = AutoDrive.getTractorTrainLength(self.vehicle, true, false) or 20
        --[=[ od.79: 35/50/65m rear goals were not checked against field boundaries.
        local back = -halfL-math.max(train, 12)-12-({0,15,30})[math.floor(attempt/(autoSide and 2 or 1))%3+1]
        local x, y, z = AutoDrive.localToWorld(self.combine, tx, 0, math.min(tz, back), self.combine.ad.ADRootNode)
        r = {target=target, rear={x=x,y=y,z=z}, leg=1}
        self.rendezvous = r
        self:diagStationary(string.format("rear approach %d, side %s, run-up %.0f m", attempt+1, tostring(side), -back))
        --]=]
        local dx, _, dz = AutoDrive.localDirectionToWorld(self.combine, 0, 0, 1, self.combine.ad.ADRootNode)
        local width = (self.vehicle.size.width or 3)/2+0.5
        for _, unit in pairs(self.trailers or {}) do
            width = math.max(width, (unit.size ~= nil and unit.size.width or 0)/2+0.5)
        end
        local candidates = {}
        local backs = {halfL+math.min(train/2, 12)+3, halfL+(self.vehicle.size.length or 6)/2+2, halfL+3}
        for _, back in ipairs(backs) do
            local x, y, z = AutoDrive.localToWorld(self.combine, tx, 0, -back, self.combine.ad.ADRootNode)
            -- Full straight train must fit at the end of the alignment leg.
            local cx, cz = x-dx*(train-(self.vehicle.size.length or 6))/2, z-dz*(train-(self.vehicle.size.length or 6))/2
            if ADUnloaderClear.fieldFits(self.workingField, cx, cz, dx, dz, width, train/2+0.5) then
                table.insert(candidates, {x=x,y=y,z=z})
            end
        end
        local tailOffset = (train-(self.vehicle.size.length or 6))/2
        local finalFits = ADUnloaderClear.fieldFits(self.workingField,
            target.x-dx*tailOffset, target.z-dz*tailOffset, dx, dz, width, train/2+0.5)
        if not finalFits then
            self:retryStationaryApproach("loading target outside working field")
            return
        end
        -- At a tight headland there may be no room behind. Let the constrained
        -- planner find a lane approach within the field, never extend across a road.
        local choice = math.floor(attempt/(autoSide and 2 or 1))%(#candidates+1)+1
        local rear = candidates[choice]
        r = {target=target, rear=rear, leg=rear ~= nil and 1 or 2,
            searchScale=1+math.floor(attempt/(2*(#candidates+1)))%3}
        self.rendezvous = r
        self:diagStationary(string.format("recovery %d, side %s, rear leg %s", attempt+1, tostring(side), tostring(rear ~= nil)))
        self:startStationaryLeg(r)
        return
    end
    r.elapsed = r.elapsed+dt
    if r.planning then
        sdm:stopVehicle(); sdm:update(dt)
        if pf:hasFinished() then
            local points = pf:getPath()
            local x, _, z = getWorldTranslation(self.vehicle.components[1].node)
            if points == nil or #points == 0 or not ADUnloaderClear.rendezvousPathSafe(r.zones, points, {x=x,z=z}) then
                self:retryStationaryApproach("no safe path")
                return
            end
            drive:setWayPoints(points)
            r.planning, r.elapsed = false, 0
            self.state = CatchCombinePipeTask.STATE_DRIVING
        elseif r.elapsed > 20000 then
            self:retryStationaryApproach("planning time exceeded")
        else
            pf:update(dt)
        end
        return
    end
    local x, _, z = getWorldTranslation(self.vehicle.components[1].node)
    -- Re-check the remaining smoothed route against current harvester geometry.
    if not ADUnloaderClear.trainOnField(self.vehicle, self.workingField) then
        sdm:stopVehicle(); sdm:update(dt)
        self:retryStationaryApproach("train reaches working-field boundary")
        return
    end
    r.previewTime = (r.previewTime or 100)+dt
    if r.previewTime >= 100 then
        r.previewTime = 0
        local zones = ADUnloaderClear.makeRendezvousZones(self.vehicle, self.combine)
        ADUnloaderClear.setRendezvousField(zones, self.vehicle, self.combine, self.workingField)
        local speed = math.abs(self.vehicle.lastSpeedReal or 0)*1000
        if not ADUnloaderClear.rendezvousPathSafe(zones, drive.wayPoints or {}, {x=x,z=z},
            drive.currentWayPoint, math.max(15, speed*2.1+speed*speed/4)) then
            sdm:stopVehicle(); sdm:update(dt)
            self:retryStationaryApproach("route blocked")
            return
        end
    end
    if drive:isTargetReached() then
        local target = r.leg == 1 and r.rear or r.target
        if MathUtil.vector2Length(x-target.x,z-target.z) > 5 then
            self:retryStationaryApproach("stopped short of target")
        elseif r.leg == 1 then
            r.leg = 2
            self:startStationaryLeg(r)
        elseif mode:getAngleToCombineHeading() < 35 then
            pf:abort()
            self.rendezvous = nil
            self.vehicle.ad.catchReplans = 0
            self:diagStationary("in loading position")
            self:finished()
        else
            self:retryStationaryApproach("not aligned at pipe")
        end
        return
    end
    r.still = (self.vehicle.lastSpeedReal or 0) < 0.0002 and r.still+dt or 0
    if r.still > 8000 or r.elapsed > 120000 then
        sdm:stopVehicle(); sdm:update(dt)
        self:retryStationaryApproach("approach obstructed")
        return
    end
    drive:update(dt)
end

function CatchCombinePipeTask:finished(propagate)
    if self.rendezvous ~= nil then
        self:abort()
        self.rendezvous = nil
    end
    CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:finished()")
    self.vehicle.ad.taskModule:setCurrentTaskFinished(propagate)
end

function CatchCombinePipeTask:startNewPathFinding()
    CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:startNewPathFinding()")
    local pipeChasePos, pipeChaseSide = self.vehicle.ad.modes[AutoDrive.MODE_UNLOAD]:getPipeChasePosition(true)
    local x, _, z = getWorldTranslation(self.combine.components[1].node)
    local targetFieldId = g_farmlandManager:getFarmlandIdAtWorldPosition(pipeChasePos.x, pipeChasePos.z)
    local combineFieldId = g_farmlandManager:getFarmlandIdAtWorldPosition(x, z)

    -- Only chase the rear on low fill levels of the combine. This should prevent getting into unneccessarily tight spots for the final approach to the pipe.
    -- Also for small fields, there is often no purpose in chasing so far behind the combine as it will already start a turn soon

    local cfillLevel, cfillCapacity, _, cfillFreeCapacity = AutoDrive.getObjectFillLevels(self.combine)
    local cFillRatio = cfillCapacity > 0 and cfillLevel / cfillCapacity or 0

    -- PropaineX edit (3.2.1.4): with Active unloading on, a harvester that is almost full is still chased (it is about
    -- to stop; we want to be under the pipe then), not given up on
    local activeUnloadingOn = self.combine.ad.isHarvester and AutoDrive.getSetting("activeUnloading", self.combine:getRootVehicle()) == true
    if (cFillRatio > 0.91 or cfillFreeCapacity < 0.1) and not activeUnloadingOn then
        CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:startNewPathFinding() - Combine is almost full - dont chase for active unloading anymore")
        self:finished(ADTaskModule.DONT_PROPAGATE)
        self.vehicle.ad.modes[AutoDrive.MODE_UNLOAD]:setToWaitForCall()
        return false
    end

    self.newPathFindingCounter = self.newPathFindingCounter + 1 -- used to prevent deadlock

    if self.combine.ad.isChopper or (pipeChaseSide ~= AutoDrive.CHASEPOS_REAR or (targetFieldId == combineFieldId and (cFillRatio <= 0.85 or activeUnloadingOn))) then
    -- PropaineX edit (3.3.0.4): with Active unloading on, the rear chase doesn't wait above 85 % (pipe over crop is fine)
    -- if self.combine:getIsBufferCombine() or (pipeChaseSide ~= AutoDrive.CHASEPOS_REAR and targetFieldId == combineFieldId and cFillRatio <= 0.85) then
        -- is chopper or chase not rear and harvester on correct field and filled < 85% - i.e. combine pipe not in fruit
        CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:startNewPathFinding() - chase pos looks good - calculate path to it...")
        self.vehicle.ad.pathFinderModule:reset()
        self.vehicle.ad.pathFinderModule:startPathPlanningToPipe(self.combine, false)
        if self.combine.ad.isChopper then
            local pf = self.vehicle.ad.pathFinderModule
            self.workingField = self.workingField or ADUnloaderClear.captureWorkingField(self.combine)
            local zones = ADUnloaderClear.makeRendezvousZones(self.vehicle, self.combine)
            ADUnloaderClear.setRendezvousField(zones, self.vehicle, self.combine, self.workingField)
            pf.rendezvousZones = zones
            pf.restrictToField, pf.stayOnField = true, true
        end
        -- use false to enable pathfinder fallback
        self.combinesStartLocation = {}
        self.combinesStartLocation.x, self.combinesStartLocation.y, self.combinesStartLocation.z = getWorldTranslation(self.combine.components[1].node)
        return true
    else
        CatchCombinePipeTask.debugMsg(self.vehicle, "CatchCombinePipeTask:startNewPathFinding() - chase pos looks bad, is not on the same field or combine's fill level is approaching limit - aborting for now")
        -- the spot to chase is behind the combine here: either not on the combine's field, or the combine is almost full
        if targetFieldId ~= combineFieldId then
            self.delayReason = CatchCombinePipeTask.DELAY_CHASE_OFF_FIELD
        else
            self.delayReason = CatchCombinePipeTask.DELAY_COMBINE_ALMOST_FULL
        end
        self.waitForCheckTimer:timer(false)
    end
    return false
end

function CatchCombinePipeTask:getExcludedVehiclesForCollisionCheck()
    -- od.77: approaching the pipe is not unloading alongside it. Keep the harvester an obstacle.
    return {}
end

function CatchCombinePipeTask:setStateNames()
    if self.statesToNames == nil then
        self.statesToNames = {}
        for name, id in pairs(CatchCombinePipeTask) do
            if string.sub(name, 1, 6) == "STATE_" then
                self.statesToNames[id] = name
            end
        end
    end
end

function CatchCombinePipeTask:getStateName(state)
    local requestedState = state
    if requestedState == nil then
        requestedState = self.state
    end
    if requestedState == nil then
        Logging.error("[AD] CatchCombinePipeTask: Could not find name for state ->%s<- !", tostring(requestedState))
    end
    return self.statesToNames[requestedState] or ""
end

function CatchCombinePipeTask:resetAllTimers()
    -- self.stuckTimer:timer(false) -- stuckTimer reset by speed changes
    self.reverseTimer:timer(false)
    self.waitTimer:timer(false)
    self.waitForCheckTimer:timer(false)
end

function CatchCombinePipeTask:getI18nInfo()
    local text = "$l10n_AD_task_catch_up_with_combine;"
    if self.harvesterTurnHold then return text .. " - $l10n_AD_task_wait_for_combine_turn;" end
    if self.state == CatchCombinePipeTask.STATE_PATHPLANNING then
        local actualState, maxStates, steps, max_pathfinder_steps = self.vehicle.ad.pathFinderModule:getCurrentState()
        text = text .. " - " .. "$l10n_AD_task_pathfinding;" .. string.format(" %d / %d - %d / %d", actualState, maxStates, steps, max_pathfinder_steps)
    elseif self.state == CatchCombinePipeTask.STATE_DELAY_PATHPLANNING then
        text = text .. " - " .. "$l10n_" .. (self.delayReason or CatchCombinePipeTask.DELAY_STARTING) .. ";"
        if self.delayReason == CatchCombinePipeTask.DELAY_PAUSED or self.delayReason == CatchCombinePipeTask.DELAY_NO_WAY_AROUND_CROP then
            text = text .. string.format(" (%d s)", math.ceil(math.max(0, self.pauseTimer) / 1000))
        elseif self.delayReason == CatchCombinePipeTask.DELAY_NO_PATH or self.delayReason == CatchCombinePipeTask.DELAY_COMBINE_MOVED
            or self.delayReason == CatchCombinePipeTask.DELAY_NOT_LINED_UP then
            -- new paths in a row, it pauses after this many
            text = text .. string.format(" (%d/%d)", self.vehicle.ad.catchReplans or 0, self.MAX_REPLANS)
        end
        if self.delayReason == CatchCombinePipeTask.DELAY_CHASE_OFF_FIELD or self.delayReason == CatchCombinePipeTask.DELAY_COMBINE_ALMOST_FULL then
            -- waiting like this, it gives up after this many tries (the count starts again with every finished path finding)
            text = text .. string.format(" (%d/%d)", self.newPathFindingCounter, self.MAX_COUNT_NEW_PATHFINDING)
        end
    elseif self.state == CatchCombinePipeTask.STATE_REVERSING then
        text = text .. " - " .. "$l10n_AD_task_reversing_from_combine;"
    elseif self.state == CatchCombinePipeTask.STATE_WAIT_BEFORE_FINISH then
        text = text .. " - " .. "$l10n_AD_task_waiting_for_room;"
    end
    return text 
end

function CatchCombinePipeTask.debugMsg(vehicle, debugText, ...)
    if CatchCombinePipeTask.debug == true then
        AutoDrive.debugMsg(vehicle, debugText, ...)
    else
        AutoDrive.debugPrint(vehicle, AutoDrive.DC_COMBINEINFO, debugText, ...)
    end
end
