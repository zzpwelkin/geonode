"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import os
from contextlib import closing
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.client import Client
from django.utils import simplejson as json
from django.contrib.auth.models import UserManager
from django.conf import settings
from django.contrib.auth.models import User
from geonode.wpsprocess.models import *
from geonode.wpsprocess.repertory import *
from geonode.wpsprocess.utils import *


def register(username, password, **kwargs):
        wpsservice = WPSService.objects.create(username=username, password=password, 
                                               repertorydir = os.path.join(settings.WPS['repertory'], username), 
                                               configfile = 'wps.cfg')
        
        # set the wps repertory for that user
        rep = RepertoryManager().create(wpsservice)
        return wpsservice
        
def unregister(wpsservice):
    
        # delete all the process from table
        for p in wpsservice.process_set.all():
            p.delete()
        
        # delete the repertory of this service
        RepertoryManager().delete(wpsservice)
        
        # delete the service
        User.objects.get(username=wpsservice.username).delete()
        
def process_msg(wpsservice):
    """
    return all the process in format
    """
    msg = 'All the process in category is: '
    for p in Process.objects.all():
        msg = msg + p.identifier + ','
    return msg
    
class RepertoryTest(TestCase):
    pass

class OGCCompatibleAPITest(TestCase):
    """
    ogc compatible api,i.e. GetCapabilities, DescribeProcess, Execute, test
    """
    def setUp(self):
        ogcUser = 'ogcTester'
        self.wpsservice = register(ogcUser, '123')
        
        # upload profile
        WPSService.objects.get(username = ogcUser).update_profile(settings.WPS.get('testprofile', ''))
        
    def tearDown(self):
        # delete ogcTester user and wps repertory
        unregister(self.wpsservice)
        print('**************** tearDown called **********')
        
    def test_ogc_Exception(self):
        c = Client()
        # not query
        response = c.get(reverse('wps_global_dispatch',args = (self.wpsservice.username, )))
        self.assertIn("exceptionCode=\"MissingParameterValue\"", response.content)
        
        # query error
        response = c.get(reverse('wps_global_dispatch',args = (self.wpsservice.username, )), 
                         {'service':'wps', 'version':'1.0.0', 'request':'everydaybewillwell'})
        self.assertIn("exceptionCode=\"InvalidParameterValue\"", response.content)
    
    def test_ogc_GetCapabilities(self):
        c = Client()
        response = c.get(reverse('wps_global_dispatch',args = (self.wpsservice.username, )), 
                         {'service':'wps', 'version':'1.0.0', 'request':'getcapabilities'})
        self.assertIn('wps:ProcessOfferings', response.content)
    
    def test_ogc_DescribeProcess(self):
        c = Client()
        response = c.get(reverse('wps_global_dispatch', args = (self.wpsservice.username, ) ), 
                         {'service':'wps', 'version':'1.0.0', 'request':'describeprocess','identifier':'asyncprocess'})
        self.assertIn('wps:ProcessDescription', response.content)
    
    def test_ogc_Execute(self):
        pass
        # not login
#        c = Client()
#        response = c.get(reverse('wps_global_dispatch', args = (self.wpsservice.username, ) ), 
#                         {'service':'wps', 'version':'1.0.0', 'request':'execute','identifier':'noinputsprocess'})
        
        # login
    
class SearchProcessTest(TestCase):
    def setUp(self):
        ogcUser = 'ogcTester'
        self.wpsservice = register(ogcUser, '123')
        
        # upload profile
        WPSService.objects.get(username = ogcUser).update_profile(settings.WPS.get('testprofile', ''))
            
        # 
        self.c = Client()
        
    def tearDown(self):
        # delete ogcTester user and wps repertory
        unregister(self.wpsservice)
        
    def test_all_category_processes(self):
        res = self.c.get(reverse('search_process', args = ('all',)))
        resobj = json.loads(res.content)
        self.assertEqual(True, resobj['success'])
        self.assertEqual(11, resobj['total'])
        
    def test_all_category_withkey_process(self):
        res = self.c.get(reverse('search_process', args = ('all',)), {'q':'Reference'})
        resobj = json.loads(res.content)
        self.assertEqual(True, resobj['success'])
        self.assertEqual(2, resobj['total'])

    def test_category_withoutproceses(self):
        res = self.c.get(reverse('search_process', args = ('projection',)))
        self.assertEqual(json.loads(r'{"total":0, "rows":[], "success":true}'), json.loads(res.content))