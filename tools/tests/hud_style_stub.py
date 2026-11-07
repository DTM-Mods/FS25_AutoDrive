"""Loads scripts/Hud/HudStyle.lua (the Overdrive look) into a test runtime, with the few engine functions it needs
stubbed where the test has not stubbed them itself. Every rounded rectangle drawn is recorded in ROUND_RECTS."""
import os

MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

STUBS = """
    g_screenAspectRatio = g_screenAspectRatio or 16 / 9
    createImageOverlay = createImageOverlay or function() return 1 end
    setOverlayColor = setOverlayColor or function() end
    setOverlayUVs = setOverlayUVs or function() end
    renderOverlay = renderOverlay or function() end
    setTextColor = setTextColor or function() end
    Utils = Utils or {}
    Utils.getFilename = Utils.getFilename or function(f, d) return tostring(d or "") .. f end
    AutoDrive = AutoDrive or {}
"""

RECORD = """
    ROUND_RECTS = {}
    local roundRect = ADHudStyle.roundRect
    ADHudStyle.roundRect = function(x, y, w, h, radius, color, isLinear, alpha)
        table.insert(ROUND_RECTS, {x = x, y = y, w = w, h = h, color = color})
        return roundRect(x, y, w, h, radius, color, isLinear, alpha)
    end
"""


def load(lua):
    lua.execute(STUBS)
    with open(os.path.join(MOD, "scripts", "Hud", "HudStyle.lua"), encoding="utf-8") as f:
        lua.execute(f.read())
    lua.execute(RECORD)
