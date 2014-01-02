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
term_size = (80, 24)
current_dir = None

send_to_shell = None
send_to_plex = None
send_to_shells = []

is_shell = False

task_runner = None

class TaskRunner:
  def __init__(self, process_server):
    self.process_server = process_server

  def handle_client_message(self, msg_type, content):
    global send_to_shells, fd_to_task
    msg = { "type": msg_type, "message": content }
    attachment = msg['message']

    log('got message of type {0} in main queue'.format(msg['type']))

    if msg['type'] == 'handle_input':
      write_input_to_task(attachment)
    elif msg['type'] == 'resize_term':
      term_size = (int(attachment['columns']), int(attachment['rows']))
      resize_terminal(attachment)
    elif msg['type'] == 'make_enough_terms':
      make_enough_terms(attachment)
    else:
      log('forwarding message of type {0} to shell'.format(msg['type']))
      log('current status of fd_to_task: {0}'.format(fd_to_task))
      if msg['type'] == 'start_task':
        shell, fd = send_to_shells.pop(0)
        send_to_shells.append((shell, fd))
        fd_to_task[fd] = attachment['identifier']
        shell.send(msg)
      elif msg['type'] == 'dir_change':
        for shell, fd in send_to_shells:
          shell.send(msg)
      elif msg['type'] == 'cat_image':
        shell, fd = send_to_shells[0]
        shell.send(msg)

def log(msg):
  global logger
  logger.info(msg)

def signal_handler(signal, frame):
  log('Got signal {0}, doing nothing'.format(signal))

def start(task_runner_):
  global logger, task_runner
  global send_to_shells, send_to_plex, fd_to_task
  global term_size, current_dir

  task_runner = task_runner_

  os.environ['TERM'] = 'xterm-256color'

  # Some initial data.
  inform_about_directory(os.getcwd())

  # Do inits that should provide different objects for each process.
  logger = logging.getLogger('server')
  logger.setLevel(logging.DEBUG)
  fh = logging.FileHandler('server.log')
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
  fh.setFormatter(formatter)
  fh.setLevel(logging.DEBUG)
  logger.addHandler(fh)

  make_enough_terms(1)

def make_enough_terms(num):
  global send_to_shells, term_size, current_dir
  for x in range(0, num - len(send_to_shells)):
    t = Thread(target=start_shell)
    t.start()


def start_shell():
  global send_to_plex, all_fds, is_shell, send_to_shells
  global current_dir, term_size

  # Start our TTY.
  port = random.randint(10000, 30000)
  address = ('localhost', port)
  (pid, fd) = pty.fork()

  log('pid {0} and fd {1}'.format(pid, fd))
  if pid == 0:
    listener = connection.Listener(address, authkey=b'LOL')
    send_to_shell = listener.accept()
    log('got send_to_shell in shell')
    send_to_plex = listener.accept()
    log('got send_to_plex in shell')
    send_to_plex.send({'type': 'test', 'message': 'lol'})
    is_shell = True

    signal.signal(signal.SIGINT, signal_handler)

    if not current_dir is None:
      os.environ['PWD'] = current_dir
      os.chdir(current_dir)

    shell_run_loop(send_to_shell)

    # Should not reach here.
    return
  else:
    while True:
      try:
        log('establishing connections..')
        send_to_shell = connection.Client(address, authkey=b'LOL')
        break
      except os.error as e:
        pass
    log('establishing connections.. 1/2')
    send_to_plex = connection.Client(address, authkey=b'LOL')
    log('establishing connections.. 2/2')

  # Initialize the terminal.
  fcntl.ioctl(fd, termios.TIOCSWINSZ,
      struct.pack("HHHH", term_size[1], term_size[0], 0, 0))

  control_chars = [b'\x04', b'\xff', b'\xff', b'\x7f', b'\x17', b'\x15', b'\x12', b'\xff', b'\x03', b'\x1c', b'\x1a', b'\x19', b'\x11', b'\x13', b'\x16', b'\x0f', b'\x01', b'\x00', b'\x14', b'\xff']
  control_chars.extend(b'\x00' for _ in range(termios.NCCS - len(control_chars)))
  termios.tcsetattr(fd, termios.TCSANOW, [
    termios.BRKINT | termios.ICRNL,
    termios.OPOST | termios.ONLCR,
    termios.CS8 | termios.CREAD | termios.HUPCL,
    termios.ECHOKE | termios.ECHOE | termios.ECHOK | termios.ECHO | termios.ECHOCTL | termios.ISIG | termios.ICANON | termios.IEXTEN | termios.PENDIN,
    termios.B230400,
    termios.B230400,
    control_chars,
    ])

  t = Thread(target=shell_response_loop, args=(fd,send_to_plex))
  t.start()

  t = Thread(target=read_thread, args=(fd,))
  t.start()

  send_to_shells.insert(0, (send_to_shell, fd))


