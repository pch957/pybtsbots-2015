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
from prettytable import PrettyTable
# from pprint import pprint


class TradeBots(object):
    def __init__(self, config):
        self.cycle = 15  # run bots every 60 seconds
        self.isSim = False
        self.data = {
            "tradeinfo": {}, "watchdog": [0, 0], "rate_usd": {},
            "bill": 0.0, "profile": {}}
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
        self.last_table = ""

    def timeout(self, timer, _timeout):
        for timestamp in self.data["watchdog"]:
            if timer - timestamp > _timeout:
                print("timeout, cancel all orders")
                return True
        return False

    @asyncio.coroutine
    def task_bots(self):
        _timeout = 60*30
        while True:
            try:
                _timer = time.time()
                if self.timeout(_timer, _timeout):
                    self.cancel_order()
                elif self.data["bill"] < 0.0:
                    self.cancel_order()
                else:
                    self.check_order()
            except Exception as e:
                print("task bots error:", e)
            self.display_order()
            yield from asyncio.sleep(self.cycle)

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
                (1+_spread_ask)*(1+self.custom["addition_spread"]))
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
            if _amount < _quota*0.5 or _amount > _quota*2.0:
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
        for _market in _need_update:
            _need_update[_market] = _market_price[_market]
        return _need_update, _need_balance

    def _generate_order(self, base, _tradeinfo, need_update, need_balance):
        _ops = []
        if base == "BTS":
            need_balance[0] -= 5.0 / self.data["rate_usd"]["BTS"][0]
        if need_balance[1] > need_balance[0]:
            scale = need_balance[0]/need_balance[1]
        else:
            scale = 1.0
        for quote in _tradeinfo[base]["sell_for"]:
            if (base, quote) not in need_update:
                continue
            for _id in _tradeinfo[base]["sell_for"][quote]["orders"]:
                _ops.append(self.build_cancel_order(_id))
            amount = scale*_tradeinfo[base]["sell_for"][quote]["quota"]
            if amount <= 0.0:
                continue
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

    def _sim_trade(self, base, quote, _tradeinfo):
        print("============sim sell %s for %s============" % (base, quote))
        _factor1, _price1 = self._sim_trade_sell(base, _tradeinfo)
        _factor2, _price2 = self._sim_trade_buy(quote, _tradeinfo)
        _spread = _factor1 / _factor2 - 1.0
        _price = _price1/_price2
        print("so the final spread sell %s for %s is %.4f, price is %.8f" % (
            base, quote, _spread, _price))
        print()

    def _sim_trade_sell(self, asset, _tradeinfo):
        alias = _tradeinfo[asset]["alias"]
        _price, _spread1, _spread2 = self.data["rate_usd"][alias]
        _spread3 = self.custom["addition_spread"]
        _factor_weight = _tradeinfo[asset]["trade_factor"][1]
        _factor_custom = 1.0

        print("got %s's price is %.5f USD, with spread for sell: %.4f" % (
            asset, _price, _spread2))
        print("factor depend on weight is %.4f " % _factor_weight)
        print("custom adition spread is %.4f" % _spread3)
        if asset in self.custom["price_factor"]:
            _factor_custom = self.custom["price_factor"][asset]
            print("custom price factor is %.3f" % _factor_custom)
        _final_factor = (1+_spread2)*(1+_spread3)*_factor_weight
        _final_price = _price*_final_factor*_factor_custom
        print("so the final factor for sell %s is %.4f, price is %.4f" % (
            asset, _final_factor, _final_price))
        print()
        return _final_factor, _final_price

    def _sim_trade_buy(self, asset, _tradeinfo):
        alias = _tradeinfo[asset]["alias"]
        _price, _spread1, _spread2 = self.data["rate_usd"][alias]
        _spread3 = self.custom["addition_spread"]
        _factor_weight = _tradeinfo[asset]["trade_factor"][0]
        _factor_custom = 1.0

        print("got %s's price is %.5f USD, with spread for buy: %.4f" % (
            asset, _price, _spread1))
        print("factor depend on weight is %.4f " % _factor_weight)
        print("custom adition spread is %.4f" % _spread3)
        if asset in self.custom["price_factor"]:
            _factor_custom = self.custom["price_factor"][asset]
            print("custom price factor is %.3f" % _factor_custom)
        _final_factor = _factor_weight/((1+_spread1)*(1+_spread3))
        _final_price = _price*_final_factor*_factor_custom
        print("so the final factor for buy %s is %.4f, price is %.4f" % (
            asset, _final_factor, _final_price))
        print()
        return _final_factor, _final_price

    def sim_trade(self, _tradeinfo):
        if not _tradeinfo or not self.data["rate_usd"]:
            return {}
        for base in _tradeinfo:
            for quote in _tradeinfo[base]["sell_for"]:
                self._sim_trade(base, quote, _tradeinfo)

    def display_add_order(self, _t, _base, _quote):
        _market = "%s/%s" % (_quote, _base)
        _tradeinfo = self.data["tradeinfo"]
        a_base = _tradeinfo[_base]["alias"]
        a_quote = _tradeinfo[_quote]["alias"]
        bid_volume = bid_spread = bid_price = None
        ask_volume = ask_spread = ask_price = None
        real_price = self.data["rate_usd"][a_base][0]/self.data[
            "rate_usd"][a_quote][0]
        if _tradeinfo[_quote]["sell_for"][_base]["orders"]:
            _id = list(_tradeinfo[_quote]["sell_for"][_base]["orders"])[0]
            _order = _tradeinfo[_quote]["sell_for"][_base]["orders"][_id]
            bid_price, bid_volume = _order
            bid_volume = bid_volume * bid_price
            bid_price = 1/bid_price
            bid_spread = real_price/bid_price - 1.0
        if _tradeinfo[_base]["sell_for"][_quote]["orders"]:
            _id = list(_tradeinfo[_base]["sell_for"][_quote]["orders"])[0]
            _order = _tradeinfo[_base]["sell_for"][_quote]["orders"][_id]
            ask_price, ask_volume = _order
            ask_spread = ask_price/real_price - 1.0
        _row = [
            _market, bid_volume, bid_spread, bid_price,
            real_price, ask_price, ask_spread, ask_volume]
        for _index in range(1, len(_row)):
            if _row[_index]:
                _row[_index] = format(_row[_index], ".4g")
        _t.add_row(_row)

    def display_order(self):
        t = PrettyTable([
            "market", "bid volume", "bid spread", "bid price",
            "real price", "ask price", "ask spread", "ask volume"])
        t.align = 'r'
        t.border = True
        for _base, _quote in self.data["profile"]["market"]:
            self.display_add_order(t, _base, _quote)
        _table = t.get_string()
        if _table == self.last_table:
            return
        self.last_table = _table
        print(_table)

    def check_order(self):
        _tradeinfo = self.data["tradeinfo"]
        if self.isSim:
            self.sim_trade(_tradeinfo)
            return
        trade_price = self.get_trade_price(_tradeinfo)
        if not trade_price:
            return
        need_update, need_balance = self.check_price(trade_price, _tradeinfo)
        # print(need_update)
        # print(need_balance)
        if not need_update:
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
        if self.isSim:
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
        self.rpc.sign_builder_transaction(handle, True)
        if wallet_was_unlocked:
            self.rpc.lock()

    def run(self):
        loop = asyncio.get_event_loop()
        self.trade_pusher.init_pusher(loop)
        loop.create_task(self.task_bots())
        loop.run_forever()
        loop.close()
