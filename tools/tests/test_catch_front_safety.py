"""od.77: execute real approach geometry, task updates and move-aside handover in Lua 5.1.

Engine positions and driving modules are doubles; rectangle intersection, vehicle footprints,
front strip, route sweep, task abort/queue, and clearance decisions are production Lua.
This is a regression test, not an in-game driving/physics validation.
"""
from pathlib import Path
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[2]
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute("""
AutoDrive = {MODE_UNLOAD=1, CHASEPOS_REAR=3, CHASEPOS_FRONT=4, CHASEPOS_UNKNOWN=0}
NetworkNode={}; Sprayer={}; Utils={overwrittenFunction=function(original) return original end}
MathUtil = {vector2Length=function(x,z) return math.sqrt(x*x+z*z) end}
ADInheritsFrom = function(base)
    local c = {}; c.__index=c; setmetatable(c,{__index=base})
    c.create=function() return setmetatable({},c) end; return c
end
getWorldTranslation=function(node) return node.x,0,node.z end
entityExists=function() return true end
AutoDrive.localDirectionToWorld=function(v,x,y,z)
    return x*math.cos(v.h)+z*math.sin(v.h),y,-x*math.sin(v.h)+z*math.cos(v.h)
end
localDirectionToWorld=AutoDrive.localDirectionToWorld
AutoDrive.getVehicleDimensions=function(v) return v.size.width,v.size.length end
AutoDrive.getAllImplements=function(v) return v.units or {v} end
AutoDrive.getAllUnits=AutoDrive.getAllImplements
AutoDrive.getHarvesterHalfSize=function(v) return v.size.width/2,v.size.length/2 end
AutoDrive.getHarvesterFrameVehicle=function(v) return v end
AutoDrive.getSidewaysHarvester=function() return nil end
AutoDrive.getSetting=function() return false end
AutoDrive.debugPrint=function() end
AutoDrive.getTractorTrainLength=function() return 20 end
Logging={info=function() end}
ADDiag={name=function() return 'truck' end}
g_server={}; g_currentMission={terrainRootNode=1,nodeToObject={}}
getTerrainHeightAtWorldPos=function() return 0 end
CombineUnloaderMode={PATH_TIMEOUT=30000}
Queue={new=function() return {items={},Clear=function(s) s.items={} end,
    Enqueue=function(s,v) table.insert(s.items,v) end} end}
function obj(x,z,h,w,l)
    local v={x=x,z=z,h=h or 0,size={width=w or 3,length=l or 8,lengthOffset=0},ad={},lastSpeedReal=0}
    v.components={{node=v}}; v.ad.ADRootNode=v
    v.getRootVehicle=function(s) return s end
    return v
end
""")
for name in ("Utils/UtilFuncs.lua", "Utils/CollisionDetectionUtils.lua", "Utils/AutoDriveTON.lua",
             "Tasks/AbstractTask.lua", "Modules/TaskModule.lua", "Manager/UnloaderEscape.lua",
             "Manager/UnloaderClear.lua", "Tasks/MoveClearOfHarvesterTask.lua",
             "Tasks/CatchCombinePipeTask.lua", "Tasks/FollowCombineTask.lua"):
    lua.execute((ROOT / "scripts" / name).read_text(encoding="utf-8"))
lua.execute("""
AutoDrive.debugPrint=function() end
AutoDrive.selectVehicleNode=function(v,node) return node or v.components[1].node end
C=obj(0,0,0,4,10); C.ad.isHarvester=true
V=obj(0,25,math.pi,3,8); T=obj(30,25,0,3,12); V.units={V,T}
g_currentMission.nodeToObject[C]=C
ADHarvestManager={harvesters={C},unregisterAsUnloader=function() UNREGISTERED=true end}
ENTRY={harvester=C,root=C,frame=C,width=6}
ENTRIES={ENTRY}
function danger(points,index)
    return ADUnloaderClear.getApproachDanger(V,ENTRIES,points,index)
end
MODE={vehicle=V,STATE_MOVE_CLEAR=99}
V.ad.modes={[1]=MODE}
STOPS=0; DRIVES=0; ABORTS=0
V.ad.specialDrivingModule={stopVehicle=function() STOPS=STOPS+1 end,
    update=function() end,releaseVehicle=function() end}
V.ad.drivePathModule={update=function() DRIVES=DRIVES+1 end}
V.ad.pathFinderModule={abort=function() ABORTS=ABORTS+1 end}
V.ad.taskModule=setmetatable({tasks=Queue:new(),onTaskChange=function() end},{__index=ADTaskModule})
ADUnloaderClear.getFruits=function() return nil end
SAFE=true
ADUnloaderClear.findSafeSpot=function() if SAFE then return 40,25,0,1 end end
function catch(state)
    MODE.combine=C; MODE.state=1; MODE.followingUnloader=T; MODE.targetUnloader=T
    local task=CatchCombinePipeTask:new(V,C); task.state=state; task.lastState=state
    V.ad.taskModule.activeTask=task
    task.shouldChaseDirectly=function() DIRECT_CHECKED=true; return true end
    return task
end
""")

