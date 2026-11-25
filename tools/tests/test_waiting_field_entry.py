"""od.81: real Lua entry/queue/separation geometry; engine motion/search are doubles."""
from chopper_test_support import lua, ROOT

source = (ROOT / "scripts/Utils/UtilFuncs.lua").read_text(encoding="utf-8")
lua.execute(source[source.index("function AutoDrive.boxesIntersect"):source.index("-- Pumps N' Hoses")])
for name in ("Tasks/WaitForCallTask.lua", "Tasks/DriveToDestinationTask.lua"):
    lua.execute((ROOT / "scripts" / name).read_text(encoding="utf-8"))
source = (ROOT / "scripts/Manager/HarvestManager.lua").read_text(encoding="utf-8")
lua.execute("ADHarvestManager={}")
lua.execute(source[source.index("function ADHarvestManager:getClosestIdleUnloader"):
                   source.index("function ADHarvestManager:hasHarvesterAvailableUnloader")])
lua.execute("CLOSEST_IDLE=ADHarvestManager.getClosestIdleUnloader")

lua.execute('''
function rect(x1,z1,x2,z2)
 return {polygonPoints={{x=x1,z=z1},{x=x2,z=z1},{x=x2,z=z2},{x=x1,z=z2}}}
end
setup()
-- A real off-field waiting start is allowed, with no field-relaxing fallback.
C.x=30;V.x,V.z=-20,-40;T.x,T.z=-20,-52
g_fieldManager.fields={rect(0,-100,100,100),rect(-80,20,-5,60)}
AutoDrive.checkIsOnField=function(x,y,z) return x>=0 or (x<=-5 and z>=20 and z<=60) end
TASK.enteredWorkingField=nil;TASK.fieldEntry=nil;TASK.rendezvous=nil;TASK.workingField=nil;TASK.fieldLookupDelay=0
TASK:update(16)
assert(TASK.rendezvous and PF.rendezvousZones.entry and not PF.restrictToField and PF.stayOnField)
local zones=PF.rendezvousZones
assert(ADUnloaderClear.rendezvousPathSafe(zones,{{x=20,z=-40}},{x=-20,z=-40}))
assert(not ADUnloaderClear.rendezvousPathSafe(zones,{{x=20,z=-40},{x=-5,z=-40}},{x=-20,z=-40}))
assert(ADUnloaderClear.rendezvousBlocked(zones,-20,40)) -- different field
assert(ADUnloaderClear.rendezvousBlocked(zones,-90,-40)) -- cannot wander away
local originalEntry=TASK.fieldEntry
V.x=-18;ADUnloaderClear.prepareRendezvous(TASK,{})
assert(TASK.fieldEntry==originalEntry) -- retries cannot move the corridor
V.x=10;T.x=-1
local nextZones=ADUnloaderClear.makeRendezvousZones(V,C)
ADUnloaderClear.prepareRendezvous(TASK,nextZones)
assert(not TASK.enteredWorkingField and nextZones.entry) -- cab in, trailer out
T.x=10;ADUnloaderClear.prepareRendezvous(TASK,nextZones)
assert(TASK.enteredWorkingField and not nextZones.entry)
assert(ADUnloaderClear.rendezvousBlocked(nextZones,-5,-40))
-- A new call from a nearby marker cannot bypass entry planning via close handover.
TASK=CatchCombinePipeTask:new(V,C);TASK.trailers={V,T};V.x=-10;T.x=-10
AutoDrive.setTrailerCoverOpen=function() end
MODE.getAngleToCombine=function() return 0 end
FINISHED=false;TASK:setUp();assert(not FINISHED)
-- The ordinary call path, not just recovery, must handle a chopper needing a
-- trailer at full buffer or with zero capacity/free space. Keep the assignment.
g_farmlandManager={getFarmlandIdAtWorldPosition=function() return 1 end}
PF.startPathPlanningToPipe=function() end
AutoDrive.getObjectFillLevels=function() return 100,100,0,0 end
assert(TASK:startNewPathFinding() and PF.rendezvousZones.entry and not PF.restrictToField)
assert(not FINISHED and MODE.combine==C)
AutoDrive.getObjectFillLevels=function() return 0,0,0,0 end
assert(TASK:startNewPathFinding() and not FINISHED)

-- Native collision rectangle decisions, not mocked overlap outcomes.
local WT=getWorldTranslation;local nodes={}
getWorldTranslation=function(node) return WT(nodes[node] or node) end
local marker={id=123}
function truck(id,x,z)
 local v=obj(x,z);nodes[id]=v;v.components[1].node=id
 local m={vehicle=v,STATE_WAIT_TO_BE_CALLED=1,STATE_DRIVE_TO_COMBINE=2,STATE_DRIVE_TO_START=3,state=1}
 v.ad.modes={[1]=m}
 v.ad.stateModule={isActive=function() return true end,getMode=function() return 1 end,getFirstMarker=function() return marker end}
 v.ad.specialDrivingModule={stopVehicle=function() STOPPED=STOPPED+1 end,update=function() end,
  releaseVehicle=function() end,driveToPoint=function() DRIVEN=DRIVEN+1 end}
 v.ad.trailerModule={handleTrailerReversing=function() end}
 return v,m
end
local a,am=truck(10,0,0);local b,bm=truck(20,0,6)
local fleet={a,b};AutoDrive.getAllVehicles=function() return fleet end
AutoDrive.checkForVehiclesInBox=function(box,excluded)
 for _,v in ipairs(fleet) do
  local skip=false;for _,e in ipairs(excluded) do if v==e then skip=true end end
  if not skip and AutoDrive.boxesIntersect(box,AutoDrive.getBoundingBoxForVehicle(v)) then return true end
 end
 return false
end
AutoDrive.driveInDirection=function(v,dt,angle,acc,slow,sa,allowed,forward,lx,lz,speed)
 assert(v==a and not forward and speed==3);DRIVEN=DRIVEN+1
end
ADGraphManager={getWayPointById=function() return {x=0,z=0} end}
bm.state=bm.STATE_DRIVE_TO_START
assert(ADUnloaderClear.queueAtWaitingPoint({vehicle=b,destinationID=123}))
assert(not ADUnloaderClear.queueAtWaitingPoint({vehicle=b,destinationID=456}))
-- Drive task finishes into the normal callable wait transition, without moving.
local returned=false
local destination=DriveToDestinationTask:new(b,123)
destination.finished=function() returned=true end
destination:update(16);assert(returned)
-- Called truck holds; one idle neighbour backs away, preserving its registration.
bm.state=bm.STATE_DRIVE_TO_COMBINE;bm.combine=C
assert(ADUnloaderClear.separationSafe(a,b,-1))
assert(not ADUnloaderClear.separationSafe(a,b,1))
local waiting=WaitForCallTask:new(a)
local before=DRIVEN
assert(ADUnloaderClear.holdForWaitingTruck({vehicle=b},16))
waiting:update(1001);assert(DRIVEN==before+1 and waiting.queueYield.direction==-1)
assert(am.state==am.STATE_WAIT_TO_BE_CALLED and bm.combine==C)
local fleetManager={idleUnloaders={a,b}}
a.ad.taskModule={getActiveTask=function() return waiting end}
b.ad.taskModule={getActiveTask=function() return nil end}
C.ad.stateModule={getFirstMarker=function() return marker end}
assert(CLOSEST_IDLE(fleetManager,C)==b) -- do not interrupt the yielding truck
-- Third truck behind prevents backing into it. Engine objects also veto movement.
local c=truck(30,0,-7);fleet={a,b,c}
assert(not ADUnloaderClear.separationSafe(a,b,-1))
fleet={a,b}
g_currentMission.getNodeObject=function() return nil end
AutoDrive.isPassThroughCollision=function() return false end
overlapBox=function(x,y,z,rx,ry,rz,w,h,l,callback,target) target[callback](target,999) end
assert(not ADUnloaderClear.separationSafe(a,b,-1))
overlapBox=nil
-- Folded trains cannot use a straight reverse approximation.
local trailer=obj(0,-8);trailer.h=0.4;a.units={a,trailer}
assert(not ADUnloaderClear.separationSafe(a,b,-1));a.units=nil
-- Once clear, release the called truck and return to ordinary idle waiting.
a.z=-10;waiting:update(16)
assert(not waiting.queueYield and not ADUnloaderClear.holdForWaitingTruck({vehicle=b},16))
-- Two idle trucks choose one mover, with a stable numeric-node priority.
a.z=0;b.z=6;bm.state=bm.STATE_WAIT_TO_BE_CALLED;bm.combine=nil
local first=WaitForCallTask:new(a);local second=WaitForCallTask:new(b)
first:update(1001);second:update(1001)
assert(not first.queueYield and second.queueYield)
-- A genuinely interlocked pair uses ONLY the existing escape opt-in. It must
-- keep terrain/third-truck checks and restore masks once the train is clear.
local ta,tb=obj(0,-12),obj(0,-6);a.units={a,ta};b.units={b,tb}
bm.state=bm.STATE_DRIVE_TO_COMBINE;bm.combine=C
assert(not ADUnloaderClear.separationSafe(a,b,-1))
assert(not ADUnloaderClear.separationSafe(a,b,1))
local ghost=false
ADUnloaderEscape.isEnabled=function() return true end
ADUnloaderEscape.isGhosted=function() return ghost end
ADUnloaderEscape.setGhost=function(v,value) assert(v==a);ghost=value end
ADUnloaderEscape.isTouchingOtherVehicle=function() return false end
local interlocked=WaitForCallTask:new(a);interlocked:update(1001)
assert(ghost and interlocked.queueYield.releaseOverlap)
a.z=-40;ta.z=-52;interlocked:update(16);assert(not ghost)
''')
print("PASS: off-field call entry, whole-train field latch, no neighbour-field detour/re-exit, callable return queue, single-truck yield, static/third-truck veto and opt-in interlock release")
