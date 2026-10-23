import pandas as pd
import re, os, json, sys
import psutil
import platform
from datetime import datetime

application_name = sys.argv[1]
list_csv = sys.argv

df_frames = []
for fname in list_csv:
    if ".csv" in fname:
        df_frames.append(fname)

tmp_dir = os.getcwd()

frames = []

for df in df_frames:
    try:
        df_test = pd.read_csv(tmp_dir+'/'+df)
        frames.append(df_test)
    except:
        print("NO COLUMNS TO PASRSE in", tmp_dir)
    
    
result = pd.concat(frames, ignore_index=True)

date_time = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

result.to_csv(application_name+'_'+date_time+'.csv', header=True, index=False)


    