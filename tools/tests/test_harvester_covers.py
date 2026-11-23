"""Execute real cover controls: nearby pipes override assignments, modes and close requests."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

root = Path(__file__).resolve().parents[2]
lua = LuaRuntime()
lua.execute("AutoDrive = {}")
lua.execute((root / "scripts/Utils/TrailerUtil.lua").read_text(encoding="utf-8"))
lua.execute('''
g_server = {}
automatic = true
AutoDrive.getSetting = function() return automatic end
AutoDrive.COVER_COMBINE_RANGE = 50
AutoDrive.isCombineFieldWork = function() return true, nil end
function trailer()
    return {spec_cover = {state = 0, covers = {{}, {}}}, calls = 0, allowed = true,
        getIsNextCoverStateAllowed = function(self) return self.allowed end,
        setCoverState = function(self, state, noEvent)
            assert(noEvent == false, "must use native multiplayer event path")
            self.calls = self.calls + 1; self.spec_cover.state = state
        end}
end
a, b, c = trailer(), trailer(), trailer()
pipe = {spec_combine = {}, spec_pipe = {objectsInTriggers = {[a] = 1, [b] = 2}}}
g_currentMission = {vehicleSystem = {vehicles = {pipe}}}
-- No root, AD mode or assignment is needed; every compatible trailer is opened.
AutoDrive.updateHarvesterCovers()
assert(a.spec_cover.state == 2 and b.spec_cover.state == 2 and c.spec_cover.state == 0)
AutoDrive.updateHarvesterCovers()
assert(a.calls == 1 and b.calls == 1, "do not spam cover events")
-- Explicit closing and unknown/distant assigned combine cannot override proximity.
AutoDrive.setTrailerCoverOpen({}, {a, b, c}, false)
assert(a.spec_cover.state == 2 and b.spec_cover.state == 2 and c.spec_cover.state == 0)
automatic = false
AutoDrive.setTrailerCoverOpen({}, {a}, false)
assert(a.spec_cover.state == 2)
a.spec_cover.state = 0
AutoDrive.updateHarvesterCovers()
assert(a.spec_cover.state == 2, "proximity must override automatic-cover setting")
-- Temporarily blocked animation is retried without fabricating a state change.
a.spec_cover.state = 0; a.allowed = false
AutoDrive.updateHarvesterCovers()
assert(a.spec_cover.state == 0)
a.allowed = true
AutoDrive.updateHarvesterCovers()
assert(a.spec_cover.state == 2)
-- A second passing harvester keeps it open after the first loses range.
other = {spec_combine = {}, spec_pipe = {objectsInTriggers = {[a] = 1}}}
g_currentMission.vehicleSystem.vehicles[2] = other
pipe.spec_pipe.objectsInTriggers[a] = nil
AutoDrive.setTrailerCoverOpen({}, {a}, false)
assert(a.spec_cover.state == 2)
other.spec_pipe.objectsInTriggers[a] = nil
automatic = true
AutoDrive.setTrailerCoverOpen({}, {a}, false)
assert(a.spec_cover.state == 0, "normal closing resumes outside range")
-- Only an in-range trailer is overridden, even in the same train.
AutoDrive.setTrailerCoverOpen({}, {a, b}, true)
assert(a.spec_cover.state == 0 and b.spec_cover.state == 2)
-- Non-harvester pipes, stale zero counts, and objects without covers are harmless.
g_currentMission.vehicleSystem.vehicles = {{spec_pipe = {objectsInTriggers = {[a] = 1}}},
    {spec_combine = {}, spec_pipe = {objectsInTriggers = {[a] = 0, [{}] = 1}}}}
AutoDrive.updateHarvesterCovers()
assert(a.spec_cover.state == 0)
-- Clients never originate proximity cover changes.
g_currentMission.vehicleSystem.vehicles = {pipe}; a.spec_cover.state = 0
pipe.spec_pipe.objectsInTriggers[a] = 1
g_server = nil
AutoDrive.updateHarvesterCovers()
assert(a.spec_cover.state == 0)
''')
print("PASS: harvester cover proximity, close overrides, settings, retries, multiple harvesters, leaving range and client authority")
