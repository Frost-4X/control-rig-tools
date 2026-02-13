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


def _parse_bone_switches(pose_bone: bpy.types.PoseBone) -> List[str]:
    """Return list of switch names assigned to this pose bone.

    Stored as a semicolon-separated string in the `control_rig_tools` custom property.
    """
    raw = pose_bone.get("control_rig_tools")
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(";") if p.strip()]
        return parts
    # fallback: single value
    return [str(raw)]


def _add_switch_to_bone(pose_bone: bpy.types.PoseBone, switch_name: str) -> None:
    """Add `switch_name` to the bone's `control_rig_tools` property (no duplicates)."""
    existing = _parse_bone_switches(pose_bone)
    if switch_name in existing:
        return
    existing.append(switch_name)
    try:
        pose_bone["control_rig_tools"] = ";".join(existing)
    except Exception:
        pass


def bone_has_switch(pose_bone: bpy.types.PoseBone, switch_name: str) -> bool:
    return switch_name in _parse_bone_switches(pose_bone)


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

    # Build mapping of switches -> assigned DEF_ bones
    switch_to_bones: Dict[str, List[str]] = {}
    for pb in armature.pose.bones:
        if not pb.name.startswith('DEF_'):
            continue
        switches = _parse_bone_switches(pb)
        for s in switches:
            switch_to_bones.setdefault(s, []).append(pb.name)

    # compute switch sizes and order by fewest bones first (priority)
    switch_order = sorted(switch_to_bones.keys(), key=lambda s: len(switch_to_bones.get(s, [])))

    # For each DEF_ bone, build constraints/drivers for every switch that references it.
    for pose_bone in armature.pose.bones:
        if not pose_bone.name.startswith('DEF_'):
            continue

        base_name = pose_bone.name[len('DEF_'):]
        fk_name = f'FK_{base_name}'
        mch_name = f'MCH_{base_name}'

        fk_pose_bone = armature.pose.bones.get(fk_name)
        mch_pose_bone = armature.pose.bones.get(mch_name)

        if fk_pose_bone is None and mch_pose_bone is None:
            continue

        # determine switches that include this bone, ordered by priority (fewest bones first)
        switches_for_bone = [s for s in switch_order if pose_bone.name in switch_to_bones.get(s, [])]
        if not switches_for_bone:
            continue

        # For each switch that contains this bone create a constraint+driver
        for s in switches_for_bone:
            # FK
            if fk_pose_bone is not None:
                cname_fk = f'CRS_FK_{s}'
                c_fk = _add_copy_transforms(pose_bone, armature, fk_name, cname_fk)
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
                    # create driver that respects priority among switches_for_bone
                    fcurve = c_fk.driver_add('influence')
                    driver = fcurve.driver
                    driver.type = 'SCRIPTED'
                    # build variables for each switch in switches_for_bone (ordered by priority)
                    for idx, sw in enumerate(switches_for_bone):
                        var = driver.variables.new()
                        var.name = f'var{idx}'
                        var.type = 'SINGLE_PROP'
                        target = var.targets[0]
                        target.id = armature
                        target.data_path = f'pose.bones["CTRL_Settings"]["{sw}"]'
                    # build expression: var0 if var0>0 else (var1 if var1>0 else ...)
                    expr = ''
                    for idx in range(len(switches_for_bone)):
                        if idx == 0:
                            expr = f'var0'
                        else:
                            # nest
                            expr = f'var{idx} if (' + ' and '.join([f'var{j}==0' for j in range(idx)]) + f') else ({expr})'
                    # the above builds nested selection where the smallest switch (var0) wins
                    # we need the expression that yields this switch value only when all smaller switches are zero
                    # wrap expression to select current switch's var or zero
                    # find index of current switch in switches_for_bone
                    idx_s = switches_for_bone.index(s)
                    if idx_s == 0:
                        final_expr = 'var0'
                    else:
                        final_expr = f'var{idx_s} if (' + ' and '.join([f'var{j}==0' for j in range(idx_s)]) + ') else 0'
                    driver.expression = final_expr
                except Exception:
                    pass

            # MCH (inverted)
            if mch_pose_bone is not None:
                cname_mch = f'CRS_MCH_{s}'
                c_mch = _add_copy_transforms(pose_bone, armature, mch_name, cname_mch)
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
                    # create driver variables and expression similar to FK then invert the result
                    fcurve = c_mch.driver_add('influence')
                    driver = fcurve.driver
                    driver.type = 'SCRIPTED'
                    for idx, sw in enumerate(switches_for_bone):
                        var = driver.variables.new()
                        var.name = f'var{idx}'
                        var.type = 'SINGLE_PROP'
                        target = var.targets[0]
                        target.id = armature
                        target.data_path = f'pose.bones["CTRL_Settings"]["{sw}"]'
                    idx_s = switches_for_bone.index(s)
                    if idx_s == 0:
                        expr = 'var0'
                    else:
                        expr = f'var{idx_s} if (' + ' and '.join([f'var{j}==0' for j in range(idx_s)]) + ') else 0'
                    driver.expression = f'1 - ({expr})'
                except Exception:
                    pass

        created.append(pose_bone.name)

        # Reorder constraints so switches with fewer bones are last (apply on top).
        try:
            # desired switch order: largest groups first, smallest last
            desired_switch_order = sorted(switches_for_bone, key=lambda s: len(switch_to_bones.get(s, [])), reverse=True)
            desired_constraint_names: List[str] = []
            for sw in desired_switch_order:
                if fk_pose_bone is not None:
                    desired_constraint_names.append(f'CRS_FK_{sw}')
                if mch_pose_bone is not None:
                    desired_constraint_names.append(f'CRS_MCH_{sw}')

            # move constraints into desired order where present
            target_index = 0
            for cname in desired_constraint_names:
                # find current index of constraint with this name
                cur_index = None
                for i, c in enumerate(pose_bone.constraints):
                    if getattr(c, 'name', '') == cname:
                        cur_index = i
                        break
                if cur_index is None:
                    continue
                try:
                    pose_bone.constraints.move(cur_index, target_index)
                    target_index += 1
                except Exception:
                    # ignore move errors and continue
                    pass
        except Exception:
            pass

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


