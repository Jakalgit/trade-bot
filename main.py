from asyncio import sleep
from datetime import timedelta
from termcolor import colored
from tensorflow import keras
import numpy as np
from tinkoff.invest import (
    CandleInstrument,
    Client,
    SubscriptionInterval, CandleInterval, OrderDirection, OrderType,
)
from tinkoff.invest.market_data_stream.market_data_stream_manager import MarketDataStreamManager
from tinkoff.invest.sandbox.client import SandboxClient
from tinkoff.invest.utils import now

TOKEN = 't.zPll1L8fGOtOZ15PcSJc58mauaiT488xlgwoC529rbp02XoXjkcyqpUg8jy87nv1BI8VluXM1kyWIIgaacLCzA'
FIGI = 'BBG00QPYJ5H0'
model = keras.models.load_model('/Users/Misha/Desktop/Trade Models/model_VTBR_1.2')


def get_last_values(array, count):
    result = []
    for i in range(count, 0, -1):
        result.append(array[-i])
    return result


def get_data(start, end):
    array = []
    with Client(TOKEN) as client:
        for candle in client.get_all_candles(
            figi=FIGI,
            from_=start,
            to=end,
            interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
        ):
            array.append(t_units_float(candle.close))
    return array


def t_units_float(price):
    return float(price.units) + float(price.nano / 1000000000)


def normalize_arr(array):
    result = []
    for i in range(0, len(array)):
        result.append((np.array(array[i]) - np.mean(array)) / np.std(array))
    return result


def get_current_balance(client):
    withdraw_limits = client.operations.get_withdraw_limits(account_id=client.users.get_accounts().accounts[0].id)
    return t_units_float(withdraw_limits.money[0])


def main():
    rate = 30000
    count_in_lot = 1
    prices = get_data(now() - timedelta(days=1), now() - timedelta(days=0))
    min_values = 12
    start_length = len(prices)
    order = None
    with SandboxClient(TOKEN) as client:
        accountId = client.users.get_accounts().accounts[0].id
        start_balance = get_current_balance(client)
        market_data_stream: MarketDataStreamManager = client.create_market_data_stream()
        market_data_stream.candles.waiting_close().subscribe(
            [
                CandleInstrument(
                    figi=FIGI,
                    interval=SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE,
                )
            ]
        )
        for marketdata in market_data_stream:
            if marketdata.subscribe_candles_response is None and marketdata.candle is not None:
                value = t_units_float(marketdata.candle.close)
                prices.append(value)
                if len(prices) >= start_length + min_values:
                    input_data = get_last_values(normalize_arr(prices), min_values)
                    pd_res = model.predict([input_data])[0]
                    lot_price = value * count_in_lot
                    count_lots = round(rate / lot_price)

                    if order is not None:
                        lots_to_sell = client.orders.get_order_state(account_id=accountId, order_id=order.order_id)\
                            .lots_executed
                        order_id = client.orders.post_order(
                            figi=FIGI,
                            quantity=lots_to_sell,
                            direction=OrderDirection.ORDER_DIRECTION_SELL,
                            order_type=OrderType.ORDER_TYPE_BESTPRICE,
                            account_id=accountId,
                        ).order_id
                        while client.orders.get_order_state(account_id=accountId, order_id=order_id)\
                                .execution_report_status != 1:
                            sleep(1)

                    # выводим данные на момент закрытия всех сделок
                    balance = start_balance - get_current_balance(client)
                    print(colored("-", 'yellow') * 20)
                    print("$$ Last value: " + str(prices[-1]) + " rub. $$ Current value: " + str(value) + " rub. $$")
                    print("Balance: \n" + colored(str(balance), "red" if balance <= 0 else "green") + " rub.")
                    print(colored("-", 'yellow') * 20)

                    # лонгуем или шортим(ничего не делаем) в зависимости от показаний нейросети
                    if pd_res[0] > pd_res[1]:
                        order_id = client.orders.post_order(
                            figi=FIGI,
                            quantity=count_lots,
                            direction=OrderzDirection.ORDER_DIRECTION_BUY,
                            order_type=OrderType.ORDER_TYPE_BESTPRICE,
                            account_id=accountId,
                        ).order_id
                        while client.orders.get_order_state(account_id=accountId, order_id=order_id)\
                                .execution_report_status != 1:
                            sleep(1)
                        order = client.orders.get_order_state(account_id=accountId, order_id=order_id)
                else:
                    print("Loading values: " + str(len(prices) - start_length + 1))
            else:
                print("Waiting data")


with SandboxClient(TOKEN) as client:
    client.orders.post_order(
        figi=FIGI,
        quantity=12,
        direction=OrderDirection.ORDER_DIRECTION_SELL,
        order_type=OrderType.ORDER_TYPE_BESTPRICE,
        # order_id='ORDER_TYPE_BESTPRICE',
        account_id='fe9d1790-6683-4a8d-8ca4-b89488ede0cc',
    )