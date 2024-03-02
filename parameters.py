"""FreeCAD Stream Deck Addon - User parameters
"""

## Modules
#

import re



## Classes
#

class _ParamObserver:
  """Parameter change observer class
  """

  def __init__(self):
    """__init__ method
    """

    self.params_changed = False



  def slotParamChanged(self, group, pname, ptype, value):
    """Callbacl for when any elements in the Parameter Editor groups
    is changed
    """

    self.params_changed = True



class UserParameters():
  """Class to get and set user parameters
  """

  # User-editable parameter variable names and corresponding Parameter Editor
  # types, names and default values organized as a tree that's easily editable
  # by the user in the Parameter Editor
  __top_level_group = "User parameter:BaseApp/StreamDeckAddon"
  __pgtree = {

	#Parameter Editor group: [
	#  (Parameter Editor name, Parameter Editor type, default value),
        #  ...],
        # ...

	__top_level_group: {

	  "addon_enabled":
	    ("Enabled", "Boolean", True)},

	__top_level_group + "/Device/Display/BracketColors": {

	  "bracket_color_repeated_toolbars":
	    ("ToolbarsOnEveryPage", "String", "Blue"),

	  "bracket_color_page_nav_keys":
	    ("PageNavigationKeys", "String", "Blue"),

	  "bracket_color_expandable_tools":
	    ("ExpandableTools", "String", "Red")},

	__top_level_group + "/Device/Display/Brightness": {

	  "max_brightness":
	    ("BrightnessPercent", "Unsigned Long", 80)},

	__top_level_group + "/Device/Display/ScreenSaver": {

	  "fading_enabled":
	    ("Enabled", "Boolean", True),

	  "fade_after_secs_inactivity":
	    ("FadeWhenUserInactiveForSeconds", "Unsigned Long", 300),

	  "min_brightness":
	    ("FadeToBrightness", "Unsigned Long", 0),

	  "fade_time":
	    ("FadeTimeSeconds", "Unsigned Long", 10)},

	__top_level_group + "/Device/Filters": {

	  "use_streamdeck_type":
	    ("UseDeviceType", "String", ""),

	  "use_streamdeck_serial":
	    ("UseDeviceSerial", "String", "")},

	__top_level_group + "/Device/keys": {

	  "long_keypress_duration":
	    ("LongKeyPressDurationSeconds", "Float", 0.5)},

	__top_level_group + "/StartStopCommands": {

	  "exec_cmd_start":
	    ("ExecuteShellCommandWhenStarting", "String", ""),

	  "exec_cmd_stop":
	    ("ExecuteShellCommandWhenStopping", "String", "")},

	__top_level_group + "/ToolbarLists": {

	  "excluded_toolbars":
	    ("ToolbarsExcluded_CommaSeparated", "String", ""),

	  "repeated_toolbars":
	    ("ToolbarsOnEveryPage_CommaSeparated", "String", "")}}




  def __init__(self, FreeCAD):
    """__init__ method
    """

    self.__FC = FreeCAD

    # Initialize the user-editable parameters with the default values
    for pgpath in self.__pgtree:
      for varname in self.__pgtree[pgpath]:
         setattr(self, varname, self.__pgtree[pgpath][varname][2])

    self.excluded_toolbars = []
    self.repeated_toolbars = []

    # Add the non user-editable parameters
    self.streamdeck_key_text_font_filename_linux = "OpenSans-Regular.ttf"
    self.streamdeck_key_text_font_filename_windows = "arial.ttf"
    self.streamdeck_key_text_font_size = 14
    self.prev_streamdeck_key_icon = "prev.png"
    self.next_streamdeck_key_icon = "next.png"
    self.blank_streamdeck_key_icon = "blank.png"
    self.broken_streamdeck_key_icon = "broken.png"
    self.check_streamdeck_keypress_every = 0.1
    self.check_toolbar_updates_every = 0.5

    # Attach our callback to detect when parameters are changed by the user
    self.__paramobserver = _ParamObserver()
    self.__top_level_param_group = self.__FC.ParamGet(self.__top_level_group)
    self.__top_level_param_group. AttachManager(self.__paramobserver)

    # Synchronize the parameters for the first time
    self.sync(force_sync = True)



  def sync(self, force_sync = False):
    """Maintain the correct Parameter Editor group / subgroups structure if
    needed, then update the parameters from them
    If force_sync is not asserted and no parameter change is reported by the
    observer, simply return False
    If the parameters are synchronized, return True
    """

    # Save the current parameters as "prev_" attributes
    for pgpath in self.__pgtree:
      for varname in self.__pgtree[pgpath]:
        setattr(self, "prev_" + varname, getattr(self, varname))

    # Should we synchronize the parameters?
    if not force_sync and not self.__paramobserver.params_changed:
      return False

    self.__paramobserver.params_changed = False

    # Temporarily turn the excluded_toolbars and repeated_toolbars lists into
    # comma-separated strings for storage in the Parameter Editor groups
    # We do this because we can't store ordered lists in the groups
    self.excluded_toolbars = ",".join(self.excluded_toolbars)
    self.repeated_toolbars = ",".join(self.repeated_toolbars)

    # Make sure the parameter tree exists and has the correct structure. Create
    # it and correct it as needed
    for pgpath in self.__pgtree:

      # Get / create the Parameter Editor group
      pg = self.__FC.ParamGet(pgpath)

      # Determine the suitable functions to get, set and remove parameters in
      # the group
      pg_get = {"String": pg.GetString,
		"Integer": pg.GetInt,
		"Float": pg.GetFloat,
		"Boolean": pg.GetBool,
		"Unsigned Long": pg.GetUnsigned}

      pg_set = {"String": pg.SetString,
		"Integer": pg.SetInt,
		"Float": pg.SetFloat,
		"Boolean": pg.SetBool,
		"Unsigned Long": pg.SetUnsigned}

      pg_rem = {"String": pg.RemString,
		"Integer": pg.RemInt,
		"Float": pg.RemFloat,
		"Boolean": pg.RemBool,
		"Unsigned Long": pg.RemUnsigned}

      # Get the Parameter Editor group's content as a dictionary keyed by
      # (name, type)
      pgcs = pg.GetContents()
      pgcontent = {(pgc[1], pgc[0]): pgc[2] for pgc in pgcs} \
			if pgcs is not None else {}

      # Remove unknown parameters in the group, if there are known parameters
      # for this group
      known_pnames = [self.__pgtree[pgpath][varname][0] \
			for varname in self.__pgtree[pgpath]]
      if known_pnames:
        for pname, ptype in pgcontent:
          if pname not in known_pnames:
            pg_rem[ptype](pname)

      # Add or correct known parameters in the group
      for varname in self.__pgtree[pgpath]:

        param_not_found = True

        # Iterate over the group's parameters
        for pname, ptype in pgcontent:

          # Is this parameter known?
          if pname == self.__pgtree[pgpath][varname][0]:

            # If the group parameter has the wrong type, remove it
            if ptype != self.__pgtree[pgpath][varname][1]:
              pg_rem[ptype](pname)

            # If the group parameter has the correct type, update our parameter
            else:
              param_not_found = False
              setattr(self, varname, pg_get[ptype](pname))

        # If the parameter was not found in the group, create it
        if param_not_found:
          pname, ptype = self.__pgtree[pgpath][varname][:2]
          pg_set[ptype](pname, getattr(self, varname))

    # Turn the excluded_toolbars and repeated_toolbars comma-separated strings
    # back into lists
    # Split the strings also on semicolons, colons, spaces and tabs while w're
    # at it
    self.excluded_toolbars = re.split("[,;: \t]", self.excluded_toolbars)
    self.repeated_toolbars = re.split("[,;: \t]", self.repeated_toolbars)

    # Indicate that the parameters have been synchronized
    return True
