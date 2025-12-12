# AIO-OCIO Updater

Blender addon to install and update OCIO color configurations from GitHub.

## Features

- **Multiple sources**: Choose between AIO-OCIO, PixelManager, or custom repository
- **One-click install/update**: Download latest release from GitHub
- **Progress bar**: Visual download progress
- **Version tracking**: Shows installed version and source
- **Auto backup**: Existing config backed up before replacement

## Supported Sources

| Source | Repository | Description |
|--------|------------|-------------|
| AIO-OCIO | RolandVyens/AIO-OCIO | Recommended for Blender (default) |
| PixelManager | Joegenco/PixelManager | Original source |
| Custom | User-defined | Any GitHub repo with OCIO releases |

## Installation

1. Install this addon in Blender (Edit > Preferences > Add-ons)
2. Enable the addon
3. (Optional) Select OCIO source in addon preferences
4. Go to Render Properties > AIO-OCIO Updater panel
5. Click "Install" button
6. Restart Blender to apply the new color configuration

## Requirements

- Blender 4.1+
- Internet connection
