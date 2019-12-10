#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from requests import post
from hashlib import sha1, md5
from string import Template
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import xml.etree.ElementTree as ET

class GetTX:

    # API endpoint
    url = "https://api.privatbank.ua/p24api/rest_fiz"

    # XML for request
    xml = Template(
        '<?xml version="1.0" encoding="UTF-8"?>' +
        '<request version="1.0">' +
        '<merchant>' +
        '<id>$merchant_id</id>' +
        '<signature>$signature</signature>' +
        '</merchant>' +
        '<data>' +
        '$data' +
        '</data>' +
        '</request>'
    )

    # data part of XML used in signature generation
    data = Template(
        '<oper>cmt</oper>' +
        '<wait>0</wait>' +
        '<test>0</test>' +
        '<payment id="">' +
        '<prop name="sd" value="$start_date" />' +
        '<prop name="ed" value="$end_date" />' +
        '<prop name="card" value="$card_number" />' +
        '</payment>'
    )

    # Merchant password and ID from Privat24
    password = 'xxx'
    merchant_id = 'nnn'

    # define the period for transactions
    now = datetime.datetime.now()
    start_date = (now.date() - datetime.timedelta(1)).strftime('%d.%m.%Y')
    end_date = start_date

    # function to get the transactions from PrivatBank
    def get_tx(self, card_number):
        """ generate signature """

        data = self.data.substitute(start_date=self.start_date, end_date=self.end_date, card_number=card_number)

        # generate signature
        signature = sha1(md5(data + self.password).hexdigest()).hexdigest()

        # update XML with signature
        xml_data = self.xml.substitute(merchant_id=self.merchant_id, signature=signature, data=data)

        """ get events """

        # prepare XML for request
        xml_data = str(xml_data)

        # perform a request and get transaction list
        result = post(self.url, data=xml_data, headers={'Content-Type': 'application/xml; charset=UTF-8'}).text

        return result

class GoogleSheets:

    def __init__(self):
        pass

    def creds(self):

        # use creds to create a client to interact with the Google Drive API
        scope = ['https://spreadsheets.google.com/feeds',
                  'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name('/path/to/credentials/json/from/google/account', scope)

        return credentials

    def add_rows(self, credentials, xml_data, card_number):

        patterns = [(ur'Продукты:|Универмаг:','Продукты и товары'),
                    (u'Ресторан:', 'Кафе и рестораны'),
                    (ur'Перевод.*сво.*карт.*', 'Перевод'),
                    (ur'Такси:|Транспортные сборы:', 'Такси и транспорт'),
                    (u'Аптека:', 'Здоровье'),]

        # google spreadsheet
        gc = gspread.authorize(credentials)

        # provide your Google sheet key
        sh = gc.open_by_key('aaaaaaqqqqqqqqqqwwwwwwwwwwddddddddd')

        worksheet = sh.worksheet('Transactions')

        # this is to determine the first transaction, used in spreadsheet to calculate card balance
        first = True

        for statement in xml_data.iter("statement"):

            st = statement.attrib
            category = "Інше"
            for pattern in patterns:
                if re.search(pattern[0], st['description'], re.UNICODE):
                    category = pattern[1]
                    break

            card_amount = float(st['cardamount'].split(' ')[0])
            card_rest = float(st['rest'].split(' ')[0])
            
            trandate = datetime.datetime.strptime(st['trandate'], '%Y-%m-%d')
            monday = trandate - datetime.timedelta(days=trandate.weekday())

            terminal = st['terminal'] 

            # this is to determine the first transaction, used in spreadsheet to calculate card balance
            if first:
                terminal = st['terminal'] + " ;balance"
                first = False

            row = [cur_month, str(monday), st['trandate'], card_number, category, st['description'], card_amount, card_rest, terminal]
            worksheet.append_row(row)


if __name__ == '__main__':

    card_numbers = ['1111222233334444', '5555666677778888',]

    tx = GetTX()

    gsheets = GoogleSheets()
    creds = gsheets.creds()

    for card_number in card_numbers:
        tree = tx.get_tx(card_number)
        root = ET.fromstring(tree.encode('utf-8'))
        gsheets.add_rows(creds, root, card_number)
