"""Diagnostics: every error and warning built by ADDiag says what happened, with what (names, distances, values) and
what to check. Each message is localized like the game does it (text keys, then the arguments), in all languages;
every text key it uses exists in every language, and none of the new texts has a percent sign (they go into gsub)."""
import os
import re
import glob
import xml.etree.ElementTree as ET
from lupa.lua55 import LuaRuntime

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def texts(lang):
    root = ET.parse(os.path.join(MOD, "translations", "translation_%s.xml" % lang)).getroot()
    return {e.get("name"): e.get("text") for e in root.iter("text")}


LANGS = sorted(re.match(r".*translation_(\w+)\.xml", p).group(1) for p in glob.glob(os.path.join(MOD, "translations", "translation_*.xml")))
assert len(LANGS) == 18, LANGS
ALL = {lang: texts(lang) for lang in LANGS}

s = LuaRuntime(unpack_returned_tuples=True)
s.execute("""
    unpack = table.unpack
    SENT = {}
    LOG = {}
    ADMessagesManager = {messageTypes = {INFO = 1, WARN = 2, ERROR = 3}}
    AutoDriveMessageEvent = {sendMessageOrNotification = function(v, typ, text, duration, ...)
        table.insert(SENT, {type = typ, text = text, args = {...}, duration = duration}) end}
    Logging = {info = function(f, ...) table.insert(LOG, string.format(f, ...)) end}
    TEXTS = {}
    AutoDrive = {MODE_DRIVETO = 1, MODE_DELIVERTO = 2, MODE_PICKUPANDDELIVER = 3, MODE_UNLOAD = 4, MODE_LOAD = 5, MODE_BGA = 6}
    AutoDrive.localize = function(text)
        return (text:gsub("%$l10n_([%w_]+);", function(k) local x = TEXTS[k]; if x == nil then error("missing l10n " .. k) end return x end))
    end
    SETTINGS = {RecordDriveDirectionOffset = 2, RecordOppositeDriveDirectionOffset = 2}
    AutoDrive.getSetting = function(name) return SETTINGS[name] end
    CP_ACTIVE = false
    AutoDrive.getIsCPActive = function(self, v) return CP_ACTIVE end
    TOOL = nil
    AutoDrive.getSelectedWorkTool = function(v) return TOOL end
    IMPLEMENTS = {}
    AutoDrive.getAllImplements = function(v, includeVehicle) return IMPLEMENTS end
    NEEDED = {}
    AutoDrive.getRequiredRefuels = function(v, ignore) return NEEDED end
    g_fillTypeManager = {getFillTypeTitleByIndex = function(self, i) return ({[1] = "Diesel", [2] = "DEF", [7] = "Silage"})[i] or "?" end}
    MARKERS = {[500] = {name = "Grain silo"}}
    ROUTE = nil
    ADGraphManager = {
        getMapMarkerByWayPointId = function(self, id) return MARKERS[id] end,
        getDistanceFromNetwork = function(self, v) return 41.6 end,
        pathFromTo = function(self, a, b) return ROUTE end,
    }
    STATIONS, WORKSHOPS = {}, {}
    ADTriggerManager = {getRefuelTriggers = function(v, i) return STATIONS end, getRepairTriggers = function() return WORKSHOPS end}
    getWorldTranslation = function(node) return 0, 0, 0 end
    MathUtil = {vector2Length = function(x, z) return math.sqrt(x * x + z * z) end}
    function unit(name, damage) return {getFullName = function() return name end, spec_wearable = damage and {damage = damage} or nil} end
    MODE = 3
    TRUCK = {lastSpeedReal = 0, components = {{node = 1}},
        getClosestWayPoint = function() return 77 end,
        spec_motorized = {consumersByFillTypeName = {DIESEL = {fillType = 1, fillUnitIndex = 1}, DEF = {fillType = 2, fillUnitIndex = 2}}},
        getFillUnitFillLevelPercentage = function(self, i) return ({0.12, 0.4})[i] end,
        ad = {stateModule = {getName = function() return "Truck 1" end, getMode = function() return MODE end},
              collisionDetectionModule = {}}}
""")
s.execute(open(os.path.join(MOD, "scripts", "Manager", "Diagnostics.lua"), encoding="utf-8").read())


