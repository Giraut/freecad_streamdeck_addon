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

  def __init__(self, toolbar, action):
    """__init__ method
    """

    self.toolbar = toolbar
    self.action = action
    self.enabled = action.isEnabled()
    self.title = action.iconText()
    self.iconhash = hash(action.icon())



  def icon_as_pil_image(self):
    """Convert the enabled or disabled versions of the QIcon into a PIL image
    """

    pixmap = self.action.icon().pixmap(128, 128,
					mode = QtGui.QIcon.Mode.Normal \
							if self.enabled else \
						QtGui.QIcon.Mode.Disabled)
    qba = QtCore.QByteArray()
    qbf = QtCore.QBuffer(qba)
    pixmap.save(qbf, "PPM")
    img = Image.open(io.BytesIO(qba))
    qbf.close

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
  global key_states

  key_presses = []

  prev_key_states = key_states
  st = streamdeck._read_control_states()
  if st is None:
    key_states = [False] * streamdeck.KEY_COUNT
  else:
    key_states = st[ControlType.KEY]

  if prev_key_states is None:
    return key_presses

  for i, ks in enumerate(key_states):
    if ks and not prev_key_states[i]:
      key_presses.append(i)

  return key_presses



def update_current_toolbar_actions():
  """update the ordered list of toolbar names, toolbar action names and known
  actions
  """

  global toolbars
  global toolbar_actions
  global actions

  all_actions = []
  toolbars.clear()
  toolbar_actions.clear()

  # Get the list of toolbars
  for toolbar in main_window.findChildren(QtGui.QToolBar):

    # Should we keep or ignore this toolbar?
    t = toolbar.objectName()
    if not toolbar.isHidden() and \
		t not in params.exclude_toolbars_from_streamdeck:

      # Keep the toolbar
      toolbars.append(t)

      # Get the list of buttons in this toolbar
      for button in toolbar.findChildren(QtGui.QToolButton):

        # Get the list of actions associated with this button
        new_action_names = []
        for action in button.actions():

          # Get the name of the action
          n = action.data()

          # keep the action if it has a name
          if n:
            all_actions.append(action)
            new_action_names.append(n)

        if new_action_names:
          if t not in toolbar_actions:
            toolbar_actions[t] = []
          toolbar_actions[t].extend(new_action_names)

    action_names_toolbars = {a: t for t in toolbars for a in toolbar_actions[t]}

    # Search the known actions that bear the name of the toolbar actions we want
    # to mirror on the Stream Deck
    processed_actions_ctr = {}
    for a in all_actions:

      # Ignore actions with no name, separators, actions that don't have an icon
      # associated with them and actions that aren't visible in the menu
      n = a.data()
      if not n or a.isSeparator() or a.icon is None or \
		not a.isIconVisibleInMenu():
        continue

      # Count the number of time we processed the same action name to spot
      # duplicates
      processed_actions_ctr[n] = processed_actions_ctr[n] + 1 \
					if n in processed_actions_ctr else 1

      if n and n in action_names_toolbars:

        # Add the action to the list of known actions if it isn't already known
        if n not in actions:
          actions[n] = Action(action_names_toolbars[n], a)

        else:
          # Remove duplicate actions
          if processed_actions_ctr[n] > 1:
            del(actions[n])

          else:
            # Update the known action as needed
            if actions[n].toolbar != action_names_toolbars[n]:
              actions[n].toolbar = action_names_toolbars[n]
              actions[n].action = a
              actions[n].title = iconText()
            actions[n].iconhash = hash(a.icon())
            actions[n].enabled = a.isEnabled()

    # Remove the name of the toolbar actions we didn't keep from the main
    # window's children
    for t in toolbars:
      nbactions = len(toolbar_actions[t])
      i = 0
      while i < nbactions:
        if toolbar_actions[t][i] not in actions:
          toolbar_actions[t].pop(i)
          nbactions -= 1
        else:
          i += 1



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
      draw.line([(margins[3] - 1, margins[0] + 1),
			(1, margins[0] + 1),
			(1, image.height - margins[2] - 2),
			(margins[3] - 1, image.height - margins[2] - 2)],
			width = 3, fill = left_bracket_color)

    if right_bracket_color:
      draw.line([(image.width - margins[1], margins[0] + 1),
			(image.width - 2, margins[0] + 1),
			(image.width - 2, image.height - margins[2] - 2),
			(image.width - margins[1],
				image.height - margins[2] - 2)],
			width = 3, fill = right_bracket_color)

  # Set the image on the key
  streamdeck.set_key_image(keyno, PILHelper.to_native_format(streamdeck, image))



