from DataPreprocessor.DataPreprocessor import DataPreprocessor
from DataScraper.DataScraper import DataScraper
from ModelTrainer.ModelTrainer import ModelTrainer
from Predictor.Predictor import Predictor
from config_tools import configuration_check, create_application_structure, validate_config, save_application_config, check_pre_generate

import argparse
import json, sys, os
import platform

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=None, type=str, help="json config file for HARP")
    parser.add_argument('--module', default=None, type=str, help="[optional] module to run")
    args = parser.parse_args()
    return args


def launch_data_scraper(config: dict):
    module = DataScraper(config)
    module.execute()
    
    
def launch_data_preprocessor(config: dict):
    module = DataPreprocessor(config)
    dataset = module.execute()
    return dataset
    
    

def launch_model_trainer(config: dict):
    module = ModelTrainer(config)
    module.execute()

def launch_predictor(config: dict):
    module = Predictor(config)
    module.execute()

def run_all(config: dict):
    launch_data_scraper(config)
    launch_data_preprocessor(config)
    launch_model_trainer(config)
    launch_predictor(config)

def main(module: str, config: dict):
    print("\t\t\t================= Executing Module: ", module)
    if module is None:
        run_all(config)
    
    if module == "data_scraper":
        launch_data_scraper(config)
    
    elif module == "data_preprocessor":
        launch_data_preprocessor(config)

    elif module == "model_trainer":
        launch_model_trainer(config)

    elif module == "predictor":
        launch_predictor(config)

    else:
        print(f'ERROR: Tried to launch invalid pipeline module `{module}`')


if __name__ == "__main__":
    #TODO allows modules
    args = parse_args()
    module, config_path = args.module, args.config
    if os.path.isfile(config_path) != True:
        print(f"ERROR: invalid path to pipeline config")
    

    with open(config_path, 'r') as file:
        config = json.load(file)


    if args.module =="configuration_check":  
        exit_status = configuration_check(config, args.config)
        if exit_status == 0:
            #validate config
            is_valid = validate_config(config)
            if is_valid != True: 
                print("ERROR: Invalid pipeline configuration - Application and category missing")
                exit()
        else:
            print("ERROR: Invalid pipeline configuration - Application folder not found")
            exit()
        
     
    elif args.module =="generate_checks":  
        exit_status = check_pre_generate(config, args.config)
        if exit_status == 0:
            #validate config
            is_valid = validate_config(config)
            if is_valid != True: 
                print("ERROR: Invalid pipeline configuration")
                exit()
        
        
    else: 
        # Step 1: create the folder structure
        pipeline_config = create_application_structure(config)
        config["pipeline_config"]=pipeline_config
        
        main(module, config)
    
        #save_application_config(config["application_config"])
    
    print("EXIT CODE: 0")