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

from bts.http_rpc import HTTPRPC
import asyncio
import time
from btsbots.trade_pusher import TradePusher
from btsbots.config import asset_info
import math
from pprint import pprint


class TradeBots(object):
    def __init__(self, config):
        self.data = {"tradeinfo": {}, "watchdog": [0, 0], "rate_usd": {}}
        self.account = config["account"]
        cli_wallet = config["cli_wallet"]
        self.password = cli_wallet["wallet_unlock"]
        self.rpc = HTTPRPC(
            cli_wallet["host"], cli_wallet["port"],
            cli_wallet["rpc_user"], cli_wallet["rpc_passwd"])
        self.custom = {}
        self.custom["addition_spread"] = config["addition_spread"]
        self.custom["threshold"] = config["threshold"]
        self.custom["price_factor"] = config["price_factor"]
        self.account_id = self.rpc.get_account(config["account"])["id"]
        self.trade_pusher = TradePusher(self.account_id, self.data)
        self.trade_pusher.cb_update_order = self.check_order
        self.trade_pusher.cb_cancel_order = self.cancel_order

    @asyncio.coroutine
    def watchdog(self):
        timeout = 60*30
        cycle = timeout/10
        while True:
            _timer = time.time()
            for timestamp in self.data["watchdog"]:
                if _timer - timestamp > timeout:
                    print("timeout, cancel all orders")
                    # todo
                    break
            yield from asyncio.sleep(cycle)

    def get_trade_price(self, _tradeinfo):
        if not _tradeinfo or not self.data["rate_usd"]:
            return {}
        trade_price = {}
        for base in _tradeinfo:
            alias = _tradeinfo[base]["alias"]
            _price, _spread_bid, _spread_ask = self.data["rate_usd"][alias]
            _factor_bid = _tradeinfo[base]["trade_factor"][0]/(
                (1+_spread_bid)*(1+self.custom["addition_spread"]))
            _factor_ask = _tradeinfo[base]["trade_factor"][1]*(
                (1+_spread_bid)*(1+self.custom["addition_spread"]))
            if base in self.custom["price_factor"]:
                _price *= self.custom["price_factor"][base]
            trade_price[base] = [_price, _factor_bid, _factor_ask]
        return trade_price

    def _check_price(
            self, trade_price, _tradeinfo,
            _market_price, _need_update, _need_balance, base, quote):
        _fa = trade_price[base][2]/trade_price[quote][1]
        _price_real = trade_price[base][0]/trade_price[quote][0]
        _price_sell = _price_real * _fa
        _market_price[(base, quote)] = _price_sell
        _quota = _tradeinfo[base]["sell_for"][quote]["quota"]
        if not _tradeinfo[base]["sell_for"][quote]["orders"]:
            if _quota:
                _need_update[(base, quote)] = _fa
                _need_balance[base][1] += _quota
            return
        for order_id in _tradeinfo[base]["sell_for"][quote]["orders"]:
            _price_now, _amount = _tradeinfo[base][
                "sell_for"][quote]["orders"][order_id]
            _need_balance[base][0] += _amount
            if _amount / _quota < 0.5:
                _need_update[(base, quote)] = _fa
                _need_balance[base][1] += _quota
                return
            _fa2 = _price_now / _price_real
            if math.fabs(_fa2/_fa-1) > self.custom["threshold"]:
                _need_update[(base, quote)] = _fa
                _need_balance[base][1] += _quota
                return
            if (quote, base) not in _need_update:
                return
            if _fa2 * _need_update[(quote, base)] <= 1.001:
                _need_update[(base, quote)] = _fa
                _need_balance[base][1] += _quota
                return

    def check_price(self, trade_price, _tradeinfo):
        _market_price = {}
        _need_update = {}
        _need_balance = {}
        for base in _tradeinfo:
            _need_balance[base] = [_tradeinfo[base]["balance"], 0]
            for quote in _tradeinfo[base]["sell_for"]:
                self._check_price(
                    trade_price, _tradeinfo, _market_price,
                    _need_update, _need_balance, base, quote)
            if not _need_balance[base][1]:
                del(_need_balance[base])
        for _market in _need_update:
            _need_update[_market] = _market_price[_market]
        return _need_update, _need_balance

    def _generate_order(self, base, _tradeinfo, need_update, need_balance):
        _ops = []
        if base == "BTS":
            need_balance[0] -= 5.0 / self.data["rate_usd"]["BTS"][0]
        if need_balance[1] >= need_balance[0]:
            scale = need_balance[0]/need_balance[1]
        else:
            scale = 1.0
        for quote in _tradeinfo[base]["sell_for"]:
            if (base, quote) not in need_update:
                continue
            for _id in _tradeinfo[base]["sell_for"][quote]["orders"]:
                _ops.append(self.build_cancel_order(_id))
            amount = scale*_tradeinfo[base]["sell_for"][quote]["quota"]
            price = need_update[(base, quote)]
            print(base, quote, price, amount)
            _ops.append(self.build_sell_order(base, quote, price, amount))
        return _ops

    def generate_order(self, _tradeinfo, need_update, need_balance):
        _ops = []
        for base in need_balance:
            _ops_base = self._generate_order(
                base, _tradeinfo, need_update, need_balance[base])
            if _ops_base:
                _ops.extend(_ops_base)
        return _ops

    def check_order(self):
        _tradeinfo = self.data["tradeinfo"]
        trade_price = self.get_trade_price(_tradeinfo)
        if not trade_price:
            return
        need_update, need_balance = self.check_price(trade_price, _tradeinfo)
        # print(need_update)
        print(need_balance)
        if not need_balance:
            return
        try:
            _ops = self.generate_order(_tradeinfo, need_update, need_balance)
        except Exception as e:
            print(e)
        if _ops:
            self.build_transaction(_ops)

    def build_cancel_order(self, order_id):
        _op_cancel = [2, {
            'fee_paying_account': self.account_id, 'order': order_id}]
        return _op_cancel

    def build_sell_order(self, base, quote, price, amount):
        _op_sell = [1, {
            'amount_to_sell': {
                'asset_id': asset_info[base]["id"],
                'amount': amount*10**asset_info[base]["precision"]},
            'min_to_receive': {
                'asset_id': asset_info[quote]["id"],
                'amount': amount*price*10**asset_info[quote]["precision"]},
            'seller': self.account_id}]
        return _op_sell

    def cancel_order(self):
        _tradeinfo = self.data["tradeinfo"]
        _ops = []
        for base in _tradeinfo:
            for quote in _tradeinfo[base]["sell_for"]:
                for order_id in _tradeinfo[base]["sell_for"][quote]["orders"]:
                    _op = self.build_cancel_order(order_id)
                    _ops.append(_op)
        self.build_transaction(_ops)

    def build_transaction(self, _ops):
        if not _ops:
            return
        wallet_was_unlocked = False

        if self.rpc.is_locked():
            wallet_was_unlocked = True
            self.rpc.unlock(self.password)
        handle = self.rpc.begin_builder_transaction()
        for _op in _ops:
            self.rpc.add_operation_to_builder_transaction(handle, _op)
        self.rpc.set_fees_on_builder_transaction(handle, "1.3.0")
        # pprint(self.rpc.sign_builder_transaction(handle, False))
        pprint(self.rpc.sign_builder_transaction(handle, True))
        if wallet_was_unlocked:
            self.rpc.lock()

    def run(self):
        loop = asyncio.get_event_loop()
        self.trade_pusher.init_pusher(loop)
        loop.create_task(self.watchdog())
        loop.run_forever()
        loop.close()
