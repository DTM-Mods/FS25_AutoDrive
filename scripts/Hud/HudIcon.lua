ADHudIcon = ADInheritsFrom(ADGenericHudElement)

ADHudIcon.TITLE = "AutoDrive Overdrive"
ADHudIcon.SEPARATOR = " · "
-- Overdrive: the title bar (screen height units, times the UI scale)
ADHudIcon.TITLE_SIZE = 0.0165
ADHudIcon.DETAIL_SIZE = 0.0115
ADHudIcon.HEADER_PAD_Y = 0.009
ADHudIcon.HEADER_PAD_X = 12      -- 1080p pixels
ADHudIcon.TITLE_GAP = 0.004      -- between the title and the details

function ADHudIcon.getHeaderPadX(uiScale)
    return ADHudStyle.px(ADHudIcon.HEADER_PAD_X, uiScale) / g_screenAspectRatio
end

--- the middle of the title line, for the header's top edge at 'top'
function ADHudIcon.getTitleCenterY(top, uiScale)
    return top - ADHudIcon.HEADER_PAD_Y * uiScale - ADHudIcon.TITLE_SIZE * uiScale / 2
end

function ADHudIcon:new(posX, posY, width, height, image, layer, name)
    local o = ADHudIcon:create()
    o:init(posX, posY, width, height)
    o.layer = layer
    o.name = name
    o.image = image
    o.isVisible = true
    o.lastLineCount = 1
    o.ov = Overlay.new(g_baseUIFilename, o.position.x, o.position.y, width, height)
    o.ov:setUVs(g_colorBgUVs)
    return o
end

function ADHudIcon:onDraw(vehicle, uiScale)
    self:updateVisibility(vehicle)

    self:updateIcon(vehicle)

    if self.name == "header" then
        -- Overdrive: no bar of its own, the title and the details on the panel
        self:onDrawHeader(vehicle, uiScale)
        return
    end
    if self.name == "background" then
        if self.isVisible then
            self:onDrawPanel(uiScale)
        end
        return
    end

    if self.isVisible and self.ov ~= nil then
        self.ov:render()
    end
end

-- Overdrive: the HUD's panel (ADHudStyle): rounded, with a shadow and the header colour as the line along the top;
-- it grows upwards with the header text's extra lines
function ADHudIcon:onDrawPanel(uiScale)
    local header = AutoDrive.Hud ~= nil and AutoDrive.Hud.headerElement or nil
    local extra = header ~= nil and header.extraHeight or 0
    ADHudStyle.panel(self.position.x, self.position.y, self.size.width, self.size.height + extra, uiScale,
        AutoDrive.currentColors.ad_color_background, true, AutoDrive.currentColors.ad_color_header, true)
end

-- Overdrive: a title bar like CourseCorrect's: "AutoDrive Overdrive" large and bold at the top, below it the details
-- (version, mode, time, tooltip, task) in grey, wrapped over more lines when long: the bar then grows upwards and the
-- header buttons move up with the title. The editor tips (extended header) below them.
function ADHudIcon:onDrawHeader(vehicle, uiScale)
    local hud = AutoDrive.Hud
    local detailSize = ADHudIcon.DETAIL_SIZE * uiScale
    local detailHeight = getTextHeight(detailSize, "text")
    local posX = self.position.x + ADHudIcon.getHeaderPadX(uiScale)

    setTextAlignment(RenderText.ALIGN_LEFT)
    self:renderDefaultText(vehicle, detailSize, posX, uiScale)
    if hud.isShowingTips and AutoDrive.pullDownListExpanded == 0 then
        setTextColor(unpack(AutoDrive.currentColors.ad_color_hudTextDefault))
        self:renderEditorTips(detailHeight, detailSize, posX, self.position.y + hud.gapHeight)
    end
    setTextBold(false)
end