def remove_bone_from_switch(armature: bpy.types.Object, bone_name: str) -> dict:
    """Remove a single bone from any switch assignment and clean its COPY_TRANSFORMS constraints/drivers.

    Returns counts: {'bone': str, 'constraints_removed': int, 'drivers_removed': int}
    """
    pb = armature.pose.bones.get(bone_name)
    if pb is None:
        raise ValueError(f'Bone not found: {bone_name}')

    # remove metadata tag if present
    try:
        if "control_rig_tools" in pb.keys():
            del pb["control_rig_tools"]
    except Exception:
        pass

    removed_constraints = 0
    removed_pairs = []
    for c in list(pb.constraints):
        if c.type == "COPY_TRANSFORMS":
            cname = c.name
            try:
                pb.constraints.remove(c)
                removed_constraints += 1
                removed_pairs.append((pb.name, cname))
            except Exception:
                pass

    removed_drivers = 0
    if getattr(armature, 'animation_data', None) is not None and armature.animation_data is not None:
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
        'bone': bone_name,
        'constraints_removed': removed_constraints,
        'drivers_removed': removed_drivers,
    }


def remove_triplet_from_switch(armature: bpy.types.Object, base_name: str, switch_name: str) -> dict:
    """Remove all bones that share `base_name` (triplet) from the given switch.

    Only bones that are tagged with the provided `switch_name` will be unassigned.
    Cleans COPY_TRANSFORMS constraints and related drivers on those bones.

    Returns counts: {'base': str, 'bones_removed': int, 'constraints_removed': int, 'drivers_removed': int}
    """
    bones_removed = 0
    constraints_removed = 0
    drivers_removed = 0
    removed_pairs = []

    # find bones matching base and switch tag
    for pb in list(armature.pose.bones):
        base = pb.name.rsplit("_", 1)[-1]
        if base != base_name:
            continue
        # support multiple switches per bone
        if not bone_has_switch(pb, switch_name):
            continue

        bones_removed += 1
        # remove only this switch from the bone's tag
        try:
            existing = _parse_bone_switches(pb)
            if switch_name in existing:
                existing.remove(switch_name)
                if existing:
                    pb["control_rig_tools"] = ";".join(existing)
                else:
                    try:
                        del pb["control_rig_tools"]
                    except Exception:
                        pass
        except Exception:
            pass

        # remove constraints that were created for this specific switch (CRS_FK_{switch} / CRS_MCH_{switch})
        for c in list(pb.constraints):
            if c.type == "COPY_TRANSFORMS" and c.name.endswith(f'_{switch_name}'):
                cname = c.name
                try:
                    pb.constraints.remove(c)
                    constraints_removed += 1
                    removed_pairs.append((pb.name, cname))
                except Exception:
                    pass

    # remove drivers targeting removed constraints
    if getattr(armature, 'animation_data', None) is not None and armature.animation_data is not None:
        drivers = list(armature.animation_data.drivers)
        for d in drivers:
            dp = getattr(d, 'data_path', '') or ''
            for pb_name, cname in removed_pairs:
                expected = f'pose.bones["{pb_name}"].constraints["{cname}"].influence'
                if dp == expected:
                    try:
                        armature.animation_data.drivers.remove(d)
                        drivers_removed += 1
                    except Exception:
                        pass

    return {
        'base': base_name,
        'bones_removed': bones_removed,
        'constraints_removed': constraints_removed,
        'drivers_removed': drivers_removed,
    }


def set_switch_enabled(armature: bpy.types.Object, switch_name: str, enabled: bool) -> dict:
    """Enable or disable constraints for a specific switch.

    This will mute/unmute COPY_TRANSFORMS constraints whose names end with the
    switch suffix (CRS_FK_<switch>, CRS_MCH_<switch>) on all DEF_ bones.

    Returns counts: {'constraints_toggled': int}
    """
    toggled = 0
    for pb in armature.pose.bones:
        # only DEF_ bones are expected to have these constraints
        if not pb.name.startswith('DEF_'):
            continue
        for c in pb.constraints:
            try:
                if c.type == 'COPY_TRANSFORMS' and c.name.endswith(f'_{switch_name}'):
                    # mute constraint when disabled, unmute when enabled
                    try:
                        c.mute = not bool(enabled)
                        toggled += 1
                    except Exception:
                        pass
            except Exception:
                pass

    try:
        # hint dependency graph to update
        armature.update_tag()
    except Exception:
        pass

    return {'constraints_toggled': toggled}
