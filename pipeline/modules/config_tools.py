import os, json, sys, re, shutil
import pandas as pd
import numpy as np
import platform

from constants import *

def validate_config(config):
    if "application" not in config.keys():
        print(f"ERROR: Application name not provided in config")
        return False
    if "application_category" not in config.keys():
        print(f"ERROR: Application Category name not provided in config")
        return False

    return True
    

def create_application_config(src_config: dict):
    # pipeline_home_path = os.getenv(PIPELINE_HOME_VAR)
    pipeline_store_path = os.getenv(HARP_STORE)

    application_home = os.path.join(pipeline_store_path, APPLICATION_FOLDER_NAME)
    # if not os.path.isdir(application_home):
    #     os.mkdir(application_home)
    
    
    pipeline_store_path = os.getenv(HARP_STORE)
    
    # Create the folder Structure 
    application_name = src_config["application"]
    application_category = src_config["application_category"]
    application_path = os.path.join(application_home, application_category, application_name)
    # os.makedirs(application_path, exist_ok=True)  

    train_path = os.path.join(application_path, TRAIN_DATASET_FOLDER_NAME)
    # os.mkdir(train_path)
    os.makedirs(train_path, exist_ok=True)  
   
    #models path
    models_path = os.path.join(application_path, MODELS_FOLDER_NAME)
    # os.mkdir(models_path)
    os.makedirs(models_path, exist_ok=True)  

    config = default_config
    config["application"] = src_config["application"] 
    config["application_category"] = src_config["application_category"]
    config["train_folder"] = train_path
    config["dataset"] = str(os.path.join(application_path, TRAIN_DATASET_FOLDER_NAME, DATASET_FILE_NAME))
    config["dataset_pca"] = str(os.path.join(application_path, TRAIN_DATASET_FOLDER_NAME, DATASET_PCA_FILE_NAME))
    config["model_commons_filename"] = str(os.path.join(application_path, MODEL_COMMONS_FILE_NAME))
    config["project_account"] = src_config["project_account"] 
    
    config_path = os.path.join(application_path, APPLICATION_CONFIG_FILE_NAME)
    with open(config_path, "w") as file:
        json.dump(config, file)

def save_application_config(config):

    pipeline_store_path = os.getenv(HARP_STORE)
    # Create the folder Structure 
    application_name = config["application"]
    application_category = config["application_category"]
    # Copy all files from run folder to train folder
    application_path = os.path.join(pipeline_store_path, APPLICATION_FOLDER_NAME, application_category, application_name)
    
    config_path = os.path.join(application_path, APPLICATION_CONFIG_FILE_NAME)

    with open(config_path, "w") as file:
        json.dump(config, file)

    

def get_application_config(application_name: str, application_category: str):
    # pipeline_home_path = os.getenv(PIPELINE_HOME_VAR)
    pipeline_store_path = os.getenv(HARP_STORE)
    application_path = os.path.join(pipeline_store_path, APPLICATION_FOLDER_NAME, application_category, application_name)
    if not os.path.isdir(application_path): #directory doesnt exist
        print(f"Application config was not found, creating a config for `{application_name}`...")
        create_application_config(application_name, application_category)
    
    config_path = os.path.join(application_path, APPLICATION_CONFIG_FILE_NAME)
    with open(config_path, "r") as file:
        config = json.load(file)
        
    return config
    
    
def create_application_structure(config: dict):
    # GET APPLICATION FOLDER FROM ENV
    # pipeline_home_path = os.getenv(PIPELINE_HOME_VAR)
    pipeline_store_path = os.getenv(HARP_STORE)
    
    # Create the folder Structure 
    application_name = config["application"]
    application_category = config["application_category"]
    application_run_folder = os.path.join(os.getenv(TARGET_APP), config['cheetah_app_directory'])
    # Copy all files from run folder to train folder
    
    application_path = os.path.join(pipeline_store_path, APPLICATION_FOLDER_NAME, application_category, application_name)
    if not os.path.isdir(application_path): #directory doesnt exist
        print(f"Application config was not found, creating a config for `{application_name}`...")
        create_application_config(config)
    
    pipeline_config_path = os.path.join(application_path, APPLICATION_CONFIG_FILE_NAME)
    pipeline_config = None
    with open(pipeline_config_path, "r") as file:
        pipeline_config = json.load(file)
    
    dest_train = pipeline_config["train_folder"]
    files = os.listdir(application_run_folder)
    filenames=[]
    for filename in files:
        if re.match(r'^'+application_name+'_[0-9_]+\.csv$', filename) :
            shutil.copy2(application_run_folder+"/"+filename, dest_train+"/"+filename)
            filenames.append(filename)
    
    print("I AM MERGING ALL FILES", filenames)
    
    frames = []
    for file in filenames:
        df_test = pd.read_csv(dest_train+'/'+file)
        frames.append(df_test)
        
    result = pd.concat(frames, ignore_index=True)
    uniq_id=[i for i in range(1, result.shape[0]+1, 1)]
    result['uniq_id']=np.array(uniq_id)
    result.to_csv(dest_train+'/'+DATASET_FILE_NAME, header=True, index=False)

    # Create a pipeline configure to train and save models
    config_path = os.path.join(application_path, APPLICATION_CONFIG_FILE_NAME)
    pipeline_config = None
    with open(config_path, "r") as file:
        pipeline_config = json.load(file)
        
    return pipeline_config
    
    

def configuration_check(config: dict, filename: str):
    exit_code = 0
      
    app_path = os.getenv(APP_HOME)
    # Check target application folder exists before checking for folders and re-writing file
    isExist = os.path.exists(app_path)
    
    if isExist:
        print("Application folder is found, ready to use HARP. ")
    else:
        print("Check for the existance of the provided application folder in the image file")
        exit_code = 1

    data_genpath = os.path.join(os.getenv(TARGET_APP), config['cheetah_app_directory'])
    os.makedirs(data_genpath, exist_ok=True)  
    
     
    return exit_code




    
def check_pre_generate(config: dict, filename: str):
    exit_code = 0
    
    data_genpath = os.path.join(os.getenv(TARGET_APP), config['cheetah_app_directory'])
    
    campaign_folders = []
    campaign_files=[]
   
        
    for i in config['runs']:
        campaign_folders.append(i['paths']['cheetah_campaign_name'])
        i['paths']['cheetah_campaign_file']=os.path.join(data_genpath, i['paths']['cheetah_campaign_file'])
        campaign_files.append(i['paths']['cheetah_campaign_file'])
        
    print_error = "The folldowing folders: [FOLDER_LIST], already exist. \nPlease delete them or change respective 'cheetah_campaign_name' names before executing 'generate phase' of HARP"
    exist_folder=[]
    for folder in campaign_folders:
        isCExist = os.path.exists(os.path.join(data_genpath, folder))
        # print(os.path.join(rel_path,folder), ":", isCExist)
        if isCExist:
            exist_folder.append(folder)
    if len(exist_folder) > 0:
        FOLDER_LIST = ", ".join(exist_folder)
        print_error = print_error.replace("FOLDER_LIST", FOLDER_LIST)
        print(print_error)
        exit_code = 1
   
    return exit_code


default_config = {
    "application": None,
    "application_category": None,
    "dataset": None,
    "dataset_pca": None,
    "train_folder": None,
    "model_commons_filename": None,
    "project_account": None
}
