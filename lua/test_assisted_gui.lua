-- Run with: lua test_assisted_gui.lua
-- Runs the darktable half of assisted_tagging.lua for real: the panel is built and the button
-- functions run as a click runs them. Only the edges are faked: the darktable API, the plugin
-- folder (empty model files) and the identify.py process (os.execute), which answers from PYTHON below.

package.path = package.path .. ";./?.lua"

local failures = 0
local function check(name, got, want)
    if got ~= want then
        failures = failures + 1
        print(string.format("FAIL %s: got %s, want %s", name, tostring(got), tostring(want)))
    else
        print(string.format("ok   %s", name))
    end
end

local WINDOWS = package.config:sub(1, 1) == "\\"
local real_execute = os.execute

local function make_dir(dir)
    real_execute(WINDOWS and ('mkdir "' .. dir:gsub("/", "\\") .. '" 2>nul') or ("mkdir -p '" .. dir .. "'"))
end

local function write_file(path, text)
    local f = assert(io.open(path, "w"))
    f:write(text)
    f:close()
end

local function read_file(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local text = f:read("a")
    f:close()
    return text
end

-- Folders -------------------------------------------------------------------------
local ROOT = ((os.getenv("TEMP") or os.getenv("TMPDIR") or "/tmp"):gsub("\\", "/"):gsub("/$", ""))
    .. "/at_gui_test_" .. os.time() .. "_" .. math.random(100000, 999999)
local PLUGIN = ROOT .. "/plugins/darktable-assisted-tagging"
for _, dir in ipairs({ "/tmp", "/config/assisted_tagging", "/collections/Rallye/refs/112", "/plugins/darktable-assisted-tagging/python",
    "/plugins/darktable-assisted-tagging/models", "/plugins/darktable-assisted-tagging/.venv/Scripts",
    "/plugins/darktable-assisted-tagging/.venv/bin" }) do
    make_dir(ROOT .. dir)
end
for _, file in ipairs({ "/python/identify.py", "/.venv/Scripts/python.exe", "/.venv/Scripts/pythonw.exe", "/.venv/bin/python",
    "/models/dfine_s_coco.onnx", "/models/text_detection_en_ppocrv3_2023may.onnx",
    "/models/text_recognition_CRNN_EN_2021sep.onnx", "/models/dinov2_small.onnx" }) do
    write_file(PLUGIN .. file, "")
end
-- closer_car_margin has no widget on the panel: a run must still carry it
write_file(ROOT .. "/collections/Rallye/settings.json", '{"family_colour": true, "family_colour_root": "Colour", "family_number": true, "family_number_root": "Number", "closer_car_margin": 0.12}')
write_file(ROOT .. "/collections/Rallye/entries.json", "[]")
write_file(ROOT .. "/collections/Rallye/refs/112/1_b0.jpg", "crop")
write_file(ROOT .. "/collections/Rallye/refs/sources.json", "{}")
write_file(ROOT .. "/collections/Rallye/index.npz", "vectors")
-- image 1's entry tag was written by Identify; its colour tag was not
write_file(ROOT .. "/config/assisted_tagging/ledger.csv", "1,Rallye|112\n")

-- identify.py ---------------------------------------------------------------------
-- What the fake process writes, and what it was last asked.
local PYTHON = {
    entries = "112,Team A,112,Rallye|112,Driver A,Co A,Pink\n35,Team B,35,Rallye|35,Driver B,Co B,Blue\n",
    results = "",
    runs = {},
}

local function flag(argv, name)
    for i, a in ipairs(argv) do
        if a == name then return argv[i + 1] end
    end
    return nil
end

local function fake_identify(argv, done_path)
    local run = { argv = argv, manifest = read_file(argv[2]), settings = flag(argv, "--settings") and read_file(flag(argv, "--settings")) }
    PYTHON.runs[#PYTHON.runs + 1] = run
    if flag(argv, "--entries-out") then write_file(flag(argv, "--entries-out"), PYTHON.entries) end
    if flag(argv, "--rules-out") then write_file(flag(argv, "--rules-out"), "") end
    if flag(argv, "--collections-out") then write_file(flag(argv, "--collections-out"), "Rallye\n") end
    if flag(argv, "--overturns-out") and PYTHON.overturns then write_file(flag(argv, "--overturns-out"), PYTHON.overturns) end
    if argv[3] ~= "-" then write_file(argv[3], PYTHON.results) end
    write_file(done_path, "0\n")
end

-- The launch as plugin_common.run_async_python writes it: a job file on Windows, a shell line elsewhere.
os.execute = function(cmd)
    if not cmd or not cmd:find("identify.py", 1, true) and not cmd:find("launch.py", 1, true) then return real_execute(cmd) end
    local argv, done_path = {}, nil
    if WINDOWS then
        local job
        for quoted in cmd:gmatch('"([^"]*)"') do job = quoted end
        local lines = {}
        for line in (read_file(job) or ""):gmatch("[^\r\n]+") do lines[#lines + 1] = line end
        done_path = lines[1]
        for i = 4, #lines do argv[#argv + 1] = lines[i] end
    else
        local tokens = {}
        for quoted in cmd:gmatch("'([^']*)'") do tokens[#tokens + 1] = quoted end
        done_path = tokens[#tokens]
        for i = 2, #tokens - 4 do argv[#argv + 1] = tokens[i] end
    end
    fake_identify(argv, done_path)
    return true
end

-- darktable -----------------------------------------------------------------------
local prints, dispatched, prefs = {}, {}, {
    ["assisted_tagging/collections_root"] = ROOT .. "/collections",
    ["assisted_tagging/last_collection"] = "Rallye",
    ["assisted_plugins/plugins_root"] = ROOT .. "/plugins",
}
local PREF_EMPTY = { string = "", directory = "", file = "", integer = 0, float = 0, bool = false }
local selection, jobs = {}, {}
local selection_sets = 0 -- times the plugin changed the selection
local panel -- the widget register_lib receives

local dt = {
    configuration = { tmp_dir = ROOT .. "/tmp", config_dir = ROOT .. "/config", version = "test", running_os = WINDOWS and "windows" or "macos" },
    gettext = { gettext = function(msgid) return msgid end },
    preferences = {
        register = function() end,
        read = function(group, name, kind)
            local value = prefs[group .. "/" .. name]
            if value == nil then return PREF_EMPTY[kind] end
            return value
        end,
        write = function(group, name, _kind, value) prefs[group .. "/" .. name] = value end,
    },
    print = function(msg) prints[#prints + 1] = msg end,
    print_error = function() end,
    print_hinter = function() end,
    tags = {
        get_tags = function(img) return img.tags end,
        find = function(name) return { name = name } end,
        create = function(name) return { name = name } end,
        attach = function(tag, img)
            for _, t in ipairs(img.tags) do
                if t.name == tag.name then return end
            end
            img.tags[#img.tags + 1] = { name = tag.name }
        end,
        detach = function(tag, img)
            for i, t in ipairs(img.tags) do
                if t.name == tag.name then table.remove(img.tags, i) break end
            end
        end,
    },
    control = {
        sleep = function() end,
        dispatch = function(fn) dispatched[#dispatched + 1] = fn end,
    },
    database = { get_image = function() return nil end },
    register_event = function() end,
    destroy_event = function() end,
    register_lib = function(...) panel = select(select("#", ...), ...) end,
    -- a widget is its own property table: children in the array part, values as fields
    new_widget = function(kind)
        return function(props)
            props.kind = kind
            return props
        end
    end,
    gui = {
        libs = {},
        views = { lighttable = {} },
        selection = function(images)
            if images then
                selection = images
                selection_sets = selection_sets + 1
            end
            return selection
        end,
        action_images = {},
        current_view = function() return { id = "lighttable" } end,
        create_job = function()
            jobs[#jobs + 1] = { valid = true, percent = 0 }
            return jobs[#jobs]
        end,
    },
}
package.loaded["darktable"] = dt
package.loaded["lib/dtutils"] = { check_min_api_version = function() end }
package.loaded["lib/dtutils.file"] = {
    check_if_bin_exists = function() return false end,
    -- a rename onto itself succeeds for a file or folder that exists, on every platform
    test_file = function(path) return os.rename(path, path) and true or false end,
}

local function image(id, filename, tag_names)
    local tags = {}
    for i, name in ipairs(tag_names) do tags[i] = { name = name } end
    return { id = id, filename = filename, path = "/photos", tags = tags }
end

local function printed(text)
    for _, msg in ipairs(prints) do
        if msg:find(text, 1, true) then return true end
    end
    return false
end

local function last_print()
    return prints[#prints] or ""
end

-- Startup -------------------------------------------------------------------------
local T = require("assisted_tagging")
check("the panel is installed at startup", T.module_installed, true)
check("startup has no Lua error", read_file(ROOT .. "/config/assisted_tagging.lua.log"), nil)
-- darktable runs the dispatched startup load after the script has loaded
for _, fn in ipairs(dispatched) do fn() end
check("startup lists the collection's entries", #PYTHON.runs > 0 and PYTHON.runs[1].argv[4], "--list")
check("the startup load has no Lua error", read_file(ROOT .. "/config/assisted_tagging.lua.log"), nil)

-- Fill entry colours ----------------------------------------------------------------
local function fill(images)
    prints, PYTHON.runs = {}, {}
    T.fill_entry_colours(images)
    return PYTHON.runs[#PYTHON.runs]
end

local run = fill({ image(2, "DSC00002.JPG", { "Somewhere|Else" }) })
check("fill colours, no entry tags: says no image names an entry", printed("no selected image carries all of one entry's tags"), true)
check("fill colours, no entry tags: no crash", printed("couldn't fill entry colours"), false)
check("fill colours: says it started as soon as it is clicked", printed("Assisted Tagging: Fill entry colours started on 1 image…"), true)
check("fill colours, no entry tags: identify.py isn't started", run, nil)
check("fill colours, no entry tags: the log says why", (read_file(ROOT .. "/config/assisted_tagging.log") or "")
    :find("DSC00002.JPG: skipped, its tags match no single entry: it carries no entry's tags", 1, true) ~= nil, true)

PYTHON.results = "1,added,set,112\n"
run = fill({ image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red" }) })
check("fill colours, Identify's entry tag + hand colour: no crash", printed("couldn't fill entry colours"), false)
check("fill colours, Identify's entry tag + hand colour: the row names the entry and the colour",
    run and run.manifest, T.csv_line({ 1, "/photos/DSC00001.JPG", "112", "Red" }) .. "\n")
check("fill colours: runs in colours-only mode", run ~= nil and flag(run.argv, "--add-reference") == "--colours-only", true)
check("fill colours: reports the entry set", printed("Assisted Tagging: colour saved for entry 112. File:"), true)

-- Identify wrote every tag: one photo's colour tag is not enough to replace the entry's colour
local ledger_text = ""
for id = 1, 9 do ledger_text = ledger_text .. id .. ",Rallye|112\n" .. id .. ",Colour|Red\n" .. id .. ",Colour|Brown\n" end
write_file(ROOT .. "/config/assisted_tagging/ledger.csv", ledger_text)
run = fill({ image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red" }) })
check("fill colours, one photo with Identify's tags: the row leaves the colour to the reading",
    run and run.manifest, T.csv_line({ 1, "/photos/DSC00001.JPG", "112", "" }) .. "\n")

-- three of four agree: their colour is sent for every row of the entry
run = fill({ image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red" }), image(4, "DSC00004.JPG", { "Rallye|112", "Colour|Red" }),
    image(5, "DSC00005.JPG", { "Rallye|112", "Colour|Brown" }), image(6, "DSC00006.JPG", { "Rallye|112", "Colour|Red" }) })
check("fill colours, Identify's colour tag on 3 of 4 photos: every row carries it", run and run.manifest,
    T.csv_line({ 1, "/photos/DSC00001.JPG", "112", "Red" }) .. "\n" .. T.csv_line({ 4, "/photos/DSC00004.JPG", "112", "Red" }) .. "\n"
    .. T.csv_line({ 5, "/photos/DSC00005.JPG", "112", "Red" }) .. "\n" .. T.csv_line({ 6, "/photos/DSC00006.JPG", "112", "Red" }) .. "\n")

-- a photo tagged Check colour has no say, so two photos are left: too few
run = fill({ image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red" }), image(4, "DSC00004.JPG", { "Rallye|112", "Colour|Red" }),
    image(6, "DSC00006.JPG", { "Rallye|112", "Colour|Red", "Assisted Tagging|Identification|Check colour" }) })
check("fill colours, Check colour photos don't count: no colour is sent",
    run and run.manifest ~= nil and run.manifest:find("Red", 1, true) == nil, true)

-- split two against two: no colour is sent
run = fill({ image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red" }), image(4, "DSC00004.JPG", { "Rallye|112", "Colour|Red" }),
    image(5, "DSC00005.JPG", { "Rallye|112", "Colour|Brown" }), image(6, "DSC00006.JPG", { "Rallye|112", "Colour|Brown" }) })
check("fill colours, Identify's colour tags split: no colour is sent",
    run and run.manifest ~= nil and run.manifest:find("Red", 1, true) == nil and run.manifest:find("Brown", 1, true) == nil, true)

run = fill({ image(3, "DSC00003.JPG", { "Rallye|35" }) })
check("fill colours, hand entry tag, no colour tag: the row leaves the colour to the reading",
    run and run.manifest, T.csv_line({ 3, "/photos/DSC00003.JPG", "35", "" }) .. "\n")

-- a number tag alone names the entry, though the photo lacks the entry's other tags
run = fill({ image(7, "DSC00007.JPG", { "Number|112", "Colour|Red" }), image(8, "DSC00008.JPG", { "Number|112", "Colour|Red" }),
    image(9, "DSC00009.JPG", { "Number|112", "Colour|Red" }) })
check("fill colours, number tag only: the rows name the entry and the agreed colour", run and run.manifest,
    T.csv_line({ 7, "/photos/DSC00007.JPG", "112", "Red" }) .. "\n" .. T.csv_line({ 8, "/photos/DSC00008.JPG", "112", "Red" }) .. "\n"
    .. T.csv_line({ 9, "/photos/DSC00009.JPG", "112", "Red" }) .. "\n")

-- Add references ------------------------------------------------------------------
local function add(images, entry_id)
    prints, PYTHON.runs = {}, {}
    T.add_references(images, entry_id)
    return PYTHON.runs[#PYTHON.runs]
end

run = add({ image(2, "DSC00002.JPG", { "Somewhere|Else" }) })
check("add references, no entry tags: no crash", printed("couldn't add references"), false)
check("add references, no entry tags: identify.py isn't started", run, nil)
check("add references: says it started as soon as it is clicked", printed("Assisted Tagging: Add references started on 1 image…"), true)
print("     add references, no entry tags, says: " .. last_print())

PYTHON.results = "3,added,,35\n"
run = add({ image(3, "DSC00003.JPG", { "Rallye|35" }) })
check("add references, hand entry tag: no crash", printed("couldn't add references"), false)
check("add references, hand entry tag: the row names the entry", run and run.manifest ~= nil
    and run.manifest:find(T.csv_line({ 3, "/photos/DSC00003.JPG", "35" }), 1, true) == 1, true)
check("add references, hand entry tag: reports the reference added",
    last_print(), "Assisted Tagging: added 1 references to their entries. Crops are in Rallye/refs.")
check("add references: the run keeps a settings.json-only value", run and run.settings
    and run.settings:find('"closer_car_margin": 0.12', 1, true) ~= nil, true)
PYTHON.results = "3,no_vehicle,,35\n"
add({ image(3, "DSC00003.JPG", { "Rallye|35" }) })
check("add references, no vehicle found: says nothing was added and why",
    last_print(), "Assisted Tagging: no reference added. Left out: 1 had no vehicle found (see log).")

-- Clear tagging marks ---------------------------------------------------------------
local marked = image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red", "Hand|Tag" })
selection, prints = { marked }, {}
local sleeps = {}
dt.control.sleep = function(ms) sleeps[#sleeps + 1] = ms end
T.clear_marks({ marked })
check("clear: the tags are cleared", printed("Assisted Tagging: cleared 2 tags from 1 images."), true)
check("clear: pauses once after the image with writes", #sleeps == 1 and sleeps[1] >= 20, true)
check("clear: the log has the timing line", (read_file(ROOT .. "/config/assisted_tagging.log") or ""):find(
    "clear: timing: 1 of 1 images in %d+s; [%d.]+s in tag writes, [%d.]+s waiting for darktable, [%d.]+s paused; 2 tag writes\n") ~= nil, true)
check("clear: the selection stays while the tags are detached", #selection, 1)
check("clear: the job bar is closed", jobs[#jobs].valid, false)
prints = {}
T.clear_marks({ marked })
check("clear: the next clear runs, the panel isn't left busy",
    printed("Assisted Tagging: nothing to clear; the selection has no tagging marks."), true)

-- the x on the job bar, clicked during the pause after the first image
local first, second, third = image(2, "DSC00002.JPG", { "Rallye|112", "Colour|Red" }),
    image(3, "DSC00003.JPG", { "Rallye|112", "Colour|Red" }), image(4, "DSC00004.JPG", { "Rallye|112", "Colour|Red" })
prints = {}
dt.control.sleep = function() jobs[#jobs].valid = false end
T.clear_marks({ first, second, third })
check("clear, cancelled: the first image is cleared, the others keep their tags",
    #first.tags .. " " .. #second.tags .. " " .. #third.tags, "0 2 2")
check("clear, cancelled: says how far it got", last_print(),
    "Assisted Tagging: stopped; cleared 2 tags from 1 images. The rest keep their marks, clear again to finish.")
dt.control.sleep = function() end
T.clear_marks({ first, second, third })
check("clear, after a cancel: the next clear finishes the rest", #second.tags + #third.tags, 0)
check("no button changes the selection", selection_sets, 0)

-- Export and import presets ---------------------------------------------------------
local function widget_where(widget, kind, field, value)
    if type(widget) ~= "table" then return nil end
    if widget.kind == kind and widget[field] == value then return widget end
    for _, child in ipairs(widget) do
        local found = widget_where(child, kind, field, value)
        if found then return found end
    end
    return nil
end

check("the progress line sits at the foot of the panel, outside the folding pages",
      panel[#panel].kind, "label")

-- To check ------------------------------------------------------------------------
local to_check = panel[#panel - 1]
check("To check sits above the progress line, outside the folding pages",
    type(to_check) == "table" and to_check[1] and to_check[1][1] and to_check[1][1].label, "To check")
to_check = type(to_check) == "table" and to_check[1] and to_check[1][1] and to_check[1][1].label == "To check" and to_check or { {}, {} }
local CHECKS_FILE = ROOT .. "/config/assisted_tagging.checks.txt"
PYTHON.results = "1,failed,,112\n"
fill({ image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red" }) })
check("To check: a photo fill colours couldn't read shows in the box", to_check.visible, true)
check("To check: the row names the action and the count",
    ((to_check[2][1] or {}).label or ""):gsub("\n", " "), "Fill entry colours: 1 photos couldn't be read (see log)")
check("To check: the item is saved for a restart",
    (read_file(CHECKS_FILE) or ""):find("Fill entry colours\t1 photos couldn't be read (see log)\t1\t", 1, true) ~= nil, true)
prints, selection_sets = {}, 0
;(widget_where(to_check, "button", "label", "Select") or { clicked_callback = function() end }).clicked_callback()
check("To check: Select changes the selection", selection_sets, 1)
check("To check: Select says which photos are gone", printed("1 of these photos are no longer in the library"), true)
selection_sets = 0
PYTHON.results = "1,added,set,112\n"
fill({ image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red" }) })
check("To check: the next fill colours run replaces its items", (read_file(CHECKS_FILE) or ""):find("Fill entry colours", 1, true), nil)
PYTHON.results = "1,failed,,112\n"
fill({ image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red" }) })
;(widget_where(to_check, "button", "label", "Clear") or { clicked_callback = function() end }).clicked_callback()
check("To check: Clear empties the box", to_check.visible, false)
check("To check: Clear empties the saved list", read_file(CHECKS_FILE), "")
check("To check: a row without a fix has no Fix button", (widget_where(to_check, "button", "label", "Fix") or {}).visible, false)

-- Verify's "differ" row, then its Fix: Identify again on those photos with replace manual on
local tagged = image(1, "DSC00001.JPG", { "Rallye|112" })
PYTHON.results, PYTHON.runs, prints = "1,0,conflict,35,,0.9,,solo,0,,0,,0\n", {}, {}
T.identify_images({ tagged }, false, true)
check("To check: Verify's differ row reads in full", ((to_check[2][1] or {}).label or ""):gsub("\n", " "),
    "Verify: 1 photos read a different entry from the one their tags name. Fix runs Identify on them with your tags replaced.")
check("To check: the label wraps, no line over 44 characters", ((to_check[2][1] or {}).label or ""):find("[^\n]" .. ("[^\n]"):rep(44)), nil)
check("To check: the differ row lists the photo and why", ((to_check[2][2] or {}).text or ""):gsub("\n%s*", " "),
    "• DSC00001.JPG: reads entry 35, its tags name 112")
check("To check: the photo list is read-only text", (to_check[2][2] or {}).kind .. " " .. tostring((to_check[2][2] or {}).editable), "text_view false")
check("To check: the saved line names its fix and the photo",
    (read_file(CHECKS_FILE) or ""):find("\t1\tidentify_replace\tDSC00001.JPG: reads entry 35, its tags name 112\t", 1, true) ~= nil, true)
local fix_button = widget_where(to_check, "button", "label", "Fix") or { clicked_callback = function() end }
check("To check: the differ row has a Fix button", fix_button.visible, true)
dt.database.get_image = function(id) return id == 1 and tagged or nil end
PYTHON.results, PYTHON.runs = "", {}
fix_button.clicked_callback()
dt.database.get_image = function() return nil end
local fix_run = PYTHON.runs[#PYTHON.runs]
check("To check: Fix starts Identify, not Verify", fix_run ~= nil and flag(fix_run.argv, "--verify") == nil
    and not table.concat(fix_run.argv, " "):find("--verify", 1, true), true)
check("To check: Fix runs with replace manual on",
    (read_file(ROOT .. "/config/assisted_tagging.log") or ""):find("settings: replace manual true", 1, true) ~= nil, true)
check("To check: Fix removes its row", (read_file(CHECKS_FILE) or ""):find("identify_replace", 1, true), nil)
local old_line = require("plugin_common").alerts_parse("Cull\tcouldn't rate\t4,5\n")[1] or { ids = {} }
check("To check: an old 3-field line still loads, with no fix", #old_line.ids .. "/" .. tostring(old_line.fix), "2/")
old_line = require("plugin_common").alerts_parse("Cull\tcouldn't rate\t4\tcull\n")[1] or { details = {} }
check("To check: a 4-field line loads its fix, no details", tostring(old_line.fix) .. "/" .. #(old_line.details or { 0 }), "cull/0")
local line = "Verify\tN photos\t1 2\tcolour_tag:1=Blue,2=Red\tA.JPG: one\31B.JPG: two\n"
line = require("plugin_common").alerts_format(require("plugin_common").alerts_parse(line))
check("To check: a fix argument and the photo list survive a save and load", line,
    "Verify\tN photos\t1,2\tcolour_tag:1=Blue,2=Red\tA.JPG: one\31B.JPG: two\n")

-- Verify's colour rows: photo 1 is tagged entry 112 (Pink in entries.json) and Colour|Red; it reads Blue
local blue = image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red" })
PYTHON.results, PYTHON.overturns, PYTHON.runs, prints = "1,0,number,112,,0.9,,solo,0,Blue,1,,0\n",
    "entry,stored,seen,n,total,ids\n112,Pink,Blue,1,1,1\n", {}, {}
;(widget_where(to_check, "button", "label", "Clear") or { clicked_callback = function() end }).clicked_callback()
T.identify_images({ blue }, false, true)
PYTHON.overturns = nil
local function row(i) return to_check[i + 1] or { {}, {}, { {}, {} } } end
local function label_of(i) return ((row(i)[1] or {}).label or ""):gsub("\n", " ") end
local function details_of(i) return ((row(i)[2] or {}).text or ""):gsub("\n%s*", " ") end
check("Verify colour: the entry colour row reads in full", label_of(1), "Verify: 1 photos read a different colour from their entry's in "
    .. "entries.json. The tag or the entry can be wrong. Fix adds the Check colour tag.")
check("Verify colour: the entry colour row lists the photo and why", details_of(1), "• DSC00001.JPG: reads Blue, entry 112 is Pink in entries.json")
check("Verify colour: the Colour tag row reads in full", label_of(2),
    "Verify: 1 photos' Colour tag differs from the colour read. Fix replaces the Colour tag with the colour read.")
check("Verify colour: the Colour tag row lists the photo and why", details_of(2), "• DSC00001.JPG: Colour tag Red, reads Blue")
check("Verify colour: the overturn row reads in full", label_of(3),
    "Verify: Entry 112 is Pink in entries.json, but 1 of its 1 photos read Blue. Fix sets its colour to Blue.")
check("Verify colour: the overturn row lists the photo", details_of(3), "• DSC00001.JPG: reads Blue")
check("Verify colour: every colour row has a Fix", tostring(row(1)[3][2].visible) .. tostring(row(2)[3][2].visible)
    .. tostring(row(3)[3][2].visible), "truetruetrue")
check("Verify colour: Verify changes no tag", #blue.tags, 2)

dt.database.get_image = function(id) return id == 1 and blue or nil end
local function has_tag(img, name)
    for _, t in ipairs(img.tags) do
        if t.name == name then return true end
    end
    return false
end
prints = {}
row(2)[3][2].clicked_callback()
check("Colour tag Fix: the Colour tag read replaces the old one",
    tostring(has_tag(blue, "Colour|Blue")) .. " " .. tostring(has_tag(blue, "Colour|Red")), "true false")
check("Colour tag Fix: the car tag stays", has_tag(blue, "Rallye|112"), true)
check("Colour tag Fix: its row is gone", (read_file(CHECKS_FILE) or ""):find("colour_tag", 1, true), nil)
row(1)[3][2].clicked_callback()
check("Check colour Fix: adds the Check colour tag", has_tag(blue, "Assisted Tagging|Identification|Check colour"), true)
check("Check colour Fix: the car tag stays", has_tag(blue, "Rallye|112"), true)
check("Check colour Fix: its row is gone", (read_file(CHECKS_FILE) or ""):find("check_colour", 1, true), nil)
PYTHON.results, PYTHON.runs = "1,added,set,112\n", {}
row(1)[3][2].clicked_callback()
check("Entry colour Fix: sends the colour read as the entry's colour", PYTHON.runs[1] and PYTHON.runs[1].manifest,
    T.csv_line({ 1, "/photos/DSC00001.JPG", "112", "Blue" }) .. "\n")
check("Entry colour Fix: its row is gone", (read_file(CHECKS_FILE) or ""):find("entry_colour", 1, true), nil)

-- a timeline: the newest run's items on top, older runs' below an "Earlier runs" line
;(widget_where(to_check, "button", "label", "Clear") or { clicked_callback = function() end }).clicked_callback()
PYTHON.results = "1,failed,,112\n"
fill({ image(1, "DSC00001.JPG", { "Rallye|112", "Colour|Red" }) })
check("timeline: one run's items have no Earlier runs line", row(1)[4] and row(1)[4].visible, false)
PYTHON.results, PYTHON.runs = "1,0,conflict,35,,0.9,,solo,0,,0,,0\n", {}
T.identify_images({ image(1, "DSC00001.JPG", { "Rallye|112" }) }, false, true)
check("timeline: the newest run's item comes first", label_of(1):match("^[^:]*"), "Verify")
check("timeline: the older run's item moves below it", label_of(2):match("^[^:]*"), "Fill entry colours")
check("timeline: an Earlier runs line sits under the newest run", row(1)[4] and row(1)[4].visible
    and row(1)[4].label:find("^Earlier runs %(before %d%d:%d%d%): may not hold any more$") ~= nil, true)
check("timeline: no Earlier runs line under the last item", row(2)[4] and row(2)[4].visible, false)
local saved = require("plugin_common").alerts_parse(read_file(CHECKS_FILE))
check("timeline: the saved list keeps the order and each run", #saved == 2 and saved[1].action .. ">" .. saved[2].action
    .. " " .. tostring(saved[1].run > saved[2].run), "Verify>Fill entry colours true")
dt.database.get_image = function() return nil end

-- the Unidentified tag goes once a later run finds the car, written by the plugin or not
local UNIDENTIFIED = "Assisted Tagging|Identification|Unidentified"
write_file(ROOT .. "/config/assisted_tagging/ledger.csv", (read_file(ROOT .. "/config/assisted_tagging/ledger.csv") or "")
    .. "5," .. UNIDENTIFIED .. "\n")
local hand_tagged = image(5, "DSC00005.JPG", { "Rallye|35", UNIDENTIFIED })
PYTHON.results = "5,-1,skipped,,,0.000,,,\n"
T.identify_images({ hand_tagged }, false, false)
check("stale Unidentified: a photo skipped as tagged by hand loses the earlier run's Unidentified tag",
    tostring(has_tag(hand_tagged, UNIDENTIFIED)) .. " " .. tostring(has_tag(hand_tagged, "Rallye|35")), "false true")
local unledgered = image(6, "DSC00006.JPG", { UNIDENTIFIED })
PYTHON.results = "6,0,number,35,,0.9,,solo,0,,0,,0\n"
T.identify_images({ unledgered }, false, false)
check("stale Unidentified: a photo identified now loses an Unidentified tag missing from the ledger",
    tostring(has_tag(unledgered, UNIDENTIFIED)) .. " " .. tostring(has_tag(unledgered, "Rallye|35")), "false true")
local held_photo = image(7, "DSC00007.JPG", { "Number|112", UNIDENTIFIED })
PYTHON.results = "7,0,conflict,35,,0.9,,solo,0,,0,,0\n"
T.identify_images({ held_photo }, false, false)
check("stale Unidentified: a photo whose hand tags name a car loses it", has_tag(held_photo, UNIDENTIFIED), false)
local still_unknown = image(8, "DSC00008.JPG", { UNIDENTIFIED })
PYTHON.results = "8,-1,no_vehicle,,,0.000,,,\n"
T.identify_images({ still_unknown }, false, false)
check("stale Unidentified: a hand Unidentified tag stays on a photo still unidentified", has_tag(still_unknown, UNIDENTIFIED), true)

-- Copy tags to group -----------------------------------------------------------------
-- a photo in a darktable group: its leader is the image with id `leader_id`
local grouped_by_id = {}
local function grouped(id, filename, tag_names, leader_id)
    local img = image(id, filename, tag_names)
    img.group = leader_id
    function img:get_group_members()
        local out = {}
        for _, other in pairs(grouped_by_id) do
            if other.group == self.group then out[#out + 1] = other end
        end
        table.sort(out, function(a, b) return a.id < b.id end)
        return out
    end
    grouped_by_id[id] = img
    return setmetatable(img, { __index = function(self, key)
        if key == "group_leader" then return grouped_by_id[self.group] end end })
end
local copy_button = widget_where(panel, "button", "label", "Copy tags to group")
local copy_confirm = widget_where(panel, "button", "label", "Merge and copy")
local CHECK_COLOUR = "Assisted Tagging|Identification|Check colour"
local function tag_list(img)
    local out = {}
    for _, t in ipairs(img.tags) do out[#out + 1] = t.name end
    table.sort(out)
    return table.concat(out, ", ")
end
local function ledger_rows_for(id)
    local n = 0
    for line in (read_file(ROOT .. "/config/assisted_tagging/ledger.csv") or ""):gmatch("[^\n]+") do
        -- `lib,id,tag`, or `id,tag` from before the library column
        if (line:match("^[^,]*,(%d+),") or line:match("^(%d+),")) == tostring(id) then n = n + 1 end
    end
    return n
end

local source = grouped(101, "DSC00101.JPG", { "Rallye|112", "Colour|Red", "Number|112" }, 101)
local member = grouped(102, "DSC00102.JPG", { "Rallye|35", "Colour|Blue", "Number|35", CHECK_COLOUR, "Hand|Tag" }, 101)
local bare = grouped(103, "DSC00103.JPG", {}, 101)
local other_source = grouped(201, "DSC00201.JPG", { "Rallye|35", "Colour|Blue" }, 201)
local other_member = grouped(202, "DSC00202.JPG", { "Number|7" }, 201)
write_file(ROOT .. "/config/assisted_tagging/ledger.csv", "102,Rallye|35\n102,Colour|Blue\n")
prints, dt.gui.action_images = {}, { source, other_source }
check("copy to group: the button is on the panel", copy_button ~= nil, true)
;(copy_button or { clicked_callback = function() end }).clicked_callback()
check("copy to group: the source's tags replace the member's entry and family tags", tag_list(member),
    "Assisted Tagging|Identification|Check colour, Colour|Red, Hand|Tag, Number|112, Rallye|112")
check("copy to group: a member with no tags gets them all", tag_list(bare), "Colour|Red, Number|112, Rallye|112")
check("copy to group: the source keeps its tags", tag_list(source), "Colour|Red, Number|112, Rallye|112")
check("copy to group, two groups: the second group copies its own source", tag_list(other_member), "Colour|Blue, Rallye|35")
check("copy to group, two groups: no tag crosses between groups",
    tostring(has_tag(other_member, "Rallye|112")) .. " " .. tostring(has_tag(bare, "Rallye|35")), "false false")
check("copy to group: the copies are the user's, the ledger has no row for them",
    ledger_rows_for(101) + ledger_rows_for(102) + ledger_rows_for(103) + ledger_rows_for(202), 0)
check("copy to group: the end message", printed("Assisted Tagging: Copy tags to group done"), true)

PYTHON.results, PYTHON.runs = "102,0,number,35,,0.9,,solo,0,,0,,0\n", {}
T.identify_images({ member }, false, false)
check("copy to group: Identify reading another car keeps the copied tags",
    tostring(has_tag(member, "Rallye|112")) .. " " .. tostring(has_tag(member, "Colour|Red")), "true true")

local differ_a = grouped(301, "DSC00301.JPG", { "Rallye|112", "Colour|Red" }, 301)
local differ_b = grouped(302, "DSC00302.JPG", { "Number|112" }, 301)
local differ_c = grouped(303, "DSC00303.JPG", { "Colour|Blue" }, 301)
prints, dt.gui.action_images = {}, { differ_a, differ_b }
;(copy_button or { clicked_callback = function() end }).clicked_callback()
local confirm_box
local function find_confirm(widget)
    for _, child in ipairs(widget) do
        if type(child) == "table" then
            if child.kind == "box" and widget_where(child, "button", "label", "Merge and copy") and child.visible ~= nil then
                confirm_box = child
            end
            find_confirm(child)
        end
    end
end
find_confirm(panel)
check("copy to group, selected photos differ: the confirm box shows", confirm_box and confirm_box.visible, true)
check("copy to group, selected photos differ: the confirm names the count",
    confirm_box and confirm_box[1].label:gsub("\n", " "),
    "The selected photos in 1 groups have different tags. Copy merges them: every photo in those groups gets all of their tags.")
check("copy to group, selected photos differ: nothing is written before the confirm", tag_list(differ_c), "Colour|Blue")
;(copy_confirm or { clicked_callback = function() end }).clicked_callback()
check("copy to group, Merge and copy: every photo gets the merged tags",
    tag_list(differ_a) .. " / " .. tag_list(differ_b) .. " / " .. tag_list(differ_c),
    "Colour|Red, Number|112, Rallye|112 / Colour|Red, Number|112, Rallye|112 / Colour|Red, Number|112, Rallye|112")
check("copy to group, Merge and copy: the confirm box hides", confirm_box and confirm_box.visible, false)
dt.gui.action_images = {}

-- Picks a menu entry by its text, as a click in darktable does.
local function choose(combo, text)
    for i = 1, #combo do
        if combo[i] == text then
            combo.selected, combo.value = i, text
            combo.changed_callback(combo)
            return true
        end
    end
    return false
end

local actions = widget_where(panel, "combobox", "label", "actions")
local out = ROOT .. "/export"
make_dir(out)
check("presets: export is offered for the Rallye collection", choose(actions, "export preset…"), true)
widget_where(panel, "file_chooser_button", "title", "folder to export the preset into").value = out
prints = {}
widget_where(panel, "button", "label", "Export").clicked_callback()
check("presets: export toast", last_print():find('preset "Rallye" exported to ' .. out .. "/Rallye.atpreset", 1, true) ~= nil, true)
check("presets: the bundle carries the entry list", read_file(out .. "/Rallye.atpreset/entries.json"), "[]")
check("presets: the bundle carries the settings", read_file(out .. "/Rallye.atpreset/preset.json") ~= nil, true)
check("presets: the manifest lists both files",
    (read_file(out .. "/Rallye.atpreset/manifest.json") or ""):find('"files": "preset.json,entries.json"', 1, true) ~= nil, true)
check("presets: unticked references stay behind", read_file(out .. "/Rallye.atpreset/refs/sources.json"), nil)

-- references, ticked: refs/ goes whole, index.npz beside it stays behind
local refs_out = ROOT .. "/export-refs"
make_dir(refs_out)
choose(actions, "export preset…")
local refs_box = widget_where(panel, "check_button", "tooltip", "Also export refs/ (the reference crops and sources.json). They go out as full JPG crops of your photos: in a people collection they are face photos. Run caches and refs-quarantine never go.")
check("presets: the references box shows the size", refs_box.label:match("^references %(2 files, ") ~= nil, true)
refs_box.value = true
widget_where(panel, "file_chooser_button", "title", "folder to export the preset into").value = refs_out
widget_where(panel, "button", "label", "Export").clicked_callback()
check("presets: ticked references are exported", read_file(refs_out .. "/Rallye.atpreset/refs/112/1_b0.jpg"), "crop")
check("presets: sources.json goes with them", read_file(refs_out .. "/Rallye.atpreset/refs/sources.json"), "{}")
check("presets: index.npz stays behind", read_file(refs_out .. "/Rallye.atpreset/index.npz"), nil)
check("presets: the manifest lists refs",
    (read_file(refs_out .. "/Rallye.atpreset/manifest.json") or ""):find('"files": "preset.json,entries.json,refs"', 1, true) ~= nil, true)
choose(actions, "export preset…")
check("presets: the references box is unticked when export opens again", refs_box.value, false)

check("presets: import is offered", choose(actions, "import preset…"), true)
widget_where(panel, "file_chooser_button", "title", "preset bundle (.atpreset folder)").value = out .. "/Rallye.atpreset"
write_file(out .. "/Rallye.atpreset/entries.json", '[{"entry": "112"}]')
prints = {}
widget_where(panel, "button", "label", "Import").clicked_callback()
check("presets: import adds Rallye (2)", last_print():find('imported "Rallye (2)"', 1, true) ~= nil, true)
check("presets: Rallye (2) holds the bundle's entry list", read_file(ROOT .. "/collections/Rallye (2)/entries.json"), '[{"entry": "112"}]')
check("presets: Rallye (2) holds the settings", read_file(ROOT .. "/collections/Rallye (2)/settings.json") ~= nil, true)
check("presets: Rallye keeps its own entry list", read_file(ROOT .. "/collections/Rallye/entries.json"), "[]")
check("presets: a bundle without refs imports none", read_file(ROOT .. "/collections/Rallye (2)/refs/sources.json"), nil)

choose(actions, "import preset…")
widget_where(panel, "file_chooser_button", "title", "preset bundle (.atpreset folder)").value = refs_out .. "/Rallye.atpreset"
prints = {}
widget_where(panel, "button", "label", "Import").clicked_callback()
check("presets: the refs bundle imports as Rallye (3)", last_print():find('imported "Rallye (3)"', 1, true) ~= nil, true)
check("presets: Rallye (3) holds the references", read_file(ROOT .. "/collections/Rallye (3)/refs/112/1_b0.jpg"), "crop")
check("presets: Rallye (3) holds sources.json", read_file(ROOT .. "/collections/Rallye (3)/refs/sources.json"), "{}")

write_file(out .. "/Rallye.atpreset/manifest.json",
    '{"version": 1, "plugin": "assisted_tagging", "preset": "Hill", "files": "preset.json"}')
widget_where(panel, "file_chooser_button", "title", "preset bundle (.atpreset folder)").value = out .. "/Rallye.atpreset"
prints = {}
widget_where(panel, "button", "label", "Import").clicked_callback()
check("presets: a bundle without entries.json is refused", last_print():find("the bundle has no entries.json", 1, true) ~= nil, true)
check("presets: the refused import leaves no folder", read_file(ROOT .. "/collections/Hill/settings.json"), nil)

check("the buttons leave no Lua error", read_file(ROOT .. "/config/assisted_tagging.lua.log"), nil)

real_execute(WINDOWS and ('rmdir /s /q "' .. ROOT:gsub("/", "\\") .. '"') or ("rm -rf '" .. ROOT .. "'"))

print("")
if failures == 0 then
    print("all tests passed")
    os.exit(0)
else
    print(failures .. " test(s) failed")
    os.exit(1)
end
