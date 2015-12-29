#!/usr/bin/env python3
###############################################################################
#
# The MIT License (MIT)
#
# Copyright (c) Tavendo GmbH
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
###############################################################################

import asyncio
from btspusher import Pusher
from btsbots.config import pusher_prefix
from pprint import pprint


class TradePusher(object):
    def __init__(self, account_id):
        self.account_id = account_id

    def onBill(self, *args, **kwargs):
        print(args, kwargs)

    def onProfile(self, *args, **kwargs):
        print("update profile:")
        pprint(args[0])

    def onTradeInfo(self, *args, **kwargs):
        print(args, kwargs)

    def onPrice(self, *args, **kwargs):
        print(args, kwargs)

    @asyncio.coroutine
    def _subscribe(self):
        topic_prefix = "%s.account.%s" % (pusher_prefix, self.account_id)
        yield from self.pusher.subscribe(self.onBill, "%s.bill" % topic_prefix)
        yield from self.pusher.subscribe(
            self.onProfile, "%s.profile" % topic_prefix)
        yield from self.pusher.subscribe(
            self.onTradeInfo, "%s.trade_info" % topic_prefix)
        topic = "%s.price" % (pusher_prefix)
        yield from self.pusher.subscribe(self.onPrice, topic)

    def run(self, loop):
        self.pusher = Pusher(loop)
        loop.run_until_complete(self._subscribe())

if __name__ == '__main__':
    import sys
    loop = asyncio.get_event_loop()
    trade_pusher = TradePusher(sys.argv[1])
    trade_pusher.run(loop)
    loop.run_forever()
    loop.close()
