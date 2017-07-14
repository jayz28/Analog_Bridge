/*
 *   Copyright (C) 2010-2015 by Jonathan Naylor G4KLX
 *
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published by
 *   the Free Software Foundation; either version 2 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with this program; if not, write to the Free Software
 *   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include "DummyRepeaterThread.h"
#include "DummyRepeaterApp.h"
#include "DStarDefines.h"
#include "MessageData.h"
#include "Version.h"

#include <string.h>
#include <sys/socket.h>

// ***********************************************************************
// Allstar USRP channel driver support
// ***********************************************************************

#define USRP_IP	(char*)"127.0.0.1"		// Default IP address for the USRP channel driver (defined in rpt.conf)
#define USRP_TXPORT	(char *)"34001"		// PCM from ASL (set up a listener here on this port)
#define USRP_RXPORT (char *)"32001"		// PCM to ASL (USRP is listening on this port for PCM)

#define USRP_PCM_SAMPLES 160
enum { USRP_TYPE_VOICE=0, USRP_TYPE_DTMF, USRP_TYPE_TEXT };
struct _chan_usrp_bufhdr {
    char eye[4];                // verification string
    uint32_t seq;               // sequence counter
    uint32_t memory;    		// memory ID or zero (default)
    uint32_t keyup;             // tracks PTT state
    uint32_t talkgroup; 		// trunk TG id
    uint32_t type;              // see above enum
    uint32_t mpxid;             // for future use
    uint32_t reserved;  		// for future use
    short audio[USRP_PCM_SAMPLES];
};

class USRP {
public:
	USRP():
	m_seq(0),
	m_usrpFD(0),
	m_usrpTx(false),
	m_message(),
	m_packetTimeout(0)
	{
	}
	~USRP() {

	}
	void openUSRP() {

		char *ip = defaultValue("USRP_IP", USRP_IP);
		int rxPort = atoi( defaultValue("USRP_RXPORT", USRP_RXPORT) );
		int txPort = atoi( defaultValue("USRP_TXPORT", USRP_TXPORT) );
		m_usrpFD = openSocket(ip, rxPort, txPort);
		::memset((void *)&m_usrpPacket, 0, sizeof(m_usrpPacket));
		memcpy(m_usrpPacket.eye, "USRP", 4);
		wxLogMessage(wxT("Open network connection to USRP"));
	}
	void sendAudioToUSRP(const wxFloat32* audio) {
		if (m_usrpPacket.keyup == 0)
			wxLogMessage(wxT("Begin exporting PCM"));
		m_usrpPacket.type = USRP_TYPE_VOICE;
		m_usrpPacket.seq = htonl(m_seq++);
		m_usrpPacket.keyup = htonl(1);
		for (int i=0;i<USRP_PCM_SAMPLES;i++)
			m_usrpPacket.audio[i] = (short)((audio[i*6]) * 32768.0F /  3.0F);
		int sentBytes = ::sendto(m_usrpFD, (const void *)&m_usrpPacket, sizeof(m_usrpPacket), MSG_DONTWAIT, (struct sockaddr *)&m_sa_write, (ssize_t)sizeof(struct sockaddr_in));
	}
	void setTransmit( bool state ) {
		bool transmittingToPartner = m_usrpPacket.keyup == htonl(1);
		if ((state == false)  && transmittingToPartner) {
			m_usrpPacket.type = USRP_TYPE_VOICE;
			m_usrpPacket.seq = htonl(m_seq++);
			m_usrpPacket.keyup = htonl(0);
			int size = sizeof(m_usrpPacket) - sizeof(m_usrpPacket.audio);
			int sentBytes = ::sendto(m_usrpFD, (const void *)&m_usrpPacket, size, MSG_DONTWAIT, (struct sockaddr *)&m_sa_write, (ssize_t)sizeof(struct sockaddr_in));
			wxLogMessage(wxT("End exporting PCM"));
		} else {
			wxLogMessage(wxT("setTransmit called but nothing done. state=%d, ttp=%d"), state, transmittingToPartner);
		}
	}
	void sendMetaData( const char *callSign ) {
		m_usrpPacket.type = USRP_TYPE_TEXT;
		m_usrpPacket.seq = htonl(m_seq++);
		m_usrpPacket.keyup = htonl(0);
		int size = sizeof(m_usrpPacket) - sizeof(m_usrpPacket.audio) + strlen(callSign) + 1;
		strcpy( (char *)m_usrpPacket.audio, callSign );
		int sentBytes = ::sendto(m_usrpFD, (const void *)&m_usrpPacket, size, MSG_DONTWAIT, (struct sockaddr *)&m_sa_write, (ssize_t)sizeof(struct sockaddr_in));
	}
	void getAudioFromUSRP(CDongleThread *m_dongle) {
		if (isUsrpTxReady()) {
			struct _chan_usrp_bufhdr rxPacket;
			socklen_t sl = sizeof(struct sockaddr_in);
			int n = recvfrom(m_usrpFD, (void *)&rxPacket, sizeof(rxPacket), 0, (struct sockaddr *)&m_sa_read, &sl);
			switch (rxPacket.type) {
				case USRP_TYPE_VOICE:
				{
					bool localTX  = ntohl(rxPacket.keyup) == 1;
					if (localTX == true) { // USRP packet with audio
						wxFloat32 audioOut[960];
						int j = 0;
						for(int i=0;i<USRP_PCM_SAMPLES;i++) {
							audioOut[j++] = wxFloat32(rxPacket.audio[i]) / 32768.0F * 6.0F;
							audioOut[j++] = 0;
							audioOut[j++] = 0;
							audioOut[j++] = 0;
							audioOut[j++] = 0;
							audioOut[j++] = 0;
						}
						m_dongle->writeEncode(audioOut, 960);
						m_packetTimeout = time(NULL) + 2;
					} else
						m_message.Empty();	//delete metadata when PTT is deasserted
					if (localTX != m_usrpTx) 
						wxLogMessage(wxT("%s encoding PCM"), localTX ? "Begin" : "End");
					m_usrpTx = localTX;
				}
				break;
			case USRP_TYPE_DTMF:
				wxLogMessage(wxT("USRP packet type: USRP_TYPE_DTMF"));
				break;
			case USRP_TYPE_TEXT:
				m_message = wxString((char *)rxPacket.audio);
				wxLogMessage(wxT("USRP packet type: USRP_TYPE_TEXT (%s)"), m_message.c_str());
				break;
			}
		}
	}
	bool getRadioSquelch1(){
		bool isReady = isUsrpTxReady();
		if (m_usrpTx && (isReady == false)) {// thinks it is keyed but no data from partner
			if (time(NULL) > m_packetTimeout) {
				m_usrpTx = false;	// have not seen a packet in too long
				wxLogMessage(wxT("TX timeout.  Have not seen USRP packet in too long"));
			}
		}
		return  m_usrpTx || isReady;
	}
	wxString getMessage() {
		return m_message;
	}
protected:
	int openSocket(char *hostName, int portNumberRx, int portNumberTx) {
		struct hostent *hp;     /* host information */

		int sockFd = -1;
		//open input socket
		sockFd = socket(AF_INET, SOCK_DGRAM, 0);
		if (sockFd >= 0) {
			memset(&m_sa_read, 0x00, sizeof(struct sockaddr_in));
			m_sa_read.sin_family = AF_INET;
			m_sa_read.sin_port = htons(portNumberTx);
			m_sa_read.sin_addr.s_addr = htonl(INADDR_ANY);

			bind(sockFd, (struct sockaddr *)&m_sa_read, sizeof(struct sockaddr_in));

			memset(&m_sa_write, 0x00, sizeof(struct sockaddr_in));
			m_sa_write.sin_family = AF_INET;
			m_sa_write.sin_port = htons(portNumberRx);
			hp = gethostbyname(hostName);
			memcpy((void *)&m_sa_write.sin_addr, hp->h_addr_list[0], hp->h_length);
		}
		else
			wxLogMessage(wxT("USRP network error"));

		return sockFd;

	}
	bool isUsrpTxReady() {
		fd_set fds;
		struct timeval tv;
		tv.tv_sec = 0;
		tv.tv_usec = 0;

		FD_ZERO(&fds);
		FD_SET(m_usrpFD, &fds);

		return (select(m_usrpFD + 1, &fds, NULL, NULL, &tv) > 0);
	}
