import json
import sys

from multiprocessing import Queue
from threading import Thread

class IOHandler:
  def __init__(self):
    self.process_server = None
    self.output_queue = Queue()

    t = Thread(target=self.read_loop)
    t.start()
    t = Thread(target=self.write_loop)
    t.start()

  def send_message(self, msg_type, content):
    self.output_queue.put({
      'type': msg_type,
      'message': content,
    })

  def read_loop(self):
    while True:
      command = json.loads(sys.stdin.readline().rstrip('\n'))
      '''
      log('Got command with type {0}'.format(command['type']))
      if command['type'] == 'start_task':
        log('Going to run command with arguments {0}'.format(command['message']))
      elif command['type'] == 'exit':
        log('Exiting')
        os.kill(os.getpgid(0), signal.SIGKILL)
      '''
      msg_type = command['type']
      content = command['message']
      self.process_server.handle_client_message(msg_type, content)

  def write_loop(self):
    while True:
      output = self.output_queue.get()
      # log('Sending output with type {0}'.format(output['type']))
      sys.stdout.write(json.dumps(output))
      sys.stdout.write('\n')