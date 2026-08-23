[app]
# (str) Title of your application
title = A Normal Clicking Game

# (str) Package name
package.name = anormalclickinggame

# (str) Package domain (needed for android/ios packaging)
package.domain = org.click

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.exts = py,png,jpg,kv,atlas

# (str) Application versioning
version = 0.1

# (list) Application requirements
requirements = python3,kivy

# (str) Supported orientations (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET

# --- THE MAGIC FIX FOR THE PIP ERROR ---
# (str) python-for-android branch to use
p4a.branch = develop

[buildozer]
# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

