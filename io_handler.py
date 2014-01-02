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

      msg_type = command['type']
      content = command['message']
      self.process_server.handle_client_message(msg_type, content)

  def write_loop(self):
    while True:
      output = self.output_queue.get()
      sys.stdout.write(json.dumps(output))
      sys.stdout.write('\n')