def last():
    m = s.eval("SENT[#SENT]")
    return m.type, m.text, [m.args[i] for i in range(1, len(m.args) + 1)], m.duration


USED = set()


def check(call, *must, typ=3):
    """run the call, localize the message in every language like the game, return the English text"""
    n = s.eval("#SENT")
    s.execute(call)
    assert s.eval("#SENT") == n + 1, call
    t, text, args, duration = last()
    assert t == typ and duration == 12000, (call, t)
    assert len(args) <= 31 and all(isinstance(a, str) for a in args), (call, args)
    keys = re.findall(r"\$l10n_([\w]+);", text)
    USED.update(keys)
    assert any(k.startswith("AD_hint_") for k in keys) or typ == 2 or "recordO" in text or "recordR" in text or "noTarget" in text, (call, text)
    english = None
    for lang in LANGS:
        for k in keys:
            assert k in ALL[lang], (lang, k)
        s.globals().TEXTS = s.table_from(ALL[lang])
        full = s.eval("function(t, ...) return string.format(AutoDrive.localize(t), ...) end")(text, *args)
        assert "$l10n_" not in full and "%s" not in full, (lang, full)
        if lang == "en":
            english = full
    for m in must:
        assert m in english, (m, english)
    if os.environ.get("SHOW_DIAG"):
        print("-", english)
    # the server log gets the same message
    assert s.eval("LOG[#LOG]") is not None
    return english


s.globals().TEXTS = s.table_from(ALL["en"])

# --- driving
s.execute("ROUTE = {}")
e = check("ADDiag.pathFailed(TRUCK, 500)", "Truck 1", "Grain silo", "nearest waypoint 77", "42 m", "Route check")
s.execute("ROUTE = {{}, {}, {}}")
e = check("ADDiag.pathFailed(TRUCK, 500)", "Grain silo", "42 m", "fences")
assert "nearest waypoint" not in e
check("ADDiag.pathFailed(TRUCK, 9)", "#9")
check("ADDiag.cannotReach(TRUCK, 500)", "Grain silo", "starting at waypoint 77", "other lane")
s.execute("DPM = {getCurrentWayPoint = function() return {id = 120, x = 30, z = 40} end}; TRUCK.lastSpeedReal = 0.3 / 3600")
e = check("ADDiag.stuck(TRUCK, DPM)", "next waypoint 120, 50 m, 0 km/h", "8 seconds")
s.execute("TRUCK.ad.collisionDetectionModule.trafficVehicle = {ad = {stateModule = {getName = function() return '8RX 410' end}}}")
check("ADDiag.stuck(TRUCK, DPM)", "blocked by 8RX 410")
s.execute("TRUCK.ad.collisionDetectionModule.trafficVehicle = nil; TRUCK.ad.collisionDetectionModule.detectedObstable = true")
check("ADDiag.stuck(TRUCK, DPM)", ", 0 km/h, ")
check("ADDiag.exitFieldNoRoute(TRUCK, '#33', 500)", "from #33 to Grain silo")
check("ADDiag.noTarget(TRUCK)", "no target set")

# --- refuel, repair, park
check("ADDiag.noRefuelStation(TRUCK, true)", "does not need fuel", "90 %", typ=2)
s.execute("NEEDED = {1, 2}; STATIONS = {}")
check("ADDiag.noRefuelStation(TRUCK, false)", "Diesel 12 %, DEF 40 %, 0 stations", "15 m")
s.execute("IMPLEMENTS = {unit('Tatra Phoenix', 0.72), unit('ASW 271', 0.02), unit('Dolly')}; WORKSHOPS = {{}, {}}")
check("ADDiag.noRepairStation(TRUCK)", "Tatra Phoenix 72 %, 2 workshops", "Auto repair")
assert "ASW" not in s.eval("LOG[#LOG]")
check("ADDiag.noParkDestination(TRUCK)", "(for ?)")
s.execute("TOOL = unit('Lizard 3000')")
check("ADDiag.noParkDestination(TRUCK)", "for Lizard 3000", "right-click")

