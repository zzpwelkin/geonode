import os,sys
import shutil
import logging
from contextlib import closing
from exceptions import SystemExit

from django.conf import settings

logger = logging.getLogger('geonode.wpsprocess.repertory')

class Repertory:
    """responsibility
    Repertory's responsibility is:
    1. manager execute files, profile, dependency describe file, dependency library files for each process
    2. the process version manager (like Git to source file)
    """
    def __init__(self, repPath, conf):
        self._pkgpath, self._pkgname = os.path.split(repPath)
        self._configfile = conf
        
    def is_profile_exit(self, name):
        """
        if the named profile exit 
        
        @param name: the profile name
        """
        return os.path.exists(os.path.join(self._pkgpath, self._pkgname, name))
        
#    def delete_profile(self, name):
#        """
#        delete an profile 
#        
#        @param name: the name of profile will be deleted
#        """
#        sys.path.append(self._pkgpath)
#        module = __import__(self._pkgname)
#        module.__all__.remove(os.path.splitext(name)[0])
#        with closing(open(os.path.join(self._pkgpath, self._pkgname, "__init__.py"), 'w')) as f:
#            __all = str(module.__all__)
#            f.write('__all__ = '+ __all[:-1] + ',' + __all[-1])
#            
#        os.remove(os.path.join(self._pkgpath, self._pkgname, name))
#    
#    def update_profile(self, name, f, commit=None):
#        """
#        update an profile 
#        
#        @param name: profile name that wanted to be updated
#        @param f: input stream with service profile context, f stream will not be closed in that method
#        @param commit: commit what the resion is for update that profile 
#        """
#        
#        profile = os.path.join(self._pkgpath, self._pkgname, name)
#        # add or update profile
#        if os.path.exists(profile):
#            #TODO: add the version manage, now just remove it
#            logger.info("remove exited profile {0} in {1} repertory".format(name, self._pkgname))
#            self.delete_profile(name)
#        
#        with closing( open( profile, 'w') ) as pf:
#            pf.write(f.read())
#        
#        sys.path.append(self._pkgpath)
#        module = __import__(self._pkgname)
#        if os.path.splitext(name)[0] not in module.__all__:
#            module.__all__.append(os.path.splitext(name)[0])
#            
#        # logger write
#        logger.info('All the profiles in repertory {0} is {1}'.format(self._pkgname, str(module.__all__)))
#            
#        with closing(open(os.path.join(self._pkgpath, self._pkgname, "__init__.py"), 'w')) as f:
#            __all = str(module.__all__)
#            # add an comma at the end of __all__
#            f.write('__all__ = '+ __all[:-1] + ',' + __all[-1])
    
    def delete_process(self, identifier, version):
        """
        delete an process from repertory
        
        @param name: process name 
        @param version: process version
        """
        sys.path.append(repPath)
        
    
    def update_process(self):
        pass
    
class RepertoryManager:
    """
    manager repertory, as create, delete, 
    """
    def create(self, wpsservice, isDel=True):
        """
        create an new repertory for the user
        
        @param  user: the instance of User model
        @param wpsservice: the WPSService instance
        @param  isDel: if delete the repertory directory if the repertory have exited, 
            an SystemExit exception will be raised if the repertory directory exit and 
            isDel was False
        
        @return: an instance of Repertory
        """
#        if (not rep) or (not conf):
#            msg = "The repertory or configure file not set for {0} user's process service".format(wpsservice.username)
#            logger.error(msg)
#            #TODO: need cacrete Exception type
#            raise Exception(msg)
        
        if (os.path.exists(wpsservice.repertorydir)):
            if (isDel):
                msg = "The process repertory of user {0} have exit and will be deleted!".format(wpsservice.username)
                logger.warn(msg)
                shutil.rmtree(wpsservice.repertorydir)
            else:
                msg = "The process repertory of user {0} have exit".format(wpsservice.username)
                raise SystemExit(msg)
            
        
        os.mkdir(wpsservice.repertorydir)
        with closing(open(os.path.join(wpsservice.repertorydir, '__init__.py'), 'w')) as f:
            f.write('__all__ = []')
            
        # copy template configure file and reset the parameter for user
        shutil.copy(settings.WPS['defconfigure'], os.path.join(wpsservice.repertorydir, wpsservice.configfile))
        self._set_config_of_service(wpsservice)
        
        return Repertory(wpsservice.repertorydir, wpsservice.configfile)
    
    def delete(self, wpsservice):
        """
        delete an repertory associated an user
        """
        if (os.path.exists(wpsservice.repertorydir)):
            shutil.rmtree( wpsservice.repertorydir)
            
    def _set_config_of_service(self, wpsservice):
        """
        reset the configure file for this user
        """
        import ConfigParser
        conf = ConfigParser.ConfigParser()
        conf.read(os.path.join(wpsservice.repertorydir, wpsservice.configfile))
        
        # wps reset
        conf.set('wps', 'serveraddress', wpsservice.serviceurl)
        
        # provider information reset
        conf.set('provider', 'providerName', wpsservice.get_full_name())
        conf.set('provider', 'individualName', wpsservice.username)
        conf.set('provider', 'electronicMailAddress', wpsservice.email)
        
        # geoserver service username and password setting
#        conf.set('geoserver', 'username', wpsservice.username)
#        conf.set('geoserver', 'password', wpsservice.password)
        
        # server reset
        conf.set('server', 'processesPath', wpsservice.repertorydir)
        conf.set('server', 'logFile', conf.get('server', 'logFile').format(wpsservice.username + ".log"))
        
        with closing(open(os.path.join(wpsservice.repertorydir, wpsservice.configfile), 'w')) as f:
            conf.write(f)
              