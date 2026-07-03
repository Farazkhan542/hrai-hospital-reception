#!/usr/bin/env python3
"""Launch the three HRAI hospital-reception nodes together.

This does NOT launch Gazebo, TIAGo, or Nav2 — the course launchers
(``sim.launch.py`` / ``nav.launch.py``) bring those up. This file adds only our
own nodes: interaction, reasoning, navigation.

Launch arguments:
  * input_mode : 'stdin' (default, interactive) | 'scripted' (replay demo)
  * use_nav2   : 'true' (default, real Nav2) | 'false' (simulated motion, CPU)

Examples:
  ros2 launch hospital_reception reception.launch.py
  ros2 launch hospital_reception reception.launch.py use_nav2:=false
  ros2 launch hospital_reception reception.launch.py input_mode:=scripted use_nav2:=false
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    input_mode = LaunchConfiguration('input_mode')
    use_nav2 = LaunchConfiguration('use_nav2')

    declare_input_mode = DeclareLaunchArgument(
        'input_mode', default_value='stdin',
        description="Visitor input mode: 'stdin' or 'scripted'.",
    )
    declare_use_nav2 = DeclareLaunchArgument(
        'use_nav2', default_value='true',
        description="Use real Nav2 (true) or simulated motion fallback (false).",
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

    interaction = Node(
        package='hospital_reception',
        executable='interaction_node',
        name='interaction_node',
        # 'screen' keeps stdin attached so interactive mode works.
        output='screen',
        emulate_tty=True,
        parameters=[{'input_mode': input_mode}],
    )

    return LaunchDescription([
        declare_input_mode,
        declare_use_nav2,
        reasoning,
        navigation,
        interaction,
    ])
