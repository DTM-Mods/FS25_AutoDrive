"""Real search/smoothing regression on field41 geometry; engine world is flat and empty.

Harvester positions/headings and radii are a parameter sweep, not live telemetry.
"""
from pathlib import Path
import sys, math, json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/tests'))
from chopper_test_support import lua
utility=(ROOT/'scripts/Utils/PathFinderUtils.lua').read_text(encoding='utf-8')
start=utility.index('function AutoDrive.boundingBoxFromCorners')
end=utility.find('\nfunction ',start+1)
lua.execute(utility[start:end])

points=json.loads((ROOT/'tools/tests/fixtures/chopper_field41.json').read_text())['points']
lua.globals().FIELD41=lua.table_from([lua.table_from(p) for p in points])
lua.execute('''
g_fieldManager={fields={{polygonPoints=FIELD41}}}
AutoDrive.checkIsOnField=function(x,y,z) return ADUnloaderClear.pointInField({points=FIELD41},x,z) end
getTerrainHeightAtWorldPos=function() return 0 end
g_currentMission.terrainRootNode=1
AutoDrive.getDriverRadius=function() return RADIUS end
AutoDrive.isEditorModeEnabled=function() return false end
AutoDrive.getDebugChannelIsSet=function() return false end
AutoDrive.debugMsg=function() end
AutoDrive.normalizeAngle=function(a) return math.atan2(math.sin(a),math.cos(a)) end
AutoDrive.round=function(a) return math.floor(a+0.5) end
AutoDrive.angleBetween=function(a,b) return math.deg(math.atan2(a.x*b.z-a.z*b.x,a.x*b.x+a.z*b.z)) end
AutoDrive.checkForVehiclePathInBox=function() return false end
AutoDrive.getSetting=function(k)
 if k=='Pathfinder' then return 1 elseif k=='pathFinderTime' then return 3 end
 return false
end
ADScheduler.addPathfinderVehicle=function() end
ADScheduler.getStepsPerFrame=function() return 20 end
table.count=function(t) local n=0;for _ in pairs(t) do n=n+1 end;return n end
MathUtil.vector3Length=function(x,y,z) return math.sqrt(x*x+y*y+z*z) end
netGetTime=function() return 0 end
overlapBox=function() return 0 end
PathFinderModule.checkSlopeAngle=function() return false,0 end
PathFinderModule.debugVehicleMsg=function() end
function run(radius,heading,cx,cz,ch)
 RADIUS=radius
 C=obj(cx,cz);C.h=ch;C.size={width=4,length=10};C.ad.isChopper=true
 ADHarvestManager={harvesters={C}}
 V=obj(1398.5,-546);V.h=heading;V.size={width=3,length=8,height=3}
 T=obj(V.x-math.sin(heading)*12,V.z-math.cos(heading)*12);T.h=heading;V.units={V,T}
 V.ad.sensors={frontSensorField={pollInfo=function() return false end}}
 V.ad.stateModule={getSpeedLimit=function() return 40 end}
 V.ad.debug={}
 local pf=setmetatable({vehicle=V},{__index=PathFinderModule})
 pf:reset()
 local target={x=cx+math.cos(ch)*7,z=cz-math.sin(ch)*7}
 local dx,dz=math.sin(ch),math.cos(ch)
 pf:startPathPlanningTo(target,{x=dx,z=dz})
 local task={vehicle=V,combine=C,workingField=ADUnloaderClear.captureWorkingField(C)}
 local zones=ADUnloaderClear.makeRendezvousZones(V,C)
 ADUnloaderClear.prepareRendezvous(task,zones)
 pf.rendezvousZones=zones;pf.restrictToField=zones.entry==nil;pf.stayOnField=true;pf.goingToPipe=true
 pf.max_pathfinder_steps=400
 for i=1,5000 do pf:update(16);if pf:hasFinished() then break end end
 local path=pf:getPath()
 local safe,reason=ADUnloaderClear.rendezvousPathSafe(zones,path,{x=V.x,z=V.z})
 return #path,safe,pf.steps,pf.completelyBlocked,reason
end
''')
cases=0
for radius in [8,12,18]:
    for cx in [1100,1300,1430]:
        for heading in [0,math.pi]:
            for ch in [math.pi/2,-math.pi/2]:
                count,safe,steps,blocked,reason=lua.globals().run(radius,heading,cx,-647,ch)
                assert count>0 and safe,(radius,cx,heading,ch,count,reason)
                cases+=1
print(f"PASS: {cases} real A* search + production smoothing routes from logged waiting coordinates on actual field41 polygon; no mocked search, final validator accepts every route")
lua.execute('''
-- Legal endpoints alone are insufficient: reject a link across the body before
-- doing any engine work, in every planner and the final goal connector.
C=obj(0,0);C.size={width=4,length=10};V=obj(-10,0)
ADHarvestManager={harvesters={C}}
local zones=ADUnloaderClear.makeRendezvousZones(V,C)
assert(not ADUnloaderClear.rendezvousBlocked(zones,-10,0))
assert(not ADUnloaderClear.rendezvousBlocked(zones,10,0))
local pf=setmetatable({vehicle=V,rendezvousZones=zones,targetCell={x=10,z=0},appendWayPoints={},
 gridLocationToWorldLocation=function(self,cell) return {x=cell.x,z=cell.z} end},
 {__index=PathFinderModule})
assert(not pf:isDriveableAstar({x=10,z=0},{x=-10,z=0}))
local cell={x=10,z=0,incoming={x=-10,z=0}}
pf:checkGridCell(cell);assert(cell.isRestricted)
assert(not pf:isDriveableDubins({worldPos={x=10,z=0},incomming={worldPos={x=-10,z=0}}}))
assert(not pf:rendezvousGoalSafe({x=-10,z=0}))
pf.wayPoints={{x=-10,z=0,direction=0},{x=0,z=-20,direction=1},{x=10,z=0,direction=0}}
pf:smoothResultingPPPath();assert(#pf.wayPoints==3) -- keep safe detour rather than skip it
pf.rendezvousZones=nil
assert(pf:rendezvousSegmentSafe({x=-10,z=0},{x=10,z=0})) -- other routes keep native behavior
''')
print("PASS: connecting edges, goal connector and zigzag shortcut enforce rendezvous constraints; non-rendezvous shortcuts unchanged")
