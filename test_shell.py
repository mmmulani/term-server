import json
import pexpect
import pytest
import sys

@pytest.fixture(scope="function")
def shell(tmpdir, request):

  ret = pexpect.spawn(' '.join([sys.executable, 'server.py']))
  ret.setecho(False)

  def teardown():
    ret.sendline(json.dumps({"type":"exit"}))
  request.addfinalizer(teardown)

  return ret

def get_shell_msg(shell, timeout):
  try:
    shell.expect('\r\n', timeout)
  except pexpect.TIMEOUT:
    print(shell.before)
    assert 0

  try:
    msg = json.loads(shell.before.decode().rstrip('\r\n'))
    return msg
  except ValueError:
    # This will happen if we receive non-JSON which usually means
    # a program error.
    sys.stdout.write(shell.before.decode())
    shell.expect(pexpect.TIMEOUT, timeout=1)
    text = shell.before
    sys.stdout.write(text.decode())
    assert 0

  return None

def expect_msg_type(shell, type, timeout=2):
  msg = get_shell_msg(shell, timeout)
  assert msg["type"] == type, \
    "Expected: {0}, got: {1} with full message of {2}".format(type, msg["type"], msg)

def expect_msg_output(shell, output, timeout=2):
  msg = get_shell_msg(shell, timeout)
  assert msg["message"]["output"] == output, \
    "Expected: {0}, got: {1} with full message of {2}".format(output, msg["message"]["output"], msg)

def expect_msg(shell, msg, timeout=2):
  output_msg = get_shell_msg(shell, timeout)
  assert msg == output_msg

def send_msg(shell, msg):
  shell.sendline(json.dumps(msg))

def test_start_shell(shell):
  expect_msg_type(shell, 'directory_info')

def test_run_echo(shell):
  expect_msg_type(shell, 'directory_info')
  send_msg(shell,
    {
      "type": "start_task",
      "message": {
        "identifier": "1",
        "arguments": ["echo", "test"],
      },
    })

  expect_msg(shell,
    {
      "type": "task_output",
      "message": {
        "output": "test\r\n",
        "identifier": "1",
      },
    })

  expect_msg(shell,
    {
      "type": "task_done",
      "message": {
        "method": "exit",
        "code": 0,
        "identifier": "1",
      },
    })

def test_exit_codes(shell):
  expect_msg_type(shell, 'directory_info')

  def test_error_code(code):
    test_error_code.counter += 1
    send_msg(shell,
      {
        "type": "start_task",
        "message": {
          "identifier": str(test_error_code.counter),
          "arguments": [sys.executable, '-c', "import sys; sys.exit({0})".format(code)],
        }
      })
    expect_msg(shell,
      {
        "type": "task_done",
        "message": {
          "method": "exit",
          "code": code,
          "identifier": str(test_error_code.counter),
        },
      })
  test_error_code.counter = 10

  test_error_code(10)
  test_error_code(12)
  test_error_code(127)
  test_error_code(130)
  test_error_code(255)

def test_multiple_cmds(shell):
  expect_msg_type(shell, 'directory_info')

  send_msg(shell,
    {
      "type": "start_task",
      "message": {
        "identifier": "1",
        "arguments": ["sleep", "1"],
      },
    })

  send_msg(shell,
    {
      "type": "make_enough_terms",
      "message": 2,
    })

  send_msg(shell,
    {
      "type": "start_task",
      "message": {
        "identifier": "2",
        "arguments": ["echo", "test"],
      },
    })

  expect_msg(shell,
    {
      "type": "task_output",
      "message": {
        "output": "test\r\n",
        "identifier": "2",
      },
    })

  expect_msg(shell,
    {
      "type": "task_done",
      "message": {
        "method": "exit",
        "code": 0,
        "identifier": "2",
      },
    })

  expect_msg(shell,
    {
      "type": "task_done",
      "message": {
        "method": "exit",
        "code": 0,
        "identifier": "1",
      },
    })

def test_change_dir(shell, tmpdir):
  expect_msg_type(shell, 'directory_info')

  send_msg(shell,
    {
      "type": "dir_change",
      "message": {
        "directory": str(tmpdir),
      },
    })

  expect_msg_type(shell, 'directory_info')
  expect_msg_type(shell, 'changed_directory')

  send_msg(shell,
    {
      "type": "start_task",
      "message": {
        "identifier": "1",
        "arguments": ["pwd"],
      },
    })

  expect_msg(shell,
    {
      "type": "task_output",
      "message": {
        "output": "{0}\r\n".format(str(tmpdir)),
        "identifier": "1",
      },
    })

  expect_msg(shell,
    {
      "type": "task_done",
      "message": {
        "method": "exit",
        "code": 0,
        "identifier": "1",
      },
    })

def test_terminal_input(shell):
  expect_msg_type(shell, 'directory_info')

  def str_to_hex(str_):
    return ''.join("{:02x}".format(ord(c)) for c in str_)

  send_msg(shell,
    {
      "type": "start_task",
      "message": {
        "identifier": "1",
        "arguments": ["cat", "-"],
      },
    })

  send_msg(shell,
    {
      "type": "handle_input",
      "message": {
        "identifier": "1",
        "input": str_to_hex("test"),
      },
    })
  expect_msg_output(shell, "test")

  send_msg(shell,
    {
      "type": "handle_input",
      "message": {
        "identifier": "1",
        "input": str_to_hex("testing\n"),
      },
    })
  expect_msg_output(shell, "testing\r\n")

  send_msg(shell,
    {
      "type": "handle_input",
      "message": {
        "identifier": "1",
        # 0x4 is EOT, i.e. CTRL+D.
        "input": "04",
      },
    })
  expect_msg_output(shell, "testtesting\r\n")
  expect_msg_output(shell, "^D\x08\x08")

  expect_msg_type(shell, "task_done")