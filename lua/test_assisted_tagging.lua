-- Run with: lua test_assisted_tagging.lua
-- Exercises the darktable-independent half of assisted_tagging.lua directly.

package.path = package.path .. ";./?.lua"
local T = require("assisted_tagging")

local failures = 0
local function check(name, got, want)
    if got ~= want then
        failures = failures + 1
        print(string.format("FAIL %s: got %s, want %s", name, tostring(got), tostring(want)))
    else
        print(string.format("ok   %s", name))
    end
end

-- plugin_common.lua ---------------------------------------------------------------
-- The same file in all three plugin repos; COMMON_HASH pins it. After changing it, copy it to the
-- other two repos and put the hash this prints into their tests too.
local COMMON_HASH = "cab10783"
local script_dir = (arg and arg[0] or ""):match("^(.*)[/\\]") or "."
local PC = dofile(script_dir .. "/plugin_common.lua")
local function fnv1a(text)
    local h = 2166136261
    for i = 1, #text do h = ((h ~ text:byte(i)) * 16777619) & 0xffffffff end
    return string.format("%08x", h)
end
local cf = assert(io.open(script_dir .. "/plugin_common.lua", "rb"))
local common_text = cf:read("a"):gsub("\r\n", "\n")
cf:close()
check("plugin_common.lua matches COMMON_HASH (copy it to the other repos after a change)", fnv1a(common_text), COMMON_HASH)
check("shell_quote: Windows escapes quotes, keeps %", PC.shell_quote('C:\\x %y% "z"', true), '"C:\\x %y% \\"z\\""')
check("shell_quote: POSIX escapes single quotes", PC.shell_quote("a'b", false), "'a'\\''b'")
check("parse_csv_line: quoted comma and doubled quote", PC.parse_csv_line('1,"a ""x"", b.jpg",3\r', 3)[2], 'a "x", b.jpg')
check("parse_csv_line: wrong field count is nil", PC.parse_csv_line("a,b", 3), nil)
check("lead_rank: full-size JPEG beats RAW", PC.lead_rank("x.JPG") > PC.lead_rank("x.nef"), true)
check("detections_path: <config_dir>/assisted_plugins/detections.sqlite, backslashes folded",
    PC.detections_path({ configuration = { config_dir = "C:\\Users\\me\\dt" } }), "C:/Users/me/dt/assisted_plugins/detections.sqlite")
check("page_index: out of range falls back to 1",
    table.concat({ PC.page_index(7, 3), PC.page_index(0, 3), PC.page_index(nil, 3), PC.page_index(2, 3) }, " "), "1 1 1 2")
