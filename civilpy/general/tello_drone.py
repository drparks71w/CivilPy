from djitellopy import Tello
import cv2

width = 320
height = 240
startCounter = 0

me = Tello()
me.conect()

me.for_back_velocity = 0
me.lefrt_right_velocity = 0
me.up_down_velocity = 0
me.yaw_velocity = 0
me.speed = 0

print(me.get_battery())

me.streamoff()
me.streamon()

while True:
    frame_read = me.get_frame_read()
    myFrame = frame_read.frame
    img = cv2.resize(myFrame, (width, height))

    if startCounter == 0:
        me.takeoff()
        me.move_left(20)
        me.rotate_clockwise(90)