def run_program_in_tty(options):
  global current_pid, current_task_id

  current_task_id = options['identifier']
  program_args = options['arguments']

  # Determine the executable that we are going to run.
  executable = program_args[0]
  if (not os.path.isfile(executable) and
    executable[0] != '.' and
    executable[0] != '/'):
    paths = os.environ['PATH'].split(':')
    for path in paths:
      if os.path.isfile(path + '/' + executable):
        executable = path + '/' + executable
        break

  log('Running {0}'.format(executable))

  pid = os.fork()
  if pid == 0:
    os.execv(executable, program_args)
  else:
    current_pid = pid
    t = Thread(target=wait_to_end)
    t.start()


def shell_response_loop(fd, send_to_plex):
  global fd_to_task, current_dir, send_to_shells

  while True:
    msg = send_to_plex.recv()
    attachment = msg['message']

    log('got message of type {0} in shell response'.format(msg['type']))

    if msg['type'] == 'forward':
      if attachment['type'] == 'changed_directory':
        current_dir = attachment['message']['directory']
      elif attachment['type'] == 'task_done':
        iden = attachment['message']['identifier']
        index = [i for (i, (shell, fd)) in enumerate(send_to_shells) if iden == fd_to_task[fd]][0]
        shell = send_to_shells.pop(index)
        send_to_shells.insert(0, shell)

      send_message(attachment['type'], attachment['message'])

def shell_run_loop(send_to_shell):
  while True:
    try:
      msg = send_to_shell.recv()
    except OSError as e:
      continue

    log('got message of type {0} in shell run loop'.format(msg['type']))

    attachment = msg['message']
    if msg['type'] == 'start_task':
      run_program_in_tty(attachment)
    elif msg['type'] == 'dir_change':
      change_directory(attachment)
    elif msg['type'] == 'cat_image':
      cat_image(attachment)

def write_input_to_task(input):
  global fd_to_task
  fd = -1

  log('trying to write to task {0}, current fd_to_task {1}'.format(input['identifier'], str(fd_to_task)))

  for k, v in fd_to_task.items():
    if v == input['identifier']:
      fd = k
      break

  if fd == -1:
    log('OH NO, didn\'t find a file descriptor')

  os.write(fd, bytes.fromhex(input['input']))

def read_thread(fd):
  global fd_to_task

  while True:
    try:
      output = os.read(fd, 1024)
    except OSError as e:
      break
    if not fd in fd_to_task:
      log('WTF no fd with output {0}'.format(output))
    send_message('task_output', {
      "output": output.decode('utf-8'), "identifier": fd_to_task[fd] })

def wait_to_end():
  global current_pid, current_task_id

  (pid, result) = os.waitpid(current_pid, 0)
  exit_code = result / (2 ** 8)
  signal = result % (2 ** 8)
  if signal == 0:
    result = { 'method': 'exit', 'code': exit_code }
  else:
    result = { 'method': 'signal', 'code': exit_code }
  result['identifier'] = current_task_id
  forward_message('task_done', result)
  current_pid = -1

def inform_about_directory(directory):
  directory = os.path.abspath(directory)
  items = [x for x in os.listdir(directory) if x[0] != '.']
  result = {}
  for item in items:
    result[item] = os.path.isdir(directory + '/' + item)
  forward_message('directory_info', { directory: result })

def change_directory(options):
  directory = options['directory']
  if not os.path.isabs(directory):
    directory = os.path.normpath(os.environ['PWD'] + '/' + directory)
  try:
    os.chdir(directory)
  except os.error as e:
    forward_message('dir_change_fail', options)
    return

  os.environ['PWD'] = directory
  options['directory'] = directory

  inform_about_directory(directory)

  forward_message('changed_directory', options)

def cat_image(options):
  f = open(options['image'], 'rb')
  content = f.read()
  options['content'] = binascii.b2a_hex(content).decode('utf-8')

  forward_message('got_image', options)

def resize_terminal(options):
  global all_fds

  for fd in all_fds:
    fcntl.ioctl(fd, termios.TIOCSWINSZ,
      struct.pack("HHHH", int(options['rows']), int(options['columns']), 0, 0))

def send_message(msg_type, content):
  task_runner.process_server._send_message(msg_type, content)

def forward_message(msg_type, content):
  global is_shell
  if not is_shell:
    send_message(msg_type, content)
    return

  send_msg_plex('forward', {
    'type': msg_type,
    'message': content,
  })

def send_msg_plex(msg_type, content):
  global send_to_plex

  send_to_plex.send({
    'type': msg_type,
    'message': content,
  })