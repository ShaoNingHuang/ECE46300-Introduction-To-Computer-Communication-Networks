# The code is subject to Purdue University copyright policies.
# DO NOT SHARE, DISTRIBUTE, OR POST ONLINE
#

import sys
from collections import defaultdict
from router import Router
from packet import Packet
from json import dumps, loads


class PQEntry:

    def __init__(self, addr, cost, next_hop):
        self.addr = addr
        self.cost = cost
        self.next_hop = next_hop

    def __lt__(self, other):
         return (self.cost < other.cost)

    def __eq__(self, other):
         return (self.cost == other.cost)


class LSrouter(Router):
    """Link state routing and forwarding implementation"""

    def __init__(self, addr, heartbeatTime):
        Router.__init__(self, addr, heartbeatTime)  # initialize superclass - don't remove
        self.graph = {} # A dictionary with KEY = router
                        # VALUE = a list of lists of all its neighbor routers/clients and the cost to each neighbor
                        # {router: [[neighbor_router_or_client, cost]]}
        self.graph[self.addr] = []
        """add your own class fields and initialization code here"""
        
        self.TimeStamp = 0
        self.TimeStampFromOthers = {}
        for port in self.links.keys():
            self.graph[self.addr].append([self.links[port].get_e2(self.addr), self.links[port].get_cost()])
        self.RoutingTable = {}

    def handlePacket(self, port, packet):
        """process incoming packet"""
        """parameters:
        port : the router port on which the packet was received
        packet : the received packet"""
        # default implementation sends packet back out the port it arrived
        # you should replace it with your implementation
        if packet.isData():
            if packet.dstAddr in self.RoutingTable.keys():
                self.send(self.RoutingTable[packet.dstAddr], packet)
            else:
                return
                
        elif packet.isControl():
            if packet.srcAddr in self.TimeStampFromOthers.keys():
                LSA = loads(packet.content)
                if LSA["TimeStamp"] > self.TimeStampFromOthers[packet.srcAddr]:
                    #Update graph
                    self.TimeStampFromOthers[packet.srcAddr] = LSA["TimeStamp"]
                    self.graph[packet.srcAddr] = [] 
                    for Neighbor in LSA.keys():
                       self.graph[packet.srcAddr].append([Neighbor, LSA[Neighbor]])
                    
                    #Flood Packet
                    for Port in self.links.keys():
                        if Port != port:
                            self.send(Port, packet)
                    
                    #Update Routing Table
                    self.Update_RoutingTable()
            else:
                LSA = loads(packet.content)
                self.TimeStampFromOthers[packet.srcAddr] = LSA["TimeStamp"]
                
                #Update graph
                self.graph[packet.srcAddr] = [] 
                for Neighbor in LSA.keys():
                   self.graph[packet.srcAddr].append([Neighbor, LSA[Neighbor]])
                
                #Flood Packet
                for Port in self.links.keys():
                    if Port != port:
                        self.send(Port, packet)
                
                #Update Routing Table
                self.Update_RoutingTable()
                
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
        for neighbor in self.graph[self.addr]:
            if neighbor[0] == endpoint:
                self.graph[self.addr].remove(neighbor)
        self.graph[self.addr].append([endpoint,cost])
        #Send LSA
        self.Send_LSA()
        #Update Routing Table
        self.Update_RoutingTable()
        
    def handleRemoveLink(self, port, endpoint):
        """an existing link has been removed from the router port. This information
        has already been updated in the "links" data structure in router.py. Implement any 
        routing/forwarding action that you might want to take under such a scenario"""
        """parameters:
        port : router port from which the link has been removed
        endpoint : the node at the other end of the removed link
        (this end of the link is self.addr)"""
        for neighbor in self.graph[self.addr]:
            if neighbor[0] == endpoint:
                self.graph[self.addr].remove(neighbor)
        #Send LSA
        self.Send_LSA()   
        #Update Routing Table
        self.Update_RoutingTable()
    
    def Send_LSA(self):
        LS = {}
        self.TimeStamp = self.TimeStamp + 1
        for Port in self.links.keys():
            Neighbor = self.links[Port].get_e2(self.addr)
            Cost = self.links[Port].get_cost()
            LS[Neighbor] = Cost
        LS["TimeStamp"] = self.TimeStamp
        LSA = dumps(LS)
        
        for Port in self.links.keys():
            Dst = self.links[Port].get_e2(self.addr)
            _LSA = Packet(Packet.CONTROL, self.addr, Dst, LSA)
            self.send(Port, _LSA)
   
    def Update_RoutingTable(self):
        Path = self.dijkstra()
        OutPort = ''
        for Entry in Path:
            for Port in self.links.keys():
                if self.links[Port].get_e2(self.addr) == Entry.next_hop:
                    OutPort = Port
                    self.RoutingTable[Entry.addr] = OutPort
    
    def handlePeriodicOps(self):
        """handle periodic operations. This method is called every heartbeatTime.
        You can change the value of heartbeatTime in the json file"""
        self.Send_LSA()
            
    def dijkstra(self):
        """An implementation of Dijkstra's shortest path algorithm.
        Operates on self.graph datastructure and returns the cost and next hop to
        each destination node in the graph as a List (finishedQ) of type PQEntry"""
        priorityQ = []
        finishedQ = [PQEntry(self.addr, 0, self.addr)]
        for neighbor in self.graph[self.addr]:
            priorityQ.append(PQEntry(neighbor[0], neighbor[1], neighbor[0]))
        priorityQ.sort(key=lambda x: x.cost)

        while len(priorityQ) > 0:
            dst = priorityQ.pop(0)
            finishedQ.append(dst)
            if not(dst.addr in self.graph.keys()):
                continue
            for neighbor in self.graph[dst.addr]:
                #neighbor already exists in finishedQ
                found = False
                for e in finishedQ:
                    if e.addr == neighbor[0]:
                        found = True
                        break
                if found:
                    continue
                newCost = dst.cost + neighbor[1]
                #neighbor already exists in priorityQ
                found = False
                for e in priorityQ:
                    if e.addr == neighbor[0]:
                        found = True
                        if newCost < e.cost:
                            e.cost = newCost
                            e.next_hop = dst.next_hop
                        break
                if not found:
                    priorityQ.append(PQEntry(neighbor[0], newCost, dst.next_hop))

                priorityQ.sort(key=lambda x: x.cost)

        return finishedQ

