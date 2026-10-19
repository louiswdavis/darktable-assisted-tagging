--[[
    assisted_tagging.lua — Assisted Tagging for darktable

    Lighttable panel that shells out to identify.py to recognise the
    motorsport vehicles in a selection (race number, then livery against a
    collection's reference samples, then burst consensus) and tags each
    image with its entries' tags.
]]

local M = {}

M.BURST_GAP_SECONDS = 2
M.cancel_requested = false
M.module_installed = false
M.event_registered = false

-- Default diagnostic tag per outcome; a collection's rules can rename or drop each one.
M.DIAG_TAGS = {
    number = "Assisted Tagging|Identification|By number",
    livery = "Assisted Tagging|Identification|By livery",
    burst = "Assisted Tagging|Identification|By burst",
    team = "Assisted Tagging|Identification|Team only",
    none = "Assisted Tagging|Identification|Unidentified",
    -- Suffixed with the literal digits read, e.g. "...|Number seen|115"; independent of
    -- the outcome tags above, added whenever OCR read a number that didn't resolve.
    number_seen = "Assisted Tagging|Identification|Number seen",
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
    if not y then return nil end
    return os.time({
        year = tonumber(y), month = tonumber(mo), day = tonumber(d),
        hour = tonumber(h), min = tonumber(mi), sec = tonumber(se),
        isdst = false, -- constant offset, so a DST change can't split a burst
    })
end

function M.cluster_by_time(items, gap_seconds)
    gap_seconds = gap_seconds or M.BURST_GAP_SECONDS
    local timed, untimed = {}, {}
    for _, item in ipairs(items) do
        if item.epoch then table.insert(timed, item) else table.insert(untimed, item) end
    end
    table.sort(timed, function(a, b) return a.epoch < b.epoch end)

    local burst_of = {}
    local next_burst = 0
    local prev_epoch = nil
    for _, item in ipairs(timed) do
        if prev_epoch == nil or (item.epoch - prev_epoch) > gap_seconds then
            next_burst = next_burst + 1
        end
        burst_of[item.id] = next_burst
        prev_epoch = item.epoch
    end
    for _, item in ipairs(untimed) do
        next_burst = next_burst + 1
        burst_of[item.id] = next_burst
    end
    return burst_of
end

function M.csv_line(fields)
    local out = {}
    for i, v in ipairs(fields) do
        out[i] = '"' .. tostring(v):gsub('"', '""') .. '"'
    end
    return table.concat(out, ",")
end

function M.parse_csv_line(line, n)
    local parts = {}
    for part in (line .. ","):gmatch("([^,]*),") do
        table.insert(parts, part)
    end
    if #parts ~= n then return nil end
    return parts
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
    return { team_only = "shared tags", unidentified = {}, diag = diag }
end

-- identify.py's rules.csv (key,value lines from entries.json's "rules") → rules.
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
        elseif e and (r.method == "number" or r.method == "livery" or r.method == "burst" or r.method == "pooled" or r.method == "face") then
            for _, t in ipairs(e.tags) do wanted[t] = true end
            note(r.method)
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

-- have: an image's tag names (name → true). Returns the names to attach and to
-- detach, sorted. Only owned tags, or tags starting with an owned prefix (the dynamic
-- "...Number seen|<digits>" diagnostic, one tag per distinct digit string), are detached.
-- `protected` (name → true): tags the user applied by hand; never detached.
function M.tag_changes(have, wanted, owned, owned_prefixes, protected)
    protected = protected or {}
    local attach, detach = {}, {}
    for name in pairs(wanted) do
        if not have[name] then attach[#attach + 1] = name end
    end
    local function is_owned(name)
        if owned[name] then return true end
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

-- Ledger: the tags the plugin attached, per image id, persisted as `id,tag` lines. A
-- tag on an image that's not in its ledger was applied by the user.
function M.ledger_parse(text)
    local ledger = {}
    for line in (text or ""):gmatch("[^\r\n]+") do
        local p = M.parse_csv_line(line, 2)
        local id = p and tonumber(p[1])
        if id and p[2] ~= "" then
            ledger[id] = ledger[id] or {}
            ledger[id][p[2]] = true
        end
    end
    return ledger
end

function M.ledger_format(ledger)
    local ids = {}
    for id in pairs(ledger) do ids[#ids + 1] = id end
    table.sort(ids)
    local out = {}
    for _, id in ipairs(ids) do
        local names = {}
        for name in pairs(ledger[id]) do names[#names + 1] = name end
        table.sort(names)
        -- unquoted: parse_csv_line doesn't unquote, and tag names never hold a comma
        for _, name in ipairs(names) do out[#out + 1] = id .. "," .. name end
    end
    return #out > 0 and table.concat(out, "\n") .. "\n" or ""
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
        local p = M.parse_csv_line(line, 8)
        local id = p and tonumber(p[1])
        if id and p[3] == "error" then
            errored[id] = true
        elseif id and p[3] == "skipped" then
            skipped[id] = true
        elseif id then
            rows_of[id] = rows_of[id] or {}
            table.insert(rows_of[id], { box = tonumber(p[2]), method = p[3], entry_id = p[4],
                                         alt_entry_id = p[5], unmatched_number = p[7], shot = p[8] })
        end
    end
    return rows_of, errored, skipped
end

-- UTF-8 → UTF-16LE (no BOM), for the .vbs launcher: wscript reads a script as
-- ANSI unless it's UTF-16, which garbles a non-ASCII tmp path.
function M.utf16le(s)
    local out = {}
    for _, c in utf8.codes(s) do
        if c >= 0x10000 then
            c = c - 0x10000
            local hi, lo = 0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF)
            out[#out + 1] = string.char(hi & 0xFF, hi >> 8, lo & 0xFF, lo >> 8)
        else
            out[#out + 1] = string.char(c & 0xFF, c >> 8)
        end
    end
    return table.concat(out)
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

-- A bare entries.json list (default rules apply). Entries already carry only
-- ids/tags/numbers that passed sanitize_id/hierarchical_tags/the digit check, so this
-- never needs to reject input.
function M.entries_json(entries)
    local parts = {}
    for _, e in ipairs(entries) do
        local tag_parts = {}
        for _, t in ipairs(e.tags) do tag_parts[#tag_parts + 1] = json_string(t) end
        parts[#parts + 1] = string.format('  { "id": %s, "number": %s, "team": %s, "tags": [%s] }',
            json_string(e.id), json_string(e.number or ""), json_string(e.team or ""), table.concat(tag_parts, ", "))
    end
    return "[\n" .. table.concat(parts, ",\n") .. "\n]\n"
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

local IS_WINDOWS = dt.configuration.running_os == "windows"
local THIS_DIR = (debug.getinfo(1, "S").source:sub(2):match("^(.*)[/\\]")) or "."

local TMP_DIR = dt.configuration.tmp_dir
local MANIFEST_PATH = TMP_DIR .. "/dt_assisted_tagging_manifest.csv"
local RESULTS_PATH = TMP_DIR .. "/dt_assisted_tagging_results.csv"
local ENTRIES_PATH = TMP_DIR .. "/dt_assisted_tagging_entries.csv"
local RULES_PATH = TMP_DIR .. "/dt_assisted_tagging_rules.csv"
local COLLECTIONS_PATH = TMP_DIR .. "/dt_assisted_tagging_collections.csv"
local PROGRESS_PATH = TMP_DIR .. "/dt_assisted_tagging_progress.txt"
local CANCEL_PATH = PROGRESS_PATH .. ".cancel"
local DONE_PATH = TMP_DIR .. "/dt_assisted_tagging_done.txt"
-- The run log: this plugin's lines plus identify.py's stderr. Kept in the
-- config dir, which outlives tmp_dir; the run before it is kept as .prev.log.
local LOG_PATH = dt.configuration.config_dir .. "/assisted_tagging.log"
local PREV_LOG_PATH = dt.configuration.config_dir .. "/assisted_tagging.prev.log"
local CACHE_PATH = dt.configuration.config_dir .. "/assisted_tagging/cache.sqlite"
local LEDGER_PATH = dt.configuration.config_dir .. "/assisted_tagging/ledger.csv"
local LAST_RUN_DIR = dt.configuration.config_dir .. "/assisted_tagging/last-run"
local RUNS_DIR = dt.configuration.config_dir .. "/assisted_tagging/runs"
local DEFAULT_COLLECTIONS_ROOT = dt.configuration.config_dir .. "/assisted_tagging/collections"

local MODEL_FILES = {
    detector_model = "object_detection_yolox_2022nov.onnx",
    ocr_detection_model = "text_detection_en_ppocrv3_2023may.onnx",
    ocr_recognition_model = "text_recognition_CRNN_EN_2021sep.onnx",
    embedder_model = "dinov2_small.onnx",
    face_detector_model = "face_detection_yunet_2023mar.onnx",
    face_recognizer_model = "face_recognition_sface_2021dec.onnx",
}

if dt.gui then
    dt.preferences.register("assisted_tagging", "python_bin", "file",
        "Assisted Tagging: Python interpreter",
        "Python executable with the packages in python/requirements.txt installed (e.g. .venv\\Scripts\\python.exe). Empty = auto-detect the repo's .venv",
        "")
    dt.preferences.register("assisted_tagging", "plugin_folder", "directory",
        "Assisted Tagging: plugin folder",
        "The darktable-assisted-tagging folder (holds python/, models/, examples/ and .venv). Empty = auto-detect",
        "")
    dt.preferences.register("assisted_tagging", "collections_root", "directory",
        "Assisted Tagging: collections folder",
        "Folder with one folder per collection (entries.json + refs). Empty = assisted_tagging/collections in darktable's config folder",
        "")
    dt.preferences.register("assisted_tagging", "embedder_file", "string",
        "Assisted Tagging: livery embedder model",
        "File name in the plugin's models folder used to compare liveries (e.g. dinov2_base.onnx). Empty = dinov2_small.onnx. Changing it re-embeds every reference on the next run",
        "")
    dt.preferences.register("assisted_tagging", "diagnostic_tags", "bool",
        "Assisted Tagging: diagnostic tags",
        "Tag how each image was identified (under Assisted Tagging|Identification: By number, By livery, By burst, Team only, Unidentified) for filtering and spot-checks; a collection's rules can rename them. Off removes them on the next run",
        true)
    dt.preferences.register("assisted_tagging", "burst_gap_seconds", "integer",
        "Assisted Tagging: burst gap (seconds)",
        "Photos taken closer together than this are one burst, and share an identification when the rest of the burst agrees",
        2, 1, 60)
end

local function file_exists(name)
    local f = io.open(name, "r")
    if f ~= nil then f:close(); return true else return false end
end

local function first_existing(paths)
    for _, p in ipairs(paths) do
        if p and p ~= "" and file_exists(p) then
            return p
        end
    end
    return nil
end

local function read_file(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local t = f:read("*a")
    f:close()
    return t
end

local function plugin_folder_pref()
    local folder = (dt.preferences.read("assisted_tagging", "plugin_folder", "directory") or ""):gsub("[/\\]+$", "")
    return folder
end

-- The script is found from the plugin folder preference alone when it's set; a
-- wrong folder is an error rather than a quiet switch to some other copy.
local function identify_script()
    local folder = plugin_folder_pref()
    if folder ~= "" then
        local script = folder .. "/python/identify.py"
        if not file_exists(script) then
            error(string.format("Assisted Tagging: the plugin folder preference (%s) has no python/identify.py. Point it at the darktable-assisted-tagging folder, or clear it to auto-detect.", folder), 0)
        end
        return script
    end
    local home = os.getenv("USERPROFILE") or os.getenv("HOME") or ""
    local found = first_existing({
        THIS_DIR .. "/identify.py",
        THIS_DIR .. "/python/identify.py",
        THIS_DIR .. "/../python/identify.py",
        THIS_DIR .. "/../../python/identify.py",
        home .. "/Pictures/DarkTable/Settings/Plugins/darktable-assisted-tagging/python/identify.py",
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
    local pref = dt.preferences.read("assisted_tagging", "python_bin", "file")
    if pref and pref ~= "" then return pref end

    local home = os.getenv("USERPROFILE") or os.getenv("HOME") or ""
    local root = plugin_root(script)
    local found = first_existing({
        root .. "/.venv/Scripts/python.exe",
        root .. "/.venv/bin/python",
        THIS_DIR .. "/../.venv/Scripts/python.exe",
        THIS_DIR .. "/../.venv/bin/python",
        home .. "/Pictures/DarkTable/Settings/Plugins/darktable-assisted-tagging/.venv/Scripts/python.exe",
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
local function model_path(name, script)
    local file = MODEL_FILES[name]
    if name == "embedder_model" then
        local chosen = dt.preferences.read("assisted_tagging", "embedder_file", "string") or ""
        if chosen ~= "" then file = chosen end
    end
    return plugin_root(script) .. "/models/" .. file
end

local function collections_root()
    local pref = dt.preferences.read("assisted_tagging", "collections_root", "directory") or ""
    return pref ~= "" and pref or DEFAULT_COLLECTIONS_ROOT
end

local function current_collection()
    return dt.preferences.read("assisted_tagging", "last_collection", "string") or ""
end

local function entries_json_path()
    return collections_root() .. "/" .. current_collection() .. "/entries.json"
end

-- The repo's shipped example collections (entries.json templates, no refs), a
-- sibling of python/. Missing if the repo was trimmed down to just the plugin.
local function examples_root()
    return plugin_root(plugin_folder_pref() == "" and identify_script() or nil) .. "/examples"
end

local function shell_quote(s)
    if IS_WINDOWS then return '"' .. s .. '"' end
    return "'" .. s:gsub("'", "'\\''") .. "'"
end

-- The exit code goes to a temp file renamed onto done_path, so done_path
-- never exists without its code in it. Returns false when it couldn't launch.
local function run_async_command(cmd, done_path)
    local done_tmp = done_path .. ".tmp"
    if IS_WINDOWS then
        local bat = TMP_DIR .. "/dt_assisted_tagging_run.bat"
        local vbs = TMP_DIR .. "/dt_assisted_tagging_run.vbs"
        local f = io.open(bat, "w")
        if not f then return false end
        local win_done, win_tmp = done_path:gsub("/", "\\"), done_tmp:gsub("/", "\\")
        f:write("@echo off\r\nchcp 65001>nul\r\n")
        f:write(cmd, " < NUL\r\n")
        -- redirect first: "echo 0> f" would redirect handle 0 and leave f empty
        f:write('> "', win_tmp, '" echo %ERRORLEVEL%\r\n')
        f:write('move /y "', win_tmp, '" "', win_done, '" >nul\r\n')
        f:close()
        local f_vbs = io.open(vbs, "wb")
        if not f_vbs then return false end
        f_vbs:write("\xFF\xFE", M.utf16le('Set WshShell = CreateObject("WScript.Shell")\r\n'
            .. 'WScript.Quit WshShell.Run(Chr(34) & "' .. bat:gsub("/", "\\") .. '" & Chr(34), 0, False)\r\n'))
        f_vbs:close()
        os.execute('wscript.exe "' .. vbs:gsub("/", "\\") .. '"')
    else
        os.execute('( ' .. cmd .. ' ; echo $? > ' .. shell_quote(done_tmp)
            .. ' ; mv -f ' .. shell_quote(done_tmp) .. ' ' .. shell_quote(done_path) .. ' ) >/dev/null 2>&1 &')
    end
    return true
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

local function log(msg)
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

-- One identify.py process at a time: runs share the tmp files and the .bat/.vbs launcher.
-- `orphan` is a cancelled or stalled process that hadn't exited when its run gave up
-- waiting; nothing starts until its done file appears.
local busy, orphan = false, false
-- A run that shows no progress for this long is given up on (it may still be loading
-- models or re-embedding references, so this is generous).
local STALL_SECONDS = 300
local verify_button, identify_button, collection_combo, entry_combo, example_combo = nil, nil, nil, nil, nil
local identify_cancellable = false -- the identify button currently reads "Cancel"
local replace_manual_check = nil
local entries, entry_order, rules = {}, {}, M.default_rules()

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
    orphan = true
    log("identify.py hasn't exited yet; the next run waits for it")
end

-- Runs identify.py with `args` (already shell-quoted) and blocks until it exits,
-- moving job.percent from `from` to `to` with its progress. Returns the exit
-- code, or nil plus "cancelled", "stalled" or "launch" (the last two already
-- reported to the user).
local function run_python(args, job, from, to, hint)
    local script = identify_script()
    pcall(os.remove, DONE_PATH)
    pcall(os.remove, PROGRESS_PATH)
    pcall(os.remove, CANCEL_PATH)
    local cmd = shell_quote(python_bin(script)) .. " -u " .. shell_quote(script) .. " " .. args
        .. " --progress " .. shell_quote(PROGRESS_PATH)
        .. " 2>> " .. shell_quote(LOG_PATH)
    log("running: " .. cmd)
    flush_log()
    if not run_async_command(cmd, DONE_PATH) then
        notify_error(string.format("Assisted Tagging: couldn't start identify.py: no write access to darktable's tmp folder (%s).", TMP_DIR))
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
            local code = tonumber((read_file(DONE_PATH) or ""):match("%d+"))
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
    end
    return string.format("Assisted Tagging: identify.py stopped with exit code %s. Details are in assisted_tagging.log in darktable's config folder.",
        tostring(code or "?"))
end

local function model_args(script)
    local args = " --detector " .. shell_quote(model_path("detector_model", script))
        .. " --ocr-det " .. shell_quote(model_path("ocr_detection_model", script))
        .. " --ocr-rec " .. shell_quote(model_path("ocr_recognition_model", script))
        .. " --embedder " .. shell_quote(model_path("embedder_model", script))
    -- face models are optional: only people collections need them, so a missing file is left unset
    for flag, name in pairs({ ["--face-detector"] = "face_detector_model", ["--face-recognizer"] = "face_recognizer_model" }) do
        local path = model_path(name, script)
        if file_exists(path) then args = args .. " " .. flag .. " " .. shell_quote(path) end
    end
    return args
end

local function collection_args()
    return " --collections-root " .. shell_quote(collections_root())
        .. " --collection " .. shell_quote(current_collection())
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
end

local function cleanup_tmp()
    -- An orphaned identify.py still needs its cancel flag, and cmd.exe is still
    -- reading its .bat, so leave those until it exits.
    if orphan then return end
    for _, p in ipairs({ MANIFEST_PATH, RESULTS_PATH, RESULTS_PATH .. ".tmp", DONE_PATH, PROGRESS_PATH, CANCEL_PATH }) do
        pcall(os.remove, p)
    end
    if IS_WINDOWS then
        pcall(os.remove, TMP_DIR .. "/dt_assisted_tagging_run.bat")
        pcall(os.remove, TMP_DIR .. "/dt_assisted_tagging_run.vbs")
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
local function reload_lists(quiet, show_plan)
    if busy or not orphan_gone() then
        if not quiet then dt.print(_("Assisted Tagging: busy, try again when the current run finishes.")) end
        return
    end
    busy = true
    local okr, err = pcall(function()
        for attempt = 1, 2 do
            pcall(os.remove, COLLECTIONS_PATH)
            pcall(os.remove, ENTRIES_PATH)
            pcall(os.remove, RULES_PATH)
            local code, why = run_python("- - --list" .. collection_args()
                .. " --collections-out " .. shell_quote(COLLECTIONS_PATH)
                .. " --entries-out " .. shell_quote(ENTRIES_PATH) .. " --rules-out " .. shell_quote(RULES_PATH), nil)
            flush_log()
            if code == nil and why ~= "cancelled" then return end -- already reported
            if code ~= 0 then
                notify_error(failure_message(code))
                return
            end
            local names = read_lines(COLLECTIONS_PATH)
            local current, sel = current_collection(), nil
            for i, n in ipairs(names) do if n == current then sel = i end end
            if not sel and names[1] and attempt == 1 then
                -- the stored collection is gone: switch to the first one and list its entries
                dt.preferences.write("assisted_tagging", "last_collection", "string", names[1])
            else
                load_entries_csv()
                fill_combo(collection_combo, #names > 0 and names or { _("(no collections)") }, sel or 1)
                refresh_entry_combo()
                if #names == 0 then
                    say(string.format("Assisted Tagging: no collections yet. Create a folder with an entries.json in %s (see the README), then click Reload.",
                        collections_root()))
                elseif show_plan then
                    say(string.format("Assisted Tagging: the tags each outcome writes in %s are listed in %s/%s/tag-plan.txt",
                        current_collection(), collections_root(), current_collection()))
                elseif not quiet then
                    say(string.format("Assisted Tagging: %d collections; %s has %d entries.", #names,
                        current_collection(), #entry_order))
                end
                return
            end
        end
    end)
    busy = false
    flush_log()
    if not okr then notify_error(_("Assisted Tagging: couldn't reload collections. ") .. tostring(err)) end
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

local function stop_job(job)
    M.cancel_requested = true
    request_cancel()
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

local WRITE_ROWS_FAILED = "couldn't write the image list to darktable's tmp folder (disk full or no write access?)"

-- A run's preconditions; prints why and returns false when it can't start.
local function can_start(images, needs_no_images)
    if busy then
        dt.print(_("Assisted Tagging: another job is still running. Wait for it to finish, or cancel it first."))
        return false
    end
    if not orphan_gone() then
        dt.print(_("Assisted Tagging: the last run is still stopping. Try again in a moment."))
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

-- Where a run leaves its per-vehicle records, for "Add confident vehicles from last run".
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

-- Groups the selection into duplicates (same file, identified once) and bursts, and reads the
-- ledger and the tags the user applied by hand. Returns the run's state and the manifest rows.
local function prepare_run(images, replace_manual)
    -- Duplicates (same file) are identified once; the tags go on every copy.
    local primaries, group_of, seen = {}, {}, {}
    for _, img in ipairs(images) do
        local key = img.path .. "/" .. img.filename
        local lead = seen[key]
        if lead then
            table.insert(group_of[lead.id], img)
        else
            seen[key] = img
            group_of[img.id] = { img }
            table.insert(primaries, img)
        end
    end

    local time_items, time_of = {}, {}
    for _, img in ipairs(primaries) do
        local epoch = M.exif_time_to_epoch(img.exif_datetime_taken)
        time_of[img.id] = epoch
        table.insert(time_items, { id = img.id, epoch = epoch })
    end
    local gap = dt.preferences.read("assisted_tagging", "burst_gap_seconds", "integer")
    local burst_of = M.cluster_by_time(time_items, (gap and gap >= 1) and gap or M.BURST_GAP_SECONDS)

    -- The ledger holds the tags this plugin attached. Entries no longer on the image are
    -- dropped, so a tag removed and re-applied by hand counts as the user's again.
    -- Protection and hints read the entries loaded at the last Reload or run, so Reload after
    -- editing entries.json.
    local ledger = M.ledger_parse(read_file(LEDGER_PATH))
    local protected_of, hints_of = {}, {}
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
        end
    end

    local rows = {}
    for _, img in ipairs(primaries) do
        rows[#rows + 1] = { img.id, img.path .. "/" .. img.filename, burst_of[img.id],
                            table.concat(sorted_names(protected_of[img.id]), ";"),
                            table.concat(sorted_names(hints_of[img.id]), ";"),
                            time_of[img.id] and tostring(time_of[img.id]) or "" }
    end
    return { primaries = primaries, group_of = group_of, protected_of = protected_of, ledger = ledger,
             applying = false }, rows
end

-- Writes the ledger of the tags this plugin attached.
local function write_ledger(ledger)
    local lf = io.open(LEDGER_PATH, "w")
    if lf then
        lf:write(M.ledger_format(ledger))
        lf:close()
    else
        log("couldn't write the tag ledger " .. LEDGER_PATH .. "; tags this run attached will count as yours next run")
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

    local owned = M.owned_tags(entries, rules)
    local owned_prefixes = (rules.diag.number_seen and rules.diag.number_seen ~= "")
        and { rules.diag.number_seen .. "|" } or {}
    local diag_on = dt.preferences.read("assisted_tagging", "diagnostic_tags", "bool")
    local tag_objs, writes, failed, first_error = {}, 0, 0, nil
    local n_tagged, n_unidentified, n_missing = 0, 0, 0
    local n_skipped, n_conflict = 0, 0
    local by_method = { number = 0, livery = 0, burst = 0, team = 0, pooled = 0, face = 0 }
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
            local wanted, diag, identified = M.wanted_tags(results, entries, rules)
            if identified then n_tagged = n_tagged + 1 else n_unidentified = n_unidentified + 1 end
            for _, r in ipairs(results) do
                if by_method[r.method] and entries[r.entry_id] then by_method[r.method] = by_method[r.method] + 1 end
                if r.method == "conflict" then n_conflict = n_conflict + 1 end
            end
            if diag_on then
                for name in pairs(diag) do wanted[name] = true end
            end
            for _, copy in ipairs(group_of[img.id]) do
                local attach, detach = M.tag_changes(tags_of(copy), wanted, owned, owned_prefixes,
                    protected_of[copy.id])
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
        if not job.valid then
            say(string.format("Assisted Tagging: stopped while writing tags; %d of %d images were updated. Run again to finish.",
                i, #primaries))
            return
        end
    end

    local parts = {}
    for _, m in ipairs({ { "number", "by number" }, { "livery", "by livery" }, { "burst", "by burst" },
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
    if not can_start(images) then return end
    busy = true
    M.cancel_requested = false
    identify_cancellable = true
    if identify_button then identify_button.label = _("Cancel") end
    start_log(verify_only and "verify started" or "identify started", #images)

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
        local code, why = run_python(shell_quote(MANIFEST_PATH) .. " " .. shell_quote(RESULTS_PATH)
            .. collection_args() .. model_args(script) .. (verify_only and " --verify" or "")
            .. " --cache " .. shell_quote(CACHE_PATH)
            .. " --entries-out " .. shell_quote(ENTRIES_PATH) .. " --rules-out " .. shell_quote(RULES_PATH)
            .. " --boxes-out " .. shell_quote(boxes_path())
            .. " --report-out " .. shell_quote(report_prefix())
            .. " --archive-dir " .. shell_quote(RUNS_DIR),
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
end

-- Writes the manifest and runs identify.py in a reference mode (`mode_args`). Sets state.job for
-- finish_reference_job. Returns results.csv's text, or nil once a cancel, stall or failure has been reported.
local function run_reference_job(state, rows, mode_args)
    pcall(os.remove, RESULTS_PATH)
    if not write_rows(MANIFEST_PATH, rows) then
        error(WRITE_ROWS_FAILED, 0)
    end
    state.job = dt.gui.create_job(_("Assisted Tagging: adding references"), true, stop_job)
    state.job.percent = 0.0
    local code, why = run_python(shell_quote(MANIFEST_PATH) .. " " .. shell_quote(RESULTS_PATH)
        .. mode_args .. collection_args() .. model_args(identify_script())
        .. " --entries-out " .. shell_quote(ENTRIES_PATH) .. " --rules-out " .. shell_quote(RULES_PATH),
        state.job, 0, 1, "adding references")
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

local function finish_reference_job(state, okr, err)
    end_job(state.job)
    busy = false
    if not okr then notify_error(_("Assisted Tagging: couldn't add references. ") .. tostring(err)) end
    cleanup_tmp()
    log("run finished")
    flush_log()
end

-- entry_id: the entry every image becomes a reference of, or nil to take each
-- image's entry from the tags it already carries.
function M.add_references(images, entry_id)
    if not can_start(images) then return end
    if entry_id == nil and #entry_order == 0 then
        dt.print(_("Assisted Tagging: the collection has no entries yet. Add them to its entries.json, then click Reload."))
        return
    end
    busy = true
    M.cancel_requested = false
    start_log(entry_id and ("add references to " .. entry_id) or "add tagged images as references", #images)

    local state = {}
    local okr, err = pcall(function()
        local rows, n_skipped = {}, 0
        for _, img in ipairs(images) do
            local eid = entry_id or M.entry_for_tags(tags_of(img), entries, entry_order)
            if not eid then
                -- tagged only to team level: identify.py saves it as a team reference when
                -- rules.partial_references is on and the shot is solo
                local prefixes = sorted_names(M.hint_prefixes(tags_of(img), nil, entries))
                if #prefixes == 1 then eid = prefixes[1] end
            end
            if eid then
                rows[#rows + 1] = { img.id, img.path .. "/" .. img.filename, eid }
            else
                n_skipped = n_skipped + 1
                log(string.format("%s: skipped, its tags match no single entry", img.filename))
            end
        end
        if #rows == 0 then
            say(_("Assisted Tagging: no selected image carries all of one entry's tags, so nothing was added."))
            return
        end
        local results = run_reference_job(state, rows, " --add-reference")
        if not results then return end
        local added, whole, failed, no_face, multi = 0, 0, 0, 0, 0
        for line in results:gmatch("[^\r\n]+") do
            local p = M.parse_csv_line(line, 2)
            if p and p[2] == "added" then added = added + 1
            elseif p and p[2] == "no_face" then no_face = no_face + 1
            elseif p and p[2] == "multiple_faces" then multi = multi + 1
            elseif p and p[2] == "no_vehicle_whole_frame" then added = added + 1; whole = whole + 1
            elseif p then failed = failed + 1 end
        end
        local extra = {}
        if whole > 0 then extra[#extra + 1] = string.format("%d used the whole frame", whole) end
        if no_face > 0 then extra[#extra + 1] = string.format("%d had no face", no_face) end
        if multi > 0 then extra[#extra + 1] = string.format("%d had several faces, so can't name one person", multi) end
        if n_skipped > 0 then extra[#extra + 1] = string.format("%d skipped", n_skipped) end
        if failed > 0 then extra[#extra + 1] = string.format("%d failed, see log", failed) end
        say(string.format("Assisted Tagging: added %d references to %s%s. Each sample's crop is in %s/refs.",
            added, entry_id or "their entries", #extra > 0 and (" (" .. table.concat(extra, ", ") .. ")") or "",
            current_collection()))
    end)
    finish_reference_job(state, okr, err)
end

-- Saves the confident vehicles (number-read, or a clear livery match) that the last
-- Identify run recorded for these images as references of the entries it found.
function M.promote_references(images)
    if not can_start(images) then return end
    local boxes = boxes_path()
    if not file_exists(boxes) then
        dt.print(_("Assisted Tagging: no records for this collection yet. Run Identify first."))
        return
    end
    busy = true
    M.cancel_requested = false
    start_log("add confident vehicles from last run", #images)

    local state = {}
    local okr, err = pcall(function()
        local rows = {}
        for _, img in ipairs(images) do
            rows[#rows + 1] = { img.id, img.path .. "/" .. img.filename, "" }
        end
        local results = run_reference_job(state, rows, " --promote-boxes --boxes-in " .. shell_quote(boxes))
        if not results then return end
        local counts = { added = 0, none_promotable = 0, stale = 0, failed = 0 }
        for line in results:gmatch("[^\r\n]+") do
            local p = M.parse_csv_line(line, 2)
            if p then counts[p[2]] = (counts[p[2]] or 0) + 1 end
        end
        local extra = {}
        if counts.none_promotable > 0 then extra[#extra + 1] = string.format("%d images had none confident enough", counts.none_promotable) end
        if counts.stale > 0 then extra[#extra + 1] = string.format("%d changed since the run (run Identify again)", counts.stale) end
        if counts.failed > 0 then extra[#extra + 1] = string.format("%d failed, see log", counts.failed) end
        say(string.format("Assisted Tagging: saved vehicles from %d images as references%s. Crops are in %s/refs.",
            counts.added, #extra > 0 and (" (" .. table.concat(extra, ", ") .. ")") or "", current_collection()))
    end)
    finish_reference_job(state, okr, err)
end

-- Refreshes the collection's reference index from refs/ and writes ref-audit.txt beside it.
-- Needs no selected images.
function M.audit_references()
    if not can_start(nil, true) then return end
    busy = true
    M.cancel_requested = false
    start_log("audit references", 0)

    local state = {}
    local okr, err = pcall(function()
        local results = run_reference_job(state, {}, " --audit-refs")
        if not results then return end
        local c, report = {}, ""
        for line in results:gmatch("[^\r\n]+") do
            local k, v = line:match("^([^,]+),(.*)$")
            if k == "report" then report = v elseif k then c[k] = tonumber(v) or 0 end
        end
        say(string.format("Assisted Tagging: audited %d references: %d mislabel suspects, %d cross-entry copies, %d outliers, %d colour outliers. Details in %s",
            c.references or 0, c.mislabel or 0, c.copies or 0, c.outliers or 0, c.colour or 0, report))
    end)
    finish_reference_job(state, okr, err)
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
    local dir = collections_root() .. "/" .. name
    if df.test_file(dir, "e") or file_exists(dir .. "/entries.json") then
        dt.print(string.format(_("Assisted Tagging: %s already exists. Pick a new name, or select it as "
            .. "the collection and use Edit entries.json instead."), name))
        return nil
    end
    return name, dir
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

-- Copies an example's entries.json (see examples_root()) into a new collection:
-- no images needed, since the example already defines the structure, just not
-- your actual entries.
function M.create_collection_from_example(example, raw_name)
    if not example then
        dt.print(_("Assisted Tagging: pick an example first"))
        return
    end
    local name, dir = new_collection_path(raw_name)
    if not name then return end

    local text = read_file(examples_root() .. "/" .. example .. "/entries.json")
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

    say(string.format(
        _("Assisted Tagging: created %s from the %s example. Edit its entries.json with your own entries, "
            .. "then click Reload."), name, example))
    dt.preferences.write("assisted_tagging", "last_collection", "string", name)
    reload_lists(true)
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
    local f = io.open(dir .. "/entries.json", "w")
    if not f then
        notify_error(string.format(
            _("Assisted Tagging: couldn't create %s/entries.json (check the collections folder preference)."), dir))
        return
    end
    f:write(M.entries_json(derived))
    f:close()

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

    dt.preferences.write("assisted_tagging", "last_collection", "string", name)
    reload_lists(true)
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
            dt.print(_("Assisted Tagging: cancelling, finishing the current step..."))
        else
            dt.print(_("Assisted Tagging: another job is still running. Wait for it to finish, or cancel it first."))
        end
        return
    end
    -- One run only: read the box, then clear it so the next run is protected again.
    local replace_manual = not verify_only and replace_manual_check and replace_manual_check.value or false
    if replace_manual_check and not verify_only then replace_manual_check.value = false end
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

local function install_panel()
    if M.module_installed then return end
    M.module_installed = true

    local new_collection_name = dt.new_widget("entry") {
        tooltip = _("Name for the new collection's folder, e.g. \"F1 2026\""),
        placeholder = _("collection name"),
        text = "",
    }
    local new_collection_button = dt.new_widget("button") {
        label = _("Create collection from tagged images"),
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
        label = _("Create collection from example"),
        tooltip = _("Copy the selected example's entries.json into a new collection with no images needed; "
            .. "edit it afterward with your own entries"),
        clicked_callback = function()
            M.create_collection_from_example(selected_example(), new_collection_name.text)
        end,
    }

    -- changed_callback runs asynchronously and also fires when the list is
    -- refilled, so it acts only on a real change from the stored collection.
    collection_combo = dt.new_widget("combobox") {
        label = _("collection"),
        tooltip = _("A folder in the collections folder with an entries.json (see preferences → Lua options)"),
        changed_callback = function(self)
            local name = self.value
            if not name or name == "" or name == _("(no collections)") or name == current_collection() then return end
            if busy or orphan then
                -- a run is using the stored collection's entries; switch back
                dt.print(_("Assisted Tagging: busy, switch collections when the current run finishes."))
                for i = 1, #self do
                    if self[i] == current_collection() then self.selected = i end
                end
                return
            end
            dt.preferences.write("assisted_tagging", "last_collection", "string", name)
            reload_lists(true)
        end,
        _("(click Reload)"),
    }
    local reload_button = dt.new_widget("button") {
        label = _("Reload"),
        tooltip = _("Reread the collections folder and the selected collection's entries.json"),
        clicked_callback = function() reload_lists(false) end,
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
            local f = io.open(path, "w")
            if not f then
                notify_error(string.format(_("Assisted Tagging: couldn't write %s (check the collections folder preference)."), path))
                return
            end
            f:write(entries_editor.text)
            f:close()
            close_entries_editor()
            reload_lists(false)
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
            if current_collection() == "" then
                dt.print(_("Assisted Tagging: pick a collection first"))
                return
            end
            local path = entries_json_path()
            local text = read_file(path)
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
        label = _("Add tagged images as references"),
        tooltip = _("For each selected image that already carries all of one entry's tags, save it as a reference of that entry"),
        clicked_callback = function() M.add_references(dt.gui.action_images, nil) end,
    }
    local promote_button = dt.new_widget("button") {
        label = _("Add confident vehicles from last run"),
        tooltip = _("Save each vehicle the last Identify run was sure of (number read, or a clear livery match) as a reference of the entry it found. Works for pack shots too: only that car's crop is saved."),
        clicked_callback = function() M.promote_references(dt.gui.action_images) end,
    }
    local audit_button = dt.new_widget("button") {
        label = _("Audit references"),
        tooltip = _("Refresh the collection's reference index from refs/, then write ref-audit.txt in the collection folder listing refs that look wrongly filed. Nothing is moved or deleted."),
        clicked_callback = function() M.audit_references() end,
    }

    local panel_box = dt.new_widget("box") {
        orientation = "vertical",
        dt.new_widget("section_label") { label = _("new collection") },
        new_collection_name,
        new_collection_button,
        example_combo,
        example_view_button,
        example_create_button,
        dt.new_widget("section_label") { label = _("collection") },
        collection_combo,
        reload_button,
        plan_button,
        edit_button,
        entries_editor,
        save_entries_button,
        cancel_entries_button,
        verify_button,
        identify_button,
        replace_manual_check,
        dt.new_widget("section_label") { label = _("references") },
        entry_combo,
        add_button,
        add_tagged_button,
        promote_button,
        audit_button,
    }

    dt.register_lib(
        "assisted_tagging", _("Assisted Tagging"), true, true,
        { [dt.gui.views.lighttable] = { "DT_UI_CONTAINER_PANEL_RIGHT_CENTER", 100 } },
        panel_box
    )
    dt.control.dispatch(reload_lists, true)
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
