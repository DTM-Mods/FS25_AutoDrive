"""Route problems where they are: while the editor is on, the route check runs by itself once the network has not
changed for a moment (not while a waypoint is dragged), every problem gets a beacon in its colour (dead ends and
loose waypoints orange, the others red), the near ones their text, a count under the HUD with the nearest distance,
an arrow when the nearest is out of sight, squares on the big map; nothing with the setting or the editor off."""
import os
from lupa.lua55 import LuaRuntime

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read(*parts):
    return open(os.path.join(MOD, *parts), encoding="utf-8").read().replace("\r\n", "\n")


s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    unpack = table.unpack
    g_time = 0
    function wp(id, x, z, out) return {id = id, x = x, y = 0, z = z, out = out, incoming = {}, flags = 0} end
    -- a two-way road 1 = 2 = 3 with targets at both ends, 3 -> 4 a dead end, 5 loose far away
    WP = {wp(1, 0, 0, {2}), wp(2, 10, 0, {1, 3}), wp(3, 20, 0, {2, 4}), wp(4, 30, 0, {}), wp(5, 2000, 0, {})}
    MARKERS = {{id = 1, name = "Farm"}, {id = 3, name = "Silo"}}
    for id, w in ipairs(WP) do for _, o in ipairs(w.out) do table.insert(WP[o].incoming, id) end end
    ADGraphManager = {getWayPoints = function() return WP end, getMapMarkers = function() return MARKERS end}
    function ADGraphManager:markChanges() self.marked = true end
    Utils = {appendedFunction = function(f, g) return function(...) f(...); g(...) end end}
    MathUtil = {vector2Length = function(x, y) return math.sqrt(x * x + y * y) end}
    table.contains = function(t, v) for _, x in pairs(t) do if x == v then return true end end return false end
    SETTINGS = {showRouteProblems = true, showHUD = true}
    EDITOR = true
    AutoDrive = {drawDistance = 50, getSetting = function(name) return SETTINGS[name] end,
                 isEditorModeEnabled = function() return EDITOR end, isEditorShowEnabled = function() return false end,
                 Hud = {posX = 0.7, posY = 0.5}}
    g_i18n = {getText = function(_, key)
        if key == "AD_routeMarkers_summary" then return "Route check: %s problems, the nearest %s m away" end
        if key == "AD_routeCheck_deadEnd" then return "Dead end" end
        if key == "AD_routeCheck_loose" then return "Loose" end
        return key end}
    LINES, SPHERES, ARROWS, TEXTS, SQUARES = {}, {}, {}, {}, {}
    ADDrawingManager = {arrows = {position = {start = 1}},
        addLineTask = function(_, x1, y1, z1, x2, y2, z2, w, r, g, b) table.insert(LINES, {x = x1, top = y2, r = r, g = g}) end,
        addSphereTask = function(_, x, y, z) table.insert(SPHERES, x) end,
        addArrowTask = function() table.insert(ARROWS, true) end}
    ADUndoManager = {POINTER_LENGTH = 25}
    function project(x, y, z) return 0.5 + x / 1000, 0.5, 0.5 end
    function renderText(x, y, size, text) table.insert(TEXTS, text) end
    function setTextColor() end; function setTextAlignment() end; function setTextBold() end
    RenderText = {ALIGN_LEFT = 0, ALIGN_CENTER = 1}
    VIEW = {0, 0}
    function getWorldTranslation(node) return VIEW[1], 0, VIEW[2] end
    vehicle = {components = {{node = 1}}, ad = {}}
    function createImageOverlay() return 1 end
    BOXES = {}
    function setOverlayColor() end
    function renderOverlay(o, x, y, w, h) table.insert(BOXES, w) end
    function getTextWidth(size, text) return #text * size * 0.5 end
    ADFleetMap = {drawSquare = function(o, x, y, pixels, r, g, b) table.insert(SQUARES, {x = x, r = r, g = g}) end}
    ADRoutePreview = {mapPosition = function(map, x, z) return x / 3000, z / 3000 end}
    function reset() LINES, SPHERES, ARROWS, TEXTS, SQUARES = {}, {}, {}, {}, {} end
