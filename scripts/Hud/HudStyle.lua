-- Overdrive: the look of the HUD and the panels next to it, the same as CourseCorrect's panel: a dark rounded panel
-- with a green line along the top, rounded dark chips for the buttons and fields (lighter under the mouse, green when
-- on), off-white text and grey secondary text.
-- Colours are written as they look on screen (sRGB); the game takes overlay and text colours as linear values, so they
-- go to it converted (once per colour table). The colours a player can change (AutoDrive.currentColors) are linear
-- already and are used as they are.
ADHudStyle = {}

ADHudStyle.GAMMA = 2.2

ADHudStyle.C = {
    bg = {0.06, 0.07, 0.085, 0.94},
    shadow = {0, 0, 0, 0.35},
    surface = {0.11, 0.125, 0.145, 1},
    chip = {0.15, 0.165, 0.19, 1},
    hover = {0.20, 0.22, 0.26, 1},
    line = {1, 1, 1, 0.06},
    text = {0.93, 0.94, 0.95, 1},
    muted = {0.60, 0.64, 0.69, 1},
    accent = {0.20, 0.72, 0.45, 1},
    accentHover = {0.25, 0.80, 0.51, 1},
    accentSoft = {0.20, 0.72, 0.45, 0.28},
    danger = {0.86, 0.30, 0.30, 1},
    dangerHover = {0.93, 0.38, 0.38, 1},
    warn = {0.98, 0.75, 0.25, 1},
    dim = {1, 1, 1, 0.35},
}

-- sizes in 1080p pixels, scaled with the UI scale
ADHudStyle.PANEL_RADIUS = 10
ADHudStyle.CHIP_RADIUS = 6
ADHudStyle.ACCENT_HEIGHT = 3
ADHudStyle.SHADOW = 4
-- the button image inside its chip
ADHudStyle.ICON_INSET = 0.14

local linearCache = setmetatable({}, {__mode = "k"})

--- sRGB colour table -> linear (cached per table)
function ADHudStyle.linear(color)
    local c = linearCache[color]
    if c == nil then
        local g = ADHudStyle.GAMMA
        c = {(color[1] or 0) ^ g, (color[2] or 0) ^ g, (color[3] or 0) ^ g, color[4] or 1}
        linearCache[color] = c
    end
    return c
end

--- 1080p pixels -> screen height units, with the UI scale
function ADHudStyle.px(pixels, uiScale)
    return pixels * (uiScale or 1) / 1080
end

local pixelOverlay, circleOverlay

local function getPixel()
    if pixelOverlay == nil then
        pixelOverlay = createImageOverlay("dataS/menu/base/graph_pixel.dds")
    end
    return pixelOverlay
end

-- a white disc: the rounded corners are its quarters
local function getCircle()
    if circleOverlay == nil then
        circleOverlay = createImageOverlay(Utils.getFilename("textures/hud_circle.dds", AutoDrive.directory))
    end
    return circleOverlay
end

-- a texture loads in the background: drawing it before that only fills the log with warnings
local function isReady(id)
    return id ~= nil and id ~= 0 and (getIsOverlayReady == nil or getIsOverlayReady(id))
end

function ADHudStyle.delete()
    if pixelOverlay ~= nil then
        delete(pixelOverlay)
        pixelOverlay = nil
    end
    if circleOverlay ~= nil then
        delete(circleOverlay)
        circleOverlay = nil
    end
end

--- colour given linear (isLinear) or sRGB, alpha multiplied by 'alpha'
local function apply(id, color, isLinear, alpha)
    local c = isLinear and color or ADHudStyle.linear(color)
    setOverlayColor(id, c[1], c[2], c[3], (c[4] or 1) * (alpha or 1))
end

function ADHudStyle.rect(x, y, w, h, color, isLinear, alpha)
    if w <= 0 or h <= 0 then
        return
    end
    local id = getPixel()
    apply(id, color, isLinear, alpha)
    renderOverlay(id, x, y, w, h)
end

local function circlePart(id, x, y, w, h, u0, v0, u1, v1)
    setOverlayUVs(id, u0, v0, u0, v1, u1, v0, u1, v1)
    renderOverlay(id, x, y, w, h)
end