private:
	char *defaultValue( const char *env, char *defaultValue ) {
		char *ptr = getenv(env);
		if (ptr != NULL)
			return ptr;
		return defaultValue;
	}
	uint32_t m_seq;							// Incrementing sequence number for each USRP packet
	int m_usrpFD;							// Network handle for TX and RX to USRP
	struct sockaddr_in m_sa_read, m_sa_write;
	struct _chan_usrp_bufhdr m_usrpPacket;	// A prototype packet to fill in and send to USRP
	bool m_usrpTx;							// local PTT flag (tracks the keyup in USRP packets)
	wxString m_message;
	time_t m_packetTimeout;
};

USRP usrp;	// Cheap hack, create a stsic instance of the class

// ***********************************************************************


CDummyRepeaterThread::CDummyRepeaterThread() :
wxThread(wxTHREAD_JOINABLE),
m_soundcard(NULL),
m_dongle(NULL),
m_controller(NULL),
m_slowDataEncoder(),
m_slowDataDecoder(),
m_protocol(NULL),
m_stopped(true),
m_decodeAudio(DSTAR_RADIO_BLOCK_SIZE * 30U),
m_encodeData(VOICE_FRAME_LENGTH_BYTES * 30U),
m_transmit(CLIENT_RECEIVE),
m_callsign1(),
m_callsign2(),
m_your(),
m_rpt1(),
m_rpt2(),
m_message(),
m_frameCount(0U),
m_networkSeqNo(0U),
m_killed(false),
m_started(false),
m_watchdog(1000U, 2U),
m_poll(1000U, 60U),
m_clockCount(0U),
m_busy(false),
m_localTX(false),
m_externalTX(false)
{
}

