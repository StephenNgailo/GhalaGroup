# -*- coding: utf-8 -*-
###################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2019-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    This program is free software: you can modify
#    it under the terms of the GNU Affero General Public License (AGPL) as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
###################################################################################
from odoo import api, fields, models
from datetime import datetime
from werkzeug import urls
from odoo.tools import consteq, float_round, image_process, ustr
import requests
import hashlib
import json

import base64

import logging

_logger = logging.getLogger(__name__)


class PaymentAcquirerAtom(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[
        ('ngenius', 'Ngenius')
    ], ondelete={'ngenius': 'cascade'})
    #fields.Selection(selection_add=[('ngenius', 'Ngenius')], ondelete={'paypal': 'set default'})
    ngenius_merchant_id = fields.Char('Merchant ID', required_if_provider='ngenius',
                                        groups='base.group_user')
    ngenius_merchant_key = fields.Char('Merchent Key', required_if_provider='ngenius',
                                        groups='base.group_user')


    @api.model
    def _get_ngenius_urls(self):
        """ Atom URLS """
        url = 'https://api-gateway.sandbox.stanbicbank.co.tz/identity/auth/access-token?realName=sandboxStanbicBankTZA'
        headers = {
            'Authorization': 'Basic NjFkNDEwOGItYWZiZC00MzMwLWI5MWItZjE0ZmY1NGRkYTE4OmJmMjAzOGZkLTZlODctNGQzOC05OTRkLWYwYzk0MWNhNjE5NQ==',
            'Content-Type': 'application/vnd.ni-identity.v1+json'}

        r = requests.post(url, headers=headers)
        json_data = json.loads(r.text)
        _token = json_data['access_token']
        outlet = "78c57fdf-144e-45e9-b290-f0d27d3f6da1"
        url = "https://api-gateway.sandbox.ngenius-payments.com/transactions/outlets/"+outlet+"/orders"
        headers = {
            'Authorization': 'Bearer '+_token,
            'Content-Type': 'application/vnd.ni-payment.v2+json',
            'Accept':'application/vnd.ni-payment.v2+json',
        }
        payload = {
            'action': 'SALE',
            'amount': {
                'currencyCode': 'TZS',
                'value': '1000000'

            }
        }
        r = requests.post(url, headers=headers, data=json.dumps(payload))
        json_data = json.loads(r.text)
        return {
            #'ngenius_form_url':'https://securegw-stage.ngenius.in/order/process'
            'ngenius_form_url':json_data['_links']['payment']['href']
        }

    @api.model
    def get_ngenius_urls(self, values):
        """ Atom URLS """
        url = 'https://api-gateway.sandbox.stanbicbank.co.tz/identity/auth/access-token?realName=sandboxStanbicBankTZA'
        headers = {
            'Authorization': 'Basic NjFkNDEwOGItYWZiZC00MzMwLWI5MWItZjE0ZmY1NGRkYTE4OmJmMjAzOGZkLTZlODctNGQzOC05OTRkLWYwYzk0MWNhNjE5NQ==',
            'Content-Type': 'application/vnd.ni-identity.v1+json'}

        r = requests.post(url, headers=headers)
        json_data = json.loads(r.text)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        _token = json_data['access_token']
        outlet = "78c57fdf-144e-45e9-b290-f0d27d3f6da1"
        url = "https://api-gateway.sandbox.ngenius-payments.com/transactions/outlets/"+outlet+"/orders"
        headers = {
            'Authorization': 'Bearer '+_token,
            'Content-Type': 'application/vnd.ni-payment.v2+json',
            'Accept':'application/vnd.ni-payment.v2+json',
        }

        payload = {
            'action': 'SALE',
            'amount': {
                'currencyCode': 'TZS',
                'value': int(values['amount']*100)

            },
            'merchantAttributes': {
                'redirectUrl': urls.url_join(base_url, '/payment/ngenius/return'),
                'cancelUrl': urls.url_join(base_url, '/payment/ngenius/cancel'),
            },
            'merchantOrderReference': values['reference'],

        }
        r = requests.post(url, headers=headers, data=json.dumps(payload))
        json_data = json.loads(r.text)
        _logger.info(json_data)
        return '/payment/ngenius/forward/?url='+json_data['_links']['payment']['href']


    def ngenius_get_form_action_url(self):
        return self._get_ngenius_urls () ['ngenius_form_url']

    def ngenius_form_generate_values(self ,values):
        self.ensure_one ()
        base_url=self.env ['ir.config_parameter'].sudo ().get_param ('web.base.url')
        now=datetime.now ()

        ngenius_values=dict (
                          MID=self.ngenius_merchant_id ,
                          ORDER_ID=str(values ['reference']) ,
                          CUST_ID = str(values.get('partner_id')),
                          INDUSTRY_TYPE_ID='Retail' ,
                          CHANNEL_ID = 'WEB',
                          TXN_AMOUNT=str(values ['amount']) ,
                          WEBSITE='WEBSTAGING',
                          EMAIL=str(values.get ('partner_email')) ,
                          MOBILE_NO = str(values.get('partner_phone')),
                          CALL_BACK_URL=urls.url_join (base_url, '/payment/ngenius/return/'),
                          tx_url= self.get_ngenius_urls(values),,
                          )

        return ngenius_values

class PaymentTransactionAtom(models.Model):
    _inherit = 'payment.transaction'

    ngenius_txn_type = fields.Char('Transaction type')

    @api.model
    def _ngenius_form_get_tx_from_data(self, data):
        reference = data.get('merchantOrderReference')
        if not reference:
            error_msg=_ ('Paytm: received data with missing reference (%s)') % (reference)
            _logger.info(error_msg)
            raise ValidationError (error_msg)

        reference = data['merchantOrderReference']

        txs=self.env ['payment.transaction'].search ([('reference' ,'=' ,reference)])
        if not txs or len (txs) > 1:
            error_msg='ngenius: received data for reference %s' % (reference)
            if not txs:
                error_msg+='; no order found'
            else:
                error_msg+='; multiple order found'
            _logger.info (error_msg)
            raise ValidationError (error_msg)
        return txs [0]


    def _ngenius_form_get_invalid_parameters(self ,data):
        invalid_parameters=[]
        if self.acquirer_reference and data.get ('mmp_txn') != self.acquirer_reference and False:
            invalid_parameters.append(('ORDERID', data.get('merchantOrderReference'), self.acquirer_reference))

        return invalid_parameters

    def _ngenius_form_validate(self ,data):
        status=data['_embedded']['payment'][0]['state']
        result=self.write ({
            'acquirer_reference':self.env ['payment.acquirer'].search ([]) ,
            'date':fields.Datetime.now () ,

        })
        if status == 'CAPTURED':
            self._set_transaction_done ()
        elif status != 'CANCELLED':
            self._set_transaction_cancel ()
        else:
            self._set_transaction_pending ()
        return result
