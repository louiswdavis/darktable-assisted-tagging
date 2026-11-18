--[[
    assisted_tagging.lua — Assisted Tagging for darktable

    Lighttable panel that shells out to identify.py to recognise the
    motorsport vehicles in a selection (race number, then livery against a
    collection's reference samples, then burst consensus) and tags each
    image with its entries' tags.
]]

local M = {}
local THIS_DIR = (debug.getinfo(1, "S").source:sub(2):match("^(.*)[/\\]")) or "."

-- plugin_common.lua lives beside this file; when this file was copied into lua/contrib by
-- hand it is found through the plugins folder preference (or the old plugin folder one).
-- C.plugin_folder isn't loaded yet, so both keys are read here directly.
local function load_common()
    local dirs, tried = { THIS_DIR }, {}
    local ok_dt, dt0 = pcall(require, "darktable")
    if ok_dt then
        local ok_r, root = pcall(dt0.preferences.read, "assisted_plugins", "plugins_root", "directory")
        if ok_r and root and root ~= "" then dirs[#dirs + 1] = root .. "/darktable-assisted-tagging/lua" end
        local ok_p, folder = pcall(dt0.preferences.read, "assisted_tagging", "plugin_folder", "directory")
        if ok_p and folder and folder ~= "" then dirs[#dirs + 1] = folder .. "/lua" end
    end
    for _, dir in ipairs(dirs) do
        local path = dir .. "/plugin_common.lua"
        local chunk = loadfile(path)
        if chunk then return chunk() end
        tried[#tried + 1] = path
    end
    error("assisted_tagging: plugin_common.lua not found (tried " .. table.concat(tried, ", ")
        .. "). Copy it next to assisted_tagging.lua, or set the plugins folder preference.")
end
local C = load_common()

M.cancel_requested = false
M.module_installed = false
M.event_registered = false

-- Default diagnostic tag per outcome; a collection's settings rename (tag_<key>_name) or drop
-- (tag_<key>) each one. PRESET_SCHEMA's tag_<key>_name defaults repeat these.
M.DIAG_TAGS = {
    number = "Assisted Tagging|Identification|By number",
    livery = "Assisted Tagging|Identification|By livery",
    burst = "Assisted Tagging|Identification|By burst",
    -- Neighbour aid (setting order_weight): a doubtful number read settled by the
    -- groups shot around it, and a read that doesn't fit the cars shot around it.
    neighbour = "Assisted Tagging|Identification|By neighbour",
    check_order = "Assisted Tagging|Identification|Check order",
    team ="Assisted Tagging|Identification|Team only",
    none = "Assisted Tagging|Identification|Unidentified",
    -- Suffixed with the literal digits read, e.g. "...|Number seen|115"; independent of
    -- the outcome tags above, added whenever OCR read a number that didn't resolve.
    number_seen = "Assisted Tagging|Identification|Number seen",
    check_colour = "Assisted Tagging|Identification|Check colour",
    -- a livery, burst or neighbour match unlike its car's anchors; the box keeps no entry tag
    check_match = "Assisted Tagging|Identification|Check match",
    -- Experimental (rules.burst_livery_pooling): a frame resolved by pooling box-0
    -- livery similarity across its burst rather than on its own.
    pooled = "Assisted Tagging|Identification|By pooled burst",
    -- One per image, from how many vehicles identify.py boxed (solo / pack / crowded).
    shot_solo = "Assisted Tagging|Identification|Shot|Solo",
    shot_pack = "Assisted Tagging|Identification|Shot|Pack",
    shot_crowded = "Assisted Tagging|Identification|Shot|Crowded",
}

-- Tag families, in order: each writes <root>|<value>, with a switch (family_<key>) and a root
-- (family_<key>_root) in the collection's settings. `sources` are the entry fields the value comes
-- from, joined with |; {} = read from the photo. Mirrors FAMILIES in python/families.py (test_families.py checks).
M.FAMILIES = {
    { key = "colour", sources = {}, default_root = "Assisted Tagging|Motorsport|Colour" },
    { key = "number", sources = { "number" }, default_root = "Assisted Tagging|Motorsport|Number" },
    { key = "team", sources = { "team" }, default_root = "Assisted Tagging|Motorsport|Team" },
    { key = "driver", sources = { "name" }, default_root = "Assisted Tagging|Motorsport|Driver" },
    { key = "co_driver", sources = { "co_driver" }, default_root = "Assisted Tagging|Motorsport|Co-driver" },
    { key = "extra", sources = { "extra" }, default_root = "Assisted Tagging|Motorsport|Class" },
    { key = "vehicle", sources = { "make", "model" }, default_root = "Assisted Tagging|Motorsport|Vehicle" },
    { key = "sponsor", sources = {}, default_root = "Assisted Tagging|Motorsport|Sponsor" },
}

-- Family key → root for each family switched on in settings `s`.
function M.family_roots(s)
    local roots = {}
    for _, f in ipairs(M.FAMILIES) do
        if s["family_" .. f.key] then roots[f.key] = s["family_" .. f.key .. "_root"] end
    end
    return roots
end

-- The shell command that opens `path` in its associated app. `os_name`: darktable's running_os
-- ("windows", "macos", anything else is treated as Linux).
function M.open_command(path, os_name)
    if os_name == "windows" then return 'start "" ' .. C.shell_quote((path:gsub("/", "\\")), true) end
    return (os_name == "macos" and "open " or "xdg-open ") .. C.shell_quote(path, false)
end

function M.exif_time_to_epoch(s)
    if not s then return nil end
    local y, mo, d, h, mi, se = s:match("(%d+):(%d+):(%d+) (%d+):(%d+):(%d+)")
    -- Before 1970 (a zero date, an old scan) os.time raises on Windows: undated.
    if not y or tonumber(y) < 1970 then return nil end
    local ok, epoch = pcall(os.time, {
        year = tonumber(y), month = tonumber(mo), day = tonumber(d),
        hour = tonumber(h), min = tonumber(mi), sec = tonumber(se),
        isdst = false, -- constant offset, so a DST change can't split a burst
    })
    return ok and epoch or nil
end

M.NEIGHBOUR_MAX_GAP_S = 20 -- python/neighbour.py's NEIGHBOUR_MAX_GAP_S

-- Candidates ({ time, ... }) shot within max_gap seconds of any selected time, in candidate order.
-- Untimed candidates (time nil or 0) and selected times of 0 are ignored.
function M.near_in_time(selected_times, candidates, max_gap)
    local ts = {}
    for _, t in ipairs(selected_times) do
        if t > 0 then ts[#ts + 1] = t end
    end
    table.sort(ts)
    local out = {}
    if #ts == 0 then return out end
    for _, c in ipairs(candidates) do
        local t = c.time
        if t and t > 0 then
            local lo, hi = 1, #ts
            while lo < hi do
                local mid = math.floor((lo + hi) / 2)
                if ts[mid] < t then lo = mid + 1 else hi = mid end
            end
            local near = math.abs(ts[lo] - t) <= max_gap or (lo > 1 and math.abs(ts[lo - 1] - t) <= max_gap)
            if near then out[#out + 1] = c end
        end
    end
    return out
end

-- Shared with the other two plugins (plugin_common.lua); re-exported for the tests.
M.latest_group_tag, M.latest_group_keys, M.group_tags_hint, M.GROUP_TAGS_HINT =
    C.latest_group_tag, C.latest_group_keys, C.group_tags_hint, C.GROUP_TAGS_HINT
M.tag_group_keys, M.native_group_keys, M.number_groups = C.tag_group_keys, C.native_group_keys, C.number_groups
M.shot_stem, M.is_raw, M.csv_line, M.parse_csv_line, M.parse_report_line, M.pythonw_of =
    C.shot_stem, C.is_raw, C.csv_line, C.parse_csv_line, C.parse_csv_fields, C.pythonw_of
local lead_rank = C.lead_rank
for name, fn in pairs(C) do
    if type(name) == "string" and name:match("^preset_") then M[name] = fn end
end


-- Images → the ones to identify, and per identified id every image that takes its tags.
-- One shot = darktable duplicates of a file plus a RAW+JPEG pair (same folder and stem),
-- so the pair always gets the same tags. A shot is read from its best-ranked member.
function M.collapse_shots(images)
    local primaries, group_of, lead_of = {}, {}, {}
    for _, img in ipairs(images) do
        local key = img.path .. "/" .. M.shot_stem(img.filename)
        local lead = lead_of[key]
        if not lead then
            primaries[#primaries + 1] = img
            lead_of[key] = { img = img, slot = #primaries }
            group_of[img.id] = { img }
        else
            local group = group_of[lead.img.id]
            group[#group + 1] = img
            if lead_rank(img.filename) > lead_rank(lead.img.filename) then
                group_of[lead.img.id] = nil
                group_of[img.id] = group
                primaries[lead.slot] = img
                lead.img = img
            end
        end
    end
    return primaries, group_of
end

-- `carriers` that take the tags of an image in `read` without being in it: the same shot
-- (see M.collapse_shots) or the same darktable group. Images: { id, path, filename, group_leader }.
function M.shot_copies(read, carriers)
    local in_read, shot, leader = {}, {}, {}
    for _, img in ipairs(read) do
        in_read[img.id] = true
        shot[img.path .. "/" .. M.shot_stem(img.filename)] = true
        if img.group_leader then leader[img.group_leader.id] = true end
    end
    local out = {}
    for _, img in ipairs(carriers) do
        if not in_read[img.id] and (shot[img.path .. "/" .. M.shot_stem(img.filename)]
            or (img.group_leader and leader[img.group_leader.id])) then
            in_read[img.id] = true
            out[#out + 1] = img
        end
    end
    return out
end

-- Selected images → the same list with each one swapped for the best-ranked image of its
-- shot found in `pool` (e.g. a RAW → its paired JPEG), duplicates dropped, order kept.
-- Also returns how many selections were swapped, and per selected id the image picked.
function M.prefer_paired(images, pool)
    local best = {}
    for _, img in ipairs(pool) do
        local key = img.path .. "/" .. M.shot_stem(img.filename)
        if not best[key] or lead_rank(img.filename) > lead_rank(best[key].filename) then best[key] = img end
    end
    local out, seen, swapped, pick_of = {}, {}, 0, {}
    for _, img in ipairs(images) do
        local pick = img
        local b = best[img.path .. "/" .. M.shot_stem(img.filename)]
        if b and lead_rank(b.filename) > lead_rank(img.filename) then
            pick = b
            swapped = swapped + 1
        end
        pick_of[img.id] = pick
        if not seen[pick.id] then
            seen[pick.id] = true
            out[#out + 1] = pick
        end
    end
    return out, swapped, pick_of
end


local function split(s, sep)
    local out = {}
    for part in s:gmatch("[^" .. sep .. "]+") do out[#out + 1] = part end
    return out
end

-- identify.py's entries.csv (id,team,number,tag;tag…,name,co_driver,colour) → entries by id, and the ids in file order.
function M.parse_entries_csv(text)
    local entries, order = {}, {}
    for line in (text or ""):gmatch("[^\r\n]+") do
        local p = M.parse_csv_line(line, 7) or M.parse_csv_line(line, 6) or M.parse_csv_line(line, 5)
            or M.parse_csv_line(line, 4)
        if p and p[1] ~= "" and p[4] ~= "" and not entries[p[1]] then
            entries[p[1]] = { id = p[1], team = p[2], number = p[3], tags = split(p[4], ";"), name = p[5] or "",
                              co_driver = p[6] or "", colour = p[7] or "" }
            order[#order + 1] = p[1]
        end
    end
    return entries, order
end

function M.default_rules()
    local diag = {}
    for k, v in pairs(M.DIAG_TAGS) do diag[k] = v end
    return { team_only = "shared tags", unidentified = {}, diag = diag, families = {}, settings = {},
        from_entries_json = {} }
end

-- The collection settings identify.py writes into rules.csv (python/settings.py MOVED_RULES).
local MOVED_RULES = { order_weight = true, neighbour_tolerance = true, min_read = true,
    colour_weight = true, partial_references = true, min_sim = true,
    margin = true, min_face_px = true, burst_livery_pooling = true, blur_references = true }

-- identify.py's rules.csv (key,value lines) → rules. Besides team_only, unidentified,
-- diag_<outcome> and family_<key> (the root of a family that is on): each resolved setting as rules.settings[key] (numbers and booleans), and
-- from_entries_json, the settings keys still read from entries.json's old "rules".
function M.parse_rules_csv(text)
    local rules = M.default_rules()
    for line in (text or ""):gmatch("[^\r\n]+") do
        local key, value = line:match("^([^,]+),(.*)$")
        if key == "team_only" then
            rules.team_only = value
        elseif key == "unidentified" then
            rules.unidentified = split(value, ";")
        elseif key and key:sub(1, 5) == "diag_" and M.DIAG_TAGS[key:sub(6)] then
            rules.diag[key:sub(6)] = value
        elseif key == "from_entries_json" then
            rules.from_entries_json = split(value, ";")
        elseif key and key:sub(1, 7) == "family_" then
            rules.families[key:sub(8)] = value
        elseif key and MOVED_RULES[key] then
            if value == "true" or value == "false" then
                rules.settings[key] = value == "true"
            else
                rules.settings[key] = tonumber(value)
            end
        end
    end
    return rules
end

-- rows: one image's results ({ box, method, entry_id, alt_entry_id }). Returns the
-- collection tags it should carry (name → true), its diagnostic tags, and whether
-- any vehicle was identified. What each outcome adds comes from `rules`. A row that adds an
-- entry's tags also adds a "Derived from" marker (rules.diag.derived|<leaf>): `hand_from`
-- ("From number" or "From driver") for a hand row, "From identification" for the rest.
function M.wanted_tags(rows, entries, rules, hand_from)
    rules = rules or M.default_rules()
    local wanted, diag, identified = {}, {}, false
    -- held: a box disagreed with tags the user applied by hand and was left as they had it.
    -- That's not "unidentified", so it adds no unidentified tags.
    local held, shot = false, nil
    local function note(outcome)
        local name = rules.diag[outcome]
        if name and name ~= "" then diag[name] = true end
    end
    local function mark(leaf)
        local base = rules.diag.derived
        if base and base ~= "" then diag[base .. "|" .. leaf] = true end
    end
    for _, r in ipairs(rows) do
        local e = entries[r.entry_id]
        if r.shot and r.shot ~= "" then shot = r.shot end
        if r.method == "conflict" then
            held = true
        elseif e and (r.method == "number" or r.method == "livery" or r.method == "burst" or r.method == "pooled" or r.method == "neighbour" or r.method == "face" or r.method == "hand") then
            for _, t in ipairs(e.tags) do wanted[t] = true end
            note(r.method)
            mark(r.method == "hand" and (hand_from or "From number") or "From identification")
            if r.order_flag then note("check_order") end
            identified = true
        elseif e and r.method == "team" then
            if rules.team_only == "shared tags" then
                local alt = entries[r.alt_entry_id]
                local shared = {}
                if alt then for _, t in ipairs(alt.tags) do shared[t] = true end end
                for _, t in ipairs(e.tags) do
                    if shared[t] then wanted[t] = true end
                end
                mark("From identification")
            end
            note("team")
            identified = true
        end
        -- Independent of the outcome above: OCR read a number that matched zero or 2+
        -- entries, so it couldn't drive identification, but it's worth seeing. One tag
        -- per distinct digit string read on this box.
        if r.unmatched_number and r.unmatched_number ~= "" then
            local base = rules.diag.number_seen
            if base and base ~= "" then
                for _, digits in ipairs(split(r.unmatched_number, ";")) do
                    diag[base .. "|" .. digits] = true
                end
            end
        end
        -- Independent of the outcome; a no-vehicle row (box -1) has no colour to report.
        if r.box >= 0 and r.colour and r.colour ~= "" then
            local base = rules.families.colour
            if base and base ~= "" then diag[base .. "|" .. r.colour] = true end
            if r.colour_flag then note("check_colour") end
        end
        -- Independent of the outcome: a match dropped because it didn't look like its car's anchors.
        if r.anchor_flag then note("check_match") end
        -- Listed sponsor words read inside this vehicle box, one tag each.
        if r.box >= 0 and r.sponsor and r.sponsor ~= "" then
            local base = rules.families.sponsor
            if base and base ~= "" then
                for _, word in ipairs(split(r.sponsor, ";")) do diag[base .. "|" .. word] = true end
            end
        end
    end
    if shot then note("shot_" .. shot) end
    if not identified and not held then
        for _, t in ipairs(rules.unidentified) do wanted[t] = true end
        note("none")
    end
    return wanted, diag, identified
end

-- Every tag the plugin may detach: the collection's entry and unidentified tags,
-- and the diagnostic tags, including the defaults a collection renamed.
function M.owned_tags(entries, rules)
    rules = rules or M.default_rules()
    local owned = {}
    for _, e in pairs(entries) do
        for _, t in ipairs(e.tags) do owned[t] = true end
    end
    for _, t in ipairs(rules.unidentified) do owned[t] = true end
    for _, t in pairs(rules.diag) do if t ~= "" then owned[t] = true end end
    for _, t in pairs(M.DIAG_TAGS) do owned[t] = true end
    return owned
end

-- The first segment of every entry and unidentified tag ("F1|Ferrari" → "F1").
function M.owned_roots(entries, rules)
    rules = rules or M.default_rules()
    local roots = {}
    local function add(t) roots[t:match("^[^|]*")] = true end
    for _, e in pairs(entries) do
        for _, t in ipairs(e.tags) do add(t) end
    end
    for _, t in ipairs(rules.unidentified) do add(t) end
    return roots
end

-- The tags in `mine` (one image's ledger) under one of `roots`: tags the plugin attached
-- for this collection, including those of entries since renamed or removed, which
-- owned_tags no longer lists. Another collection's roots stay out, so its tags survive.
function M.ledgered_owned(mine, roots)
    local out = {}
    for name in pairs(mine or {}) do
        if roots[name:match("^[^|]*")] then out[name] = true end
    end
    return out
end

-- rules with every diagnostic named from settings `s` (tag_<key>_name; tag_shot_name|Solo/Pack,
-- tag_shot_crowded_name|Crowded), switch on or off: rules.csv leaves a switched-off diagnostic blank, and detach,
-- hand-tag protection and tooltips still need its name.
function M.named_rules(rules, s)
    local named, diag = {}, {}
    for k, v in pairs(rules) do named[k] = v end
    for k in pairs(M.DIAG_TAGS) do
        local leaf = k:match("^shot_(.+)$")
        local base = k == "shot_crowded" and s.tag_shot_crowded_name or s.tag_shot_name
        diag[k] = leaf and (base .. "|" .. leaf:sub(1, 1):upper() .. leaf:sub(2))
            or s["tag_" .. k .. "_name"]
    end
    -- not a DIAG_TAGS outcome (rules.csv never names it): the base of the "Derived from" markers
    diag.derived = s.tag_derived_name
    named.diag = diag
    -- every family's root, on or off: a switched-off family's tags are still the plugin's
    local families = {}
    for _, f in ipairs(M.FAMILIES) do families[f.key] = s["family_" .. f.key .. "_root"] end
    named.families = families
    return named
end

-- rules with the diagnostics in `off` (outcome key → true) blanked, for wanted_tags.
-- owned_tags keeps the full rules, so the next run detaches what is off.
-- "shot" covers shot_solo and shot_pack; "shot_crowded" has its own switch.
function M.mask_diag(rules, off)
    local masked, diag = {}, {}
    for k, v in pairs(rules) do masked[k] = v end
    for k, v in pairs(rules.diag) do
        diag[k] = (off[k] or (off.shot and (k == "shot_solo" or k == "shot_pack"))) and "" or v
    end
    masked.diag = diag
    return masked
end

-- Prefixes of the tags written one per value: "...Number seen|<digits>", "...Derived|From <source>"
-- and the colour and sponsor families' "<root>|<value>".
function M.owned_prefixes(rules)
    local out = {}
    for _, base in ipairs({ rules.diag.number_seen or "", rules.diag.derived or "", rules.families.colour or "",
                            rules.families.sponsor or "" }) do
        if base ~= "" then out[#out + 1] = base .. "|" end
    end
    return out
end

-- The tags in `have` under any root in `roots` (family key → root) that are not in `ledger_set`
-- (the plugin's own): family tags the user set by hand, which a run must never detach.
function M.hand_family_tags(have, ledger_set, roots)
    local out = {}
    for _, root in pairs(roots or {}) do
        if root ~= "" then
            local prefix = root .. "|"
            for name in pairs(have) do
                if name:sub(1, #prefix) == prefix and not (ledger_set and ledger_set[name]) then out[name] = true end
            end
        end
    end
    return out
end

-- The values the user set by hand under `root`, sorted. Empty for no root.
local function hand_values(have, ledger_set, root)
    local out = {}
    if not root or root == "" then return out end
    for name in pairs(M.hand_family_tags(have, ledger_set, { root })) do out[#out + 1] = name:sub(#root + 2) end
    table.sort(out)
    return out
end

-- The value the user set by hand under `root`: the suffix of the one tag there that is in
-- `have` but not in `ledger_set`. nil for none, several, or no root.
function M.hand_value(have, ledger_set, root)
    local values = hand_values(have, ledger_set, root)
    return #values == 1 and values[1] or nil
end

-- The entry the user's hand tags name: a number tag (`roots.number`|<n>) names the entry with that
-- number, a driver tag (`roots.driver`|<name>) the entry with that name, a co-driver tag
-- (`roots.co_driver`|<name>) the entry with that co_driver. A value two or more entries share names
-- none of them by itself. Returns the id; or nil, "ambiguous" when the tags only
-- narrow it to several entries; or nil, "disagree" when they name different entries. Team and
-- colour tags never name an entry. `roots`: family key → root of the families switched on.
function M.hand_entry(have, ledger_set, entries, roots)
    local named, shared = {}, {}
    for _, f in ipairs({ { root = roots.number, field = "number" }, { root = roots.driver, field = "name" },
                         { root = roots.co_driver, field = "co_driver" } }) do
        for _, value in ipairs(hand_values(have, ledger_set, f.root)) do
            local ids = {}
            for id, e in pairs(entries) do
                if e[f.field] == value then ids[#ids + 1] = id end
            end
            if #ids == 1 then named[ids[1]] = true elseif #ids > 1 then shared[#shared + 1] = ids end
        end
    end
    local id = next(named)
    if not id then return nil, #shared > 0 and "ambiguous" or nil end
    if next(named, id) then return nil, "disagree" end
    for _, ids in ipairs(shared) do
        local among = false
        for _, other in ipairs(ids) do if other == id then among = true end end
        if not among then return nil, "disagree" end
    end
    return id
end

-- The "Derived from" leaf for a hand row (M.wanted_tags' hand_from): "From number" when the
-- user's number tags alone name the entry, else "From driver" (a driver or co-driver tag did).
function M.hand_source(have, ledger_set, entries, roots)
    return M.hand_entry(have, ledger_set, entries, { number = roots.number }) and "From number" or "From driver"
end

-- Mirror of python/car_colour.py NEAR_COLOURS and colour_relation: 1 when an entry's colour and a
-- seen colour agree, -1 when they differ, 0 when either is empty, either is Multi, or the pair is near.
local NEAR_COLOURS = { White = { Grey = true }, Grey = { White = true, Black = true }, Black = { Grey = true } }
function M.colour_relation(entry_colour, seen)
    if not entry_colour or entry_colour == "" or not seen or seen == "" then return 0 end
    if entry_colour == seen then return 1 end
    if entry_colour == "Multi" or seen == "Multi" or (NEAR_COLOURS[entry_colour] or {})[seen] then return 0 end
    return -1
end

-- The values of the tags in `have` under `root` (hand or plugin), sorted. Empty for no root.
local function values_under(have, root)
    local out = {}
    if not root or root == "" then return out end
    local prefix = root .. "|"
    for name in pairs(have) do
        if name:sub(1, #prefix) == prefix then out[#out + 1] = name:sub(#prefix + 1) end
    end
    table.sort(out)
    return out
end

-- What a Derive button adds to one image, by lookup only. `mode` "number": the entry the user's
-- hand number tags name (M.hand_entry). `mode` "colour": the one entry whose colour equals the
-- image's single colour tag, narrowed by hand team tags; an image whose hand number names an entry
-- is left to Derive from number. `names`: { derived = marker base, check_colour = tag } ("" = off).
-- Returns { entry_id, attach = sorted tag names, reason = why nothing was added ("" when added) };
-- attach can hold only the Check colour tag when the number's entry and the colour tag differ.
function M.derive_plan(have, ledger_set, entries, order, roots, mode, names)
    local plan = { attach = {}, reason = "" }
    local add = {}
    local colours = values_under(have, roots.colour)
    local number_id, why = M.hand_entry(have, ledger_set, entries, { number = roots.number })
    if number_id and #colours == 1 and names.check_colour ~= "" and not have[names.check_colour]
        and M.colour_relation(entries[number_id].colour, colours[1]) == -1 then
        add[names.check_colour] = true
    end
    local id, leaf
    if mode == "number" then
        if number_id then
            id, leaf = number_id, "From number"
        else
            plan.reason = why == "ambiguous" and "its number fits several entries"
                or why == "disagree" and "its number tags name different entries"
                or "no number tag of yours names an entry"
        end
    elseif number_id then
        plan.reason = "it has a number tag: use Derive from number"
    elseif M.entry_for_tags(have, entries, order) then
        plan.reason = "it already has an entry's tags"
    elseif #colours ~= 1 then
        plan.reason = #colours == 0 and "it has no colour tag" or "it has several colour tags"
    else
        local teams = M.hint_tags(have, ledger_set, entries, roots.team)
        local found = {}
        for _, entry_id in ipairs(order) do
            local e = entries[entry_id]
            if M.colour_relation(e.colour, colours[1]) == 1
                and (not next(teams) or teams[roots.team .. "|" .. e.team]) then
                found[#found + 1] = entry_id
            end
        end
        if #found == 1 then
            id, leaf = found[1], "From colour"
        else
            plan.reason = #found == 0 and ("no entry is " .. colours[1])
                or string.format("%d entries are %s", #found, colours[1])
        end
    end
    if id then
        plan.entry_id = id
        local added = false
        for _, t in ipairs(entries[id].tags) do
            if not have[t] then add[t], added = true, true end
        end
        if not added then
            plan.reason = "it already has the entry's tags"
        elseif names.derived ~= "" and not have[names.derived .. "|" .. leaf] then
            add[names.derived .. "|" .. leaf] = true
        end
    end
    for name in pairs(add) do plan.attach[#plan.attach + 1] = name end
    table.sort(plan.attach)
    return plan
end

local CANDIDATE_KINDS = { number = 1, team = 2, driver = 3, co_driver = 4, split = 5 }
local CANDIDATE_FIELDS = { team = "team", driver = "name", co_driver = "co_driver" }

-- "Smith / Jones" → "Smith", "Jones"; nil unless the name is exactly two non-empty halves around one " / ".
local function split_name(name)
    local first, rest = (name or ""):match("^(.-) / (.*)$")
    if not first or rest:find(" / ", 1, true) then return nil end
    first, rest = first:match("^%s*(.-)%s*$"), rest:match("^%s*(.-)%s*$")
    if first == "" or rest == "" then return nil end
    return first, rest
end

local function by_number_first(a, b)
    local na, nb = tonumber(a), tonumber(b)
    if na and nb and na ~= nb then return na < nb end
    return a < b
end

-- Find new entries: what the selected photos show that entries.json lacks. `images`: list of
-- { id, have, ledger_set }. A `<seen_base>|<digits>` tag whose digits are no entry's number makes a
-- `number` row (image in `read`); a hand tag `<number root>|<n>` with n unlisted makes one too
-- (image in `hand`, never also in `read`). Unlisted means no entry has n as its number or id, and n
-- is 1-3 digits. A hand team, driver or co-driver tag on an image whose number tags,
-- hand or plugin-written, name exactly one entry with that field empty makes a `team`/`driver`/
-- `co_driver` row (`entry` = its id). That one entry, when its name is two names around one " / "
-- and its co_driver is empty, also makes a `split` row (image in `read`; `value` = the name,
-- `driver`/`co_driver` = the halves). One row per number, per split entry or per (entry, field,
-- value); values holding `|` are skipped, and team, driver or co-driver values holding , ; or "
-- (identify.py rejects them). Rows come most photos first, then by number.
function M.new_entry_candidates(images, entries, roots, seen_base)
    local listed, taken = {}, {}
    for id, e in pairs(entries) do
        taken[id] = true
        if e.number and e.number ~= "" then
            taken[e.number] = true
            listed[e.number] = listed[e.number] or {}
            listed[e.number][#listed[e.number] + 1] = id
        end
    end
    local rows, index = {}, {}
    local function add(key, fresh, list, image_id)
        local r = index[key]
        if not r then
            r = fresh
            r.read, r.hand = {}, {}
            index[key] = r
            rows[#rows + 1] = r
        end
        r[list][#r[list] + 1] = image_id
    end
    local number_root = roots.number or ""
    local seen_prefix = (seen_base or "") ~= "" and seen_base .. "|" or nil
    for _, img in ipairs(images) do
        local hand_numbers = {}
        for _, n in ipairs(hand_values(img.have, img.ledger_set, number_root)) do
            if not n:find("|", 1, true) then hand_numbers[n] = true end
        end
        local read_numbers = {}
        if seen_prefix then
            for name in pairs(img.have) do
                local digits = name:sub(1, #seen_prefix) == seen_prefix and name:sub(#seen_prefix + 1)
                if digits and digits:match("^%d+$") and not hand_numbers[digits] then read_numbers[#read_numbers + 1] = digits end
            end
        end
        table.sort(read_numbers)
        for _, n in ipairs(read_numbers) do
            if not taken[n] and n:match("^%d%d?%d?$") then add("number\0" .. n, { kind = "number", number = n, value = n }, "read", img.id) end
        end
        local hands = {}
        for n in pairs(hand_numbers) do hands[#hands + 1] = n end
        table.sort(hands)
        for _, n in ipairs(hands) do
            if not taken[n] and n:match("^%d%d?%d?$") then add("number\0" .. n, { kind = "number", number = n, value = n }, "hand", img.id) end
        end
        if number_root ~= "" then
            local ids, prefix = {}, number_root .. "|"
            for name in pairs(img.have) do
                local n = name:sub(1, #prefix) == prefix and name:sub(#prefix + 1)
                for _, id in ipairs(n and listed[n] or {}) do ids[id] = true end
            end
            local eid = next(ids)
            if eid and not next(ids, eid) then
                local e = entries[eid]
                local driver, co_driver = split_name(e.name)
                if driver and (e.co_driver or "") == "" then
                    add("split\0" .. eid, { kind = "split", entry = eid, number = e.number, value = e.name,
                                            driver = driver, co_driver = co_driver }, "read", img.id)
                end
                for _, kind in ipairs({ "team", "driver", "co_driver" }) do
                    local field = CANDIDATE_FIELDS[kind]
                    if (e[field] or "") == "" then
                        for _, value in ipairs(hand_values(img.have, img.ledger_set, roots[kind])) do
                            if not value:find('[|,;"]') then
                                add(kind .. "\0" .. eid .. "\0" .. value,
                                    { kind = kind, entry = eid, number = e.number, value = value }, "hand", img.id)
                            end
                        end
                    end
                end
            end
        end
    end
    table.sort(rows, function(a, b)
        local ca, cb = #a.read + #a.hand, #b.read + #b.hand
        if ca ~= cb then return ca > cb end
        if a.number ~= b.number then return by_number_first(a.number, b.number) end
        if a.kind ~= b.kind then return CANDIDATE_KINDS[a.kind] < CANDIDATE_KINDS[b.kind] end
        return a.value < b.value
    end)
    return rows
end

-- The check-button text of a Find new entries row.
function M.candidate_label(row)
    local function photos(n) return n == 1 and "1 photo" or (n .. " photos") end
    local seen
    if #row.read > 0 and #row.hand > 0 then
        seen = "read on " .. photos(#row.read) .. ", hand-tagged on " .. photos(#row.hand)
    elseif #row.read > 0 then
        seen = "read on " .. photos(#row.read)
    else
        seen = "hand-tagged on " .. photos(#row.hand)
    end
    local what
    if row.kind == "number" then
        what = row.number
    elseif row.kind == "split" then
        what = string.format('%s: split "%s" → driver %s, co-driver %s', row.number, row.value, row.driver, row.co_driver)
    else
        what = row.number .. ": " .. (row.kind == "co_driver" and "co-driver" or row.kind) .. " " .. row.value
    end
    return what .. "    " .. seen
end

-- Why the ticked rows can't be added, or nil when they can. `roots`: the families switched on.
function M.check_additions(ticked, roots)
    if #ticked == 0 then return "Nothing ticked." end
    for _, r in ipairs(ticked) do
        if r.kind == "number" and (roots.number or "") == "" then
            return "Turn on the number family before adding numbers: a new entry needs a tag."
        end
    end
    local values, order = {}, {}
    for _, r in ipairs(ticked) do
        if r.kind ~= "number" then
            local key = r.entry .. "\0" .. r.kind
            if not values[key] then
                values[key] = {}
                order[#order + 1] = { key = key, row = r }
            end
            values[key][#values[key] + 1] = r.value
        end
    end
    for _, o in ipairs(order) do
        if #values[o.key] > 1 then
            return string.format("Entry %s has two ticked %ss: %s. Tick one.",
                o.row.number, o.row.kind == "co_driver" and "co-driver" or o.row.kind, table.concat(values[o.key], ", "))
        end
    end
    for _, o in ipairs(order) do
        if o.row.kind == "split" then
            for _, kind in ipairs({ "driver", "co_driver" }) do
                if values[o.row.entry .. "\0" .. kind] then
                    return string.format("Entry %s has a split and a %s ticked. Tick one.",
                        o.row.number, kind == "co_driver" and "co-driver" or kind)
                end
            end
        end
    end
    return nil
end

-- The additions CSV rows entries_file.py reads: `number,<n>`, `split,<entry id>` and
-- `field,<entry id>,<team|name|co_driver>,<value>`.
function M.addition_rows(ticked)
    local out = {}
    for _, r in ipairs(ticked) do
        out[#out + 1] = r.kind == "number" and { "number", r.number }
            or r.kind == "split" and { "split", r.entry }
            or { "field", r.entry, CANDIDATE_FIELDS[r.kind], r.value }
    end
    return out
end

-- have: an image's tag names (name → true). Returns the names to attach and to
-- detach, sorted. Only owned tags, or tags starting with an owned prefix (the dynamic
-- "...Number seen|<digits>" diagnostic, one tag per distinct digit string), are detached.
-- `protected` (name → true): tags the user applied by hand; never detached.
-- `also_owned` (name → true): this image's extra owned tags, from M.ledgered_owned.
function M.tag_changes(have, wanted, owned, owned_prefixes, protected, also_owned)
    protected = protected or {}
    local attach, detach = {}, {}
    for name in pairs(wanted) do
        if not have[name] then attach[#attach + 1] = name end
    end
    local function is_owned(name)
        if owned[name] or (also_owned and also_owned[name]) then return true end
        for _, p in ipairs(owned_prefixes or {}) do
            if name:sub(1, #p) == p then return true end
        end
        return false
    end
    for name in pairs(have) do
        if is_owned(name) and not wanted[name] and not protected[name] then
            detach[#detach + 1] = name
        end
    end
    table.sort(attach)
    table.sort(detach)
    return attach, detach
end

-- Ledger: the tags the plugin attached, per image id, persisted as `<library>,id,tag` lines. A
-- tag on an image that's not in its ledger was applied by the user. `library` is C.library_key:
-- image ids restart in every library, so only library `lib`'s lines are parsed (keyed by id);
-- other libraries' lines are kept in ledger.other and written back unchanged. Lines from
-- before the library column (`id,tag`) belong to `lib`.
function M.ledger_parse(text, lib)
    lib = lib or ""
    local ledger = { other = {} }
    for line in (text or ""):gmatch("[^\r\n]+") do
        local p = M.parse_csv_line(line, 3)
        if not p then
            p = M.parse_csv_line(line, 2)
            if p then table.insert(p, 1, lib) end
        end
        local id = p and tonumber(p[2])
        if p and p[1] ~= lib then
            ledger.other[#ledger.other + 1] = table.concat(p, ",")
        elseif id and p[3] ~= "" then
            ledger[id] = ledger[id] or {}
            ledger[id][p[3]] = true
        end
    end
    return ledger
end

M.ledger_prune = C.ledger_prune

-- What Clear detaches, decided by the ledger alone: for each record (`{ id, tags = set }`)
-- with a ledger row, the row's tags still on the image, sorted. Records with no row get no
-- plan, so hand-applied tags stay even under the plugin's roots.
function M.plan_clear(records, ledger)
    local plans = {}
    for _, r in ipairs(records) do
        local row = ledger[r.id]
        if row then
            local detach = {}
            for name in pairs(row) do
                if r.tags[name] then detach[#detach + 1] = name end
            end
            table.sort(detach)
            plans[#plans + 1] = { id = r.id, detach = detach }
        end
    end
    return plans
end

-- A reference job's results.csv (`id,status,colour_note,entry_id`; files from before colour
-- notes have two columns, before entry ids three) → its rows { id, status, note, entry_id }
-- (missing columns "") and the count of each colour note.
function M.parse_reference_results(text)
    local rows, notes = {}, { set = 0, differs = 0, already = 0 }
    for line in (text or ""):gmatch("[^\r\n]+") do
        local p = M.parse_csv_line(line, 4) or M.parse_csv_line(line, 3) or M.parse_csv_line(line, 2)
        if p then
            p[3] = p[3] or ""
            p[4] = p[4] or ""
            rows[#rows + 1] = p
            if notes[p[3]] then notes[p[3]] = notes[p[3]] + 1 end
        end
    end
    return rows, notes
end

-- A colours-only job's rows → entries whose colour was set, entries that already had it, images
-- whose colour was unread, and images the job failed on (the first two count distinct entry ids).
function M.colour_summary(rows)
    local set, already, unread, failed = {}, {}, 0, 0
    for _, p in ipairs(rows) do
        if p[3] == "set" then set[p[4]] = true
        elseif p[3] == "already" then already[p[4]] = true end
        if p[2] == "unread" then unread = unread + 1
        elseif p[2] == "failed" then failed = failed + 1 end
    end
    local n_set, n_already = 0, 0
    for _ in pairs(set) do n_set = n_set + 1 end
    for _ in pairs(already) do n_already = n_already + 1 end
    return n_set, n_already, unread, failed
end

-- The done-message clauses for a reference job's colour notes; only non-zero counts.
function M.colour_note_extras(notes)
    local out = {}
    if notes.set > 0 then out[#out + 1] = string.format("%d entries got a colour", notes.set) end
    if notes.differs > 0 then out[#out + 1] = string.format("%d colour readings differ from entries.json (see log)", notes.differs) end
    return out
end

function M.ledger_format(ledger, lib)
    lib = lib or ""
    local ids = {}
    for id in pairs(ledger) do
        if type(id) == "number" then ids[#ids + 1] = id end
    end
    table.sort(ids)
    local out = {}
    for _, id in ipairs(ids) do
        local names = {}
        for name in pairs(ledger[id]) do names[#names + 1] = name end
        table.sort(names)
        -- unquoted: parse_csv_line doesn't unquote, and tag names never hold a comma
        for _, name in ipairs(names) do out[#out + 1] = lib .. "," .. id .. "," .. name end
    end
    for _, line in ipairs(ledger.other or {}) do out[#out + 1] = line end
    return #out > 0 and table.concat(out, "\n") .. "\n" or ""
end

-- Diagnostic, unidentified and number-seen / colour tags among `have` that the plugin
-- didn't attach (not in `ledger_set`): applied by hand, so a run must never detach them.
-- Only ever added to the detach protection, not sent to the identifier.
function M.hand_diag_tags(have, ledger_set, rules)
    rules = rules or M.default_rules()
    local fixed = {}
    for _, t in ipairs(rules.unidentified) do fixed[t] = true end
    for _, t in pairs(rules.diag) do if t ~= "" then fixed[t] = true end end
    for _, t in pairs(M.DIAG_TAGS) do fixed[t] = true end
    local prefixes = M.owned_prefixes(rules)
    local out = {}
    for name in pairs(have) do
        if not (ledger_set and ledger_set[name]) then
            local hit = fixed[name]
            for _, p in ipairs(prefixes) do
                if name:sub(1, #p) == p then hit = true end
            end
            if hit then out[name] = true end
        end
    end
    return out
end

-- Entry tags among `have` that the plugin didn't attach (not in `ledger_set`): the
-- user's own, which a run must never detach. With `roots` (family key → root), so is every
-- hand tag under one of them, listed in an entry or not.
function M.protected_tags(have, ledger_set, entries, roots)
    local in_entry = {}
    for _, e in pairs(entries) do
        for _, t in ipairs(e.tags) do in_entry[t] = true end
    end
    local out = {}
    for name in pairs(have) do
        if in_entry[name] and not (ledger_set and ledger_set[name]) then out[name] = true end
    end
    for name in pairs(M.hand_family_tags(have, ledger_set, roots)) do out[name] = true end
    return out
end

-- Team tags (`team_root`|<team> of an entry) among `have` that the user applied (not in
-- `ledger_set`): hints that narrow matching. Empty when the team family is off (no `team_root`).
function M.hint_tags(have, ledger_set, entries, team_root)
    local out = {}
    if not team_root or team_root == "" then return out end
    for _, e in pairs(entries) do
        local name = e.team ~= "" and (team_root .. "|" .. e.team)
        if name and have[name] and not (ledger_set and ledger_set[name]) then out[name] = true end
    end
    return out
end

local function same_tag_set(a, b)
    local set, n, m = {}, 0, 0
    for _, t in ipairs(a) do if not set[t] then set[t] = true; n = n + 1 end end
    local seen = {}
    for _, t in ipairs(b) do
        if not set[t] then return false end
        if not seen[t] then seen[t] = true; m = m + 1 end
    end
    return n == m
end

-- The entry an already-tagged image belongs to: the one whose tags it carries
-- all of (a shared team tag alone matches no one). nil when none or several do;
-- entries with the same tag set (a double-driven car's two entries) count as one, the first.
-- Tags in `ledger_set` (the plugin wrote them) don't count, so its own guesses never become references.
function M.entry_for_tags(have, entries, order, ledger_set)
    local found = nil
    for _, id in ipairs(order) do
        local all = #entries[id].tags > 0
        for _, t in ipairs(entries[id].tags) do
            if not have[t] or (ledger_set and ledger_set[t]) then all = false; break end
        end
        if all then
            if not found then
                found = id
            elseif not same_tag_set(entries[found].tags, entries[id].tags) then
                return nil
            end
        end
    end
    return found
end

-- identify.py's results.csv → rows by image id, and the ids it couldn't analyse.
-- Those get no rows, so their tags are left exactly as they were. `skipped` (already
-- fully tagged, not analysed) is the same.
function M.read_results(text)
    local rows_of, errored, skipped = {}, {}, {}
    for line in (text or ""):gmatch("[^\r\n]+") do
        local p = M.parse_csv_line(line, 13) or M.parse_csv_line(line, 12) or M.parse_csv_line(line, 11) or M.parse_csv_line(line, 10) or M.parse_csv_line(line, 9)
        local id = p and tonumber(p[1])
        if id and p[3] == "error" then
            errored[id] = true
        elseif id and p[3] == "skipped" then
            skipped[id] = true
        elseif id then
            rows_of[id] = rows_of[id] or {}
            table.insert(rows_of[id], { box = tonumber(p[2]), method = p[3], entry_id = p[4],
                                         alt_entry_id = p[5], unmatched_number = p[7], shot = p[8], order_flag = p[9] == "1",
                                         colour = p[10] or "", colour_flag = p[11] == "1", sponsor = p[12] or "",
                                         anchor_flag = p[13] == "1" })
        end
    end
    return rows_of, errored, skipped
end

-- The start-list import's column roles, as import_start_list.py ROLES names them.
M.IMPORT_ROLES = { "number", "driver", "co-driver", "team", "class", "make", "model", "shares-car", "paddock" }

-- `import_start_list.py --header` output → (CSV headers in order, {role = mapped header or ""}).
function M.parse_header_report(out)
    local headers, mapped = {}, {}
    for line in (out or ""):gmatch("[^\r\n]+") do
        local h = line:match("^header\t(.*)$")
        if h then
            headers[#headers + 1] = h
        else
            local role, name = line:match("^role\t([^\t]+)\t(.*)$")
            if role then mapped[role] = name end
        end
    end
    return headers, mapped
end

-- {role = header or ""} → the --columns value, every role named so "" stops the usual-name guess.
function M.columns_spec(picked)
    local parts = {}
    for _, role in ipairs(M.IMPORT_ROLES) do parts[#parts + 1] = role .. "=" .. (picked[role] or "") end
    return table.concat(parts, ";")
end

-- Tags usable to build an entry: hierarchical (A|B), not the plugin's own
-- diagnostics, and clean enough for entries.json (no , ; ").
local ASSISTED_PREFIX = "Assisted Tagging|"


function M.hierarchical_tags(names)
    local out = {}
    for _, n in ipairs(names) do
        if n:find("|", 1, true) and n:sub(1, #ASSISTED_PREFIX) ~= ASSISTED_PREFIX and not n:find('[,;"]') then
            out[#out + 1] = n
        end
    end
    table.sort(out)
    return out
end

local function tag_depth(tag)
    local n = 0
    for _ in tag:gmatch("|") do n = n + 1 end
    return n
end

local function tag_leaf(tag)
    return tag:match("([^|]+)$")
end

-- entries.json's id can't hold , ; " / \ : * ? < > |
function M.sanitize_id(s)
    s = (s or ""):gsub('[,;"/\\:*?<>|]', "-"):gsub("^%s+", ""):gsub("%s+$", "")
    return s ~= "" and s or "entry"
end

-- A single sample tells the matcher nothing about what varies between photos of the
-- same target (angle, light, crop); below this many it can't "understand" the target,
-- motorsport livery or not, so the group is reported instead of becoming an entry.
M.MIN_REFS_PER_ENTRY = 2

-- images: { { key = <string>, tags = {<raw tag name>, ...} }, ... }. Groups images
-- carrying the exact same hierarchical tags into one entry: the shared tags become
-- the entry's tags, and a tag shared with some but not every other group becomes an
-- inferred team (one every group shares identifies no one; one shared with no one
-- isn't a team). The entry's id is seeded from its deepest tag, e.g. "Team|Driver" ->
-- "Driver"; but if that deepest tag's leaf is 1-3 digits AND there's a tag one level
-- up (e.g. "Team|Driver|44"), the number comes from the digits and the id instead
-- comes from that shallower tag, so a numbered entry still gets a readable id. With
-- no such shallower tag (e.g. just "Team|44"), the old behaviour holds: the digits
-- seed both the id and the number.
-- Returns entries ({ id, number, team, tags }, first-seen order), entry_of (key -> id),
-- skipped (keys with no usable hierarchical tag), and thin (keys whose tags matched
-- fewer than MIN_REFS_PER_ENTRY images, so no entry was built for them).
function M.derive_entries(images)
    local groups, order, skipped = {}, {}, {}
    for _, img in ipairs(images) do
        local tags = M.hierarchical_tags(img.tags)
        if #tags == 0 then
            skipped[#skipped + 1] = img.key
        else
            local sig = table.concat(tags, "\30")
            if not groups[sig] then
                groups[sig] = { tags = tags, keys = {} }
                order[#order + 1] = sig
            end
            table.insert(groups[sig].keys, img.key)
        end
    end

    local function deepest(tags)
        local best = tags[1]
        for _, t in ipairs(tags) do
            if tag_depth(t) > tag_depth(best) or (tag_depth(t) == tag_depth(best) and t > best) then best = t end
        end
        return best
    end

    local function is_number_tag(t)
        return tag_leaf(t):match("^%d%d?%d?$") ~= nil
    end

    local used_ids, entries, entry_of, thin = {}, {}, {}, {}
    for _, sig in ipairs(order) do
        local g = groups[sig]
        if #g.keys < M.MIN_REFS_PER_ENTRY then
            for _, k in ipairs(g.keys) do thin[#thin + 1] = k end
        else
            local deep = deepest(g.tags)
            local own_deep, number_tag = deep, nil
            if #g.tags >= 3 and is_number_tag(deep) then
                -- The deepest tag is a number and there's a level besides team beneath
                -- it: it's a "Team|Driver|Number" chain, so the number comes from here
                -- and the id instead comes from the driver tag one level up.
                number_tag = deep
                local parent_depth = tag_depth(deep) - 1
                for _, t in ipairs(g.tags) do
                    if tag_depth(t) == parent_depth then own_deep = t end
                end
            end
            local base = M.sanitize_id(tag_leaf(own_deep))
            local id, n = base, 1
            while used_ids[id] do n = n + 1; id = base .. "-" .. n end
            used_ids[id] = true

            local team, team_depth = "", -1
            for _, t in ipairs(g.tags) do
                if t ~= own_deep and t ~= number_tag then
                    local shared_by, shared_with_all = 0, true
                    for _, osig in ipairs(order) do
                        local has = false
                        for _, t2 in ipairs(groups[osig].tags) do
                            if t2 == t then has = true; break end
                        end
                        if has then shared_by = shared_by + 1 else shared_with_all = false end
                    end
                    if shared_by > 1 and not shared_with_all and tag_depth(t) > team_depth then
                        team, team_depth = tag_leaf(t), tag_depth(t)
                    end
                end
            end

            local number = number_tag and tag_leaf(number_tag) or (tag_leaf(own_deep):match("^%d%d?%d?$") or "")
            entries[#entries + 1] = { id = id, number = number, team = team, tags = g.tags }
            for _, k in ipairs(g.keys) do entry_of[k] = id end
        end
    end
    return entries, entry_of, skipped, thin
end

local function json_string(s)
    return '"' .. tostring(s):gsub('\\', '\\\\'):gsub('"', '\\"') .. '"'
end

-- An entries.json for derived entries: each with its full tags. Entries already carry only
-- ids/tags/numbers that passed sanitize_id/hierarchical_tags/the digit check, so this never
-- needs to reject input.
function M.entries_json(entries)
    local parts = {}
    for _, e in ipairs(entries) do
        local tag_parts = {}
        for _, t in ipairs(e.tags) do tag_parts[#tag_parts + 1] = json_string(t) end
        parts[#parts + 1] = string.format('    { "id": %s, "number": %s, "team": %s, "tags": [%s] }',
            json_string(e.id), json_string(e.number or ""), json_string(e.team or ""), table.concat(tag_parts, ", "))
    end
    return '{\n  "entries": [\n' .. table.concat(parts, ",\n") .. "\n  ]\n}\n"
end


-- A collection's settings (settings.json beside entries.json). The built-in "template"
-- holds these defaults. replace_manual is a panel preference (darktable prefs), not a collection setting.
-- Mirrors SETTINGS_SCHEMA in python/settings.py (test_settings.py checks keys and defaults).
M.PRESET_SCHEMA = {
    { key = "use_hints", kind = "bool", default = true },
    { key = "group_support", kind = "choice", choices = { "native", "tags", "none" }, default = "native" },
    { key = "group_node", kind = "string", default = "" },
    { key = "run_tag", kind = "choice", choices = { "none", "changed", "all" }, default = "none" },
    { key = "suggest_crops", kind = "bool", default = false },
    { key = "quarantine", kind = "bool", default = false },
    { key = "cars_per_photo", kind = "choice", choices = { "solo", "packs" }, default = "solo" },
    { key = "closer_car_margin", kind = "number", default = 0 },
    { key = "order_weight", kind = "number", default = 0 },
    { key = "neighbour_tolerance", kind = "number", default = 5 },
    { key = "min_read", kind = "number", default = 0.85 },
    { key = "colour_weight", kind = "number", default = 0 },
    { key = "partial_references", kind = "bool", default = false },
    { key = "min_sim", kind = "number", default = 0.5 },
    { key = "margin", kind = "number", default = 0.05 },
    { key = "min_face_px", kind = "number", default = 48 },
    { key = "burst_livery_pooling", kind = "bool", default = false },
    { key = "blur_references", kind = "bool", default = false },
    { key = "family_colour", kind = "bool", default = true },
    { key = "family_colour_root", kind = "string", default = "Assisted Tagging|Motorsport|Colour" },
    { key = "family_number", kind = "bool", default = true },
    { key = "family_number_root", kind = "string", default = "Assisted Tagging|Motorsport|Number" },
    { key = "family_team", kind = "bool", default = true },
    { key = "family_team_root", kind = "string", default = "Assisted Tagging|Motorsport|Team" },
    { key = "family_driver", kind = "bool", default = true },
    { key = "family_driver_root", kind = "string", default = "Assisted Tagging|Motorsport|Driver" },
    { key = "family_co_driver", kind = "bool", default = true },
    { key = "family_co_driver_root", kind = "string", default = "Assisted Tagging|Motorsport|Co-driver" },
    { key = "family_extra", kind = "bool", default = true },
    { key = "family_extra_root", kind = "string", default = "Assisted Tagging|Motorsport|Class" },
    { key = "family_vehicle", kind = "bool", default = true },
    { key = "family_vehicle_root", kind = "string", default = "Assisted Tagging|Motorsport|Vehicle" },
    { key = "family_sponsor", kind = "bool", default = false },
    { key = "family_sponsor_root", kind = "string", default = "Assisted Tagging|Motorsport|Sponsor" },
    { key = "tag_number", kind = "bool", default = true },
    { key = "tag_number_name", kind = "string", default = "Assisted Tagging|Identification|By number" },
    { key = "tag_livery", kind = "bool", default = true },
    { key = "tag_livery_name", kind = "string", default = "Assisted Tagging|Identification|By livery" },
    { key = "tag_burst", kind = "bool", default = true },
    { key = "tag_burst_name", kind = "string", default = "Assisted Tagging|Identification|By burst" },
    { key = "tag_pooled", kind = "bool", default = true },
    { key = "tag_pooled_name", kind = "string", default = "Assisted Tagging|Identification|By pooled burst" },
    { key = "tag_neighbour", kind = "bool", default = true },
    { key = "tag_neighbour_name", kind = "string", default = "Assisted Tagging|Identification|By neighbour" },
    { key = "tag_check_order", kind = "bool", default = true },
    { key = "tag_check_order_name", kind = "string", default = "Assisted Tagging|Identification|Check order" },
    { key = "tag_team", kind = "bool", default = true },
    { key = "tag_team_name", kind = "string", default = "Assisted Tagging|Identification|Team only" },
    { key = "tag_none", kind = "bool", default = true },
    { key = "tag_none_name", kind = "string", default = "Assisted Tagging|Identification|Unidentified" },
    { key = "tag_number_seen", kind = "bool", default = true },
    { key = "tag_number_seen_name", kind = "string", default = "Assisted Tagging|Identification|Number seen" },
    { key = "tag_check_colour", kind = "bool", default = true },
    { key = "tag_check_colour_name", kind = "string", default = "Assisted Tagging|Identification|Check colour" },
    { key = "tag_check_match", kind = "bool", default = true },
    { key = "tag_check_match_name", kind = "string", default = "Assisted Tagging|Identification|Check match" },
    { key = "tag_shot", kind = "bool", default = true },
    { key = "tag_shot_name", kind = "string", default = "Assisted Tagging|Identification|Shot" },
    { key = "tag_shot_crowded", kind = "bool", default = true },
    { key = "tag_shot_crowded_name", kind = "string", default = "Assisted Tagging|Identification|Shot" },
    { key = "tag_derived", kind = "bool", default = true },
    { key = "tag_derived_name", kind = "string", default = "Assisted Tagging|Derived" },
}

-- Number ranges, as SETTINGS_SCHEMA's lo/hi (open = the bound itself is out) and whole numbers.
local SETTING_RANGES = {
    closer_car_margin = { lo = 0, hi = 1 },
    order_weight = { lo = 0, hi = 1 },
    neighbour_tolerance = { lo = 0, integer = true },
    min_read = { lo = 0, hi = 1 },
    colour_weight = { lo = 0 },
    min_sim = { lo = 0, hi = 1, lo_open = true },
    margin = { lo = 0, hi = 1, hi_open = true },
    min_face_px = { lo = 1, integer = true },
}

local SCHEMA_BY_KEY = {}
for _, item in ipairs(M.PRESET_SCHEMA) do SCHEMA_BY_KEY[item.key] = item end

-- Settings that no longer exist → the family setting that replaced each
-- (python/settings.py REMOVED_KEYS).
local REMOVED_SETTINGS = {
    { "colour_tags", "family_colour" },
    { "tag_colour", "family_colour" },
    { "tag_colour_name", "family_colour_root" },
}
-- Model-file settings the plugin now picks itself (python/settings.py MODEL_KEYS_GONE).
-- A blank value is ignored; a set one stops the run.
local MODEL_SETTINGS_GONE = { "embedder_file", "ocr_rec_file" }

-- Why decoded settings.json `s` can't be used: the first removed key it still holds, worded as
-- identify.py words it. nil when it holds none.
function M.removed_settings(s)
    for _, pair in ipairs(REMOVED_SETTINGS) do
        if s[pair[1]] ~= nil then
            return string.format('settings.json: %s was removed; use %s (README, "Tag families")', pair[1], pair[2])
        end
    end
    for _, key in ipairs(MODEL_SETTINGS_GONE) do
        local v = s[key]
        if type(v) == "string" then v = v:match("^%s*(.-)%s*$") end
        if v ~= nil and v ~= "" then
            return string.format('settings.json: %s was removed; the plugin picks the model now (README, "Models")', key)
        end
    end
    return nil
end

-- Panel entry text for setting `key` → its value, or nil and why. Blank text is an error;
-- the panel decides what blank means.
function M.parse_setting(key, text)
    local item = SCHEMA_BY_KEY[key]
    if not item then return nil, "unknown setting" end
    local t = tostring(text or ""):match("^%s*(.-)%s*$")
    if t == "" then return nil, "blank" end
    if item.kind == "string" then
        if key:match("_name$") and t:find('[,;"]') then return nil, 'a tag name can\'t hold , ; or "' end
        if key:match("^family_.+_root$") then
            if t:find('[,;"]') then return nil, 'can\'t contain , ; or "' end
            if t:find("^|") or t:find("|$") then return nil, "can't start or end with | or a space" end
        end
        return t
    end
    if item.kind == "bool" then
        if t == "true" then return true end
        if t == "false" then return false end
        return nil, "not true or false"
    end
    if item.kind == "choice" then
        for _, c in ipairs(item.choices) do
            if c == t then return t end
        end
        return nil, "not one of the choices"
    end
    local n = tonumber(t)
    if not n or n ~= n or n == math.huge or n == -math.huge then return nil, "not a number" end
    local r = SETTING_RANGES[key] or {}
    if r.integer then
        if n ~= math.floor(n) then return nil, "not a whole number" end
        n = math.tointeger(n)
    end
    if r.lo and (r.lo_open and n <= r.lo or n < r.lo) then return nil, "below " .. r.lo end
    if r.hi and (r.hi_open and n >= r.hi or n > r.hi) then return nil, "above " .. r.hi end
    return n
end

-- A panel entry's value: blank → the schema default; invalid → nil and "<key>: <why>".
function M.panel_value(key, text)
    if tostring(text or ""):match("^%s*$") then return SCHEMA_BY_KEY[key].default end
    local value, why = M.parse_setting(key, text)
    if value == nil then return nil, key .. ": " .. why end
    return value
end

-- A copy of settings `s` with every PRESET_SCHEMA key present: a missing key gets its
-- default (not listed), and each number, tag name or family root that M.parse_setting refuses (e.g. a
-- hand-edited settings.json out of range) is set to its default and listed in `replaced`.
function M.checked_settings(s)
    local out, replaced = {}, {}
    for k, v in pairs(s) do out[k] = v end
    for _, item in ipairs(M.PRESET_SCHEMA) do
        local key = item.key
        if s[key] == nil then
            out[key] = item.default
        elseif item.kind == "number" or key:match("^tag_.+_name$") or key:match("^family_.+_root$") then
            if M.parse_setting(key, tostring(s[key] or "")) == nil then
                out[key] = item.default
                replaced[#replaced + 1] = key
            end
        end
    end
    return out, replaced
end

-- A settings key's value as rules.csv resolved it: rules.settings, or for the tag_* keys
-- the diagnostic names (off = ""). Nil when rules.csv doesn't say.
local function rules_value(rules, key)
    if rules.settings and rules.settings[key] ~= nil then return rules.settings[key] end
    local name_of = key:match("^tag_(.-)_name$")
    local on_of = not name_of and key:match("^tag_(.+)$")
    local which = name_of or on_of
    if not which then return nil end
    local name = rules.diag[which == "shot" and "shot_solo" or which]
    if name == nil then return nil end
    if on_of then return name ~= "" end
    if name == "" then return nil end
    if which == "shot_crowded" then return name:match("^(.*)|Crowded$") end
    if which ~= "shot" then return name end
    return name:match("^(.*)|Solo$")
end

-- Copies the settings identify.py still read from entries.json's old "rules" into the stored
-- settings.json text, only where the stored value is missing, blank or invalid. Returns the new
-- text and the keys copied, or nil when nothing changed (or the stored text isn't JSON).
function M.backfill_settings(stored_text, rules)
    local decoded = stored_text and M.preset_decode(stored_text)
    if not decoded then return nil end
    local merged, problems = M.preset_merge(M.PRESET_SCHEMA, decoded)
    local bad = {}
    for _, key in ipairs(problems) do bad[key] = true end
    local copied = {}
    for _, key in ipairs(rules.from_entries_json or {}) do
        local stored = decoded[key]
        local usable = stored ~= nil and not bad[key] and M.parse_setting(key, tostring(stored)) ~= nil
        local value = SCHEMA_BY_KEY[key] and rules_value(rules, key)
        if not usable and value ~= nil then
            merged[key] = value
            copied[#copied + 1] = key
        end
    end
    if #copied == 0 then return nil end
    return M.preset_encode(M.PRESET_SCHEMA, merged), copied
end

-- Old settings.json text predates the Shot crowded switch: copies tag_shot and tag_shot_name into
-- the missing tag_shot_crowded and tag_shot_crowded_name. It may also hold run_tag as true/false,
-- from before the choice: true becomes "all", false "none". Returns the new text and the keys
-- changed, or the text unchanged and nil when nothing changed (or the text isn't JSON).
function M.upgrade_settings_text(text)
    local decoded = text and M.preset_decode(text)
    if not decoded then return text, nil end
    local copied = {}
    if type(decoded.run_tag) == "boolean" then
        decoded.run_tag = decoded.run_tag and "all" or "none"
        copied[#copied + 1] = "run_tag"
    end
    for _i, pair in ipairs({ { "tag_shot_crowded", "tag_shot" }, { "tag_shot_crowded_name", "tag_shot_name" } }) do
        if decoded[pair[1]] == nil and decoded[pair[2]] ~= nil then
            decoded[pair[1]] = decoded[pair[2]]
            copied[#copied + 1] = pair[1]
        end
    end
    if #copied == 0 then return text, nil end
    local merged = M.preset_merge(M.PRESET_SCHEMA, decoded)
    return M.preset_encode(M.PRESET_SCHEMA, merged), copied
end

-- The settings file a GUI run passes as --settings: the panel's values, beside the run's
-- other temp files (`base` is their shared name prefix).
function M.run_settings_path(base)
    return base .. "settings.run.json"
end

-- One "tag_<outcome>" setting per diagnostic under Assisted Tagging|Identification
-- (keys match M.DIAG_TAGS / the rules' diag_<outcome>; "shot" covers Solo and Pack).
-- Off = runs stop writing it and detach it from the images they process. Entry and
-- unidentified tags (entries.json) and identification itself are unchanged.
local TAG_TOGGLES = {
    { key = "number", kind = "diag", label = "By number", when = "its race number was read." },
    { key = "livery", kind = "diag", label = "By livery", when = "it matched the entry's reference samples." },
    { key = "burst", kind = "diag", label = "By burst", when = "the rest of its burst agreed on one entry." },
    { key = "pooled", kind = "diag", label = "By pooled burst",
      when = "the experimental burst_livery_pooling rule resolved it from its burst's pooled livery similarity." },
    { key = "neighbour", kind = "diag", label = "By neighbour",
      when = "a doubtful number read was settled by the groups shot just before and after. Needs the collection's order_weight above 0." },
    { key = "check_order", kind = "check", label = "Check order",
      when = "a low-confidence number read that no neighbouring group supports. The entry tag stays; delete this tag once checked." },
    { key = "team", kind = "diag", label = "Team only", when = "two teammates were too close to call; only their shared tags are added." },
    { key = "none", kind = "check", label = "Unidentified (check)", when = "no vehicle was found, or no confident match." },
    { key = "number_seen", kind = "diag", label = "Number seen",
      when = "OCR read digits that didn't resolve to one entry. Added alongside the outcome tag." },
    { key = "check_colour", kind = "check", label = "Check colour",
      when = "the number read is confident but the car's colour differs from its entry's. Delete this tag once checked." },
    { key = "check_match", kind = "check", label = "Check match",
      when = "a livery, burst or neighbour match didn't look like the car's anchors (refs you tagged or picked, or strong number reads), so no entry tag was added. Tag the photo by hand if it is that car. With closer_car_margin above 0, a match clearly closer to another car's anchors is tagged as that car and keeps this tag: check it." },
    { key = "shot", kind = "check", label = "Shot",
      when = "Solo: one vehicle found. Pack: two or three." },
    { key = "shot_crowded", kind = "check", label = "Shot crowded",
      when = "three or more cars were in frame, so the number read may belong to another car: check it by hand." },
    { key = "derived", kind = "diag", label = "Derived from",
      when = "an entry's tags were added. From identification: Identify's models picked the entry. From number / From driver: your hand tag named it. From colour: Derive from colour found one entry of that colour." },
}
M.TAG_TOGGLES = TAG_TOGGLES

-- Tag switches whose tag needs another setting: `on` takes that setting's raw value (nil when
-- missing = off) and `off` is the suffix the row's label shows while the setting is off.
M.TAG_GATES = {
    { key = "check_colour", by = "family_colour", on = function(v) return v and true or false end,
      off = "the Colour family is off" },
    { key = "neighbour", by = "order_weight",
      on = function(v) return (tonumber(v) or 0) > 0 end, off = "order weight is 0" },
    { key = "pooled", by = "burst_livery_pooling", on = function(v) return v and true or false end,
      off = "burst_livery_pooling is off in settings.json" },
}

-- A TAG_TOGGLES row's label under `settings`: the plain label, or "<label> (off: <why>)" and
-- true when one of its gates is off.
function M.tag_row_label(t, settings)
    for _i, g in ipairs(M.TAG_GATES) do
        if g.key == t.key and not g.on(settings[g.by]) then
            return t.label .. " (off: " .. g.off .. ")", true
        end
    end
    return t.label, false
end

-- Headings of the tags-written page, in order; each TAG_TOGGLES row's `kind` is one of these.
M.TAG_KINDS = {
    { kind = "check", label = "checks" },
    { kind = "diag", label = "how it decided" },
}

-- TAG_TOGGLES rows grouped by TAG_KINDS order, file order within a kind.
function M.tag_rows_in_order()
    local rows = {}
    for _i, k in ipairs(M.TAG_KINDS) do
        for _j, t in ipairs(TAG_TOGGLES) do
            if t.kind == k.kind then rows[#rows + 1] = t end
        end
    end
    return rows
end

-- The panel's pages and the preset keys each page's widgets edit (C.page_coverage checks them).
local tag_page_keys = {}
for _i, f in ipairs(M.FAMILIES) do
    tag_page_keys[#tag_page_keys + 1] = "family_" .. f.key
    tag_page_keys[#tag_page_keys + 1] = "family_" .. f.key .. "_root"
end
for _i, t in ipairs(TAG_TOGGLES) do
    tag_page_keys[#tag_page_keys + 1] = "tag_" .. t.key
    tag_page_keys[#tag_page_keys + 1] = "tag_" .. t.key .. "_name"
end
M.PANEL_PAGES = {
    { number = 1, title = "collection", keys = {} },
    { number = 2, title = "bursts", keys = { "group_support", "group_node" } },
    { number = 3, title = "matching", keys = { "cars_per_photo", "use_hints",
        "neighbour_tolerance", "order_weight", "min_read", "colour_weight", "partial_references" } },
    { number = 4, title = "tags written", keys = tag_page_keys },
    { number = 5, title = "run", keys = { "run_tag" } },
    { number = 6, title = "references", keys = { "suggest_crops", "quarantine" } },
}
-- settings.json only, no panel widget
M.PANEL_OTHER_KEYS = { "closer_car_margin", "min_sim", "margin", "min_face_px", "burst_livery_pooling", "blur_references" }

-- Model files per job, best first. `base` is the base install (README, "Models"), the last
-- file when unset; files after it are older fallbacks, then models on trial (PP-OCRv6 small,
-- used only when nothing listed before it is installed). A run passes the first file present
-- in models/ to identify.py. Listed in log order and also indexed by job name.
M.MODEL_LISTS = {
    { job = "vehicles", flag = "--detector", files = { "dfine_x_coco.onnx", "dfine_l_coco.onnx",
        "rtdetr_v2_r50vd.onnx", "dfine_m_coco.onnx", "dfine_s_coco.onnx", "object_detection_yolox_2022nov.onnx" } },
    { job = "segmenter", flag = "--segmenter", optional = true, files = {
        "image_segmentation_efficientsam_ti_2025april.onnx" } },
    { job = "text finder", flag = "--ocr-det", base = "text_detection_en_ppocrv3_2023may.onnx",
        files = { "text_detection_en_ppocrv3_2023may.onnx", "PP-OCRv6_small_det.onnx" } },
    { job = "number reader", flag = "--ocr-rec", base = "en_PP-OCRv5_mobile_rec.onnx and its .yml",
        files = { "PP-OCRv5_server_rec.onnx", "en_PP-OCRv5_mobile_rec.onnx", "text_recognition_CRNN_EN_2021sep.onnx",
            "PP-OCRv6_small_rec.onnx" } },
    { job = "livery embedder", flag = "--embedder", files = { "dinov2_large.onnx", "dinov2_base.onnx", "dinov2_small.onnx" } },
    { job = "box check", flag = "--siglip", optional = true, files = { "siglip2_base_vision.onnx" } },
    { job = "face detector", flag = "--face-detector", optional = true, files = { "face_detection_yunet_2023mar.onnx" } },
    { job = "face recognizer", flag = "--face-recognizer", optional = true, files = { "face_recognition_sface_2021dec.onnx" } },
}
for _, item in ipairs(M.MODEL_LISTS) do M.MODEL_LISTS[item.job] = item end

-- Files that must sit beside model file `path` for `job`: SigLIP 2's text model and tokenizer,
-- named after its vision file. Empty for every other job.
function M.model_siblings(path, job)
    if job ~= "box check" then return {} end
    return { (path:gsub("vision%.onnx$", "text.onnx")), (path:gsub("vision%.onnx$", "tokenizer.json")) }
end

-- Whether model file `path` for `job` can be used, `exists(path)` saying what is on disk.
-- A PaddleOCR model (any number reader but the CRNN, any text finder but opencv_zoo's PP-OCRv3)
-- also needs its .yml beside it, and the box check its M.model_siblings.
function M.model_present(path, job, exists)
    if not exists(path) then return false end
    for _, sibling in ipairs(M.model_siblings(path, job)) do
        if not exists(sibling) then return false end
    end
    local paddle = job == "number reader" and not path:match("text_recognition_CRNN[^/\\]*$")
        or job == "text finder" and not path:match("text_detection_en_ppocrv3[^/\\]*$")
    return not paddle or exists((path:gsub("%.onnx$", ".yml")))
end

-- The first file of `files` for which `present(file)` holds, or nil; and the files before it
-- that are absent (all of them when none is present).
function M.pick_model(files, present)
    local missing = {}
    for _, file in ipairs(files) do
        if present(file) then return file, missing end
        missing[#missing + 1] = file
    end
    return nil, missing
end

-- `no_yml`: set of files in `missing_better` that are on disk but lack their .yml.
function M.pick_log_line(job, picked, missing_better, no_yml)
    local absent, partial = {}, {}
    for _, file in ipairs(missing_better) do
        if no_yml and no_yml[file] then partial[#partial + 1] = file else absent[#absent + 1] = file end
    end
    local line = job .. ": " .. picked
    if #absent > 0 then line = line .. " (better, not installed: " .. table.concat(absent, ", ") .. ")" end
    if #partial > 0 then line = line .. " (better, no .yml beside it: " .. table.concat(partial, ", ") .. ")" end
    return line
end

function M.missing_model_message(item)
    return string.format('Assisted Tagging: no %s model in models/. Install %s (README, "Models").',
        item.job, item.base or item.files[#item.files])
end

-- One MODEL_LISTS item → { file = picked or nil, line = run-log line, err = message when a
-- required job has nothing installed, or a model is on disk without its M.model_siblings }.
-- `on_disk(file)`, optional, says a file exists even when `present` rejects it (a reader
-- without its .yml).
function M.model_choice(item, present, on_disk)
    local file, missing = M.pick_model(item.files, present)
    if file then
        local no_yml = {}
        for _, f in ipairs(missing) do
            if on_disk and on_disk(f) then no_yml[f] = true end
        end
        return { file = file, line = M.pick_log_line(item.job, file, missing, no_yml) }
    end
    for _, f in ipairs(missing) do
        local siblings = M.model_siblings(f, item.job)
        if #siblings > 0 and on_disk and on_disk(f) then
            local absent = {}
            for _, sibling in ipairs(siblings) do
                if not on_disk(sibling) then absent[#absent + 1] = sibling end
            end
            return { line = item.job .. ": " .. f .. " is missing files", err = string.format(
                'Assisted Tagging: %s needs %s beside it in models/ (README, "Models").', f, table.concat(absent, " and ")) }
        end
    end
    if item.optional then return { line = item.job .. ": none installed" } end
    return { line = item.job .. ": none installed", err = M.missing_model_message(item) }
end

-- identify.py's progress line: `stage,cur,tot,cached` ({ stage, cur, tot, cached }), or the
-- older `cur,tot` (stage nil, cached 0). nil when there is no line yet.
function M.parse_progress(line)
    local stage, cur, tot, cached = (line or ""):match("^([%a ]+),(%d+),(%d+),(%d+)")
    if not stage then
        cur, tot = (line or ""):match("^(%d+),(%d+)")
        if not cur then return nil end
        cached = "0"
    end
    return { stage = stage, cur = tonumber(cur), tot = tonumber(tot), cached = tonumber(cached) }
end

local ok, dt = pcall(require, "darktable")
if not ok then return M end

local du = require "lib/dtutils"
local df = require "lib/dtutils.file"
local tags = dt.tags

du.check_min_api_version("7.0.0", "assisted_tagging")

local gettext = dt.gettext.gettext
local function _(msgid)
    return gettext(msgid)
end

-- Every tag attach/detach rewrites the XMP sidecar and queues a GUI event, so writes are paced:
-- after a budget of writes the run waits for darktable to catch up (wait_for_writes).
local WRITE_BUDGET = 12
local WRITE_SLEEP_MS = 20

local IS_WINDOWS = C.IS_WINDOWS

local TMP_DIR = dt.configuration.tmp_dir
-- Leftovers of a darktable that crashed or was killed mid-run; a day old is surely not live.
C.sweep_temp(TMP_DIR, "dt_assisted_tagging_", 86400)
-- This instance's temp files: named per darktable instance, so two darktables (or a
-- crashed one's orphaned identify.py) never read or write each other's.
local TMP_BASE = C.temp_base(TMP_DIR, "dt_assisted_tagging_")
local MANIFEST_PATH = TMP_BASE .. "manifest.csv"
local RESULTS_PATH = TMP_BASE .. "results.csv"
local NEIGHBOURS_PATH = TMP_BASE .. "neighbours.csv"
local ENTRIES_PATH = TMP_BASE .. "entries.csv"
local RULES_PATH = TMP_BASE .. "rules.csv"
local COLLECTIONS_PATH = TMP_BASE .. "collections.csv"
local PROGRESS_PATH = TMP_BASE .. "progress.txt"
local CANCEL_PATH = PROGRESS_PATH .. ".cancel"
local DONE_PATH = TMP_BASE .. "done.txt"
local RUN_SETTINGS_PATH = M.run_settings_path(TMP_BASE)
-- The run log: this plugin's lines plus identify.py's stderr. Kept in the
-- config dir, which outlives tmp_dir; the run before it is kept as .prev.log.
local LOG_PATH = dt.configuration.config_dir .. "/assisted_tagging.log"
local PREV_LOG_PATH = dt.configuration.config_dir .. "/assisted_tagging.prev.log"
-- Lua errors (panel build, callbacks, events) go to their own log, which runs never rotate.
local LUA_LOG_PATH = dt.configuration.config_dir .. "/assisted_tagging.lua.log"
local guard = C.error_guard(dt, LUA_LOG_PATH, "Assisted Tagging")
local new_widget = C.guarded_widget_maker(dt, guard)
local CACHE_PATH = dt.configuration.config_dir .. "/assisted_tagging/cache.sqlite"
local LEDGER_PATH = dt.configuration.config_dir .. "/assisted_tagging/ledger.csv"
local LIB_KEY = C.library_key(dt)
local LAST_RUN_DIR = dt.configuration.config_dir .. "/assisted_tagging/last-run"
local RUNS_DIR = dt.configuration.config_dir .. "/assisted_tagging/runs"
local DEFAULT_COLLECTIONS_ROOT = dt.configuration.config_dir .. "/assisted_tagging/collections"

if dt.gui then
    C.register_shared_prefs(dt)
    dt.preferences.register("assisted_tagging", "collections_root", "directory",
        "Assisted Tagging: collections folder",
        "Folder with one folder per collection (entries.json + refs). Empty = assisted_tagging/collections in darktable's config folder",
        "")
end

local file_exists, first_existing, read_file = C.file_exists, C.first_existing, C.read_file

-- Defined with the log buffer further down; the preference readers log deprecations.
local log

local function plugin_folder_pref()
    return C.plugin_folder(dt, "assisted_tagging", "darktable-assisted-tagging", log)
end

-- The script is found from the plugin folder preference alone when it's set; a
-- wrong folder is an error rather than a quiet switch to some other copy.
local function identify_script()
    local folder = plugin_folder_pref()
    if folder ~= "" then
        local script = folder .. "/python/identify.py"
        if not file_exists(script) then
            error(string.format("Assisted Tagging: the plugins folder preference gives %s, which has no python/identify.py. Point it at the folder holding darktable-assisted-tagging, or clear it to auto-detect.", folder), 0)
        end
        return script
    end
    local found = first_existing({
        THIS_DIR .. "/identify.py",
        THIS_DIR .. "/python/identify.py",
        THIS_DIR .. "/../python/identify.py",
        THIS_DIR .. "/../../python/identify.py",
    })
    return found or (THIS_DIR .. "/identify.py")
end

local function plugin_root(script)
    local folder = plugin_folder_pref()
    if folder ~= "" then return folder end
    local script_dir = (script and script:match("^(.*)[/\\]")) or THIS_DIR
    return script_dir:match("^(.*)[/\\]python$") or script_dir
end

local function python_bin(script)
    local root = plugin_root(script)
    local found = first_existing({
        root .. "/.venv/Scripts/python.exe",
        root .. "/.venv/bin/python",
        THIS_DIR .. "/../.venv/Scripts/python.exe",
        THIS_DIR .. "/../.venv/bin/python",
    })
    if found then return found end

    local v = df.check_if_bin_exists(IS_WINDOWS and "python" or "python3")
    if not v then
        v = IS_WINDOWS and "python" or "python3"
    end
    return v
end

-- A model in the plugin folder's models/. A missing file is passed through
-- as-is, so identify.py names it in its error.
local function collections_root()
    local pref = dt.preferences.read("assisted_tagging", "collections_root", "directory") or ""
    return pref ~= "" and pref or DEFAULT_COLLECTIONS_ROOT
end

-- The selected collection's folder name; "" = the template (no collection).
local function current_collection()
    return dt.preferences.read("assisted_tagging", "last_collection", "string") or ""
end

-- The settings a run reads: the selected collection's settings.json, or the panel's values
-- when a GUI run starts. A collection without settings.json (or the template) uses defaults.
local function collection_settings(name)
    local f = name ~= "" and io.open(collections_root() .. "/" .. name .. "/settings.json", "rb")
    if not f then return M.preset_defaults(M.PRESET_SCHEMA) end
    local text = f:read("a")
    f:close()
    text = M.upgrade_settings_text(text)
    -- Hand-edited blank or invalid values fall back to the default here too (show_panel logs them).
    return (M.checked_settings(M.preset_merge(M.PRESET_SCHEMA, M.preset_decode(text) or {})))
end
local settings = collection_settings(current_collection())

-- M.removed_settings of the selected collection's settings.json; nil for the template.
local function removed_setting()
    local name = current_collection()
    local f = name ~= "" and io.open(collections_root() .. "/" .. name .. "/settings.json", "rb")
    if not f then return nil end
    local text = f:read("a")
    f:close()
    return M.removed_settings(M.preset_decode(text) or {})
end

local function entries_json_path()
    return collections_root() .. "/" .. current_collection() .. "/entries.json"
end

local function settings_json_path()
    return collections_root() .. "/" .. current_collection() .. "/settings.json"
end

-- The repo's shipped example collections (entries.json templates, no refs), a
-- sibling of python/. Missing if the repo was trimmed down to just the plugin.
local function examples_root()
    return plugin_root(plugin_folder_pref() == "" and identify_script() or nil) .. "/examples"
end

local shell_quote, command_line, run_async_python = C.shell_quote, C.command_line, C.run_async_python

-- Lists → one list, in order: argument lists built in parts.
local function args_of(...)
    local out = {}
    for _, part in ipairs({ ... }) do table.move(part, 1, #part, #out + 1, out) end
    return out
end

local function read_log_tail()
    local t = read_file(LOG_PATH) or ""
    t = t:gsub("%s+$", "")
    if #t > 800 then t = t:sub(#t - 799) end
    return t
end

local function fmt_eta(elapsed, done, total)
    if elapsed < 3 or done <= 0 or done >= total then return "" end
    local remaining = math.ceil(elapsed * (total - done) / done)
    return string.format(" | ~%dm %02ds left", remaining // 60, remaining % 60)
end

-- Lines wait here while identify.py appends its stderr to the same file:
-- two processes appending at once can overwrite each other's lines on Windows.
local log_buffer = {}

function log(msg)
    log_buffer[#log_buffer + 1] = os.date("%H:%M:%S ") .. "lua: " .. msg
end

-- Only call while no identify.py process is running.
local function flush_log()
    if #log_buffer == 0 then return end
    local f = io.open(LOG_PATH, "a")
    if not f then return end
    f:write(table.concat(log_buffer, "\n"), "\n")
    f:close()
    log_buffer = {}
end

local function say(msg)
    dt.print(msg)
    log(msg)
end

-- dt.print_error only writes to darktable's log (-d lua); users never see it.
local function notify_error(msg)
    dt.print(msg)
    dt.print_error(msg)
    log(msg)
end

local function tags_of(img)
    local have = {}
    for _, t in ipairs(tags.get_tags(img)) do have[t.name] = true end
    return have
end

-- One identify.py process at a time: runs share the tmp files and the job file.
-- `orphan` is a cancelled or stalled process that hadn't exited when its run gave up
-- waiting; nothing starts until its done file appears.
local busy, orphan = false, false
local orphan_since = 0 -- os.time() the current orphan was left running
-- Jobs clicked while another runs: { label = "...", run = function() ... end }, started in order as each finishes.
local queue = {}
-- A run that shows no progress for this long is given up on (it may still be loading
-- models or re-embedding references, so this is generous).
local STALL_SECONDS = 300
local verify_button, identify_button, entry_combo, example_combo = nil, nil, nil, nil
local status_label, status_text = nil, "" -- the progress line under Identify selection

-- Shows a progress line in the panel. Never dt.print_hinter: it sets darktable's hinter label from
-- the Lua thread without marshalling to the GUI thread, and frequent calls corrupt the label and
-- crash darktable (5.6.2, pixman access violation). A Lua widget setter runs on the GUI thread.
local function show_status(text)
    if not status_label or text == status_text then return end
    status_text = text
    status_label.label = text
end
local preset_ctl = nil -- the preset controls; each preset is a collection (set by install_panel)
local collection_store -- defined with the panel code below
local collection_loaded = false -- the last collection switch loaded its entries
local identify_cancellable = false -- the identify button currently reads "Cancel"
local replace_manual_check = nil
local read_panel = nil -- set by install_panel: the panel's values as settings

-- A GUI run reads the panel as it starts; headless runs keep the collection's settings.
-- False, with read_panel's "<key>: <why>" on screen, when an entry is invalid (blank entries
-- read as their defaults), so the run doesn't start. Nor does it while settings.json holds a
-- removed setting: the panel's values would hide what identify.py refuses.
local function take_settings()
    local removed = removed_setting()
    if removed then dt.print("Assisted Tagging: " .. removed); return false end
    if not read_panel then return true end
    local s, why = read_panel()
    if not s then dt.print("Assisted Tagging: " .. why); return false end
    settings = s
    -- text entries have no change callback, so their edits show as unsaved from the run on
    if preset_ctl then preset_ctl.check_dirty() end
    return true
end
local entries, entry_order, rules = {}, {}, M.default_rules()
local tag_checks = {} -- TAG_TOGGLES key → its check button (set by install_panel)

-- Writes/When/Off for a tag switch, naming the tag from `named` (M.named_rules of the
-- loaded collection's settings).
local function tag_tooltip(t, named)
    local keys = t.key == "shot" and { "shot_solo", "shot_pack" } or { t.key }
    local names = {}
    for _i, k in ipairs(keys) do
        local name = named.diag[k]
        names[#names + 1] = (k == "number_seen" and name .. "|<digits>") or (k == "derived" and name .. "|From <source>") or name
    end
    local writes = table.concat(names, ", ")
    return string.format(_("Writes: %s\nWhen: %s\nOff: stops writing it and removes it from images on the next run. Identification is unchanged."),
        writes, _(t.when))
end

local function refresh_tag_tooltips()
    local named = M.named_rules(rules, collection_settings(current_collection()))
    for _i, t in ipairs(TAG_TOGGLES) do
        if tag_checks[t.key] then tag_checks[t.key].tooltip = tag_tooltip(t, named) end
    end
end
local lists_loaded = false -- reload_lists has filled the collection and entry lists at least once
-- Starting identify.py imports numpy and cv2, so the first load waits until darktable has opened.
local STARTUP_RELOAD_DELAY_MS = 5000

local function cancelled(job)
    return M.cancel_requested or (job and not job.valid) or file_exists(CANCEL_PATH)
end

local function request_cancel()
    local cf = io.open(CANCEL_PATH, "w")
    if cf then cf:write("1"); cf:close() end
end

-- Ends a job once. Setting valid = false destroys darktable's progress object without
-- checking it still exists (src/lua/gui.c), so a second call would free it twice.
local function end_job(job)
    if job and job.valid then job.valid = false end
end

-- Asks a running identify.py to stop and waits briefly; if it's still running, it's an
-- orphan and blocks the next run until it exits.
local function abandon_process()
    request_cancel()
    for _ = 1, 50 do
        if file_exists(DONE_PATH) then return end
        dt.control.sleep(100)
    end
    orphan, orphan_since = true, os.time()
    log("identify.py hasn't exited yet; the next run waits for it")
end

-- Runs identify.py with the argument list `args` and blocks until it exits,
-- moving job.percent from `from` to `to` with its progress. Returns the exit
-- code, or nil plus "cancelled", "stalled" or "launch" (the last two already
-- reported to the user).
-- Where each stage of an Identify run sits on the job bar, { from, to }. A stage fills its band
-- as it reports cur / tot. Python stage names match identify.py's write_progress calls.
local IDENTIFY_BANDS = {
    ["preparing"] = { 0.00, 0.02 },
    ["neighbours"] = { 0.02, 0.04 },
    ["starting Python"] = { 0.04, 0.05 },
    ["loading models"] = { 0.05, 0.10 },
    ["references"] = { 0.10, 0.13 },
    ["checking cache"] = { 0.13, 0.15 },
    ["starting workers"] = { 0.15, 0.17 },
    ["analysing"] = { 0.17, 0.66 },
    ["rescue"] = { 0.66, 0.70 },
    ["refining"] = { 0.70, 0.76 },
    ["matching"] = { 0.76, 0.80 },
    ["writing tags"] = { 0.80, 0.98 },
    ["saving"] = { 0.98, 1.00 },
}
local shown_stage = nil

-- Moves the job bar to `done` (0–1) through `stage`'s band. A new stage gets a toast and a log line.
local function show_stage(job, stage, done)
    local band = IDENTIFY_BANDS[stage]
    if job and job.valid and band then
        job.percent = band[1] + (band[2] - band[1]) * math.max(0, math.min(1.0, done or 0))
    end
    if stage ~= shown_stage then
        shown_stage = stage
        dt.print("Assisted Tagging: " .. stage .. "…")
        log("stage: " .. stage)
    end
end

-- staged: an Identify run, whose stages each fill their IDENTIFY_BANDS band instead of from..to
local function run_python(args, job, from, to, hint, staged)
    local script = identify_script()
    pcall(os.remove, DONE_PATH)
    pcall(os.remove, PROGRESS_PATH)
    pcall(os.remove, CANCEL_PATH)
    local py = python_bin(script)
    local argv = args_of({ script }, args, { "--progress", PROGRESS_PATH })
    log("running: " .. command_line(py, argv))
    flush_log()
    local launched, why = run_async_python(py, argv, LOG_PATH, true, DONE_PATH)
    if not launched then
        notify_error("Assisted Tagging: couldn't start identify.py: " .. why .. ".")
        return nil, "launch"
    end
    if staged then show_stage(job, "starting Python", 0) end
    local start, last_progress, last_change, stage = os.time(), nil, os.time(), nil
    while true do
        if job and cancelled(job) then
            M.cancel_requested = true
            abandon_process()
            return nil, "cancelled"
        end
        if file_exists(DONE_PATH) then
            local code = tonumber((read_file(DONE_PATH) or ""):match("-?%d+"))
            log("identify.py exit " .. tostring(code))
            return code
        end
        local progress = read_file(PROGRESS_PATH)
        if progress ~= last_progress then
            last_progress, last_change = progress, os.time()
        elseif os.time() - last_change > STALL_SECONDS then
            abandon_process()
            notify_error(string.format("Assisted Tagging: identify.py made no progress for %d minutes, so the run was stopped. Details are in assisted_tagging.log in darktable's config folder.",
                STALL_SECONDS // 60))
            return nil, "stalled"
        end
        local p = M.parse_progress(progress)
        if p and p.stage ~= stage then stage, start = p.stage, os.time() end
        if hint and p and p.tot > 0 then
            if staged and p.stage and IDENTIFY_BANDS[p.stage] then
                show_stage(job, p.stage, p.cur / p.tot)
            elseif job and job.valid then
                job.percent = from + (to - from) * math.min(1.0, p.cur / p.tot)
            end
            show_status(string.format("%s %d / %d%s", p.stage or hint, p.cur, p.tot,
                fmt_eta(os.time() - start, p.cur - p.cached, p.tot - p.cached)))
        end
        dt.control.sleep(150)
    end
end

-- The message for a failed run: identify.py's own last line for bad input (exit 2), else where to look.
local function failure_message(code)
    if code == 2 then
        local found = nil
        for line in read_log_tail():gmatch("[^\r\n]+") do
            if line:sub(1, 18) == "Assisted Tagging: " then found = line end
        end
        if found then return found end
    elseif code == 3 then
        return _("Assisted Tagging: Python is missing a package. Install python/requirements.txt into darktable-assisted-tagging/.venv, or see assisted_tagging.log.")
    elseif code == 9009 or code == 127 then -- cmd.exe / sh: command not found
        return _("Assisted Tagging: Python wasn't found. Create darktable-assisted-tagging/.venv, or put python on PATH.")
    end
    return string.format("Assisted Tagging: identify.py stopped with exit code %s. Details are in assisted_tagging.log in darktable's config folder.",
        tostring(code or "?"))
end

-- The best installed model per job (M.MODEL_LISTS), one log line each. Raises before
-- identify.py starts when a required job has nothing installed.
local function model_args(script)
    local dir = plugin_root(script) .. "/models/"
    local args = { "--detections", (C.detections_path(dt)) } -- parens: gsub's count would ride along as an argument
    for _, item in ipairs(M.MODEL_LISTS) do
        local choice = M.model_choice(item, function(file) return M.model_present(dir .. file, item.job, file_exists) end,
            function(file) return file_exists(dir .. file) end)
        log(choice.line)
        if choice.err then error(choice.err, 0) end
        if choice.file then
            args[#args + 1] = item.flag
            args[#args + 1] = dir .. choice.file
        end
    end
    return args
end

local function collection_args()
    return { "--collections-root", collections_root(), "--collection", current_collection() }
end

-- A GUI run's settings (take_settings) as a temp file for --settings, so the run uses the panel's
-- values without saving them to the collection's settings.json. Headless runs read that file.
local function settings_args()
    if not read_panel then return {} end
    local ok_w, err = C.write_file_atomic(RUN_SETTINGS_PATH, M.preset_encode(M.PRESET_SCHEMA, settings))
    if not ok_w then error("couldn't write " .. RUN_SETTINGS_PATH .. ": " .. tostring(err), 0) end
    return { "--settings", RUN_SETTINGS_PATH }
end

local function read_lines(path)
    local out = {}
    for line in (read_file(path) or ""):gmatch("[^\r\n]+") do out[#out + 1] = line end
    return out
end

local function fill_combo(combo, items, selected)
    if not combo then return end
    for i = #combo, 1, -1 do combo[i] = nil end
    for i, item in ipairs(items) do combo[i] = item end
    if #items > 0 then combo.selected = math.max(1, math.min(selected or 1, #items)) end
end

local function entry_label(e)
    local bits = {}
    if e.number ~= "" then bits[#bits + 1] = "#" .. e.number end
    if e.team ~= "" then bits[#bits + 1] = e.team end
    return #bits > 0 and (e.id .. " (" .. table.concat(bits, ", ") .. ")") or e.id
end

local function refresh_entry_combo()
    local labels = {}
    for i, id in ipairs(entry_order) do labels[i] = entry_label(entries[id]) end
    fill_combo(entry_combo, #labels > 0 and labels or { _("(no entries)") }, 1)
end

local function load_entries_csv()
    entries, entry_order = M.parse_entries_csv(read_file(ENTRIES_PATH))
    rules = M.parse_rules_csv(read_file(RULES_PATH))
    refresh_tag_tooltips()
end

local function cleanup_tmp()
    -- An orphaned identify.py still needs its cancel flag, so leave the files until it exits.
    if orphan then return end
    for _, p in ipairs({ MANIFEST_PATH, RESULTS_PATH, RESULTS_PATH .. ".tmp", NEIGHBOURS_PATH, DONE_PATH, DONE_PATH .. ".job",
        PROGRESS_PATH, CANCEL_PATH, RUN_SETTINGS_PATH }) do
        pcall(os.remove, p)
    end
end

-- False while an orphaned identify.py is still running; clears up after it once it exits.
local function orphan_gone()
    if orphan and file_exists(DONE_PATH) then
        orphan = false
        cleanup_tmp()
    end
    return not orphan
end

-- Refreshes the collection and entry lists from disk via identify.py --list,
-- which also rewrites the collection's tag-plan.txt; show_plan points the user at it.
-- Settings still read from entries.json's old rules are copied into settings.json.
-- reread_settings: show settings.json in the panel again (hand edits; unsaved panel changes go).
-- Returns true once the lists loaded.
local function reload_lists(quiet, show_plan, reread_settings)
    if busy or not orphan_gone() then
        if not quiet then dt.print(_("Assisted Tagging: busy, try again when the current run finishes.")) end
        return false
    end
    -- rereads the collection folders; a selected collection that has gone falls back to template
    if preset_ctl then preset_ctl.refresh() end
    busy = true
    local loaded = false
    local okr, err = pcall(function()
        pcall(os.remove, COLLECTIONS_PATH)
        pcall(os.remove, ENTRIES_PATH)
        pcall(os.remove, RULES_PATH)
        local code, why = run_python(args_of({ "-", "-", "--list" }, collection_args(), {
            "--collections-out", COLLECTIONS_PATH,
            "--entries-out", ENTRIES_PATH, "--rules-out", RULES_PATH,
        }), nil)
        flush_log()
        if code == nil and why ~= "cancelled" then return end -- already reported
        if code ~= 0 then
            notify_error(failure_message(code))
            return
        end
        local names = read_lines(COLLECTIONS_PATH)
        load_entries_csv()
        -- the template has no settings.json, so its panel values stay as they are
        if current_collection() ~= "" then
            local store = collection_store()
            local stored = store.read_raw(current_collection())
            -- backfill first, so a tag_shot_name copied from entries.json also reaches tag_shot_crowded_name
            local backfilled, copied = M.backfill_settings(stored, rules)
            local text, upgraded_keys = M.upgrade_settings_text(backfilled or stored)
            if copied or upgraded_keys then
                if store.write(current_collection(), text) then
                    if copied then log("settings.json: copied " .. table.concat(copied, ", ") .. " from entries.json") end
                    if upgraded_keys then
                        log("settings.json: " .. table.concat(upgraded_keys, ", ") .. " copied from the Shot switch (old settings)")
                    end
                    reread_settings = true
                else
                    log("settings.json: couldn't write " .. store.path(current_collection()))
                end
            end
            if reread_settings and preset_ctl then preset_ctl.reload() end
        end
        lists_loaded, loaded = true, true
        refresh_entry_combo()
        if #names == 0 then
            say(string.format("Assisted Tagging: no collections yet. Create one under new collection (template selected), "
                .. "or a folder with an entries.json in %s (see the README), then click Reload.", collections_root()))
        elseif current_collection() == "" then
            if not quiet then
                say(string.format("Assisted Tagging: %d collections. Pick one in the preset list.", #names))
            end
        elseif show_plan then
            say(string.format("Assisted Tagging: the tags each outcome writes in %s are listed in %s/%s/tag-plan.txt",
                current_collection(), collections_root(), current_collection()))
        elseif not quiet then
            say(string.format("Assisted Tagging: %d collections; %s has %d entries.", #names,
                current_collection(), #entry_order))
        end
    end)
    busy = false
    flush_log()
    if not okr then notify_error(_("Assisted Tagging: couldn't reload collections. ") .. tostring(err)) end
    return loaded
end

-- Subfolders of `root` holding an entries.json: a plain directory listing, not
-- identify.py, so it never contends with a run in progress.
local function list_examples(root)
    local names = {}
    local cmd = IS_WINDOWS
        and string.format('dir /b /ad "%s" 2>nul', root:gsub("/", "\\"))
        or ("ls -1 " .. shell_quote(root) .. " 2>/dev/null")
    local p = io.popen(cmd)
    if not p then return names end
    for line in p:lines() do
        if file_exists(root .. "/" .. line .. "/entries.json") then names[#names + 1] = line end
    end
    p:close()
    table.sort(names)
    return names
end

-- Lists the repo's shipped example collections (see examples_root()) into example_combo.
local function reload_examples()
    local root = examples_root()
    local names = (df.test_file(root, "e") or file_exists(root)) and list_examples(root) or {}
    fill_combo(example_combo, #names > 0 and names or { _("(no examples)") }, 1)
end

local function set_idle_label()
    identify_cancellable = false
    if identify_button then identify_button.label = _("Identify selection") end
end

-- Each tag write queues a TAG_CHANGED event on darktable's GUI thread. A Lua widget update is
-- queued at the same priority and blocks until it runs, so re-setting the button label waits
-- until darktable has processed every write so far. Counters shown after it count finished
-- writes, and no backlog is left to stall the end of the run.
local function wait_for_writes()
    if identify_button then
        identify_button.label = identify_button.label
    else
        dt.control.sleep(WRITE_SLEEP_MS)
    end
end

-- Empties the selection for a batch of tag writes and returns what it was. On every tag write
-- darktable refreshes the thumbnail info and the tagging module's attached list for every
-- selected image (thumbtable.c, libs/tagging.c), so a large selection slows each write.
local function hide_selection()
    local selected = dt.gui.selection()
    if #selected > 0 then
        dt.gui.selection({})
        log(string.format("selection: %d images deselected while tags are written", #selected))
    end
    return selected
end

local function restore_selection(selected)
    if selected and #selected > 0 then dt.gui.selection(selected) end
end

-- The panel's progress line, "<what> cur / tot | ~ETA", as run_python shows for
-- identify.py's stages. `every` thins the updates on long loops: each one is a GUI round trip.
local function show_count(what, cur, tot, start, every)
    if tot <= 0 or (every and cur % every ~= 0 and cur ~= tot) then return end
    show_status(string.format("%s %d / %d%s", what, cur, tot,
        fmt_eta(os.time() - start, cur, tot)))
end

-- Drops every queued job; a cancel means "stop what I started", not "run the rest".
local function clear_queue()
    if #queue == 0 then return end
    dt.print(string.format(_("Assisted Tagging: %d queued jobs dropped."), #queue))
    queue = {}
end

local function stop_job(job)
    M.cancel_requested = true
    request_cancel()
    clear_queue()
    end_job(job)
end

local function start_log(what, n)
    flush_log() -- anything logged since the last run belongs to its log
    pcall(os.remove, PREV_LOG_PATH)
    pcall(os.rename, LOG_PATH, PREV_LOG_PATH)
    log(string.format("%s: darktable %s, %d images, collection %s", what,
        tostring(dt.configuration.version), n, current_collection()))
end

local function write_rows(path, rows)
    local f = io.open(path, "w")
    if not f then return false end
    for _, r in ipairs(rows) do f:write(M.csv_line(r), "\n") end
    f:close()
    return true
end

local write_file_atomic = C.write_file_atomic

local WRITE_ROWS_FAILED = "couldn't write the image list to darktable's tmp folder (disk full or no write access?)"

-- While a job runs, remembers `run` to start when it finishes and returns true. Returns false
-- (do nothing) when nothing is running or there is nothing to queue (`has_input` false), so the
-- caller's normal checks print their own message.
local function queue_if_busy(label, has_input, run)
    if not busy or not has_input then return false end
    queue[#queue + 1] = { label = label, run = run }
    dt.print(string.format(_("Assisted Tagging: %s queued (%d waiting); it starts when the current job finishes."),
        label, #queue))
    return true
end

-- Starts the oldest queued job. Called by every job as it finishes, after busy is cleared.
local function run_next()
    if busy or #queue == 0 then return end
    if not orphan_gone() then
        clear_queue() -- the stopped process still holds the tmp files; nothing safe to start
        return
    end
    local nxt = table.remove(queue, 1)
    log("starting queued job: " .. nxt.label)
    nxt.run()
end

-- A run's preconditions; prints why and returns false when it can't start.
local function can_start(images, needs_no_images)
    if busy then
        dt.print(_("Assisted Tagging: another job is still running. Wait for it to finish, or cancel it first."))
        return false
    end
    if not orphan_gone() then
        if os.time() - orphan_since < 60 then
            dt.print(_("Assisted Tagging: the last run is still stopping. Try again in a moment."))
        else -- the wrapper writes the done file once python exits, so ending it unblocks this
            dt.print(IS_WINDOWS
                and _("Assisted Tagging: the last run's python.exe hasn't stopped. End it in Task Manager (Details tab), then try again.")
                or _("Assisted Tagging: the last run's identify.py hasn't stopped. Run: pkill -f identify.py, then try again."))
        end
        return false
    end
    if not needs_no_images and (not images or #images == 0) then
        dt.print(_("Assisted Tagging: select some images first"))
        return false
    end
    if current_collection() == "" then
        dt.print(string.format("Assisted Tagging: no collection selected. Create one in %s (see the README), then click Reload.",
            collections_root()))
        return false
    end
    return true
end

-- Where a run leaves its per-vehicle records, for "Add from last run".
local function boxes_path()
    return LAST_RUN_DIR .. "/" .. current_collection() .. ".boxes.json"
end

-- Prefix of the run's debug report: identify.py writes <prefix>.md and <prefix>.json.
local function report_prefix()
    return LAST_RUN_DIR .. "/" .. current_collection() .. ".report"
end

local function sorted_names(set)
    local out = {}
    for name in pairs(set) do out[#out + 1] = name end
    table.sort(out)
    return out
end

-- Groups the selection into duplicates (same file, identified once) and groups, and reads the
-- ledger and the tags the user applied by hand. Returns the run's state and the manifest rows.
local function prepare_run(images, replace_manual, job)
    -- Duplicates and RAW+JPEG pairs are identified once, from the JPEG; the tags go on every copy.
    local primaries, group_of = M.collapse_shots(images)

    local time_of, primary_ids = {}, {}
    for _, img in ipairs(primaries) do
        time_of[img.id] = M.exif_time_to_epoch(img.exif_datetime_taken)
        table.insert(primary_ids, img.id)
    end

    local mechanism = settings.group_support
    local key_of, node, multi, n_runs = {}, nil, {}, 0
    if mechanism == "native" then
        local items = {}
        for _, img in ipairs(primaries) do
            items[#items + 1] = { id = img.id, leader = img.group_leader and img.group_leader.id }
        end
        key_of = M.native_group_keys(items)
    elseif mechanism == "tags" then
        local items = {}
        for _, img in ipairs(primaries) do items[#items + 1] = { id = img.id, tags = tags_of(img) } end
        local typed = settings.group_node:match("^%s*(.-)%s*$")
        if typed ~= "" then
            node = typed
            key_of, multi = M.tag_group_keys(items, node)
        else
            key_of, n_runs = M.latest_group_keys(items)
        end
    end
    local burst_of = M.number_groups(primary_ids, key_of)

    local size_of, grouped = {}, 0
    for _, id in ipairs(primary_ids) do size_of[burst_of[id]] = (size_of[burst_of[id]] or 0) + 1 end
    for _, id in ipairs(primary_ids) do
        if size_of[burst_of[id]] >= 2 then grouped = grouped + 1 end
    end
    local msg = string.format("group support %s: %d of %d photos in groups of 2+", mechanism, grouped, #primaries)
    if mechanism == "tags" then
        if node then
            msg = msg .. string.format(", node %s", node)
        else
            msg = msg .. (n_runs > 0 and string.format(", latest run per photo (%d runs)", n_runs) or ", no grouping tags found")
        end
        if node and next(key_of) == nil then msg = msg .. " (matches no selected photo)" end
        if #multi > 0 then msg = msg .. ", several children on ids " .. table.concat(multi, ",") end
    end
    log(msg)
    if mechanism == "native" and grouped == 0 then
        local items = {}
        for _, img in ipairs(primaries) do items[#items + 1] = { id = img.id, tags = tags_of(img) } end
        local hint = M.group_tags_hint(grouped, items)
        if hint then log(hint); dt.print("Assisted Tagging: " .. hint) end
    end

    -- The ledger holds the tags this plugin attached. Entries no longer on the image are
    -- dropped, so a tag removed and re-applied by hand counts as the user's again.
    -- Protection and hints read the entries loaded at the last Reload or run, so Reload after
    -- editing entries.json.
    local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
    local protected_of, hints_of, sent_protected_of, hand_of = {}, {}, {}, {}
    local use_hints = settings.use_hints
    local named = M.named_rules(rules, settings)
    local on_roots = M.family_roots(settings)
    local team_root = on_roots.team
    -- the families whose hand tags name a car (M.hand_entry)
    local naming_roots = { number = on_roots.number, driver = on_roots.driver, co_driver = on_roots.co_driver }
    local n_copies, n_read, start = 0, 0, os.time()
    for _, copies in pairs(group_of) do n_copies = n_copies + #copies end
    local every = math.max(1, n_copies // 200)
    for _, copies in pairs(group_of) do
        for _, copy in ipairs(copies) do
            n_read = n_read + 1
            if n_read % every == 0 then show_stage(job, "preparing", n_read / n_copies) end
            show_count("reading tags, copy", n_read, n_copies, start, every)
            local have = tags_of(copy)
            local kept = {}
            for name in pairs(ledger[copy.id] or {}) do
                if have[name] then kept[name] = true end
            end
            ledger[copy.id] = next(kept) and kept or nil
            protected_of[copy.id] = replace_manual and {} or M.protected_tags(have, kept, entries)
            hints_of[copy.id] = replace_manual and {} or M.hint_tags(have, kept, entries, team_root)
            -- the identifier sees protected tags for skip and conflict checks; with hints off a team tag
            -- is not among them, but protected_of still keeps the run from detaching it
            local sent = {}
            for name in pairs(protected_of[copy.id]) do
                if use_hints or not hints_of[copy.id][name] then sent[name] = true end
            end
            -- a hand number, driver or co-driver tag is sent too, listed or not: a different reading is a conflict
            hand_of[copy.id] = replace_manual and {} or M.hand_family_tags(have, kept, naming_roots)
            for name in pairs(hand_of[copy.id]) do sent[name] = true end
            sent_protected_of[copy.id] = sent
            if not use_hints then hints_of[copy.id] = {} end
            -- other hand family tags (colour, an unlisted team) only stop a detach; sent to the
            -- identifier they'd read as entry tags
            for name in pairs(replace_manual and {} or M.hand_family_tags(have, kept, named.families)) do
                protected_of[copy.id][name] = true
            end
            -- likewise hand-applied diagnostic, unidentified and number-seen tags
            for name in pairs(replace_manual and {} or M.hand_diag_tags(have, kept, named)) do
                protected_of[copy.id][name] = true
            end
        end
    end

    local rows, hand_from_of = {}, {}
    for _, img in ipairs(primaries) do
        -- a hand tag on any copy (e.g. only the RAW) counts for the shot
        local sent, hints, hand = {}, {}, {}
        for _, copy in ipairs(group_of[img.id]) do
            for name in pairs(sent_protected_of[copy.id]) do sent[name] = true end
            for name in pairs(hints_of[copy.id]) do hints[name] = true end
            for name in pairs(hand_of[copy.id]) do hand[name] = true end
        end
        local hand_id, why = M.hand_entry(hand, nil, entries, naming_roots)
        if hand_id then hand_from_of[img.id] = M.hand_source(hand, nil, entries, naming_roots) end
        if why then
            log(string.format("%s: the tags you applied (%s) %s; no car is taken from them", img.filename,
                table.concat(sorted_names(hand), "; "),
                why == "ambiguous" and "fit more than one entry" or "name different entries"))
        end
        rows[#rows + 1] = { img.id, img.path .. "/" .. img.filename, burst_of[img.id],
                            table.concat(sorted_names(sent), ";"),
                            table.concat(sorted_names(hints), ";"),
                            time_of[img.id] and tostring(time_of[img.id]) or "",
                            hand_id or "" }
    end
    return { primaries = primaries, group_of = group_of, protected_of = protected_of, ledger = ledger,
             hand_from_of = hand_from_of, applying = false }, rows
end

-- Whether image `id` is still in the library. A get_image error counts as gone, as does a
-- stale image whose fields can't be read; ledger_prune skips the prune when nothing resolves.
local function image_exists(id)
    local ok, name = pcall(function()
        local img = dt.database.get_image(id)
        return img and img.filename
    end)
    return ok and name ~= nil
end

-- Writes the ledger of the tags this plugin attached, first dropping the rows of images no
-- longer in the library. A failed write is tried once more, then reported on screen with
-- `consequence` (default: what a failed save after a tagging run means).
-- `keep_gone`: skip the prune. It looks up every image the ledger has ever held, one darktable
-- call each, which took 9 minutes after a 1830-image run.
local function write_ledger(ledger, consequence, keep_gone)
    if not keep_gone then
        local prune_start = os.time()
        local pruned, skipped = M.ledger_prune(ledger, image_exists)
        if pruned > 0 then log(string.format("ledger: dropped %d images no longer in the library", pruned)) end
        if skipped then log("ledger: prune skipped, no image id resolved") end
        log(string.format("ledger: prune took %ds", os.time() - prune_start))
    end
    local text = M.ledger_format(ledger, LIB_KEY)
    local ok_w, err = write_file_atomic(LEDGER_PATH, text)
    if not ok_w then
        dt.control.sleep(200)
        ok_w, err = write_file_atomic(LEDGER_PATH, text)
    end
    if not ok_w then
        log("ledger: couldn't save " .. LEDGER_PATH .. " after two tries: " .. tostring(err))
        notify_error(_("Assisted Tagging: couldn't save the tag ledger ") .. LEDGER_PATH .. " (" .. tostring(err)
            .. "). " .. (consequence or _("Tags this run attached will count as yours next run.")))
    end
end

-- Detaches every tag the ledger says this plugin attached to the selected images, from any
-- collection's roots, then drops their ledger rows. Hand-applied tags and run stamps stay.
-- A tag that fails to detach keeps its place in the row, so clearing again retries it.
function M.clear_marks(images)
    if queue_if_busy(_("Clear tagging marks"), images and #images > 0, function() M.clear_marks(images) end) then return end
    if not can_start(images) then return end
    busy = true
    M.cancel_requested = false
    start_log("clear", #images)
    local job, selected

    local okr, err = pcall(function()
        local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
        local records, img_of = {}, {}
        for _, img in ipairs(images) do
            local id = tonumber(img.id)
            if ledger[id] and not img_of[id] then
                records[#records + 1] = { id = id, tags = tags_of(img) }
                img_of[id] = img
            end
        end
        if #records == 0 then
            say(_("Assisted Tagging: nothing to clear; the selection has no tagging marks."))
            return
        end
        local n_tags, n_images, writes = 0, 0, 0
        local plans, stopped = M.plan_clear(records, ledger), false
        local n_writes, done, start = 0, 0, os.time()
        for _, plan in ipairs(plans) do n_writes = n_writes + #plan.detach end
        job = dt.gui.create_job(_("Assisted Tagging: clear tagging marks"), true, stop_job)
        selected = hide_selection()
        for _, plan in ipairs(plans) do
            if M.cancel_requested or not job.valid then
                stopped = true
                break
            end
            -- the row is rebuilt from the failures, so ledger tags no longer on the image go too
            local left = {}
            for _, name in ipairs(plan.detach) do
                local tag = tags.find(name)
                local okd = tag and pcall(tags.detach, tag, img_of[plan.id])
                if okd then
                    n_tags = n_tags + 1
                else
                    left[name] = true
                end
                writes, done = writes + 1, done + 1
                if writes >= WRITE_BUDGET then
                    writes = 0
                    wait_for_writes()
                    job.percent = done / n_writes
                    show_count("removing tags", done, n_writes, start)
                end
            end
            if next(left) then
                ledger[plan.id] = left
                log(string.format("clear: image %d keeps ledger tags that did not detach", plan.id))
            else
                ledger[plan.id] = nil
                n_images = n_images + 1
            end
        end
        wait_for_writes()
        show_status("")
        log(string.format("clear: darktable finished %d tag writes, %ds", done, os.time() - start))
        write_ledger(ledger, _("The cleared images keep their old ledger rows, so tags you add to them by hand "
            .. "can be removed by the next run or clear."))
        if stopped then
            say(string.format(_("Assisted Tagging: stopped; cleared %d tags from %d images. "
                .. "The rest keep their marks, clear again to finish."), n_tags, n_images))
        else
            say(string.format(_("Assisted Tagging: cleared %d tags from %d images."), n_tags, n_images))
        end
    end)
    restore_selection(selected)
    end_job(job)
    busy = false
    if not okr then notify_error(_("Assisted Tagging: couldn't clear tagging marks. ") .. tostring(err)) end
    log("clear finished")
    flush_log()
    run_next()
end

-- Derive from number (`mode` "number") or colour ("colour"): adds the entry tags M.derive_plan
-- looks up for each selected image, plus its "Derived from" marker, and records them in the
-- ledger. Lookups only: no model runs, and no tag is ever detached.
function M.derive_images(images, mode)
    local label = mode == "number" and _("Derive from number") or _("Derive from colour")
    if queue_if_busy(label, images and #images > 0, function() M.derive_images(images, mode) end) then return end
    if not can_start(images) or not take_settings() then return end
    busy = true
    M.cancel_requested = false
    start_log("derive " .. mode, #images)
    local job

    local okr, err = pcall(function()
        load_entries_csv()
        if not next(entries) then
            say(_("Assisted Tagging: no entries loaded; pick the collection (or Reload) first."))
            return
        end
        local s = settings
        local named = M.named_rules(rules, s)
        local roots = M.family_roots(s)
        local names = { derived = s.tag_derived and named.diag.derived or "",
                        check_colour = s.tag_check_colour and named.diag.check_colour or "" }
        local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
        local n_derived, n_skipped, n_check, n_tags, writes, failed, stopped = 0, 0, 0, 0, 0, 0, false
        local start = os.time()
        job = dt.gui.create_job(_("Assisted Tagging: ") .. label, true, stop_job)
        for i, img in ipairs(images) do
            if M.cancel_requested or not job.valid then
                stopped = true
                break
            end
            job.percent = (i - 1) / #images
            -- the tag count is only known once each image is looked up, so this counts images
            show_count(string.format("deriving (%d tags written), image", n_tags), i, #images, start)
            local have = tags_of(img)
            local plan = M.derive_plan(have, ledger[tonumber(img.id)], entries, entry_order, roots, mode, names)
            if plan.reason ~= "" then
                n_skipped = n_skipped + 1
                log(string.format("derive %s: %s skipped, %s", mode, img.filename, plan.reason))
            else
                n_derived = n_derived + 1
                log(string.format("derive %s: %s -> %s", mode, img.filename, plan.entry_id))
            end
            if names.check_colour ~= "" and not have[names.check_colour] then
                for _, name in ipairs(plan.attach) do
                    if name == names.check_colour then n_check = n_check + 1 end
                end
            end
            local mine = ledger[tonumber(img.id)] or {}
            local okw, werr = pcall(function()
                for _, name in ipairs(plan.attach) do
                    tags.attach(tags.create(name), img)
                    mine[name] = true
                    n_tags = n_tags + 1
                end
            end)
            ledger[tonumber(img.id)] = next(mine) and mine or nil
            if not okw then
                failed = failed + 1
                log(string.format("derive %s: %s couldn't be tagged: %s", mode, img.filename, tostring(werr)))
            end
            writes = writes + #plan.attach
            if writes >= WRITE_BUDGET then
                writes = 0
                wait_for_writes()
            end
        end
        wait_for_writes()
        show_status("")
        log(string.format("derive %s: darktable finished %d tag writes, %ds", mode, n_tags, os.time() - start))
        write_ledger(ledger)
        local msg = string.format(_("Assisted Tagging: %s%s: %d images derived, %d skipped (reasons in the log)"),
            stopped and _("stopped; ") or "", label, n_derived, n_skipped)
        if n_check > 0 then msg = msg .. string.format(_(", %d check colour"), n_check) end
        if failed > 0 then msg = msg .. string.format(_(", %d couldn't be updated (see log)"), failed) end
        say(msg .. ".")
    end)
    end_job(job)
    busy = false
    if not okr then notify_error(_("Assisted Tagging: couldn't derive tags. ") .. tostring(err)) end
    log("derive finished")
    flush_log()
    run_next()
end

-- Syncs each image's tags to identify.py's results and reports the outcome. Sets run.applying
-- before the first tag write and updates run.ledger as tags change, so the caller can save the
-- ledger even when this stops or errors partway.
local function apply_results(run, job)
    local primaries, group_of, protected_of, ledger = run.primaries, run.group_of, run.protected_of, run.ledger
    load_entries_csv()
    refresh_entry_combo()
    -- an image identify.py couldn't analyse has no rows, so its tags are left alone
    local rows_of, _errors, skipped = M.read_results(read_file(RESULTS_PATH))
    if run.verify_only then
        local n_checked, n_differ = 0, 0
        for _, results in pairs(rows_of) do
            n_checked = n_checked + 1
            for _, r in ipairs(results) do
                if r.method == "conflict" then n_differ = n_differ + 1; break end
            end
        end
        say(string.format("Assisted Tagging: verify only, no tags changed. %d images checked, %d differ from their tags (see the report's conflict section).", n_checked, n_differ))
        return
    end

    local named = M.named_rules(rules, settings)
    local owned = M.owned_tags(entries, named)
    local owned_roots = M.owned_roots(entries, named)
    local owned_prefixes = M.owned_prefixes(named)
    -- owned (above) names every diagnostic, so switched-off ones are still detached
    local diag_off = {}
    for _, t in ipairs(TAG_TOGGLES) do
        if not settings["tag_" .. t.key] then diag_off[t.key] = true end
    end
    local write_rules = M.mask_diag(named, diag_off)
    -- likewise named.families holds every root; only the families that are on get written
    write_rules.families = M.family_roots(settings)
    -- one stamp per run; never owned, so later runs leave earlier stamps in place. "changed"
    -- stamps only copies this run adds or removes tags on; "all" stamps every copy it processes
    local stamp_all = settings.run_tag == "all"
    local run_tag = settings.run_tag ~= "none"
        and os.date("Assisted Tagging|Run|%Y-%m-%d %H:%M") or nil
    local tag_objs, writes, failed, first_error = {}, 0, 0, nil
    local n_tagged, n_unidentified, n_missing = 0, 0, 0
    local n_skipped, n_conflict = 0, 0
    local by_method = { number = 0, livery = 0, burst = 0, team = 0, pooled = 0, face = 0, neighbour = 0, hand = 0 }
    local function tag_named(name)
        tag_objs[name] = tag_objs[name] or tags.create(name)
        return tag_objs[name]
    end

    run.applying = true
    -- identify.py has exited, so the log can be flushed as the writes go: a crash mid-apply
    -- then leaves the last image reached in the log
    local n_copies = 0
    for _, img in ipairs(primaries) do n_copies = n_copies + #group_of[img.id] end
    -- every copy's changes are worked out before the first write, so the counter has a known total
    local plans_of, n_writes = {}, 0
    for i, img in ipairs(primaries) do
        local plans = {}
        plans_of[i] = plans
        local results = rows_of[tonumber(img.id)]
        if skipped[tonumber(img.id)] then
            n_skipped = n_skipped + 1
        elseif not results then
            n_missing = n_missing + 1
        else
            local wanted, diag, identified = M.wanted_tags(results, entries, write_rules, run.hand_from_of[img.id])
            if identified then n_tagged = n_tagged + 1 else n_unidentified = n_unidentified + 1 end
            for _, r in ipairs(results) do
                if by_method[r.method] and entries[r.entry_id] then by_method[r.method] = by_method[r.method] + 1 end
                if r.method == "conflict" then n_conflict = n_conflict + 1 end
            end
            for name in pairs(diag) do wanted[name] = true end
            if run_tag and stamp_all then wanted[run_tag] = true end
            for _, copy in ipairs(group_of[img.id]) do
                local attach, detach = M.tag_changes(tags_of(copy), wanted, owned, owned_prefixes,
                    protected_of[copy.id], M.ledgered_owned(ledger[copy.id], owned_roots))
                if run_tag and not stamp_all and (#attach > 0 or #detach > 0) then
                    attach[#attach + 1] = run_tag
                end
                plans[#plans + 1] = { copy = copy, attach = attach, detach = detach }
                n_writes = n_writes + #attach + #detach
            end
        end
    end

    log(string.format("apply: writing %d tags to %d images (%d copies)", n_writes, #primaries, n_copies))
    flush_log()
    local apply_start, total_writes = os.time(), 0
    -- restored by the caller, so a stop or error partway still gets it back
    run.selected = hide_selection()
    show_stage(job, "writing tags", 0)
    for i, img in ipairs(primaries) do
        -- wait_for_writes runs every WRITE_BUDGET writes, so this count trails darktable by at most that
        log(string.format("apply: %d / %d images, image id %s, %s, %d / %d writes done by darktable, %ds", i,
            #primaries, tostring(img.id), tostring(img.filename), total_writes, n_writes, os.time() - apply_start))
        flush_log()
        for _, plan in ipairs(plans_of[i]) do
            local copy, attach, detach = plan.copy, plan.attach, plan.detach
            -- what the plugin owns on this copy: its earlier tags minus the detached, plus the
            -- attached; recorded per tag so a failure partway still keeps the ledger true
            local mine = ledger[copy.id] or {}
            local okw, werr = pcall(function()
                for _, name in ipairs(detach) do
                    tags.detach(tag_named(name), copy)
                    mine[name] = nil
                end
                for _, name in ipairs(attach) do
                    tags.attach(tag_named(name), copy)
                    mine[name] = true
                end
            end)
            ledger[copy.id] = next(mine) and mine or nil
            if not okw then
                failed = failed + 1
                first_error = first_error or tostring(werr)
            end
            writes = writes + #attach + #detach
            total_writes = total_writes + #attach + #detach
            if writes >= WRITE_BUDGET then
                writes = 0
                wait_for_writes()
                show_stage(job, "writing tags", total_writes / n_writes)
                show_count("writing tags", total_writes, n_writes, apply_start)
            end
        end
        if cancelled(job) then
            wait_for_writes()
            show_status("")
            say(string.format("Assisted Tagging: stopped while writing tags; %d of %d images were updated. Run again to finish.",
                i, #primaries))
            return
        end
    end
    wait_for_writes()
    show_stage(job, "writing tags", 1)
    show_status("")
    log(string.format("apply: darktable finished %d tag writes, %ds", total_writes, os.time() - apply_start))

    local parts = {}
    for _, m in ipairs({ { "number", "by number" }, { "livery", "by livery" }, { "burst", "by burst" }, { "neighbour", "by neighbour" },
                         { "team", "team only" }, { "pooled", "by pooled burst" }, { "face", "by face" },
                         { "hand", "by your tag" } }) do
        if by_method[m[1]] > 0 then parts[#parts + 1] = string.format("%d %s", by_method[m[1]], m[2]) end
    end
    local msg = string.format("Assisted Tagging: done. %d of %d images tagged", n_tagged, #primaries)
    if #parts > 0 then msg = msg .. " (vehicles: " .. table.concat(parts, ", ") .. ")" end
    if n_unidentified > 0 then msg = msg .. string.format(", %d unidentified", n_unidentified) end
    if n_skipped > 0 then msg = msg .. string.format(", %d already tagged (skipped)", n_skipped) end
    if n_conflict > 0 then msg = msg .. string.format(", %d vehicles left as you tagged them", n_conflict) end
    if n_missing > 0 then msg = msg .. string.format(", %d unreadable (see log)", n_missing) end
    if failed > 0 then msg = msg .. string.format(", %d couldn't be updated (see log)", failed) end
    say(msg)
    if first_error then log("first tag write error: " .. first_error) end
end

-- replace_manual: lift the protection of tags the user applied by hand.
-- verify_only: analyse fully tagged images too and report disagreements, changing no tags.
-- Unselected photos in the selection's film rolls, shot near it and already tagged with an entry:
-- rows { id, epoch, entry id } that neighbour aid reads for support only. They are never tagged.
local function library_neighbour_rows(images, job)
    local selected, films, times = {}, {}, {}
    for _, img in ipairs(images) do
        selected[img.id] = true
        times[#times + 1] = M.exif_time_to_epoch(img.exif_datetime_taken) or 0
        local okf, film = pcall(function() return img.film end)
        if okf and film then films[film.id] = film end
    end
    local pool, film_list, start = {}, {}, os.time()
    for _, film in pairs(films) do film_list[#film_list + 1] = film end
    -- the bar's first half is reading the film rolls, the second the nearby photos' tags
    for f, film in ipairs(film_list) do
        show_stage(job, "neighbours", 0.5 * (f - 1) / #film_list)
        show_count("reading film roll", f, #film_list, start)
        local okr = pcall(function()
            for i = 1, #film do
                local img = film[i]
                if not selected[img.id] then
                    pool[#pool + 1] = { img = img, time = M.exif_time_to_epoch(img.exif_datetime_taken) }
                end
            end
        end)
        if not okr then log("couldn't read film roll " .. tostring(film.path) .. "; its photos lend no neighbour support") end
    end
    local rows = {}
    local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
    local on_roots = M.family_roots(settings)
    local naming_roots = { number = on_roots.number, driver = on_roots.driver, co_driver = on_roots.co_driver }
    local near = M.near_in_time(times, pool, M.NEIGHBOUR_MAX_GAP_S)
    local every = math.max(1, #near // 200)
    start = os.time()
    for i, c in ipairs(near) do
        if i % every == 0 then show_stage(job, "neighbours", 0.5 + 0.5 * i / #near) end
        show_count("reading nearby photo", i, #near, start, every)
        local have = tags_of(c.img)
        -- a photo carrying all of an entry's tags, or one the user's hand tag names
        local eid = M.entry_for_tags(have, entries, entry_order)
            or (M.hand_entry(have, ledger[c.img.id], entries, naming_roots))
        if eid then rows[#rows + 1] = { c.img.id, c.time, eid } end
    end
    return rows
end

function M.identify_images(images, replace_manual, verify_only)
    local label = verify_only and _("Verify") or _("Identify")
    if queue_if_busy(label, images and #images > 0, function() M.identify_images(images, replace_manual, verify_only) end) then
        return
    end
    if not can_start(images) then return end
    if not take_settings() then return end
    busy = true
    M.cancel_requested = false
    identify_cancellable = true
    if identify_button then identify_button.label = _("Cancel") end
    start_log(verify_only and "verify started" or "identify started", #images)
    log(string.format("settings: replace manual %s, cars per photo %s, team hints %s, tag each run %s, grouping support %s, node %s, neighbour tolerance %s, order weight %s",
        tostring(replace_manual and true or false),
        tostring(settings.cars_per_photo),
        tostring(settings.use_hints),
        tostring(settings.run_tag),
        settings.group_support,
        settings.group_node ~= "" and settings.group_node or "(blank)",
        tostring(settings.neighbour_tolerance),
        tostring(settings.order_weight)))

    local job, run = nil, nil
    local okr, err = pcall(function()
        -- the job and log go up before the reads below, which touch every selected photo and
        -- film roll and can take minutes on thousands of photos
        job = dt.gui.create_job(_("Assisted Tagging"), true, stop_job)
        job.percent = 0.0
        shown_stage = nil
        show_stage(job, "preparing", 0)
        local stage_start = os.time()
        log("prepare: reading tags of the selection")
        flush_log()
        local rows
        run, rows = prepare_run(images, replace_manual, job)
        show_stage(job, "preparing", 1)
        log(string.format("prepare: done, %d rows, %ds", #rows, os.time() - stage_start))
        flush_log()
        run.verify_only = verify_only
        pcall(os.remove, RESULTS_PATH)
        pcall(os.remove, ENTRIES_PATH)
        pcall(os.remove, RULES_PATH)
        if not write_rows(MANIFEST_PATH, rows) then
            error(WRITE_ROWS_FAILED, 0)
        end
        local neighbour_args = {}
        if not verify_only and settings.order_weight > 0 then
            stage_start = os.time()
            show_stage(job, "neighbours", 0)
            log("neighbour: reading the film rolls of the selection")
            flush_log()
            local lib_rows = library_neighbour_rows(images, job)
            show_stage(job, "neighbours", 1)
            log(string.format("neighbour: %d unselected tagged photos shot near the selection, %ds",
                #lib_rows, os.time() - stage_start))
            flush_log()
            if #lib_rows > 0 then
                if not write_rows(NEIGHBOURS_PATH, lib_rows) then error(WRITE_ROWS_FAILED, 0) end
                neighbour_args = { "--neighbours", NEIGHBOURS_PATH }
            end
        end

        local script = identify_script()
        local code, why = run_python(args_of({ MANIFEST_PATH, RESULTS_PATH },
            collection_args(), settings_args(), model_args(script), verify_only and { "--verify" } or {}, neighbour_args, {
                "--cache", CACHE_PATH,
                "--entries-out", ENTRIES_PATH, "--rules-out", RULES_PATH,
                "--boxes-out", boxes_path(),
                "--report-out", report_prefix(),
                "--archive-dir", RUNS_DIR,
            }),
            job, 0, 0.8, "identifying", true)
        flush_log()
        show_status("")

        -- Burst consensus needs whole bursts, so a cancelled run applies nothing.
        if why == "cancelled" or code == 130 then
            say(_("Assisted Tagging: cancelled, no tags were changed."))
            return
        end
        if code == nil then return end -- stalled or couldn't launch; already reported
        if code ~= 0 or not file_exists(RESULTS_PATH) then
            notify_error(failure_message(code))
            return
        end
        apply_results(run, job)
    end)

    -- Saved once tags may have changed, even if the apply stopped or errored partway, so the tags
    -- this run attached aren't mistaken for the user's next time. Earlier stages leave it as it was.
    restore_selection(run and run.selected)
    if run and run.applying then
        show_stage(job, "saving", 0)
        log("apply: saving the ledger")
        flush_log()
        local save_start = os.time()
        write_ledger(run.ledger, nil, true)
        log(string.format("apply: ledger saved, %ds", os.time() - save_start))
    end
    -- 2026-11-17 debug: 4 minutes passed between "ledger saved" and "run finished"; each line
    -- below is flushed so the log shows which step holds it.
    local finish_start = os.time()
    log("finish: ending the job")
    flush_log()
    end_job(job)
    log(string.format("finish: job ended, %ds; resetting the button", os.time() - finish_start))
    flush_log()
    busy = false
    set_idle_label()
    log(string.format("finish: button reset, %ds; removing temp files", os.time() - finish_start))
    flush_log()
    if not okr then notify_error(_("Assisted Tagging: couldn't run. ") .. tostring(err)) end
    cleanup_tmp()
    log(string.format("finish: temp files removed, %ds", os.time() - finish_start))
    log("run finished")
    flush_log()
    run_next()
end

-- Writes the manifest and runs identify.py in a reference mode (`mode_args`). Sets state.job for
-- finish_reference_job. Returns results.csv's text, or nil once a cancel, stall or failure has been reported.
-- what: the job-area title and progress hint, e.g. "auditing references".
local function run_reference_job(state, rows, mode_args, what)
    pcall(os.remove, RESULTS_PATH)
    if not write_rows(MANIFEST_PATH, rows) then
        error(WRITE_ROWS_FAILED, 0)
    end
    state.job = dt.gui.create_job("Assisted Tagging: " .. what, true, stop_job)
    state.job.percent = 0.0
    local code, why = run_python(args_of({ MANIFEST_PATH, RESULTS_PATH },
        mode_args, collection_args(), settings_args(), model_args(identify_script()),
        { "--entries-out", ENTRIES_PATH, "--rules-out", RULES_PATH }),
        state.job, 0, 1, what)
    flush_log()
    show_status("")
    if why == "cancelled" or code == 130 then
        say(_("Assisted Tagging: cancelled. References already saved stay in the collection."))
        return nil
    end
    if code == nil then return nil end -- stalled or couldn't launch; already reported
    if code ~= 0 or not file_exists(RESULTS_PATH) then
        notify_error(failure_message(code))
        return nil
    end
    return read_file(RESULTS_PATH) or ""
end

-- failure: the sentence a crash is reported with, e.g. "couldn't audit references."
local function finish_reference_job(state, okr, err, failure)
    end_job(state.job)
    busy = false
    if not okr then notify_error("Assisted Tagging: " .. failure .. " " .. tostring(err)) end
    cleanup_tmp()
    log("run finished")
    flush_log()
    run_next()
end

-- Swaps each selected RAW for its paired JPEG when darktable has the JPEG (same film roll,
-- same stem), so references come from the camera's exposure and colour and match the image
-- Identify read. Each film is read once, and only for selections that hold a RAW.
local function with_paired_jpegs(images)
    local pool, films_done = {}, {}
    for _, img in ipairs(images) do
        if lead_rank(img.filename) < 2 then
            local okf, film = pcall(function() return img.film end)
            if okf and film and not films_done[film.id] then
                films_done[film.id] = true
                local okr = pcall(function()
                    for i = 1, #film do pool[#pool + 1] = film[i] end
                end)
                if not okr then log("couldn't read film roll " .. tostring(film.path) .. "; RAWs there are used as they are") end
            end
        end
    end
    local out, swapped, pick_of = M.prefer_paired(images, pool)
    if swapped > 0 then log(string.format("%d RAW selections read from their paired JPEG", swapped)) end
    return out, pick_of
end

-- entry_id: the entry every image becomes a reference of, or nil to take each
-- image's entry from the tags it already carries.
function M.add_references(images, entry_id)
    if queue_if_busy(_("Add references"), images and #images > 0, function() M.add_references(images, entry_id) end) then return end
    if not can_start(images) then return end
    if entry_id == nil and #entry_order == 0 then
        dt.print(_("Assisted Tagging: the collection has no entries yet. Add them to its entries.json, then click Reload."))
        return
    end
    if not take_settings() then return end
    busy = true
    M.cancel_requested = false
    start_log(entry_id and ("add references to " .. entry_id) or "add tagged images as references", #images)

    local state = {}
    local okr, err = pcall(function()
        local rows, n_skipped, sent = {}, 0, {}
        local pick_of = select(2, with_paired_jpegs(images))
        local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
        local colour_base = M.family_roots(settings).colour
        for _, img in ipairs(images) do
            -- the entry comes from the selected image's tags; the crop from its paired JPEG
            local src = pick_of[img.id]
            local eid = entry_id or M.entry_for_tags(tags_of(img), entries, entry_order, ledger[img.id])
            if not eid then
                -- tagged only to team level: identify.py saves it as a team reference when
                -- rules.partial_references is on and the shot is solo
                local prefixes = sorted_names(M.hint_tags(tags_of(img), ledger[img.id], entries, M.family_roots(settings).team))
                if #prefixes == 1 then eid = prefixes[1] end
            end
            if eid then
                if not sent[src.id] then
                    sent[src.id] = true
                    rows[#rows + 1] = { src.id, src.path .. "/" .. src.filename, eid,
                        M.hand_value(tags_of(img), ledger[img.id], colour_base) or "" }
                end
            else
                n_skipped = n_skipped + 1
                log(string.format("%s: skipped, its tags match no single entry", img.filename))
            end
        end
        if #rows == 0 then
            say(_("Assisted Tagging: no selected image carries all of one entry's tags, so nothing was added."))
            return
        end
        -- a chosen car makes picked refs (anchors, like hand ones; refs/sources.json records which)
        local results = run_reference_job(state, rows, entry_id and { "--add-reference", "--picked" } or { "--add-reference" },
            "adding references")
        if not results then return end
        local added, no_car, failed, no_face, multi, team_rule = 0, 0, 0, 0, 0, 0
        local parsed, notes = M.parse_reference_results(results)
        for _, p in ipairs(parsed) do
            if p[2] == "added" then added = added + 1
            elseif p[2] == "team_refs_off" or p[2] == "team_not_solo" then team_rule = team_rule + 1
            elseif p[2] == "no_face" then no_face = no_face + 1
            elseif p[2] == "multiple_faces" then multi = multi + 1
            elseif p[2] == "no_vehicle" then no_car = no_car + 1
            else failed = failed + 1 end
        end
        local extra = M.colour_note_extras(notes)
        if no_car > 0 then extra[#extra + 1] = string.format("%d had no vehicle found, not saved", no_car) end
        if no_face > 0 then extra[#extra + 1] = string.format("%d had no face", no_face) end
        if multi > 0 then extra[#extra + 1] = string.format("%d had several faces, so can't name one person", multi) end
        if team_rule > 0 then extra[#extra + 1] = string.format("%d tagged only to team level, not saved (the team-reference rule is off or the shot isn't solo)", team_rule) end
        if n_skipped > 0 then extra[#extra + 1] = string.format("%d skipped", n_skipped) end
        if failed > 0 then extra[#extra + 1] = string.format("%d failed, see log", failed) end
        say(string.format("Assisted Tagging: added %d references to %s%s. Each sample's crop is in %s/refs.%s",
            added, entry_id or "their entries", #extra > 0 and (" (" .. table.concat(extra, ", ") .. ")") or "",
            current_collection(), notes.set > 0 and (" Colours: " .. entries_json_path()) or ""))
    end)
    finish_reference_job(state, okr, err, "couldn't add references.")
end

-- Reads the paintwork colour of each selected image's car and writes it as that entry's colour
-- in entries.json, saving no references. Mirrors M.add_references(images, nil): the entry comes
-- from the image's tags, a hand-applied colour tag wins over the reading.
-- After Find new entries adds numbers: each image that read one (`read`), and its unselected
-- copies still carrying <seen_base>|<n> (M.shot_copies), gets the number tag <number root>|<n>
-- in place of <seen_base>|<n>, both recorded as the plugin's in the ledger. Hand-tagged images
-- keep their tags. `image_of`: image id → image. Returns the images retagged.
local function retag_added_numbers(rows, image_of, number_root, seen_base)
    local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
    local n_images, failed = 0, nil
    for _, r in ipairs(rows) do
        if r.kind == "number" then
            local new_name, old_name = number_root .. "|" .. r.number, seen_base .. "|" .. r.number
            local new_tag = tags.create(new_name)
            local read, carriers = {}, {}
            for _, id in ipairs(r.read) do read[#read + 1] = image_of[id] end
            local old_tag = tags.find(old_name)
            for i = 1, old_tag and #old_tag or 0 do carriers[#carriers + 1] = old_tag[i] end
            local targets = { table.unpack(read) }
            for _, img in ipairs(M.shot_copies(read, carriers)) do targets[#targets + 1] = img end
            for _, img in ipairs(targets) do
                local mine = ledger[img.id] or {}
                local ok, err = pcall(function()
                    local have = tags_of(img)
                    -- a copy may carry the number tag by hand; it stays the user's
                    if not have[new_name] or mine[new_name] then
                        tags.attach(new_tag, img)
                        mine[new_name] = true
                    end
                    if have[old_name] then
                        tags.detach(tags.create(old_name), img)
                        mine[old_name] = nil
                    end
                end)
                ledger[img.id] = next(mine) and mine or nil
                if ok then n_images = n_images + 1 else failed = failed or tostring(err) end
            end
        end
    end
    write_ledger(ledger, _("The number tags just attached will count as yours next run."))
    if failed then notify_error(_("Assisted Tagging: some number tags couldn't be attached: ") .. failed) end
    return n_images
end

-- Find new entries: the rows for the selected images (see M.new_entry_candidates), with the
-- images by id. nil when the run can't start (the reason is already on screen).
function M.find_new_entries(images)
    if not can_start(images) or not take_settings() then return nil end
    local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
    local list, image_of = {}, {}
    for _, img in ipairs(images) do
        image_of[img.id] = img
        list[#list + 1] = { id = img.id, have = tags_of(img), ledger_set = ledger[img.id] or {} }
    end
    local roots = M.family_roots(settings)
    return M.new_entry_candidates(list, entries, roots, M.named_rules(rules, settings).diag.number_seen), image_of
end

-- Adds the ticked Find new entries rows to entries.json (entries_file.py, which keeps a .bak),
-- reloads the lists, then retags the images that read an added number. Returns true when
-- entries.json was written; on false the message is already on screen.
function M.add_found_entries(ticked, image_of)
    if busy or not orphan_gone() then
        dt.print(_("Assisted Tagging: busy, try again when the current run finishes."))
        return false
    end
    if not take_settings() then return false end
    local roots = M.family_roots(settings)
    local problem = M.check_additions(ticked, roots)
    if problem then
        dt.print("Assisted Tagging: " .. _(problem))
        return false
    end
    local path = TMP_DIR .. "/assisted_tagging_additions.csv"
    local lines = {}
    for _, row in ipairs(M.addition_rows(ticked)) do lines[#lines + 1] = M.csv_line(row) end
    if not write_file_atomic(path, table.concat(lines, "\n") .. "\n") then
        notify_error(_("Assisted Tagging: couldn't write the additions to darktable's tmp folder."))
        return false
    end
    local script = identify_script()
    local cmd = command_line(python_bin(script), { plugin_root(script) .. "/python/entries_file.py", "add",
        entries_json_path(), path }) .. " 2>&1"
    -- cmd.exe strips the outer quotes of a quoted command line, so the whole thing gets one more pair
    if IS_WINDOWS then cmd = '"' .. cmd .. '"' end
    log("add new entries: " .. cmd)
    local p = io.popen(cmd)
    if not p then
        notify_error(_("Assisted Tagging: couldn't start Python to add the entries."))
        return false
    end
    local out = (p:read("a") or ""):gsub("%s+$", "")
    local ok = p:close()
    log("add new entries: " .. (out ~= "" and out or (ok and "no output" or "failed")))
    if not ok then
        notify_error("Assisted Tagging: " .. (out ~= "" and out or _("adding the entries failed, see the log.")))
        return false
    end
    if not reload_lists(true) then return true end
    local n_images = retag_added_numbers(ticked, image_of, roots.number, M.named_rules(rules, settings).diag.number_seen)
    say(string.format("Assisted Tagging: %s; %d photos tagged with their new number.", out, n_images))
    return true
end

function M.fill_entry_colours(images)
    if queue_if_busy(_("Fill entry colours"), images and #images > 0, function() M.fill_entry_colours(images) end) then return end
    if not can_start(images) then return end
    if #entry_order == 0 then
        dt.print(_("Assisted Tagging: the collection has no entries yet. Add them to its entries.json, then click Reload."))
        return
    end
    if not take_settings() then return end
    if not settings.family_colour then
        dt.print(_("Assisted Tagging: tick the Colour family (section 4) first."))
        return
    end
    busy = true
    M.cancel_requested = false
    start_log("fill entry colours", #images)

    local state = {}
    local okr, err = pcall(function()
        local rows, n_skipped, sent = {}, 0, {}
        local pick_of = select(2, with_paired_jpegs(images))
        local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
        local colour_base = M.family_roots(settings).colour
        for _, img in ipairs(images) do
            local src = pick_of[img.id]
            local hand_colour = M.hand_value(tags_of(img), ledger[img.id], colour_base)
            -- with a colour tag applied by hand, the entry tags Identify wrote name the entry too
            local eid = M.entry_for_tags(tags_of(img), entries, entry_order, not hand_colour and ledger[img.id] or nil)
            if not eid then
                local prefixes = sorted_names(M.hint_tags(tags_of(img), ledger[img.id], entries, M.family_roots(settings).team))
                if #prefixes == 1 then eid = prefixes[1] end
            end
            if eid then
                if not sent[src.id] then
                    sent[src.id] = true
                    rows[#rows + 1] = { src.id, src.path .. "/" .. src.filename, eid, hand_colour or "" }
                end
            else
                n_skipped = n_skipped + 1
                log(string.format("%s: skipped, its tags match no single entry", img.filename))
            end
        end
        if #rows == 0 then
            say(_("Assisted Tagging: no selected image carries all of one entry's tags (applied by you, or by Identify when you added a colour tag), so no colour was read."))
            return
        end
        local results = run_reference_job(state, rows, { "--add-reference", "--colours-only" }, "reading entry colours")
        if not results then return end
        local parsed, notes = M.parse_reference_results(results)
        local n_set, n_already, n_unread, n_failed = M.colour_summary(parsed)
        local extra = {}
        if n_skipped > 0 then extra[#extra + 1] = string.format("%d skipped", n_skipped) end
        if n_failed > 0 then extra[#extra + 1] = string.format("%d failed, see log", n_failed) end
        if notes.differs > 0 then extra[#extra + 1] = string.format("%d colour readings differ from entries.json (see log)", notes.differs) end
        say(string.format("Assisted Tagging: colours set for %d entries, %d already set, %d unread.%s File: %s",
            n_set, n_already, n_unread, #extra > 0 and (" (" .. table.concat(extra, ", ") .. ")") or "", entries_json_path()))
    end)
    finish_reference_job(state, okr, err, "couldn't fill entry colours.")
end

-- Saves the confident vehicles (number-read, or a clear livery match) that the last
-- Identify run recorded for these images as references of the entries it found.
function M.promote_references(images)
    if queue_if_busy(_("Add confident vehicles"), images and #images > 0, function() M.promote_references(images) end) then return end
    if not can_start(images) then return end
    local boxes = boxes_path()
    if not file_exists(boxes) then
        dt.print(_("Assisted Tagging: no records for this collection yet. Run Identify first."))
        return
    end
    if not take_settings() then return end
    busy = true
    M.cancel_requested = false
    start_log("add confident vehicles from last run", #images)

    local state = {}
    local okr, err = pcall(function()
        -- Identify recorded boxes for the JPEG of a RAW+JPEG pair, so a selected RAW reads its JPEG's
        local rows = {}
        local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
        local colour_base = M.family_roots(settings).colour
        for _, img in ipairs((with_paired_jpegs(images))) do
            rows[#rows + 1] = { img.id, img.path .. "/" .. img.filename, "",
                M.hand_value(tags_of(img), ledger[img.id], colour_base) or "" }
        end
        local results = run_reference_job(state, rows, { "--promote-boxes", "--boxes-in", boxes }, "saving vehicles as references")
        if not results then return end
        local counts = { added = 0, none_promotable = 0, flagged = 0, stale = 0, failed = 0 }
        local parsed, notes = M.parse_reference_results(results)
        for _, p in ipairs(parsed) do counts[p[2]] = (counts[p[2]] or 0) + 1 end
        local extra = M.colour_note_extras(notes)
        if counts.none_promotable > 0 then extra[#extra + 1] = string.format("%d images had none confident enough", counts.none_promotable) end
        if counts.flagged > 0 then extra[#extra + 1] = string.format("%d not saved: the audit checks flagged them (see log)", counts.flagged) end
        if counts.stale > 0 then extra[#extra + 1] = string.format("%d changed since the run (run Identify again)", counts.stale) end
        if counts.failed > 0 then extra[#extra + 1] = string.format("%d failed, see log", counts.failed) end
        say(string.format("Assisted Tagging: saved vehicles from %d images as references%s. Crops are in %s/refs.%s",
            counts.added, #extra > 0 and (" (" .. table.concat(extra, ", ") .. ")") or "", current_collection(),
            notes.set > 0 and (" Colours: " .. entries_json_path()) or ""))
    end)
    finish_reference_job(state, okr, err, "couldn't save vehicles as references.")
end

-- Refreshes the collection's reference index from refs/ and writes ref-audit.txt beside it.
-- Needs no selected images.
function M.audit_references()
    if queue_if_busy(_("Audit references"), true, M.audit_references) then return end
    if not can_start(nil, true) then return end
    if not take_settings() then return end
    busy = true
    M.cancel_requested = false
    start_log("audit references", 0)

    local state = {}
    local okr, err = pcall(function()
        local suggest = settings.suggest_crops
        local quarantine = settings.quarantine
        local results = run_reference_job(state, {}, args_of({ "--audit-refs" }, suggest and { "--suggest-crops" } or {},
            quarantine and { "--quarantine" } or {}), "auditing references")
        if not results then return end
        local c, report = {}, ""
        for line in results:gmatch("[^\r\n]+") do
            local k, v = line:match("^([^,]+),(.*)$")
            if k == "report" then report = v elseif k then c[k] = tonumber(v) or 0 end
        end
        local crops_note = (c.suggested or 0) > 0 and string.format(" %d suggested re-crops are in ref-audit-crops.", c.suggested) or ""
        if (c.quarantined or 0) > 0 then
            crops_note = crops_note .. string.format(" %d refs moved to refs-quarantine (listed in moved.txt).", c.quarantined)
        end
        if (c.doubtful_anchors or 0) > 0 then
            crops_note = crops_note .. string.format(" %d anchors look doubtful (never moved; check them by hand).", c.doubtful_anchors)
        end
        crops_note = crops_note .. string.format(" %d cars have no anchor.", c.unanchored or 0)
        say(string.format("Assisted Tagging: audited %d references: %d mislabel suspects, %d cross-entry copies, %d outliers, %d colour outliers, %d odd crops; %d flagged by 2+ checks (start there).%s Details in %s",
            c.references or 0, c.mislabel or 0, c.copies or 0, c.outliers or 0, c.colour or 0, c.crops or 0, c.strongest or 0, crops_note, report))
    end)
    finish_reference_job(state, okr, err, "couldn't audit references.")
end

local BAD_FOLDER_CHARS = '[/\\:*?"<>|]'

-- Validates a typed collection name and that it doesn't already exist, printing
-- why and returning nil when it can't proceed. Doesn't touch disk.
local function new_collection_path(raw_name)
    if busy then
        dt.print(_("Assisted Tagging: another job is still running. Wait for it to finish, or cancel it first."))
        return nil
    end
    if not orphan_gone() then
        dt.print(_("Assisted Tagging: the last run is still stopping. Try again in a moment."))
        return nil
    end
    local name = (raw_name or ""):gsub("^%s+", ""):gsub("%s+$", "")
    if name == "" then
        dt.print(_("Assisted Tagging: type a name for the new collection first"))
        return nil
    end
    if name:find(BAD_FOLDER_CHARS) then
        dt.print(_('Assisted Tagging: collection name can\'t contain / \\ : * ? " < > |'))
        return nil
    end
    if name:lower() == "template" then
        dt.print(_('Assisted Tagging: "template" is the built-in preset, pick another name'))
        return nil
    end
    local dir = collections_root() .. "/" .. name
    if df.test_file(dir, "e") or file_exists(dir .. "/entries.json") then
        dt.print(string.format(_("Assisted Tagging: %s already exists. Pick a new name, or select it as "
            .. "the collection and use Open entries.json instead."), name))
        return nil
    end
    return name, dir
end

-- Selects a just-created collection in the preset list. True once its entries loaded.
local function open_new_collection(name)
    collection_loaded = false
    preset_ctl.refresh()
    if not preset_ctl.select(name) then return false end
    return collection_loaded or reload_lists(true)
end

local function make_collection_dir(dir)
    if IS_WINDOWS then
        os.execute(string.format('mkdir "%s" 2>nul', dir:gsub("/", "\\")))
    else
        os.execute("mkdir -p " .. shell_quote(dir) .. " 2>/dev/null")
    end
end

-- Opens a file in whatever app the OS has associated with it, so the user can
-- read and edit entries.json without leaving darktable for a file manager.
local function open_in_app(path)
    local os_name = dt.configuration.running_os
    local cmd = M.open_command(path, os_name)
    -- cmd.exe strips the outer quotes of a quoted command line, so the whole thing gets one more pair
    if IS_WINDOWS then
        cmd = '"' .. cmd .. '"'
    elseif os_name ~= "macos" then
        cmd = cmd .. " >/dev/null 2>&1 &"
    end
    log("open: " .. cmd)
    if not file_exists(path) or not os.execute(cmd) then
        notify_error(string.format(_("Assisted Tagging: Could not open %s"), path))
    end
end

-- Copies an example's entries.json and, when it has one, its settings.json (see
-- examples_root()) into a new collection: no images needed, since the example
-- already defines the structure, just not your actual entries.
function M.create_collection_from_example(example, raw_name)
    if not example then
        dt.print(_("Assisted Tagging: pick an example first"))
        return
    end
    local name, dir = new_collection_path(raw_name)
    if not name then return end

    local example_dir = examples_root() .. "/" .. example
    local text = read_file(example_dir .. "/entries.json")
    if not text then
        notify_error(string.format(_("Assisted Tagging: couldn't read the %s example's entries.json."), example))
        return
    end
    make_collection_dir(dir)
    local f = io.open(dir .. "/entries.json", "w")
    if not f then
        notify_error(string.format(
            _("Assisted Tagging: couldn't create %s/entries.json (check the collections folder preference)."), dir))
        return
    end
    f:write(text)
    f:close()
    local settings_text = read_file(example_dir .. "/settings.json")
    if settings_text then
        local ok, err = write_file_atomic(dir .. "/settings.json", settings_text)
        if not ok then
            notify_error(string.format(_("Assisted Tagging: couldn't create %s/settings.json: %s"), dir, tostring(err)))
            return
        end
    end

    say(string.format(
        _("Assisted Tagging: created %s from the %s example. Edit its entries.json with your own entries, "
            .. "then click Reload."), name, example))
    open_new_collection(name)
end

-- Builds a new collection's entries.json from the hierarchical tags already on
-- `images` (see M.derive_entries), then adds each image as its entry's reference.
function M.create_collection(images, raw_name)
    if not images or #images == 0 then
        dt.print(_("Assisted Tagging: select some tagged images first"))
        return
    end
    local name, dir = new_collection_path(raw_name)
    if not name then return end

    local image_rows = {}
    for _, img in ipairs(images) do
        local names = {}
        for _, t in ipairs(tags.get_tags(img)) do names[#names + 1] = t.name end
        image_rows[#image_rows + 1] = { key = tostring(img.id), tags = names }
    end
    local derived, entry_of, skipped, thin = M.derive_entries(image_rows)
    if #derived == 0 then
        dt.print(_("Assisted Tagging: none of the selected images carry a hierarchical tag "
            .. "(e.g. Series|Team|Driver) shared by at least " .. M.MIN_REFS_PER_ENTRY .. " of the selected images"))
        return
    end

    make_collection_dir(dir)
    if not write_file_atomic(dir .. "/entries.json", M.entries_json(derived)) then
        notify_error(string.format(
            _("Assisted Tagging: couldn't create %s/entries.json (check the collections folder preference)."), dir))
        return
    end

    local extra = {}
    if #skipped > 0 then
        extra[#extra + 1] = string.format(_("%d skipped (no hierarchical tag)"), #skipped)
    end
    if #thin > 0 then
        extra[#extra + 1] = string.format(
            _("%d skipped (fewer than %d images shared their tag)"), #thin, M.MIN_REFS_PER_ENTRY)
    end
    say(string.format(_("Assisted Tagging: created %s with %d entr%s%s."), name, #derived,
        #derived == 1 and "y" or "ies", #extra > 0 and (" (" .. table.concat(extra, ", ") .. ")") or ""))

    if not open_new_collection(name) then
        notify_error(string.format(_("Assisted Tagging: created %s but couldn't load it, so no references were added. "
            .. "Click Reload, then \"Add tagged images\" with the same images selected (why: assisted_tagging.log)."), name))
        return
    end
    local active_images = {}
    for _, img in ipairs(images) do
        if entry_of[tostring(img.id)] then active_images[#active_images + 1] = img end
    end
    M.add_references(active_images, nil)
end

-- verify_only: report disagreements with existing tags, change none (see M.identify_images).
local function start_identify(allow_cancel, verify_only)
    if busy then
        if allow_cancel and identify_button and identify_cancellable then
            M.cancel_requested = true
            request_cancel()
            identify_cancellable = false
            identify_button.label = _("Cancelling...")
            clear_queue()
            dt.print(_("Assisted Tagging: cancelling, finishing the current step..."))
            return
        end
    end
    -- One run only: M.identify_images clears the box once the run is accepted.
    local replace_manual = not verify_only and replace_manual_check and replace_manual_check.value or false
    M.identify_images(dt.gui.action_images, replace_manual, verify_only)
end

local function selected_entry_id()
    local i = entry_combo and entry_combo.selected or 0
    return entry_order[i]
end

local function selected_example()
    local i = example_combo and example_combo.selected or 0
    local name = example_combo and example_combo[i]
    if not name or name == _("(no examples)") then return nil end
    return name
end

local preset_file_store, make_preset_controls = C.preset_file_store, C.make_preset_controls


-- The preset store for make_preset_controls: each collection folder (one holding an
-- entries.json) is a preset, its settings in settings.json beside entries.json.
collection_store = function()
    local store, warned = {}, {}
    local function dir(name) return collections_root() .. "/" .. name end
    function store.path(name) return dir(name) .. "/settings.json" end
    function store.list()
        local names = {}
        for _i, name in ipairs(list_examples(collections_root())) do
            if name:lower() ~= "template" then
                names[#names + 1] = name
            elseif not warned[name] then
                warned[name] = true
                log(string.format('collection "%s" is hidden: "template" is the built-in preset. Rename its folder to use it.', name))
            end
        end
        return names
    end
    -- A collection without settings.json opens with the defaults.
    function store.read_raw(name)
        if not file_exists(dir(name) .. "/entries.json") then return nil end
        return C.read_file_or_tmp(store.path(name)) or "{}"
    end
    -- The panel's view: old settings upgraded in memory. reload_lists writes the upgrade back.
    function store.read(name)
        local text = store.read_raw(name)
        return text and (M.upgrade_settings_text(text))
    end
    function store.write(name, text) return write_file_atomic(store.path(name), text) end
    -- Renames the collection folder, references and all.
    function store.rename(old, new)
        if busy or orphan or #queue > 0 then return false, "a run is using it, rename it when the run finishes" end
        if df.test_file(dir(new), "e") then return false, dir(new) .. " already exists" end
        local ok, err = os.rename(dir(old), dir(new))
        return ok and true or false, err
    end
    -- Deletes settings.json only; the collection and its references stay.
    function store.remove(name)
        local ok, err = os.remove(store.path(name))
        return ok and true or false, err
    end
    local function run_busy() return busy or orphan or #queue > 0 end
    -- Files and bytes under `path` (0, 0 when it's missing).
    local function tree_size(path)
        local files, bytes = 0, 0
        local p = io.popen(IS_WINDOWS
            and ('dir /s /a-d ' .. shell_quote((path:gsub("/", "\\"))) .. ' 2>nul')
            or ("find " .. shell_quote(path) .. " -type f 2>/dev/null | wc -l; du -sk " .. shell_quote(path) .. " 2>/dev/null"))
        if not p then return files, bytes end
        local lines = {}
        for line in p:lines() do lines[#lines + 1] = line:gsub("\r$", "") end
        p:close()
        if IS_WINDOWS then
            -- the last "N File(s)  1,234 bytes" line is the total over all subfolders
            for _i, line in ipairs(lines) do
                local n, b = line:match("^%s*(%d+) File%(s%)%s+([%d,%.%s\194\160]+) bytes")
                if n then files, bytes = tonumber(n), tonumber((b:gsub("%D", ""))) or 0 end
            end
        else
            files = tonumber((lines[1] or ""):match("%d+")) or 0
            bytes = (tonumber((lines[2] or ""):match("^%d+")) or 0) * 1024
        end
        return files, bytes
    end
    -- Store new copies the whole collection folder: entries, references, settings.
    function store.copy_note(from, to)
        if from == "template" then
            return nil, "store new copies a collection: pick one first (new empty collections come from the new collection section)"
        end
        if run_busy() then return nil, "a run is using it, store a new one when the run finishes" end
        if df.test_file(dir(to), "e") then return nil, dir(to) .. " already exists" end
        local files, bytes = tree_size(dir(from) .. "/refs")
        return string.format('Copies "%s" to "%s" with its %d reference crops (%.1f MB). Continue?',
            from, to, files, bytes / 1048576)
    end
    function store.copy(from, to)
        if run_busy() then return false, "a run is using it, store a new one when the run finishes" end
        if df.test_file(dir(to), "e") then return false, dir(to) .. " already exists" end
        local ok, _how, code
        if IS_WINDOWS then
            ok, _how, code = os.execute('robocopy ' .. shell_quote((dir(from):gsub("/", "\\"))) .. ' '
                .. shell_quote((dir(to):gsub("/", "\\"))) .. ' /E /NFL /NDL /NJH /NJS /NP >nul')
            ok = code ~= nil and code < 8 -- robocopy: 0-7 success, 8+ failure
        else
            ok = os.execute("cp -R " .. shell_quote(dir(from)) .. " " .. shell_quote(dir(to)))
        end
        if not ok or not file_exists(dir(to) .. "/entries.json") then return false, "copy to " .. dir(to) .. " failed" end
        return true
    end
    return store
end

local GROUP_SUPPORT_LABELS = { native = "native groups", tags = "grouping tags", none = "none" }

local function install_panel()
    if M.module_installed then return end
    M.module_installed = true

    local refresh_gates -- re-labels and greys the gated tag rows; set once the panel's entries exist
    local function changed()
        if preset_ctl then preset_ctl.check_dirty() end
        if refresh_gates then refresh_gates() end
    end
    local panel_ready = false -- the first collection load waits for darktable to open (see the end)

    local new_collection_name = new_widget("entry") {
        tooltip = _("Name for the new collection's folder, e.g. \"F1 2026\""),
        placeholder = _("collection name"),
        text = "",
    }
    local new_collection_button = new_widget("button") {
        label = _("From tagged images"),
        tooltip = _("Build a new collection from the selected images' existing tags: images carrying the "
            .. "same hierarchical tags (e.g. Series|Team|Driver) become one entry, then each image is "
            .. "added as that entry's reference. A tag only " .. (M.MIN_REFS_PER_ENTRY - 1)
            .. " image carries is skipped, not made into an entry (and a numeric leaf, e.g. Car|Number|44, "
            .. "becomes that entry's race number)"),
        clicked_callback = function()
            M.create_collection(dt.gui.action_images, new_collection_name.text)
        end,
    }
    example_combo = new_widget("combobox") {
        label = _("example"),
        tooltip = _("A collection template shipped in the repo's examples folder, with placeholder entries and no references"),
        _("(no examples)"),
    }
    local example_view_button = new_widget("button") {
        label = _("View example"),
        tooltip = _("Open the selected example's entries.json in your editor, to read or copy from"),
        clicked_callback = function()
            local example = selected_example()
            if not example then
                dt.print(_("Assisted Tagging: pick an example first"))
                return
            end
            open_in_app(examples_root() .. "/" .. example .. "/entries.json")
        end,
    }
    local example_create_button = new_widget("button") {
        label = _("From example"),
        tooltip = _("Copy the selected example's entries.json into a new collection with no images needed; "
            .. "edit it afterward with your own entries"),
        clicked_callback = function()
            M.create_collection_from_example(selected_example(), new_collection_name.text)
        end,
    }

    local reload_button = new_widget("button") {
        label = _("Reload"),
        tooltip = _("Reread the collections folder (the preset list) and the selected collection's entries.json and settings.json. Unsaved panel changes are replaced by settings.json."),
        clicked_callback = function() reload_lists(false, false, true) end,
    }
    local plan_button = new_widget("button") {
        label = _("Show tag plan"),
        tooltip = _("Write tag-plan.txt in the collection's folder and open it: the exact tags every entry and outcome (team only, unidentified tags (yours), diagnostics) writes, from its entries.json"),
        clicked_callback = function()
            if reload_lists(false, true) and current_collection() ~= "" then
                open_in_app(collections_root() .. "/" .. current_collection() .. "/tag-plan.txt")
            end
        end,
    }
    local open_entries_button = new_widget("button") {
        label = _("Open entries.json"),
        tooltip = _("Open the selected collection's entries.json in the app your system uses for .json files. Save it there, then click Reload."),
        clicked_callback = function() open_in_app(entries_json_path()) end,
    }
    local open_settings_button = new_widget("button") {
        label = _("Open settings.json"),
        tooltip = _("Open the selected collection's settings.json in the app your system uses for .json files, e.g. to delete a removed setting. Save it there, then click Reload; unsaved panel changes are replaced."),
        clicked_callback = function() open_in_app(settings_json_path()) end,
    }
    -- Runs import_start_list.py with argv after the script path; (ok, trimmed output).
    local function run_start_list_import(extra)
        local script = identify_script()
        local argv = { plugin_root(script) .. "/python/import_start_list.py", collections_root() .. "/" .. current_collection() }
        for _, a in ipairs(extra) do argv[#argv + 1] = a end
        local cmd = command_line(python_bin(script), argv) .. " 2>&1"
        -- cmd.exe strips the outer quotes of a quoted command line, so the whole thing gets one more pair
        if IS_WINDOWS then cmd = '"' .. cmd .. '"' end
        log("import start list: " .. cmd)
        local p = io.popen(cmd)
        if not p then return false, _("couldn't start Python for the start list import.") end
        local out = (p:read("a") or ""):gsub("%s+$", "")
        return p:close(), out
    end
    -- One picker per role: (none) + the chosen CSV's headers, preset to the usual names.
    local ROLE_LABELS = { number = _("number"), driver = _("driver"), ["co-driver"] = _("co-driver"), team = _("team"),
        class = _("class"), make = _("make"), model = _("model"), ["shares-car"] = _("shares car with"), paddock = _("paddock") }
    local column_headers = {} -- the chosen CSV's headers; {} until one is read
    local column_combos = {}
    for i, role in ipairs(M.IMPORT_ROLES) do
        column_combos[i] = new_widget("combobox") {
            label = ROLE_LABELS[role],
            tooltip = _("The CSV column that holds this role. Choosing a CSV picks the usual header names; (none) leaves the role out. Only number is required. Driver and co-driver in one cell (Smith / Jones) split when co-driver is (none)."),
            _("(none)"),
        }
    end
    local function load_start_list_header(path)
        column_headers = {}
        local mapped = {}
        if path ~= "" then
            local ok, out = run_start_list_import({ "--csv", path, "--header" })
            if ok then
                column_headers, mapped = M.parse_header_report(out)
            else
                log("import start list: " .. (out or ""))
                notify_error("Assisted Tagging: " .. (out ~= "" and out or _("couldn't read the CSV's header, see the log.")))
            end
        end
        local items = { _("(none)") }
        for _, h in ipairs(column_headers) do items[#items + 1] = h end
        for i, role in ipairs(M.IMPORT_ROLES) do
            local at = 1
            for j, h in ipairs(column_headers) do if h == mapped[role] then at = j + 1 break end end
            fill_combo(column_combos[i], items, at)
        end
    end
    local start_list_file = new_widget("file_chooser_button") {
        title = _("Start list CSV"),
        value = "",
        is_directory = false,
        changed_callback = function(self) load_start_list_header(self.value or "") end,
    }
    local start_list_text = new_widget("text_view") {
        editable = true,
        text = "",
        tooltip = _("Paste an entry list here, e.g. copied from a PDF: one entry per line, number first, e.g. 12 Smith / Jones. Lines without a leading number are skipped."),
    }
    -- File / Paste tabs: a stack shows one source; the open tab's label starts with ●.
    -- text_view has no placeholder, so the paste tab carries its hint as a label.
    local start_list_stack = new_widget("stack") {
        new_widget("box") { orientation = "vertical", start_list_file, table.unpack(column_combos) },
        new_widget("box") {
            orientation = "vertical",
            new_widget("label") { label = _("one entry per line, number first, e.g. 12 Smith / Jones"), halign = "start" },
            start_list_text,
        },
    }
    local start_list_tabs = {}
    local function show_start_list_tab(index)
        start_list_stack.active = index
        start_list_tabs[1].label = (index == 1 and "● " or "○ ") .. _("CSV file")
        start_list_tabs[2].label = (index == 2 and "● " or "○ ") .. _("paste text")
    end
    start_list_tabs[1] = new_widget("button") { clicked_callback = function() show_start_list_tab(1) end }
    start_list_tabs[2] = new_widget("button") { clicked_callback = function() show_start_list_tab(2) end }
    show_start_list_tab(1)
    local start_list_tab_box = new_widget("box") { orientation = "horizontal", start_list_tabs[1], start_list_tabs[2] }
    local import_start_list_button = new_widget("button") {
        label = _("Import start list"),
        tooltip = _("Add the open tab's entries (the CSV or the pasted text) to the selected collection's entries.json. Numbers already listed are kept and reported; the previous file is saved as entries.json.bak."),
        clicked_callback = function()
            if busy or not orphan_gone() then
                dt.print(_("Assisted Tagging: busy, try again when the current run finishes."))
                return
            end
            local argv = {}
            local pasted = start_list_text.text or ""
            if start_list_stack.active == 2 then
                if not pasted:match("%S") then
                    dt.print(_("Assisted Tagging: paste the entries first."))
                    return
                end
                local path = TMP_DIR .. "/assisted_tagging_start_list.txt"
                if not write_file_atomic(path, pasted) then
                    notify_error(_("Assisted Tagging: couldn't write the pasted list to darktable's tmp folder."))
                    return
                end
                argv[#argv + 1] = "--text"
                argv[#argv + 1] = path
            elseif (start_list_file.value or "") ~= "" then
                argv[#argv + 1] = "--csv"
                argv[#argv + 1] = start_list_file.value
                if #column_headers > 0 then
                    local picked = {}
                    for i, role in ipairs(M.IMPORT_ROLES) do
                        picked[role] = column_headers[(column_combos[i].selected or 1) - 1] or ""
                    end
                    argv[#argv + 1] = "--columns"
                    argv[#argv + 1] = M.columns_spec(picked)
                end
            else
                dt.print(_("Assisted Tagging: choose a start list CSV first."))
                return
            end
            local ok, out = run_start_list_import(argv)
            log("import start list: " .. (out ~= "" and out or (ok and "no output" or "failed")))
            if not ok then
                notify_error("Assisted Tagging: " .. (out ~= "" and out or _("the start list import failed, see the log.")))
                return
            end
            start_list_text.text = ""
            -- quiet reload: the import's own summary is the message to keep on screen
            if reload_lists(true) then dt.print("Assisted Tagging: " .. out) end
        end,
    }
    local found = { checks = {}, rows = {}, image_of = {} }
    local found_title = new_widget("label") { label = "", halign = "start" }
    local found_box = new_widget("box") { orientation = "vertical" }
    local add_found_button = new_widget("button") {
        label = _("Add ticked to entries.json"),
        tooltip = _("Add the ticked numbers as new entries and the ticked teams, drivers and co-drivers to their entries; a ticked split turns a \"Driver / Co-driver\" name into a driver and a co-driver. The previous file is saved as entries.json.bak. Photos that read an added number get its number tag."),
        visible = false,
        clicked_callback = function() end,
    }
    local function show_found(rows, title)
        for i = #found_box, 1, -1 do found_box[i] = nil end
        found.rows, found.checks = rows, {}
        for i, r in ipairs(rows) do
            found.checks[i] = new_widget("check_button") { label = M.candidate_label(r), value = false }
            found_box[#found_box + 1] = found.checks[i]
        end
        found_title.label = title
        add_found_button.visible = #rows > 0
    end
    local function clear_found() show_found({}, "") end
    add_found_button.clicked_callback = C.guarded_callback(guard, "button add found entries", function()
        local ticked = {}
        for i, check in ipairs(found.checks) do
            if check.value then ticked[#ticked + 1] = found.rows[i] end
        end
        if M.add_found_entries(ticked, found.image_of) then clear_found() end
    end)
    local find_button = new_widget("button") {
        label = _("Find new entries"),
        tooltip = _("List the numbers the selected photos read or carry by hand that entries.json lacks, the teams, drivers and co-drivers you tagged by hand on entries that have none, and entries whose name still holds \"Driver / Co-driver\" to split. Nothing is added until you tick it."),
        clicked_callback = function()
            local images = dt.gui.action_images
            local rows, image_of = M.find_new_entries(images)
            if not rows then return end
            found.image_of = image_of
            if #rows == 0 then
                show_found(rows, string.format(_("No new entries in %d selected photos."), #images))
            else
                show_found(rows, string.format(_("New in %d selected photos:"), #images))
            end
        end,
    }
    identify_button = new_widget("button") {
        label = _("Identify selection"),
        tooltip = _("Identify the vehicles in the selected images with the models (number reading, livery, colour) and tag them with their entries' tags, plus Derived|From identification (or From number / From driver when your own tag named the car). Writes darktable tags, the tag ledger, boxes.json and report.md. Never writes entries.json."),
        clicked_callback = function() start_identify(true) end,
    }
    local clear_marks_button = new_widget("button") {
        label = _("Clear tagging marks"),
        tooltip = _("Removes every tag this plugin attached to the selected images (entries, colours, diagnostics, unidentified) and forgets them in the ledger. Tags you applied by hand and run stamps stay."),
        clicked_callback = function() M.clear_marks(dt.gui.action_images) end,
    }
    local derive_number_button = new_widget("button") {
        label = _("Derive from number"),
        tooltip = _("For each selected image whose number tag (added by you) names one entry, add that entry's tags and Derived|From number. Lookup only: no model runs, nothing is removed. Adds Check colour too when the image's colour tag differs from the entry's colour. Writes darktable tags and the tag ledger only."),
        clicked_callback = function() M.derive_images(dt.gui.action_images, "number") end,
    }
    local derive_colour_button = new_widget("button") {
        label = _("Derive from colour"),
        tooltip = _("For each selected image with one colour tag, add the tags of the one entry with that colour (narrowed by your team tags) and Derived|From colour. Skips the image when several entries or none have that colour, or when it has a number tag (use Derive from number). Lookup only: no model runs, nothing is removed. Needs entry colours in entries.json (Fill entry colours). Writes darktable tags and the tag ledger only."),
        clicked_callback = function() M.derive_images(dt.gui.action_images, "colour") end,
    }
    status_label = new_widget("label") { label = "", halign = "start" }
    replace_manual_check = new_widget("check_button") {
        label = _("Replace manual tags"),
        tooltip = _("Normally tags you applied by hand are never removed, and images already carrying all of one entry's tags are skipped. Tick this to let runs replace them. It stays ticked until you untick it."),
        value = dt.preferences.read("assisted_tagging", "replace_manual", "bool"),
        clicked_callback = function(w) dt.preferences.write("assisted_tagging", "replace_manual", "bool", w.value) end,
    }
    verify_button = new_widget("button") {
        label = _("Verify selection"),
        tooltip = _("Identify the selected images, fully tagged ones included, and report where the result differs from your tags (boxes.json and report.md). No tags are changed."),
        clicked_callback = function() start_identify(false, true) end,
    }
    entry_combo = new_widget("combobox") {
        label = _("entry"),
        tooltip = _("The entry Add as reference saves the selected images under"),
        _("(no entries)"),
    }
    local add_button = new_widget("button") {
        label = _("Add as reference"),
        tooltip = _("Save the largest vehicle in each selected image as a reference sample of the entry above. Also fills the entry's colour in entries.json when read car colour is on."),
        clicked_callback = function()
            local eid = selected_entry_id()
            if not eid then
                dt.print(_("Assisted Tagging: pick an entry first. If the list is empty, add entries to the collection's entries.json and click Reload."))
                return
            end
            M.add_references(dt.gui.action_images, eid)
        end,
    }
    local add_tagged_button = new_widget("button") {
        label = _("Add tagged images"),
        tooltip = _("For each selected image that already carries all of one entry's tags, save it as a reference of that entry. Also fills the entry's colour in entries.json when read car colour is on."),
        clicked_callback = function() M.add_references(dt.gui.action_images, nil) end,
    }
    local fill_colours_button = new_widget("button") {
        label = _("Fill entry colours"),
        tooltip = _("Read the paintwork colour of each selected image's car and write it as that entry's colour in entries.json when it has none. A colour tag you applied to the image is used instead of the reading, and replaces a colour the entry already has. Saves no references. Needs read car colour on."),
        clicked_callback = function() M.fill_entry_colours(dt.gui.action_images) end,
    }
    local promote_button = new_widget("button") {
        label = _("Add from last run"),
        tooltip = _("Save each vehicle the last Identify run was sure of (number read, or a clear livery match) as a reference of the entry it found. Works for pack shots too: only that car's crop is saved. Also fills the entry's colour in entries.json when read car colour is on."),
        clicked_callback = function() M.promote_references(dt.gui.action_images) end,
    }
    local audit_button = new_widget("button") {
        label = _("Audit references"),
        tooltip = _("Refresh the collection's reference index from refs/, then write ref-audit.txt in the collection folder listing refs that look wrongly filed. Nothing is moved or deleted."),
        clicked_callback = function() M.audit_references() end,
    }

    -- Settings: everything below is part of the collection's preset (settings.json).
    local checks, check_order = {}, {}
    local function check(key, label, tooltip)
        local c = new_widget("check_button") {
            label = label,
            tooltip = tooltip,
            value = false,
            clicked_callback = changed,
        }
        checks[key] = c
        check_order[#check_order + 1] = key
        return c
    end

    local use_hints_check = check("use_hints", _("Use team tags as hints"),
        _("On: a team tag you applied by hand to a solo shot limits matching to that team's entries. Off: team tags are ignored, so the run can override them; a team tag you applied stays on the image next to whatever the run adds. Driver tags still protect their images either way.\nDefault: on. Turn off when your team tags are unreliable and the run should overrule them."))
    local suggest_crops_check = check("suggest_crops", _("Audit: suggest re-crops"),
        _("Also write re-cut copies of wide references (one car found) into ref-audit-crops in the collection folder, for you to review. Nothing in refs/ is changed. The first audit with this ticked is slow (about 8 minutes for 2000 refs); later ones are fast.\nDefault: off. Turn on when the audit flags wide refs you want re-cut."))
    local quarantine_check = check("quarantine", _("Audit: quarantine poor refs"),
        _("After the report is written, move the refs flagged by 2+ checks out of refs/ into refs-quarantine in the collection folder (moved.txt lists each). Nothing is deleted: copy a file back into refs/<entry>/ to undo it.\nDefault: off. Turn on once you trust the audit's flags for this collection."))
    local partial_references_check = check("partial_references", _("partial references"),
        _("Add tagged images also accepts a solo shot tagged only to team level and saves it as a team reference; a clear team lead with no clear driver then gives a team result.\nDefault: off."))
    -- Per tag switch: its check button and the tag name it writes (tag_<key>_name). The row's
    -- box is greyed while a gate in M.TAG_GATES is off (refresh_gates). A heading opens each kind.
    local tag_rows, name_entries, tag_row_boxes = {}, {}, {}
    -- Per family: its switch and the root its tags sit under (family_<key>_root).
    local family_rows = {
        colour = { _("Colour"), _("Read each car's paintwork colour and write it as <root>|<colour>. Also needed by Check colour and entry colours (Fill entry colours and the reference actions). Turning it on re-reads every photo once.") },
        number = { _("Number"), _("Write an identified entry's race number as <root>|<number>.") },
        team = { _("Team"), _("Write an identified entry's team as <root>|<team>. A team tag you applied by hand is also the hint that narrows matching.") },
        driver = { _("Driver"), _("Write an identified entry's name as <root>|<name>.") },
        co_driver = { _("Co-driver"), _("Write an identified entry's co-driver as <root>|<co-driver>. Entries without a co-driver get no tag.") },
        extra = { _("Class"), _("Write an identified entry's class (start-list Class column) as <root>|<class>.") },
        vehicle = { _("Vehicle"), _("Write an identified entry's make and model as <root>|<make>|<model>.") },
        sponsor = { _("Sponsor"), _("Write each rules.sponsor_keywords word read on a car as <root>|<Word>. Words read outside a vehicle box (banners) and words not listed are never written.\nDefault: off.") },
    }
    tag_rows[#tag_rows + 1] = new_widget("section_label") { label = _("tag families") }
    for _i, f in ipairs(M.FAMILIES) do
        local label, what = family_rows[f.key][1], family_rows[f.key][2]
        local c = check("family_" .. f.key, label,
            what .. "\n" .. _("Off: runs stop writing it.") .. "\n" .. _("Default: on."))
        local e = new_widget("entry") {
            placeholder = "blank = " .. f.default_root,
            tooltip = string.format(_("The root the %s tags sit under. Each family needs its own root. Blank = %s."), label, f.default_root),
            text = "",
        }
        name_entries[#name_entries + 1] = { key = "family_" .. f.key .. "_root", entry = e }
        tag_rows[#tag_rows + 1] = new_widget("box") { orientation = "horizontal", c, e }
    end
    local kind_labels, last_kind = {}, nil
    for _i, k in ipairs(M.TAG_KINDS) do kind_labels[k.kind] = k.label end
    for _i, t in ipairs(M.tag_rows_in_order()) do
        if t.kind ~= last_kind then
            tag_rows[#tag_rows + 1] = new_widget("section_label") { label = _(kind_labels[t.kind]) }
            last_kind = t.kind
        end
        local c = check("tag_" .. t.key, t.label, tag_tooltip(t, M.named_rules(rules, settings)))
        tag_checks[t.key] = c
        local name_key = "tag_" .. t.key .. "_name"
        local default
        for _j, f in ipairs(M.PRESET_SCHEMA) do
            if f.key == name_key then default = f.default end
        end
        local e = new_widget("entry") {
            placeholder = "blank = " .. default,
            tooltip = string.format(_("The tag %s writes. Blank = %s."), t.label, default),
            text = "",
        }
        name_entries[#name_entries + 1] = { key = name_key, entry = e }
        local row = new_widget("box") { orientation = "horizontal", c, e }
        tag_rows[#tag_rows + 1] = row
        tag_row_boxes[t.key] = row
    end

    local support_keys
    for _i, f in ipairs(M.PRESET_SCHEMA) do
        if f.key == "group_support" then support_keys = f.choices end
    end
    local shown_support = "native" -- last shown or picked: the combo's callback acts only on a change
    local group_support_combo = new_widget("combobox") {
        label = _("grouping support"),
        tooltip = _("What groups photos for shared identification. Native groups: darktable's image groups. Grouping tags: the children of the tag node below. None: every photo is its own group.\nDefault: native groups. Pick grouping tags after an Assisted Grouping run you have not applied as darktable groups."),
        changed_callback = function(self)
            local key = support_keys[self.selected]
            if not key or key == shown_support then return end
            shown_support = key
            changed()
        end,
        _(GROUP_SUPPORT_LABELS[support_keys[1]]), _(GROUP_SUPPORT_LABELS[support_keys[2]]),
        _(GROUP_SUPPORT_LABELS[support_keys[3]]),
    }
    local run_tag_keys
    for _i, f in ipairs(M.PRESET_SCHEMA) do
        if f.key == "run_tag" then run_tag_keys = f.choices end
    end
    local RUN_TAG_LABELS = { none = "no images", changed = "changed images", all = "all images" }
    local shown_run_tag = "none" -- last shown or picked: the combo's callback acts only on a change
    local run_tag_combo = new_widget("combobox") {
        label = _("tag each run"),
        tooltip = _("Add a timestamp tag (Assisted Tagging|Run|YYYY-MM-DD HH:MM) so the latest run's photos can be filtered apart from earlier ones. Changed images: only copies whose tags this run added or removed. All images: every copy the run processes, which writes to every copy each run and can stall darktable for minutes on a large shoot. Stamps accumulate; remove old ones in darktable's tag manager.\nDefault: no images. Pick changed images when re-running a shoot and you want to review only what changed."),
        changed_callback = function(self)
            local key = run_tag_keys[self.selected]
            if not key or key == shown_run_tag then return end
            shown_run_tag = key
            changed()
        end,
        _(RUN_TAG_LABELS[run_tag_keys[1]]), _(RUN_TAG_LABELS[run_tag_keys[2]]),
        _(RUN_TAG_LABELS[run_tag_keys[3]]),
    }
    local cars_keys
    for _i, f in ipairs(M.PRESET_SCHEMA) do
        if f.key == "cars_per_photo" then cars_keys = f.choices end
    end
    local CARS_LABELS = { solo = "one car (solo)", packs = "several cars (packs)" }
    local shown_cars = "solo" -- last shown or picked: the combo's callback acts only on a change
    local cars_combo = new_widget("combobox") {
        label = _("cars per photo"),
        tooltip = _("One car: only the largest car in each photo is tagged; a smaller car counts only when its number is read, so background traffic adds no car or colour tags. Several cars: every car found is tagged, for racing where cars share a shot.\nDefault: one car. Pick several cars for circuit racing."),
        changed_callback = function(self)
            local key = cars_keys[self.selected]
            if not key or key == shown_cars then return end
            shown_cars = key
            changed()
        end,
        _(CARS_LABELS[cars_keys[1]]), _(CARS_LABELS[cars_keys[2]]),
    }
    local group_node_entry = new_widget("entry") {
        placeholder = _("Grouping tag node (blank = latest run per photo)"),
        tooltip = _("Grouping tags only: the tag node whose children are the groups, e.g. Assisted Grouping|2026-01-01 12:00:00|Group. Blank uses each photo's own latest Assisted Grouping run, so photos regrouped by a later run and photos left on an earlier run both keep their groups.\nDefault: blank. Set it to pin one run."),
        text = "",
    }
    local tolerance_entry = new_widget("entry") {
        placeholder = _("blank = 5"),
        tooltip = _("The most places apart in the sorted number list a neighbouring car can be and still support a doubtful read. The collection's order_weight sets how much of it is used: a neighbour up to order_weight × (tolerance + 1) places away counts. A whole number, 0 or more. Only used when order_weight is above 0.\nDefault: 5. Lower it when cars pass in strict number order; raise it when the order is loose."),
        text = "",
    }
    local order_weight_entry = new_widget("entry") {
        placeholder = _("blank = 0"),
        tooltip = _("How far the cars pass in number order, from 0 (random: the neighbour aid is off) to 1 (strictly in order); 0.5 is loose order.\nDefault: 0. Set 0.5 for a rally or club event shot roughly in number order."),
        text = "",
    }
    local min_read_entry = new_widget("entry") {
        placeholder = _("blank = 0.85"),
        tooltip = _("How sure a number read must be to count, from 0 to 1: raise it if plates or signs get read as numbers, lower it if clear numbers are missed.\nDefault: 0.85."),
        text = "",
    }
    local colour_weight_entry = new_widget("entry") {
        placeholder = _("blank = 0"),
        tooltip = _("How much the colour histogram counts in livery matching, from 0 (off) up; separate from colour tags.\nDefault: 0."),
        text = "",
    }
    -- Number entries read through M.parse_setting.
    local number_entries = {
        { key = "order_weight", entry = order_weight_entry },
        { key = "neighbour_tolerance", entry = tolerance_entry },
        { key = "min_read", entry = min_read_entry },
        { key = "colour_weight", entry = colour_weight_entry },
    }
    local function trim(s) return (s or ""):match("^%s*(.-)%s*$") end

    local shown = M.preset_defaults(M.PRESET_SCHEMA) -- the values show_panel last filled in

    -- The panel's values, or nil and "<key>: <why>" for the first entry M.panel_value refuses.
    read_panel = function()
        local s = {
            group_support = support_keys[group_support_combo.selected] or shown_support,
            run_tag = run_tag_keys[run_tag_combo.selected] or shown_run_tag,
            cars_per_photo = cars_keys[cars_combo.selected] or shown_cars,
            group_node = trim(group_node_entry.text),
        }
        for _i, list in ipairs({ number_entries, name_entries }) do
            for _j, n in ipairs(list) do
                local value, why = M.panel_value(n.key, n.entry.text)
                if value == nil then return nil, why end
                s[n.key] = value
            end
        end
        -- settings.json-only keys have no widget: a run and Save carry the values last loaded
        for _i, key in ipairs(M.PANEL_OTHER_KEYS) do s[key] = shown[key] end
        for _i, key in ipairs(check_order) do s[key] = checks[key].value and true or false end
        return s
    end

    -- Fills the panel from `s`; a number or tag name M.parse_setting refuses shows its default.
    local function show_panel(s)
        local replaced
        s, replaced = M.checked_settings(s)
        for _i, key in ipairs(replaced) do
            log(string.format("settings.json: %s invalid, using %s", key, tostring(s[key])))
        end
        shown = s
        shown_support = s.group_support
        for i, key in ipairs(support_keys) do
            if key == s.group_support and group_support_combo.selected ~= i then group_support_combo.selected = i end
        end
        shown_run_tag = s.run_tag
        for i, key in ipairs(run_tag_keys) do
            if key == s.run_tag and run_tag_combo.selected ~= i then run_tag_combo.selected = i end
        end
        shown_cars = s.cars_per_photo
        for i, key in ipairs(cars_keys) do
            if key == s.cars_per_photo and cars_combo.selected ~= i then cars_combo.selected = i end
        end
        group_node_entry.text = s.group_node
        for _i, n in ipairs(number_entries) do n.entry.text = tostring(s[n.key]) end
        for _i, n in ipairs(name_entries) do n.entry.text = s[n.key] end
        for _i, key in ipairs(check_order) do checks[key].value = s[key] end
        refresh_gates()
    end

    -- Each gated tag row (M.TAG_GATES) says in its label why it is off and is greyed meanwhile,
    -- from the panel as it stands. An entry read_panel refuses leaves the rows as they are.
    refresh_gates = function()
        local s = read_panel()
        if not s then return end
        for _i, t in ipairs(TAG_TOGGLES) do
            local label, gated = M.tag_row_label(t, s)
            tag_checks[t.key].label = label
            tag_row_boxes[t.key].sensitive = not gated
        end
    end

    -- template: only the new-collection controls; a collection: everything else
    local template_box = new_widget("box") {
        orientation = "vertical",
        new_widget("section_label") { label = _("new collection") },
        new_collection_name,
        new_collection_button,
        example_combo,
        example_view_button,
        example_create_button,
    }
    local page_widgets = {
        { plan_button,
          new_widget("label") { label = _("start list"), halign = "start" },
          start_list_tab_box, start_list_stack, import_start_list_button,
          find_button, found_title, found_box, add_found_button },
        {
            group_support_combo,
            new_widget("label") { label = _("grouping tag node"), halign = "start" },
            group_node_entry,
        },
        {
            cars_combo,
            use_hints_check,
            new_widget("label") { label = _("neighbour tolerance"), halign = "start" },
            tolerance_entry,
            new_widget("label") { label = _("order weight"), halign = "start" },
            order_weight_entry,
            new_widget("label") { label = _("min read"), halign = "start" },
            min_read_entry,
            new_widget("label") { label = _("colour weight"), halign = "start" },
            colour_weight_entry,
            partial_references_check,
        },
        tag_rows,
        { new_widget("section_label") { label = _("identify (models; writes tags)") },
          replace_manual_check, run_tag_combo, verify_button, identify_button, status_label,
          new_widget("section_label") { label = _("derive (lookups only; adds tags)") },
          derive_number_button, derive_colour_button,
          new_widget("section_label") { label = _("undo") },
          clear_marks_button },
        { entry_combo, add_button, add_tagged_button, fill_colours_button, promote_button,
          suggest_crops_check, quarantine_check, audit_button },
    }
    local pages = {}
    for i, page in ipairs(M.PANEL_PAGES) do
        pages[i] = { number = page.number, title = _(page.title), widgets = page_widgets[i] }
    end
    -- Open entries.json and Open settings.json sit in the top area, above the page buttons
    local collection_box = new_widget("box") {
        orientation = "vertical",
        new_widget("box") { orientation = "horizontal", open_entries_button, open_settings_button },
        C.paged_sections("assisted_tagging", pages),
    }

    preset_ctl = make_preset_controls({
        prefix = "Assisted Tagging",
        schema = M.PRESET_SCHEMA,
        store = collection_store(),
        read_panel = read_panel,
        show = show_panel,
        remember = function(name)
            dt.preferences.write("assisted_tagging", "last_collection", "string", name == "template" and "" or name)
        end,
        initial = current_collection() ~= "" and current_collection() or "template",
        -- a run may be appending to the log; its lines wait in the buffer until the run ends
        log = function(msg) log(msg); if not busy then flush_log() end end,
        on_change = function(name, is_template)
            template_box.visible = is_template
            collection_box.visible = not is_template
            clear_found()
            collection_loaded = false
            if is_template then
                entries, entry_order = {}, {}
                refresh_entry_combo()
            elseif panel_ready then
                collection_loaded = reload_lists(true)
            end
        end,
        -- a run reads the stored collection's entries and refs until it finishes
        can_switch = function()
            if busy or orphan or #queue > 0 then
                return false, "busy, switch collections when the current run finishes"
            end
            return true
        end,
        allow_store_new = true,
    })

    local panel_box = new_widget("box") {
        orientation = "vertical",
        -- shows the template defaults; nothing is saved
        reset_callback = function()
            show_panel(M.preset_defaults(M.PRESET_SCHEMA))
            changed()
        end,
        preset_ctl.widget,
        reload_button,
        template_box,
        collection_box,
    }

    dt.register_lib(
        "assisted_tagging", _("Assisted Tagging"), true, true,
        { [dt.gui.views.lighttable] = { "DT_UI_CONTAINER_PANEL_RIGHT_CENTER", 100 } },
        panel_box
    )
    dt.control.dispatch(function()
        dt.control.sleep(STARTUP_RELOAD_DELAY_MS)
        panel_ready = true
        if not lists_loaded then collection_loaded = reload_lists(true) end
    end)
    reload_examples()
end

local function destroy()
    if dt.gui.libs["assisted_tagging"] then
        dt.gui.libs["assisted_tagging"].visible = false
    end
    dt.destroy_event("assisted_tagging_run", "shortcut")
end

local function restart()
    if dt.gui.libs["assisted_tagging"] then
        dt.gui.libs["assisted_tagging"].visible = true
    end

    pcall(dt.destroy_event, "assisted_tagging_run", "shortcut")
    dt.register_event("assisted_tagging_run", "shortcut",
        function(event, shortcut)
            guard("shortcut identify", start_identify, false)
        end, _("identify and tag the selected images with Assisted Tagging")
    )
end

M.destroy = destroy
M.restart = restart
M.destroy_method = "hide"
M.show = restart
M.metadata = {
    name = _("Assisted Tagging"),
    purpose = _("Identify and tag motorsport vehicles"),
    author = "Custom Script",
    help = ""
}

if dt.gui then
    if dt.gui.current_view().id == "lighttable" then
        guard("panel install", function()
            install_panel()
            restart()
        end)
    else
        if not M.event_registered then
            dt.register_event("assisted_tagging", "view-changed", function(event, old_view, new_view)
                if new_view.name == "lighttable" or new_view.id == "lighttable" then
                    guard("panel install", function()
                        install_panel()
                        restart()
                    end)
                end
            end)
            M.event_registered = true
        end
    end
end

M.fmt_eta = fmt_eta -- test hook (test_assisted_tagging.lua)

return M
