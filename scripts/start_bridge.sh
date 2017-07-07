#!/bin/sh

#############################################################################
# Front end script to launch 2 selected partners.  The directory structure
# is defined as base_dir -> ipsc_bridge -> dmrlink
#                                   -> hblink
#                    -> analog_bridge
# This script is in base_dir, all others are relative.  If this is not how
# you installed the components, then adjust the code below to your liking.
#############################################################################

cd "$(dirname "$0")"
BASE_DIR=`pwd`
DMR_ROOT="$BASE_DIR/ipsc_bridge"
IPSC_ROOT="$DMR_ROOT/dmrlink"
HB_ROOT="$DMR_ROOT/hblink"
AUDIO_ROOT="$BASE_DIR/DMRGateway/analog_bridge"

RETURN_OK=0
RETURN_FAIL=1

function usage {
    echo $(basename $0) "[IPSC|HB|ANALOG] | [IPSC|HB|ANALOG] | [RANDOM|DEFAULT]"
    echo "If no arguments are supplied, this script runs in interactive mode"
    echo "Use RANDOM to assign random complementry ports to the partners"
    echo "Use DEFAULT to set the partners to our default port assignments"
    exit 1
}

function get_port {
    FOO=`grep $2 "$1" | awk '{print $3}'`
    if [ "$FOO"xxx == "xxx" ]; then
        >&2 echo "Port error, symbol" $2 "was not found in file" $1
        sleep 1000
    fi
    echo $FOO
}

function testPorts {
    if [ ${!1} -ne ${!2} ]; then
        echo "Input/Output ports do not match $1 != $2"
        exit
    fi
}

function launchApp {
    if [ "$(uname)" == "Darwin" ]; then
        osascript -e 'tell application "Terminal" to do script "cd \"'"$1"'\";'"$2"'"' &
    else
        cd "$1"
        $2 &
    fi
}

function toUpper {
    echo "$1" | tr '[:lower:]' '[:upper:]'
}

function random {
    FLOOR=$1
    number=0   #initialize
    while [ "$number" -le $FLOOR ]
    do
        number=$RANDOM
    done
    echo $number
}

function editConfig {
    echo "$1"
    case $1 in
        ANALOG)
            sed -i "" 's/fromDMRPort = .*/fromDMRPort = '$2'/g' "${AUDIO_ROOT}/Analog_Bridge.ini"
            sed -i "" 's/toDMRPort = .*/toDMRPort = '$3'/g' "${AUDIO_ROOT}/Analog_Bridge.ini"
        ;;
        IPSC)
            sed -i "" 's/fromGatewayPort = .*/fromGatewayPort = '$2'/g' "${IPSC_ROOT}/IPSC_Bridge.cfg"
            sed -i "" 's/toGatewayPort = .*/toGatewayPort = '$3'/g' "${IPSC_ROOT}/IPSC_Bridge.cfg"
        ;;
        HB)
            sed -i "" 's/fromGatewayPort = .*/fromGatewayPort = '$2'/g' "${HB_ROOT}/HB_Bridge.cfg"
            sed -i "" 's/toGatewayPort = .*/toGatewayPort = '$3'/g' "${HB_ROOT}/HB_Bridge.cfg"
        ;;
    esac
}

function assignSpecificPorts {
    partner1=$1
    partner2=$2
    port1=$3
    port2=$4

    editConfig $partner1 $port1 $port2
    editConfig $partner2 $port2 $port1
}

function assignRandomPorts {
    partner1=$1
    partner2=$2
    port1=`random 1024`
    port2=`random 1024`

    editConfig $partner1 $port1 $port2
    editConfig $partner2 $port2 $port1
}

function selectPartners {
    declare PARTNERS="{\"HB <--> IPSC\", \"HB <--> Analog\", \"IPSC <--> Analog\"}"
    if [ "$(uname)" == "Darwin" ]; then
    osascript <<EOD
        set partners to $PARTNERS
        set selectedPartners to {choose from list partners with title "Partners" with prompt "Choose partners"}
        return selectedPartners
EOD
    else
python <<EOD
from Tkinter import *

master = Tk()
master.title("Start Bridge")

listbox = Listbox(master)
listbox.pack()

but_frame = Frame(master)
Button(but_frame, text='OK',command=lambda: close(listbox)).pack(side=LEFT)
Button(but_frame, text='Cancel',command=lambda: close(None), bg='red', fg='white').pack(side=LEFT) 
but_frame.pack(side=BOTTOM)

def close(widget):
    if widget != None:
        selection=widget.curselection()
        value = widget.get(selection[0])
        print(value)
    exit()

def OnDouble(event):
    close(event.widget)
    
for item in ["HB <--> IPSC", "HB <--> Analog", "IPSC <--> Analog"]:
    listbox.insert(END, item)
listbox.bind("<Double-Button-1>", OnDouble)
listbox.selection_set(0)

mainloop()
EOD
    fi
}

if [ "$#" -eq 3 ] && [ $3 == RANDOM ]; then
    echo "Assign Random Ports for $1 and $2"
    assignRandomPorts $1 $2
fi

if [ "$#" -eq 3 ] && [ $3 == DEFAULT ]; then
    echo "Assign default Ports for $1 and $2"
    assignSpecificPorts $1 $2 31003 31000
fi

ANALOG_IN=`get_port "${AUDIO_ROOT}/Analog_Bridge.ini" fromDMRPort`
ANALOG_OUT=`get_port "${AUDIO_ROOT}/Analog_Bridge.ini" toDMRPort`
IPSC_IN=`get_port "${IPSC_ROOT}/IPSC_Bridge.cfg" fromGatewayPort`
IPSC_OUT=`get_port "${IPSC_ROOT}/IPSC_Bridge.cfg" toGatewayPort`
HB_IN=`get_port "${HB_ROOT}/HB_Bridge.cfg" fromGatewayPort`
HB_OUT=`get_port "${HB_ROOT}/HB_Bridge.cfg" toGatewayPort`

if [ "$#" -eq 0 ]; then
    partner=`selectPartners`
    case $partner in
        "HB <--> IPSC")
            $BASE_DIR/start_bridge.sh IPSC HB DEFAULT
        ;;
        "HB <--> Analog")
            $BASE_DIR/start_bridge.sh HB ANALOG DEFAULT
        ;;
        "IPSC <--> Analog")
            $BASE_DIR/start_bridge.sh IPSC ANALOG DEFAULT
        ;;
    esac
    exit
fi

echo "Testing for complementry port assignments in $1 and $2"
testPorts `toUpper "$1"_IN` `toUpper "$2"_OUT`
testPorts `toUpper "$1"_OUT` `toUpper "$2"_IN`
echo "Ports passed"

for i in "$@"
do
    case `toUpper $i` in
        -h|--help|"-?")
            usage
            shift
        ;;
        IPSC)
            launchApp "$IPSC_ROOT" "python IPSC_Bridge.py"
        ;;
        HB)
            launchApp "$HB_ROOT" "python HB_Bridge.py"
        ;;
        ANALOG)
            launchApp "$AUDIO_ROOT" "./Analog_Bridge"
        ;;
        RANDOM)
            echo "Using random ports"
        ;;
        *)
            echo "Invalid argument"
            usage
    esac
done

echo "Running"
