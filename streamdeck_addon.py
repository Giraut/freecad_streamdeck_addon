"""FreeCAD Stream Deck Addon - Main program
"""

## Modules
#


import re
import os
import sys
from time import time

import FreeCADGui as Gui
from PySide import QtCore

import platform_support
from parameters import UserParameters
from streamdeck_comm import StreamDeck
from gui_actions import ToolbarActions, WORKBENCH_ACTION_PREFIX
from streamdeck_pages import StreamDeckPages
from streamdeck_folders import StreamDeckFolders



## Classes
#

class UserActivity():
  """Class to check if the user is active or idle based on cursor movements
  """

  def __init__(self, main_window):
    """__init__ method
    """

    self.main_window = main_window
    self.main_window_is_active = True

    self.last_check_tstamp = None

    self.cursor_pos = None
    self.last_activity_tstamp = None



  def is_active(self, now, inactivity_time, external_activity_flags):
    """Determine if the user is active based on cursor movements and external
    activity flags, and whether the cursor movements occur while the main
    window is active
    external_activity_flag is a list of bools, any of which being True indicates
    that the user is active even if the cursor doesn't move
    If inactivity_time is None, the check is disabled and the user is deemed
    active all the time
    If the main window isn't active, the user is busy doing something else,
    therefore reputed inactive here
    If the cursor hasn't moved within inactivity_time, return False
    """

    prev_check_tstamp = self.last_check_tstamp
    self.last_check_tstamp = now

    if inactivity_time is None:
      return True

    if self.cursor_pos is None:
      self.cursor_pos = self.main_window.cursor().pos()
      self.last_activity_tstamp = now
      return True

    prev_main_window_is_active = self.main_window_is_active
    self.main_window_is_active = self.main_window.isActiveWindow()

    prev_cursor_pos = self.cursor_pos

    if self.main_window_is_active:
      self.cursor_pos = self.main_window.cursor().pos()

      if not prev_main_window_is_active or self.cursor_pos != prev_cursor_pos:
        self.last_activity_tstamp = now

    if any(external_activity_flags):
      self.last_activity_tstamp = now

    return now - self.last_activity_tstamp < inactivity_time \
			if inactivity_time > (now - prev_check_tstamp) * 2 \
		else self.last_activity_tstamp == now



## Routines
#

def shutdown():
  """Callback to clean things up before stopping
  """

  global params
  global streamdeck

  streamdeck.close()

  # If we have a shell command to execute when starting, execute it
  if params.exec_cmd_stop:
    os.system(params.exec_cmd_stop)



def action_changed():
  """Callback when any of the toolbar actions has changed
  """
  global update_actions

  update_actions = True



def make_pages():
  """Create the object that lays out the toolbars and actions on the Stream
  Deck pages, according to the layout chosen in the parameters
  """

  global params
  global streamdeck

  if params.layout == "Pages":
    return StreamDeckPages(streamdeck.nbkeys, streamdeck.nbdials == 0)

  return StreamDeckFolders(streamdeck.nbkeys, streamdeck.nbdials == 0)



def key_image(n, enabled):
  """Return the image to display on a key given the command and enabled fields
  of its key string: None for a blank key, the name of a predefined image for a
  navigation key, or the icon of an action as a PIL image
  """

  global tbactions

  if not n:
    return None

  # Keys of the page under a menu: the image of the original key, faded if
  # the key is shown disabled - the tool the menu belongs to isn't
  if n.startswith(StreamDeckFolders.CLOSE_PREFIX):
    image = key_image(n[len(StreamDeckFolders.CLOSE_PREFIX):], "1")
    if enabled != "0" or image is None:
      return image
    if isinstance(image, str):
      return image if image.endswith(StreamDeck.IMAGE_OFF_SUFFIX) else \
		image + StreamDeck.IMAGE_OFF_SUFFIX
    return StreamDeck.dimmed_image(image)

  if n in (StreamDeckFolders.PAGEPREV, StreamDeckFolders.PAGENEXT,
		StreamDeckFolders.PAGEBACK):
    return n + (StreamDeck.IMAGE_OFF_SUFFIX if enabled == "0" else "")

  try:

    # The key going up to the workbench list shows the icon of the active
    # workbench. On the workbench list, where it does nothing, it shows the
    # workbench grid icon, in color
    if n == StreamDeckFolders.WORKBENCH_LIST:
      if enabled == "0":
        return StreamDeck.WORKBENCH
      if not tbactions.active_workbench_action:
        return None
      return tbactions.actions[tbactions.active_workbench_action].\
		icon_as_pil_image(force_enabled = True)

    # Toolbar folders show the icon of their first tool, always as enabled
    if n.startswith(StreamDeckFolders.OPEN_PREFIX):
      t = n[len(StreamDeckFolders.OPEN_PREFIX):]
      return tbactions.actions[tbactions.toolbar_actions[t][0]].\
		icon_as_pil_image(force_enabled = True)

    return tbactions.actions[n].icon_as_pil_image()

  except Exception:
    return None



