#-*- coding:utf-8 -*-
# Create your views here.

import os, sys
import logging
from lxml import etree
from StringIO import StringIO
from urllib2 import urlparse
from owslib import wps
import traceback

from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.utils import simplejson as json
from django.utils.html import escape
from django.shortcuts import get_object_or_404
from django.views.generic import View, ListView
from django.views.generic.edit import FormView

from pywps.models import TopicCategory
from pywps.views import WpsStandardServiceApi as WpsStandardServiceApiBase
from geonode.wpsprocess.utils import *
from geonode.wpsprocess.models import Process as GeonodeProcess
from geonode.wpsprocess.models import *
from geonode.wpsprocess.repertory import *
from geonode.wpsprocess.forms import *
from geonode.wpsprocess.decorates import geonode_filter
from geonode.utils import get_query

from geonode.layers.models import Layer

logger = logging.getLogger('geonode.wpsprocess.view')

class WpsStandardServiceApi(WpsStandardServiceApiBase):
    """request to wps service for spectial user,and need login if the request is Execute"""
    def get(self, request, *args, **kwargs):
        provider = kwargs['provider']
        if not User.objects.get_by_natural_key(provider):
            return HttpResponseNotFound()

        logger.debug('provider is {0}'.format(provider))
        wpssvr = get_object_or_404(WPSService, username = provider)
        return HttpResponse (self.wps_request(request, os.path.join(wpssvr.repertorydir, wpssvr.configfile)), mimetype='application/xml')
    
    def post(self, request, *args, **kwargs):
        provider = kwargs['provider']
        if not User.objects.get_by_natural_key(provider):
            return HttpResponseNotFound()

        logger.debug('provider is {0}'.format(provider))
        wpssvr = get_object_or_404(WPSService, username = provider)
        return HttpResponse (self.wps_request(request, os.path.join(wpssvr.repertorydir, wpssvr.configfile)), mimetype='application/xml')
    
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
        found_entries = GeonodeProcess.objects.all()
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
        #doc['manual_link'] = p.manual_link
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
            return GeonodeProcess.objects.all()
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
    
class ProcessExecuteView(FormView, WpsStandardServiceApiBase):
    
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
                kwargs['coverages'].append((layer.uuid, layer.title))
            elif layer.storeType == 'featureStore':
                kwargs['features'].append((layer.uuid, layer.title))

        logger.info('the values of form is : {0}'.format(str(kwargs)))
        return kwargs
    
    def form_valid(self, form):
        #super(ProcessExecuteView, self).form_valid(form)
        
        vals = []
        for field in form.fields:
            vals.append( (field, form.cleaned_data[field]))
        
        logger.info("{0} process's input paramter is:{1}".format(self.kwargs.get('identifier'), str(vals)))
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
                logger.info('{0} {1}'.format(type(value[1]), str(value[1])))
                layer = Layer.objects.get(uuid = value[1])
                if not layer:
                    raise Exception('No such layer')

                for lk in layer.link_set.data():
                    if lk.name.lower() == 'geotiff':
                        inputs[index] = (value[0], lk.url.encode())
                
            elif isinstance(value[1], unicode):
                inputs[index] = (value[0], value[1].encode())
            else:
                inputs[index] = (value[0], str(value[1]))
           
        execute = wps.WPSExecution()
        request.META['QUERY_STRING'] = StringIO(etree.tostring(execute.buildRequest(identifier, inputs)))
        
        wpssvr = get_object_or_404(WPSService, username = provider)
        return self.wps_request(request, os.path.join(wpssvr.repertorydir, wpssvr.configfile))
    
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
        describe = self.wps_request(request, os.path.join(wpssvr.repertorydir, wpssvr.configfile))
    
        etree = wps.WPSDescribeProcessReader().readFromString(describe)
        
        # TODO: catch exception, as InvalidParameterValue , and do some things ...   
        
        self.identifier =  etree.xpath('//ProcessDescription/ows:Identifier', namespaces=etree.nsmap)[0].text
        
        inputs = {}

        for v in etree.xpath('//Input', namespaces=etree.nsmap):
            input = wps.Input(v)
            inputs[input.identifier] = input
        
        return inputs
    
