"""Overdrive tab in the AutoDrive settings: every setting Overdrive adds is there (and only there), the vehicle
section only while in a vehicle, the drive-through row only with No AI Collisions, apply/reset only see the shown
rows, stripes start again under each section header, and the tab is wired into the settings window."""
import os
import re
import glob
import subprocess
import xml.etree.ElementTree as ET
from lupa.lua55 import LuaRuntime

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read(*parts):
    return open(os.path.join(MOD, *parts), encoding="utf-8").read().replace("\r\n", "\n")


def settings_of(page):
    root = ET.parse(os.path.join(MOD, "gui", page)).getroot()
    return [e.get("name") for e in root.iter() if e.get("onCreate") == "onCreateAutoDriveSetting"]


# --- every setting Overdrive adds (not in upstream) is on the Overdrive tab and on no other tab
up = subprocess.run(["git", "show", "upstream/main:scripts/Settings.lua"], cwd=MOD, capture_output=True, text=True, encoding="utf-8")
cur = read("scripts", "Settings.lua")
names = lambda t: set(re.findall(r"AutoDrive\.settings\.(\w+) = \{", t))
overdrive_tab = settings_of("overdriveSettingsPage.xml")
if up.returncode == 0:
    added = names(cur) - names(up.stdout)
    assert added == set(overdrive_tab), (added ^ set(overdrive_tab))
for page in glob.glob(os.path.join(MOD, "gui", "*SettingsPage.xml")):
    if not page.endswith("overdriveSettingsPage.xml"):
        others = set(settings_of(os.path.basename(page)))
        assert not (others & set(overdrive_tab)), (page, others & set(overdrive_tab))
blocks = dict(re.findall(r"AutoDrive\.settings\.(\w+) = \{(.*?)\n\}", cur, re.S))
vehicle_rows = [n for n in overdrive_tab if "isVehicleSpecific = true" in blocks[n]]
user_rows = [n for n in overdrive_tab if "isUserSpecific = true" in blocks[n]]
assert vehicle_rows + user_rows == overdrive_tab                     # vehicle section first, then "you"
assert len(vehicle_rows) == 6 and len(user_rows) == 3

# --- wiring
gui = read("scripts", "Gui.lua")
assert "AutoDrive.gui.ADOverdriveSettingsPage = ADOverdriveSettings.attach(ADSettingsPage.new())" in gui
assert '"gui/overdriveSettingsPage.xml", "autoDriveOverdriveSettings", AutoDrive.gui.ADOverdriveSettingsPage, true' in gui
assert gui.index("gui/overdriveSettingsPage.xml") < gui.index('"gui/settings.xml"')
assert 'ref="autoDriveOverdriveSettings"' in read("gui", "settings.xml")
win = read("scripts", "Gui", "Settings.lua")
assert '{self.autoDriveOverdriveSettings, alwaysEnabled, "ad_gui.speedmeter"' in win
assert win.index("self.autoDriveOverdriveSettings") < win.index("{self.autoDriveDebugSettings")
assert 'id="speedmeter"' in read("textures", "ad_gui.xml")
reg = read("register.lua")
assert reg.index("scripts/Gui/OverdriveSettingsPage.lua") > reg.index("scripts/Gui/SettingsPage.lua")
page_xml = read("gui", "overdriveSettingsPage.xml")
assert '<GUI name="autoDriveOverdriveSettings">' in page_xml
assert page_xml.count('onCreate="onCreateOverdriveSectionHeader"') == 3
for key in ("gui_ad_overdriveSettingsPage_title", "gui_ad_od_thisVehicle", "gui_ad_od_noVehicle", "gui_ad_od_you"):
    for path in glob.glob(os.path.join(MOD, "translations", "translation_*.xml")):
        texts = {e.get("name"): e.get("text") for e in ET.parse(path).getroot().iter("text")}
        assert texts.get(key) and "%" not in texts[key], (path, key)

