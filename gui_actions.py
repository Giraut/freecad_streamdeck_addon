"""FreeCAD Stream Deck Addon - Actions class
"""

## Modules
#

import re
import io
from PIL import Image

from PySide import QtCore, QtGui

import key_labels



## Constants
#

# Name of the pseudo-toolbar holding one action per workbench, so the Stream
# Deck can switch workbenches. No real toolbar has that object name
WORKBENCH_TOOLBAR = "StreamDeckAddon_Workbenches"
WORKBENCH_TOOLBAR_TITLE = "Workbench"

# Prefix of the names of the workbench actions, followed by the name of the
# workbench, e.g. "Std_Workbench#PartDesignWorkbench"
WORKBENCH_ACTION_PREFIX = "Std_Workbench#"

# FreeCAD's own toolbar with the workbench drop-down list or tabs, which the
# Stream Deck leaves out when it shows the workbenches itself
FREECAD_WORKBENCH_TOOLBAR = "Workbench"

# Workbenches FreeCAD disables when the user never changed the list in the
# preferences, by FreeCAD version
DEFAULT_DISABLED_WORKBENCHES = {
	(1, 0): "NoneWorkbench,TestWorkbench",
	(1, 1): "NoneWorkbench,TestWorkbench,InspectionWorkbench,"
		"RobotWorkbench,OpenSCADWorkbench"}



## Routines
#

def disabled_workbenches():
  """Return the set of the names of the workbenches disabled in FreeCAD's
  preferences - the ones its workbench selector doesn't show
  """

  import FreeCAD

  pg = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Workbenches")

  if "Disabled" in [c[1] for c in (pg.GetContents() or [])]:
    disabled = pg.GetString("Disabled")

  # The user never changed the list: use FreeCAD's default
  else:
    try:
      version = tuple(int(v) for v in FreeCAD.Version()[:2])
    except Exception:
      version = (1, 0)
    disabled = DEFAULT_DISABLED_WORKBENCHES[max([v for v in \
				DEFAULT_DISABLED_WORKBENCHES if v <= version],
				default = (1, 0))]

  return set(disabled.split(",")) | {"NoneWorkbench"}



def workbench_actions():
  """Return the actions of FreeCAD's workbench selector as a list of
  (workbench name, QAction) tuples, in the order FreeCAD shows them.
  Triggering one of the actions activates its workbench, exactly like picking
  it in FreeCAD's drop-down list or tabs
  Return an empty list if the actions aren't available
  """

  try:
    import FreeCADGui
    actions = FreeCADGui.Command.get("Std_Workbench").getAction()
  except Exception:
    return []

  # The selector holds the enabled workbenches first, in the order set in the
  # preferences, then the disabled ones: leave those out
  try:
    disabled = disabled_workbenches()
  except Exception:
    disabled = {"NoneWorkbench"}

  return [(a.objectName(), a) for a in actions \
		if a.objectName() and a.objectName() not in disabled]



def active_workbench_name():
  """Return the name of the active workbench, e.g. "PartDesignWorkbench", or
  None if it can't be found
  """

  try:
    import FreeCADGui
    return FreeCADGui.activeWorkbench().name()
  except Exception:
    return None



def workbench_menu_text(name):
  """Return the name of a workbench as FreeCAD displays it, e.g. "Part Design"
  for "PartDesignWorkbench"
  """

  try:
    import FreeCADGui
    text = getattr(FreeCADGui.listWorkbenches()[name], "MenuText", None)
    if text and isinstance(text, str):
      return text
  except Exception:
    pass

  return re.sub("Workbench$", "", name)



def workbench_names():
  """Return the names of the installed workbenches as displayed in FreeCAD,
  plus a few common ones, to strip them from the beginning of toolbar names
  """

  names = list(key_labels.DEFAULT_WORKBENCH_NAMES)

  try:
    import FreeCADGui
    for wb in FreeCADGui.listWorkbenches().values():
      n = getattr(wb, "MenuText", None)
      if n and isinstance(n, str) and n not in names:
        names.append(n)
  except Exception:
    pass

  return names



## Classes
#

