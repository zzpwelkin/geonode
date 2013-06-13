import os
from contextlib import closing
from owslib import wps

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.db.models.signals import post_save, pre_delete
from django.core.urlresolvers import reverse

from geonode.wpsprocess.repertory import RepertoryManager, Repertory
from geonode.wpsprocess.utils import wps_request

# Create your models here.

class WPSService(User):
    """
    @param serviceurl:
    @param repertorydir: 
    @param configfile:
    """    
    serviceurl = models.URLField()
    repertorydir = models.CharField(max_length=200)
    configfile = models.CharField(max_length=50)
    #user = models.OneToOneField(User, related_name = 'wpsservice')
    
    def __unicode__(self):
        return u"user:{0} \n email:".format(self.username, self.email)
    
    def update_profile(self, file):
        """
        update an profile file, one profile consisted in one or more  process,
        if this profile not exit then will be added
        
        @param file: profile path. file name will be as profile name in repertory
        """
        _rep = Repertory(self.repertorydir, self.configfile)
        processlist = []
        # if this profile file exit then first remove the records in Process model
        profile_name = os.path.split(file)[1]
        if (_rep.is_profile_exit(profile_name)):
            for p in self.process_set.filter(profile=profile_name):
                p.delete()

        # update this file to repertory
        with closing(open(file)) as f:
            _rep.update_profile(profile_name, f)
        
        # first get all processes from this profile
        #wpssrv = WPSService.objects.get(user = self._user)
        conf = os.path.join( self.repertorydir,  self.configfile)
        req = HttpRequest()
        req.method = 'GET'
        req.META['QUERY_STRING'] = 'service=wps&version=1.0.0&request=GetCapabilities'
        
        # get lxml elem tree with owslib
        captree = wps.WPSCapabilitiesReader().readFromString(wps_request(req, conf))
        
        # insert every process to Process model
        for p in (captree.xpath('./wps:ProcessOfferings',namespaces=captree.nsmap)[0]).getchildren():
            p = wps.Process(p)
            _version = '1.0'
            _abstract = ''
            _manual = None
            if hasattr(p, 'abstract'):
                _abstract = p.abstract
                if p.abstract.startswith('http://'):
                    _manual = p.abstract
            if hasattr(p, 'processVersion'):
                _version = p.processVersion
                
            Process.objects.create(identifier = p.identifier, version = _version, 
                                   title = p.title, abstract = _abstract, manual_link = _manual,
                                   topiccategory = TopicCategory.objects.get(slug = 'miscellaneous'), 
                                   wpsservice = self,
                                   created_time = timezone.now(), recent_changed_time = timezone.now(),
                                   profile = profile_name)
            
            processlist.append((p.identifier, p.processVersion))
            
        return processlist
    
def wpsservice_create_of_user(instance, sender, **kwargs):
    wpsservice = WPSService(user_ptr=instance)
    wpsservice.__dict__.update(instance.__dict__)
    #wpsservice.update(repertorydir = os.path.join(settings.WPS['repertory'], instance.username),
    #                  configfile = 'wps.cfg')
    wpsservice.serviceurl = reverse('wps_global_dispatch', args=( instance.username,))
    wpsservice.repertorydir = os.path.join(settings.WPS['repertory'], instance.username)
    wpsservice.configfile = 'wps.cfg'
    wpsservice.save()
    
    # set the wps repertory for that user
    RepertoryManager().create(wpsservice)
    
    #post_save.connect(receiver=wpsservice_create_of_user, sender=User)
        
def wpsservice_delete_of_user(instance, sender, **kwargs):
        wpsservice = WPSService.objects.get(user_ptr=instance)
        
        # delete all the process from table
        for p in wpsservice.process_set.all():
            p.delete()
        
        # delete the repertory of this service
        RepertoryManager().delete(wpsservice)
        
        # delete the service
        wpsservice.delete()
        
        #post_delete.connect(receiver=wpsservice_create_of_user, sender=User)

class TopicCategory(models.Model):

    name = models.CharField(max_length=50)
    slug = models.SlugField()
    description = models.TextField(blank=True)

    def __unicode__(self):
        return u"{0}".format(self.name)

    class Meta:
        ordering = ("name",)
        
class Process(models.Model):
    identifier = models.CharField(max_length=20)
    version = models.CharField(max_length=10)
    title = models.TextField()
    abstract = models.TextField()
    profile = models.CharField(max_length=20, blank = False, null = False, help_text='profile file name in which this process publishing implement')
    #keywords = TaggableManager('keywords', blank=True, help_text='commonly used word(s) or formalised word(s) or phrase(s) used to describe the subject (space or comma-separated')
    manual_link = models.URLField(null=True, help_text="the url where describe the process's using method in detail, even more with example and implement method")
    created_time = models.DateTimeField()
    recent_changed_time = models.DateTimeField()
    topiccategory = models.ForeignKey(TopicCategory)
    wpsservice = models.ForeignKey(WPSService)
    
if 'geonode.wpsprocess' in settings.INSTALLED_APPS:
    post_save.connect(receiver=wpsservice_create_of_user, sender=User)
    pre_delete.connect(receiver=wpsservice_delete_of_user, sender=User)
    