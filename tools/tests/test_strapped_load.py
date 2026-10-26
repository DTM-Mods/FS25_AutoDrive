"""Strapped load: pallets and bales held by the tension belts of ordinary trailers count as load, best price and the
unload products dialog see them, and at the unload target only the trailers whose products are sold there get their
belts opened; the stop waits while the selling point takes them and straps what is left again."""
import os
from lupa.lua55 import LuaRuntime

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read(*parts):
    return open(os.path.join(MOD, *parts), encoding="utf-8").read().replace("\r\n", "\n")


s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    FillType = {UNKNOWN = 0}
    g_time = 0
    LOG = {}
    Logging = {info = function(f, ...) table.insert(LOG, string.format(f, ...)) end}
    function entityExists(node) return node ~= nil and node > 0 end
    AutoDrive = {}
    function AutoDrive:hasAL(unit) return unit.isAL == true end
    UNITS = {}
    function AutoDrive.getAllUnits(vehicle) return UNITS end
    OWN_LEVEL = 0
    function AutoDrive.getAllFillLevels(units)
        -- the tippable load plus, unless skipped, the strapped load of units without capacity
        local level = OWN_LEVEL
        for _, unit in ipairs(units) do
            local l = ADStrappedLoad.getFillLevels(unit, unit.capacity or 0)
            if l ~= nil then level = level + l end
        end
        return level
    end
    ADUnloadFilter = {}
    function ADUnloadFilter.getObjectProduct(object) return object.ft, object.litres end
    ALLOWED = nil       -- fill type -> true (best price stop / lists); nil = everything
    function ADUnloadFilter.allowsProduct(vehicle, fillType) return ALLOWED == nil or ALLOWED[fillType] == true end
    HOLDS = 0
    ADGroundUnload = {hold = function(vehicle, dt) HOLDS = HOLDS + 1 end}
    VEHICLE = {ad = {stateModule = {getName = function() return "Truck 1" end}, specialDrivingModule = {}}}

    local nextNode = 1
    function pallet(ft, litres)
        nextNode = nextNode + 1
        return {ft = ft, litres = litres, rootNode = nextNode, specializationsByName = {pallet = {}, fillUnit = {}}}
    end
    function bale(ft, litres)
        nextNode = nextNode + 1
        return {ft = ft, litres = litres, nodeId = nextNode, isRoundbale = false}
    end
    function tractor()
        nextNode = nextNode + 1
        return {ft = 99, litres = 400, rootNode = nextNode, specializationsByName = {motorized = {}, fillUnit = {}}}
    end
    function trailer(objects, fastened)
        local t = {belts = fastened ~= false, calls = {}}
        t.spec_tensionBelts = {objectsToJoint = {}}
        t.objects = objects
        function t:setAllTensionBeltsActive(active, noEventSend)
            table.insert(self.calls, active)
            self.belts = active
            self.spec_tensionBelts.objectsToJoint = {}
            if active then
                for i, o in ipairs(self.objects) do
                    if not o.isDeleted then self.spec_tensionBelts.objectsToJoint[o.rootNode or o.nodeId] = {object = o} end
                end
            end
        end
        function t:freeTensionBeltObject(objectId, objectsToJoint, isDynamic, object)
            table.insert(self.freed, object)
            objectsToJoint[objectId] = nil
            object.canBeSold = true
        end
        function t:refreshTensionBelts()
            self.refreshes = self.refreshes + 1
            self:setAllTensionBeltsActive(true)
            table.remove(self.calls)
        end
        t.freed, t.refreshes = {}, 0
        if t.belts then t:setAllTensionBeltsActive(true) end
        t.calls = {}
        return t
    end
    function oldTrailer(objects)
        local t = trailer(objects)
        t.freeTensionBeltObject = nil
        return t
    end
    function sell(objects) for _, o in ipairs(objects) do o.isDeleted = true end end
