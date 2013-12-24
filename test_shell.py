import json
import pexpect
import pytest

@pytest.fixture(scope="function")
def shell(tmpdir, request):
  import sys

  ret = pexpect.spawn(' '.join([sys.executable, 'server.py']))
  ret.setecho(False)

  def teardown():
    ret.sendline(json.dumps({"type":"exit"}))
    ret.wait()
  request.addfinalizer(teardown)

  return ret

def expect_msg_type(shell, type):
  try:
    shell.expect('\r\n', timeout=2)
  except pexpect.TIMEOUT:
    print(shell.before)
    assert 0

  msg = json.loads(shell.before.decode().rstrip('\r\n'))
  assert msg["type"] == type

def expect_msg(shell, msg, timeout=2):
  try:
    shell.expect('\r\n', timeout)
  except pexpect.TIMEOUT:
    print(shell.before)
    assert 0

  output_msg = json.loads(shell.before.decode().rstrip('\r\n'))
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
    import sys
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