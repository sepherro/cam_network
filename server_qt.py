__author__ = 'Amin'

from twisted.internet.endpoints import TCP4ServerEndpoint

from PyQt4.QtCore import *
from PyQt4.QtGui import *

import sys
import time

from pyqtgraph.Qt import QtGui, QtCore

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    _fromUtf8 = lambda s: s

import numpy as np

import cv2

from VSNServer import VSNServerFactory
from VSNPacket import VSNPacketToClient
from VSNPacket import IMAGE_TYPES
from VSNGraph import VSNGraphController


class CircleWidget(QWidget):
    def __init__(self, parent=None):
        super(CircleWidget, self).__init__(parent)
        self.nframe = 0
        self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def minimumSizeHint(self):
        return QSize(50, 50)

    def sizeHint(self):
        return QSize(180, 180)

    def next(self):
        self.nframe += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.translate(self.width() / 2, self.height() / 2)

        for diameter in range(0, 64, 9):
            delta = abs((self.nframe % 64) - diameter / 2)
            alpha = 255 - (delta * delta) / 4 - diameter
            if alpha > 0:
                painter.setPen(QPen(QColor(0, diameter / 2, 127, alpha), 3))
                painter.drawEllipse(QRectF(
                    -diameter / 2.0,
                    -diameter / 2.0,
                    diameter,
                    diameter))


class LogWidget(QTextBrowser):
    def __init__(self, parent=None):
        super(LogWidget, self).__init__(parent)
        palette = QPalette()
        palette.setColor(QPalette.Base, QColor("#ddddfd"))
        self.setPalette(palette)

dependency_table = {'picam01': [0.0, 0.5, 0.5, 0.5],
                    'picam02': [0.5, 0.0, 0.5, 0.5],
                    'picam03': [0.5, 0.5, 0.0, 0.5],
                    'picam04': [0.5, 0.5, 0.5, 0.0]
                    }

# TODO:
# gather data about state of each camera - how long it was in low-power and how long in high power
# ability to change gain and sample time on the fly
# server controller - separate class
# ability to choose (from GUI) if image should be send or not)

