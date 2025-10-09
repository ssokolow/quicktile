#!/bin/sh

TEST_DUMMY="${TEST_DUMMY:-featherpad}"

TEST_SCRIPT="center top top-right right bottom-right bottom bottom-left left top-left top-left move-to-center move-to-top move-to-top-right move-to-right move-to-bottom-right move-to-bottom move-to-bottom-left move-to-left move-to-top-left monitor-switch monitor-prev monitor-next monitor-prev bordered bordered shade shade maximize maximize vertical-maximize vertical-maximize horizontal-maximize horizontal-maximize fullscreen fullscreen always-above always-above always-below always-below all-desktops all-desktops show-desktop show-desktop minimize workspace-go-down workspace-go-up workspace-go-right workspace-go-left workspace-go-next workspace-go-prev"

if ! which dbus-send >/dev/null; then
    echo "ERROR: Command 'dbus-send' not found. Please make sure it's installed so the D-Bus tests can run."
    exit 1
fi

if ! which "dbus-send" >/dev/null; then
    echo "ERROR: Command '$TEST_DUMMY' not found. Please set the TEST_DUMMY environment variable to something which will start quickly and take focus with a window to be moved around the screen."
    exit 1
fi

echo "This script will do a very cursory functional test run, relying on the human to notice if the command invoked doesn't have the desired effect."
echo "To minimize the chance of problems, please ensure you are not on the rightmost virtual desktop of a multi-column grid, or the bottom-most virtual-desktop of a multi-row grid."
echo "Make sure it's running in a free-floating terminal window that is NOT yet on-all-desktops or always-on-top, prepare to pay attention and press Enter to begin testing the CLI interface."
read -r _FOO

# Make the current window follow us around
./quicktile.sh all-desktops always-above

"$TEST_DUMMY" &
echo "3..."
sleep 1
echo "2..."
sleep 1
echo "1..."
sleep 1

for command in $TEST_SCRIPT; do
    echo "CLI Testing $command..."
    ./quicktile.sh "$command"
    sleep 1
done

echo ""
echo "THE TEST WINDOW SHOULD NOW BE MINIMIZED. Please close it and then press Enter to begin the D-Bus test."
read -r _FOO

echo "Starting daemonized QuickTile in background..."
./quicktile.sh --daemonize >/dev/null 2>/dev/null &
quicktile_pid=$!
"$TEST_DUMMY" &
echo "3..."
sleep 1
echo "2..."
sleep 1
echo "1..."
sleep 1

for command in $TEST_SCRIPT; do
    echo "D-Bus Testing $command..."
    dbus-send --type=method_call \
        --dest=com.ssokolow.QuickTile \
        /com/ssokolow/QuickTile \
        com.ssokolow.QuickTile.doCommand \
        "string:$command"
    sleep 1
done

kill "$quicktile_pid"

# Reverse changes made to the terminal window
./quicktile.sh all-desktops always-above

echo ""
echo "Commands that were not tested because they change the active window:"
echo "    workspace-send-down"
echo "    workspace-send-left"
echo "    workspace-send-next"
echo "    workspace-send-prev"
echo "    workspace-send-right"
echo "    workspace-send-up"
echo ""
echo "Commands that were not tested due to a lack of isolation:"
echo "    monitor-next-all"
echo "    monitor-prev-all"
echo "    monitor-switch-all"
echo ""
echo "Commands that were not tested because they require manual input:"
echo "    trigger-move"
echo "    trigger-resize"
echo ""
echo "Interfaces that were not tested:"
echo "    Internal keybinder"
echo ""
echo "THE TEST WINDOW SHOULD NOW BE MINIMIZED. You may close it. The test is complete."

# TODO: Decide how to simply, externally detect keybinding failure so I can
# test --daemonize's internal keybinder using xdotool and
# a temporary config file.
