#! /usr/bin/env python

'''
Description: Read all lines from STDIN and process them.

License: NASA Open Source Agreement 1.3
'''

import os
import sys
import shutil
import socket
import json
import datetime
from time import sleep
from argparse import ArgumentParser

# local objects and methods
import settings
import utilities
import sensor
from logging_tools import EspaLogging

# local objects and methods
from environment import Environment
import parameters
import processor

import api_interface

from config_utils import retrieve_cfg


MAPPER_LOG_PREFIX = 'espa-mapper'
MAPPER_LOG_FILENAME = '.'.join([MAPPER_LOG_PREFIX, 'log'])


def set_product_error(server, order_id, product_id, processing_location):
    """Call the API server routine to set a product request to error

    Provides a sleep retry implementation to hopefully by-pass any errors
    encountered, so that we do not get requests that have failed, but
    show a status of processing.
    """

    if server is not None:
        logger = EspaLogging.get_logger(settings.PROCESSING_LOGGER)

        attempt = 0
        sleep_seconds = settings.DEFAULT_SLEEP_SECONDS
        while True:
            try:
                logger.info('Product ID is [{}]'.format(product_id))
                logger.info('Order ID is [{}]'.format(order_id))
                logger.info('Processing Location is [{}]'
                            .format(processing_location))

                logged_contents = \
                    EspaLogging.read_logger_file(settings.PROCESSING_LOGGER)

                status = server.set_scene_error(product_id, order_id,
                                                processing_location,
                                                logged_contents)

                if not status:
                    logger.critical('Failed processing API call to'
                                    ' set_scene_error')
                    return False

                break

            except Exception:
                logger.critical('Failed processing API call to'
                                ' set_scene_error')
                logger.exception('Exception encountered and follows')

                if attempt < settings.MAX_SET_SCENE_ERROR_ATTEMPTS:
                    sleep(sleep_seconds)  # sleep before trying again
                    attempt += 1
                    sleep_seconds = int(sleep_seconds * 1.5)
                    continue
                else:
                    return False

    return True


def get_sleep_duration(proc_cfg, start_time, dont_sleep):
    """Logs details and returns number of seconds to sleep
    """

    logger = EspaLogging.get_logger(settings.PROCESSING_LOGGER)

    # Determine if we need to sleep
    end_time = datetime.datetime.now()
    seconds_elapsed = (end_time - start_time).seconds
    logger.info('Processing Time Elapsed {0} Seconds'.format(seconds_elapsed))

    min_seconds = int(proc_cfg.get('processing',
                                   'espa_min_request_duration_in_seconds'))

    seconds_to_sleep = 1
    if dont_sleep:
        # We don't need to sleep
        seconds_to_sleep = 1
    elif seconds_elapsed < min_seconds:
        seconds_to_sleep = (min_seconds - seconds_elapsed)

    logger.info('Sleeping An Additional {0} Seconds'.format(seconds_to_sleep))

    return seconds_to_sleep


def archive_log_files(order_id, product_id):
    """Archive the log files for the current job
    """

    logger = EspaLogging.get_logger(settings.PROCESSING_LOGGER)

    try:
        # Determine the destination path for the logs
        output_dir = Environment().get_distribution_directory()
        destination_path = os.path.join(output_dir, 'logs', order_id)
        # Create the path
        utilities.create_directory(destination_path)

        # Job log file
        logfile_path = EspaLogging.get_filename(settings.PROCESSING_LOGGER)
        full_logfile_path = os.path.abspath(logfile_path)
        log_name = os.path.basename(full_logfile_path)
        # Determine full destination
        destination_file = os.path.join(destination_path, log_name)
        # Copy it
        shutil.copyfile(full_logfile_path, destination_file)

        # Mapper log file
        full_logfile_path = os.path.abspath(MAPPER_LOG_FILENAME)
        final_log_name = '-'.join([MAPPER_LOG_PREFIX, order_id, product_id])
        final_log_name = '.'.join([final_log_name, 'log'])
        # Determine full destination
        destination_file = os.path.join(destination_path, final_log_name)
        # Copy it
        shutil.copyfile(full_logfile_path, destination_file)

    except Exception:
        # We don't care because we are at the end of processing
        # And if we are on the successful path, we don't care either
        logger.exception('Exception encountered and follows')


