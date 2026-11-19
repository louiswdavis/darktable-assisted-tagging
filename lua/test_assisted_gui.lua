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
