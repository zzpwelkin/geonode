#-*- coding:utf-8 -*-
# Create your views here.

import os, sys
import logging
from lxml import etree
from StringIO import StringIO
from urllib2 import urlparse
from owslib import wps

from geonode import settings
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.utils import simplejson as json
from django.utils.html import escape
from django.shortcuts import get_object_or_404
from django.views.generic import ListView
from django.views.generic.edit import FormView, FormMixin

from geonode.wpsprocess.utils import *
from geonode.wpsprocess.models import *
from geonode.wpsprocess.repertory import *
from geonode.wpsprocess.forms import *
from geonode.wpsprocess.decorates import geonode_filter
from geonode.utils import get_query

from geonode.layers.models import Layer

logger = logging.getLogger('geonode.wpsprocess.view')

def wps_global_dispatch(request, provider):
    """request to wps service for spectial user,and need login if the request is Execute"""
    if not User.objects.get_by_natural_key(provider):
        return HttpResponseNotFound()

    logger.debug('provider is {0}'.format(provider))
    wpssvr = get_object_or_404(WPSService, username = provider)
    
    #wpssvr = WPSService.objects.get(username = provider)
    if (request.method == 'GET' and request.GET.get('request','').lower() != 'execute') or \
        (request.method == 'POST' and request.POST.get('request','').lower() != 'execute'):
        
        logger.debug(os.path.join(wpssvr.repertorydir, wpssvr.configfile))
        return HttpResponse (wps_request(request, os.path.join(wpssvr.repertorydir, wpssvr.configfile)), mimetype='application/xml')
    else:
        return WPSExecute(request, os.path.join(wpssvr.repertorydir, wpssvr.configfile))
    
@login_required
def WPSExecute(request, wps_cfg):
    response_doc = wps_request(request, wps_cfg)
    
    # geonode filter that add records 
    # TODO: modify it to the django signal pattern
    geonode_filter(request.user, response_doc)
    
    return HttpResponse (response_doc, mimetype='application/xml')
    
def search_process(request, slug):
    """
    handles a basic search for process, if slug is "all", then do not category filter

    the search accepts:
    q - general query for keywords across all fields
    start - skip to this point in the results
    limit - max records to return

    for ajax requests, the search returns a json structure
    like this:
    {ExeciteForm
    'total': <total result count>,
    'next': <url for next batch if exists>,
    'prev': <url for previous batch if exists>,
    'query_info': {
    'start': <integer indicating where this batch starts>,
    'limit': <integer indicating the batch size used>,
    'q': <keywords used to query>,
    },
    'rows': [
    {
    'identifier': '...'
    'version':'x.x.x...'
    'title': <language neutral attribution>,
    'abstract': 'href': <url>( link to manual of this process ),
    'topiccategory':<topiccategory>,
    'keywords': ['foo', ...],
    'detail' = 'href':<url>(link to wps DescribeProcess requestL),
    'manual' = 'href': <url>( link to manual of this process )
    'provider' = '<User>'
    'create_time' = '<date>'
    'recent_change_time' = '<date>'
    },
    ...
    ]}
    
    @param slug:
    """
    query_string = ''
    found_entries = None
    result = {}
    
    if (slug == 'all'):
        found_entries = Process.objects.all()
    else:
        try:
            found_entries = ( TopicCategory.objects.get(slug = slug) ).process_set.all()
        except TopicCategory.DoesNotExist, e:
            result['msg'] = "not found process for that {0} topic category".format(slug)
            result['rows'] = {}
            result['success'] = True
            return HttpResponse(json.dump(res), mimetype="application/json")
    
    if ('q' in request.GET) and request.GET['q'].strip():
        query_string = request.GET['q']
    
        entry_query = get_query(query_string, ['identifier', 'title', 'abstract', ])
    
        found_entries = found_entries.filter(entry_query)
    
    result['total'] = len(found_entries)
    
    rows = []
    
    for p in found_entries:
        
        doc = {}
        doc['identifier'] = p.identifier
        doc['version'] = p.version
        doc['title'] = p.title
        doc['abstract'] = p.abstract
        doc['topiccategory'] = p.topiccategory.slug
        doc['keyworks'] = None
        doc['ogc_wps_service_link'] = reverse('wps_global_dispatch', args=( p.wpsservice.username, ))
        doc['manual_link'] = p.manual_link
        doc['provider'] = p.wpsservice.username
        doc['create_time'] = p.created_time.isoformat()
        doc['recent_changed_time'] = p.recent_changed_time.isoformat()
        rows.append(doc)
    
    result['rows'] = rows
    result['success'] = True
    return HttpResponse(json.dumps(result), mimetype="application/json")


