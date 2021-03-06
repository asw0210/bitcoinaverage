import csv
import StringIO
from decimal import Decimal
from decimal import InvalidOperation
import simplejson
import requests

import bitcoinaverage as ba
from bitcoinaverage.config import DEC_PLACES


def get24hAverage(currency_code):
    average_price = DEC_PLACES
    history_currency_API_24h_path = '%s%s/per_minute_24h_sliding_window.csv' % (ba.server.API_INDEX_URL_HISTORY, currency_code)

    try:
        csv_result = requests.get(history_currency_API_24h_path).text
    except (simplejson.decoder.JSONDecodeError, requests.exceptions.ConnectionError):
        return 0

    csvfile = StringIO.StringIO(csv_result)
    csvreader = csv.reader(csvfile, delimiter=',')
    price_sum = DEC_PLACES
    index = 0
    header_passed = False
    for row in csvreader:
        if not header_passed:
            header_passed = True
            continue
        try:
            price_sum = price_sum + Decimal(row[1])
            index = index + 1
        except IndexError:
            continue
    try:
        average_price = (price_sum / Decimal(index)).quantize(DEC_PLACES)
    except InvalidOperation:
        average_price = DEC_PLACES

    return average_price

