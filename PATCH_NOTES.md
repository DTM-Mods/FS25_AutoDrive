# AutoDrive Overdrive: PropaineX edits, patch notes

Changes made on top of AutoDrive Overdrive (by chrisdfennell, based on AutoDrive by the AutoDrive Team).
Newest first. "Untested" means it has not been tried in the game yet.

## 3.1.0.4 (2026-11-05): unloader keeps out of the harvester's way
*Untested.*

- While an unloader waits on the field to be called, it checks every second whether it is standing where a harvester
  is going to drive. This counts combines and forage harvesters alike. It is in the way when it is:
  - in the strip in front of the harvester (80 m ahead, the header width plus 10 m on each side),
  - within 10 m of standing crop (where the next passes go), or
  - in the headland along the field edge where the harvester turns (20 m, or two header widths if that is more).
- If it is still in the way after 3 seconds, it drives to the nearest spot on harvested ground that is at least 15 m
  clear of all of that (it looks up to 80 m away, away from the harvester first). If there is no such spot, it goes
  15 m outside the field edge. Then it waits for a call again.
- While it moves it shows "Moving out of the harvester's way", and no harvester can call it until it has stopped.
- If it cannot get clear three times in a row, it waits 60 seconds before trying again.
- Not checked while it is driving to a combine, unloading or on its way to unload. A second unloader queued behind the
  one being filled is not checked either (the existing "Drive clear when blocked" setting still covers it).

## 3.0.2.4 (2026-11-05): longer run-up to the pipe
*Untested.*

- When the unloader drives up to a combine's pipe, the straight stretch it gets after its last turn is now 50% longer.
  The trailer has more time to line up behind the tractor instead of coming in at an angle.
  Example: a 12 m combine with an 18 m tractor and trailer: 19.8 m becomes 29.7 m. The shortest run-up goes from 7 m
  to 10.5 m.
- Forage harvesters with a fixed spout: 1.5 combine lengths instead of 1.
- Unchanged: forage harvesters that aim their spout themselves, and chasing straight behind a combine (neither has a
  run-up).
- On tight headlands the unloader may have to swing out a little further before it comes in.
