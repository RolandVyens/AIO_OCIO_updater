# SPDX-License-Identifier: GPL-3.0-or-later
# AIO-OCIO Updater - Install and update AIO-OCIO color configuration

bl_info = {
    "name": "AIO-OCIO Updater",
    "author": "Roland Vyens",
    "version": (1, 1, 0),
    "blender": (4, 1, 0),
    "location": "Properties > Render > Color Management",
    "description": "Install and update AIO-OCIO color configuration for Blender",
    "category": "Render",
}

import bpy
import os
import shutil
import tempfile
import zipfile
import urllib.request
import threading
import json
from datetime import datetime
from bpy.types import Operator, Panel, AddonPreferences
from bpy.props import StringProperty, EnumProperty
import webbrowser


# Global progress tracking
_download_progress = 0.0
_download_status = ""
_is_downloading = False

# Version info file name
VERSION_FILE = ".aio_ocio_version.json"

# Repository URLs
REPO_AIO_OCIO = "https://github.com/RolandVyens/AIO-OCIO"
REPO_PIXELMANAGER = "https://github.com/Joegenco/PixelManager"

# Network timeout in seconds
NETWORK_TIMEOUT = 30


def get_releases_api_url(repo_url):
    """Convert GitHub repo URL to releases API URL.
    
    Example: https://github.com/RolandVyens/AIO-OCIO 
         ->  https://api.github.com/repos/RolandVyens/AIO-OCIO/releases/latest
    """
    # Remove trailing slash if present
    repo_url = repo_url.rstrip('/')
    
    # Extract owner/repo from URL
    if 'github.com/' in repo_url:
        parts = repo_url.split('github.com/')[-1]
        return f"https://api.github.com/repos/{parts}/releases/latest"
    
    # Fallback if URL format is unexpected
    return repo_url


def get_addon_preferences():
    """Get addon preferences."""
    addon = bpy.context.preferences.addons.get(__package__)
    if addon:
        return addon.preferences
    return None


def get_repo_url():
    """Get the repository URL based on current preference settings."""
    prefs = get_addon_preferences()
    if not prefs:
        return REPO_AIO_OCIO
    
    if prefs.ocio_source == 'AIO_OCIO':
        return REPO_AIO_OCIO
    elif prefs.ocio_source == 'PIXELMANAGER':
        return REPO_PIXELMANAGER
    else:  # CUSTOM
        return prefs.custom_repo_url


def get_colormanagement_path():
    """Get the path to Blender's colormanagement folder.
    
    Prioritizes USER location to avoid permission issues with system installs.
    """
    user_path = bpy.utils.resource_path('USER')
    cm_path = os.path.join(user_path, 'datafiles', 'colormanagement')
    return cm_path


def get_version_info():
    """Get installed version info from version file."""
    cm_path = get_colormanagement_path()
    version_file = os.path.join(cm_path, VERSION_FILE)
    
    if os.path.exists(version_file):
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_version_info(tag_name, published_date, source_name):
    """Save version info to version file."""
    cm_path = get_colormanagement_path()
    version_file = os.path.join(cm_path, VERSION_FILE)
    
    version_data = {
        "tag_name": tag_name,
        "published_date": published_date,
        "installed_date": datetime.now().isoformat(),
        "source": source_name,
    }
    
    try:
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, indent=2)
    except Exception:
        pass


def get_latest_release_info(api_url):
    """Fetch latest release info from GitHub API.
    
    Returns dict with tag_name, published_at, and zipball_url.
    """
    try:
        request = urllib.request.Request(
            api_url,
            headers={'User-Agent': 'AIO-OCIO-Updater'}
        )
        response = urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT)
        data = json.loads(response.read().decode('utf-8'))
        return {
            "tag_name": data.get("tag_name", ""),
            "published_at": data.get("published_at", ""),
            "zipball_url": data.get("zipball_url", ""),
            "name": data.get("name", ""),
        }
    except Exception:
        return None


def download_with_progress(url, dest_path, progress_callback):
    """Download a file with progress reporting."""
    try:
        request = urllib.request.Request(
            url,
            headers={'User-Agent': 'AIO-OCIO-Updater'}
        )
        response = urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT)
        total_size = response.getheader('Content-Length')
        
        if total_size:
            total_size = int(total_size)
        else:
            total_size = 0
        
        downloaded = 0
        block_size = 8192
        
        with open(dest_path, 'wb') as f:
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                
                downloaded += len(buffer)
                f.write(buffer)
                
                if total_size > 0:
                    progress = downloaded / total_size
                else:
                    progress = 0.5  # Unknown size, show 50%
                
                progress_callback(progress, f"Downloading... {downloaded // 1024} KB")
        
        return True, ""
    except Exception as e:
        return False, str(e)


