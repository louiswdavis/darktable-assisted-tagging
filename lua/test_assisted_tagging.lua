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
local COMMON_HASH = "069ea47d"
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
check("shell_quote: Windows escapes quotes and doubles %", PC.shell_quote('C:\\x %y% "z"', true), '"C:\\x %%y%% \\"z\\""')
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
check("newest_group_node picks the greatest stamp",
    T.newest_group_node({ { G10 .. "|0001" }, { "F1|Ferrari", G12 .. "|0001" } }), G12)
check("newest_group_node ignores other tags", T.newest_group_node({ { "F1|Ferrari" } }), nil)
check("newest_group_node with empty input", T.newest_group_node({}), nil)

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
check("parse_setting: tag name with a comma refused", parsed("tag_colour_name", "Cars,Paint"), "nil err")

-- panel_value: what read_panel makes of an entry
check("panel_value: blank number is the default", T.panel_value("min_read", "  "), 0.85)
check("panel_value: blank tag name is the default", T.panel_value("tag_colour_name", ""), "Assisted Tagging|Colour")
local pv, pv_why = T.panel_value("order_weight", "0,5")
check("panel_value: 0,5 refused", pv, nil)
check("panel_value: the message names the key", pv_why:sub(1, 14), "order_weight: ")
pv, pv_why = T.panel_value("tag_colour_name", "Cars,Paint")
check("panel_value: tag name with a comma refused", pv, nil)
check("panel_value: tag name message names the key", pv_why:sub(1, 17), "tag_colour_name: ")
check("panel_value: valid number", T.panel_value("neighbour_tolerance", "4"), 4)

-- tag_row_label: a gated tag switch says in its label why it is off
local toggles_by_key = {}
for _, t in ipairs(T.TAG_TOGGLES) do toggles_by_key[t.key] = t end
local function row_label(key, s)
    local label, gated = T.tag_row_label(toggles_by_key[key], s)
    return label .. (gated and " [gated]" or "")
end
check("tag_row_label: Colour gated by colour_tags off", row_label("colour", { colour_tags = false }),
      "Colour (off: read car colour is off) [gated]")
check("tag_row_label: Colour with colour_tags on", row_label("colour", { colour_tags = true }), "Colour")
check("tag_row_label: Check colour gated by colour_tags missing", row_label("check_colour", {}),
      "Check colour (off: read car colour is off) [gated]")
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
check("tag_rows_in_order: outputs, checks, then diagnostics", table.concat(ordered, ","),
    "colour,check_order,none,check_colour,shot,shot_crowded,number,livery,burst,pooled,neighbour,team,number_seen")
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
cs.min_sim, cs.margin, cs.tag_team_name, cs.order_weight = 0, 1, "A,B", 0.3
local fixed, replaced = T.checked_settings(cs)
check("checked_settings: out-of-range and bad names replaced", table.concat(replaced, " "), "min_sim margin tag_team_name")
check("checked_settings: min_sim back to default", fixed.min_sim, 0.5)
check("checked_settings: bad tag name back to default", fixed.tag_team_name, "Assisted Tagging|Identification|Team only")
check("checked_settings: a valid value kept", fixed.order_weight, 0.3)
check("checked_settings: the given settings untouched", cs.min_sim, 0)
-- A settings.json lacking a key: the panel shows that key's default, and nothing is logged.
local sparse = { min_sim = 0 }
local filled, sparse_replaced = T.checked_settings(sparse)
check("checked_settings: missing name key gets the default", filled.tag_colour_name, "Assisted Tagging|Colour")
check("checked_settings: missing number key gets the default", filled.min_read, 0.85)
check("checked_settings: missing keys are not listed as replaced", table.concat(sparse_replaced, " "), "min_sim")
check("checked_settings: an invalid key is still replaced and listed", filled.min_sim, 0.5)

-- named_rules: switched-off diagnostics keep their names (rules.csv leaves them blank)
local off_s = T.preset_defaults(T.PRESET_SCHEMA)
off_s.tag_colour, off_s.tag_shot = false, false
off_s.tag_shot_name = "My|Shot"
off_s.tag_shot_crowded_name = "My|Framing"
local blank_rules = T.parse_rules_csv("diag_colour,\ndiag_shot_solo,\n")
local named = T.named_rules(blank_rules, off_s)
local named_has_colour = false
for _, p in ipairs(T.owned_prefixes(named)) do
    if p == "Assisted Tagging|Colour|" then named_has_colour = true end
