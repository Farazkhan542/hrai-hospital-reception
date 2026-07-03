#!/usr/bin/env python3
"""Convenience launch for the scripted demo video.

Brings up the reasoning + navigation nodes and then runs the ``run_demo`` driver
(``scripts/run_demo.py``), which plays the two scripted interactions (easy +
hard case) end-to-end. Defaults to ``use_nav2:=false`` so the whole demo runs on
a weak, no-GPU Windows/WSL2 machine with only the simulated-motion fallback.

We intentionally do NOT also launch ``interaction_node`` here — ``run_demo`` is
the driver for this launch, so launching both would double-drive the dialogue.
To exercise ``interaction_node``'s own scripted mode instead, use:
    ros2 launch hospital_reception reception.launch.py input_mode:=scripted use_nav2:=false

Examples:
  ros2 launch hospital_reception demo.launch.py
  ros2 launch hospital_reception demo.launch.py use_nav2:=true
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    use_nav2 = LaunchConfiguration('use_nav2')

    declare_use_nav2 = DeclareLaunchArgument(
        'use_nav2', default_value='false',
        description="Use real Nav2 (true) or simulated motion fallback (false). "
                    "Defaults to false for the CPU-only demo.",
    )

    reasoning = Node(
        package='hospital_reception',
        executable='reasoning_node',
        name='reasoning_node',
        output='screen',
    )

    navigation = Node(
        package='hospital_reception',
        executable='navigation_node',
        name='navigation_node',
        output='screen',
        parameters=[{'use_nav2': use_nav2}],
    )

    # The scripted driver (own node): plays the two demo interactions.
    demo_driver = Node(
        package='hospital_reception',
        executable='run_demo',
        name='run_demo',
        output='screen',
        emulate_tty=True,
    )

    return LaunchDescription([
        declare_use_nav2,
        reasoning,
        navigation,
        demo_driver,
    ])
