# Python
import logging
import time
import picamera
from picamera.array import PiRGBArray
from picamera import PiCamera
import numpy as np
import cv2  #MAF
from threading import Thread

logging.basicConfig()
LOGLEVEL = logging.getLogger().getEffectiveLevel()

RESOLUTION = (320, 320)

logging.basicConfig()

# https://github.com/dtreskunov/rpi-sensorium/commit/40c6f3646931bf0735c5fe4579fa89947e96aed7


def run_pantilt_detect(center_x, center_y, labels, model_cls, rotation, resolution=RESOLUTION):

    model = model_cls()

    capture_manager = WebcamVideoStream(resolution=RESOLUTION)     ###
    capture_manager.start()
    #capture_manager.start_overlay()

    label_idxs = model.label_to_category_index(labels)
    start_time = time.time()
    fps_counter = 0
    while not capture_manager.stopped:
        if capture_manager.grabbed:                     ###
            frame = capture_manager.read()         
            prediction = model.predict(frame)

            if not len(prediction.get('detection_boxes')):
                continue

            if any(item in label_idxs for item in prediction.get('detection_classes')):

                tracked = (
                    (i, x) for i, x in
                    enumerate(prediction.get('detection_classes'))
                    if x in label_idxs
                )
                tracked_idxs, tracked_classes = zip(*tracked)

                track_target = prediction.get('detection_boxes')[
                    tracked_idxs[0]]
                # [ymin, xmin, ymax, xmax]
                y = int(
                    RESOLUTION[1] - ((np.take(track_target, [0, 2])).mean() * RESOLUTION[1]))
                center_y.value = y
                x = int(
                    RESOLUTION[0] - ((np.take(track_target, [1, 3])).mean() * RESOLUTION[0]))
                center_x.value = x

                display_name = model.category_index[tracked_classes[0]]['name']
                logging.info(
                    f'Tracking {display_name} center_x {x} center_y {y}')

            overlay = model.create_overlay(frame, prediction)
            print(type(overlay))
            #capture_manager.overlay_buff = overlay
            if LOGLEVEL is logging.DEBUG and (time.time() - start_time) > 1:
                fps_counter += 1
                fps = fps_counter / (time.time() - start_time)
                logging.debug(f'FPS: {fps}')
                fps_counter = 0
                start_time = time.time()

def run_stationary_detect(labels, model_cls, rotation):
    '''
        Overlay is rendered around all tracked objects
    '''
    model = model_cls()

    capture_manager = WebcamVideoStream(resolution=RESOLUTION)
    capture_manager.start()
    #capture_manager.start_overlay()

    label_idxs = model.label_to_category_index(labels)
    start_time = time.time()
    fps_counter = 0

    try:
        while not capture_manager.stopped:
            if capture_manager.grabbed:
                frame = capture_manager.read()
                prediction = model.predict(frame)

                if not len(prediction.get('detection_boxes')):
                    continue
                if any(item in label_idxs for item in prediction.get('detection_classes')):
                    
                    # Not all models will need to implement a filter_tracked() interface
                    # For example, FaceSSD only allows you to track 1 class (faces) and does not implement this method
                    try:
                        filtered_prediction = model.filter_tracked(
                        prediction, label_idxs)
                    except AttributeError:
                        filtered_prediction = prediction

                    overlay = model.create_overlay(frame, filtered_prediction)
                    print(type(overlay))
                    #capture_manager.overlay_buff = overlay

                if LOGLEVEL is logging.DEBUG and (time.time() - start_time) > 1:
                    fps_counter += 1
                    fps = fps_counter / (time.time() - start_time)
                    logging.debug(f'FPS: {fps}')
                    fps_counter = 0
                    start_time = time.time()
    except KeyboardInterrupt:
        capture_manager.stop()

        
class WebcamVideoStream:
	def __init__(self, src=0, name="WebcamVideoStream",resolution=(320,320) ):
		# initialize the video camera stream and read the first frame
		# from the stream
		self.stream = cv2.VideoCapture(src)
		(self.grabbed, self.frame) = self.stream.read()
        
        # initialize the thread name
		self.name = name
    
    self.resolution = resolution

		# initialize the variable used to indicate if the thread should
		# be stopped
		self.stopped = False

	def start(self):
		# start the thread to read frames from the video stream
		t = Thread(target=self.update, name=self.name, args=())
		t.daemon = True
		t.start()
		return self

	def update(self):
		# keep looping infinitely until the thread is stopped
		while True:
			# if the thread indicator variable is set, stop the thread
			if self.stopped:
				return

			# otherwise, read the next frame from the stream
			(self.grabbed, self.frame) = self.stream.read()

	def read(self):
		# return the frame most recently read
		return cv2.resize(self.frame,self.resolution)

	def stop(self):
		# indicate that the thread should be stopped
		self.stopped = True
"""
def _monkey_patch_picamera(overlay):
    original_send_buffer = picamera.mmalobj.MMALPortPool.send_buffer

    def silent_send_buffer(zelf, *args, **kwargs):
        try:
            original_send_buffer(zelf, *args, **kwargs)
        except picamera.exc.PiCameraMMALError as error:
            # Only silence MMAL_EAGAIN for our target instance.
            our_target = overlay.renderer.inputs[0].pool == zelf
            if not our_target or error.status != 14:
                raise error

    picamera.mmalobj.MMALPortPool.send_buffer = silent_send_buffer


class PiCameraStream(object):

    def __init__(self,
                 resolution=(320, 240),
                 framerate=24,
                 vflip=False,
                 hflip=False,
                 rotation=0,
                 max_workers=2
                 ):

        self.camera = PiCamera()                ###
        self.camera.resolution = resolution     ###
        self.camera.framerate = framerate       ###
        self.camera.vflip = vflip               ###
        self.camera.hflip = hflip               ###
        self.camera.rotation = rotation         ###
        self.overlay = None

        self.data_container = PiRGBArray(self.camera, size=resolution)      ###

        self.stream = self.camera.capture_continuous(
            self.data_container, format="rgb", use_video_port=True
        )                                                                   ###

        self.overlay_buff = None
        self.frame = None
        self.stopped = False
        logging.info('starting camera preview')
        self.camera.start_preview()                                         ###

    def render_overlay(self):
        while True:
            if self.overlay and self.overlay_buff:
                self.overlay.update(self.overlay_buff)
            elif not self.overlay and self.overlay_buff:
                self.overlay = self.camera.add_overlay(
                    self.overlay_buff, layer=3, size=self.camera.resolution)
                _monkey_patch_picamera(self.overlay)                        ###

    def start_overlay(self):
        Thread(target=self.render_overlay, args=()).start()
        return self

    def start(self):
        '''Begin handling frame stream in a separate thread'''
        Thread(target=self.flush, args=()).start()
        return self

    def flush(self):
        # looping until self.stopped flag is flipped
        # for now, grab the first frame in buffer, then empty buffer
        for f in self.stream:
            self.frame = f.array
            self.data_container.truncate(0)

            if self.stopped:
                self.stream.close()
                self.data_container.close()
                self.camera.close()                                         ###
                return

    def read(self):
        return self.frame

    def stop(self):
        self.stopped = True
"""
