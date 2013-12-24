from multiprocessing import Process, Queue
from threading import Thread
import json
import pty
import os
import sys
import logging

import task_runner

def log(msg):
  global logger
  logger.info(msg)

def command_run_loop():
  global main_queue

  while True:
    command = json.loads(sys.stdin.readline().rstrip('\n'))
    log('Got command with type {0}'.format(command['type']))
    if command['type'] == 'start_task':
      log('Going to run command with arguments {0}'.format(command['message']))
    
    main_queue.put(command)

def child_run_loop():
  global output_queue

  while True:
    output = output_queue.get()
    log('Sending output with type {0}'.format(output['type']))
    sys.stdout.write(json.dumps(output))
    sys.stdout.write('\n')

if __name__ == '__main__':
  logger = logging.getLogger('server')
  logger.setLevel(logging.DEBUG)
  fh = logging.FileHandler('server.log')
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  fh.setFormatter(formatter)
  fh.setLevel(logging.DEBUG)
  logger.addHandler(fh)

  logger.info('--- started server ---')

  main_queue = Queue()
  output_queue = Queue()
  p = Process(target=task_runner.start, args=(main_queue, output_queue))
  p.start()

  t = Thread(target=command_run_loop)
  t.start()
  t = Thread(target=child_run_loop)
  t.start()