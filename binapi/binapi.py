import decimal
import hmac
import time
import pandas as pd
import hashlib
from decimal import Decimal
from reqs import *

"""
Here a class is defined based on Binance API commands,
to facilitate manipulation in a client portfolio.
Args:
    full paths to a text file containing api access keys
Returns:
    data
"""

def whichside(entryPrice, liqPrice):
    if liqPrice > entryPrice:
        return 'SELL'
    else:
        return 'BUY'

def reverse(side):
    return 'BUY' if side=='SELL' else 'SELL'

def sidebin(side):
    return -1 if side=='SELL' else 1

def float2fixed(flt, prec):
    return int(flt * prec)/prec


class binance:
    
    request_delay  = 150   # tricking binance to get faster requests in miliseconds
    mxlimit        = 1500  # maximum possible number of data to retrive
    prec           = 100
    ORDER_STATUS_NEW = 'NEW'
    ORDER_STATUS_PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    ORDER_STATUS_FILLED = 'FILLED'
    ORDER_STATUS_CANCELED = 'CANCELED'
    ORDER_STATUS_PENDING_CANCEL = 'PENDING_CANCEL'
    ORDER_STATUS_REJECTED = 'REJECTED'
    ORDER_STATUS_EXPIRED = 'EXPIRED'

    SIDE_BUY = 'BUY'
    SIDE_SELL = 'SELL'

    ORDER_TYPE_LIMIT = 'LIMIT'
    ORDER_TYPE_MARKET = 'MARKET'
    ORDER_TYPE_STOP_LOSS = 'STOP_LOSS'
    ORDER_TYPE_STOP_LOSS_LIMIT = 'STOP_LOSS_LIMIT'
    ORDER_TYPE_TAKE_PROFIT = 'TAKE_PROFIT'
    ORDER_TYPE_TAKE_PROFIT_LIMIT = 'TAKE_PROFIT_LIMIT'
    ORDER_TYPE_LIMIT_MAKER = 'LIMIT_MAKER'

    KLINE_INTERVALS = ['1m', '3m', '5m', '15m', '30m',
                       '1h', '2h', '4h', '6h', '8h', '12h',
                       '1d', '3d', '1w', '1M']
    INTERVAL_DETAIL = {'1m' :{'insec': 60,      'tf_reference': 60000},
                       '3m' :{'insec': 180,     'tf_reference': 180000},
                       '5m' :{'insec': 300,     'tf_reference': 300000},
                       '15m':{'insec': 900,     'tf_reference': 900000},
                       '30m':{'insec': 1800,    'tf_reference': 1800000},
                       '1h' :{'insec': 3600,    'tf_reference': 3600000},
                       '2h' :{'insec': 7200,    'tf_reference': 1000},
                       '4h' :{'insec': 14400,   'tf_reference': 1000},
                       '6h' :{'insec': 21600,   'tf_reference': 1000},
                       '8h' :{'insec': 28800,   'tf_reference': 1000},
                       '12h':{'insec': 43200,   'tf_reference': 1000},
                       '1d' :{'insec': 86400,   'tf_reference': 1000},
                       '3d' :{'insec': 259200,  'tf_reference': 1000},
                       '1w' :{'insec': 604800,  'tf_reference': 1000},
                       '1M' :{'insec': 2592000, 'tf_reference': 1000}}
        
    def __init__(self, filename=None):

        self.basev1 = 'https://fapi.binance.com/fapi/v1/' #base api url
        self.basev2 = 'https://fapi.binance.com/fapi/v2/' #base api url
        
        self.reqs = reqs
        self.endpoints = {                            # endpoints representing each api command
            "ping":          'ping',
            "time":          'time',
            "leverage":      'leverage',
            "marginType":    'marginType',
            "order":         'order',
            "testOrder":     'order/test',
            "allOrders":     'allOrders',
            "klines":        'klines',
            "exchangeInfo":  'exchangeInfo',
            "24hrTicker" :   'ticker/24hr',
            "averagePrice" : 'avgPrice',
            "orderBook" :    'depth',
            "account" :      'account',
            "positionRisk":  'positionRisk'}
        
        self.account_access = False                    #Initializing that there is no access to the api yet

        if filename == None:
            raise Exception("Cannot access api without the keys.")
            return
    
        f = open(filename, "r")
        contents = []
        if f.mode == 'r':
            contents = f.read().split('\n')

        self.binance_keys = dict(api_key = contents[0], secret_key=contents[1])
        self.headers = {"X-MBX-APIKEY": self.binance_keys['api_key']}
        self.account_access = True

        ret = self.test_connectivity()
        if ret:
            print('Connection Successful to the brokers API')
        else:
            print('Connection Failed to the brokers API')
    
    def test_connectivity(self):
        # url  = self.basev1 + self.endpoints["ping"]
        url  = self.basev1 + self.endpoints["time"]
        #data  = self.reqs._get(url1, headers = self.headers)
        data  = self.reqs._get(url)
        if data.__contains__('code'):
            if data['code'] == -1:
                return False
        return True
        
    def GetAllSymbols(self, quoteAssets:list=None):
        ''' Gets All symbols and classifies them to
            online, offline and trading (currently) '''
        url  = self.basev1 + self.endpoints["exchangeInfo"]
        data = self.reqs._get(url)
        if data.__contains__('code'):
            raise Exception("Failed to read exchange information")

        online_symbols        = []  #symbols that are currently being traded
        trading_symbols       = []  #symbols that this bot can trade based on
                                    #available qoute assets
        offline_symbols       = []  #symbols that are currently on a break
        trading_symbols_data  = []  #whole data of trading symbols

        for pair in data['symbols']:
            if pair['status'] == 'TRADING':
                online_symbols.append(pair['symbol'])
                if quoteAssets != None and pair['quoteAsset'] in quoteAssets:
                    trading_symbols.append(pair['symbol'])
                    trading_symbols_data.append(pair)
            else:
                offline_symbols.append(pair['symbol'])

        symbols = {'online':  online_symbols,
                   'trading': trading_symbols,
                   'offline': offline_symbols,
                   'tdata':   trading_symbols_data}
        
        return symbols

    def GetSymbolKlines(self, symbol:str, interval:str, limit:int=mxlimit, end_time=None):
        ''' 
        Gets trading price data for a given symbol 
        
        Parameters:
        --
            symbol str:        The symbol for which to get the trading data
            interval str:      The interval on which to get the trading data
            limit:             The number of data to get
            end_time:          The time from which to start looking backward for 'limit'
                               Number of data
        '''

        if limit > self.mxlimit:
            return self.GetSymbolKlinesExtra(symbol, interval, limit, end_time)
        
        params = {'symbol': symbol,
                  'interval': interval,
                  'limit': str(limit)}
        
        if end_time != None:
            params.update({'endTime': str(int(end_time))})

        url = self.basev1 + self.endpoints['klines']  # creat the url
        data = self.reqs._get(url, params)               # download data
        try:
            df = pd.DataFrame(data)                     # put in dataframe pandas format
        except Exception as Err:
            print(data)
            raise(Err)

        df = df.drop(range(6, 12), axis=1)          # Droping useless columns
        
        #print(df)
        col_names = ['time', 'open', 'high',
                     'low', 'close', 'volume']      # rename columns
        df.columns = col_names

        for col in col_names:                       # transform values from strings to floats
            df[col] = df[col].astype(float)

        df['time'] = df['time'].astype(int)

        df['date'] = pd.to_datetime(df['time'] * 1000000, infer_datetime_format=True)
                                                    #transfer date and time to human readable
        return df
    
    def GetSymbolKlinesExtra(self, symbol:str, interval:str, limit:int=mxlimit, end_time=None):
        """ it is to call the GetSymbolKlines as many times as we need 
            in order to get all the historical data required (based on
            the limit parameter) and we'll be merging the results into
            one long dataframe. """

        repeat_rounds = 0
        if limit > self.mxlimit:
            if limit%self.mxlimit==0:
                repeat_rounds = (limit//self.mxlimit)
            else:
                repeat_rounds = (limit//self.mxlimit)+1
   
        initial_limit = limit % self.mxlimit
        if initial_limit == 0:
            initial_limit = self.mxlimit
        # First, we get the last initial_limit candles, starting at end_time and going
        # backwards (or starting in the present moment, if end_time is False)
        df = self.GetSymbolKlines(symbol, interval, limit=initial_limit, end_time=end_time)
        repeat_rounds = repeat_rounds - 1
        while repeat_rounds > 0:
            # Then, for every other maximum possible candles, we get them, but starting at the beginning
            # of the previously received candles.
            df2 = self.GetSymbolKlines(symbol, interval, limit=self.mxlimit, end_time=df['time'][0])
            df = df2.append(df, ignore_index = True)
            repeat_rounds = repeat_rounds - 1
        return df

    def GetSymbolSubData(self, symbol:str, interval:str, start_time:int, subinterval:str):
        ''' 
        Gets trading price data in a lower candle for a given higher candle in a symbol 
        
        Parameters:
        --
            symbol str:        The symbol for which to get the trading data
            interval str:      The interval of the great candle that is to look inside for small candles
            subinterval:       The interval of the small candles that are to be in the large one
        '''
        end_time = start_time + self.INTERVAL_DETAIL[interval]['insec']*1000 - self.INTERVAL_DETAIL[subinterval]['insec']*1000
        noww = time.time_ns()//1000000
        if end_time<=noww:
            limit = self.INTERVAL_DETAIL[interval]['insec']//self.INTERVAL_DETAIL[subinterval]['insec']
        else:
            diff = (end_time-noww)
            remcandles = (diff//self.INTERVAL_DETAIL[subinterval]['tf_reference'] + 1)
            limit = self.INTERVAL_DETAIL[interval]['insec']//self.INTERVAL_DETAIL[subinterval]['insec'] - remcandles
            end_time = None

        df = self.GetSymbolKlines(symbol, subinterval, limit=limit, end_time=end_time)
        return df

    def signRequest(self, params:dict):
        ''' Signs the request using keys and sha256 '''

        query_string = '&'.join(["{}={}".format(d, params[d]) for d in params])
        signature    = hmac.new(self.binance_keys['secret_key'].encode('utf-8'),
                             query_string.encode('utf-8'), hashlib.sha256)
        params['signature'] = signature.hexdigest()

    def GetAccountData(self):
        """ Gets Balances & Account Data """

        url = self.basev2 + self.endpoints["account"]
        
        params = { 'recvWindow': 6000,
                   'timestamp': int(round(time.time()*1000)) + self.request_delay }
        self.signRequest(params)
        data = self.reqs._get(url, params, self.headers)
        return data

    def GetPositionData(self, symbol):
        """ Gets Position Data on a symbol """

        url = self.basev2 + self.endpoints["positionRisk"]
        
        params = { 'symbol': symbol,
                   'recvWindow': 6000,
                   'timestamp': int(round(time.time()*1000)) + self.request_delay }
        self.signRequest(params)
        data = self.reqs._get(url, params, self.headers)
        return data

    def Get24hrTicker(self, symbol:str):
        url    = self.basev1 + self.endpoints['24hrTicker']
        params = {"symbol": symbol}
        return self.reqs._get(url, params)
    
    def setleverage(self, symbol, leverage:int=1):
        if leverage<1 or leverage>125:
            raise Exception("leverage is not standard")
        params = {}
        params['symbol']     = symbol
        params['leverage']   = leverage
        params['recvWindow'] = 6000
        params['timestamp']  = int(round(time.time()*1000)) + self.request_delay


        url     = self.basev1 + self.endpoints['leverage']
        
        self.signRequest(params)
        self.reqs._post(url, params=params, headers=self.headers)
        params.pop('leverage')
        params['marginType'] = 'ISOLATED'
        url     = self.basev1 + self.endpoints['marginType']
        
        self.signRequest(params)
        self.reqs._post(url, params=params, headers=self.headers)
        return True
        
    
    @classmethod
    def floatToString(cls, f:float):
        ''' Converts the given float to a string,
            without resorting to the scientific notation '''

        ctx      = decimal.Context()
        ctx.prec = 12
        d1       = ctx.create_decimal(repr(f))
        return format(d1, 'f')

    def PlaceOrder(self, params, test:bool=True):
        '''
        Places an order on Binance
        Parameters
        --
            symbol str:        The symbol for which to get the trading data
            side str:          The side of the order 'BUY' or 'SELL'
            type str:          The type, 'LIMIT', 'MARKET', 'STOP_LIMIT', 'STOP_MARKET'
            quantity float:    The amount to be traded
        '''
        if not params.keys().__contains__('symbol'):
            raise Exception("Mandatory parameter 'symbol' is missing")
        if not params.keys().__contains__('type'):
            params['type'] = 'MARKET'
        if not params.keys().__contains__('side'):
            raise Exception("Mandatory parameter 'side' is missing")
        if not params.keys().__contains__('recvWindow'):
            params['recvWindow'] = 6000
        
        params['timestamp'] = int(round(time.time()*1000)) + self.request_delay
        self.signRequest(params)
        url = ''
        if test: 
            url = self.basev1 + self.endpoints['testOrder']
        else:
            url = self.basev1 + self.endpoints['order']

        data = self.reqs._post(url, params=params, headers=self.headers)
        return data

    def CancelOrder(self, symbol, orderId):
        '''
            Cancels the order on a symbol based on orderId
        '''
        params = {}
        params['symbol']     = symbol
        params['orderId']    = orderId
        params['recvWindow'] = 6000
        params['timestamp'] = int(round(time.time()*1000)) + self.request_delay
        self.signRequest(params)
        url  = self.basev1 + self.endpoints['order']
        data = self.reqs._delete(url, params=params, headers=self.headers)
        return data

    def GetOrderInfo(self, symbol, orderId):
        '''
            Gets info about an order on a symbol based on orderId
        '''
        params = {}
        params['symbol']     = symbol
        params['orderId']    = orderId
        params['recvWindow'] = 6000
        params['timestamp']  = int(round(time.time()*1000)) + self.request_delay
        self.signRequest(params)

        url  = self.basev1 + self.endpoints['order']
        data = self.reqs._get(url, params=params, headers=self.headers)
        return data

    def GetAllOrderInfo(self, symbol, status:str='NEW'):
        '''
            Gets info about all order on a symbol
        '''
        params = {}
        params['symbol']     = symbol
        params['recvWindow'] = 6000
        params['timestamp']  = int(round(time.time()*1000)) + self.request_delay

        self.signRequest(params)

        url = self.basev1 + self.endpoints['allOrders']
        data = self.reqs._get(url, params=params, headers=self.headers)
        orders = []
        # if data:
        if not status=='ALL':
            for order in data:
                if order['status'] == status:
                    orders.append(order)
        else:
            orders = data
        return orders

    def place_limit_order(self, symbol, side, quantity, price):
        params = {}
        params['symbol']      = symbol
        params['side']        = side
        params['quantity']    = quantity
        params['type']        = 'LIMIT'
        params['price']       = float2fixed(price, self.prec)
        params['timeInForce'] = 'GTC' #'GTX'
        order = self.PlaceOrder(params, test=False)
        return order

    def place_market_order(self, symbol, side, quantity, reduceOnly=False):
        params = {}
        params['symbol']      = symbol
        params['side']        = side
        params['quantity']    = quantity
        params['type']        = 'MARKET'
        if reduceOnly:
            params['reduceOnly']  = True
        order = self.PlaceOrder(params, test=False)
        return order

    def place_redOnly_limit_order(self, symbol, side, quantity, price):
        params = {}
        params['symbol']          = symbol
        params['side']            = side
        params['quantity']        = quantity
        params['type']            = 'LIMIT' # LIMIT, MARKET, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET
        params['price']           = float2fixed(price, self.prec)
        params['reduceOnly']      = True
        params['timeInForce']     = 'GTX'  # GTC, IOC, FOK, GTX
        order = self.PlaceOrder(params, test=False)
        return order

    def place_tp_limit_order(self, symbol, side, quantity, price, stprice):
        params = {}
        params['symbol']          = symbol
        params['side']            = reverse(side)
        params['quantity']        = quantity
        params['stopPrice']       = float2fixed(stprice, self.prec)
        params['type']            = 'TAKE_PROFIT' # LIMIT, MARKET, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET
        params['price']           = float2fixed(price, self.prec)
        params['reduceOnly']      = True
        params['workingType']     = 'CONTRACT_PRICE' # MARK_PRICE, CONTRACT_PRICE (default)
        params['priceProtection'] = True
        params['timeInForce']     = 'GTC'  # GTC, IOC, FOK, GTX
        order = self.PlaceOrder(params, test=False)
        return order

    def place_tp_market_order(self, symbol, side, quantity, stprice):
        params = {}
        params['symbol']          = symbol
        params['side']            = reverse(side)
        params['quantity']        = quantity
        params['stopPrice']       = float2fixed(stprice, self.prec)
        params['type']            = 'TAKE_PROFIT_MARKET' # LIMIT, MARKET, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET
        params['reduceOnly']      = True
        params['workingType']     = 'MARK_PRICE' # MARK_PRICE, CONTRACT_PRICE (default)
        params['priceProtection'] = True
        params['timeInForce']     = 'GTC'  # GTC, IOC, FOK, GTX
        order = self.PlaceOrder(params, test=False)
        return order

    def place_sl_limit_order(self, symbol, side, quantity, price, stprice):
        params = {}
        params['symbol']          = symbol
        params['side']            = reverse(side)
        params['quantity']        = quantity
        params['stopPrice']       = float2fixed(stprice, self.prec)
        params['type']            = 'STOP' # LIMIT, MARKET, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET
        params['price']           = float2fixed(price, self.prec)
        params['reduceOnly']      = True
        params['workingType']     = 'CONTRACT_PRICE' # MARK_PRICE, CONTRACT_PRICE (default)
        params['priceProtection'] = True
        params['timeInForce']     = 'GTC'  # GTC, IOC, FOK, GTX
        order = self.PlaceOrder(params, test=False)
        return order

    def place_sl_market_order(self, symbol, side, quantity, stprice):
        params = {}
        params['symbol']          = symbol
        params['side']            = reverse(side)
        params['quantity']        = quantity
        params['stopPrice']       = float2fixed(stprice, self.prec)
        params['type']            = 'STOP' # LIMIT, MARKET, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET
        params['reduceOnly']      = True
        params['workingType']     = 'MARK_PRICE' # MARK_PRICE, CONTRACT_PRICE (default)
        params['priceProtection'] = True
        params['timeInForce']     = 'GTC'  # GTC, IOC, FOK, GTX
        order = self.PlaceOrder(params, test=False)
        return order

    def cancel_all_orders(self, symbol):
        orders = self.GetAllOrderInfo(symbol, status='NEW')
        if orders:
            for item in orders:
                self.CancelOrder(symbol, item['orderId'])
            return True
        else:
            return False

    def proctor(self, symbol):
        position           = self.GetPositionData(symbol)[0]
        posamt_signed      = position['positionAmt']
        if posamt_signed=='0.000':
            return None
        else:
            # posamt         = str(abs(float(posamt_signed)))
            entryPrice     = position['entryPrice']
            # markPrice      = position['markPrice']
            liqPrice       = position['liquidationPrice']
            # side           = whichside(entryPrice, liqPrice)
            neworders      = self.GetAllOrderInfo(symbol)
            if len(neworders)==2:
                tpy = []
                for item in neworders:
                    tpy.append(item['type'])
                if (('PROFIT' in tpy[0]) or 'PROFIT' in tpy[1]) and (('STOP' in tpy[0]) or ('STOP' in tpy[1])):
                    print('position is safe!')
                    return 'PROTECTED'
            print('position is not safe! Need to close emergentically')
            return 'NOT PROTECTED'

    def closeposition(self, symbol):
        position           = self.GetPositionData(symbol)[0]
        posamt_signed      = position['positionAmt']
        if not (posamt_signed=='0.000'):
            posamt         = str(abs(float(posamt_signed)))
            entryPrice     = position['entryPrice']
            liqPrice       = position['liquidationPrice']
            side           = whichside(entryPrice, liqPrice)
            order          = self.place_market_order(symbol, reverse(side), posamt, True)
            self.cancel_all_orders(symbol)
            return True
        else:
            return False

    def pending_tofill_order(self, symbol, orderId, durab:int=60):
        stime   = time.time()
        endtime = stime + durab
        print(stime)
        print(endtime)
        while True:
            order = self.GetOrderInfo(symbol, orderId)
            print(order)
            if order['status'] in ('FILLED'):
                print('Order number {} filled successfully'.format(orderId))
                return True
            else:
                if time.time()>endtime:
                    self.CancelOrder(symbol, orderId)
                    return False

if __name__ == '__main__':
    symbol   = 'BTCUSDT'
    #symbol   = 'ETHUSDT'
    #client_id = '73a40bae-61c7-11ea-8e67-f40f241d61b4'
    filename = '/home/pj/Documents/Assets/Binance/api/keys.txt'
    exchange = binance(filename)
    print("class creation successful")
    con = exchange.test_connectivity()
    print("connectivity test successful")
    # smbl  = exchange.GetAllSymbols(['USDT'])
    # print("online")
    # print(smbl['online'])
    # print(len(smbl['online']))
    # print("getting all symbols successful")
    # print("-------------------")
    # df = exchange.GetSymbolKlines(symbol, '1h', 1000)
    # print(df['date'])
    # print(df.iloc[-1])
    # side  = -1
    # sider = {1:'BUY', -1:'SELL'}
    # # Placing market order:
    
    # params = {}
    # params['symbol']      = symbol
    # params['side']        = sider[side]
    # params['quantity']    = '0.009'

    # # positions = exchange.GetOrderInfo(params)
    # positions = exchange.PlaceOrder(params, test=False)
    # print(positions)

    # # Placing Stop loss order for it:
    # params = {}
    # params['symbol']      = symbol
    # params['side']        = sider[-side]
    # params['quantity']    = '0.009'
    # params['type']        = 'STOP_MARKET'
    # params['stopPrice']   = 36230
    # params['reduceOnly']  = True

    # # positions = exchange.GetOrderInfo(params)
    # positions = exchange.PlaceOrder(params, test=False)
    # print(positions)

    # params = {'symbol': symbol}
    # # positions = exchange.GetOrderInfo(params)
    # orders = exchange.GetAllOrderInfo('BTCUSDT', status='NEW')
    # print(orders)
    # for item in positions:
    #     print(item)
    #     print()

    # # data = exchange.GetAccountData()
    # # print(data)

    data = exchange.GetPositionData('BTCUSDT')
    print(data)

    # leverage     = 15
    # posamt       = '0.006'
    # side         = 'BUY'
    # symbol       = 'BTCUSDT'
    # entryPrice   = 20000
    # trigger      = 0.0001
    # tp           = 40000
    # tpstopPrice  = tp - sidebin(side)*(trigger*tp)
    # tpstopPrice  = tpstopPrice
    # sl           = 18000
    # slstopPrice  = sl - sidebin(side)*(trigger*sl)
    # slstopPrice  = slstopPrice

    # # ret = exchange.setleverage(symbol, leverage)
    # print(ret)

    # print(tp)
    # print(tpstopPrice)
    # print(sl)
    # print(slstopPrice)

    # ret0       = exchange.place_limit_order(symbol, side, posamt, entryPrice)
    # print(ret0)
    # ret = exchange.place_tp_limit_order(symbol, reverse(side), posamt, tp, tpstopPrice)
    # print(ret)
    # # ret = exchange.place_redOnly_limit_order(symbol, reverse(side), posamt, tp)
    # # print(ret)
    # ret = exchange.place_sl_limit_order(symbol, reverse(side), posamt, sl, slstopPrice)
    # print(ret)

    # ret = exchange.GetAllOrderInfo(symbol)
    # print(ret)

    # ret = exchange.GetOrderInfo(symbol, ret0['orderId'])
    # print(ret)
    
    # ret = exchange.pending_tofill_order(symbol, ret0['orderId'], 60*5*2)
    # print(ret)

    # ret = exchange.cancel_all_orders('BTCUSDT')
    # print(ret)
    
    # ret = exchange.proctor('BTCUSDT')
    # print(ret)
    