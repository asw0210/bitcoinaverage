#!/usr/bin/python2.7
import os
import sys

include_path = os.path.abspath(os.path.join(__file__, os.pardir))
sys.path.insert(0, include_path)


import json
import time
from email import utils
from decimal import Decimal

import bitcoinaverage as ba
from bitcoinaverage import api_parsers
from bitcoinaverage.config import EXCHANGE_LIST, CURRENCY_LIST, DEC_PLACES, API_QUERY_FREQUENCY, API_FILES, FIAT_RATES_QUERY_FREQUENCY
import bitcoinaverage.helpers as helpers
from bitcoinaverage.nogox import create_nogox_api
from bitcoinaverage.api_calculations import get24hAverage

if ba.server.PROJECT_PATH == '':
    ba.server.PROJECT_PATH = include_path
if ba.server.LOG_PATH == '':
    ba.server.LOG_PATH = os.path.join(ba.server.PROJECT_PATH, 'runtime', 'app.log')
if ba.server.API_DOCUMENT_ROOT == '':
    ba.server.API_DOCUMENT_ROOT = os.path.join(ba.server.PROJECT_PATH, 'api')
    ba.server.API_DOCUMENT_ROOT_NOGOX = os.path.join(ba.server.API_DOCUMENT_ROOT, 'no-mtgox')
if ba.server.WWW_DOCUMENT_ROOT == '':
    ba.server.WWW_DOCUMENT_ROOT = os.path.join(ba.server.PROJECT_PATH, 'www')
if ba.server.HISTORY_DOCUMENT_ROOT == '':
    ba.server.HISTORY_DOCUMENT_ROOT = os.path.join(ba.server.PROJECT_PATH, 'api', 'history')

helpers.write_log('script started', 'LOG')
helpers.write_js_config()
helpers.write_api_index_files()
last_fiat_exchange_rate_update = 0