CDummyRepeaterThread::~CDummyRepeaterThread()
{
}

void* CDummyRepeaterThread::Entry()
{
	// Wait here until we have the essentials to run
	while (!m_killed && (m_dongle == NULL || m_controller == NULL || m_soundcard == NULL || m_protocol == NULL || m_callsign1.IsEmpty()))
		Sleep(500UL);		// 1/2 sec

	if (m_killed)
		return NULL;

	m_stopped = false;

	m_poll.start();

	m_dongle->Create();
	m_dongle->SetPriority(100U);
	m_dongle->Run();

	m_controller->setRadioTransmit(false);

	usrp.openUSRP();	// Open network connection to USRP

	while (!m_killed) {
		if (m_transmit == CLIENT_RECEIVE)
			receive();
		else
			transmit();
	}

	m_dongle->kill();

	m_controller->setRadioTransmit(false);
	m_controller->close();

	m_protocol->close();
	delete m_protocol;

	m_soundcard->close();
	delete m_soundcard;

	return NULL;
}

void CDummyRepeaterThread::decodeCallback(const wxFloat32* audio, unsigned int length)
{
	m_decodeAudio.addData(audio, length);
	if (m_busy) // is this packet still in transmit mode?
		usrp.sendAudioToUSRP(audio);	// Send PCM to the USRP channel driver
}

void CDummyRepeaterThread::encodeCallback(const unsigned char* ambe, unsigned int length, PTT_STATE state)
{
	if (state == PS_TRANSMIT && m_transmit != CLIENT_TRANSMIT)
		::wxGetApp().setGUITransmit(true);
	else if (state == PS_RECEIVE && m_transmit == CLIENT_TRANSMIT)
		::wxGetApp().setGUITransmit(false);

	m_encodeData.addData(ambe, length);
}

