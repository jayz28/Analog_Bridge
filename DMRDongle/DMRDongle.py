#!/usr/bin/python
###################################################################################
# Copyright (C) 2014, 2015, 2016 N4IRR
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND ISC DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS.  IN NO EVENT SHALL ISC BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
# OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.
###################################################################################

from Tkinter import *
import ttk
from time import time, sleep, clock, localtime, strftime
from random import randint
import tkMessageBox
import socket
import struct
import thread
import shlex
import ConfigParser, traceback

###################################################################################
# Manage a popup dialog for on the fly TGs
###################################################################################
class MyDialog:
    
    def __init__(self, parent):
        
        top = self.top = Toplevel(parent)
        
        Label(top, text="Talk Group").pack()
        
        self.e = Entry(top)
        self.e.pack(padx=5)
        
        b = Button(top, text="OK", command=self.ok)
        b.pack(pady=5)
    
    def ok(self):
        
        print "value is", self.e.get()
        item = self.e.get()
        if len(item):
            if "," not in item:
                item = item + "," + item
            listbox.insert(END, item)
        self.top.destroy()


###################################################################################
# Main socket listener for async events from Analog_Bridge or xx_Bridge.py
###################################################################################
def launchUDP():
    global ptt
    global myCall
    print("Starting thread")
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Bind the socket to the port
    server_address = ('', 34003)
    sock.bind(server_address)
    while True:
        data, address = sock.recvfrom(4096)
        if data:
            print(data)
            args = shlex.split(data)
            if args[0] == 'reply':
                if args[1] == 'vox':
                    v = 1 if args[2] == 'true' else 0
                    voxEnable.set(v)
                elif args[1] == 'vox_threshold':
                    voxThreshold.set(int(args[2]))
                elif args[1] == 'vox_delay':
                    voxDelay.set(int(args[2]))
                elif args[1] == 'ptt':
                    ptt = True if args[2] == 'true' else False
                    showPTTState(1)
                elif args[1] == 'log':
                    logList.see(logList.insert('', 'end', None, values=(args[2], args[3], args[4], args[5], args[6], args[7], args[8])))
                    currentTxValue.set(myCall)
                elif args[1] == 'log2':
                    currentTxValue.set('{} -> {}'.format(args[2], args[3]))
                elif args[1] == 'dmr_info':
                    master.set(args[2])
                    repeaterID.set(int(args[3]))
                    subscriberID.set(int(args[4]))
                    myCall = args[5]
                    currentTxValue.set(myCall)
                    pass
                else:
                    print("Unknown reply: {}".format(args))
        sleep(1)

###################################################################################
# Catch and display any socket errors
###################################################################################
def socketFailure():
    connectedMsg.set( "Connection failure" )
    print("Socket failure")

###################################################################################
# Send command to xx_Bridge.py
###################################################################################
def sendRemoteControlCommand( cmd ):
    try:
        # Use TLV to send command.  GUI will use tag 0x05  for now
        host = ipAddress.get()
        _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cmd = struct.pack("BB", 0x05, len(cmd))[0:2] + cmd
        _sock.sendto(cmd, (host, 31003))
        _sock.close()
    except:
        socketFailure()

###################################################################################
# Send command to DMRGateway
###################################################################################
def sendToGateway( cmd ):
    try:
        host = ipAddress.get()
        _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _sock.sendto(cmd, (host, 34002))
        _sock.close()
    except:
        socketFailure()

###################################################################################
# xx_Bridge command: section
###################################################################################
def setRemoteNetwork( netName ):
    sendRemoteControlCommand("section=" + netName)

###################################################################################
#
###################################################################################
def setRemoteTG( tg ):
    
    items = map(int, listbox.curselection())
    if len(items) > 1:
        tgs="tgs="
        comma = ""
        for atg in items:
            foo = listbox.get(atg)
            tgs = tgs + comma + foo.split(',')[1]
            comma = ","
        sendRemoteControlCommand(tgs)
        sendRemoteControlCommand("txTg=0")
        connectedMsg.set( "Connected to ")
        transmitButton.configure(state='disabled')
    else :
        sendRemoteControlCommand("tgs=" + str(tg))
        sendRemoteControlCommand("txTg=" + str(tg))
    setDMRInfo()

###################################################################################
#
###################################################################################
def setRemoteTS( ts ):
    sendRemoteControlCommand("txTs=" + str(ts))

