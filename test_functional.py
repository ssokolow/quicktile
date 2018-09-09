#!/usr/bin/env python

import subprocess

TEST_SCRIPT = """
monitor-next-all
monitor-prev-all
monitor-switch-all
monitor-prev-all

monitor-next
monitor-prev
monitor-switch
monitor-prev

bottom
bottom-left
bottom-right
left
middle
right
top
top-left
top-right

move-to-bottom
move-to-bottom-left
move-to-bottom-right
move-to-center
move-to-left
move-to-right
move-to-top
move-to-top-left
move-to-top-right

bordered
bordered

always-above
always-above
always-below
always-below
horizontal-maximize
horizontal-maximize
vertical-maximize
vertical-maximize
shade
shade
fullscreen
fullscreen
all-desktops
all-desktops

maximize
maximize
minimize

trigger-move
trigger-resize

show-desktop
show-desktop

workspace-send-down
workspace-send-up
workspace-send-left
workspace-send-right
workspace-send-next
workspace-send-prev

workspace-go-down
workspace-go-up
workspace-go-left
workspace-go-right
workspace-go-next
workspace-go-prev
"""

raw_input("IMPORTANT! Switch to an empty desktop and press Enter.")

for command in TEST_SCRIPT.split('\n'):
    command = command.split('#')[0].strip()
    if command:
        subprocess.check_call(['quicktile', command])
