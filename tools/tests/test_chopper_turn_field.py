"""od.80: real shared controller, Follow/Catch transitions and field geometry.

Engine motion, discharge state and native path search are doubles. Field polygons,
road gaps, initial train footprints, turn signals and lifecycle are exercised explicitly.
"""
from chopper_test_support import lua, ROOT

lua.execute((ROOT / "scripts/Tasks/FollowCombineTask.lua").read_text(encoding="utf-8"))
lua.execute((ROOT / "scripts/Modules/DrivePathModule.lua").read_text(encoding="utf-8"))
lua.execute('''
AutoDrive.getIsCPTurning=function() return TURNING or false end
AutoDrive.getIsCPWaitingForUnload=function() return NEEDS_TRAILER or false end
local originalBoxes=ADUnloaderEscape.getUnitBoxes
function rectangle(x1,z1,x2,z2)
 return {polygonPoints={{x=x1,z=z1},{x=x2,z=z1},{x=x2,z=z2},{x=x1,z=z2}}}
end
function reset()
 TURNING=false;NEEDS_TRAILER=false
 g_fieldManager={fields={rectangle(-200,-200,200,200)}}
 AutoDrive.checkIsOnField=function() return true end
 ADUnloaderEscape.getUnitBoxes=originalBoxes
 setup()
end
function follow()
 FOLLOWS=0;QUEUED=nil
 V.ad.taskModule.abortAllTasks=function() end
 V.ad.taskModule.addTask=function(self,task) QUEUED=task end
 MODE.STATE_DRIVE_TO_COMBINE=CombineUnloaderMode.STATE_DRIVE_TO_COMBINE
 local f=setmetatable({vehicle=V,combine=C,combineRootVehicle=C,trailers={V,T},
  state=FollowCombineTask.STATE_CHASING,filled=false,
  stuckTimer=AutoDriveTON:new(),angleWrongTimer=AutoDriveTON:new(),waitForTurnTimer=AutoDriveTON:new(),
  updateStates=function() end,followChasePoint=function() FOLLOWS=FOLLOWS+1 end},
  {__index=FollowCombineTask})
 return f
end

-- Early CP turn: no 47-degree delay, including while the pickup stays lowered.
reset();local pickup={spec_pickup={},low=true,getIsLowered=function(self) return self.low end}
C.getChildVehicles=function() return {C,pickup} end
local f=follow();f:update(16);assert(FOLLOWS==1)
TURNING=true;f:update(16)
assert(f.harvesterTurnHold and FOLLOWS==1 and STOPPED>0 and QUEUED==nil)
assert(string.find(f:getI18nInfo(),'AD_task_wait_for_combine_turn',1,true))
-- Neither the 3s stopped heuristic nor old 60s turn timeout may drive into a live CP turn.
f:update(61000);assert(f.harvesterTurnHold and FOLLOWS==1 and QUEUED==nil)
-- Header stays up: keep waiting after CP's flag clears.
pickup.low=false;TURNING=false;f:update(1000);assert(f.harvesterTurnHold)
-- Clean release queues a fresh field-contained approach with assignment retained.
f.lineDir={x=1,z=0};f.turnSwing=9;f.combineTurnRate=3;f.laneLined=true
pickup.low=true;f:update(250);assert(QUEUED==nil)
f:update(250)
assert(QUEUED and QUEUED.chopperRecovery and QUEUED.combine==C and MODE.combine==C)
assert(f.lineDir==nil and f.turnSwing==nil and f.combineTurnRate==nil and f.laneLined==nil)
-- Turning detection doesn't turn ordinary steering corrections into stop commands.
reset();f=follow();f:update(16);C.h=0.1;f:update(16)
assert(not f.harvesterTurnHold and FOLLOWS==2 and QUEUED==nil)
-- Stationary chopper needing a trailer can pause the turn and load, then continue turning.
reset();f=follow();TURNING=true;f:update(16)
NEEDS_TRAILER=true;f:update(1000)
assert(QUEUED and QUEUED.chopperRecovery and not f.harvesterTurnHold)
reset();TURNING=true;NEEDS_TRAILER=true;C.lastSpeedReal=0.001
assert(ADHarvesterTurn.update(TASK,2000)) -- moving turn cannot claim an unload-pause exemption
-- A fixed pipe has the same early hold; no special auto-aim-only loophole.
reset();C.ad.isAutoAimingChopper=false;C.ad.isFixedPipeChopper=true;f=follow();TURNING=true
f:update(16);assert(f.harvesterTurnHold and FOLLOWS==0)
-- Mode escape/idle/stuck monitors cannot issue movement while the shared hold owns control.
V.ad.taskModule.getActiveTask=function() return f end;MODE.keepCoverOpen=function() end
CombineUnloaderMode.monitorTasks(MODE,1000);assert(MODE.combine==C)
MODE.state=CombineUnloaderMode.STATE_ACTIVE_UNLOAD_COMBINE
MODE.leaveBreadCrumbs=function(self) self.crumbCalls=(self.crumbCalls or 0)+1 end
CombineUnloaderMode.monitorTasks(MODE,16);assert(MODE.crumbCalls==1)
-- A queued post-turn approach owns the handover frame before it becomes the active task.
MODE.state=CombineUnloaderMode.STATE_DRIVE_TO_COMBINE
MODE.activeTask={chopperRecovery=true};V.ad.taskModule.getActiveTask=function() return nil end
CombineUnloaderMode.monitorTasks(MODE,16);assert(MODE.combine==C)
-- A normal valid catch is not replaced by an unconditional long rear manoeuvre.
reset();TASK.chopperRecovery=nil;TASK.rendezvous=nil
TASK.shouldChaseDirectly=function() return true end;TASK.lastState=TASK.state
TASK:update(16);assert(FINISHED and TASK.rendezvous==nil)
reset();TASK.chopperRecovery=nil;TASK:waitForCrop()
assert(TASK.chopperRecovery and MODE.combine==C) -- try another legal lane without a call-cycle reset
-- Native async discharge detection uses the last raycast object, and only this train.
reset();C.spec_pipe={isAsyncRaycastActive=true}
C.getDischargeState=function() return 2 end
C.getCurrentDischargeNode=function() return {lastDischargeObject=T} end
assert(ADHarvesterTurn.receiving(TASK))
C.getCurrentDischargeNode=function() return {lastDischargeObject={},dischargeObject=T} end
assert(not ADHarvesterTurn.receiving(TASK))
C.getCurrentDischargeNode=function() return {dischargeObject=T} end
assert(not ADHarvesterTurn.receiving(TASK)) -- async nil must not fall back to a stale synchronous result
-- A chopper remains an obstacle in both chasing and turn-wait states.
f=follow();assert(#f:getExcludedVehiclesForCollisionCheck()==0)
f.state=FollowCombineTask.STATE_WAIT_FOR_TURN;assert(#f:getExcludedVehiclesForCollisionCheck()==0)
-- The real follow method applies whole-train keep-out steering AND dynamic collision checks.
reset();f=follow();f.followChasePoint=nil
localToWorld=AutoDrive.localToWorld
f.chasePos={x=7,y=0,z=8};f.chaseSide=1;f.chaseTimer=AutoDriveTON:new()
f.isCaughtCurrentChaseSide=function() return true end
f.shouldWaitForChasePos=function() return false end
V.ad.specialDrivingModule.driveToPoint=function(self,dt,point,speed,dynamic)
 assert(dynamic==true);DRIVEN=DRIVEN+1
end
f:followChasePoint(16);assert(DRIVEN==1)
f:followChasePoint(8001)
assert(QUEUED and QUEUED.chopperRecovery and DRIVEN==1) -- blocked follow must recover, never generic reverse
-- Preserve a fixed/rear discharge lane when the entire train is behind the tail.
reset();f=follow();f.followChasePoint=nil
V.x,V.z=0,-30;T.x,T.z=0,-42
f.chasePos={x=0,y=0,z=-25};f.chaseSide=AutoDrive.CHASEPOS_REAR;f.chaseTimer=AutoDriveTON:new()
f.isCaughtCurrentChaseSide=function() return true end;f.shouldWaitForChasePos=function() return false end
f.keepOffHarvester=function() error('rear lane must not be pushed onto a bunker side lane') end
V.ad.specialDrivingModule.driveToPoint=function(self,dt,point,speed,dynamic,acc,max,chase,steer)
 assert(dynamic and steer.x==0);DRIVEN=DRIVEN+1
end
f:followChasePoint(16);assert(DRIVEN==1)
-- The real 8s path no-progress handler returns to this task instead of restarting AD.
reset();V.isServer=true
V.ad.taskModule.stopAndRestartAD=function() error('must not restart and lose this assignment') end
V.ad.specialDrivingModule.isStoppingVehicle=function() return false end
local nav=setmetatable({vehicle=V,minDistanceTimer=AutoDriveTON:new(),minDistanceToNextWp=0,
 getCurrentWayPoint=function() return {x=24,z=-30} end},{__index=ADDrivePathModule})
assert(nav:checkIfStuck(8001)==true)
assert(TASK.chopperRecovery and TASK.rendezvous==nil and MODE.combine==C)

-- Same owner/field-ground isn't enough: the neighbouring polygon is a different field.
reset();C.x=-12;V.x=-15;T.x=-15
g_fieldManager.fields={rectangle(-60,-60,0,60),rectangle(5,-60,60,60)}
local field=ADUnloaderClear.captureWorkingField(C)
assert(field and ADUnloaderClear.fieldContains(field,-10,0))
assert(not ADUnloaderClear.fieldContains(field,10,0))
local zones=ADUnloaderClear.makeRendezvousZones(V,C)
ADUnloaderClear.setRendezvousField(zones,V,C,field)
assert(not ADUnloaderClear.rendezvousPathSafe(zones,{{x=20,z=-30}},{x=-15,z=-30}))
-- A road gap inside a coarse map polygon is still forbidden after smoothing.
reset();C.x=-12;V.x=-15;T.x=-15
field=ADUnloaderClear.captureWorkingField(C)
AutoDrive.checkIsOnField=function(x) return x<0 or x>5 end
zones=ADUnloaderClear.makeRendezvousZones(V,C)
ADUnloaderClear.setRendezvousField(zones,V,C,field)
assert(not ADUnloaderClear.rendezvousPathSafe(zones,{{x=20,z=-30}},{x=-15,z=-30}))
-- Both ends of a row: discarded 35/50/65m goals would cross the boundary/road.
for _,edge in ipairs({-1,1}) do
 reset();g_fieldManager.fields={rectangle(-60,-30,60,30),rectangle(-60,35,60,80)}
 C.z=edge*20;C.h=edge==1 and math.pi or 0
 V.x,V.z,V.h=14,0,C.h;T.x,T.z,T.h=14,edge*12,C.h
 TASK.rendezvous=nil;TASK.workingField=nil;TASK:update(1100)
 assert(TASK.rendezvous and TASK.rendezvous.leg==2) -- safe lane instead of an off-field rear point
 assert(PF.stayOnField and PF.restrictToField)
 assert(ADUnloaderClear.fieldContains(TASK.workingField,PF.target.x,PF.target.z))
 assert(math.abs(PF.target.z)<30)
 -- Inspect the REAL planner's fallback guards, including when the UI setting was false.
 assert(not (PF.restrictToField and not PF.stayOnField))
end
-- Initial close-side position can leave the envelope, but never cut inward or re-enter it.
reset();V.x,V.z=3,0;T.x,T.z=6,-12
zones=ADUnloaderClear.makeRendezvousZones(V,C)
assert(not ADUnloaderClear.rendezvousBlocked(zones,3.5,0))
assert(ADUnloaderClear.rendezvousBlocked(zones,2.5,0))
assert(ADUnloaderClear.rendezvousPathSafe(zones,{{x=6,z=0}},{x=3,z=0}))
assert(not ADUnloaderClear.rendezvousPathSafe(zones,{{x=6,z=0},{x=3.5,z=0}},{x=3,z=0}))
-- Actual trailer corners must stay in the same field, even when the cab is inside it.
reset();g_fieldManager.fields={rectangle(-60,-30,60,30)}
field=ADUnloaderClear.captureWorkingField(C);V.z=0;T.z=-29
assert(not ADUnloaderClear.trainOnField(V,field))
-- An unavailable map boundary never enables a free-road fallback.
reset();g_fieldManager=nil;TASK.rendezvous=nil;TASK.workingField=nil;TASK:update(16)
assert(TASK.rendezvous==nil and STOPPED>0)
''')
print("PASS: early turn hold/clean resume, paused unloading, pickup/fixed pipes, normal catch, async flow, both field edges, road gap, neighbouring field, close-side escape and trailer bounds")