end
check("named_rules: colour off still owns the colour prefix", named_has_colour, true)
check("named_rules: shot_crowded from tag_shot_crowded_name", named.diag.shot_crowded, "My|Framing|Crowded")
check("named_rules: solo and pack from tag_shot_name", named.diag.shot_solo .. " " .. named.diag.shot_pack, "My|Shot|Solo My|Shot|Pack")
check("named_rules: off diagnostic still owned", T.owned_tags({}, named)["My|Shot|Solo"], true)
check("named_rules: leaves the rules it was given alone", blank_rules.diag.colour, "")

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
    local CB = "Assisted Tagging|Colour"
    local ident, unident, none_box = row("number", "VER"), row("none"), row("none")
    ident.colour, unident.colour, none_box.colour = "Red", "Blue", "Red"
    none_box.box = -1
    local _w, dd = T.wanted_tags({ ident }, entries)
    check("identified row gets the colour tag", dd[CB .. "|Red"], true)
    _w, dd = T.wanted_tags({ unident }, entries)
    check("unidentified row gets the colour tag", dd[CB .. "|Blue"], true)
    _w, dd = T.wanted_tags({ none_box }, entries)
    check("box -1 row gets no colour tag", dd[CB .. "|Red"], nil)
    local no_colour = T.default_rules()
    no_colour.diag.colour = ""
    _w, dd = T.wanted_tags({ ident }, entries, no_colour)
    check("colour rule blank writes no colour tag", dd[CB .. "|Red"], nil)
    local fl = row("number", "VER")
    fl.colour, fl.colour_flag = "Red", true
    _w, dd = T.wanted_tags({ fl }, entries)
    check("colour flag adds Check colour", dd["Assisted Tagging|Identification|Check colour"], true)
    _w, dd = T.wanted_tags({ fl }, entries, T.mask_diag(T.default_rules(), { colour = true }))
    check("mask_diag: colour off blanks colour", dd[CB .. "|Red"], nil)
    _w, dd = T.wanted_tags({ fl }, entries, T.mask_diag(T.default_rules(), { check_colour = true }))
    check("mask_diag: check_colour off blanks it", dd["Assisted Tagging|Identification|Check colour"], nil)
    check("owned: colour check tag", T.owned_tags(entries, rules)["Assisted Tagging|Identification|Check colour"], true)
    local pre = T.owned_prefixes(rules)
    local has = false
    for _, p in ipairs(pre) do if p == CB .. "|" then has = true end end
    check("owned_prefixes includes the colour base", has, true)
    check("hand_colour: one hand colour", T.hand_colour({ [CB .. "|Red"] = true }, {}, CB), "Red")
    check("hand_colour: two colours", T.hand_colour({ [CB .. "|Red"] = true, [CB .. "|Blue"] = true }, {}, CB), nil)
    check("hand_colour: ledgered tag", T.hand_colour({ [CB .. "|Red"] = true }, { [CB .. "|Red"] = true }, CB), nil)
    check("hand_colour: empty base", T.hand_colour({ [CB .. "|Red"] = true }, {}, ""), nil)
    do
        local have = { [CB .. "|Red"] = true, [CB .. "|White"] = true }
        local ledger_set = { [CB .. "|White"] = true }
        local prot = T.hand_colour_tags(have, ledger_set, CB)
        local _, detach = T.tag_changes(have, { [CB .. "|Blue"] = true }, {}, pre, prot, ledger_set)
        check("hand colour tag survives a Blue reading", table.concat(detach, ";"), CB .. "|White")
        check("hand_colour_tags: empty base", next(T.hand_colour_tags(have, {}, "")), nil)
    end
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

local hint = T.hint_prefixes(
    { ["F1|Red Bull"] = true, ["F1|Red Bull|Verstappen"] = true, ["F1|Ferrari"] = true, ["Holiday"] = true },
    { ["F1|Ferrari"] = true }, entries)
