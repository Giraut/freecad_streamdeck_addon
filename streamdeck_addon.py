"""FreeCAD Stream Deck Addon - Main program
"""

## Modules
#

import parameters as params

import re
import io
import os
import sys
import appdirs
import importlib
from time import time
from PIL import Image

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from streamdeckclass import StreamDeck



## Classes
#

class Action():
  """Single known displayed action descriptor
  """

  def __init__(self, name, toolbar, action, issubactionof = None):
    """__init__ method
    """

    self.name = name

    self.toolbar = toolbar
    self.action = action

    self.enabled = action.isEnabled()
    self.title = action.iconText()
    self.iconid = action.icon().cacheKey()

    self.issubactionof = issubactionof	# If the action is a menu item,
					# of which action
    self.islastsubaction = False	# If the action is a menu item, whether
					# it's the last item in the menu



  def update(self, toolbar, action):
    """Update this Action object with new toolbar and action data as needed
    """

    if self.toolbar != toolbar:
      self.toolbar = toolbar
      self.action = action
      self.title = action.iconText()

    self.iconid = action.icon().cacheKey()
    self.enabled = action.isEnabled()



  def icon_as_pil_image(self):
    """Convert the enabled or disabled versions of the QIcon into a PIL image
    """

    try:
      pixmap = self.action.icon().pixmap(128, 128,
					mode = QtGui.QIcon.Mode.Normal \
							if self.enabled else \
						QtGui.QIcon.Mode.Disabled)
      qba = QtCore.QByteArray()
      qbf = QtCore.QBuffer(qba)
      pixmap.save(qbf, "PPM")
      img = Image.open(io.BytesIO(qba))
      qbf.close

    except:
      img = None

    return img



## Routines
#

def shutdown():
  """Callback to clean things up before stopping
  """

  global streamdeck

  streamdeck.close()

  # If we have a shell command to execute when starting, execute it
  if params.execute_shell_command_when_stopping:
    os.system(params.execute_shell_command_when_stopping)



def action_changed():
  """Callback when any of the toolbar actions has changed
  """
  global update_actions

  update_actions = True



def update_current_toolbar_actions():
  """update the ordered list of toolbar names, toolbar actions and subactions
  Return True if the toolbars have changed in any way, False if they haven't
  """

  global previous_toolbars
  global toolbars
  global toolbar_actions
  global actions
  global update_actions
  global expanded_actions

  previous_toolbars = toolbars
  toolbars = []

  # Get the list of toolbars
  tbs = []
  for toolbar in main_window.findChildren(QtGui.QToolBar):

    # Should we keep or ignore this toolbar?
    t = toolbar.objectName()
    if not toolbar.isHidden() and \
		t not in params.exclude_toolbars_from_streamdeck:

      # Keep the toolbar
      tbs.append(toolbar)
      toolbars.append(t)

  # If the new list of toolbars is different from the previous one in any way,
  # update all the associated actions
  if len(toolbars) != len(previous_toolbars) or \
	any([previous_toolbars[i] != t for i, t in enumerate(toolbars)]):
    update_actions = True

  # Should we update all the toolbar actions?
  if update_actions:
    update_actions = False

    toolbar_actions.clear()
    for i, toolbar in enumerate(tbs):

      t = toolbars[i]
      toolbar_actions[t] = []

      # Get the list of buttons in this toolbar
      for button in toolbar.findChildren(QtGui.QToolButton):

        # Get the list of actions associated with this button
        for action in button.actions():

          # Should we keep or ignore this action?
          n = action.data()
          if n and not action.isSeparator() and action.isIconVisibleInMenu():

            # Add the action to the list of known actions if it isn't
            # already known and connect its changed signal to our callback,
            # otherwise update the known action
            if n not in actions:
              actions[n] = Action(n, t, action)
              action.changed.connect(action_changed)
            else:
              actions[n].update(t, action)
            toolbar_actions[t].append(n)

            # Does the button have a menu associated with it?
            m = button.findChildren(QtGui.QMenu)
            if m:

              # Add this action to the list of expand(able) actions if it isn't
              # in it already
              if n not in expanded_actions:
                expanded_actions[n] = False

              # Should we expand the subactions?
              if expanded_actions[n]:

                # Get all the menu subactions
                last_subactions = None
                for subaction in m[0].actions():

                  # Should we keep or ignore this action?
                  if not subaction.isSeparator() and \
				subaction.isIconVisibleInMenu():

                    # Create a name for this subaction: either the straight name
                    # from .objectName(), or the name of the parent action with
                    # the menu number from .data() appended to it
                    sn = subaction.objectName()
                    if not sn:
                      sn = n + "#" + str(subaction.data())

                    # Add the subaction to the list of known actions if it isn't
                    # already known and connect its changed signal to our
                    # callback, otherwise update the known action
                    if sn not in actions:
                      actions[sn] = Action(sn, t, subaction, issubactionof = n)
                      subaction.changed.connect(action_changed)
                    else:
                      actions[sn].update(t, subaction)
                    toolbar_actions[t].append(sn)

                    last_subaction = sn

                # Mark the last subaction in this menu
                if last_subaction is not None:
                  actions[last_subaction].islastsubaction = True

    # Signal that the actions have been updated
    return True

  # Signal that the actions have not been updated
  return False



