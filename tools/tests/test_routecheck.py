"""Route check: every kind of problem is found in a small network, nothing in a clean one, waypoints on top of each
other are no problem, and the check is fast enough for a big map."""
import os
import time
import run_undo_test as t

s = t.make_runtime(True)
s.execute(t.read(os.path.join(t.MOD, "scripts", "Manager", "RouteCheck.lua")))
s.execute("""
    function wp(id, x, z, out) return {id = id, x = x, y = 0, z = z, out = out, incoming = {}, flags = 0} end
    function kinds(problems)
        local r = {}
        for _, p in ipairs(problems) do r[#r + 1] = p.kind .. "@" .. p.wayPointId end
        table.sort(r)
        return table.concat(r, " ")
    end
""")

# a two-way ring 1..4 with targets, plus every kind of problem
s.execute("""
    W = {
        wp(1, 0, 0, {2, 4}), wp(2, 10, 0, {1, 3, 5}), wp(3, 10, 10, {2, 4, 9}), wp(4, 0, 10, {3, 1, 12}),
        wp(5, 20, 0, {6}),                -- one-way spur from 2 ...
        wp(6, 30, 0, {}),                 -- ... ending in a dead end
        wp(7, 50, 50, {}),                -- loose waypoint
        wp(8, 10.1, 10.1, {3}),           -- on top of 3 (0.14 m), only leads into the ring: not reported
        wp(9, 40, 10, {10}),              -- trap: 9 -> 10 -> 11 -> 10 ... no way out
        wp(10, 50, 10, {11}), wp(11, 60, 10, {10}),
        wp(12, -10, 10, {}),              -- target at a dead end: no way back
        wp(13, -50, -50, {14}), wp(14, -60, -50, {13}), -- separate loop with a target: unreachable
    }
    M = {
        {id = 1, name = "Farm"}, {id = 3, name = "Silo"}, {id = 12, name = "Shed"}, {id = 13, name = "Island"},
        {id = 6, name = "debug", isADDebug = true},
    }
    -- forward connections, as in a real network: every waypoint lists where it is reached from
    for id, w in ipairs(W) do for _, o in ipairs(w.out) do table.insert(W[o].incoming, id) end end
""")
problems = s.eval("ADRouteCheck.analyse(W, M)")
got = s.globals().kinds(problems)
# kinds: LOOSE=1 DEAD_END=2 TRAP=3 UNREACHABLE=4 NO_WAY_BACK=5, the trap is entered at 10
expected = sorted(["1@7", "2@6", "3@10", "5@12", "4@13"])
assert got == " ".join(expected), got

by_kind = {p.kind: p for p in problems.values()}
assert by_kind[3].count == 2, by_kind[3].count
assert by_kind[4].name == "Island" and by_kind[4].noWayBack
assert by_kind[5].name == "Shed"

# backup points: a short stub off a waypoint where vehicles back up is no dead end; the end of a reverse leg neither;
# a long dead-end road still is
s.execute("""
    function road(id, x, z, out, incoming) return {id = id, x = x, y = 0, z = z, out = out, incoming = incoming, flags = 0} end
    B = {
        [1] = road(1, 0, 0, {2}, {2}), [2] = road(2, 10, 0, {1, 3}, {1}),   -- 1 = 2 two-way, 2 -> 3
        [3] = road(3, 20, 0, {4, 6}, {2}),                                -- junction: on to 4 (stub), and 6
        [4] = road(4, 21, 0, {}, {3}),                                    -- 1 m stub: the backup point
        [5] = road(5, 0, 50, {}, {}),                                     -- loose
        [6] = road(6, 20, 8, {7}, {3}),
        [7] = road(7, 20, 16, {2}, {6}),                                  -- 6 -> 7 forward, 7 -> 2 reversing (2 does not list 7)
        [8] = road(8, 30, 0, {}, {}),                                     -- reached by reversing from 2 ...
    }
    table.insert(B[2].out, 8)                                        -- ... 2 -> 8 reverse
    for id = 9, 15 do B[id] = road(id, 100 + id * 10, 0, id < 15 and {id + 1} or {}, {id - 1}) end
    table.insert(B[1].out, 9); B[9].incoming = {1}                   -- 1 -> 9 ... 15: a 70 m road that just ends
    BM = {{id = 1, name = "Farm"}}
""")
got = s.globals().kinds(s.eval("ADRouteCheck.analyse(B, BM)"))
assert "2@4" not in got and "2@8" not in got, got
assert "2@15" in got and "1@5" in got, got

