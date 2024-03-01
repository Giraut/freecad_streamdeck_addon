"""FreeCAD Stream Deck Addon - Actions class
"""

## Modules
#

import io
from PIL import Image

from PySide import QtCore, QtGui



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



class ToolbarActions():
  """Toolbar and toolbar actions extracted from the GUI
  """

  def __init__(self, main_window, ignored_toolbars, action_changed_callback):
    """__init__ method
    """

    self.main_window = main_window

    self.ignored_toolbars = ignored_toolbars

    self.action_changed_callback = action_changed_callback

    self.previous_toolbars = []
    self.toolbars = []
    self.toolbar_actions = {}
    self.actions = {}

    self.expanded_actions = {}



  def extract_toolbar_actions_from_gui(self, update_actions = True):
    """update the ordered list of toolbar names, toolbar actions and subactions
    from the GUI
    If update_actions is asserted, unconditionally update all the known actions
    If update_actions is not asserted, only update all the known actions if
    the toolbars have changed
    Return True if the toolbars or the actions have changed
    """

    self.previous_toolbars = self.toolbars
    self.toolbars = []

    # Get the list of toolbars
    tbs = []
    for toolbar in self.main_window.findChildren(QtGui.QToolBar):

      # Should we keep or ignore this toolbar?
      t = toolbar.objectName()
      if not toolbar.isHidden() and t not in self.ignored_toolbars:

        # Keep the toolbar
        tbs.append(toolbar)
        self.toolbars.append(t)

    # If the new list of toolbars is different from the previous one in any way,
    # update all the associated actions
    if not update_actions and \
		(len(self.toolbars) != len(self.previous_toolbars) or \
		any([self.previous_toolbars[i] != t \
			for i, t in enumerate(self.toolbars)])):
      update_actions = True

    # Should we update all the toolbar actions?
    if update_actions:

      self.toolbar_actions.clear()
      for i, toolbar in enumerate(tbs):

        t = self.toolbars[i]
        self.toolbar_actions[t] = []

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

                # Should we expand the subactions?
                if self.expanded_actions[n]:

                  # Get all the menu subactions
                  last_subactions = None
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

                      # Add the subaction to the list of known actions if it
                      # isn't already known and connect its changed signal to
                      # our callback, otherwise update the known action
                      if sn not in self.actions:
                        self.actions[sn] = Action(sn, t, subaction,
							issubactionof = n)
                        subaction.changed.connect(self.action_changed_callback)
                      else:
                        self.actions[sn].update(t, subaction)
                      self.toolbar_actions[t].append(sn)

                      last_subaction = sn

                  # Mark the last subaction in this menu
                  if last_subaction is not None:
                    self.actions[last_subaction].islastsubaction = True

      # Signal that the actions have been updated
      return True

    # Signal that the actions have not been updated
    return False