class OCIO_Preferences(AddonPreferences):
    """Addon preferences for AIO-OCIO Updater."""
    bl_idname = __package__
    
    ocio_source: EnumProperty(
        name="OCIO Source",
        description="Choose which OCIO configuration to install",
        items=[
            ('AIO_OCIO', "AIO-OCIO", "RolandVyens/AIO-OCIO (recommended for Blender)"),
            ('PIXELMANAGER', "PixelManager", "Joegenco/PixelManager (original)"),
            ('CUSTOM', "Custom", "Use a custom GitHub repository URL"),
        ],
        default='AIO_OCIO',
    )
    
    custom_repo_url: StringProperty(
        name="Custom Repository URL",
        description="GitHub repository URL for custom OCIO config",
        default="",
    )
    
    def draw(self, context):
        layout = self.layout
        
        layout.prop(self, "ocio_source")
        
        # Show custom URL field only when Custom is selected
        if self.ocio_source == 'CUSTOM':
            layout.prop(self, "custom_repo_url")


class OCIO_OT_open_repo(Operator):
    """Open repository webpage in browser"""
    bl_idname = "ocio.open_repo"
    bl_label = "Open Repository"
    bl_description = "Open the OCIO repository webpage in your default browser"
    
    def execute(self, context):
        repo_url = get_repo_url()
        if repo_url:
            webbrowser.open(repo_url)
            self.report({'INFO'}, f"Opened {repo_url}")
        else:
            self.report({'WARNING'}, "No repository URL configured")
        return {'FINISHED'}


class OCIO_OT_install_update(Operator):
    """Install or update OCIO color configuration"""
    bl_idname = "ocio.install_update_aio"
    bl_label = "Install/Update OCIO"
    bl_description = "Download and install the latest OCIO color configuration from GitHub"
    bl_options = {'REGISTER'}
    
    def update_progress(self, progress, status):
        """Update progress from download thread."""
        global _download_progress, _download_status
        _download_progress = progress
        _download_status = status
    
    def download_and_install(self):
        """Background thread for download and installation."""
        global _download_progress, _download_status, _is_downloading
        
        temp_dir = None
        try:
            # Get repo URL from preferences
            repo_url = get_repo_url()
            
            if not repo_url:
                self._error_msg = "No repository URL configured. Please set a custom URL in preferences."
                self._finished = True
                return
            
            api_url = get_releases_api_url(repo_url)
            
            # Get latest release info
            self.update_progress(0.0, "Checking latest release...")
            self._release_info = get_latest_release_info(api_url)
            
            if not self._release_info or not self._release_info.get("zipball_url"):
                self._error_msg = "Failed to get release info from GitHub"
                self._finished = True
                return
            
            zipball_url = self._release_info["zipball_url"]
            
            # Create temp directory
            temp_dir = tempfile.mkdtemp(prefix="aio_ocio_")
            zip_path = os.path.join(temp_dir, "aio_ocio.zip")
            
            # Download
            self.update_progress(0.05, f"Downloading {self._release_info.get('tag_name', '')}...")
            success, error = download_with_progress(
                zipball_url, 
                zip_path, 
                self.update_progress
            )
            
            if not success:
                self._error_msg = f"Download failed: {error}"
                self._finished = True
                return
            
            # Extract
            self.update_progress(0.7, "Extracting files...")
            extract_dir = os.path.join(temp_dir, "extracted")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find the extracted folder (GitHub adds -master suffix)
            extracted_folders = os.listdir(extract_dir)
            if not extracted_folders:
                self._error_msg = "No files found in downloaded archive"
                self._finished = True
                return
            
            source_dir = os.path.join(extract_dir, extracted_folders[0])
            
            # Get destination path
            cm_path = get_colormanagement_path()
            backup_path = cm_path + "_backup"
            
            self.update_progress(0.8, "Backing up existing config...")
            
            # Ensure parent directory exists
            parent_dir = os.path.dirname(cm_path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            
            # Backup existing if present
            if os.path.exists(cm_path):
                if os.path.exists(backup_path):
                    shutil.rmtree(backup_path)
                shutil.move(cm_path, backup_path)
            
            self.update_progress(0.9, "Installing new config...")
            
            # Copy new files
            shutil.copytree(source_dir, cm_path)
            
            # Rename config file for Blender
            config_source = os.path.join(cm_path, "config_CG_Lin709.ocio")
            config_dest = os.path.join(cm_path, "config.ocio")
            
            if os.path.exists(config_source):
                if os.path.exists(config_dest):
                    os.remove(config_dest)
                shutil.copy2(config_source, config_dest)
            
            # Save version info with source name
            if self._release_info:
                prefs = get_addon_preferences()
                source_name = prefs.ocio_source if prefs else 'AIO_OCIO'
                save_version_info(
                    self._release_info.get("tag_name", "unknown"),
                    self._release_info.get("published_at", ""),
                    source_name
                )
            
            self.update_progress(1.0, "Installation complete!")
            self._success = True
            
        except Exception as e:
            self._error_msg = str(e)
        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
            
            self._finished = True
            _is_downloading = False
    
    def modal(self, context, event):
        global _is_downloading
        
        if event.type == 'TIMER':
            # Redraw UI to show progress
            for area in context.screen.areas:
                if area.type == 'PROPERTIES':
                    area.tag_redraw()
            
            if self._finished:
                context.window_manager.event_timer_remove(self._timer)
                _is_downloading = False
                
                if self._success:
                    self.report({'INFO'}, "AIO-OCIO installed successfully! Restart Blender to apply changes.")
                else:
                    self.report({'ERROR'}, f"Installation failed: {self._error_msg}")
                
                return {'FINISHED'}
        
        return {'PASS_THROUGH'}
    
    def execute(self, context):
        global _is_downloading, _download_progress, _download_status
        
        if _is_downloading:
            self.report({'WARNING'}, "Download already in progress")
            return {'CANCELLED'}
        
        self._timer = None
        self._thread = None
        self._finished = False
        self._success = False
        self._error_msg = ""
        self._release_info = None
        
        _is_downloading = True
        _download_progress = 0.0
        _download_status = "Initializing..."
        
        # Start background thread
        self._thread = threading.Thread(target=self.download_and_install)
        self._thread.daemon = True
        self._thread.start()
        
        # Setup timer for modal updates
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}


