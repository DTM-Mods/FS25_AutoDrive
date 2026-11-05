# AutoDrive Overdrive: PropaineX edits, patch notes

Changes made on top of AutoDrive Overdrive (by chrisdfennell, based on AutoDrive by the AutoDrive Team).
Newest first. "Untested" means it has not been tried in the game yet.

## 3.5.0.4 (2026-11-05): unloaders drive like semis when chasing
*Untested.*

Semi trucks chasing a harvester's pipe used to aim the cab straight at the spot under the pipe and steer as hard as
needed. With the spot right beside the cab or just behind it (inside the truck's turning circle) they drove in circles
or folded the trailer up (jackknifed) and got stuck. Now, while chasing with a trailer attached:
- It never steers tighter than a semi can turn (12 m radius). A spot it can't reach is no longer chased at full
  lock: it stays nearly straight, lets the harvester come by, and lines up from behind.
- Jackknife guard: if the cab gets more than 45 degrees off the trailer, it straightens the wheels and drives on at
  8 km/h or less until the trailer is back within 15 degrees.
- Driving on roads and AutoDrive routes, and rigs without a trailer: unchanged.

## 3.4.1.4 (2026-11-05): "in the harvester's way" made tighter and smarter
*Untested.*

A waiting unloader now only counts as in a harvester's way when it's:
- in the strip in front of the harvester: **50 m** ahead (was 80 m), the header width plus **5 m** on each side (was
  10 m), or
- in the headland **where the harvester is going to turn**: at the end of the field it's heading to, from its own lane
  toward the side with standing crop (it turns into the next pass). With crop on neither side, or both, both
  directions count.

No longer in the way:
- parked next to standing crop (the "within 10 m of crop" rule is gone),
- parked in the headland on the side the harvester turns away from.

When it does move, its new spot no longer has to keep away from crop or from the whole headland, only from the strip
(by 15 m) and from where the harvester turns.

## 3.4.0.4 (2026-11-05): unloader stays on when its harvester leaves
*Untested.*

- When a harvester stops working (it drives off to refuel or get repaired, its helper is switched off, or you fold
  the pipe), its unloader no longer stops where it is with AutoDrive switched off. Instead:
  - trailer 50% full or more: it drives off to unload, as with a full trailer (leaving the field first);
  - under 50%: it stays on, waits for the next call, and keeps out of the harvester's way as usual. When the
    harvester comes back and starts working, an unloader is sent again.
- A second unloader queued behind it does the same, based on its own trailer.
- With Active unloading on, an unloader is now only sent while the harvester is on a field. A Courseplay harvester
  driving on the road to or from a field doesn't get chased down the road.

## 3.3.0.4 (2026-11-05): Active unloading: chase from the start
*Untested.*

- With Active unloading on, a combine no longer waits until it reaches the "Call unloader at" (pre-call) level before
  it gets an unloader. As soon as it is working, the closest free unloader is sent to chase it, even at 0% full.
- It also keeps calling one when it is over 90% full, so a nearly full combine is chased too.
- Nothing holds it back because the pipe would be over standing crop any more (AI crop damage is off on our server).
  Before, an unloader that would chase from behind wasn't sent above 70% full, and one already coming in from behind
  waited above 85%.
- Active unloading off: unchanged, it still waits for the pre-call level.

## 3.2.1.4 (2026-11-05): no backing away from a nearly full combine (Active unloading)
*Untested.*

- 3.2.0.4 only stopped the "combine over 90% full and I'm within 25 m, back away" rule for an unloader called to a
  standing combine. A combine still driving and over 90% full still made it back away. With Active unloading on, that
  rule is now off completely.
- With Active unloading on, an unloader chasing a combine no longer gives up and goes back to waiting when the combine
  gets past 91% full. It keeps chasing, so it's under the pipe when the combine stops.
- With Active unloading on, a combine that is still driving but over 94.5% full now gets an unloader that chases it.
  Before, the unloader drove to the spot where the pipe was, as if the combine were standing.
- When a combine with Active unloading on stops and the unloader is at the pipe (within 3 m), the unloader holds still
  there, ready, and moves the moment the combine does.
- Active unloading off: unchanged.

## 3.2.0.4 (2026-11-05): Active unloading means always chasing
*Untested.*

- With Active unloading on, an unloader that reaches a standing combine no longer does a "standing unload". It goes
  straight into chase mode and holds still under the pipe while the combine stands. The moment the combine rolls, it
  rolls with it. There is no switch-over any more, so it can't miss the combine driving off (in 3.1.3.4 it sat there,
  gave up once the combine was 30 m away, looped round and came back).
- While it waits under a standing combine like this, it doesn't count as stuck, and it no longer backs away because
  the combine is over 90% full and close by.
- If the combine starts driving while the unloader is still on its way, it still switches to chasing after half a
  second (as in 3.1.3.4).
- Active unloading off, forage harvesters, a combine that is turning, and a Courseplay combine in a pocket: unchanged,
  standing unload as before.

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
