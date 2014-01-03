from multiprocessing import connection, Process, Queue
from threading import Thread
import binascii
import fcntl
import logging
import pty
import os
import random
import signal
import struct
import sys
import termios

current_pid = -1
logger = None
current_task_id = 0
fd_to_task = {}
all_fds = []
current_dir = None

send_to_shell = None
send_to_plex = None
send_to_shells = []

is_shell = False

task_runner = None

class TaskRunner:
  def __init__(self, process_server):
    self.process_server = process_server
    self.identifier = -1
    self.current_pid = None

  def start_shell(self):
    global term_size

    (self.master_fd, self.slave_fd) = pty.openpty()

    # Initialize the terminal.
    self.resize_terminal()

    control_chars = [b'\x04', b'\xff', b'\xff', b'\x7f', b'\x17', b'\x15', b'\x12', b'\xff', b'\x03', b'\x1c', b'\x1a', b'\x19', b'\x11', b'\x13', b'\x16', b'\x0f', b'\x01', b'\x00', b'\x14', b'\xff']
    control_chars.extend(b'\x00' for _ in range(termios.NCCS - len(control_chars)))
    termios.tcsetattr(self.master_fd, termios.TCSANOW, [
      termios.BRKINT | termios.ICRNL,
      termios.OPOST | termios.ONLCR,
      termios.CS8 | termios.CREAD | termios.HUPCL,
      termios.ECHOKE | termios.ECHOE | termios.ECHOK | termios.ECHO | termios.ECHOCTL | termios.ISIG | termios.ICANON | termios.IEXTEN | termios.PENDIN,
      termios.B230400,
      termios.B230400,
      control_chars,
      ])

    t = Thread(target=self.read_thread)
    t.start()

  def write_input(self, input):
    import server
    try:
      n = os.write(self.master_fd, bytes.fromhex(input))
    except OSError as e:
      server.log('error writing bytes: {0}'.format(str(e)))

  def read_thread(self):
    while True:
      try:
        output = os.read(self.master_fd, 1024)
      except OSError as e:
        import server
        server.log('read thread error: {0}'.format(str(e)))
        break
      if self.available():
        identifier = self.old_id
      else:
        identifier = self.identifier
      self.process_server._send_message('task_output', {
        "output": output.decode('utf-8'), "identifier": identifier })

  def run_program_in_tty(self, identifier, arguments):
    # Determine the executable that we are going to run.
    executable = arguments[0]
    if (not os.path.isfile(executable) and
      executable[0] != '.' and
      executable[0] != '/'):
      paths = os.environ['PATH'].split(':')
      for path in paths:
        if os.path.isfile(path + '/' + executable):
          executable = path + '/' + executable
          break

    self.identifier = identifier

    fd = self.master_fd
    pid = os.fork()
    if pid == 0:
      os.dup2(self.slave_fd, 0)
      os.dup2(self.slave_fd, 1)
      os.dup2(self.slave_fd, 2)
      os.close(self.slave_fd)
      os.close(self.master_fd)

      os.execv(executable, arguments)
    else:
      self.current_pid = pid
      t = Thread(target=self.wait_to_end)
      t.start()

  def wait_to_end(self):
    (pid, result) = os.waitpid(self.current_pid, 0)
    exit_code = result / (2 ** 8)
    signal = result % (2 ** 8)
    if signal == 0:
      result = { 'method': 'exit', 'code': exit_code }
    else:
      result = { 'method': 'signal', 'code': exit_code }
    result['identifier'] = self.identifier
    self.process_server._send_message('task_done', result)

    # It is possible to get output after we are done running, so we need to old
    # identifier to correctly inform about the remaining output.
    self.old_id = self.identifier
    self.identifier = -1
    self.current_pid = None

  def available(self):
    return self.identifier == -1

  def resize_terminal(self):
    (columns, rows) = self.process_server.term_size
    fcntl.ioctl(self.slave_fd, termios.TIOCSWINSZ,
      struct.pack("HHHH", rows, columns, 0, 0))
    if self.current_pid is not None:
      os.kill(self.current_pid, signal.SIGWINCH)
