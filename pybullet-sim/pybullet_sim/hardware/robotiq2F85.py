from fileinput import close
import logging
import math
from typing import List
import pybullet as p 
import pybullet_data
from pybullet_sim.assets.path import get_asset_root_folder
from pybullet_sim.pybullet_utils import HideOutput
import math
class Gripper():
    open_relative_position = 0.0
    closed_relative_position = 1.0

    def __init__(self, gripper_id, simulate_realtime: bool = True ) -> None:
        self.gripper_id = gripper_id
        self.simulate_real_time = simulate_realtime

        self.target_relative_position: float = Gripper.open_relative_position
        self.reset()

    def reset(self, pose:List[float] = None):
        self.target_relative_position = Gripper.open_relative_position
        self._set_joint_targets(self.target_relative_position, max_force=100)
        if pose is not None:
            p.resetBasePositionAndOrientation(self.gripper_id, pose[:3], pose[3:])

    def open_gripper(self,max_force: int = 100):
        self.movej(Gripper.open_relative_position,max_force)
    
    def close_gripper(self,max_force: int = 100):
        self.movej(Gripper.closed_relative_position, max_force)

    def movej(self, target_relative_position:float, max_force: int = 100, max_steps:int = 200):
        # bookkeeping
        self.target_relative_position = target_relative_position


        for _ in range(max_steps):
            current_relative_position = self.get_relative_position()
            if abs(target_relative_position - current_relative_position) < 1e-2:
                return True
            self._set_joint_targets(target_relative_position, max_force)
            p.stepSimulation()
            if self.simulate_real_time:
                time.sleep(1.0 / 240)
        logging.debug(f"Warning: movej exceeded {max_steps} simulation steps for {self.__class__}. Skipping.")
        
    def _set_joint_targets(self, target_relative_position:float, max_force: int,max_steps: int = 100):
        raise NotImplementedError

    def is_object_grasped(self):
        # rather hacky proxy, use with care..
        return abs(self.target_relative_position - self.get_relative_position()) > 0.1
    
    def get_relative_position(self):
        raise NotImplementedError



class Robotiq2F85(Gripper):
    """
    the Robotiq grippers proved to be a pain to simulate as they have a closed chain due to their parallel inner and outer knuckles.
    Actuating the 6 joints seperately is not recommended as the joints would close faster/slower, resulting in unrealistic grasping. 

    In fact all joints on each finger (3/finger) should mimic each other, and so do the 2 fingers, however this resulted in physics instabilities so I 
    hacked until something worked.
    
    I attached the outer joint to the finger pad joint, to make sure the pad is vertical at all times.
    The inner knuckle acuates independently, but has no collision object so this is cosmetic.
    """
    open_position = 0.000
    closed_position = 0.085

    def __init__(self) -> None:
        gripper_id = p.loadURDF(str(get_asset_root_folder()  / "robotiq2f85" / "robotiq_2f_85.urdf"),useFixedBase=False)
  
        super().__init__(gripper_id)
        self._create_constraints()

    def _create_constraints(self):
        constraint_dict = {5:{7:-1},0: {2:-1}} # attach finger joint to outer knuckle to keep fingertips vertical.
        for parent_id, children_dict in constraint_dict.items():
            for joint_id, multiplier in children_dict.items():
                print(joint_id)
                c = p.createConstraint(self.gripper_id, parent_id,
                                    self.gripper_id, joint_id,
                                    jointType=p.JOINT_GEAR,
                                    jointAxis=[0, 1, 0],
                                    parentFramePosition=[0, 0, 0],
                                    childFramePosition=[0, 0, 0])
                p.changeConstraint(c, gearRatio=-multiplier, maxForce=100, erp=1)  # Note: the mysterious `erp` is of EXTREME importance
            
    def _set_joint_targets(self, target_relative_position ,max_force):
        open_angle = self._relative_position_to_joint_angle(target_relative_position)
        right_finger_dict = {7:-1,9:1,5:1} # finger and inner knuckle
        left_finger_dict = {2:-1,4:1,0:1} # finger and inner knuckle
        for finger_dict in [left_finger_dict,right_finger_dict]:
            for id, direction in finger_dict.items():
                p.setJointMotorControl2(self.gripper_id, id,p.POSITION_CONTROL,targetPosition=open_angle * direction,force=max_force, maxVelocity=0.5)

    @staticmethod
    def _joint_angle_to_relative_position(angle:float) -> float:
        abs_position = math.sin(0.715-angle) * 0.1143 + 0.01
        rel_position = abs_position - Robotiq2F85.closed_position / (Robotiq2F85.open_position-Robotiq2F85.closed_position)
        return rel_position

    @staticmethod
    def _relative_position_to_joint_angle(relative_position: float) -> float:
        abs_position = Robotiq2F85.closed_position + (Robotiq2F85.open_position - Robotiq2F85.closed_position) * relative_position
        open_angle = 0.715 - math.asin((abs_position - 0.010) / 0.1143)  # angle calculation approx 
        return open_angle

    def get_relative_position(self):
        joint_config = p.getJointState(self.gripper_id, 0)[0]
        return self._joint_angle_to_relative_position(joint_config)

        
