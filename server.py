import json
import logging
import os
import pty
import signal
import sys

from multiprocessing import Process, Queue
from threading import Thread

import task_runner

from io_handler import IOHandler
from process_server import ProcessServer

def log(msg):
  global logger
  logger.info(msg)

if __name__ == '__main__':
  logger = logging.getLogger('server')
  logger.setLevel(logging.DEBUG)
  fh = logging.FileHandler('server.log')
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  fh.setFormatter(formatter)
  fh.setLevel(logging.DEBUG)
  logger.addHandler(fh)

  logger.info('--- started server ---')

  io_handler = IOHandler()
  process_server = ProcessServer(io_handler)

  task_runner.start(process_server.task_runner)