###################################################################################
#
###################################################################################
def setDMRID( id ):
    sendRemoteControlCommand("gateway_dmr_id=" + str(id))

###################################################################################
#
###################################################################################
def setPeerID( id ):
    sendRemoteControlCommand("gateway_peer_id=" + str(id))

###################################################################################
#
###################################################################################
def setDMRCall( call ):
    sendRemoteControlCommand("gateway_call=" + call)

def setDMRInfo():
    sendToGateway("set info " + str(subscriberID.get()) + ',' + str(repeaterID.get()) + ',' + str(getCurrentTG()) + ',' + str(slot.get()) + ',x')

###################################################################################
#
###################################################################################
def setVoxData():
    v = "true" if voxEnable.get() > 0 else "false"
    sendToGateway("set vox " + v)
    sendToGateway("set vox_threshold " + str(voxThreshold.get()))
    sendToGateway("set vox_delay " + str(voxDelay.get()))

###################################################################################
#
###################################################################################
def getVoxData():
    sendToGateway("get vox")
    sendToGateway("get vox_threshold ")
    sendToGateway("get vox_delay ")

###################################################################################
#
###################################################################################
def setAudioData():
    dm = "true" if dongleMode.get() > 0 else "false"
    sendToGateway("set dongle_mode " + dm)
    sendToGateway("set sp_level " + str(spVol.get()))
    sendToGateway("set mic_level " + str(micVol.get()))

###################################################################################
#
###################################################################################
def getCurrentTG():
    items = map(int, listbox.curselection())
    foo = listbox.get(items[0])
    tg = int(foo.split(',')[1])
    return tg

###################################################################################
#
###################################################################################
def getCurrentTGName():
    items = map(int, listbox.curselection())
    foo = listbox.get(items[0])
    tg = foo.split(',')[0]
    return tg

###################################################################################
# Connect to a specific set of TS/TG values
###################################################################################
def connect():
    tg = getCurrentTG()
    connectedMsg.set( "Connected to " + str(tg))
    transmitButton.configure(state='normal')
    
    setRemoteNetwork(master.get())
    setRemoteTG(tg)
    setRemoteTS(slot.get())

###################################################################################
# Mute all TS/TGs
###################################################################################
def disconnect():
    connectedMsg.set( "Connected to ")
    setRemoteTG(0)
    transmitButton.configure(state='disabled')

###################################################################################
#
###################################################################################
def start():
    setDMRID(subscriberID.get())
    getVoxData()

###################################################################################
# Combined command to get all values from servers and display them on UI
###################################################################################
def getValuesFromServer():
    #   ipAddress.set("127.0.0.1")
    #   loopback.set(1)

    # get values from Analog_Bridge (repeater ID, Sub ID, master, tg, slot)
    ### Old Command ### sendRemoteControlCommand('get_info')
    sendToGateway('get info')
    #   currentTxValue.set(mycall)          #Subscriber  call
    #    master.set(servers[0])              #DMR Master
    #   repeaterID.set(12345)              #DMR Peer ID
    #   subscriberID.set(54321)           #DMR Subscriber radio ID
    slot.set(2)                         #current slot
    listbox.selection_set(0)            #current TG
    connectedMsg.set("Connected to")    #current TG
    
    # get values from Analog_Bridge (vox enable, delay and threshold) (not yet: sp level, mic level, audio devices)
    getVoxData()                        #vox enable, delay and threshold
    dongleMode.set(1)                   #dongle mode enable
    micVol.set(50)                      #microphone level
    spVol.set(50)                       #speaker level

###################################################################################
# Update server data state to match GUI values
###################################################################################
def sendValuesToServer():
    # send values to Analog_Bridge
    setDMRInfo()
    # tg = getCurrentTG()
    # setRemoteNetwork(master.get())      #DMR Master
    # setRemoteTG(tg)                     #DMR TG
    # setRemoteTS(slot.get())             #DMR slot
    # setDMRID(subscriberID.get())        #DMR Subscriber ID
    # setDMRCall(myCall)                  #Subscriber call
    # setPeerID(repeaterID.get())         #DMR Peer ID

    # send values to 
    setVoxData()                        #vox enable, delay and threshold
    setAudioData()                      #sp level, mic level, dongle mode

###################################################################################
# Toggle PTT and display new state
###################################################################################
def transmit():
    global ptt
    
    sendToGateway("set ptt toggle")
    ptt = not ptt
    showPTTState(0)