def streamdeck_update():
  """Mirror the current content of the Freecad toolbars onto the stream deck
  """

  global previous_toolbars
  global toolbars
  global toolbar_actions
  global actions
  global update_actions
  global expanded_actions

  global streamdeck
  global streamdeck_was_open
  global show_help

  global current_page
  global current_page_no
  global last_action_pressed

  global pages

  global timer
  global timer_reschedule_every_ms
  global next_actions_update_tstamp

  now = time()

  update_streamdeck_keys = False

  # If the Stream Deck device is not open, try to open it
  if not streamdeck.is_open():

    streamdecks_info = streamdeck.open(params.use_streamdeck_device_type,
					params.use_streamdeck_device_serial,
					params.streamdeck_brightness)

    # If the open failed, reschedule ourselves to run in a while to let the
    # FreeCAD UI breathe a bit, as it takes long enough to try opening a Stream
    # Deck device that the FreeCAD UI freezes for a short time, which is not
    # desirable
    if not streamdeck.is_open():

      # Show information about the Stream Decks if a Stream Deck was open before
      if streamdeck_was_open is None or streamdeck_was_open:
        print("-" * 79)
        for l in streamdecks_info:
          print(l)
        print("Retrying every 30 seconds...")
        print("-" * 79)

      streamdeck_was_open = False
      timer.start(30 * 1000)
      return

    previous_toolbars = []
    toolbars = []
    toolbar_actions = {}
    actions = {}
    update_actions = True
    expanded_actions = {}

    pages = []

    current_page = None
    last_action_pressed = None

    # Show information about the Stream Decks if no Stream Deck was open before
    if not streamdeck_was_open:

      print("-" * 79)
      for l in streamdecks_info:
        print(l)

      # Print out a bit of help once after the first open
      if show_help:
        print("-" * 79)
        print("Short-press an enabled button to activate the function")
        print("Long-press buttons between {} brackets to expand/collapse them".
		format(params.brackets_color_for_expandable_tool_buttons))
        print("Buttons between {} brackets are available in all pages".format(
		params.brackets_color_for_toolbars_on_every_streamdeck_page))

        show_help = False

      print("-" * 79)

      streamdeck_was_open = True

  # Get Stream Deck key press events
  try:
    pressed_keys = streamdeck.get_keypresses()
  except Exception as e:
    print(e)
    streamdeck.close()

  # Process Stream Deck key press events if a current page is displayed
  if streamdeck.is_open() and current_page is not None:
    keystrings = current_page.split(";")

    for is_long_press, key in pressed_keys:

      n = keystrings[key].split("~")[1]

      # Is the key occupied?
      if n:

        # Change the page
        if n in ("PAGEPREV", "PAGENEXT"):
          last_action_pressed = None

          current_page_no = current_page_no + (-1 if n == "PAGEPREV" else +1)
          current_page_no = min(len(pages) - 1, max(0, current_page_no))

          prev_current_page = current_page
          current_page = pages[current_page_no]

          update_streamdeck_keys = True

        # Act upon a real action
        else:
          last_action_pressed = actions[n]

          # Long key press?
          if is_long_press:

            # If the action is expandable, toggle its expansion and
            # force-rebuild all the pages
            if n in expanded_actions:
              expanded_actions[n] = not expanded_actions[n]
              update_actions = True
              next_actions_update_tstamp = 0

            # If the action is a subaction of another action toggle the parent
            # action's expansion and force-rebuild all the pages
            elif actions[n].issubactionof is not None and \
		actions[n].issubactionof in expanded_actions:
              expanded_actions[actions[n].issubactionof] = \
				not expanded_actions[actions[n].issubactionof]
              update_actions = True
              next_actions_update_tstamp = 0

          # Short key press: if the action is enabled, execute it
          elif actions[n].enabled:
            actions[n].action.trigger()

  # Should we get the current state of the FreeCAD toolbars and update the
  # Stream Deck pages?
  if streamdeck.is_open() and not update_streamdeck_keys and \
	now > next_actions_update_tstamp:

    # Update the currently displayed toolbar actions
    if update_current_toolbar_actions():

      # Find out the first of the new toolbars, if there are new toolbars, so
      # we can switch to it on the Stream Deck display
      new_toolbar = None
      for t in toolbars:
        if t not in previous_toolbars and \
		t not in params.toolbars_on_every_streamdeck_page:
          new_toolbar = t
          break

      # Compose the new pages to display on the Stream Deck: the pages are
      # described in a multiline string with each line in the following format:
      #
      # <key0>;<key1>;...;<keyN>
      #
      # and each key is composed of:
      # <toolbarmarker>~[action]~[0|1]~[iconid]~[toptext]~[bottomtext]~
      #    [leftbracketcolor]~[rightbracketcolor]
      #
      ptbc = params.brackets_color_for_toolbars_on_every_streamdeck_page
      nkbc = params.brackets_color_for_streamdeck_page_navigation_keys
      exbc = params.brackets_color_for_expandable_tool_buttons

      # Create a pattern of one or more pages (hopefully just one) that contain
      # the keys for the actions of the toolbars that should be repeated on
      # every page at the beginning, the page navigation keys at the end and
      # at least one free key slot in-between.
      keys = []
      for t in params.toolbars_on_every_streamdeck_page:
        if t in toolbars:
          last_action_i = len(toolbar_actions[t]) - 1
          keys.extend(["[toolbar]~{}~{}~{}~{}~{}~{}~{}".
			format(n, 1 if actions[n].enabled else 0,
				actions[n].iconid,
				actions[n].title, t,
				ptbc if i == 0 else \
				exbc if n in expanded_actions else "",
				ptbc if i == last_action_i else \
				exbc if not expanded_actions.get(n, True) or \
					actions[n].islastsubaction else "")
			for i, n in enumerate(toolbar_actions[t])])
      nbkeys = len(keys)

      empty_new_pages = []
      while nbkeys > streamdeck.nbkeys - 3:	# The last page of the new empty
						# pages should have 2 slots left
						# for the page navigation keys
						# and 1 empty slot
        empty_new_pages.append(";".join(keys[:streamdeck.nbkeys - 2]) + \
				";[pageprev];[pagenext]")
        keys = keys[streamdeck.nbkeys - 2:]
        nbkeys -= streamdeck.nbkeys - 2

      empty_new_pages.append(";".join(keys) + \
				(";" if keys and \
				(streamdeck.nbkeys - nbkeys - 2) else "") + \
				";".join(["[key]" for _ in \
				range(streamdeck.nbkeys - nbkeys - 2)]) + \
				";[pageprev];[pagenext]")

      last_empty_new_page_i = len(empty_new_pages) - 1

      # Create the pages of action keys
      previous_pages = pages
      pages = []
      prev_page_toolbar = None

      indiv_toolbar_page_maker_ctr = 0
      page_marker = lambda: "{}#{}".format(t, indiv_toolbar_page_maker_ctr)

      for t in toolbars:
        if t not in params.toolbars_on_every_streamdeck_page:

          # Get the list of key strings for this toolbar
          keys = ["{}~{}~{}~{}~{}~{}~{}~{}".
			format(t, n, 1 if actions[n].enabled else 0,
				actions[n].iconid, actions[n].title, t,
				exbc if n in expanded_actions else "",
				exbc if not expanded_actions.get(n, True) or \
					actions[n].islastsubaction else "")
			for n in toolbar_actions[t]]

          indiv_toolbar_page_maker_ctr = 0

          # Add all the keys to the pages
          for key in keys:

            # If we don't have empty key slots left, add empty pages
            if not pages or "[key]" not in pages[-1]:

              # Replace the previous page's [pagenext] placeholder, if any
              if pages:
                pages[-1] = pages[-1].replace("[pagenext]",
						"{}~PAGENEXT~~~~{}~~{}".
						format(page_marker(), t, nkbc))

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
                pages.append(new_page)

              prev_page_toolbar = t

            # Insert the next key into the pages
            pages[-1] = pages[-1].replace("[key]", key, 1)

          # Add blank keys to complete the last page for this toolbar
          pages[-1] = pages[-1].replace("[key]", "{}~~~~~~~".
					format(page_marker()))

      # Replace the last [pagenext] placeholder if any
      if pages:
        pages[-1] = pages[-1].replace("[pagenext]", "{}~~~~~~~{}".
					format(page_marker(), nkbc))

      # Determine the page to be displayed / updated
      prev_current_page = current_page
      current_page_updated = False

      # Do we have pages?
      if pages:

        # If we have no current page, pick the first one
        if current_page is None:
          current_page = pages[0]
          current_page_no = 0

        # If we have a new toolbar, switch to the first page containing keys
        # marked with the name of the new toolbar
        if new_toolbar:
          r = re.compile("(^|;){}~".format(new_toolbar))
          for page_no, page in enumerate(pages):
            if r.search(page):
              current_page_no = page_no
              current_page = page
              current_page_updated = True
              break

        # If any of the pages have changed, try to find a page in the new pages
        # that matches it with regard to action names and placements, regardless
        # of their enabled status, regardless of their icons and regardless of
        # page navigation keys
        if not current_page_updated and \
		(len(previous_pages) != len(pages) or \
		any([previous_pages[i] != p for i, p in enumerate(pages)])):
          r = re.compile("^" + ";".join([("{}~({})?(~[^;~]*){{6}}".
						format(t, n) \
						if n in ("PAGEPREV",
							"PAGENEXT") else \
					"{}~{}~.?~[^;~]*?~{}~{}~{}~{}".
						format(t, n, tt, bt, lbc, rbc))\
					for t, n, _, _, tt, bt, lbc, rbc in \
						[ks.split("~") \
					for ks in current_page.split(";")]]) \
			+ "$")
          for page_no, page in enumerate(pages):
            if r.match(page):
              current_page_no = page_no
              current_page = page
              current_page_updated = True
              break

        # Try to switch to the page containing the last action pressed -
        # i.e. same toolbar name and same action name...
        if not current_page_updated and last_action_pressed:
          r = re.compile("(^|;){}~{}~".
				format(last_action_pressed.toolbar,
					last_action_pressed.name))
          for page_no, page in enumerate(pages):
            if r.search(page):
              current_page_no = page_no
              current_page = page
              current_page_updated = True
              break

          # ...and if the name of the last action pressed wasn't found and
          # it's a subaction of another action, try to switch to the page
          # containing the key corresponding to the parent action
          if not current_page_updated and \
		last_action_pressed.issubactionof is not None:
            r = re.compile("(^|;){}~{}~".
				format(last_action_pressed.toolbar,
					last_action_pressed.issubactionof))
            for page_no, page in enumerate(pages):
              if r.search(page):
                current_page_no = page_no
                current_page = page
                current_page_updated = True
                break

        # Try to switch to the first page containing keys marked with the name
        # of the current toolbar
        if not current_page_updated:
          r = re.compile("(^|;){}~".
				format(current_page.split("~", 1)[0].\
					split("#", 1)[0]))
          for page_no, page in enumerate(pages):
            if r.search(page):
              current_page_no = page_no
              current_page = page
              current_page_updated = True
              break

        # Default to the first page as a last resort
        if not current_page_updated:
          current_page = pages[0]
          current_page_no = 0

      update_streamdeck_keys = True

    # Calculate the next time we need to update the Stream Deck keys
    next_actions_update_tstamp = now + params.check_toolbar_updates_every

  # Should we update the Stream Deck keys?
  if streamdeck.is_open() and update_streamdeck_keys:

    # Update the keys that need updating
    if not current_page:

      # Clear all the Stream Deck keys if we don't have a current page anymore
      if prev_current_page:
        for keyno in range(streamdeck.nbkeys):
          try:
            streamdeck.set_key(keyno, None)
          except:
            streamdeck.close()
            break

    # Update the keys to display the current page as needed
    else:
      keystrings = current_page.split(";")
      if prev_current_page:
        prev_keystrings = prev_current_page.split(";")

      for keyno, ks in enumerate(keystrings):
        if not prev_current_page or ks != prev_keystrings[keyno]:

          _, n, _, _, tt, bt, lbc, rbc = ks.split("~")
          img = n if n in ("", "PAGEPREV", "PAGENEXT") else \
		actions[n].icon_as_pil_image()

          try:
            streamdeck.set_key(keyno, img, tt, bt, lbc, rbc)
          except:
            streamdeck.close()
            break

  # Reschedule ourselves
  timer.start(timer_reschedule_every_ms)



