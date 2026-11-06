"""The HUD in CourseCorrect's look (ADHudStyle): the panel (rounded, shadow, header colour as the line along the top,
growing with the header's lines), the header (title bold, the rest grey, parts split by dots), buttons on chips
(lighter under the mouse, green when on, image inset once; the small header buttons flat), the speed and loop
counter on chips, the drop-down lists as rounded fields and an opened list as a panel with the row under the mouse
highlighted. Faster: a button image is switched only when its state changes, the header text is wrapped and list
names shortened only when they change. Colours: new defaults, a saved colour still at its old default gets the new
one. The panels next to the HUD use the same style."""
import os
from lupa.lua55 import LuaRuntime
import hud_style_stub

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read(*parts):
    return open(os.path.join(MOD, *parts), encoding="utf-8").read().replace("\r\n", "\n")


s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    TEXTS, OVERLAYS, SLICE_SETS, LINE_LENGTH_CALLS, WIDTH_CALLS = {}, {}, 0, 0, 0
    unpack = unpack or table.unpack
    function string.split(text, sep)
        local parts, from = {}, 1
        while true do
            local i = string.find(text, sep, from, true)
            if i == nil then table.insert(parts, string.sub(text, from)); return parts end
            table.insert(parts, string.sub(text, from, i - 1)); from = i + #sep
        end
    end
    BOLD, COLOR = false, {1, 1, 1, 1}
    function renderText(x, y, size, text) table.insert(TEXTS, {x = x, y = y, size = size, text = text, bold = BOLD, color = COLOR}) end
    function setTextBold(b) BOLD = b end
    function setTextColor(r, g, b, a) COLOR = {r, g, b, a} end
    function setTextAlignment() end
    RenderText = {ALIGN_LEFT = 0, ALIGN_CENTER = 1}
    function getTextWidth(size, text) WIDTH_CALLS = WIDTH_CALLS + 1; return #text * size * 0.25 end
    function getTextHeight(size) return size end
    function getTextLineLength(size, text, width) LINE_LENGTH_CALLS = LINE_LENGTH_CALLS + 1; return math.floor(width / (size * 0.5)) end
    function utf8Substr(text, from, n) return string.sub(text, from + 1, from + n) end
    function drawFilledRect() end
    g_screenAspectRatio = 16 / 9
    local function overlay(slice, x, y, w, h)
        local o = {slice = slice, x = x, y = y, w = w, h = h, overlayId = #OVERLAYS + 1, renders = 0}
        function o:setSliceId(id) SLICE_SETS = SLICE_SETS + 1; self.slice = id end
        function o:setPosition(px, py) self.x, self.y = px, py end
        function o:setDimension(pw, ph) self.w = pw or self.w; self.h = ph or self.h end
        function o:setColor() end
        function o:setUVs() end
        function o:render() self.renders = self.renders + 1 end
        table.insert(OVERLAYS, o)
        return o
    end
    g_overlayManager = {createOverlay = function(self, slice, x, y, w, h) return overlay(slice, x, y, w, h) end,
        textureConfigs = {ad_gui = {slices = {input_start_stop_1 = true, input_start_stop_2 = true, input_toggleHud_1 = true,
            avoidFruit_1 = true, avoidFruit_2 = true}}}}
    Overlay = {new = function(file, x, y, w, h) return overlay(file, x, y, w, h) end}
    g_baseUIFilename, g_colorBgUVs = "ui.png", {}
    MOUSE = true
    g_inputBinding = {getShowMouseCursor = function() return MOUSE end}
    g_lastMousePosX, g_lastMousePosY = -1, -1
    g_i18n = {getText = function(self, k) return k end}
    AutoDrive = {FONT_SCALE = 0.009, version = "3.0.1.4-od.64", pullDownListExpanded = 0, directory = "mod/"}
    SETTINGS = {showTooltips = true}
    AutoDrive.getSetting = function(name) return SETTINGS[name] end
    AutoDrive.getSettingState = function(name) return SETTINGS[name .. "State"] or 1 end
    AutoDrive.isEditorModeEnabled = function() return false end
    AutoDrive.getDebugChannelIsSet = function() return false end
    AutoDrive.MODE_DRIVETO = 1
    MODE, ACTIVE = 1, false
    VEHICLE = {ad = {sToolTip = "", stateModule = {
        getMode = function() return MODE end, isActive = function() return ACTIVE end,
        getRemainingDriveTime = function() return 0 end, getCurrentLocalizedTaskInfo = function() return TASK or "" end}}}
    AutoDriveHud = {getModeName = function() return "Drive to" end}
""")
hud_style_stub.load(s)
s.execute(read("scripts", "AutoDrive.lua")[read("scripts", "AutoDrive.lua").index("AutoDrive.colors = {"):].split("AutoDrive.fuelFillTypes")[0])
s.execute("""
    AutoDrive.currentColors = {}
    for k, v in pairs(AutoDrive.colors) do AutoDrive.currentColors[k] = v end
""")
for f in ("GenericHudElement.lua", "HudButton.lua", "HudSettingsButton.lua", "HudCounterButton.lua", "HudSpeedmeter.lua", "HudIcon.lua", "PullDownList.lua"):
    code = read("scripts", "Hud", f)
    # (Lua 5.1 lets the list assign its loop variable, the test's Lua 5.5 does not: that line is left out here)
    code = code.replace("                    i = i - 1" + chr(10), "")
    s.execute(code)
s.execute("""
    U = 1080
    AutoDrive.Hud = {gapWidth = 3 / 1920, gapHeight = 3 / U, headerIconWidth = 16 / 1920, buttonWidth = 32 / 1920, buttonHeight = 32 / U,
        listItemHeight = 20 / U}
    BG = ADHudIcon:new(0.8, 0.3, 0.19, 0.2, "ad_gui.Background", 0, "background")
    HEADER = ADHudIcon:new(0.8, 0.48, 0.19, 0.046, "ad_gui.Header", 1, "header")
    AutoDrive.Hud.headerElement = HEADER
    -- a header button on the title line, as AutoDriveHud:createHudAt places it
    HB = ADHudButton:new(0.97, ADHudIcon.getTitleCenterY(0.48 + 0.046, 1) - 0.012, 0.0135, 0.024, "input_toggleHud", nil, nil, nil, nil, nil, nil, nil, "", 1, true):setFlat()
    HB.headerBaseY = HB.position.y
    AutoDrive.Hud.headerButtons = {HB}
""")


def rects():
    return [dict(r.items()) for r in s.eval("ROUND_RECTS").values()]


# the panel: shadow, body in the background colour, a line along the top in the header colour
s.execute("ROUND_RECTS = {}; BG:onDraw(VEHICLE, 1)")
r = rects()
assert len(r) == 3, r
assert s.eval("ROUND_RECTS[2].color == AutoDrive.currentColors.ad_color_background")
assert s.eval("ROUND_RECTS[3].color == AutoDrive.currentColors.ad_color_header")
top = r[1 + 1]["y"] + r[1 + 1]["h"]
assert abs(r[2]["y"] + r[2]["h"] - top) < 1e-9 and r[2]["w"] < r[1]["w"] and r[0]["w"] > r[1]["w"]
assert s.eval("BG.ov.renders") == 0   # the old square background is not drawn

# the header: a title bar: the title large and bold at the top, the details in grey on the line below, split by dots;
# the header's square bar is not drawn
s.execute("TEXTS = {}; HEADER:onDraw(VEHICLE, 1)")
texts = [dict(t.items()) for t in s.eval("TEXTS").values()]
assert len(texts) == 2, texts
assert texts[0]["text"] == "AutoDrive Overdrive" and texts[0]["bold"] and abs(texts[0]["size"] - 0.0165) < 1e-9, texts
assert texts[1]["text"] == "3.0.1.4-od.64 · Drive to" and not texts[1]["bold"] and abs(texts[1]["size"] - 0.0115) < 1e-9, texts
assert texts[1]["y"] < texts[0]["y"] and texts[1]["y"] > 0.48, texts      # below the title, inside the bar
assert texts[0]["y"] + texts[0]["size"] <= 0.48 + 0.046 + 1e-9                # the title inside the bar's top
assert tuple(texts[1]["color"].values()) == tuple(s.eval("ADHudStyle.linear(ADHudStyle.C.muted)").values())
assert s.eval("HEADER.ov.renders") == 0
# the header button sits on the title line
title_mid = texts[0]["y"] + texts[0]["size"] / 2
assert abs(s.eval("HB.position.y + HB.size.height / 2") - title_mid) < 1e-9
# wrapped again only when the text changes: no measuring on unchanged frames
s.execute("WIDTH_CALLS = 0; HEADER:onDraw(VEHICLE, 1); HEADER:onDraw(VEHICLE, 1)")
assert s.eval("WIDTH_CALLS") == 0, s.eval("WIDTH_CALLS")
s.execute("TASK = 'Driving to a very long target name ' .. string.rep('x', 120); WIDTH_CALLS = 0; TEXTS = {}; HEADER:onDraw(VEHICLE, 1)")
assert s.eval("WIDTH_CALLS") > 0 and s.eval("#HEADER.wrappedLines") > 1
# more lines: the title and the header button move up together, the details go down line by line
texts = [dict(t.items()) for t in s.eval("TEXTS").values()]
extra = s.eval("HEADER.extraHeight")
assert extra > 0 and abs(texts[0]["y"] + texts[0]["size"] / 2 - (title_mid + extra)) < 1e-9
assert abs(s.eval("HB.position.y + HB.size.height / 2") - (title_mid + extra)) < 1e-9 and s.eval("HB.ov.y") == s.eval("HB.position.y")
assert all(texts[k + 1]["y"] < texts[k]["y"] for k in range(1, len(texts) - 1))
# the panel grows upwards with the extra lines
s.execute("ROUND_RECTS = {}; BG:onDraw(VEHICLE, 1)")
assert abs(rects()[1]["h"] - (0.2 + s.eval("HEADER.extraHeight"))) < 1e-9 and s.eval("HEADER.extraHeight") > 0
s.execute("TASK = nil; HEADER:onDraw(VEHICLE, 1)")
assert s.eval("HEADER.extraHeight") == 0 and s.eval("HB.position.y") == s.eval("HB.headerBaseY")

# the title ends before the leftmost header button shown: undo / redo (editor only) are drawn under it otherwise
def title_after(undo_x):
    s.execute(f"""
        UNDO = ADHudButton:new({undo_x}, HB.position.y, 0.0135, 0.024, "input_undo", nil, nil, nil, nil, nil, nil, nil, "", 1, false):setFlat()
        UNDO.headerBaseY = UNDO.position.y
        AutoDrive.Hud.headerButtons = {{HB, UNDO}}
        TEXTS = {{}}; HEADER:onDraw(VEHICLE, 1)
        UNDO.isVisible = true
        TEXTS = {{}}; HEADER:onDraw(VEHICLE, 1)
    """)
    return dict(s.eval("TEXTS[1]").items())


def title_width(t):
    return len(t["text"]) * t["size"] * 0.25          # as the stub's getTextWidth


t = title_after(0.89)           # room 0.0806 for 0.0784: the full title
assert t["text"] == "AutoDrive Overdrive" and abs(t["size"] - 0.0165) < 1e-9, t
t = title_after(0.88)           # a bit less room: the full title a little smaller, on the same middle line
assert t["text"] == "AutoDrive Overdrive" and 0.0165 * 0.8 <= t["size"] < 0.0165, t
assert t["x"] + title_width(t) <= 0.88 + 1e-9 and abs(t["y"] + t["size"] / 2 - title_mid) < 1e-9, t
t = title_after(0.85)           # far less room: the short title
assert t["text"] == "AutoDrive" and t["x"] + title_width(t) <= 0.85 + 1e-9, t
t = title_after(0.815)          # even the short title too long: smaller
assert t["text"] == "AutoDrive" and t["x"] + title_width(t) <= 0.815 + 1e-9, t
# undo / redo hidden (editor off): the full title again; measured only when the room changes
s.execute("UNDO.isVisible = false; TEXTS = {}; HEADER:onDraw(VEHICLE, 1); WIDTH_CALLS = 0; HEADER:onDraw(VEHICLE, 1)")
assert s.eval("TEXTS[1].text") == "AutoDrive Overdrive" and s.eval("WIDTH_CALLS") == 0
s.execute("AutoDrive.Hud.headerButtons = {HB}")

# a button: on a chip, image moved inside once; green tint when on; lighter under the mouse; image switched only on changes
s.execute("""
    START = ADHudButton:new(0.81, 0.31, 32 / 1920, 32 / U, "input_start_stop", nil, nil, nil, nil, nil, nil, nil, "tip", 1, true)
    ADHudButton.getNewState = function(self, vehicle) return ACTIVE and 2 or 1 end
    ROUND_RECTS = {}; SLICE_SETS = 0; START:onDraw(VEHICLE, 1)
""")
assert len(rects()) == 1 and s.eval("ROUND_RECTS[1].color == ADHudStyle.C.chip")
assert s.eval("START.ov.w") < s.eval("START.size.width") and s.eval("START.ov.x") > s.eval("START.position.x")
assert s.eval("SLICE_SETS") == 1 and s.eval("START.ov.renders") == 1
s.execute("ov_x = START.ov.x; ROUND_RECTS = {}; SLICE_SETS = 0; START:onDraw(VEHICLE, 1); START:onDraw(VEHICLE, 1)")
assert s.eval("SLICE_SETS") == 0 and s.eval("START.ov.x") == s.eval("ov_x")
s.execute("ACTIVE = true; ROUND_RECTS = {}; START:onDraw(VEHICLE, 1)")
assert s.eval("SLICE_SETS") == 1 and len(rects()) == 2 and s.eval("ROUND_RECTS[2].color == ADHudStyle.C.accent")
s.execute("g_lastMousePosX, g_lastMousePosY = 0.811, 0.311; ROUND_RECTS = {}; START:onDraw(VEHICLE, 1)")
assert s.eval("ROUND_RECTS[1].color == ADHudStyle.C.hover") and s.eval("ROUND_RECTS[2].color == ADHudStyle.C.accentHover")
# the mouse not shown for AutoDrive: no hover
s.execute("MOUSE = false; ROUND_RECTS = {}; START:onDraw(VEHICLE, 1); MOUSE = true")
assert s.eval("ROUND_RECTS[1].color == ADHudStyle.C.chip")
s.execute("ACTIVE = false")
# a header button: flat, a round spot only under the mouse, image not moved
s.execute("""
    CLOSE = ADHudButton:new(0.95, 0.48, 16 / 1920, 16 / U, "input_toggleHud", nil, nil, nil, nil, nil, nil, nil, "", 1, true):setFlat()
    g_lastMousePosX, g_lastMousePosY = 0, 0; ROUND_RECTS = {}; CLOSE:onDraw(VEHICLE, 1)
""")
assert len(rects()) == 0 and s.eval("CLOSE.ov.x") == 0.95
s.execute("g_lastMousePosX, g_lastMousePosY = 0.9502, 0.4802; ROUND_RECTS = {}; CLOSE:onDraw(VEHICLE, 1); g_lastMousePosX, g_lastMousePosY = 0, 0")
assert len(rects()) == 1 and s.eval("ROUND_RECTS[1].color == ADHudStyle.C.hover")

# a yes / no setting on the HUD: green chip when yes
s.execute("""
    FRUIT = ADHudSettingsButton:new(0.82, 0.31, 32 / 1920, 32 / U, "avoidFruit", "tip", 1, true)
    SETTINGS.avoidFruitState = 2; ROUND_RECTS = {}; FRUIT:onDraw(VEHICLE, 1)
""")
assert len(rects()) == 2 and s.eval("ROUND_RECTS[2].color == ADHudStyle.C.accent")
s.execute("SETTINGS.avoidFruitState = 1; ROUND_RECTS = {}; FRUIT:onDraw(VEHICLE, 1)")
assert len(rects()) == 1

# speed and loop counter on chips, the counter green while it counts
s.execute("""
    VEHICLE.ad.stateModule.getSpeedLimit = function() return 40 end
    g_i18n.getSpeed = function(self, v) return v end
    SPEED = ADHudSpeedmeter:new(0.83, 0.31, 32 / 1920, 32 / U, false)
    ROUND_RECTS = {}; TEXTS = {}; SPEED:onDraw(VEHICLE, 1)
    LOOP = ADHudCounterButton:new(0.84, 0.31, 32 / 1920, 32 / U, "loop_counter")
    ADHudCounterButton.getNewState = function() return ADHudCounterButton.STATE_ACTIVE, 3 end
    LOOP:onDraw(VEHICLE, 1)
""")
assert len(rects()) == 3 and s.eval("TEXTS[1].text") == "40" and s.eval("ROUND_RECTS[3].color == ADHudStyle.C.accent")

# a drop-down list: a rounded field; opened, a panel with the row under the mouse highlighted
s.execute("""
    LIST = setmetatable({}, {__index = ADPullDownList})
    LIST:init(0.82, 0.4, 0.1, 32 / U)
    LIST.type, LIST.state, LIST.text, LIST.selected, LIST.hovered = ADPullDownList.TYPE_TARGET, ADPullDownList.STATE_COLLAPSED, "Farm silo", 1, 2
    LIST.iconSize = {width = 16 / 1920, height = 16 / U}
    LIST.rightIconPos = {x = 0.9, y = 0.4}; LIST.rightIconPos2 = {x = 0.89, y = 0.4}; LIST.rightIconPos3 = {x = 0.88, y = 0.4}; LIST.rightIconPos4 = {x = 0.87, y = 0.4}
    LIST.ovExpand = g_overlayManager:createOverlay("arrow", 0, 0, 1, 1)
    LIST.ovBG = g_overlayManager:createOverlay("bg", 0, 0, 1, 1)
    LIST.expandedSize = {width = 0.1, height = 0.2}
    LIST.direction = ADPullDownList.EXPANDED_DOWN
    LIST.isVisible = true
    LIST.updateState = function() end
    LIST.imagePlus, LIST.imageMinus, LIST.imageFilter, LIST.imageCollapseAll, LIST.imageRename = "p", "m", "f", "c", "r"
    LIST:initReusableOverlaysOnlyOnce()
    VEHICLE.ad.destinationFilterText = ""
    ENTRIES = {{displayName = "Farm silo", returnValue = 1, isFolder = false}, {displayName = "Field 12", returnValue = 2, isFolder = false},
               {displayName = "Shop", returnValue = 3, isFolder = false}}
    LIST.getListElementByDisplayIndex = function(self, vehicle, i) return ENTRIES[i] end
    ROUND_RECTS = {}; LIST:onDraw(VEHICLE, 1)
""")
assert len(rects()) == 1 and s.eval("ROUND_RECTS[1].color == ADHudStyle.C.surface") and s.eval("LIST.ovBG.renders") == 0
s.execute("g_lastMousePosX, g_lastMousePosY = 0.83, 0.405; ROUND_RECTS = {}; LIST:onDraw(VEHICLE, 1); g_lastMousePosX, g_lastMousePosY = 0, 0")
assert s.eval("ROUND_RECTS[1].color == ADHudStyle.C.hover")
s.execute("""
    SETTINGS.useFolders = false
    LIST.state = ADPullDownList.STATE_EXPANDED; LIST.expandedBottom = 0.2
    ROUND_RECTS = {}; TEXTS = {}; LIST:onDraw(VEHICLE, 1)
""")
r = rects()
# shadow + panel, then one highlight: the hovered row (hovered 2 = the 2nd entry, 'Field 12')
assert len(r) == 3 and s.eval("ROUND_RECTS[2].color == ADHudStyle.C.surface") and s.eval("ROUND_RECTS[3].color == ADHudStyle.C.hover"), r
field = [dict(t.items()) for t in s.eval("TEXTS").values() if dict(t.items())["text"] == "Field 12"][0]
assert r[2]["y"] < s.eval("LIST:getTextPositionByDisplayIndex(3, 1).y") + 0.009 < r[2]["y"] + r[2]["h"]
assert tuple(field["color"].values()) == tuple(s.eval("AutoDrive.currentColors.ad_color_hudTextHover").values())
# list names are shortened once, then taken from the cache
s.execute("LINE_LENGTH_CALLS = 0; LIST:onDraw(VEHICLE, 1); LIST:onDraw(VEHICLE, 1)")
assert s.eval("LINE_LENGTH_CALLS") == 0

# colours: a saved colour still at the old default is the player's old default, not their choice
s.execute(read("scripts", "XML.lua")[read("scripts", "XML.lua").index("function AutoDrive.isPreviousHudColor"):].split("\nend\n")[0] + "\nend\n")
assert s.eval("AutoDrive.isPreviousHudColor('ad_color_background', 0, 0, 0, 0.67)") is True
assert s.eval("AutoDrive.isPreviousHudColor('ad_color_header', 0.171, 0.323, 0, 1)") is True
assert s.eval("AutoDrive.isPreviousHudColor('ad_color_background', 0.2, 0, 0, 0.67)") is False
assert s.eval("AutoDrive.isPreviousHudColor('ad_color_markerText', 0.5, 1, 0.5, 1)") is False
xml = read("scripts", "XML.lua")
assert "if not AutoDrive.isPreviousHudColor(color, red, green, blue, alpha) then" in xml

# wiring: sourced right after the generic element; header buttons flat; the HUD keeps its header element
reg = read("register.lua")
assert reg.index("scripts/Hud/HudStyle.lua") == reg.index("scripts/Hud/GenericHudElement.lua") + len("scripts/Hud/GenericHudElement.lua") + len('", g_currentModDirectory))\nsource(Utils.getFilename("')
hud = read("scripts", "Hud.lua")
assert hud.count(":setFlat())") == 4 and hud.count("addHeaderButton(ADHudButton:new(") == 4 and "AutoDriveHud.defaultHeaderHeight = 0.046" in hud and "self.rowHeader + self.headerHeight - self.posY + self.gapHeight" in hud and "self.headerElement = ADHudIcon:new(" in hud
assert os.path.getsize(os.path.join(MOD, "textures", "hud_circle.dds")) == 16512
# the panels next to the HUD in the same look
for f in (("Gui", "WaypointPanel.lua"), ("Manager", "NodeSelection.lua"), ("Manager", "RouteMarkers.lua")):
    assert "ADHudStyle." in read("scripts", *f), f

print("OK: HUD in CourseCorrect's look (panel with shadow and top line, title bold + grey details, buttons on chips: hover, "
      "green when on, flat header buttons; speed / loop counter chips; lists as rounded fields, opened list as a panel with "
      "the hovered row highlighted); images switched / header wrapped / names shortened only on changes; old default "
      "colours migrated; waypoint panel, selection menu and route-check count in the same style")