###################################################################################
# Update UI with PTT state.
###################################################################################
def showPTTState(flag):
    global _startTime
    if ptt:
        transmitButton.configure(highlightbackground='red')
        _startTime = time()
        currentTxValue.set('{} -> {}'.format(myCall, getCurrentTG()))
    else:
        transmitButton.configure(highlightbackground='white')
        if flag == 1:
            _date = strftime("%m/%d/%y", localtime(time()))
            _time = strftime("%H:%M:%S", localtime(time()))
            _duration = '{:.2f}'.format(time() - _startTime)
            logList.see(logList.insert('', 'end', None, values=(_date, _time, myCall, str(slot.get()), str(getCurrentTGName()), '0.00%', str(_duration)+'s')))
            currentTxValue.set(myCall)

###################################################################################
# Convience method to help with ttk values
###################################################################################
def makeTkVar( constructor, val, trace=None ):
    avar = constructor()
    avar.set(val)
    if trace:
        avar.trace('w', trace)
    return avar

###################################################################################
# Callback when the master has changed
###################################################################################
def masterChanged(*args):
    fillTalkgroupList(master.get())
    print master.get()

###################################################################################
# Callback when a button is pressed
###################################################################################
def buttonPress(*args):
    tkMessageBox.showinfo("DMRGui", "This is just a prototype")

###################################################################################
# Used for debug
###################################################################################
def cb(value):
    print("value = ", value.get())

###################################################################################
#
###################################################################################
def whiteLabel(parent, textVal):
    l = Label(parent, text=textVal, background = "white", anchor=W)
    return l

###################################################################################
#
###################################################################################
def tgDialog():
    d = MyDialog(root)
    root.wait_window(d.top)