## Entry point
#

# Determine the platform
is_win = sys.platform[0:3] == "win"

# Determine the installation directory
install_dir = os.path.dirname(__file__)
in_install_dir = lambda f: os.path.abspath(os.path.join(install_dir, f))

# Try to read the user's parameters file if it exists
user_params_file = getattr(params, "user_parameters_file", None)

if user_params_file:
  user_cfg_dir = os.path.abspath(appdirs.user_config_dir())
  user_params_file = os.path.join(user_cfg_dir, user_params_file)

  if os.path.exists(user_params_file):
    n = params.__name__
    try:
      spec = importlib.util.spec_from_file_location(n, user_params_file)
      params = importlib.util.module_from_spec(spec)
      spec.loader.exec_module(params)
    except Exception as e:
      print("WARNING: cannot read user parameters file {}: {}".
		format(user_params_file, e))

# Make sure we have all the parameters we need
default_parameters = {
	"use_streamdeck_device_type": None,
	"use_streamdeck_device_serial": None,
	"execute_shell_command_when_starting": None,
	"execute_shell_command_when_stopping": None,
	"check_streamdeck_keypress_every": 0.1,
	"streamdeck_key_long_press_duration": 0.5,
	"check_toolbar_updates_every": 0.5,
	"exclude_toolbars_from_streamdeck": [],
	"toolbars_on_every_streamdeck_page": [],
	"brackets_color_for_toolbars_on_every_streamdeck_page": "blue",
	"brackets_color_for_streamdeck_page_navigation_keys": "blue",
	"brackets_color_for_expandable_tool_buttons": "red",
	"streamdeck_key_text_font_filename_linux": "OpenSans-Regular.ttf",
	"streamdeck_key_text_font_filename_windows": "arial.ttf",
	"streamdeck_key_text_font_size": 14,
	"prev_streamdeck_key_icon": "prev.png",
	"next_streamdeck_key_icon": "next.png",
	"blank_streamdeck_key_icon": "blank.png",
	"broken_streamdeck_key_icon": "broken.png",
	"streamdeck_brightness": 80}

