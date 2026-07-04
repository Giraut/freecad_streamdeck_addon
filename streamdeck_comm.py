"""FreeCAD Stream Deck Addon - Stream Deck device handling class
"""

## Modules
#

from time import time

from PIL import Image, ImageDraw, ImageFont

from StreamDeck.Devices.StreamDeck import ControlType, DialEventType
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper



## Classes
#

class StreamDeck():
  """Stream Deck handling class
  """

  # Input event types
  SHORT_KEYPRESS = 0
  LONG_KEYPRESS = 1
  DIAL_SPIN_CLICKS = 2



  def __init__(self, ttf_file, ttf_size, prev_image_file, next_image_file,
		blank_image_file, broken_image_file):
    """__init__ method
    Load the specified TrueType font of the specified size and load the
    predefined images
    """

    self.dev = None
    self.nbkeys = None
    self.nbdials = None

    self.__key_states_tstamps = None
    self.__brightness = None
    self.__fade_start_tstamp = None
    self.__key_image_cache = {}

    # Load the TrueType font
    self.ttf_file = ttf_file
    self.font = ImageFont.truetype(ttf_file, ttf_size)

    # Preload icons for the Stream Deck keys
    self.prev_image = Image.open(prev_image_file)
    self.next_image = Image.open(next_image_file)
    self.blank_image = Image.open(blank_image_file)
    self.broken_image = Image.open(broken_image_file)

    # Determine the margins between the icon and the edges of the Stream Deck
    # keys to leave just enough space for the top and bottom text
    _, font_text_min_y, _, font_text_max_y = self.font.getbbox("A!_j")
    self.margins = [font_text_max_y - font_text_min_y + 1] * 4



  def initials_icon(self, name):
    """Build a placeholder icon showing the initials of each word of name (e.g.
    "B-Spline Tools" -> "BT"), for use as an icon representing a named group
    such as a toolbar that has no icon of its own
    Return the blank icon if name is empty or blank
    """

    initials = "".join(w[0] for w in name.split()).upper() if name else ""

    if not initials:
      return self.blank_image

    icon = self.blank_image.copy()
    icon = icon.convert("RGB")

    # Find the largest font size that fits the initials within the icon, down
    # to a minimum size below which we just let the text overflow
    font_size = icon.height
    while font_size > 8:
      font = ImageFont.truetype(self.ttf_file, font_size)
      left, top, right, bottom = font.getbbox(initials)
      if right - left <= icon.width * 0.85 and bottom - top <= icon.height * 0.7:
        break
      font_size -= 2

    draw = ImageDraw.Draw(icon)
    draw.text((icon.width / 2, icon.height / 2), text = initials, font = font,
			anchor = "mm", fill = "yellow")

    return icon



  def open(self, device_type, serial_number):
    """Try to open and reset the Stream Deck device with the specified device
    type and serial number (case-independent)
    If device_type is None, any device type is valid
    If serial_number is None, any serial number is valid
    Return information lines summarizing what devices were found and which was
    opened, or what happened if the open failed
    """

    self.dev = None
    self.__key_states_tstamps = None
    self.__key_image_cache = {}

    dev_sns = None
    info = []

    # Get a list of available Stream Deck devices and their serial numbers if
    # possible
    try:
      dev_sns = {d: None for d in DeviceManager().enumerate()}
      if dev_sns:
        info.append("Stream Deck devices found:")

    except Exception as e:
      info.append("Error finding available Stream Deck devices: {}".format(e))
      dev_sns = None

    # Did we find devices?
    if dev_sns is not None:

      # Get the serial numbers of the available Stream Deck devices if possible
      for self.dev in dev_sns:
        try:
          self.dev.device.open()
          dev_sns[self.dev] = self.dev.get_serial_number()
          info.append('  Type "{}": serial number "{}"'.
			format(self.dev.deck_type(), dev_sns[self.dev]))
        except Exception as e:
          info.append('  Type "{}": could not get serial number: {}'.
			format(self.dev.deck_type(), e))

        if self.dev is not None:
          try:
            self.dev.close()
          except:
            pass

      # Try to match a device to open
      for self.dev in dev_sns:
        if not device_type or \
		self.dev.deck_type().lower() == device_type.lower():
          if not serial_number or \
		(dev_sns[self.dev] and \
			dev_sns[self.dev].lower() == serial_number.lower()):
            info.append('Using Stream Deck type "{}" {}'.
			format(self.dev.deck_type(),
				'with serial number "{}"'.
					format(dev_sns[self.dev]) \
						if dev_sns[self.dev] else ""))

            # Open the device
            try:
              self.dev.device.open()
              self.dev._reset_key_stream()

            except Exception as e:
              info.append('  Error opening the device: {}"'.format(e))
              try:
                self.dev.close()
              except:
                pass
              self.dev = None

            # If the open was successful, stop trying
            if self.dev is not None:
              self.nbkeys = self.dev.key_count()
              self.nbdials = self.dev.dial_count()
              break

      else:
        info.append("Stream Deck {}{}not found".format(
			"" if not device_type else \
			'type "{}" '.format(device_type),
			"" if not serial_number else \
			'with serial number "{}" '.format(serial_number)))
        self.dev = None

    return info



  def close(self):
    """Try to reset and close the Stream Deck
    Ignore errors
    """

    if self.dev is not None:

      # Try to reset the Stream Deck
      try:
        self.dev.reset()
      except:
        pass

      # Set the brightness of the Stream Deck's display to 0 to preserve it
      try:
        self.dev.set_brightness(0)
      except:
        pass

      # Try to close the Stream Deck
      try:
        self.dev.close()
      except:
        pass

      self.dev = None
      self.nbkeys = None
      self.__key_states_tstamps = None
      self.__brightness = None
      self.__fade_start_tstamp = None
      self.__key_image_cache = {}


  def is_open(self):
    """Return whether the Stream Deck is open
    """

    return self.dev is not None



  def get_input_events(self, long_keypress_duration):
    """Detect short key presses - i.e. keys going back up after being down for
    a short time - or long key presses - i.e. keys staying down for a long time
    Long keypress duration is how long a key press should last to be considered
    a long press
    Also detect dial spin clicks if the device has dials
    Return a list of (event_type, keyno or dial_spin_clicks) tuples
    """

    input_events = []

    # Get and process input events until we run out
    while True:

      now = time()

      prev_key_states_tstamps = self.__key_states_tstamps

      # Read events from the Stream Deck
      events = self.dev._read_control_states()
      key_states = None
      dial_spin_clicks = 0	# -n = dials spun n clicks counterclockwise,
				# +n = dials spun n clicks clockwise

      # Process the events
      for ct in events if events is not None else {}:

        # Is the event a key state change?
        if ct == ControlType.KEY:
          key_states = events[ct][:self.dev.KEY_COUNT]

        # Do we have dial events?
        elif ct == ControlType.DIAL:

          # Process the dial events
          for dt in events[ct]:

            # Is the event a dial turn?
            if dt == DialEventType.TURN:

              # Use all the dial indiscriminately to count the overall number
              # of dial clicks clockwise or counterclockwise
              dial_spin_clicks = sum(events[ct][dt])

      # If we have a non-zero number of dial clicks, add it to the input events
      if dial_spin_clicks:
        input_events.append((self.DIAL_SPIN_CLICKS, dial_spin_clicks))

      # If there was no previous key press timestamps, initialize the current
      # key press timestamps and return empty key presses
      if not prev_key_states_tstamps:
        self.__key_states_tstamps = [None] * self.dev.KEY_COUNT
        return input_events

      self.__key_states_tstamps = []

      # Determine the current key states
      if key_states is None:
        key_states = [ts is not None for ts in prev_key_states_tstamps]

      # Determine the current key presses
      for i, ks in enumerate(key_states):

        # The key is down
        if ks:

          # If it was up, record the time it went down
          if prev_key_states_tstamps[i] is None:
            self.__key_states_tstamps.append(now)

          # It was already down
          else:

            # If it was down for long enough, register a long key press event
            # and mark the key as down but "spent"
            if prev_key_states_tstamps[i] > 0 and \
		now - prev_key_states_tstamps[i] > long_keypress_duration:
              input_events.append((self.LONG_KEYPRESS, i))
              self.__key_states_tstamps.append(0)

            # The key was down but already "spent": carry on the previous state
            else:
              self.__key_states_tstamps.append(prev_key_states_tstamps[i])

        # The key is up
        else:

          # If it was down, register a short key press event
          if prev_key_states_tstamps[i]:
            input_events.append((self.SHORT_KEYPRESS, i))

          # Clear the status of the key
          self.__key_states_tstamps.append(None)

      # We didn't receive any event in this round
      if events is None:
        break

    return input_events



  def keys_down(self):
    """Return the set of key numbers currently held down, based on the state
    determined by the last call to get_input_events()
    """

    return {i for i, ts in enumerate(self.__key_states_tstamps or []) \
			if ts is not None}



  def set_key(self, keyno, cache_key, image_provider,
		top_text = None, bottom_text = None,
		left_bracket_color = None, right_bracket_color = None):
    """Upload an image to a Stream Deck key number with optional text at the top
    and at the bottom, and optional colored brackets left and right of the
    image
    cache_key identifies the icon returned by image_provider (e.g. an action's
    icon cache key and enabled state, or "", "PAGEPREV", "PAGENEXT"): the fully
    rendered key image (icon scaled plus any text and brackets) is cached and
    reused for as long as cache_key and the text/bracket arguments are
    unchanged, so image_provider is only called - and the icon only scaled,
    drawn on and converted - on a cache miss
    image_provider is a callable taking no argument, returning either None or
    "" for the blank icon, "PAGEPREV"/"PAGENEXT" for the previous/next icon, or
    a PIL image
    In case of error loading the image and/or scaling it, load and scale a
    "broken image" icon instead
    """

    full_cache_key = (cache_key, top_text, bottom_text,
			left_bracket_color, right_bracket_color)
    native_image = self.__key_image_cache.get(full_cache_key)

    # Do we need to render this key image?
    if native_image is None:

      image = image_provider()

      if not image:
        image = self.blank_image

      elif image == "PAGEPREV":
        image = self.prev_image

      elif image == "PAGENEXT":
        image = self.next_image

      try:
        image = PILHelper.create_scaled_image(self.dev, image,
						margins = self.margins)

      except:
        image = PILHelper.create_scaled_image(self.dev, self.broken_image,
						margins = self.margins)

      xm = image.width / 2	# Middle horizontal coordinate in the image
      xr = image.width - 1	# Right horizontal coordinate in the image
      yb = image.height - 1	# Bottom vertical coordinate in the image

      # Do we have text or brackets to add to the icon?
      if top_text or bottom_text or left_bracket_color or right_bracket_color:

        # If we have text, write it on top of the image
        draw = ImageDraw.Draw(image)

        if top_text:
          draw.text((xm, 0), text = top_text,
			font = self.font, anchor = "mt", fill = "white")

        if bottom_text:
          draw.text((xm, yb), text = bottom_text,
			font = self.font, anchor = "mb", fill = "white")

        # If we have brackets, draw them. If the color name is incorrect,
        # default to dark grey
        if left_bracket_color:
          for color in (left_bracket_color, "darkslategrey"):
            try:
              draw.line([(self.margins[3] - 2, self.margins[0] + 2),
			(4, self.margins[0] + 2),
			(4, yb - self.margins[2] - 2),
			(self.margins[3] - 2, yb - self.margins[2] - 2)],
			width = 5, fill = color)
              break
            except:
              pass

        if right_bracket_color:
          for color in (right_bracket_color, "darkslategrey"):
            try:
              draw.line([(xr - self.margins[1] + 2, self.margins[0] + 2),
			(xr - 4, self.margins[0] + 2),
			(xr - 4, yb - self.margins[2] - 2),
			(xr - self.margins[1] + 2, yb - self.margins[2] - 2)],
			width = 5, fill = color)
              break
            except:
              pass

      native_image = PILHelper.to_native_key_format(self.dev, image)
      self.__key_image_cache[full_cache_key] = native_image

    # Upload the image to the key
    self.dev.set_key_image(keyno, native_image)



  def set_brightness(self, min_brightness, max_brightness, fade_time,
			user_active = True):
    """Set the brightness of the Stream Deck's display
    If the user is active, set the maximum brightness
    If the user is inactive, set the brightness according to how long they have
    been inactive, down the the minimum brightness
    """

    # Is the user active?
    if user_active:
      self.__fade_start_tstamp = None

      # Set the maximum brightness if it's not already set
      if self.__brightness is None or self.__brightness != max_brightness:
        self.__brightness = max_brightness
        self.dev.set_brightness(self.__brightness)

    # The user is inactive
    else:
      now = time()

      # If the user was previously active, mark the start of the inactivity
      if self.__fade_start_tstamp is None:
        self.__fade_start_tstamp = now

      # Calculate the brightness based on how long the user has been inactive
      if fade_time == 0 or now - self.__fade_start_tstamp > fade_time:
        b = min_brightness
      else:
        b = round(max(min_brightness,
			max_brightness - (now - self.__fade_start_tstamp) * \
			(max_brightness - min_brightness) / fade_time))

      # Set the brightness value if it's different from the one already set
      if b != self.__brightness:
        self.__brightness = b
        self.dev.set_brightness(self.__brightness)