checks = 0


def check(name, code):
    global checks
    lua.execute(code)
    checks += 1
    print("ok  " + name)


check("head-on truck already in the front zone", "assert(danger() == ENTRY)")
check("safe truck, trailer still across the front", "V.x=30; T.x=0; assert(danger() == ENTRY)")
check("whole train clear beside the strip", "T.x=30; assert(danger() == nil)")
check("swept segment detects crossing even with both waypoints outside",
      "V.x=-12; V.z=25; assert(danger({{x=12,z=25}}) == ENTRY)")
check("safe parallel approach stays outside the strip",
      "V.x=15; V.z=-15; assert(danger({{x=15,z=60}}) == nil)")
check("only upcoming waypoints count",
      "assert(danger({{x=0,z=25},{x=15,z=-30}},2) == nil)")
check("corner in route is checked, not a straight line to final target",
      "V.x=-12; V.z=25; assert(danger({{x=-12,z=26},{x=12,z=26}}) == ENTRY)")
check("distant route hazard outside the preview does not divert yet",
      "V.x=-60; V.z=25; V.lastSpeedReal=0; assert(danger({{x=30,z=25}}) == nil)")
check("higher approach speed extends preview to braking distance",
      "V.lastSpeedReal=0.015; assert(danger({{x=30,z=25}}) == ENTRY)")
check("rotated harvester front strip uses its actual heading",
      "V.lastSpeedReal=0; C.h=math.pi/2; V.x=25; V.z=0; assert(danger() == ENTRY); C.h=0")

for state in ("STATE_DRIVING", "STATE_PATHPLANNING", "STATE_DELAY_PATHPLANNING", "STATE_REVERSING"):
    check("front clearance precedes " + state + " and direct-chase handover", f"""
        V.x=0; V.z=25; V.lastSpeedReal=0.01; DIRECT_CHECKED=false; DRIVES=0
        TASK=catch(CatchCombinePipeTask.{state}); TASK:update(16)
        assert(not DIRECT_CHECKED and DRIVES==0 and MODE.state==MODE.STATE_MOVE_CLEAR)
        assert(MODE.combine==nil and MODE.followingUnloader==nil and MODE.targetUnloader==nil)
        assert(V.ad.taskModule.activeTask==nil and #V.ad.taskModule.tasks.items==1)
        assert(MODE.activeTask.target.x==40 and MODE.activeTask.straightFallback==false)
    """)

