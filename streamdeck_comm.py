"""FreeCAD Stream Deck Addon - Stream Deck device handling class
"""

## Modules
#

from time import time

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps

from StreamDeck.Devices.StreamDeck import ControlType, DialEventType
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper

import platform_support
import key_labels



## Classes
#

class StreamDeck():
  """Stream Deck handling class
  """

  # Input event types
  SHORT_KEYPRESS = 0
  LONG_KEYPRESS = 1
  DIAL_SPIN_CLICKS = 2

  # Predefined key images
  PAGEPREV = "PAGEPREV"
  PAGENEXT = "PAGENEXT"
  PAGEBACK = "PAGEBACK"
  WORKBENCH = "WORKBENCH"	# Top-left key of the workbench list
  IMAGE_OFF_SUFFIX = ":OFF"	# Appended to a predefined image name to get a
				# dimmed version of it

  # Key text layout, in pixels
  TEXT_SIDE_PADDING = 3		# Between the text and the sides of the key
  TEXT_EDGE_PADDING = 1		# Between the text and the top / bottom edge
  TEXT_ICON_GAP = 1		# Between the text and the icon
  TEXT_LINE_SPACING = -1	# Added to the font's line height
  ICON_SIDE_MARGIN = 8		# Between the icon and the sides of the key,
				# leaving room for the brackets and marks
  ICON_EDGE_MARGIN = 3		# Between the icon and the top / bottom edge
				# when there's no text
  BRACKET_ARM_LENGTH = 8
  BRACKET_WIDTH = 5

  # Marks drawn in a corner of a key in the folders layout, sized for a 72-pixel
  # key and scaled with the key size:
  #  - MARK_MENU: a small triangle in the bottom-right corner of the icon area,
  #    like the arrow FreeCAD draws on toolbar buttons with a drop-down menu, on
  #    the tools that have a menu to open with a long press
  #  - MARK_FOLDER: a small folder in the top-right corner, on toolbar folder
  #    keys placed inside another folder. The home page shows only folders, so
  #    its folder keys don't need one
  MARK_MENU = "menu"
  MARK_FOLDER = "folder"
  MARK_EDGE_PADDING = 4		# Between a mark and the side of the key
  MARK_MENU_SIZE = 10		# Length of the sides of the triangle
  MARK_FOLDER_SIZE = (15, 11)	# Width and height of the folder
  MARK_DEFAULT_COLORS = {MARK_MENU: "whitesmoke", MARK_FOLDER: "goldenrod"}

  TEXT_COLOR = "white"
  DIMMED_TEXT_COLOR = "#8c8c8c"



  def __init__(self, ttf_file, ttf_size, prev_image_file, next_image_file,
		blank_image_file, broken_image_file, font_dirs = None,
		back_image_file = None, workbench_image_file = None):
    """__init__ method
    Load a TrueType font of the specified size and load the predefined images
    ttf_file is the preferred font file. If it can't be loaded - which is the
    normal case on macOS, where neither the Linux nor the Windows font exists -
    the platform's usual fonts are tried in turn, then Pillow's built-in font,
    so a missing font never prevents the addon from loading
    ttf_size is the largest font size used for the key text: text that doesn't
    fit is written in smaller sizes, down to about 80% of that size
    font_dirs is an optional list of extra directories to look the font up in
    """

    self.dev = None
    self.nbkeys = None
    self.nbdials = None

    self.__key_states_tstamps = None
    self.__brightness = None
    self.__fade_start_tstamp = None

    # Load the TrueType font
    self.font, self.font_file = platform_support.load_font(ttf_size,
						preferred = ttf_file,
						extra_dirs = font_dirs)

    # Font sizes to try, largest first, when fitting text in a key, and cache
    # of fonts of those sizes
    self.font_sizes = list(range(ttf_size, max(6, round(ttf_size * 0.78)) - 1,
					-1))
    self.__fonts = {ttf_size: self.font}

    # Font sizes used in the fixed layout, where all the keys get the same
    # space for two lines of text: the largest is the normal size, the others
    # are only used for words too long to fit otherwise. They're scaled to the
    # size of the keys of the device once it's open
    self.ttf_size = ttf_size
    self.set_label_font_sizes(72)

    # Preload icons for the Stream Deck keys
    self.prev_image = Image.open(prev_image_file)
    self.next_image = Image.open(next_image_file)
    self.blank_image = Image.open(blank_image_file)
    self.broken_image = Image.open(broken_image_file)
    try:
      self.back_image = Image.open(back_image_file)
    except Exception:
      self.back_image = self.prev_image
    try:
      self.workbench_image = Image.open(workbench_image_file)
    except Exception:
      self.workbench_image = self.broken_image

    # Predefined images by name, and dimmed versions of them
    self.predefined_images = {self.PAGEPREV: self.prev_image,
				self.PAGENEXT: self.next_image,
				self.PAGEBACK: self.back_image,
				self.WORKBENCH: self.workbench_image}
    for n, img in list(self.predefined_images.items()):
      self.predefined_images[n + self.IMAGE_OFF_SUFFIX] = self.dimmed_image(img)



  @staticmethod
  def with_transparency(img):
    """Return an image that can be drawn over a colored background: a
    greyscale image without transparency - white drawing on black, like the
    built-in "broken image" icon - becomes its white drawing with the black
    transparent. Other images are returned as they are
    """

    if img.mode == "L" and "transparency" not in img.info:
      white = Image.new("L", img.size, 255)
      return Image.merge("RGBA", (white, white, white, img))

    return img



  @staticmethod
  def dimmed_image(img):
    """Return the dimmed version of a predefined image, for a navigation key
    that can't be used: greyed out and faded like FreeCAD's disabled icons for
    a colour image with transparency, or simply darker for a greyscale image
    """

    if img.mode in ("RGBA", "LA", "PA") or \
		(img.mode == "P" and "transparency" in img.info):
      r, g, b, a = img.convert("RGBA").split()
      grey = ImageOps.grayscale(Image.merge("RGB", (r, g, b))).\
		point(lambda v: int(v * 0.6))
      return Image.merge("RGBA", (grey, grey, grey,
					a.point(lambda v: int(v * 0.55))))

    return img.point(lambda v: int(v * 0.3))




  def set_label_font_sizes(self, key_width):
    """Set the label font sizes used in the fixed layout in proportion to the
    width of the keys in pixels, relative to a 72-pixel key
    """

    base = self.ttf_size * key_width / 72
    self.label_font_sizes = [max(6, round(base * f)) \
				for f in (12 / 14, 11 / 14, 10 / 14)]



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

      # On macOS this almost always means the HIDAPI library is missing or was
      # built for the wrong architecture: say so rather than leaving the user
      # with a bare exception message
      if platform_support.IS_MACOS:
        ok, hidapi_info = platform_support.ensure_hidapi_loadable()
        if not ok:
          info.extend(["  " + l for l in hidapi_info])

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
              try:
                self.set_label_font_sizes(
				self.dev.key_image_format()["size"][0])
              except Exception:
                self.set_label_font_sizes(72)
              break

      else:
        if not dev_sns and platform_support.IS_MACOS:
          info.append("No HID device was enumerated at all. If the Stream Deck")
          info.append("is plugged in, check System Settings > Privacy & "
			"Security >")
          info.append("Input Monitoring and allow FreeCAD, then restart it.")

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



  def get_font(self, size):
    """Return the key text font in the specified size
    """

    if size not in self.__fonts:
      try:
        self.__fonts[size] = ImageFont.truetype(self.font_file, size)
      except Exception:
        try:
          self.__fonts[size] = ImageFont.load_default(size)
        except Exception:
          self.__fonts[size] = self.font

    return self.__fonts[size]



  @staticmethod
  def wrap_text(text, font, max_width, max_lines):
    """Break text into at most max_lines lines no wider than max_width pixels
    at word boundaries
    Return the list of lines, or None if the text doesn't fit
    """

    lines = []
    for word in text.split():
      if lines and font.getlength(lines[-1] + " " + word) <= max_width:
        lines[-1] += " " + word
      else:
        if font.getlength(word) > max_width or len(lines) == max_lines:
          return None
        lines.append(word)

    return lines



  @staticmethod
  def ellipsize_text(text, font, max_width, max_lines):
    """Break text into at most max_lines lines no wider than max_width pixels,
    truncating it with an ellipsis where it doesn't fit
    Return the list of lines
    """

    # Break the text at word boundaries, with words too long for a line on a
    # line of their own
    lines = []
    for word in text.split():
      if lines and font.getlength(lines[-1] + " " + word) <= max_width:
        lines[-1] += " " + word
      else:
        lines.append(word)

    # Put whatever doesn't fit in the last line
    if len(lines) > max_lines:
      lines = lines[:max_lines - 1] + [" ".join(lines[max_lines - 1:])]

    # Truncate the lines that are too long
    for i, l in enumerate(lines):
      if font.getlength(l) > max_width:
        while l and font.getlength(l.rstrip() + "…") > max_width:
          l = l[:-1]
        lines[i] = l.rstrip() + "…"

    return lines



  def fit_text(self, text, max_width, max_lines, sizes = None,
		prefer_full_text = False):
    """Find the best way to write text in a space max_width pixels wide and at
    most max_lines lines high, using the font sizes in sizes - by default all
    the key text font sizes - largest first
    By default, the order of preference is:
      - on one line in the largest font size that fits, down to the
        next-to-smallest size, as-is or in its compact form
      - same, on two lines, three lines...
      - same in the smallest font size
      - truncated with an ellipsis in the smallest font size
    which keeps the text short to leave the icon as much room as possible
    If prefer_full_text is asserted - when the space for the text is reserved
    anyway - the text is kept as-is on as many lines as it takes before
    resorting to its compact form, size by size
    Return (font, list of lines)
    """

    sizes = sizes or self.font_sizes

    candidates = [text]
    compact_text = key_labels.compact_label(text)
    if compact_text != text:
      candidates.append(compact_text)

    if prefer_full_text:
      for size in sizes:
        font = self.get_font(size)
        for c in candidates:
          for nblines in range(1, max_lines + 1):
            lines = self.wrap_text(c, font, max_width, nblines)
            if lines:
              return (font, lines)

    else:
      for sizes_group in (sizes[:-1] or sizes, sizes[-1:]):
        for nblines in range(1, max_lines + 1):
          for size in sizes_group:
            font = self.get_font(size)
            for c in candidates:
              lines = self.wrap_text(c, font, max_width, nblines)
              if lines:
                return (font, lines)

    font = self.get_font(sizes[-1])
    return (font, self.ellipsize_text(candidates[-1], font, max_width,
					max_lines))



  def text_block_height(self, font, nblines):
    """Height in pixels of a block of nblines lines of text written in font
    """

    ascent, descent = font.getmetrics()
    return nblines * (ascent + descent) + \
		(nblines - 1) * self.TEXT_LINE_SPACING



  def free_text_margin(self, font, nblines):
    """Margin to leave between the icon and the edge of the key for a block of
    nblines lines of text written in font, in the free layout. The icon may
    overlap the descender space of the text, which is mostly empty, as in
    previous versions, so the icons don't get smaller
    """

    _, descent = font.getmetrics()
    return self.TEXT_EDGE_PADDING + self.text_block_height(font, nblines) - \
		descent + 1



  def set_key(self, keyno, image,
		top_text = None, bottom_text = None,
		left_bracket_color = None, right_bracket_color = None,
		dimmed = False, label_lines = None,
		mark = None, mark_color = None, background = None):
    """Upload an image to a Stream Deck key number with optional text at the top
    and at the bottom, optional colored brackets left and right of the image
    - pages layout - and an optional mark in a corner - MARK_MENU or
    MARK_FOLDER, folders layout - in mark_color, or the mark's default color if
    mark_color is empty or not a color Pillow knows
    The key is drawn over the background color, black if background is empty
    or not a color Pillow knows. The transparent parts of the image let it show
    through
    If image is None or "", load the blank icon
    If image is the name of a predefined image - "PAGEPREV", "PAGENEXT" or
    "PAGEBACK", optionally followed by ":OFF" for a dimmed version - load that
    image
    If image is another string, treat it as a filename load this image file
    In case of error loading the image file and/or scaling it, load and scale a
    "broken image" icon instead
    The text is fitted into the key: it's written smaller, shortened, wrapped
    onto two lines - when there's only one text - or truncated as needed. The
    icon is scaled to whatever space the text leaves
    If label_lines is set, the key uses a fixed layout instead, so all the keys
    look alike: the bottom of the key is reserved for label_lines lines of
    bottom text - whatever the text, or even if there's no text - in the label
    font sizes, and the icon gets the same space above on every key
    If dimmed is asserted, the text and the menu mark are drawn in grey
    """

    try:
      background = ImageColor.getrgb(background.strip())
    except Exception:
      background = (0, 0, 0)

    blank = not image
    if blank:
      image = self.blank_image

    elif isinstance(image, str) and image in self.predefined_images:
      image = self.predefined_images[image]

    elif isinstance(image, str):
      try:
        image = Image.open(image)
      except:
        image = self.broken_image

    image = self.with_transparency(image)

    key_width, key_height = self.dev.key_image_format()["size"]
    max_text_width = key_width - 2 * self.TEXT_SIDE_PADDING

    margins = [self.ICON_EDGE_MARGIN, self.ICON_SIDE_MARGIN,
		self.ICON_EDGE_MARGIN, self.ICON_SIDE_MARGIN]

    # Fixed layout: reserve the bottom of the key for the label, and fit the
    # label in it, keeping it whole on several lines rather than shortening it
    # if possible
    if label_lines:
      top = self.fit_text(top_text, max_text_width, 1,
				self.label_font_sizes) if top_text else None
      bottom = self.fit_text(bottom_text, max_text_width, label_lines,
				self.label_font_sizes,
				prefer_full_text = True) \
			if bottom_text else None
      bottom_area_height = self.text_block_height(
				self.get_font(self.label_font_sizes[0]),
				label_lines)
      margins[2] = self.TEXT_EDGE_PADDING + self.TEXT_ICON_GAP + \
			bottom_area_height

    # Free layout: fit the text in as little space as possible and give the
    # icon the rest. If there's text both at the top and at the bottom, each
    # gets one line. Otherwise the text gets up to two lines
    else:
      max_lines = 1 if top_text and bottom_text else 2
      top = self.fit_text(top_text, max_text_width, max_lines) \
		if top_text else None
      bottom = self.fit_text(bottom_text, max_text_width, max_lines) \
		if bottom_text else None
      if bottom:
        bottom_area_height = self.text_block_height(bottom[0], len(bottom[1]))
        margins[2] = self.free_text_margin(bottom[0], len(bottom[1]))

    if top:
      margins[0] = self.free_text_margin(top[0], len(top[1]))

    # A blank key is just the background
    if blank:
      image = Image.new("RGB", (key_width, key_height), background)

    else:
      try:
        image = PILHelper.create_scaled_image(self.dev, image,
						margins = margins,
						background = background)

      except:
        image = PILHelper.create_scaled_image(self.dev,
					self.with_transparency(self.broken_image),
					margins = margins,
					background = background)

    xm = image.width / 2	# Middle horizontal coordinate in the image
    xr = image.width - 1	# Right horizontal coordinate in the image
    yb = image.height - 1	# Bottom vertical coordinate in the image

    # Do we have text, brackets or a mark to add to the icon?
    if top or bottom or left_bracket_color or right_bracket_color or mark:

      draw = ImageDraw.Draw(image)
      text_color = self.DIMMED_TEXT_COLOR if dimmed else self.TEXT_COLOR

      # Write the text, centered horizontally, top text downward from the top
      # edge, bottom text upward from the bottom edge
      for block, at_top in ((top, True), (bottom, False)):
        if block:
          font, lines = block
          ascent, descent = font.getmetrics()
          line_height = ascent + descent + self.TEXT_LINE_SPACING
          y = self.TEXT_EDGE_PADDING if at_top else \
		image.height - self.TEXT_EDGE_PADDING - bottom_area_height
          for l in lines:
            draw.text((xm, y), text = l, font = font, anchor = "ma",
			fill = text_color)
            y += line_height

      # If we have brackets, draw them alongside the icon. If the color name is
      # incorrect, default to dark grey
      x0 = self.BRACKET_WIDTH // 2 + 2
      y0 = margins[0] + 1
      y1 = yb - margins[2] - 1
      for color, x, d in ((left_bracket_color, x0, 1),
				(right_bracket_color, xr - x0, -1)):
        if color:
          for c in (color, "darkslategrey"):
            try:
              draw.line([(x + d * self.BRACKET_ARM_LENGTH, y0), (x, y0),
				(x, y1), (x + d * self.BRACKET_ARM_LENGTH, y1)],
				width = self.BRACKET_WIDTH, fill = c,
				joint = "curve")
              break
            except:
              pass

      # If we have a mark, draw it in its corner
      if mark in self.MARK_DEFAULT_COLORS:
        self.draw_mark(draw, mark, mark_color, dimmed, xr, yb - margins[2],
			image.width / 72)

    # Upload the image to the key
    self.dev.set_key_image(keyno, PILHelper.to_native_key_format(self.dev,
									image))



  def draw_mark(self, draw, mark, color, dimmed, xr, y_icon_bottom, scale):
    """Draw a mark in a corner of a key image: MARK_MENU at the bottom right
    of the icon area, which ends at y_icon_bottom, or MARK_FOLDER at the top
    right. xr is the rightmost coordinate of the image, and scale the size of
    the key relative to a 72-pixel key
    The menu mark of a disabled tool is greyed out like its text. A color Pillow
    doesn't know falls back to the mark's default color
    """

    if dimmed and mark == self.MARK_MENU:
      color = self.DIMMED_TEXT_COLOR

    try:
      color = ImageColor.getrgb(color.strip())
    except Exception:
      color = self.MARK_DEFAULT_COLORS[mark]

    x1 = xr + 1 - round(self.MARK_EDGE_PADDING * scale)

    if mark == self.MARK_MENU:
      s = round(self.MARK_MENU_SIZE * scale)
      draw.polygon([(x1, y_icon_bottom - s), (x1, y_icon_bottom),
			(x1 - s, y_icon_bottom)], fill = color)

    elif mark == self.MARK_FOLDER:
      w, h = [round(v * scale) for v in self.MARK_FOLDER_SIZE]
      x0 = x1 - w
      y0 = round(self.ICON_EDGE_MARGIN * scale)
      r = max(1, round(scale))
      draw.rounded_rectangle([x0, y0, x0 + w // 2, y0 + h // 2], radius = r,
				fill = color)		# Tab
      draw.rounded_rectangle([x0, y0 + h // 5, x1, y0 + h], radius = 2 * r,
				fill = color)		# Body



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
