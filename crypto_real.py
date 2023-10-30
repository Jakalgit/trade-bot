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
TICKER = 'BTCUSDT'
TICKER_P = 'BTCTUSD'
api_key = 'smXYfifKg6qxkDEDAFo4SHilcYfJlBU5Ubth2AoMy5M0qguQvUavzv7GvYxi8Wdw'
api_secret = 'X6UwaZXjOizuQlNBEFNzu2PY5lJKXRwjym1ewmVL4BHEeMF4n7NxBhlJwRToB15v'

streams = ["%s@kline_15m" % (TICKER_P.lower())]

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


def loading_fill(order, client, message):
    timer = 0
    delay = 0.9
    origQty = order['origQty']
    while True:
        order_status = client.get_order(symbol=TICKER, orderId=order['orderId'])
        if order_status['status'] == Client.ORDER_STATUS_FILLED:
            print(message)
            break
        sleep(delay)
        timer += 1
        if timer >= 120:
            order_info = client.get_order(symbol=TICKER, orderId=order['orderId'])
            if order_info['status'] != 'FILLED':
                client.cancel_order(symbol=TICKER, orderId=order['orderId'])
                remaining_quantity = round(float(order_info['origQty']) - float(order_info['executedQty']), 4)
                if remaining_quantity > 0:
                    print("Выполение по маркету.")
                    order = client.create_order(
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

        client = Client(api_key, api_secret, testnet=True)

        rate = 30000
        cl_area = 1.5
        time = -1
        order = None
        last_od = None
        last_balance = None
        data = client.get_historical_klines(TICKER_P, Client.KLINE_INTERVAL_15MINUTE, "1 day ago UTC")
        opens, highs, lows, closes, volumes = transform_data(data)
        start_balance = float(client.get_asset_balance(asset='USDT')['free'])
        min_value = 32
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
                candles = client.get_historical_klines(
                    symbol=TICKER,
                    interval=Client.KLINE_INTERVAL_15MINUTE,
                    limit=1
                )
                last_usdt = float(candles[-1][4])
                if len(closes) >= min_value:
                    closes_n, n1 = normalize_values(get_last_values(closes, min_value), last_close)
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
                    current_od = None
                    res_v = closes_n[-1]
                    if pd_res < res_v:
                        current_od = 'Long'
                    elif pd_res > res_v:
                        current_od = 'Short'
                    # закрываем сделку, если она была открыта
                    if order is not None and last_od != current_od:
                        if order['side'] == 'SELL':
                            order = client.create_order(
                                symbol=TICKER,
                                side=Client.SIDE_BUY,
                                type=Client.ORDER_TYPE_LIMIT,
                                timeInForce=Client.TIME_IN_FORCE_GTC,
                                price=last_usdt + cl_area,
                                quantity=order['origQty']
                            )
                        elif order['side'] == 'BUY':
                            order = client.create_order(
                                symbol=TICKER,
                                side=Client.SIDE_SELL,
                                type=Client.ORDER_TYPE_LIMIT,
                                timeInForce=Client.TIME_IN_FORCE_GTC,
                                price=last_usdt - cl_area,
                                quantity=order['origQty']
                            )
                        last_balance = None
                        order = loading_fill(order, client, "Закрытие выполнено.")
                        order_trades = client.get_my_trades(symbol=TICKER, orderId=order['orderId'])
                        closing_price = float(order_trades[0]['price'])
                        print(f"Цена закрытия ордера: {closing_price} USDT")
                        order = None
                        print(f"Позиция успешно закрыта.")
                    print(str(last_usdt))
                    print(str(res_v) + " " + str(pd_res))
                    balance = float(client.get_asset_balance(asset='USDT')['free']) - start_balance
                    if last_balance is None:
                        print("Текущий баланс:")
                        print(colored(str(balance) + " $.", "green" if balance >= 0 else "red"))
                        last_balance = balance
                    else:
                        print("Последний баланс:")
                        print(colored(str(last_balance) + " $.", "green" if balance >= 0 else "red"))
                    print(colored("-" * 20, "yellow"))
                    if current_od != last_od:
                        ticker = client.get_symbol_ticker(symbol=TICKER)
                        btc_price = float(ticker['price'])
                        quantity = round(300.0 / btc_price, 4)
                        if current_od == 'Long':
                            # лонг
                            order = client.create_order(
                                symbol=TICKER,
                                side=Client.SIDE_BUY,
                                quantity=quantity,
                                type=Client.ORDER_TYPE_LIMIT,
                                timeInForce=Client.TIME_IN_FORCE_GTC,
                                price=last_usdt + cl_area,
                            )
                            print(colored("LONG ->>>>>>>", "green"))
                        elif current_od == 'Short':
                            # шорт
                            order = client.create_order(
                                symbol=TICKER,
                                side=Client.SIDE_SELL,
                                quantity=quantity,
                                type=Client.ORDER_TYPE_LIMIT,
                                timeInForce=Client.TIME_IN_FORCE_GTC,
                                price=last_usdt - cl_area,
                            )
                            print(colored("SHORT ->>>>>>>", "red"))
                        last_od = current_od
                        order = loading_fill(order, client, "Ордер выполнен.")
                        order_trades = client.get_my_trades(symbol=TICKER, orderId=order['orderId'])
                        opening_price = float(order_trades[0]['price'])
                        print(f"Цена открытия ордера: {opening_price} USDT")
                    else:
                        print("Идём в том же направлении")
                    # mess = "<b>%s $.</b>" % str(balance)
                    # bot.send_message(
                    #     588522164,
                    #     mess,
                    #     parse_mode='html'
                    # )
                else:
                    print("Loading values: " + colored(str(len(closes)), "yellow"))
                time = next_time
                print("__" * 20)


print("Starting tests...")
asyncio.run(subscribe_to_stream())
