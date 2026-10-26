"""Drive through obstructions: the vehicle setting for the No AI Collisions mod, published as
vehicle.ad.allowDriveThrough; the settings row only shows when that mod is loaded; the wiring in the other files."""
import os
import re
import glob
import xml.etree.ElementTree as ET
from lupa.lua55 import LuaRuntime

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read(*parts):
    return open(os.path.join(MOD, *parts), encoding="utf-8").read().replace("\r\n", "\n")


s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    table.unpack = table.unpack or unpack
    SETTINGS = {}
    AutoDrive = {getSetting = function(name, vehicle)
        assert(name == "allowDriveThrough")
        local v = vehicle and vehicle.value
        if v == nil then return true end
        return v
    end}
    InGameMenuSettingsFrame = {COLOR_ALTERNATING = {[true] = {1, 1, 1, 1}, [false] = {0, 0, 0, 1}}}
    function element(visible)
        local e = {visible = visible ~= false, color = nil}
        function e:setVisible(v) self.visible = v end
        function e:getIsVisible() return self.visible end
        function e:setImageColor(_, r, g, b, a) self.color = r end
        return e
    end
    function makePage()
        LAYOUT = {elements = {}, invalidated = 0}
        function LAYOUT:invalidateLayout() self.invalidated = self.invalidated + 1 end
        ROWS = {}
        for i = 1, 5 do
            local row = element(true)
            row.parent = LAYOUT
            row.color = (i % 2 == 1) and 0 or 1     -- stripes as created: false, true, false, ...
            table.insert(LAYOUT.elements, row)
            ROWS[i] = row
        end
        OPTION = {parent = ROWS[3]}
        return {settingElements = {allowDriveThrough = OPTION, other = {parent = ROWS[1]}}}
    end
""")
s.execute(read("scripts", "Manager", "DriveThrough.lua"))
D = "ADDriveThrough"

# --- is No AI Collisions loaded (any mod name containing NoAICollisions), cached
s.execute("g_modIsLoaded = {FS25_AutoDrive = true, FS25_NoAICollisions_ProEdition = true}; ADDriveThrough.modLoaded = nil")
assert s.eval("ADDriveThrough.isNoAICollisionsLoaded()") is True
s.execute("g_modIsLoaded = {FS25_AutoDrive = true}")
assert s.eval("ADDriveThrough.isNoAICollisionsLoaded()") is True          # cached for the session
s.execute("ADDriveThrough.modLoaded = nil")
assert s.eval("ADDriveThrough.isNoAICollisionsLoaded()") is False
s.execute("g_modIsLoaded = {FS25_NoAICollisions = true}; ADDriveThrough.modLoaded = nil")
assert s.eval("ADDriveThrough.isNoAICollisionsLoaded()") is True           # plain edition too
s.execute("g_modIsLoaded = {FS25_NoAICollisions_ProEdition = false}; ADDriveThrough.modLoaded = nil")
assert s.eval("ADDriveThrough.isNoAICollisionsLoaded()") is False          # present but not loaded
s.execute("g_modIsLoaded = nil; ADDriveThrough.modLoaded = nil")
assert s.eval("ADDriveThrough.isNoAICollisionsLoaded()") is False

# --- the published field follows the setting; default true; safe without ad
s.execute("V = {ad = {}}; ADDriveThrough.update(V)")
assert s.eval("V.ad.allowDriveThrough") is True
s.execute("V.value = false; ADDriveThrough.update(V)")
assert s.eval("V.ad.allowDriveThrough") is False
s.execute("V.value = true; ADDriveThrough.update(V)")
assert s.eval("V.ad.allowDriveThrough") is True
s.execute("ADDriveThrough.update(nil); ADDriveThrough.update({})")

# --- what No AI Collisions is asked to do: read it on the root vehicle, nil = allowed
s.execute("""
    function modAllows(vehicle)
        local root = vehicle.rootVehicle or vehicle
        return not (root.ad ~= nil and root.ad.allowDriveThrough == false)
    end
    TRUCK = {ad = {}, value = false}; TRAILER = {rootVehicle = TRUCK}
    ADDriveThrough.update(TRUCK)
""")
assert s.eval("modAllows(TRAILER)") is False and s.eval("modAllows(TRUCK)") is False
assert s.eval("modAllows({ad = {}})") is True and s.eval("modAllows({})") is True

# (the row is shown or hidden by the Overdrive tab, see test_overdrive_settings.py)

# --- wiring
settings = read("scripts", "Settings.lua")
block = re.search(r"AutoDrive\.settings\.allowDriveThrough = \{(.*?)\n\}", settings, re.S).group(1)
for need in ("values = {false, true}", "default = 2,", "current = 2,", 'text = "gui_ad_allowDriveThrough"',
             'tooltip = "gui_ad_allowDriveThrough_tooltip"', "isVehicleSpecific = true", "isCopyPaste = true"):
    assert need in block, need
page = ET.parse(os.path.join(MOD, "gui", "overdriveSettingsPage.xml")).getroot()
opts = [e for e in page.iter("BinaryOption") if e.get("name") == "allowDriveThrough"]
assert len(opts) == 1 and opts[0].get("id") == "allowDriveThrough" and opts[0].get("onCreate") == "onCreateAutoDriveSetting"
order = [e.get("name") for e in page.iter() if e.get("onCreate") == "onCreateAutoDriveSetting"]
assert order.index("allowDriveThrough") == order.index("unloaderEscape") + 1          # next to "Drive clear when blocked"
register = read("register.lua")
assert register.index("scripts/Manager/DriveThrough.lua") > register.index("scripts/Manager/UnloaderEscape.lua")
spec = read("scripts", "Specialization.lua")
on_update = spec[spec.index("function AutoDrive:onUpdate(dt)"):]
assert "ADDriveThrough.update(self)" in on_update[:300]
assert "ADDriveThrough" not in read("scripts", "Gui", "SettingsPage.lua")          # upstream page untouched
langs = glob.glob(os.path.join(MOD, "translations", "translation_*.xml"))
assert len(langs) == 18
for path in langs:
    texts = {e.get("name"): e.get("text") for e in ET.parse(path).getroot().iter("text")}
    for key in ("gui_ad_allowDriveThrough", "gui_ad_allowDriveThrough_tooltip"):
        assert texts.get(key), (path, key)
        assert "%" not in texts[key], (path, key)
        assert "No AI Collisions" in texts[key], (path, key)

print("OK: drive through obstructions (No AI Collisions detection, vehicle.ad.allowDriveThrough follows the setting, "
      "default yes, root vehicle contract, setting next to drive clear on the Overdrive tab, "
      "wiring, 18 languages)")
