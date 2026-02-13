"""
Core IK/FK switch utilities

Contains helper functions to validate the armature, manage the CTRL_Settings
pose bone properties, and build constraints and drivers for DEF_ bones.
"""
from typing import Dict, List

import bpy


# named constant for Blender's RNA UI metadata key so the code is explicit
RUNTIME_UI_KEY = "_RNA_UI"


def get_active_armature(context: bpy.types.Context) -> bpy.types.Object:
    selected_object = context.object
    if selected_object is None or selected_object.type != "ARMATURE":
        raise ValueError("Select an Armature object to use these tools.")
    return selected_object


def get_control_settings_pose_bone(armature: bpy.types.Object) -> bpy.types.PoseBone:
    pose_bone = armature.pose.bones.get("CTRL_Settings")
    if pose_bone is None:
        raise ValueError(
            'Armature must contain a pose bone named "CTRL_Settings".')
    return pose_bone


def list_switches(control_settings_pose_bone: bpy.types.PoseBone) -> Dict[str, float]:
    switches: Dict[str, float] = {}
    for key, value in control_settings_pose_bone.items():
        # ignore RNA_UI metadata and non-numeric props
        if key == RUNTIME_UI_KEY:
            continue
        if isinstance(value, (float, int)):
            switches[key] = float(value)
    return switches


def add_switch_property(armature: bpy.types.Object, name: str) -> None:
    control_settings = get_control_settings_pose_bone(armature)
    if name in control_settings.keys():
        return
    control_settings[name] = 0.0
    # Do not write _RNA_UI metadata here; UI will construct sliders from proxy properties instead.


def _ensure_constraint_unique(pose_bone: bpy.types.PoseBone, cname: str, target_name: str) -> bool:
    for c in pose_bone.constraints:
        if c.type == "COPY_TRANSFORMS" and c.name == cname and getattr(c, "subtarget", "") == target_name:
            return False
    return True


def _add_copy_transforms(pose_bone: bpy.types.PoseBone, armature: bpy.types.Object, target_name: str, cname: str) -> bpy.types.Constraint:
    if not _ensure_constraint_unique(pose_bone, cname, target_name):
        # find and return existing constraint
        for c in pose_bone.constraints:
            if c.type == "COPY_TRANSFORMS" and c.name == cname and getattr(c, "subtarget", "") == target_name:
                # ensure constraint uses local space for both owner and target
                try:
                    c.owner_space = 'LOCAL'
                    c.target_space = 'LOCAL'
                except Exception:
                    pass
                return c

    c = pose_bone.constraints.new(type="COPY_TRANSFORMS")
    c.name = cname
    c.target = armature
    c.subtarget = target_name
    # use local space rather than world space for consistent local transforms
    try:
        c.owner_space = 'LOCAL'
        c.target_space = 'LOCAL'
    except Exception:
        pass
    return c


def _add_driver_for_constraint_influence(constraint: bpy.types.Constraint, armature: bpy.types.Object, switch_name: str, invert: bool = False) -> None:
    # driver on constraint.influence
    fcurve = constraint.driver_add("influence")
    driver = fcurve.driver
    driver.type = 'SCRIPTED'
    # create single variable pointing to CTRL_Settings switch property
    variable = driver.variables.new()
    variable.name = "var"
    variable.type = 'SINGLE_PROP'
    target = variable.targets[0]
    target.id = armature
    target.data_path = f'pose.bones["CTRL_Settings"]["{switch_name}"]'
    driver.expression = "1 - var" if invert else "var"


