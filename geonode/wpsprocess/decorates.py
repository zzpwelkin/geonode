import logging, re, uuid
from urllib2 import urlparse, unquote
from owslib import wps
from geoserver import resource

from django.conf import settings 
from django.core.urlresolvers import reverse

from geonode.layers.models import Layer
from geonode.layers.utils import add_record_of_resource, projection_and_bbox_checked

logger = logging.getLogger('geonode.wpsprocess.decorates')

def geonode_filter(user, response_doc):
    """
    the filter that add recodes of reference results of execute to geonode 
    
    @param response_doc: response document of one process executed
    @return:  
    """
    execution = wps.WPSExecution()
    execution.parseResponse(wps.WPSExecuteReader().readFromString(response_doc))
    
    if execution.isSucceded():
        identifier = execution.process.identifier
    else:
        raise execution.errors[0]
    
    logger.info("Create the geonode records for the output of {0} process".format(execution.process.identifier))
    redirect_layer = []
    for output in execution.processOutputs:
        logging.info('output {0} with reference: {1}'.format(output.identifier, output.reference))
        if output.reference:
            output_ref = output.reference
            
            # parse WCS or WFS REST API and get the storename/workspacename/resourcename
            pres = urlparse.urlparse(unquote(output_ref))
            
            if 'image/tiff' in output.mimeType:
                name = urlparse.parse_qs(pres.query)['COVERAGE'][0]
                
            elif 'application/zip' in output.mimeType:
                name = urlparse.parse_qs(pres.query)['TYPENAME'][0]
            else:
                #TODO: add the document to database and add records to geonode
                return
            
            cat = Layer.objects.gs_catalog
                
            mth = re.match('.*/(?P<wk>[_\w]+?)/wcs', pres.path)
            workspace = mth.groupdict()['wk']
            
            if workspace == 'default':
                wk = cat.get_default_workspace()
            else:
                wk = cat.get_workspace(workspace)
            
            resource = cat.get_resource(name, workspace = wk)
            
            logger.info('Check if the projection and bbox is right of resource {0}'.format(resource.name))
            projection_and_bbox_checked(resource)
            
            logger.info('Add record of resource {0}'.format(resource.name))
            saved_layer = add_record_of_resource(user, resource)
            
            return saved_layer
    
    