def process_key_event_pages(event_type, n):
  """Process a key press on a key showing the command n in the pages layout
  Return True if the Stream Deck keys need updating
  """

  global streamdeck
  global tbactions
  global pages
  global update_actions
  global next_actions_update_tstamp
  global last_action_pressed

  # Change the page
  if n in ("PAGEPREV", "PAGENEXT"):
    last_action_pressed = None
    return pages.flip(1 if n == "PAGENEXT" else -1)

  # Act upon a real action
  last_action_pressed = tbactions.actions[n]

  # Is the event a long key press?
  if event_type == streamdeck.LONG_KEYPRESS:

    # If the action is expandable, toggle its expansion and force-rebuild all
    # the pages
    if n in tbactions.expanded_actions:
      tbactions.expanded_actions[n] = not tbactions.expanded_actions[n]
      update_actions = True
      next_actions_update_tstamp = 0

    # If the action is a subaction of another action toggle the parent action's
    # expansion and force-rebuild all the pages
    elif tbactions.actions[n].issubactionof is not None and \
		tbactions.actions[n].issubactionof in tbactions.expanded_actions:
      tbactions.expanded_actions[tbactions.actions[n].issubactionof] = \
		not tbactions.expanded_actions[tbactions.actions[n].issubactionof]
      update_actions = True
      next_actions_update_tstamp = 0

  # If the event is a short key press and the action is enabled, execute it
  elif tbactions.actions[n].enabled:
    tbactions.actions[n].action.trigger()

  return False



def process_key_event_folders(event_type, n, enabled):
  """Process a key press on a key showing the command n in the folders layout
  Return True if the Stream Deck keys need updating
  """

  global streamdeck
  global tbactions
  global pages
  global update_actions
  global next_actions_update_tstamp
  global last_action_pressed

  long_press = event_type == streamdeck.LONG_KEYPRESS

  # A key of the page under a menu - faded, or the tool the menu
  # belongs to: close the menu
  if n.startswith(pages.CLOSE_PREFIX):
    last_action_pressed = None
    return pages.go_back()

  # Change the page within the current toolbar, menu or home page
  if n in (pages.PAGEPREV, pages.PAGENEXT):
    last_action_pressed = None
    return enabled != "0" and pages.flip(1 if n == pages.PAGENEXT else -1)

  # Go up one level - the top-left key. A long press goes straight back to
  # the workbench page from a toolbar or a menu
  if n in (pages.PAGEBACK, pages.WORKBENCH_LIST):
    last_action_pressed = None
    return pages.go_home() if long_press else pages.go_back()

  # Open a toolbar
  if n.startswith(pages.OPEN_PREFIX):
    last_action_pressed = None
    return pages.open_toolbar(n[len(pages.OPEN_PREFIX):])

  # Act upon a real action
  a = tbactions.actions.get(n)
  if a is None:
    return False

  last_action_pressed = a

  # A long press opens the action's menu if it has one, or closes the current
  # menu if the action is a menu item
  if long_press:
    if tbactions.subactions.get(n):
      return pages.open_menu(n)
    if pages.in_menu:
      return pages.go_back()
    return False

  # A short press on a workbench in the workbench list switches to it, then
  # opens its page with its toolbars - picking a workbench is a one-time step,
  # the list isn't left behind under the workbench page's levels. Read the
  # toolbars again right away rather than showing the previous workbench's
  # toolbars until the next check
  if n.startswith(WORKBENCH_ACTION_PREFIX):
    if a.enabled:
      a.action.trigger()
      pages.show_workbench(first_page = True)
      update_actions = True
      next_actions_update_tstamp = 0
    return False

  # A short press executes the action if it's enabled, then closes the current
  # menu if the action is a menu item - like picking an item in a dropdown menu
  if a.enabled:
    a.action.trigger()
    if pages.in_menu:
      return pages.go_back()

  return False



