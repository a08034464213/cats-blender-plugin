# -*- coding: utf-8 -*-

import logging
import os

import bpy
import math
from mathutils import Vector, Quaternion

from mmd_tools_local import utils
from mmd_tools_local.bpyutils import matmul
from mmd_tools_local.core import vmd
from mmd_tools_local.core.camera import MMDCamera
from mmd_tools_local.core.lamp import MMDLamp


class _MirrorMapper:
    def __init__(self, data_map=None):
        from mmd_tools_local.operators.view import FlipPose
        self.__data_map = data_map
        self.__flip_name = FlipPose.flip_name

    def get(self, name, default=None):
        return self.__data_map.get(self.__flip_name(name), None) or self.__data_map.get(name, default)

    @staticmethod
    def get_location(location):
        return (-location[0], location[1], location[2])

    @staticmethod
    def get_rotation(rotation_xyzw):
        return (rotation_xyzw[0], -rotation_xyzw[1], -rotation_xyzw[2], rotation_xyzw[3])

    @staticmethod
    def get_rotation3(rotation_xyz):
        return (rotation_xyz[0], -rotation_xyz[1], -rotation_xyz[2])


class RenamedBoneMapper:
    def __init__(self, armObj=None, rename_LR_bones=True, use_underscore=False, translator=None):
        self.__pose_bones = armObj.pose.bones if armObj else None
        self.__rename_LR_bones = rename_LR_bones
        self.__use_underscore = use_underscore
        self.__translator = translator

    def init(self, armObj):
        self.__pose_bones = armObj.pose.bones
        return self

    def get(self, bone_name, default=None):
        bl_bone_name = bone_name
        if self.__rename_LR_bones:
            bl_bone_name = utils.convertNameToLR(bl_bone_name, self.__use_underscore)
        if self.__translator:
            bl_bone_name = self.__translator.translate(bl_bone_name)
        return self.__pose_bones.get(bl_bone_name, default)


class BoneConverter:
    def __init__(self, pose_bone, scale, invert=False):
        mat = pose_bone.bone.matrix_local.to_3x3()
        mat[1], mat[2] = mat[2].copy(), mat[1].copy()
        self.__mat = mat.transposed()
        self.__scale = scale
        if invert:
            self.__mat.invert()

    def convert_location(self, location):
        return matmul(self.__mat, Vector(location)) * self.__scale

    def convert_rotation(self, rotation_xyzw):
        rot = Quaternion()
        rot.x, rot.y, rot.z, rot.w = rotation_xyzw
        return Quaternion(matmul(self.__mat, rot.axis) * -1, rot.angle).normalized()

class BoneConverterPoseMode:
    def __init__(self, pose_bone, scale, invert=False):
        mat = pose_bone.matrix.to_3x3()
        mat[1], mat[2] = mat[2].copy(), mat[1].copy()
        self.__mat = mat.transposed()
        self.__scale = scale
        self.__mat_rot = pose_bone.matrix_basis.to_3x3()
        self.__mat_loc = matmul(self.__mat_rot, self.__mat)
        self.__offset = pose_bone.location.copy()
        self.convert_location = self._convert_location
        self.convert_rotation = self._convert_rotation
        if invert:
            self.__mat.invert()
            self.__mat_rot.invert()
            self.__mat_loc.invert()
            self.convert_location = self._convert_location_inverted
            self.convert_rotation = self._convert_rotation_inverted

    def _convert_location(self, location):
        return self.__offset + matmul(self.__mat_loc, Vector(location)) * self.__scale

    def _convert_rotation(self, rotation_xyzw):
        rot = Quaternion()
        rot.x, rot.y, rot.z, rot.w = rotation_xyzw
        rot = Quaternion(matmul(self.__mat, rot.axis) * -1, rot.angle)
        return matmul(self.__mat_rot, rot.to_matrix()).to_quaternion()

    def _convert_location_inverted(self, location):
        return matmul(self.__mat_loc, Vector(location) - self.__offset) * self.__scale

    def _convert_rotation_inverted(self, rotation_xyzw):
        rot = Quaternion()
        rot.x, rot.y, rot.z, rot.w = rotation_xyzw
        rot = matmul(self.__mat_rot, rot.to_matrix()).to_quaternion()
        return Quaternion(matmul(self.__mat, rot.axis) * -1, rot.angle).normalized()


