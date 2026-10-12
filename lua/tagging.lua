--[[
    tagging.lua — Assisted Tagging for darktable

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
    number = "Assisted Tagging|Motorsport|Identified|By number",
    livery = "Assisted Tagging|Motorsport|Identified|By livery",
    burst = "Assisted Tagging|Motorsport|Identified|By burst",
    team = "Assisted Tagging|Motorsport|Team only",
    none = "Assisted Tagging|Motorsport|Unidentified",
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
    local function note(outcome)
        local name = rules.diag[outcome]
        if name and name ~= "" then diag[name] = true end
    end
    for _, r in ipairs(rows) do
        local e = entries[r.entry_id]
        if e and (r.method == "number" or r.method == "livery" or r.method == "burst") then
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
    end
    if not identified then
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
-- detach, sorted. Only owned tags are ever detached.
function M.tag_changes(have, wanted, owned)
    local attach, detach = {}, {}
    for name in pairs(wanted) do
        if not have[name] then attach[#attach + 1] = name end
    end
    for name in pairs(have) do
        if owned[name] and not wanted[name] then detach[#detach + 1] = name end
    end
    table.sort(attach)
    table.sort(detach)
    return attach, detach
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
-- Those get no rows, so their tags are left exactly as they were.
function M.read_results(text)
    local rows_of, errored = {}, {}
    for line in (text or ""):gmatch("[^\r\n]+") do
        local p = M.parse_csv_line(line, 6)
        local id = p and tonumber(p[1])
        if id and p[3] == "error" then
            errored[id] = true
        elseif id then
            rows_of[id] = rows_of[id] or {}
            table.insert(rows_of[id], { box = tonumber(p[2]), method = p[3], entry_id = p[4], alt_entry_id = p[5] })
        end
    end
    return rows_of, errored
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
local DEFAULT_COLLECTIONS_ROOT = dt.configuration.config_dir .. "/assisted_tagging/collections"

local MODEL_FILES = {
    detector_model = "object_detection_yolox_2022nov.onnx",
    ocr_detection_model = "text_detection_en_ppocrv3_2023may.onnx",
    ocr_recognition_model = "text_recognition_CRNN_EN_2021sep.onnx",
    embedder_model = "dinov2_small.onnx",
}

if dt.gui then
    dt.preferences.register("assisted_tagging", "python_bin", "file",
        "Assisted Tagging: Python interpreter",
        "Python executable with the packages in python/requirements.txt installed (e.g. .venv\\Scripts\\python.exe). Empty = auto-detect the repo's .venv",
        "")
    dt.preferences.register("assisted_tagging", "identify_script", "file",
        "Assisted Tagging: identify.py",
        "Path to identify.py from darktable-assisted-tagging (empty = auto-detect)",
        "")
    dt.preferences.register("assisted_tagging", "detector_model", "file",
        "Assisted Tagging: vehicle detector model (YOLOX .onnx)",
        "Empty = models/" .. MODEL_FILES.detector_model .. " in the repo",
        "")
    dt.preferences.register("assisted_tagging", "ocr_detection_model", "file",
        "Assisted Tagging: number detection model (PP-OCRv3 .onnx)",
        "Empty = models/" .. MODEL_FILES.ocr_detection_model .. " in the repo",
        "")
    dt.preferences.register("assisted_tagging", "ocr_recognition_model", "file",
        "Assisted Tagging: number reading model (CRNN .onnx)",
        "Empty = models/" .. MODEL_FILES.ocr_recognition_model .. " in the repo",
        "")
    dt.preferences.register("assisted_tagging", "embedder_model", "file",
        "Assisted Tagging: livery matching model (DINOv2 .onnx)",
        "Empty = models/" .. MODEL_FILES.embedder_model .. " in the repo",
        "")
    dt.preferences.register("assisted_tagging", "collections_root", "directory",
        "Assisted Tagging: collections folder",
        "Folder with one folder per collection (entries.json + refs). Empty = assisted_tagging/collections in darktable's config folder",
        "")
    dt.preferences.register("assisted_tagging", "diagnostic_tags", "bool",
        "Assisted Tagging: diagnostic tags",
        "Tag how each image was identified (under Assisted Tagging|Motorsport: Identified|By number, |By livery, |By burst, then Team only and Unidentified) for filtering and spot-checks; a collection's rules can rename them. Off removes them on the next run",
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
        if p and p ~= "" and (df.test_file(p, "e") or file_exists(p)) then
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

local function identify_script()
    local pref = dt.preferences.read("assisted_tagging", "identify_script", "file") or ""
    local home = os.getenv("USERPROFILE") or os.getenv("HOME") or ""
    local found = first_existing({
        pref,
        THIS_DIR .. "/identify.py",
        THIS_DIR .. "/python/identify.py",
        THIS_DIR .. "/../python/identify.py",
        THIS_DIR .. "/../../python/identify.py",
        home .. "/Pictures/DarkTable/Settings/Plugins/darktable-assisted-tagging/python/identify.py",
    })
    return found or (THIS_DIR .. "/identify.py")
end

local function plugin_root(script)
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

-- A model preference, or the repo's models/ copy when it's empty. A missing
-- file is passed through as-is, so identify.py names it in its error.
local function model_path(pref_name, script)
    local pref = dt.preferences.read("assisted_tagging", pref_name, "file") or ""
    if pref ~= "" then return pref end
    return plugin_root(script) .. "/models/" .. MODEL_FILES[pref_name]
end

local function collections_root()
    local pref = dt.preferences.read("assisted_tagging", "collections_root", "directory") or ""
    return pref ~= "" and pref or DEFAULT_COLLECTIONS_ROOT
end

local function current_collection()
    return dt.preferences.read("assisted_tagging", "last_collection", "string") or ""
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
local identify_button, collection_combo, entry_combo = nil, nil, nil
local entries, entry_order, rules = {}, {}, M.default_rules()

local function cancelled(job)
    return M.cancel_requested or (job and not job.valid) or file_exists(CANCEL_PATH)
end

-- Ends a job once. Setting valid = false destroys darktable's progress object without
-- checking it still exists (src/lua/gui.c), so a second call would free it twice.
local function end_job(job)
    if job and job.valid then job.valid = false end
end

-- Asks a running identify.py to stop and waits briefly; if it's still running, it's an
-- orphan and blocks the next run until it exits.
local function abandon_process()
    local cf = io.open(CANCEL_PATH, "w")
    if cf then cf:write("1"); cf:close() end
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
    return " --detector " .. shell_quote(model_path("detector_model", script))
        .. " --ocr-det " .. shell_quote(model_path("ocr_detection_model", script))
        .. " --ocr-rec " .. shell_quote(model_path("ocr_recognition_model", script))
        .. " --embedder " .. shell_quote(model_path("embedder_model", script))
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
            local code = run_python("- - --list" .. collection_args()
                .. " --collections-out " .. shell_quote(COLLECTIONS_PATH)
                .. " --entries-out " .. shell_quote(ENTRIES_PATH) .. " --rules-out " .. shell_quote(RULES_PATH), nil)
            flush_log()
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

local function set_idle_label()
    if identify_button then identify_button.label = _("Identify selection") end
end

local function stop_job(job)
    M.cancel_requested = true
    local cf = io.open(CANCEL_PATH, "w")
    if cf then cf:write("1"); cf:close() end
    end_job(job)
end

local function start_log(what, n)
    flush_log() -- anything logged since the last run belongs to its log
    pcall(os.remove, PREV_LOG_PATH)
    pcall(os.rename, LOG_PATH, PREV_LOG_PATH)
    log(string.format("%s: darktable %s, %d images, collection %s", what,
        tostring(dt.configuration.version), n, current_collection()))
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

local function write_rows(path, rows)
    local f = io.open(path, "w")
    if not f then return false end
    for _, r in ipairs(rows) do f:write(M.csv_line(r), "\n") end
    f:close()
    return true
end

-- A run's preconditions; prints why and returns false when it can't start.
local function can_start(images)
    if busy then
        dt.print(_("Assisted Tagging: already running. Click Cancel in the panel to stop it."))
        return false
    end
    if not orphan_gone() then
        dt.print(_("Assisted Tagging: the last run is still stopping. Try again in a moment."))
        return false
    end
    if not images or #images == 0 then
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

function M.identify_images(images)
    if not can_start(images) then return end
    busy = true
    M.cancel_requested = false
    if identify_button then identify_button.label = _("Cancel") end
    start_log("identify started", #images)

    local job = nil
    local okr, err = pcall(function()
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

        local time_items = {}
        for _, img in ipairs(primaries) do
            table.insert(time_items, { id = img.id, epoch = M.exif_time_to_epoch(img.exif_datetime_taken) })
        end
        local gap = dt.preferences.read("assisted_tagging", "burst_gap_seconds", "integer")
        local burst_of = M.cluster_by_time(time_items, (gap and gap >= 1) and gap or M.BURST_GAP_SECONDS)

        local rows = {}
        for _, img in ipairs(primaries) do
            rows[#rows + 1] = { img.id, img.path .. "/" .. img.filename, burst_of[img.id] }
        end
        pcall(os.remove, RESULTS_PATH)
        pcall(os.remove, ENTRIES_PATH)
        pcall(os.remove, RULES_PATH)
        if not write_rows(MANIFEST_PATH, rows) then
            error("couldn't write the image list to darktable's tmp folder (disk full or no write access?)", 0)
        end

        job = dt.gui.create_job(_("Assisted Tagging"), true, stop_job)
        job.percent = 0.0
        local script = identify_script()
        local code = run_python(shell_quote(MANIFEST_PATH) .. " " .. shell_quote(RESULTS_PATH)
            .. collection_args() .. model_args(script)
            .. " --cache " .. shell_quote(CACHE_PATH)
            .. " --entries-out " .. shell_quote(ENTRIES_PATH) .. " --rules-out " .. shell_quote(RULES_PATH),
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

        load_entries_csv()
        refresh_entry_combo()
        local rows_of = M.read_results(read_file(RESULTS_PATH))

        local owned = M.owned_tags(entries, rules)
        local diag_on = dt.preferences.read("assisted_tagging", "diagnostic_tags", "bool")
        local tag_objs, writes, failed, first_error = {}, 0, 0, nil
        local n_tagged, n_unidentified, n_missing = 0, 0, 0
        local by_method = { number = 0, livery = 0, burst = 0, team = 0 }
        local function tag_named(name)
            tag_objs[name] = tag_objs[name] or tags.create(name)
            return tag_objs[name]
        end

        for i, img in ipairs(primaries) do
            local results = rows_of[tonumber(img.id)]
            if not results then
                n_missing = n_missing + 1
            else
                local wanted, diag, identified = M.wanted_tags(results, entries, rules)
                if identified then n_tagged = n_tagged + 1 else n_unidentified = n_unidentified + 1 end
                for _, r in ipairs(results) do
                    if by_method[r.method] and entries[r.entry_id] then by_method[r.method] = by_method[r.method] + 1 end
                end
                if diag_on then
                    for name in pairs(diag) do wanted[name] = true end
                end
                for _, copy in ipairs(group_of[img.id]) do
                    local attach, detach = M.tag_changes(tags_of(copy), wanted, owned)
                    local okw, werr = pcall(function()
                        for _, name in ipairs(detach) do tags.detach(tag_named(name), copy) end
                        for _, name in ipairs(attach) do tags.attach(tag_named(name), copy) end
                    end)
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
                             { "team", "team only" } }) do
            if by_method[m[1]] > 0 then parts[#parts + 1] = string.format("%d %s", by_method[m[1]], m[2]) end
        end
        local msg = string.format("Assisted Tagging: done. %d of %d images tagged", n_tagged, #primaries)
        if #parts > 0 then msg = msg .. " (vehicles: " .. table.concat(parts, ", ") .. ")" end
        if n_unidentified > 0 then msg = msg .. string.format(", %d unidentified", n_unidentified) end
        if n_missing > 0 then msg = msg .. string.format(", %d unreadable (see log)", n_missing) end
        if failed > 0 then msg = msg .. string.format(", %d couldn't be updated (see log)", failed) end
        say(msg)
        if first_error then log("first tag write error: " .. first_error) end
    end)

    if job then pcall(function() job.valid = false end) end
    busy = false
    set_idle_label()
    if not okr then notify_error(_("Assisted Tagging: couldn't run. ") .. tostring(err)) end
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

    local job = nil
    local okr, err = pcall(function()
        local rows, n_skipped = {}, 0
        for _, img in ipairs(images) do
            local eid = entry_id or M.entry_for_tags(tags_of(img), entries, entry_order)
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
        pcall(os.remove, RESULTS_PATH)
        if not write_rows(MANIFEST_PATH, rows) then
            error("couldn't write the image list to darktable's tmp folder (disk full or no write access?)", 0)
        end
        job = dt.gui.create_job(_("Assisted Tagging: adding references"), true, stop_job)
        job.percent = 0.0
        local code = run_python(shell_quote(MANIFEST_PATH) .. " " .. shell_quote(RESULTS_PATH)
            .. " --add-reference" .. collection_args() .. model_args(identify_script())
            .. " --entries-out " .. shell_quote(ENTRIES_PATH) .. " --rules-out " .. shell_quote(RULES_PATH),
            job, 0, 1, "adding references")
        flush_log()
        dt.print_hinter(" ")
        if code == nil or code == 130 then
            say(_("Assisted Tagging: cancelled. References already saved stay in the collection."))
            return
        end
        if code ~= 0 or not file_exists(RESULTS_PATH) then
            notify_error(failure_message(code))
            return
        end
        local added, whole, failed = 0, 0, 0
        for line in (read_file(RESULTS_PATH) or ""):gmatch("[^\r\n]+") do
            local p = M.parse_csv_line(line, 2)
            if p and p[2] == "added" then added = added + 1
            elseif p and p[2] == "no_vehicle_whole_frame" then added = added + 1; whole = whole + 1
            elseif p then failed = failed + 1 end
        end
        local extra = {}
        if whole > 0 then extra[#extra + 1] = string.format("%d used the whole frame", whole) end
        if n_skipped > 0 then extra[#extra + 1] = string.format("%d skipped", n_skipped) end
        if failed > 0 then extra[#extra + 1] = string.format("%d failed, see log", failed) end
        say(string.format("Assisted Tagging: added %d references to %s%s. Each sample's crop is in %s/refs.",
            added, entry_id or "their entries", #extra > 0 and (" (" .. table.concat(extra, ", ") .. ")") or "",
            current_collection()))
    end)

    if job then pcall(function() job.valid = false end) end
    busy = false
    if not okr then notify_error(_("Assisted Tagging: couldn't add references. ") .. tostring(err)) end
    cleanup_tmp()
    log("run finished")
    flush_log()
end

local function start_identify(allow_cancel)
    if busy then
        if allow_cancel and identify_button and identify_button.label == _("Cancel") then
            M.cancel_requested = true
            local cf = io.open(CANCEL_PATH, "w")
            if cf then cf:write("1"); cf:close() end
            identify_button.label = _("Cancelling...")
            dt.print(_("Assisted Tagging: cancelling, finishing the current step..."))
        else
            dt.print(_("Assisted Tagging: already running. Click Cancel in the panel to stop it."))
        end
        return
    end
    M.identify_images(dt.gui.action_images)
end

local function selected_entry_id()
    local i = entry_combo and entry_combo.selected or 0
    return entry_order[i]
end

local function install_panel()
    if M.module_installed then return end
    M.module_installed = true

    -- changed_callback runs asynchronously and also fires when the list is
    -- refilled, so it acts only on a real change from the stored collection.
    collection_combo = dt.new_widget("combobox") {
        label = _("collection"),
        tooltip = _("A folder in the collections folder with an entries.json (see preferences → Lua options)"),
        changed_callback = function(self)
            local name = self.value
            if not name or name == "" or name == _("(no collections)") or name == current_collection() then return end
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
    identify_button = dt.new_widget("button") {
        label = _("Identify selection"),
        tooltip = _("Identify the vehicles in the selected images and tag them with their entries' tags"),
        clicked_callback = function() start_identify(true) end,
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

    local panel_box = dt.new_widget("box") {
        orientation = "vertical",
        collection_combo,
        reload_button,
        plan_button,
        identify_button,
        dt.new_widget("section_label") { label = _("references") },
        entry_combo,
        add_button,
        add_tagged_button,
    }

    dt.register_lib(
        "assisted_tagging", _("Assisted Tagging"), true, true,
        { [dt.gui.views.lighttable] = { "DT_UI_CONTAINER_PANEL_RIGHT_CENTER", 100 } },
        panel_box
    )
    dt.control.dispatch(reload_lists, true)
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

M.fmt_eta = fmt_eta

return M
