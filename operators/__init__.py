"""
Blender operators for rigging actions
"""
from typing import List

import bpy

from ..core import switches
from ..utils import helpers

import bpy.props as _props


# Proxy property used to draw sliders with explicit RNA metadata.
def _proxy_value_update(self, context):
    try:
        armature = switches.get_active_armature(context)
        control_settings = switches.get_control_settings_pose_bone(armature)
        # write back to the underlying custom property
        control_settings[self.switch_name] = float(self.value)
        # tag the armature so dependency graph updates driver evaluations
        try:
            armature.update_tag()
        except Exception:
            pass
    except Exception:
        # ignore errors during UI updates
        pass


class CRL_SwitchProxy(bpy.types.PropertyGroup):
    switch_name: _props.StringProperty()
    value: _props.FloatProperty(
        name="value",
        description="Switch value (0 = IK/MCH, 1 = FK)",
        min=0.0,
        max=1.0,
        step=1,
        update=_proxy_value_update,
    )
    expanded: _props.BoolProperty(
        name="expanded",
        description="Expand to show assigned bones",
        default=False,
    )


class CRL_OT_add_switch(bpy.types.Operator):
    bl_idname = "crl.add_switch"
    bl_label = "Add Switch"
    bl_description = (
        "Create a new IK/FK switch property on CTRL_Settings. "
        "If in Pose Mode and pose bones are selected those bones will be assigned to the new switch (only metadata is added)."
    )
    bl_options = {'REGISTER'}

    name: bpy.props.StringProperty(name="Switch Name")

    def execute(self, context):
        try:
            armature = switches.get_active_armature(context)
            if not getattr(self, 'name', None) or not str(self.name).strip():
                raise ValueError('Provide a non-empty switch name')
            switches.add_switch_property(armature, self.name)
            assigned = 0
            assigned_names = set()
            if context.mode == 'POSE':
                selected_pose_bones = context.selected_pose_bones
                if selected_pose_bones:
                    for pose_bone in selected_pose_bones:
                        # assign metadata only; allow multiple switches per bone
                        _ = None
                        try:
                            switches._add_switch_to_bone(pose_bone, self.name)
                        except Exception:
                            # fallback to simple assignment
                            pose_bone["control_rig_tools"] = self.name
                        assigned_names.add(pose_bone.name)
                    # for each selected bone also assign other bones that share the derived base name
                    for pb in armature.pose.bones:
                        if pb.name not in assigned_names:
                            base = helpers.derive_base_name_from_last_underscore(pb.name)
                            for sel in selected_pose_bones:
                                if base == helpers.derive_base_name_from_last_underscore(sel.name):
                                    try:
                                        _switches._add_switch_to_bone(pb, self.name)
                                    except Exception:
                                        pb["control_rig_tools"] = self.name
                                    assigned_names.add(pb.name)
            assigned = len(assigned_names)
            # ensure UI proxy exists and is in sync
            scene = context.scene
            helpers.ensure_proxy_for_switch(scene, self.name, 0.0)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if assigned:
            self.report({'INFO'}, f"Added switch '{self.name}'; assigned {assigned} bones")
        else:
            self.report({'INFO'}, f"Added switch '{self.name}'")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class CRL_OT_assign_switch(bpy.types.Operator):
    bl_idname = "crl.assign_switch"
    bl_label = "Assign Selected Bones to Switch"
    bl_description = (
        "Assign selected pose bones to the named switch and create constraints/drivers. "
        "Requirements: select an Armature and enter Pose Mode. Select pose bones that have matching FK_ and/or MCH_ counterparts (groups of single matches per DEF_ bone are OK). "
        "The operator adds the `control_rig_tools` custom prop and immediately builds COPY_TRANSFORMS constraints and influence drivers."
    )

    switch_name: bpy.props.StringProperty()

    def execute(self, context):
        try:
            armature = switches.get_active_armature(context)
            if context.mode != 'POSE':
                raise ValueError(
                    'Enter Pose Mode and select pose bones to assign.')
            selected_pose_bones = context.selected_pose_bones
            if not selected_pose_bones:
                raise ValueError('No pose bones selected.')
            assigned_names = set()
            for pose_bone in selected_pose_bones:
                # assign the selected bone (metadata only)
                try:
                    switches._add_switch_to_bone(pose_bone, self.switch_name)
                except Exception:
                    pose_bone["control_rig_tools"] = self.switch_name
                assigned_names.add(pose_bone.name)
                # derive base name using substring after last underscore and assign matching prefixed bones
                base = helpers.derive_base_name_from_last_underscore(pose_bone.name)
                for pb in armature.pose.bones:
                    if pb.name not in assigned_names and helpers.derive_base_name_from_last_underscore(pb.name) == base:
                        try:
                            switches._add_switch_to_bone(pb, self.switch_name)
                        except Exception:
                            pb["control_rig_tools"] = self.switch_name
                        assigned_names.add(pb.name)
            # Note: do not build constraints here; building is a separate explicit action
            processed = 0
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report(
            {'INFO'}, f"Assigned {len(assigned_names)} bones to switch '{self.switch_name}'; processed {processed} DEF_ bones")
        return {'FINISHED'}


