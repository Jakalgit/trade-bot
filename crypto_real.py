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
api_key = 'smXYfifKg6qxkDEDAFo4SHilcYfJlBU5Ubth2AoMy5M0qguQvUavzv7GvYxi8Wdw'
api_secret = 'X6UwaZXjOizuQlNBEFNzu2PY5lJKXRwjym1ewmVL4BHEeMF4n7NxBhlJwRToB15v'

streams = ["%s@kline_5m" % (TICKER.lower())]

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
    open = []
    high = []
    low = []
    for i in range(0, len(array)):
        open.append(float(array[i][1]))
        high.append(float(array[i][2]))
        low.append(float(array[i][3]))
        close.append(float(array[i][4]))
        vol.append(float(array[i][5]))
    return open, high, low, close, vol


def get_last_values(array, count):
    result = []
    for i in range(count, 0, -1):
        result.append(array[-i])
    return result


def loading_fill(order, client, message):
    while True:
        order_status = client.get_order(symbol='BTCUSDT', orderId=order['orderId'])
        if order_status['status'] == Client.ORDER_STATUS_FILLED:
            print(message)
            break


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
        time = -1
        order = None
        data = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_5MINUTE, "1 day ago UTC")
        opens, highs, lows, closes, volumes = transform_data(data)
        start_length = len(data)
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
                if len(closes) >= min_value:
                    # закрываем сделку, если она была открыта
                    if order is not None:
                        try:
                            if order['side'] == 'SELL':
                                order = client.create_order(
                                    symbol='BTCUSDT',
                                    side=Client.SIDE_BUY,
                                    type=Client.ORDER_TYPE_MARKET,
                                    quantity=order['executedQty']
                                )
                            elif order['side'] == 'BUY':
                                order = client.create_order(
                                    symbol='BTCUSDT',
                                    side=Client.SIDE_SELL,
                                    type=Client.ORDER_TYPE_MARKET,
                                    quantity=order['executedQty']
                                )
                            loading_fill(order, client, "Закрытие выполнено.")
                            order_trades = client.get_my_trades(symbol='BTCUSDT', orderId=order['orderId'])
                            opening_price = float(order_trades[0]['price'])
                            print(f"Цена закрытия ордера: {opening_price} USDT")
                            order = None
                            print(f"Позиция успешно закрыта.")
                        except Exception as e:
                            print(f"Ошибка при закрытии позиции: {e}")
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
                    v1 = closes[-1]
                    v2 = last_close
                    balance = float(client.get_asset_balance(asset='USDT')['free']) - start_balance
                    print(str(v2))
                    print(str(res_v) + " " + str(pd_res))
                    # print(colored("-" * 20, "yellow"))
                    # print(
                    #     "[] Last close value: " + str(v1) + " $. [] Current close value: " + str(v2) + " $. []")
                    print("Balance:")
                    print(colored(str(balance) + " $.", "green" if balance >= 0 else "red"))
                    print(colored("-" * 20, "yellow"))
                    ticker = client.get_symbol_ticker(symbol='BTCUSDT')
                    btc_price = float(ticker['price'])
                    quantity = round(600.0 / btc_price, 3)
                    if pd_res > res_v:
                        # лонг
                        order = client.create_order(
                            symbol='BTCUSDT',
                            side=Client.SIDE_BUY,
                            quantity=quantity,
                            type=Client.ORDER_TYPE_MARKET,
                        )
                        print(colored("LONG ->>>>>>>", "green"))
                    elif pd_res < res_v:
                        # шорт
                        order = client.create_order(
                            symbol='BTCUSDT',
                            side=Client.SIDE_SELL,
                            quantity=quantity,
                            type=Client.ORDER_TYPE_MARKET,
                        )
                        print(colored("SHORT ->>>>>>>", "red"))
                    loading_fill(order, client, "Ордер выполнен.")
                    order_trades = client.get_my_trades(symbol='BTCUSDT', orderId=order['orderId'])
                    opening_price = float(order_trades[0]['price'])
                    print(f"Цена открытия ордера: {opening_price} USDT")
                    # mess = "<b>%s $.</b>" % str(balance)
                    # bot.send_message(
                    #     588522164,
                    #     mess,
                    #     parse_mode='html'
                    # )
                else:
                    print("Loading values: " + colored(str(len(closes)), "yellow"))
                time = next_time
                print("#-#" * 20)


print("Starting tests...")
asyncio.run(subscribe_to_stream())
