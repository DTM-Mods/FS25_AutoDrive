"""Stationary chopper recovery: real Lua controls and geometry; mocked engine/search."""
from chopper_test_support import lua

lua.execute('''
setup()
-- od.79 asserted PF.target.z < -30; od.80 adapts the run-up inside the working field.
assert(TASK.rendezvous.leg==1 and PF.target.z < -10 and PF.target.z > -30 and MODE.combine==C)
assert(PF.restrictToField and PF.stayOnField)
assert(PF.goingToPipe and not PF.chasingVehicle and PF.rendezvousZones~=nil)
-- Loading alongside is legal; cutting across the header/front remains forbidden.
local zones=PF.rendezvousZones
assert(not ADUnloaderClear.rendezvousBlocked(zones,7,15))
assert(ADUnloaderClear.rendezvousBlocked(zones,0,15))
assert(ADUnloaderClear.rendezvousBlocked(zones,0,0))
assert(not ADUnloaderClear.rendezvousPathSafe(zones,{{x=-10,z=15}},{x=10,z=15}))
-- Search failure chooses the opposite permitted lane without dropping the call.
ready({});assert(TASK.rendezvous==nil and TASK.rendezvousAttempt==1 and MODE.combine==C)
TASK:update(1100);TASK:update(16);assert(PF.target.x<0)
ready({});TASK:update(1100);TASK:update(16);assert(PF.target.x>0 and PF.target.z > -30)
-- An explicit side selection must not be overridden by retry alternation.
CHASE_SETTING=1;setup();ready({});TASK:update(1100);TASK:update(16);assert(PF.target.x==7);CHASE_SETTING=nil
-- Reject a smoothed shortcut through the front, even if its endpoints are clear.
setup();ready({{x=14,z=20},{x=-14,z=20},{x=7,z=-40}})
assert(TASK.rendezvous==nil and MODE.combine==C and DRIVEN==0)
-- Successful rear leg then loading leg, with the harvester NEVER moving.
setup();ready();local rear=TASK.rendezvous.rear;V.x,V.z=rear.x,rear.z;DRIVE.reached=true
TASK:update(16);assert(TASK.rendezvous.leg==2 and PF.target.z==8 and not FINISHED)
ready();TASK:update(16);assert(DRIVEN>0)
V.x,V.z=PF.target.x,PF.target.z;DRIVE.reached=true;TASK:update(16)
assert(FINISHED and MODE.combine==C and C.lastSpeedReal==0)
-- Do not accept a route module reporting reached far short of the target.
setup();ready();DRIVE.reached=true;TASK:update(16);assert(not FINISHED and TASK.rendezvous==nil)
-- If the crop begins flowing to this trailer, let normal following take over.
setup();C.getCurrentDischargeNode=function() return {dischargeObject=T} end
C.getDischargeState=function() return 2 end;TASK:update(16);assert(FINISHED)
setup();C.getCurrentDischargeNode=function() return {dischargeObject={}} end
C.getDischargeState=function() return 2 end;TASK:update(16);assert(not FINISHED)
-- Slow/blocked driving tries another approach, rather than generic move-aside.
setup();ready();TASK:update(8001);assert(TASK.rendezvous==nil and MODE.combine==C)
-- Planning timeout and explicit task abort both cancel the pathfinder.
setup();TASK:update(20001);assert(TASK.rendezvous==nil and MODE.combine==C)
setup();TASK:abort();assert(PF.rendezvousZones==nil)
-- Generic idle-clear/ghost/reverse monitors may not steal a stationary rendezvous.
setup();MODE.keepCoverOpen=function() end
CombineUnloaderMode.monitorTasks(MODE,16);assert(MODE.combine==C)
-- Every planner enforces the constraint BEFORE other engine work.
local fake={rendezvousZones=PF.rendezvousZones,
 gridLocationToWorldLocation=function() return {x=0,z=15} end}
local cell={};PathFinderModule.checkGridCell(fake,cell);assert(cell.isRestricted)
assert(not PathFinderModule.isDriveableAstar(fake,{}))
assert(not PathFinderModule.isDriveableDubins(fake,{worldPos={x=0,z=15}}))
-- Rotated harvester: geometry follows its travel frame.
C.h=math.pi/2;C.x,C.z=80,40
local x,_,z=AutoDrive.localToWorld(C,0,0,15)
assert(ADUnloaderClear.rendezvousBlocked(PF.rendezvousZones,x,z))
-- A truck initially ahead can escape sideways, but not move toward the header.
setup();V.x,V.z=1,20
zones=ADUnloaderClear.makeRendezvousZones(V,C)
assert(not ADUnloaderClear.rendezvousBlocked(zones,2,20))
assert(ADUnloaderClear.rendezvousBlocked(zones,1,16))
-- Wider headers and trailers still leave the selected loading lane outside the barrier.
setup();C.size.width=10;T.size.width=4;TASK.rendezvous=nil;TASK:update(16)
assert(PF.target.x>=7.5 and not ADUnloaderClear.rendezvousBlocked(PF.rendezvousZones,PF.target.x,15))
-- Fixed-pipe machines retain their supplied target and never swap discharge sides.
setup();C.ad.isAutoAimingChopper=false;C.ad.isFixedPipeChopper=true
ready({});TASK:update(1100);TASK:update(16);assert(TASK.rendezvous.target.x==7)
-- A moving machine falls back to ordinary catching, canceling the constrained search.
setup();C.lastSpeedReal=0.001
-- od.80 retains a requested, field-contained recovery while moving straight.
-- The previous unconditional stationary branch used to abandon it as soon as speed rose.
-- od.79 fixture shortcut: ADUnloaderEscape.getUnitBoxes=function() return {} end
TASK:update(16);assert(TASK.rendezvous~=nil and PF.rendezvousZones~=nil and not FINISHED)
-- Deleting the assigned machine must not leave a scheduled pathfinder behind.
setup();g_currentMission.nodeToObject[C]=nil;TASK:update(16)
assert(FINISHED and PF.rendezvousZones==nil)
''')
print("PASS: stationary forage rendezvous, alternate lanes/run-ups, assignment retention, rear/loading legs, planner barriers, safe escape and flow handover")
