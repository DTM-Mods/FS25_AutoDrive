-- Drive clear when blocked (ADUnloaderEscape): with collisions to other vehicles off, drive to the nearest field
-- edge (just outside it), wait there until no other vehicle is near, switch collisions back on and finish.
-- CombineUnloaderMode then carries on as after reversing from a bad location.
EscapeToFieldEdgeTask = ADInheritsFrom(AbstractTask)

EscapeToFieldEdgeTask.STATE_DRIVING = 1
EscapeToFieldEdgeTask.STATE_WAIT_CLEAR = 2

-- close enough to the target (m)
EscapeToFieldEdgeTask.ARRIVED = 4
-- the longest drive to the edge (ms), and how long to wait for others to get clear before moving on a bit (ms)
EscapeToFieldEdgeTask.DRIVE_TIME = 120000
EscapeToFieldEdgeTask.CLEAR_WAIT = 20000
-- moving on: this far ahead (m), at most this often
EscapeToFieldEdgeTask.NUDGE_DISTANCE = 15
EscapeToFieldEdgeTask.MAX_NUDGES = 3
EscapeToFieldEdgeTask.SPEED = 12
-- off the field already: drive this far ahead (m)
EscapeToFieldEdgeTask.OFF_FIELD_DISTANCE = 20

function EscapeToFieldEdgeTask:new(vehicle)
    local o = EscapeToFieldEdgeTask:create()
    o.vehicle = vehicle
    return o
end

function EscapeToFieldEdgeTask:setUp()
    self.vehicle.ad.escapeActive = true
    ADUnloaderEscape.setGhost(self.vehicle, true)
    local x, _, z = getWorldTranslation(self.vehicle.components[1].node)
    local tx, tz = ADUnloaderEscape.findFieldEdge(x, z)
    if tx == nil then
        local ax, _, az = AutoDrive.localToWorld(self.vehicle, 0, 0, EscapeToFieldEdgeTask.OFF_FIELD_DISTANCE)
        tx, tz = ax, az
    end
    self:setTarget(tx, tz)
    self.nudges = 0
end

function EscapeToFieldEdgeTask:setTarget(x, z)
    local y = getTerrainHeightAtWorldPos(g_currentMission.terrainRootNode, x, 0, z)
    self.target = {x = x, y = y, z = z}
    self.state = EscapeToFieldEdgeTask.STATE_DRIVING
    self.elapsed = 0
end

function EscapeToFieldEdgeTask:update(dt)
    self.elapsed = self.elapsed + dt
    local sdm = self.vehicle.ad.specialDrivingModule
    if self.state == EscapeToFieldEdgeTask.STATE_DRIVING then
        local x, _, z = getWorldTranslation(self.vehicle.components[1].node)
        if MathUtil.vector2Length(x - self.target.x, z - self.target.z) < EscapeToFieldEdgeTask.ARRIVED or self.elapsed > EscapeToFieldEdgeTask.DRIVE_TIME then
            self.state = EscapeToFieldEdgeTask.STATE_WAIT_CLEAR
            self.elapsed = 0
            sdm:stopVehicle()
            sdm:update(dt)
            return
        end
        -- no obstacle checks: the vehicles it drives through are what it is getting away from
        sdm:driveToPoint(dt, self.target, EscapeToFieldEdgeTask.SPEED, false, 1, EscapeToFieldEdgeTask.SPEED)
    else
        sdm:stopVehicle()
        sdm:update(dt)
        if not ADUnloaderEscape.isTouchingOtherVehicle(self.vehicle, ADUnloaderEscape.CLEAR_MARGIN) then
            ADUnloaderEscape.setGhost(self.vehicle, false)
            self:finished()
        elseif self.elapsed > EscapeToFieldEdgeTask.CLEAR_WAIT then
            if self.nudges < EscapeToFieldEdgeTask.MAX_NUDGES then
                -- something stays next to it: move on a bit
                self.nudges = self.nudges + 1
                local ax, _, az = AutoDrive.localToWorld(self.vehicle, 0, 0, EscapeToFieldEdgeTask.NUDGE_DISTANCE)
                self:setTarget(ax, az)
            else
                -- give up waiting, the watcher switches collisions on once it is clear
                self:finished()
            end
        end
    end
end

function EscapeToFieldEdgeTask:abort()
    self.vehicle.ad.escapeActive = false
end

function EscapeToFieldEdgeTask:finished()
    self.vehicle.ad.escapeActive = false
    self.vehicle.ad.specialDrivingModule:releaseVehicle()
    self.vehicle.ad.taskModule:setCurrentTaskFinished()
end

function EscapeToFieldEdgeTask:getInfoText()
    return g_i18n:getText("AD_task_escape")
end

function EscapeToFieldEdgeTask:getI18nInfo()
    return "$l10n_AD_task_escape;"
end
