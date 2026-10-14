"""FreeCAD Stream Deck Addon - Key label helpers

The Stream Deck keys are small - 72 x 72 pixels on a 15-key Stream Deck - and
FreeCAD's tool and toolbar names are long. These helpers produce shorter forms
of the names that the key renderer falls back on when the full name doesn't
fit
"""

## Modules
#

import re



## Constants
#

# Leading words that can be dropped from a tool name without losing its
# meaning, since the icon carries it: "Create a datum plane" -> "Datum plane",
# "Constrain horizontal distance" -> "Horizontal distance"
_COMPACT_PREFIXES = re.compile(r"^(create|make|insert|add)( an?| the)? |"
				r"^(constrain|toggle) ", re.IGNORECASE)

# Trailing words that can be dropped from a toolbar name:
# "B-spline tools" -> "B-spline", "Helper Features" -> "Helper"
_COMPACT_SUFFIXES = re.compile(r" (features|tools|toolbar)$", re.IGNORECASE)

# Long words that have a common shorter form
_ABBREVIATIONS = {
	"transformation": "transform",
	"coordinate": "coord.",
	"construction": "constr.",
	"configuration": "config"}

# Names of workbenches commonly found at the beginning of toolbar names, used
# when the names of the installed workbenches can't be obtained from FreeCAD
DEFAULT_WORKBENCH_NAMES = (
	"Part Design", "Part", "Sketcher", "Draft", "BIM", "Arch", "TechDraw",
	"FEM", "Assembly", "Mesh", "Spreadsheet", "Surface", "CAM", "Path",
	"OpenSCAD", "Points", "Reverse Engineering", "Robot", "Material",
	"Measure", "Inspection")



## Routines
#

def _capitalize(s):
  """Uppercase the first character of a string, leaving the rest as it is
  """

  return s[:1].upper() + s[1:]



def _abbreviate(word):
  """Return the common shorter form of a word if it has one, with the same
  capitalization
  """

  a = _ABBREVIATIONS.get(word.lower())
  if a is None:
    return word

  return _capitalize(a) if word[:1].isupper() else a



def compact_label(text):
  """Return a shorter form of a tool or toolbar name, or the name itself if it
  can't be shortened
  """

  if not text:
    return text

  c = _COMPACT_PREFIXES.sub("", text, 1)
  c = _COMPACT_SUFFIXES.sub("", c, 1)
  c = " ".join([_abbreviate(w) for w in c.split()])
  c = c.strip()

  return _capitalize(c) if c else text



def short_toolbar_title(title, workbench_names = DEFAULT_WORKBENCH_NAMES):
  """Strip a leading workbench name from a toolbar title, since the workbench
  is obvious from the context:
  "Part Design Helper Features" -> "Helper Features"
  "Sketcher constraints" -> "Constraints"
  """

  if not title:
    return title

  for w in sorted([w for w in workbench_names if w], key = len,
			reverse = True):
    if title.lower().startswith(w.lower() + " "):
      rest = title[len(w):].strip()
      if rest:
        return _capitalize(rest)

  return title
