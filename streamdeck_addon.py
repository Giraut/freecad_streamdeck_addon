"""FreeCAD Stream Deck Addon - Main program
"""

## Modules
#


import os
import sys
from time import time

import FreeCADGui as Gui
from PySide import QtCore

from parameters import UserParameters
from streamdeck_comm import StreamDeck
from gui_actions import ToolbarActions
from streamdeck_pages import StreamDeckPages



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
      self.cursor_pos = main_window.cursor().pos()
      self.last_activity_tstamp = now
      return True

    prev_main_window_is_active = self.main_window_is_active
    self.main_window_is_active = main_window.isActiveWindow()

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
    # of toolbars displayed on every Stream Deck page or any of the bracket
    # colors have changed, force a full update of the list of toolbars and
    # toolbar actions, and rebuilding of the Stream Deck pages
    if params.excluded_toolbars != params.prev_excluded_toolbars or \
	params.repeated_toolbars != params.prev_repeated_toolbars or \
	params.bracket_color_repeated_toolbars != \
			 params.prev_bracket_color_repeated_toolbars or \
	params.bracket_color_page_nav_keys != \
			params.prev_bracket_color_page_nav_keys or \
	params.bracket_color_expandable_tools != \
			params.prev_bracket_color_expandable_tools:
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

    pages = StreamDeckPages(streamdeck.nbkeys)

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
        print("Long-press buttons between {} brackets to expand/collapse them".
		format(params.bracket_color_expandable_tools.lower()))
        print("Buttons between {} brackets are available on all pages".
		format(params.bracket_color_repeated_toolbars.lower()))

        show_help = False

      print("-" * 79)

      streamdeck_was_open = True

  # Get Stream Deck key press events
  try:
    pressed_keys = streamdeck.get_keypresses(params.long_keypress_duration)
  except:
    streamdeck.close()
    del(tbactions)
    del(pages)
    del(useractivity)

  # Is the Stream Deck still open?
  if streamdeck.is_open():

    # Process Stream Deck key press events if a current page is displayed
    if pages.current_page:
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
                tbactions.expanded_actions[
				tbactions.actions[n].issubactionof] = \
			not tbactions.expanded_actions[
				tbactions.actions[n].issubactionof]
                update_actions = True
                next_actions_update_tstamp = 0

            # Short key press: if the action is enabled, execute it
            elif tbactions.actions[n].enabled:
              tbactions.actions[n].action.trigger()

    # Should we get the current state of the FreeCAD toolbars and update the
    # Stream Deck pages?
    if not update_streamdeck_keys and now > next_actions_update_tstamp:

      # Get the list of toolbars and toolbar actions currently displayed
      if tbactions.extract_toolbar_actions_from_gui(params.excluded_toolbars,
							update_actions):
        update_actions = False

        # Find out the first of the new toolbars, if there are new toolbars, so
        # we can switch to it on the Stream Deck display
        new_toolbar = None
        for t in tbactions.toolbars:
          if t not in tbactions.previous_toolbars and \
		t not in params.repeated_toolbars:
            new_toolbar = t
            break

        # Rebuild the entire set of Stream Deck pages using the updated toolbars
        # and actions
        pages.rebuild_pages(tbactions, params.repeated_toolbars,
				params.bracket_color_repeated_toolbars,
				params.bracket_color_page_nav_keys,
				params.bracket_color_expandable_tools)

        # Find the new location of the current page in the newly-rebuilt pages
        # and update it
        pages.locate_current_page(new_toolbar, last_action_pressed)

        update_streamdeck_keys = True

      # Calculate the next time we need to get the list of toolbars and actions
      next_actions_update_tstamp = now + params.check_toolbar_updates_every

    # Should we update the Stream Deck keys?
    if update_streamdeck_keys:

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

    ua = useractivity.is_active(now, params.fade_after_secs_inactivity \
					if params.fading_enabled else None,
					[pressed_keys, parameters_synchronized])
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

  global timer
  global timer_reschedule_every_ms
  global next_actions_update_tstamp

  # Create the parameters
  params = UserParameters(FreeCAD)

  # Determine the platform
  is_win = sys.platform[0:3] == "win"

  # Determine the installation directory
  install_dir = os.path.dirname(__file__)
  as_installed = lambda f: os.path.abspath(os.path.join(install_dir, f))

  # Get the name of the appropriate font to write in the Stream Deck keys
  # depending on the platform
  font_filename = params.streamdeck_key_text_font_filename_windows \
				if is_win else \
			params.streamdeck_key_text_font_filename_linux

  # Initialize the streamdeck object
  streamdeck = StreamDeck(font_filename, params.streamdeck_key_text_font_size,
				as_installed(params.prev_streamdeck_key_icon),
				as_installed(params.next_streamdeck_key_icon),
				as_installed(params.blank_streamdeck_key_icon),
				as_installed(params.broken_streamdeck_key_icon))
  streamdeck_was_open = None
  show_help = True
  retry_open_at_tstamp = 0

  # Timer interval in milliseconds
  timer_reschedule_every_ms = round(params.check_streamdeck_keypress_every \
					* 1000)

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
