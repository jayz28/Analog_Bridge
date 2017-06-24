###############################################################################
#
#   Copyright (C) 2017 Mike Zingman N4IRR
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software Foundation,
#   Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
#
###############################################################################


import serial
import sys
import getopt
import array
import thread
import time
import string
from time import sleep

def ambeSend( port, cmd ):
	return port.write(cmd)

def ambeRecv( port ):
	_val = port.read(1024)
	return len(_val), _val

def ambeValidate( port, cmd, expect, label ):
	print "Testing", label
	_wrote = ambeSend( port, cmd )
	if _wrote != len(cmd):
		print 'Error, tried to write', len(cmd),'and did write',_wrote,'bytes',label
	else:
		_readLen, buffer = ambeRecv(port)
		if _readLen == 0:
			print 'Error, no reply from DV3000.  Command issued was:', label
		else:
			if ord(buffer[0]) != 0x61:
				print 'Errror, DV3000 send back invalid start byte.  Expected 0x61 and got', ord(buffer[0]),label
				print ''.join('{:02x}'.format(ord(x)) for x in buffer)
			else:
				_packetLen = (ord(buffer[1]) * 256) + ord(buffer[2])
				if _readLen < (_packetLen+3):
					print 'Error, read', _readLen,'Bytes and AMBE header says it has',_packetLen,'bytes',label
					print ''.join('{:02x}'.format(ord(x)) for x in buffer)
				else:
					_payload = buffer[5:]
					if len(_payload) > 0:
						for x in range(0,len(expect)):
							if ord(_payload[x]) != expect[x]:
								print "In test", label
								print 'Error, did not get expected value from DV3000.  Got:',_payload,'expected',expect
								print ''.join('{:02x}'.format(ord(x)) for x in _payload)
								return None
					print 'Test result: Success ('+''.join('{:02x}'.format(ord(x)) for x in buffer)+")"
					return _payload
	return None


def main(argv):
	SERIAL_BAUD=230400
	serialport = "/dev/ttyAMA0"
	try:
		opts, args = getopt.getopt(argv,"hns:",["serial="])
	except getopt.GetoptError:
		print 'AMBEtest4.py -s <serial port>'
		print 'AMBEtest4.py -n -s <serial port> (for ThumbDV Model A)'
		sys.exit(2)
	for opt, arg in opts:
		if opt == '-h':
			print 'AMBEtest4.py -s <serial port>'
			sys.exit()
		elif opt in ("-s", "--serial"):
			serialport = arg
		elif opt == "-n":
			SERIAL_BAUD=460800

	print 'Setting serial port'
	port = serial.Serial(serialport, baudrate=SERIAL_BAUD, timeout=1.0, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, xonxoff=False, rtscts=False, dsrdtr=False)

	port.flushInput()
	port.flushOutput()

	print 'Serial port parameters:'
	print 'Port name:\t', serialport
	print 'Baudrate:\t', str(port.baudrate)
	print 'Byte size:\t', port.bytesize
	print 'Parity:\t\t', port.parity
	print 'Stop bits:\t', port.stopbits
	print 'Xon Xoff:\t', port.xonxoff
	print 'RTS/CTS:\t', port.rtscts
	print 'DST/DTR:\t', port.dsrdtr

	time.sleep(0.02)
	rcv = port.read(10)
	sys.stdout.write(rcv)
	print '*********************'

	reset = bytearray.fromhex("61 00 01 00 33");
	setDstar = bytearray.fromhex("61 00 0c 00 0a 01 30 07 63 40 00 00 00 00 00 00 48");
	getProdId = bytearray.fromhex("61 00 01 00 30");
	getVersion = bytearray.fromhex("61 00 01 00 31");

	ambeValidate(port, reset, bytearray.fromhex("39"), 'Reset DV3000')
	ambeValidate(port, getProdId, bytearray.fromhex("414d4245333030305200"), 'Get Product ID')
	ambeValidate(port, getVersion, bytearray.fromhex("563132302e453130302e585858582e433130362e473531342e523030392e42303031303431312e433030323032303800"), 'Get Version')
	ambeValidate(port, setDstar, bytearray.fromhex("00"), 'Set DSTAR Mode')

	setDMR = bytearray.fromhex("61 00 0D 00 0A 04 31 07 54 24 00 00 00 00 00 6F 48")
	ambeValidate(port, reset, bytearray.fromhex("39"), 'Reset DV3000')
	ambeValidate(port, setDMR, bytearray.fromhex("00"), 'Set DMR Mode')

	for _ in range(0,10):
		silence = bytearray.fromhex("AC AA 40 20 00 44 40 80 80")
		DMRAmbe = bytearray.fromhex("61 00 0B 01 01 48") + silence
		_payload = ambeValidate(port, DMRAmbe, bytearray.fromhex("a0"), 'Decode AMBE')
		if _payload != None:
			DMRPCM = bytearray.fromhex("61 01 42 02 00 A0") + _payload
			expect = bytearray.fromhex("48954be6500310b00777")
			ambeValidate(port, DMRPCM, '', 'Encode PCM')
		sleep(1)


if __name__ == "__main__":
	main(sys.argv[1:])

