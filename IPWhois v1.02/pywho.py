# MIT License
# 
# Copyright (c) 2025 [Lyst]
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys
import socket
import argparse
import requests
import subprocess
import os
import re
from ipwhois import IPWhois
from concurrent.futures import ThreadPoolExecutor

# Hardcoded API Keys (FOR TESTING ONLY)
SHODAN_API_KEY = ""
ABUSEIPDB_API_KEY = ""

# Safe directory for storing output files
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)  # Ensure the directory exists

def display_banner():
    return "\nOSINT - IP Lookup [Version 1.01]\n(c) Lyxt. All rights reserved.\n"

def verbose_print(verbose, message):
    if verbose:
        print(f"[INFO] {message}")

def sanitize_filename(filename):
    """Sanitize filename to prevent Path Traversal (CWE-23)"""
    filename = re.sub(r"[^\w\-.]", "_", filename)  # Allow only safe characters
    return os.path.basename(filename)  # Prevent directory traversal

def whois_lookup(ip_address, verbose):
    try:
        verbose_print(verbose, f"Performing WHOIS lookup for {ip_address}...")
        obj = IPWhois(ip_address)
        result = obj.lookup_rdap()
        hostname = socket.gethostbyaddr(ip_address)[0] if socket.gethostbyaddr(ip_address) else "No PTR record found"
        return (f"\n[ WHOIS Information ]\n"
                f"IP Address: {ip_address}\n"
                f"Hostname: {hostname}\n"
                f"ASN: AS{result.get('asn', 'N/A')}\n"
                f"Country: {result.get('asn_country_code', 'N/A')}\n")
    except Exception as e:
        return f"[ERROR] WHOIS lookup failed: {e}\n"

def geoip_lookup(ip_address, verbose):
    try:
        verbose_print(verbose, f"Performing GeoIP lookup for {ip_address}...")
        url = f"http://ip-api.com/json/{ip_address}"
        response = requests.get(url).json()
        return (f"\n[ GeoIP Information ]\n"
                f"Country: {response.get('country', 'N/A')}\n"
                f"City: {response.get('city', 'N/A')}\n")
    except Exception as e:
        return f"[ERROR] GeoIP lookup failed: {e}\n"

def shodan_lookup(ip_address, verbose):
    try:
        verbose_print(verbose, f"Querying Shodan for {ip_address}...")
        url = f"https://api.shodan.io/shodan/host/{ip_address}?key={SHODAN_API_KEY}"
        response = requests.get(url).json()
        if "error" in response:
            return f"\n[ Shodan Information ]\nError: {response['error']}\n"
        return (f"\n[ Shodan Information ]\n"
                f"Open Ports: {response.get('ports', 'N/A')}\n")
    except Exception as e:
        return f"[ERROR] Shodan lookup failed: {e}\n"

def abuseipdb_lookup(ip_address, verbose):
    try:
        verbose_print(verbose, f"Checking AbuseIPDB for {ip_address}...")
        headers = {"Accept": "application/json", "Key": ABUSEIPDB_API_KEY}
        params = {"ipAddress": ip_address, "maxAgeInDays": 90, "verbose": True}
        url = "https://api.abuseipdb.com/api/v2/check"
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return f"\n[ AbuseIPDB Information ]\nError: {response.status_code} - {response.text}\n"
        data = response.json()
        if "data" not in data:
            return "\n[ AbuseIPDB Information ]\nNo data found for this IP.\n"
        abuse_data = data["data"]
        return (f"\n[ AbuseIPDB Information ]\n"
                f"Abuse Confidence Score: {abuse_data.get('abuseConfidenceScore', 'N/A')}\n")
    except Exception as e:
        return f"[ERROR] AbuseIPDB lookup failed: {e}\n"

def nmap_scan(ip_address, verbose):
    try:
        verbose_print(verbose, f"Running Nmap scan on {ip_address}...")
        cmd = ["nmap", "-sV", "-Pn", "--top-ports", "100", "-T4", ip_address]  # Optimized scan
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)  # Timeout after 60s
        return f"\n[ Nmap Scan Results ]\n{result.stdout}\n"
    except subprocess.TimeoutExpired:
        return "[ERROR] Nmap scan timed out (took too long).\n"
    except Exception as e:
        return f"[ERROR] Nmap scan failed: {e}\n"

def run_lookups(ip_address, options, verbose):
    results = ""
    with ThreadPoolExecutor() as executor:
        futures = {}
        if options["whois"]:
            futures["whois"] = executor.submit(whois_lookup, ip_address, verbose)
        if options["geoip"]:
            futures["geoip"] = executor.submit(geoip_lookup, ip_address, verbose)
        if options["shodan"]:
            futures["shodan"] = executor.submit(shodan_lookup, ip_address, verbose)
        if options["abuseipdb"]:
            futures["abuseipdb"] = executor.submit(abuseipdb_lookup, ip_address, verbose)
        if options["nmap"]:
            futures["nmap"] = executor.submit(nmap_scan, ip_address, verbose)
        
        for key, future in futures.items():
            results += future.result()
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Perform OSINT lookups on an IP address.")
    parser.add_argument("ip", help="Target IP address")
    parser.add_argument("-w", "--whois", action="store_true", help="Perform WHOIS lookup")
    parser.add_argument("-g", "--geoip", action="store_true", help="Perform GeoIP lookup")
    parser.add_argument("-sd", "--shodan", action="store_true", help="Perform Shodan lookup")
    parser.add_argument("-aip", "--abuseipdb", action="store_true", help="Check IP reputation on AbuseIPDB")
    parser.add_argument("-n", "--nmap", action="store_true", help="Run Nmap scan (-sV -Pn --top-ports 100 -T4)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-o", "--output", help="Save results to a file")
    args = parser.parse_args()
    
    options = {
        "whois": args.whois, 
        "geoip": args.geoip, 
        "shodan": args.shodan, 
        "abuseipdb": args.abuseipdb, 
        "nmap": args.nmap
    }
    
    results = display_banner() + run_lookups(args.ip, options, args.verbose)
    
    # Print results
    print(results)

    # Save to file if -o is provided (SAFE FILE HANDLING)
    if args.output:
        safe_filename = sanitize_filename(args.output)
        safe_path = os.path.join(OUTPUT_DIR, safe_filename)
        if os.path.exists(safe_path):
            print(f"[ERROR] File '{safe_filename}' already exists. Choose a different name.")
        else:
            try:
                with open(safe_path, "w", encoding="utf-8") as f:
                    f.write(results)
                print(f"[INFO] Results saved to {safe_path}")
            except Exception as e:
                print(f"[ERROR] Failed to save results: {e}")

if __name__ == "__main__":
    main()
