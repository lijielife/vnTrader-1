#  encoding: UTF-8
# from gateway.shzd2Gateway import shzd2Gateway
# # shzd2Gateway.testtd()

import numpy as np

# class CtaTickData(object):
#     def __init__(self):
#         self.vtSymbol = ''
#         self.symbol  = ''
#
# tick = CtaTickData()
#
# print tick.__dict__
#
# print locals()


# import datetime
#
#
# time1 =  datetime.datetime.strptime('2018-06-17 20:45:10','%Y-%m-%d %H:%M:%S')
#
# time2 = time1 + datetime.timedelta(seconds=10)
#
# print time1,time2
#
# if time2 - datetime.timedelta(seconds=time2.second) == time1 - datetime.timedelta(seconds=time1.second):
#     print True

from pymongo import MongoClient

conn = MongoClient()
conn['mydb']['mycol'].insert_one({'a':1})