""")
s.execute(read("scripts", "Manager", "StrappedLoad.lua"))

# --- what counts: pallets and bales, not a tractor on a low-loader; only while strapped; not on autoload trailers
s.execute("A = trailer({pallet(10, 1000), pallet(10, 1000), bale(20, 4000), tractor()})")
assert s.eval("#ADStrappedLoad.getObjects(A)") == 3
assert s.eval("ADStrappedLoad.getLoad(A)[10]") == 2000 and s.eval("ADStrappedLoad.getLoad(A)[20]") == 4000
assert s.eval("ADStrappedLoad.getLoad(A)[99]") is None
assert s.eval("ADStrappedLoad.getLitres(A)") == 6000
s.execute("OPEN = trailer({pallet(10, 1000)}, false)")
assert s.eval("ADStrappedLoad.getLitres(OPEN)") == 0                          # belts open: nothing held
# Universal Autoload vehicle: only what Autoload does not track (forklift + the game's belts); APalletAutoLoader: nothing
s.execute("""
    TRACKED, MANUAL = pallet(10, 1000), pallet(20, 700)
    UAL = trailer({TRACKED, MANUAL}); UAL.spec_universalAutoload = {loadedObjects = {[TRACKED] = true}}
    APAL = trailer({pallet(10, 1000)}); APAL.spec_aPalletAutoLoader = {}
""")
assert s.eval("ADStrappedLoad.getLitres(UAL)") == 700 and s.eval("ADStrappedLoad.getLoad(UAL)[10]") is None
assert s.eval("ADStrappedLoad.getLitres(APAL)") == 0
# Autoload's fill levels get the untracked strapped load added, and count as loaded
assert s.eval("table.pack(ADStrappedLoad.addToAutoloadLevels(UAL, 1000, 20000, false, 19000))[1]") == 1700
assert s.eval("table.pack(ADStrappedLoad.addToAutoloadLevels(UAL, 1000, 20000, false, 19000))[2]") == 20700
assert s.eval("table.pack(ADStrappedLoad.addToAutoloadLevels(UAL, 1000, 20000, false, 19000))[3]") is True
assert s.eval("table.pack(ADStrappedLoad.addToAutoloadLevels(UAL, 1000, 20000, false, 19000))[4]") == 19000
assert s.eval("table.pack(ADStrappedLoad.addToAutoloadLevels(APAL, 0, 0, false, 0))[3]") is False   # nothing added
s.execute("ADStrappedLoad.skip = true")
assert s.eval("table.pack(ADStrappedLoad.addToAutoloadLevels(UAL, 1000, 20000, false, 19000))[1]") == 1000
s.execute("ADStrappedLoad.skip = false")
# at a stop on the Autoload vehicle only the untracked pallets of the products sold here are released
s.execute("UNITS = {UAL}; ALLOWED = nil; OWN_LEVEL = 0; g_time = 0; TASK = {vehicle = VEHICLE}")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is True
assert s.eval("#UAL.freed") == 1 and s.eval("UAL.freed[1] == MANUAL") is True
# Autoload unload position "off": the pallets Autoload tracks are released too (only sold-here products)
s.execute("""
    T1, T2 = pallet(10, 1000), pallet(30, 1000)
    UAL = trailer({T1, T2}); UAL.spec_universalAutoload = {loadedObjects = {[T1] = true, [T2] = true}}
    AL_UNLOAD = 0
    AutoDrive.getSetting = function(name, vehicle) assert(name == "ALUnload"); return AL_UNLOAD end
    UNITS = {UAL}; ALLOWED = {[10] = true}; g_time = 0; TASK = {vehicle = VEHICLE}
