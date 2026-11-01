-- "Refuel at" row (ADRefuelChoice) on the Overdrive tab and next to Auto Refuel on the vehicle tab: Nearest and the
-- refuel targets for the controlled vehicle's fuels. It is not one of AutoDrive's settings (those are a fixed list of
-- values, this one is a target name), so the row keeps its own choice until OK sends it; both rows show the same one.
ADRefuelChoiceRow = {}
ADRefuelChoiceRow.pending = nil     -- the choice made in the open settings window, nil = none

function ADSettingsPage:onCreateRefuelDestination(element)
    self.refuelDestinationElement = element
end

function ADSettingsPage:onRefuelDestinationChange(state, element)
    local names = self.refuelDestinationNames or {}
    ADRefuelChoiceRow.pending = names[state - 1] or ADRefuelChoice.NEAREST
end

function ADRefuelChoiceRow.getVehicle()
    local vehicle = AutoDrive.getControlledVehicle()
    if vehicle ~= nil and vehicle.ad ~= nil then
        return vehicle
    end
    return nil
end

function ADRefuelChoiceRow.hasChange()
    local vehicle = ADRefuelChoiceRow.getVehicle()
    return vehicle ~= nil and ADRefuelChoiceRow.pending ~= nil and ADRefuelChoiceRow.pending ~= ADRefuelChoice.get(vehicle)
end

-- fills the row: hidden without a vehicle, else Nearest + the targets, the current (or pending) choice selected
function ADRefuelChoiceRow.refresh(page)
    local element = page.refuelDestinationElement
    if element == nil then
        return
    end
    local vehicle = ADRefuelChoiceRow.getVehicle()
    if element.parent ~= nil and element.parent.setVisible ~= nil then
        element.parent:setVisible(vehicle ~= nil)
    end
    if page.allSettingElements ~= nil and ADOverdriveSettings ~= nil then
        ADOverdriveSettings.restripe(page)
    end
    if vehicle == nil then
        return
    end
    local current = ADRefuelChoiceRow.pending or ADRefuelChoice.get(vehicle)
    local names = ADRefuelChoice.getChoices(vehicle)
    if current ~= ADRefuelChoice.NEAREST and not table.contains(names, current) then
        -- chosen before, not usable now: still shown, so it is not changed by just opening the window
        table.insert(names, current)
    end
    page.refuelDestinationNames = names
    local labels = {g_i18n:getText("gui_ad_refuelNearest")}
    local state = 1
    for i, name in ipairs(names) do
        labels[i + 1] = name
        if name == current then
            state = i + 1
        end
    end
    element:setTexts(labels)
    element:setState(state, false)
end

function ADRefuelChoiceRow.apply()
    local vehicle = ADRefuelChoiceRow.getVehicle()
    if ADRefuelChoiceRow.hasChange() then
        AutoDriveRefuelDestinationEvent.sendEvent(vehicle, ADRefuelChoiceRow.pending)
    end
    ADRefuelChoiceRow.pending = nil
end

ADSettingsPage.onFrameOpen = Utils.appendedFunction(ADSettingsPage.onFrameOpen, function(page)
    ADRefuelChoiceRow.refresh(page)
end)

-- the window asks before throwing a change away
ADSettingsPage.hasChanges = Utils.overwrittenFunction(ADSettingsPage.hasChanges, function(page, superFunc)
    return superFunc(page) or (page.refuelDestinationElement ~= nil and ADRefuelChoiceRow.hasChange())
end)

ADSettings.onClickOK = Utils.prependedFunction(ADSettings.onClickOK, function()
    ADRefuelChoiceRow.apply()
end)

ADSettings.onClose = Utils.appendedFunction(ADSettings.onClose, function()
    ADRefuelChoiceRow.pending = nil
end)

-- Reset on the page and Restore (defaults) put the row back to the vehicle's choice / Nearest
ADSettings.resetPage = Utils.appendedFunction(ADSettings.resetPage, function(_, page)
    if page ~= nil and page.refuelDestinationElement ~= nil then
        ADRefuelChoiceRow.pending = nil
        ADRefuelChoiceRow.refresh(page)
    end
end)

ADSettings.onClickRestore = Utils.appendedFunction(ADSettings.onClickRestore, function(settings)
    local page = settings.currentPage
    if page ~= nil and page.refuelDestinationElement ~= nil and ADRefuelChoiceRow.getVehicle() ~= nil then
        ADRefuelChoiceRow.pending = ADRefuelChoice.NEAREST
        ADRefuelChoiceRow.refresh(page)
    end
end)