def streamdeck_update():
  """Mirror the current content of the Freecad toolbars onto the stream deck
  """

  global toolbars
  global toolbar_actions
  global actions

  global streamdeck
  global current_page
  global current_page_no
  global key_states

  global pages

  global timer
  global timer_reschedule_every_ms
  global next_actions_update_tstamp

  now = time()

  update_streamdeck_keys = False

  # If the Stream Deck device is not open, try to open it
  if streamdeck is None:
    open_streamdeck()
    current_page = None
    key_states = None
    show_streamdecks_info = False

  # If the Stream Deck device is not open, reschedule ourselves to run in a
  # while to let the FreeCAD UI breathe a bit, it takes long enough to try
  # opening a Stream Deck device that the FreeCAD UI freezes for a short time
  # which is not desirable
  if streamdeck is None:
    print("Retrying in 30 seconds...")
    timer.start(30 * 1000)
    return

  try:
    pressed_keys = get_streamdeck_keypresses()
  except:
    close_streamdeck()
    return

  # Process Stream Deck key presses if a current page is displayed
  if current_page is not None:
    pageslist = current_page.split(";")

    for key in pressed_keys:
      n = pageslist[key].split(",")[1]

      # Is the key occupied?
      if n:

        # Change the page
        if n in ("PAGEPREV", "PAGENEXT"):

          pageslist = pages.split("\n")
          current_page_no = current_page_no + (-1 if n == "PAGEPREV" else +1)
          current_page_no = min(len(pageslist) - 1, max(0, current_page_no))

          prev_current_page = current_page
          current_page = pageslist[current_page_no]

          update_streamdeck_keys = True

        # If the action is enabled, execute it
        elif actions[n].enabled:
          actions[n].action.trigger()

  # Should we get the current state of the FreeCAD toolbars and update the
  # Stream Deck pages?
  if not update_streamdeck_keys and now > next_actions_update_tstamp:

    kpp = streamdeck.KEY_COUNT	# Keys per page

    # Update the currently displayed toolbar actions
    previous_toolbars = copy(toolbars)
    update_current_toolbar_actions()
    new_toolbar = None
    for t in toolbars:
      if t not in previous_toolbars and \
		t not in params.toolbars_on_every_streamdeck_pages:
        new_toolbar = t
        break

    # Compose the new pages to display on the Stream Deck: the pages are
    # described in a multiline string with each line in the following format:
    #
    # <key0>;<key1>;...;<keyKEY_COUNT-1>
    #
    # and each key is composed of:
    # <toolbarmarker>,[action],[0|1],[iconhash],[toptext],[bottomtext],
    #    [leftbracketcolor],[rightbracketcolor],
    #

    # Create a pattern of one or more pages (hopefully just one) that contain
    # the keys for the actions of the toolbars that should be repeated on every
    # page at the beginning, the page navigation keys at the end and at least
    # one free key slot in-between.
    keys = []
    bc = params.brackets_color_for_toolbar_on_every_streamdeck_page

    for t in params.toolbars_on_every_streamdeck_pages:
      if t in toolbars:
        last_action_i = len(toolbar_actions[t]) - 1
        keys.extend(["#[toolbar],{},{},{},{},{},{},{}".
			format(n, 1 if actions[n].enabled else 0,
				actions[n].iconhash,
				actions[n].title, t,
				bc if i == 0 else "",
				bc if i == last_action_i else "") \
			for i, n in enumerate(toolbar_actions[t])])
    nbkeys = len(keys)

    empty_new_pages = ""
    while nbkeys > kpp - 3:	# The last page of the new empty pages should
				# have 2 slots left for the page navigation keys
				# and 1 empty slot
      empty_new_pages += ";".join(keys[:kpp - 2])
      empty_new_pages += ";[pageprev];[pagenext]\n"	# Placeholders
      keys = keys[kpp - 2:]
      nbkeys -= kpp - 2

    empty_new_pages += ";".join(keys)
    if kpp - nbkeys - 2:
      empty_new_pages += ";"
    empty_new_pages += ";".join(["[key]" for _ in \
			range(kpp - nbkeys - 2)])	# Placeholders
    empty_new_pages += ";[pageprev];[pagenext]\n"	# Placeholders

    # Create the pages of action keys
    pages = ""
    prev_page_toolbar = None
    nkbc = params.brackets_color_for_streamdeck_page_navigation_keys

    for t in toolbars:
      if t not in params.toolbars_on_every_streamdeck_pages:

        # Get the list of key strings for this toolbar
        keys = ["{},{},{},{},{},{},,".
			format(t, n, 1 if actions[n].enabled else 0,
				actions[n].iconhash, actions[n].title, t)
		for n in toolbar_actions[t]]

        # Add all the keys to the pages
        for key in keys:

          # If we don't have empty key slots left, add empty pages
          if not "[key]" in pages:

            # Replace the previous page's [pagenext] placeholder, if any
            pages = pages.replace("[pagenext]",
					"{}#,PAGENEXT,,,,{},,{}".
						format(t, t, nkbc))

            # Add new pages
            pages += empty_new_pages

            # Replace the [toolbar] placeholders in the new pages with the name
            # of this toolbar
            pages = pages.replace("[toolbar]", t)

            # If we have more than one [pagenext] placeholders in the new pages,
            # replaces all but the last one too
            cpn = pages.count("[pagenext]")
            if cpn > 1:
              pages = pages.replace("[pagenext]",
					"{}#,PAGENEXT,,,,{},,{}".
						format(t, t, nkbc),
					cpn - 1)

            # Replace the first [pageprev] placeholder
            pages = pages.replace("[pageprev]",
					"{}#,PAGEPREV,,,,{},{},".
					format(t, prev_page_toolbar, nkbc) \
						 if prev_page_toolbar else \
					"{}#,,,,,,{},".format(t, nkbc), 1)
            # Replace the remaining [pageprev] placeholder if any
            pages = pages.replace("[pageprev]",
					"{}#,PAGEPREV,,,,{},{},".
						format(t, t, nkbc))

            prev_page_toolbar = t

          # Insert the next key into the pages
          pages = pages.replace("[key]", key, 1)

        # Add blank keys to complete the last page for this toolbar
        pages = pages.replace("[key]", "{},,,,,,,".format(t))

    # Replace the last [pagenext] placeholder if any and strip the trailing LF
    pages = pages[:-1].replace("[pagenext]", "{}#,,,,,,,{}".format(t, nkbc))

    # Determine the page to be displayed / updated
    prev_current_page = current_page

    # If we have no pages, display nothing
    if not pages:
      current_page = None
      current_page_no = None

    # We have pages
    else:
      pageslist = pages.split("\n")

      # If we have no current page, pick the first one
      if not current_page:
        current_page = pageslist[0]
        current_page_no = 0

      # If we have a new toolbar, switch to the first page containing keys
      # marked with the name of the new toolbar
      elif new_toolbar:
        r = re.compile("(^|;){},".format(new_toolbar))
        for page_no, page in enumerate(pageslist):
          if r.search(page):
            current_page_no = page_no
            current_page = page
            break

      # If we have a current page, try to find a page in the new pages that
      # matches it with regard to action names and placements, regardless of
      # their enabled status, regardless of their icons and regardless of page
      # navigation keys
      else:
        r = re.compile("^" + ";".join([("{},({})?(,[^;,]*){{6}}".
						format(t, n) \
						if n in ("PAGEPREV",
							"PAGENEXT") else \
					"{},{},.?,.*?,{},{},{},{}".
						format(t, n, tt, bt, lbc, rbc))\
					for t, n, _, _, tt, bt, lbc, rbc in \
						[ks.split(",") \
					for ks in current_page.split(";")]]) \
			+ "$")
        for page_no, page in enumerate(pageslist):
          if r.match(page):
            current_page_no = page_no
            current_page = page
            break

        else:
          # We didn't find a matching page: try to switch to the first page
          # containing keys marked with the name of the current toolbar
          for page_no, page in enumerate(pageslist):
            r = re.compile("(^|;){},".
				format(current_page.split(",", 1)[0].\
					strip("#")))
            if r.search(page):
              current_page_no = page_no
              current_page = page
              break

          else:
            # We didn't find a matching toolbar: default to the first page
            current_page = pageslist[0]
            current_page_no = 0

    # Calculate the next time we need to update the Stream Deck keys
    next_actions_update_tstamp = now + params.check_toolbar_updates_every

    update_streamdeck_keys = True

  # Should we update the Stream Deck keys?
  if update_streamdeck_keys:

    # Update the keys that need updating
    if not current_page:

      # Clear all the Stream Deck keys if we don't have a current page anymore
      if prev_current_page:
        for keyno in range(kpp):
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

          _, n, _, _, tt, bt, lbc, rbc = ks.split(",")
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

toolbars = []
toolbar_actions = {}
actions = {}

pages = []

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
