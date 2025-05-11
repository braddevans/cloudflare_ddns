import subprocess
import json
import requests
from datetime import datetime


def load_config():
    with open("config.json", "r") as f:
        return json.load(f)


def get_external_ip(command):
    try:
        result = subprocess.check_output(command, shell=True).decode().strip()
        return result
    except subprocess.CalledProcessError:
        return None


def get_zone_id(email, api_token, zone_name):
    response = requests.get(
        f"https://api.cloudflare.com/client/v4/zones?name={zone_name}&status=active",
        headers={
            "Content-Type": "application/json",
            "X-Auth-Email": email,
            "Authorization": f"Bearer {api_token}",
        },
    )
    result = response.json().get("result", [])
    return result[0]["id"] if result else None


def get_dns_record(email, api_token, zone_id, record_type, dns_record):
    response = requests.get(
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type={record_type}&name={dns_record}",
        headers={
            "Content-Type": "application/json",
            "X-Auth-Email": email,
            "Authorization": f"Bearer {api_token}",
        },
    )
    result = response.json().get("result", [])
    if result:
        return result[0]["id"], result[0]["content"]
    return None, None


def update_dns_record(email, api_token, zone_id, record_id, record_type, dns_record, new_ip, logfile):
    payload = {
        "type": record_type,
        "name": dns_record,
        "content": new_ip,
        "ttl": 1,
        "proxied": False,
    }
    response = requests.put(
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}",
        headers={
            "Content-Type": "application/json",
            "X-Auth-Email": email,
            "Authorization": f"Bearer {api_token}",
        },
        json=payload,
    )
    success = response.json().get("success", False)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M")
    if success:
        print(f"{dns_record} updated to: {new_ip}")
        with open(logfile, "a") as log:
            log.write(f"{timestamp} {record_type}: {dns_record} updated to: {new_ip}\n")
    else:
        print(f"{record_type}: {dns_record} update failed")
        with open(logfile, "a") as log:
            log.write(f"{timestamp} {record_type}: {dns_record} update failed\n")


def check_records(config, ip, record_type):
    email = config["email"]
    api_token = config["api_token"]
    logfile = config["logfile"]
    domains = config["domains"]

    for zone_name in domains:
        print(f"Domain {zone_name}")
        zone_id = get_zone_id(email, api_token, zone_name)
        if not zone_id:
            print(f"Could not get zone ID for {zone_name}")
            continue

        for sub in domains[zone_name]:
            dns_record = f"{sub}.{zone_name}" if sub != "@" else zone_name

            record_id, cf_ip = get_dns_record(email, api_token, zone_id, record_type, dns_record)
            print(f"{dns_record} cf_ip: {cf_ip}")

            if cf_ip != ip:
                if record_id:
                    update_dns_record(email, api_token, zone_id, record_id, record_type, dns_record, ip, logfile)
                else:
                    print(f"No existing record found for {dns_record}")
            else:
                print(f"{dns_record} already up to date")


def main():
    config = load_config()

    ipv4 = get_external_ip(config["ipv4_command"])
    if ipv4:
        print(f"Found IPV4: {ipv4}")
        check_records(config, ipv4, "A")

    ipv6 = get_external_ip(config["ipv6_command"])
    if ipv6:
        print(f"Found IPV6: {ipv6}")
        check_records(config, ipv6, "AAAA")


if __name__ == "__main__":
    main()