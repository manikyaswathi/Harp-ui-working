import pandas as pd
import numpy as np

from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

NUMBERIC_TYPES=['int64', 'float64']

def write_csv(dataset, filename: str):
    dataset.to_csv(filename, header = True, index = False)

def remove_outliers(dataset):
    # Removing Outliers:
    all_data_final = dataset
    scaler = StandardScaler()
    scaler.fit(all_data_final)
    temp = scaler.transform(all_data_final)
    # print(np.abs(stats.zscore(df)))
    all_data_final_noOut = all_data_final[(np.abs(temp) < 3).all(axis=1)]
    return all_data_final_noOut


def pca(dataset, X_cols, Y_col):

    X_Features = dataset[X_cols]
    x = X_Features.values
    X_Features = StandardScaler().fit_transform(x)
   
    no_of_fetures = min(len(X_cols), X_Features.shape[0])
    pca_n = PCA(n_components=no_of_fetures, random_state=2048)

    
    pca_n.fit(X_Features)
    X_Features_pca = pca_n.transform(X_Features)
        
    df_pca = pd.DataFrame(X_Features_pca)
    df_pca['walltime'] = dataset[Y_col].values

    return df_pca
    
    
def preprocess(dataset_list: list):
    data_l= dataset_list

    data = None
    for fi in dataset_list:
        data = pd.read_csv(fi)
    

    delete_cols = ['run_config', 'sys_name', 'sys_processor']
    target_col = 'walltime'
    all_columns = data.columns
    cols_needed = [i for i in all_columns if i not in delete_cols and i != target_col]
    
    map_rev={"cat":[], "ord":[]}
    data = data[cols_needed+[target_col]]
    data[target_col] = round(data[target_col], 3)
    for (columnName, columnData) in data.items(): #data.iteritems():
        if columnData.dtype not in NUMBERIC_TYPES:
            if columnData.dtype == 'bool':
                data['Education'].replace([False, True], [0, 1], inplace=True)
            if columnData.dtype == 'object':
                tmp = columnData.values.tolist()
                tmp = list(set(tmp))
                ord_v = list(range(1,len(tmp)+1,1))
                print("FOR", columnName, "FORM-TO", tmp, ord_v)
                data[columnName].replace(tmp, ord_v, inplace=True)
                if columnName == 'run_type':
                    map_rev["cat"]=tmp
                    map_rev["ord"]=ord_v
                                   
    order_data = []
    test_data_ord = -1
    for cat, ordi in zip(map_rev["cat"], map_rev["ord"]):
        if cat == "SD":
            order_data.append(ordi)
        if cat == "FS":
            order_data.append(ordi)
        if cat == "test_data":
            test_data_ord = ordi
    
    del_after_sort = ['run_type']
    data_with_outliers = data[(data['run_type'] == order_data[0]) | (data['run_type'] == order_data[1])]
    data_merge = data_with_outliers[del_after_sort]
    cols_needed_pca = [i for i in cols_needed if i not in del_after_sort]
    data_with_outliers = data_with_outliers[cols_needed_pca+[target_col]]
    data_with_no_outliers = remove_outliers(data_with_outliers)
    data_outliers_train = pd.concat([data_with_no_outliers, data_merge], axis=1)
    randColumn = data_outliers_train.columns[1]
    data_outliers_train = data_outliers_train.dropna()
    
    data_with_tests = data[(data['run_type'] == test_data_ord)]
    data_with_tests = data_with_tests[cols_needed+[target_col]]
    
    data_pre_pca = pd.concat([data_outliers_train, data_with_tests], ignore_index=True)
    data_pre_pca = data_pre_pca.reset_index()

    # Replace back the run type
    data_pre_pca['run_type'].replace(map_rev['ord'], map_rev['cat'], inplace=True)
    cols_needed_pca = [i for i in cols_needed_pca if i != 'uniq_id']
    data_merge = data_pre_pca[del_after_sort+['uniq_id']]

    data_pca = pca(data_pre_pca, cols_needed_pca, target_col)
    final_df = pd.concat([data_pca, data_merge], axis=1)
    return final_df





def preprocess_old(dataset_list: list):
    data_l= dataset_list

    data = None
    for fi in dataset_list:
        data = pd.read_csv(fi)


    all_columns = data.columns
    delete_cols = ['run_config', 'sys_name', 'sys_processor']
    target_col = 'walltime'
    
    cols_needed = [i for i in all_columns if i not in delete_cols and i != target_col]
    
    map_rev={"cat":[], "ord":[]}
    
    data = data[cols_needed+[target_col]]
    data[target_col] = round(data[target_col], 3)
    
    for (columnName, columnData) in data.items():
        if columnData.dtype not in NUMBERIC_TYPES:
            if columnData.dtype == 'bool':
                data['Education'].replace([False, True], [0, 1], inplace=True)
            if columnData.dtype == 'object':
                tmp = columnData.values.tolist()
                tmp = list(set(tmp))
                ord_v = list(range(1,len(tmp)+1,1))
                data[columnName].replace(tmp, ord_v, inplace=True)
                if columnName == 'run_type':
                    print("FOR", columnName, "FORM-TO", tmp, ord_v)
                    map_rev["cat"]=tmp
                    map_rev["ord"]=ord_v
    
    order_data =[]
    for cat, ord in zip(map_rev["cat"], map_rev["ord"]):
        if cat == "SD":
            order_data.append(ord)
        if cat == "FS":
            order_data.append(ord)
    
    data_with_ouliers = data[(data['run_type'] == order_data[0]) | (data['run_type'] == order_data[1])] 
    
    data_no_outliers = remove_outliers(data_with_ouliers)
    data_no_outliers = data_no_outliers.reset_index()
    
    del_after_sort = ['run_type']
    data_no_outliers['run_type'].replace(map_rev['ord'], map_rev['cat'], inplace=True)
    data_merge = data_no_outliers[del_after_sort]
    cols_needed_pca = [i for i in cols_needed if i not in del_after_sort]
    data_no_outliers = data_no_outliers[cols_needed_pca+[target_col]]
    
    df_pca = pca(data_no_outliers, cols_needed_pca, target_col)
    
    final_df = pd.concat([df_pca, data_merge], axis=1)
    
    tmp = final_df['run_type']
    tmp = list(set(tmp))
    print("THIS SHIFT", tmp)



    return final_df


