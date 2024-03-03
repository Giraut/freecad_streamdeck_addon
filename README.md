# FreeCAD Stream Deck Addon
## v0.1.0

FreeCAD addon to use an [Elgato](https://www.elgato.com) [Stream Deck](https://www.elgato.com/us/en/s/welcome-to-stream-deck) macropad as an input device.

![](https://github.com/Giraut/freecad_streamdeck_addon/assets/37288252/ddb8ef90-c9a4-4eaa-a3de-2d2e6a5f98d4)

The toolbar tools displayed in the FreeCAD window are mirrored in real-time on the Stream Deck keys. When a key is pressed, the corresponding tool is applied as if selected in the main window.

When a Stream Deck key representing a tool with a sub-menu is long-pressed, the tool is expanded to show the additional tools in the sub-menu. When any of the expanded sub-menu tools is long-pressed again, the sub-menu is collapsed back to a single tool. The tools with sub-menus are shown between red brackets.

The toolbar tools are organized in pages of keys. A toolbar occupies its own set of pages.

Certain toolbars may be displayed on all the pages. Those tools are shown between blue brackets. Other toolbars can be excluded from the Stream Deck and never shown.

Two keys at the bottom right of the Stream Deck are used to change pages.



### Installation

Copy or clone this git repo directory in your FreeCAD addon directory. Typically:

User:
  - Linux:   `~/.local/share/FreeCAD/Mod/`
  - Windows: `%APPDATA%\FreeCAD\Mod\`

System-wide:
  - Linux:   `/usr/share/freecad/Mod/`
  - Windows: `C:\Program Files\FreeCAD\Mod\`

You also need to install the following Python modules (e.g. with `python -m pip install`):

- streamdeck
- Pillow

*Note: If you use a FreeCAD AppImage, the addon may not find the streamdeck package on your system. You can solve the problem by installing it directly in the directory the addon was installed in with `python -m pip install--target=<directory>`.*



### Settings

In the FreeCAD menu, go to `Tools ▶ Edit Parameters`.  All the settings to control the addon are under `BaseApp ▶ StreamDeckAddon`.

![](https://github.com/Giraut/freecad_streamdeck_addon/assets/37288252/c79150aa-aa47-4d0d-b88d-5425a5a179c8)

The ones you're really interested in are:

- **Enabled**

  Enable or disable the addon. When it is disabled, the Stream Deck device is fully released and usable by other applications while FreeCAD is running.

- **Device ▶ Filter ▶ UseDeviceType**

  The type of the Stream Deck device you want to use if more than one device is connected. E.g. `Stream Deck XL`. Leave blank to use a device of any type.

- **Device ▶ Filter ▶ UseDeviceSerial**

  The serial number of the Stream Deck device you want to use if more than one device is connected. E.g. `A00NA325307HF5`. Leave blank to use a device with any serial number.

- **StartStopCommands ▶ ExecuteShellCommandWhenStarting**

  Shell script to run when starting. Useful to kill another Stream Deck application such as streamdeck-ui and release the Stream Deck device for use by this addon. E.g. `killall streamdeck`. Leave blank to disable.

- **StartStopCommands ▶ ExecuteShellCommandWhenStopping**

  Shell script to run when stopping. Useful to restart another Stream Deck application such as streamdeck-ui after the Stream Deck device has been releases by this addon. E.g. `streamdeck &`. Leave blank to disable.

- **ToolbarLists ▶ ToolbarsExcluded_CommaSeparated**

  Comma-separated list of names of toolbars you never want displayed on the Stream Deck regardless of whether they're enabled in the main window, to reduce clutter. E.g. `Help,Navigation`. Leave blank to display all the toolbars on the Stream Deck.

- **ToolbarLists ▶ ToolbarsOnEveryPage_CommaSeparated**

  Comma-separated list of names of toolbars you want repeated on all the Stream Deck pages, so they're always available regardless of the particular toolbar page you're in.  E.g. `Edit,View`.  Note that those permanently-displayed toolbars are laid out on the Stream Deck in the order they're listed.

  If your Stream Deck has enough keys - Stream Deck XL for example - you can have more permanently-displayed toolbar tools without multiplying the number of pages.

  If your Stream Deck has fewer keys, you may want to have fewer permanently-displayed toolbar tools to free up more keys per page.

  Leave blank if you don't want any toolbars repeated on all the pages.

- **Display ▶ Brightness ▶ BrightnessPercent**

  How bright the Stream Deck's display should be. Percentage from 0% to 100%.

- **Display ▶ ScreenSaver ▶ Enabled**  
**Display ▶ ScreenSaver ▶ FadeWhenUserInactiveForSeconds**  
**Display ▶ ScreenSaver ▶ FadeToBrightness**  
**Display ▶ ScreenSaver ▶ FadeTimeSeconds**  

  Stream Deck screen saver settings.

All setting changes take effect immediately. You don't need to restart FreeCAD.



### Notes

- The addon needs exclusive access to the Stream Deck device. It cannot coexist
  with Elgato's Stream Deck software on Windows or with streamdeck-ui on Linux.
  Either the addon has control of the Stream Deck device or the other
  application does, but not both at the same time.

- Tested with FreeCAD 0.22 on Linux and Windows, with a Stream Deck Mk2 and a
  Stream Deck XL. It may or may not work with other models.

- This software is still under development. Please bear with me as I make it nicer 🙂
