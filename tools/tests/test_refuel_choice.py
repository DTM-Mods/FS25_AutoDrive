"""Refuel at: a vehicle refuels at the target the player picked (stored by name) or, with Nearest, at the nearest
refuel point along the routes (straight line without a route), its own farm's if at most 1.5x as far; a chosen
target that can not be used falls back to Nearest with one message; every caller gets it (the upstream function is
replaced); synced by event and with the vehicle, saved per vehicle; a row on the Overdrive and the vehicle tab."""
import os
import re
from lupa.lua55 import LuaRuntime

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read(*parts):
    return open(os.path.join(MOD, *parts), encoding="utf-8").read().replace("\r\n", "\n")


s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    unpack = table.unpack
    g_time = 0
    table.contains = function(t, v) for _, x in pairs(t) do if x == v then return true end end return false end
    MathUtil = {vector2Length = function(x, z) return math.sqrt(x * x + z * z) end}
    -- road 1 (0,0) -> 2 (100,0) -> 3 (300,0) -> 4 (300,60) -> 5 (0,60); the vehicle stands at waypoint 1
    function wp(id, x, z, out) return {id = id, x = x, y = 0, z = z, out = out} end
    WP = {wp(1, 0, 0, {2}), wp(2, 100, 0, {3}), wp(3, 300, 0, {4}), wp(4, 300, 60, {5}), wp(5, 0, 60, {})}
    MARKERS = {{id = 5, name = "Farm Diesel A"}, {id = 3, name = "Town Station B"}, {id = 4, name = "Own Tank C"},
               {id = 2, name = "Empty Pump"}}
    ADGraphManager = {getWayPoints = function() return WP end, getMapMarkers = function() return MARKERS end}
    function ADGraphManager:getMapMarkerById(id) return MARKERS[id] end
    function ADGraphManager:getWayPointById(id) return WP[id] end
    function farmTrigger(farm) return {source = {owningPlaceable = {getOwnerFarmId = function() return farm end}}} end
    TA, TB, TC = farmTrigger(0), {}, farmTrigger(2)
    DESTS = {{mapMarkerID = 1, refuelTrigger = TA, distance = 5}, {mapMarkerID = 2, refuelTrigger = TB, distance = 5},
             {mapMarkerID = 3, refuelTrigger = TC, distance = 5}}
    ADTriggerManager = {getRefuelDestinations = function(vehicle, ignore) return DESTS end,
                        getClosestRefuelDestination = function() return "upstream" end}
    FUELS = {32}
    AutoDrive = {getRequiredRefuels = function() return FUELS end}
    MESSAGES = {}
    ADDiag = {refuelChoiceUnusable = function(v, name, gone) table.insert(MESSAGES, {name = name, gone = gone}) end}
    CLOSEST = 1
    VEHICLE = {ad = {}, components = {{node = 1}}, getOwnerFarmId = function() return 1 end,
               getClosestWayPoint = function() return CLOSEST end}
    getWorldTranslation = function() return 0, 0, 0 end