check("route hazard diverts a truck not yet in the strip", """
    V.x=-12; V.z=25; V.ad.drivePathModule.wayPoints={{x=12,z=25}}
    V.ad.drivePathModule.currentWayPoint=1; DIRECT_CHECKED=false
    TASK=catch(CatchCombinePipeTask.STATE_DRIVING); TASK:update(16)
    assert(not DIRECT_CHECKED and MODE.state==99)
    V.ad.drivePathModule.wayPoints=nil
""")
check("no safe spot: brake and retry without driving old route or blind fallback", """
    V.x=0; V.z=25; SAFE=false; DRIVES=0; DIRECT_CHECKED=false
    TASK=catch(CatchCombinePipeTask.STATE_DRIVING); TASK:update(16)
    assert(V.ad.taskModule.activeTask==TASK and MODE.state==1 and not DIRECT_CHECKED and DRIVES==0)
    SAFE=true; TASK:update(16); assert(MODE.state==99)
""")
check("safe approach still hands over directly", """
    V.x=30; V.z=25; DIRECT_CHECKED=false
    TASK=catch(CatchCombinePipeTask.STATE_DRIVING)
    TASK.finished=function() FINISHED=true end; FINISHED=false
    TASK:update(16); assert(DIRECT_CHECKED and FINISHED)
""")
check("harvester collision exclusion removed in all catch states", """
    for _,state in ipairs({CatchCombinePipeTask.STATE_DRIVING,CatchCombinePipeTask.STATE_PATHPLANNING,
        CatchCombinePipeTask.STATE_REVERSING}) do
        TASK.state=state; assert(#TASK:getExcludedVehiclesForCollisionCheck()==0)
    end
""")
check("client cannot initiate a safety task", """
    V.x=0; g_server=nil; assert(not ADUnloaderClear.clearApproach(TASK,16,true)); g_server={}
""")
check("missing destination never enables a forbidden straight fallback", """
    MOVE=MoveClearOfHarvesterTask:new(V,nil,nil,false)
    MOVE.finished=function() FINISHED=true end
    ADUnloaderClear.onMoveFailed=function() FAILED=true end
    FINISHED=false; FAILED=false; MOVE:setUp()
    assert(FAILED and FINISHED and MOVE.state~=MoveClearOfHarvesterTask.STATE_STRAIGHT)
""")
check("failed clearance route never drives blindly forward", """
    MOVE=MoveClearOfHarvesterTask:new(V,{x=40,y=0,z=25},{x=0,z=1},false)
    MOVE.finished=function() FINISHED=true end; FINISHED=false; FAILED=false
    MOVE:onNoPath(); assert(FAILED and FINISHED and MOVE.state~=MoveClearOfHarvesterTask.STATE_STRAIGHT)
""")
check("rear corner back-off stops at 15 m and stays stopped after drift", """
    V.z=0; REVERSES=0
    V.ad.trailerModule={canBeHandledInReverse=function() return true end}
    V.ad.specialDrivingModule.driveReverse=function() REVERSES=REVERSES+1 end
    FOLLOW=setmetatable({vehicle=V,combine=C},{__index=FollowCombineTask})
    FOLLOW:updateTurnBack(16); assert(REVERSES==1)
    V.z=-14.9; FOLLOW:updateTurnBack(16); assert(REVERSES==2)
    V.z=-15; FOLLOW:updateTurnBack(16); assert(FOLLOW.turnBackDone and REVERSES==2)
    V.z=-14; FOLLOW:updateTurnBack(16); assert(REVERSES==2)
""")
check("wrong side remembered across tasks and cleared after unloading starts", """
    AutoDrive.getPipeSide=function() return 1 end
    worldToLocal=function(v,x,y,z)
        local dx,dz=x-v.x,z-v.z
        return dx*math.cos(v.h)-dz*math.sin(v.h),y,dx*math.sin(v.h)+dz*math.cos(v.h)
    end
    AutoDrive.setTrailerCoverOpen=function() end
    V.x=-10; V.z=-25
    FOLLOW:rememberWrongSide(); assert(MODE.odWrongSide.combine==C and MODE.odWrongSide.side==-1)
    FOLLOW=setmetatable({vehicle=V,combine=C},{__index=FollowCombineTask})
    FOLLOW:setUp(); assert(FOLLOW.rememberedWrong and FOLLOW.pushedOutSide==-1)
    FOLLOW:forgetWrongSide(); assert(MODE.odWrongSide==nil and FOLLOW.rememberedWrong==nil)
""")
check("a new harvester does not inherit the old harvester's wrong side", """
    MODE.odWrongSide={combine={},side=-1}; FOLLOW:setUp()
    assert(MODE.odWrongSide==nil and FOLLOW.pushedOutSide==nil)
""")
check("remembered crossing target cannot cut inside the 12 m tail clearance", """
    localToWorld=function(v,x,y,z)
        local dx,_,dz=localDirectionToWorld(v,x,y,z); return v.x+dx,y,v.z+dz
    end
    FOLLOW.rememberedWrong=true; FOLLOW.chaseSide=1; FOLLOW.chasePos={x=8,y=0,z=0}
    FOLLOW.getCabSpanZ=function() return -6,-14 end
    FOLLOW.getKeepOutLane=function() return 8 end
    local lane=FOLLOW:getLaneApproach(-8,-10,8,2,5)
    assert(lane.steer.z<=-17)
""")
check("let-it-pass hold in the front strip starts moving clear", """
    Dischargeable={DISCHARGE_STATE_OBJECT=1}; C.lastSpeedReal=0.003
    V.x=0; V.z=25; V.h=math.pi; V.lastSpeedReal=0
    FOLLOW=setmetatable({vehicle=V,combine=C,chaseSide=1,chasePos={x=8,y=0,z=0},
        state=FollowCombineTask.STATE_CHASING,stuckTimer=AutoDriveTON:new(),angleWrongTimer=AutoDriveTON:new(),
        updatePipeRun=function() return false end,updateTurnRate=function() end,
        updateBackOff=function() return false end,getCabSpanZ=function() return 29,21 end},
        {__index=FollowCombineTask})
    MODE.state=1; V.ad.taskModule.activeTask=FOLLOW
    FOLLOW:updatePipeLock(16); assert(MODE.state==99)
""")
check("wrong-side hold in the front strip also starts moving clear", """
    V.x=-8; V.z=25; FOLLOW.wrongSideTime=2000
    MODE.state=1; V.ad.taskModule.activeTask=FOLLOW
    FOLLOW:updatePipeLock(16); assert(MODE.state==99)
""")
check("aborting catch-up planning cancels the old pathfinder", """
    TASK=catch(CatchCombinePipeTask.STATE_PATHPLANNING); ABORTS=0
    TASK:abort(); assert(ABORTS==1)
""")
print(f"PASS: {checks} approach safety regressions (Lua 5.1)")