do
    local schema = { { key = "x" }, { key = "y" }, { key = "z" }, { key = "w" } }
    local missing, duplicate = PC.page_coverage({ { title = "a", keys = { "x", "y" } }, { title = "b", keys = { "y" } } }, { "z" }, schema)
    check("page_coverage: missing and duplicate keys are named", table.concat(missing, " ") .. "|" .. table.concat(duplicate, " "), "w|y")
    missing, duplicate = PC.page_coverage({ { title = "a", keys = { "x", "y" } }, { title = "b", keys = {} } }, { "z" },
        { { key = "x" }, { key = "y" }, { key = "z" } })
    check("page_coverage: complete panel is clean", #missing + #duplicate, 0)
end
do -- temp_base / sweep_temp: leftovers older than max_age go, newer ones and other prefixes stay
    local dir = os.tmpname()
    os.remove(dir)
    os.execute(PC.IS_WINDOWS and ('mkdir "' .. dir .. '"') or ("mkdir -p '" .. dir .. "'"))
    local function touch(name) local f = assert(io.open(dir .. "/" .. name, "w")); f:write("x"); f:close() end
    touch("dt_assisted_x_1000_1_old.csv"); touch("dt_assisted_x_5000_1_new.csv"); touch("dt_assisted_y_1000_1_other.csv")
    local base = PC.temp_base(dir, "dt_assisted_x_")
    check("temp_base: <dir>/<prefix><epoch>_<seq>_", base:match("^" .. dir:gsub("%p", "%%%0") .. "/dt_assisted_x_%d+_%d+_$") ~= nil, true)
    local removed = PC.sweep_temp(dir, "dt_assisted_x_", 86400, 1000 + 86401)
    check("sweep_temp: removes only this prefix's stale files", table.concat(removed, ","), "dt_assisted_x_1000_1_old.csv")
    check("sweep_temp: newer file kept", PC.file_exists(dir .. "/dt_assisted_x_5000_1_new.csv"), true)
    check("sweep_temp: other prefix kept", PC.file_exists(dir .. "/dt_assisted_y_1000_1_other.csv"), true)
    for _, n in ipairs(PC.list_dir(dir)) do os.remove(dir .. "/" .. n) end
    os.remove(dir)
end
do -- Lua error log: guard logs + toasts errors, passes results through; log trims to its newer half
    local log_path = os.tmpname()
    os.remove(log_path)
    local toasts, made = {}, {}
    local fake_dt = {
        print = function(msg) toasts[#toasts + 1] = msg end,
        new_widget = function(kind) return function(props) made[#made + 1] = props; return props end end,
    }
    local guard = PC.error_guard(fake_dt, log_path, "Assisted Tagging")
    check("error_guard: results pass through", select(2, guard("ok", function(a, b) return a, b end, 1, 2)), 2)
    check("error_guard: error returns nil", guard("panel install", function() error("boom") end), nil)
    local text = PC.read_file(log_path) or ""
    check("error_guard: log has label and traceback", text:match("%] panel install\n.-boom.-traceback") ~= nil, true)
    check("error_guard: toast names the log file", toasts[1], "Assisted Tagging: Lua error, see " .. log_path:match("[^/\\]+$"))
    local widget = PC.guarded_widget_maker(fake_dt, guard)("button") {
        label = "Derive", clicked_callback = function() error("cb") end, tooltip = "t" }
    widget.clicked_callback()
    check("guarded_widget_maker: callback errors are logged with kind + label",
        (PC.read_file(log_path) or ""):match("%] button Derive\n") ~= nil, true)
    check("guarded_widget_maker: other props untouched", made[1].tooltip, "t")
    os.remove(log_path)
    PC.write_file_atomic(log_path, string.rep("old line\n", 30) .. string.rep("new line\n", 30))
    PC.append_error_log(log_path, "x", "y", 300, "T")
    text = PC.read_file(log_path)
    check("append_error_log: older half dropped at a line start", text:sub(1, 9), "new line\n")
    check("append_error_log: entry appended", text:sub(-9), "[T] x\ny\n\n")
    os.remove(log_path)
end
do -- shared preferences: assisted_plugins key first, old per-plugin key logged once
    local prefs, logged = {}, {}
    local fake_dt = { preferences = { read = function(group, name) return prefs[group .. "/" .. name] or "" end } }
    local function log(msg) logged[#logged + 1] = msg end
    prefs["assisted_plugins/plugins_root"] = "/plugins/"
    check("plugin_folder: plugins_root/<folder>", PC.plugin_folder(fake_dt, "assisted_tagging", "darktable-assisted-tagging", log, "/fb"),
        "/plugins/darktable-assisted-tagging")
    check("shared key set: nothing logged", #logged, 0)
    prefs["assisted_plugins/plugins_root"] = ""
    prefs["assisted_tagging/plugin_folder"] = "/old/folder"
    check("plugin_folder: old key when shared blank", PC.plugin_folder(fake_dt, "assisted_tagging", "darktable-assisted-tagging", log, "/fb"), "/old/folder")
    PC.plugin_folder(fake_dt, "assisted_tagging", "darktable-assisted-tagging", log, "/fb")
    check("deprecations: one line per old key", #logged, 1)
    check("deprecation line: plugin_folder", logged[1], "preferences: assisted_tagging/plugin_folder is deprecated; set assisted_plugins/plugins_root")
    prefs["assisted_tagging/plugin_folder"] = ""
    check("plugin_folder: both blank -> fallback", PC.plugin_folder(fake_dt, "assisted_tagging", "darktable-assisted-tagging", log, "/fb"), "/fb")
    check("plugin_folder: no fallback -> empty", PC.plugin_folder(fake_dt, "assisted_tagging", "darktable-assisted-tagging", log), "")
    local registered = {}
    fake_dt.preferences.register = function(group, name) registered[#registered + 1] = group .. "/" .. name end
    package.loaded["assisted_plugins.shared_prefs_registered"] = nil
    PC.register_shared_prefs(fake_dt)
    dofile(script_dir .. "/plugin_common.lua").register_shared_prefs(fake_dt)
    check("register_shared_prefs: once across plugin copies", table.concat(registered, ","), "assisted_plugins/plugins_root")
    package.loaded["assisted_plugins.shared_prefs_registered"] = nil
end

local function keys(set)
    local out = {}
    for k in pairs(set) do out[#out + 1] = k end
    table.sort(out)
    return table.concat(out, " + ")
end

-- exif_time_to_epoch -----------------------------------
check("parses a normal timestamp", T.exif_time_to_epoch("2026:06:01 14:30:00") ~= nil, true)
check("returns nil for missing timestamp", T.exif_time_to_epoch(nil), nil)
check("returns nil for garbage input", T.exif_time_to_epoch("not a date"), nil)
check("returns nil for an all-zero date", T.exif_time_to_epoch("0000:00:00 00:00:00"), nil)
check("returns nil for a pre-1970 date", T.exif_time_to_epoch("1965:03:01 12:00:00"), nil)

-- near_in_time -----------------------------------------
local function near_ids(sel, cands)
    local ids = {}
    for _, c in ipairs(T.near_in_time(sel, cands, 120)) do ids[#ids + 1] = c.id end
    return table.concat(ids, ",")
end
check("near_in_time keeps candidates within the gap of any selected time",
    near_ids({ 1000, 5000 }, { { id = 1, time = 880 }, { id = 2, time = 879 }, { id = 3, time = 5120 }, { id = 4, time = 3000 } }),
    "1,3")
check("near_in_time ignores untimed candidates and selected times",
    near_ids({ 1000, 0 },{ { id = 1, time = nil }, { id = 2, time = 0 }, { id = 3, time = 1050 } }), "3")
check("near_in_time with no timed selection is empty", near_ids({}, { { id = 1, time = 100 } }), "")

-- group keys ----------------------------------------------------------------
local G10 = "Assisted Grouping|2026-11-09 10:00:00|Group"
local G12 = "Assisted Grouping|2026-11-09 12:30:00|Group"
check("latest_group_tag picks the greatest stamp",
    T.latest_group_tag({ [G10 .. "|0001"] = true, ["F1|Ferrari"] = true, [G12 .. "|0003"] = true }), G12 .. "|0003")
check("latest_group_tag ignores other tags and the bare node",
    T.latest_group_tag({ ["F1|Ferrari"] = true, [G12] = true, [G12 .. "|0001|x"] = true }), nil)

-- Half-regrouped selection: photos 1-2 only carry the 10:00 run, 3-4 the 12:30 run.
local lk, n_runs = T.latest_group_keys({
    { id = 1, tags = { [G10 .. "|0001"] = true } },
    { id = 2, tags = { [G10 .. "|0001"] = true } },
    { id = 3, tags = { [G10 .. "|0002"] = true, [G12 .. "|0001"] = true } },
    { id = 4, tags = { [G12 .. "|0001"] = true } },
    { id = 5, tags = { ["F1|Ferrari"] = true } },
})
check("latest_group_keys keeps each photo's own run", lk[1] == lk[2] and lk[3] == lk[4] and lk[1] ~= lk[3], true)
check("latest_group_keys counts runs", n_runs, 2)
check("latest_group_keys leaves untagged photos out", lk[5], nil)
local lng = T.number_groups({ 1, 2, 3, 4, 5 }, lk)
check("latest_group_keys -> two groups plus a single",
    table.concat({ lng[1], lng[2], lng[3], lng[4], lng[5] }, ","), "1,1,2,2,3")

local tagged = { { id = 1, tags = { [G12 .. "|0001"] = true } } }
check("group_tags_hint fires when native found nothing but tags exist", T.group_tags_hint(0, tagged), T.GROUP_TAGS_HINT)
check("group_tags_hint silent when native groups exist", T.group_tags_hint(2, tagged), nil)
check("group_tags_hint silent without grouping tags", T.group_tags_hint(0, { { id = 1, tags = {} } }), nil)

local gk = T.tag_group_keys({
    { id = 1, tags = { [G12 .. "|0001"] = true, [G12 .. "|0001|x"] = true } },
    { id = 2, tags = { [G12 .. "|0002"] = true } },
}, G12)
check("tag_group_keys reads immediate children only", gk[1] .. "/" .. gk[2], "0001/0002")
local gk2, multi = T.tag_group_keys({
    { id = 3, tags = { [G12 .. "|0002"] = true, [G12 .. "|0001"] = true } },
}, G12)
check("tag_group_keys takes the first child by name", gk2[3], "0001")
check("tag_group_keys reports the photo", multi[1], 3)
local gk3 = T.tag_group_keys({ { id = 4, tags = { [G10 .. "|0001"] = true } } }, G12)
check("tag_group_keys leaves unmatched photos out", gk3[4], nil)

local nk = T.native_group_keys({ { id = 1, leader = 5 }, { id = 2, leader = 5 }, { id = 3 } })
check("native_group_keys maps leaders", nk[1] .. nk[2] .. tostring(nk[3]), "55nil")

local ng = T.number_groups({ 10, 11, 12, 13 }, { [10] = "a", [11] = "a", [13] = "b" })
check("number_groups shares and separates",
    table.concat({ ng[10], ng[11], ng[12], ng[13] }, ","), "1,1,2,3")
local ng2 = T.number_groups({ 7, 8, 9 }, {})
check("number_groups with no keys at all", ng2[7] .. ng2[8] .. ng2[9], "123")

-- collapse_shots ------------------------------------------------------------
local function ids(list)
    local out = {}
    for _, img in ipairs(list) do out[#out + 1] = tostring(img.id) end
    return table.concat(out, ",")
end
local cp, cg = T.collapse_shots({
    { id = 1, path = "D:/a", filename = "DSC1.ARW" },
    { id = 2, path = "D:/a", filename = "dsc1.jpg" },
    { id = 3, path = "D:/a", filename = "DSC2.ARW" },
    { id = 4, path = "D:/b", filename = "DSC1.JPG" },
    { id = 5, path = "D:/a", filename = "DSC1.ARW" },
})
check("collapse_shots: JPEG leads its RAW pair, any case", ids(cp), "2,3,4")
check("collapse_shots: pair and duplicate take the JPEG's tags", ids(cg[2]), "1,2,5")
check("collapse_shots: RAW alone is read itself", ids(cg[3]), "3")
check("collapse_shots: same stem in another folder is its own shot", ids(cg[4]), "4")
check("collapse_shots: the replaced lead has no group", cg[1], nil)

-- shot_copies ---------------------------------------------------------------
local sc_read = { { id = 2, path = "D:/a", filename = "dsc1.jpg", group_leader = { id = 2 } } }
local sc = T.shot_copies(sc_read, {
    { id = 1, path = "D:/a", filename = "DSC1.ARW", group_leader = { id = 1 } },
    { id = 2, path = "D:/a", filename = "dsc1.jpg", group_leader = { id = 2 } },
    { id = 6, path = "D:/a", filename = "DSC9.jpg", group_leader = { id = 2 } },
    { id = 7, path = "D:/b", filename = "DSC1.JPG", group_leader = { id = 7 } },
    { id = 1, path = "D:/a", filename = "DSC1.ARW", group_leader = { id = 1 } },
})
check("shot_copies: RAW pair and group member, not the read image, another folder or a repeat", ids(sc), "1,6")

-- prefer_paired -------------------------------------------------------------
local raw1 = { id = 1, path = "D:/a", filename = "DSC1.ARW" }
local jpg1 = { id = 2, path = "D:/a", filename = "dsc1.JPG" }
local raw2 = { id = 3, path = "D:/a", filename = "DSC2.ARW" }
local jpgB = { id = 4, path = "D:/b", filename = "DSC2.jpg" }
local pp, nsw, pick = T.prefer_paired({ raw1, raw2, jpg1 }, { raw1, jpg1, raw2, jpgB })
check("prefer_paired: RAW swapped for its JPEG, dupes dropped, order kept", ids(pp), "2,3")
check("prefer_paired: counts swaps", nsw, 1)
check("prefer_paired: pick_of maps the RAW to the JPEG", pick[1].id, 2)
check("prefer_paired: a JPEG in another folder is not a pair", pick[3].id, 3)
local pe = T.prefer_paired({ raw1 }, {})
check("prefer_paired: empty pool keeps the selection", ids(pe), "1")

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
check("entries: four fields leave the name empty", entries.VER.name, "")
local named_entries = T.parse_entries_csv("NOR,McLaren,4,Assisted Tagging|Motorsport|Number|4;Assisted Tagging|Motorsport|Driver|Norris,Norris")
check("entries: a fifth field is the name", named_entries.NOR.name, "Norris")
check("entries: five fields still split the tags", named_entries.NOR.tags[2], "Assisted Tagging|Motorsport|Driver|Norris")
check("entries: five fields leave the co-driver empty", named_entries.NOR.co_driver, "")
local rally_entries = T.parse_entries_csv("12,Team,12,M|Number|12;M|Co-driver|Jones,Smith,Jones")
check("entries: a sixth field is the co-driver", rally_entries["12"].name .. "|" .. rally_entries["12"].co_driver, "Smith|Jones")
check("entries: a parsed co-driver names its entry", (T.hand_entry({ ["M|Co-driver|Jones"] = true }, {}, rally_entries,
    { number = "M|Number", driver = "M|Driver", co_driver = "M|Co-driver" })), "12")
check("entries: six fields leave the colour empty", rally_entries["12"].colour, "")
local coloured_entries = T.parse_entries_csv("12,Team,12,M|Number|12,Smith,Jones,Red")
check("entries: a seventh field is the colour", coloured_entries["12"].colour, "Red")

-- colour_relation (mirror of car_colour.py) ---------------------------------
check("colour_relation: equal agrees", T.colour_relation("Red", "Red"), 1)
check("colour_relation: different colours differ", T.colour_relation("Red", "Blue"), -1)
check("colour_relation: empty entry colour is 0", T.colour_relation("", "Red"), 0)
check("colour_relation: Multi is 0", T.colour_relation("Multi", "Red"), 0)
check("colour_relation: White/Grey near is 0", T.colour_relation("White", "Grey"), 0)
check("colour_relation: Black/Grey near is 0", T.colour_relation("Black", "Grey"), 0)
check("colour_relation: White/Black differ", T.colour_relation("White", "Black"), -1)

-- derive_plan / hand_source --------------------------------------------------
do
    local de, dorder = T.parse_entries_csv(table.concat({
        "1,Alpha,1,M|Number|1;M|Team|Alpha;M|Driver|Ann,Ann,,Red",
        "2,Beta,2,M|Number|2;M|Team|Beta;M|Driver|Bob,Bob,,Blue",
        "3,Gamma,3,M|Number|3;M|Team|Gamma;M|Driver|Cy,Cy,,Blue",
        "4,Gamma,4,M|Number|4;M|Team|Gamma;M|Driver|Di,Di,,Green",
    }, "\n"))
    local roots = { number = "M|Number", driver = "M|Driver", team = "M|Team", colour = "M|Colour" }
    local names = { derived = "AT|Derived", check_colour = "AT|Check colour" }
    local function plan(have, mode, ledger_set)
        local p = T.derive_plan(have, ledger_set, de, dorder, roots, mode, names)
        return table.concat(p.attach, ";") .. " / " .. p.reason
    end
    check("derive number: hand number adds the entry's tags and From number",
        plan({ ["M|Number|2"] = true }, "number"), "AT|Derived|From number;M|Driver|Bob;M|Team|Beta / ")
    check("derive number: a ledgered (plugin) number tag is not the user's",
        plan({ ["M|Number|2"] = true }, "number", { ["M|Number|2"] = true }), " / no number tag of yours names an entry")
    check("derive number: colour that differs adds Check colour",
        plan({ ["M|Number|1"] = true, ["M|Colour|Blue"] = true }, "number"),
        "AT|Check colour;AT|Derived|From number;M|Driver|Ann;M|Team|Alpha / ")
    check("derive number: entry already on the image is skipped",
        plan({ ["M|Number|4"] = true, ["M|Team|Gamma"] = true, ["M|Driver|Di"] = true }, "number"),
        " / it already has the entry's tags")
    check("derive number: Check colour already on the image isn't attached again",
        plan({ ["M|Number|1"] = true, ["M|Colour|Blue"] = true, ["AT|Check colour"] = true }, "number"),
        "AT|Derived|From number;M|Driver|Ann;M|Team|Alpha / ")
    check("derive number: the From number marker already on the image isn't attached again",
        plan({ ["M|Number|2"] = true, ["AT|Derived|From number"] = true }, "number"), "M|Driver|Bob;M|Team|Beta / ")
    check("derive colour: one entry of that colour",
        plan({ ["M|Colour|Green"] = true }, "colour"), "AT|Derived|From colour;M|Driver|Di;M|Number|4;M|Team|Gamma / ")
    check("derive colour: two entries of that colour skip",
        plan({ ["M|Colour|Blue"] = true }, "colour"), " / 2 entries are Blue")
    check("derive colour: a hand team tag narrows to one",
        plan({ ["M|Colour|Blue"] = true, ["M|Team|Beta"] = true }, "colour"),
        "AT|Derived|From colour;M|Driver|Bob;M|Number|2 / ")
    check("derive colour: no entry of that colour", plan({ ["M|Colour|Pink"] = true }, "colour"), " / no entry is Pink")
    check("derive colour: no colour tag", plan({}, "colour"), " / it has no colour tag")
    check("derive colour: a number tag defers to Derive from number, flagging the colour",
        plan({ ["M|Number|1"] = true, ["M|Colour|Blue"] = true }, "colour"),
        "AT|Check colour / it has a number tag: use Derive from number")
    check("derive: markers off add no marker",
        table.concat(T.derive_plan({ ["M|Number|2"] = true }, nil, de, dorder, roots, "number",
            { derived = "", check_colour = "" }).attach, ";"), "M|Driver|Bob;M|Team|Beta")
    check("hand_source: a number tag", T.hand_source({ ["M|Number|2"] = true }, nil, de, roots), "From number")
    check("hand_source: a driver tag", T.hand_source({ ["M|Driver|Bob"] = true }, nil, de, roots), "From driver")
    local mrules = T.default_rules()
    mrules.diag.derived = "AT|Derived"
    local _w, mdiag = T.wanted_tags({ { box = 0, method = "livery", entry_id = "1" } }, de, mrules)
    check("wanted_tags: a model result marks From identification", mdiag["AT|Derived|From identification"], true)
    local _w2, hdiag = T.wanted_tags({ { box = 0, method = "hand", entry_id = "1" } }, de, mrules, "From driver")
    check("wanted_tags: a hand result marks its source", hdiag["AT|Derived|From driver"], true)
    check("owned_prefixes: the Derived base is owned per value",
        table.concat(T.owned_prefixes({ diag = { derived = "AT|Derived" }, families = {} }), ";"), "AT|Derived|")
end

local defaults = T.default_rules()
check("default rules share team tags", defaults.team_only, "shared tags")
check("default diagnostics sit under Assisted Tagging|Identification", defaults.diag.livery,
    "Assisted Tagging|Identification|By livery")
local rules = T.parse_rules_csv(table.concat({
    "team_only,none",
    "unidentified,F1|Check;F1|Check|Later",
    "diag_number,Assisted Tagging|Identification|By number",
    "diag_burst,",
    "diag_team,X|Team",
}, "\n"))
check("rules: team_only", rules.team_only, "none")
check("rules: unidentified tags", table.concat(rules.unidentified, ","), "F1|Check,F1|Check|Later")
check("rules: an empty diagnostic is off", rules.diag.burst, "")
check("rules: a renamed diagnostic", rules.diag.team, "X|Team")
check("rules: unlisted diagnostics keep their default", rules.diag.none, "Assisted Tagging|Identification|Unidentified")
check("rules: no family line, no family", next(rules.families), nil)
local fam_rules = T.parse_rules_csv("family_colour,Assisted Tagging|Motorsport|Colour\nfamily_team,Rally 2026|Team")
check("rules: a family root keeps its space and |", fam_rules.families.team, "Rally 2026|Team")
check("rules: an off family has no line and no root", fam_rules.families.number, nil)

-- families ------------------------------------------------------------------
do
    local keys_in_order = {}
    for _, f in ipairs(T.FAMILIES) do keys_in_order[#keys_in_order + 1] = f.key end
    check("FAMILIES: order", table.concat(keys_in_order, ","), "colour,number,team,driver,co_driver,extra,vehicle,sponsor")
    local fs = T.preset_defaults(T.PRESET_SCHEMA)
    local roots = T.family_roots(fs)
    check("family_roots: every family on by default", roots.colour .. " " .. roots.number .. " " .. roots.team .. " " .. roots.driver,
        "Assisted Tagging|Motorsport|Colour Assisted Tagging|Motorsport|Number Assisted Tagging|Motorsport|Team Assisted Tagging|Motorsport|Driver")
    fs.family_team, fs.family_number_root = false, "Rally|Number"
    roots = T.family_roots(fs)
    check("family_roots: an off family has no root", roots.team, nil)
    check("family_roots: a set root is used", roots.number, "Rally|Number")
    check("removed_settings: clean settings pass", T.removed_settings(fs), nil)
    check("removed_settings: colour_tags", T.removed_settings({ colour_tags = false }),
        'settings.json: colour_tags was removed; use family_colour (README, "Tag families")')
    check("removed_settings: tag_colour", T.removed_settings({ tag_colour = true }),
        'settings.json: tag_colour was removed; use family_colour (README, "Tag families")')
    check("removed_settings: tag_colour_name", T.removed_settings({ tag_colour_name = "X" }),
        'settings.json: tag_colour_name was removed; use family_colour_root (README, "Tag families")')
    check("removed_settings: set embedder_file stops", T.removed_settings({ embedder_file = "dinov2_base.onnx" }),
        'settings.json: embedder_file was removed; the plugin picks the model now (README, "Models")')
    check("removed_settings: set ocr_rec_file stops", T.removed_settings({ ocr_rec_file = "x.onnx" }),
        'settings.json: ocr_rec_file was removed; the plugin picks the model now (README, "Models")')
    check("removed_settings: blank model keys are ignored",
        T.removed_settings({ embedder_file = "", ocr_rec_file = "  " }), nil)
end

-- wanted_tags ---------------------------------------------------------------
local function row(method, entry, alt) return { box = 0, method = method, entry_id = entry or "", alt_entry_id = alt or "" } end

local w, d, ok = T.wanted_tags({ row("number", "VER") }, entries)
check("a number result wants the entry's tags", keys(w), "F1|Red Bull + F1|Red Bull|Verstappen")
check("a number result gets the By number diagnostic", keys(d), "Assisted Tagging|Identification|By number")
check("a number result is identified", ok, true)

w, d = T.wanted_tags({ row("team", "VER", "TSU") }, entries)
check("team only wants just the shared tags", keys(w), "F1|Red Bull")
check("team only gets the Team only diagnostic", keys(d), "Assisted Tagging|Identification|Team only")
w, d = T.wanted_tags({ row("team", "VER", "TSU") }, entries, rules)
check("team_only none wants no collection tags", keys(w), "")
check("team_only none still uses its diagnostic", keys(d), "X|Team")

w, d, ok = T.wanted_tags({ row("number", "VER"), { box = 1, method = "livery", entry_id = "HAM", alt_entry_id = "" } },
    entries)
check("two cars want both entries' tags", keys(w),
    "F1|Ferrari + F1|Ferrari|Hamilton + F1|Red Bull + F1|Red Bull|Verstappen")

w, d, ok = T.wanted_tags({ { box = -1, method = "none", entry_id = "", alt_entry_id = "" } }, entries)
check("no vehicle wants nothing by default", keys(w), "")
check("no vehicle gets the Unidentified diagnostic", keys(d), "Assisted Tagging|Identification|Unidentified")
check("no vehicle is not identified", ok, false)
w = T.wanted_tags({ row("none") }, entries, rules)
check("unidentified rule tags are wanted", keys(w), "F1|Check + F1|Check|Later")
w, d = T.wanted_tags({ row("burst", "TSU") }, entries, rules)
check("a dropped diagnostic writes none", keys(d), "")
w, _, ok = T.wanted_tags({ row("number", "GONE") }, entries)
check("an entry no longer in entries.json identifies nothing", ok, false)

w, d, ok = T.wanted_tags({ row("neighbour", "VER") }, entries)
check("a neighbour result wants the entry's tags", keys(w), "F1|Red Bull + F1|Red Bull|Verstappen")
check("a neighbour result gets the By neighbour diagnostic", keys(d), "Assisted Tagging|Identification|By neighbour")
check("a neighbour result is identified", ok, true)
local flagged = row("number", "VER")
flagged.order_flag = true
w, d = T.wanted_tags({ flagged }, entries)
check("a flagged read keeps the entry's tags", keys(w), "F1|Red Bull + F1|Red Bull|Verstappen")
check("a flagged read gets By number and Check order",
    keys(d), "Assisted Tagging|Identification|By number + Assisted Tagging|Identification|Check order")
w, d = T.wanted_tags({ flagged }, entries, T.parse_rules_csv("diag_check_order,"))
check("a dropped Check order diagnostic writes none", keys(d), "Assisted Tagging|Identification|By number")
-- mask_diag: the tag_<outcome> preferences
local masked = T.mask_diag(T.default_rules(), { check_order = true })
w, d = T.wanted_tags({ flagged }, entries, masked)
check("mask_diag: an off outcome writes no diagnostic", keys(d), "Assisted Tagging|Identification|By number")
check("mask_diag: entry tags are unchanged", keys(w), "F1|Red Bull + F1|Red Bull|Verstappen")
masked = T.mask_diag(rules, { team = true })
w, d = T.wanted_tags({ row("team", "VER", "TSU") }, entries, masked)
check("mask_diag: switches off a renamed diagnostic too", keys(d), "")
check("mask_diag: keeps the other rules", masked.team_only, "none")
check("mask_diag: leaves the rules it was given alone", rules.diag.team, "X|Team")
masked = T.mask_diag(T.default_rules(), { shot = true })
check("mask_diag: off.shot blanks Solo and Pack, leaves shot_crowded",
    masked.diag.shot_solo .. masked.diag.shot_pack, "")
check("mask_diag: off.shot leaves shot_crowded", masked.diag.shot_crowded, "Assisted Tagging|Identification|Shot|Crowded")
masked = T.mask_diag(T.default_rules(), { shot_crowded = true })
check("mask_diag: off.shot_crowded blanks only shot_crowded",
    masked.diag.shot_crowded .. "|" .. masked.diag.shot_solo .. "|" .. masked.diag.shot_pack,
    "|Assisted Tagging|Identification|Shot|Solo|Assisted Tagging|Identification|Shot|Pack")
local seen = row("none")
seen.unmatched_number = "115"
w, d = T.wanted_tags({ seen }, entries, T.mask_diag(T.default_rules(), { number_seen = true }))
check("mask_diag: number_seen off drops the Number seen tags", keys(d), "Assisted Tagging|Identification|Unidentified")
local function parsed(key, text)
    local v, err = T.parse_setting(key, text)
    return tostring(v) .. (err and " err" or "")
end
check("parse_setting: whole tolerance", parsed("neighbour_tolerance", "5"), "5")
check("parse_setting: fractional tolerance refused", parsed("neighbour_tolerance", "3.5"), "nil err")
check("parse_setting: order weight 1", parsed("order_weight", "1"), "1")
check("parse_setting: order weight above 1 refused", parsed("order_weight", "1.1"), "nil err")
check("parse_setting: blank refused", parsed("min_read", ""), "nil err")
check("parse_setting: tag name with a comma refused", parsed("tag_number_seen_name", "Cars,Paint"), "nil err")
check("parse_setting: family root kept whole", parsed("family_number_root", " Rally 2026|Number "), "Rally 2026|Number")
check("parse_setting: family root with a comma refused", parsed("family_number_root", "Rally,Number"), "nil err")
check("parse_setting: family root starting with | refused", parsed("family_number_root", "|Number"), "nil err")
check("parse_setting: family root ending with | refused", parsed("family_number_root", "Number|"), "nil err")

-- panel_value: what read_panel makes of an entry
check("panel_value: blank number is the default", T.panel_value("min_read", "  "), 0.85)
check("panel_value: blank tag name is the default", T.panel_value("tag_number_seen_name", ""),
    "Assisted Tagging|Identification|Number seen")
check("panel_value: blank family root is the default", T.panel_value("family_team_root", ""), "Assisted Tagging|Motorsport|Team")
local pv, pv_why = T.panel_value("order_weight", "0,5")
check("panel_value: 0,5 refused", pv, nil)
check("panel_value: the message names the key", pv_why:sub(1, 14), "order_weight: ")
pv, pv_why = T.panel_value("tag_number_seen_name", "Cars,Paint")
check("panel_value: tag name with a comma refused", pv, nil)
check("panel_value: tag name message names the key", pv_why:sub(1, 22), "tag_number_seen_name: ")
pv, pv_why = T.panel_value("family_team_root", "|Team")
check("panel_value: bad family root refused", pv, nil)
check("panel_value: family root message", pv_why, "family_team_root: can't start or end with | or a space")
check("panel_value: valid number", T.panel_value("neighbour_tolerance", "4"), 4)

-- tag_row_label: a gated tag switch says in its label why it is off
local toggles_by_key = {}
for _, t in ipairs(T.TAG_TOGGLES) do toggles_by_key[t.key] = t end
local function row_label(key, s)
    local label, gated = T.tag_row_label(toggles_by_key[key], s)
    return label .. (gated and " [gated]" or "")
end
check("tag_row_label: Check colour gated by family_colour off", row_label("check_colour", { family_colour = false }),
      "Check colour (off: the Colour family is off) [gated]")
check("tag_row_label: Check colour with family_colour on", row_label("check_colour", { family_colour = true }), "Check colour")
check("tag_row_label: By neighbour gated by order_weight 0", row_label("neighbour", { order_weight = 0 }),
      "By neighbour (off: order weight is 0) [gated]")
check("tag_row_label: By neighbour with order_weight 0.5", row_label("neighbour", { order_weight = 0.5 }), "By neighbour")
check("tag_row_label: By pooled burst gated by burst_livery_pooling nil", row_label("pooled", {}),
      "By pooled burst (off: burst_livery_pooling is off in settings.json) [gated]")
check("tag_row_label: ungated row unchanged", row_label("number", {}), "By number")
local schema_keys = {}
for _, f in ipairs(T.PRESET_SCHEMA) do schema_keys[f.key] = true end
local bad_gates = {}
for _, g in ipairs(T.TAG_GATES) do
    if not toggles_by_key[g.key] or not schema_keys[g.by] then bad_gates[#bad_gates + 1] = g.key .. "/" .. g.by end
end
check("TAG_GATES: every gate names a TAG_TOGGLES key and a PRESET_SCHEMA key", table.concat(bad_gates, " "), "")

local kinds, bad_kinds = {}, {}
for _, k in ipairs(T.TAG_KINDS) do kinds[k.kind] = true end
for _, t in ipairs(T.TAG_TOGGLES) do
    if not kinds[t.kind] then bad_kinds[#bad_kinds + 1] = t.key end
end
check("TAG_TOGGLES: every row has a kind in TAG_KINDS", table.concat(bad_kinds, " "), "")
local ordered = {}
for _, t in ipairs(T.tag_rows_in_order()) do ordered[#ordered + 1] = t.key end
check("tag_rows_in_order: checks, then diagnostics", table.concat(ordered, ","),
    "check_order,none,check_colour,shot,shot_crowded,number,livery,burst,pooled,neighbour,team,number_seen,derived")
local none_label
for _, t in ipairs(T.TAG_TOGGLES) do if t.key == "none" then none_label = t.label end end
check("TAG_TOGGLES: none is labelled Unidentified (check)", none_label, "Unidentified (check)")
local page_missing, page_duplicate = PC.page_coverage(T.PANEL_PAGES, T.PANEL_OTHER_KEYS, T.PRESET_SCHEMA)
check("PANEL_PAGES: every preset key is on one page or listed off-stack",
    table.concat(page_missing, " ") .. table.concat(page_duplicate, " "), "")
local page_titles = {}
for _, p in ipairs(T.PANEL_PAGES) do page_titles[#page_titles + 1] = p.title end
check("PANEL_PAGES: titles match the README sections", table.concat(page_titles, ","),
    "collection,bursts,matching,tags written,run,references")

-- checked_settings: hand-edited settings.json values show_panel would display
local cs = T.preset_defaults(T.PRESET_SCHEMA)
cs.min_sim, cs.margin, cs.tag_team_name, cs.order_weight, cs.family_driver_root = 0, 1, "A,B", 0.3, "Driver|"
local fixed, replaced = T.checked_settings(cs)
check("checked_settings: out-of-range and bad names replaced", table.concat(replaced, " "),
    "min_sim margin family_driver_root tag_team_name")
check("checked_settings: bad family root back to default", fixed.family_driver_root, "Assisted Tagging|Motorsport|Driver")
check("checked_settings: min_sim back to default", fixed.min_sim, 0.5)
check("checked_settings: bad tag name back to default", fixed.tag_team_name, "Assisted Tagging|Identification|Team only")
check("checked_settings: a valid value kept", fixed.order_weight, 0.3)
check("checked_settings: the given settings untouched", cs.min_sim, 0)
-- A settings.json lacking a key: the panel shows that key's default, and nothing is logged.
local sparse = { min_sim = 0 }
local filled, sparse_replaced = T.checked_settings(sparse)
check("checked_settings: missing name key gets the default", filled.tag_number_seen_name,
    "Assisted Tagging|Identification|Number seen")
check("checked_settings: missing family root gets the default", filled.family_colour_root, "Assisted Tagging|Motorsport|Colour")
check("checked_settings: missing number key gets the default", filled.min_read, 0.85)
check("checked_settings: missing keys are not listed as replaced", table.concat(sparse_replaced, " "), "min_sim")
check("checked_settings: an invalid key is still replaced and listed", filled.min_sim, 0.5)

-- named_rules: switched-off diagnostics keep their names (rules.csv leaves them blank)
local off_s = T.preset_defaults(T.PRESET_SCHEMA)
off_s.family_colour, off_s.tag_shot = false, false
off_s.tag_shot_name = "My|Shot"
off_s.tag_shot_crowded_name = "My|Framing"
local blank_rules = T.parse_rules_csv("diag_shot_solo,\n")
local named = T.named_rules(blank_rules, off_s)
local named_has_colour = false
for _, p in ipairs(T.owned_prefixes(named)) do
    if p == "Assisted Tagging|Motorsport|Colour|" then named_has_colour = true end
end
check("named_rules: colour off still owns the colour prefix", named_has_colour, true)
check("named_rules: shot_crowded from tag_shot_crowded_name", named.diag.shot_crowded, "My|Framing|Crowded")
check("named_rules: solo and pack from tag_shot_name", named.diag.shot_solo .. " " .. named.diag.shot_pack, "My|Shot|Solo My|Shot|Pack")
check("named_rules: off diagnostic still owned", T.owned_tags({}, named)["My|Shot|Solo"], true)
check("named_rules: an off family keeps its root", named.families.colour, "Assisted Tagging|Motorsport|Colour")
check("named_rules: leaves the rules it was given alone", blank_rules.diag.shot_solo .. "|" .. tostring(next(blank_rules.families)), "|nil")

-- owned_tags / tag_changes (Review Focus 5) ---------------------------------
local owned = T.owned_tags(entries, rules)
check("owned: entry tags", owned["F1|Ferrari|Hamilton"], true)
check("owned: unidentified rule tags", owned["F1|Check"], true)
check("owned: renamed diagnostics", owned["X|Team"], true)
check("owned: default diagnostics stay owned after a rename", owned["Assisted Tagging|Identification|Team only"], true)
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
local car_tags = { "Rally|Number|30", "Rally|Number|730" }
local car_entries = { ["30"] = { tags = car_tags }, ["730"] = { tags = car_tags }, ["12"] = { tags = { "Rally|Number|12" } } }
check("a double-driven car's full tags map to its first entry",
    T.entry_for_tags({ ["Rally|Number|30"] = true, ["Rally|Number|730"] = true }, car_entries, { "30", "730", "12" }), "30")
check("a car plus another entry's tags map to no one", T.entry_for_tags({
    ["Rally|Number|30"] = true, ["Rally|Number|730"] = true, ["Rally|Number|12"] = true,
}, car_entries, { "30", "730", "12" }), nil)
local tsu_tags = { ["F1|Red Bull"] = true, ["F1|Red Bull|Tsunoda"] = true }
check("tags the plugin wrote (in the ledger) map to no one",
    T.entry_for_tags(tsu_tags, entries, order, { ["F1|Red Bull|Tsunoda"] = true }), nil)
check("tags the user added by hand still map with a ledger",
    T.entry_for_tags(tsu_tags, entries, order, { ["F1|Ferrari|Hamilton"] = true }), "TSU")

-- read_results (review fix 4) ----------------------------------------------
local rows_of, errored, skipped_ids = T.read_results(table.concat({
    "1,0,number,VER,,0.950,,pack,",
    "1,1,none,,,0.000,,pack,",
    "4,-1,none,,,0.000,,,",
    "5,-1,error,,,0.000,,,",
    "6,-1,skipped,,,0.000,,,",
    "7,0,none,,,0.000,,",
    "8,0,number,VER,,0.850,,solo,1",
    "garbage",
}, "\n"))
check("results group by image id", #rows_of[1], 2)
check("a no-vehicle frame has a row", rows_of[4][1].method, "none")
check("an errored frame has no rows to apply", rows_of[5], nil)
check("an errored frame is reported", errored[5], true)
check("a skipped frame has no rows to apply", rows_of[6], nil)
check("a skipped frame is reported", skipped_ids[6], true)
check("rows carry the shot type", rows_of[1][1].shot, "pack")
check("an 8-field line is rejected", rows_of[7], nil)
check("a row carries the order flag", rows_of[8][1].order_flag, true)
check("an unflagged row has no order flag", rows_of[1][1].order_flag, false)

-- colour columns ----------------------------------------------------------------
do
    local ro = T.read_results(table.concat({
        "20,0,number,VER,,0.950,,solo,",
        "21,0,number,VER,,0.950,,solo,,Red",
        "22,0,none,,,0.000,,solo,,Multi,1",
    }, "\n"))
    check("9-column row has no colour", ro[20][1].colour, "")
    check("9-column row has no colour flag", ro[20][1].colour_flag, false)
    check("10-column row carries the colour", ro[21][1].colour, "Red")
    check("10-column row has no colour flag", ro[21][1].colour_flag, false)
    check("11-column row carries colour and flag", ro[22][1].colour .. tostring(ro[22][1].colour_flag), "Multitrue")
    local CB = "Assisted Tagging|Motorsport|Colour"
    local ident, unident, none_box = row("number", "VER"), row("none"), row("none")
    ident.colour, unident.colour, none_box.colour = "Red", "Blue", "Red"
    none_box.box = -1
    local crules = T.default_rules()
    crules.families = { colour = CB }
    local _w, dd = T.wanted_tags({ ident }, entries, crules)
    check("identified row gets the colour tag", dd[CB .. "|Red"], true)
    _w, dd = T.wanted_tags({ unident }, entries, crules)
    check("unidentified row gets the colour tag", dd[CB .. "|Blue"], true)
    _w, dd = T.wanted_tags({ none_box }, entries, crules)
    check("box -1 row gets no colour tag", dd[CB .. "|Red"], nil)
    _w, dd = T.wanted_tags({ ident }, entries, T.default_rules())
    check("colour family off writes no colour tag", dd[CB .. "|Red"], nil)
    local fl = row("number", "VER")
    fl.colour, fl.colour_flag = "Red", true
    _w, dd = T.wanted_tags({ fl }, entries, crules)
    check("colour flag adds Check colour", dd["Assisted Tagging|Identification|Check colour"], true)
    local masked = T.mask_diag(crules, { check_colour = true })
    _w, dd = T.wanted_tags({ fl }, entries, masked)
    check("mask_diag: check_colour off blanks it", dd["Assisted Tagging|Identification|Check colour"], nil)
    check("mask_diag: the colour tag is still written", dd[CB .. "|Red"], true)
    check("owned: colour check tag", T.owned_tags(entries, rules)["Assisted Tagging|Identification|Check colour"], true)
    check("owned_prefixes: no colour root, no colour prefix", #T.owned_prefixes(T.default_rules()), 1)
    local pre = T.owned_prefixes(crules)
    local has = false
    for _, p in ipairs(pre) do if p == CB .. "|" then has = true end end
    check("owned_prefixes includes the colour base", has, true)
    check("hand_value: one hand colour", T.hand_value({ [CB .. "|Red"] = true }, {}, CB), "Red")
    check("hand_value: two colours", T.hand_value({ [CB .. "|Red"] = true, [CB .. "|Blue"] = true }, {}, CB), nil)
    check("hand_value: ledgered tag", T.hand_value({ [CB .. "|Red"] = true }, { [CB .. "|Red"] = true }, CB), nil)
    check("hand_value: empty base", T.hand_value({ [CB .. "|Red"] = true }, {}, ""), nil)
    do
        local have = { [CB .. "|Red"] = true, [CB .. "|White"] = true }
        local ledger_set = { [CB .. "|White"] = true }
        local prot = T.hand_family_tags(have, ledger_set, { colour = CB })
        local _, detach = T.tag_changes(have, { [CB .. "|Blue"] = true }, {}, pre, prot, ledger_set)
        check("hand colour tag survives a Blue reading", table.concat(detach, ";"), CB .. "|White")
        check("hand_family_tags: empty root", next(T.hand_family_tags(have, {}, { colour = "" })), nil)
    end
end

-- sponsor column ----------------------------------------------------------------
do
    local ro = T.read_results(table.concat({
        "30,0,number,VER,,0.950,,solo,,Red,,Castrol;Shell",
        "31,0,number,VER,,0.950,,solo,,Red,1",
    }, "\n"))
    check("12-column row carries the sponsor", ro[30][1].sponsor, "Castrol;Shell")
    check("11-column row has no sponsor", ro[31][1].sponsor, "")
    local SB = "Assisted Tagging|Motorsport|Sponsor"
    local sp, none_box = row("number", "VER"), row("none")
    sp.sponsor, none_box.sponsor = "Castrol;Shell", "Castrol"
    none_box.box = -1
    local srules = T.default_rules()
    srules.families = { sponsor = SB }
    local _w, dd = T.wanted_tags({ sp }, entries, srules)
    check("sponsor family writes each word", tostring(dd[SB .. "|Castrol"]) .. tostring(dd[SB .. "|Shell"]), "truetrue")
    _w, dd = T.wanted_tags({ none_box }, entries, srules)
    check("box -1 row gets no sponsor tag", dd[SB .. "|Castrol"], nil)
    _w, dd = T.wanted_tags({ sp }, entries, T.default_rules())
    check("sponsor family off writes no sponsor tag", dd[SB .. "|Castrol"], nil)
    local has = false
    for _, p in ipairs(T.owned_prefixes(srules)) do if p == SB .. "|" then has = true end end
    check("owned_prefixes includes the sponsor base", has, true)
end

-- start list column pickers -------------------------------------------------------
do
    local headers, mapped = T.parse_header_report("header\tNr\r\nheader\tPilot\nrole\tnumber\tNr\nrole\tdriver\tPilot\nrole\tteam\t\n")
    check("parse_header_report: headers in order", table.concat(headers, ","), "Nr,Pilot")
    check("parse_header_report: mapped roles", mapped.number .. "/" .. mapped.driver .. "/" .. mapped.team, "Nr/Pilot/")
    check("parse_header_report: empty output", #(T.parse_header_report("")), 0)
    check("columns_spec names every role, none as empty",
        T.columns_spec({ number = "Nr", driver = "Pilot" }),
        "number=Nr;driver=Pilot;co-driver=;team=;class=;make=;model=;shares-car=")
end

-- ledger / protected tags / shot + conflict handling ---------------------------
local led = T.ledger_parse(T.ledger_format({ [3] = { b = true, a = true }, [1] = { z = true } }))
check("ledger round-trips", led[3].a and led[3].b and led[1].z, true)
check("ledger output is sorted", T.ledger_format({ [3] = { b = true, a = true }, [1] = { z = true } }, "lib"),
    "lib,1,z\nlib,3,a\nlib,3,b\n")
check("an empty ledger formats to nothing", T.ledger_format({}), "")
check("a missing ledger file parses to empty", next(T.ledger_parse(nil).other) or next(T.ledger_parse(nil), "other"), nil)
do -- library column: other libraries' lines pass through, 2-field lines belong to the current library
    local l = T.ledger_parse("libA,7,F1|x\n9,F1|old\nlibB,9,F1|b\n", "libB")
    check("ledger_parse: another library's lines aren't ours", l[7], nil)
    check("ledger_parse: lines without a library column are ours", l[9] and l[9]["F1|old"] and l[9]["F1|b"], true)
    check("ledger_parse: the other library's lines are kept", table.concat(l.other, ";"), "libA,7,F1|x")
    local back = T.ledger_format(l, "libB")
    check("ledger_format: ours first, the other library's after", back, "libB,9,F1|b\nlibB,9,F1|old\nlibA,7,F1|x\n")
    check("ledger_format of an unchanged file is stable", T.ledger_format(T.ledger_parse(back, "libB"), "libB"), back)
    l[10] = { ["F1|gone"] = true }
    local pruned, skipped = T.ledger_prune(l, function(id) return id == 9 end)
    check("ledger_prune drops an image that's gone", pruned .. "," .. tostring(skipped) .. "," .. tostring(l[10]), "1,false,nil")
    pruned, skipped = T.ledger_prune(l, function() return false end)
    check("ledger_prune: nothing resolving means the lookup failed", pruned .. "," .. tostring(skipped) .. "," .. tostring(l[9] ~= nil), "0,true,true")
end
do -- plan_clear: the ledger alone decides what Clear detaches
    local ledger = { [7] = { ["F1|Ferrari"] = true, ["Assisted Tagging|Identification|By number"] = true } }
    local plans = T.plan_clear({ { id = 7, tags = { ["F1|Ferrari"] = true, ["Rally|2026|12"] = true } } }, ledger)
    check("plan_clear: detaches ledger tags still on the image, hand tags stay",
        #plans .. ":" .. plans[1].id .. ":" .. table.concat(plans[1].detach, ";"), "1:7:F1|Ferrari")
    ledger = { [7] = { ["Rally|2025|3"] = true, ["F1|Ferrari"] = true } }
    plans = T.plan_clear({ { id = 7, tags = { ["Rally|2025|3"] = true, ["F1|Ferrari"] = true } } }, ledger)
    check("plan_clear: another collection's ledger tags are removed too", table.concat(plans[1].detach, ";"), "F1|Ferrari;Rally|2025|3")
    plans = T.plan_clear({ { id = 8, tags = { ["F1|Ferrari"] = true, ["Assisted Tagging|Identification|By number"] = true } } },
        { [7] = { ["F1|Ferrari"] = true } })
    check("plan_clear: no ledger row, no plan", #plans, 0)
    local l = T.ledger_parse("libA,7,F1|x\n9,F1|old\n", "libB")
    l[9] = nil
    check("ledger_format after clear keeps other libraries' rows", T.ledger_format(l, "libB"), "libA,7,F1|x\n")
end
do -- hand-applied diagnostic / unidentified / number-seen tags are protected from detach
    local NS = T.DIAG_TAGS.number_seen
    local have = { [T.DIAG_TAGS.none] = true, [NS .. "|42"] = true, [T.DIAG_TAGS.number] = true, ["Holiday"] = true }
    local prot = T.hand_diag_tags(have, { [T.DIAG_TAGS.number] = true }, rules)
    check("hand_diag: the unidentified tag applied by hand", prot[T.DIAG_TAGS.none], true)
    check("hand_diag: a number-seen tag applied by hand", prot[NS .. "|42"], true)
    check("hand_diag: a ledgered diagnostic is the plugin's", prot[T.DIAG_TAGS.number], nil)
    check("hand_diag: a foreign tag is not a diagnostic", prot["Holiday"], nil)
    check("hand_diag: an entry tag is protected_tags' job, not this one's",
        T.hand_diag_tags({ ["F1|Ferrari"] = true }, {}, rules)["F1|Ferrari"], nil)
    local _, detach = T.tag_changes(have, T.wanted_tags({ row("number", "VER") }, entries), owned, T.owned_prefixes(rules), prot)
    check("hand_diag: a run detaches only the ledgered diagnostic", table.concat(detach, ","), T.DIAG_TAGS.number)
end

-- reference results.csv: id,status,colour_note,entry_id; older files have two or three columns
do
    local rows, notes = T.parse_reference_results("1,added,set,VER\n2,added,differs,HAM\n3,added,,\n4,stale\n5,added,set\n6,read,already,VER\n")
    check("reference results: every row parses", #rows, 6)
    check("reference results: four-column rows keep the entry id", rows[1][4], "VER")
    check("reference results: a 3-column row reads an empty entry id", rows[5][3] .. "|" .. rows[5][4], "set|")
    check("reference results: a 2-column row reads an empty note", rows[4][2] .. "|" .. rows[4][3] .. "|" .. rows[4][4], "stale||")
    check("reference results: colour notes are counted", notes.set .. "," .. notes.differs .. "," .. notes.already, "2,1,1")
    check("reference results: the done message names each count", table.concat(T.colour_note_extras(notes), "; "),
        "2 entries got a colour; 1 colour readings differ from entries.json (see log)")
    local _, none = T.parse_reference_results("1,added\n")
    check("reference results: no colour notes, nothing to add", #T.colour_note_extras(none), 0)
end

-- colour_summary: distinct entries per note, unread rows counted
do
    local rows = T.parse_reference_results("1,read,set,VER\n2,read,set,VER\n3,read,already,HAM\n4,unread,,\n")
    local n_set, n_already, n_unread = T.colour_summary(rows)
    check("colour_summary: distinct entries per note", n_set .. "," .. n_already .. "," .. n_unread, "1,1,1")
    check("colour_summary: nothing read, all zero", table.concat({ T.colour_summary({}) }, ","), "0,0,0,0")
    local failed = T.parse_reference_results("1,failed,,\n2,read,set,VER\n")
    check("colour_summary: failed rows are counted", table.concat({ T.colour_summary(failed) }, ","), "1,0,0,1")
end

local prot = T.protected_tags(
    { ["F1|Red Bull"] = true, ["F1|Red Bull|Verstappen"] = true, ["Holiday"] = true },
    { ["F1|Red Bull|Verstappen"] = true }, entries)
check("protected: an entry tag not in the ledger is the user's", prot["F1|Red Bull"], true)
check("protected: a ledgered tag is the plugin's", prot["F1|Red Bull|Verstappen"], nil)
check("protected: a non-entry tag is ignored", prot["Holiday"], nil)

-- hand tags that name an entry ---------------------------------------------------
do
    local he = T.parse_entries_csv(table.concat({
        "NOR,McLaren,4,M|Number|4;M|Driver|Norris;M|Team|McLaren,Norris",
        "PIA,McLaren,81,M|Number|81;M|Driver|Piastri;M|Team|McLaren,Piastri",
        "SCH1,Haas,47,M|Number|47;M|Driver|Schumacher,Schumacher",
        "SCH2,Prema,9,M|Number|9;M|Driver|Schumacher,Schumacher",
    }, "\n"))
    local roots = { number = "M|Number", driver = "M|Driver" }
    local function hand(have, ledger_set)
        local id, why = T.hand_entry(have, ledger_set or {}, he, roots)
        return tostring(id) .. "," .. tostring(why)
    end
    -- test_hand_entry_number
    check("hand_entry: a number tag names its entry", hand({ ["M|Number|4"] = true }), "NOR,nil")
    -- test_hand_entry_driver
    check("hand_entry: a driver tag names its entry", hand({ ["M|Driver|Piastri"] = true }), "PIA,nil")
    check("hand_entry: number and driver of one entry agree", hand({ ["M|Number|4"] = true, ["M|Driver|Norris"] = true }), "NOR,nil")
    -- test_hand_entry_ambiguous_driver
    local shared = { ["M|Driver|Schumacher"] = true }
    check("hand_entry: a shared driver name names no entry", hand(shared), "nil,ambiguous")
    check("hand_entry: the shared name is still protected", T.protected_tags(shared, {}, he, roots)["M|Driver|Schumacher"], true)
    check("hand_entry: a number settles a shared name", hand({ ["M|Driver|Schumacher"] = true, ["M|Number|47"] = true }), "SCH1,nil")
    check("hand_entry: a number outside the shared name disagrees",
        hand({ ["M|Driver|Schumacher"] = true, ["M|Number|4"] = true }), "nil,disagree")
    -- test_hand_entry_disagreeing_tags
    local both = { ["M|Number|4"] = true, ["M|Driver|Piastri"] = true }
    check("hand_entry: tags naming two entries name none", hand(both), "nil,disagree")
    local _, detach = T.tag_changes(both, {}, { ["M|Number|4"] = true, ["M|Driver|Piastri"] = true }, {},
        T.protected_tags(both, {}, he, roots))
    check("hand_entry: disagreeing tags are both kept", #detach, 0)
    -- test_hand_entry_ledgered
    check("hand_entry: a ledgered tag is the plugin's", hand({ ["M|Number|4"] = true }, { ["M|Number|4"] = true }), "nil,nil")
    -- test_unlisted_hand_number_protected
    local unlisted = { ["M|Number|88"] = true }
    check("hand_entry: an unlisted number names no entry", hand(unlisted), "nil,nil")
    check("protected: an unlisted hand number is kept", T.protected_tags(unlisted, {}, he, roots)["M|Number|88"], true)
    check("protected: without roots only entry tags are", T.protected_tags(unlisted, {}, he)["M|Number|88"], nil)
    check("protected: a ledgered unlisted number is the plugin's", T.protected_tags(unlisted, unlisted, he, roots)["M|Number|88"], nil)
    -- test_hand_team_is_hint_only
    local team = { ["M|Team|McLaren"] = true }
    check("hand_entry: a team tag names no entry",
        tostring((T.hand_entry(team, {}, he, { number = "M|Number", driver = "M|Driver", team = "M|Team" }))), "nil")
    check("hint: the hand team tag still hints", T.hint_tags(team, {}, he, "M|Team")["M|Team|McLaren"], true)
    -- test_hand_vehicle_protected_not_identifying
    local ford = { ["Assisted Tagging|Motorsport|Vehicle|Ford"] = true }
    check("hand_family_tags: vehicle root",
        T.hand_family_tags(ford, {}, { vehicle = "Assisted Tagging|Motorsport|Vehicle" })["Assisted Tagging|Motorsport|Vehicle|Ford"], true)
    check("hand_entry: a vehicle tag names no entry", tostring((T.hand_entry(ford, {}, he,
        { number = "M|Number", driver = "M|Driver", vehicle = "Assisted Tagging|Motorsport|Vehicle" }))), "nil")
    -- test_wanted_tags_hand_row
    local hw, hd, hok = T.wanted_tags({ { box = -1, method = "hand", entry_id = "NOR", alt_entry_id = "" } }, he)
    check("a hand result wants the entry's tags", keys(hw), "M|Driver|Norris + M|Number|4 + M|Team|McLaren")
    check("a hand result adds no diagnostic", keys(hd), "")
    check("a hand result counts as identified", hok, true)
    -- test_hand_entry_co_driver
    local rally = {
        ["12"] = { number = "12", name = "Smith", co_driver = "Jones" },
        ["14"] = { number = "14", name = "Lee", co_driver = "Kim" },
        ["15"] = { number = "15", name = "Ray", co_driver = "Kim" },
    }
    local rally_roots = { number = "M|Number", driver = "M|Driver", co_driver = "M|Co-driver" }
    local function co_hand(have)
        local id, why = T.hand_entry(have, {}, rally, rally_roots)
        return tostring(id) .. "," .. tostring(why)
    end
    check("hand_entry: a co-driver tag names its entry", co_hand({ ["M|Co-driver|Jones"] = true }), "12,nil")
    check("hand_entry: a shared co-driver names no entry", co_hand({ ["M|Co-driver|Kim"] = true }), "nil,ambiguous")
    check("hand_entry: a number settles a shared co-driver", co_hand({ ["M|Co-driver|Kim"] = true, ["M|Number|15"] = true }), "15,nil")
    check("hand_entry: a co-driver of another entry disagrees", co_hand({ ["M|Co-driver|Jones"] = true, ["M|Number|14"] = true }), "nil,disagree")
end

-- Find new entries ----------------------------------------------------------
do
    local NR, SEEN = "M|Number", "AT|Seen"
    local roots = { number = NR, team = "M|Team", driver = "M|Driver" }
    local ne = {
        ["12"] = { number = "12", team = "", name = "" },
        ["7"] = { number = "7", team = "Ferrari", name = "Leclerc" },
    }
    local function img(id, have, ledger_set) return { id = id, have = have, ledger_set = ledger_set or {} } end
    local function shape(rows)
        local out = {}
        for _, r in ipairs(rows) do
            out[#out + 1] = r.kind .. ":" .. r.number .. ":" .. r.value .. " r" .. table.concat(r.read, ",") .. " h" .. table.concat(r.hand, ",")
        end
        return table.concat(out, "; ")
    end
    -- test_new_entries_from_reads
    check("new entries: unlisted reads make one number row", shape(T.new_entry_candidates({
        img(1, { [SEEN .. "|115"] = true, [SEEN .. "|7"] = true }), img(2, { [SEEN .. "|115"] = true }),
    }, ne, roots, SEEN)), "number:115:115 r1,2 h")
    -- test_new_entries_from_hand_number
    check("new entries: an unlisted hand number makes a row; read too counts as hand", shape(T.new_entry_candidates({
        img(1, { [NR .. "|88"] = true, [SEEN .. "|88"] = true }), img(2, { [NR .. "|88"] = true }, { [NR .. "|88"] = true }),
    }, ne, roots, SEEN)), "number:88:88 r h1")
    -- test_new_entries_field_row
    local field = T.new_entry_candidates({
        img(1, { [NR .. "|12"] = true, ["M|Team|Ferrari"] = true }, { [NR .. "|12"] = true }),
        img(2, { [NR .. "|12"] = true, ["M|Team|Ferrari"] = true, ["M|Driver|Smith"] = true }),
    }, ne, roots, SEEN)
    check("new entries: hand team and driver on entry 12 make field rows", shape(field),
        "team:12:Ferrari r h1,2; driver:12:Smith r h2")
    check("new entries: a field row carries its entry", field[1].entry, "12")
    -- test_new_entries_field_already_set
    check("new entries: a field the entry has makes no row", shape(T.new_entry_candidates({
        img(1, { [NR .. "|7"] = true, ["M|Team|Sauber"] = true, ["M|Driver|Bearman"] = true }),
    }, ne, roots, SEEN)), "")
    -- test_new_entries_order
    check("new entries: most photos first, then number", shape(T.new_entry_candidates({
        img(1, { [SEEN .. "|115"] = true, [SEEN .. "|9"] = true, [SEEN .. "|30"] = true }),
        img(2, { [SEEN .. "|30"] = true }),
    }, ne, roots, SEEN)), "number:30:30 r1,2 h; number:9:9 r1 h; number:115:115 r1 h")
    check("new entries: a ledgered team tag makes no row", shape(T.new_entry_candidates({
        img(1, { [NR .. "|12"] = true, ["M|Team|Ferrari"] = true }, { ["M|Team|Ferrari"] = true }),
    }, ne, roots, SEEN)), "")
    check("new entries: an entry's id or a 4-digit number makes no row", shape(T.new_entry_candidates({
        img(1, { [SEEN .. "|5"] = true, [SEEN .. "|1234"] = true, [NR .. "|5"] = true }),
    }, { ["5"] = { number = "55", team = "", name = "" } }, roots, SEEN)), "")
    check("new entries: a team or driver holding , ; or \" makes no row", shape(T.new_entry_candidates({
        img(1, { [NR .. "|12"] = true, ["M|Team|Smith, Jones"] = true, ["M|Driver|O\"Neil"] = true }),
    }, ne, roots, SEEN)), "")
    check("candidate_label: read", T.candidate_label({ kind = "number", number = "115", value = "115", read = { 1, 2 }, hand = {} }),
        "115    read on 2 photos")
    check("candidate_label: both ways, one photo", T.candidate_label({ kind = "number", number = "88", value = "88", read = { 1 }, hand = { 2, 3 } }),
        "88    read on 1 photo, hand-tagged on 2 photos")
    check("candidate_label: field", T.candidate_label({ kind = "team", entry = "12", number = "12", value = "Ferrari", read = {}, hand = { 1 } }),
        "12: team Ferrari    hand-tagged on 1 photo")
    -- test_same_field_twice
    local t1 = { kind = "team", entry = "12", number = "12", value = "Ferrari" }
    local t2 = { kind = "team", entry = "12", number = "12", value = "AF Corse" }
    check("check_additions: two teams for one entry", T.check_additions({ t1, t2 }, roots),
        "Entry 12 has two ticked teams: Ferrari, AF Corse. Tick one.")
    -- test_number_family_off
    check("check_additions: number family off", T.check_additions({ { kind = "number", number = "115", value = "115" } }, { team = "M|Team" }),
        "Turn on the number family before adding numbers: a new entry needs a tag.")
    -- test_none_ticked
    check("check_additions: nothing ticked", T.check_additions({}, roots), "Nothing ticked.")
    check("check_additions: a number and one team pass", tostring(T.check_additions({ t1, { kind = "number", number = "115", value = "115" } }, roots)), "nil")
    check("addition_rows: number and field rows", T.csv_line(T.addition_rows({ { kind = "number", number = "115" } })[1]) .. " / "
        .. T.csv_line(T.addition_rows({ { kind = "driver", entry = "12", value = "Smith" } })[1]),
        '"number","115" / "field","12","name","Smith"')
    -- test_new_entries_split
    local co_roots = { number = NR, team = "M|Team", driver = "M|Driver", co_driver = "M|Co-driver" }
    local rally = {
        ["21"] = { number = "21", name = "Smith / Jones" },
        ["22"] = { number = "22", name = "A / B / C" },
        ["23"] = { number = "23", name = "Smith / " },
        ["24"] = { number = "24", name = "Lee / Kim", co_driver = "Kim" },
        ["25"] = { number = "25", name = "Ray" },
    }
    local split = T.new_entry_candidates({ img(1, { [NR .. "|21"] = true }) }, rally, co_roots, SEEN)
    check("new entries: an entry named \"A / B\" makes a split row", shape(split), "split:21:Smith / Jones r1 h")
    check("new entries: a split row carries both halves", split[1].driver .. "|" .. split[1].co_driver, "Smith|Jones")
    check("new entries: three names, an empty half or a co-driver already set make no split row",
        shape(T.new_entry_candidates({ img(1, { [NR .. "|22"] = true }), img(2, { [NR .. "|23"] = true }),
            img(3, { [NR .. "|24"] = true }) }, rally, co_roots, SEEN)), "")
    check("new entries: a hand co-driver tag makes a co_driver row", shape(T.new_entry_candidates({
        img(1, { [NR .. "|25"] = true, ["M|Co-driver|Moss"] = true }) }, rally, co_roots, SEEN)), "co_driver:25:Moss r h1")
    check("candidate_label: split", T.candidate_label(split[1]),
        '21: split "Smith / Jones" → driver Smith, co-driver Jones    read on 1 photo')
    check("candidate_label: co-driver", T.candidate_label({ kind = "co_driver", entry = "25", number = "25", value = "Moss", read = {}, hand = { 1 } }),
        "25: co-driver Moss    hand-tagged on 1 photo")
    local s21 = split[1]
    check("check_additions: a split and a co-driver", T.check_additions({ s21,
        { kind = "co_driver", entry = "21", number = "21", value = "Jones" } }, co_roots),
        "Entry 21 has a split and a co-driver ticked. Tick one.")
    check("check_additions: a split and a driver", T.check_additions({ s21,
        { kind = "driver", entry = "21", number = "21", value = "Smith" } }, co_roots),
        "Entry 21 has a split and a driver ticked. Tick one.")
    check("check_additions: a split alone passes", tostring(T.check_additions({ s21 }, co_roots)), "nil")
    check("addition_rows: split and co_driver rows", T.csv_line(T.addition_rows({ s21 })[1]) .. " / "
        .. T.csv_line(T.addition_rows({ { kind = "co_driver", entry = "25", value = "Moss" } })[1]),
        '"split","21" / "field","25","co_driver","Moss"')
end

-- test_open_command
local pp_new = T.parse_progress("analysing,12,40,10")
check("parse_progress: a staged line", pp_new.stage .. " " .. pp_new.cur .. "/" .. pp_new.tot .. " " .. pp_new.cached,
    "analysing 12/40 10")
local pp_old = T.parse_progress("3,9")
check("parse_progress: an old cur,tot line has no stage and nothing cached",
    tostring(pp_old.stage) .. " " .. pp_old.cur .. "/" .. pp_old.tot .. " " .. pp_old.cached, "nil 3/9 0")
check("parse_progress: no line yet", T.parse_progress(nil), nil)
check("parse_progress: a two-word stage", T.parse_progress("writing tags,1,2,0").stage, "writing tags")

check("open_command: Windows", T.open_command("C:/My Photos/Rallye/entries.json", "windows"),
    'start "" "C:\\My Photos\\Rallye\\entries.json"')
check("open_command: macOS", T.open_command("/Users/me/My Photos/entries.json", "macos"), "open '/Users/me/My Photos/entries.json'")
check("open_command: Linux", T.open_command("/home/me/My Photos/entries.json", "linux"), "xdg-open '/home/me/My Photos/entries.json'")

local hint_have = { ["F1|Red Bull"] = true, ["F1|Red Bull|Verstappen"] = true, ["F1|Ferrari"] = true, ["Holiday"] = true }
local hint = T.hint_tags(hint_have, { ["F1|Ferrari"] = true }, entries, "F1")
check("hint: a user-applied team tag hints", hint["F1|Red Bull"], true)
check("hint: a tag under the team tag is not a hint", hint["F1|Red Bull|Verstappen"], nil)
check("hint: a ledgered tag is the plugin's, not a hint", hint["F1|Ferrari"], nil)
check("hint: a non-entry tag is ignored", hint["Holiday"], nil)
check("hint: another root's team tag is not a hint", next(T.hint_tags(hint_have, {}, entries, "Assisted Tagging|Motorsport|Team")), nil)
check("hint: team family off, no hints", next(T.hint_tags(hint_have, {}, entries, nil)), nil)

attach, detach = T.tag_changes({ ["F1|Red Bull"] = true, ["F1|Red Bull|Verstappen"] = true },
    T.wanted_tags({ row("none") }, entries), owned, nil, { ["F1|Red Bull"] = true })
check("a protected tag is never detached", table.concat(detach, ","), "F1|Red Bull|Verstappen")

-- ledgered tags of renamed / removed entries (audit M1)
local roots = T.owned_roots(entries, rules)
check("owned_roots: entry roots", roots["F1"], true)
check("owned_roots: diagnostics root is not one", roots["Assisted Tagging"], nil)
local mine = { ["F1|Red Bull|Old name"] = true, ["MotoGP|Ducati"] = true,
               ["Assisted Tagging|Run|2026-11-09 10:00"] = true }
local extra = T.ledgered_owned(mine, roots)
check("ledgered_owned: a stale tag under the collection's root", extra["F1|Red Bull|Old name"], true)
check("ledgered_owned: another collection's tag stays out", extra["MotoGP|Ducati"], nil)
check("ledgered_owned: the run stamp stays out", extra["Assisted Tagging|Run|2026-11-09 10:00"], nil)
check("ledgered_owned: no ledger is nothing", next(T.ledgered_owned(nil, roots)), nil)
attach, detach = T.tag_changes(
    { ["F1|Red Bull|Old name"] = true, ["MotoGP|Ducati"] = true, ["F1|Red Bull|Hand"] = true },
    T.wanted_tags({ row("number", "VER") }, entries), owned, nil, nil, extra)
check("a renamed entry's ledgered tag is detached; others stay", table.concat(detach, ","), "F1|Red Bull|Old name")

w, d, ok = T.wanted_tags({ { box = 0, method = "conflict", entry_id = "VER", alt_entry_id = "", shot = "solo" } },
    entries, rules)
check("a conflict-only image gets no unidentified tags", keys(w), "")
check("a conflict-only image gets no none diagnostic", keys(d), "Assisted Tagging|Identification|Shot|Solo")
check("a conflict is not identified", ok, false)
w, d, ok = T.wanted_tags({
    { box = 0, method = "conflict", entry_id = "VER", alt_entry_id = "", shot = "pack" },
    { box = 1, method = "number", entry_id = "HAM", alt_entry_id = "", shot = "pack" },
}, entries, rules)
check("a pack still tags its other cars beside a conflict", keys(w), "F1|Ferrari + F1|Ferrari|Hamilton")
check("a pack adds its shot diagnostic once", keys(d),
    "Assisted Tagging|Identification|By number + Assisted Tagging|Identification|Shot|Pack")

-- pythonw_of (Windows launches through pythonw.exe beside the chosen python.exe) --
check("pythonw_of: venv python.exe", T.pythonw_of("C:/x/.venv/Scripts/python.exe"), "C:/x/.venv/Scripts/pythonw.exe")
check("pythonw_of: case-insensitive", T.pythonw_of("C:\\Py\\Python.EXE"), "C:\\Py\\pythonw.exe")
check("pythonw_of: bare python on PATH", T.pythonw_of("python"), "pythonw")
check("pythonw_of: other launcher is refused", T.pythonw_of("C:/Windows/py.exe"), nil)

-- hierarchical_tags / sanitize_id -------------------------------------------
check("hierarchical_tags keeps only tags with a hierarchy", table.concat(T.hierarchical_tags({
    "F1|Red Bull|Verstappen", "Holiday", "F1|Red Bull",
}), ","), "F1|Red Bull,F1|Red Bull|Verstappen")
check("hierarchical_tags drops the plugin's own diagnostics", table.concat(T.hierarchical_tags({
    "F1|Red Bull", "Assisted Tagging|Identification|Unidentified",
}), ","), "F1|Red Bull")
check("hierarchical_tags drops a tag entries.json can't hold", table.concat(T.hierarchical_tags({
    "F1|Red Bull", 'F1|Red,Bull',
}), ","), "F1|Red Bull")
check("sanitize_id replaces folder-unsafe characters", T.sanitize_id("Max/Verstappen"), "Max-Verstappen")
check("sanitize_id trims whitespace", T.sanitize_id("  Hamilton  "), "Hamilton")
check("sanitize_id falls back on an empty name", T.sanitize_id(""), "entry")

-- derive_entries / entries_json (new collection bootstrap) -------------------
local function img(key, tags) return { key = key, tags = tags } end

check("entries need at least this many samples of their tag", T.MIN_REFS_PER_ENTRY, 2)

local derived, entry_of, skipped, thin = T.derive_entries({
    img("1a", { "F1|Red Bull", "F1|Red Bull|Verstappen", "Holiday" }),
    img("1b", { "F1|Red Bull", "F1|Red Bull|Verstappen" }),
    img("2a", { "F1|Red Bull", "F1|Red Bull|Tsunoda" }),
    img("2b", { "F1|Red Bull", "F1|Red Bull|Tsunoda" }),
    img("3", { "F1|Safety Car" }),
    img("4", { "Holiday" }),
})
check("one entry per distinct tag set with enough samples", #derived, 2)
check("derive_entries skips images with no hierarchical tag", table.concat(skipped, ","), "4")
check("a tag only one image carries doesn't become an entry", table.concat(thin, ","), "3")
check("the deepest tag seeds the id", derived[1].id, "Verstappen")
check("a tag shared by only some groups becomes the team", derived[1].team, "Red Bull")
check("teammates share the same team", derived[2].team, "Red Bull")
check("a non-numeric leaf sets no race number", derived[1].number, "")
check("entry_of maps each sampled image to its entry",
    entry_of["1a"] .. "/" .. entry_of["1b"] .. "/" .. entry_of["2a"], "Verstappen/Verstappen/Tsunoda")
check("a thin group's images aren't mapped to an entry", entry_of["3"], nil)

local numbered = T.derive_entries({
    img("1a", { "Car|Number|44" }),
    img("1b", { "Car|Number|44" }),
    img("2a", { "Car|Number|1" }),
    img("2b", { "Car|Number|1" }),
})
check("a numeric leaf becomes the race number", numbered[1].number, "44")
check("a numeric leaf also seeds the id", numbered[1].id, "44")
check("no shared tag between numbers means no team", numbered[1].team, "")
check("a 4-digit leaf isn't mistaken for a race number", T.derive_entries({
    img("1a", { "Car|Number|1234" }),
    img("1b", { "Car|Number|1234" }),
})[1].number, "")

local dup = T.derive_entries({
    img("1a", { "A|X" }),
    img("1b", { "A|X" }),
    img("2a", { "B|X" }),
    img("2b", { "B|X" }),
})
check("a colliding id gets a numeric suffix", dup[1].id .. "," .. dup[2].id, "X,X-2")

local j = T.entries_json({
    { id = "VER", number = "1", team = "Red Bull", tags = { "F1|Red Bull", "F1|Red Bull|Verstappen", "F1|Champion" } },
})
check("entries_json emits the entries object", j:match('^{\n  "entries": %[') ~= nil, true)
check("entries_json quotes every field", j:find('"id": "VER"', 1, true) ~= nil, true)
check("entries_json emits the number field", j:find('"number": "1"', 1, true) ~= nil, true)
check("entries_json emits the tag array", j:find('"tags": ["F1|Red Bull", "F1|Red Bull|Verstappen", "F1|Champion"]', 1, true) ~= nil,
    true)
check("entries_json writes no rules", j:find('"rules"', 1, true), nil)

require("test_preset_block")(T, check)

do
    local d = T.preset_defaults(T.PRESET_SCHEMA)
    -- the key list itself is checked against settings.py by test_settings.py (lua schema keys)
    local seen, twice = {}, {}
    for _, s in ipairs(T.PRESET_SCHEMA) do
        if seen[s.key] then twice[#twice + 1] = s.key end
        seen[s.key] = true
    end
    check("tagging schema: no key twice", table.concat(twice, ","), "")
    check("colour keys default on", tostring(d.family_colour) .. tostring(d.tag_check_colour), "truetrue")
    for _, f in ipairs(T.FAMILIES) do
        check("family " .. f.key .. " defaults", tostring(d["family_" .. f.key]) .. " " .. d["family_" .. f.key .. "_root"],
            tostring(f.key ~= "sponsor") .. " " .. f.default_root)
    end
    check("tagging defaults", table.concat({ tostring(d.use_hints), d.group_support, d.group_node,
        tostring(d.run_tag), tostring(d.suggest_crops), tostring(d.quarantine),
        tostring(d.neighbour_tolerance) }, " "), "true native  none false false 5")
    local all_on = true
    for _, item in ipairs(T.PRESET_SCHEMA) do
        if item.key:match("^tag_") and item.kind == "bool" and d[item.key] ~= true then all_on = false end
    end
    check("every tag switch defaults on", all_on, true)
    check("tolerance 3 kept", (T.preset_merge(T.PRESET_SCHEMA, { neighbour_tolerance = 3 })).neighbour_tolerance, 3)
    local merged, problems = T.preset_merge(T.PRESET_SCHEMA, { order_weight = "" })
    check("stored blank order_weight is the default", merged.order_weight, 0)
    check("stored blank order_weight is no problem", #problems, 0)
    local r = T.parse_rules_csv("order_weight,0.5\nneighbour_tolerance,5\nblur_references,true\nfrom_entries_json,order_weight;blur_references")
    check("rules.csv: order_weight number", r.settings.order_weight, 0.5)
    check("rules.csv: neighbour_tolerance number", r.settings.neighbour_tolerance, 5)
    check("rules.csv: blur_references boolean", r.settings.blur_references, true)
    check("rules.csv: from_entries_json keys", table.concat(r.from_entries_json, ";"), "order_weight;blur_references")
    check("rules.csv: empty from_entries_json", #T.parse_rules_csv("from_entries_json,").from_entries_json, 0)
end

do -- run_settings_text_round_trips: every key non-default survives encode → decode → merge
    local values = {}
    for _, item in ipairs(T.PRESET_SCHEMA) do
        local v = item.default
        if item.kind == "bool" then v = not v
        elseif item.kind == "number" then v = item.key == "min_face_px" and 64
            or item.key == "neighbour_tolerance" and 3 or v == 0 and 0.25 or v / 2
        elseif item.kind == "choice" then v = item.choices[2]
        else v = item.key:match("_name$") and "Custom|" .. item.key or "x " .. item.key end
        values[item.key] = v
    end
    local back, problems = T.preset_merge(T.PRESET_SCHEMA,
        T.preset_decode(T.preset_encode(T.PRESET_SCHEMA, values)))
    local differing = {}
    for _, item in ipairs(T.PRESET_SCHEMA) do
        if back[item.key] ~= values[item.key] or values[item.key] == item.default then
            differing[#differing + 1] = item.key
        end
    end
    check("run_settings_text_round_trips", table.concat(differing, ",") .. "/" .. #problems, "/0")
end

do -- backfill_settings: entries.json rules fill only missing, blank or invalid stored values
    local r = T.default_rules()
    r.settings = { order_weight = 0.5, min_read = 0.9 }
    r.from_entries_json = { "order_weight", "min_read" }
    local text, copied = T.backfill_settings('{ "order_weight": 0.3 }', r)
    local back = T.preset_decode(text or "{}")
    check("backfill_adds_only_missing", tostring(back.min_read) .. "/" .. tostring(back.order_weight)
        .. "/" .. table.concat(copied or {}, ","), "0.9/0.3/min_read")
    check("backfill_adds_only_missing: text", (text or ""):find('"min_read": 0.9', 1, true) ~= nil
        and text:find('"order_weight": 0.3', 1, true) ~= nil, true)

    check("backfill_noop_returns_nil", T.backfill_settings('{ "order_weight": 0.3, "min_read": 0.8 }', r), nil)
    local none = T.default_rules()
    check("backfill_noop_returns_nil: nothing from entries.json", T.backfill_settings("{}", none), nil)
    check("backfill: unreadable settings.json left alone", T.backfill_settings("{ not json", r), nil)

    local blank = T.preset_decode(T.backfill_settings('{ "order_weight": "", "min_read": 0.8 }', r) or "{}")
    check("backfill_overwrites_blank", blank.order_weight, 0.5)
    local out_of_range = T.preset_decode(T.backfill_settings('{ "order_weight": 3, "min_read": 0.8 }', r) or "{}")
    check("backfill: out-of-range stored value replaced", out_of_range.order_weight, 0.5)

    local d = T.default_rules()
    d.diag.burst = ""
    d.diag.livery = "Old|By livery"
    d.diag.shot_solo, d.diag.shot_pack, d.diag.shot_crowded = "Old|Shot|Solo", "Old|Shot|Pack", "Old|Shot|Crowded"
    d.from_entries_json = { "tag_burst", "tag_livery_name", "tag_shot_name" }
    local tags = T.preset_decode(T.backfill_settings("{}", d) or "{}")
    check("backfill: tag keys from the diagnostic names", tostring(tags.tag_burst) .. "/" .. tostring(tags.tag_livery_name)
        .. "/" .. tostring(tags.tag_shot_name), "false/Old|By livery/Old|Shot")

    check("run_settings_path", T.run_settings_path("/tmp/dt_assisted_tagging_1_2_"), "/tmp/dt_assisted_tagging_1_2_settings.run.json")
end

do
    local text, copied = T.upgrade_settings_text('{"tag_shot":false,"tag_shot_name":"My|Shot"}')
    local back = T.preset_decode(text)
    check("upgrade_settings_text: copies tag_shot into tag_shot_crowded", back.tag_shot_crowded, false)
    check("upgrade_settings_text: copies tag_shot_name into tag_shot_crowded_name", back.tag_shot_crowded_name, "My|Shot")
    check("upgrade_settings_text: reports both keys", table.concat(copied, ","), "tag_shot_crowded,tag_shot_crowded_name")
    local both = '{"tag_shot":false,"tag_shot_crowded":true,"tag_shot_crowded_name":"X"}'
    local same, none = T.upgrade_settings_text(both)
    check("upgrade_settings_text: no-op when both present", tostring(same == both) .. tostring(none), "truenil")
    same, none = T.upgrade_settings_text("{ not json")
    check("upgrade_settings_text: no-op on text that is not JSON", tostring(same == "{ not json") .. tostring(none), "truenil")
    local on_text, on_keys = T.upgrade_settings_text(both:sub(1, -2) .. ',"run_tag":true}')
    check("upgrade_settings_text: run_tag true becomes all", T.preset_decode(on_text).run_tag, "all")
    check("upgrade_settings_text: reports run_tag", table.concat(on_keys, ","), "run_tag")
    local off_text = T.upgrade_settings_text(both:sub(1, -2) .. ',"run_tag":false}')
    check("upgrade_settings_text: run_tag false becomes none", T.preset_decode(off_text).run_tag, "none")
end

do -- model auto-pick: first installed file on each job's best-first list
    local function present_of(names)
        local set = {}
        for _, n in ipairs(names) do set[n] = true end
        return function(file) return set[file] == true end
    end
    local picked, missing = T.pick_model({ "a", "b", "c" }, present_of({ "b", "c" }))
    check("pick first present", picked .. " " .. table.concat(missing, ","), "b a")
    picked, missing = T.pick_model({ "a", "b", "c" }, present_of({ "a", "b", "c" }))
    check("pick best present", picked .. " " .. #missing, "a 0")
    picked, missing = T.pick_model({ "a", "b", "c" }, present_of({}))
    check("none present", tostring(picked) .. " " .. table.concat(missing, ","), "nil a,b,c")

    local reader = T.MODEL_LISTS["number reader"]
    local on_disk = present_of({ "m/en_PP-OCRv5_mobile_rec.onnx", "m/text_recognition_CRNN_EN_2021sep.onnx" })
    picked = T.pick_model(reader.files, function(file) return T.model_present("m/" .. file, reader.job, on_disk) end)
    check("paddle reader without yml is skipped", picked, "text_recognition_CRNN_EN_2021sep.onnx")
    on_disk = present_of({ "m/en_PP-OCRv5_mobile_rec.onnx", "m/en_PP-OCRv5_mobile_rec.yml" })
    picked = T.pick_model(reader.files, function(file) return T.model_present("m/" .. file, reader.job, on_disk) end)
    check("paddle reader with yml is picked", picked, "en_PP-OCRv5_mobile_rec.onnx")
    on_disk = present_of({ "m/PP-OCRv6_small_rec.onnx", "m/PP-OCRv6_small_rec.yml", "m/en_PP-OCRv5_mobile_rec.onnx",
        "m/en_PP-OCRv5_mobile_rec.yml" })
    picked = T.pick_model(reader.files, function(file) return T.model_present("m/" .. file, reader.job, on_disk) end)
    check("v5 mobile wins over the v6 small trial reader", picked, "en_PP-OCRv5_mobile_rec.onnx")
    local finder = T.MODEL_LISTS["text finder"]
    check("v3 text finder needs no yml", T.model_present("m/text_detection_en_ppocrv3_2023may.onnx", finder.job,
        present_of({ "m/text_detection_en_ppocrv3_2023may.onnx" })), true)
    check("v6 text finder without yml is skipped", T.model_present("m/PP-OCRv6_small_det.onnx", finder.job,
        present_of({ "m/PP-OCRv6_small_det.onnx" })), false)
    picked = T.pick_model(finder.files, function(file) return T.model_present("m/" .. file, finder.job,
        present_of({ "m/PP-OCRv6_small_det.onnx", "m/PP-OCRv6_small_det.yml" })) end)
    check("v6 text finder with yml is picked when v3 is moved aside", picked, "PP-OCRv6_small_det.onnx")

    local choice = T.model_choice(T.MODEL_LISTS["segmenter"], present_of({}))
    check("optional job with nothing installed picks nil",
        tostring(choice.file) .. " " .. tostring(choice.err) .. " " .. choice.line, "nil nil segmenter: none installed")
    choice = T.model_choice(T.MODEL_LISTS["face detector"], present_of({}))
    check("face detector is optional", tostring(choice.file) .. " " .. tostring(choice.err), "nil nil")
    choice = T.model_choice(reader, present_of({}))
    check("required job with nothing installed is an error", choice.err, T.missing_model_message(reader))
    check("missing reader names the base reader and its yml", T.missing_model_message(reader),
        'Assisted Tagging: no number reader model in models/. Install en_PP-OCRv5_mobile_rec.onnx and its .yml (README, "Models").')
    check("missing text finder names its base", T.missing_model_message(T.MODEL_LISTS["text finder"]),
        'Assisted Tagging: no text finder model in models/. Install text_detection_en_ppocrv3_2023may.onnx (README, "Models").')

    on_disk = present_of({ "m/en_PP-OCRv5_mobile_rec.onnx", "m/text_recognition_CRNN_EN_2021sep.onnx" })
    choice = T.model_choice(reader, function(file) return T.model_present("m/" .. file, reader.job, on_disk) end,
        function(file) return on_disk("m/" .. file) end)
    check("reader without yml is logged as missing its yml", choice.line,
        "number reader: text_recognition_CRNN_EN_2021sep.onnx (better, not installed: PP-OCRv5_server_rec.onnx)"
        .. " (better, no .yml beside it: en_PP-OCRv5_mobile_rec.onnx)")

    local box_check = T.MODEL_LISTS["box check"]
    check("SigLIP 2 siblings", table.concat(T.model_siblings("m/siglip2_base_vision.onnx", box_check.job), ","),
        "m/siglip2_base_text.onnx,m/siglip2_base_tokenizer.json")
    check("other jobs have no siblings", #T.model_siblings("m/dinov2_base.onnx", "livery embedder"), 0)
    on_disk = present_of({ "m/siglip2_base_vision.onnx", "m/siglip2_base_text.onnx", "m/siglip2_base_tokenizer.json" })
    check("SigLIP 2 with both siblings is present",
        T.model_present("m/siglip2_base_vision.onnx", box_check.job, on_disk), true)
    on_disk = present_of({ "m/siglip2_base_vision.onnx", "m/siglip2_base_text.onnx" })
    check("SigLIP 2 without its tokenizer is not present",
        T.model_present("m/siglip2_base_vision.onnx", box_check.job, on_disk), false)
    choice = T.model_choice(box_check, function(file) return T.model_present("m/" .. file, box_check.job, on_disk) end,
        function(file) return on_disk("m/" .. file) end)
    check("SigLIP 2 without its tokenizer is an error", choice.err,
        'Assisted Tagging: siglip2_base_vision.onnx needs siglip2_base_tokenizer.json beside it in models/ (README, "Models").')
    choice = T.model_choice(box_check, present_of({}), present_of({}))
    check("box check is optional", tostring(choice.file) .. " " .. tostring(choice.err), "nil nil")

    check("pick log line", T.pick_log_line("livery embedder", "dinov2_base.onnx", { "dinov2_large.onnx" }),
        "livery embedder: dinov2_base.onnx (better, not installed: dinov2_large.onnx)")
    check("pick log line, best installed", T.pick_log_line("livery embedder", "dinov2_large.onnx", {}),
        "livery embedder: dinov2_large.onnx")

    local jobs = {}
    for _, item in ipairs(T.MODEL_LISTS) do jobs[#jobs + 1] = item.job end
    check("model jobs in log order", table.concat(jobs, ","),
        "vehicles,segmenter,text finder,number reader,livery embedder,box check,face detector,face recognizer")
    local bases = {}
    for _, item in ipairs(T.MODEL_LISTS) do bases[#bases + 1] = item.files[#item.files] end
    check("each list ends in today's file or a model on trial", table.concat(bases, ","),
        "object_detection_yolox_2022nov.onnx,image_segmentation_efficientsam_ti_2025april.onnx,"
        .. "PP-OCRv6_small_det.onnx,PP-OCRv6_small_rec.onnx,dinov2_small.onnx,"
        .. "siglip2_base_vision.onnx,face_detection_yunet_2023mar.onnx,face_recognition_sface_2021dec.onnx")
end

print("")
if failures == 0 then
    print("all tests passed")
    os.exit(0)
else
    print(failures .. " test(s) failed")
    os.exit(1)
end
