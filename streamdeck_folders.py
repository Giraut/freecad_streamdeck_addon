"""FreeCAD Stream Deck Addon - Folder-style Stream Deck pages

The toolbars are presented like folders, which suits Stream Decks with few
keys. There are four levels, and the top-left key always goes up one level:

  - The workbench list - the home level - shows one key per workbench, in the
    order FreeCAD shows them. Picking one activates it and opens its page.
    Without the workbench list (WorkbenchSwitcher off), the workbench page is
    the home level
  - The workbench page shows the tools of the toolbars to show on every page,
    then one folder key per remaining toolbar, the current workbench's
    toolbars first. Its first key, labelled with the name of the workbench,
    goes up to the workbench list
  - Pressing a folder key opens the toolbar: the first key goes back to the
    workbench page and the other keys are the toolbar's tools
  - Long-pressing a tool that has a menu pops the menu up over the toolbar:
    the tool stays as it is, the menu items take the keys after it - and
    before it if needed - and the rest of the toolbar is faded. Picking an
    item applies it and closes the menu. Pressing the tool or a faded key
    closes the menu

When a toolbar, menu or the home page has more entries than fit on one page,
the last two keys of each page become previous / next page keys. On a Stream
Deck with dials, the dials turn the pages instead.

Instead of brackets, the keys carry small marks in a corner: a triangle on the
tools that have a menu to open with a long press, and a folder on toolbar keys
placed inside another folder. The home page shows only folders, so its toolbar
keys have no mark. The navigation keys have no mark either: their arrows say
what they do.

The pages are described with strings shaped like those of StreamDeckPages, so
the same code can display either: one string per page, made of one string per
key separated by SK, each made of the following fields separated by SV:

  <marker>SV<command>SV<enabled>SV<iconid>SV<toptext>SV<bottomtext>SV
	<mark>SV<markcolor>

where command is either an action name, "" for a blank key, one of PAGEPREV,
PAGENEXT, PAGEBACK or WORKBENCH_LIST - the key going up from the workbench page
to the workbench list -, OPEN_PREFIX followed by a toolbar name, or
CLOSE_PREFIX followed by any of those, for the keys that close a menu. Enabled is "0"
for a disabled action or an unavailable page key. Mark is "", MARK_MENU or
MARK_FOLDER, in the last two fields where StreamDeckPages has bracket colors.

Each level has its own key background color, so it's clear at a glance where
you are: the workbench list, a workbench page, a toolbar or a menu. Only the
keys that belong to the level - workbenches, toolbar folders, tools, menu
items - and its previous / next page keys get it: the key going up a level and
the empty keys stay black. The marker
field identifies the level and ends with the key's background color after
BG_SEP, so any change of level or of color changes the key strings and the keys
get redrawn.
"""

## Classes
#

