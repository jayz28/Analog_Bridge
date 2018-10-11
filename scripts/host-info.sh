#!/bin/bash
set -o errexit

# N4IRS 03/23/2018

################################################
#                                              #
#         Collect data from the host           #
# The purpose of this script is to figure out  #
# the type of system running. These routines   #
# can be used in other scripts to control      #
# script processing                            #
#                                              #
################################################
#
# Functions must be defined before they are used

# Data sources
# /proc/cpuinfo
# uname
# lsb_release
# /proc/device-tree
# /sys/class/thermal/thermal_zone0/temp
# /sys/firmware/devicetree/base/model?
# add hardware MAC?

function get_pi_version() {
  declare -r REVCODE=$(awk '/Revision/ {print $3}' /proc/cpuinfo)
  declare -rA REVISIONS=(
    [0002]="Model B Rev 1, 256 MB RAM"
    [0003]="Model B Rev 1 ECN0001, 256 MB RAM"
    [0004]="Model B Rev 2, 256 MB RAM"
    [0005]="Model B Rev 2, 256 MB RAM"
    [0006]="Model B Rev 2, 256 MB RAM"
    [0007]="Model A, 256 MB RAM"
    [0008]="Model A, 256 MB RAM"
    [0009]="Model A, 256 MB RAM"
    [000d]="Model B Rev 2, 512 MB RAM"
    [000e]="Model B Rev 2, 512 MB RAM"
    [000f]="Model B Rev 2, 512 MB RAM"
    [0010]="Model B+, 512 MB RAM"
    [0011]="Compute Module (512MB)"
    [0013]="Model B+, 512 MB RAM"
    [900032]="Model B+, 512 MB RAM"
    [0011]="Compute Module, 512 MB RAM"
    [0014]="Compute Module, 512 MB RAM"
    [0012]="Model A+, 256 MB RAM"
    [0015]="Model A+, 256 MB or 512 MB RAM"
    [a01041]="2 Model B v1.1, 1 GB RAM"
    [a21041]="2 Model B v1.1, 1 GB RAM"
    [a22042]="2 Model B v1.2, 1 GB RAM"
    [90092]="Zero v1.2, 512 MB RAM"
    [90093]="Zero v1.3, 512 MB RAM"
    [0x9000C1]="Zero W, 512 MB RAM"
    [a02082]="3 Model B, 1 GB RAM"
    [a22082]="3 Model B, 1 GB RAM"
  )
RPI_REVCODE=${REVCODE}
RPI_REVISION=${REVISIONS[${REVCODE}]}
}

cache_uname() {
    uname_kernel_name="$(uname -s)"
    uname_nodename="$(uname -n)"
    uname_kernel_release="$(uname -r)"
    uname_kernel_version="$(uname -v)"
    uname_machine="$(uname -m)"
    uname_operating_system="$(uname -o)"
}

get_cpuinfo_prop () {
  target_line=$(grep -m1 ^"$1" /proc/cpuinfo || true)
  cpuinfo_prop="${target_line##*: }"
}

command_exists () {
    type "$1" &> /dev/null ;
}

function echo2() {
   if [ -n "$2" ]
   then
      echo "$1" "$2" "$3" | xargs
   fi
}

############## Collect system info ###############################

# Process LSB results if available
if command_exists lsb_release ; then
        lsb_id=$(lsb_release -is)
        lsb_release=$(lsb_release -rs)
        lsb_codename=$(lsb_release -cs)
fi

# Process Device Tree results if available
if [[ -d "/proc/device-tree" && ! -L " /proc/device-tree" ]] ; then
        DEVTREE_MODEL=$(awk '{print $1} {print $2}' /proc/device-tree/model)
        DEVTREE_COMPATABLE=$(awk '{print $1} {print $2}' /proc/device-tree/compatible)
	DEVTREE_SERIAL=$(awk '{print $1} {print $2}' /proc/device-tree/serial-number)
fi

# Process /proc/cpuinfo results
get_cpuinfo_prop "model name" ; CPUINFO_MODEL=$cpuinfo_prop
get_cpuinfo_prop "Hardware" ; CPUINFO_HARDWARE=$cpuinfo_prop
get_cpuinfo_prop "Revision" ; CPUINFO_REVISION=$cpuinfo_prop
get_cpuinfo_prop "Serial" ; CPUINFO_SERIAL=$cpuinfo_prop

