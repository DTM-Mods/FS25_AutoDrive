"""Selecting several waypoints: Ctrl + Shift + drag box, Ctrl (+ Shift) + click toggles, the menu opens once all keys
are let go (move, put on the ground, side road, direction, tidy, delete, deselect), a click outside closes it and
clears, Alt + click on a selected one deletes them all, dragging a selected one moves them all (one event each), ids
shifting clears the selection, Ctrl + click with nothing selected and Ctrl + Shift + click on the ground keep their
old meaning."""
import os
from lupa.lua55 import LuaRuntime

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read(*parts):
    return open(os.path.join(MOD, *parts), encoding="utf-8").read().replace("\r\n", "\n")


s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    -- waypoints 1..5 on a line, 1 -> 2 -> 3 -> 4 one way, 5 alone; the screen position is x / 100, z / 100
    WP = {}
    for i = 1, 5 do WP[i] = {id = i, x = i * 10, y = 0, z = 10, flags = 0, out = {}, incoming = {}} end
    for i = 1, 3 do table.insert(WP[i].out, i + 1); table.insert(WP[i + 1].incoming, i) end
    COUNT = 5
    SENT = {}
    ADGraphManager = {
        getWayPointsCount = function() return COUNT end,
        getWayPointById = function(_, id) return WP[id] end,
        markChanges = function() end,
        changeWayPointPosition = function(_, id) table.insert(SENT, "single " .. id) end,
        moveWayPoints = function(_, moves) SENT.moves = moves end,
        getIsPointSubPrio = function(_, id) return WP[id].flags == 1 end,
    }
    local function has(list, v) for _, x in pairs(list) do if x == v then return true end end return false end
    ADWaypointPanel = {OUT = 1, IN = 2, DUAL = 3, REVERSE = 4, REVERSE_IN = 5,
        getDirection = function(a, b)
            if has(a.out, b.id) and has(b.out, a.id) then return 3 elseif has(a.out, b.id) then return 1
            elseif has(b.out, a.id) then return 2 end
        end,
        setRoadDirection = function(chain, mode) SENT.road = {chain = chain, mode = mode} end,
        setPairsDirection = function(pairs, mode) SENT.pairs = {pairs = pairs, mode = mode} end,
        setSideRoadOnIds = function(ids, on) SENT.side = {ids = ids, on = on} end,
        tidyRoad = function(chain, tool) SENT.tidy = {chain = chain, tool = tool} end}
    ADTidyTools = {EVEN = 1, STRAIGHTEN = 2, SMOOTH = 3, groundHeight = function() return 0 end}
    AutoDriveDeleteWayPointsEvent = {sendEvent = function(ids) SENT.deleted = ids end}
    function project(x, y, z) return x / 100, z / 100, 0.5 end
    MathUtil = {vector2Length = function(x, y) return math.sqrt(x * x + y * y) end}
    g_i18n = {getText = function(_, key) return key end}
    function getTextWidth(size, t) return #t * size * 0.5 end
    DRAWN = {}
    function drawFilledRect() end
    function renderText(x, y, size, t) table.insert(DRAWN, t) end
    function setTextAlignment() end; function setTextColor() end; function setTextBold() end
    RenderText = {ALIGN_LEFT = 0}; unpack = table.unpack
    GROUND = {20, 0, 10}
    AutoDrive = {drawHeight = 0, drawDistance = 100, playSample = function() end, selectedWayPointSample = 1, mouseClickSample = 2,
                 getSetting = function() return 0 end,
                 getTerrainHeightAtWorldPos = function() return 0 end,
                 getGroundUnderMouse = function() return GROUND[1], GROUND[2], GROUND[3] end,
                 isInExtendedEditorMode = function() return true end}
    function keys(ctrl, shift, alt)
        AutoDrive.leftCTRLmodifierKeyPressed = ctrl; AutoDrive.leftLSHIFTmodifierKeyPressed = shift
        AutoDrive.leftALTmodifierKeyPressed = alt; AutoDrive.rightSHIFTmodifierKeyPressed = false
    end
    vehicle = {ad = {}}
    function vehicle:getWayPointsInRange() return WP end
    function mouse(x, y, isDown, isUp, button, hovered)
        g_lastMousePosX, g_lastMousePosY = x, y
        vehicle.ad.hoveredNodeId = hovered
        return ADNodeSelection:mouseEvent(vehicle, x, y, isDown, isUp, button)
    end
    -- press the menu button with this label
    function press(label)
        for _, b in ipairs(ADNodeSelection.menu.layout.buttons) do
            if b.label == label then
                local x, y = b.rect.x + 0.001, b.rect.y + 0.001
                mouse(x, y, true, false, 1)
                return mouse(x, y, false, true, 1)
            end
        end
        error("no button " .. label)
    end
    -- the mouse away from the waypoints, all keys let go, a frame drawn
    function letGo()
        mouse(0.8, 0.9, false, false, 0)
        keys(false, false, false)
        ADNodeSelection:draw(vehicle)
    end
    function labels()
        local list = {}
        for _, b in ipairs(ADNodeSelection.menu.layout.buttons) do table.insert(list, b.label) end
        return table.concat(list, ",")
    end
