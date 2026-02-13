"""
Utility helpers shared across the add-on.
"""
from typing import Optional

import bpy


def find_armature_with_ctrl_settings(context: Optional[bpy.types.Context] = None) -> Optional[bpy.types.Object]:
    """Return an armature object that contains a pose bone named "CTRL_Settings".

    Prefer the active object from the provided `context` if it is an armature,
    otherwise fall back to searching all objects in the file.
    """
    if context is not None:
        obj = getattr(context, "object", None)
        if obj is not None and obj.type == "ARMATURE":
            if obj.pose and obj.pose.bones.get("CTRL_Settings"):
                return obj
    # fallback: search all objects
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE" and obj.pose and obj.pose.bones.get("CTRL_Settings"):
            return obj
    return None


def derive_base_name_from_last_underscore(name: str) -> str:
    """Return the substring after the last underscore in `name`.

    If no underscore is present, return the original name.
    """
    return name.rsplit("_", 1)[-1]


def ensure_proxy_for_switch(scene: bpy.types.Scene, switch_name: str, initial_value: float, proxy_collection_name: str = "crl_switch_proxies") -> Optional[bpy.types.PropertyGroup]:
    """Ensure a proxy exists on `scene.<proxy_collection_name>` for `switch_name`.

    Returns the proxy item (new or existing). If the collection does not exist
    on the scene, returns None.
    """
    if not hasattr(scene, proxy_collection_name):
        return None
    coll = getattr(scene, proxy_collection_name)
    for p in coll:
        if getattr(p, "switch_name", None) == switch_name:
            try:
                p.value = float(initial_value)
            except Exception:
                pass
            return p
    # add new
    p = coll.add()
    p.switch_name = switch_name
    try:
        p.value = float(initial_value)
    except Exception:
        p.value = 0.0
    return p