""")
s.execute(read("scripts", "Manager", "RefuelChoice.lua"))


def dest(ignore=True):
    return s.eval("ADRefuelChoice.getDestination(VEHICLE, %s)" % ("true" if ignore else "false"))


# every caller gets the choice
assert s.eval("ADTriggerManager.getClosestRefuelDestination == ADRefuelChoice.getDestination")
# Nearest by route: B (300 m) before C (360 m) and A (660 m; only 60 m in a straight line)
assert s.eval("ADRefuelChoice.get(VEHICLE)") == "" and dest() == 2
# no route (vehicle off the network): straight line, A
s.execute("CLOSEST = -1")
assert dest() == 1
s.execute("CLOSEST = 1")
# the own farm's refuel point wins when at most 1.5x as far: C (360 <= 450)
s.execute("TC.source.owningPlaceable.getOwnerFarmId = function() return 1 end")
assert dest() == 3
# ... but not when further: A of the own farm at 660 m, C someone else's
s.execute("TC.source.owningPlaceable.getOwnerFarmId = function() return 2 end; TA.source.owningPlaceable.getOwnerFarmId = function() return 1 end")
assert dest() == 2
s.execute("TA.source.owningPlaceable.getOwnerFarmId = function() return 0 end")

# the chosen target, by name
s.execute('ADRefuelChoice.set(VEHICLE, "Farm Diesel A")')
assert dest() == 1 and s.eval("#MESSAGES") == 0
# gone: Nearest, said once (not again within a minute), again for another name
s.execute('ADRefuelChoice.set(VEHICLE, "Gone Station")')
assert dest() == 2 and dest() == 2
assert s.eval("#MESSAGES") == 1 and s.eval("MESSAGES[1].name") == "Gone Station" and s.eval("MESSAGES[1].gone") is True
s.execute("g_time = 61000")
assert dest() == 2 and s.eval("#MESSAGES") == 2
# a target that exists but has no usable refuel point (empty, no access, wrong fuel): Nearest, says so
s.execute('ADRefuelChoice.set(VEHICLE, "Empty Pump")')
assert dest() == 2 and s.eval("MESSAGES[3].gone") is False and s.eval("MESSAGES[3].name") == "Empty Pump"
# nothing needed: no message
s.execute("FUELS = {}; ADRefuelChoice.set(VEHICLE, 'Other gone'); ADRefuelChoice.getDestination(VEHICLE, false); FUELS = {32}")
assert s.eval("#MESSAGES") == 3
# no refuel point at all: nil, as before
s.execute("SAVED = DESTS; DESTS = {}")
assert s.eval("ADRefuelChoice.getDestination(VEHICLE, true)") is None
s.execute("DESTS = SAVED")
# the choices: sorted names of the refuel targets
assert list(s.eval("ADRefuelChoice.getChoices(VEHICLE)").values()) == ["Farm Diesel A", "Own Tank C", "Town Station B"]
# the API for other mods
s.execute('ADRefuelChoice.set(VEHICLE, "Own Tank C")')
assert s.eval("AutoDrive.getRefuelDestination(VEHICLE)") == "Own Tank C"

# savegame: only a chosen target is written; read back
s.execute("""
    XML = {values = {}}
    function XML:setValue(k, v) self.values[k] = v end
    function XML:getValue(k) return self.values[k] end
    ADRefuelChoice.saveToXML(VEHICLE, XML, "v")
    V2 = {ad = {}}; ADRefuelChoice.loadFromXML(V2, XML, "v")
    ADRefuelChoice.set(VEHICLE, ""); XML2 = setmetatable({values = {}}, {__index = XML}); ADRefuelChoice.saveToXML(VEHICLE, XML2, "v")
""")
assert s.eval("V2.ad.refuelDestination") == "Own Tank C" and s.eval("next(XML2.values)") is None
assert s.eval('XML.values["v#refuelDestination"]') == "Own Tank C"

# event: the server sets it and sends it to every client; a client sends it to the server
s.execute("""
    Event = {new = function(mt) return setmetatable({}, mt) end}
    function Class(c, super) return {__index = c} end
    function InitEventClass() end
    SENT, BROADCAST = {}, {}
    NetworkUtil = {getObjectId = function(o) return 7 end, writeNodeObjectId = function(_, id) table.insert(SENT, id) end,
                   readNodeObjectId = function() return 7 end, getObject = function() return VEHICLE end}
    function streamWriteString(_, v) table.insert(SENT, v) end
    STREAM = {}; function streamReadString() return table.remove(STREAM, 1) end
    g_server = {broadcastEvent = function(_, e) table.insert(BROADCAST, e.name) end}
""")
s.execute(read("scripts", "Events", "RefuelDestinationEvent.lua"))
s.execute('AutoDrive.setRefuelDestination(VEHICLE, "Town Station B")')
assert s.eval("ADRefuelChoice.get(VEHICLE)") == "Town Station B" and list(s.eval("BROADCAST").values()) == ["Town Station B"]
s.execute("""
    g_server = nil; TO_SERVER = {}
    g_client = {getServerConnection = function() return {sendEvent = function(_, e) table.insert(TO_SERVER, e) end} end}
    AutoDrive.setRefuelDestination(VEHICLE, "")
    TO_SERVER[1]:writeStream(1)
""")
assert s.eval("ADRefuelChoice.get(VEHICLE)") == "Town Station B"     # not before the server says so
assert list(s.eval("SENT").values()) == [7, ""]
s.execute('STREAM = {"Own Tank C"}; E = AutoDriveRefuelDestinationEvent.emptyNew(); E:readStream(1)')
assert s.eval("ADRefuelChoice.get(VEHICLE)") == "Own Tank C"

# the row: Nearest + choices, current one selected; a change is sent on OK only; the window asks before throwing it
# away; reset / restore; hidden without a vehicle
s.execute("""
    g_server = {broadcastEvent = function() end}
    Utils = {appendedFunction = function(f, g) return function(...) f(...); g(...) end end,
             prependedFunction = function(f, g) return function(...) g(...); f(...) end end,
             overwrittenFunction = function(f, g) return function(self, ...) return g(self, f, ...) end end}
    ADSettingsPage = {onFrameOpen = function() end, hasChanges = function() return false end}
    ADSettings = {onClickOK = function() end, onClose = function() end, resetPage = function() end, onClickRestore = function() end}
    g_i18n = {getText = function(_, k) return k == "gui_ad_refuelNearest" and "Nearest" or k end}
    AutoDrive.getControlledVehicle = function() return CONTROLLED end
    CONTROLLED = VEHICLE
    ROW = {visible = true}; function ROW:setVisible(v) self.visible = v end
    EL = {parent = ROW}; function EL:setTexts(t) self.texts = t end; function EL:setState(i) self.state = i end
    PAGE = setmetatable({}, {__index = ADSettingsPage})
