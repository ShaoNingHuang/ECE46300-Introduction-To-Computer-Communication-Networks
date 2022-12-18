
import sys
from collections import defaultdict
from router import Router
from packet import Packet
from json import dumps, loads


class DVrouter(Router):
    """Distance vector routing and forwarding implementation"""

    def __init__(self, addr, heartbeatTime, infinity):
        Router.__init__(self, addr, heartbeatTime)  # initialize superclass - don't remove
        self.infinity = infinity
        """add your own class fields and initialization code here"""
        self.RoutingTable = {}
        self.LinkCostBackUp = {}
        self.RoutingTable[self.addr] = [self.addr, 0, self.addr]
        for Port in self.links.keys():
            Neighbor = self.links[Port].get_e2(self.addr)
            CostToNeighbor = self.links[Port].get_cost()
            self.RoutingTable[Neighbor] = [Neighbor, CostToNeighbor, Neighbor]
            self.LinkCostBackUp[Port] = CostToNeighbor
            
    def handlePacket(self, port, packet):
        """process incoming packet"""
        """parameters:
        port : the router port on which the packet was received
        packet : the received packet"""
        # default implementation sends packet back out the port it arrived
        # you should replace it with your implementation
        if packet.isData():
            if packet.dstAddr in self.RoutingTable.keys():
                for Port in self.links.keys():
                    if self.links[Port].get_e2(self.addr) == self.RoutingTable[packet.dstAddr][2]:
                        self.send(Port,packet)
            else:
                return
            
        elif packet.isControl:
            
            Advertisement = loads(packet.content)
            Updated = False
            for Dst in Advertisement.keys():
                if Dst in self.RoutingTable.keys():
                    #Case0
                    if Advertisement[Dst][2] != self.addr:
                        #Case1
                        if self.RoutingTable[Dst][2] == packet.srcAddr:                            
                            self.RoutingTable[Dst] = [Dst, Advertisement[Dst][1] + self.links[port].get_cost(), packet.srcAddr]
                            Updated = True
                        else:
                            #Case2
                            if self.links[port].get_cost() + Advertisement[Dst][1] < self.RoutingTable[Dst][1]:
                                self.RoutingTable[Dst] = [Dst, self.links[port].get_cost() + Advertisement[Dst][1], packet.srcAddr]
                                Updated = True
                                
                else:
                    if Advertisement[Dst][2] != self.addr:
                        self.RoutingTable[Dst] = [Dst, Advertisement[Dst][1] + self.links[port].get_cost(), packet.srcAddr]
                        Updated = True
                        
                #Count to Infinity
                if self.RoutingTable[Dst][1] >= self.infinity:
                    self.RoutingTable[Dst] = [Dst, self.infinity, None]
                    Updated = True
                    
            if Updated:
                Table = dumps(self.RoutingTable)
                for Port in self.links.keys():
                    Dst = self.links[Port].get_e2(self.addr)
                    Advertisement = Packet(Packet.CONTROL, self.addr, Dst, Table)
                    self.send(Port, Advertisement)
                

    def handleNewLink(self, port, endpoint, cost):
        """a new link has been added to router port and initialized, or an existing
        link cost has been updated. This information has already been updated in the
        "links" data structure in router.py. Implement any routing/forwarding action
        that you might want to take under such a scenario"""
        """parameters:
        port : router port of the new link / the existing link whose cost has been updated
        endpoint : the node at the other end of the new link / the exisitng link whose cost has been updated
        (this end of the link is self.addr)
        cost : cost of the new link / new cost of the exisitng link whose cost has been updated""" 
        #Set the entries whose next hop is endpoint to new cost      
        if endpoint in self.RoutingTable.keys():
            for Path in self.RoutingTable.values():
                if Path[2] == endpoint:
                    Path[1] = Path[1] - self.LinkCostBackUp[port] + cost
            #Update LinkCostBackUp
            self.LinkCostBackUp[port] = cost
                        
        else:
            self.RoutingTable[endpoint] = [endpoint, cost, endpoint]
            #Update LinkCostBackUp
            self.LinkCostBackUp[port] = cost
        
        Table = dumps(self.RoutingTable)
        for Port in self.links.keys():
            Dst = self.links[Port].get_e2(self.addr)
            Advertisement = Packet(Packet.CONTROL, self.addr, Dst, Table)
            self.send(Port, Advertisement) 
        
    def handleRemoveLink(self, port, endpoint):
        """an existing link has been removed from the router port. This information
        has already been updated in the "links" data structure in router.py. Implement any 
        routing/forwarding action that you might want to take under such a scenario"""
        """parameters:
        port : router port from which the link has been removed
        endpoint : the node at the other end of the removed link
        (this end of the link is self.addr)"""
        #Set the entries whose next hop is endpoint to infinity and null
        for Path in self.RoutingTable.values():
            if Path[2] == endpoint:
                Path[2] = None
                Path[1] = self.infinity 
        
        #Update LinkCostBackUp
        for Port,Cost in self.LinkCostBackUp.items():
            if Port != port:
                self.LinkCostBackUp[Port] = Cost
        
        #Send Advertisement
        Table = dumps(self.RoutingTable)
        for Port in self.links.keys():
            Dst = self.links[Port].get_e2(self.addr)
            Advertisement = Packet(Packet.CONTROL, self.addr, Dst, Table)
            self.send(Port, Advertisement)
           
    def handlePeriodicOps(self):
        """handle periodic operations. This method is called every heartbeatTime.
        You can change the value of heartbeatTime in the json file"""
        Table = dumps(self.RoutingTable)
        for Port in self.links.keys():
            Dst = self.links[Port].get_e2(self.addr)
            Advertisement = Packet(Packet.CONTROL, self.addr, Dst, Table)
            self.send(Port, Advertisement)