class Action():
  """Single known displayed action descriptor
  """

  def __init__(self, name, toolbar, action, issubactionof = None):
    """__init__ method
    """

    self.name = name

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



  def icon_as_pil_image(self, force_enabled = False):
    """Convert the enabled or disabled versions of the QIcon into a PIL image
    If force_enabled is asserted, always use the enabled version
    """

    try:
      pixmap = self.action.icon().pixmap(128, 128,
					mode = QtGui.QIcon.Mode.Normal \
						if self.enabled or \
							force_enabled else \
						QtGui.QIcon.Mode.Disabled)

      if pixmap is None or pixmap.isNull():
        return None

      qba = QtCore.QByteArray()
      qbf = QtCore.QBuffer(qba)

      # The buffer must be explicitly opened for writing, otherwise
      # QPixmap.save() fails and we end up with a blank key
      qbf.open(QtCore.QIODevice.OpenModeFlag.WriteOnly \
			if hasattr(QtCore.QIODevice, "OpenModeFlag") else \
		QtCore.QIODevice.WriteOnly)

      # PNG keeps the icon's transparency, so the key's background color shows
      # around it. PPM, used before, turned the transparent parts black
      try:
        saved = pixmap.save(qbf, "PNG")
      finally:
        qbf.close()

      img = Image.open(io.BytesIO(qba.data())) if saved else None

    except:
      img = None

    return img



