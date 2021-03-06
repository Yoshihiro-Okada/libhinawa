#!/usr/bin/env python2

import sys

# PyQt4 is not released for python3, sigh...
# The combination of Python2 and Qt4 has a disadvantage for QString.
# This forces interpretor to handle QString as usual unicode string.
import sip
sip.setapi('QString', 2)
from PyQt4.QtCore import Qt
from PyQt4.QtGui import QApplication, QWidget, QHBoxLayout, QVBoxLayout
from PyQt4.QtGui import QToolButton, QGroupBox, QLineEdit, QLabel

# Hinawa-1.0 gir
from gi.repository import Hinawa

# to handle UNIX signal
from gi.repository import GLib
import signal

from array import array

import glob

# helper function
def get_array():
    # The width with 'L' parameter is depending on environment.
    arr = array('L')
    if arr.itemsize is not 4:
        arr = array('I')
    return arr

# query sound devices and get FireWire sound unit
for fullpath in glob.glob('/dev/snd/hw*'):
    try:
        snd_unit = Hinawa.SndDice()
        snd_unit.open(fullpath)
    except:
        del snd_unit
        try:
            snd_unit = Hinawa.SndEfw()
            snd_unit.open(fullpath)
        except:
            del snd_unit
            try:
                snd_unit = Hinawa.SndUnit()
                snd_unit.open(fullpath)
            except:
                del snd_unit
                continue
    break

if 'snd_unit' not in locals():
    print('No sound FireWire devices found.')
    sys.exit()

# create sound unit
def handle_lock_status(snd_unit, status):
    if status:
        print("streaming is locked.");
    else:
        print("streaming is unlocked.");
def handle_disconnected(snd_unit):
    print('disconnected')
    app.main_quit()
print('Sound device info:')
print(' type:\t{0}'.format(snd_unit.get_property("type")))
print(' card:\t{0}'.format(snd_unit.get_property("card")))
print(' device:\t{0}'.format(snd_unit.get_property("device")))
print(' GUID:\t{0:016x}'.format(snd_unit.get_property("guid")))
snd_unit.connect("lock-status", handle_lock_status)
snd_unit.connect("disconnected", handle_disconnected)

# create FireWire unit
def handle_bus_update(snd_unit):
	print(snd_unit.get_property('generation'))
snd_unit.connect("bus-update", handle_bus_update)

# start listening
try:
    snd_unit.listen()
except Exception as e:
    print(e)
    sys.exit()
print(" listening:\t{0}".format(snd_unit.get_property('listening')))

# create firewire responder
resp = Hinawa.FwResp()
def handle_request(resp, tcode, req_frame):
    print('Requested with tcode {0}:'.format(tcode))
    for i in range(len(req_frame)):
        print(' [{0:02d}]: 0x{1:08x}'.format(i, req_frame[i]))
    # Return no data for the response frame
    return None
try:
    resp.register(snd_unit, 0xfffff0000d00, 0x100)
    resp.connect('requested', handle_request)
except Exception as e:
    print(e)
    sys.exit()

# create firewire requester
req = Hinawa.FwReq()

# Fireworks/BeBoB/OXFW supports FCP and some AV/C commands
if snd_unit.get_property('type') is not 1:
    request = bytearray(8)
    request[0] = 0x01
    request[1] = 0xff
    request[2] = 0x19
    request[3] = 0x00
    request[4] = 0xff
    request[5] = 0xff
    request[6] = 0xff
    request[7] = 0xff

    try:
        response = snd_unit.fcp_transact(request)
    except Exception as e:
        print(e)
        sys.exit()
    print('FCP Response:')
    for i in range(len(response)):
        print(' [{0:02d}]: 0x{1:02x}'.format(i, ord(response[i])))

# Echo Fireworks Transaction
if snd_unit.get_property("type") is 2:
    args = get_array()
    args.append(5)
    try:
        params = snd_unit.transact(6, 1, args)
    except Exception as e:
        print(e)
        sys.exit()
    print('Echo Fireworks Transaction Response:')
    for i in range(len(params)):
        print(" [{0:02d}]: {1:08x}".format(i, params[i]))

# Dice notification
def handle_notification(self, message):
    print("Dice Notification: {0:08x}".format(message))
if snd_unit.get_property('type') is 1:
    snd_unit.connect('notified', handle_notification)
    args = get_array()
    args.append(0x0000030c)
    try:
        # The address of clock in Impact Twin
        snd_unit.transact(0xffffe0000074, args, 0x00000020)
    except Exception as e:
        print(e)
        sys.exit()

# GUI
class Sample(QWidget):
    def __init__(self, parent=None):
        super(Sample, self).__init__(parent)

        self.setWindowTitle("Hinawa-1.0 gir sample with PyQt4")

        layout = QVBoxLayout()
        self.setLayout(layout)

        top_grp = QGroupBox(self)
        top_layout = QHBoxLayout()
        top_grp.setLayout(top_layout)
        layout.addWidget(top_grp)

        buttom_grp = QGroupBox(self)
        buttom_layout = QHBoxLayout()
        buttom_grp.setLayout(buttom_layout)
        layout.addWidget(buttom_grp)

        button = QToolButton(top_grp)
        button.setText('transact')
        top_layout.addWidget(button)
        button.clicked.connect(self.transact)

        close = QToolButton(top_grp)
        close.setText('close')
        top_layout.addWidget(close)
        close.clicked.connect(app.quit)

        self.addr = QLineEdit(buttom_grp)
        self.addr.setText('0xfffff0000980')
        buttom_layout.addWidget(self.addr)

        self.value = QLabel(buttom_grp)
        self.value.setText('00000000')
        buttom_layout.addWidget(self.value)

        # handle unix signal
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, \
                             self.handle_unix_signal, None)

    def handle_unix_signal(self, user_data):
        app.quit()

    def transact(self, val):
        try:
            addr = int(self.addr.text(), 16)
            val = req.read(snd_unit, addr, 1)
        except Exception as e:
            print(e)
            return

        self.value.setText('0x{0:08x}'.format(val[0]))
        print(self.value.text())

app = QApplication(sys.argv)
sample = Sample()

sample.show()
app.exec_()

del app
del sample
print('delete window object')

snd_unit.unlisten()
del snd_unit
print('delete snd_unit object')

resp.unregister()
del resp
print('delete fw_resp object')

del req
print('delete fw_req object')

sys.exit()
