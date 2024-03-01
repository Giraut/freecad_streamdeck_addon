"""FreeCAD Stream Deck Addon - Main program
"""

## Modules
#

import parameters as params

import os
import sys
import appdirs
import importlib
from time import time

import FreeCADGui as Gui
from PySide import QtCore

from streamdeck_comm import StreamDeck
from gui_actions import ToolbarActions
from streamdeck_pages import StreamDeckPages



## Classes
#

class UserActivity():
  """Class to check if the user is active or idle based on cursor movements
  If the cursor hasn't moved within inactivity_time, the user is deemed inactive
  If inactivity_time is None, the check is disabled and the user is deemed
  active all the time
  """

  def __init__(self, main_window, inactivity_time):
    """__init__ method
    """

    self.main_window = main_window

    self.inactivity_time = inactivity_time

    self.main_window_is_active = True

    self.cursor_pos = None
    self.last_cursor_movement_tstamp = None



  def is_active(self, now):
    """Determine if the user is active based on cursor movements and whether
    they occur while the main window is active
    If the main window isn't active, the user is busy doing something else,
    therefore reputed inactive here
    If the cursor hasn't moved within inactivity_time, return False
    """

    if not self.inactivity_time:
      return True

    if self.cursor_pos is None:
      self.cursor_pos = main_window.cursor().pos()
      self.last_cursor_movement_tstamp = now
      return True

    prev_main_window_is_active = self.main_window_is_active
    self.main_window_is_active = main_window.isActiveWindow()

    prev_cursor_pos = self.cursor_pos

    if self.main_window_is_active:
      self.cursor_pos = self.main_window.cursor().pos()

      if not prev_main_window_is_active or self.cursor_pos != prev_cursor_pos:
        self.last_cursor_movement_tstamp = now

    return now - self.last_cursor_movement_tstamp < self.inactivity_time



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



def streamdeck_update():
  """Mirror the current content of the Freecad toolbars onto the stream deck
  """

  global main_window

  global streamdeck
  global streamdeck_was_open
  global show_help

  global update_actions

  global tbactions
  global pages
  global useractivity

  global last_action_pressed

  global timer
  global timer_reschedule_every_ms
  global next_actions_update_tstamp

  now = time()

  update_streamdeck_keys = False

  # If the Stream Deck device is not open, try to open it
  if not streamdeck.is_open():

    streamdecks_info = streamdeck.open(params.use_streamdeck_device_type,
					params.use_streamdeck_device_serial,
					params.streamdeck_brightness_fade_to,
					params.streamdeck_brightness,
					params.streamdeck_brightness_fade_time)

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

    tbactions = ToolbarActions(main_window,
					params.exclude_toolbars_from_streamdeck,
					action_changed)
    update_actions = True

    pages = StreamDeckPages(
		params.toolbars_on_every_streamdeck_page,
		params.brackets_color_for_toolbars_on_every_streamdeck_page,
		params.brackets_color_for_streamdeck_page_navigation_keys,
		params.brackets_color_for_expandable_tool_buttons,
		streamdeck.nbkeys)

    useractivity = UserActivity(main_window, params.\
			streamdeck_brightness_fade_when_user_inactive_for)

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
  except:
    streamdeck.close()
    del(tbactions)
    del(pages)
    del(useractivity)

  # Process Stream Deck key press events if a current page is displayed
  if streamdeck.is_open() and pages.current_page:
    keystrings = pages.current_page.split(";")

    for is_long_press, key in pressed_keys:

      n = keystrings[key].split("~")[1]

      # Is the key occupied?
      if n:

        # Change the page
        if n in ("PAGEPREV", "PAGENEXT"):
          last_action_pressed = None
          pages.flip(to_next_page = n == "PAGENEXT")
          update_streamdeck_keys = True

        # Act upon a real action
        else:
          last_action_pressed = tbactions.actions[n]

          # Long key press?
          if is_long_press:

            # If the action is expandable, toggle its expansion and
            # force-rebuild all the pages
            if n in tbactions.expanded_actions:
              tbactions.expanded_actions[n] = \
			not tbactions.expanded_actions[n]
              update_actions = True
              next_actions_update_tstamp = 0

            # If the action is a subaction of another action toggle the parent
            # action's expansion and force-rebuild all the pages
            elif tbactions.actions[n].issubactionof is not None and \
			tbactions.actions[n].issubactionof in \
					tbactions.expanded_actions:
              tbactions.expanded_actions[tbactions.actions[n].issubactionof] = \
			not tbactions.expanded_actions[tbactions.actions[n].\
								issubactionof]
              update_actions = True
              next_actions_update_tstamp = 0

          # Short key press: if the action is enabled, execute it
          elif tbactions.actions[n].enabled:
            tbactions.actions[n].action.trigger()

  # Should we get the current state of the FreeCAD toolbars and update the
  # Stream Deck pages?
  if streamdeck.is_open() and not update_streamdeck_keys and \
	now > next_actions_update_tstamp:

    # Update the currently displayed toolbar actions
    if tbactions.extract_toolbar_actions_from_gui(update_actions):
      update_actions = False

      # Find out the first of the new toolbars, if there are new toolbars, so
      # we can switch to it on the Stream Deck display
      new_toolbar = None
      for t in tbactions.toolbars:
        if t not in tbactions.previous_toolbars and \
		t not in params.toolbars_on_every_streamdeck_page:
          new_toolbar = t
          break

      # Rebuild the entire set of Stream Deck pages using the updated toolbars
      # and actions
      pages.rebuild_pages(tbactions)

      # Find the new location of the current page in the newly-rebuilt pages
      # and update it
      pages.locate_current_page(new_toolbar, last_action_pressed)

      update_streamdeck_keys = True

    # Calculate the next time we need to update the Stream Deck keys
    next_actions_update_tstamp = now + params.check_toolbar_updates_every

  # Should we update the Stream Deck keys?
  if streamdeck.is_open() and update_streamdeck_keys:

    # Update the keys that need updating
    if not pages.current_page:

      # Clear all the Stream Deck keys if we don't have a current page anymore
      if pages.previous_current_page:
        for keyno in range(streamdeck.nbkeys):
          try:
            streamdeck.set_key(keyno, None)
          except:
            streamdeck.close()
            del(tbactions)
            del(pages)
            del(useractivity)
            break

    # Update the keys to display the current page as needed
    else:
      keystrings = pages.current_page.split(";")
      if pages.previous_current_page:
        prev_keystrings = pages.previous_current_page.split(";")

      for keyno, ks in enumerate(keystrings):
        if not pages.previous_current_page or ks != prev_keystrings[keyno]:

          _, n, _, _, tt, bt, lbc, rbc = ks.split("~")
          img = n if n in ("", "PAGEPREV", "PAGENEXT") else \
		tbactions.actions[n].icon_as_pil_image()

          try:
            streamdeck.set_key(keyno, img, tt, bt, lbc, rbc)
          except:
            streamdeck.close()
            del(tbactions)
            del(pages)
            del(useractivity)
            break

  # Determine if the user is active and set the brightness of the Stream Deck's
  # display accordingly
  if streamdeck.is_open():

    ua = useractivity.is_active(now)

    try:
      streamdeck.set_brightness(pressed_keys or update_streamdeck_keys or ua)
    except:
      streamdeck.close()
      del(tbactions)
      del(pages)
      del(useractivity)

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
	"streamdeck_brightness": 80,
	"streamdeck_brightness_fade_to": 0,
	"streamdeck_brightness_fade_time": 10,
	"streamdeck_brightness_fade_when_user_inactive_for": None}

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

# What time we should update the toolbars and actions next
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
