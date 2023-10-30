from time import sleep
import telebot
import asyncio
import json
from binance.client import Client
from termcolor import colored
import websockets
from ta.momentum import ROCIndicator
from ta.trend import SMAIndicator
import pandas as pd

TOKEN_BOT = "5669115775:AAGNYvbBer4Sc9g15l4Q-eE8aLUm_TKLrjQ"
TICKER = 'SOLUSDT'
api_key = 'smXYfifKg6qxkDEDAFo4SHilcYfJlBU5Ubth2AoMy5M0qguQvUavzv7GvYxi8Wdw'
api_secret = 'X6UwaZXjOizuQlNBEFNzu2PY5lJKXRwjym1ewmVL4BHEeMF4n7NxBhlJwRToB15v'

streams = ["%s@kline_5m" % (TICKER.lower())]
bot = telebot.TeleBot(TOKEN_BOT)


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


def stop_loss(client, open_price, current_close, type_order, percent):
    ...


def take_profit(open_price, current_close, type_order, percent):
    ...


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

        rate = 320
        time = -1
        order = None
        data = client.get_historical_klines("SOLUSDT", Client.KLINE_INTERVAL_5MINUTE, "2 day ago UTC")
        opens, highs, lows, closes, volumes = transform_data(data)
        start_balance = float(client.get_asset_balance(asset='USDT')['free'])
        take_p = 12
        stop_p = 16
        eps = 0.17
        open_price = -1
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
                sma_50 = SMAIndicator(pd.Series(closes), 50).sma_indicator()
                sma_200 = SMAIndicator(pd.Series(closes), 200).sma_indicator()
                roc = ROCIndicator(pd.Series(closes), 14).roc()
                s_50 = sma_50[-1]
                s_200 = sma_200[-1]
                s_50_prev = sma_50[-2]
                s_200_prev = sma_200[-2]
                rc = roc[-1]
                if abs(s_50 - s_200) <= eps < abs(s_50_prev - s_200_prev):
                    if order is not None and open_price != -1:
                        if order['side'] == 'BUY':
                            order = client.create_order(
                                symbol=TICKER,
                                side=Client.SIDE_SELL,
                                type=Client.ORDER_TYPE_MARKET,
                                quantity=order['origQty']
                            )
                        elif order['side'] == 'SELL':
                            order = client.create_order(
                                symbol=TICKER,
                                side=Client.SIDE_BUY,
                                type=Client.ORDER_TYPE_MARKET,
                                quantity=order['origQty']
                            )

                time = next_time
                print("- - " * 20)