def streamdeck_update():
  """Mirror the current content of the Freecad toolbars onto the stream deck
  """

  global params

  global main_window

  global streamdeck
  global streamdeck_was_open
  global show_help
  global retry_open_at_tstamp

  global update_actions

  global tbactions
  global pages
  global useractivity
  global displayed_keys
  global recreate_pages

  global last_action_pressed

  global timer
  global timer_reschedule_every_ms
  global next_actions_update_tstamp

  now = time()

  update_streamdeck_keys = False

  # Synchronize the parameters
  parameters_synchronized =  params.sync()
  if parameters_synchronized:

    # If the list of toolbars excluded from the Stream Deck display, the list
    # of toolbars displayed on every Stream Deck page or any of the bracket or
    # mark colors have changed, force a full update of the list of toolbars and
    # toolbar actions, and rebuilding of the Stream Deck pages
    if params.excluded_toolbars != params.prev_excluded_toolbars or \
	params.repeated_toolbars != params.prev_repeated_toolbars or \
	params.bracket_color_repeated_toolbars != \
			 params.prev_bracket_color_repeated_toolbars or \
	params.bracket_color_page_nav_keys != \
			params.prev_bracket_color_page_nav_keys or \
	params.bracket_color_expandable_tools != \
			params.prev_bracket_color_expandable_tools or \
	params.mark_color_menu_tools != params.prev_mark_color_menu_tools or \
	params.mark_color_nested_folders != \
			params.prev_mark_color_nested_folders or \
	params.workbench_switcher != params.prev_workbench_switcher or \
	params.background_workbench_list != \
			params.prev_background_workbench_list or \
	params.background_workbench_page != \
			params.prev_background_workbench_page or \
	params.background_toolbars != params.prev_background_toolbars or \
	params.background_menus != params.prev_background_menus:
      update_actions = True

    # If the layout has changed, recreate the pages from scratch
    if params.layout != params.prev_layout:
      recreate_pages = True
      update_actions = True

    # Has any parameter affecting the connection with the Stream Deck device
    # changed?
    if params.prev_addon_enabled != params.addon_enabled or \
	(params.prev_use_streamdeck_type != params.use_streamdeck_type) or \
	(params.prev_use_streamdeck_serial != params.use_streamdeck_serial):

      # Close the device if needed
      if streamdeck.is_open():
        streamdeck.close()
        del(tbactions)
        del(pages)
        del(useractivity)

      # Try to reopen the device immediately with an unknown previous status, so
      # information is displayed upon trying to open the device
      streamdeck_was_open = None
      retry_open_at_tstamp = 0

  # If the addon is disabled, reschedule ourselves to recheck the parameeters
  # in 1 second
  if not params.addon_enabled:
    timer.start(1000)
    return

  # Is the Stream Deck closed
  if not streamdeck.is_open():

    # If it's too early to try opening it, reschedule ourselves to rechech the
    # parameters in 1 second
    if now < retry_open_at_tstamp:
      timer.start(1000)
      return

    # Try opening the device
    streamdecks_info = streamdeck.open(params.use_streamdeck_type,
					params.use_streamdeck_serial)

    # If the open failed, reschedule ourselves to run in a while to let the
    # FreeCAD UI breathe a bit, as it takes long enough to try opening a Stream
    # Deck device that the FreeCAD UI freezes for a short time, which is not
    # desirable
    if not streamdeck.is_open():

      # Show information about the Stream Decks if a Stream Deck was open before
      # or its status is unknown
      if streamdeck_was_open is None or streamdeck_was_open:
        print("-" * 79)
        for l in streamdecks_info:
          print(l)
        print("Retrying every 30 seconds...")

      streamdeck_was_open = False
      retry_open_at_tstamp = now + 30

      # Reschedule ourselves to recheck the parameeters in 1 second
      timer.start(1000)
      return

    tbactions = ToolbarActions(main_window, action_changed)
    update_actions = True

    pages = make_pages()
    recreate_pages = False

    # What's currently displayed on each key, as a key string. Unknown at
    # first, so all the keys get updated
    displayed_keys = [None] * streamdeck.nbkeys

    useractivity = UserActivity(main_window)

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
        if isinstance(pages, StreamDeckFolders):
          if params.workbench_switcher:
            print("The top level lists the workbenches: press one to switch "
		"to it and see its toolbars")
          print("A workbench's page shows one button per toolbar: press one "
		"to open that toolbar")
          print("The top-left button goes up one level. Long-press it to go "
		"straight back to the workbench's page")
          print("Long-press buttons with a small triangle in the bottom-right "
		"corner to open their menu")
          if streamdeck.nbdials > 0:
            print("Spin the dials to change pages")
          else:
            print("Toolbars with more than {} tools have several pages: "
			"use the".format(streamdeck.nbkeys - 1))
            print("arrow buttons at the bottom right to change pages")
        else:
          print("Long-press buttons between {} brackets to expand/collapse "
			"them".format(params.bracket_color_expandable_tools.lower()))
          print("Buttons between {} brackets are available on all pages".
		format(params.bracket_color_repeated_toolbars.lower()))
          if streamdeck.nbdials > 0:
            print("Spin the dials to change pages")

        show_help = False

      print("-" * 79)

      streamdeck_was_open = True

  # Get Stream Deck key press events
  try:
    input_events = streamdeck.get_input_events(params.long_keypress_duration)
  except:
    streamdeck.close()
    del(tbactions)
    del(pages)
    del(useractivity)

  # Is the Stream Deck still open?
  if streamdeck.is_open():

    # If the layout has changed, replace the pages with pages in the new layout
    # and collapse all the actions expanded in the pages layout
    if recreate_pages:
      pages = make_pages()
      for n in tbactions.expanded_actions:
        tbactions.expanded_actions[n] = False
      update_actions = True
      next_actions_update_tstamp = 0
      recreate_pages = False

    folders_layout = isinstance(pages, StreamDeckFolders)

    # Process Stream Deck input events if a current page is displayed
    if pages.current_page:
      keystrings = pages.current_page.split(pages.SK)

      for event_type, val in input_events:

        # Is the event a key press?
        if event_type in (streamdeck.SHORT_KEYPRESS, streamdeck.LONG_KEYPRESS):

          # Get the command associated with the key
          _, n, enabled = keystrings[val].split(pages.SV)[:3]

          # Is the key occupied?
          if n:
            if (process_key_event_folders(event_type, n, enabled) \
			if folders_layout else \
		process_key_event_pages(event_type, n)):
              update_streamdeck_keys = True

        # Is the event a dial spin?
        elif event_type == streamdeck.DIAL_SPIN_CLICKS:

          # Flip as many pages as we got dial clicks
          last_action_pressed = None
          if pages.flip(val):
            update_streamdeck_keys = True

    # Should we get the current state of the FreeCAD toolbars and update the
    # Stream Deck pages?
    if not update_streamdeck_keys and now > next_actions_update_tstamp:

      # Get the list of toolbars and toolbar actions currently displayed
      if tbactions.extract_toolbar_actions_from_gui(params.excluded_toolbars,
				update_actions,
				with_workbenches = params.workbench_switcher):
        update_actions = False

        # Find out the first of the new toolbars, if there are new toolbars, so
        # we can switch to it on the Stream Deck display
        new_toolbar = None
        for t in tbactions.toolbars:
          if t not in tbactions.previous_toolbars and \
		t not in params.repeated_toolbars:
            new_toolbar = t
            break

        # Folders layout: rebuild the current page using the updated toolbars
        # and actions. If new toolbars appeared - i.e. the workbench changed or
        # a sketch is being edited - go back to the home page, which shows them
        if folders_layout:
          pages.rebuild(tbactions, params.repeated_toolbars,
				params.mark_color_menu_tools,
				params.mark_color_nested_folders,
				go_home = new_toolbar is not None,
				home_color = params.background_workbench_page,
				toolbar_color = params.background_toolbars,
				menu_color = params.background_menus,
				workbenches_color = \
					params.background_workbench_list)

        # Pages layout: rebuild the entire set of Stream Deck pages using the
        # updated toolbars and actions
        else:
          pages.rebuild_pages(tbactions, params.repeated_toolbars,
				params.bracket_color_repeated_toolbars,
				params.bracket_color_page_nav_keys,
				params.bracket_color_expandable_tools)

          # Find the new location of the current page in the newly-rebuilt
          # pages and update it
          pages.locate_current_page(new_toolbar, last_action_pressed)

        update_streamdeck_keys = True

      # Calculate the next time we need to get the list of toolbars and actions
      next_actions_update_tstamp = now + params.check_toolbar_updates_every

    # Should we update the Stream Deck keys?
    if update_streamdeck_keys:

      # Get what each key should display. If we don't have a current page
      # anymore, clear all the keys
      blank_key = pages.SV * 7
      keystrings = pages.current_page.split(pages.SK) \
			if pages.current_page else \
		[blank_key] * streamdeck.nbkeys

      # Update the keys that display something different
      for keyno, ks in enumerate(keystrings[:streamdeck.nbkeys]):
        if ks != displayed_keys[keyno]:

          # The last two fields are the colors of the left and right brackets
          # in the pages layout, the mark and its color in the folders layout.
          # In the folders layout, the marker ends with the level's background
          # color
          marker, n, enabled, _, tt, bt, f7, f8 = ks.split(pages.SV)

          # Write the text of disabled tools in grey. The page keys get a
          # dimmed icon instead, and keep their page number readable. The
          # Workbench key at the top of the workbench list does nothing but
          # stays in color
          dimmed = enabled == "0" and n not in (StreamDeckFolders.PAGEPREV,
					StreamDeckFolders.PAGENEXT,
					StreamDeckFolders.PAGEBACK,
					StreamDeckFolders.WORKBENCH_LIST)

          try:
            if folders_layout:
              streamdeck.set_key(keyno, key_image(n, enabled), tt, bt,
					dimmed = dimmed, label_lines = 2,
					mark = f7, mark_color = f8,
					background = marker.rpartition(
						StreamDeckFolders.BG_SEP)[2])
            else:
              streamdeck.set_key(keyno, key_image(n, enabled), tt, bt,
					f7, f8, dimmed = dimmed)
            displayed_keys[keyno] = ks

          except:
            streamdeck.close()
            del(tbactions)
            del(pages)
            del(useractivity)
            break

  # Determine if the user is active and set the brightness of the Stream Deck's
  # display accordingly
  if streamdeck.is_open():

    ua = useractivity.is_active(now, params.fade_after_secs_inactivity \
					if params.fading_enabled else None,
					[input_events, parameters_synchronized])
    try:
      streamdeck.set_brightness(params.min_brightness, params.max_brightness,
				params.fade_time, ua)
    except:
      streamdeck.close()
      del(tbactions)
      del(pages)
      del(useractivity)

  # Reschedule ourselves
  timer.start(timer_reschedule_every_ms)