for p in default_parameters:
  if p not in params.__dict__:
    setattr(params, p, default_parameters[p])

# Get the name of the appropriate font to write in the Stream Deck keys
# depending on the platform
font_filename = params.streamdeck_key_text_font_filename_windows \
			if is_win else \
		params.streamdeck_key_text_font_filename_linux

# Initialize the streamdeck object
streamdeck = StreamDeck(font_filename, params.streamdeck_key_text_font_size,
			in_install_dir(params.prev_streamdeck_key_icon),
			in_install_dir(params.next_streamdeck_key_icon),
			in_install_dir(params.blank_streamdeck_key_icon),
			in_install_dir(params.broken_streamdeck_key_icon),
			params.streamdeck_key_long_press_duration)

streamdeck_was_open = None
show_help = True

# Timer interval in milliseconds
timer_reschedule_every_ms = round(params.check_streamdeck_keypress_every * 1000)

# What time we should update the toolbars and actions
next_actions_update_tstamp = 0

# Get the main window
main_window = Gui.getMainWindow()

# Set up the single-short timer, connect it to the Stream Deck update routine
timer = QtCore.QTimer()
timer.setSingleShot(True)
timer.timeout.connect(streamdeck_update)

# If we have a shell command to execute when starting, execute it
if params.execute_shell_command_when_starting:
  os.system(params.execute_shell_command_when_starting)

# Connect the main window's destroyed() signal to the Strem Deck close function
main_window.destroyed.connect(shutdown)

# Schedule the timer for the first itme
timer.start()