""")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is True and s.eval("#UAL.freed") == 1 and s.eval("UAL.freed[1] == T1") is True
assert s.eval("ADStrappedLoad.getLitres(UAL)") == 0                            # still counted by Autoload, not twice
s.execute("UAL = trailer({T1, T2}); UAL.spec_universalAutoload = {loadedObjects = {[T1] = true, [T2] = true}}; AL_UNLOAD = 1; UNITS = {UAL}; TASK = {vehicle = VEHICLE}")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is False and s.eval("#UAL.freed") == 0   # center: Autoload's way
s.execute("AutoDrive.getSetting = nil")
# the stop logs what it found (diagnostics)
assert any("Strapped check" in str(l) for l in s.eval("LOG").values())
s.execute("SAME = trailer({}); local p = pallet(10, 500); SAME.objects = {p}; SAME.spec_tensionBelts.objectsToJoint = {[1] = {object = p}, [2] = {object = p}}")
assert s.eval("ADStrappedLoad.getLitres(SAME)") == 500                         # one pallet held by two belts counts once

# --- as fill levels: only units without a tippable load of their own, counted as full; skippable
assert s.eval("select('#', ADStrappedLoad.getFillLevels(A, 0))") == 4
assert s.eval("table.pack(ADStrappedLoad.getFillLevels(A, 0))[1]") == 6000
assert s.eval("table.pack(ADStrappedLoad.getFillLevels(A, 0))[3]") is True
assert s.eval("ADStrappedLoad.getFillLevels(A, 18000)") is None                # a tipper with belts keeps its own levels
assert s.eval("ADStrappedLoad.getFillLevels(OPEN, 0)") is None
s.execute("ADStrappedLoad.skip = true")
assert s.eval("ADStrappedLoad.getFillLevels(A, 0)") is None
s.execute("ADStrappedLoad.skip = false")

# --- a stop: only the pallets / bales of the products sold here are released, wherever they sit
s.execute("""
    W1, W2, C1 = pallet(10, 1000), pallet(10, 1000), pallet(30, 1000)
    A = trailer({W1, C1, W2}); B = trailer({bale(20, 4000), pallet(10, 500)})
    UNITS = {A, B}; ALLOWED = {[10] = true}; OWN_LEVEL = 0; g_time = 1000; HOLDS = 0
    TASK = {vehicle = VEHICLE}
""")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is True
assert s.eval("#A.freed") == 2 and s.eval("#B.freed") == 1                     # both 10s on A, the 10 on B
assert s.eval("A.freed[1].ft") == 10 and s.eval("A.freed[2].ft") == 10 and s.eval("B.freed[1].ft") == 10
assert len(s.eval("A.calls")) == 0 and len(s.eval("B.calls")) == 0             # belts stay closed
assert s.eval("C1.canBeSold") is None                                           # product 30 stays locked
assert s.eval("ADStrappedLoad.getLitres(A)") == 1000                            # only C1 still held
assert s.eval("HOLDS") == 1 and s.eval("VEHICLE.ad.specialDrivingModule.motorShouldNotBeStopped") is True
assert s.eval("ADStrappedLoad.stopFinished(TASK)") is False
s.execute("sell({W1}); g_time = 3000")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is True
s.execute("sell({W2, B.freed[1]}); g_time = 3100")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is False                  # all released ones sold: done
assert s.eval("A.refreshes") == 1 and s.eval("B.refreshes") == 1               # belts redone for what is left
assert s.eval("ADStrappedLoad.getLitres(A)") == 1000 and s.eval("ADStrappedLoad.getLitres(B)") == 4000
assert s.eval("ADStrappedLoad.stopFinished(TASK)") is True                     # the rest is for other stops
assert "3 of 3 pallets / bales sold here" in s.eval("LOG[#LOG]")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is False

# --- the selling point does not take everything released: done 5 s after the last sale, locked again
s.execute("""
    P1, P2 = pallet(10, 1000), pallet(10, 1000)
    A = trailer({P1, P2}); UNITS = {A}; ALLOWED = {[10] = true}; g_time = 0
    TASK = {vehicle = VEHICLE}
