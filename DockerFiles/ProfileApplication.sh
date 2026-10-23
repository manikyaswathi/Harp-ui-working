#!/bin/bash

# DO NOT Modify FROM HERE

# Checks for TACC vs OSC singularity setup
# Do not provie any arguments for local box execution
if [ -z "$1" ]
then
    echo "In local box, with mounted volume"
else
    if [ "$1" = "osc" ]
    then
        echo "Configuring Scratch Space for HARP profiler with OSC"
        if [ "$2" = "" ] 
        then
            echo "Provide a second argument with a system path with RWX priviledges"
            exit 1
        fi
        SCRATCH=$2
    else
        echo "The Scratch space for TACC is configured with singularity."
    fi
fi

# This is the location to store all Models and emulated histories 
export HARP_STORE="$SCRATCH/HARP_STORE"
mkdir -p $HARP_STORE
# This is the location for storing temporary emulated data - logs, oputput files, etc. 
export TARGET_APP="$SCRATCH/TARGET_APP"
mkdir -p $TARGET_APP

# Copying the application to a persisyant storage with read, write and execute priviledges
echo "Copying the application to be profiled (the complete folder path to the application should be provided)"
cp -R /app/$APP_NAME $TARGET_APP/.
cp -R /app/HARP/Post_Execution_Scripts/basic/* $TARGET_APP/$APP_NAME/.
chmod -R 755 $TARGET_APP/*
export APP_HOME="$TARGET_APP/$APP_NAME"
cd $APP_HOME
# DO NOT Modify TILL HERE

# Replace the "pipeline_config.json" with the filename with all profiling configurations of HARP at the Target application work folder
harp pipeline_config.json

