"""
Control Rig Tools - A Blender add-on for rigging utilities
"""

bl_info = {
    "name": "Control Rig Tools",
    "author": "Frost-4X",
    "version": (0, 1, 1),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Control Rig Tools",
    "description": "A Blender add-on that provides utility helpers such as automatic IK-FK switches and more",
    "category": "Rigging",
}


def register():
    """Register the add-on"""
    from . import operators, ui
    operators.register()
    ui.register()


def unregister():
    """Unregister the add-on"""
    from . import operators, ui
    ui.unregister()
    operators.unregister()


if __name__ == "__main__":
    register()
