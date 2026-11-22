"""Physical pipe-side regression tests; engine transforms are doubles, not game physics."""
from pathlib import Path
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[2]
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute("""
AutoDrive={CHASEPOS_LEFT=1,CHASEPOS_RIGHT=-1,CHASEPOS_REAR=3,MODE_UNLOAD=1}
AbstractTask={}; AbstractMode={}
ADInheritsFrom=function() return {} end
AutoDrive.sign=function(x) return x>0 and 1 or x<0 and -1 or 0 end
getWorldTranslation=function(n) return n.x,0,n.z end
AutoDrive.worldToLocal=function(c,x,y,z,node)
    -- Deliberately different pipe-root and travel frames.
    local h=c.h+(node==c.pipeRoot and math.pi or 0)
    x=x-c.x; z=z-c.z
    return x*math.cos(h)-z*math.sin(h),y,x*math.sin(h)+z*math.cos(h)
end
function world(c,x,z)
    return {x=c.x+x*math.cos(c.h)+z*math.sin(c.h),
            z=c.z-x*math.sin(c.h)+z*math.cos(c.h)}
end
function fixture(h,side)
    C={x=100,z=200,h=h,size={width=4,length=10},ad={isHarvester=true},
       spec_pipe={currentState=2},out=true,pipeRoot={}}
    C.ad.ADRootNode={}; C.ad.pipeRoot=C.pipeRoot
    C.ad.storedPipeSide=-side -- stale legacy cache must not determine travel side
    C.tip=world(C,side*8,2)
    C.spec_dischargeable={dischargeNodes={{node=C.tip}}}
    V={size={width=3,length=8},ad={}}
    MODE=setmetatable({combine=C,vehicle=V},{__index=CombineUnloaderMode})
    F=setmetatable({combine=C,vehicle=V,chaseSide=3,chasePos=world(C,-side*8,-10)},
                   {__index=FollowCombineTask})
end
""")
for name in ("Utils/CombineUtil.lua", "Modes/CombineUnloaderMode.lua", "Tasks/FollowCombineTask.lua"):
    lua.execute((ROOT / "scripts" / name).read_text(encoding="utf-8"))
lua.execute("""
AutoDrive.isPipeOut=function(c) return c.out end
AutoDrive.getHarvesterHalfSize=function(c) return c.size.width/2,c.size.length/2 end
""")
cases = 0
for heading in (0, 0.4, 1.5707963267948966, 3.141592653589793, -2.4):
    for side in (1, -1):
        lua.execute(f"fixture({heading},{side})")
        assert lua.eval("AutoDrive.getPipeSide(C)") == side
        assert lua.eval("F:getPipeSide()") == side  # rear waypoint is on opposite side
        lua.execute(f"V.components={{{{node=world(C,{-side*8},-20)}}}}; V.h=C.h+math.pi")
        truck_side, pipe_side, x, z = lua.eval("F:getSides()")
        assert truck_side == -side and pipe_side == side and abs(z + 20) < 1e-9
        assert abs(lua.eval("MODE:getRearChaseOffsetX(false,false)") - side * 4.5) < 1e-9
        lua.execute("C.spec_pipe.currentState=0; C.tip=world(C,0.1,1); C.spec_dischargeable.dischargeNodes[1].node=C.tip")
        assert lua.eval("AutoDrive.getPipeSide(C)") == side
        lua.execute("C.out=false; C.spec_pipe.currentState=1")
        assert lua.eval("AutoDrive.getPipeSide(C)") == side
        cases += 1

lua.execute("fixture(0,1)")
assert lua.eval("MODE:getRearChaseOffsetX(true,false)") == 0
lua.execute("fixture(0,-1)")
assert lua.eval("MODE:getRearChaseOffsetX(false,true)") == 0
lua.execute("fixture(0,1); C.spec_pipe.currentState=0")
assert lua.eval("AutoDrive.getPipeSide(C)") == 0
assert lua.eval("F:getPipeSide()") is None
assert lua.eval("MODE:getRearChaseOffsetX(false,false)") == 0
lua.execute("C.spec_pipe.currentState=2; C.tip.x=C.x+0.1")
assert lua.eval("AutoDrive.getPipeSide(C)") == 0  # don't learn a centreline sign
lua.execute("fixture(0,1); V.components={{node=world(C,0.1,-20)}}")
assert lua.eval("F:getSides()")[0] == 0
lua.execute("V.components[1].node=world(C,-0.1,-20)")
assert lua.eval("F:getSides()")[0] == 0

# Exercise the real chase-target selector, including its standing/planning
# exception, rather than testing only the offset helper.
lua.execute("""
fixture(0,1); C.out=false; C.ad.noMovementTimer={elapsedTime=5000}
local sensor={setSwathDetection=function() end,pollInfo=function() return false end}
AutoDrive.getCombineSensors=function() return setmetatable({},{__index=function() return sensor end}) end
AutoDrive.getSetting=function() return false end
AutoDrive.getNextFreeDischargeableUnit=function() return 1,1 end
AutoDrive.createWayPointRelativeToVehicle=function(c,x,z) return world(c,x,z) end
MODE.getSideChaseOffsetX=function() return 8 end
MODE.getSideChaseOffsetZ=function() return 0 end
MODE.getRearChaseOffsetZ=function() return -45 end
MODE.getPipeSlopeCorrection=function() return 0 end
MODE.getAngleToChasePos=function() return 0 end
MODE.isUnloaderOnCorrectSide=function() return true end
local target,side=MODE:getPipeChasePosition(true)
assert(side==AutoDrive.CHASEPOS_REAR and target.x==C.x)
""")

# Unknown physical side must stop before pipe running or chasing, while still
# allowing the existing front-strip clearance to take priority.
lua.execute("""
fixture(0,1); C.out=false
F.stuckTimer={timer=function() end}; F.angleWrongTimer=F.stuckTimer
STOPS=0; CLEARS=0; UNSAFE=false
V.ad.specialDrivingModule={stopVehicle=function() STOPS=STOPS+1 end,update=function() end}
ADUnloaderClear={clearApproach=function() CLEARS=CLEARS+1; return UNSAFE end}
F.updatePipeRun=function() error('unknown side must not drive') end
F:updatePipeLock(100)
assert(STOPS==1 and CLEARS==1)
UNSAFE=true; F:updatePipeLock(100)
assert(STOPS==1 and CLEARS==2)
""")
print(f"PASS: {cases} rotated left/right layouts; folding, stale cache, rear targets, blocked lanes, centreline and unknown-side holds")