function ADHudIcon:renderDefaultText(vehicle, fontSize, posX, uiScale)
    local hud = AutoDrive.Hud
    local textHeight = getTextHeight(fontSize, "text")
    local textToShow = AutoDrive.version
    textToShow = textToShow .. " - " .. AutoDriveHud:getModeName(vehicle)
    textToShow = self:addVehicleDriveTimeString(vehicle, textToShow)
    textToShow = self:addTooltipString(vehicle, textToShow)    

    local taskInfo = vehicle.ad.stateModule:getCurrentLocalizedTaskInfo()
    if taskInfo ~= "" then
        textToShow = textToShow .. " - " .. taskInfo
    end

    if AutoDrive.isEditorModeEnabled() and AutoDrive.getDebugChannelIsSet(AutoDrive.DC_PATHINFO) then
        if vehicle.ad.pathFinderModule.steps > 0 then
            textToShow = textToShow .. " - " .. "Fallback: " .. tostring(vehicle.ad.pathFinderModule.fallBackMode)
        end
    end

    -- the details have the whole width below the title (the header buttons are on the title line)
    -- measuring the text is the expensive part and it rarely changes, so it is wrapped again only when it changed
    local maxWidth = self.size.width - 2 * (posX - self.position.x)
    if textToShow ~= self.wrappedText or fontSize ~= self.wrappedFontSize or maxWidth ~= self.wrappedMaxWidth then
        self.wrappedLines = self:splitTextByLength(textToShow, fontSize, maxWidth)
        self.wrappedText, self.wrappedFontSize, self.wrappedMaxWidth = textToShow, fontSize, maxWidth
    end
    local lines = self.wrappedLines

    -- a long header text wraps, the header grows upwards by the extra lines, the header buttons move up with the title
    self.extraHeight = (textHeight + hud.gapHeight) * (#lines - 1)
    if #lines ~= self.lastLineCount and self.ov ~= nil then
        self.ov:setDimension(nil, self.size.height + self.extraHeight)
    end
    for _, button in ipairs(hud.headerButtons or {}) do
        button:setY(button.headerBaseY + self.extraHeight)
    end
    self.lastLineCount = #lines
    if AutoDrive.pullDownListExpanded ~= 0 then
        return
    end

    local fullTitleSize = ADHudIcon.TITLE_SIZE * uiScale
    local top = self.position.y + self.size.height + self.extraHeight
    local titleY = ADHudIcon.getTitleCenterY(top, uiScale) - fullTitleSize / 2
    setTextBold(true)
    local title, titleSize = self:fitTitle(fullTitleSize, self:getTitleRoom(posX, uiScale))
    setTextColor(unpack(AutoDrive.currentColors.ad_color_hudTextDefault))
    renderText(posX, titleY + (fullTitleSize - titleSize) / 2, titleSize, title)

    setTextBold(false)
    ADHudStyle.setTextColor(ADHudStyle.C.muted)
    local posY = titleY - ADHudIcon.TITLE_GAP * uiScale - textHeight
    for _, lineText in ipairs(lines) do
        renderText(posX, posY, fontSize, (string.gsub(lineText, " %- ", ADHudIcon.SEPARATOR)))
        posY = posY - textHeight - hud.gapHeight
    end
    setTextColor(unpack(AutoDrive.currentColors.ad_color_hudTextDefault))
end

-- Overdrive: the room for the title, from its left edge to the leftmost header button shown (undo / redo in the
-- editor) less a gap; the title is drawn above the buttons, so it must not reach them
function ADHudIcon:getTitleRoom(posX, uiScale)
    local right = self.position.x + self.size.width
    for _, button in ipairs(AutoDrive.Hud.headerButtons or {}) do
        if button.isVisible and button.position.x < right then
            right = button.position.x
        end
    end
    return right - ADHudIcon.getHeaderPadX(uiScale) / 2 - posX
end

ADHudIcon.SHORT_TITLE = "AutoDrive"
ADHudIcon.MIN_TITLE_SCALE = 0.8

--- the title and its size that fit into 'room': the full title, smaller down to MIN_TITLE_SCALE, else the short
--- title (smaller when even that does not fit); measured only when the room or the size changed
function ADHudIcon:fitTitle(size, room)
    if size ~= self.fittedSize or room ~= self.fittedRoom then
        self.fittedSize, self.fittedRoom = size, room
        self.fittedTitle, self.fittedTitleSize = ADHudIcon.TITLE, size
        local width = getTextWidth(size, ADHudIcon.TITLE)
        if width > room then
            local scale = room / width
            if scale >= ADHudIcon.MIN_TITLE_SCALE then
                self.fittedTitleSize = size * scale
            else
                self.fittedTitle = ADHudIcon.SHORT_TITLE
                width = getTextWidth(size, ADHudIcon.SHORT_TITLE)
                if width > room and room > 0 then
                    self.fittedTitleSize = size * room / width
                end
            end
        end
    end
    return self.fittedTitle, self.fittedTitleSize
end

function ADHudIcon:renderEditorTips(textHeight, fontSize, posX, posY)
    local editorTips = {}
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_11"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_10"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_9"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_8"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_7"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_6"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_5"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_4"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_3"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_2"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_1"))
    table.insert(editorTips, g_i18n:getText("gui_ad_editorTip_12"))

    for tipId, tip in pairs(editorTips) do
        if AutoDrive.pullDownListExpanded == 0 then
            renderText(posX, posY, fontSize, tip)
            posY = posY + textHeight + AutoDrive.Hud.gapHeight
            if tipId == 3 or tipId == 6 or tipId == 11 then
                posY = posY + textHeight + AutoDrive.Hud.gapHeight
            end
        end
    end
end

function ADHudIcon:addVehicleDriveTimeString(vehicle, currentText)
    local remainingTime = vehicle.ad.stateModule:getRemainingDriveTime()
    if remainingTime ~= 0 then
        local remainingMinutes = math.floor(remainingTime / 60)
        local remainingSeconds = remainingTime % 60
        if remainingMinutes > 0 then
            currentText = currentText .. " - " .. string.format("%.0f", remainingMinutes) .. ":" .. string.format("%02d", math.floor(remainingSeconds))
        elseif remainingSeconds ~= 0 then
            currentText = currentText .. " - " .. string.format("%2.0f", remainingSeconds) .. "s"
        end
    end
    return currentText
end

function ADHudIcon:addTooltipString(vehicle, currentText)
    if vehicle.ad.sToolTip ~= "" and AutoDrive.getSetting("showTooltips") then
        if vehicle.ad.toolTipIsSetting then
            currentText = currentText .. " - " .. g_i18n:getText(vehicle.ad.sToolTip)
        else
            currentText = currentText .. " - " .. string.sub(g_i18n:getText(vehicle.ad.sToolTip), 5, string.len(g_i18n:getText(vehicle.ad.sToolTip)))
        end

        if vehicle.ad.sToolTipInfo ~= nil then
            currentText = currentText .. " - " .. vehicle.ad.sToolTipInfo
        end
    end
    return currentText
end

function ADHudIcon:splitTextByLength(text, fontSize, maxLength)
    local lines = {}
    local textParts = string.split(text, "-")
    local line = textParts[1]
    local index = 2
    while index <= #textParts do
        if getTextWidth(fontSize, line .. "-" .. textParts[index]) > maxLength then
            table.insert(lines, line)
            line = textParts[index]:sub(2)
        else
            line = line .. "-" .. textParts[index]
        end
        index = index + 1
    end
    table.insert(lines, line)
    return lines
end

function ADHudIcon:updateVisibility(vehicle)
    local newVisibility = self.isVisible
    if self.name == "unloadOverlay" then
        if (vehicle.ad.stateModule:getMode() == AutoDrive.MODE_PICKUPANDDELIVER or vehicle.ad.stateModule:getMode() == AutoDrive.MODE_UNLOAD or vehicle.ad.stateModule:getMode() == AutoDrive.MODE_LOAD) then
            newVisibility = true
        else
            newVisibility = false
        end
    end

    if self.name == "fruitOverlay" then
        if (vehicle.ad.stateModule:getMode() == AutoDrive.MODE_PICKUPANDDELIVER or vehicle.ad.stateModule:getMode() == AutoDrive.MODE_LOAD) then
            newVisibility = true
        else
            newVisibility = false
        end
    end

    self.isVisible = newVisibility
end

-- the header can be grabbed on all its lines, not only on the first one
function ADHudIcon:hit(posX, posY, layer)
    local height = self.size.height
    if self.name == "header" and self.extraHeight ~= nil then
        height = height + self.extraHeight
    end
    return layer <= self.layer and posX >= self.position.x and posX <= (self.position.x + self.size.width) and posY >= self.position.y and posY <= (self.position.y + height)
end

function ADHudIcon:act(vehicle, posX, posY, isDown, isUp, button)
    if self.name == "header" then
        if button == 1 and isDown and AutoDrive.pullDownListExpanded == 0 then
            if (not g_inGameMenu.isOpen or AutoDrive.aiFrameOpen) then
                AutoDrive.Hud:startMovingHud(posX, posY)
                return true
            end
        end
    end
    return false
end

function ADHudIcon:updateIcon(vehicle)
    local newIcon = self.image
    if self.name == "unloadOverlay" then
        if vehicle.ad.stateModule:getMode() == AutoDrive.MODE_LOAD then
            newIcon = "ad_gui.tipper_load"
        elseif vehicle.ad.stateModule:getMode() == AutoDrive.MODE_PICKUPANDDELIVER then
            newIcon = "ad_gui.tipper_overlay"
        elseif vehicle.ad.stateModule:getMode() == AutoDrive.MODE_UNLOAD then
            newIcon = "ad_gui.tipper_overlay"
        end
    elseif self.name == "destinationOverlay" then
        if vehicle.ad.stateModule:getMode() == AutoDrive.MODE_PICKUPANDDELIVER then
            newIcon = "ad_gui.tipper_load"
        elseif vehicle.ad.stateModule:getMode() == AutoDrive.MODE_DELIVERTO then
            newIcon = "ad_gui.tipper_overlay"
        elseif vehicle.ad.stateModule:getMode() ~= AutoDrive.MODE_BGA then
            newIcon = "ad_gui.destination"
        end
    end

    self.image = newIcon
    if self.ov ~= nil then
        -- self.ov:setSliceId(self.image)
    end
end
