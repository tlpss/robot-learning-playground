import logging
from pathlib import Path

import wandb
from pybullet_sim.pick_env import UR3ePick

from robot_learning.se2_action_map_q_learning import SpatialActionDQN, seed_all

if __name__ == "__main__":

    config = {
        "n_demonstration_steps": 10,
        "lr": 1e-3,
        "batch_size": 4,
        "n_rotations": 1,
        "n_channels": 128,
        "n_downsampling_layers": 1,
        "n_resnet_blocks": 1,
        "discount_factor": 0.0,
        "action_sample_temperature": 1e-8,
        "n_training_steps": 1000,
        "seed": 2022,
    }
    logging.basicConfig(level=logging.INFO)
    wandb.init(
        project="spatial-action-pybullet-pick", dir=str(Path(__file__).parents[1]), mode="online", config=config
    )
    # get possibly updated config from wandb
    config = wandb.config

    seed_all(config["seed"])
    env = UR3ePick(use_motion_primitive=True, use_spatial_action_map=True, simulate_realtime=False)
    dqn = SpatialActionDQN(env.image_dimensions[0], device="cuda", **config)
    dqn.train(env, config["n_training_steps"])