""")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is True
s.execute("sell({P1}); g_time = 1000")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is True
s.execute("g_time = 5900")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is True
s.execute("g_time = 6000")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is False
assert s.eval("A.refreshes") == 1 and s.eval("ADStrappedLoad.getLitres(A)") == 1000   # P2 locked again

# --- nothing here for it: nothing released, the stop is done at once
s.execute("A = trailer({pallet(30, 1000)}); UNITS = {A}; ALLOWED = {[10] = true}; TASK = {vehicle = VEHICLE}")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is False and s.eval("#A.freed") == 0 and s.eval("A.refreshes") == 0
assert s.eval("ADStrappedLoad.stopFinished(TASK)") is True
# without best price or lists everything is released (as pressing L)
s.execute("A = trailer({pallet(30, 1000)}); B = trailer({bale(20, 1)}); UNITS = {A, B}; ALLOWED = nil; TASK = {vehicle = VEHICLE}")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is True and s.eval("#A.freed") == 1 and s.eval("#B.freed") == 1
# tippable load left: not finished by the strapped part
s.execute("sell(A.objects); sell(B.objects); g_time = g_time + 100; ADStrappedLoad.updateStop(TASK, 16); OWN_LEVEL = 5000")
assert s.eval("ADStrappedLoad.stopFinished(TASK)") is False
# a game version without freeTensionBeltObject: the whole trailer opens when one of its products is sold here
s.execute("A = oldTrailer({pallet(10, 1000), pallet(30, 1000)}); UNITS = {A}; ALLOWED = {[10] = true}; OWN_LEVEL = 0; g_time = 0; TASK = {vehicle = VEHICLE}")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is True and list(s.eval("A.calls").values()) == [False]
s.execute("g_time = 6000")
assert s.eval("ADStrappedLoad.updateStop(TASK, 16)") is False and list(s.eval("A.calls").values()) == [False, True]
# never longer than MAX_TIME, even while things still disappear now and then
s.execute("""
    OBJ = {}
    for i = 1, 30 do OBJ[i] = pallet(10, 100) end
    A = trailer(OBJ); UNITS = {A}; ALLOWED = nil; OWN_LEVEL = 0; g_time = 0; TASK = {vehicle = VEHICLE}
    ADStrappedLoad.updateStop(TASK, 16)
    for i = 1, 25 do g_time = g_time + 2500; sell({OBJ[i]}); RESULT = ADStrappedLoad.updateStop(TASK, 16) end
""")
assert s.eval("RESULT") is False and s.eval("g_time") >= 60000

# --- wiring
trailer_util = read("scripts", "Utils", "TrailerUtil.lua")
f = trailer_util[trailer_util.index("function AutoDrive.getObjectFillLevels(object)"):]
f = f[:f.index("\nend\n")]
assert f.index("ADStrappedLoad.getFillLevels(object, fillCapacity)") < f.index("local filledToUnload = AutoDrive.isUnloadFillLevelReached")
task = read("scripts", "Tasks", "UnloadAtDestinationTask.lua")
assert task.index("if ADStrappedLoad.updateStop(self, dt) then") < task.index("local fillLevel = AutoDrive.getAllFillLevels(self.trailers)\n                if")
assert "or ADStrappedLoad.stopFinished(self)" in task
assert "ADStrappedLoad.addToAutoloadLevels(object, fillLevel, fillCapacity, filledToUnload, fillFreeCapacity)" in read("scripts", "ExternalInterface.lua")
assert "ADStrappedLoad.getLoad(unit)" in read("scripts", "Manager", "BestPrice.lua")
assert "ADStrappedLoad.getLoad(unit)" in read("scripts", "Manager", "UnloadFilter.lua")
reg = read("register.lua")
assert reg.count("scripts/Manager/StrappedLoad.lua") == 1       # only used at run time, order free

print("OK: strapped load (pallets and bales only, held by fastened belts, on Universal Autoload vehicles only what Autoload does not track, not on APalletAutoLoader, counted once, added to Autoload's levels; "
      "fill levels as full for trailers without own load; stop releases only the pallets sold there, wherever they sit, belts stay closed, waits, locks the rest again, old-game fallback per trailer, "
      "5 s settle, 60 s max, nothing to sell or everything without limits; wiring)")
