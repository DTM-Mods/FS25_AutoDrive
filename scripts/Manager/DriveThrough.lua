-- Drive through obstructions: a vehicle setting for the No AI Collisions mod (FS25_NoAICollisions_ProEdition, by
-- PropaineX). That mod lets a helper that has been stopped by an obstruction for 2 s switch collisions off and drive
-- through it. AutoDrive only offers the choice per vehicle and publishes it on the vehicle; the mod does the driving.
--
-- Contract with No AI Collisions (plain field, so neither mod has to find the other's classes):
--   vehicle.ad.allowDriveThrough  true  = the mod may drive this vehicle through obstructions (default, as before)
--                                 false = it must not; the vehicle waits as AutoDrive normally does
-- Read it on the root vehicle. nil (an AutoDrive version without this setting) means true.
-- The row (Overdrive tab of the settings, ADOverdriveSettings) only shows when No AI Collisions is loaded.
ADDriveThrough = {}

ADDriveThrough.SETTING = "allowDriveThrough"

-- No AI Collisions loaded? Any mod whose name contains "NoAICollisions" (Pro Edition or not).
function ADDriveThrough.isNoAICollisionsLoaded()
    if ADDriveThrough.modLoaded ~= nil then
        return ADDriveThrough.modLoaded
    end
    local loaded = false
    if type(g_modIsLoaded) == "table" then
        for modName, isLoaded in pairs(g_modIsLoaded) do
            if isLoaded and type(modName) == "string" and string.find(modName, "NoAICollisions", 1, true) ~= nil then
                loaded = true
                break
            end
        end
    end
    ADDriveThrough.modLoaded = loaded
    return loaded
end

-- Called every update of an AutoDrive vehicle: keeps the published field in step with the setting
function ADDriveThrough.update(vehicle)
    if vehicle == nil or vehicle.ad == nil then
        return
    end
    vehicle.ad.allowDriveThrough = AutoDrive.getSetting(ADDriveThrough.SETTING, vehicle) ~= false
end
