-- Run with: lua test_assisted_tagging.lua
-- Exercises the darktable-independent half of tagging.lua directly.

package.path = package.path .. ";./?.lua"
local T = require("tagging")

local failures = 0
local function check(name, got, want)
    if got ~= want then
        failures = failures + 1
        print(string.format("FAIL %s: got %s, want %s", name, tostring(got), tostring(want)))
    else
        print(string.format("ok   %s", name))
    end
end

local function keys(set)
    local out = {}
    for k in pairs(set) do out[#out + 1] = k end
    table.sort(out)
    return table.concat(out, " + ")
end

-- exif_time_to_epoch / cluster_by_time -----------------------------------
check("parses a normal timestamp", T.exif_time_to_epoch("2026:06:01 14:30:00") ~= nil, true)
check("returns nil for missing timestamp", T.exif_time_to_epoch(nil), nil)
check("returns nil for garbage input", T.exif_time_to_epoch("not a date"), nil)

local t0 = T.exif_time_to_epoch("2026:06:01 14:30:00")
local bursts = T.cluster_by_time({
    { id = 1, epoch = t0 }, { id = 2, epoch = t0 + 1 }, { id = 3, epoch = t0 + 10 }, { id = 4, epoch = nil },
}, 2)
check("frames within the gap share a burst", bursts[1], bursts[2])
check("a frame past the gap starts a new burst", bursts[3] ~= bursts[2], true)
check("an untimed frame gets its own burst", bursts[4] ~= bursts[3] and bursts[4] ~= bursts[1], true)

-- csv ---------------------------------------------------------------------
check("csv_line quotes every field", T.csv_line({ 42, "/a b/c.NEF", 'x"y' }), '"42","/a b/c.NEF","x""y"')
local p = T.parse_csv_line("7,0,team,VER,TSU,0.712", 6)
check("parse_csv_line splits a results row", p and (p[3] .. "/" .. p[5]), "team/TSU")
check("parse_csv_line keeps empty fields", T.parse_csv_line("7,-1,none,,,0.000", 6)[4], "")
check("parse_csv_line rejects the wrong field count", T.parse_csv_line("7,0,none", 6), nil)

-- entries.csv / rules.csv ---------------------------------------------------
local entries, order = T.parse_entries_csv(table.concat({
    "VER,Red Bull,1,F1|Red Bull;F1|Red Bull|Verstappen",
    "TSU,Red Bull,22,F1|Red Bull;F1|Red Bull|Tsunoda",
    "HAM,Ferrari,44,F1|Ferrari;F1|Ferrari|Hamilton",
    "SC,,,F1|Safety Car",
    "broken line",
}, "\n"))
check("entries keep file order", table.concat(order, ","), "VER,TSU,HAM,SC")
check("entries split their tags", entries.VER.tags[2], "F1|Red Bull|Verstappen")
check("an entry may have no team or number", entries.SC.team .. "|" .. entries.SC.number, "|")

local defaults = T.default_rules()
check("default rules share team tags", defaults.team_only, "shared tags")
check("default diagnostics sit under Assisted Tagging|Motorsport", defaults.diag.livery,
    "Assisted Tagging|Motorsport|Identified|By livery")
local rules = T.parse_rules_csv(table.concat({
    "team_only,none",
    "unidentified,F1|Check;F1|Check|Later",
    "diag_number,Assisted Tagging|Motorsport|Identified|By number",
    "diag_burst,",
    "diag_team,X|Team",
}, "\n"))
check("rules: team_only", rules.team_only, "none")
check("rules: unidentified tags", table.concat(rules.unidentified, ","), "F1|Check,F1|Check|Later")
check("rules: an empty diagnostic is off", rules.diag.burst, "")
check("rules: a renamed diagnostic", rules.diag.team, "X|Team")
check("rules: unlisted diagnostics keep their default", rules.diag.none, "Assisted Tagging|Motorsport|Unidentified")

-- wanted_tags ---------------------------------------------------------------
local function row(method, entry, alt) return { box = 0, method = method, entry_id = entry or "", alt_entry_id = alt or "" } end

local w, d, ok = T.wanted_tags({ row("number", "VER") }, entries)
check("a number result wants the entry's tags", keys(w), "F1|Red Bull + F1|Red Bull|Verstappen")
check("a number result gets the By number diagnostic", keys(d), "Assisted Tagging|Motorsport|Identified|By number")
check("a number result is identified", ok, true)

w, d = T.wanted_tags({ row("team", "VER", "TSU") }, entries)
check("team only wants just the shared tags", keys(w), "F1|Red Bull")
check("team only gets the Team only diagnostic", keys(d), "Assisted Tagging|Motorsport|Team only")
w, d = T.wanted_tags({ row("team", "VER", "TSU") }, entries, rules)
check("team_only none wants no collection tags", keys(w), "")
check("team_only none still uses its diagnostic", keys(d), "X|Team")

w, d, ok = T.wanted_tags({ row("number", "VER"), { box = 1, method = "livery", entry_id = "HAM", alt_entry_id = "" } },
    entries)
check("two cars want both entries' tags", keys(w),
    "F1|Ferrari + F1|Ferrari|Hamilton + F1|Red Bull + F1|Red Bull|Verstappen")

w, d, ok = T.wanted_tags({ { box = -1, method = "none", entry_id = "", alt_entry_id = "" } }, entries)
check("no vehicle wants nothing by default", keys(w), "")
check("no vehicle gets the Unidentified diagnostic", keys(d), "Assisted Tagging|Motorsport|Unidentified")
check("no vehicle is not identified", ok, false)
w = T.wanted_tags({ row("none") }, entries, rules)
check("unidentified rule tags are wanted", keys(w), "F1|Check + F1|Check|Later")
w, d = T.wanted_tags({ row("burst", "TSU") }, entries, rules)
check("a dropped diagnostic writes none", keys(d), "")
w, _, ok = T.wanted_tags({ row("number", "GONE") }, entries)
check("an entry no longer in entries.json identifies nothing", ok, false)

-- owned_tags / tag_changes (Review Focus 5) ---------------------------------
local owned = T.owned_tags(entries, rules)
check("owned: entry tags", owned["F1|Ferrari|Hamilton"], true)
check("owned: unidentified rule tags", owned["F1|Check"], true)
check("owned: renamed diagnostics", owned["X|Team"], true)
check("owned: default diagnostics stay owned after a rename", owned["Assisted Tagging|Motorsport|Team only"], true)
check("owned: the user's own tags are not", owned["Holiday"], nil)

local attach, detach = T.tag_changes(
    { ["F1|Red Bull"] = true, ["F1|Red Bull|Verstappen"] = true, ["Holiday"] = true },
    T.wanted_tags({ row("number", "HAM") }, entries), owned)
check("VER → HAM attaches Hamilton's tags", table.concat(attach, ","), "F1|Ferrari,F1|Ferrari|Hamilton")
check("VER → HAM drops every Red Bull tag and keeps the user's own", table.concat(detach, ","),
    "F1|Red Bull,F1|Red Bull|Verstappen")
attach, detach = T.tag_changes({ ["F1|Red Bull"] = true, ["Holiday"] = true },
    T.wanted_tags({ row("number", "VER") }, entries), owned)
check("team → VER attaches only the driver tag", table.concat(attach, ","), "F1|Red Bull|Verstappen")
check("team → VER keeps the team tag without detaching it", #detach, 0)

-- entry_for_tags --------------------------------------------------------------
check("an image with all of one entry's tags maps to it",
    T.entry_for_tags({ ["F1|Red Bull"] = true, ["F1|Red Bull|Tsunoda"] = true }, entries, order), "TSU")
check("a shared team tag alone maps to no one", T.entry_for_tags({ ["F1|Red Bull"] = true }, entries, order), nil)
check("two drivers' tags map to no one", T.entry_for_tags({
    ["F1|Red Bull"] = true, ["F1|Red Bull|Tsunoda"] = true, ["F1|Ferrari"] = true, ["F1|Ferrari|Hamilton"] = true,
}, entries, order), nil)
check("no matching tags map to no one", T.entry_for_tags({ ["Holiday"] = true }, entries, order), nil)

-- read_results (review fix 4) ----------------------------------------------
local rows_of, errored = T.read_results(table.concat({
    "1,0,number,VER,,0.950",
    "1,1,none,,,0.000",
    "4,-1,none,,,0.000",
    "5,-1,error,,,0.000",
    "garbage",
}, "\n"))
check("results group by image id", #rows_of[1], 2)
check("a no-vehicle frame has a row", rows_of[4][1].method, "none")
check("an errored frame has no rows to apply", rows_of[5], nil)
check("an errored frame is reported", errored[5], true)

-- utf16le (review fix 6: the .vbs launcher must survive a non-ASCII tmp path) --
check("utf16le: ASCII", T.utf16le("a"), "a\0")
check("utf16le: Latin-1", T.utf16le("é"), "\xE9\0")
check("utf16le: astral plane uses a surrogate pair", T.utf16le("😀"), "\x3D\xD8\x00\xDE")

print("")
if failures == 0 then
    print("all tests passed")
    os.exit(0)
else
    print(failures .. " test(s) failed")
    os.exit(1)
end