while True:
    start_time = int(time.time())

    exchanges_rates, exchanges_ignored = ba.api_parsers.callAll()

    calculated_average_rates = {}
    total_currency_volumes = {}
    total_currency_volumes_ask = {}
    total_currency_volumes_bid = {}
    calculated_volumes = {}
    for currency in CURRENCY_LIST:
        calculated_average_rates[currency] = {'last': DEC_PLACES,
                                               'ask': DEC_PLACES,
                                               'bid': DEC_PLACES,
                                                }
        total_currency_volumes[currency] = DEC_PLACES
        total_currency_volumes_ask[currency] = DEC_PLACES
        total_currency_volumes_bid[currency] = DEC_PLACES
        calculated_volumes[currency] = {}

    for i, rate in enumerate(exchanges_rates):
        for currency in CURRENCY_LIST:
            if currency in rate:
                if rate[currency]['volume'] is not None and rate[currency]['volume'] > 0:
                    total_currency_volumes[currency] = total_currency_volumes[currency] + rate[currency]['volume']
                    if rate[currency]['ask'] is not None:
                        total_currency_volumes_ask[currency] = total_currency_volumes_ask[currency] + rate[currency]['volume']
                    if rate[currency]['bid'] is not None:
                        total_currency_volumes_bid[currency] = total_currency_volumes_bid[currency] + rate[currency]['volume']
                else:
                    pass
                    # del exchanges_rates[i][currency]
                    # i think we should not hide exchanges with 0 volume, it should be just zeroed, but still shown. @AlexyKot

    for rate in exchanges_rates:
        for currency in CURRENCY_LIST:
            if currency in rate:
                calculated_volumes[currency][rate['exchange_name']] = {}
                calculated_volumes[currency][rate['exchange_name']]['rates'] = {'ask': rate[currency]['ask'],
                                                                                'bid': rate[currency]['bid'],
                                                                                'last': rate[currency]['last'],
                                                                                    }
                calculated_volumes[currency][rate['exchange_name']]['source'] = rate['data_source']
                if calculated_volumes[currency][rate['exchange_name']]['rates']['last'] is not None:
                    calculated_volumes[currency][rate['exchange_name']]['rates']['last'].quantize(DEC_PLACES)

                if rate[currency]['volume'] is None:
                    rate[currency]['volume'] = DEC_PLACES
                calculated_volumes[currency][rate['exchange_name']]['volume_btc'] = rate[currency]['volume'].quantize(DEC_PLACES)

                if total_currency_volumes[currency] > 0:
                    calculated_volumes[currency][rate['exchange_name']]['volume_percent'] = (rate[currency]['volume']
                        / total_currency_volumes[currency] * Decimal(100) ).quantize(DEC_PLACES)
                else:
                    calculated_volumes[currency][rate['exchange_name']]['volume_percent'] = Decimal(0).quantize(DEC_PLACES)

                if calculated_volumes[currency][rate['exchange_name']]['rates']['ask'] is not None:
                    calculated_volumes[currency][rate['exchange_name']]['rates']['ask'].quantize(DEC_PLACES)
                    if total_currency_volumes[currency] > 0:
                        calculated_volumes[currency][rate['exchange_name']]['volume_percent_ask'] = (rate[currency]['volume']
                            / total_currency_volumes_ask[currency] * Decimal(100) ).quantize(DEC_PLACES)
                    else:
                        calculated_volumes[currency][rate['exchange_name']]['volume_percent_ask'] = Decimal(0).quantize(DEC_PLACES)

                if calculated_volumes[currency][rate['exchange_name']]['rates']['bid'] is not None:
                    calculated_volumes[currency][rate['exchange_name']]['rates']['bid'].quantize(DEC_PLACES)
                    if total_currency_volumes[currency] > 0:
                        calculated_volumes[currency][rate['exchange_name']]['volume_percent_bid'] = (rate[currency]['volume']
                            / total_currency_volumes_bid[currency] * Decimal(100) ).quantize(DEC_PLACES)
                    else:
                        calculated_volumes[currency][rate['exchange_name']]['volume_percent_bid'] = Decimal(0).quantize(DEC_PLACES)

    for rate in exchanges_rates:
        for currency in CURRENCY_LIST:
            if currency in rate:
                if rate[currency]['last'] is not None:
                    calculated_average_rates[currency]['last'] = ( calculated_average_rates[currency]['last']
                                                            + rate[currency]['last'] * calculated_volumes[currency][rate['exchange_name']]['volume_percent'] / Decimal(100) )
                if rate[currency]['ask'] is not None:
                    calculated_average_rates[currency]['ask'] = ( calculated_average_rates[currency]['ask']
                                                            + rate[currency]['ask'] * calculated_volumes[currency][rate['exchange_name']]['volume_percent_ask'] / Decimal(100) )
                if rate[currency]['bid'] is not None:
                    calculated_average_rates[currency]['bid'] = ( calculated_average_rates[currency]['bid']
                                                            + rate[currency]['bid'] * calculated_volumes[currency][rate['exchange_name']]['volume_percent_bid'] / Decimal(100) )

                calculated_average_rates[currency]['last'] = calculated_average_rates[currency]['last'].quantize(DEC_PLACES)
                calculated_average_rates[currency]['ask'] = calculated_average_rates[currency]['ask'].quantize(DEC_PLACES)
                calculated_average_rates[currency]['bid'] = calculated_average_rates[currency]['bid'].quantize(DEC_PLACES)

    for currency in CURRENCY_LIST:
        try:
            calculated_average_rates[currency]['last'] = float(calculated_average_rates[currency]['last'])
        except TypeError:
            calculated_average_rates[currency]['last'] = str(calculated_average_rates[currency]['last'])
        try:
            calculated_average_rates[currency]['ask'] = float(calculated_average_rates[currency]['ask'])
        except TypeError:
            calculated_average_rates[currency]['ask'] = str(calculated_average_rates[currency]['ask'])
        try:
            calculated_average_rates[currency]['bid'] = float(calculated_average_rates[currency]['bid'])
        except TypeError:
            calculated_average_rates[currency]['bid'] = str(calculated_average_rates[currency]['bid'])
        try:
            calculated_average_rates[currency]['total_vol'] = float(total_currency_volumes[currency])
        except TypeError:
            calculated_average_rates[currency]['total_vol'] = str(total_currency_volumes[currency])
        try:
            calculated_average_rates[currency]['24h_avg'] = float(get24hAverage(currency))
        except TypeError:
            calculated_average_rates[currency]['24h_avg'] = str(get24hAverage(currency))

        for exchange_name in EXCHANGE_LIST:
            if exchange_name in calculated_volumes[currency]:
                try:
                    calculated_volumes[currency][exchange_name]['rates']['last'] = float(calculated_volumes[currency][exchange_name]['rates']['last'])
                except TypeError:
                    calculated_volumes[currency][exchange_name]['rates']['last'] = str(calculated_volumes[currency][exchange_name]['rates']['last'])
                try:
                    calculated_volumes[currency][exchange_name]['rates']['ask'] = float(calculated_volumes[currency][exchange_name]['rates']['ask'])
                except TypeError:
                    calculated_volumes[currency][exchange_name]['rates']['ask'] = str(calculated_volumes[currency][exchange_name]['rates']['ask'])
                try:
                    calculated_volumes[currency][exchange_name]['rates']['bid'] = float(calculated_volumes[currency][exchange_name]['rates']['bid'])
                except TypeError:
                    calculated_volumes[currency][exchange_name]['rates']['bid'] = str(calculated_volumes[currency][exchange_name]['rates']['bid'])
                try:
                    calculated_volumes[currency][exchange_name]['volume_btc'] = float(calculated_volumes[currency][exchange_name]['volume_btc'])
                except TypeError:
                    calculated_volumes[currency][exchange_name]['volume_btc'] = str(calculated_volumes[currency][exchange_name]['volume_btc'])
                try:
                    calculated_volumes[currency][exchange_name]['volume_percent'] = float(calculated_volumes[currency][exchange_name]['volume_percent'])
                except TypeError:
                    calculated_volumes[currency][exchange_name]['volume_percent'] = str(calculated_volumes[currency][exchange_name]['volume_percent'])

                if 'volume_percent_ask' in calculated_volumes[currency][exchange_name]:
                    del calculated_volumes[currency][exchange_name]['volume_percent_ask']
                if 'volume_percent_bid' in calculated_volumes[currency][exchange_name]:
                    del calculated_volumes[currency][exchange_name]['volume_percent_bid']

    timestamp = utils.formatdate(time.time())
    try:
        all_data = {}
        all_data['timestamp'] = timestamp
        all_data['ignored_exchanges'] = exchanges_ignored
        for currency in CURRENCY_LIST:
            cur_data = {'exchanges': calculated_volumes[currency],
                        'averages': calculated_average_rates[currency],
                        }
            all_data[currency] = cur_data

        with open(os.path.join(ba.server.API_DOCUMENT_ROOT, API_FILES['ALL_FILE']), 'w+') as api_all_data_file:
            api_all_data_file.write(json.dumps(all_data,  indent=2, sort_keys=True, separators=(',', ': ')))

        rates_all = calculated_average_rates
        rates_all['timestamp'] = timestamp
        with open(os.path.join(ba.server.API_DOCUMENT_ROOT, API_FILES['TICKER_PATH'], 'all'), 'w+') as api_ticker_all_file:
            api_ticker_all_file.write(json.dumps(rates_all, indent=2, sort_keys=True, separators=(',', ': ')))

        for currency in CURRENCY_LIST:
            ticker_cur = calculated_average_rates[currency]
            ticker_cur['timestamp'] = timestamp
            api_ticker_file = open(os.path.join(ba.server.API_DOCUMENT_ROOT, API_FILES['TICKER_PATH'], currency), 'w+')
            api_ticker_file.write(json.dumps(ticker_cur,  indent=2, sort_keys=True, separators=(',', ': ')))
            api_ticker_file.close()

        volumes_all = calculated_volumes
        volumes_all['timestamp'] = timestamp
        with open(os.path.join(ba.server.API_DOCUMENT_ROOT, API_FILES['EXCHANGES_PATH'], 'all'), 'w+') as api_volume_all_file:
            api_volume_all_file.write(json.dumps(volumes_all, indent=2, sort_keys=True, separators=(',', ': ')))

        for currency in CURRENCY_LIST:
            volume_cur = calculated_volumes[currency]
            volume_cur['timestamp'] = timestamp
            api_ticker_file = open(os.path.join(ba.server.API_DOCUMENT_ROOT, API_FILES['EXCHANGES_PATH'], currency), 'w+')
            api_ticker_file.write(json.dumps(volume_cur,  indent=2, sort_keys=True, separators=(',', ': ')))
            api_ticker_file.close()

        with open(os.path.join(ba.server.API_DOCUMENT_ROOT, API_FILES['IGNORED_FILE']), 'w+') as api_ignored_file:
            api_ignored_file.write(json.dumps(exchanges_ignored,  indent=2, sort_keys=True, separators=(',', ': ')))

    except IOError as error:
        error_text = '%s, %s ' % (sys.exc_info()[0], error)
        helpers.write_log(error_text)
        print 'ERROR: %s ' % (error_text)
        raise error

    create_nogox_api(timestamp)

    if last_fiat_exchange_rate_update < int(time.time())-FIAT_RATES_QUERY_FREQUENCY:
        helpers.write_html_currency_pages()
        helpers.write_sitemap()
        helpers.write_fiat_rates_config()
        last_fiat_exchange_rate_update = int(time.time())

    cycle_time = int(time.time())-start_time
    sleep_time = max(0, API_QUERY_FREQUENCY['default']-cycle_time)
    print '%s, sleeping %ss - api daemon' % (timestamp, str(sleep_time))

    time.sleep(sleep_time)
