import subprocess
import signal
import string
import random
import re
import json
import time
import os
import socket
import requests
import logging
import sys

from flask import Flask, request, send_from_directory, jsonify, render_template, redirect
app = Flask(__name__, static_url_path='')

logfile = '/home/pi/raspberry-pi-turnkey/turnkey.log'
logging.basicConfig(filename=logfile, filemode='w', level=logging.DEBUG)

currentdir = os.path.dirname(os.path.abspath(__file__))
os.chdir(currentdir)

ssid_list = []
def getssid():
    global ssid_list
    logging.debug('entered getssid()')
    if len(ssid_list) > 0:
        return ssid_list
    ssid_list = []
    get_ssid_list = subprocess.check_output(('iw', 'dev', 'wlan0', 'scan', 'ap-force'))
    ssids = get_ssid_list.splitlines()
    for s in ssids:
        s = s.strip().decode('utf-8')
        if s.startswith("SSID"):
            a = s.split(": ")
            try:
                ssid_list.append(a[1])
            except:
                pass
    logging.debug(ssid_list)
    ssid_list = sorted(list(set(ssid_list)))
    return ssid_list

def getProjectList():
    project_list = [
        ['k3s', 'Lightweight Kubernetes Cluster'],
        ['Rancher', 'Rancher Management Server'],
        ['k3os', 'An OS optimized for container orchestration']
    ]
    return project_list

def id_generator(size=6, chars=string.ascii_lowercase + string.digits):
    logging.debug("running id_generator()")
    return ''.join(random.choice(chars) for _ in range(size))

wpa_conf = """country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
network={
    ssid="%s"
    %s
}"""

wpa_conf_default = """country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
"""



@app.route('/')
def main():
    logging.debug('entered main()')
    piid = open('pi.id', 'r').read().strip()
    projects = zip(*getProjectList())
    # TODO: UPDATE THIS TO REFLECT ACTUAL CONTACT METHOD (SMS?)
    return render_template('index.html', ssids=getssid(), projectIDs=next(projects), message="Once connected you'll find IP address @ <a href='https://snaptext.live/{}' target='_blank'>snaptext.live/{}</a>.".format(piid,piid))

# Captive portal when connected with iOS or Android
@app.route('/generate_204')
def redirect204():
    logging.debug('entered redirect204()')
    return redirect("http://192.168.4.1", code=302)

@app.route('/hotspot-detect.html')
def applecaptive():
    logging.debug('entered applecaptive()')
    return redirect("http://192.168.4.1", code=302)

# Not working for Windows, needs work!
@app.route('/ncsi.txt')
def windowscaptive():
    logging.debug('entered windowscaptive()')
    return redirect("http://192.168.4.1", code=302)

def check_cred(ssid, password):
    logging.debug('entered check_cred()')
    '''Validates ssid and password and returns True if valid and False if not valid'''
    wpadir = currentdir + '/wpa/'
    testconf = wpadir + 'test.conf'
    wpalog = wpadir + 'wpa.log'
    wpapid = wpadir + 'wpa.pid'

    if not os.path.exists(wpadir):
        os.mkdir(wpadir)

    for _file in [testconf, wpalog, wpapid]:
        if os.path.exists(_file):
            os.remove(_file)

    # Generate temp wpa.conf
    result = subprocess.check_output(['wpa_passphrase', ssid, password])
    logging.debug("generated wpa.conf with result: '" + result.decode('utf-8') + "'")
    with open(testconf, 'w') as f:
        f.write(result.decode('utf-8'))

    def stop_ap(stop):
        logging.debug("stop request is: " + str(stop))
        if stop:
            logging.debug("stopping services [hostapd,dnsmaq,dhcpcd]")
            # Services need to be stopped to free up wlan0 interface
            subprocess.check_output(['systemctl', "stop", "hostapd", "dnsmasq", "dhcpcd"])
        else:
            logging.debug("starting services [hostapd,dnsmaq,dhcpcd]")
            subprocess.check_output(['systemctl', "restart", "dnsmasq", "dhcpcd"])
            time.sleep(15)
            subprocess.check_output(['systemctl', "restart", "hostapd"])

    # Sentences to check for
    fail = "pre-shared key may be incorrect"
    success = "WPA: Key negotiation completed"

    stop_ap(True)

    # RPi 4 driver is wext. RPi older driver is nl80211
    result = subprocess.check_output(['wpa_supplicant',
                                      "-Dwext",
                                      "-iwlan0",
                                      "-c", testconf,
                                      "-f", wpalog,
                                      "-B",
                                      "-P", wpapid])

    logging.debug("wpa_supplicant test credentials outcome: '" + result.decode('utf-8') + "'")
    checkwpa = True
    while checkwpa:
        with open(wpalog, 'r') as f:
            content = f.read()
            if success in content:
                valid_psk = True
                checkwpa = False
            elif fail in content:
                valid_psk = False
                checkwpa = False
            else:
                continue

    # Kill wpa_supplicant to stop it from setting up dhcp, dns
    with open(wpapid, 'r') as p:
        pid = p.read()
        pid = int(pid.strip())
        os.kill(pid, signal.SIGTERM)

    stop_ap(False) # Restart services
    return valid_psk

