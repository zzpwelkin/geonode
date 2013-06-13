#-*-coding:utf8-*-
"""
"""
import os, logging
from owslib import wps
from pywps import Pywps
from pywps.Exceptions import NoApplicableCode, WPSException

logger = logging.getLogger(__name__)

def wps_request(req, wps_cfg):
    """
    requst from local wps service and reponse the result documennt of processed
    
    @param  req: HttpRequest instance
    @param wps_cfg: the configure file that pywps need
       
    @return: an string document
    """
    res = 'Error'
    inputQuery = req.META['QUERY_STRING']
    logger.info("Query of wps service is : {0}".format(inputQuery))

    if not inputQuery:
        err =  NoApplicableCode("No query string found.")
        res = err.__str__()
        
    # create the WPS object
    os.environ['PYWPS_CFG'] = wps_cfg
    try:
        # setting configure file from Pywps initial not effect
        wps = Pywps(req.method, wps_cfg)
        if wps.parseRequest(inputQuery):
            res = wps.performRequest()
        else:
            msg = "wps service parse request failed! "
            logger.warn(msg)
            res = msg
    except WPSException,e:
        res = e.__str__()

    return res

