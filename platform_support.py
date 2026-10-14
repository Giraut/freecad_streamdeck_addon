"""FreeCAD Stream Deck Addon - Platform-specific support

Small helpers to keep the addon working on Linux, Windows and macOS:

  - platform detection
  - locating a usable TrueType font to label the Stream Deck keys
  - locating the HIDAPI shared library on macOS, where Homebrew and MacPorts
    install it in directories the dynamic linker doesn't search by default
"""

## Modules
#

import os
import sys
import ctypes
import ctypes.util
import platform
import subprocess



## Platform detection
#

IS_WINDOWS = sys.platform.startswith("win") or os.name == "nt"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = not IS_WINDOWS and not IS_MACOS



## Fonts
#

# Font candidates per platform, tried in order. Entries may be bare file names -
# looked up by Pillow in the usual system font directories - or absolute paths.

FONT_CANDIDATES_WINDOWS = [
	"arial.ttf",
	"segoeui.ttf",
	"tahoma.ttf",
	"verdana.ttf"]

FONT_CANDIDATES_MACOS = [
	"/System/Library/Fonts/Supplemental/Arial.ttf",
	"/Library/Fonts/Arial.ttf",
	"/System/Library/Fonts/Helvetica.ttc",
	"/System/Library/Fonts/HelveticaNeue.ttc",
	"/System/Library/Fonts/SFNS.ttf",
	"/System/Library/Fonts/SFNSDisplay.ttf",
	"/System/Library/Fonts/Supplemental/Verdana.ttf",
	"/System/Library/Fonts/LucidaGrande.ttc",
	"/System/Library/Fonts/Geneva.ttf",
	"Arial.ttf",
	"Helvetica.ttc"]

FONT_CANDIDATES_LINUX = [
	"OpenSans-Regular.ttf",
	"DejaVuSans.ttf",
	"LiberationSans-Regular.ttf",
	"FreeSans.ttf",
	"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
	"/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
	"/usr/share/fonts/TTF/DejaVuSans.ttf"]



def font_candidates(preferred = None, extra_dirs = None):
  """Return the ordered list of font files to try for the current platform
  If preferred is given, it's tried first - both as-is and resolved against
  each of the extra_dirs directories, so a font dropped into the addon's own
  directory is picked up
  """

  candidates = []

  def add(f):
    if f and f not in candidates:
      candidates.append(f)

  for f in ([preferred] if preferred else []):
    for d in (extra_dirs or []):
      add(os.path.join(d, f))
    add(f)

  # Let a font bundled with the addon override the system fonts
  for d in (extra_dirs or []):
    for f in ("OpenSans-Regular.ttf", "DejaVuSans.ttf"):
      add(os.path.join(d, f))

  for f in (FONT_CANDIDATES_WINDOWS if IS_WINDOWS else \
		FONT_CANDIDATES_MACOS if IS_MACOS else \
		FONT_CANDIDATES_LINUX):
    add(f)

  # Try the other platforms' fonts too as a last resort, so an unusual setup
  # still gets something readable
  for l in (FONT_CANDIDATES_LINUX, FONT_CANDIDATES_MACOS,
		FONT_CANDIDATES_WINDOWS):
    for f in l:
      add(f)

  return candidates



def load_font(size, preferred = None, extra_dirs = None):
  """Load the first usable TrueType font of the specified size
  Return (font object, name of the font file that was loaded)
  Fall back on Pillow's built-in bitmap font if no TrueType font is usable at
  all, so the addon still runs rather than failing to load
  """

  from PIL import ImageFont

  for f in font_candidates(preferred, extra_dirs):
    try:
      return (ImageFont.truetype(f, size), f)
    except Exception:
      continue

  # No TrueType font found: fall back on Pillow's built-in font
  try:
    return (ImageFont.load_default(size), "<Pillow default font>")
  except Exception:
    return (ImageFont.load_default(), "<Pillow default font>")



## HIDAPI
#

# Names of the HIDAPI shared library on macOS, and the directories it's
# typically installed in by Homebrew, MacPorts or by hand
HIDAPI_LIBRARY_NAMES_MACOS = [
	"libhidapi.dylib",
	"libhidapi.0.dylib",
	"libhidapi-libusb.dylib",
	"libhidapi-iohidmanager.dylib",
	"libhidapi-hidraw.dylib"]

