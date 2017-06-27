#!/bin/sh

IP_ADDRESS="127.0.0.1"
IP_PORT=31003

REPEATER_ID=3113043
DMR_ID=311317
SLOT=2
CC=1


TAG_TG_TUNE=3
TAG_SET_INFO=8

function setTG() {
    printf "setTG tg=$1\n" $1
python - <<END
#!/usr/bin/env python
import sys, socket, struct

_sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
_gateway = ("$IP_ADDRESS", $IP_PORT)

def send_tlv(_tag, _value):
	_tlv = struct.pack("bb", _tag, len(_value)) + _value
	_sock.sendto(_tlv, _gateway)

send_tlv($TAG_TG_TUNE, '='+str("$1"))    # start transmission
END
}

function setDMRInfo() {
    printf "setDMRInfo: src_id=%d repeater_id=%d dest_id=%d slot=%d cc=%d\n" $1 $2 $3 $4 $5
python - <<END
#!/usr/bin/env python
import sys, socket, struct

_sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
_gateway = ("$IP_ADDRESS", $IP_PORT)

def hex_str_3(_int_id):
    try:
        return format(_int_id,'x').rjust(6,'0').decode('hex')
    except TypeError:
        raise

# Create a 4 byte hex string from an integer
def hex_str_4(_int_id):
    try:
        return format(_int_id,'x').rjust(8,'0').decode('hex')
    except TypeError:
        raise

def send_tlv(_tag, _value):
	_tlv = struct.pack("bb", _tag, len(_value)) + _value
	_sock.sendto(_tlv, _gateway)

_src_id = hex_str_3($1)
_repeater_id = 	hex_str_4($2)
_dst_id = hex_str_3($3)
_slot = $4
_cc = $5

metadata = _src_id[0:3] + _repeater_id[0:4] + _dst_id[0:3] + struct.pack("b", _slot) + struct.pack("b", _cc)
send_tlv($TAG_SET_INFO, metadata)    # start transmission
END
}

if [ "$#" -eq 0 ]; then
    TG=3100
else
    TG=$1
fi

setDMRInfo $REPEATER_ID $DMR_ID $TG $SLOT $CC
setTG $TG