class ToolbarActions():
  """Toolbar and toolbar actions extracted from the GUI
  """

  def __init__(self, main_window, action_changed_callback):
    """__init__ method
    """

    self.main_window = main_window

    self.action_changed_callback = action_changed_callback

    self.previous_toolbars = []
    self.toolbars = []
    self.toolbar_actions = {}
    self.actions = {}

    self.expanded_actions = {}

    # Menu items of the actions that have a menu, whether they're expanded or
    # not: {action name: [subaction names]}
    self.subactions = {}

    # Toolbar titles as displayed in FreeCAD, and short versions of them
    # without the name of the workbench: {toolbar name: title}
    self.toolbar_titles = {}
    self.toolbar_short_titles = {}

    # The active workbench, when the workbench list is shown: the name of its
    # action in the workbench list - for its icon - or None if it isn't in the
    # list, and its name as FreeCAD displays it, e.g. "Part Design"
    self.active_workbench_action = None
    self.active_workbench_title = ""

    self.workbench_names = None



  def extract_toolbar_actions_from_gui(self, excluded_toolbars,
					update_actions = True,
					with_workbenches = True):
    """update the ordered list of toolbar names, toolbar actions and subactions
    from the GUI
    Excluded_toolbars is the list of toolbar names that should be ignored
    If update_actions is asserted, unconditionally update all the known actions
    If update_actions is not asserted, only update all the known actions if
    the toolbars have changed
    If with_workbenches is asserted, add the WORKBENCH_TOOLBAR pseudo-toolbar
    at the end, with one action per workbench, in place of FreeCAD's own
    workbench toolbar
    Return True if the toolbars or the actions have changed
    """

    self.previous_toolbars = self.toolbars
    self.toolbars = []

    wb_actions = workbench_actions() if with_workbenches else []

    # Get the list of toolbars
    tbs = []
    for toolbar in self.main_window.findChildren(QtGui.QToolBar):

      # Should we keep or ignore this toolbar?
      t = toolbar.objectName()
      if not toolbar.isHidden() and t not in excluded_toolbars and \
		not (wb_actions and t == FREECAD_WORKBENCH_TOOLBAR):

        # Keep the toolbar
        tbs.append(toolbar)
        self.toolbars.append(t)

    if wb_actions:
      self.toolbars.append(WORKBENCH_TOOLBAR)

    # If the new list of toolbars is different from the previous one in any way,
    # update all the associated actions
    if not update_actions and \
		(len(self.toolbars) != len(self.previous_toolbars) or \
		any([self.previous_toolbars[i] != t \
			for i, t in enumerate(self.toolbars)])):
      update_actions = True

    # Should we update all the toolbar actions?
    if update_actions:

      if self.workbench_names is None:
        self.workbench_names = workbench_names()

      self.toolbar_actions.clear()
      self.subactions.clear()
      self.active_workbench_action = None
      self.active_workbench_title = ""
      for i, toolbar in enumerate(tbs):

        t = self.toolbars[i]
        self.toolbar_actions[t] = []

        # Get the toolbar's title as displayed in FreeCAD
        try:
          title = toolbar.windowTitle() or t
        except Exception:
          title = t
        self.toolbar_titles[t] = title
        self.toolbar_short_titles[t] = key_labels.short_toolbar_title(title,
							self.workbench_names)

        # Get the list of buttons in this toolbar
        for button in toolbar.findChildren(QtGui.QToolButton):

          # Get the list of actions associated with this button
          for action in button.actions():

            # Get the object name: primarily from .objectName(), and if that's
            # empty, fall back on .data() unless .data() is None or "" or a
            # number, so we don't miss any action name we care about
            n = action.objectName()
            if not n:
              n = action.data()
              if not n or re.match("^[0-9]+$", n):
                n = None

            # Should we keep or ignore this action?
            if n and not action.isSeparator() and action.isIconVisibleInMenu():

              # Add the action to the list of known actions if it isn't
              # already known and connect its changed signal to our callback,
              # otherwise update the known action
              if n not in self.actions:
                self.actions[n] = Action(n, t, action)
                action.changed.connect(self.action_changed_callback)
              else:
                self.actions[n].update(t, action)
              self.toolbar_actions[t].append(n)

              # Does the button have a menu associated with it?
              m = button.findChildren(QtGui.QMenu)
              if m:

                # Add this action to the list of expand(able) actions if it
                # isn't in it already
                if n not in self.expanded_actions:
                  self.expanded_actions[n] = False

                # Get all the menu subactions
                self.subactions[n] = []
                for subaction in m[0].actions():

                  # Should we keep or ignore this action?
                  if not subaction.isSeparator() and \
				subaction.isIconVisibleInMenu():

                    # Create a name for this subaction: either the straight
                    # name from .objectName(), or the name of the parent
                    # action with the hash sign and the menu number from
                    # .data() appended to it
                    sn = subaction.objectName()
                    if not sn:
                      sn = n + "#" + str(subaction.data())

                    # Don't let a menu item shadow the parent action
                    if sn == n or sn in self.subactions[n]:
                      continue

                    # Add the subaction to the list of known actions if it
                    # isn't already known and connect its changed signal to
                    # our callback, otherwise update the known action
                    if sn not in self.actions:
                      self.actions[sn] = Action(sn, t, subaction,
							issubactionof = n)
                      subaction.changed.connect(self.action_changed_callback)
                    else:
                      self.actions[sn].update(t, subaction)
                    self.actions[sn].islastsubaction = False
                    self.subactions[n].append(sn)

                # Mark the last subaction in this menu
                if self.subactions[n]:
                  self.actions[self.subactions[n][-1]].islastsubaction = True
                else:
                  del self.subactions[n]

                # Should we expand the subactions in the toolbar, i.e. display
                # them right after the parent action?
                if self.expanded_actions[n]:
                  self.toolbar_actions[t].extend(self.subactions.get(n, []))

      # Add the workbenches as the actions of the workbench pseudo-toolbar
      if wb_actions:
        self.add_workbench_toolbar(wb_actions)

      # Signal that the actions have been updated
      return True

    # Signal that the actions have not been updated
    return False



  def add_workbench_toolbar(self, wb_actions):
    """Fill in the WORKBENCH_TOOLBAR pseudo-toolbar with one action per
    workbench, given the (workbench name, QAction) tuples of FreeCAD's
    workbench selector. Also note which one is the active workbench, and its
    name as FreeCAD displays it
    """

    t = WORKBENCH_TOOLBAR
    self.toolbar_actions[t] = []
    self.toolbar_titles[t] = WORKBENCH_TOOLBAR_TITLE
    self.toolbar_short_titles[t] = WORKBENCH_TOOLBAR_TITLE

    for wb, action in wb_actions:
      n = WORKBENCH_ACTION_PREFIX + wb
      if n not in self.actions:
        self.actions[n] = Action(n, t, action)
        action.changed.connect(self.action_changed_callback)
      else:
        self.actions[n].update(t, action)
      self.toolbar_actions[t].append(n)

    active = active_workbench_name()
    if active:
      n = WORKBENCH_ACTION_PREFIX + active
      a = self.actions.get(n) if n in self.toolbar_actions[t] else None
      self.active_workbench_action = n if a is not None else None
      self.active_workbench_title = a.title if a is not None and a.title \
					else workbench_menu_text(active)