# --- helpers
check("ADDiag.wrongModeForHelper(TRUCK)", "current mode", "Pickup and deliver")
check("ADDiag.aiJobActive(TRUCK)", "the game's helper is driving it")
s.execute("CP_ACTIVE = true")
check("ADDiag.aiJobActive(TRUCK)", "Courseplay is driving it")
check("ADDiag.cannotStartAIJob(TRUCK, nil, false)", "not standing on a field", "30 m")
check("ADDiag.cannotStartAIJob(TRUCK, 'Field 12 is not owned', true)", "(Field 12 is not owned)")

# --- recording, bunker silo, others
check("ADDiag.recordingTwoRoads(TRUCK, false)", "different offsets (2 m / 2 m)")
check("ADDiag.recordingTwoRoads(TRUCK, true)", "reversing")
check("ADDiag.noShovel(TRUCK)", "attached Tatra Phoenix, ASW 271, Dolly", "shovel")
check("ADDiag.noBunker(TRUCK)", "100 m")
check("ADDiag.bunkerEmpty(TRUCK, 7)", "(Silage)", "fermenting")
check("ADDiag.bunkerEmpty(TRUCK, nil)", "(?)")
check("ADDiag.noTrailerForShovel(TRUCK)", "50 m")
check("ADDiag.ualNotSupported(TRUCK)", "Universal Autoload", typ=2)
n = s.eval("#SENT")
s.execute("ADDiag.ualNotSupported(TRUCK)")
assert s.eval("#SENT") == n                         # once a session

# --- every new text: in all languages, no percent sign (gsub replacement), not empty
NEW = [k for k in ALL["en"] if k.startswith(("AD_diag_", "AD_hint_", "AD_cpHint_"))]
assert len(NEW) >= 60, len(NEW)
for lang in LANGS:
    for k in NEW:
        assert k in ALL[lang] and ALL[lang][k].strip(), (lang, k)
        assert "%" not in ALL[lang][k], (lang, k)
assert ALL["ea"]["AD_hint_refuel"] == ALL["es"]["AD_hint_refuel"]
# every key a Diagnostics, Ticker or escape message uses
for f in [("Manager", "Diagnostics.lua"), ("Gui", "Ticker.lua"), ("Manager", "UnloaderEscape.lua")]:
    src = open(os.path.join(MOD, "scripts", *f), encoding="utf-8").read()
    for k in set(re.findall(r'"(AD_(?:hint|diag|wait)_\w+)"', src)) | set(re.findall(r"\$l10n_(AD_\w+);", src)):
        for lang in LANGS:
            assert k in ALL[lang], (f, lang, k)
# the Courseplay hints exist for the infos the ticker shows
ticker = open(os.path.join(MOD, "scripts", "Gui", "Ticker.lua"), encoding="utf-8").read()
for name in ["ERROR_STOPPED", "ERROR_NO_PATH_FOUND", "IS_STUCK", "BLOCKED_BY_OBJECT", "OUT_OF_MONEY", "FUEL_IS_EMPTY",
             "IS_COMPLETELY_BROKEN", "NEEDS_UNLOADING", "WAITING_FOR_UNLOADER", "WAITING_FOR_RAIN_TO_FINISH"]:
    assert "AD_cpHint_" + name in ALL["en"], name
assert "AD_cpHint_" in ticker

print("OK: diagnostics (path finding: no route vs blocked, cannot reach, stuck with next waypoint / distance / speed / blocker, exit field, "
      "no target, refuel: fuels and stations, repair: damaged units and workshops, park: tool, helper mode, AI active, AI job, "
      "recording, shovel, bunker, empty bunker, trailer, Universal Autoload once; all %d languages, %d keys, no percent signs)" % (len(LANGS), len(NEW)))