def process(proc_cfg, developer_sleep_mode=False):
    """Read all lines from STDIN and process them

    Each line is converted to a JSON dictionary of the parameters for
    processing.  Validation is performed on the JSON dictionary to test if
    valid for this mapper.  After validation the generation of the products
    is performed.
    """

    # Initially set to the base logger
    logger = EspaLogging.get_logger('base')

    processing_location = socket.gethostname()

    # Process each line from stdin
    for line in sys.stdin:
        if not line or len(line) < 1 or not line.strip().find('{') > -1:
            # this is how the nlineinputformat is supplying values:
            # 341104        {"orderid":
            # logger.info('BAD LINE:{}##'.format(line))
            continue
        else:
            # take the entry starting at the first opening parenth to the end
            line = line[line.find('{'):]
            line = line.strip()

        # Reset these for each line
        (server, order_id, product_id) = (None, None, None)

        start_time = datetime.datetime.now()

        # Initialize so that we don't sleep
        dont_sleep = True

        try:
            line = line.replace('#', '')
            parms = json.loads(line)

            if not parameters.test_for_parameter(parms, 'options'):
                raise ValueError('Error missing JSON [options] record')

            # TODO scene will be replaced with product_id someday
            (order_id, product_id, product_type, options) = \
                (parms['orderid'], parms['scene'], parms['product_type'],
                 parms['options'])

            if product_id != 'plot':
                # Developer mode is always false unless you are a developer
                # so sleeping will always occur for none plotting requests
                # Override with the developer mode
                dont_sleep = developer_sleep_mode

            # Fix the orderid in-case it contains any single quotes
            # The processors can not handle single quotes in the email
            # portion due to usage in command lines.
            parms['orderid'] = order_id.replace("'", '')

            # If it is missing due to above TODO, then add it
            if not parameters.test_for_parameter(parms, 'product_id'):
                parms['product_id'] = product_id

            # Figure out if debug level logging was requested
            debug = False
            if parameters.test_for_parameter(options, 'debug'):
                debug = options['debug']

            # Configure and get the logger for this order request
            EspaLogging.configure(settings.PROCESSING_LOGGER, order=order_id,
                                  product=product_id, debug=debug)
            logger = EspaLogging.get_logger(settings.PROCESSING_LOGGER)

            logger.info('Processing {}:{}'.format(order_id, product_id))

            # Update the status in the database
            if parameters.test_for_parameter(parms, 'espa_api'):
                if parms['espa_api'] != 'skip_api':
                    server = api_interface.api_connect(parms['espa_api'])
                    if server is not None:
                        status = server.update_status(product_id, order_id,
                                                      processing_location,
                                                      'processing')
                        if not status:
                            msg = ('Failed processing API call'
                                   ' to update_status to processing')
                            raise api_interface.APIException(msg)

            if product_id != 'plot':
                # Make sure we can process the sensor
                tmp_info = sensor.info(product_id)
                del tmp_info

                # Make sure we have a valid output format
                if not parameters.test_for_parameter(options, 'output_format'):
                    logger.warning('[output_format] parameter missing'
                                   ' defaulting to envi')
                    options['output_format'] = 'envi'

                if (options['output_format']
                        not in parameters.VALID_OUTPUT_FORMATS):

                    raise ValueError('Invalid Output format {}'
                                     .format(options['output_format']))

            # ----------------------------------------------------------------
            # NOTE: The first thing the product processor does during
            #       initialization is validate the input parameters.
            # ----------------------------------------------------------------

            destination_product_file = 'ERROR'
            destination_cksum_file = 'ERROR'
            pp = None
            try:
                # All processors are implemented in the processor module
                pp = processor.get_instance(proc_cfg, parms)
                (destination_product_file, destination_cksum_file) = \
                    pp.process()

            finally:
                # Free disk space to be nice to the whole system.
                if pp is not None:
                    pp.remove_product_directory()

            # Sleep the number of seconds for minimum request duration
            sleep(get_sleep_duration(proc_cfg, start_time, dont_sleep))

            archive_log_files(order_id, product_id)

            # Everything was successfull so mark the scene complete
            if server is not None:
                status = server.mark_scene_complete(product_id, order_id,
                                                    processing_location,
                                                    destination_product_file,
                                                    destination_cksum_file,
                                                    '')
                if not status:
                    msg = ('Failed processing API call to'
                           ' mark_scene_complete')
                    raise api_interface.APIException(msg)

        except api_interface.APIException as excep:
            # This is expected when scenes have been cancelled after queueing
            logger.warning('Halt. API raised error: {}'.format(excep.message))

        except Exception as excep:

            # First log the exception
            logger.exception('Exception encountered stacktrace follows')

            # Sleep the number of seconds for minimum request duration
            sleep(get_sleep_duration(proc_cfg, start_time, dont_sleep))

            archive_log_files(order_id, product_id)

            if server is not None:
                try:
                    status = set_product_error(server,
                                               order_id,
                                               product_id,
                                               processing_location)
                except Exception:
                    logger.exception('Exception encountered stacktrace'
                                     ' follows')
        finally:
            # Reset back to the base logger
            logger = EspaLogging.get_logger('base')


def export_environment_variables(cfg):
    """Export the configuration to environment variables

    Supporting applications require them to be in the environmant

    Args:
        cfg <ConfigParser>: Configuration
    """

    for key, value in cfg.items('processing'):
        os.environ[key.upper()] = value


PROC_CFG_FILENAME = 'processing.conf'


def main():
    """Some parameter and logging setup, then call the process routine
    """

    # Create a command line argument parser
    description = 'Main mapper for a request'
    parser = ArgumentParser(description=description)

    # Add our only options to determine if we are a developer or not
    parser.add_argument('--developer',
                        action='store_true', dest='developer', default=False,
                        help='use a developer mode for sleeping')

    # Parse the command line arguments
    args = parser.parse_args()

    proc_cfg = retrieve_cfg(PROC_CFG_FILENAME)
    export_environment_variables(proc_cfg)

    EspaLogging.configure_base_logger(filename=MAPPER_LOG_FILENAME)
    # Initially set to the base logger
    logger = EspaLogging.get_logger('base')

    try:
        # Joe-Developer doesn't want to wait so if set skip sleeping
        developer_sleep_mode = args.developer

        process(proc_cfg, developer_sleep_mode)
    except Exception:
        logger.exception('Processing failed stacktrace follows')


if __name__ == '__main__':
    main()
