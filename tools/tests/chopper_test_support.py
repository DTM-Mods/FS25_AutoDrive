"""Stationary-chopper route control/geometry in real Lua 5.1; engine/search/driving are doubles."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[2]
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
AutoDrive={MODE_UNLOAD=1,CHASEPOS_LEFT=1,CHASEPOS_RIGHT=-1,CHASEPOS_REAR=3,CHASEPOS_AUTO=5,PERF_FRAMES=10}
MathUtil={vector2Length=function(x,z) return math.sqrt(x*x+z*z) end}
ADInheritsFrom=function(base)
 local c={}; c.__index=c; setmetatable(c,{__index=base})
 c.create=function() return setmetatable({},c) end; return c
end
AbstractTask={}; AbstractMode={}
Logging={info=function() end}; ADDiag={name=function() return 'vehicle' end}
Dischargeable={DISCHARGE_STATE_OBJECT=2}
AutoDrive.debugPrint=function() end
getWorldTranslation=function(n) return n.x,0,n.z end
AutoDrive.localToWorld=function(v,x,y,z)
 return v.x+x*math.cos(v.h)+z*math.sin(v.h),y,v.z-x*math.sin(v.h)+z*math.cos(v.h)
end
AutoDrive.localDirectionToWorld=function(v,x,y,z)
 return x*math.cos(v.h)+z*math.sin(v.h),y,-x*math.sin(v.h)+z*math.cos(v.h)
end
AutoDrive.worldToLocal=function(v,x,y,z)
 x,z=x-v.x,z-v.z
 return x*math.cos(v.h)-z*math.sin(v.h),y,x*math.sin(v.h)+z*math.cos(v.h)
end
AutoDrive.createWayPointRelativeToVehicle=function(v,x,z)
 local wx,wy,wz=AutoDrive.localToWorld(v,x,0,z); return {x=wx,y=wy,z=wz}
end
AutoDrive.getHarvesterHalfSize=function(v) return v.size.width/2,v.size.length/2 end
AutoDrive.getHarvesterFrameVehicle=function(v) return v end
AutoDrive.getAllUnits=function(v) return v.units or {v} end
AutoDrive.getAllImplements=AutoDrive.getAllUnits
AutoDrive.getBoundingBoxForVehicle=function(v)
 local box={}
 for _,k in ipairs({{-1,-1},{1,-1},{1,1},{-1,1}}) do
  local x,y,z=AutoDrive.localToWorld(v,k[1]*v.size.width/2,0,k[2]*v.size.length/2)
  table.insert(box,{x=x,y=y,z=z})
 end
 return box
end
AutoDrive.getFrontToolWidth=function(v) return v.size.width end
AutoDrive.getSidewaysHarvester=function() return nil end
AutoDrive.getDistanceBetween=function(a,b) return MathUtil.vector2Length(a.x-b.x,a.z-b.z) end
AutoDrive.getTractorTrainLength=function() return 20 end
AutoDrive.getSetting=function(k) if k=='chaseSide' then return CHASE_SETTING or 5 end; return false end
AutoDrive.checkIsOnField=function() return true end
g_fieldManager={fields={{polygonPoints={{x=-200,z=-200},{x=200,z=-200},{x=200,z=200},{x=-200,z=200}}}}}
function obj(x,z)
 local o={x=x,z=z,h=0,size={width=3,length=8},ad={},lastSpeedReal=0}
 o.components={{node=o}};o.ad.ADRootNode=o;o.getRootVehicle=function(self) return self end;return o
end
g_server={}; g_currentMission={nodeToObject={}}
ADScheduler={removePathfinderVehicle=function() end}
''')
for name in ["Manager/HarvesterTurn.lua", "Utils/AutoDriveTON.lua", "Manager/UnloaderEscape.lua", "Manager/UnloaderClear.lua", "Modules/PathFinderModule.lua",
             "Modes/CombineUnloaderMode.lua", "Tasks/CatchCombinePipeTask.lua"]:
    lua.execute((ROOT / "scripts" / name).read_text(encoding="utf-8"))
lua.execute('''
function setup()
 C=obj(0,0);C.size={width=4,length=10};C.ad.isChopper=true;C.ad.isAutoAimingChopper=true
 V=obj(14,-30);T=obj(14,-42);V.units={V,T}
 ADHarvestManager={harvesters={C},unregisterAsUnloader=function() error('assignment lost') end}
 g_currentMission.nodeToObject[C]=C
 STOPPED,DRIVEN,ABORTED,FINISHED=0,0,0,false
 PF={reset=function(self) self.done=false end,
  startPathPlanningTo=function(self,p,d) self.target=p;self.direction=d end,
  abort=function(self) ABORTED=ABORTED+1;self.rendezvousZones=nil end,
  hasFinished=function(self) return self.done end,getPath=function(self) return self.path end,
  update=function(self) end}
 DRIVE={setWayPoints=function(self,p) self.wayPoints=p;self.currentWayPoint=1;self.reached=false end,
  isTargetReached=function(self) return self.reached end,update=function() DRIVEN=DRIVEN+1 end}
 V.ad.pathFinderModule=PF;V.ad.drivePathModule=DRIVE
 V.ad.specialDrivingModule={stopVehicle=function() STOPPED=STOPPED+1 end,update=function() end}
 MODE={vehicle=V,combine=C,getPipeChasePosition=function() return AutoDrive.createWayPointRelativeToVehicle(C,7,8),1 end,
  getSideChaseOffsetX=function() return 7 end,getSideChaseOffsetZ=function() return 10 end,
  getPipeSlopeCorrection=function() return 0 end,getAngleToCombineHeading=function() return 0 end}
 setmetatable(MODE,{__index=CombineUnloaderMode})
 V.ad.modes={[1]=MODE}
 TASK=CatchCombinePipeTask:new(V,C);TASK.trailers={V,T}
 TASK.chopperRecovery=true -- od.80: recovery must be explicitly requested
 V.ad.taskModule={setCurrentTaskFinished=function() FINISHED=true end,getActiveTask=function() return TASK end}
 TASK:update(16)
end
function ready(points)
 PF.done=true;PF.path=points or {{x=PF.target.x,y=0,z=PF.target.z}}
 TASK:update(16)
end
''')
