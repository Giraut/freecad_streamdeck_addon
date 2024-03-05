"""FreeCAD Stream Deck Addon - Stream Deck pages class
"""

## Modules
#

import re



## Classes
#

class StreamDeckPages():

  def __init__(self, nb_streamdeck_keys, with_nav_keys):
    """__init__ method
    """

    self.nb_streamdeck_keys = nb_streamdeck_keys
    self.with_nav_keys = with_nav_keys

    self.previous_pages = []
    self.pages = []

    self.previous_current_page = None
    self.current_page = None
    self.current_page_no = None



  def rebuild_pages(self, tbactions, repeated_toolbars,
			bracket_color_repeated_toolbars,
			bracket_color_page_nav_keys,
			brackets_color_expandable_tools):
    """Rebuild Stream Deck pages given a list of toolbars and actions passed as
    a ToolbarActions object
    """

    # Get the lowercase color names
    ptbc = bracket_color_repeated_toolbars.lower()
    nkbc = bracket_color_page_nav_keys.lower()
    exbc = brackets_color_expandable_tools.lower()

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
    for t in repeated_toolbars:
      if t in tbactions.toolbars:
        last_action_i = len(tbactions.toolbar_actions[t]) - 1
        keys.extend(["[toolbar]~{}~{}~{}~{}~{}~{}~{}".
		format(n, 1 if tbactions.actions[n].enabled else 0,
			tbactions.actions[n].iconid,
			tbactions.actions[n].title, t,
			ptbc if i == 0 else \
			exbc if n in tbactions.expanded_actions else "",
			ptbc if i == last_action_i else \
			exbc if not tbactions.expanded_actions.get(n, True) or \
				tbactions.actions[n].islastsubaction else "")
		for i, n in enumerate(tbactions.toolbar_actions[t])])
    nbkeys = len(keys)

    reserve_nb_last_keys = 2 if self.with_nav_keys else 0
    last_2_page_keys = ";[pageprev];[pagenext]" if self.with_nav_keys else ""

    empty_new_pages = []

    # The last page of the new empty pages should have however many reserved
    # slots and at lease 1 empty slot for a key left
    while nbkeys > self.nb_streamdeck_keys - reserve_nb_last_keys - 1:
      empty_new_pages.append(";".join(keys[:self.nb_streamdeck_keys - \
						reserve_nb_last_keys]) + \
				last_2_page_keys)
      keys = keys[self.nb_streamdeck_keys - reserve_nb_last_keys:]
      nbkeys -= self.nb_streamdeck_keys - reserve_nb_last_keys

    empty_new_pages.append(";".join(keys) + \
				(";" if keys and \
					(self.nb_streamdeck_keys - nbkeys - \
						reserve_nb_last_keys) \
					else "") + \
				";".join(["[key]" for _ in \
					range(self.nb_streamdeck_keys - \
						nbkeys - \
						reserve_nb_last_keys)]) \
				+ last_2_page_keys)

    last_empty_new_page_i = len(empty_new_pages) - 1

    # Create the pages of action keys
    self.previous_pages = self.pages
    self.pages = []
    prev_page_toolbar = None

    indiv_toolbar_page_maker_ctr = 0
    page_marker = lambda: "{}#{}".format(t, indiv_toolbar_page_maker_ctr)

    for t in tbactions.toolbars:
      if t not in repeated_toolbars:

        # Get the list of key strings for this toolbar
        keys = ["{}~{}~{}~{}~{}~{}~{}~{}".
		format(t, n, 1 if tbactions.actions[n].enabled else 0,
			tbactions.actions[n].iconid,
			tbactions.actions[n].title, t,
			exbc if n in tbactions.expanded_actions else "",
			exbc if not tbactions.expanded_actions.get(n, True) or \
				tbactions.actions[n].islastsubaction else "")
		for n in tbactions.toolbar_actions[t]]

        indiv_toolbar_page_maker_ctr = 0

        # Add all the keys to the pages
        for key in keys:

          # If we don't have empty key slots left, add empty pages
          if not self.pages or "[key]" not in self.pages[-1]:

            # If we have navigation keys, replace the previous page's [pagenext]
            # placeholder if any
            if self.with_nav_keys and self.pages:
              self.pages[-1] = self.pages[-1].replace("[pagenext]",
							"{}~PAGENEXT~~~~{}~~{}".
							format(page_marker(),
								t, nkbc))

            # Add new pages. Mark all the new pages' keys with a unique page
            # marker.
            for i, p in enumerate(empty_new_pages):

              indiv_toolbar_page_maker_ctr += 1

              new_page = p.replace("[toolbar]", page_marker())

              # Do we have navigation keys?
              if self.with_nav_keys:

                # If we have more than one new page, replace the [pagenext]
                # placeholder in all but the last new page
                if i < last_empty_new_page_i:
                  new_page = new_page.replace("[pagenext]",
						"{}~PAGENEXT~~~~{}~~{}".
						format(page_marker(), t, nkbc))

                # Replace the first [pageprev] placeholder
                if i == 0:
                  new_page = new_page.replace("[pageprev]",
						"{}~PAGEPREV~~~~{}~{}~".
						format(page_marker(),
							prev_page_toolbar,
							nkbc) \
						if prev_page_toolbar else \
						"{}~~~~~~{}~".
						format(page_marker(), nkbc), 1)

                # Replace the remaining [pageprev] placeholders if any
                else:
                  new_page = new_page.replace("[pageprev]",
						"{}~PAGEPREV~~~~{}~{}~".
						format(page_marker(), t, nkbc))

              # Add the new page to the pages
              self.pages.append(new_page)

            prev_page_toolbar = t

          # Insert the next key into the pages
          self.pages[-1] = self.pages[-1].replace("[key]", key, 1)

        # Add blank keys to complete the last page for this toolbar
        self.pages[-1] = self.pages[-1].replace("[key]", "{}~~~~~~~".
						format(page_marker()))

    # If we have navigation keys, replace the last [pagenext] placeholder if any
    if self.with_nav_keys and self.pages:
      self.pages[-1] = self.pages[-1].replace("[pagenext]", "{}~~~~~~~{}".
						format(page_marker(), nkbc))



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



  def flip(self, nbpages):
    """Jump nbpages pages: before the current page if nbpages <0, after if
    nbpages >0
    Return True if the page was changed
    """

    new_page_no = min(len(self.pages) - 1,
			max(0, self.current_page_no + nbpages))

    if new_page_no == self.current_page_no:
      return False

    self.current_page_no = new_page_no
    self.previous_current_page = self.current_page
    self.current_page = self.pages[self.current_page_no]

    return True
