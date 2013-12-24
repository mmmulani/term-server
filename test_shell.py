import json
import pexpect
import pytest

@pytest.fixture
def shell(tmpdir):
  import sys

  ret = pexpect.spawn(' '.join([sys.executable, 'server.py']))
  ret.setecho(False)
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