class VMDImporter:
    def __init__(self, filepath, scale=1.0, bone_mapper=None, use_pose_mode=False,
            convert_mmd_camera=True, convert_mmd_lamp=True, frame_margin=5, use_mirror=False):
        self.__vmdFile = vmd.File()
        self.__vmdFile.load(filepath=filepath)
        self.__scale = scale
        self.__convert_mmd_camera = convert_mmd_camera
        self.__convert_mmd_lamp = convert_mmd_lamp
        self.__bone_mapper = bone_mapper
        self.__bone_util_cls = BoneConverterPoseMode if use_pose_mode else BoneConverter
        self.__frame_margin = frame_margin + 1
        self.__mirror = use_mirror


    @staticmethod
    def __minRotationDiff(prev_q, curr_q):
        pq, q = prev_q, curr_q
        nq = q.copy()
        nq.negate()
        t1 = (pq.w-q.w)**2+(pq.x-q.x)**2+(pq.y-q.y)**2+(pq.z-q.z)**2
        t2 = (pq.w-nq.w)**2+(pq.x-nq.x)**2+(pq.y-nq.y)**2+(pq.z-nq.z)**2
        #t1 = pq.rotation_difference(q).angle
        #t2 = pq.rotation_difference(nq).angle
        if t2 < t1:
            return nq
        return q

    @staticmethod
    def __setInterpolation(bezier, kp0, kp1):
        if bezier[0] == bezier[1] and bezier[2] == bezier[3]:
            kp0.interpolation = 'LINEAR'
        else:
            kp0.interpolation = 'BEZIER'
            kp0.handle_right_type = 'FREE'
            kp1.handle_left_type = 'FREE'
            d = (kp1.co - kp0.co) / 127.0
            kp0.handle_right = kp0.co + Vector((d.x * bezier[0], d.y * bezier[1]))
            kp1.handle_left = kp0.co + Vector((d.x * bezier[2], d.y * bezier[3]))

    @staticmethod
    def __fixFcurveHandles(fcurve):
        kp0 = fcurve.keyframe_points[0]
        kp0.handle_left = kp0.co + Vector((-1, 0))
        kp = fcurve.keyframe_points[-1]
        kp.handle_right = kp.co + Vector((1, 0))


    def __assignToArmature(self, armObj, action_name=None):
        boneAnim = self.__vmdFile.boneAnimation
        logging.info('---- bone animations:%5d  target: %s', len(boneAnim), armObj.name)
        if len(boneAnim) < 1:
            return

        action_name = action_name or armObj.name
        action = bpy.data.actions.new(name=action_name)
        armObj.animation_data_create().action = action

        extra_frame = 1 if self.__frame_margin > 1 else 0

        pose_bones = armObj.pose.bones
        if self.__bone_mapper:
            pose_bones = self.__bone_mapper(armObj)

        _loc = _rot = lambda i: i
        if self.__mirror:
            pose_bones = _MirrorMapper(pose_bones)
            _loc, _rot = _MirrorMapper.get_location, _MirrorMapper.get_rotation

        bone_name_table = {}
        for name, keyFrames in boneAnim.items():
            num_frame = len(keyFrames)
            if num_frame < 1:
                continue
            bone = pose_bones.get(name, None)
            if bone is None:
                logging.warning('WARNING: not found bone %s (%d frames)', name, len(keyFrames))
                continue
            logging.info('(bone) frames:%5d  name: %s', len(keyFrames), name)
            assert(bone_name_table.get(bone.name, name) == name)
            bone_name_table[bone.name] = name

            fcurves = [None]*7 # x, y, z, rw, rx, ry, rz
            default_values = list(bone.location) + list(bone.rotation_quaternion)
            data_path = 'pose.bones["%s"].location'%bone.name
            for axis_i in range(3):
                fcurves[axis_i] = action.fcurves.new(data_path=data_path, index=axis_i, action_group=bone.name)
            data_path = 'pose.bones["%s"].rotation_quaternion'%bone.name
            for axis_i in range(4):
                fcurves[3+axis_i] = action.fcurves.new(data_path=data_path, index=axis_i, action_group=bone.name)

            for i, c in enumerate(fcurves):
                c.keyframe_points.add(extra_frame+num_frame)
                kp_iter = iter(c.keyframe_points)
                if extra_frame:
                    kp = next(kp_iter)
                    kp.co = (1, default_values[i])
                    kp.interpolation = 'LINEAR'
                fcurves[i] = kp_iter

            converter = self.__bone_util_cls(bone, self.__scale)
            prev_rot = bone.rotation_quaternion if extra_frame else None
            prev_kps, indices = None, (0, 32, 16, 48, 48, 48, 48) # x, z, y, rw, rx, ry, rz
            keyFrames.sort(key=lambda x:x.frame_number)
            for k, x, y, z, rw, rx, ry, rz in zip(keyFrames, *fcurves):
                frame = k.frame_number + self.__frame_margin
                loc = converter.convert_location(_loc(k.location))
                curr_rot = converter.convert_rotation(_rot(k.rotation))
                if prev_rot is not None:
                    curr_rot = self.__minRotationDiff(prev_rot, curr_rot)
                prev_rot = curr_rot

                x.co = (frame, loc[0])
                y.co = (frame, loc[1])
                z.co = (frame, loc[2])
                rw.co = (frame, curr_rot[0])
                rx.co = (frame, curr_rot[1])
                ry.co = (frame, curr_rot[2])
                rz.co = (frame, curr_rot[3])

                curr_kps = (x, y, z, rw, rx, ry, rz)
                if prev_kps is not None:
                    interp = k.interp
                    for idx, prev_kp, kp in zip(indices, prev_kps, curr_kps):
                        self.__setInterpolation(interp[idx:idx+16:4], prev_kp, kp)
                prev_kps = curr_kps

        for c in action.fcurves:
            self.__fixFcurveHandles(c)

        # ensure IK's default state
        for b in armObj.pose.bones:
            if not b.mmd_ik_toggle:
                b.mmd_ik_toggle = True

        # property animation
        propertyAnim = self.__vmdFile.propertyAnimation
        if len(propertyAnim) < 1:
            return
        logging.info('---- IK animations:%5d  target: %s', len(propertyAnim), armObj.name)
        for keyFrame in propertyAnim:
            frame = keyFrame.frame_number + self.__frame_margin
            for ikName, enable in keyFrame.ik_states:
                bone = pose_bones.get(ikName, None)
                if bone:
                    bone.mmd_ik_toggle = enable
                    bone.keyframe_insert(data_path='mmd_ik_toggle', frame=frame)


    def __assignToMesh(self, meshObj, action_name=None):
        shapeKeyAnim = self.__vmdFile.shapeKeyAnimation
        logging.info('---- morph animations:%5d  target: %s', len(shapeKeyAnim), meshObj.name)
        if len(shapeKeyAnim) < 1:
            return

        action_name = action_name or meshObj.name
        action = bpy.data.actions.new(name=action_name)
        meshObj.data.shape_keys.animation_data_create().action = action

        mirror_map = _MirrorMapper(meshObj.data.shape_keys.key_blocks) if self.__mirror else {}
        shapeKeyDict = {k:mirror_map.get(k, v) for k, v in meshObj.data.shape_keys.key_blocks.items()}

        from math import floor, ceil
        for name, keyFrames in shapeKeyAnim.items():
            if name not in shapeKeyDict:
                logging.warning('WARNING: not found shape key %s (%d frames)', name, len(keyFrames))
                continue
            logging.info('(mesh) frames:%5d  name: %s', len(keyFrames), name)
            shapeKey = shapeKeyDict[name]
            fcurve = action.fcurves.new(data_path='key_blocks["%s"].value'%shapeKey.name)
            fcurve.keyframe_points.add(len(keyFrames))
            keyFrames.sort(key=lambda x:x.frame_number)
            for k, v in zip(keyFrames, fcurve.keyframe_points):
                v.co = (k.frame_number+self.__frame_margin, k.weight)
                v.interpolation = 'LINEAR'
            weights = tuple(i.weight for i in keyFrames)
            shapeKey.slider_min = min(shapeKey.slider_min, floor(min(weights)))
            shapeKey.slider_max = max(shapeKey.slider_max, ceil(max(weights)))


    def __assignToRoot(self, rootObj, action_name=None):
        propertyAnim = self.__vmdFile.propertyAnimation
        logging.info('---- display animations:%5d  target: %s', len(propertyAnim), rootObj.name)
        if len(propertyAnim) < 1:
            return

        action_name = action_name or rootObj.name
        action = bpy.data.actions.new(name=action_name)
        rootObj.animation_data_create().action = action

        for keyFrame in propertyAnim:
            rootObj.mmd_root.show_meshes = keyFrame.visible
            rootObj.keyframe_insert(data_path='mmd_root.show_meshes',
                                    frame=keyFrame.frame_number+self.__frame_margin)


    @staticmethod
    def detectCameraChange(fcurve, threshold=10.0):
        frames = list(fcurve.keyframe_points)
        frameCount = len(frames)
        frames.sort(key=lambda x:x.co[0])
        for i, f in enumerate(frames):
            if i+1 < frameCount:
                n = frames[i+1]
                if n.co[0] - f.co[0] <= 1.0 and abs(f.co[1] - n.co[1]) > threshold:
                    f.interpolation = 'CONSTANT'

    def __assignToCamera(self, cameraObj, action_name=None):
        mmdCameraInstance = MMDCamera.convertToMMDCamera(cameraObj, self.__scale)
        mmdCamera = mmdCameraInstance.object()
        cameraObj = mmdCameraInstance.camera()

        cameraAnim = self.__vmdFile.cameraAnimation
        logging.info('(camera) frames:%5d  name: %s', len(cameraAnim), mmdCamera.name)
        if len(cameraAnim) < 1:
            return

        action_name = action_name or mmdCamera.name
        parent_action = bpy.data.actions.new(name=action_name)
        distance_action = bpy.data.actions.new(name=action_name+'_dis')
        mmdCamera.animation_data_create().action = parent_action
        cameraObj.animation_data_create().action = distance_action

        _loc = _rot = lambda i: i
        if self.__mirror:
            _loc, _rot = _MirrorMapper.get_location, _MirrorMapper.get_rotation3

        fcurves = []
        for i in range(3):
            fcurves.append(parent_action.fcurves.new(data_path='location', index=i)) # x, y, z
        for i in range(3):
            fcurves.append(parent_action.fcurves.new(data_path='rotation_euler', index=i)) # rx, ry, rz
        fcurves.append(parent_action.fcurves.new(data_path='mmd_camera.angle')) # fov
        fcurves.append(parent_action.fcurves.new(data_path='mmd_camera.is_perspective')) # persp
        fcurves.append(distance_action.fcurves.new(data_path='location', index=1)) # dis
        for c in fcurves:
            c.keyframe_points.add(len(cameraAnim))

        prev_kps, indices = None, (0, 8, 4, 12, 12, 12, 16, 20) # x, z, y, rx, ry, rz, dis, fov
        cameraAnim.sort(key=lambda x:x.frame_number)
        for k, x, y, z, rx, ry, rz, fov, persp, dis in zip(cameraAnim, *(c.keyframe_points for c in fcurves)):
            frame = k.frame_number + self.__frame_margin
            x.co, z.co, y.co = ((frame, val*self.__scale) for val in _loc(k.location))
            rx.co, rz.co, ry.co = ((frame, val) for val in _rot(k.rotation))
            fov.co = (frame, math.radians(k.angle))
            dis.co = (frame, k.distance*self.__scale)
            persp.co = (frame, k.persp)

            persp.interpolation = 'CONSTANT'
            curr_kps = (x, y, z, rx, ry, rz, dis, fov)
            if prev_kps is not None:
                interp = k.interp
                for idx, prev_kp, kp in zip(indices, prev_kps, curr_kps):
                    self.__setInterpolation(interp[idx:idx+4:2]+interp[idx+1:idx+4:2], prev_kp, kp)
            prev_kps = curr_kps

        for fcurve in fcurves:
            self.__fixFcurveHandles(fcurve)
            if fcurve.data_path == 'rotation_euler':
                self.detectCameraChange(fcurve)


    @staticmethod
    def detectLampChange(fcurve, threshold=0.1):
        frames = list(fcurve.keyframe_points)
        frameCount = len(frames)
        frames.sort(key=lambda x:x.co[0])
        for i, f in enumerate(frames):
            f.interpolation = 'LINEAR'
            if i+1 < frameCount:
                n = frames[i+1]
                if n.co[0] - f.co[0] <= 1.0 and abs(f.co[1] - n.co[1]) > threshold:
                    f.interpolation = 'CONSTANT'

    def __assignToLamp(self, lampObj, action_name=None):
        mmdLampInstance = MMDLamp.convertToMMDLamp(lampObj, self.__scale)
        mmdLamp = mmdLampInstance.object()
        lampObj = mmdLampInstance.lamp()

        lampAnim = self.__vmdFile.lampAnimation
        logging.info('(lamp) frames:%5d  name: %s', len(lampAnim), mmdLamp.name)
        if len(lampAnim) < 1:
            return

        action_name = action_name or mmdLamp.name
        color_action = bpy.data.actions.new(name=action_name+'_color')
        location_action = bpy.data.actions.new(name=action_name+'_loc')
        lampObj.data.animation_data_create().action = color_action
        lampObj.animation_data_create().action = location_action

        _loc = _MirrorMapper.get_location if self.__mirror else lambda i: i
        for keyFrame in lampAnim:
            frame = keyFrame.frame_number + self.__frame_margin
            lampObj.data.color = Vector(keyFrame.color)
            lampObj.location = Vector(_loc(keyFrame.direction)).xzy * -1
            lampObj.data.keyframe_insert(data_path='color', frame=frame)
            lampObj.keyframe_insert(data_path='location', frame=frame)

        for fcurve in lampObj.animation_data.action.fcurves:
            self.detectLampChange(fcurve)


    def assign(self, obj, action_name=None):
        if obj is None:
            return
        if action_name is None:
            action_name = os.path.splitext(os.path.basename(self.__vmdFile.filepath))[0]

        if MMDCamera.isMMDCamera(obj):
            self.__assignToCamera(obj, action_name+'_camera')
        elif MMDLamp.isMMDLamp(obj):
            self.__assignToLamp(obj, action_name+'_lamp')
        elif getattr(obj.data, 'shape_keys', None):
            self.__assignToMesh(obj, action_name+'_facial')
        elif obj.type == 'ARMATURE':
            self.__assignToArmature(obj, action_name+'_bone')
        elif obj.type == 'CAMERA' and self.__convert_mmd_camera:
            self.__assignToCamera(obj, action_name+'_camera')
        elif obj.type == 'LAMP' and self.__convert_mmd_lamp:
            self.__assignToLamp(obj, action_name+'_lamp')
        elif obj.mmd_type == 'ROOT':
            self.__assignToRoot(obj, action_name+'_display')
        else:
            pass