###################################################################################
#
###################################################################################
def makeModeFrame( parent ):
    modeFrame = LabelFrame(parent, text = "Server", pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
    ttk.Button(modeFrame, text="Read", command=getValuesFromServer).grid(column=1, row=1, sticky=W)
    ttk.Button(modeFrame, text="Write", command=sendValuesToServer).grid(column=1, row=2, sticky=W)
    return modeFrame

###################################################################################
#
###################################################################################
def makeAudioFrame( parent ):
    audioFrame = LabelFrame(parent, text = "Audio", pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
    whiteLabel(audioFrame, "Mic").grid(column=1, row=1, sticky=W, padx = 5)
    whiteLabel(audioFrame, "Speaker").grid(column=1, row=2, sticky=W, padx = 5)
    ttk.Scale(audioFrame, from_=0, to=100, orient=HORIZONTAL, variable=micVol,
              command=lambda x: cb(micVol)).grid(column=2, row=1, sticky=W)
    ttk.Scale(audioFrame, from_=0, to=100, orient=HORIZONTAL, variable=spVol,
              command=lambda x: cb(spVol)).grid(column=2, row=2, sticky=W)
    return audioFrame

###################################################################################
#
###################################################################################
def fillTalkgroupList( listName ):
    listbox.delete(0, END)
    for item in talkGroups[listName]:
        listbox.insert(END, item[0] + "," + item[1])
    listbox.selection_set(0)

###################################################################################
#
###################################################################################
def makeDMRFrame( parent ):
    global listbox
    dmrFrame = LabelFrame(parent, text = "Talk Groups", pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
    whiteLabel(dmrFrame, "TS").grid(column=1, row=1, sticky=W, padx = 5)
    Spinbox(dmrFrame, from_=1, to=2, width = 5, textvariable = slot).grid(column=2, row=1, sticky=W)
    whiteLabel(dmrFrame, "TG").grid(column=1, row=2, sticky=(N, W), padx = 5)
    listbox = Listbox(dmrFrame, selectmode=EXTENDED)
    listbox.configure(exportselection=False)
    listbox.grid(column=2, row=2, sticky=W, columnspan=2)
    
    fillTalkgroupList(defaultServer)
    ttk.Button(dmrFrame, text="TG", command=tgDialog, width = 1).grid(column=1, row=3, sticky=W)
    ttk.Button(dmrFrame, text="Connect", command=connect).grid(column=2, row=3, sticky=W)
    ttk.Button(dmrFrame, text="Disconnect", command=disconnect).grid(column=3, row=3, sticky=W)
    return dmrFrame

###################################################################################
#
###################################################################################
def makeLogFrame( parent ):
    global logList
    logFrame = Frame(parent, pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)


    logList = ttk.Treeview(logFrame)
    logList.grid(column=1, row=2, sticky=W, columnspan=5)
    
    cols = ('Date', 'Time', 'Call', 'Slot', 'TG', 'Loss', 'Duration')
    widths = [75, 75, 70, 45, 140, 60, 85]
    logList.config(columns=cols)
    logList.column("#0", width=1 )
    i = 0
    for item in cols:
        a = 'w' if i < 6 else 'e'
        logList.column(item, width=widths[i], anchor=a )
        logList.heading(item, text=item)
        i += 1

    return logFrame

###################################################################################
#
###################################################################################
def makeTransmitFrame(parent):
    global transmitButton
    transmitFrame = Frame(parent, pady = 5, padx = 5, bg = "white", bd = 1)
    transmitButton = Button(transmitFrame, text="Transmit", command=transmit, width = 40, state='disabled')
    transmitButton.grid(column=1, row=1, sticky=W)
    return transmitFrame

###################################################################################
#
###################################################################################
def makeAppFrame( parent ):
    appFrame = Frame(parent, pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
    appFrame.grid(column=0, row=0, sticky=(N, W, E, S))
    appFrame.columnconfigure(0, weight=1)
    appFrame.rowconfigure(0, weight=1)

    makeDMRSettingsFrame(appFrame).grid(column=1, row=1, sticky=(N,W), padx = 5)
    makeDMRFrame(appFrame).grid(column=3, row=1, sticky=N)
    makeTransmitFrame(appFrame).grid(column=1, row=2, sticky=N, columnspan=3, pady = 10)

    return appFrame

###################################################################################
#
###################################################################################
def makeDMRSettingsFrame( parent ):
    ypad = 4
    dmrgroup = LabelFrame(parent, text="DMR", padx=5, pady=ypad)
    whiteLabel(dmrgroup, "Master").grid(column=1, row=1, sticky=W, padx = 5, pady = ypad)
    w = apply(OptionMenu, (dmrgroup, master) + tuple(servers))
    w.grid(column=2, row=1, sticky=W, padx = 5, pady = ypad)

    whiteLabel(dmrgroup, "Repeater ID").grid(column=1, row=2, sticky=W, padx = 5, pady = ypad)
    Entry(dmrgroup, width = 20, textvariable = repeaterID).grid(column=2, row=2, pady = ypad)
    whiteLabel(dmrgroup, "Subscriber ID").grid(column=1, row=3, sticky=W, padx = 5, pady = ypad)
    Entry(dmrgroup, width = 20, textvariable = subscriberID).grid(column=2, row=3, pady = ypad)

    return dmrgroup

###################################################################################
#
###################################################################################
def makeVoxSettingsFrame( parent ):
    ypad = 4
    voxSettings = LabelFrame(parent, text="Vox", padx=5, pady = ypad)
    Checkbutton(voxSettings, text = "Dongle Mode", variable=dongleMode, command=lambda: cb(dongleMode)).grid(column=1, row=1, sticky=W)
    Checkbutton(voxSettings, text = "Vox Enable", variable=voxEnable, command=lambda: cb(voxEnable)).grid(column=1, row=2, sticky=W)
    whiteLabel(voxSettings, "Threshold").grid(column=1, row=3, sticky=W, padx = 5, pady = ypad)
    Spinbox(voxSettings, from_=1, to=32767, width = 5, textvariable = voxThreshold).grid(column=2, row=3, sticky=W, pady = ypad)
    whiteLabel(voxSettings, "Delay").grid(column=1, row=4, sticky=W, padx = 5, pady = ypad)
    Spinbox(voxSettings, from_=1, to=5, width = 5, textvariable = voxDelay).grid(column=2, row=4, sticky=W, pady = ypad)

    return voxSettings

###################################################################################
#
###################################################################################
def makeIPSettingsFrame( parent ):
    ypad = 4
    ipSettings = LabelFrame(parent, text="Network", padx=5, pady = ypad)
    Checkbutton(ipSettings, text = "Loopback", variable=loopback, command=lambda: cb(loopback)).grid(column=1, row=1, sticky=W)
    whiteLabel(ipSettings, "IP Address").grid(column=1, row=2, sticky=W, padx = 5, pady = ypad)
    Entry(ipSettings, width = 20, textvariable = ipAddress).grid(column=2, row=2, pady = ypad)
    return ipSettings

###################################################################################
#
###################################################################################
def makeSettingsFrame( parent ):
    settingsFrame = Frame(parent, width = 500, height = 500,pady = 5, padx = 5, bg = "white", bd = 1, relief = SUNKEN)
    makeModeFrame(settingsFrame).grid(column=1, row=1, sticky=(N,W), padx = 5)
    makeIPSettingsFrame(settingsFrame).grid(column=2, row=1, sticky=(N,W), padx = 5, pady = 5, columnspan=2)
    makeVoxSettingsFrame(settingsFrame).grid(column=1, row=2, sticky=(N,W), padx = 5)
    makeAudioFrame(settingsFrame).grid(column=2, row=2, sticky=(N,W), padx = 5)
    return settingsFrame

###################################################################################
#
###################################################################################
def update_clock(obj):
    now = strftime("%H:%M:%S")
    obj.configure(text=now)
    root.after(1000, update_clock, obj)

###################################################################################
#
###################################################################################
def makeStatusBar( parent ):
    global currentTxLabel
    w = 22
    statusBar = Frame(parent, pady = 5, padx = 5)
    Label(statusBar, textvariable=connectedMsg, anchor=W, width = w).grid(column=1, row=1, sticky=W)
    Label(statusBar, textvariable=currentTxValue, anchor=CENTER, width = w).grid(column=2, row=1, sticky=N)
    obj = Label(statusBar, text="", anchor=E, width = w)
    obj.grid(column=3, row=1, sticky=E)
    root.after(1000, update_clock, obj)
    return statusBar

############################################################################################################
# Global commands
############################################################################################################

root = Tk()
root.title("DMRGui")
root.resizable(width=FALSE, height=FALSE)

nb = ttk.Notebook(root)

# Load data from the config file
configFileName = "dmrgui.cfg"
config = ConfigParser.ConfigParser()
config.optionxform = lambda option: option
try:
    config.read(configFileName)
    myCall = config.get('DEFAULTS', "myCall").split(None)[0]
    loopback = makeTkVar(IntVar, config.get('DEFAULTS', "loopback").split(None)[0])
    dongleMode = makeTkVar(IntVar, config.get('DEFAULTS', "dongleMode").split(None)[0])
    voxEnable = makeTkVar(IntVar, config.get('DEFAULTS', "voxEnable").split(None)[0])
    micVol = makeTkVar(IntVar, config.get('DEFAULTS', "micVol").split(None)[0])
    spVol = makeTkVar(IntVar, config.get('DEFAULTS', "spVol").split(None)[0])
    repeaterID = makeTkVar(IntVar, config.get('DEFAULTS', "repeaterID").split(None)[0])
    subscriberID = makeTkVar(IntVar, config.get('DEFAULTS', "subscriberID").split(None)[0])
    voxThreshold = makeTkVar(IntVar, config.get('DEFAULTS', "voxThreshold").split(None)[0])
    voxDelay = makeTkVar(IntVar, config.get('DEFAULTS', "voxDelay").split(None)[0])
    ipAddress = makeTkVar(StringVar, config.get('DEFAULTS', "ipAddress").split(None)[0])
    slot = makeTkVar(IntVar, config.get('DEFAULTS', "slot").split(None)[0])
    defaultServer = config.get('DEFAULTS', "defaultServer").split(None)[0]
    
    talkGroups = {}
    for sect in config.sections():
        if (sect != "DEFAULTS"):
            talkGroups[sect] = config.items(sect)
        
except:
    traceback.print_exc()
    sys.exit('Configuration file \''+configFileName+'\' is not a valid configuration file! Exiting...')


servers = sorted(talkGroups.keys())
master = makeTkVar(StringVar, defaultServer, masterChanged)
connectedMsg = makeTkVar(StringVar, "Connected to")
currentTxValue = makeTkVar(StringVar, myCall)

ptt = False
_startTime = 0

listbox = None
transmitButton = None
logList = None

# Create the two frames
appFrame = makeAppFrame( nb )
settingsFrame = makeSettingsFrame( nb )

# Add each frame to the tabs
nb.add(appFrame, text='Main')
nb.add(settingsFrame, text='Settings')
nb.grid(column=1, row=1)

# Create the other frames
makeLogFrame(root).grid(column=1, row=2, sticky=W)
makeStatusBar(root).grid(column=1, row=3, sticky=W)

# Start up the UDP reader to get async status from servers
thread.start_new_thread( launchUDP, ( ) )
getValuesFromServer()

root.mainloop()