def build_rebuild_switches(armature: bpy.types.Object) -> List[str]:
    created: List[str] = []

    for pose_bone in armature.pose.bones:
        switch = pose_bone.get("control_rig_tools")
        if not switch:
            continue
        # Only apply to DEF_ bones
        if not pose_bone.name.startswith("DEF_"):
            continue

        base_name = pose_bone.name[len("DEF_"):]
        fk_name = f"FK_{base_name}"
        mch_name = f"MCH_{base_name}"

        fk_pose_bone = armature.pose.bones.get(fk_name)
        mch_pose_bone = armature.pose.bones.get(mch_name)

        if fk_pose_bone is None and mch_pose_bone is None:
            # nothing to do for this deform bone
            continue

        # Add FK constraint and driver
        if fk_pose_bone is not None:
            cname_fk = f"CRS_FK_{switch}"
            c_fk = _add_copy_transforms(pose_bone, armature, fk_name, cname_fk)
            # ensure driver exists and uses CTRL_Settings[switch]
            try:
                # remove existing drivers targeting this constraint/influence
                if getattr(armature, 'animation_data', None) is not None and armature.animation_data is not None:
                    data_path_fk = f'pose.bones["{pose_bone.name}"].constraints["{c_fk.name}"].influence'
                    drivers = list(armature.animation_data.drivers)
                    for d in drivers:
                        if getattr(d, 'data_path', None) == data_path_fk:
                            try:
                                armature.animation_data.drivers.remove(d)
                            except Exception:
                                pass
                _add_driver_for_constraint_influence(c_fk, armature, switch, invert=False)
            except Exception:
                pass

        # Add MCH constraint and driver (inverted)
        if mch_pose_bone is not None:
            cname_mch = f"CRS_MCH_{switch}"
            c_mch = _add_copy_transforms(
                pose_bone, armature, mch_name, cname_mch)
            try:
                if getattr(armature, 'animation_data', None) is not None and armature.animation_data is not None:
                    data_path_mch = f'pose.bones["{pose_bone.name}"].constraints["{c_mch.name}"].influence'
                    drivers = list(armature.animation_data.drivers)
                    for d in drivers:
                        if getattr(d, 'data_path', None) == data_path_mch:
                            try:
                                armature.animation_data.drivers.remove(d)
                            except Exception:
                                pass
                _add_driver_for_constraint_influence(c_mch, armature, switch, invert=True)
            except Exception:
                pass

        created.append(pose_bone.name)

    return created


def clean_rig(armature: bpy.types.Object) -> dict:
    """Remove COPY_TRANSFORMS constraints and related drivers from DEF_ bones.

    Returns a dict with counts: {'constraints_removed': int, 'drivers_removed': int}
    """
    removed_constraints = 0
    removed_drivers = 0
    removed_pairs = []  # list of (pose_bone_name, constraint_name) removed
    bones_processed = 0

    # Only process DEF_ bones (deform bones)
    for pose_bone in list(armature.pose.bones):
        if not pose_bone.name.startswith("DEF_"):
            continue
        bones_processed += 1
        # copy list to avoid mutation issues
        for c in list(pose_bone.constraints):
            if c.type == "COPY_TRANSFORMS":
                cname = c.name
                try:
                    pose_bone.constraints.remove(c)
                    removed_constraints += 1
                    removed_pairs.append((pose_bone.name, cname))
                except Exception:
                    pass

    # Remove drivers that targeted removed constraint influences
    if getattr(armature, 'animation_data', None) is not None and armature.animation_data is not None:
        # iterate over a copy because we may remove items
        drivers = list(armature.animation_data.drivers)
        for d in drivers:
            dp = getattr(d, 'data_path', '') or ''
            for pb_name, cname in removed_pairs:
                expected = f'pose.bones["{pb_name}"].constraints["{cname}"].influence'
                if dp == expected:
                    try:
                        armature.animation_data.drivers.remove(d)
                        removed_drivers += 1
                    except Exception:
                        pass

    return {
        'bones_processed': bones_processed,
        'constraints_removed': removed_constraints,
        'drivers_removed': removed_drivers,
    }


def clear_switch_properties(armature: bpy.types.Object) -> dict:
    """Remove switch properties from CTRL_Settings and clear per-bone metadata.

    Returns counts: {'switch_props_removed': int, 'bone_tags_removed': int}
    """
    control_settings = get_control_settings_pose_bone(armature)
    # collect keys to remove (ignore RNA metadata)
    keys = [k for k in control_settings.keys() if k != RUNTIME_UI_KEY]
    removed_props = 0
    for k in keys:
        try:
            del control_settings[k]
            removed_props += 1
        except Exception:
            pass

    removed_tags = 0
    for pb in armature.pose.bones:
        if "control_rig_tools" in pb.keys():
            try:
                del pb["control_rig_tools"]
                removed_tags += 1
            except Exception:
                pass

    return {
        'switch_props_removed': removed_props,
        'bone_tags_removed': removed_tags,
    }