class UploadProccessView(FormView):
    form_class = UpLoadProcessForm
    #success_url = reverse('process_browse')
    
    def delete_without_success(self, process, meta, inputoutputs):
        """
        delete the added new record of process, as process and it's input ,output and metadata recursive.
        
        @param process: process that added
        @param meta: meta added new record of process
        @param inputoutputs: an dictionary of inputs and outpus of format is {field_name:[new_record1,new_record2],...}
        """
        # disassociate the meta of process and delete meta
        if meta:
            meta.process_set.clear()
            for _m in meta:
                _m.delete()
        
        # first delete the inputs and ouputs then disassociate the relation to process  
        if inputoutputs:
            for fname, values in inputoutputs.iteritems():
                for v in values:
                    v.delete_recursive()
                    v.__getattribute__(fname+'_set').clear()
        
        # delete process           
        if process:
            process.delete()
            
    
    def meta_field_save(self, data):
        """
        save metadata and return objects added
        
        @param data: an list or tuple that contain many {Meta} value, as, [{'a','http://a.com','b','http://b.com'...}]
        
        @return: list of objects
        """
        new_obj = []
        for d in data:
            new_obj.append(Meta.objects.create(title = d['title'], link = d['link']))
            
        return new_obj
    
    def manytomany_field_save(self, data):
        """
        save manytomany field and return objects added
        
        @param data: data from form.cleaned_data
        @return: dictionary with format: {field_name:added_object, ...}
        """
        model_map = {'LiteralDataInput':LiteralDataInput, 'LiteralDataOutput':LiteralDataOutput, 
                     'ComplexDataInput':ComplexData, 'ComplexDataOutput':ComplexData,}
        res = {}
        try:
            for field in Process._meta.many_to_many:
                # filter the metadata or some manytomany fields that not consideration
                if not model_map.has_key(field.name):
                    continue
                
                res[field.name] = []
                for form_data in data[field.name]:                      
                    data_dic = {}
                    for attr_field in model_map[field.name]._meta.fields:
                        if attr_field.name not in ( 'id', 'processbase_ptr', 'input_ptr', ):
                            if form_data.get(attr_field.name, None):
                                data_dic[attr_field.name] = form_data[attr_field.name]
                                
                    new_obj = model_map[field.name].objects.create(**data_dic)
                    
                    # add supported format for complexdata
                    if model_map[field.name] == ComplexData:
                        supported = [ data_dic['Default'] ] + data_dic.get('Supported', [])
                        new_obj.Supported.add(*supported)
                        
                    # add metadata  
                    meta = self.meta_field_save(form_data['Metadata'])
                    if meta:
                        new_obj.add(*meta)
                    res[field.name].append(new_obj)
                
        except Exception, e:
            traceback.print_exc(file=sys.stderr)
            self.delete_without_success(None, None, res)
            logger.exception(e)
            
        return res
        
    def form_valid(self, form):
        try:
            data_dic = {}
            manytomany_data_dic = self.manytomany_field_save(form.cleaned_data)
            logger.info('manytomany files value is: {0}'.format(str(manytomany_data_dic)))
            
            meta = self.meta_field_save(form.cleaned_data['Metadata'])
            logger.info('meta of this process is: {0}'.format(str(meta)))
            
            for field in Process._meta.fields:
                if field.name not in ( ( 'id', 'created_time', 'recent_changed_time','processbase_ptr', ) + self.form_class.Meta.exclude):
                    data_dic[field.name] = form.cleaned_data[field.name]
                     
            data_dic['wpsservice'] = WPSService.objects.get(username=self.request.user.username)
            data_dic['WSDL'] = data_dic['wpsservice'].serviceurl+'?WSDL'
            data_dic['Profile'] = 'OGC::WPS::ZZP'
            process = GeonodeProcess(**data_dic)
            process.save()
            
            # if metadata was setted then add them to process
            if meta:
                process.Metadata.add(*meta)
            
            # if manytomany field, as ComplexDataInput, was setted then add them to process
            if manytomany_data_dic:
                for m2m_name, m2m_value in manytomany_data_dic.iteritems():
                    process.setInputorOuputValue(m2m_name, m2m_value)
                
        except Exception, e:
            #log the traceback information
            #traceback.print_exc(file=sys.stderr)
            error_str = StringIO()
            traceback.print_exc(file = error_str)
            logger.error(error_str.getvalue())
            
            # delete all the information with this failed process
            if locals().has_key('manytomany_data_dic'):
                self.delete_without_success(locals().get('process', None), locals().get('meta'), locals().get('manytomany_data_dic', None))
                    
            return HttpResponse("Failed with the resion :{0}".format(e))
        
        return HttpResponse('success')
        
    
#class UpdateProfileView(FormView):
#    """
#    upload an profie
#    
#    return an json data that list all the process added if success, 
#    
#    TODO1: it's may be better to popup an message box that list all the processes added
#    TODO2: only the administrator have the permission of updating profile (添加之前需要用户登录并获取管理员权限) 
#    """
#    form_class = ProfileUploadForm
#    
#    def get_context_data(self, **kwargs):
#        context = super(UpdateProfileView, self).get_context_data(**kwargs)
#        #context['GEONODE_CLIENT_LOCATION'] = settings.GEONODE_CLIENT_LOCATION
#        return context
#    
#    def form_valid(self, form):
#        try:
#            p_file = form.write_file()
#            
#            #TODO: change the 'zzpwelkin' user to permission manage
#            ps = WPSService.objects.get(username = self.user.username).update_profile(p_file) 
#
#            # it's may be better to popup an message box that list all the processes added 
#            return HttpResponse(json.dumps({
#                "success": True,
#                "addedprocess": ps}))
#        except Exception, e:
#            logger.exception("Unexpected error during upload.")
#            return HttpResponse(json.dumps({
#                "success": False,
#                "errormsgs": ["Unexpected error during upload: " + escape(str(e))]}))
#        finally:
#            if os.path.exists(p_file):
#                    os.remove(p_file)
        
        
