"""FreeCAD Stream Deck Addon - Parameters
"""

## Parameters
#

use_streamdeck_device_type = ""		# E.g. "Stream Deck Original" or
					#      "Stream Deck XL"
					# "" for any device type

use_streamdeck_device_serial = ""	# E.g. "A00NA325307HF5"
					# "" for any device serial number

check_streamdeck_keypress_every = 0.1 #s
check_toolbar_updates_every = 0.5 #s

exclude_toolbars_from_streamdeck = ["Workbench", "Help", "Navigation"]
toolbars_on_every_streamdeck_pages = ["Edit", "View"]

brackets_color_for_toolbar_on_every_streamdeck_page = "red"
brackets_color_for_streamdeck_page_navigation_keys = "blue"

streamdeck_key_text_font_filename_linux = "OpenSans-Regular.ttf"
streamdeck_key_text_font_filename_windows = "arial.ttf"
streamdeck_key_text_font_size = 14

prev_streamdeck_key_icon = "prev.png"
next_streamdeck_key_icon = "next.png"
blank_streamdeck_key_icon = "blank.png"
broken_streamdeck_key_icon = "broken.png"

streamdeck_brightness = 80 #%
