# DECtalker
DECtalker is a discord bot wrapper for the DECtalk `say` binary. 

## Installation on Linux
```sh
git clone https://github.com/RealArtsn/DECtalker.git
cd DECtalker
pip install -r requirements.txt
```

Next, clone the dectalk repository and follow compile instructions here: https://github.com/dectalk/dectalk

DECtalker will look for the binary in its default location.


## Usage

This bot has built-in slash commands. To sync these slash commands with Discord, run the following:

`python main.py sync`

Users will then be able to communicate with the bot and have it speak within voice channels.