--- rectangle with round corners, radius in screen height units
function ADHudStyle.roundRect(x, y, w, h, radius, color, isLinear, alpha)
    if w <= 0 or h <= 0 then
        return
    end
    local ry = math.min(radius, h / 2)
    local rx = math.min(ry / g_screenAspectRatio, w / 2)
    ry = rx * g_screenAspectRatio
    local id = getCircle()
    if rx <= 0 or not isReady(id) then
        return ADHudStyle.rect(x, y, w, h, color, isLinear, alpha)
    end
    apply(id, color, isLinear, alpha)
    circlePart(id, x, y, rx, ry, 0, 0, 0.5, 0.5)
    circlePart(id, x, y + h - ry, rx, ry, 0, 0.5, 0.5, 1)
    circlePart(id, x + w - rx, y, rx, ry, 0.5, 0, 1, 0.5)
    circlePart(id, x + w - rx, y + h - ry, rx, ry, 0.5, 0.5, 1, 1)
    if w > 2 * rx then
        ADHudStyle.rect(x + rx, y, w - 2 * rx, h, color, isLinear, alpha)
    end
    if h > 2 * ry then
        ADHudStyle.rect(x, y + ry, rx, h - 2 * ry, color, isLinear, alpha)
        ADHudStyle.rect(x + w - rx, y + ry, rx, h - 2 * ry, color, isLinear, alpha)
    end
end

--- a panel: soft shadow, the rounded dark body, the green line along the top (accent nil: none)
function ADHudStyle.panel(x, y, w, h, uiScale, body, bodyIsLinear, accent, accentIsLinear)
    local C = ADHudStyle.C
    local radius = ADHudStyle.px(ADHudStyle.PANEL_RADIUS, uiScale)
    local shadowY = ADHudStyle.px(ADHudStyle.SHADOW, uiScale)
    local shadowX = shadowY / g_screenAspectRatio
    ADHudStyle.roundRect(x - shadowX, y - shadowY * 1.5, w + 2 * shadowX, h + 2 * shadowY, radius + shadowY, C.shadow)
    ADHudStyle.roundRect(x, y, w, h, radius, body or C.bg, bodyIsLinear)
    if accent ~= nil then
        local barH = ADHudStyle.px(ADHudStyle.ACCENT_HEIGHT, uiScale)
        local inset = (radius * 1.2) / g_screenAspectRatio
        ADHudStyle.roundRect(x + inset, y + h - barH, w - 2 * inset, barH, barH / 2, accent, accentIsLinear)
    end
end

--- the chip behind a button: dark, lighter under the mouse, green tinted when on, faded when not usable
function ADHudStyle.chip(x, y, w, h, uiScale, hovered, active, disabled)
    local C = ADHudStyle.C
    local color = C.chip
    if hovered and not disabled then
        color = C.hover
    end
    local radius = ADHudStyle.px(ADHudStyle.CHIP_RADIUS, uiScale)
    ADHudStyle.roundRect(x, y, w, h, radius, color, false, disabled and 0.55 or 1)
    if active then
        ADHudStyle.roundRect(x, y, w, h, radius, hovered and C.accentHover or C.accent, false, 0.30)
    end
end

--- is the mouse (shown, for AutoDrive) over the box?
function ADHudStyle.isHovered(x, y, w, h)
    local mx, my = g_lastMousePosX, g_lastMousePosY
    if mx == nil or my == nil or g_inputBinding == nil or not g_inputBinding:getShowMouseCursor() then
        return false
    end
    return mx >= x and mx <= x + w and my >= y and my <= y + h
end

function ADHudStyle.setTextColor(color, isLinear)
    local c = isLinear and color or ADHudStyle.linear(color)
    setTextColor(c[1], c[2], c[3], c[4] or 1)
end

--- the overlay of a button image moved into its chip (a little smaller, centred)
function ADHudStyle.insetOverlay(ov, x, y, w, h)
    if ov == nil or ov.setPosition == nil or ov.setDimension == nil then
        return
    end
    local insetX, insetY = w * ADHudStyle.ICON_INSET, h * ADHudStyle.ICON_INSET
    ov:setPosition(x + insetX, y + insetY)
    ov:setDimension(w - 2 * insetX, h - 2 * insetY)
end
