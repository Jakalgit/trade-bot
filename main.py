import telebot
import asyncio
import json
from binance.client import Client
from termcolor import colored
import websockets
from tensorflow import keras
from ta.momentum import RSIIndicator
import pandas as pd

TICKER = 'BTCUSDT'
api_key = 'smXYfifKg6qxkDEDAFo4SHilcYfJlBU5Ubth2AoMy5M0qguQvUavzv7GvYxi8Wdw'
api_secret = 'X6UwaZXjOizuQlNBEFNzu2PY5lJKXRwjym1ewmVL4BHEeMF4n7NxBhlJwRToB15v'

client = Client(api_key, api_secret, testnet=True)

print(client.get_asset_balance(asset='BTC')['free'])