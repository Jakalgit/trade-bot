from time import sleep

import telebot
import asyncio
import json
from binance.client import Client
from termcolor import colored
import websockets
from tensorflow import keras
from ta.momentum import RSIIndicator
import pandas as pd

TOKEN_BOT = "5669115775:AAGNYvbBer4Sc9g15l4Q-eE8aLUm_TKLrjQ"
TICKER = 'BTCTUSD'
api_key = 'tqbGB3Te2GS7dc8IcJMXWoSPBQxjwW3PbzwRocGSN9Ugt0y8mQ9fxy9GzOEL26hw'
api_secret = 'sV03zCztEmookHEtCyLUSx8ImIbx2gbIrrbzOselyqdaPqzYvkrbNQEu8ZYyK0KN'

streams = ["%s@kline_15m" % (TICKER.lower())]

model = keras.models.load_model('C:/Users/Cydia/Desktop/model_TUSD_15min')
bot = telebot.TeleBot(TOKEN_BOT)


def normalize_values(array, res_v):
    res = []
    max_v = max(array)
    min_v = min(array)
    for i in range(0, len(array)):
        res.append((array[i] - min_v) / (max_v - min_v))
    res_v = (res_v - min_v) / (max_v - min_v)
    return res, res_v


def transform_data(array):
    close = []
    vol = []
    opn = []
    high = []
    low = []
    for i in range(0, len(array)):
        opn.append(float(array[i][1]))
        high.append(float(array[i][2]))
        low.append(float(array[i][3]))
        close.append(float(array[i][4]))
        vol.append(float(array[i][5]))
    return opn, high, low, close, vol


def get_last_values(array, count):
    result = []
    for i in range(count, 0, -1):
        result.append(array[-i])
    return result


def get_margin_balance(client):
    margin_account_info = client.get_margin_account()
    asset_name = 'TUSD'
    for asset in margin_account_info['userAssets']:
        if asset['asset'] == asset_name:
            tusd_balance = float(asset['free'])
            return tusd_balance


def loading_fill(order, client, message):
    timer = 0
    delay = 0.1
    time = 240 # секунды
    origQty = order['origQty']
    while True:
        order_status = client.get_order(symbol=TICKER, orderId=order['orderId'])
        if order_status['status'] == Client.ORDER_STATUS_FILLED:
            print(message)
            break
        sleep(delay)
        timer += 1
        if timer >= time / delay:
            order_info = client.get_order(symbol=TICKER, orderId=order['orderId'])
            if order_info['status'] != 'FILLED':
                client.cancel_order(symbol=TICKER, orderId=order['orderId'])
                remaining_quantity = float(order_info['origQty']) - float(order_info['executedQty'])
                if remaining_quantity > 0:
                    print("Выполение по маркету.")
                    order = client.create_margin_order(
                        symbol=TICKER,
                        side=order_info['side'],
                        type=Client.ORDER_TYPE_MARKET,
                        quantity=remaining_quantity
                    )
                    while True:
                        order_status = client.get_order(symbol=TICKER, orderId=order['orderId'])
                        if order_status['status'] == Client.ORDER_STATUS_FILLED:
                            print(message)
                            break
            break
    order['origQty'] = origQty
    return order