class ProcessListView(ListView):
    queryset = Process.objects.all()
    context_object_name = "process_list"

    def get_queryset(self):
        #category = TopicCategory.objects.get(slug=self.kwargs['slug'])
        if not self.kwargs.get('slug', '') or self.kwargs.get('slug')=='all' :
            return Process.objects.all()
        else:
            category = get_object_or_404(TopicCategory, slug = self.kwargs['slug'])
        return Process.objects.filter(topiccategory = category)
    
    def get_context_data(self, **kwargs):
        """
        this is the method for template render and inherit fro TemplateView
        """
        context = super(ProcessListView,self).get_context_data(**kwargs)
        context['topic_category'] = TopicCategory.objects
        context['curr_category'] = kwargs.get('slug', 'All')
        return context
    
class ProcessExecuteView(FormView):
    
    _inputs = None
    form_class = ExecuteForm
    #success_url = reverse('process_browse')
    
    def get_form_kwargs(self):
        kwargs = super(ProcessExecuteView,self).get_form_kwargs()
        
        if not self._inputs:
            self._inputs = self._inputsParse(self.kwargs.get('provider'), self.kwargs.get('identifier'))

        kwargs['inputs'] = self._inputs
        # get the feature and coverage datas
        kwargs['features'] = kwargs['coverages'] = []
        for layer in Layer.objects.all():
            if layer.storeType == 'coverageStore':
                kwargs['coverages'].append((layer.topic_category,layer.title))
            elif layer.storeType == 'featureStore':
                kwargs['features'].append((layer.topic_category,layer.title))

        logger.info('the values of form is : {0}'.format(str(kwargs)))
        return kwargs
    
    def form_valid(self, form):
        #super(ProcessExecuteView, self).form_valid(form)
        
        vals = []
        for field in form.fields:
            vals.append( (field, form.cleaned_data[field]))
        return HttpResponse(self._execute(self.kwargs.get('provider'), self.kwargs.get('identifier'), vals), mimetype='application/xml')
    
    def _execute(self, provider, identifier, inputs):
        """
        @param provider: the owner of this process
        @param identifier: the requested process identifier
        @param inputs: array of input arguments for the process and are expresses as simple (key, value) tuples.
        """
        assert (self._inputs != None)
        request = HttpRequest()
        request.method = 'POST'
        # encode the inputs UNICODE to str
        for index, value in enumerate(inputs):
            if self._inputs[value[0]].dataType == 'ComplexData':
                pass
            elif isinstance(value[1], unicode):
                inputs[index] = (value[0], value[1].encode())
            else:
                inputs[index] = (value[0], str(value[1]))
                
        execute = wps.WPSExecution()
        request.META['QUERY_STRING'] = StringIO(etree.tostring(execute.buildRequest(identifier, inputs)))
        
        wpssvr = get_object_or_404(WPSService, username = provider)
        return wps_request(request, os.path.join(wpssvr.repertorydir, wpssvr.configfile))
    
    def _inputsParse(self, provider, identifier):
        """
        parse the describe document of process 
        
        @param provider: the owner of this process
        @param identifier: the requested process identifier
        
        @return: inputs dict of this process
        """
        request = self.request
        request.method = 'GET'        
        request.META['QUERY_STRING'] = 'service=wps&version=1.0.0&request=DescribeProcess&identifier={0}'.format(self.kwargs.get('identifier'))
        wpssvr = get_object_or_404(WPSService, username = provider)
        describe = wps_request(request, os.path.join(wpssvr.repertorydir, wpssvr.configfile))
        
        etree = wps.WPSDescribeProcessReader().readFromString(describe)
        
        # TODO: catch exception, as InvalidParameterValue , and do some things ...   
        
        self.identifier =  etree.xpath('//ProcessDescription/ows:Identifier', namespaces=etree.nsmap)[0].text
        
        inputs = {}

        for v in etree.xpath('//Input', namespaces=etree.nsmap):
            input = wps.Input(v)
            inputs[input.identifier] = input
        
        return inputs
    
class UpdateProfileView(FormView):
    """
    upload an profie
    
    return an json data that list all the process added if success, 
    
    TODO1: it's may be better to popup an message box that list all the processes added
    TODO2: only the administrator have the permission of updating profile (添加之前需要用户登录并获取管理员权限) 
    """
    form_class = ProfileUploadForm
    
    def get_context_data(self, **kwargs):
        context = super(UpdateProfileView, self).get_context_data(**kwargs)
        #context['GEONODE_CLIENT_LOCATION'] = settings.GEONODE_CLIENT_LOCATION
        return context
    
    def form_valid(self, form):
        try:
            p_file = form.write_file()
            
            #TODO: change the 'zzpwelkin' user to permission manage
            ps = WPSService.objects.get(username = self.user.username).update_profile(p_file) 

            # it's may be better to popup an message box that list all the processes added 
            return HttpResponse(json.dumps({
                "success": True,
                "addedprocess": ps}))
        except Exception, e:
            logger.exception("Unexpected error during upload.")
            return HttpResponse(json.dumps({
                "success": False,
                "errormsgs": ["Unexpected error during upload: " + escape(str(e))]}))
        finally:
            if os.path.exists(p_file):
                    os.remove(p_file)
        
        
