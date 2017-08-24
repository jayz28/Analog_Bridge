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

import sys
import socket

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.internet import task

UDP_PORT = 2460
ip_address = "127.0.0.1"

DV3000_TYPE_CONTROL     = 0x00
DV3000_TYPE_AMBE        = 0x01
DV3000_TYPE_AUDIO       = 0x02

TYPE_CONTROL_VERSION    = 0x31
TYPE_CONTROL_RESET      = 0x33
DV3000_CONTROL_RATET    = 0x09
DV3000_CONTROL_RATEP    = 0x0A
DV3000_CONTROL_PRODID   = 0x30
DV3000_CONTROL_READY    = 0x39

_sock = 0
DEBUG = False

class AMBEServer(DatagramProtocol):
    def datagramReceived(self, _data, (_host, _port)):
        if ord(_data[0]) == 0x61:
            _packetLen = int(ord(_data[1]) * 256) + ord(_data[2])  # Grab the packet length
            if len(_data) == (_packetLen+4):
                if ord(_data[3]) == DV3000_TYPE_CONTROL:
                    self.processControl(_data, (_host, _port))
                elif ord(_data[3]) == DV3000_TYPE_AMBE:
                    self.processAmbe(_data, (_host, _port))
                elif ord(_data[3]) == DV3000_TYPE_AUDIO:
                    self.processAudio(_data, (_host, _port))
            else:
                print 'Data length does not match AMBE length value'
        else:
            print 'AMBE header byte not found', ord(_data[0])
    def ambeSend( self, cmd, addr ):
        global _sock
        if DEBUG:
            print ''.join('{:02x} '.format((x)) for x in cmd)
        return _sock.sendto(cmd, addr)
    def processControl(self, _data, addr):
        print 'processControl'
        if ord(_data[4]) == TYPE_CONTROL_RESET:
            self.ambeSend( bytearray.fromhex("61 00 01 00 39"), addr )
        elif ord(_data[4]) == DV3000_CONTROL_PRODID:
            self.ambeSend( bytearray.fromhex("61000B0030414d4245333030305200"), addr )
        elif ord(_data[4]) == TYPE_CONTROL_VERSION:
            self.ambeSend( bytearray.fromhex("6100310031563132302e453130302e585858582e433130362e473531342e523030392e42303031303431312e433030323032303800"), addr )
        elif ord(_data[4]) == DV3000_CONTROL_RATEP:
            self.ambeSend( bytearray.fromhex("610002000A00"), addr )            
        else:
            print 'unknown control command', ord(_data[4])
        pass
    def processAmbe(self, _data, addr):
        print 'processAmbe'
        pcm = bytearray.fromhex("6101420200A0") + bytearray(320)
        self.ambeSend( pcm, addr )
        pass
    def processAudio(self, _data, addr):
        print 'processAudio'
        ambe = bytearray.fromhex("61 00 0B 01 01 48 AC AA 40 20 00 44 40 80 80")
        self.ambeSend( ambe, addr )
        pass
    def executeServer( self ):
        global _sock
        _sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        _sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.udp_port = reactor.listenUDP(UDP_PORT, self)


if __name__ == "__main__":


    _sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    _sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _sock.bind(('', UDP_PORT))

    server = AMBEServer()
    while True:
        data, addr = _sock.recvfrom(1024) # buffer size is 1024 bytes
        server.datagramReceived(data,addr)

    server = AMBEServer()
    server.executeServer()
    reactor.run()

