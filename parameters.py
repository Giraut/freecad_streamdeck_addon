"""FreeCAD Stream Deck Addon - Parameters
"""

## Parameters
#

# Per-user parameters file in ~/.config (Linux) or %LOCALAPPDATA% (Windows)
# Same format as this parameters file, overrides the parameters in this file
# if it's present and readable
user_parameters_file = "freecad_streamdeck_addons.py"

# Type of the Stream Deck device to use
# Comment out for any device type
#use_streamdeck_device_type = "Stream Deck XL"	# E.g. "Stream Deck Original"

# Serial number of the Stream Deck device to use
# Comment out for any serial number
#use_streamdeck_device_serial = "A00NA325307HF7"

# Commands to execute when starting and stopping, to deal with conflicts with
# another Stream Deck application like streamdeck-ui for example
# Comment out to disable
#execute_shell_command_when_starting = "killall -HUP streamdeck 2> /dev/null"
#execute_shell_command_when_stopping = "streamdeck --no-ui &"

# Stream Deck key press detection parameters
#check_streamdeck_keypress_every = 0.1 #s
#streamdeck_key_long_press_duration = 0.5 #s

# FreeCAD UI synchronization frequency
#check_toolbar_updates_every = 0.5 #s

# Which toolbars should never be mirrored on the Stream Deck
exclude_toolbars_from_streamdeck = ["Help", "Navigation"]

# Which toolbars should be available on all the Stream Deck pages
#toolbars_on_every_streamdeck_page = ["Edit", "View"]	# Ok for Stream Deck XL
toolbars_on_every_streamdeck_page = ["Edit"]		# Ok for smaller Deck

# Colors of the Stream Deck key icon brackets
#brackets_color_for_toolbars_on_every_streamdeck_page = "green"
#brackets_color_for_streamdeck_page_navigation_keys = "green"
#brackets_color_for_expandable_tool_buttons = "yellow"

# Font type and size of the text above and below the Stream Deck key icons
#streamdeck_key_text_font_filename_linux = "OpenSans-Regular.ttf"
#streamdeck_key_text_font_filename_windows = "arial.ttf"
#streamdeck_key_text_font_size = 14

# Predefined Stream Deck key icons
#prev_streamdeck_key_icon = "prev.png"
#next_streamdeck_key_icon = "next.png"
#blank_streamdeck_key_icon = "blank.png"
#broken_streamdeck_key_icon = "broken.png"

# Brightness of the Stream Deck keys
streamdeck_brightness = 80 #%

# How dim the Stream Deck should become when the user is inactive
streamdeck_brightness_fade_to = 5 #%

# How much time the Stream Deck should take to fully dim
streamdeck_brightness_fade_time = 10 #s

# How long the user should be inactive for for the Stream Deck to start dimming
# Comment out or set to 0 to disable fading
streamdeck_brightness_fade_when_user_inactive_for = 300 #s
