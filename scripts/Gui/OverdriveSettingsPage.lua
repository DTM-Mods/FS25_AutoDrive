-- Overdrive tab in the AutoDrive settings: every setting Overdrive adds, in one place instead of mixed in with the
-- upstream ones. The page is a normal ADSettingsPage (gui/overdriveSettingsPage.xml), in two sections:
--   "This vehicle" - vehicle settings, only while the player is in a vehicle (they are saved on that vehicle; without
--                    one the rows are hidden, so nothing can be written as the template for every vehicle)
--   "You"          - user settings, always
-- Apply, reset, restore and "make default" of the settings window work on page.settingElements, so on every open
-- that table holds only the rows that are shown; all of them stay in page.allSettingElements.
ADOverdriveSettings = {}

-- turns a freshly created ADSettingsPage into the Overdrive tab
function ADOverdriveSettings.attach(page)
    page.onFrameOpen = ADOverdriveSettings.onFrameOpen
    return page
end

function ADOverdriveSettings.onFrameOpen(page)
    ADOverdriveSettings.refresh(page)
    ADSettingsPage.onFrameOpen(page)
end

-- is a setting's row shown right now
function ADOverdriveSettings.isShown(settingName, hasVehicle)
    local setting = AutoDrive.settings[settingName]
    if setting == nil then
        return false
    end
    if setting.isVehicleSpecific and not hasVehicle then
        return false
    end
    if ADDriveThrough ~= nil and settingName == ADDriveThrough.SETTING and not ADDriveThrough.isNoAICollisionsLoaded() then
        return false
    end
    return true
end

function ADOverdriveSettings.refresh(page)
    if page.allSettingElements == nil then
        page.allSettingElements = page.settingElements
    end
    local vehicle = AutoDrive.getControlledVehicle()
    local hasVehicle = vehicle ~= nil and vehicle.ad ~= nil

    local shown = {}
    for settingName, element in pairs(page.allSettingElements) do
        local visible = ADOverdriveSettings.isShown(settingName, hasVehicle)
        if element.parent ~= nil and element.parent.setVisible ~= nil then
            element.parent:setVisible(visible)
        end
        if visible then
            shown[settingName] = element
        end
    end
    page.settingElements = shown

    if page.odVehicleHeader ~= nil and page.odVehicleHeader.setText ~= nil then
        local title = g_i18n:getText("gui_ad_od_thisVehicle")
        if hasVehicle and vehicle.ad.stateModule ~= nil then
            title = title .. ": " .. tostring(vehicle.ad.stateModule:getName())
        end
        page.odVehicleHeader:setText(title)
    end
    if page.odNoVehicleText ~= nil and page.odNoVehicleText.setVisible ~= nil then
        page.odNoVehicleText:setVisible(not hasVehicle)
    end

    ADOverdriveSettings.restripe(page)
end

-- alternating row colours, starting again after every section header
function ADOverdriveSettings.restripe(page)
    local layout = page.boxLayout
    if layout == nil or layout.elements == nil then
        return
    end
    local colors = InGameMenuSettingsFrame ~= nil and InGameMenuSettingsFrame.COLOR_ALTERNATING or nil
    local isEvenRow = false
    for _, child in ipairs(layout.elements) do
        local visible = child.getIsVisible == nil or child:getIsVisible()
        if child.odSectionHeader then
            isEvenRow = false
        elseif visible and child.setImageColor ~= nil and colors ~= nil then
            child:setImageColor(nil, table.unpack(colors[isEvenRow]))
            isEvenRow = not isEvenRow
        end
    end
    if layout.invalidateLayout ~= nil then
        layout:invalidateLayout()
    end
end

-- onCreate of the section headers in the XML: marks them, so the stripes start again below them
function ADSettingsPage:onCreateOverdriveSectionHeader(element)
    element.odSectionHeader = true
end