""")
s.execute(read("scripts", "Gui", "RefuelChoiceRow.lua"))
s.execute("PAGE:onCreateRefuelDestination(EL); PAGE:onFrameOpen()")
assert list(s.eval("EL.texts").values()) == ["Nearest", "Farm Diesel A", "Own Tank C", "Town Station B"] and s.eval("EL.state") == 3
assert s.eval("PAGE:hasChanges()") is False
s.execute("PAGE:onRefuelDestinationChange(4, EL)")
assert s.eval("PAGE:hasChanges()") is True and s.eval("ADRefuelChoice.get(VEHICLE)") == "Own Tank C"
s.execute("PAGE:onFrameOpen()")                                     # the other tab shows the pending choice
assert s.eval("EL.state") == 4
s.execute("ADSettings:onClickOK(); ADSettings:onClose()")
assert s.eval("ADRefuelChoice.get(VEHICLE)") == "Town Station B" and s.eval("ADRefuelChoiceRow.pending") is None
s.execute("PAGE:onRefuelDestinationChange(1, EL); ADSettings:onClose()")    # Back: thrown away
assert s.eval("ADRefuelChoice.get(VEHICLE)") == "Town Station B"
s.execute("PAGE:onRefuelDestinationChange(2, EL); ADSettings:resetPage(PAGE)")
assert s.eval("ADRefuelChoiceRow.pending") is None and s.eval("EL.state") == 4
s.execute("ADSettings.currentPage = PAGE; ADSettings:onClickRestore(); ADSettings:onClickOK()")
assert s.eval("ADRefuelChoice.get(VEHICLE)") == ""
# a chosen target that is not in the list now still shows (opening the window does not change it)
s.execute('ADRefuelChoice.set(VEHICLE, "Gone Station"); PAGE:onFrameOpen()')
assert s.eval("EL.texts[5]") == "Gone Station" and s.eval("EL.state") == 5 and s.eval("PAGE:hasChanges()") is False
s.execute("CONTROLLED = nil; PAGE:onFrameOpen()")
assert s.eval("ROW.visible") is False

# wiring
reg = read("register.lua")
assert reg.index("scripts/Manager/TriggerManager.lua") < reg.index("scripts/Manager/RefuelChoice.lua")
assert reg.index("scripts/Gui/Settings.lua") < reg.index("scripts/Gui/RefuelChoiceRow.lua")
assert "scripts/Events/RefuelDestinationEvent.lua" in reg
spec = read("scripts", "Specialization.lua")
for part in ("ADRefuelChoice.registerSavegameKeys(schemaSavegame)", "ADRefuelChoice.loadFromXML(self, xmlFile, key)",
             "ADRefuelChoice.saveToXML(self, xmlFile, adKey)"):
    assert part in spec, part
write = spec[spec.index("function AutoDrive:onWriteStream"):]
write = write[:write.index("\nend\n")]
readfn = spec[spec.index("function AutoDrive:onReadStream"):]
readfn = readfn[:readfn.index("\nend\n")]
assert write.rstrip().endswith("streamWriteString(streamId, ADRefuelChoice.get(self))")
assert readfn.rstrip().endswith("ADRefuelChoice.set(self, streamReadString(streamId))")
for page in ("overdriveSettingsPage.xml", "vehicleSettingsPage.xml"):
    assert 'onCreate="onCreateRefuelDestination"' in read("gui", page), page
vp = read("gui", "vehicleSettingsPage.xml")
assert vp.index('name="autoRefuel"') < vp.index('name="refuelDestination"') < vp.index('name="autoRepair"')
diag = read("scripts", "Manager", "Diagnostics.lua")
assert "function ADDiag.refuelChoiceUnusable" in diag
for f in os.listdir(os.path.join(MOD, "translations")):
    t = read("translations", f)
    for key in ("gui_ad_refuelDestination", "gui_ad_refuelDestination_tooltip", "gui_ad_refuelNearest",
                "AD_diag_refuelChoiceGone", "AD_diag_refuelChoiceUnusable", "AD_diag_refuelUsingNearest"):
        m = re.search(r'name="%s" text="([^"]+)"' % key, t)
        assert m and "%" not in m.group(1), (f, key)

print("OK: refuel at (chosen target by name, else Nearest by route / straight line, own farm within 1.5x; unusable "
      "choice falls back with one message; replaces getClosestRefuelDestination for every caller; saved, synced by "
      "event and with the vehicle; row on the Overdrive and vehicle tab with OK / Back / reset / restore; 18 languages)")