void CDummyRepeaterThread::kill()
{
	m_killed = true;
}

void CDummyRepeaterThread::setCallsign(const wxString& callsign1, const wxString& callsign2)
{
	m_callsign1 = callsign1;
	m_callsign2 = callsign2;
}

void CDummyRepeaterThread::setSoundCard(CSoundCardReaderWriter* soundcard)
{
	wxASSERT(soundcard != NULL);

	if (!m_stopped) {
		soundcard->close();
		delete soundcard;
		return;
	}

	if (m_soundcard != NULL) {
		m_soundcard->close();
		delete m_soundcard;
	}

	m_soundcard = soundcard;
}

void CDummyRepeaterThread::setDongle(CDongleThread* dongle)
{
	wxASSERT(dongle != NULL);

	if (!m_stopped) {
		dongle->kill();
		return;
	}

	if (m_dongle != NULL)
		m_dongle->kill();

	m_dongle = dongle;
}

void CDummyRepeaterThread::setController(CExternalController* controller)
{
	wxASSERT(controller != NULL);

	if (!m_stopped) {
		controller->close();
		return;
	}

	if (m_controller != NULL)
		m_controller->close();

	m_controller = controller;
}

void CDummyRepeaterThread::setProtocol(CRepeaterProtocolHandler* protocol)
{
	wxASSERT(protocol != NULL);

	if (!m_stopped) {
		protocol->close();
		delete protocol;
		return;
	}

	if (m_protocol != NULL) {
		m_protocol->close();
		delete m_protocol;
	}

	m_protocol = protocol;
}

void CDummyRepeaterThread::setMessage(const wxString& text)
{
	m_message = text;
}

void CDummyRepeaterThread::setBleep(bool on)
{
	if (m_dongle != NULL)
		m_dongle->setBleep(on);
}

void CDummyRepeaterThread::setYour(const wxString& your)
{
	m_your = your;
}

void CDummyRepeaterThread::setRpt1(const wxString& rpt1)
{
	// An empty RPT1 callsign also implies an empty RPT2
	if (rpt1.IsSameAs(UNUSED)) {
		m_rpt1 = wxT("        ");
		m_rpt2 = wxT("        ");
	} else {
		m_rpt1 = rpt1;
	}
}

void CDummyRepeaterThread::setRpt2(const wxString& rpt2)
{
	// An empty RPT2 callsign
	if (rpt2.IsSameAs(UNUSED))
		m_rpt2 = wxT("        ");
	else
		m_rpt2 = rpt2;
}

bool CDummyRepeaterThread::setTransmit(bool transmit)
{
	if (m_stopped)
		return false;

	m_localTX = transmit;

	if (m_localTX && m_transmit != CLIENT_TRANSMIT) {
		m_transmit = CLIENT_TRANSMIT;
	} else if (!m_localTX && m_transmit == CLIENT_TRANSMIT) {
		if (!m_externalTX) {
			resetReceiver();
			m_transmit = CLIENT_WANT_RECEIVE;
		}
	}
	return true;
}

void CDummyRepeaterThread::checkController()
{
	m_externalTX = m_controller->getRadioSquelch1();
	m_externalTX = usrp.getRadioSquelch1();		// Test if there is any data available from the USRP channel driver connection

	if (m_externalTX && m_transmit != CLIENT_TRANSMIT) {
		m_transmit = CLIENT_TRANSMIT;
		::wxGetApp().setGUITransmit(true);
	} else if (!m_externalTX && m_transmit == CLIENT_TRANSMIT) {
		if (!m_localTX) {
			resetReceiver();
			m_transmit = CLIENT_WANT_RECEIVE;
		}
		::wxGetApp().setGUITransmit(false);
	}

	m_controller->setRadioTransmit(m_busy);
}

