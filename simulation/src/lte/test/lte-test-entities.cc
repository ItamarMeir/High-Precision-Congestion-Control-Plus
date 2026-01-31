/* -*-  Mode: C++; c-file-style: "gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2011 Centre Tecnologic de Telecomunicacions de Catalunya (CTTC)
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Author: Manuel Requena <manuel.requena@cttc.es>
 */

#include "ns3/simulator.h"
#include "ns3/log.h"

#include "ns3/lte-rlc-header.h"
#include "ns3/lte-rlc-am-header.h"
#include "ns3/lte-pdcp-header.h"

#include "lte-test-entities.h"

NS_LOG_COMPONENT_DEFINE ("LteTestEntities");

namespace ns3 {


/////////////////////////////////////////////////////////////////////

TypeId
LteTestRrc::GetTypeId (void)
{
  static TypeId tid = TypeId ("ns3::LteTestRrc")
    .SetParent<Object> ()
    .AddConstructor<LteTestRrc> ()
    ;

  return tid;
}

LteTestRrc::LteTestRrc ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity

  m_txPdus = 0;
  m_txBytes = 0;
  m_rxPdus = 0;
  m_rxBytes = 0;
  m_txLastTime = Time (0);
  m_rxLastTime = Time (0);;

  m_pdcpSapUser = new LtePdcpSpecificLtePdcpSapUser<LteTestRrc> (this);
//   Simulator::ScheduleNow (&LteTestRrc::Start, this);
}

LteTestRrc::~LteTestRrc ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
}

void
LteTestRrc::DoDispose ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
  delete m_pdcpSapUser;
}

void
LteTestRrc::SetLtePdcpSapProvider (LtePdcpSapProvider* s)
{
  m_pdcpSapProvider = s;
}

LtePdcpSapUser*
LteTestRrc::GetLtePdcpSapUser (void)
{
  return m_pdcpSapUser;
}


std::string
LteTestRrc::GetDataReceived (void)
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
  return m_receivedData;
}

// Stats
uint32_t
LteTestRrc::GetTxPdus (void)
{
  NS_LOG_FUNCTION (m_txPdus);
  return m_txPdus;
}

uint32_t
LteTestRrc::GetTxBytes (void)
{
  NS_LOG_FUNCTION (m_txBytes);
  return m_txBytes;
}

uint32_t
LteTestRrc::GetRxPdus (void)
{
  NS_LOG_FUNCTION (m_rxPdus);
  return m_rxPdus;
}

uint32_t
LteTestRrc::GetRxBytes (void)
{
  NS_LOG_FUNCTION (m_rxBytes);
  return m_rxBytes;
}

Time
LteTestRrc::GetTxLastTime (void)
{
  NS_LOG_FUNCTION (m_txLastTime);
  return m_txLastTime;
}

Time
LteTestRrc::GetRxLastTime (void)
{
  NS_LOG_FUNCTION (m_rxLastTime);
  return m_rxLastTime;
}


void
LteTestRrc::SetArrivalTime (Time arrivalTime)
{
  NS_LOG_FUNCTION (arrivalTime);
  m_arrivalTime = arrivalTime;
}

void
LteTestRrc::SetPduSize (uint32_t pduSize)
{
  NS_LOG_FUNCTION (pduSize);
  m_pduSize = pduSize;
}


/**
 * PDCP SAP
 */

void
LteTestRrc::DoReceiveRrcPdu (LtePdcpSapUser::ReceiveRrcPduParameters params)
{
  NS_LOG_FUNCTION (params.rrcPdu->GetSize ());
  Ptr<Packet> p = params.rrcPdu;
//   NS_LOG_LOGIC ("PDU received = " << (*p));

  uint32_t dataLen = p->GetSize ();
  uint8_t *buf = new uint8_t[dataLen];

  // Stats
  m_rxPdus++;
  m_rxBytes += dataLen;
  m_rxLastTime = Simulator::Now ();

  p->CopyData (buf, dataLen);
  m_receivedData = std::string ((char *)buf, dataLen);

//   NS_LOG_LOGIC (m_receivedData);

  delete [] buf;
}

