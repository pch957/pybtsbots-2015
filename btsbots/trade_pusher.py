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


class TradePusher(object):
    def __init__(self, account_id, data=None):
        self.account_id = account_id
        if data:
            self.data = data
        else:
            self.data = {
                "tradeinfo": {}, "watchdog": [0, 0], "rate_usd": {},
                "profile": {}}

    def init_pusher(self, loop):
        self.future_pusher = asyncio.Future()
        self.pusher = Pusher(loop, co=self.__init_pusher)
        loop.run_until_complete(
            asyncio.wait_for(self.future_pusher, 999))

    def onBill(self, *args, **kwargs):
        billinfo = args[0]
        if billinfo["balance"] < 1.0:
            print("no balance, please recharge")
        else:
            print("bill info:", billinfo)
        self.data["bill"] = billinfo["balance"]

    def onProfile(self, *args, **kwargs):
        print("update profile:")
        print(args, kwargs)
        self.data["profile"] = args[0]

    def onTradeInfo(self, *args, **kwargs):
        self.data["tradeinfo"] = args[0]
        self.data["watchdog"][0] = kwargs["_time"]
        # print("got a trade info at time: ", kwargs["_time"])

    def onPrice(self, *args, **kwargs):
        self.data["rate_usd"] = args[0]
        self.data["watchdog"][1] = kwargs["_time"]
        # print("got a rate event at time: ", kwargs["_time"])

    @asyncio.coroutine
    def __init_pusher(self, pusher):
        topic_prefix = "%s.account.%s" % (pusher_prefix, self.account_id)
        yield from pusher.subscribe(self.onBill, "%s.bill" % topic_prefix)
        yield from pusher.subscribe(
            self.onProfile, "%s.profile" % topic_prefix)
        yield from pusher.subscribe(
            self.onTradeInfo, "%s.tradeinfo" % topic_prefix)
        topic = "%s.price" % (pusher_prefix)
        yield from pusher.subscribe(self.onPrice, topic)
        yield from self.__init_data(pusher)
        self.future_pusher.set_result(1)

    @asyncio.coroutine
    def __init_data(self, pusher):
        topic_prefix = "%s.account.%s" % (pusher_prefix, self.account_id)
        topic = "%s.bill" % topic_prefix
        _ret = yield from pusher.call("pusher.get_last", topic)
        if _ret:
            self.onBill(*_ret["args"], **_ret["kwargs"])
        topic = "%s.price" % (pusher_prefix)
        _ret = yield from pusher.call("pusher.get_last", topic)
        if _ret:
            self.onPrice(*_ret["args"], **_ret["kwargs"])
        topic = "%s.tradeinfo" % topic_prefix
        _ret = yield from pusher.call("pusher.get_last", topic)
        if _ret:
            self.onTradeInfo(*_ret["args"], **_ret["kwargs"])
        topic = "%s.profile" % topic_prefix
        _ret = yield from pusher.call("pusher.get_last", topic)
        if _ret:
            self.onProfile(*_ret["args"], **_ret["kwargs"])

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    trade_pusher = TradePusher("1.2.33015")
    trade_pusher.init_pusher(loop)
    loop.run_forever()
    loop.close()
