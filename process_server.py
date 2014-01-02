from io_handler import IOHandler
from task_runner import TaskRunner

class ProcessServer:
  def __init__(self, io_handler):
    self.io_handler = io_handler
    self.io_handler.process_server = self
    self.task_runner = TaskRunner(self)

  def handle_client_message(self, msg_type, content):
    self.task_runner.handle_client_message(msg_type, content)

  def _send_message(self, msg_type, content):
    self.io_handler.send_message(msg_type, content)