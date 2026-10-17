"""Generate two mock supplier datasets (100 products each) for the Procurement Agent.

    python setup/generate_mock_suppliers.py

Writes
    data/suppliers/northstar_office.json   NorthStar Office Supply (USD, flat schema)
    data/suppliers/techsource.json         TechSource Supply Co. (USD, nested schema)

Both draw from one shared base catalog of office/IT products so 46 products appear in
both suppliers under different names, IDs, MPN formatting and prices (for price comparison).
Neither supplier lists the same product twice.
Generation is deterministic (fixed seed). Seeded edge cases are listed in README.md.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 42
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "suppliers"

# ---------------------------------------------------------------------------
# Shared base catalog: (mpn, brand, name, category, usd_list_price, specs)
# ---------------------------------------------------------------------------
BASE: list[tuple[str, str, str, str, float, dict]] = [
    # --- 27" office monitors -------------------------------------------------
    ("U2723QE", "Dell", "UltraSharp U2723QE 27\" 4K USB-C Hub Monitor", "monitor", 619.99, {"size_in": 27, "resolution": "3840x2160", "panel": "IPS Black", "usb_c": True, "refresh_hz": 60}),
    ("P2723DE", "Dell", "P2723DE 27\" QHD USB-C Hub Monitor", "monitor", 409.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 60}),
    ("S2722DC", "Dell", "S2722DC 27\" QHD USB-C Monitor", "monitor", 329.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 75}),
    ("P2723QE", "Dell", "P2723QE 27\" 4K USB-C Hub Monitor", "monitor", 489.99, {"size_in": 27, "resolution": "3840x2160", "panel": "IPS", "usb_c": True, "refresh_hz": 60}),
    ("27UP850-W", "LG", "27UP850-W 27\" UHD 4K IPS USB-C Monitor", "monitor", 449.99, {"size_in": 27, "resolution": "3840x2160", "panel": "IPS", "usb_c": True, "refresh_hz": 60}),
    ("27QN600-B", "LG", "27QN600-B 27\" QHD IPS Monitor", "monitor", 249.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": False, "refresh_hz": 75}),
    ("27BQ75QB-B", "LG", "27BQ75QB-B 27\" QHD USB-C Business Monitor", "monitor", 379.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 60}),
    ("6N4E2AA", "HP", "E27 G5 27\" FHD Monitor", "monitor", 259.00, {"size_in": 27, "resolution": "1920x1080", "panel": "IPS", "usb_c": False, "refresh_hz": 75}),
    ("6N4D3AA", "HP", "E27u G5 27\" QHD USB-C Monitor", "monitor", 379.00, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 75}),
    ("6N6F2AA", "HP", "E27k G5 27\" 4K USB-C Monitor", "monitor", 489.00, {"size_in": 27, "resolution": "3840x2160", "panel": "IPS", "usb_c": True, "refresh_hz": 60}),
    ("63A3GAR1US", "Lenovo", "ThinkVision T27h-30 27\" QHD USB-C Monitor", "monitor", 399.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 75}),
    ("63A1GAR1US", "Lenovo", "ThinkVision P27h-30 27\" QHD USB-C Monitor", "monitor", 459.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 60}),
    ("62B1GAT1US", "Lenovo", "ThinkVision T27i-30 27\" FHD Monitor", "monitor", 219.99, {"size_in": 27, "resolution": "1920x1080", "panel": "IPS", "usb_c": False, "refresh_hz": 60}),
    ("LS27B800PXNXGO", "Samsung", "ViewFinity S8 S27B800 27\" 4K USB-C Monitor", "monitor", 549.99, {"size_in": 27, "resolution": "3840x2160", "panel": "IPS", "usb_c": True, "refresh_hz": 60}),
    ("LS27A600UUNXGO", "Samsung", "S27A600U 27\" QHD USB-C Monitor", "monitor", 329.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 75}),
    ("GW2790QT", "BenQ", "GW2790QT 27\" QHD Eye-Care USB-C Monitor", "monitor", 329.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 75}),
    ("PA278CV", "ASUS", "ProArt PA278CV 27\" QHD USB-C Monitor", "monitor", 349.00, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 75}),
    ("276B1", "Philips", "276B1 27\" QHD USB-C Docking Monitor", "monitor", 359.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 75}),
    ("VG2755-2K", "ViewSonic", "VG2755-2K 27\" QHD USB-C Ergonomic Monitor", "monitor", 309.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 60}),
    ("UM.HB7AA.E01", "Acer", "Vero B277 27\" FHD Monitor", "monitor", 199.99, {"size_in": 27, "resolution": "1920x1080", "panel": "IPS", "usb_c": False, "refresh_hz": 75}),
    ("Q27P2CA", "AOC", "Q27P2CA 27\" QHD USB-C Monitor", "monitor", 279.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 75}),
    ("XUB2792QSU-B5", "iiyama", "ProLite XUB2792QSU-B5 27\" QHD Monitor", "monitor", 269.00, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": False, "refresh_hz": 75}),
    # --- near-miss monitors (wrong size / gaming) ----------------------------
    ("P2422H", "Dell", "P2422H 24\" FHD Monitor", "monitor", 219.99, {"size_in": 24, "resolution": "1920x1080", "panel": "IPS", "usb_c": False, "refresh_hz": 60}),
    ("U2422HE", "Dell", "UltraSharp U2422HE 24\" USB-C Hub Monitor", "monitor", 359.99, {"size_in": 24, "resolution": "1920x1080", "panel": "IPS", "usb_c": True, "refresh_hz": 60}),
    ("6N6E9AA", "HP", "E24 G5 24\" FHD Monitor", "monitor", 209.00, {"size_in": 24, "resolution": "1920x1080", "panel": "IPS", "usb_c": False, "refresh_hz": 75}),
    ("24MP400-B", "LG", "24MP400-B 24\" FHD IPS Monitor", "monitor", 129.99, {"size_in": 24, "resolution": "1920x1080", "panel": "IPS", "usb_c": False, "refresh_hz": 75}),
    ("U3223QE", "Dell", "UltraSharp U3223QE 32\" 4K USB-C Hub Monitor", "monitor", 849.99, {"size_in": 32, "resolution": "3840x2160", "panel": "IPS Black", "usb_c": True, "refresh_hz": 60}),
    ("U3423WE", "Dell", "UltraSharp U3423WE 34\" Curved USB-C Hub Monitor", "monitor", 899.99, {"size_in": 34, "resolution": "3440x1440", "panel": "IPS", "usb_c": True, "refresh_hz": 60}),
    ("LC27G55TQWNXZA", "Samsung", "Odyssey G5 27\" QHD 144Hz Curved Gaming Monitor", "monitor", 299.99, {"size_in": 27, "resolution": "2560x1440", "panel": "VA", "usb_c": False, "refresh_hz": 144, "gaming": True}),
    ("27GN800-B", "LG", "UltraGear 27GN800-B 27\" QHD 144Hz Gaming Monitor", "monitor", 329.99, {"size_in": 27, "resolution": "2560x1440", "panel": "IPS", "usb_c": False, "refresh_hz": 144, "gaming": True}),
    # --- docking stations ----------------------------------------------------
    ("WD19S-130W", "Dell", "WD19S USB-C Docking Station 130W", "docking_station", 229.99, {"connector": "USB-C", "max_displays": 3, "power_delivery_w": 90, "thunderbolt": False}),
    ("WD22TB4", "Dell", "WD22TB4 Thunderbolt 4 Dock", "docking_station", 309.99, {"connector": "Thunderbolt 4", "max_displays": 4, "power_delivery_w": 90, "thunderbolt": True}),
    ("UD22", "Dell", "UD22 Universal USB-C Dock", "docking_station", 269.99, {"connector": "USB-C", "max_displays": 4, "power_delivery_w": 96, "thunderbolt": False}),
    ("D6000", "Dell", "D6000 Universal Dock", "docking_station", 199.99, {"connector": "USB-C / USB-A", "max_displays": 3, "power_delivery_w": 65, "thunderbolt": False}),
    ("40AY0090US", "Lenovo", "ThinkPad Universal USB-C Dock", "docking_station", 219.99, {"connector": "USB-C", "max_displays": 3, "power_delivery_w": 100, "thunderbolt": False}),
    ("40B00135US", "Lenovo", "ThinkPad Thunderbolt 4 Dock", "docking_station", 329.99, {"connector": "Thunderbolt 4", "max_displays": 4, "power_delivery_w": 100, "thunderbolt": True}),
    ("40AS0090US", "Lenovo", "ThinkPad USB-C Dock Gen 2", "docking_station", 189.99, {"connector": "USB-C", "max_displays": 3, "power_delivery_w": 60, "thunderbolt": False}),
    ("5TW10AA", "HP", "USB-C Dock G5", "docking_station", 189.00, {"connector": "USB-C", "max_displays": 3, "power_delivery_w": 100, "thunderbolt": False}),
    ("4J0G4AA", "HP", "Thunderbolt Dock G4 120W", "docking_station", 299.00, {"connector": "Thunderbolt 4", "max_displays": 4, "power_delivery_w": 100, "thunderbolt": True}),
    ("72C71AA", "HP", "USB-C G5 Essential Dock", "docking_station", 139.00, {"connector": "USB-C", "max_displays": 2, "power_delivery_w": 65, "thunderbolt": False}),
    ("K38240NA", "Kensington", "SD4700P USB-C / USB-A Hybrid Dock", "docking_station", 219.99, {"connector": "USB-C / USB-A", "max_displays": 2, "power_delivery_w": 60, "thunderbolt": False}),
    ("K35175NA", "Kensington", "SD5700T Thunderbolt 4 Dual 4K Dock", "docking_station", 339.99, {"connector": "Thunderbolt 4", "max_displays": 2, "power_delivery_w": 90, "thunderbolt": True}),
    ("K33620NA", "Kensington", "SD4780P USB-C / USB-A 10Gbps Dual 4K Dock", "docking_station", 249.99, {"connector": "USB-C / USB-A", "max_displays": 2, "power_delivery_w": 100, "thunderbolt": False}),
    ("A8392", "Anker", "575 USB-C Docking Station 13-in-1", "docking_station", 249.99, {"connector": "USB-C", "max_displays": 3, "power_delivery_w": 85, "thunderbolt": False}),
    ("A8397", "Anker", "563 USB-C Docking Station 10-in-1", "docking_station", 199.99, {"connector": "USB-C", "max_displays": 3, "power_delivery_w": 65, "thunderbolt": False}),
    ("UD-6950PDZ", "Plugable", "UD-6950PDZ USB-C Triple Display Dock 100W", "docking_station", 229.00, {"connector": "USB-C", "max_displays": 3, "power_delivery_w": 100, "thunderbolt": False}),
    ("UD-3900", "Plugable", "UD-3900 USB 3.0 Universal Docking Station", "docking_station", 109.00, {"connector": "USB-A", "max_displays": 2, "power_delivery_w": 0, "thunderbolt": False}),
    ("TS4", "CalDigit", "TS4 Thunderbolt 4 Dock 18 ports", "docking_station", 399.99, {"connector": "Thunderbolt 4", "max_displays": 2, "power_delivery_w": 98, "thunderbolt": True}),
    ("DOCK190USZ", "Targus", "Universal USB-C DV4K Docking Station 100W", "docking_station", 229.99, {"connector": "USB-C", "max_displays": 2, "power_delivery_w": 100, "thunderbolt": False}),
    ("DK30C2DAGPD", "StarTech", "USB-C Dual 4K Dock 60W PD", "docking_station", 199.99, {"connector": "USB-C", "max_displays": 2, "power_delivery_w": 60, "thunderbolt": False}),
    ("INC006TTSGY", "Belkin", "Connect Thunderbolt 4 Dock Core", "docking_station", 229.99, {"connector": "Thunderbolt 4", "max_displays": 2, "power_delivery_w": 90, "thunderbolt": True}),
    ("1GK-00001", "Microsoft", "Surface Dock 2", "docking_station", 259.99, {"connector": "Surface Connect", "max_displays": 2, "power_delivery_w": 120, "thunderbolt": False}),
    # --- keyboards & mice ----------------------------------------------------
    ("920-011406", "Logitech", "MX Keys S Wireless Keyboard", "keyboard", 109.99, {"connection": "Bluetooth / Logi Bolt", "ergonomic": False}),
    ("920-010473", "Logitech", "MX Keys Mini Wireless Keyboard", "keyboard", 99.99, {"connection": "Bluetooth / Logi Bolt", "ergonomic": False}),
    ("920-009166", "Logitech", "Ergo K860 Split Ergonomic Keyboard", "keyboard", 129.99, {"connection": "Bluetooth / USB receiver", "ergonomic": True}),
    ("920-008671", "Logitech", "MK540 Advanced Wireless Keyboard and Mouse Combo", "keyboard", 59.99, {"connection": "USB receiver", "ergonomic": False, "bundle": "keyboard + mouse"}),
    ("910-006556", "Logitech", "MX Master 3S Wireless Mouse", "mouse", 99.99, {"connection": "Bluetooth / Logi Bolt", "ergonomic": True}),
    ("910-006466", "Logitech", "Lift Vertical Ergonomic Mouse", "mouse", 69.99, {"connection": "Bluetooth / Logi Bolt", "ergonomic": True}),
    ("910-006231", "Logitech", "Signature M650 L Wireless Mouse", "mouse", 39.99, {"connection": "Bluetooth / Logi Bolt", "ergonomic": False}),
    ("L5V-00001", "Microsoft", "Sculpt Ergonomic Desktop Keyboard and Mouse", "keyboard", 129.99, {"connection": "USB receiver", "ergonomic": True, "bundle": "keyboard + mouse"}),
    ("LXM-00001", "Microsoft", "Ergonomic Keyboard", "keyboard", 59.99, {"connection": "Wired USB", "ergonomic": True}),
    ("KM7321W", "Dell", "Premier Multi-Device Wireless Keyboard and Mouse KM7321W", "keyboard", 99.99, {"connection": "Bluetooth / USB receiver", "ergonomic": False, "bundle": "keyboard + mouse"}),
    ("KB216", "Dell", "KB216 Wired Multimedia Keyboard", "keyboard", 19.99, {"connection": "Wired USB", "ergonomic": False}),
    ("MS116", "Dell", "MS116 Wired Optical Mouse", "mouse", 12.99, {"connection": "Wired USB", "ergonomic": False}),
    ("K75501WW", "Kensington", "Pro Fit Ergo Vertical Wireless Trackball", "mouse", 89.99, {"connection": "Bluetooth / USB receiver", "ergonomic": True}),
    ("3L4T0AA", "HP", "230 Wireless Mouse", "mouse", 19.99, {"connection": "USB receiver", "ergonomic": False}),
    ("9SR37AA", "HP", "320K Wired Keyboard", "keyboard", 24.99, {"connection": "Wired USB", "ergonomic": False}),
    ("K2-C1", "Keychron", "K2 Wireless Mechanical Keyboard (Brown switch)", "keyboard", 89.99, {"connection": "Bluetooth / Wired USB-C", "ergonomic": False}),
    # --- headsets, speakerphones, webcams ------------------------------------
    ("26599-989-999", "Jabra", "Evolve2 65 UC Stereo Wireless Headset USB-A", "headset", 249.00, {"connection": "Bluetooth / USB-A dongle", "wireless": True, "anc": False, "uc_certified": "UC"}),
    ("26599-999-999", "Jabra", "Evolve2 65 MS Stereo Wireless Headset USB-A", "headset", 249.00, {"connection": "Bluetooth / USB-A dongle", "wireless": True, "anc": False, "uc_certified": "Teams"}),
    ("24089-989-999", "Jabra", "Evolve2 40 UC Stereo Wired Headset USB-A", "headset", 129.00, {"connection": "Wired USB-A", "wireless": False, "anc": False, "uc_certified": "UC"}),
    ("25599-989-999", "Jabra", "Evolve2 55 UC Stereo Wireless Headset", "headset", 229.00, {"connection": "Bluetooth / USB-A dongle", "wireless": True, "anc": True, "uc_certified": "UC"}),
    ("213726-01", "Poly", "Voyager Focus 2 UC Wireless Headset", "headset", 229.95, {"connection": "Bluetooth / USB-A dongle", "wireless": True, "anc": True, "uc_certified": "UC"}),
    ("207576-01", "Poly", "Blackwire 5220 Stereo Wired Headset USB-A / 3.5mm", "headset", 89.95, {"connection": "Wired USB-A", "wireless": False, "anc": False, "uc_certified": "UC"}),
    ("981-000870", "Logitech", "Zone Wired UC Headset", "headset", 129.99, {"connection": "Wired USB-C", "wireless": False, "anc": False, "uc_certified": "UC"}),
    ("981-001256", "Logitech", "Zone Vibe 100 Wireless Headset", "headset", 99.99, {"connection": "Bluetooth", "wireless": True, "anc": False, "uc_certified": "none"}),
    ("1000882", "EPOS", "ADAPT 260 Bluetooth Stereo Headset", "headset", 139.00, {"connection": "Bluetooth / USB-A dongle", "wireless": True, "anc": False, "uc_certified": "UC"}),
    ("960-001257", "Logitech", "C920s HD Pro Webcam 1080p", "webcam", 69.99, {"resolution": "1080p", "fps": 30, "privacy_shutter": True}),
    ("960-001105", "Logitech", "Brio 4K Ultra HD Webcam", "webcam", 199.99, {"resolution": "4K", "fps": 30, "privacy_shutter": True}),
    ("960-001494", "Logitech", "Brio 500 Full HD Webcam", "webcam", 129.99, {"resolution": "1080p", "fps": 30, "privacy_shutter": True}),
    ("WB7022", "Dell", "UltraSharp Webcam WB7022 4K", "webcam", 199.99, {"resolution": "4K", "fps": 30, "privacy_shutter": True}),
    ("2200-87070-001", "Poly", "Studio P5 Webcam 1080p", "webcam", 89.95, {"resolution": "1080p", "fps": 30, "privacy_shutter": True}),
    ("2755-109", "Jabra", "Speak2 55 UC Speakerphone", "speakerphone", 169.00, {"connection": "Bluetooth / USB-C", "battery_h": 12}),
    ("A3302", "Anker", "PowerConf S3 Bluetooth Speakerphone", "speakerphone", 99.99, {"connection": "Bluetooth / USB-C", "battery_h": 24}),
    # --- laptops (several overlap with DummyJSON) ----------------------------
    ("MKGP3LL/A", "Apple", "MacBook Pro 14-inch M1 Pro 16GB 512GB Space Grey", "laptop", 1999.00, {"screen_in": 14.2, "cpu": "Apple M1 Pro", "ram_gb": 16, "ssd_gb": 512}),
    ("MLXW3LL/A", "Apple", "MacBook Air 13-inch M2 8GB 256GB Midnight", "laptop", 1099.00, {"screen_in": 13.6, "cpu": "Apple M2", "ram_gb": 8, "ssd_gb": 256}),
    ("XPS9300-7909SLV", "Dell", "XPS 13 9300 13.4\" i7 16GB 512GB", "laptop", 1499.99, {"screen_in": 13.4, "cpu": "Intel Core i7-1065G7", "ram_gb": 16, "ssd_gb": 512}),
    ("LAT5540-I5-16-256", "Dell", "Latitude 5540 15.6\" i5 16GB 256GB", "laptop", 1249.00, {"screen_in": 15.6, "cpu": "Intel Core i5-1335U", "ram_gb": 16, "ssd_gb": 256}),
    ("80Y700CNUS", "Lenovo", "Yoga 920 13.9\" i7 8GB 256GB 2-in-1", "laptop", 1099.99, {"screen_in": 13.9, "cpu": "Intel Core i7-8550U", "ram_gb": 8, "ssd_gb": 256}),
    ("21HD0005US", "Lenovo", "ThinkPad T14 Gen 4 14\" i5 16GB 512GB", "laptop", 1389.00, {"screen_in": 14, "cpu": "Intel Core i5-1335U", "ram_gb": 16, "ssd_gb": 512}),
    ("21HM0005US", "Lenovo", "ThinkPad X1 Carbon Gen 11 14\" i7 16GB 512GB", "laptop", 1849.00, {"screen_in": 14, "cpu": "Intel Core i7-1355U", "ram_gb": 16, "ssd_gb": 512}),
    ("7L1R2UT", "HP", "EliteBook 840 G10 14\" i5 16GB 512GB", "laptop", 1429.00, {"screen_in": 14, "cpu": "Intel Core i5-1335U", "ram_gb": 16, "ssd_gb": 512}),
    ("7P3D4UT", "HP", "ProBook 450 G10 15.6\" i5 16GB 256GB", "laptop", 999.00, {"screen_in": 15.6, "cpu": "Intel Core i5-1335U", "ram_gb": 16, "ssd_gb": 256}),
    ("R1S-00001", "Microsoft", "Surface Laptop 5 13.5\" i5 8GB 256GB Platinum", "laptop", 999.99, {"screen_in": 13.5, "cpu": "Intel Core i5-1235U", "ram_gb": 8, "ssd_gb": 256}),
    # --- chairs, desks, monitor arms ----------------------------------------
    ("AER1B", "Herman Miller", "Aeron Chair Size B Graphite", "chair", 1395.00, {"adjustable_arms": True, "lumbar": True, "weight_capacity_lb": 350}),
    ("435A00", "Steelcase", "Series 1 Office Chair", "chair", 495.00, {"adjustable_arms": True, "lumbar": True, "weight_capacity_lb": 300}),
    ("46216179", "Steelcase", "Leap V2 Office Chair", "chair", 1079.00, {"adjustable_arms": True, "lumbar": True, "weight_capacity_lb": 400}),
    ("HONI2M2AMLC10TK", "HON", "Ignition 2.0 Mid-Back Mesh Task Chair", "chair", 349.00, {"adjustable_arms": True, "lumbar": True, "weight_capacity_lb": 300}),
    ("F211", "Humanscale", "Freedom Task Chair with Headrest", "chair", 1299.00, {"adjustable_arms": True, "lumbar": True, "weight_capacity_lb": 300}),
    ("BR-ERG-01", "Branch", "Ergonomic Chair", "chair", 349.00, {"adjustable_arms": True, "lumbar": True, "weight_capacity_lb": 300}),
    ("E7-60-BLK", "Flexispot", "E7 Pro Electric Standing Desk 60x30 Black", "desk", 549.99, {"width_in": 60, "depth_in": 30, "electric": True, "height_range_in": "22.8-48.4"}),
    ("UPL-V2-6030", "Uplift", "V2 Standing Desk 60x30 Bamboo", "desk", 749.00, {"width_in": 60, "depth_in": 30, "electric": True, "height_range_in": "25.3-50.9"}),
    ("400803", "Vari", "Electric Standing Desk 60x30 White", "desk", 695.00, {"width_in": 60, "depth_in": 30, "electric": True, "height_range_in": "25-50.5"}),
    ("JRV-BAM-6030", "Fully", "Jarvis Bamboo Standing Desk 60x30", "desk", 699.00, {"width_in": 60, "depth_in": 30, "electric": True, "height_range_in": "24.5-50"}),
    ("45-241-026", "Ergotron", "LX Desk Mount Monitor Arm Polished Aluminum", "monitor_arm", 189.99, {"displays": 1, "max_size_in": 34, "max_weight_lb": 25}),
    ("45-245-026", "Ergotron", "LX Dual Side-by-Side Monitor Arm", "monitor_arm", 349.99, {"displays": 2, "max_size_in": 27, "max_weight_lb": 20}),
    ("M21", "Humanscale", "M2.1 Single Monitor Arm", "monitor_arm", 259.00, {"displays": 1, "max_size_in": 32, "max_weight_lb": 15}),
    ("STAND-V002", "VIVO", "Dual Monitor Desk Mount Stand", "monitor_arm", 39.99, {"displays": 2, "max_size_in": 27, "max_weight_lb": 22}),
    ("HNDS6", "HUANUO", "Dual Monitor Stand Gas Spring", "monitor_arm", 59.99, {"displays": 2, "max_size_in": 32, "max_weight_lb": 19.8}),
    ("0007901", "Fellowes", "Lotus Sit-Stand Workstation", "desk_converter", 349.99, {"width_in": 32.75, "electric": False}),
    ("8037601", "Fellowes", "Professional Series Back Support", "accessory", 44.99, {}),
    ("48121", "Fellowes", "Standard Footrest", "accessory", 29.99, {}),
    # --- printers & consumables ---------------------------------------------
    ("W1A53A", "HP", "LaserJet Pro M404dn Mono Laser Printer", "printer", 329.00, {"type": "laser", "color": False, "duplex": True, "network": "Ethernet"}),
    ("W1A30A", "HP", "LaserJet Pro MFP M428fdw Mono All-in-One", "printer", 449.00, {"type": "laser", "color": False, "duplex": True, "network": "Ethernet / Wi-Fi"}),
    ("HL-L2370DW", "Brother", "HL-L2370DW Mono Laser Printer", "printer", 199.99, {"type": "laser", "color": False, "duplex": True, "network": "Ethernet / Wi-Fi"}),
    ("MFC-L3770CDW", "Brother", "MFC-L3770CDW Color All-in-One LED Printer", "printer", 499.99, {"type": "led", "color": True, "duplex": True, "network": "Ethernet / Wi-Fi"}),
    ("5161C005", "Canon", "imageCLASS MF455dw Mono All-in-One", "printer", 399.00, {"type": "laser", "color": False, "duplex": True, "network": "Ethernet / Wi-Fi"}),
    ("C11CJ60201", "Epson", "EcoTank ET-4850 Color All-in-One", "printer", 449.99, {"type": "inkjet", "color": True, "duplex": True, "network": "Ethernet / Wi-Fi"}),
    ("CF258A", "HP", "58A Black Original LaserJet Toner Cartridge", "consumable", 109.99, {"yield_pages": 3000}),
    ("TN760", "Brother", "TN-760 High Yield Black Toner", "consumable", 79.99, {"yield_pages": 3000}),
    ("PA03770-B615", "Fujitsu", "ScanSnap iX1600 Document Scanner", "scanner", 419.99, {"ppm": 40, "duplex": True}),
    # --- storage & memory ----------------------------------------------------
    ("MU-PC1T0T/AM", "Samsung", "T7 Portable SSD 1TB USB 3.2", "storage", 109.99, {"capacity_gb": 1000, "interface": "USB-C 3.2"}),
    ("SDSSDE81-2T00-G25", "SanDisk", "Extreme Pro Portable SSD 2TB", "storage", 199.99, {"capacity_gb": 2000, "interface": "USB-C 3.2"}),
    ("STKM4000400", "Seagate", "Expansion Portable HDD 4TB", "storage", 99.99, {"capacity_gb": 4000, "interface": "USB 3.0"}),
    ("MZ-V8P1T0B/AM", "Samsung", "980 PRO 1TB NVMe M.2 SSD", "storage", 119.99, {"capacity_gb": 1000, "interface": "PCIe 4.0 NVMe"}),
    ("CT2K16G48C40S5", "Crucial", "32GB Kit (2x16GB) DDR5-4800 SODIMM", "memory", 89.99, {"capacity_gb": 32, "type": "DDR5-4800 SODIMM"}),
    ("SDCZ48-128G-U46", "SanDisk", "Ultra 128GB USB 3.0 Flash Drive", "storage", 14.99, {"capacity_gb": 128, "interface": "USB-A 3.0"}),
    ("DT70/64GB", "Kingston", "DataTraveler 70 64GB USB-C Flash Drive", "storage", 9.99, {"capacity_gb": 64, "interface": "USB-C 3.2"}),
    # --- cables, adapters, power, networking, misc ---------------------------
    ("A8856", "Anker", "USB-C to USB-C 100W Cable 6ft (2-pack)", "cable", 19.99, {"length_ft": 6, "pack_qty": 2, "spec": "USB 2.0 / 100W PD"}),
    ("201026", "Cable Matters", "USB-C to DisplayPort 1.4 Cable 6ft 8K", "cable", 24.99, {"length_ft": 6, "pack_qty": 1, "spec": "DP 1.4 8K60"}),
    ("201355", "Cable Matters", "USB-C to HDMI 2.1 Cable 6ft 4K120", "cable", 29.99, {"length_ft": 6, "pack_qty": 1, "spec": "HDMI 2.1"}),
    ("USB31CC1M", "StarTech", "USB-C to USB-C Cable 1m 10Gbps 100W", "cable", 21.99, {"length_ft": 3.3, "pack_qty": 1, "spec": "USB 3.1 Gen 2 / 100W PD"}),
    ("P580-006", "Tripp Lite", "DisplayPort 1.2 Cable 6ft", "cable", 12.99, {"length_ft": 6, "pack_qty": 1, "spec": "DP 1.2 4K60"}),
    ("13537", "Monoprice", "Cat6 Ethernet Patch Cable 7ft (10-pack)", "cable", 24.99, {"length_ft": 7, "pack_qty": 10, "spec": "Cat6 UTP"}),
    ("A8352", "Anker", "7-in-1 USB-C Hub (HDMI, PD, SD, 3x USB-A)", "adapter", 34.99, {"ports": 7, "pd_w": 85}),
    ("MX0J2AM/A", "Apple", "96W USB-C Power Adapter", "power", 79.00, {"watts": 96}),
    ("450-AHRG", "Dell", "130W USB-C AC Adapter", "power", 89.99, {"watts": 130}),
    ("A2667", "Anker", "735 Charger GaNPrime 65W 3-port", "power", 59.99, {"watts": 65}),
    ("BE112230-08", "Belkin", "12-Outlet Surge Protector 8ft 3940J", "power", 34.99, {"outlets": 12, "joules": 3940}),
    ("BE600M1", "APC", "Back-UPS 600VA 7-Outlet UPS", "power", 89.99, {"va": 600, "outlets": 7}),
    ("CP1500PFCLCD", "CyberPower", "CP1500PFCLCD PFC Sinewave UPS 1500VA", "power", 249.95, {"va": 1500, "outlets": 12}),
    ("GS308-300PAS", "Netgear", "GS308 8-Port Gigabit Unmanaged Switch", "network", 29.99, {"ports": 8, "managed": False}),
    ("TL-SG108", "TP-Link", "TL-SG108 8-Port Gigabit Desktop Switch", "network", 24.99, {"ports": 8, "managed": False}),
    ("U6-LITE-US", "Ubiquiti", "UniFi 6 Lite Access Point", "network", 99.00, {"wifi": "Wi-Fi 6", "poe": True}),
    ("910-004654", "Logitech", "Spotlight Presentation Remote", "accessory", 129.99, {}),
    ("K64440WW", "Kensington", "ClickSafe 2.0 Keyed Laptop Lock", "accessory", 44.99, {}),
    ("K65020WW", "Kensington", "MicroSaver 2.0 Keyed Laptop Lock", "accessory", 39.99, {}),
    ("5060408461426", "Yubico", "YubiKey 5 NFC Security Key", "accessory", 50.00, {"interfaces": "USB-A / NFC"}),
    ("10032", "Rain Design", "mStand Laptop Stand Silver", "laptop_stand", 49.90, {"adjustable": False}),
    ("RST-V3", "Roost", "Laptop Stand V3", "laptop_stand", 89.95, {"adjustable": True}),
    ("12-2003", "Twelve South", "Curve Laptop Stand Matte Black", "laptop_stand", 59.99, {"adjustable": False}),
    ("B07D74DT3B", "Amazon Basics", "Ventilated Adjustable Laptop Stand", "laptop_stand", 29.99, {"adjustable": True}),
    ("MP114", "3M", "Precise Mouse Pad with Gel Wrist Rest", "accessory", 19.99, {}),
    ("956-000001", "Logitech", "MX Palm Rest", "accessory", 19.99, {}),
]

assert len(BASE) == 154, len(BASE)
assert len({b[0] for b in BASE}) == len(BASE), "duplicate MPN in BASE"

CATEGORY_A = {  # NorthStar's own taxonomy
    "monitor": "Computers & Tablets > Monitors",
    "docking_station": "Computers & Tablets > Docking Stations & Hubs",
    "keyboard": "Computer Accessories > Keyboards",
    "mouse": "Computer Accessories > Mice & Trackballs",
    "headset": "Audio & Video > Headsets",
    "webcam": "Audio & Video > Webcams",
    "speakerphone": "Audio & Video > Conference Speakerphones",
    "laptop": "Computers & Tablets > Laptops",
    "chair": "Furniture > Office Chairs",
    "desk": "Furniture > Standing Desks",
    "desk_converter": "Furniture > Sit-Stand Converters",
    "monitor_arm": "Furniture > Monitor Arms & Mounts",
    "accessory": "Office Supplies > Desk Accessories",
    "printer": "Printers & Scanners > Printers",
    "scanner": "Printers & Scanners > Scanners",
    "consumable": "Printers & Scanners > Ink & Toner",
    "storage": "Computer Accessories > Storage",
    "memory": "Computer Accessories > Memory",
    "cable": "Computer Accessories > Cables",
    "adapter": "Computer Accessories > Adapters & Hubs",
    "power": "Computer Accessories > Power & Surge",
    "network": "Networking",
    "laptop_stand": "Computer Accessories > Laptop Stands",
}
CATEGORY_B = {  # TechSource taxonomy (short codes + labels)
    "monitor": ("MON", "Monitors"),
    "docking_station": ("DOCK", "Docking Stations"),
    "keyboard": ("INP-KB", "Input Devices / Keyboards"),
    "mouse": ("INP-MS", "Input Devices / Mice"),
    "headset": ("AUD-HS", "Audio / Headsets"),
    "webcam": ("VID-CAM", "Video / Webcams"),
    "speakerphone": ("AUD-SP", "Audio / Conferencing"),
    "laptop": ("NB", "Laptops"),
    "chair": ("FURN-CH", "Office Furniture / Chairs"),
    "desk": ("FURN-DK", "Office Furniture / Desks"),
    "desk_converter": ("FURN-DK", "Office Furniture / Desks"),
    "monitor_arm": ("FURN-ARM", "Office Furniture / Monitor Mounts"),
    "accessory": ("ACC", "Accessories"),
    "printer": ("PRN", "Printers"),
    "scanner": ("SCN", "Scanners"),
    "consumable": ("PRN-SUP", "Printers / Supplies"),
    "storage": ("STO", "Storage"),
    "memory": ("MEM", "Memory"),
    "cable": ("CAB", "Cables"),
    "adapter": ("CAB-ADP", "Cables / Adapters"),
    "power": ("PWR", "Power"),
    "network": ("NET", "Networking"),
    "laptop_stand": ("ACC-STD", "Accessories / Laptop Stands"),
}

def upc12(rng: random.Random) -> str:
    digits = [0] + [rng.randint(0, 9) for _ in range(10)]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits))
    return "".join(map(str, digits)) + str((10 - total % 10) % 10)


def spec_sentence(cat: str, s: dict) -> str:
    if cat == "monitor":
        return f"{s['size_in']}-inch {s['panel']} panel, {s['resolution']} at {s['refresh_hz']} Hz" + (", USB-C input with power delivery" if s.get("usb_c") else "")
    if cat == "docking_station":
        return f"{s['connector']} host connection, up to {s['max_displays']} displays, {s['power_delivery_w']} W power delivery"
    if cat in ("keyboard", "mouse"):
        return f"{s['connection']} connectivity" + (", ergonomic design" if s.get("ergonomic") else "")
    if cat == "headset":
        return f"{s['connection']}" + (", active noise cancelling" if s.get("anc") else "") + f", {s['uc_certified']} certified"
    if cat == "webcam":
        return f"{s['resolution']} at {s['fps']} fps with privacy shutter"
    if cat == "laptop":
        return f"{s['screen_in']}\" display, {s['cpu']}, {s['ram_gb']} GB RAM, {s['ssd_gb']} GB SSD"
    if cat == "desk":
        return f"{s['width_in']}x{s['depth_in']} in top, electric height range {s['height_range_in']} in"
    if cat == "monitor_arm":
        return f"Holds {s['displays']} display(s) up to {s['max_size_in']} in / {s['max_weight_lb']} lb each"
    if cat == "printer":
        return f"{'Color' if s['color'] else 'Monochrome'} {s['type']}, {'automatic duplex' if s['duplex'] else 'simplex'}, {s['network']}"
    if cat in ("storage", "memory"):
        return f"{s['capacity_gb']} GB, {s.get('interface', s.get('type'))}"
    if cat == "cable":
        return f"{s['length_ft']} ft, {s['spec']}" + (f", pack of {s['pack_qty']}" if s["pack_qty"] > 1 else "")
    return ""


# ---------------------------------------------------------------------------
# Supplier A: NorthStar Office Supply
# ---------------------------------------------------------------------------
def build_northstar(items: list[tuple], rng: random.Random) -> dict:
    out = []
    for i, (mpn, brand, name, cat, usd, specs) in enumerate(items, start=1):
        price = round(usd * rng.uniform(0.96, 1.06), 2)
        qty = rng.choice([0, 0, 3, 5, 8, 12, 25, 40, 60, 120, 250])
        ships = rng.choice([1, 1, 2, 2, 3, 3, 5, 7, 10, 14])
        rating = round(rng.uniform(3.2, 4.9), 1)
        sent = spec_sentence(cat, specs)
        desc = f"{brand} {name}. " + (f"{sent}. " if sent else "") + "Suitable for everyday office and hybrid-work use."
        out.append(
            {
                "item_number": f"NS-{100000 + i * 7}",
                "name": f"{brand} {name}",
                "manufacturer": brand,
                "mfr_part_number": mpn,
                "category_path": CATEGORY_A[cat],
                "description": desc,
                "unit_price": price,
                "price_note": None,
                "in_stock": qty > 0,
                "qty_available": qty,
                "ships_in_days": ships if qty > 0 else None,
                "shipping_method": "Ground" if ships >= 3 else "Expedited",
                "rating": rating,
                "review_count": rng.randint(0, 900),
                "return_window_days": rng.choice([30, 30, 30, 45, 90, 0]),
                "warranty": rng.choice(["1 year manufacturer", "2 year manufacturer", "3 year manufacturer", "90 days"]),
                "min_order_qty": 1,
                "specs": specs,
                "_cat": cat,
            }
        )

    # --- seeded edge cases ---
    def pick(pred, n):
        cands = [p for p in out if pred(p) and "_edge" not in p]
        chosen = rng.sample(cands, n)
        for c in chosen:
            c["_edge"] = True
        return chosen

    for p in pick(lambda p: p["_cat"] in ("chair", "desk", "printer", "laptop"), 4):  # quote-only
        p["unit_price"] = None
        p["price_note"] = "Call for pricing"
    for p in pick(lambda p: p["_cat"] in ("cable", "consumable"), 3):  # MOQ
        p["min_order_qty"] = rng.choice([5, 10, 24])
    for p in pick(lambda p: p["_cat"] == "monitor" and p["specs"]["size_in"] == 27 and p["mfr_part_number"] != "U2723QE", 1):  # suspicious price
        p["unit_price"] = 27.99
        p["description"] += " Clearance - open box."
    for p in pick(lambda p: p["rating"] is not None, 5):  # missing rating
        p["rating"] = None
        p["review_count"] = 0
    for p in pick(lambda p: p["qty_available"] > 0, 2):  # long backorder-style lead time
        p["ships_in_days"] = 45
        p["shipping_method"] = "Freight"

    for p in out:
        p.pop("_cat", None)
        p.pop("_edge", None)

    assert len(out) == 100, len(out)
    return {
        "supplier": {
            "id": "northstar",
            "name": "NorthStar Office Supply",
            "country": "US",
            "currency": "USD",
            "prices_include_tax": False,
            "catalog_version": "2026-10-16",
        },
        "items": out,
    }


# ---------------------------------------------------------------------------
# Supplier B: TechSource Supply Co.
# ---------------------------------------------------------------------------
def vary_mpn(mpn: str, rng: random.Random) -> str:
    """Introduce realistic MPN formatting drift (dedupe trap)."""
    r = rng.random()
    if r < 0.25:
        return mpn.lower()
    if r < 0.45:
        return mpn.replace("-", "").replace("/", "")
    if r < 0.55:
        return mpn.replace("-", " ")
    return mpn


def name_b(brand: str, name: str, mpn: str, rng: random.Random) -> str:
    style = rng.random()
    if style < 0.35:
        return f"{brand} {mpn} - {name}"
    if style < 0.6:
        return f"{name} | {brand}"
    if style < 0.75:
        return f"{brand} {name.replace(chr(34), ' in.').replace('-inch', ' in.')}"
    return f"{brand} {name}"


def build_techsource(items: list[tuple], rng: random.Random) -> dict:
    out = []
    for i, (mpn, brand, name, cat, usd, specs) in enumerate(items, start=1):
        price = round(usd * rng.uniform(0.95, 1.08), 2)
        status = rng.choices(
            ["available", "available", "available", "low_stock", "backorder", "discontinued", "on_request"],
            weights=[40, 20, 15, 10, 8, 4, 3],
        )[0]
        qty = {"available": rng.randint(15, 400), "low_stock": rng.randint(1, 5), "backorder": 0, "discontinued": 0, "on_request": None}[status]
        lead = {"available": rng.choice([1, 2, 3]), "low_stock": rng.choice([2, 3, 5]), "backorder": rng.choice([21, 28, 35, 45]), "discontinued": None, "on_request": None}[status]
        window = {
            1: "1-2 business days", 2: "2-3 business days", 3: "3-5 business days", 5: "5-7 business days",
            21: "3-4 weeks", 28: "4-5 weeks", 35: "5-6 weeks", 45: "6-8 weeks", None: None,
        }[lead]
        code, label = CATEGORY_B[cat]
        attrs = [{"name": k, "value": v} for k, v in specs.items()]
        price_block = None if status == "on_request" else {"amount": price, "currency": "USD"}
        out.append(
            {
                "product": {
                    "id": f"TS{20000 + i * 3}",
                    "name": name_b(brand, name, mpn, rng),
                    "brand": brand,
                    "identifiers": {"mpn": vary_mpn(mpn, rng), "upc": upc12(rng)},
                    "category": {"code": code, "label": label},
                    "long_description": f"{spec_sentence(cat, specs)}." if spec_sentence(cat, specs) else f"{brand} {name}.",
                    "attributes": attrs,
                },
                "pricing": price_block,
                "availability": {"status": status, "quantity": qty, "lead_time_days": lead},
                "logistics": {"delivery_window": window, "ships_from": rng.choice(["TX-Dallas", "OH-Columbus", "NV-Reno"])},
                "rating": None if rng.random() < 0.15 else {"average": round(rng.uniform(3.0, 5.0), 2), "count": rng.randint(1, 400), "scale": 5},
                "policies": {"return_days": rng.choice([14, 14, 30, 30, 0]), "warranty_months": rng.choice([12, 24, 24, 36, 60])},
                "min_order_quantity": 1,
                "_cat": cat,
            }
        )

    def pick(pred, n):
        cands = [p for p in out if pred(p) and "_edge" not in p]
        chosen = rng.sample(cands, n)
        for c in chosen:
            c["_edge"] = True
        return chosen

    for p in pick(lambda p: p["_cat"] in ("cable", "consumable", "accessory"), 3):
        p["min_order_quantity"] = rng.choice([5, 10, 25])
    for p in pick(lambda p: p["pricing"] is not None, 1):  # pricing present but amount missing (malformed)
        p["pricing"]["amount"] = None

    for p in out:
        p.pop("_cat", None)
        p.pop("_edge", None)

    assert len(out) == 100, len(out)
    return {
        "vendor": {
            "code": "TSC",
            "name": "TechSource Supply Co.",
            "country": "US",
            "currency": "USD",
            "prices_include_tax": False,
            "feed_generated": "2026-10-16T06:00:00Z",
        },
        "products": out,
    }


def main() -> None:
    rng = random.Random(SEED)
    shuffled = BASE[:]
    rng.shuffle(shuffled)
    a_items = shuffled[:100]         # 100 items
    b_items = shuffled[54:154]       # 100 items; indices 54..99 overlap with A (46 products)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "northstar_office.json").write_text(
        json.dumps(build_northstar(a_items, random.Random(SEED + 1)), indent=2, ensure_ascii=False) + "\n"
    )
    (OUT_DIR / "techsource.json").write_text(
        json.dumps(build_techsource(b_items, random.Random(SEED + 2)), indent=2, ensure_ascii=False) + "\n"
    )
    overlap = {x[0] for x in a_items} & {x[0] for x in b_items}
    print(f"NorthStar: 100 items, TechSource: 100 items, shared MPNs: {len(overlap)}")


if __name__ == "__main__":
    main()
