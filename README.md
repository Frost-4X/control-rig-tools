# control-rig-tools

Control Rig Tools is a small Blender add-on that helps set up and manage IK/FK
switches for character rigs. It provides utilities to create named switch
properties on a dedicated `CTRL_Settings` pose bone, assign pose bones to
switch groups, and automatically build COPY_TRANSFORMS constraints and influence
drivers that toggle between FK and MCH/IK controls.

## Overview

- Adds and manages IK/FK switches stored as custom properties on a pose bone
  named `CTRL_Settings`.
- Builds `COPY_TRANSFORMS` constraints on `DEF_` bones and drivers that use the
  switch value to blend between `FK_` (direct) and `MCH_` (inverted) inputs.
- Exposes slider proxies in the UI for a convenient workflow without editing
  the armature data directly.

## Usage

1. Prepare your armature
    - Select an Armature object in the 3D View.
    - The rig should contain a pose bone named `CTRL_Settings`. This bone stores
      the switch properties.
    - For each deform bone you want to switch, use a naming convention like
      `DEF_name` with corresponding driver/source bones named `FK_name` and/or
      `MCH_name` (the code derives the base name after the `DEF_` prefix).

2. Open the add-on UI - In the 3D View, open the Sidebar and switch to the `Control Rig Tools`
   tab. The panel shows existing switches (if any) and buttons to `Add
Switch` and `Build / Rebuild Switches`.

3. Add a switch (metadata only)
    - Click `Add Switch` and enter a switch name. This creates a numeric
      property on the `CTRL_Settings` pose bone (range 0.0–1.0).
    - If you are in Pose Mode and have pose bones selected when adding a switch,
      those bones will be assigned to the new switch automatically. Note: this
      step only writes metadata (which bones belong to a switch); it does not
      create constraints or drivers.

4. Assign bones to a switch
    - Select pose bones in Pose Mode and press the `Assign` button next to a
      switch in the panel (or run the operator `crl.assign_switch`). The
      operator adds a `control_rig_tools` custom property to the selected bones
      and to other bones that share the same base name (derived after the last
      underscore). This also only writes metadata and does not build drivers or
      constraints.

5. Create a rig-wide switch
    - Use `Create Rig Switch` to create a switch and assign all `DEF_` bones
      that have matching `FK_` or `MCH_` counterparts. This operation writes
      metadata for the entire rig so you can later refine or overwrite groups
      of bones with smaller, more specific switches.

6. Build / Rebuild constraints and drivers
    - Run `Build / Rebuild Switches` (operator `crl.build_switches`) for the
      selected armature. For each `DEF_` bone assigned to a switch the add-on
      creates `COPY_TRANSFORMS` constraints targeting the matching `FK_` and
      `MCH_` bones and adds drivers on the constraints' influence values.
    - FK constraints use the switch value directly; MCH constraints use the
      inverted value (so when the switch is 1.0 FK is active, when 0.0 MCH is
      active).
    - Running the operation multiple times is safe; the builder clears any
      previously added drivers on the same constraint influence before adding a
      fresh driver to avoid duplicates.

7. Using the sliders
    - The UI displays slider proxies (scene-level helpers) that update the
      underlying `CTRL_Settings` switch property. Slide to blend between MCH
      (0.0) and FK (1.0).

## Tips and conventions

- Naming: keep consistent prefixes: `DEF_`, `FK_`, and `MCH_` with the same
  base name (for example `DEF_arm_01`, `FK_arm_01`, `MCH_arm_01`).
- The add-on uses a `control_rig_tools` custom property on pose bones to mark
  which DEF bones belong to a given switch group.
- If you prefer, you can add the `control_rig_tools` custom property manually
  to pose bones; running the build operator will then create the constraints
  and drivers.

## Operators (for reference)

- `crl.add_switch` — add a named switch to `CTRL_Settings` and optionally
- `crl.add_switch` — add a named switch to `CTRL_Settings` and optionally
  assign selected bones (metadata only).
- `crl.assign_switch` — assign selected pose bones to a named switch
  (metadata only).
- `crl.create_rig_switch` — create a switch and assign all `DEF_` bones
  that have matching `FK_`/`MCH_` counterparts (metadata only).
- `crl.build_switches` — build or rebuild constraints and drivers for assigned
  `DEF_` bones. The builder cleans duplicate drivers before adding new ones.
- `crl.clean_rig` — remove COPY_TRANSFORMS constraints and related drivers
  added by the tool (does not remove switch metadata).
- `crl.clear_switch_properties` — remove switch properties from `CTRL_Settings`
  and clear per-bone `control_rig_tools` metadata; also clears UI proxies.

If you have questions or want help adapting the naming conventions to your
rig, open an issue or request specific examples.