void CDummyRepeaterThread::receive()
{
	m_clockCount = 0U;
	m_busy = false;

	unsigned int hangCount = 0U;

	// While receiving and not exitting
	while (m_transmit == CLIENT_RECEIVE && !m_killed) {
		// Get the audio from the RX
		NETWORK_TYPE type;

		for (;;) {
			type = m_protocol->read();

			if (type == NETWORK_NONE) {
				break;
			} else if (type == NETWORK_HEADER) {
				CHeaderData* header = m_protocol->readHeader();
				if (header != NULL) {
					processHeader(header);
					m_watchdog.start();
					m_clockCount = 0U;
					hangCount = 0U;
					m_busy = true;
				}
				break;
			} else if (type == NETWORK_DATA) {
				unsigned char buffer[DV_FRAME_LENGTH_BYTES];
				unsigned char seqNo;
				unsigned int length = m_protocol->readData(buffer, DV_FRAME_LENGTH_BYTES, seqNo);
				if (length != 0U) {
					bool end = processFrame(buffer, seqNo);
					if (end)
						hangCount = 30U;
					else
						hangCount = 0U;
					m_watchdog.reset();
					m_clockCount = 0U;
				}
				break;
			} else if (type == NETWORK_TEXT) {
				wxString text, reflector;
				LINK_STATUS status;
				m_protocol->readText(text, status, reflector);
				::wxGetApp().showSlowData(text);
			} else if (type == NETWORK_TEMPTEXT) {
				wxString text;
				m_protocol->readTempText(text);
			} else if (type == NETWORK_STATUS1) {
				wxString text = m_protocol->readStatus1();
				::wxGetApp().showStatus1(text);
			} else if (type == NETWORK_STATUS2) {
				wxString text = m_protocol->readStatus2();
				::wxGetApp().showStatus2(text);
			} else if (type == NETWORK_STATUS3) {
				wxString text = m_protocol->readStatus3();
				::wxGetApp().showStatus3(text);
			} else if (type == NETWORK_STATUS4) {
				wxString text = m_protocol->readStatus4();
				::wxGetApp().showStatus4(text);
			} else if (type == NETWORK_STATUS5) {
				wxString text = m_protocol->readStatus5();
				::wxGetApp().showStatus5(text);
			}
		}

		// Have we missed a data frame?
		if (type == NETWORK_NONE && m_busy) {
			m_clockCount++;
			if (m_clockCount == 8U) {
				// Create a silence frame
				unsigned char buffer[DV_FRAME_LENGTH_BYTES];
				::memcpy(buffer, NULL_FRAME_DATA_BYTES, DV_FRAME_LENGTH_BYTES);
				processFrame(buffer, m_networkSeqNo);

				m_clockCount = 0U;
			}
		}

		if (m_watchdog.isRunning() && m_watchdog.hasExpired()) {
			wxLogMessage(wxT("Network watchdog has expired"));
			m_dongle->setIdle();
			m_protocol->reset();
			resetReceiver();
		}

		if (hangCount > 0U) {
			hangCount--;
			if (hangCount == 0U) {
				m_dongle->setIdle();
				resetReceiver();
			}
		}

		checkController();

		Sleep(DSTAR_FRAME_TIME_MS / 4UL);
	}
}