class OCIO_PT_updater(Panel):
    """AIO-OCIO Updater Panel"""
    bl_label = "AIO-OCIO Updater"
    bl_idname = "RENDER_PT_aio_ocio_updater"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    bl_order = 101
    
    @classmethod
    def poll(cls, context):
        return context.scene is not None
    
    def draw(self, context):
        global _is_downloading, _download_progress, _download_status
        
        layout = self.layout
        
        if _is_downloading:
            # Show progress with text-based bar
            col = layout.column(align=True)
            col.label(text=_download_status)
            
            # Create a visual progress bar using text
            progress_pct = int(_download_progress * 100)
            bar_width = 20
            filled = int(_download_progress * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            col.label(text=f"[{bar}] {progress_pct}%")
        else:
            # Show install button
            cm_path = get_colormanagement_path()
            config_path = os.path.join(cm_path, "config.ocio")
            
            # Get current source name for display
            prefs = get_addon_preferences()
            if prefs:
                source_names = {'AIO_OCIO': 'AIO-OCIO', 'PIXELMANAGER': 'PixelManager', 'CUSTOM': 'Custom OCIO'}
                current_source = source_names.get(prefs.ocio_source, 'OCIO')
            else:
                current_source = 'OCIO'
            
            if os.path.exists(config_path):
                # Check version info to see what's installed
                version_info = get_version_info()
                if version_info:
                    installed_source = version_info.get("source", "")
                    source_names = {'AIO_OCIO': 'AIO-OCIO', 'PIXELMANAGER': 'PixelManager', 'CUSTOM': 'Custom OCIO'}
                    installed_name = source_names.get(installed_source, 'OCIO Config')
                    
                    layout.label(text=f"{installed_name} is installed", icon='CHECKMARK')
                    
                    tag = version_info.get("tag_name", "")
                    installed = version_info.get("installed_date", "")[:10]
                    if tag:
                        layout.label(text=f"Version: {tag} ({installed})")
                else:
                    # No version info, check for marker file
                    aio_marker = os.path.join(cm_path, "config_CG_Lin709.ocio")
                    if os.path.exists(aio_marker):
                        layout.label(text="OCIO Config installed", icon='CHECKMARK')
                    else:
                        layout.label(text="Custom OCIO detected", icon='INFO')
                
                layout.operator("ocio.install_update_aio", text=f"Update {current_source}", icon='FILE_REFRESH')
            else:
                layout.label(text="No OCIO config found", icon='ERROR')
                layout.operator("ocio.install_update_aio", text=f"Install {current_source}", icon='IMPORT')
            
            layout.separator()
            layout.label(text="Restart Blender after install", icon='INFO')
            
            # Open repo button
            layout.operator("ocio.open_repo", text="Open Repository", icon='URL')


# Registration
classes = (
    OCIO_Preferences,
    OCIO_OT_open_repo,
    OCIO_OT_install_update,
    OCIO_PT_updater,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
