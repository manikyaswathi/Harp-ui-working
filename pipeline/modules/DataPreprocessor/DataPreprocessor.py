from PipelineModule import PipelineModule
from .BasicAppPreprocessor import preprocess as basic_app_preprocess

import os


class DataPreprocessor(PipelineModule):
    def __init__(self, config):
        super().__init__()
        self.application = str.lower(config["application"])
        self.application_category = str.lower(config["application_category"])
        self.config = config


    def set_should_train(self, num_rows):
        metadata = self.config["application_config"]
        old_num_rows = metadata["num_rows"] or 0.01 #to avoid none and division by zero
        metadata["num_rows"] = num_rows
        change = float(num_rows - old_num_rows) / old_num_rows
        if change >= 0.15:
            metadata["train"] = True


    def write_csv(self, dataset):
        application_config = self.config["pipeline_config"]
        dataset.to_csv(application_config["dataset_pca"], header = True, index = False)

        
        
    def get_dataset_list(self):
        application_config = self.config["pipeline_config"] #pipeline_config
        train_dataset = application_config["dataset"]
        return [train_dataset]


    def execute(self):
        #TODO get dataset list
        if self.application_category == "basic":
            dataset_list = self.get_dataset_list()
            dataset = basic_app_preprocess(dataset_list)
            self.write_csv(dataset)

        else:
            print(f"Invalid application `{self.application}` passed to data preprocessor")

        print("INFO: DataPreprocessor completed successfully")

        return dataset