""")
import hud_style_stub
hud_style_stub.load(s)
s.execute(read("scripts", "Manager", "NodeSelection.lua"))
sel = lambda: list(s.eval("ADNodeSelection:getIds()").values())

# Ctrl + Shift + drag a box around waypoints 2..3 (screen x 0.2, 0.3): press is not used, the move and release are
s.execute("keys(true, true, false)")
assert s.eval("mouse(0.15, 0.05, true, false, 1)") is False
assert s.eval("mouse(0.35, 0.15, false, false, 0)") is True and s.eval("ADNodeSelection.box.active") is True
assert s.eval("mouse(0.35, 0.15, false, true, 1)") is True
assert sel() == [2, 3] and s.eval("ADNodeSelection.box") is None
# the menu waits while keys are held, opens at the mouse once they are let go
s.execute("ADNodeSelection:draw(vehicle)")
assert s.eval("ADNodeSelection.menu") is None
s.execute("letGo()")
assert s.eval("ADNodeSelection.menu.x") == 0.81
assert s.eval("ADNodeSelection.menu") is not None
assert s.eval("labels()") == ("AD_nodeSelection_move,AD_nodeSelection_ground,AD_wpPanel_on,AD_wpPanel_off,AD_wpPanel_oneWay,"
                              "AD_wpPanel_twoWay,AD_wpPanel_flip,AD_nodeSelection_delete,AD_nodeSelection_deselect")
assert "2 AD_nodeSelection_count" in list(s.eval("DRAWN").values())
# the menu stays on the screen
assert s.eval("ADNodeSelection.menu.layout.x + ADNodeSelection.menu.layout.width") <= 1
assert s.eval("ADNodeSelection.menu.layout.y") >= 0

# Ctrl + click on waypoint 5 (menu closes, the click adds it), the menu comes back with keys let go
s.execute("keys(true, false, false)")
assert s.eval("mouse(0.5, 0.1, false, true, 1, 5)") is True and sel() == [2, 3, 5]
assert s.eval("ADNodeSelection.menu") is None
s.execute("letGo()")
# 2, 3, 5 is no line: no one-way, no tidy; 2-3 is connected: two-way and flip
assert s.eval("labels()") == ("AD_nodeSelection_move,AD_nodeSelection_ground,AD_wpPanel_on,AD_wpPanel_off,"
                              "AD_wpPanel_twoWay,AD_wpPanel_flip,AD_nodeSelection_delete,AD_nodeSelection_deselect")
s.execute("press('AD_wpPanel_twoWay')")
assert s.eval("SENT.pairs.mode") == "twoWay" and [list(p.values()) for p in s.eval("SENT.pairs.pairs").values()] == [[2, 3]]
assert s.eval("ADNodeSelection.menu") is not None   # stays open after an action
s.execute("press('AD_wpPanel_on')")
assert list(s.eval("SENT.side.ids").values()) == [2, 3, 5] and s.eval("SENT.side.on") is True
# Ctrl + Shift + click on 5 removes it again
s.execute("keys(true, true, false); mouse(0.5, 0.1, true, false, 1, 5)")
assert s.eval("mouse(0.5, 0.1, false, true, 1, 5)") is True and sel() == [2, 3]
# with keys held a click on the menu goes through it to the waypoint below
s.execute("ADNodeSelection:openMenu(vehicle, 0.15, 0.2); keys(true, false, false)")
assert s.eval("mouse(0.4, 0.1, false, true, 1, 4)") is True and sel() == [2, 3, 4] and s.eval("ADNodeSelection.menu") is None
s.execute("ADNodeSelection:toggle(4); keys(true, true, false)")
# Ctrl + Shift + click on the ground (no drag) is left to the editor: makes a sub-priority waypoint as before
s.execute("mouse(0.9, 0.9, true, false, 1)")
assert s.eval("mouse(0.9, 0.9, false, true, 1)") is False and sel() == [2, 3]

# 1..4 is a line: one-way along the way it is driven, tidy tools
s.execute("keys(true, true, false); mouse(0.1, 0.1, false, true, 1, 1); mouse(0.4, 0.1, false, true, 1, 4)")
s.execute("letGo()")
assert list(s.eval("ADNodeSelection:getChain()").values()) == [1, 2, 3, 4]
assert "AD_wpPanel_oneWay" in s.eval("labels()") and "AD_wpPanel_smooth" in s.eval("labels()")
s.execute("press('AD_wpPanel_oneWay')")
assert s.eval("SENT.road.mode") == "oneWay" and list(s.eval("SENT.road.chain").values()) == [1, 2, 3, 4]
s.execute("press('AD_wpPanel_smooth')")
assert s.eval("SENT.tidy.tool") == 3 and list(s.eval("SENT.tidy.chain").values()) == [1, 2, 3, 4]
# a line driven the other way round is turned round
s.execute("for i = 1, 4 do WP[i].out, WP[i].incoming = {}, {} end; for i = 1, 3 do table.insert(WP[i + 1].out, i); table.insert(WP[i].incoming, i + 1) end")
assert list(s.eval("ADNodeSelection:getChain()").values()) == [4, 3, 2, 1]
s.execute("for i = 1, 4 do WP[i].out, WP[i].incoming = {}, {} end; for i = 1, 3 do table.insert(WP[i].out, i + 1); table.insert(WP[i + 1].incoming, i) end")
# a branch is no line
s.execute("table.insert(WP[2].out, 5); table.insert(WP[5].incoming, 2); ADNodeSelection:add(5)")
assert s.eval("ADNodeSelection:getChain()") is None
s.execute("ADNodeSelection:toggle(5); WP[2].out = {3}; WP[5].incoming = {}")

# Move: the selection follows the ground under the mouse, a click puts it down in one move, the menu comes back
s.execute("press('AD_nodeSelection_move')")
assert s.eval("ADNodeSelection.moving") is not None and s.eval("ADNodeSelection.menu") is None
s.execute("GROUND = {25, 0, 13}")
assert s.eval("mouse(0.6, 0.6, false, false, 0)") is True
assert s.eval("WP[1].x") == 15 and s.eval("WP[4].z") == 13 and s.eval("WP[5].x") == 50
s.execute("ADNodeSelection:draw(vehicle)")
assert "AD_nodeSelection_place" in list(s.eval("DRAWN").values())
assert s.eval("mouse(0.6, 0.6, true, false, 1)") is True and s.eval("mouse(0.6, 0.6, false, true, 1)") is True
assert [(m["id"], m["x"]) for m in s.eval("SENT.moves").values()] == [(1, 15), (2, 25), (3, 35), (4, 45)]
assert s.eval("ADNodeSelection.moving") is None
s.execute("ADNodeSelection:draw(vehicle)")
assert s.eval("ADNodeSelection.menu") is not None
# Put on the ground: only the ones above it, one move
s.execute("SENT.moves = nil; WP[2].y = 3; press('AD_nodeSelection_ground')")
assert [(m["id"], m["y"]) for m in s.eval("SENT.moves").values()] == [(2, 0)]
# leaving the editor while moving puts them back
s.execute("for _, id in ipairs({1, 2, 3, 4}) do WP[id].undoOrigin = nil end; press('AD_nodeSelection_move'); GROUND = {30, 0, 10}; mouse(0.6, 0.6, false, false, 0)")
assert s.eval("WP[1].x") == 20
s.execute("AutoDrive.isInExtendedEditorMode = function() return false end; ADNodeSelection:draw(vehicle)")
assert s.eval("WP[1].x") == 15 and s.eval("WP[1].undoOrigin") is None and sel() == []
s.execute("AutoDrive.isInExtendedEditorMode = function() return true end")

# a click without keys outside the menu closes it and clears the selection, and does nothing else
s.execute("keys(true, true, false); mouse(0.2, 0.1, false, true, 1, 2); mouse(0.3, 0.1, false, true, 1, 3); letGo()")
assert s.eval("ADNodeSelection.menu") is not None
assert s.eval("mouse(0.01, 0.99, false, true, 1)") is True and sel() == [] and s.eval("ADNodeSelection.menu") is None
# Deselect and Delete in the menu
s.execute("keys(true, true, false); mouse(0.2, 0.1, false, true, 1, 2); mouse(0.3, 0.1, false, true, 1, 3); letGo()")
s.execute("press('AD_nodeSelection_deselect')")
assert sel() == [] and s.eval("ADNodeSelection.menu") is None
s.execute("keys(true, true, false); mouse(0.2, 0.1, false, true, 1, 2); mouse(0.3, 0.1, false, true, 1, 3); letGo()")
s.execute("press('AD_nodeSelection_delete')")
assert list(s.eval("SENT.deleted").values()) == [3, 2] and sel() == [] and s.eval("ADNodeSelection.menu") is None

# dragging waypoint 3 (already moved by the editor, undoOrigin set) takes 5 along, release sends one move for both
s.execute("keys(true, true, false); mouse(0.3, 0.1, false, true, 1, 3); mouse(0.5, 0.1, false, true, 1, 5); keys(false, false, false)")
s.execute("WP[3].undoOrigin = {x = 30, y = 0, z = 10}; WP[3].x = 33; WP[3].z = 14; vehicle.ad.nodeToMoveId = 3")
s.execute("ADNodeSelection:updateGroupMove(vehicle)")
assert s.eval("WP[5].x") == 53 and s.eval("WP[5].z") == 14 and s.eval("WP[5].undoOrigin.x") == 50
s.execute("ADNodeSelection:draw(vehicle)")
assert s.eval("ADNodeSelection.menu") is None   # not while dragging
s.execute("ADNodeSelection:finishMove(3); vehicle.ad.nodeToMoveId = nil")
assert [(m["id"], m["x"]) for m in s.eval("SENT.moves").values()] == [(3, 33), (5, 53)]
# a drag of a waypoint that is not selected moves only that one
s.execute("ADNodeSelection:finishMove(1)")
assert s.eval("SENT[1]") == "single 1"

# Alt + click on a selected waypoint deletes them all (highest id first), Alt + click elsewhere is left alone
s.execute("ADNodeSelection.menu = nil; keys(false, false, true)")
assert s.eval("mouse(0.1, 0.1, false, true, 1, 1)") is False
assert s.eval("mouse(0.5, 0.1, false, true, 1, 5)") is True
assert list(s.eval("SENT.deleted").values()) == [5, 3] and sel() == []

# with nothing selected, Ctrl + click on a waypoint keeps its old meaning (start a chain)
s.execute("keys(true, false, false)")
assert s.eval("mouse(0.4, 0.1, false, true, 1, 4)") is False and sel() == []
# a plain click (menu not open) clears the selection and is left to the editor (selects that waypoint as before)
s.execute("keys(true, true, false); mouse(0.4, 0.1, false, true, 1, 4); keys(false, false, false); ADNodeSelection.menuPending = false")
assert sel() == [4]
assert s.eval("mouse(0.1, 0.1, false, true, 1, 1)") is False and sel() == []
# waypoints added or deleted: ids shift, the selection is cleared
s.execute("keys(true, true, false); mouse(0.4, 0.1, false, true, 1, 4); COUNT = 6; ADNodeSelection:checkValid()")
assert sel() == []

# wiring
hud = read("scripts", "Hud.lua")
assert "ADNodeSelection:mouseEvent(vehicle, posX, posY, isDown, isUp, button)" in hud
assert hud.count("ADNodeSelection:finishMove(vehicle.ad.nodeToMoveId)") == 2
assert "ADNodeSelection:updateGroupMove(vehicle)" in hud and "ADNodeSelection.safeDraw(vehicle)" in hud
assert "ADNodeSelection:isSelected(point.id)" in read("scripts", "Specialization.lua")
assert read("register.lua").count("scripts/Manager/NodeSelection.lua") == 1
for f in os.listdir(os.path.join(MOD, "translations")):
    for key in ("count", "move", "ground", "delete", "deselect", "place"):
        assert 'name="AD_nodeSelection_%s"' % key in read("translations", f), (f, key)

print("OK: waypoint selection (box, Ctrl / Ctrl + Shift click toggle, menu once keys are let go: move with the mouse, "
      "put on the ground, side road, two-way / flip, one-way and tidy for a line, delete, deselect; click outside "
      "clears, Alt + click deletes all, group drag in one step, ids shifting clears, old Ctrl meanings kept, wired, "
      "translated)")