# Process uname results
cache_uname

# Process current stats
FREE_MEM=$(free -m | awk 'NR==2{printf "%s MB of %s MB (%.2f%%)\n", $3,$2,$3*100/$2 }')
DISK_USED=$(df -h | awk '$NF=="/"{printf "%d GB of %d GB (%s)\n", $3,$2,$5}')
CPU_LOAD=$(top -bn1 | grep load | awk '{printf "%.2f\n", $(NF-2)}')

if [ -f /sys/class/thermal/thermal_zone0/temp ]
then
        TEMPERATURE=$(awk '{printf("%.1f°F\n",(($1*1.8)/1e3)+32)}' /sys/class/thermal/thermal_zone0/temp)
fi

HOSTNAME=$(hostname)

############## Determine type of system #######################################

# system_type=unknown

# Get Armbian info if available
if [ -f /etc/armbian-release ]
then
        source /etc/armbian-release
        system_type=armbian
	# cat /run/machine.id
fi

# Get TI Debian if info available
if [ -f /boot/SOC.sh ]
then
        source /boot/SOC.sh
        system_type=ti_debian
fi

# Get Raspberry Pi info if available
if [[ $DEVTREE_MODEL =~ .*Raspberry.* ]]
then
        get_pi_version
        system_type=rpi
fi

# Get Intel / AMD info if available
if [ $uname_machine == "x86_64" ] || [ $uname_machine == "i686" ]
then
        system_type=intel-amd
fi

# system_type=unknown
echo ""

####################### Display results #########################

# if [[ $system_type == unknown ]]
# then
        echo "=== $system_type ==="
	echo2 "Raspberry Pi" "$RPI_REVISION" "($RPI_REVCODE)"

        echo2 "Device Tree Model =" "$DEVTREE_MODEL"
        echo2 "Device Tree Compatable =" "$DEVTREE_COMPATABLE"
        echo2 "Device Tree Serial number =" "$DEVTREE_SERIAL"
        echo2 "Node name =" "$uname_nodename"
        echo2 "Host name =" "$HOSTNAME"
        echo2 "Machine =" "$uname_machine"
        # echo ""
        echo2 "CPU Model =" "$CPUINFO_MODEL"
        echo2 "CPU Hardware =" "$CPUINFO_HARDWARE"
        echo2 "CPU Revision =" "$CPUINFO_REVISION"
        echo2 "CPU Serial =" "$CPUINFO_SERIAL"
	# echo ""
        echo2 "BOARD =" "$BOARD"
        echo2 "BOARD_NAME =" "$BOARD_NAME"
        echo2 "BOARDFAMILY =" "$BOARDFAMILY"
        echo2 "VERSION =" "$VERSION"
        echo2 "LINUXFAMILY =" "$LINUXFAMILY"
        echo2 "BRANCH =" "$BRANCH"
        echo2 "ARCH =" "$ARCH"
	# echo ""
        echo2 "format =" "$format"
        echo2 "bootloader_location =" "$bootloader_location"
        echo2 "boot_fstype =" "$boot_fstype"
        echo2 "serial_tty =" "$serial_tty"
        echo2 "usbnet_mem =" "$usbnet_mem"
	# echo ""
        echo2 "Operating system =" "$uname_operating_system"
        echo2 "ID =" "$lsb_id"
        echo2 "Release =" "$lsb_release"
        echo2 "Codename =" "$lsb_codename"
        # echo ""
        echo2 "Kernel-name =" "$uname_kernel_name"
        echo2 "Kernel-release =" "$uname_kernel_release"
        echo2 "Kernel-version =" "$uname_kernel_version"
        # echo ""
        echo2 "Free Memory =" "$FREE_MEM"
        echo2 "Disk Used =" "$DISK_USED"
        echo2 "CPU Load =" "$CPU_LOAD"
	echo2 "Temperature =" "$TEMPERATURE"
# fi

# lshw
# lscpu
# dmidecode
# inxi
# https://github.com/dylanaraps/neofetch/blob/master/neofetch