void CDummyRepeaterThread::transmit()
{
	m_encodeData.clear();
	m_dongle->setEncode();

	// Pause until all the silence data has been processed by the AMBE2020
	for (unsigned int startCount = 30U; startCount > 0U; startCount--) {
		unsigned char frame[DV_FRAME_LENGTH_BYTES];
		unsigned int n = 0U;
		do {
			n += m_encodeData.getData(frame + n, VOICE_FRAME_LENGTH_BYTES - n);

			if (n < VOICE_FRAME_LENGTH_BYTES)
				Sleep(DSTAR_FRAME_TIME_MS / 4UL);
		} while (n < VOICE_FRAME_LENGTH_BYTES);

		serviceNetwork();
		checkController();
	}

	CHeaderData* header = new CHeaderData(m_callsign1, m_callsign2, m_your, m_rpt2, m_rpt1);

	wxLogMessage(wxT("Transmitting to - My: %s/%s  Your: %s  Rpt1: %s  Rpt2: %s"), header->getMyCall1().c_str(), header->getMyCall2().c_str(), header->getYourCall().c_str(), header->getRptCall1().c_str(), header->getRptCall2().c_str());

	m_slowDataEncoder.reset();
	m_slowDataEncoder.setHeaderData(*header);

	serviceNetwork();
	checkController();

	if (!usrp.getMessage().IsEmpty())
		m_slowDataEncoder.setMessageData(usrp.getMessage());
	else if (!m_message.IsEmpty())
		m_slowDataEncoder.setMessageData(m_message);

	m_protocol->writeHeader(*header);
	delete header;

	serviceNetwork();
	checkController();

	m_frameCount = 20U;

	unsigned int endCount = 30U;

	// While transmitting and not exiting
	for (;;) {
		unsigned char frame[DV_FRAME_LENGTH_BYTES];
		unsigned int n = 0U;
		do {
			n += m_encodeData.getData(frame + n, VOICE_FRAME_LENGTH_BYTES - n);

			if (n < VOICE_FRAME_LENGTH_BYTES)
				Sleep(DSTAR_FRAME_TIME_MS / 4UL);
		} while (n < VOICE_FRAME_LENGTH_BYTES);

		serviceNetwork();
		checkController();

		if (m_frameCount == 20U) {
			// Put in the data resync pattern
			::memcpy(frame + VOICE_FRAME_LENGTH_BYTES, DATA_SYNC_BYTES, DATA_FRAME_LENGTH_BYTES);
			m_frameCount = 0U;
		} else {
			// Tack the slow data on the end
			m_slowDataEncoder.getData(frame + VOICE_FRAME_LENGTH_BYTES);
			m_frameCount++;
		}

		if (m_transmit != CLIENT_TRANSMIT)
			endCount--;

		// Send the AMBE and slow data frame
		if (endCount == 0U || m_killed) {
			m_protocol->writeData(frame, DV_FRAME_LENGTH_BYTES, 0U, true);
			break;
		} else {
			m_protocol->writeData(frame, DV_FRAME_LENGTH_BYTES, 0U, false);
		}

		serviceNetwork();
		checkController();
	}

	m_dongle->setIdle();

	resetReceiver();

	m_transmit = CLIENT_RECEIVE;

	serviceNetwork();
	checkController();
}

void CDummyRepeaterThread::processHeader(CHeaderData* header)
{
	wxASSERT(header != NULL);

	wxLogMessage(wxT("Header decoded - My: %s/%s  Your: %s  Rpt1: %s  Rpt2: %s"), header->getMyCall1().c_str(), header->getMyCall2().c_str(), header->getYourCall().c_str(), header->getRptCall1().c_str(), header->getRptCall2().c_str());

	// Tell the GUI, this must be last
	::wxGetApp().showHeader(header);
	usrp.sendMetaData( header->getMyCall1().c_str() );

	m_dongle->setDecode();

	// Put 60ms of silence into the buffer
	m_dongle->writeDecode(NULL_AMBE_DATA_BYTES, VOICE_FRAME_LENGTH_BYTES);
	m_dongle->writeDecode(NULL_AMBE_DATA_BYTES, VOICE_FRAME_LENGTH_BYTES);
	m_dongle->writeDecode(NULL_AMBE_DATA_BYTES, VOICE_FRAME_LENGTH_BYTES);

	m_slowDataDecoder.reset();

	m_networkSeqNo = 0U;
}

