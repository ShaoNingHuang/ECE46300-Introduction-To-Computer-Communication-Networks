# The code is subject to Purdue University copyright policies.
# DO NOT SHARE, DISTRIBUTE, OR POST ONLINE
#

import sys
import threading
import json
import pickle
import signal
import time
import os.path
import queue
from collections import defaultdict
from client import Client
from link import Link
from switch import Switch
from STPswitch import STPswitch


class Network:
    """Network class maintains all clients, switches, links, and confguration"""

    def __init__(self, netJsonFilepath, switchClass):
        """Create a new network from the parameters in the file at
           netJsonFilepath. switchClass determines whether to use STPswitch,
           or the default switch"""

        # parse configuration details
        netJsonFile = open(netJsonFilepath, 'r')
        netJson = json.load(netJsonFile)
        self.latencyMultiplier = 100
        self.heartbeatTime = netJson["heartbeatTime"] * self.latencyMultiplier
        self.endTime = netJson["endTime"] * self.latencyMultiplier
        self.clientSendRate = netJson["clientSendRate"]*self.latencyMultiplier

        # parse and create switches, clients, and links
        self.switches = self.parseswitches(netJson["switches"], switchClass)
        self.clients = self.parseClients(netJson["clients"], self.clientSendRate)
        self.links = self.parseLinks(netJson["links"])

        # parse link changes
        if "changes" in netJson:
            self.changes = self.parseChanges(netJson["changes"])
        else:
            self.changes = None

        # parse correct routes and create some tracking fields
        self.threads = []
        self.routes = {}
        self.broadcastRoutes = {}
        self.correctRoutes = self.parseCorrectRoutes(netJson["correctRoutes"])
        #self.routesLock = thread.allocate_lock()
        self.routesLock = threading.Lock()
        netJsonFile.close()


    def parseswitches(self, switchParams, switchClass):
        """Parse switches from switchParams dict"""
        switches = {}
        for addr in switchParams:
            switches[addr] = switchClass(addr, self.heartbeatTime)
        return switches


    def parseClients(self, clientParams, clientSendRate):
        """Parse clients from clientParams dict"""
        clients = {}
        for addr in clientParams:
            clients[addr] = Client(addr, clientParams, clientSendRate, self.updateRoute, self.updateBroadcastRoute)
        return clients


    def parseLinks(self, linkParams):
        """Parse links from linkParams dict"""
        links = {}
        for addr1, addr2, p1, p2, c in linkParams:
            link = Link(addr1, addr2, c, self.latencyMultiplier)
            links[(addr1,addr2)] = (p1, p2, c, link)
        return links


    def parseChanges(self, changesParams):
        """Parse link changes from changesParams dict"""
        changes = queue.PriorityQueue()
        for change in changesParams:
            changes.put(change)
        return changes


    def parseCorrectRoutes(self, routesParams):
        """parse correct routes, from routesParams dict"""
        correctRoutes = defaultdict(list)
        for route in routesParams:
            src, dst = route[0], route[-1]
            correctRoutes[(src,dst)].append(route)
            self.routes[(src,dst)] = ([], False, -1)
            self.broadcastRoutes[(src,dst)] = ([], False, -1)
        return correctRoutes


    def run(self):
        """Run the network.  Start threads for each client and switch. Start
           thread to track link changes.  Wait until
           end time and then print final output"""
        for switch in self.switches.values():
            thread = switch_thread(switch)
            thread.start()
            self.threads.append(thread)
        for client in self.clients.values():
            thread = client_thread(client)
            thread.start()
            self.threads.append(thread)
        self.addLinks()
        if self.changes:
            self.handleChangesThread = handle_changes_thread(self)
            self.handleChangesThread.start()
        signal.signal(signal.SIGINT, self.handleInterrupt)
        time.sleep(self.endTime/float(1000))
        self.finalRoutes()
        broadcastRoutesString = self.getBroadcastRouteString()[0]
        broadcastRoutesCorrect = self.getBroadcastRouteString()[1]
        sys.stdout.write("\nRoutes taken by broadcast packets")
        sys.stdout.write("\n"+broadcastRoutesString+"\n")
        sys.stdout.write("Routes taken by unicast packets")
        sys.stdout.write("\n"+self.getRouteString(broadcastRoutesCorrect)+"\n")
        self.joinAll()


    def addLinks(self):
        """Add links to clients and switches"""
        for addr1, addr2 in self.links:
            p1, p2, c, link = self.links[(addr1, addr2)]
            if addr1 in self.clients:
                self.clients[addr1].changeLink(("add", link))
            if addr2 in self.clients:
                self.clients[addr2].changeLink(("add", link))
            if addr1 in self.switches:
                self.switches[addr1].changeLink(("add", p1, addr2, link, c))
            if addr2 in self.switches:
                self.switches[addr2].changeLink(("add", p2, addr1, link, c))


    def handleChanges(self):
        """Handle changes to links. Run this method in a separate thread.
           Uses a priority queue to track time of next change"""
        startTime = time.time()*1000
        while not self.changes.empty():
            changeTime, target, change = self.changes.get()
            currentTime = time.time()*1000
            waitTime = (changeTime*self.latencyMultiplier + startTime) - currentTime
            if waitTime > 0:
                time.sleep(waitTime/float(1000))
            # link changes
            if change == "up":
                addr1, addr2, p1, p2, c = target
                link = Link(addr1, addr2, c, self.latencyMultiplier)
                self.links[(addr1,addr2)] = (p1, p2, c, link)
                self.switches[addr1].changeLink(("add", p1, addr2, link, c))
                self.switches[addr2].changeLink(("add", p2, addr1, link, c))
            elif change == "down":
                addr1, addr2, = target
                p1, p2, _, link = self.links[(addr1, addr2)]
                self.switches[addr1].changeLink(("remove", p1))
                self.switches[addr2].changeLink(("remove", p2))


    def updateRoute(self, src, dst, route, seqNum):
        """Callback function used by clients to update the
           current routes taken by DATA packets"""
        self.routesLock.acquire()
        isGood = route in self.correctRoutes[(src,dst)]
        if (not route) and (not self.correctRoutes[(src,dst)]):
            isGood = True
        self.routes[(src,dst)] = (route, isGood, seqNum)
        self.routesLock.release()


    def updateBroadcastRoute(self, src, dst, route, seqNum):
        """Callback function used by clients to update the
           current routes taken by DATA packets"""
        self.routesLock.acquire()
        isGood = route in self.correctRoutes[(src,dst)]
        if (not route) and (not self.correctRoutes[(src,dst)]):
            isGood = True
        self.broadcastRoutes[(src,dst)] = (route, isGood, seqNum)
        self.routesLock.release()


    def getRouteString(self, broadcastRoutesCorrect, labelIncorrect=True):
        """Create a string with all the current routes found by DATA
           packets and whether they are correct"""
        self.routesLock.acquire()
        routeStrings = []
        allCorrect = True
        for src,dst in self.routes:
            route, isGood, _ = self.routes[(src,dst)]
            routeStrings.append("{} -> {}: {} {}".format(src, dst, route,
                "" if (isGood or not labelIncorrect) else "Incorrect Route"))
            if not isGood:
                allCorrect = False
        routeStrings.sort()
        if allCorrect and len(self.routes) > 0 and broadcastRoutesCorrect:
            routeStrings.append("\nSUCCESS: All routes are correct!\n")
        else:
            routeStrings.append("\nFAILURE: Not all routes are correct\n")
        routeString = "\n".join(routeStrings)
        self.routesLock.release()
        return routeString


    def getBroadcastRouteString(self, labelIncorrect=True):
        """Create a string with all the current routes found by DATA
           packets and whether they are correct"""
        self.routesLock.acquire()
        routeStrings = []
        allCorrect = True
        for src,dst in self.broadcastRoutes:
            route, isGood, _ = self.broadcastRoutes[(src,dst)]
            routeStrings.append("{} -> {}: {} {}".format(src, dst, route,
                "" if (isGood or not labelIncorrect) else "Incorrect Route"))
            if not isGood:
                allCorrect = False
        routeStrings.sort()
        if allCorrect and len(self.broadcastRoutes) > 0:
            allCorrect = True
        else:
            allCorrect = False
        routeString = "\n".join(routeStrings)
        self.routesLock.release()
        return (routeString, allCorrect)


    def getRoutePickle(self):
        """Create a pickle with the current routes
           found by DATA packets"""
        self.routesLock.acquire()
        routePickle = pickle.dumps(self.routes)
        self.routesLock.release()
        return routePickle


    def clearQueues(self):
        for addr1,addr2 in self.links:
            _, _, _, link = self.links[(addr1,addr2)]
            while not link.q12.empty():
                link.q12.get_nowait()
            while not link.q21.empty():
                link.q21.get_nowait()


    def finalRoutes(self):
        """Have the clients send one final batch of DATA packets"""
        self.clearQueues()
        for client in self.clients.values():
            client.lastSend()
        time.sleep(30)


    def joinAll(self):
        if self.changes:
            self.handleChangesThread.join()
        for thread in self.threads:
            thread.join()


    def handleInterrupt(self, signum, _):
        self.joinAll()
        quit()



def main():
    """Main function parses command line arguments and runs network"""
    if len(sys.argv) < 2:
        sys.stdout.write("Usage: python network.py [networkSimulationFile.json]\n")
        return
    netCfgFilepath = sys.argv[1]
    switchClass = STPswitch
    net = Network(netCfgFilepath, switchClass)
    net.run()
    return

# Extensions of threading.Thread class

class switch_thread(threading.Thread):

    def __init__(self, switch):
        threading.Thread.__init__(self)
        self.switch = switch

    def run(self):
        self.switch.runSwitch()

    def join(self, timeout=None):
        self.switch.keepRunning = False
        super(switch_thread, self).join(timeout)

class client_thread(threading.Thread):

    def __init__(self, client):
        threading.Thread.__init__(self)
        self.client = client

    def run(self):
        self.client.runClient()

    def join(self, timeout=None):
        self.client.keepRunning = False
        super(client_thread, self).join(timeout)

class handle_changes_thread(threading.Thread):

    def __init__(self, network):
        threading.Thread.__init__(self)
        self.network = network

    def run(self):
        self.network.handleChanges()


if __name__ == "__main__":
    main()
