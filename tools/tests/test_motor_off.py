"""Motor off when AutoDrive finishes: on a dedicated server a player only counts as "in the vehicle" while the
vehicle is controlled, not just because controllerUserId still names a user (that left finished trucks running)."""
import os
import re
from lupa.lua55 import LuaRuntime

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read(*parts):
    return open(os.path.join(MOD, *parts), encoding="utf-8").read().replace("\r\n", "\n")


utils = read("scripts", "Utils", "AutoDriveUtilFuncs.lua")
funcs = []
for name in ("function AutoDrive:getIsEntered(vehicle)", "function AutoDrive:isPlayerInVehicle(vehicle)"):
    start = utils.index(name)
    funcs.append(utils[start:utils.index("\nend\n", start) + 5])

s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    AutoDrive = {}
    USERS = {[7] = {nickname = "Fennell"}}
    g_currentMission = {userManager = {getUserByUserId = function(self, id) return USERS[id] end}}
    function truck(userId, controlled, entered)
        local v = {spec_enterable = {controllerUserId = userId}}
        function v:getIsControlled() return controlled end
        function v:getIsEntered() return entered end
        return v
    end
""")
for f in funcs:
    s.execute(f)

# dedicated server
s.execute("g_dedicatedServer = {}")
assert s.eval("AutoDrive:getIsEntered(truck(7, false))") is True                 # the old check: stale id still counts
assert s.eval("AutoDrive:isPlayerInVehicle(truck(7, false))") is False           # got out: motor goes off
assert s.eval("AutoDrive:isPlayerInVehicle(truck(7, true))") is True             # sits in it: motor stays on
assert s.eval("AutoDrive:isPlayerInVehicle(truck(0, false))") is False           # nobody
assert s.eval("AutoDrive:isPlayerInVehicle(truck(99, true))") is False           # unknown user
# single player / host: unchanged (getIsEntered or getIsControlled)
s.execute("g_dedicatedServer = nil")
assert s.eval("AutoDrive:isPlayerInVehicle(truck(nil, false, true))") is True
assert s.eval("AutoDrive:isPlayerInVehicle(truck(nil, false, false))") is False

# the motor decision in stopAutoDrive uses it and logs what happened
spec = read("scripts", "Specialization.lua")
stop = spec[spec.index("function AutoDrive:stopAutoDrive()"):]
stop = stop[:stop.index("\nend\n")]
assert "local playerInVehicle = AutoDrive:isPlayerInVehicle(self)" in stop
assert re.search(r"if not playerInVehicle then\s.*?self:stopMotor\(\)", stop, re.S)
assert "AutoDrive switched off, motor" in stop
# getIsEntered itself is unchanged for its other users (manually driven combines etc.)
assert "user = g_currentMission.userManager:getUserByUserId(vehicle.spec_enterable.controllerUserId)" in utils

print("OK: motor off when AutoDrive finishes (dedicated server: stale controllerUserId no longer keeps it running, "
      "a player sitting in it still does; single player unchanged; logged)")
