import json
import pexpect
import pytest

@pytest.fixture
def shell(tmpdir):
  import sys

  return pexpect.spawn(' '.join([sys.executable, 'server.py']))

def expect_msg_type(shell, type):
  try:
    shell.expect('\r\n', timeout=2)
  except pexpect.TIMEOUT:
    print(shell.before)
    assert 0

  msg = json.loads(shell.before.decode().rstrip('\r\n'))
  assert msg["type"] == type

def send_msg(shell, msg):
  shell.sendline(json.dumps(msg))

def test_start_shell(shell):
  expect_msg_type(shell, 'directory_info')
