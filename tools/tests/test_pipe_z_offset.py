"""Pipe offset front/back (pipeZOffset): a vehicle setting from -5 to +5 m in 0.25 m steps, default 0; it moves the
unloader's place beside the combine forward (+) or back (-) for the side chase and the planning target built from it,
not behind the combine, not for auto-aiming choppers or sugarcane harvesters; on the vehicle tab next to Pipe Offset
and on the Overdrive tab; saved, loaded and synced like every vehicle setting; translated."""
import os
import re
from lupa.lua55 import LuaRuntime

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read(*parts):
    return open(os.path.join(MOD, *parts), encoding="utf-8").read().replace("\r\n", "\n")


s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    AutoDrive = {settings = {}}
    function ADInheritsFrom() return {} end
    AbstractMode = {}
""")
s.execute(read("scripts", "Settings.lua").split("\nfunction ")[0])
setting = s.eval("AutoDrive.settings.pipeZOffset")
values = list(setting["values"].values())
texts = list(setting.texts.values())
assert values == [i * 0.25 for i in range(-20, 21)], values
assert len(texts) == 41 and texts[0] == "-5.0m" and texts[15] == "-1.25m" and texts[20] == "0m" and texts[25] == "+1.25m" and texts[40] == "+5.0m"
assert values[setting.default - 1] == 0 and setting.current == setting.default
assert setting.isVehicleSpecific is True and setting.translate is False and not setting.isUserSpecific

# the side chase Z (static, dynamic and from the discharge node) moves by the setting; 0 changes nothing
s.execute(read("scripts", "Modes", "CombineUnloaderMode.lua"))
s.execute("""
    OFFSET = 0
    AutoDrive.getSetting = function(name, vehicle) if name == "pipeZOffset" then return OFFSET end end
    AutoDrive.getFrontToolLength = function() return 4 end
    AutoDrive.worldToLocal = function() return 0, 0, -3 end
    getWorldTranslation = function() return 0, 0, 0 end
    MODE = setmetatable({vehicle = {size = {length = 6}}, combine = {size = {length = 10}, ad = {}}, targetFillNode = 1},
                        {__index = CombineUnloaderMode})
    MODE.getDynamicSideChaseOffsetZ = function() return 1.5 end
    function all(planning) return {MODE:getSideChaseOffsetZ(false), MODE:getSideChaseOffsetZ(true), MODE:getDynamicSideChaseOffsetZ_fromDischargeNode(planning)} end
""")
def offsets(planning=False):
    return list(s.eval("all(%s)" % ("true" if planning else "false")).values())
base, base_plan = offsets(), offsets(True)
assert base == [4, 1.5, 3] and base_plan == [4, 1.5, 6], (base, base_plan)
s.execute("OFFSET = 1.25")
assert offsets() == [b + 1.25 for b in base] and offsets(True) == [b + 1.25 for b in base_plan]
s.execute("OFFSET = -2.5")
assert offsets() == [b - 2.5 for b in base]
# fixed-pipe choppers too; not auto-aiming choppers or sugarcane harvesters
s.execute("MODE.combine.ad = {isChopper = true, isFixedPipeChopper = true}")
assert offsets() == [b - 2.5 for b in base]
for kind in ("isAutoAimingChopper", "isSugarcaneHarvester"):
    s.execute("MODE.combine.ad = {isChopper = true, %s = true}" % kind)
    assert offsets() == base, kind
# behind the combine: followDistance only
mode = read("scripts", "Modes", "CombineUnloaderMode.lua")
rear = mode[mode.index("function CombineUnloaderMode:getRearChaseOffsetZ"):]
assert "pipeZOffset" not in rear[:rear.index("\nend\n")]
# the planning target comes from getPipeChasePosition(true), which uses these
assert ":getPipeChasePosition(true)" in read("scripts", "Modules", "PathFinderModule.lua")

# GUI: vehicle tab right after Pipe Offset, Overdrive tab; a tab shows a change made on the other one
vehicle_page = read("gui", "vehicleSettingsPage.xml")
assert vehicle_page.index('name="pipeOffset"') < vehicle_page.index('name="pipeZOffset"') < vehicle_page.index('name="followDistance"')
assert 'name="pipeZOffset"' in read("gui", "overdriveSettingsPage.xml")
s.execute("""
    ADSettingsPage = {}
    ADSettingsPage.superClass = function() return {onFrameOpen = function() end} end
    FocusManager = {setFocus = function() end}
""")
page_src = read("scripts", "Gui", "SettingsPage.lua")
for name in ("onFrameOpen", "showPendingSettings", "hasChanges", "loadGUISettings", "loadGUISetting", "onOptionChange"):
    body = page_src[page_src.index("function ADSettingsPage:%s(" % name):]
    s.execute(body[:body.index("\nend\n") + 5])
s.execute("""
    VEHICLE = {ad = {settings = {pipeZOffset = {current = 21}}}}
    AutoDrive.getControlledVehicle = function() return VEHICLE end
    function element(name) return {name = name, setState = function(self, state) self.state = state end} end
    A = {settingElements = {pipeZOffset = element("pipeZOffset")}, debugMsg = function() end}
    B = {settingElements = {pipeZOffset = element("pipeZOffset")}, debugMsg = function() end}
    setmetatable(A, {__index = ADSettingsPage}); setmetatable(B, {__index = ADSettingsPage})
    A:onFrameOpen(); B:onFrameOpen()
    A:onOptionChange(26, A.settingElements.pipeZOffset)
    B:onFrameOpen()
""")
assert s.eval("B.settingElements.pipeZOffset.state") == 26 and s.eval("VEHICLE.ad.settings.pipeZOffset.new") == 26

# saved, loaded and synced by the loops over every vehicle setting
spec = read("scripts", "Specialization.lua")
assert 'if setting.isVehicleSpecific then\n            schemaSavegame:register(XMLValueType.INT, "vehicles.vehicle(?).AutoDrive#" .. settingName' in spec
assert "setting.isVehicleSpecific and not setting.isUserSpecific" in read("scripts", "Events", "UpdateSettingsEvent.lua")

for f in os.listdir(os.path.join(MOD, "translations")):
    t = read("translations", f)
    for key in ("gui_ad_pipeZOffset", "gui_ad_pipeZOffset_tooltip"):
        m = re.search(r'name="%s"\s+text="([^"]+)"' % key, t)
        assert m and "%" not in m.group(1), (f, key)

print("OK: pipe offset front/back (pipeZOffset, -5..+5 m in 0.25 m, default 0, + forward): side chase, dynamic and "
      "discharge-node Z and so the planning target move by it, 0 changes nothing, not behind the combine, not for "
      "auto-aiming choppers or sugarcane; vehicle tab next to Pipe Offset and Overdrive tab, a tab shows a change from "
      "the other; saved/synced as a vehicle setting; 18 languages)")