# --- page logic
s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    table.unpack = table.unpack or unpack
    ADSettingsPage = {opened = 0}
    function ADSettingsPage.onFrameOpen(page) ADSettingsPage.opened = ADSettingsPage.opened + 1 end
    InGameMenuSettingsFrame = {COLOR_ALTERNATING = {[true] = {1, 1, 1, 1}, [false] = {0, 0, 0, 1}}}
    g_i18n = {getText = function(self, key) return ({gui_ad_od_thisVehicle = "This vehicle"})[key] or key end}
    AutoDrive = {settings = {}}
    VEHICLE = nil
    AutoDrive.getControlledVehicle = function() return VEHICLE end
    ADDriveThrough = {SETTING = "allowDriveThrough", loaded = true}
    function ADDriveThrough.isNoAICollisionsLoaded() return ADDriveThrough.loaded end
    local function element(kind)
        local e = {visible = true, kind = kind}
        function e:setVisible(v) self.visible = v end
        function e:getIsVisible() return self.visible end
        if kind == "row" then function e:setImageColor(_, r) self.color = r end end
        if kind == "text" then function e:setText(t) self.text = t end end
        return e
    end
    function makePage(vehicleNames, userNames)
        local layout = {elements = {}, invalidated = 0}
        function layout:invalidateLayout() self.invalidated = self.invalidated + 1 end
        local page = {settingElements = {}, boxLayout = layout}
        local function header()
            local h = element("text"); h.odSectionHeader = true; table.insert(layout.elements, h); return h
        end
        page.odVehicleHeader = header()
        page.odNoVehicleText = header()
        local function rows(list, vehicleSpecific)
            for _, n in ipairs(list) do
                AutoDrive.settings[n] = {isVehicleSpecific = vehicleSpecific, isUserSpecific = not vehicleSpecific}
                local row = element("row")
                table.insert(layout.elements, row)
                page.settingElements[n] = {parent = row, name = n}
            end
        end
        rows(vehicleNames, true)
        header()
        rows(userNames, false)
        return page
    end
""")
s.execute(read("scripts", "Gui", "OverdriveSettingsPage.lua"))
lua_list = lambda xs: "{" + ",".join('"%s"' % x for x in xs) + "}"
s.execute("PAGE = ADOverdriveSettings.attach(makePage(%s, %s))" % (lua_list(vehicle_rows), lua_list(user_rows)))


def shown():
    return sorted(s.eval("(function() local t = {} for n in pairs(PAGE.settingElements) do t[#t + 1] = n end return table.concat(t, ',') end)()").split(","))


def visible(name):
    return s.eval('PAGE.allSettingElements["%s"].parent.visible' % name)


# not in a vehicle: only the "you" rows, the note shows, apply/reset only see those rows
s.execute("VEHICLE = nil; PAGE:onFrameOpen()")
assert shown() == sorted(user_rows), shown()
assert all(not visible(n) for n in vehicle_rows) and all(visible(n) for n in user_rows)
assert s.eval("PAGE.odNoVehicleText.visible") is True and s.eval("PAGE.odVehicleHeader.text") == "This vehicle"
assert s.eval("ADSettingsPage.opened") == 1                         # the normal page open still runs
# in a vehicle: all rows, header names the vehicle, note hidden
s.execute("VEHICLE = {ad = {stateModule = {getName = function() return 'Tatra 6x6' end}}}; PAGE:onFrameOpen()")
assert shown() == sorted(overdrive_tab), shown()
assert s.eval("PAGE.odNoVehicleText.visible") is False and s.eval("PAGE.odVehicleHeader.text") == "This vehicle: Tatra 6x6"
# without No AI Collisions the drive-through row stays hidden, also in a vehicle
s.execute("ADDriveThrough.loaded = false; PAGE:onFrameOpen()")
assert "allowDriveThrough" not in shown() and not visible("allowDriveThrough")
assert len(shown()) == len(overdrive_tab) - 1
# stripes: start with the first colour under each header, skip hidden rows
colors = s.eval("""(function()
    local out = {}
    for _, e in ipairs(PAGE.boxLayout.elements) do
        if e.odSectionHeader then out[#out + 1] = "|" elseif e.visible then out[#out + 1] = tostring(e.color) end
    end
    return table.concat(out, ",")
end)()""")
assert colors == "|,|,0,1,0,1,0,|,0,1,0", colors                   # 5 vehicle rows shown (drive-through hidden), 3 user rows
assert s.eval("PAGE.boxLayout.invalidated") == 3

print("OK: Overdrive tab (all %d Overdrive settings, none left on other tabs, vehicle section only in a vehicle with "
      "its name, drive-through row only with No AI Collisions, apply/reset see only shown rows, stripes per section, "
      "wired into the settings window, 18 languages)" % len(overdrive_tab))
