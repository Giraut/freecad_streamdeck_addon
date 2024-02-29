"""FreeCAD Stream Deck Addon - Stream Deck device handling class
"""

## Modules
#

from time import time

from PIL import Image, ImageDraw, ImageFont

from StreamDeck.Devices.StreamDeck import ControlType
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper



## Classes
#

class StreamDeck():
  """Stream Deck handling class
  """

  def __init__(self, ttf_file, ttf_size, prev_image_file, next_image_file,
		blank_image_file, broken_image_file, long_keypress_duration):
    """__init__ method
    Load the specified TrueType font of the specified size and load the
    predefined images
    """

    self.dev = None
    self.nbkeys = None
    self.__key_states_tstamps = None

    # Load the TrueType font
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

    self.long_keypress_duration = long_keypress_duration



  def open(self, device_type, serial_number, brightness):
    """Try to open and reset the Stream Deck device with the specified device
    type and serial number (case-independent), then try to set the screen's
    brightness if specified
    If device_type is None, any device type is valid
    If serial_number is None, any serial number is valid
    Return information lines summarizing what devices were found and which was
    opened, or what happened if the open failed
    """

    self.dev = None
    self.__key_states_tstamps = None

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

            # Set Stream Deck screen's brightness if the device was open
            if self.dev is not None:
              try:
                self.dev.set_brightness(brightness)
              except Exception as e:
                info.append('  Error setting the brightness to {}: {}"'.
				format(brightness, e))
                try:
                  self.dev.close()
                except:
                  pass
                self.dev = None

            # If the open was successful, stop trying
            if self.dev is not None:
              self.nbkeys = self.dev.KEY_COUNT
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

      # Set the brightness of the Stream Deck's screen to 0 to save the screen
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



  def is_open(self):
    """Return whether the Stream Deck is open
    """

    return self.dev is not None



  def get_keypresses(self):
    """Detect short key presses - i.e. keys going back up after being down for
    a short time - or long key presses - i.e. keys staying down for a long time
    Return list of (is_long_press, keyno) tuples
    """

    now = time()

    prev_key_states_tstamps = self.__key_states_tstamps
    key_presses = []

    # Read key state events from the Stream Deck
    st = self.dev._read_control_states()
    if st is None:
      key_states = None
    else:
      key_states = st[ControlType.KEY]

    # If there was no previous key press timestamps, initialize the current
    # key press timestamps and return empty key presses
    if not prev_key_states_tstamps:
      self.__key_states_tstamps = [None] * self.dev.KEY_COUNT
      return key_presses

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

          # If it was down for long enough, register a long key press event and
          # mark the key as down but "spent"
          if prev_key_states_tstamps[i] > 0 and \
		now - prev_key_states_tstamps[i] > self.long_keypress_duration:
            key_presses.append((True, i))
            self.__key_states_tstamps.append(0)

          # The key was down but already "spent": carry on the previous state
          else:
            self.__key_states_tstamps.append(prev_key_states_tstamps[i])

      # The key is up
      else:

        # If it was down, register a short key press event
        if prev_key_states_tstamps[i]:
          key_presses.append((False, i))

        # Clear the status of the key
        self.__key_states_tstamps.append(None)

    return key_presses



  def set_key(self, keyno, image,
		top_text = None, bottom_text = None,
		left_bracket_color = None, right_bracket_color = None):
    """Upload an image to a Stream Deck key number with optional text at the top
    and at the bottom, and optional colored brackets left and right of the
    image
    If image is None or "", load the blank icon
    If image is "PAGEPREV", load the previous icon
    If image is "PAGENEXT", load the next icon
    If image is a string, treat it as a filename load this image file
    In case of error loading the image file and/or scaling it, load and scale a
    "broken image" icon instead
    """

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
      image = PILHelper.create_scaled_image(self.dev, broken_image,
						margins = self.margins)

    # If we have text, write it on top of the image
    if top_text or bottom_text or left_bracket_color or right_bracket_color:

      draw = ImageDraw.Draw(image)

      if top_text:
        draw.text((image.width / 2, 0),
			text = top_text,
			font = self.font, anchor = "mt", fill = "white")

      if bottom_text:
        draw.text((image.width / 2, image.height - 1),
			text = bottom_text,
			font = self.font, anchor = "mb", fill = "white")

      if left_bracket_color:
        draw.line([(self.margins[3] - 2, self.margins[0] + 2),
			(4, self.margins[0] + 2),
			(4, image.height - self.margins[2] - 3),
			(self.margins[3] - 2,
				image.height - self.margins[2] - 3)],
			width = 5, fill = left_bracket_color)

      if right_bracket_color:
        draw.line([(image.width - self.margins[1], self.margins[0] + 2),
			(image.width - 3, self.margins[0] + 2),
			(image.width - 3, image.height - self.margins[2] - 5),
			(image.width - self.margins[1],
				image.height - self.margins[2] - 5)],
			width = 5, fill = right_bracket_color)

    # Upload the image to the key
    self.dev.set_key_image(keyno, PILHelper.to_native_format(self.dev, image))
