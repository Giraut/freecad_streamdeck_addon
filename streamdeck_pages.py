"""FreeCAD Stream Deck Addon - Stream Deck pages class
"""

## Modules
#

import re



## Classes
#

class StreamDeckPages():

  def __init__(self, toolbars_on_every_streamdeck_page,
		brackets_color_for_toolbars_on_every_streamdeck_page,
		brackets_color_for_streamdeck_page_navigation_keys,
		brackets_color_for_expandable_tool_buttons,
		nb_streamdeck_keys):
    """__init__ method
    """

    self.toolbars_on_every_streamdeck_page = toolbars_on_every_streamdeck_page

    self.ptbc = brackets_color_for_toolbars_on_every_streamdeck_page
    self.nkbc = brackets_color_for_streamdeck_page_navigation_keys
    self.exbc = brackets_color_for_expandable_tool_buttons

    self.nb_streamdeck_keys = nb_streamdeck_keys

    self.previous_pages = []
    self.pages = []

    self.previous_current_page = None
    self.current_page = None
    self.current_page_no = None



  def rebuild_pages(self, tbactions):
    """Rebuild Stream Deck pages given a list of toolbars and actions passed as
    a ToolbarActions object
    """

    # Compose the new pages to display on the Stream Deck: the pages are
    # described in a multiline string with each line in the following format:
    #
    # <key0>;<key1>;...;<keyN>
    #
    # and each key is composed of:
    # <toolbarmarker>~[action]~[0|1]~[iconid]~[toptext]~[bottomtext]~
    #    [leftbracketcolor]~[rightbracketcolor]
    #

    # Create a pattern of one or more pages (hopefully just one) that contain
    # the keys for the actions of the toolbars that should be repeated on
    # every page at the beginning, the page navigation keys at the end and
    # at least one free key slot in-between.
    keys = []
    for t in self.toolbars_on_every_streamdeck_page:
      if t in tbactions.toolbars:
        last_action_i = len(tbactions.toolbar_actions[t]) - 1
        keys.extend(["[toolbar]~{}~{}~{}~{}~{}~{}~{}".
		format(n, 1 if tbactions.actions[n].enabled else 0,
			tbactions.actions[n].iconid,
			tbactions.actions[n].title, t,
			self.ptbc if i == 0 else \
			self.exbc if n in tbactions.expanded_actions else \
			"",
			self.ptbc if i == last_action_i else \
			self.exbc if \
				not tbactions.expanded_actions.get(n, True) or \
				tbactions.actions[n].islastsubaction else \
			"")
		for i, n in enumerate(tbactions.toolbar_actions[t])])
    nbkeys = len(keys)

    empty_new_pages = []
    while nbkeys > self.nb_streamdeck_keys - 3:	# The last page of the new empty
						# pages should have 2 slots left
						# for the page navigation keys
						# and 1 empty slot
      empty_new_pages.append(";".join(keys[:self.nb_streamdeck_keys - 2]) + \
				";[pageprev];[pagenext]")
      keys = keys[self.nb_streamdeck_keys - 2:]
      nbkeys -= self.nb_streamdeck_keys - 2

    empty_new_pages.append(";".join(keys) + \
				(";" if keys and \
					(self.nb_streamdeck_keys - nbkeys - 2) \
					else "") + \
				";".join(["[key]" for _ in \
				range(self.nb_streamdeck_keys - nbkeys - 2)]) \
				+ ";[pageprev];[pagenext]")

    last_empty_new_page_i = len(empty_new_pages) - 1

    # Create the pages of action keys
    self.previous_pages = self.pages
    self.pages = []
    prev_page_toolbar = None

    indiv_toolbar_page_maker_ctr = 0
    page_marker = lambda: "{}#{}".format(t, indiv_toolbar_page_maker_ctr)

    for t in tbactions.toolbars:
      if t not in self.toolbars_on_every_streamdeck_page:

        # Get the list of key strings for this toolbar
        keys = ["{}~{}~{}~{}~{}~{}~{}~{}".
		format(t, n, 1 if tbactions.actions[n].enabled else 0,
			tbactions.actions[n].iconid,
			tbactions.actions[n].title, t,
			self.exbc if n in tbactions.expanded_actions else "",
			self.exbc if \
				not tbactions.expanded_actions.get(n, True) or \
				tbactions.actions[n].islastsubaction else \
			"")
		for n in tbactions.toolbar_actions[t]]

        indiv_toolbar_page_maker_ctr = 0

        # Add all the keys to the pages
        for key in keys:

          # If we don't have empty key slots left, add empty pages
          if not self.pages or "[key]" not in self.pages[-1]:

            # Replace the previous page's [pagenext] placeholder, if any
            if self.pages:
              self.pages[-1] = self.pages[-1].replace("[pagenext]",
							"{}~PAGENEXT~~~~{}~~{}".
							format(page_marker(), t,
								self.nkbc))

            # Add new pages. Mark all the new pages' keys with a unique page
            # marker.
            for i, p in enumerate(empty_new_pages):

              indiv_toolbar_page_maker_ctr += 1

              new_page = p.replace("[toolbar]", page_marker())

              # If we have more than one new page, replace the [pagenext]
              # placeholder in all but the last new page
              if i < last_empty_new_page_i:
                new_page = new_page.replace("[pagenext]",
						"{}~PAGENEXT~~~~{}~~{}".
						format(page_marker(), t,
							self.nkbc))

              # Replace the first [pageprev] placeholder
              if i == 0:
                new_page = new_page.replace("[pageprev]",
						"{}~PAGEPREV~~~~{}~{}~".
						format(page_marker(),
							prev_page_toolbar,
							self.nkbc) \
						if prev_page_toolbar else \
						"{}~~~~~~{}~".
						format(page_marker(),
							self.nkbc), 1)

              # Replace the remaining [pageprev] placeholders if any
              else:
                new_page = new_page.replace("[pageprev]",
						"{}~PAGEPREV~~~~{}~{}~".
						format(page_marker(), t,
							self.nkbc))

              # Add the new page to the pages
              self.pages.append(new_page)

            prev_page_toolbar = t

          # Insert the next key into the pages
          self.pages[-1] = self.pages[-1].replace("[key]", key, 1)

        # Add blank keys to complete the last page for this toolbar
        self.pages[-1] = self.pages[-1].replace("[key]", "{}~~~~~~~".
						format(page_marker()))

    # Replace the last [pagenext] placeholder if any
    if self.pages:
      self.pages[-1] = self.pages[-1].replace("[pagenext]", "{}~~~~~~~{}".
						format(page_marker(),
							self.nkbc))



  def locate_current_page(self, new_toolbar = None, last_action_pressed = None):
    """Find the new location of the current page by finding the page in the
    current set of pages that best matches it, then update the current page and
    page number
    If new_toolbar is defined, try to set the new page to the beginning of that
    toolbar
    It last_action_pressed is defined, use it to locate the current page if a
    we can't find a better matching page
    """

    self.previous_current_page = self.current_page

    # Do we have pages?
    if not self.pages:
      self.current_page = None
      self.current_page_no = None
      return

    # If we have no current page, pick the first one
    if self.current_page is None:
      self.current_page = self.pages[0]
      self.current_page_no = 0
      return

    # If we have a new toolbar, switch to the first page containing keys
    # marked with the name of the new toolbar
    if new_toolbar:
      r = re.compile("(^|;){}~".format(new_toolbar))
      for page_no, page in enumerate(self.pages):
        if r.search(page):
          self.current_page_no = page_no
          self.current_page = page
          return

    # If any of the pages have changed, try to find a page in the new pages
    # that matches it with regard to action names and placements, regardless
    # of their enabled status, regardless of their icons and regardless of
    # page navigation keys
    if (len(self.previous_pages) != len(self.pages) or \
	any([self.previous_pages[i] != p for i, p in enumerate(self.pages)])):
      r = re.compile("^" + ";".join([("{}~({})?(~[^;~]*){{6}}".
						format(t, n) \
					if n in ("PAGEPREV", "PAGENEXT") else \
					"{}~{}~.?~[^;~]*?~{}~{}~{}~{}".
						format(t, n, tt, bt, lbc, rbc))\
					for t, n, _, _, tt, bt, lbc, rbc in \
						[ks.split("~") \
					for ks in self.current_page.\
							split(";")]]) + "$")
      for page_no, page in enumerate(self.pages):
        if r.match(page):
          self.current_page_no = page_no
          self.current_page = page
          return

    # If we have a last action pressed, try to switch to the page containing
    # that action - i.e. same toolbar name and same action name...
    if last_action_pressed:
      r = re.compile("(^|;){}~{}~".
			format(last_action_pressed.toolbar,
				last_action_pressed.name))
      for page_no, page in enumerate(self.pages):
        if r.search(page):
          self.current_page_no = page_no
          self.current_page = page
          return

      # ...and if the name of the last action pressed wasn't found and
      # it's a subaction of another action, try to switch to the page
      # containing the key corresponding to the parent action
      if last_action_pressed.issubactionof is not None:
        r = re.compile("(^|;){}~{}~".
			format(last_action_pressed.toolbar,
				last_action_pressed.issubactionof))
        for page_no, page in enumerate(self.pages):
          if r.search(page):
            self.current_page_no = page_no
            self.current_page = page
            return

    # Try to switch to the first page containing keys marked with the name
    # of the current toolbar
    r = re.compile("(^|;){}~".format(self.current_page.split("~", 1)[0].\
							split("#", 1)[0]))
    for page_no, page in enumerate(self.pages):
      if r.search(page):
        self.current_page_no = page_no
        self.current_page = page
        return

    # Default to the first page as a last resort
    self.current_page = self.pages[0]
    self.current_page_no = 0



  def flip(self, to_next_page):
    """Increment or decrement the page number and change the current page to the
    previous page or the next page depending on whether to_next_page is asserted
    or not
    """

    self.current_page_no += (1 if to_next_page else -1)
    self.current_page_no = min(len(self.pages) - 1,
				max(0, self.current_page_no))

    self.previous_current_page = self.current_page
    self.current_page = self.pages[self.current_page_no]
