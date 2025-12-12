# AIO-OCIO Updater

**What it is:**
A Blender addon that manages OpenColorIO (OCIO) configurations, specifically designed for AIO-OCIO and PixelManager.

**What it does:**
It allows you to install or update your Blender color management configuration with a single click directly from the UI, supporting multiple sources (AIO-OCIO, PixelManager, or Custom).

**How it works:**
1.  Downloads the latest release zipball from the selected GitHub repository.
2.  Backs up your existing `datafiles/colormanagement` folder.
3.  Extracts and installs the new configuration to your Blender user scripts directory, ensuring no permission issues.