HIDAPI_SEARCH_DIRS_MACOS = [
	"/opt/homebrew/lib",		# Homebrew, Apple Silicon
	"/usr/local/lib",		# Homebrew, Intel
	"/opt/local/lib",		# MacPorts
	"/usr/lib",
	"/Library/Frameworks"]


_orig_find_library = None


def _brew_prefix():
  """Ask Homebrew for its install prefix, in case it's in a non-standard place
  Return None if Homebrew isn't installed or doesn't answer
  """

  for brew in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew",
		"/usr/bin/brew"):
    if os.path.isfile(brew):
      try:
        p = subprocess.run([brew, "--prefix"], stdout = subprocess.PIPE,
				stderr = subprocess.DEVNULL, timeout = 10)
        prefix = p.stdout.decode().strip()
        if prefix and os.path.isdir(prefix):
          return prefix
      except Exception:
        pass

  return None



def find_hidapi_library():
  """Look for the HIDAPI shared library on macOS in the usual install
  directories
  Return the absolute path of the library, or None if it wasn't found
  """

  if not IS_MACOS:
    return None

  search_dirs = []

  env_prefix = os.environ.get("HOMEBREW_PREFIX")
  if env_prefix:
    search_dirs.append(os.path.join(env_prefix, "lib"))

  search_dirs.extend(HIDAPI_SEARCH_DIRS_MACOS)

  for d in search_dirs:
    for n in HIDAPI_LIBRARY_NAMES_MACOS:
      p = os.path.join(d, n)
      if os.path.isfile(p):
        return p

  # Nothing in the usual places: ask Homebrew where it lives
  prefix = _brew_prefix()
  if prefix:
    for n in HIDAPI_LIBRARY_NAMES_MACOS:
      p = os.path.join(prefix, "lib", n)
      if os.path.isfile(p):
        return p

  return None



def _hook_find_library(libpath):
  """Make ctypes.util.find_library() return libpath for any HIDAPI library
  name, so the streamdeck module finds the library even though it lives in a
  directory the dynamic linker doesn't search
  """

  global _orig_find_library

  if _orig_find_library is None:
    _orig_find_library = ctypes.util.find_library

  orig = _orig_find_library

  def find_library(name):
    try:
      if name and "hidapi" in str(name).lower():
        return libpath
    except Exception:
      pass
    return orig(name)

  ctypes.util.find_library = find_library



def ensure_hidapi_loadable():
  """Make sure the streamdeck module will be able to load the HIDAPI library
  On Linux and Windows, nothing needs doing here
  On macOS, locate the library, check that it can actually be loaded - which
  catches an architecture mismatch between FreeCAD and the library - and make
  ctypes find it by absolute path
  Return (ok, list of information lines)
  """

  if not IS_MACOS:
    return (True, [])

  libpath = find_hidapi_library()

  if libpath is None:
    return (False, [
	"HIDAPI library not found.",
	"The Stream Deck module needs it to talk to the device.",
	"Install it with Homebrew:  brew install hidapi",
	"or with MacPorts:          sudo port install hidapi"])

  # Try to load the library ourselves first: this gives a readable error when
  # the library was built for a different architecture than FreeCAD
  try:
    ctypes.CDLL(libpath)
  except Exception as e:
    return (False, [
	"Found the HIDAPI library at {}".format(libpath),
	"but it could not be loaded: {}".format(e),
	"FreeCAD is running as {}.".format(platform.machine()),
	"Make sure HIDAPI is installed for the same architecture,",
	"i.e. reinstall it with the matching Homebrew:",
	"  arch -arm64 brew install hidapi    (Apple Silicon)",
	"  arch -x86_64 brew install hidapi   (Intel)"])

  # Recent versions of the streamdeck module look for the library under
  # $HOMEBREW_PREFIX, which isn't set when FreeCAD is started from the Finder
  libdir = os.path.dirname(libpath)
  if os.path.basename(libdir) == "lib" and "HOMEBREW_PREFIX" not in os.environ:
    os.environ["HOMEBREW_PREFIX"] = os.path.dirname(libdir)

  # Older versions only look the library up by name: make that lookup succeed
  _hook_find_library(libpath)

  return (True, ["Using HIDAPI library {}".format(libpath)])
