[app]
# (str) Title of your application
title = A Normal Cliking Game

# (str) Package name
package.name = anormalclickinggame

# (str) Package domain (needed for android/ios packaging)
package.domain = org.click

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include
source.exts = py,png,jpg,kv,atlas

# (str) Application versioning
version = 0.1

# (list) Application requirements
requirements = python3,kivy

# (str) Supported orientations
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET

[buildozer]
# (int) Log level
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1