bool CDummyRepeaterThread::processFrame(const unsigned char* buffer, unsigned char seqNo)
{
	bool end = (seqNo & 0x40U) == 0x40U;
	if (end)
		return true;

	// Mask out the control bits of the sequence number
	seqNo &= 0x1FU;

	// Count the number of silence frames to insert
	unsigned int tempSeqNo = m_networkSeqNo;
	unsigned int count = 0U;
	while (seqNo != tempSeqNo) {
		count++;

		tempSeqNo++;
		if (tempSeqNo >= 21U)
			tempSeqNo = 0U;
	}

	// If the number is too high, then it probably means an old out-of-order frame, ignore it
	if (count > 18U)
		return false;

	// Insert missing frames
	while (seqNo != m_networkSeqNo) {
		if (m_networkSeqNo == 0U) {
			m_slowDataDecoder.sync();
		} else {
			m_slowDataDecoder.addData(NULL_SLOW_DATA_BYTES);
			CMessageData* message = m_slowDataDecoder.getMessageData();
			if (message != NULL)
				::wxGetApp().showMessage(message);
		}

		// Write a silence frame
		m_dongle->writeDecode(NULL_AMBE_DATA_BYTES, VOICE_FRAME_LENGTH_BYTES);

		m_networkSeqNo++;
		if (m_networkSeqNo >= 21U)
			m_networkSeqNo = 0U;
	}

	if (seqNo == 0U) {
		m_slowDataDecoder.sync();
		m_networkSeqNo = 1U;
	} else {
		m_slowDataDecoder.addData(buffer + VOICE_FRAME_LENGTH_BYTES);
		CMessageData* message = m_slowDataDecoder.getMessageData();
		if (message != NULL)
			::wxGetApp().showMessage(message);

		m_networkSeqNo++;
		if (m_networkSeqNo >= 21U)
			m_networkSeqNo = 0U;
	}

	m_dongle->writeDecode(buffer, VOICE_FRAME_LENGTH_BYTES);

	return false;
}

void CDummyRepeaterThread::readCallback(const wxFloat32* input, unsigned int nSamples, int)
{
	if (m_stopped)
		return;
	if (m_transmit != CLIENT_RECEIVE) {
		if (usrp.getRadioSquelch1())			// If there is data available from USRP
			usrp.getAudioFromUSRP(m_dongle);	// then import and encode it
		else
			m_dongle->writeEncode(input, nSamples);
	}
	m_poll.clock(20U);
	m_watchdog.clock(20U);

	// Send the network poll if needed and restart the timer
	if (m_poll.hasExpired()) {
#if defined(__WINDOWS__)
		m_protocol->writePoll(wxT("win_dummy-") + VERSION);
#else
		m_protocol->writePoll(wxT("linux_dummy-") + VERSION);
#endif
		m_poll.reset();
	}
}

void CDummyRepeaterThread::writeCallback(wxFloat32* output, unsigned int& nSamples, int)
{
	::memset(output, 0x00U, nSamples * sizeof(wxFloat32));

	if (m_stopped)
		return;

	if (nSamples > 0U)
		nSamples = m_decodeAudio.getData(output, nSamples);
}

void CDummyRepeaterThread::resetReceiver()
{
	// Tell the GUI
	::wxGetApp().showHeader(NULL);

	m_slowDataDecoder.reset();

	m_watchdog.stop();

	m_busy = false;
	usrp.setTransmit(false);
}

void CDummyRepeaterThread::serviceNetwork()
{
	for (;;) {
		NETWORK_TYPE type = m_protocol->read();

		if (type == NETWORK_NONE) {
			return;
		} else if (type == NETWORK_TEXT) {
			wxString text, reflector;
			LINK_STATUS status;
			m_protocol->readText(text, status, reflector);
			wxGetApp().showSlowData(text);
		} else if (type == NETWORK_STATUS1) {
			wxString text = m_protocol->readStatus1();
			::wxGetApp().showStatus1(text);
		} else if (type == NETWORK_STATUS2) {
			wxString text = m_protocol->readStatus2();
			::wxGetApp().showStatus2(text);
		} else if (type == NETWORK_STATUS3) {
			wxString text = m_protocol->readStatus3();
			::wxGetApp().showStatus3(text);
		} else if (type == NETWORK_STATUS4) {
			wxString text = m_protocol->readStatus4();
			::wxGetApp().showStatus4(text);
		} else if (type == NETWORK_STATUS5) {
			wxString text = m_protocol->readStatus5();
			::wxGetApp().showStatus5(text);
		}
	}
}