# field entries: a target at the end of a one-way spur has no way back; near a field that is how it is meant to be
s.execute("""
    F = {
        road(1, 0, 0, {2}, {2}), road(2, 10, 0, {1, 3}, {1}),
        road(3, 20, 0, {4}, {2, 4}), road(4, 30, 0, {3}, {3}),      -- 2 -> 3 <-> 4, target on 4
    }
    FM = {{id = 1, name = "Farm"}, {id = 2, name = "Shop"}, {id = 4, name = "Field 7"}}
""")
assert s.globals().kinds(s.eval("ADRouteCheck.analyse(F, FM)")) == "3@3 5@4"
assert s.globals().kinds(s.eval("ADRouteCheck.analyse(F, FM, function() return false end)")) == "3@3 5@4"
assert s.globals().kinds(s.eval("ADRouteCheck.analyse(F, FM, function(x, y, z) return x == 30 end)")) == ""
# one that can not be reached at all is still reported, also near a field
s.execute("F[2].out = {1}; F[3].incoming = {4}")
assert "4@4" in s.globals().kinds(s.eval("ADRouteCheck.analyse(F, FM, function() return true end)"))

# texts
s.globals().P = problems
texts = [s.eval("ADRouteCheck.getProblemText(P[%d])" % i) for i in range(1, len(problems) + 1)]
assert all("%" not in x for x in texts), texts

# sorting and limit
s.execute("ADRouteCheck.sortByDistance(P, 0, 0)")
d = [problems[i].distance for i in range(1, len(problems) + 1)]
assert d == sorted(d)
counts = s.eval("ADRouteCheck.countKinds(P)")
assert [counts[i] for i in range(1, 6)] == [1, 1, 1, 1, 1]

# clean network: two-way ring with targets, nothing found
s.execute("""
    W = {wp(1, 0, 0, {2, 3}), wp(2, 10, 0, {1, 3}), wp(3, 5, 8, {1, 2})}
    M = {{id = 1, name = "A"}, {id = 3, name = "B"}}
""")
assert len(s.eval("ADRouteCheck.analyse(W, M)")) == 0

# a separate loop without targets (e.g. a field outline) is no problem
s.execute("""
    W[4] = wp(4, 100, 0, {5}); W[5] = wp(5, 110, 0, {6}); W[6] = wp(6, 105, 8, {4})
""")
assert len(s.eval("ADRouteCheck.analyse(W, M)")) == 0, s.globals().kinds(s.eval("ADRouteCheck.analyse(W, M)"))

# big map: a 40000 waypoint chain in both directions, a long one-way chain for deep recursion
start = time.time()
s.execute("""
    W = {}
    local n = 40000
    for i = 1, n do
        local out = {}
        if i > 1 then out[#out + 1] = i - 1 end
        if i < n then out[#out + 1] = i + 1 end
        W[i] = wp(i, (i % 200) * 5, math.floor(i / 200) * 5, out)
    end
    M = {{id = 1, name = "A"}, {id = n, name = "B"}}
    BIG = ADRouteCheck.analyse(W, M)
    ONEWAY = {}
    for i = 1, n do ONEWAY[i] = wp(i, i * 3, 0, i < n and {i + 1} or {1}) end
    BIG2 = ADRouteCheck.analyse(ONEWAY, M)
""")
elapsed = time.time() - start
assert s.eval("#BIG") == 0 and s.eval("#BIG2") == 0
assert elapsed < 10, elapsed
print("OK: route check finds all 5 kinds of problems, waypoints on top of each other, backup points and field entries are fine, clean networks pass, 2x40000 waypoints in %.1fs" % elapsed)
