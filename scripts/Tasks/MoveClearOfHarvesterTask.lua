-- PropaineX edit: drive a waiting unloader to a spot out of the harvesters' way (ADUnloaderClear), with the
-- pathfinder (field and fruit settings as usual). CombineUnloaderMode then waits for a call again.
MoveClearOfHarvesterTask = ADInheritsFrom(AbstractTask)

MoveClearOfHarvesterTask.STATE_PATHPLANNING = 1
MoveClearOfHarvesterTask.STATE_DRIVING = 2

MoveClearOfHarvesterTask.PLAN_TIME = 30000   -- ms at most for the pathfinder
MoveClearOfHarvesterTask.DRIVE_TIME = 120000 -- ms at most for the drive

function MoveClearOfHarvesterTask:new(vehicle, target, direction)
    local o = MoveClearOfHarvesterTask:create()
    o.vehicle = vehicle
    o.target = target
    o.direction = direction
    return o
end

function MoveClearOfHarvesterTask:setUp()
    self.state = MoveClearOfHarvesterTask.STATE_PATHPLANNING
    self.elapsed = 0
    local pfm = self.vehicle.ad.pathFinderModule
    pfm:reset()
    pfm:startPathPlanningTo({x = self.target.x, y = self.target.y, z = self.target.z}, {x = self.direction.x, z = self.direction.z})
    table.insert(pfm.appendWayPoints, {x = self.target.x, y = self.target.y, z = self.target.z})
end

function MoveClearOfHarvesterTask:update(dt)
    self.elapsed = self.elapsed + dt
    local pfm = self.vehicle.ad.pathFinderModule
    if self.state == MoveClearOfHarvesterTask.STATE_PATHPLANNING then
        if pfm:hasFinished() then
            local wayPoints = pfm:getPath()
            if wayPoints == nil or #wayPoints == 0 then
                ADUnloaderClear.onMoveFailed(self.vehicle)
                self:finished()
                return
            end
            self.vehicle.ad.drivePathModule:setWayPoints(wayPoints)
            self.state = MoveClearOfHarvesterTask.STATE_DRIVING
            self.elapsed = 0
        elseif self.elapsed > MoveClearOfHarvesterTask.PLAN_TIME then
            pfm:abort()
            ADUnloaderClear.onMoveFailed(self.vehicle)
            self:finished()
        else
            pfm:update(dt)
            self.vehicle.ad.specialDrivingModule:stopVehicle()
            self.vehicle.ad.specialDrivingModule:update(dt)
        end
    else
        if self.vehicle.ad.drivePathModule:isTargetReached() then
            ADUnloaderClear.onMoveDone(self.vehicle)
            self:finished()
        elseif self.elapsed > MoveClearOfHarvesterTask.DRIVE_TIME then
            ADUnloaderClear.onMoveFailed(self.vehicle)
            self:finished()
        else
            self.vehicle.ad.drivePathModule:update(dt)
        end
    end
end

function MoveClearOfHarvesterTask:abort()
    if self.state == MoveClearOfHarvesterTask.STATE_PATHPLANNING then
        self.vehicle.ad.pathFinderModule:abort()
    end
end

function MoveClearOfHarvesterTask:finished()
    self.vehicle.ad.taskModule:setCurrentTaskFinished()
end

function MoveClearOfHarvesterTask:getInfoText()
    return g_i18n:getText("AD_task_move_clear")
end

function MoveClearOfHarvesterTask:getI18nInfo()
    return "$l10n_AD_task_move_clear;"
end