/**
 * START
 */

void
LteTestRrc::Start ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
  NS_ASSERT_MSG (m_arrivalTime != 0, "Arrival time must be different from 0");

  // Stats
  m_txPdus++;
  m_txBytes += m_pduSize;
  m_txLastTime = Simulator::Now ();

  LtePdcpSapProvider::TransmitRrcPduParameters p;
  p.rnti = 1111;
  p.lcid = 222;
  p.rrcPdu = Create<Packet> (m_pduSize);

  Simulator::ScheduleNow (&LtePdcpSapProvider::TransmitRrcPdu, m_pdcpSapProvider, p);
  m_nextPdu = Simulator::Schedule (m_arrivalTime, &LteTestRrc::Start, this);
//   Simulator::Run ();
}

void
LteTestRrc::Stop ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
  m_nextPdu.Cancel ();
}

void
LteTestRrc::SendData (Time at, std::string dataToSend)
{
  NS_LOG_FUNCTION (at << dataToSend.length () << dataToSend);

  // Stats
  m_txPdus++;
  m_txBytes += dataToSend.length ();

  LtePdcpSapProvider::TransmitRrcPduParameters p;
  p.rnti = 1111;
  p.lcid = 222;

  NS_LOG_LOGIC ("Data(" << dataToSend.length () << ") = " << dataToSend.data ());
  p.rrcPdu = Create<Packet> ((uint8_t *) dataToSend.data (), dataToSend.length ());

  NS_LOG_LOGIC ("Packet(" << p.rrcPdu->GetSize () << ")");
  Simulator::Schedule (at, &LtePdcpSapProvider::TransmitRrcPdu, m_pdcpSapProvider, p);
}

/////////////////////////////////////////////////////////////////////

TypeId
LteTestPdcp::GetTypeId (void)
{
  static TypeId tid = TypeId ("ns3::LteTestPdcp")
    .SetParent<Object> ()
    .AddConstructor<LteTestPdcp> ()
    ;

  return tid;
}

LteTestPdcp::LteTestPdcp ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
  m_rlcSapUser = new LteRlcSpecificLteRlcSapUser<LteTestPdcp> (this);
  Simulator::ScheduleNow (&LteTestPdcp::Start, this);
}

LteTestPdcp::~LteTestPdcp ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
}

void
LteTestPdcp::DoDispose ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
  delete m_rlcSapUser;
}

void
LteTestPdcp::SetLteRlcSapProvider (LteRlcSapProvider* s)
{
  m_rlcSapProvider = s;
}

LteRlcSapUser*
LteTestPdcp::GetLteRlcSapUser (void)
{
  return m_rlcSapUser;
}


std::string
LteTestPdcp::GetDataReceived (void)
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity

  return m_receivedData;
}


/**
 * RLC SAP
 */

void
LteTestPdcp::DoReceivePdcpPdu (Ptr<Packet> p)
{
  NS_LOG_FUNCTION (p->GetSize ());
  NS_LOG_LOGIC ("Data = " << (*p));

  uint32_t dataLen = p->GetSize ();
  uint8_t *buf = new uint8_t[dataLen];
  p->CopyData (buf, dataLen);
  m_receivedData = std::string ((char *)buf, dataLen);

  NS_LOG_LOGIC (m_receivedData);

  delete [] buf;
}

/**
 * START
 */

void
LteTestPdcp::Start ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
}

void
LteTestPdcp::SendData (Time time, std::string dataToSend)
{
  NS_LOG_FUNCTION (time << dataToSend.length () << dataToSend);

  LteRlcSapProvider::TransmitPdcpPduParameters p;
  p.rnti = 1111;
  p.lcid = 222;

  NS_LOG_LOGIC ("Data(" << dataToSend.length () << ") = " << dataToSend.data ());
  p.pdcpPdu = Create<Packet> ((uint8_t *) dataToSend.data (), dataToSend.length ());

  NS_LOG_LOGIC ("Packet(" << p.pdcpPdu->GetSize () << ")");
  Simulator::Schedule (time, &LteRlcSapProvider::TransmitPdcpPdu, m_rlcSapProvider, p);
}

