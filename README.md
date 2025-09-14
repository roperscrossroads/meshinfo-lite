# MeshInfo-Lite (Generic & Configurable)

Realtime web UI to run against a Meshtastic regional or private mesh network.

## Overview

MeshInfo-Lite is a highly customized version of [MeshInfo](https://github.com/MeshAddicts/meshinfo) written in Python and connects to an MQTT server that is receiving Meshtastic messages for the purpose of visualizing and inspecting traffic. It uses MariaDB to persist content.

**🎯 NEW: Fully Generic & Configurable!** This version has been made completely generic and configurable via `config.ini` files. Multiple mesh networks can use the same codebase by simply swapping configuration files - no template modifications required!

To make deployment to run an instance for your mesh easy, Docker support is included. We recommend using Docker Compose with a personalized version of the `docker-compose.yml` file to most easily deploy it, but any seasoned Docker user can also use the Docker image alone.

## 🎯 For Other Mesh Networks

This fork has been made **fully generic and configurable**. Other mesh networks can:

1. **Fork this repository**
2. **Copy one of the example configs** (`config-csra.ini.example` or `config-middlega.ini.example`) 
3. **Customize the config** for their network
4. **Deploy without any template modifications**

**No more mesh-specific forks needed!** 🎉 Everything is driven by configuration files.

**Example deployments:**
- [CSRA Mesh](https://csramesh.duckdns.org/) (Central Savannah River Area)
- [Middle GA Mesh](https://middlega.duckdns.org) (Middle Georgia)
- [South African Mesh](https://mesh.zr1rf.za.net) (Original example)
- Your mesh network here!

If you deploy this for your mesh network, let us know and we'll add you to the list above!

If you are running a high elevation node, preferrably a `Router` or `Repeater` node, you might be interested in getting on the notification list for a [cavity filter](https://shop.airframes.io/products/lora-915mhz-filter) that Kevin and Trevor are having made.

If you're interested in aeronautical (ADS-B/ACARS/VDL/HFDL/SATCOM) or ship tracking (AIS), please take a look at sister project [Airframes](https://airframes.io) / [Airframes Github](https://github.com/airframesio).

## Screenshots

[<img src="https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo1.png" alt="MeshInfo Map" width="200" />](https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo1.png)
[<img src="https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo2.png" alt="MeshInfo Node" width="200" />](https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo2.png)
[<img src="https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo3.png" alt="MeshInfo Neighbors" width="200" />](https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo3.png)
[<img src="https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo4.png" alt="MeshInfo Node Details" width="200" />](https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo4.png)
[<img src="https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo6.png" alt="MeshInfo Graph" width="200" />](https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo6.png)
[<img src="https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo7.png" alt="#MeshtasticMonday" width="200" />](https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo7.png)
[<img src="https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo5.png" alt="Container running" width="260" />](https://raw.githubusercontent.com/dadecoza/meshinfo-lite/main/docs/meshinfo5.png)


## Supported Meshtastic Message Types

- neighborinfo
- nodeinfo
- position
- telemetry
- text
- traceroute
- mapreport
- routing

## Features

### Current

- Chat
- Map
- Nodes
- Node Neighbors
- Mesh Messages
- MQTT Messages
- Telemetry
- Traceroutes
- Routing Messages

### Configuration-Driven Customization

**🆕 All mesh-specific content is now configurable via `config.ini`:**

- **Branding**: Mesh name, region, description, logo
- **MQTT Settings**: Server, credentials, display settings
- **Navigation Links**: Customizable dropdown with external tools/resources
- **Community Links**: Fellow mesh network cross-linking
- **External Node Links**: MeshMap, regional maps, etc.
- **Theming**: Colors, styles, favicon
- **Features**: Toggle #MeshtasticMonday, experimental features
- **Node Registration**: Optional user accounts and node claiming

**Example mesh networks using this codebase:**
- CSRA Mesh (Central Savannah River Area)
- Middle GA Mesh (Middle Georgia)
- Your mesh network here!

### Upcoming

- Statistics
- Overview of Routes

## Chat

If you're using this and have questions, or perhaps you want to join in on the dev effort and want to interact collaboratively, come chat with us on [#meshinfo on Meshtastic ZA Discord](https://discord.gg/cmFCKBxY).

## Documentation

📚 **Complete documentation is available in the [docs/](docs/) directory:**

- **[Setup Guide](docs/SETUP_DOCKER.md)** - Docker Compose installation (recommended)
- **[Manual Setup](docs/SETUP.md)** - Traditional installation guide
- **[Caching & Performance](docs/CACHING.md)** - Memory management and optimization
- **[Contributing](docs/CONTRIBUTING.md)** - How to contribute to the project

## 🚀 Quick Deploy Guide

### For Your Mesh Network

1. **Clone this repository**
2. **Choose a starting config:**
   - Copy `config.ini.sample` to `config.ini` for a blank template
   - OR copy `config-csra.ini.example` to `config.ini` for CSRA-style setup
   - OR copy `config-middlega.ini.example` to `config.ini` for Middle GA-style setup
3. **Edit your `config.ini`:**
   - Update `[mesh]` section with your network details
   - Update `[mqtt]` section with your MQTT server
   - Customize `[tools]` and `[community_links]` sections as needed
4. **Deploy using Docker Compose** (see sections below)

That's it! No template modifications needed - everything is config-driven.

### 💡 **Why This Fork?**

Unlike other MeshInfo-Lite forks that require template modifications for each mesh network, this version:

- ✅ **Single codebase** supports unlimited mesh networks
- ✅ **Zero template editing** required 
- ✅ **Easy updates** without losing customizations
- ✅ **Professional branding** for each mesh network
- ✅ **Community cross-linking** between mesh networks
- ✅ **Example configurations** to get started quickly

**Perfect for mesh network operators who want a professional site without the hassle!**

## Running

### Docker Compose (preferred for 24/7 servers)

For detailed Docker setup instructions, see **[docs/SETUP_DOCKER.md](docs/SETUP_DOCKER.md)**.

#### Quick Setup

##### Clone the repo

```sh
git clone https://github.com/agessaman/meshinfo-lite.git
cd meshinfo-lite
```

##### Edit Configuration

1. Copy and then edit the `config.ini.sample` to `config.ini`
2. **OR** use one of the provided example configs:
   - `cp config-csra.ini.example config.ini` (for CSRA Mesh setup)
   - `cp config-middlega.ini.example config.ini` (for Middle GA Mesh setup) 
      
#### To Run

Change to the directory.

```sh
cd meshinfo-lite
```

```sh
docker compose down && docker compose up --build -d && docker compose ps && docker compose logs -f meshinfo
```

#### To Update

```sh
git fetch && git pull && docker compose down && docker compose up --build -d && docker compose ps && docker compose logs -f meshinfo
```

### Directly (without Docker)

Be sure you have `Python 3.12.4` or higher installed.

Install MariaDB and create the database and user permissions
```
sudo mysql -u root
CREATE DATABASE IF NOT EXISTS meshdata;
CREATE USER IF NOT EXISTS 'meshdata'@'localhost' IDENTIFIED BY 'passw0rd';
GRANT ALL ON meshdata.* TO 'meshdata'@'localhost';
ALTER DATABASE meshdata CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
COMMIT;
```


```sh
python -m venv .
. bin/activate
pip install -r requirements.txt
python main.py
```

## Development

### Building a local Docker image

Clone the repository.

```sh
git clone https://github.com/agessaman/meshinfo-lite.git
```

If already existing, be sure to pull updates.

```sh
git fetch && git pull
```

Build. Be sure to specify a related version number and suffix (this example `dev5` but could be your name or initials and a number) as this will help prevent collisions in your local image cache when testing.

```sh
scripts/docker-build.sh 0.0.1dev5
```

### Running via Docker Compose while developing

```sh
docker compose -f docker-compose-dev.yml up --build --force-recreate
```

You will need to CTRL-C and run again if you make any changes to the python code, but not if you only make changes to
the templates.


## Contributing

We happily accept Pull Requests! Please see **[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)** for detailed guidelines and **[docs/CODE_OF_CONDUCT.md](docs/CODE_OF_CONDUCT.md)** for our community standards.

## Meshtastic node settings

These are the settings that must be set, and how they must be set on your node if you would like it to show up on the map. Anything that is not preceded by "Recommended" must be set as stated for your node to show.

```
Channels > Click on LongFast
	Uplink Enabled: True
	Downlink Enabled: Recommended False
	Position Enabled: True
	Precise Location: False
	Bottom slider: 1194ft is the *most* accurate setting that will still show up on any map. This is a meshtastic limitation.
	
	Be sure to click send to save after each page/section

Position: 
	
	Set your lat/long/alt and set "Used fixed position" to True if your node doesn't have GPS or is stationary
	
	Otherwise set your GPS settings.
	
Lora: 
	OK to MQTT: True
	
MQTT:
	Address: mqtt.meshtastic.org
	Username: meshdev
	Password: large4cats
	
	Encryption enabled: True
	JSON output enabled: False

	Root topic: msh/US/FL/anything
 (Typical options to replace 'anything' above are: orl, jax, etc...As long as your root topic starts with msh/US/FL then you're good.)

	Proxy to client enabled: True if your board isn't directly hooked to Wi-Fi or Ethernet.
	Map reporting: True
	Precise location: False
	
	Slider at the bottom: 1194 feet is the *most* accurate you can set things to and still have your node show up on maps.
	
	Map reporting interval: 900
```
