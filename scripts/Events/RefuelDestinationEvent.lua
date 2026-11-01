-- where a vehicle refuels (ADRefuelChoice): a client asks the server to change it, the server changes it and sends it
-- to all clients
AutoDriveRefuelDestinationEvent = {}
AutoDriveRefuelDestinationEvent_mt = Class(AutoDriveRefuelDestinationEvent, Event)

InitEventClass(AutoDriveRefuelDestinationEvent, "AutoDriveRefuelDestinationEvent")

function AutoDriveRefuelDestinationEvent.emptyNew()
    local self = Event.new(AutoDriveRefuelDestinationEvent_mt)
    return self
end

function AutoDriveRefuelDestinationEvent.new(vehicle, name)
    local self = AutoDriveRefuelDestinationEvent.emptyNew()
    self.vehicle = vehicle
    self.name = name or ""
    return self
end

function AutoDriveRefuelDestinationEvent:writeStream(streamId, connection)
    NetworkUtil.writeNodeObjectId(streamId, NetworkUtil.getObjectId(self.vehicle))
    streamWriteString(streamId, self.name)
end

function AutoDriveRefuelDestinationEvent:readStream(streamId, connection)
    self.vehicle = NetworkUtil.getObject(NetworkUtil.readNodeObjectId(streamId))
    self.name = streamReadString(streamId)
    self:run(connection)
end

function AutoDriveRefuelDestinationEvent:run(connection)
    if self.vehicle == nil or self.vehicle.ad == nil then
        return
    end
    ADRefuelChoice.set(self.vehicle, self.name)
    if g_server ~= nil then
        g_server:broadcastEvent(AutoDriveRefuelDestinationEvent.new(self.vehicle, self.name), false)
    end
end

function AutoDriveRefuelDestinationEvent.sendEvent(vehicle, name)
    local event = AutoDriveRefuelDestinationEvent.new(vehicle, name)
    if g_server ~= nil then
        event:run(nil)
    else
        g_client:getServerConnection():sendEvent(event)
    end
end
