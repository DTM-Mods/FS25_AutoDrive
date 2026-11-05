# AutoDrive Overdrive: PropaineX edits, patch notes

Changes made on top of AutoDrive Overdrive (by chrisdfennell, based on AutoDrive by the AutoDrive Team).
Newest first. "Untested" means it has not been tried in the game yet.

## 3.1.3.4 (2026-11-05): chase a standing combine the moment it moves
*Untested.*

- When the unloader is sent to a combine that is standing still and the combine starts to drive, the unloader now
  switches to chasing it after half a second, whatever it is doing: still planning its way there, driving up,
  waiting for the pipe, or already unloading. It used to notice only once it had stopped under the pipe, so if the
  combine pulled away while it was coming in, it first drove to the empty spot where the pipe had been.
- It only does this once it has seen the combine standing. A combine that is still moving but nearly full is also
  sent an unloader the "standing" way (it is about to stop); that one is not chased straight away.

## 3.1.2.4 (2026-11-05): unloader stays with the combine
*Untested.*

- Under the pipe the unloader now drives at exactly the combine's speed, no faster. "Under the pipe" means within
  1 m of its place. Further back it still catches up: the combine's speed plus 1 km/h, plus 3 km/h for every metre
  beyond that 1 m.
- When it has driven up to a combine that is standing still, and the combine drives off, the unloader now starts
  following it after half a second. It used to stand still for 4 seconds first, so the combine was already several
  metres away.
- In that moment it now always follows. It used to give up and go back to waiting if its tractor or trailer was near
  standing crop.
- If a combine set to Active unloading is emptied while standing still, and the unloader still has room, it now
  stays with the combine and follows it, so it is already under the pipe when the combine fills again. It used to
  leave and wait for the next call. A full unloader still drives off to unload as before, and nothing changes for
  forage harvesters or for combines with Active unloading off.

## 3.1.1.4 (2026-11-05): unloader stays under the pipe
*Untested.*

- When the unloader chases a combine that unloads on the move, it now pushes harder to get back under the pipe.
  It aims for the combine's speed plus 1 km/h, plus 3 km/h for every metre it is short of its place (it used to be
  only 1.4 to 2 km/h per metre, so it crept up slowly and the combine kept getting away from it).
  For example, 3 m short: combine + 10 km/h (was combine + 4 km/h).
- If it gets ahead of its place, it now drops below the combine's speed and slides back, instead of overshooting.
- Your Field speed setting is still its top speed.
- Only the pipe chase works this way. Bale unloading, reversing out of a bad spot and driving clear to the field edge
  are unchanged.

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
