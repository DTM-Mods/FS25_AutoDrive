-- PropaineX edit (od.68): UNLOADER RECORDER. Records what an unloader truck and its harvester really do in the game,
-- so the unloader simulator (tools/tests/test_unloader_sim.py) can be rebuilt from real data instead of guesses.
-- Watches only: it changes nothing about how anything drives.
--
-- Server only. While a FollowCombineTask runs, every SAMPLE_MS it writes one CSV row per truck: truck, every trailer
-- and the harvester (position, heading, speed), the wheels' steering, what the driving code asked for (target point,
-- steer point, direction, speed, forward / reverse / stop), the pipe spot, and which rule drove the truck
-- (holdReason). Speeds in m/s (truck signed: minus = reversing). Once per task a "#unit" line with the sizes.
-- Files: modSettings/FS25_AutoDrive/recorder/rec_<date>_<time>_<part>.csv, a new part every FLUSH_MS (only
-- FileAccess.WRITE is used, the one the game's own code uses), at most MAX_PARTS parts per game session.

ADRecorder = {}
ADRecorder.ENABLED = true       -- test build: on. Switch off before any public release.
ADRecorder.SAMPLE_MS = 250
ADRecorder.FLUSH_MS = 10000
ADRecorder.MAX_PARTS = 1440     -- 4 h at 10 s a part
ADRecorder.buffer = {}
ADRecorder.part = 0
ADRecorder.lastFlush = nil
ADRecorder.cmd = {}             -- per vehicle: what the driving code asked for this frame

ADRecorder.HEADER = "t_ms,truck,id,combine,holdReason,state,laneLined," ..
    "tx,tz,th,tv,steer,steerMin,steerMax,cmd,cmdLx,cmdLz,cmdSpeed,ptX,ptZ,stX,stZ,cmdFollow,cmdMax," ..
    "cx,cz,ch,cv,cturn,chaseX,chaseZ,halfW,halfL,units"

local function f(v)
    if v == nil then
        return ""
    end
    if type(v) == "number" then
        return string.format("%.3f", v)
    end
    return (tostring(v):gsub("[,\r\n]", " "))
end

local function heading(node)
    local dx, _, dz = localDirectionToWorld(node, 0, 0, 1)
    return math.atan2(dx, dz)
end

local function stateName(task)
    for k, v in pairs(FollowCombineTask) do
        if v == task.state and type(k) == "string" and k:sub(1, 6) == "STATE_" then
            return k:sub(7)
        end
    end
    return ""
end

function ADRecorder.folder()
    return getUserProfileAppPath() .. "modSettings/FS25_AutoDrive/recorder/"
end

function ADRecorder.flush()
    if #ADRecorder.buffer == 0 or ADRecorder.part >= ADRecorder.MAX_PARTS then
        ADRecorder.buffer = {}
        return
    end
    if ADRecorder.stamp == nil then
        ADRecorder.stamp = getDate("%Y%m%d_%H%M%S")
        createFolder(getUserProfileAppPath() .. "modSettings/")
        createFolder(getUserProfileAppPath() .. "modSettings/FS25_AutoDrive/")
        createFolder(ADRecorder.folder())
    end
    ADRecorder.part = ADRecorder.part + 1
    local path = string.format("%srec_%s_%04d.csv", ADRecorder.folder(), ADRecorder.stamp, ADRecorder.part)
    local file = createFile(path, FileAccess.WRITE)
    if file ~= nil and file ~= 0 then
        fileWrite(file, ADRecorder.HEADER .. "\n" .. table.concat(ADRecorder.buffer, "\n") .. "\n")
        delete(file)
    else
        Logging.warning("[AD] Recorder: could not write %s", path)
    end
    ADRecorder.buffer = {}
end

-- once per task: sizes of the truck, its trailers and the harvester
function ADRecorder.writeUnits(task)
    local v, c = task.vehicle, task.combine
    local units = {}
    local all = AutoDrive.getAllUnits(v) or {v}
    for i, u in ipairs(all) do
        table.insert(units, string.format("%d:%s:%.2f:%.2f", i, f(u.getName and u:getName() or "?"),
            u.size and u.size.width or 0, u.size and u.size.length or 0))
    end
    local hw, hl = AutoDrive.getHarvesterHalfSize(c)
    table.insert(ADRecorder.buffer, string.format("#unit,%d,%s,%s,harvester %.2f x %.2f (size %.2f x %.2f),%s",
        g_time, f(v.getName and v:getName()), f(c.getName and c:getName()), (hw or 0) * 2, (hl or 0) * 2,
        c.size and c.size.width or 0, c.size and c.size.length or 0, table.concat(units, " ")))
end

function ADRecorder.sample(task, dt)
    local v, c = task.vehicle, task.combine
    if v == nil or c == nil or v.components == nil or c.components == nil then
        return
    end
    if task.recUnitsWritten ~= c then
        task.recUnitsWritten = c
        ADRecorder.writeUnits(task)
    end
    task.recTimer = (task.recTimer or 0) + dt
    if task.recTimer < ADRecorder.SAMPLE_MS then
        return
    end
    task.recTimer = 0
    local node = v.components[1].node
    local tx, _, tz = getWorldTranslation(node)
    local cnode = c.components[1].node
    local cx, _, cz = getWorldTranslation(cnode)
    local cmd = ADRecorder.cmd[v]
    if cmd ~= nil and cmd.time ~= g_updateLoopIndex then
        cmd = nil -- nothing asked this frame
    end
    local d = cmd and cmd.drive or {}
    local p = cmd and cmd.point or {}
    local units = {}
    local all = AutoDrive.getAllUnits(v) or {v}
    for i = 2, #all do
        local u = all[i]
        if u.components ~= nil then
            local ux, _, uz = getWorldTranslation(u.components[1].node)
            table.insert(units, string.format("%.3f %.3f %.4f", ux, uz, heading(u.components[1].node)))
        end
    end
    local hw, hl = AutoDrive.getHarvesterHalfSize(c)
    local chase = task.chasePos or {}
    local row = {
        g_time, f(v.getName and v:getName()), f(node), f(c.getName and c:getName()), f(task.holdReason), stateName(task),
        task.laneLined and 1 or 0,
        f(tx), f(tz), string.format("%.4f", heading(node)), f((v.lastSignedSpeed or 0) * 1000),
        f(v.rotatedTime), f(v.minRotTime), f(v.maxRotTime),
        f(cmd and cmd.kind or "none"), f(d.lx), f(d.lz), f(d.speed),
        f(p.ptX), f(p.ptZ), f(p.stX), f(p.stZ), f(p.follow), f(p.max),
        f(cx), f(cz), string.format("%.4f", heading(cnode)), f((c.lastSpeedReal or 0) * 1000),
        f(task.combineTurnRate), f(chase.x), f(chase.z), f(hw), f(hl), table.concat(units, " | ")
    }
    for i = 1, #row do
        row[i] = tostring(row[i])
    end
    table.insert(ADRecorder.buffer, table.concat(row, ","))
    if cmd ~= nil then
        cmd.point = nil -- a driveInDirection without a driveToPoint (other code) must not show this point again
    end
end

-- by game time, not dt: several trucks each call this every frame
function ADRecorder.update()
    if ADRecorder.lastFlush == nil or g_time < ADRecorder.lastFlush then
        ADRecorder.lastFlush = g_time
    elseif g_time - ADRecorder.lastFlush >= ADRecorder.FLUSH_MS then
        ADRecorder.lastFlush = g_time
        ADRecorder.flush()
    end
end

function ADRecorder.install()
    if not ADRecorder.ENABLED or ADRecorder.installed then
        return
    end
    ADRecorder.installed = true
    local origUpdate = FollowCombineTask.update
    FollowCombineTask.update = function(self, dt)
        origUpdate(self, dt)
        if g_server ~= nil then
            local ok, err = pcall(ADRecorder.sample, self, dt)
            if ok then
                ok, err = pcall(ADRecorder.update)
            end
            if not ok and not ADRecorder.errLogged then
                ADRecorder.errLogged = true
                Logging.warning("[AD] Recorder: %s", tostring(err))
            end
        end
    end
    local origDrive = AutoDrive.driveInDirection
    AutoDrive.driveInDirection = function(self, dt, steeringAngleLimit, acceleration, slowAcceleration, slowAngleLimit,
                                          allowedToDrive, moveForwards, lx, lz, maxSpeed, ...)
        local cmd = ADRecorder.cmd[self] or {}
        cmd.time = g_updateLoopIndex
        cmd.kind = allowedToDrive == false and "hold" or (moveForwards == false and "rev" or "fwd")
        cmd.drive = {lx = lx, lz = lz, speed = maxSpeed}
        ADRecorder.cmd[self] = cmd
        return origDrive(self, dt, steeringAngleLimit, acceleration, slowAcceleration, slowAngleLimit, allowedToDrive,
            moveForwards, lx, lz, maxSpeed, ...)
    end
    local origStop = ADSpecialDrivingModule.stopVehicle
    ADSpecialDrivingModule.stopVehicle = function(self, ...)
        if self.vehicle ~= nil then
            local cmd = ADRecorder.cmd[self.vehicle] or {}
            cmd.time = g_updateLoopIndex
            cmd.kind = "stop"
            cmd.drive = {}
            cmd.point = {}
            ADRecorder.cmd[self.vehicle] = cmd
        end
        return origStop(self, ...)
    end
    local origToPoint = ADSpecialDrivingModule.driveToPoint
    ADSpecialDrivingModule.driveToPoint = function(self, dt, point, maxFollowSpeed, checkDynamicCollision, maxAcc, maxSpeed,
                                                   chaseCatchUp, steerPoint, ...)
        if self.vehicle ~= nil then
            local cmd = ADRecorder.cmd[self.vehicle] or {}
            cmd.point = {ptX = point and point.x, ptZ = point and point.z, stX = steerPoint and steerPoint.x,
                         stZ = steerPoint and steerPoint.z, follow = maxFollowSpeed, max = maxSpeed}
            ADRecorder.cmd[self.vehicle] = cmd
        end
        return origToPoint(self, dt, point, maxFollowSpeed, checkDynamicCollision, maxAcc, maxSpeed, chaseCatchUp,
            steerPoint, ...)
    end
    Logging.info("[AD] Recorder on: unloader runs are written to %s", ADRecorder.folder())
end

ADRecorder.install()
