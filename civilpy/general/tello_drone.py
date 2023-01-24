from djitellopy import Tello
import cv2
import time

width = 320
height = 240
startCounter = 0

me = Tello()
me.connect()

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
    cv2.imshow("MyResult", img)

    if startCounter == 0:
        me.takeoff()
        time.sleep(8)
        me.rotate_clockwise(180)
        time.sleep(3)
        me.flip_right()
        time.sleep(3)
        me.flip_forward()
        me.land()
        startCounter = 1

    if cv2.waitKey(1) & 0xFF == ord('q'):
        me.land()
        break