## Main routine
#

def start(FreeCAD):
  """Start the addon
  """

  global params

  global main_window

  global streamdeck
  global streamdeck_was_open
  global show_help
  global retry_open_at_tstamp
  global recreate_pages

  global timer
  global timer_reschedule_every_ms
  global next_actions_update_tstamp

  # Determine the installation directory
  install_dir = os.path.dirname(__file__)
  as_installed = lambda f: os.path.abspath(os.path.join(install_dir, f))

  # If the package.xml file is around, try to extract the version number from it
  # and display it
  try:
    with open(as_installed("package.xml"), "r") as f:
      print("*** Stream Deck Addon version {} ***".
		format(re.search(r"<version>\s*(\S+)\s*</version>",
			f.read())[1]))
  except Exception as e:
    pass

  # Create the parameters
  params = UserParameters(FreeCAD)

  # Make sure the streamdeck module will find the HIDAPI library. This is only
  # ever needed on macOS, where Homebrew and MacPorts install it outside of the
  # directories the dynamic linker searches by default
  hidapi_ok, hidapi_info = platform_support.ensure_hidapi_loadable()
  if not hidapi_ok:
    print("-" * 79)
    for l in hidapi_info:
      print(l)
    print("-" * 79)

  # Get the name of the preferred font to write in the Stream Deck keys
  # depending on the platform. If it can't be loaded, the StreamDeck object
  # falls back on the other fonts usually available on this platform
  font_filename = params.streamdeck_key_text_font_filename_windows \
				if platform_support.IS_WINDOWS else \
			params.streamdeck_key_text_font_filename_macos \
				if platform_support.IS_MACOS else \
			params.streamdeck_key_text_font_filename_linux

  # Initialize the streamdeck object
  streamdeck = StreamDeck(font_filename, params.streamdeck_key_text_font_size,
				as_installed(params.prev_streamdeck_key_icon),
				as_installed(params.next_streamdeck_key_icon),
				as_installed(params.blank_streamdeck_key_icon),
				as_installed(params.broken_streamdeck_key_icon),
				font_dirs = [install_dir],
				back_image_file = \
					as_installed(params.back_streamdeck_key_icon),
				workbench_image_file = \
					as_installed(params.workbench_streamdeck_key_icon))
  streamdeck_was_open = None
  show_help = True
  retry_open_at_tstamp = 0
  recreate_pages = False

  # Timer interval in milliseconds
  timer_reschedule_every_ms = round(params.check_streamdeck_every * 1000)

  # What time we should update the toolbars and actions next
  next_actions_update_tstamp = 0

  # Get the main window
  main_window = Gui.getMainWindow()

  # Set up the single-short timer, connect it to the Stream Deck update routine
  timer = QtCore.QTimer()
  timer.setSingleShot(True)
  timer.timeout.connect(streamdeck_update)

  # If we have a shell command to execute when starting, execute it
  if params.exec_cmd_start:
    os.system(params.exec_cmd_start)

  # Connect the main window's destroyed() signal to the shutdown callback
  main_window.destroyed.connect(shutdown)

  # Schedule the timer for the first itme
  timer.start()