/////////////////////////////////////////////////////////////////////

TypeId
LteTestMac::GetTypeId (void)
{
  static TypeId tid = TypeId ("ns3::LteTestMac")
    .SetParent<Object> ()
    .AddConstructor<LteTestMac> ()
    ;

  return tid;
}

LteTestMac::LteTestMac ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
  m_device = 0;
  m_macSapProvider = new EnbMacMemberLteMacSapProvider<LteTestMac> (this);
  m_macSapUser = 0;
  m_macLoopback = 0;
  m_pdcpHeaderPresent = false;
  m_rlcHeaderType = UM_RLC_HEADER;
  m_txOpportunityMode = MANUAL_MODE;
  m_txOppTime = Seconds (0.001);
  m_txOppSize = 0;

  m_txPdus = 0;
  m_txBytes = 0;
  m_rxPdus = 0;
  m_rxBytes = 0;

//   m_cmacSapProvider = new EnbMacMemberLteEnbCmacSapProvider (this);
//   m_schedSapUser = new EnbMacMemberFfMacSchedSapUser (this);
//   m_cschedSapUser = new EnbMacMemberFfMacCschedSapUser (this);
//   m_enbPhySapUser = new EnbMacMemberLteEnbPhySapUser (this);
}

LteTestMac::~LteTestMac ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
}

void
LteTestMac::DoDispose ()
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
  delete m_macSapProvider;
//   delete m_cmacSapProvider;
//   delete m_schedSapUser;
//   delete m_cschedSapUser;
//   delete m_enbPhySapUser;

  m_device = 0;
}

void
LteTestMac::SetDevice (Ptr<NetDevice> device)
{
  m_device = device;
}

void
LteTestMac::SetLteMacSapUser (LteMacSapUser* s)
{
  m_macSapUser = s;
}

LteMacSapProvider*
LteTestMac::GetLteMacSapProvider (void)
{
  return m_macSapProvider;
}

void
LteTestMac::SetLteMacLoopback (Ptr<LteTestMac> s)
{
  m_macLoopback = s;
}

std::string
LteTestMac::GetDataReceived (void)
{
  // NS_LOG_FUNCTION (this); // Removed due to compiler ambiguity
  return m_receivedData;
}

// Stats
uint32_t
LteTestMac::GetTxPdus (void)
{
  NS_LOG_FUNCTION (m_txPdus);
  return m_txPdus;
}

uint32_t
LteTestMac::GetTxBytes (void)
{
  NS_LOG_FUNCTION (m_txBytes);
  return m_txBytes;
}

uint32_t
LteTestMac::GetRxPdus (void)
{
  NS_LOG_FUNCTION (m_rxPdus);
  return m_rxPdus;
}

uint32_t
LteTestMac::GetRxBytes (void)
{
  NS_LOG_FUNCTION (m_rxBytes);
  return m_rxBytes;
}


void
LteTestMac::SendTxOpportunity (Time time, uint32_t bytes)
{
  NS_LOG_FUNCTION (time << bytes);
  Simulator::Schedule (time, &LteMacSapUser::NotifyTxOpportunity, m_macSapUser, bytes, 0);
  if (m_txOpportunityMode == RANDOM_MODE)
  {
    if (m_txOppTime != Seconds (0))
    {
      Simulator::Schedule (m_txOppTime, &LteTestMac::SendTxOpportunity, this, m_txOppTime, m_txOppSize);
    }
  }
}

void
LteTestMac::SetPdcpHeaderPresent (bool present)
{
  NS_LOG_FUNCTION (present);
  m_pdcpHeaderPresent = present;
}

void
LteTestMac::SetRlcHeaderType (uint8_t rlcHeaderType)
{
  NS_LOG_FUNCTION (rlcHeaderType);
  m_rlcHeaderType = rlcHeaderType;
}