class WSG50(Gripper):
    def __init__(self):
        # values taken from https://colab.research.google.com/drive/1eXq-Tl3QKzmbXGSKU2hDk0u_EHdfKVd0?usp=sharing
        # and then adapted
        open_position = 0.0
        closed_position = 0.085
        self.home_joint_positions = [0.000000, -0.011130, -0.206421, 0.205143, -0.0, 0.000000, -0.0, 0.000000]
        with HideOutput():
            gripper_id = p.loadSDF("gripper/wsg50_one_motor_gripper_new_free_base.sdf")[0]
     
        super().__init__(gripper_id,open_position, closed_position)
        self.left_pincher_joint_id  = 4
        self.right_pincher_joint_id = 6

    
    def reset(self, pose=None):
        for jointIndex in range(p.getNumJoints(self.gripper_id)):
            p.resetJointState(self.gripper_id, jointIndex, self.home_joint_positions[jointIndex])
            p.setJointMotorControl2(self.gripper_id, jointIndex, p.POSITION_CONTROL, self.home_joint_positions[jointIndex], 0)
        super().reset(pose)


    def _set_joint_targets(self, position, max_force):
        for id in [self.left_pincher_joint_id, self.right_pincher_joint_id]:
            p.setJointMotorControl2(self.gripper_id,id, p.POSITION_CONTROL, targetPosition=position, maxVelocity=0.5, force=max_force)




if __name__ == "__main__":
    import time 
    from pybullet_sim.hardware.ur3e import UR3e
    physicsClient = p.connect(p.GUI)  # or p.DIRECT for non-graphical version
    p.setAdditionalSearchPath(pybullet_data.getDataPath())  # optionally
    #p.setGravity(0, 0, -10)
    tableId = p.loadURDF(str(get_asset_root_folder() / "ur3e_workspace" / "workspace.urdf"), [0, -0.3, -0.01])

    target = p.getDebugVisualizerCamera()[11]
    p.configureDebugVisualizer(p.COV_ENABLE_RGB_BUFFER_PREVIEW, 1)

    p.resetDebugVisualizerCamera(cameraDistance=1.8, cameraYaw=0, cameraPitch=-45, cameraTargetPosition=target)


    robot = UR3e(simulate_real_time=True)
    gripper = Robotiq2F85()
    gripper.reset(robot.get_eef_pose())
    for i in range(p.getNumJoints(gripper.gripper_id)):
        print(p.getJointInfo(gripper.gripper_id, i))

    kuka_cid = p.createConstraint(robot.robot_id,robot.eef_id, gripper.gripper_id, -1, p.JOINT_FIXED, [0, 0, 0.0], [0.0, 0.0, 0], [0, 0,0],childFrameOrientation=p.getQuaternionFromEuler([0,0,1.57]))
    gripper.movej(1.0,max_steps= 500)

    robot.movep([0.2,-0.0,0.2,0,0,0,1],speed=0.001)
    gripper.movej(0.6,max_steps=500)
    gripper.movej(1.0,max_steps=500)
    gripper.movej(0.0,max_steps=500)

    time.sleep(100)
    p.disconnect()