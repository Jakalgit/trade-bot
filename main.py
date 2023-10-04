import telebot
import asyncio
import json
from binance.client import Client
from termcolor import colored
import websockets
from tensorflow import keras
from ta.momentum import RSIIndicator
import pandas as pd

TICKER = 'BTCTUSD'
api_key = 'tqbGB3Te2GS7dc8IcJMXWoSPBQxjwW3PbzwRocGSN9Ugt0y8mQ9fxy9GzOEL26hw'
api_secret = 'sV03zCztEmookHEtCyLUSx8ImIbx2gbIrrbzOselyqdaPqzYvkrbNQEu8ZYyK0KN'

client = Client(api_key, api_secret, testnet=False)

margin_account_info = client.get_margin_account()

# Название актива TUSD
asset_name = 'TUSD'

# Найти баланс TUSD в полученных данных
tusd_balance = None
for asset in margin_account_info['userAssets']:
    if asset['asset'] == asset_name:
        tusd_balance = float(asset['free'])

if tusd_balance is not None:
    print(f"Баланс TUSD на маржинальном кошельке: {tusd_balance} {asset_name}")
else:
    print(f"У вас нет баланса TUSD на маржинальном кошельке.")