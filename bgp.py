from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import lg, info, setLogLevel
from mininet.util import dumpNodeConnections, quietRun, moveIntf
from mininet.cli import CLI
from mininet.node import Switch, OVSKernelSwitch

from subprocess import Popen, PIPE, check_output
from time import sleep, time
from multiprocessing import Process
from argparse import ArgumentParser

import sys
import os
import termcolor as T
import time


"""
С Т А Р Т   П Р О Г Р А М М Ы
Д О К У М Е Н Т А Ц И Я 
http://mininet.org/api/annotated.html
"""
"""
В этой программе мы:
1) создаем сеть
2) создаем host 
3) добавляем routers
4) настраиваем связь между host и routers
5) запускаем веб - сервер
"""

setLogLevel('info')
parser = ArgumentParser("Configure simple BGP network in Mininet.")
parser.add_argument('--rogue', action="store_true", default=False)
parser.add_argument('--sleep', default=3, type=int)
args = parser.parse_args()

FLAGS_rogue_as = args.rogue
"номер коммутатора, за которым будет скрываться злоумышленние"
ROGUE_AS_NAME = 'R4'

def log(s, col="green"):
    print(T.colored(s, col))

class Router(Switch):
    """
    Определяет новый маршрутизатор, который находится внутри сетевого пространства имен, чтобы
    отдельные записи маршрутизации не сталкивались.
    """
    ID = 0
    def __init__(self, name, **kwargs):
        kwargs['inNamespace'] = True
        Switch.__init__(self, name, **kwargs)
        Router.ID += 1
        self.switch_id = Router.ID

    @staticmethod
    def setup():
        return

    def start(self, controllers):
        pass

    def stop(self):
        self.deleteIntfs()

    def log(self, s, col="magenta"):
        print(T.colored(s, col))


class SimpleTopo(Topo):
    """
    Топология автономной системы представляет собой простую прямолинейную топологию
    между AS1 - AS2 - AS3. Мошенник AS (AS4) подключается к AS 1 напрямую.
    """
    def __init__(self):
        super(SimpleTopo, self ).__init__()
        num_hosts_per_as = 3
        num_ases = 3
        num_hosts = num_hosts_per_as * num_ases
        # Топология имеет один маршрутизатор на AS

	routers = []
        for i in xrange(num_ases):
            router = self.addSwitch('R%d' % (i+1))
	    routers.append(router)
        hosts = []
        for i in xrange(num_ases):
            router = 'R%d' % (i+1)
            for j in xrange(num_hosts_per_as):
                hostname = 'h%d-%d' % (i+1, j+1)
                host = self.addNode(hostname)
                hosts.append(host)
                self.addLink(router, host)

        for i in xrange(num_ases-1):
            self.addLink('R%d' % (i+1), 'R%d' % (i+2))

        routers.append(self.addSwitch('R4'))
        for j in xrange(num_hosts_per_as):
            hostname = 'h%d-%d' % (4, j+1)
            host = self.addNode(hostname)
            hosts.append(host)
            self.addLink('R4', hostname)
        "Это должно быть добавлено в конце"
        self.addLink('R1', 'R4')
        return


def getIP(hostname):
    AS, idx = hostname.replace('h', '').split('-')
    AS = int(AS)
    if AS == 4:
        AS = 3
    ip = '%s.0.%s.1/24' % (10+AS, idx)
    return ip


def getGateway(hostname):
    AS, idx = hostname.replace('h', '').split('-')
    AS = int(AS)
    # Это условие дает AS4 тот же диапазон IP, что и AS3, так что это может быть
    # нападающий.
    if AS == 4:
        AS = 3
    gw = '%s.0.%s.254' % (10+AS, idx)
    return gw


def startWebserver(net, hostname, text="Default web server"):
    """Запуск сервера"""
    host = net.getNodeByName(hostname)
    return host.popen("python webserver.py --text '%s'" % text, shell=True)


def main():
    os.system("rm -f /tmp/R*.log /tmp/R*.pid logs/*")
    os.system("mn -c >/dev/null 2>&1")
    os.system("killall -9 zebra bgpd > /dev/null 2>&1")
    os.system('pgrep -f webserver.py | xargs kill -9')

    net = Mininet(topo=SimpleTopo(), switch=Router)
    net.start()
    for router in net.switches:
        router.cmd("sysctl -w net.ipv4.ip_forward=1")
        router.waitOutput()

    log("Waiting %d seconds for sysctl changes to take effect..."
        % args.sleep)
    sleep(args.sleep)

    for router in net.switches:
        if router.name == ROGUE_AS_NAME and not FLAGS_rogue_as:
            continue

        log("Starting zebra and bgpd on %s" % router.name)

    for host in net.hosts:
        host.cmd("ifconfig %s-eth0 %s" % (host.name, getIP(host.name)))
        host.cmd("route add default gw %s" % (getGateway(host.name)))

    log("Starting web servers", 'yellow')
    startWebserver(net, 'h3-1', "Default web server")
    startWebserver(net, 'h4-1', "*** Attacker web server ***")

    CLI(net)
    net.stop()
    os.system("killall -9 zebra bgpd")
    os.system('pgrep -f webserver.py | xargs kill -9')


if __name__ == "__main__":
    main()
