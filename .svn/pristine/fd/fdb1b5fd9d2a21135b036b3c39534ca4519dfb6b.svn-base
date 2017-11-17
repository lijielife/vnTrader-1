# encoding: utf-8

from vnrpc import RpcClient
from threading import Timer

class AppClient(RpcClient):
    def __init__(self, reqAddress, subAddress):
        super(AppClient, self).__init__(reqAddress, subAddress)
        self.usePickle()



#----------------------------------------------------
def main():
    reqAddress = 'tcp://localhost:2017'
    subAddress = 'tcp://localhost:0616'
    client = AppClient(reqAddress, subAddress)
    client.start()

    def timeoutHandler():
        client.initStrategy()
        client.startStrategy()

    t = Timer(60, timeoutHandler)
    t.start()

    while True:
        cmd = raw_input('> ')
        if cmd == 'start':
            t.cancel()
            client.initStrategy()
            client.startStrategy()
            
        elif cmd == 'change':
            arg_name = raw_input('Input parameter name:')
            arg_value = input('Input value:')
            d = {arg_name : arg_value}
            client.changeParameters(u'Hedge', d)

        elif cmd == 'stop':
            client.stopStrategy()

        elif cmd == 'exit':
            try:
                client.stopStrategy()
                client.quit()
            except Exception, e:
                print e
            break
    print 'exit from strategy'
    client.stop()

if __name__ == '__main__':
    main()
    