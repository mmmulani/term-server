import fcntl
import os
import termios

from io_handler import IOHandler
from task_runner import TaskRunner

class ProcessServer:
  def __init__(self, io_handler):
    self.io_handler = io_handler
    self.io_handler.process_server = self
    self.task_runners = []
    self.term_size = (80, 24)

  def handle_client_message(self, msg_type, content):
    import server
    server.log("got a message of type {0}".format(msg_type))
    func_name = '_msg_' + msg_type
    if hasattr(self, func_name):
      server.log("sending the message..")
      getattr(self, func_name)(**content)

  def _send_message(self, msg_type, content):
    self.io_handler.send_message(msg_type, content)

  def start(self):
    # If we are connected to a TTY, remove our connection to it.
    try:
      tty_fd = os.open('/dev/tty', os.O_RDWR)
      fcntl.ioctl(tty_fd, termios.TIOCNOTTY)
    except OSError as e:
      pass

    os.environ['TERM'] = 'xterm-256color'

    self._msg_make_enough_terms(amount=1)

    self.inform_about_directory(os.getcwd())

  def inform_about_directory(self, directory):
    directory = os.path.abspath(directory)
    items = [x for x in os.listdir(directory) if x[0] != '.']
    result = {}
    for item in items:
      result[item] = os.path.isdir(directory + '/' + item)
    self._send_message('directory_info', { directory: result })

  '''
  Methods that start with _msg_ are automatically called when a message with the
  same "type" field is received.
  For example, _msg_make_enough_terms is called when a message with
  "make_enough_terms" for its "type" field is received. Furthermore, the
  "message" field is used as a dictionary for the arguments.
  '''
  def _msg_make_enough_terms(self, amount):
    for i in range(amount - len(self.task_runners)):
      tr = TaskRunner(self)
      tr.start_shell()
      self.task_runners.append(tr)

  def _msg_dir_change(self, directory):
    import server
    server.log('changing directory to {0}'.format(directory))
    if not os.path.isabs(directory):
      directory = os.path.normpath(os.environ['PWD'] + '/' + directory)
    try:
      os.chdir(directory)
    except os.error as e:
      self._send_message('dir_change_fail', {"directory": directory})
      return

    os.environ['PWD'] = directory

    server.log('looks like we changed directory')

    self.inform_about_directory(directory)

    self._send_message('changed_directory', {"directory": directory})

  def _msg_handle_input(self, identifier, input):
    for tr in self.task_runners:
      if tr.identifier == identifier:
        tr.write_input(input)
        return

    # TODO: Log unhandled input.

  def _msg_start_task(self, identifier, arguments):
    for tr in self.task_runners:
      if tr.available():
        tr.run_program_in_tty(identifier, arguments)
        return

    import server
    server.log("no task runners were available!!")

  def _msg_exit(self):
    os.killpg(0, 9)

  def _msg_resize(self, rows, columns):
    self.term_size = (int(columns), int(rows))
    for tr in self.task_runners:
      tr.resize_terminal()
