"""
UI panels and interface elements
"""
import bpy

from ..core import switches
from ..utils import helpers


class ControlRigToolsPanel(bpy.types.Panel):
    bl_label = "Control Rig Tools"
    bl_idname = "CONTROL_RIG_TOOLS_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Control Rig Tools'

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        try:
            armature = switches.get_active_armature(context)
            control_settings = switches.get_control_settings_pose_bone(
                armature)
        except Exception as e:
            layout.label(text=str(e), icon='ERROR')
            return

        switches_dict = switches.list_switches(control_settings)
        if not switches_dict:
            layout.label(text='No switches found on CTRL_Settings')

        scene = context.scene
        for name in sorted(switches_dict.keys()):
            row = layout.row(align=True)
            # ensure a proxy exists and is synced (helpers handles creation)
            proxy = helpers.ensure_proxy_for_switch(
                scene, name, control_settings.get(name, 0.0))

            if proxy is not None:
                row.prop(proxy, 'value', text=name, slider=True)
            else:
                row.prop(control_settings,
                         f'["{name}"]', text=name, slider=True)

            op = row.operator('crl.assign_switch', text='Assign')
            op.switch_name = name

        layout.separator()
        layout.operator('crl.add_switch', text='Add Switch')
        layout.operator('crl.build_switches', text='Build / Rebuild Switches')
        layout.operator('crl.create_rig_switch', text='Create Rig Switch')
        layout.operator('crl.clean_rig', text='Clean Rig')
        layout.operator('crl.clear_switch_properties', text='Clear Switch Properties')


classes = [ControlRigToolsPanel]


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
