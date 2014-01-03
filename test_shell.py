import json
import pexpect
import pytest
import sys

test_id = 100

@pytest.fixture(scope="function")
def shell(tmpdir, request):

  ret = pexpect.spawn(' '.join([sys.executable, 'server.py']))
  ret.setecho(False)

  def teardown():
    try:
      ret.sendline(json.dumps({"type":"exit", "message": {}}))
    except OSError:
      pass
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
    shell.expect([pexpect.TIMEOUT, pexpect.EOF], timeout=1)
    text = shell.before
    sys.stdout.write(text.decode())

    f = open('server.log')
    sys.stdout.write(f.read())

    assert 0

  return None

def str_to_hex(str_):
  return ''.join("{:02x}".format(ord(c)) for c in str_)

def expect_msg_type(shell, type, timeout=2):
  msg = get_shell_msg(shell, timeout)
  assert msg["type"] == type, \
    "Expected: {0}, got: {1} with full message of {2}".format(type, msg["type"], msg)

def expect_msg_output(shell, output, timeout=2):
  collected = ""
  while output.startswith(collected) and len(output) > len(collected):
    msg = get_shell_msg(shell, timeout)
    assert msg["type"] == "task_output"
    collected += msg["message"]["output"]
  assert collected == output, \
    "Expected: {0}, got: {1} with full message of {2}".format(output, collected, msg)

def expect_msg_output_partial(shell, output, timeout=2):
  msg = get_shell_msg(shell, timeout)
  assert msg["message"]["output"].startswith(output), \
    "Expected: {0}, got: {1} with full message of {2}".format(output, msg["message"]["output"], msg)

def expect_program_output(shell, cmd, output, timeout=2):
  global test_id
  test_id = test_id + 1
  iden = test_id

  send_msg(shell,
    {
      "type": "start_task",
      "message": {
        "identifier": str(iden),
        "arguments": cmd.split(" "),
      },
    })

  expect_msg_output(shell, output, timeout)
  expect_msg(shell,
    {
      "type": "task_done",
      "message": {
        "method": "exit",
        "code": 0,
        "identifier": str(iden),
      },
    }, timeout)

def expect_msg(shell, msg, timeout=2):
  output_msg = get_shell_msg(shell, timeout)
  assert msg == output_msg

def expect_msgs(shell, msgs, timeout=2):
  output_msgs = []
  for m in msgs:
    output_msgs.append(get_shell_msg(shell, timeout))

  for m in msgs:
    try:
      output_msgs.remove(m)
    except ValueError:
      pass

  assert len(output_msgs) == 0


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

  expect_msgs(shell,
    [{
      "type": "task_output",
      "message": {
        "output": "test\r\n",
        "identifier": "1",
      },
    },
    {
      "type": "task_done",
      "message": {
        "method": "exit",
        "code": 0,
        "identifier": "1",
      },
    }])

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
      "message": {
        "amount": 2,
      },
    })

  send_msg(shell,
    {
      "type": "start_task",
      "message": {
        "identifier": "2",
        "arguments": ["echo", "test"],
      },
    })

  expect_msgs(shell,
    [{
      "type": "task_output",
      "message": {
        "output": "test\r\n",
        "identifier": "2",
      },
    },
    {
      "type": "task_done",
      "message": {
        "method": "exit",
        "code": 0,
        "identifier": "2",
      },
    },
    {
      "type": "task_done",
      "message": {
        "method": "exit",
        "code": 0,
        "identifier": "1",
      },
    }])

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

  expect_msg(shell,
    {
      "type": "changed_directory",
      "message": {
        "directory": str(tmpdir),
      },
    })

  send_msg(shell,
    {
      "type": "start_task",
      "message": {
        "identifier": "1",
        "arguments": ["pwd"],
      },
    })

  expect_msgs(shell,
    [{
      "type": "task_output",
      "message": {
        "output": "{0}\r\n".format(str(tmpdir)),
        "identifier": "1",
      },
    },
    {
      "type": "task_done",
      "message": {
        "method": "exit",
        "code": 0,
        "identifier": "1",
      },
    }])

def test_terminal_input(shell):
  expect_msg_type(shell, 'directory_info')

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
  expect_msg_output(shell, "testing\r\ntesttesting\r\n")

  send_msg(shell,
    {
      "type": "handle_input",
      "message": {
        "identifier": "1",
        # 0x4 is EOT, i.e. CTRL+D.
        "input": "04",
      },
    })
  # It looks like Mac and some Linux variants output different things for CTRL+D
  # For Mac we get "^D\x08\x08" but on Linux we only get "^D".
  expect_msg_output_partial(shell, "^D")

  expect_msg_type(shell, "task_done")

def test_terminal_size(shell):
  expect_msg_type(shell, 'directory_info')

  expect_program_output(shell, "tput lines", "24\r\n")
  expect_program_output(shell, "tput cols", "80\r\n")

  send_msg(shell,
    {
      "type": "resize",
      "message": {
        "columns": 81,
        "rows": 20,
      },
    })

  expect_program_output(shell, "tput lines", "20\r\n")
  expect_program_output(shell, "tput cols", "81\r\n")

  # TODO: Test that resizing while a program is live works.
