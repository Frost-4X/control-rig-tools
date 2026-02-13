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
            # header row with proxy slider and assign button
            row = layout.row(align=True)
            proxy = helpers.ensure_proxy_for_switch(
                scene, name, control_settings.get(name, 0.0))

            if proxy is not None:
                # find proxy index in scene collection for context_toggle
                proxy_idx = None
                if hasattr(scene, 'crl_switch_proxies'):
                    for i, p in enumerate(scene.crl_switch_proxies):
                        if p is proxy or getattr(p, 'switch_name', None) == name:
                            proxy_idx = i
                            break

                # checkbox to enable/disable this switch
                row.prop(proxy, 'enabled', text='')

                # expand/collapse triangle
                if proxy_idx is not None:
                    icon = 'TRIA_DOWN' if proxy.expanded else 'TRIA_RIGHT'
                    t = row.operator('wm.context_toggle', text='', icon=icon)
                    t.data_path = f'scene.crl_switch_proxies[{proxy_idx}].expanded'
                else:
                    # fallback to small toggle if we can't find index
                    row.prop(proxy, 'expanded', text='')

                # slider
                row.prop(proxy, 'value', text=name, slider=True)
            else:
                row.prop(control_settings,
                         f'["{name}"]', text=name, slider=True)

            # small icon-only Assign and Remove buttons
            a = row.operator('crl.assign_switch', text='', icon='ADD')
            a.switch_name = name
            r = row.operator('crl.remove_selection_from_switch', text='', icon='REMOVE')
            r.switch_name = name

            # when expanded show triplets (grouped by base) with remove buttons
            if proxy is not None and getattr(proxy, 'expanded', False):
                # collect triplets for this switch
                triplets = {}
                for pb in armature.pose.bones:
                    # bone may belong to multiple switches (semicolon-separated)
                    try:
                        from ..core import switches as _switches
                        if not _switches.bone_has_switch(pb, name):
                            continue
                    except Exception:
                        if pb.get('control_rig_tools') != name:
                            continue
                    base = pb.name.rsplit('_', 1)[-1]
                    triplets.setdefault(base, []).append(pb.name)

                box = layout.box()
                for base in sorted(triplets.keys()):
                    r = box.row(align=True)
                    # show only the shared base name (strip prefixes)
                    r.label(text=base)
                    rem = r.operator('crl.remove_triplet_from_switch', text='Remove')
                    rem.switch_name = name
                    rem.base_name = base

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
