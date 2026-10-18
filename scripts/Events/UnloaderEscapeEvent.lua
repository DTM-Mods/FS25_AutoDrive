-- Drive clear when blocked (ADUnloaderEscape): collision masks are local engine state, the server tells the
-- clients when an unloader's collisions with other vehicles go off and on again
AutoDriveUnloaderEscapeEvent = {}
AutoDriveUnloaderEscapeEvent_mt = Class(AutoDriveUnloaderEscapeEvent, Event)

InitEventClass(AutoDriveUnloaderEscapeEvent, "AutoDriveUnloaderEscapeEvent")

function AutoDriveUnloaderEscapeEvent.emptyNew()
    local self = Event.new(AutoDriveUnloaderEscapeEvent_mt)
    return self
end

function AutoDriveUnloaderEscapeEvent.new(vehicle, ghost)
    local self = AutoDriveUnloaderEscapeEvent.emptyNew()
    self.vehicle = vehicle
    self.ghost = ghost
    return self
end

function AutoDriveUnloaderEscapeEvent:writeStream(streamId, connection)
    NetworkUtil.writeNodeObjectId(streamId, NetworkUtil.getObjectId(self.vehicle))
    streamWriteBool(streamId, self.ghost)
end

function AutoDriveUnloaderEscapeEvent:readStream(streamId, connection)
    self.vehicle = NetworkUtil.getObject(NetworkUtil.readNodeObjectId(streamId))
    self.ghost = streamReadBool(streamId)
    self:run(connection)
end

function AutoDriveUnloaderEscapeEvent:run(connection)
    if g_server == nil and self.vehicle ~= nil then
        ADUnloaderEscape.applyGhost(self.vehicle, self.ghost)
    end
end
