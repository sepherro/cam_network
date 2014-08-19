import socket
import cv2
import numpy
import cv2.cv as cv
import math
import time

TCP_IP = '192.168.0.100'
TCP_PORT = 5001

sock = socket.socket()
sock.connect((TCP_IP, TCP_PORT))
capture = cv2.VideoCapture(0)

capture.set(cv.CV_CAP_PROP_FRAME_WIDTH, 320)
capture.set(cv.CV_CAP_PROP_FRAME_HEIGHT, 240)

for x in range(0, 15):
    ret, frame = capture.read()
background = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
struct = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))

print "Frame resolution set to: (" + str(capture.get(cv.CV_CAP_PROP_FRAME_WIDTH)) + "; " + str(capture.get(cv.CV_CAP_PROP_FRAME_HEIGHT)) + ")"
print "Client running, press ESC to quit"

activation_level_past = 0

def lowpass(prev_sample, input):
    gain = 0.1
    time_constant = 1
    sample_time = 0.1
    output = (gain/time_constant) * input + prev_sample * pow(math.e, -1.0 *(sample_time/time_constant))
    return output

while True:

    # simple profiling
    start = time.clock()

    ret, frame = capture.read()

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask_gt = cv2.compare(background, gray, cv2.CMP_GT)
    mask_lt = cv2.compare(background, gray, cv2.CMP_LT)
    background += mask_lt/128
    background -= mask_gt/128
    difference = cv2.absdiff(background, gray)
    difference = cv2.medianBlur(difference, 3)
    display = cv2.compare(difference, 6, cv2.CMP_GT)
    eroded = cv2.erode(display, struct)
    dilated = cv2.dilate(eroded, struct)
    nonzero = cv2.countNonZero(dilated)

    height, width = dilated.shape[:2]
    percentage = (nonzero * 100 / (height * width))

    activation_level = lowpass(activation_level_past, percentage)
    activation_level_past = activation_level

    encode_param=[int(cv2.IMWRITE_JPEG_QUALITY),90]
    result, imgencode = cv2.imencode('.jpg', dilated, encode_param)
    data = numpy.array(imgencode)
   
    stringData = data.tostring()
    sock.send( socket.gethostname().ljust(8) )
    sock.send( str(percentage).ljust(32) )
    sock.send( str(activation_level).ljust(32) )
    sock.send( str(len(stringData)).ljust(32) )
    sock.send( stringData )

    key = cv2.waitKey(10)
    if key == 27:               # exit on ESC
        break

    print "Elapsed time: ", time.clock() - start , "seconds"

sock.close()

cv2.waitKey(0)
cv2.destroyAllWindows() 

print "Client terminated"
