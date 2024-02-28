"""FreeCAD Stream Deck Addon - Main program
"""

## Modules
#

import parameters as params

import re
import io
import os
import sys
from copy import copy
from time import time
from PIL import Image, ImageDraw, ImageFont

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from StreamDeck.Devices.StreamDeck import ControlType
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper



## Classes
#

class Action():
  """Single known displayed action descriptor
  """

  def __init__(self, toolbar, action, issubactionof = None):
    """__init__ method
    """

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

def open_streamdeck():
  """Try to open and reset the Stream Deck device
  """
  global streamdeck
  global show_streamdecks_info

  streamdeck = None
  dev_sns = None

  # Get a list of available Stream Deck devices and their serial numbers if
  # possible
  try:
    dev_sns = {d: None for d in DeviceManager().enumerate()}
    if dev_sns and show_streamdecks_info:
      print("Stream Deck devices found:")

  except Exception as e:
    if show_streamdecks_info:
      print("Error finding available Stream Deck devices: {}".format(e))
      return

  if dev_sns is not None:

    # Get the serial numbers of the available Stream Deck devices if possible
    for streamdeck in dev_sns:
      try:
        streamdeck.device.open()
        dev_sns[streamdeck] = streamdeck.get_serial_number()
        streamdeck.device.close()
        if show_streamdecks_info:
          print('  Type "{}": serial number "{}"'.
			format(streamdeck.deck_type(), dev_sns[streamdeck]))
      except Exception as e:
        if show_streamdecks_info:
          print('  Type "{}": could not get serial number: {}'.
			format(streamdeck.deck_type(), e))
        try:
          streamdeck.close()
        except:
          pass

    # Try to match a device to open
    for streamdeck in dev_sns:
      if not params.use_streamdeck_device_type or \
		streamdeck.deck_type().lower() == \
			params.use_streamdeck_device_type.lower():
        if not params.use_streamdeck_device_serial or \
		(dev_sns[streamdeck] and \
			dev_sns[streamdeck].lower() == \
				params.use_streamdeck_device_serial.lower()):
          if show_streamdecks_info:
            print('Using Stream Deck type "{}"{}'.
			format(streamdeck.deck_type(),
				'with serial number "{}"'.
					format(dev_sns[streamdeck]) \
				if dev_sns[streamdeck] else ""))

          # Open the device
          try:
            streamdeck.device.open()
            streamdeck._reset_key_stream()

          except Exception as e:
            if show_streamdecks_info:
              print('Error opening the device: {}"'.format(e))
            try:
              streamdeck.close()
            except:
              pass
            streamdeck = None
            break

          # Set the brightness of the Stream Deck's screen
          try:
            streamdeck.set_brightness(params.streamdeck_brightness)
          except Exception as e:
            if show_streamdecks_info:
              print('Error setting the brightness to {}: {}"'.
			format(params.streamdeck_brightness, e))
            try:
              streamdeck.close()
            except:
              pass
            streamdeck = None

          break

    else:
      print("Stream Deck {}{}not found".
		format("" if not params.use_streamdeck_device_type else \
			'type "{}" '.
				format(params.use_streamdeck_device_type),
			"" if not params.use_streamdeck_device_serial else \
			'with serial number "{}" '.
				format(params.use_streamdeck_device_serial)))



def close_streamdeck():
  """Try to reset and close the Stream Deck. Ignore errors.
  """
  global streamdeck

  if streamdeck is not None:

    # Try to reset the Stream Deck
    try:
      streamdeck.reset()
    except:
      pass

    # Set the brightness of the Stream Deck's screen to zero to save the screen
    try:
      streamdeck.set_brightness(0)
    except:
      pass

    # Try to close the Stream Deck
    try:
      streamdeck.close()
    except:
      pass

    streamdeck = None
    show_streamdecks_info = True



def get_streamdeck_keypresses():
  """Detect key presses (i.e. keys going from up to down). Return a list of
  detected key presses.
  """

  global streamdeck
  global key_states_tstamps

  now = time()

  prev_key_states_tstamps = key_states_tstamps
  key_presses = []

  # Read key state events from the Stream Deck
  st = streamdeck._read_control_states()
  if st is None:
    key_states = None
  else:
    key_states = st[ControlType.KEY]

  # If there was no previous key press timestamps, initialize the current
  # key press timestamps and return empty key presses
  if not prev_key_states_tstamps:
    key_states_tstamps = [None] * streamdeck.KEY_COUNT
    return key_presses

  key_states_tstamps = []

  # Determine the current key states
  if key_states is None:
    key_states = [ts is not None for ts in prev_key_states_tstamps]

  # Determine the current key presses
  for i, ks in enumerate(key_states):

    # The key is down
    if ks:

      # If it was up, record the time it went down
      if prev_key_states_tstamps[i] is None:
        key_states_tstamps.append(now)

      # It was already down
      else:

        # If it was down for long enough, register a long key press event and
        # mark the key as down but "spent"
        if prev_key_states_tstamps[i] > 0 and \
		now - prev_key_states_tstamps[i] > \
			params.streamdeck_key_long_press_duration:
          key_presses.append((True, i))
          key_states_tstamps.append(0)

        # The key was down but already "spent": carry on the previous state
        else:
          key_states_tstamps.append(prev_key_states_tstamps[i])

    # The key is up
    else:

      # If it was down, register a short key press event
      if prev_key_states_tstamps[i]:
        key_presses.append((False, i))

      # Clear the status of the key
      key_states_tstamps.append(None)

  return key_presses



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
              actions[n] = Action(t, action)
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
                      actions[sn] = Action(t, subaction, issubactionof = n)
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



