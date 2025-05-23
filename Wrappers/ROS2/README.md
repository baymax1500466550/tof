# Introduction #

This package contains ROS2 wrapper nodes for ToF Sensor AFBR-S50 with CAN and UART interface.

### System Configurations ###

* OS / ROS
	Ubuntu 22.04 / ROS Humble
* USB TO UART module
* AFBR-S50 mikroE sensor board (https://www.mikroe.com/bdc-afbr-s50-tof-sensor-board#/279-tof_sensor_board-bdc_afbr_s50mv85i)

# Quick Start

## Installation

### Installing ROS

Install "ROS Desktop Full" on Ubuntu PC.

- ROS Humble for Ubuntu 22.04
    - https://docs.ros.org/en/humble/Installation/Alternatives/Ubuntu-Development-Setup.html

## Installation of tof_driver ##


```
$ git clone https://github.com/baymax1500466550/tof.git
$ cd ~/tof/Wrappers/ROS2/s50_tof_wrappers
$ colcon build
$ source ~/tof/Wrappers/ROS2/s50_tof_wrappers/install/setup.bash
```

### Setup ###
* The TOF sensor is by default connected to the 'ttyUSB1' port with a baud rate of '2M'.To adjust these settings, use the following command:
```
$ nano ~/tof/Wrappers/ROS2/s50_tof_wrappers/src/raw_tof/src/raw_tof.cpp
```
* Edit here:
```
serial_port.setPort("/dev/ttyUSB1");  // Set the serial port
serial_port.setBaudrate(2000000);  // Set the baud rate
```
* Rebuild again:
```
$ cd ~/tof/Wrappers/ROS2/s50_tof_wrappers
$ colcon build
```

### Connecting Tof sensors ###

* Connect a bunch tof sensors through the CAN interface (e.g. https://www.mikroe.com/bdc-afbr-s50-tof-sensor-board#/279-tof_sensor_board-bdc_afbr_s50mv85i) to form a daisy chain
* Connect the Tof sensor to the USB port of your Ubuntu PC via USB TO UART module

![connection](media/daisychain.png)


### Launching Software ###
#### Option 1 : Publish original data to ROS ####

* Open a new terminal and launch the raw data publisher.
```
$ source ~/tof/Wrappers/ROS2/s50_tof_wrappers/install/setup.bash
$ chmod 777 /dev/ttyUSB1
$ ros2 run raw_tof raw_tof
```

#### Option 2 : PointCloud in Rviz ####

* Open a new terminal and launch the pointcloud2 publisher.
```
$ rosrun rviz rviz
$ source ~/tof/Wrappers/ROS2/s50_tof_wrappers/install/setup.bash
$ chmod 777 /dev/ttyUSB1
$ ros2 launch pointcloud pointcloud.launch.py
```

For visualization and application tests an example implementation on a turtlebot using 5 x sensors boards is used.  
(https://www.mikroe.com/bdc-afbr-s50-tof-sensor-board#/279-tof_sensor_board-bdc_afbr_s50mv85i)  

![turtle](media/turtle.png)

The next video shows the streamed sensor data via Rviz showing a pointcloud of 5 x 32 pixels into the 3D-space.  

![Rviz](media/rviz.gif)

Here is an application video showing the capability of AFBR-S50 sensor for cliff detection.  

![cliff](media/cliff.gif)  

The video above shows the capability of Broadcom ToF sensors to be used for cliff and void detection on AMRs/AGVs. While the LIDAR (red dots) just see the side walls,
the downwards oriented ToF sensors (white point cloud) clearly detect the platform edges and initiates a direction change.