void
LteTestMac::SetTxOpportunityMode (uint8_t mode)
{
  NS_LOG_FUNCTION ((uint32_t)mode);
  m_txOpportunityMode = mode;

  if (m_txOpportunityMode == RANDOM_MODE)
    {
      if (m_txOppTime != Seconds (0.0))
        {
          SendTxOpportunity (m_txOppTime, m_txOppSize);
        }
    }
}

void
LteTestMac::SetTxOppTime (Time txOppTime)
{
  NS_LOG_FUNCTION (txOppTime);
  m_txOppTime = txOppTime;
}

void
LteTestMac::SetTxOppSize (uint32_t txOppSize)
{
  NS_LOG_FUNCTION (txOppSize);
  m_txOppSize = txOppSize;
}


/**
 * MAC SAP
 */

void
LteTestMac::DoTransmitPdu (LteMacSapProvider::TransmitPduParameters params)
{
  NS_LOG_FUNCTION (params.pdu->GetSize ());

  m_txPdus++;
  m_txBytes += params.pdu->GetSize ();

  if (m_device)
    {
      m_device->Send (params.pdu, m_device->GetBroadcast (), 0);
    }
  else if (m_macLoopback)
    {
      Simulator::Schedule (Seconds (0.1), &LteMacSapUser::ReceivePdu,
                           m_macLoopback->m_macSapUser, params.pdu);
    }
  else
    {
      LtePdcpHeader pdcpHeader;

      if (m_rlcHeaderType == AM_RLC_HEADER)
        {
          // Remove AM RLC header
          LteRlcAmHeader rlcAmHeader;
          params.pdu->RemoveHeader (rlcAmHeader);
          NS_LOG_LOGIC ("AM RLC header: " << rlcAmHeader);
        }
      else // if (m_rlcHeaderType == UM_RLC_HEADER)
        {
          // Remove UM RLC header
          LteRlcHeader rlcHeader;
          params.pdu->RemoveHeader (rlcHeader);
          NS_LOG_LOGIC ("UM RLC header: " << rlcHeader);
        }

      // Remove PDCP header, if present
      if (m_pdcpHeaderPresent)
        {
          params.pdu->RemoveHeader (pdcpHeader);
          NS_LOG_LOGIC ("PDCP header: " << pdcpHeader);
        }

      // Copy data to a string
      uint32_t dataLen = params.pdu->GetSize ();
      uint8_t *buf = new uint8_t[dataLen];
      params.pdu->CopyData (buf, dataLen);
      m_receivedData = std::string ((char *)buf, dataLen);

      NS_LOG_LOGIC ("Data (" << dataLen << ") = " << m_receivedData);
      delete [] buf;
    }
}

void
LteTestMac::DoReportBufferStatus (LteMacSapProvider::ReportBufferStatusParameters params)
{
  NS_LOG_FUNCTION (params.txQueueSize << params.retxQueueSize << params.statusPduSize);

  if (m_txOpportunityMode == AUTOMATIC_MODE)
    {
      if (params.statusPduSize)
        {
          Simulator::Schedule (Seconds (0.1), &LteMacSapUser::NotifyTxOpportunity,
                               m_macSapUser, params.statusPduSize + 2, 0);
        }
      else if (params.txQueueSize)
        {
          Simulator::Schedule (Seconds (0.1), &LteMacSapUser::NotifyTxOpportunity,
                               m_macSapUser, params.txQueueSize + 2, 0);
        }
      else if (params.retxQueueSize)
        {
          Simulator::Schedule (Seconds (0.1), &LteMacSapUser::NotifyTxOpportunity,
                               m_macSapUser, params.retxQueueSize + 2, 0);
        }
    }
}


bool
LteTestMac::Receive (Ptr<NetDevice> nd, Ptr<const Packet> p, uint16_t protocol, const Address& addr)
{
  NS_LOG_FUNCTION (addr << protocol << p->GetSize ());

  m_rxPdus++;
  m_rxBytes += p->GetSize ();

  Ptr<Packet> packet = p->Copy ();
  m_macSapUser->ReceivePdu (packet);
  return true;
}

} // namespace ns3