async def subscribe_to_stream():
    url = "wss://stream.binance.com:9443/stream?streams="
    async with websockets.connect(url) as websocket:
        subscribe_request = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1,
        }
        await websocket.send(json.dumps(subscribe_request))

        response = json.loads(await websocket.recv())
        print(response)

        client = Client(api_key, api_secret, testnet=False)

        rate = 14.0  # USD
        time = -1
        order = None
        min_value = 32
        data = client.get_historical_klines(TICKER, Client.KLINE_INTERVAL_15MINUTE, "1 day ago UTC")
        start_balance = get_margin_balance(client)
        opens, highs, lows, closes, volumes = transform_data(data)
        async for message in websocket:
            data = json.loads(message)
            next_time = data.get('data', {}).get('k', {}).get('t')
            if time == -1:
                time = next_time
            if time != next_time:
                print("Обнаружена новая свеча")
                last_close = float(data.get('data', {}).get('k', {}).get('c'))
                last_open = float(data.get('data', {}).get('k', {}).get('o'))
                last_high = float(data.get('data', {}).get('k', {}).get('h'))
                last_low = float(data.get('data', {}).get('k', {}).get('l'))
                last_volume = float(data.get('data', {}).get('k', {}).get('v'))
                closes.append(last_close)
                opens.append(last_open)
                highs.append(last_high)
                lows.append(last_low)
                volumes.append(last_volume)
                if len(closes) >= min_value:
                    # закрываем сделку, если она была открыта
                    if order is not None:
                        if order['side'] == 'SELL':
                            order = client.create_margin_order(
                                symbol=TICKER,
                                side=Client.SIDE_BUY,
                                type=Client.ORDER_TYPE_LIMIT,
                                price=last_close,
                                quantity=order['executedQty']
                            )
                        elif order['side'] == 'BUY':
                            order = client.create_margin_order(
                                symbol=TICKER,
                                side=Client.SIDE_SELL,
                                type=Client.ORDER_TYPE_LIMIT,
                                price=last_close,
                                quantity=order['executedQty']
                            )
                        while True:
                            order_status = client.get_order(symbol=TICKER, orderId=order['orderId'])
                            if order_status['status'] == Client.ORDER_STATUS_FILLED:
                                print("Закрытие выполнено.")
                                break
                        order = loading_fill(order, client, "Закрытие выполнено.")
                        order_trades = client.get_my_trades(symbol=TICKER, orderId=order['orderId'])
                        closing_price = float(order_trades[0]['price'])
                        print(f"Цена закрытия ордера: {closing_price} TUSD")
                        order = None
                        print(f"Позиция успешно закрыта.")
                    closes_n, res_v = normalize_values(get_last_values(closes, min_value), last_close)
                    volume_n, n1 = normalize_values(get_last_values(volumes, min_value), 1)
                    rsi7_n, n1 = normalize_values(
                        get_last_values(RSIIndicator(pd.Series(closes), 7).rsi().tolist(), min_value),
                        1
                    )
                    rsi14_n, n1 = normalize_values(
                        get_last_values(RSIIndicator(pd.Series(closes), 14).rsi().tolist(), min_value),
                        1
                    )
                    rsi21_n, n1 = normalize_values(
                        get_last_values(RSIIndicator(pd.Series(closes), 21).rsi().tolist(), min_value),
                        1
                    )
                    input_data = []
                    for i in range(0, min_value):
                        input_data.append([closes_n[i], volume_n[i], rsi7_n[i], rsi14_n[i], rsi21_n[i]])
                    pd_res = model.predict([input_data])[0][0]
                    balance = get_margin_balance(client) - start_balance
                    print(str(last_close))
                    print(str(res_v) + " " + str(pd_res))
                    print("Balance:")
                    print(colored(str(balance) + " $.", "green" if balance >= 0 else "red"))
                    print(colored("-" * 20, "yellow"))
                    ticker = client.get_symbol_ticker(symbol=TICKER)
                    btc_price = float(ticker['price'])
                    quantity = round(rate / btc_price, 6)
                    if pd_res < res_v:
                        # лонг
                        order = client.create_margin_order(
                            symbol=TICKER,
                            side=Client.SIDE_BUY,
                            quantity=quantity,
                            type=Client.ORDER_TYPE_LIMIT,
                            price=last_close,
                        )
                        print(colored("LONG ->>>>>>>", "green"))
                    elif pd_res > res_v:
                        # шорт
                        order = client.create_order(
                            symbol=TICKER,
                            side=Client.SIDE_SELL,
                            quantity=quantity,
                            type=Client.ORDER_TYPE_LIMIT,
                            price=last_close,
                        )
                        print(colored("SHORT ->>>>>>>", "red"))
                    order = loading_fill(order, client, "Ордер выполнен.")
                    order_trades = client.get_my_trades(symbol=TICKER, orderId=order['orderId'])
                    opening_price = float(order_trades[0]['price'])
                    print(f"Цена открытия ордера: {opening_price} TUSD")
                    mess = "<b>%s TUSD.</b>" % str(balance)
                    bot.send_message(
                        588522164,
                        mess,
                        parse_mode='html'
                    )
                else:
                    print("Loading values: " + colored(str(len(closes)), "yellow"))
                time = next_time
                print("__" * 20)
                print('\n')


print("Starting bot...")
asyncio.run(subscribe_to_stream())