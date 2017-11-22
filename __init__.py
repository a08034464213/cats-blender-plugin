# MIT License

# Copyright (c) 2017 GiveMeAllYourCats

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the 'Software'), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Code author: GiveMeAllYourCats
# Repo: https://github.com/michaeldegroot/cats-blender-plugin
# Edits by: 

import bpy
import sys
import os
import importlib

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)

import tools.viseme
import tools.atlas
import tools.eyetracking
import tools.rootbone
import tools.translate
import tools.armature
import tools.boneweight
import tools.common
import globs

importlib.reload(tools.viseme)
importlib.reload(tools.atlas)
importlib.reload(tools.eyetracking)
importlib.reload(tools.rootbone)
importlib.reload(tools.translate)
importlib.reload(tools.armature)
importlib.reload(tools.boneweight)
importlib.reload(tools.common)

bl_info = {
    'name': 'Cats Blender Plugin',
    'category': '3D View',
    'author': 'GiveMeAllYourCats',
    'location': 'View 3D > Tool Shelf > CATS',
    'description': 'A tool designed to shorten steps needed to import and optimise MMD models into VRChat',
    'version': (0, 0, 5),
    'blender': (2, 79, 0),
    'wiki_url': 'https://github.com/michaeldegroot/cats-blender-plugin',
    'tracker_url': 'https://github.com/michaeldegroot/cats-blender-plugin/issues',
    'warning': '',
}

bl_options = {'REGISTER', 'UNDO'}

# updater ops import, all setup in this file
from . import addon_updater_ops

class ToolPanel():
    bl_label = 'Cats Blender Plugin'
    bl_idname = '3D_VIEW_TS_vrc'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = 'CATS'

    bpy.types.Scene.island_margin = bpy.props.FloatProperty(
        name='Margin',
        description='Margin to reduce bleed of adjacent islands',
        default=0.01,
        min=0.0,
        max=1.0,
    )

    bpy.types.Scene.area_weight = bpy.props.FloatProperty(
        name='Area weight',
        description='Weight projections vector by faces with larger areas',
        default=0.0,
        min=0.0,
        max=1.0,
    )

    bpy.types.Scene.angle_limit = bpy.props.FloatProperty(
        name='Angle',
        description='Lower for more projection groups, higher for less distortion',
        default=82.0,
        min=1.0,
        max=89.0,
    )

    bpy.types.Scene.texture_size = bpy.props.EnumProperty(
        name='Texture size',
        description='Lower for faster bake time, higher for more detail.',
        items=tools.common.get_texture_sizes
    )

    bpy.types.Scene.one_texture = bpy.props.BoolProperty(
        name='Disable multiple textures',
        description='Texture baking and multiple textures per material can look weird in the end result. Check this box if you are experiencing this.',
        default=True
    )

    bpy.types.Scene.pack_islands = bpy.props.BoolProperty(
        name='Pack islands',
        description='Transform all islands so that they will fill up the UV space as much as possible.',
        default=True
    )

    bpy.types.Scene.mesh_name_eye = bpy.props.EnumProperty(
        name='Mesh',
        description='The mesh with the eyes vertex groups',
        items=tools.common.get_meshes
    )

    bpy.types.Scene.mesh_name_atlas = bpy.props.EnumProperty(
        name='Target mesh',
        description='The mesh that you want to create a atlas from',
        items=tools.common.get_meshes
    )

    bpy.types.Scene.head = bpy.props.EnumProperty(
        name='Head',
        description='Head bone name',
        items=tools.common.get_bones,
    )

    bpy.types.Scene.eye_left = bpy.props.EnumProperty(
        name='Left eye',
        description='Eye bone left name',
        items=tools.common.get_bones,
    )

    bpy.types.Scene.eye_right = bpy.props.EnumProperty(
        name='Right eye',
        description='Eye bone right name',
        items=tools.common.get_bones,
    )

    bpy.types.Scene.wink_right = bpy.props.EnumProperty(
        name='Blink right',
        description='The name of the shape key that controls wink right',
        items=tools.common.get_shapekeys,
    )

    bpy.types.Scene.wink_left = bpy.props.EnumProperty(
        name='Blink left',
        description='The name of the shape key that controls wink left',
        items=tools.common.get_shapekeys,
    )

    bpy.types.Scene.lowerlid_right = bpy.props.EnumProperty(
        name='Lowerlid right',
        description='The name of the shape key that controls lowerlid right',
        items=tools.common.get_shapekeys,
    )

    bpy.types.Scene.lowerlid_left = bpy.props.EnumProperty(
        name='Lowerlid left',
        description='The name of the shape key that controls lowerlid left',
        items=tools.common.get_shapekeys,
    )

    bpy.types.Scene.experimental_eye_fix = bpy.props.BoolProperty(
        name='Experimental eye fix',
        description='Script will try to verify the newly created eye bones to be located in the correct position, this works by checking the location of the old eye vertex group. It is very useful for models that have over-extended eye bones that point out of the head',
        default=False
    )

    bpy.types.Scene.mesh_name_viseme = bpy.props.EnumProperty(
        name='Mesh',
        description='The mesh with the mouth shape keys',
        items=tools.common.get_meshes
    )

    bpy.types.Scene.mouth_a = bpy.props.EnumProperty(
        name='Viseme A',
        description='The name of the shape key that controls the mouth movement that looks like someone is saying A',
        items=tools.common.get_shapekeys,
    )

    bpy.types.Scene.mouth_o = bpy.props.EnumProperty(
        name='Viseme OH',
        description='The name of the shape key that controls the mouth movement that looks like someone is saying OH',
        items=tools.common.get_shapekeys,
    )

    bpy.types.Scene.mouth_ch = bpy.props.EnumProperty(
        name='Viseme CH',
        description='The name of the shape key that controls the mouth movement that looks like someone is saying CH',
        items=tools.common.get_shapekeys,
    )

    bpy.types.Scene.shape_intensity = bpy.props.FloatProperty(
        name='Shape key mix intensity',
        description='Controls the strength in the creation of the shape keys. Lower for less mouth movement strength.',
        max=1,
        min=0.01,
        default=1,
        step=1,
    )

    bpy.types.Scene.root_bone = bpy.props.EnumProperty(
        name='To parent',
        description='This is a list of bones that look like they could be parented together to a root bone, this is very useful for dynamic bones. Select a group of bones from the list and press "Parent bones"',
        items=tools.common.get_parent_root_bones,
    )


class ArmaturePanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_armature'
    bl_label = 'Armature'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        
        box = layout.box()
        row = box.row(align=True)
        row.operator('pmxarm_tool.fix_an_armature')
        row = box.row(align=True)
        row.operator('neitri_tools.delete_zero_weight_bones_and_vertex_groups')
        row = box.row(align=True)
        row.operator('neitri_tools.delete_bones_constraints')
        # row = box.row(align=True)
        # row.operator('neitri_tools.delete_bone_and_add_weights_to_parent')


class EyeTrackingPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_eye'
    bl_label = 'Eye tracking'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        row = box.row(align=True)
        row.prop(context.scene, 'mesh_name_eye')
        row = box.row(align=True)
        row.prop(context.scene, 'head')
        row = box.row(align=True)
        row.prop(context.scene, 'eye_left')
        row = box.row(align=True)
        row.prop(context.scene, 'eye_right')
        row = box.row(align=True)
        row.prop(context.scene, 'wink_left')
        row = box.row(align=True)
        row.prop(context.scene, 'wink_right')
        row = box.row(align=True)
        row.prop(context.scene, 'lowerlid_left')
        row = box.row(align=True)
        row.prop(context.scene, 'lowerlid_right')
        row = box.row(align=True)
        row.prop(context.scene, 'experimental_eye_fix')
        row = box.row(align=True)
        row.operator('create.eyes')


class VisemePanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_viseme'
    bl_label = 'Visemes'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        row = box.row(align=True)
        row.prop(context.scene, 'mesh_name_viseme')
        row = box.row(align=True)
        row.prop(context.scene, 'mouth_a')
        row = box.row(align=True)
        row.prop(context.scene, 'mouth_o')
        row = box.row(align=True)
        row.prop(context.scene, 'mouth_ch')
        row = box.row(align=True)
        row.prop(context.scene, 'shape_intensity')
        row = box.row(align=True)
        row.operator('auto.viseme')


class TranslationPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_translation'
    bl_label = 'Translation'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        
        box = layout.box()
        row = box.row(align=True)
        row.operator('translate.shapekey')
        row.operator('translate.bone')
        row.operator('translate.objects')
        row = box.row(align=True)
        row.operator('translate.textures')
        row.operator('translate.materials')


class BoneRootPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_boneroot'
    bl_label = 'Bone Parenting'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        row = box.row(align=True)
        row.prop(context.scene, 'root_bone')
        row = box.row(align=True)
        row.operator('refresh.root')
        row.operator('root.function')


class AtlasPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_atlas'
    bl_label = 'Atlas'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        row = box.row(align=True)
        row.prop(context.scene, 'island_margin')
        row = box.row(align=True)
        row.prop(context.scene, 'angle_limit')
        row = box.row(align=True)
        row.prop(context.scene, 'area_weight')
        row = box.row(align=True)
        row.prop(context.scene, 'texture_size')
        row = box.row(align=True)
        row.prop(context.scene, 'mesh_name_atlas')
        row = box.row(align=True)
        row.prop(context.scene, 'one_texture')
        row.prop(context.scene, 'pack_islands')
        row = box.row(align=True)
        row.operator('auto.atlas')

class UpdaterPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_updater'
    bl_label = 'Updater'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        addon_updater_ops.check_for_update_background()
        addon_updater_ops.update_settings_ui(self, context)

class CreditsPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_credits'
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        row = box.row(align=True)
        box.label('Cats Blender Plugin')
        row = box.row(align=True)
        box.label('Created by GiveMeAllYourCats for the VRC community <3')
        row = box.row(align=True)
        box.label('Special thanks to: Shotariya, Hotox and Neitri!')


class DemoPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    # addon updater preferences

    auto_check_update = bpy.props.BoolProperty(
        name='Auto-check for Update',
        description='If enabled, auto-check for updates using an interval',
        default=False,
        )
    updater_intrval_months = bpy.props.IntProperty(
        name='Months',
        description='Number of months between checking for updates',
        default=0,
        min=0
        )
    updater_intrval_days = bpy.props.IntProperty(
        name='Days',
        description='Number of days between checking for updates',
        default=7,
        min=0,
        )
    updater_intrval_hours = bpy.props.IntProperty(
        name='Hours',
        description='Number of hours between checking for updates',
        default=0,
        min=0,
        max=23
        )
    updater_intrval_minutes = bpy.props.IntProperty(
        name='Minutes',
        description='Number of minutes between checking for updates',
        default=0,
        min=0,
        max=59
        )

    def draw(self, context):
        layout = self.layout

        # updater draw function
        addon_updater_ops.update_settings_ui(self, context)

def register():
    bpy.utils.register_class(tools.atlas.AutoAtlasButton)
    bpy.utils.register_class(tools.eyetracking.CreateEyesButton)
    bpy.utils.register_class(tools.viseme.AutoVisemeButton)
    bpy.utils.register_class(tools.translate.TranslateShapekeyButton)
    bpy.utils.register_class(tools.translate.TranslateBonesButton)
    bpy.utils.register_class(tools.translate.TranslateMeshesButton)
    bpy.utils.register_class(tools.translate.TranslateTexturesButton)
    bpy.utils.register_class(tools.translate.TranslateMaterialsButton)
    bpy.utils.register_class(tools.rootbone.RootButton)
    bpy.utils.register_class(tools.rootbone.RefreshRootButton)
    bpy.utils.register_class(tools.armature.FixPMXArmature)
    bpy.utils.register_class(tools.boneweight.DeleteZeroWeightBonesAndVertexGroups)
    #bpy.utils.register_class(tools.boneweight.DeleteBoneAndAddWeightsToParent)
    bpy.utils.register_class(tools.boneweight.DeleteBonesConstraints)
    bpy.utils.register_class(ArmaturePanel)
    bpy.utils.register_class(EyeTrackingPanel)
    bpy.utils.register_class(VisemePanel)
    bpy.utils.register_class(BoneRootPanel)
    bpy.utils.register_class(TranslationPanel)
    bpy.utils.register_class(AtlasPanel)
    bpy.utils.register_class(UpdaterPanel)
    bpy.utils.register_class(CreditsPanel)
    bpy.utils.register_class(DemoPreferences)
    addon_updater_ops.register(bl_info)

def unregister():
    bpy.utils.unregister_class(tools.atlas.AutoAtlasButton)
    bpy.utils.unregister_class(tools.eyetracking.CreateEyesButton)
    bpy.utils.unregister_class(tools.viseme.AutoVisemeButton)
    bpy.utils.unregister_class(tools.translate.TranslateShapekeyButton)
    bpy.utils.unregister_class(tools.translate.TranslateBonesButton)
    bpy.utils.unregister_class(tools.translate.TranslateMeshesButton)
    bpy.utils.unregister_class(tools.translate.TranslateTexturesButton)
    bpy.utils.unregister_class(tools.translate.TranslateMaterialsButton)
    bpy.utils.unregister_class(tools.rootbone.RootButton)
    bpy.utils.unregister_class(tools.rootbone.RefreshRootButton)
    bpy.utils.unregister_class(tools.armature.FixPMXArmature)
    bpy.utils.unregister_class(tools.boneweight.DeleteZeroWeightBonesAndVertexGroups)
    #bpy.utils.unregister_class(tools.boneweight.DeleteBoneAndAddWeightsToParent)
    bpy.utils.unregister_class(tools.boneweight.DeleteBonesConstraints)
    bpy.utils.unregister_class(AtlasPanel)
    bpy.utils.unregister_class(EyeTrackingPanel)
    bpy.utils.unregister_class(VisemePanel)
    bpy.utils.unregister_class(BoneRootPanel)
    bpy.utils.unregister_class(TranslationPanel)
    bpy.utils.unregister_class(ArmaturePanel)
    bpy.utils.unregister_class(UpdaterPanel)
    bpy.utils.unregister_class(CreditsPanel)
    bpy.utils.unregister_class(DemoPreferences)
    addon_updater_ops.unregister()

if __name__ == '__main__':
    register()