def set_streamdeck_key(keyno, image, top_text = None, bottom_text = None,
			left_bracket_color = None, right_bracket_color = None):
  """Upload an image to a Stream Deck key number with optional text at the top
  and at the bottom, and optional colored brackets left and right of the image.
  If image is None or "", load a blank icon
  If image is "PAGEPREV", load the previous icon
  If image is "PAGENEXT", load the next icon
  If image is a string, load this image filen
  In case of error loading the image file and/or scaling it, load and scale a
  "broken image" icon instead
  """

  global font
  global margins
  global prev_image
  global next_image
  global blank_image
  global broken_image

  if not image:
    image = blank_image

  elif image == "PAGEPREV":
    image = prev_image

  elif image == "PAGENEXT":
    image = next_image

  try:
    image = PILHelper.create_scaled_image(streamdeck, image, margins = margins)

  except:
    image = PILHelper.create_scaled_image(streamdeck, broken_image,
						margins = margins)

  # If we have text, write it on top of the image
  if top_text or bottom_text or left_bracket_color or right_bracket_color:

    draw = ImageDraw.Draw(image)

    if top_text:
      draw.text((image.width / 2, 0),
			text = top_text,
			font = font, anchor = "mt", fill = "white")

    if bottom_text:
      draw.text((image.width / 2, image.height - 1),
			text = bottom_text,
			font = font, anchor = "mb", fill = "white")

    if left_bracket_color:
      draw.line([(margins[3] - 2, margins[0] + 2),
			(4, margins[0] + 2),
			(4, image.height - margins[2] - 3),
			(margins[3] - 2, image.height - margins[2] - 3)],
			width = 5, fill = left_bracket_color)

    if right_bracket_color:
      draw.line([(image.width - margins[1], margins[0] + 2),
			(image.width - 3, margins[0] + 2),
			(image.width - 3, image.height - margins[2] - 5),
			(image.width - margins[1],
				image.height - margins[2] - 5)],
			width = 5, fill = right_bracket_color)

  # Set the image on the key
  streamdeck.set_key_image(keyno, PILHelper.to_native_format(streamdeck, image))



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
  global current_page
  global current_page_no
  global key_states_tstamps

  global pages

  global timer
  global timer_reschedule_every_ms
  global next_actions_update_tstamp

  now = time()

  update_streamdeck_keys = False

  # If the Stream Deck device is not open, try to open it
  if streamdeck is None:
    open_streamdeck()

    # If the Stream Deck device is not open, reschedule ourselves to run in a
    # while to let the FreeCAD UI breathe a bit, it takes long enough to try
    # opening a Stream Deck device that the FreeCAD UI freezes for a short time
    # which is not desirable
    if streamdeck is None:
      print("Retrying in 30 seconds...")
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
    key_states_tstamps = None
    show_streamdecks_info = False

    # Print out a bit of help
    print()
    print("Short-press on an enabled button to activate the function")
    print("Long-press on buttons between {} brackets to expand / collapse them".
		format(params.brackets_color_for_expandable_tool_buttons))
    print("Buttons between {} brackets are available in all pages".format(
		params.brackets_color_for_toolbars_on_every_streamdeck_page))

  # Get Stream Deck key press events
  try:
    pressed_keys = get_streamdeck_keypresses()
  except:
    close_streamdeck()
    return

  # Process Stream Deck key press events if a current page is displayed
  if current_page is not None:
    keystrings = current_page.split(";")

    for is_long_press, key in pressed_keys:
      n = keystrings[key].split("~")[1]

      # Is the key occupied?
      if n:

        # Change the page
        if n in ("PAGEPREV", "PAGENEXT"):

          current_page_no = current_page_no + (-1 if n == "PAGEPREV" else +1)
          current_page_no = min(len(pages) - 1, max(0, current_page_no))

          prev_current_page = current_page
          current_page = pages[current_page_no]

          update_streamdeck_keys = True

        # Was it a long press?
        elif is_long_press:

          # If the action is expandable, toggle its expansion and force-rebuild
          # all the pages
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

        # Short press: if the action is enabled, execute it
        elif actions[n].enabled:
          actions[n].action.trigger()

  # Should we get the current state of the FreeCAD toolbars and update the
  # Stream Deck pages?
  if not update_streamdeck_keys and now > next_actions_update_tstamp:

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
      # <key0>;<key1>;...;<keyKEY_COUNT-1>
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
      while nbkeys > streamdeck.KEY_COUNT - 3:	# The last page of the new empty
						# pages should have 2 slots left
						# for the page navigation keys
						# and 1 empty slot
        empty_new_pages.append(";".join(keys[:streamdeck.KEY_COUNT - 2]) + \
				";[pageprev];[pagenext]")
        keys = keys[streamdeck.KEY_COUNT - 2:]
        nbkeys -= streamdeck.KEY_COUNT - 2

      empty_new_pages.append(";".join(keys) + \
				(";" if keys and \
				(streamdeck.KEY_COUNT - nbkeys - 2) else "") + \
				";".join(["[key]" for _ in \
				range(streamdeck.KEY_COUNT - nbkeys - 2)]) + \
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

      # If we have no pages, display nothing
      if not pages:
        current_page = None
        current_page_no = None

      # We have pages
      else:

        # If we have no current page, pick the first one
        if not current_page:
          current_page = pages[0]
          current_page_no = 0

        # If we have a new toolbar, switch to the first page containing keys
        # marked with the name of the new toolbar
        elif new_toolbar:
          r = re.compile("(^|;){}~".format(new_toolbar))
          for page_no, page in enumerate(pages):
            if r.search(page):
              current_page_no = page_no
              current_page = page
              break

        # If any of the pages have changed, try to find a page in the new pages
        # that matches it with regard to action names and placements, regardless
        # of their enabled status, regardless of their icons and regardless of
        # page navigation keys
        elif len(previous_pages) != len(pages) or \
		any([previous_pages[i] != p for i, p in enumerate(pages)]):
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
              break

          else:
            # We didn't find a matching page: try to switch to the first page
            # containing keys marked with the name of the current toolbar
            for page_no, page in enumerate(pages):
              r = re.compile("(^|;){}~".
				format(current_page.split("~", 1)[0].\
					split("#", 1)[0]))
              if r.search(page):
                current_page_no = page_no
                current_page = page
                break

            else:
              # We didn't find a matching toolbar: default to the first page
              current_page = pages[0]
              current_page_no = 0

      update_streamdeck_keys = True

    # Calculate the next time we need to update the Stream Deck keys
    next_actions_update_tstamp = now + params.check_toolbar_updates_every

  # Should we update the Stream Deck keys?
  if update_streamdeck_keys:

    # Update the keys that need updating
    if not current_page:

      # Clear all the Stream Deck keys if we don't have a current page anymore
      if prev_current_page:
        for keyno in range(streamdeck.KEY_COUNT):
          try:
            set_streamdeck_key(keyno, None)
          except:
            close_streamdeck()
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
            set_streamdeck_key(keyno, img, tt, bt, lbc, rbc)
          except:
            close_streamdeck()
            break

  # Reschedule ourselves
  timer.start(timer_reschedule_every_ms)



## Entry point
#

is_win = sys.platform[0:3] == "win"
install_dir = os.path.dirname(__file__)
in_install_dir = lambda f: os.path.abspath(os.path.join(install_dir, f))

streamdeck = None
show_streamdecks_info = True

timer_reschedule_every_ms = round(params.check_streamdeck_keypress_every * 1000)
next_actions_update_tstamp = 0

# Get the appropriate font for the platform to write in the Stream Deck keys
font_filename = params.streamdeck_key_text_font_filename_windows \
			if is_win else \
		params.streamdeck_key_text_font_filename_linux
font = ImageFont.truetype(font_filename, params.streamdeck_key_text_font_size)

# Determine the margins between the icon and the edges of the Stream Deck keys
# to leave just enough space for the top and bottom text
_, font_text_min_y, _, font_text_max_y = font.getbbox("A!_j")
margins = [font_text_max_y - font_text_min_y + 1] * 4

# Preload icons for the Stream Deck keys
prev_image = Image.open(in_install_dir(params.prev_streamdeck_key_icon))
next_image = Image.open(in_install_dir(params.next_streamdeck_key_icon))
blank_image = Image.open(in_install_dir(params.blank_streamdeck_key_icon))
broken_image = Image.open(in_install_dir(params.broken_streamdeck_key_icon))

# Get the main window
main_window = Gui.getMainWindow()

# Set up the single-short timer, connect it to the Stream Deck update routine
timer = QtCore.QTimer()
timer.setSingleShot(True)
timer.timeout.connect(streamdeck_update)

# Connect the main window's destroyed() signal to the Strem Deck close function
main_window.destroyed.connect(close_streamdeck)

# Schedule the timer for the first itme
timer.start()