check("hint: a user-applied strict prefix of an entry tag hints", hint["F1|Red Bull"], true)
check("hint: a driver's own leaf tag is not a hint", hint["F1|Red Bull|Verstappen"], nil)
check("hint: a ledgered tag is the plugin's, not a hint", hint["F1|Ferrari"], nil)
check("hint: a non-entry tag is ignored", hint["Holiday"], nil)

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
check("entries_json emits a bare list", j:match("^%[") ~= nil, true)
check("entries_json quotes every field", j:find('"id": "VER"', 1, true) ~= nil, true)
check("entries_json emits the number field", j:find('"number": "1"', 1, true) ~= nil, true)
check("entries_json emits the tag array", j:find('"tags": ["F1|Red Bull", "F1|Red Bull|Verstappen", "F1|Champion"]', 1, true) ~= nil,
    true)

local pj = T.entries_json({
    { id = "VER", number = "1", team = "Red Bull", tags = { "Sports|F1|Red Bull", "Sports|F1|Red Bull|Verstappen" } },
    { id = "NOR", number = "4", team = "McLaren", tags = { "Sports|F1|McLaren", "Sports|F1|McLaren|Norris" } },
})
check("a shared prefix emits the object form", pj:match("^{") ~= nil, true)
check("the shared prefix becomes rules.tag_prefix", pj:find('"tag_prefix": "Sports|F1"', 1, true) ~= nil, true)
check("the driver leaf becomes name", pj:find('"name": "Norris"', 1, true) ~= nil, true)
check("prefix form drops explicit tags", pj:find('"tags"', 1, true), nil)
check("differing prefixes fall back to the bare list", T.entries_json({
    { id = "A", number = "", team = "X", tags = { "P|X", "P|X|A" } },
    { id = "B", number = "", team = "Y", tags = { "Q|Y", "Q|Y|B" } },
}):match("^%[") ~= nil, true)
check("extra tags fall back to the bare list", T.entries_json({
    { id = "A", number = "", team = "X", tags = { "P|X", "P|X|A", "P|Other" } },
}):match("^%[") ~= nil, true)

require("test_preset_block")(T, check)

do
    local d = T.preset_defaults(T.PRESET_SCHEMA)
    check("tagging schema has 45 keys", #T.PRESET_SCHEMA, 45)
    check("colour keys default on", tostring(d.tag_colour) .. tostring(d.tag_check_colour), "truetrue")
    check("tagging defaults", table.concat({ tostring(d.use_hints), d.group_support, d.group_node,
        tostring(d.run_tag), tostring(d.suggest_crops), tostring(d.quarantine), d.embedder_file,
        d.ocr_rec_file, tostring(d.neighbour_tolerance) }, " "), "true native  false false false   5")
    local all_on = true
    for _, item in ipairs(T.PRESET_SCHEMA) do
        if item.key:match("^tag_") and item.kind == "bool" and d[item.key] ~= true then all_on = false end
    end
    check("every tag switch defaults on", all_on, true)
    check("tolerance 3 kept", (T.preset_merge(T.PRESET_SCHEMA, { neighbour_tolerance = 3 })).neighbour_tolerance, 3)
    local merged, problems = T.preset_merge(T.PRESET_SCHEMA, { order_weight = "" })
    check("stored blank order_weight is the default", merged.order_weight, 0)
    check("stored blank order_weight is no problem", #problems, 0)
    local r = T.parse_rules_csv("order_weight,0.5\nneighbour_tolerance,5\ncolour_tags,true\nfrom_entries_json,order_weight;colour_tags")
    check("rules.csv: order_weight number", r.settings.order_weight, 0.5)
    check("rules.csv: neighbour_tolerance number", r.settings.neighbour_tolerance, 5)
    check("rules.csv: colour_tags boolean", r.settings.colour_tags, true)
    check("rules.csv: from_entries_json keys", table.concat(r.from_entries_json, ";"), "order_weight;colour_tags")
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
end

print("")
if failures == 0 then
    print("all tests passed")
    os.exit(0)
else
    print(failures .. " test(s) failed")
    os.exit(1)
end
