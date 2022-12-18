# The code is subject to Purdue University copyright policies.
# DO NOT SHARE, DISTRIBUTE, OR POST ONLINE
#

import sys
import time
from switch import Switch
from link import Link
from client import Client
from packet import Packet


class STPswitch(Switch):
    """STP, MAC learning and MAC forwarding implementation"""
    def __init__(self, addr, heartbeatTime):
        Switch.__init__(self, addr, heartbeatTime)  # initialize superclass - don't remove
        """add your own class fields and initialization code here"""
        self.ForwardingTable = {}

        self.View = [int(self.addr),0,int(self.addr),int(self.addr)]

        self.View = [int(self.addr), 0, int(self.addr), int(self.addr)] # [Root, Cost, Self, Nexthop]
    def handlePacket(self, port, packet):
        """process incoming packet"""
        # default implementation sends packet back out the port it arrived
        # you should replace it with your implementation
        #Data Forwarding
        Infinity = 20
        
        if packet.isData():
            if self.links[port].status != Link.INACTIVE:
                if packet.dstAddr =='X':    # Broadcast packet
                    for p, link in self.links.items():
                         if p != port and link.status != Link.INACTIVE:
                             self.send(p, packet)
                else:
                    if packet.dstAddr in self.ForwardingTable.keys():
                        # Drop the packet if port equal receiving port
                        self.ForwardingTable[packet.srcAddr] = port
                        if port != self.ForwardingTable[packet.dstAddr] and self.links[port].status != Link.INACTIVE:
                            self.send(self.ForwardingTable[packet.dstAddr], packet)
                    else:
                        self.ForwardingTable[packet.srcAddr] = port
                        for p, link in self.links.items():
                            if p != port and link.status != Link.INACTIVE:
                                self.send(p, packet)
            else:
                if packet.srcAddr in self.ForwardingTable.keys():
                    self.ForwardingTable = {dst : Port  for dst, Port in self.ForwardingTable.items() if Port != port }    
        elif packet.isControl():

            if int(packet.content[1]) >= Infinity:
                self.ForwardingTable = {dst : Port for dst,Port in self.ForwardingTable.items() if dst != packet.dstAddr}
                self.View[0] = int(self.addr)
                self.View[1] = 0
                self.View[2] = int(self.addr)
                self.View[3] = int(self.addr)
                Content = str(self.View[0]) + str(self.View[1]) + str(self.View[2]) + str(self.View[3])
                for Ports in self.links.keys():
                    View = Packet(Packet.CONTROL,self.addr,self.links[Ports].get_e2(self.addr),Content)
                    self.send(Ports,View)
                return
         #Handle Control Packet to perform STP            
      
            if int(packet.content[3]) != int(self.addr):
                # Case 1
                if int(packet.content[2]) == self.View[3]:
                      if int(packet.content[0]) < self.View[2]:
                          self.View[0] = int(packet.content[0])
                          self.View[1] = int(packet.content[1]) + int(self.links[port].get_cost())
                          Content = str(self.View[0]) + str(self.View[1]) + str(self.View[2]) + str(self.View[3])
                          for Ports in self.links.keys():
                              View = Packet(Packet.CONTROL,self.addr, self.links[Ports].get_e2(self.addr),Content)
                              self.send(Ports, View)
                          
                      else:
                          self.View[0] = int(self.addr)
                          self.View[1] = 0
                          self.View[3] = int(self.addr)
                          Content = str(self.View[0]) + str(self.View[1]) + str(self.View[2]) + str(self.View[3])
                          for Ports in self.links.keys():
                              View = Packet(Packet.CONTROL, self.addr,self.links[Ports].get_e2(self.addr), Content)
                              self.send(Ports, View)
               # Case 2
                
               
                else:
                    if int(packet.content[0]) < self.View[0]:
                        self.View[0] = int(packet.content[0])
                        self.View[1] = int(packet.content[1]) + int(self.links[port].get_cost())
                        self.View[3] = int(packet.content[2])
                        self.links[port].status = Link.ACTIVE
                        Content = str(self.View[0]) + str(self.View[1]) + str(self.View[2]) + str(self.View[3])
                        for Ports in self.links.keys():
                            View = Packet(Packet.CONTROL,self.addr,self.links[Ports].get_e2(self.addr),Content)
                            self.send(Ports,View)
                    elif int(packet.content[0]) == self.View[0] and (int(self.links[port].get_cost()) + int(packet.content[1])) < self.View[1]:
                        self.View[1] = int(self.links[port].get_cost()) + int(packet.content[1])
                        self.View[3] = int(packet.content[2])
                        self.links[port].status = Link.ACTIVE
                        Content = str(self.View[0]) + str(self.View[1]) + str(self.View[2]) + str(self.View[3])
                        for Ports in self.links.keys():
                            View = Packet(Packet.CONTROL,self.addr,self.links[Ports].get_e2(self.addr),Content)
                            self.send(Ports,View)
                    elif int(packet.content[0]) == self.View[0] and (int(self.links[port].get_cost()) + int(packet.content[1])) == self.View[1] and int(packet.content[2]) < int(self.View[3]):
                        self.View[3] = int(packet.content[2])
                        self.links[port].status = Link.ACTIVE
                        Content = str(self.View[0]) + str(self.View[1]) + str(self.View[2]) + str(self.View[3])
                        for Ports in self.links.keys():
                            View = Packet(Packet.CONTROL,self.addr,self.links[Ports].get_e2(self.addr),Content)
                            self.send(Ports,View)
            
            
            if(self.View[3] != int(packet.content[2]) and int(packet.content[3]) != int(self.addr)):
                self.links[port].status = Link.INACTIVE
                self.ForwardingTable ={dst : Port for dst,Port in self.links.items() if Port != port}
            else:
                self.links[port].status = Link.ACTIVE
    def handleNewLink(self, port, endpoint, cost):
        """a new link has been added to switch port and initialized, or an existing
        link cost has been updated. Implement any routing/forwarding action that
        you might want to take under such a scenario"""
        
        self.links[port].status = Link.ACTIVE
        self.ForwardingTable[endpoint] = port







    def handleRemoveLink(self, port, endpoint):
        """an existing link has been removed from the switch port. Implement any 
        routing/forwarding action that you might want to take under such a scenario"""
        
        self.ForwardingTable = {dst : Port for dst,Port in self.links.items() if Port != port}
        
        
    def handlePeriodicOps(self):
        """handle periodic operations. This method is called every heartbeatTime.
        You can change the value of heartbeatTime in the json file"""
        Content = str(self.View[0]) + str(self.View[1]) + str(self.View[2]) + str(self.View[3])
        for Ports in self.links.keys():
            View = Packet(Packet.CONTROL,self.addr,self.links[Ports].get_e2(self.addr),Content)
            self.send(Ports,View)
            
                        

