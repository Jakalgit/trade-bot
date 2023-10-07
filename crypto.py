import telebot
import asyncio
import json
from binance import Client
from termcolor import colored
import websockets
from tensorflow import keras
from ta.momentum import RSIIndicator, StochasticOscillator
import numpy as np
import pandas as pd

TOKEN_BOT = "5669115775:AAGNYvbBer4Sc9g15l4Q-eE8aLUm_TKLrjQ"
TICKER = 'BTCFDUSD'
TICKER_P = 'BTCTUSD'
api_key = 'tqbGB3Te2GS7dc8IcJMXWoSPBQxjwW3PbzwRocGSN9Ugt0y8mQ9fxy9GzOEL26hw'
api_secret = 'sV03zCztEmookHEtCyLUSx8ImIbx2gbIrrbzOselyqdaPqzYvkrbNQEu8ZYyK0KN'

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

        client = Client(api_key, api_secret)

        rate = 30000
        balance = 0
        time = -1
        data = client.get_historical_klines(TICKER_P, Client.KLINE_INTERVAL_15MINUTE, "1 day ago UTC")
        opens, highs, lows, closes, volumes = transform_data(data)
        start_length = len(data)
        min_value = 32
        last_close = -1
        last_low = -1
        last_high = -1
        last_open = -1
        last_volume = -1
        async for message in websocket:
            data = json.loads(message)
            next_time = data.get('data', {}).get('k', {}).get('t')
            if time != next_time:
                if time != -1:
                    if len(closes) >= start_length:
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
                        candles = client.get_historical_klines(
                            symbol=TICKER,
                            interval=Client.KLINE_INTERVAL_15MINUTE,
                            limit=3
                        )
                        v1 = float(candles[-3][4])
                        v2 = float(candles[-2][4])
                        k = abs(1 - v2 / v1)
                        if (pd_res < res_v and v2 >= v1) or (pd_res >= res_v and v2 <= v1):
                            balance += rate * k
                        elif (pd_res <= res_v and v2 >= v1) or (pd_res > res_v and v2 <= v1):
                            balance -= rate * k
                        print(str(v2))
                        print(str(res_v) + " " + str(pd_res))
                        print(colored("-" * 20, "yellow"))
                        if pd_res < res_v:
                            print(colored("LONG ->>>>>>>", "green"))
                        if pd_res > res_v:
                            print(colored("SHORT ->>>>>>>", "red"))
                        print(
                            "$$ Last close value: " + str(v1) + " rub. $$ Current close value: " + str(v2) + " rub. $$")
                        print("Balance:")
                        print(colored(str(balance) + " rub.", "green" if balance >= 0 else "red"))
                        print(colored("-" * 20, "yellow"))
                        mess = "<b>%s руб.</b>" % str(balance)
                        bot.send_message(
                            588522164,
                            mess,
                            parse_mode='html'
                        )
                    else:
                        print("Loading values: " + colored(str(len(closes) - start_length + 1), "yellow"))
                    closes.append(last_close)
                    opens.append(last_open)
                    highs.append(last_high)
                    lows.append(last_low)
                    volumes.append(last_volume)
                time = next_time
            last_close = float(data.get('data', {}).get('k', {}).get('c'))
            last_open = float(data.get('data', {}).get('k', {}).get('o'))
            last_high = float(data.get('data', {}).get('k', {}).get('h'))
            last_low = float(data.get('data', {}).get('k', {}).get('l'))
            last_volume = float(data.get('data', {}).get('k', {}).get('v'))


print("Starting tests...")
asyncio.run(subscribe_to_stream())
