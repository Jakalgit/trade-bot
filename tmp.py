from tensorflow import keras
import numpy as np
from binance.client import Client as Client
from sklearn.preprocessing import MinMaxScaler

api_key = 'tqbGB3Te2GS7dc8IcJMXWoSPBQxjwW3PbzwRocGSN9Ugt0y8mQ9fxy9GzOEL26hw'
api_secret = 'sV03zCztEmookHEtCyLUSx8ImIbx2gbIrrbzOselyqdaPqzYvkrbNQEu8ZYyK0KN'

client = Client(api_key, api_secret,)

data = client.get_historical_klines("BTCTUSD", Client.KLINE_INTERVAL_15MINUTE, "1 Jun, 2023", "30 Sep, 2023")

file = open("data_15min.txt", "w")
for i in range(0, len(data)):
    file.write(str(data[i][0]) + " " + str(data[i][1]) + " " + str(data[i][2]) + " " + str(data[i][3]) + " " + str(data[i][4]) + " " +
               str(data[i][5]) + " " + str(data[i][6]) + " " + str(data[i][7]) + " " + str(data[i][8]) + " " + str(data[i][9]) + " " +
               str(data[i][10]) + " " + str(data[i][11]) + '\n')