""")
s.execute(read("scripts", "Manager", "RouteCheck.lua"))
s.execute(read("scripts", "Manager", "RouteMarkers.lua"))

# changes are counted (and the old markChanges still runs); checked only after 1.5 s without changes
s.execute("ADGraphManager:markChanges(); g_time = 1000; ADRouteMarkers:draw(vehicle)")
assert s.eval("ADGraphManager.marked") is True and s.eval("ADRouteMarkers.changes") == 1
assert s.eval("#ADRouteMarkers.problems") == 0 and s.eval("#LINES") == 0
# not while a waypoint is dragged
s.execute("g_time = 3000; vehicle.ad.nodeToMoveId = 4; ADRouteMarkers:draw(vehicle)")
assert s.eval("#ADRouteMarkers.problems") == 0
s.execute("vehicle.ad.nodeToMoveId = nil; ADRouteMarkers:draw(vehicle)")
assert s.eval("#ADRouteMarkers.problems") == 2
# a beacon each: the dead end (orange) near, the loose waypoint (2 km away) too; the near one has its text, the far
# one not; under the HUD the count and the nearest distance
lines = [dict(l.items()) for l in s.eval("LINES").values()]
beacons = [l for l in lines if l["top"] == 25]
assert sorted(b["x"] for b in beacons) == [30, 2000] and all(b["r"] == 1 and b["g"] == 0.55 for b in beacons)
texts = list(s.eval("TEXTS").values())
assert "Dead end" in texts and "Loose" not in texts
assert not any(t.startswith("Route check") for t in texts)
# the count under the HUD comes on its own, on a dark box as wide as its text, drawn before the HUD
s.execute("reset(); BOXES = {}; ADRouteMarkers:drawSummary(vehicle)")
assert list(s.eval("TEXTS").values()) == ["Route check: 2 problems, the nearest 30 m away"]
assert s.eval("#BOXES") == 1 and s.eval("BOXES[1]") > s.eval("getTextWidth(0.012, TEXTS[1])")
s.execute("SETTINGS.showRouteProblems = false; reset(); ADRouteMarkers:drawSummary(vehicle); SETTINGS.showRouteProblems = true")
assert s.eval("#TEXTS") == 0
s.execute("reset()")
assert s.eval("#ARROWS") == 0
# not checked again without changes
s.execute("ADRouteMarkers.problems = {}; ADRouteMarkers:draw(vehicle)")
assert s.eval("#ADRouteMarkers.problems") == 0
s.execute("ADGraphManager:markChanges(); g_time = 5000; reset(); ADRouteMarkers:draw(vehicle)")
assert s.eval("#ADRouteMarkers.problems") == 2
# the nearest one out of sight: an arrow towards it
s.execute("VIEW = {500, 500}; reset(); ADRouteMarkers:draw(vehicle)")
assert s.eval("#ARROWS") == 1
# the big map: a square (and its black border) for each
s.execute("reset(); ADRouteMarkers:drawOnMap({})")
assert s.eval("#SQUARES") == 4
# a trap is red
s.execute("""
    WP[4].out = {6}; WP[6] = wp(6, 40, 0, {4}); WP[6].incoming = {4}; table.insert(WP[4].incoming, 6)    -- 4 <-> 6 can be entered from 3 but not left
    ADGraphManager:markChanges(); g_time = 9000; VIEW = {0, 0}; reset(); ADRouteMarkers:draw(vehicle)
""")
kinds = sorted(p.kind for p in s.eval("ADRouteMarkers.problems").values())
assert kinds == [1, 3], kinds
red = [dict(l.items()) for l in s.eval("LINES").values() if l.top == 25 and l.g == 0.1]
assert len(red) == 1
# nothing with the setting off or the editor off
for off in ("SETTINGS.showRouteProblems = false", "EDITOR = false"):
    s.execute("SETTINGS.showRouteProblems = true; EDITOR = true; reset(); " + off + "; ADRouteMarkers:draw(vehicle); ADRouteMarkers:drawOnMap({})")
    assert s.eval("#LINES") == 0 and s.eval("#SQUARES") == 0 and s.eval("#TEXTS") == 0

# wiring
reg = read("register.lua")
assert reg.index("scripts/Manager/RouteMarkers.lua") > reg.index("scripts/Gui/FleetMap.lua") > reg.index("scripts/Manager/RouteCheck.lua")
spec = read("scripts", "Specialization.lua")
assert "ADRouteMarkers.safeDraw(self)" in spec
assert spec.index("ADRouteMarkers.safeDrawSummary(self)") < spec.index("AutoDrive.Hud:drawHud(self)")
assert 'name="showRouteProblems"' in read("gui", "overdriveSettingsPage.xml")
for f in os.listdir(os.path.join(MOD, "translations")):
    t = read("translations", f)
    for key in ("gui_ad_showRouteProblems", "gui_ad_showRouteProblems_tooltip", "AD_routeMarkers_summary"):
        assert 'name="%s"' % key in t, (f, key)

print("OK: route problems where they are (checked after 1.5 s without changes, not while dragging, beacons in "
      "orange / red, text for the near ones, count and nearest distance under the HUD (on a dark box, behind the HUD lists), arrow when out of sight, "
      "squares on the big map, off with the setting or the editor; wired, 18 languages)")
