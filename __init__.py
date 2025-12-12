# SPDX-License-Identifier: GPL-3.0-or-later
# AIO-OCIO Updater - Install and update AIO-OCIO color configuration

bl_info = {
    "name": "AIO-OCIO Updater",
    "author": "Roland Vyens",
    "version": (1, 0, 0),
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
from bpy.types import Operator, Panel
from bpy.props import FloatProperty, StringProperty, BoolProperty


# Global progress tracking
_download_progress = 0.0
_download_status = ""
_is_downloading = False


def get_colormanagement_path():
    """Get the path to Blender's colormanagement folder.
    
    Prioritizes USER location to avoid permission issues with system installs.
    """
    # Use USER datafiles path (avoids permission issues with Program Files installs)
    user_path = bpy.utils.resource_path('USER')
    cm_path = os.path.join(user_path, 'datafiles', 'colormanagement')
    
    # Ensure parent directory exists
    parent = os.path.dirname(cm_path)
    if not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    
    return cm_path


def download_with_progress(url, dest_path, progress_callback):
    """Download a file with progress reporting."""
    try:
        response = urllib.request.urlopen(url)
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


class OCIO_OT_install_update(Operator):
    """Install or update AIO-OCIO color configuration"""
    bl_idname = "ocio.install_update_aio"
    bl_label = "Install/Update AIO-OCIO"
    bl_description = "Download and install the latest AIO-OCIO color configuration from GitHub"
    bl_options = {'REGISTER'}
    
    _timer = None
    _thread = None
    _finished = False
    _success = False
    _error_msg = ""
    
    GITHUB_URL = "https://github.com/RolandVyens/AIO-OCIO/archive/refs/heads/master.zip"
    
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
            # Create temp directory
            temp_dir = tempfile.mkdtemp(prefix="aio_ocio_")
            zip_path = os.path.join(temp_dir, "aio_ocio.zip")
            
            # Download
            self.update_progress(0.0, "Starting download...")
            success, error = download_with_progress(
                self.GITHUB_URL, 
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
        
        _is_downloading = True
        _download_progress = 0.0
        _download_status = "Initializing..."
        self._finished = False
        self._success = False
        self._error_msg = ""
        
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
    bl_options = {'DEFAULT_CLOSED'}
    # Place after Color Management panel (which has bl_order around 100)
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
            
            if os.path.exists(config_path):
                # Check if it's AIO-OCIO by looking for characteristic files
                aio_marker = os.path.join(cm_path, "config_CG_Lin709.ocio")
                if os.path.exists(aio_marker):
                    layout.label(text="AIO-OCIO is installed", icon='CHECKMARK')
                    layout.operator("ocio.install_update_aio", text="Update AIO-OCIO", icon='FILE_REFRESH')
                else:
                    layout.label(text="Custom OCIO detected", icon='INFO')
                    layout.operator("ocio.install_update_aio", text="Install AIO-OCIO", icon='IMPORT')
            else:
                layout.label(text="No OCIO config found", icon='ERROR')
                layout.operator("ocio.install_update_aio", text="Install AIO-OCIO", icon='IMPORT')
            
            # Info
            layout.separator()
            layout.label(text="Restart Blender after install", icon='INFO')


# Registration
classes = (
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
