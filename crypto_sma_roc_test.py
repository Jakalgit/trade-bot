import telebot
import json
import asyncio
from binance.client import Client
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


def waiting_order(client, order):
    while True:
        order_status = client.get_order(symbol=TICKER, orderId=order['orderId'])
        if order_status['status'] == Client.ORDER_STATUS_FILLED:
            print("Ордер исполнен")
            break


def stop_loss(client, order, open_price, current_close, percent):
    if order is not None and open_price != -1 and percent > 0:
        k = 0
        if order['side'] == 'SELL':
            k = (current_close / open_price) - 1
        elif order['side'] == 'BUY':
            k = 1 - (current_close / open_price)
        if k >= percent / 100:
            print("!!!!" * 20)
            if order['side'] == 'SELL':
                order = client.create_order(
                    symbol=TICKER,
                    side=Client.SIDE_BUY,
                    type=Client.ORDER_TYPE_MARKET,
                    quantity=order['origQty']
                )
            elif order['side'] == 'BUY':
                order = client.create_order(
                    symbol=TICKER,
                    side=Client.SIDE_SELL,
                    type=Client.ORDER_TYPE_MARKET,
                    quantity=order['origQty']
                )
            print("Закрытие по стоп-лосс")
            waiting_order(client, order)
            print("!!!!" * 20)
            order = None
            open_price = -1
    return order, open_price


def take_profit(client, order, open_price, current_close, percent):
    if order is not None and open_price != -1 and percent > 0:
        k = 0
        if order['side'] == 'SELL':
            k = 1 - (current_close / open_price)
        elif order['side'] == 'BUY':
            k = (current_close / open_price) - 1
        if k >= percent / 100:
            print("!!!!" * 20)
            if order['side'] == 'SELL':
                order = client.create_order(
                    symbol=TICKER,
                    side=Client.SIDE_BUY,
                    type=Client.ORDER_TYPE_MARKET,
                    quantity=order['origQty']
                )
            elif order['side'] == 'BUY':
                order = client.create_order(
                    symbol=TICKER,
                    side=Client.SIDE_SELL,
                    type=Client.ORDER_TYPE_MARKET,
                    quantity=order['origQty']
                )
            print("Закрытие по тейк-профит")
            waiting_order(client, order)
            print("!!!!" * 20)
            order = None
            open_price = -1
    return order, open_price


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
        take_p = 35  # 12
        stop_p = 18  # 16
        eps = 0.264  # 0.17
        open_price = -1
        async for message in websocket:
            data = json.loads(message)
            next_time = data.get('data', {}).get('k', {}).get('t')
            if time == -1:
                time = next_time
            if time != next_time:
                print("Обнаружена новая свеча")
                last_close = float(data.get('data', {}).get('k', {}).get('c'))
                closes.append(last_close)
                sma_50 = SMAIndicator(pd.Series(closes), 50).sma_indicator()
                sma_200 = SMAIndicator(pd.Series(closes), 200).sma_indicator()
                roc = ROCIndicator(pd.Series(closes), 14).roc()
                s_50 = sma_50.tolist()[-1]
                s_200 = sma_200.tolist()[-1]
                s_50_prev = sma_50.tolist()[-2]
                s_200_prev = sma_200.tolist()[-2]
                rc = roc.tolist()[-1]

                order, open_price = stop_loss(client, order, open_price, last_close, stop_p)
                order, open_price = take_profit(client, order, open_price, last_close, take_p)

                if abs(s_50 - s_200) <= eps < abs(s_50_prev - s_200_prev):
                    signal = 0
                    if s_50_prev < s_200_prev and rc > 0:
                        signal = 1
                    elif s_50_prev > s_200_prev and rc < 0:
                        signal = -1
                    if signal != 0:
                        print("Обнаружена точка входа")
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
                            print("Закрытие предыдущего ордера")
                            waiting_order(client, order)
                        ticker = client.get_symbol_ticker(symbol=TICKER)
                        current_price = float(ticker['price'])

                        balance = float(client.get_asset_balance(asset='USDT')['free']) - start_balance
                        print("Баланс: " + str(balance) + " $")
                        mess = "<b>%s $.</b>" % str(balance)
                        bot.send_message(
                            588522164,
                            mess,
                            parse_mode='html'
                        )

                        quantity = round(rate / current_price, 4)
                        print("Открытие нового ордера")
                        if signal == 1:
                            order = client.create_order(
                                symbol=TICKER,
                                side=Client.SIDE_BUY,
                                type=Client.ORDER_TYPE_MARKET,
                                quantity=quantity
                            )
                        elif signal == -1:
                            order = client.create_order(
                                symbol=TICKER,
                                side=Client.SIDE_SELL,
                                type=Client.ORDER_TYPE_MARKET,
                                quantity=quantity
                            )
                        waiting_order(client, order)
                        open_price = last_close
                time = next_time
                print("- - " * 20)


print("Starting tests...")
asyncio.run(subscribe_to_stream())