class SampleGUIServerWindow(QMainWindow):
    def __init__(self, reactor, parent=None):
        super(SampleGUIServerWindow, self).__init__(parent)
        self.reactor = reactor

        self.create_main_frame()
        self.create_server()
        self.create_timer()

        # ## global variables ###
        # current neighbouring nodes activation level
        self._activation_neighbours = np.zeros((4, 1))

        #self._graphs = [VSNGraph(i) for i in xrange(4)]

        self._graphsController = VSNGraphController()
        self._graphsController.create_graph_window()
        self._graphsController.add_new_graph()
        self._graphsController.add_new_graph()
        self._graphsController.add_new_graph()
        self._graphsController.add_new_graph()

        timer_plot = QtCore.QTimer(self)
        timer_plot.timeout.connect(self._graphsController.update_graphs)
        timer_plot.start(200)

    def create_main_frame(self):
        self.circle_widget = CircleWidget()
        self.doit_button = QPushButton('Do it!')
        self.doit_button.clicked.connect(self.on_doit)
        self.log_widget = LogWidget()

        self.label = QtGui.QLabel()

        myPixmap = QtGui.QPixmap(_fromUtf8('Crazy-Cat.jpg'))
        myScaledPixmap = myPixmap.scaled(self.label.size(), Qt.KeepAspectRatio)
        self.label.setPixmap(myScaledPixmap)

        self._label_picam1 = QtGui.QLabel("Picam01")
        self._label_picam2 = QtGui.QLabel("Picam02")
        self._label_activations_neighbours = QtGui.QLabel("activations_neighbours")

        hbox = QHBoxLayout()
        hbox.addWidget(self.log_widget)
        hbox.addWidget(self.label)

        vbox = QtGui.QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.circle_widget)
        vbox.addWidget(self.doit_button)
        vbox.addWidget(self._label_picam1)
        vbox.addWidget(self._label_picam2)
        vbox.addWidget(self._label_activations_neighbours)

        main_frame = QWidget()
        main_frame.setLayout(vbox)

        self.setCentralWidget(main_frame)

    def create_timer(self):
        self.circle_timer = QTimer(self)
        self.circle_timer.timeout.connect(self.circle_widget.next)
        self.circle_timer.start(25)

    def create_server(self):
        self.server = VSNServerFactory(
                        self.on_client_connection_made,
                        self.on_client_connection_lost,
                        self.on_client_data_received,
                        self.on_client_image_received
        )
        self.log('Connecting...')
        # When the connection is made, self.client calls the on_client_connect
        # callback.
        #
        endpoint = TCP4ServerEndpoint(reactor, TCP_PORT)
        endpoint.listen(self.server)

    def on_doit(self):
        packet_to_client = VSNPacketToClient()
        packet_to_client.set(4.5, IMAGE_TYPES.background, False)
        self.server.send_packet_to_all_clients(packet_to_client)

        # test for adding new row to the graph window
        self._graphsController.add_new_graph()

    def on_client_connection_made(self):
        self.log('Connected to server. Sending...')
        #self.server.send_data([0, 10, 45, 99])

    def on_client_connection_lost(self):
        # reason is a twisted.python.failure.Failure  object
        self.log('Connection failed')

    def on_client_data_received(self, packet, client):
        #self.log('Client reply: %s' % msg)
        self.log('Received data')

        camera_number = packet.camera_number
        white_pixels = packet.white_pixels
        activation_level = packet.activation_level

        self.service_client(camera_number, white_pixels, activation_level, client)

    def on_client_image_received(self, image_as_string):
        data = np.fromstring(image_as_string, dtype='uint8')
        #decode jpg image to numpy array and display
        decimg = cv2.imdecode(data, cv2.CV_LOAD_IMAGE_GRAYSCALE)

        qi = QtGui.QImage(decimg, 320, 240, QtGui.QImage.Format_Indexed8)
        self.label.setPixmap(QtGui.QPixmap.fromImage(qi))

    def service_client(self, camera_number, white_pixels, activation_level, client):
        # TODO - this should be corrected
        node_index = camera_number-1
        node_name = "picam" + str(camera_number).zfill(2)

        self._activation_neighbours[node_index] = 0
        for idx in xrange(0, 3):
            self._activation_neighbours[node_index] += \
                dependency_table[node_name][idx] * self._graphsController._percentages[idx]
                #dependency_table[node_name][idx] * self._graphsController._activations[idx]
        packet_to_send = VSNPacketToClient()
        packet_to_send.set(
            self._activation_neighbours[node_index],
            IMAGE_TYPES.background,
            False
        )
        client.send_packet(packet_to_send)

        self._graphsController.set_new_values(
            node_index,
            activation_level + self._activation_neighbours[node_index],
            white_pixels
        )

        info = "Camera: " + str(camera_number) + ", " \
               "{:.2f}".format(activation_level) + ", " + \
               "{:.2f}".format(white_pixels) + ", " + \
               ""
        if node_index == 0:
            self._label_picam1.setText(info)
        elif node_index == 1:
            self._label_picam2.setText(info)

        activations_neighbours_text = str(self._activation_neighbours)
        self._label_activations_neighbours.setText(activations_neighbours_text)

    def log(self, msg):
        timestamp = '[%010.3f]' % time.clock()
        self.log_widget.append(timestamp + ' ' + str(msg))

    def closeEvent(self, e):
        self.reactor.stop()


#-------------------------------------------------------------------------------

TCP_PORT = 50001

if __name__ == "__main__":
    app = QApplication(sys.argv)

    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()

    from twisted.internet import reactor
    main_window = SampleGUIServerWindow(reactor)
    main_window.show()

    reactor.run()
