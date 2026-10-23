#!/bin/bash

scapper_file=DataScrapper.py

cp $APP_HOME/$scapper_file $scapper_file

python3 $scapper_file "train"