class CRL_OT_build_switches(bpy.types.Operator):
    bl_idname = "crl.build_switches"
    bl_label = "Build / Rebuild Switches"
    bl_description = (
        "Create COPY_TRANSFORMS constraints and drivers for all DEF_ bones assigned to switches (bones with the control_rig_tools prop). "
        "Requirements: select an Armature. This is safe to run multiple times; FK constraints use the switch value, MCH constraints use the inverted value."
    )

    def execute(self, context):
        try:
            arm = switches.get_active_armature(context)
            created = switches.build_rebuild_switches(arm)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f"Processed {len(created)} DEF_ bones")
        return {'FINISHED'}


class CRL_OT_create_rig_switch(bpy.types.Operator):
    bl_idname = "crl.create_rig_switch"
    bl_label = "Create Rig Switch"
    bl_description = (
        "Create a switch and assign all DEF_ bones that have FK_/MCH_ counterparts. Only metadata is added; no constraints are created."
    )

    name: bpy.props.StringProperty(name="Switch Name")
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            arm = switches.get_active_armature(context)
            if not getattr(self, 'name', None) or not str(self.name).strip():
                raise ValueError('Provide a non-empty switch name')
            switches.add_switch_property(arm, self.name)
            assigned = 0
            for pb in arm.pose.bones:
                if not pb.name.startswith('DEF_'):
                    continue
                base = pb.name[len('DEF_'):]
                fk = f'FK_{base}'
                mch = f'MCH_{base}'
                if fk in arm.pose.bones or mch in arm.pose.bones:
                    try:
                        switches._add_switch_to_bone(pb, self.name)
                    except Exception:
                        pb['control_rig_tools'] = self.name
                    assigned += 1
            # ensure UI proxy exists
            helpers.ensure_proxy_for_switch(context.scene, self.name, 0.0)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f"Created rig switch '{self.name}'; assigned {assigned} DEF_ bones")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class CRL_OT_remove_triplet_from_switch(bpy.types.Operator):
    bl_idname = "crl.remove_triplet_from_switch"
    bl_label = "Remove Triplet from Switch"
    bl_description = "Remove a set of bones (triplet) sharing a base name from the named switch"

    switch_name: bpy.props.StringProperty()
    base_name: bpy.props.StringProperty()

    def execute(self, context):
        try:
            arm = switches.get_active_armature(context)
            switches.remove_triplet_from_switch(arm, self.base_name, self.switch_name)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f"Removed triplet '{self.base_name}' from switch '{self.switch_name}'")
        return {'FINISHED'}


class CRL_OT_clean_rig(bpy.types.Operator):
    bl_idname = "crl.clean_rig"
    bl_label = "Clean Rig"
    bl_description = "Remove COPY_TRANSFORMS constraints and related drivers from DEF_ bones (does not remove switch metadata)."

    def execute(self, context):
        try:
            arm = switches.get_active_armature(context)
            result = switches.clean_rig(arm)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f"Processed {result.get('bones_processed')} bones. Removed {result.get('constraints_removed',0)} constraints and {result.get('drivers_removed',0)} drivers")
        return {'FINISHED'}


class CRL_OT_clear_switch_properties(bpy.types.Operator):
    bl_idname = "crl.clear_switch_properties"
    bl_label = "Clear Switch Properties"
    bl_description = "Remove switch properties from CTRL_Settings and clear per-bone switch metadata."

    def execute(self, context):
        try:
            arm = switches.get_active_armature(context)
            result = switches.clear_switch_properties(arm)
            # clear UI proxies on the scene if present
            if hasattr(context.scene, 'crl_switch_proxies'):
                coll = getattr(context.scene, 'crl_switch_proxies')
                for i in range(len(coll)-1, -1, -1):
                    try:
                        coll.remove(i)
                    except Exception:
                        pass
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f"Removed {result.get('switch_props_removed',0)} switch props and {result.get('bone_tags_removed',0)} bone tags")
        return {'FINISHED'}


classes = [
    CRL_SwitchProxy,
    CRL_OT_add_switch,
    CRL_OT_assign_switch,
    CRL_OT_build_switches,
    CRL_OT_create_rig_switch,
    CRL_OT_clean_rig,
    CRL_OT_clear_switch_properties,
    CRL_OT_remove_triplet_from_switch,
]


def register():
    for c in classes:
        bpy.utils.register_class(c)
    # collection of proxies stored on the scene so UI sliders can expose metadata
    bpy.types.Scene.crl_switch_proxies = _props.CollectionProperty(
        type=CRL_SwitchProxy)


def unregister():
    # remove scene property
    if hasattr(bpy.types.Scene, "crl_switch_proxies"):
        delattr(bpy.types.Scene, "crl_switch_proxies")
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