class StreamDeckFolders():

  # Key and variable separators for page strings, same as in StreamDeckPages
  SK = "\x1d"
  SV = "\x1e"

  # Commands of the navigation keys
  PAGEPREV = "PAGEPREV"
  PAGENEXT = "PAGENEXT"
  PAGEBACK = "PAGEBACK"
  WORKBENCH_LIST = "WORKBENCH"
  OPEN_PREFIX = "OPEN\x1f"
  CLOSE_PREFIX = "CLOSE\x1f"	# Followed by the original command: a key of
				# the page under a menu, which closes the menu

  # Key marks, same values as StreamDeck.MARK_MENU and StreamDeck.MARK_FOLDER
  MARK_MENU = "menu"
  MARK_FOLDER = "folder"

  # Workbench pseudo-toolbar, same value as gui_actions.WORKBENCH_TOOLBAR
  WORKBENCH_TOOLBAR = "StreamDeckAddon_Workbenches"

  # Levels, top to bottom. WORKBENCHES is the workbench list, HOME the page of
  # the active workbench with its toolbar folders
  WORKBENCHES = "workbenches"
  HOME = "home"
  TOOLBAR = "toolbar"
  MENU = "menu"

  # Separator between the level and the background color in the marker field
  BG_SEP = "@"

  # FreeCAD's standard toolbars, shown on the workbench page after the current
  # workbench's own toolbars
  STANDARD_TOOLBARS = ("File", "Edit", "Clipboard", "Workbench", "Macro",
			"View", "Individual views", "Structure", "Help",
			"Navigation", "Measure")



  def __init__(self, nb_streamdeck_keys, with_nav_keys):
    """__init__ method
    """

    self.nb_streamdeck_keys = nb_streamdeck_keys
    self.with_nav_keys = with_nav_keys

    self.tbactions = None
    self.repeated_toolbars = []
    self.menu_mark_color = ""
    self.folder_mark_color = ""

    # Key background color of each level, and of the current page
    self.level_colors = {self.WORKBENCHES: "", self.HOME: "", self.TOOLBAR: "",
				self.MENU: ""}
    self.background = ""

    # Navigation stack: list of [level, key, page number], top level first.
    # The workbench list is added at the bottom once we know it exists, so we
    # start on the workbench page
    self.stack = [[self.HOME, None, 0]]

    self.current_page = None
    self.current_page_no = None
    self.nb_pages = None



  @property
  def in_menu(self):
    """Whether a menu is currently open
    """

    return self.stack[-1][0] == self.MENU



  @property
  def has_workbench_list(self):
    """Whether the workbench list exists, as the top level
    """

    return self.tbactions is not None and \
		self.WORKBENCH_TOOLBAR in self.tbactions.toolbars and \
		bool(self.tbactions.toolbar_actions.get(self.WORKBENCH_TOOLBAR))



  def rebuild(self, tbactions, repeated_toolbars,
		mark_color_menu_tools,
		mark_color_nested_folders,
		go_home = False,
		home_color = "", toolbar_color = "", menu_color = "",
		workbenches_color = ""):
    """Rebuild the current page given a list of toolbars and actions passed as
    a ToolbarActions object, the colors of the marks and the key background
    colors of the workbench page - home_color -, the toolbar pages, the menu
    pages and the workbench list
    If go_home is asserted, go to the workbench page - new toolbars appeared.
    Otherwise stay at the same place if it still exists, or the nearest place
    up that does
    Return True if the current page changed
    """

    self.tbactions = tbactions
    self.repeated_toolbars = [t for t in repeated_toolbars if t]
    self.menu_mark_color = mark_color_menu_tools.strip().lower()
    self.folder_mark_color = mark_color_nested_folders.strip().lower()
    self.level_colors = {self.WORKBENCHES: workbenches_color.strip().lower(),
			self.HOME: home_color.strip().lower(),
			self.TOOLBAR: toolbar_color.strip().lower(),
			self.MENU: menu_color.strip().lower()}

    if go_home:
      return self.show_workbench()

    return self._compose()



  def open_toolbar(self, toolbar):
    """Open a toolbar from the workbench page
    Return True if the current page changed
    """

    if self.tbactions is None or \
		not self.tbactions.toolbar_actions.get(toolbar):
      return False

    self._cut_to_workbench_page()
    self.stack.append([self.TOOLBAR, toolbar, 0])
    return self._compose()



  def open_menu(self, action_name):
    """Open the menu of an action
    Return True if the current page changed
    """

    if self.tbactions is None or \
		not self.tbactions.subactions.get(action_name):
      return False

    # Don't stack a menu on top of another menu
    if self.in_menu:
      self.stack.pop()

    self.stack.append([self.MENU, action_name, 0])
    return self._compose()



  def go_back(self):
    """Go up one level
    Return True if the current page changed
    """

    if len(self.stack) <= 1:
      return False

    self.stack.pop()
    return self._compose()



  def go_home(self):
    """Long press on the top-left key: go straight back to the workbench page
    from a toolbar or a menu, or up to the workbench list from the workbench
    page
    Return True if the current page changed
    """

    if self.stack[-1][0] in (self.TOOLBAR, self.MENU):
      return self.show_workbench()

    return self.go_back()



  def show_workbench(self, first_page = False):
    """Show the page of the active workbench, below the workbench list: after
    picking a workbench, or when new toolbars appear. If first_page is
    asserted, show its first page
    Return True if the current page changed
    """

    self._cut_to_workbench_page()
    if first_page:
      self.stack[-1][2] = 0

    return self._compose()



  def _cut_to_workbench_page(self):
    """Make the workbench page the current level, keeping the levels above it
    """

    for i, frame in enumerate(self.stack):
      if frame[0] == self.HOME:
        del self.stack[i + 1:]
        return

    self.stack.append([self.HOME, None, 0])



  def flip(self, nbpages):
    """Jump nbpages pages within the current level: before the current page if
    nbpages <0, after if nbpages >0
    Return True if the page was changed
    """

    if self.current_page_no is None:
      return False

    new_page_no = min(self.nb_pages - 1,
			max(0, self.current_page_no + nbpages))

    if new_page_no == self.current_page_no:
      return False

    self.stack[-1][2] = new_page_no
    return self._compose()



  def _is_valid(self, frame):
    """Whether a level of the navigation stack still exists
    """

    level, key, _ = frame
    tba = self.tbactions

    if level == self.WORKBENCHES:
      return self.has_workbench_list

    if level == self.HOME:
      return True

    if level == self.TOOLBAR:
      return key in tba.toolbars and bool(tba.toolbar_actions.get(key))

    if level == self.MENU:
      return bool(tba.subactions.get(key)) and key in tba.actions

    return False



  def _marker(self, frame, colored = True):
    """Marker field of the keys of a level: the level - and the toolbar or the
    action whose menu it is - then the level's background color if colored is
    asserted - the keys that belong to the level and its page keys -, or no
    color - the key going up a level and the empty keys
    """

    level, key, _ = frame
    where = level if key is None else "{}:{}".format(level, key)

    return where + self.BG_SEP + \
		(self.level_colors.get(level, "") if colored else "")



  def _key(self, marker, command = "", enabled = "", iconid = "",
		top_text = "", bottom_text = "", mark = "", mark_color = ""):
    """Compose a key string
    """

    return self.SV.join([marker, command, enabled, str(iconid), top_text,
				bottom_text, mark, mark_color])



  def _tool_key(self, marker, n):
    """Compose the key string of a tool. Tools with a menu to open with a long
    press get the menu mark
    """

    a = self.tbactions.actions[n]
    has_menu = bool(self.tbactions.subactions.get(n))

    return self._key(marker, n, "1" if a.enabled else "0", a.iconid, "",
			a.title, self.MARK_MENU if has_menu else "",
			self.menu_mark_color if has_menu else "")



  def _folder_key(self, marker, t, nested = False):
    """Compose the key string of a toolbar folder, showing the toolbar's title
    and the icon of its first tool. A folder placed inside another folder -
    nested - gets the folder mark, to tell it apart from the tools around it.
    On the workbench page, which shows only folders, it doesn't need one
    """

    tba = self.tbactions
    iconid = tba.actions[tba.toolbar_actions[t][0]].iconid

    return self._key(marker, self.OPEN_PREFIX + t, "1", iconid, "",
			tba.toolbar_short_titles.get(t, t),
			self.MARK_FOLDER if nested else "",
			self.folder_mark_color if nested else "")



  def _level_title(self, frame):
    """Title of a level, shown on the back key
    """

    level, key, _ = frame

    if level == self.TOOLBAR:
      return self.tbactions.toolbar_short_titles.get(key, key)

    if level == self.MENU:
      return self.tbactions.actions[key].title

    return ""



  def home_toolbars(self):
    """Return the toolbars shown as folders on the workbench page, in order:
    all the toolbars that have tools except those shown on every page and the
    workbench list, the current workbench's toolbars first, then FreeCAD's
    standard toolbars
    """

    tba = self.tbactions

    folders = [t for t in tba.toolbars \
		if t not in self.repeated_toolbars and \
			t != self.WORKBENCH_TOOLBAR and tba.toolbar_actions.get(t)]
    folders.sort(key = lambda t: t in self.STANDARD_TOOLBARS)

    return folders



  def _entries(self, frame):
    """Return the key strings of all the entries of a level, without the
    navigation keys
    """

    level, key, _ = frame
    tba = self.tbactions
    marker = self._marker(frame)

    if level == self.WORKBENCHES:
      return [self._tool_key(marker, n) \
		for n in tba.toolbar_actions[self.WORKBENCH_TOOLBAR]]

    if level == self.HOME:
      entries = []
      for t in self.repeated_toolbars:
        if t in tba.toolbars:
          entries.extend([self._tool_key(marker, n) \
				for n in tba.toolbar_actions.get(t, [])])
      entries.extend([self._folder_key(marker, t, nested = False) \
				for t in self.home_toolbars()])
      return entries

    if level == self.TOOLBAR:
      return [self._tool_key(marker, n) for n in tba.toolbar_actions[key]]

    if level == self.MENU:
      return [self._tool_key(marker, n) for n in tba.subactions[key]]

    return []



  def _compose(self):
    """Compose the current page string from the current place in the
    navigation stack
    Return True if the current page changed
    """

    previous_page = self.current_page

    if self.tbactions is None:
      self.current_page = None
      self.current_page_no = None
      self.nb_pages = None
      return previous_page is not None

    # The workbench list is the top level when it exists. Add it or remove it
    # if it appeared or disappeared - WorkbenchSwitcher turned on or off
    if self.has_workbench_list and self.stack[0][0] != self.WORKBENCHES:
      self.stack.insert(0, [self.WORKBENCHES, None, 0])
    elif not self.has_workbench_list and self.stack[0][0] == self.WORKBENCHES:
      del self.stack[0]
      if not self.stack:
        self.stack = [[self.HOME, None, 0]]

    # Drop the levels that don't exist anymore, and the levels below them
    for i, frame in enumerate(self.stack):
      if not self._is_valid(frame):
        del self.stack[i:]
        break

    frame = self.stack[-1]
    level = frame[0]
    self.background = self.level_colors.get(level, "")

    # A menu pops up over the page of the tool it belongs to. Anything else is
    # a page of its own
    if level == self.MENU and len(self.stack) >= 2:
      keys, self.nb_pages, page_no = self._popup_keys(self.stack[-2], frame)
    else:
      keys, self.nb_pages, page_no = self._page_keys(frame,
							len(self.stack) > 1)

    frame[2] = self.current_page_no = page_no
    self.current_page = self.SK.join(keys)

    return self.current_page != previous_page



  def _page_keys(self, frame, below_top):
    """Return the key strings of the current page of a level - frame - the
    number of pages of the level and the current page number. below_top says
    whether the level has a level above it
    """

    level = frame[0]
    entries = self._entries(frame)

    # The key going up a level and the empty keys have no background color.
    # The page keys turn the pages of the level, so they take its color
    marker = self._marker(frame, colored = False)
    page_marker = self._marker(frame)

    # How many keys can show entries? The top-left key goes up one level on all
    # levels but the top one. On the workbench list, it stays as a "Workbench"
    # key that does nothing, so pressing the top-left key again and again
    # always ends on the workbench list rather than picking a workbench
    with_back_key = below_top or level == self.WORKBENCHES
    nb_slots = self.nb_streamdeck_keys - (1 if with_back_key else 0)

    # Do we need page keys? If so, they take the last two keys of each page
    with_page_keys = self.with_nav_keys and len(entries) > nb_slots and \
			nb_slots >= 3
    nb_per_page = max(1, nb_slots - (2 if with_page_keys else 0))

    nb_pages = max(1, (len(entries) + nb_per_page - 1) // nb_per_page)
    page_no = min(max(0, frame[2]), nb_pages - 1)

    page_indicator = "{}/{}".format(page_no + 1, nb_pages) \
			if nb_pages > 1 else ""

    keys = []

    # Back key: shows where we are, plus the page number if there are no page
    # keys to show it. On the workbench page, it's the key going up to the
    # workbench list, with the icon and the name of the workbench. On the
    # workbench list, the same key does nothing: workbench grid icon, in color,
    # labelled "Workbench"
    if with_back_key:
      tba = self.tbactions
      if level == self.HOME:
        a = tba.actions.get(tba.active_workbench_action or "")
        keys.append(self._key(marker, self.WORKBENCH_LIST, "1",
				a.iconid if a is not None else "",
				"" if with_page_keys else page_indicator,
				tba.active_workbench_title or "Workbench"))
      elif level == self.WORKBENCHES:
        keys.append(self._key(marker, self.WORKBENCH_LIST, "0", "",
				"" if with_page_keys else page_indicator,
				tba.toolbar_short_titles.get(self.WORKBENCH_TOOLBAR,
								"Workbench")))
      else:
        keys.append(self._key(marker, self.PAGEBACK, "1", "",
				"" if with_page_keys else page_indicator,
				self._level_title(frame)))

    keys.extend(entries[page_no * nb_per_page:(page_no + 1) * nb_per_page])

    # Blank keys to fill up the page
    keys.extend([self._key(marker)] * (self.nb_streamdeck_keys - len(keys) - \
					(2 if with_page_keys else 0)))

    # Page keys, in the level's color, dimmed when there's no page in that
    # direction. The next page key shows the page number
    if with_page_keys:
      keys.append(self._key(page_marker, self.PAGEPREV,
				"1" if page_no > 0 else "0"))
      keys.append(self._key(page_marker, self.PAGENEXT,
				"1" if page_no < nb_pages - 1 else "0", "",
				"", page_indicator))

    return keys, nb_pages, page_no



  def _popup_keys(self, parent, frame):
    """Return the key strings of a menu popping up over the page of the tool it
    belongs to - parent -, the number of pages of the menu and its current page
    number:
      - The tool stays where it is, as it is: in its own color, not faded
      - The menu items take the keys after the tool and, if they run out, as
        many keys just before it as needed - in reading order -, in the
        menu's color
      - The rest of the page stays visible, faded. Pressing one of its keys, or
        the tool, closes the menu: there is no back key
      - A menu with more items than keys gets its own previous / next page
        keys, the last two keys of the page, in the menu's color. On a Stream
        Deck with dials, the dials turn its pages and the page number shows on
        the tool
    """

    nbkeys = self.nb_streamdeck_keys
    under, _, _ = self._page_keys(parent, self.stack.index(parent) > 0)
    items = self._entries(frame)
    marker = self._marker(frame)	# The menu's color

    # Where's the tool on the page? If it isn't there - another page - the
    # menu starts at the first key
    anchor = None
    for i, ks in enumerate(under):
      if ks.split(self.SV)[1] == frame[1]:
        anchor = i
        break
    a = -1 if anchor is None else anchor

    # Keys the menu can use: after the tool, and before it
    after = [k for k in range(nbkeys) if k > a]
    before = [k for k in range(nbkeys) if k < a]

    # Page keys - the last two keys the menu can use - if the menu doesn't fit
    nb_free = len(after) + len(before)
    with_page_keys = self.with_nav_keys and len(items) > nb_free and \
			nb_free >= 3
    page_keys = sorted(after + before)[-2:] if with_page_keys else []
    after = [k for k in after if k not in page_keys]
    before = [k for k in before if k not in page_keys]

    nb_per_page = max(1, len(after) + len(before))
    nb_pages = max(1, (len(items) + nb_per_page - 1) // nb_per_page)
    page_no = min(max(0, frame[2]), nb_pages - 1)
    page_indicator = "{}/{}".format(page_no + 1, nb_pages) \
			if nb_pages > 1 else ""
    page_items = items[page_no * nb_per_page:(page_no + 1) * nb_per_page]

    # The items go after the tool first, then on the keys just before it
    nb_before = max(0, len(page_items) - len(after))
    slots = after[:len(page_items)] + before[len(before) - nb_before:]

    # Fade the page underneath: its keys close the menu
    keys = [self._faded(ks) for ks in under]

    # The tool stays as it is - its own color, not faded - so it stands out
    # from the faded keys and from the menu items. It closes the menu too
    if anchor is not None:
      f = under[anchor].split(self.SV)
      f[1] = self.CLOSE_PREFIX + f[1]
      f[2] = "1"
      if nb_pages > 1 and not with_page_keys:
        f[4] = page_indicator
      keys[anchor] = self.SV.join(f)

    # The menu items
    for k, item in zip(slots, page_items):
      keys[k] = item

    # The menu's page keys
    if with_page_keys:
      keys[page_keys[0]] = self._key(marker, self.PAGEPREV,
					"1" if page_no > 0 else "0")
      keys[page_keys[1]] = self._key(marker, self.PAGENEXT,
					"1" if page_no < nb_pages - 1 else "0",
					"", "", page_indicator)

    return keys, nb_pages, page_no



  def _faded(self, key_string):
    """Return the faded version of a key string from the page under a menu: its
    command becomes CLOSE_PREFIX followed by the original command - pressing it
    closes the menu - and it shows disabled
    """

    f = key_string.split(self.SV)
    f[1] = self.CLOSE_PREFIX + f[1]
    f[2] = "0"

    return self.SV.join(f)
