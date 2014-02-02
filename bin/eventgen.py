'''
Copyright (C) 2005-2014 Splunk Inc. All Rights Reserved.
'''

# TODO Allow override of any configuration variable from the command line

from __future__ import division

import sys, os
path_prepend = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lib')
sys.path.append(path_prepend)

import logging
import threading
import multiprocessing
import time
import datetime
from select import select
from eventgenconfig import Config
from eventgentimer import Timer
from eventgenoutput import Output

if __name__ == '__main__':
    c = Config()
    # Logger is setup by Config, just have to get an instance
    logger = logging.getLogger('eventgen')
    logger.info('Starting eventgen')
    
    # 5/6/12 CS use select to listen for input on stdin
    # if we timeout, assume we're not splunk embedded
    # Only support standalone mode on Unix due to limitation with select()
    if os.name != "nt":
        rlist, _, _ = select([sys.stdin], [], [], 1)
        if rlist:
            sessionKey = sys.stdin.readline().strip()
        else:
            sessionKey = ''
    else:
        sessionKey = sys.stdin.readline().strip()
    
    if len(sessionKey) > 0:
        c.makeSplunkEmbedded(sessionKey=sessionKey)
        
    c.parse()

    t = Timer(1.0, interruptcatcher=True)

    for s in c.samples:
        if s.interval > 0 or s.mode == 'replay':
            if s.backfillSearchUrl == None:
                s.backfillSearchUrl = s.splunkUrl
            logger.info("Creating timer object for sample '%s' in app '%s'" % (s.name, s.app) )    
            t = Timer(1.0, s) 
            c.sampleTimers.append(t)
    

    first = True
    outputQueueCounter = 0
    generatorQueueCounter = 0
    while (1):
        try:
            ## Only need to start timers once
            if first:
                if os.name != "nt":
                    c.set_exit_handler(c.handle_exit)
                c.start()
                first = False

            # Every 5 seconds, get values and output basic statistics about our operations
            generatorDecrements = c.generatorQueueSize.totaldecrements()
            outputDecrements = c.outputQueueSize.totaldecrements()
            generatorsPerSec = (generatorDecrements - generatorQueueCounter) / 5
            outputtersPerSec = (outputDecrements - outputQueueCounter) / 5
            outputQueueCounter = outputDecrements
            generatorQueueCounter = generatorDecrements
            logger.info('Output Queue depth: %d  Generator Queue depth: %d Generators Per Sec: %d Outputters Per Sec: %d' % (c.outputQueueSize.value(), c.generatorQueueSize.value(), generatorsPerSec, outputtersPerSec))
            kiloBytesPerSec = c.bytesSent.valueAndClear() / 5 / 1024
            gbPerDay = (kiloBytesPerSec / 1024 / 1024) * 60 * 60 * 24
            eventsPerSec = c.eventsSent.valueAndClear() / 5
            logger.info('Events/Sec: %s Kilobytes/Sec: %1f GB/Day: %1f' % (eventsPerSec, kiloBytesPerSec, gbPerDay))
            time.sleep(5)
        except KeyboardInterrupt:
            c.handle_exit()