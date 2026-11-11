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
    -- Suffixed with the decided colour, e.g. "...|Colour|Red"; independent of the outcome.
    colour = "Assisted Tagging|Colour",
    check_colour = "Assisted Tagging|Identification|Check colour",
    -- Experimental (rules.burst_livery_pooling): a frame resolved by pooling box-0
    -- livery similarity across its burst rather than on its own.
    pooled = "Assisted Tagging|Identification|By pooled burst",
    -- One per image, from how many vehicles identify.py boxed (solo / pack / crowded).
    shot_solo = "Assisted Tagging|Identification|Shot|Solo",
    shot_pack = "Assisted Tagging|Identification|Shot|Pack",
    shot_crowded = "Assisted Tagging|Identification|Shot|Crowded",
}

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

-- Shared with the other two plugins (plugin_common.lua); re-exported for the tests.
M.newest_group_node, M.tag_group_keys, M.native_group_keys, M.number_groups =
    C.newest_group_node, C.tag_group_keys, C.native_group_keys, C.number_groups
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

-- identify.py's entries.csv (id,team,number,tag;tag…) → entries by id, and the ids in file order.
function M.parse_entries_csv(text)
    local entries, order = {}, {}
    for line in (text or ""):gmatch("[^\r\n]+") do
        local p = M.parse_csv_line(line, 4)
        if p and p[1] ~= "" and p[4] ~= "" and not entries[p[1]] then
            entries[p[1]] = { id = p[1], team = p[2], number = p[3], tags = split(p[4], ";") }
            order[#order + 1] = p[1]
        end
    end
    return entries, order
end

function M.default_rules()
    local diag = {}
    for k, v in pairs(M.DIAG_TAGS) do diag[k] = v end
    return { team_only = "shared tags", unidentified = {}, diag = diag, settings = {}, from_entries_json = {} }
end

-- The collection settings identify.py writes into rules.csv (python/settings.py MOVED_RULES).
local MOVED_RULES = { order_weight = true, neighbour_tolerance = true, min_read = true,
    colour_weight = true, colour_tags = true, partial_references = true, min_sim = true,
    margin = true, min_face_px = true, burst_livery_pooling = true, blur_references = true }

-- identify.py's rules.csv (key,value lines) → rules. Besides team_only, unidentified and
-- diag_<outcome>: each resolved setting as rules.settings[key] (numbers and booleans), and
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
-- any vehicle was identified. What each outcome adds comes from `rules`.
function M.wanted_tags(rows, entries, rules)
    rules = rules or M.default_rules()
    local wanted, diag, identified = {}, {}, false
    -- held: a box disagreed with tags the user applied by hand and was left as they had it.
    -- That's not "unidentified", so it adds no unidentified tags.
    local held, shot = false, nil
    local function note(outcome)
        local name = rules.diag[outcome]
        if name and name ~= "" then diag[name] = true end
    end
    for _, r in ipairs(rows) do
        local e = entries[r.entry_id]
        if r.shot and r.shot ~= "" then shot = r.shot end
        if r.method == "conflict" then
            held = true
        elseif e and (r.method == "number" or r.method == "livery" or r.method == "burst" or r.method == "pooled" or r.method == "neighbour" or r.method == "face") then
            for _, t in ipairs(e.tags) do wanted[t] = true end
            note(r.method)
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
            local base = rules.diag.colour
            if base and base ~= "" then diag[base .. "|" .. r.colour] = true end
            if r.colour_flag then note("check_colour") end
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

-- rules with every diagnostic named from settings `s` (tag_<key>_name, tag_shot_name|Solo/Pack/
-- Crowded), switch on or off: rules.csv leaves a switched-off diagnostic blank, and detach,
-- hand-tag protection and tooltips still need its name.
function M.named_rules(rules, s)
    local named, diag = {}, {}
    for k, v in pairs(rules) do named[k] = v end
    for k in pairs(M.DIAG_TAGS) do
        local leaf = k:match("^shot_(.+)$")
        diag[k] = leaf and (s.tag_shot_name .. "|" .. leaf:sub(1, 1):upper() .. leaf:sub(2))
            or s["tag_" .. k .. "_name"]
    end
    named.diag = diag
    return named
end

-- rules with the diagnostics in `off` (outcome key → true) blanked, for wanted_tags.
-- owned_tags keeps the full rules, so the next run detaches what is off.
-- "shot" covers shot_solo, shot_pack and shot_crowded.
function M.mask_diag(rules, off)
    local masked, diag = {}, {}
    for k, v in pairs(rules) do masked[k] = v end
    for k, v in pairs(rules.diag) do
        diag[k] = (off[k] or (off.shot and k:sub(1, 5) == "shot_")) and "" or v
    end
    masked.diag = diag
    return masked
end

-- Prefixes of the dynamic diagnostics (one tag per value): "...Number seen|<digits>"
-- and "...Colour|<colour>".
function M.owned_prefixes(rules)
    local out = {}
    for _, k in ipairs({ "number_seen", "colour" }) do
        local base = rules.diag[k]
        if base and base ~= "" then out[#out + 1] = base .. "|" end
    end
    return out
end

-- The colour the user set by hand: the suffix of the one tag under `base` that is in
-- `have` but not in `ledger_set` (the plugin's own). nil for none, several, or no base.
function M.hand_colour(have, ledger_set, base)
    if not base or base == "" then return nil end
    local prefix, found, n = base .. "|", nil, 0
    for name in pairs(have) do
        if name:sub(1, #prefix) == prefix and not (ledger_set and ledger_set[name]) then
            found, n = name:sub(#prefix + 1), n + 1
        end
    end
    return n == 1 and found or nil
end

-- The tags under `base` in `have` that are not in `ledger_set`: colours the user set by
-- hand, which a run must never detach. Empty for no base.
function M.hand_colour_tags(have, ledger_set, base)
    local out = {}
    if not base or base == "" then return out end
    local prefix = base .. "|"
    for name in pairs(have) do
        if name:sub(1, #prefix) == prefix and not (ledger_set and ledger_set[name]) then out[name] = true end
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

-- A reference job's results.csv (`id,status,colour_note`; files from before colour notes have
-- no third column) → its rows { id, status, note } and the count of each colour note.
function M.parse_reference_results(text)
    local rows, notes = {}, { set = 0, differs = 0, layout = 0 }
    for line in (text or ""):gmatch("[^\r\n]+") do
        local p = M.parse_csv_line(line, 3) or M.parse_csv_line(line, 2)
        if p then
            p[3] = p[3] or ""
            rows[#rows + 1] = p
            if notes[p[3]] then notes[p[3]] = notes[p[3]] + 1 end
        end
    end
    return rows, notes
end

-- The done-message clauses for a reference job's colour notes; only non-zero counts.
function M.colour_note_extras(notes)
    local out = {}
    if notes.set > 0 then out[#out + 1] = string.format("%d entries got a colour", notes.set) end
    if notes.differs > 0 then out[#out + 1] = string.format("%d colour readings differ from entries.json (see log)", notes.differs) end
    if notes.layout > 0 then out[#out + 1] = string.format("%d colours to add by hand (see log)", notes.layout) end
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
-- user's own, which a run must never detach.
function M.protected_tags(have, ledger_set, entries)
    local in_entry = {}
    for _, e in pairs(entries) do
        for _, t in ipairs(e.tags) do in_entry[t] = true end
    end
    local out = {}
    for name in pairs(have) do
        if in_entry[name] and not (ledger_set and ledger_set[name]) then out[name] = true end
    end
    return out
end

-- Tags among `have` the user applied (not in `ledger_set`) that are a strict prefix of some
-- entry's tag (`prefix|…`): team-level hints that narrow matching. A driver's own leaf tag is not.
function M.hint_prefixes(have, ledger_set, entries)
    local below = {}
    for _, e in pairs(entries) do
        for _, t in ipairs(e.tags) do
            local pos = 1
            while true do
                local bar = t:find("|", pos, true)
                if not bar then break end
                below[t:sub(1, bar - 1)] = true
                pos = bar + 1
            end
        end
    end
    local out = {}
    for name in pairs(have) do
        if below[name] and not (ledger_set and ledger_set[name]) then out[name] = true end
    end
    return out
end

-- The entry an already-tagged image belongs to: the one whose tags it carries
-- all of (a shared team tag alone matches no one). nil when none or several do.
function M.entry_for_tags(have, entries, order)
    local found = nil
    for _, id in ipairs(order) do
        local all = #entries[id].tags > 0
        for _, t in ipairs(entries[id].tags) do
            if not have[t] then all = false; break end
        end
        if all then
            if found then return nil end
            found = id
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
        local p = M.parse_csv_line(line, 11) or M.parse_csv_line(line, 10) or M.parse_csv_line(line, 9)
        local id = p and tonumber(p[1])
        if id and p[3] == "error" then
            errored[id] = true
        elseif id and p[3] == "skipped" then
            skipped[id] = true
        elseif id then
            rows_of[id] = rows_of[id] or {}
            table.insert(rows_of[id], { box = tonumber(p[2]), method = p[3], entry_id = p[4],
                                         alt_entry_id = p[5], unmatched_number = p[7], shot = p[8], order_flag = p[9] == "1",
                                         colour = p[10] or "", colour_flag = p[11] == "1" })
        end
    end
    return rows_of, errored, skipped
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

-- The shared prefix and each entry's name when every entry's tags are exactly
-- prefix|team and prefix|team|name (prefix|name with no team) under one prefix, which
-- is what rules.tag_prefix rebuilds; nil when any entry doesn't fit.
function M.prefix_form(entries)
    local prefix, names = nil, {}
    for i, e in ipairs(entries) do
        local team = e.team or ""
        local deepest = e.tags[1]
        for _, t in ipairs(e.tags) do
            if tag_depth(t) > tag_depth(deepest) then deepest = t end
        end
        local name = tag_leaf(deepest)
        local parent = deepest:match("^(.*)|[^|]*$")
        if not parent or #e.tags ~= (team ~= "" and 2 or 1) then return nil end
        if team ~= "" then
            if tag_leaf(parent) ~= team then return nil end
            local team_tag = false
            for _, t in ipairs(e.tags) do if t == parent then team_tag = true end end
            parent = parent:match("^(.*)|[^|]*$")
            if not team_tag or not parent then return nil end
        end
        if prefix and prefix ~= parent then return nil end
        prefix, names[i] = parent, name
    end
    return prefix, names
end

-- An entries.json for derived entries. Entries already carry only ids/tags/numbers that
-- passed sanitize_id/hierarchical_tags/the digit check, so this never needs to reject
-- input. With prefix_form it is the {rules, entries} object using rules.tag_prefix and
-- `name`; otherwise a bare list of entries with full tags (default rules apply).
function M.entries_json(entries)
    local prefix, names = M.prefix_form(entries)
    if prefix then
        local parts = {}
        for i, e in ipairs(entries) do
            parts[#parts + 1] = string.format('    { "id": %s, "number": %s, "team": %s, "name": %s }',
                json_string(e.id), json_string(e.number or ""), json_string(e.team or ""), json_string(names[i]))
        end
        return string.format('{\n  "rules": { "tag_prefix": %s },\n  "entries": [\n%s\n  ]\n}\n',
            json_string(prefix), table.concat(parts, ",\n"))
    end
    local parts = {}
    for _, e in ipairs(entries) do
        local tag_parts = {}
        for _, t in ipairs(e.tags) do tag_parts[#tag_parts + 1] = json_string(t) end
        parts[#parts + 1] = string.format('  { "id": %s, "number": %s, "team": %s, "tags": [%s] }',
            json_string(e.id), json_string(e.number or ""), json_string(e.team or ""), table.concat(tag_parts, ", "))
    end
    return "[\n" .. table.concat(parts, ",\n") .. "\n]\n"
end


-- A collection's settings (settings.json beside entries.json). The built-in "template"
-- holds these defaults. replace_manual is a one-off choice per run, not a setting.
-- Mirrors SETTINGS_SCHEMA in python/settings.py (test_settings.py checks keys and defaults).
M.PRESET_SCHEMA = {
    { key = "use_hints", kind = "bool", default = true },
    { key = "group_support", kind = "choice", choices = { "native", "tags", "none" }, default = "native" },
    { key = "group_node", kind = "string", default = "" },
    { key = "run_tag", kind = "bool", default = false },
    { key = "suggest_crops", kind = "bool", default = false },
    { key = "quarantine", kind = "bool", default = false },
    { key = "embedder_file", kind = "string", default = "" },
    { key = "ocr_rec_file", kind = "string", default = "" },
    { key = "order_weight", kind = "number", default = 0 },
    { key = "neighbour_tolerance", kind = "number", default = 5 },
    { key = "min_read", kind = "number", default = 0.85 },
    { key = "colour_weight", kind = "number", default = 0 },
    { key = "colour_tags", kind = "bool", default = false },
    { key = "partial_references", kind = "bool", default = false },
    { key = "min_sim", kind = "number", default = 0.5 },
    { key = "margin", kind = "number", default = 0.05 },
    { key = "min_face_px", kind = "number", default = 48 },
    { key = "burst_livery_pooling", kind = "bool", default = false },
    { key = "blur_references", kind = "bool", default = false },
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
    { key = "tag_colour", kind = "bool", default = true },
    { key = "tag_colour_name", kind = "string", default = "Assisted Tagging|Colour" },
    { key = "tag_check_colour", kind = "bool", default = true },
    { key = "tag_check_colour_name", kind = "string", default = "Assisted Tagging|Identification|Check colour" },
    { key = "tag_shot", kind = "bool", default = true },
    { key = "tag_shot_name", kind = "string", default = "Assisted Tagging|Identification|Shot" },
}

-- Number ranges, as SETTINGS_SCHEMA's lo/hi (open = the bound itself is out) and whole numbers.
local SETTING_RANGES = {
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

-- Panel entry text for setting `key` → its value, or nil and why. Blank text is an error;
-- the panel decides what blank means.
function M.parse_setting(key, text)
    local item = SCHEMA_BY_KEY[key]
    if not item then return nil, "unknown setting" end
    local t = tostring(text or ""):match("^%s*(.-)%s*$")
    if t == "" then return nil, "blank" end
    if item.kind == "string" then
        if key:match("_name$") and t:find('[,;"]') then return nil, 'a tag name can\'t hold , ; or "' end
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

-- A copy of settings `s` with each number or tag name that M.parse_setting refuses (e.g. a
-- hand-edited settings.json out of range) set to its default, and the keys replaced.
function M.checked_settings(s)
    local out, replaced = {}, {}
    for k, v in pairs(s) do out[k] = v end
    for _, item in ipairs(M.PRESET_SCHEMA) do
        local key = item.key
        if item.kind == "number" or key:match("^tag_.+_name$") then
            if M.parse_setting(key, tostring(s[key])) == nil then
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

-- The settings file a GUI run passes as --settings: the panel's values, beside the run's
-- other temp files (`base` is their shared name prefix).
function M.run_settings_path(base)
    return base .. "settings.run.json"
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

-- Every tag attach/detach rewrites the XMP sidecar, so writes are paced:
-- after a budget of writes the GUI gets a short sleep. Identifying fills the
-- progress bar to PROGRESS_ANALYSIS, writing tags fills the rest.
local PROGRESS_ANALYSIS = 0.8
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
local CACHE_PATH = dt.configuration.config_dir .. "/assisted_tagging/cache.sqlite"
local LEDGER_PATH = dt.configuration.config_dir .. "/assisted_tagging/ledger.csv"
local LIB_KEY = C.library_key(dt)
local LAST_RUN_DIR = dt.configuration.config_dir .. "/assisted_tagging/last-run"
local RUNS_DIR = dt.configuration.config_dir .. "/assisted_tagging/runs"
local DEFAULT_COLLECTIONS_ROOT = dt.configuration.config_dir .. "/assisted_tagging/collections"

local MODEL_FILES = {
    detector_model = "object_detection_yolox_2022nov.onnx",
    ocr_detection_model = "text_detection_en_ppocrv3_2023may.onnx",
    ocr_recognition_model = "en_PP-OCRv5_mobile_rec.onnx",  -- needs its .yml beside it
    ocr_recognition_fallback = "text_recognition_CRNN_EN_2021sep.onnx",
    embedder_model = "dinov2_small.onnx",
    face_detector_model = "face_detection_yunet_2023mar.onnx",
    face_recognizer_model = "face_recognition_sface_2021dec.onnx",
}

if dt.gui then
    C.register_shared_prefs(dt)
    dt.preferences.register("assisted_tagging", "collections_root", "directory",
        "Assisted Tagging: collections folder",
        "Folder with one folder per collection (entries.json + refs). Empty = assisted_tagging/collections in darktable's config folder",
        "")
end

-- One "tag_<outcome>" setting per diagnostic under Assisted Tagging|Identification
-- (keys match M.DIAG_TAGS / the rules' diag_<outcome>; "shot" covers all three Shot tags).
-- Off = runs stop writing it and detach it from the images they process. Entry and
-- unidentified tags (entries.json) and identification itself are unchanged.
local TAG_TOGGLES = {
    { key = "number", label = "By number", when = "its race number was read." },
    { key = "livery", label = "By livery", when = "it matched the entry's reference samples." },
    { key = "burst", label = "By burst", when = "the rest of its burst agreed on one entry." },
    { key = "pooled", label = "By pooled burst",
      when = "the experimental burst_livery_pooling rule resolved it from its burst's pooled livery similarity." },
    { key = "neighbour", label = "By neighbour",
      when = "a doubtful number read was settled by the groups shot just before and after. Needs the collection's order_weight above 0." },
    { key = "check_order", label = "Check order",
      when = "a low-confidence number read that no neighbouring group supports. The entry tag stays; delete this tag once checked." },
    { key = "team", label = "Team only", when = "two teammates were too close to call; only their shared tags are added." },
    { key = "none", label = "Unidentified", when = "no vehicle was found, or no confident match." },
    { key = "number_seen", label = "Number seen",
      when = "OCR read digits that didn't resolve to one entry. Added alongside the outcome tag." },
    { key = "colour", label = "Colour",
      when = "a colour was decided for the vehicle. Added alongside the outcome tag." },
    { key = "check_colour", label = "Check colour",
      when = "the number read is confident but the car's colour differs from its entry's. Delete this tag once checked." },
    { key = "shot", label = "Shot",
      when = "Solo: one vehicle found. Pack: two or three. Crowded: the detector's limit was reached, so there may be more cars than were identified." },
}

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
    local pref = C.python_bin(dt, "assisted_tagging", log)
    if pref ~= "" then return pref end

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
    return (M.preset_merge(M.PRESET_SCHEMA, M.preset_decode(text) or {}))
end
local settings = collection_settings(current_collection())

local function model_path(name, script)
    local file = MODEL_FILES[name]
    if name == "embedder_model" and settings.embedder_file ~= "" then file = settings.embedder_file end
    if name == "ocr_recognition_model" and settings.ocr_rec_file ~= "" then file = settings.ocr_rec_file end
    return plugin_root(script) .. "/models/" .. file
end

local function entries_json_path()
    return collections_root() .. "/" .. current_collection() .. "/entries.json"
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
local preset_ctl = nil -- the preset controls; each preset is a collection (set by install_panel)
local collection_store -- defined with the panel code below
local collection_loaded = false -- the last collection switch loaded its entries
local identify_cancellable = false -- the identify button currently reads "Cancel"
local replace_manual_check = nil
local read_panel = nil -- set by install_panel: the panel's values as settings

-- A GUI run reads the panel as it starts; headless runs keep the collection's settings.
-- False (and says why) when the panel holds a value it can't use.
local function take_settings()
    if not read_panel then return true end
    local s, why = read_panel()
    if not s then dt.print("Assisted Tagging: " .. why); return false end
    settings = s
    return true
end
local entries, entry_order, rules = {}, {}, M.default_rules()
local tag_checks = {} -- TAG_TOGGLES key → its check button (set by install_panel)

-- Writes/When/Off for a tag switch, naming the tag from `named` (M.named_rules of the
-- loaded collection's settings).
local function tag_tooltip(t, named)
    local keys = t.key == "shot" and { "shot_solo", "shot_pack", "shot_crowded" } or { t.key }
    local names = {}
    for _i, k in ipairs(keys) do
        local name = named.diag[k]
        names[#names + 1] = k == "number_seen" and name .. "|<digits>"
            or k == "colour" and name .. "|<colour>" or name
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
local function run_python(args, job, from, to, hint)
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
    local start, last_progress, last_change = os.time(), nil, os.time()
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
        local cur, tot = (progress or ""):match("(%d+),(%d+)")
        local num, total = tonumber(cur), tonumber(tot)
        if hint and num and total and total > 0 then
            if job and job.valid then job.percent = from + (to - from) * math.min(1.0, num / total) end
            dt.print_hinter(string.format("Assisted Tagging: %s %d / %d%s", hint, num, total,
                fmt_eta(os.time() - start, num, total)))
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
        return _("Assisted Tagging: Python is missing a package. Install python/requirements.txt into the interpreter set in preferences → Lua options, or see assisted_tagging.log.")
    elseif code == 9009 or code == 127 then -- cmd.exe / sh: command not found
        return _("Assisted Tagging: Python wasn't found. Set \"Python interpreter (.venv)\" in preferences → Lua options.")
    end
    return string.format("Assisted Tagging: identify.py stopped with exit code %s. Details are in assisted_tagging.log in darktable's config folder.",
        tostring(code or "?"))
end

-- The collection's reader when one is set; else PP-OCRv5, or the CRNN with one
-- warning when the v5 model or its .yml isn't in models/ (an older install).
local function ocr_rec_path(script)
    local path = model_path("ocr_recognition_model", script)
    if settings.ocr_rec_file ~= "" then return path end
    if file_exists(path) and file_exists((path:gsub("%.onnx$", ".yml"))) then return path end
    local fallback = model_path("ocr_recognition_fallback", script)
    log(string.format("number reader: %s or its .yml is missing from models/, using %s (see the README to download PP-OCRv5)",
        MODEL_FILES.ocr_recognition_model, MODEL_FILES.ocr_recognition_fallback))
    return fallback
end

local function model_args(script)
    local args = {
        "--detector", model_path("detector_model", script),
        "--ocr-det", model_path("ocr_detection_model", script),
        "--ocr-rec", ocr_rec_path(script),
        "--embedder", model_path("embedder_model", script),
    }
    -- face models are optional: only people collections need them, so a missing file is left unset
    for flag, name in pairs({ ["--face-detector"] = "face_detector_model", ["--face-recognizer"] = "face_recognizer_model" }) do
        local path = model_path(name, script)
        if file_exists(path) then args[#args + 1] = flag; args[#args + 1] = path end
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
    for _, p in ipairs({ MANIFEST_PATH, RESULTS_PATH, RESULTS_PATH .. ".tmp", DONE_PATH, DONE_PATH .. ".job",
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
            local text, copied = M.backfill_settings(store.read(current_collection()), rules)
            if text then
                if store.write(current_collection(), text) then
                    log("settings.json: copied " .. table.concat(copied, ", ") .. " from entries.json")
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
local function prepare_run(images, replace_manual)
    -- Duplicates and RAW+JPEG pairs are identified once, from the JPEG; the tags go on every copy.
    local primaries, group_of = M.collapse_shots(images)

    local time_of, primary_ids = {}, {}
    for _, img in ipairs(primaries) do
        time_of[img.id] = M.exif_time_to_epoch(img.exif_datetime_taken)
        table.insert(primary_ids, img.id)
    end

    local mechanism = settings.group_support
    local key_of, node, multi = {}, nil, {}
    if mechanism == "native" then
        local items = {}
        for _, img in ipairs(primaries) do
            items[#items + 1] = { id = img.id, leader = img.group_leader and img.group_leader.id }
        end
        key_of = M.native_group_keys(items)
    elseif mechanism == "tags" then
        local items, lists = {}, {}
        for _, img in ipairs(primaries) do
            local have = tags_of(img)
            items[#items + 1] = { id = img.id, tags = have }
            local names = {}
            for name in pairs(have) do names[#names + 1] = name end
            lists[#lists + 1] = names
        end
        local typed = settings.group_node:match("^%s*(.-)%s*$")
        node = typed ~= "" and typed or M.newest_group_node(lists)
        if node then key_of, multi = M.tag_group_keys(items, node) end
    end
    local burst_of = M.number_groups(primary_ids, key_of)

    local size_of, grouped = {}, 0
    for _, id in ipairs(primary_ids) do size_of[burst_of[id]] = (size_of[burst_of[id]] or 0) + 1 end
    for _, id in ipairs(primary_ids) do
        if size_of[burst_of[id]] >= 2 then grouped = grouped + 1 end
    end
    local msg = string.format("group support %s: %d of %d photos in groups of 2+", mechanism, grouped, #primaries)
    if mechanism == "tags" then
        msg = msg .. string.format(", node %s", node or "(none found)")
        if node and next(key_of) == nil then msg = msg .. " (matches no selected photo)" end
        if #multi > 0 then msg = msg .. ", several children on ids " .. table.concat(multi, ",") end
    end
    log(msg)

    -- The ledger holds the tags this plugin attached. Entries no longer on the image are
    -- dropped, so a tag removed and re-applied by hand counts as the user's again.
    -- Protection and hints read the entries loaded at the last Reload or run, so Reload after
    -- editing entries.json.
    local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
    local protected_of, hints_of, sent_protected_of = {}, {}, {}
    local use_hints = settings.use_hints
    local named = M.named_rules(rules, settings)
    for _, copies in pairs(group_of) do
        for _, copy in ipairs(copies) do
            local have = tags_of(copy)
            local kept = {}
            for name in pairs(ledger[copy.id] or {}) do
                if have[name] then kept[name] = true end
            end
            ledger[copy.id] = next(kept) and kept or nil
            protected_of[copy.id] = replace_manual and {} or M.protected_tags(have, kept, entries)
            hints_of[copy.id] = replace_manual and {} or M.hint_prefixes(have, kept, entries)
            -- the identifier sees protected tags for skip and conflict checks; with hints off a team tag
            -- is not among them, but protected_of still keeps the run from detaching it
            local sent = {}
            for name in pairs(protected_of[copy.id]) do
                if use_hints or not hints_of[copy.id][name] then sent[name] = true end
            end
            sent_protected_of[copy.id] = sent
            if not use_hints then hints_of[copy.id] = {} end
            -- hand colour tags only stop a detach; sent to the identifier they'd read as entry tags
            for name in pairs(replace_manual and {} or M.hand_colour_tags(have, kept, named.diag.colour)) do
                protected_of[copy.id][name] = true
            end
            -- likewise hand-applied diagnostic, unidentified and number-seen tags
            for name in pairs(replace_manual and {} or M.hand_diag_tags(have, kept, named)) do
                protected_of[copy.id][name] = true
            end
        end
    end

    local rows = {}
    for _, img in ipairs(primaries) do
        -- a hand tag on any copy (e.g. only the RAW) counts for the shot
        local sent, hints = {}, {}
        for _, copy in ipairs(group_of[img.id]) do
            for name in pairs(sent_protected_of[copy.id]) do sent[name] = true end
            for name in pairs(hints_of[copy.id]) do hints[name] = true end
        end
        rows[#rows + 1] = { img.id, img.path .. "/" .. img.filename, burst_of[img.id],
                            table.concat(sorted_names(sent), ";"),
                            table.concat(sorted_names(hints), ";"),
                            time_of[img.id] and tostring(time_of[img.id]) or "" }
    end
    return { primaries = primaries, group_of = group_of, protected_of = protected_of, ledger = ledger,
             applying = false }, rows
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
-- longer in the library. A failed write is tried once more, then reported on screen.
local function write_ledger(ledger)
    local pruned, skipped = M.ledger_prune(ledger, image_exists)
    if pruned > 0 then log(string.format("ledger: dropped %d images no longer in the library", pruned)) end
    if skipped then log("ledger: prune skipped, no image id resolved") end
    local text = M.ledger_format(ledger, LIB_KEY)
    local ok_w, err = write_file_atomic(LEDGER_PATH, text)
    if not ok_w then
        dt.control.sleep(200)
        ok_w, err = write_file_atomic(LEDGER_PATH, text)
    end
    if not ok_w then
        log("ledger: couldn't save " .. LEDGER_PATH .. " after two tries: " .. tostring(err))
        notify_error(_("Assisted Tagging: couldn't save the tag ledger ") .. LEDGER_PATH .. " (" .. tostring(err)
            .. "). Tags this run attached will count as yours next run.")
    end
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
    -- one stamp per run; never owned, so later runs leave earlier stamps in place
    local run_tag = settings.run_tag
        and os.date("Assisted Tagging|Run|%Y-%m-%d %H:%M") or nil
    local tag_objs, writes, failed, first_error = {}, 0, 0, nil
    local n_tagged, n_unidentified, n_missing = 0, 0, 0
    local n_skipped, n_conflict = 0, 0
    local by_method = { number = 0, livery = 0, burst = 0, team = 0, pooled = 0, face = 0, neighbour = 0 }
    local function tag_named(name)
        tag_objs[name] = tag_objs[name] or tags.create(name)
        return tag_objs[name]
    end

    run.applying = true
    for i, img in ipairs(primaries) do
        local results = rows_of[tonumber(img.id)]
        if skipped[tonumber(img.id)] then
            n_skipped = n_skipped + 1
        elseif not results then
            n_missing = n_missing + 1
        else
            local wanted, diag, identified = M.wanted_tags(results, entries, write_rules)
            if identified then n_tagged = n_tagged + 1 else n_unidentified = n_unidentified + 1 end
            for _, r in ipairs(results) do
                if by_method[r.method] and entries[r.entry_id] then by_method[r.method] = by_method[r.method] + 1 end
                if r.method == "conflict" then n_conflict = n_conflict + 1 end
            end
            for name in pairs(diag) do wanted[name] = true end
            if run_tag then wanted[run_tag] = true end
            for _, copy in ipairs(group_of[img.id]) do
                local attach, detach = M.tag_changes(tags_of(copy), wanted, owned, owned_prefixes,
                    protected_of[copy.id], M.ledgered_owned(ledger[copy.id], owned_roots))
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
                if writes >= WRITE_BUDGET then
                    writes = 0
                    dt.control.sleep(WRITE_SLEEP_MS)
                end
            end
        end
        if cancelled(job) then
            say(string.format("Assisted Tagging: stopped while writing tags; %d of %d images were updated. Run again to finish.",
                i, #primaries))
            return
        end
    end

    local parts = {}
    for _, m in ipairs({ { "number", "by number" }, { "livery", "by livery" }, { "burst", "by burst" }, { "neighbour", "by neighbour" },
                         { "team", "team only" }, { "pooled", "by pooled burst" }, { "face", "by face" } }) do
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

-- replace_manual: lift the protection of tags the user applied by hand, for this run only.
-- verify_only: analyse fully tagged images too and report disagreements, changing no tags.
function M.identify_images(images, replace_manual, verify_only)
    local label = verify_only and _("Verify") or _("Identify")
    -- the replace box covers one run: it clears once this run is queued or started, not when refused
    local function used_replace_box()
        if replace_manual and replace_manual_check then replace_manual_check.value = false end
    end
    if queue_if_busy(label, images and #images > 0, function() M.identify_images(images, replace_manual, verify_only) end) then
        used_replace_box()
        return
    end
    if not can_start(images) then return end
    if not take_settings() then return end
    used_replace_box()
    busy = true
    M.cancel_requested = false
    identify_cancellable = true
    if identify_button then identify_button.label = _("Cancel") end
    start_log(verify_only and "verify started" or "identify started", #images)
    log(string.format("settings: replace manual %s, team hints %s, tag each run %s, grouping support %s, node %s, neighbour tolerance %s, order weight %s",
        tostring(replace_manual and true or false),
        tostring(settings.use_hints),
        tostring(settings.run_tag),
        settings.group_support,
        settings.group_node ~= "" and settings.group_node or "(blank)",
        tostring(settings.neighbour_tolerance),
        tostring(settings.order_weight)))

    local job, run = nil, nil
    local okr, err = pcall(function()
        local rows
        run, rows = prepare_run(images, replace_manual)
        run.verify_only = verify_only
        pcall(os.remove, RESULTS_PATH)
        pcall(os.remove, ENTRIES_PATH)
        pcall(os.remove, RULES_PATH)
        if not write_rows(MANIFEST_PATH, rows) then
            error(WRITE_ROWS_FAILED, 0)
        end

        job = dt.gui.create_job(_("Assisted Tagging"), true, stop_job)
        job.percent = 0.0
        local script = identify_script()
        local code, why = run_python(args_of({ MANIFEST_PATH, RESULTS_PATH },
            collection_args(), settings_args(), model_args(script), verify_only and { "--verify" } or {}, {
                "--cache", CACHE_PATH,
                "--entries-out", ENTRIES_PATH, "--rules-out", RULES_PATH,
                "--boxes-out", boxes_path(),
                "--report-out", report_prefix(),
                "--archive-dir", RUNS_DIR,
            }),
            job, 0, PROGRESS_ANALYSIS, "identifying")
        flush_log()
        dt.print_hinter(" ")

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
    if run and run.applying then write_ledger(run.ledger) end
    end_job(job)
    busy = false
    set_idle_label()
    if not okr then notify_error(_("Assisted Tagging: couldn't run. ") .. tostring(err)) end
    cleanup_tmp()
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
    dt.print_hinter(" ")
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
        local _, pick_of = with_paired_jpegs(images)
        local ledger = M.ledger_parse(C.read_file_or_tmp(LEDGER_PATH), LIB_KEY)
        local colour_base = M.named_rules(rules, settings).diag.colour
        for _, img in ipairs(images) do
            -- the entry comes from the selected image's tags; the crop from its paired JPEG
            local src = pick_of[img.id]
            local eid = entry_id or M.entry_for_tags(tags_of(img), entries, entry_order)
            if not eid then
                -- tagged only to team level: identify.py saves it as a team reference when
                -- rules.partial_references is on and the shot is solo
                local prefixes = sorted_names(M.hint_prefixes(tags_of(img), nil, entries))
                if #prefixes == 1 then eid = prefixes[1] end
            end
            if eid then
                if not sent[src.id] then
                    sent[src.id] = true
                    rows[#rows + 1] = { src.id, src.path .. "/" .. src.filename, eid,
                        M.hand_colour(tags_of(img), ledger[img.id], colour_base) or "" }
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
        local results = run_reference_job(state, rows, { "--add-reference" }, "adding references")
        if not results then return end
        local added, whole, failed, no_face, multi, team_rule = 0, 0, 0, 0, 0, 0
        local parsed, notes = M.parse_reference_results(results)
        for _, p in ipairs(parsed) do
            if p[2] == "added" then added = added + 1
            elseif p[2] == "team_refs_off" or p[2] == "team_not_solo" then team_rule = team_rule + 1
            elseif p[2] == "no_face" then no_face = no_face + 1
            elseif p[2] == "multiple_faces" then multi = multi + 1
            elseif p[2] == "no_vehicle_whole_frame" then added = added + 1; whole = whole + 1
            else failed = failed + 1 end
        end
        local extra = M.colour_note_extras(notes)
        if whole > 0 then extra[#extra + 1] = string.format("%d used the whole frame", whole) end
        if no_face > 0 then extra[#extra + 1] = string.format("%d had no face", no_face) end
        if multi > 0 then extra[#extra + 1] = string.format("%d had several faces, so can't name one person", multi) end
        if team_rule > 0 then extra[#extra + 1] = string.format("%d tagged only to team level, not saved (the team-reference rule is off or the shot isn't solo)", team_rule) end
        if n_skipped > 0 then extra[#extra + 1] = string.format("%d skipped", n_skipped) end
        if failed > 0 then extra[#extra + 1] = string.format("%d failed, see log", failed) end
        say(string.format("Assisted Tagging: added %d references to %s%s. Each sample's crop is in %s/refs.",
            added, entry_id or "their entries", #extra > 0 and (" (" .. table.concat(extra, ", ") .. ")") or "",
            current_collection()))
    end)
    finish_reference_job(state, okr, err, "couldn't add references.")
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
        local colour_base = M.named_rules(rules, settings).diag.colour
        for _, img in ipairs((with_paired_jpegs(images))) do
            rows[#rows + 1] = { img.id, img.path .. "/" .. img.filename, "",
                M.hand_colour(tags_of(img), ledger[img.id], colour_base) or "" }
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
        say(string.format("Assisted Tagging: saved vehicles from %d images as references%s. Crops are in %s/refs.",
            counts.added, #extra > 0 and (" (" .. table.concat(extra, ", ") .. ")") or "", current_collection()))
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
            .. "the collection and use Edit entries.json instead."), name))
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
    if not file_exists(path) then
        dt.print(string.format(_("Assisted Tagging: %s doesn't exist."), path))
        return
    end
    if IS_WINDOWS then
        os.execute(string.format('start "" "%s"', path:gsub("/", "\\")))
    elseif dt.configuration.running_os == "macos" then
        os.execute("open " .. shell_quote(path))
    else
        os.execute("xdg-open " .. shell_quote(path) .. " >/dev/null 2>&1 &")
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

local step_label, make_section = C.step_label, C.make_section

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
    function store.read(name)
        if not file_exists(dir(name) .. "/entries.json") then return nil end
        return C.read_file_or_tmp(store.path(name)) or "{}"
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

    local function changed()
        if preset_ctl then preset_ctl.check_dirty() end
    end
    local panel_ready = false -- the first collection load waits for darktable to open (see the end)

    local new_collection_name = dt.new_widget("entry") {
        tooltip = _("Name for the new collection's folder, e.g. \"F1 2026\""),
        placeholder = _("collection name"),
        text = "",
    }
    local new_collection_button = dt.new_widget("button") {
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
    example_combo = dt.new_widget("combobox") {
        label = _("example"),
        tooltip = _("A collection template shipped in the repo's examples folder, with placeholder entries and no references"),
        _("(no examples)"),
    }
    local example_view_button = dt.new_widget("button") {
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
    local example_create_button = dt.new_widget("button") {
        label = _("From example"),
        tooltip = _("Copy the selected example's entries.json into a new collection with no images needed; "
            .. "edit it afterward with your own entries"),
        clicked_callback = function()
            M.create_collection_from_example(selected_example(), new_collection_name.text)
        end,
    }

    local reload_button = dt.new_widget("button") {
        label = _("Reload"),
        tooltip = _("Reread the collections folder (the preset list) and the selected collection's entries.json and settings.json. Unsaved panel changes are replaced by settings.json."),
        clicked_callback = function() reload_lists(false, false, true) end,
    }
    local plan_button = dt.new_widget("button") {
        label = _("Show tag plan"),
        tooltip = _("Write tag-plan.txt in the collection's folder: the exact tags every entry and outcome (team only, unidentified, diagnostics) writes, from its entries.json"),
        clicked_callback = function() reload_lists(false, true) end,
    }
    local entries_editor = dt.new_widget("text_view") {
        editable = true,
        text = "",
        visible = false,
    }
    local save_entries_button, cancel_entries_button
    local function close_entries_editor()
        entries_editor.visible = false
        save_entries_button.visible = false
        cancel_entries_button.visible = false
    end
    save_entries_button = dt.new_widget("button") {
        label = _("Save entries.json"),
        tooltip = _("Write the edited text back to entries.json and reload"),
        visible = false,
        clicked_callback = function()
            local path = entries_json_path()
            local before = C.read_file_or_tmp(path)
            if not write_file_atomic(path, entries_editor.text) then
                notify_error(string.format(_("Assisted Tagging: couldn't write %s (check the collections folder preference)."), path))
                return
            end
            -- --list reads the new file; if it doesn't load, the old file goes back and the
            -- editor stays open with the text to fix
            if reload_lists(false) then
                close_entries_editor()
            elseif before then
                -- no dt.print here: it would replace reload_lists' message saying what's wrong
                write_file_atomic(path, before)
                log("entries.json edit didn't load; the previous file was put back and the editor left open")
            end
        end,
    }
    cancel_entries_button = dt.new_widget("button") {
        label = _("Cancel edit"),
        tooltip = _("Discard changes and close the editor"),
        visible = false,
        clicked_callback = close_entries_editor,
    }
    local edit_button = dt.new_widget("button") {
        label = _("Edit entries.json"),
        tooltip = _("Edit the selected collection's entries.json in place below, then click Save entries.json"),
        clicked_callback = function()
            local path = entries_json_path()
            local text = C.read_file_or_tmp(path)
            if not text then
                notify_error(string.format(_("Assisted Tagging: couldn't read %s."), path))
                return
            end
            entries_editor.text = text
            entries_editor.visible = true
            save_entries_button.visible = true
            cancel_entries_button.visible = true
        end,
    }
    local start_list_file = dt.new_widget("file_chooser_button") {
        title = _("Start list CSV"),
        value = "",
        is_directory = false,
    }
    local start_list_columns = dt.new_widget("entry") {
        placeholder = _("columns: number=No.; driver=Driver (blank = usual header names)"),
        text = "",
        tooltip = _("Which CSV header holds each role, as role=header pairs separated by ;. Roles: number, driver, co-driver, team, class. Blank finds them by their usual names; only number is required."),
    }
    local start_list_text = dt.new_widget("text_view") {
        editable = true,
        text = "",
        tooltip = _("Or paste an entry list here, one entry per line, number first, e.g. 12 Smith / Jones. Pasted text is used instead of the chosen file."),
    }
    local import_start_list_button = dt.new_widget("button") {
        label = _("Import start list"),
        tooltip = _("Add the CSV's or the pasted entries to the selected collection's entries.json. Numbers already listed are kept and reported; the previous file is saved as entries.json.bak."),
        clicked_callback = function()
            if busy or not orphan_gone() then
                dt.print(_("Assisted Tagging: busy, try again when the current run finishes."))
                return
            end
            local script = identify_script()
            local argv = { plugin_root(script) .. "/python/import_start_list.py", collections_root() .. "/" .. current_collection() }
            local pasted = start_list_text.text or ""
            if pasted:match("%S") then
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
                local cols = start_list_columns.text or ""
                if cols:match("%S") then
                    argv[#argv + 1] = "--columns"
                    argv[#argv + 1] = cols
                end
            else
                dt.print(_("Assisted Tagging: choose a start list CSV or paste the entries first."))
                return
            end
            local cmd = command_line(python_bin(script), argv) .. " 2>&1"
            -- cmd.exe strips the outer quotes of a quoted command line, so the whole thing gets one more pair
            if IS_WINDOWS then cmd = '"' .. cmd .. '"' end
            log("import start list: " .. cmd)
            local p = io.popen(cmd)
            if not p then
                notify_error(_("Assisted Tagging: couldn't start Python for the start list import."))
                return
            end
            local out = (p:read("a") or ""):gsub("%s+$", "")
            local ok = p:close()
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
    identify_button = dt.new_widget("button") {
        label = _("Identify selection"),
        tooltip = _("Identify the vehicles in the selected images and tag them with their entries' tags"),
        clicked_callback = function() start_identify(true) end,
    }
    replace_manual_check = dt.new_widget("check_button") {
        label = _("Replace manual tags"),
        tooltip = _("Normally tags you applied by hand are never removed, and images already carrying all of one entry's tags are skipped. Tick this to let the next run replace them. It clears itself after the run."),
        value = false,
    }
    verify_button = dt.new_widget("button") {
        label = _("Verify selection"),
        tooltip = _("Identify the selected images, fully tagged ones included, and report where the result differs from your tags (boxes.json and report.md). No tags are changed."),
        clicked_callback = function() start_identify(false, true) end,
    }
    entry_combo = dt.new_widget("combobox") {
        label = _("entry"),
        tooltip = _("The entry Add as reference saves the selected images under"),
        _("(no entries)"),
    }
    local add_button = dt.new_widget("button") {
        label = _("Add as reference"),
        tooltip = _("Save the largest vehicle in each selected image as a reference sample of the entry above"),
        clicked_callback = function()
            local eid = selected_entry_id()
            if not eid then
                dt.print(_("Assisted Tagging: pick an entry first. If the list is empty, add entries to the collection's entries.json and click Reload."))
                return
            end
            M.add_references(dt.gui.action_images, eid)
        end,
    }
    local add_tagged_button = dt.new_widget("button") {
        label = _("Add tagged images"),
        tooltip = _("For each selected image that already carries all of one entry's tags, save it as a reference of that entry"),
        clicked_callback = function() M.add_references(dt.gui.action_images, nil) end,
    }
    local promote_button = dt.new_widget("button") {
        label = _("Add from last run"),
        tooltip = _("Save each vehicle the last Identify run was sure of (number read, or a clear livery match) as a reference of the entry it found. Works for pack shots too: only that car's crop is saved."),
        clicked_callback = function() M.promote_references(dt.gui.action_images) end,
    }
    local audit_button = dt.new_widget("button") {
        label = _("Audit references"),
        tooltip = _("Refresh the collection's reference index from refs/, then write ref-audit.txt in the collection folder listing refs that look wrongly filed. Nothing is moved or deleted."),
        clicked_callback = function() M.audit_references() end,
    }

    -- Settings: everything below is part of the collection's preset (settings.json).
    local checks, check_order = {}, {}
    local function check(key, label, tooltip)
        local c = dt.new_widget("check_button") {
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
    local run_tag_check = check("run_tag", _("Tag each run"),
        _("Add a timestamp tag (Assisted Tagging|Run|YYYY-MM-DD HH:MM) to every image a run writes, so the latest run's photos can be filtered apart from earlier ones. Stamps accumulate; remove old ones in darktable's tag manager.\nDefault: off. Turn on when re-running a shoot and you want to review only what changed."))
    local suggest_crops_check = check("suggest_crops", _("Audit: suggest re-crops"),
        _("Also write re-cut copies of wide references (one car found) into ref-audit-crops in the collection folder, for you to review. Nothing in refs/ is changed. The first audit with this ticked is slow (about 8 minutes for 2000 refs); later ones are fast.\nDefault: off. Turn on when the audit flags wide refs you want re-cut."))
    local quarantine_check = check("quarantine", _("Audit: quarantine poor refs"),
        _("After the report is written, move the refs flagged by 2+ checks out of refs/ into refs-quarantine in the collection folder (moved.txt lists each). Nothing is deleted: copy a file back into refs/<entry>/ to undo it.\nDefault: off. Turn on once you trust the audit's flags for this collection."))
    local colour_tags_check = check("colour_tags", _("colour tags"),
        _("Read each car's paintwork colour, write it as a Colour tag and use an entry's colour to break ties and flag number reads that disagree; turning it on re-reads every photo once.\nDefault: off."))
    local partial_references_check = check("partial_references", _("partial references"),
        _("Add tagged images also accepts a solo shot tagged only to team level and saves it as a team reference; a clear team lead with no clear driver then gives a team result.\nDefault: off."))
    -- Per tag switch: its check button and the tag name it writes (tag_<key>_name).
    local tag_rows, name_entries = {}, {}
    for _i, t in ipairs(TAG_TOGGLES) do
        local c = check("tag_" .. t.key, t.label, tag_tooltip(t, M.named_rules(rules, settings)))
        tag_checks[t.key] = c
        local name_key = "tag_" .. t.key .. "_name"
        local default
        for _j, f in ipairs(M.PRESET_SCHEMA) do
            if f.key == name_key then default = f.default end
        end
        local e = dt.new_widget("entry") {
            placeholder = default,
            tooltip = string.format(_("The tag %s writes. Blank = %s."), t.label, default),
            text = "",
        }
        name_entries[#name_entries + 1] = { key = name_key, entry = e, default = default }
        tag_rows[#tag_rows + 1] = dt.new_widget("box") { orientation = "vertical", c, e }
    end

    local support_keys
    for _i, f in ipairs(M.PRESET_SCHEMA) do
        if f.key == "group_support" then support_keys = f.choices end
    end
    local shown_support = "native" -- last shown or picked: the combo's callback acts only on a change
    local group_support_combo = dt.new_widget("combobox") {
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
    local group_node_entry = dt.new_widget("entry") {
        placeholder = _("Grouping tag node (blank = newest run)"),
        tooltip = _("Grouping tags only: the tag node whose children are the groups, e.g. Assisted Grouping|2026-01-01 12:00:00|Group. Blank uses the newest Assisted Grouping run on the selected photos.\nDefault: blank. Set it when the photos carry more than one grouping run."),
        text = "",
    }
    local embedder_entry = dt.new_widget("entry") {
        placeholder = _("embedder model file (blank = bundled)"),
        tooltip = _("File name in the plugin's models/ folder used to compare liveries, e.g. dinov2_base.onnx. Changing it re-embeds every reference on the next run.\nDefault: blank (dinov2_small.onnx). Change it to try a larger model when liveries are confused."),
        text = "",
    }
    local ocr_rec_entry = dt.new_widget("entry") {
        placeholder = _("number reader model file (blank = bundled)"),
        tooltip = _("File name in the plugin's models/ folder used to read race numbers, e.g. en_PP-OCRv5_mobile_rec.onnx. A PaddleOCR model needs its inference.yml beside it, renamed to the model's name with .yml. Changing it re-reads every photo on the next run.\nDefault: blank (en_PP-OCRv5_mobile_rec.onnx, or text_recognition_CRNN_EN_2021sep.onnx when the v5 files are missing). Type the CRNN name to go back to the older reader."),
        text = "",
    }
    local tolerance_entry = dt.new_widget("entry") {
        placeholder = _("neighbour tolerance"),
        tooltip = _("The most places apart in the sorted number list a neighbouring car can be and still support a doubtful read. The collection's order_weight sets how much of it is used: a neighbour up to order_weight × (tolerance + 1) places away counts. A whole number, 0 or more. Only used when order_weight is above 0.\nDefault: 5. Lower it when cars pass in strict number order; raise it when the order is loose."),
        text = "",
    }
    local order_weight_entry = dt.new_widget("entry") {
        placeholder = _("order weight"),
        tooltip = _("How far the cars pass in number order, from 0 (random: the neighbour aid is off) to 1 (strictly in order); 0.5 is loose order.\nDefault: 0. Set 0.5 for a rally or club event shot roughly in number order."),
        text = "",
    }
    local min_read_entry = dt.new_widget("entry") {
        placeholder = _("min read"),
        tooltip = _("How sure a number read must be to count, from 0 to 1: raise it if plates or signs get read as numbers, lower it if clear numbers are missed.\nDefault: 0.85."),
        text = "",
    }
    local colour_weight_entry = dt.new_widget("entry") {
        placeholder = _("colour weight"),
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
    -- Set in the schema and settings.json only, never on the panel.
    local HAND_EDIT_KEYS = { "min_sim", "margin", "min_face_px", "burst_livery_pooling", "blur_references" }

    local function trim(s) return (s or ""):match("^%s*(.-)%s*$") end

    local shown = M.preset_defaults(M.PRESET_SCHEMA) -- the values show_panel last filled in
    local warned = {} -- key → the entry text last logged as invalid, so a check doesn't repeat it

    -- An entry's value; blank or invalid keeps the shown value (logged once per text).
    local function entry_value(key, text, blank_default)
        local value = M.parse_setting(key, text)
        if value ~= nil then
            warned[key] = nil
            return value
        end
        if blank_default ~= nil and trim(text) == "" then return blank_default end
        if warned[key] ~= text then
            warned[key] = text
            log(string.format("panel: %s invalid, keeping %s", key, tostring(shown[key])))
        end
        return shown[key]
    end

    read_panel = function()
        local s = {
            group_support = support_keys[group_support_combo.selected] or shown_support,
            group_node = trim(group_node_entry.text),
            embedder_file = trim(embedder_entry.text),
            ocr_rec_file = trim(ocr_rec_entry.text),
        }
        for _i, n in ipairs(number_entries) do s[n.key] = entry_value(n.key, n.entry.text) end
        for _i, n in ipairs(name_entries) do
            s[n.key] = entry_value(n.key, n.entry.text, n.default)
        end
        for _i, key in ipairs(HAND_EDIT_KEYS) do s[key] = shown[key] end
        for _i, key in ipairs(check_order) do s[key] = checks[key].value and true or false end
        return s
    end

    local function show_panel(s)
        shown, warned = s, {}
        shown_support = s.group_support
        for i, key in ipairs(support_keys) do
            if key == s.group_support and group_support_combo.selected ~= i then group_support_combo.selected = i end
        end
        group_node_entry.text = s.group_node
        embedder_entry.text = s.embedder_file
        ocr_rec_entry.text = s.ocr_rec_file
        for _i, n in ipairs(number_entries) do n.entry.text = tostring(s[n.key]) end
        for _i, n in ipairs(name_entries) do n.entry.text = s[n.key] end
        for _i, key in ipairs(check_order) do checks[key].value = s[key] end
    end

    -- template: only the new-collection controls; a collection: everything else
    local template_box = dt.new_widget("box") {
        orientation = "vertical",
        dt.new_widget("section_label") { label = _("new collection") },
        new_collection_name,
        new_collection_button,
        example_combo,
        example_view_button,
        example_create_button,
    }
    local collection_box = dt.new_widget("box") {
        orientation = "vertical",
        make_section(1, _("collection"),
            { plan_button, edit_button, entries_editor, save_entries_button, cancel_entries_button,
              dt.new_widget("label") { label = _("start list"), halign = "start" },
              start_list_file, start_list_columns, start_list_text, import_start_list_button }),
        make_section(2, _("bursts"), {
            group_support_combo,
            dt.new_widget("label") { label = _("grouping tag node"), halign = "start" },
            group_node_entry,
        }),
        make_section(3, _("matching"), {
            use_hints_check,
            dt.new_widget("label") { label = _("embedder model file"), halign = "start" },
            embedder_entry,
            dt.new_widget("label") { label = _("number reader model file"), halign = "start" },
            ocr_rec_entry,
            dt.new_widget("label") { label = _("neighbour tolerance"), halign = "start" },
            tolerance_entry,
            dt.new_widget("label") { label = _("order weight"), halign = "start" },
            order_weight_entry,
            dt.new_widget("label") { label = _("min read"), halign = "start" },
            min_read_entry,
            dt.new_widget("label") { label = _("colour weight"), halign = "start" },
            colour_weight_entry,
            colour_tags_check,
            partial_references_check,
        }),
        make_section(4, _("tags written"), tag_rows),
        step_label(5, _("run")),
        replace_manual_check,
        run_tag_check,
        verify_button,
        identify_button,
        make_section(nil, _("references"), { entry_combo, add_button, add_tagged_button, promote_button,
            suggest_crops_check, quarantine_check, audit_button }),
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
            close_entries_editor()
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

    local panel_box = dt.new_widget("box") {
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
            start_identify(false)
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
        install_panel()
        restart()
    else
        if not M.event_registered then
            dt.register_event("assisted_tagging", "view-changed", function(event, old_view, new_view)
                if new_view.name == "lighttable" or new_view.id == "lighttable" then
                    install_panel()
                    restart()
                end
            end)
            M.event_registered = true
        end
    end
end

M.fmt_eta = fmt_eta -- test hook (test_assisted_tagging.lua)

return M