@app.route('/static/<path:path>')
def send_static(path):
    logging.debug('entered send_static()')
    return send_from_directory('static', path)

@app.route('/signin', methods=['POST'])
def signin():
    logging.debug('entered signin()')
    email = request.form['email']
    ssid = request.form['ssid']
    install_type = request.form['installType']
    password = request.form['password']

    pwd = 'psk="' + password + '"'
    if password == "":
        pwd = "key_mgmt=NONE" # If open AP

    logging.debug(email + ssid + password)
    valid_psk = check_cred(ssid, password)
    logging.debug("valid_psk: " + str(valid_psk))
    if not valid_psk:
        # User will not see this because they will be disconnected but we need to break here anyway
        return render_template('ap.html', message="Wrong password!")

    # Configure the WiFi module to connect to the desired network
    with open('wpa.conf', 'w') as f:
        f.write(wpa_conf % (ssid, pwd))
    with open('status.json', 'w') as f:
        f.write(json.dumps({'status':'disconnected'}))
    subprocess.Popen(["./disable_ap.sh"])
    piid = open('pi.id', 'r').read().strip()
    # TODO: UPDATE THIS MESSAGE BASED ON THE CONTACT METHOD USED (SMS?)
    return render_template('index.html', message="Please wait 2 minutes to connect. Then your IP address will show up at <a href='https://snaptext.live/{}'>snaptext.live/{}</a>.".format(piid,piid))

def wificonnected():
    logging.debug('entered wificonnected()')
    result = subprocess.check_output(['iwconfig', 'wlan0'])
    logging.debug("iwconfig wlan0: " + result.decode('utf-8'))
    # The assumption of this match filter is that 
    # the network ESSID is quoted when connected and 
    # nothing is quoted when not connected
    matches = re.findall(r'\"(.+?)\"', result.split(b'\n')[0].decode('utf-8'))
    if len(matches) > 0:
        logging.debug("got connected to " + matches[0])
        return True
    return False

if __name__ == "__main__":
    # things to run the first time it boots
    
    # Create a unique id for the device
    if not os.path.isfile('pi.id'):
        with open('pi.id', 'w') as f:
            f.write(id_generator())
        #subprocess.Popen("./expand_filesystem.sh")
        time.sleep(300)
    piid = open('pi.id', 'r').read().strip()
    logging.debug(piid)
    time.sleep(15)
        
    # get status
    s = {'status':'disconnected'}
    if not os.path.isfile('status.json'):
        with open('status.json', 'w') as f:
            f.write(json.dumps(s))
    else:
        s = json.load(open('status.json'))

    #check connection
    if wificonnected():
        s['status'] = 'connected'
    if not wificonnected():
        if s['status'] == 'connected': # Don't change if status in status.json is hostapd
            s['status'] = 'disconnected'

    with open('status.json', 'w') as f:
        f.write(json.dumps(s))
    if s['status'] == 'disconnected':
        s['status'] = 'hostapd'
        with open('status.json', 'w') as f:
            f.write(json.dumps(s))
        with open('wpa.conf', 'w') as f:
            f.write(wpa_conf_default)
        subprocess.Popen("./enable_ap.sh")
    elif s['status'] == 'connected':
        piid = open('pi.id', 'r').read().strip()

        # get ip address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ipaddress = s.getsockname()[0]
        s.close()

        ## alert user via sms not snaptext
        #r = requests.post("https://snaptext.live",data=json.dumps({"message":"Your Pi is online at {}".format(ipaddress),"to":piid,"from":"Raspberry Pi Turnkey"}))
        #print(r.json())

        # STARTUP K3S
        #subprocess.Popen("./startup.sh")
        while True:
            time.sleep(60000)
    else:
        app.run(host="0.0.0.0", port=80, threaded=True)
