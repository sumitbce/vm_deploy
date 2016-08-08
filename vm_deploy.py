#!/usr/bin/env python3
"""
:Author:   Sumit Pandey <sumpande@cisco.com>
:Version:  1.0

"""
import sys
import argparse
import signal
import time
import winrm

VM_DEPLOY_PS = 'powershell C:\\Users\\Administrator\\Documents\\vm_deploy.ps1'
WIN_URL = 'bgl1006-pod.cisco.com:9005'
WIN_USER = 'Administrator'
WIN_PWD = 'Cisco123!'

def sigint_handler(sig, frame):
    """Handling interupt signal gracefully"""
    print("Signal %s frame %s" % (sig, frame))
    print("Keyboard Interrupt!")
    sys.exit(1)

def argparser():
    arg_parser = argparse.ArgumentParser(description="VM Deployment")
    reqd = arg_parser.add_argument_group('Mandatory Arguments')
    reqd.add_argument('-action', '--action', help='specify the action', required=True,\
            choices=['snapshot', 'remove'])
    reqd.add_argument('-vm', '--vm_name', help='specify the vm name or pattern', required=True)
    params = vars(arg_parser.parse_args())
    return params


def get_winrm_session():
    """ Return windows remote management session handle"""
    return winrm.Session(WIN_URL, auth=(WIN_USER, WIN_PWD))


def vm_action(args):
    ws = get_winrm_session()
    CMD = VM_DEPLOY_PS + " " +  args['action'] + " "  + args['vm_name']
    try:
        r = ws.run_cmd("%s" % CMD)
        output = ((r.std_out).decode('utf-8'))
        print(output)
    except:
        pass


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    
    start_time = time.time()

    args = argparser()

    vm_action(args)

    print("Finished in %s second(s)" % (time.time() - start_time))
